from __future__ import annotations
from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, 
    Type, Hashable, Generator, Union, Protocol
)

from dataclasses import dataclass, replace
from syncraft.ast import ThenKind, Then, Choice, Many, ChoiceKind, SyncraftError, CallWith
from syncraft.cache import Cache, InProgress, LeftRecursionError, Right, Left, Incomplete, Either
from syncraft.constraint import Bindable
from functools import cached_property
import re

from rich import print







S = TypeVar('S', bound=Bindable)
    
A = TypeVar('A')  # Result type
B = TypeVar('B')  # Mapped result type




@dataclass(frozen=True)
class Error:
    this: Any
    message: Optional[str] = None
    error: Optional[Any] = None    
    state: Optional[Any] = None
    committed: bool = False
    previous: Optional[Error] = None
    
    def push( self, 
                *,
                this: Any, 
                message: Optional[str] = None,
                error: Optional[Any] = None, 
                state: Optional[Any] = None) -> Error:
        return Error(
            this=this,
            error=error,
            message=message or str(error),
            state=state,
            previous=self
        )
    def to_list(self)->List[Error]:
        lst = []
        current: Optional[Error] = self
        while current is not None:
            lst.append(current)
            current = current.previous
        return lst

YieldChannelType = Incomplete[S] | InProgress[Either[Any, Tuple[A, S]]]
SendChannelType = Union[S, Either[Any, Tuple[A, S]]]
@dataclass(frozen=True)        
class Algebra(Generic[A, S]):
######################################################## shared among all subclasses ########################################################
    run_f: Callable[[S, Cache[S, Either[Any, Tuple[A, S]]]], Generator[YieldChannelType, SendChannelType, Either[Any, Tuple[A, S]]]] 
    _name: str | Callable[[], str]
    @classmethod
    def state(cls, **kwargs:Any)->Optional[S]: 
        return None
        
    def named(self, name: str) -> Algebra[A, S]:
        return replace(self, _name=name)

    @property
    def name(self) -> str:
        if isinstance(self._name, str):
            return self._name
        elif callable(self._name):
            return self._name()
        else:
            return self.__class__.__name__
        
    def __repr__(self) -> str:
        return self.name
    
    def __str__(self) -> str:
        return self.__repr__()

    @cached_property
    def hashable(self)->Hashable:
        return frozenset({'name': self.name, 'run_f': self.run_f})


    def __call__(self, 
                 input: S, 
                 cache: Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                        SendChannelType, 
                                                                        Either[Any, Tuple[A, S]]]:
        return self.run(input, cache=cache)

    def run(self, 
            input: S, 
            cache: Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                   SendChannelType, 
                                                                   Either[Any, Tuple[A, S]]]:
        try:
            return (yield from cache.gen(self.run_f, input))
        except LeftRecursionError as e:
            if e.offending is self.run_f or len(e.stack) == 0:
                e = e.push(f"\u25cf {self.name}")
            else:
                e = e.push(self.name)
            raise e
        

    def as_(self, typ: Type[B])->B:
        return cast(typ, self) # type: ignore
        
    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[A, S]]) -> Algebra[A, S]:
        def algebra_lazy_run(input: S, 
                             cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                                   SendChannelType, 
                                                                                   Either[Any, Tuple[A, S]]]:
            alg = thunk()
            result = yield from alg.run(input, cache)
            return result
        return cls(algebra_lazy_run, _name=lambda: f"{cls.__name__}.lazy(...)")
    
    @classmethod
    def fail(cls, error: Any) -> Algebra[Any, S]:
        def fail_run(input: S, 
                     cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                           SendChannelType, 
                                                                           Either[Any, Tuple[A, S]]]:
            return (yield from cache.return_value(Left(Error(
                error=error,
                this=cls,
                state=input
            )), input))

        return cls(fail_run, _name=cls.__name__ + '.fail')
    
    @classmethod
    def success(cls, value: Any) -> Algebra[Any, S]:
        def success_run(input: S, 
                        cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                              SendChannelType, 
                                                                              Either[Any, Tuple[A, S]]]:
            return (yield from cache.return_value(Right((value, input)), input))
        return cls(success_run, _name=cls.__name__ + '.success')
    
    @classmethod
    def factory(cls,
                name: str, 
                *args: Any, 
                **kwargs: Any) -> Algebra[A, S]:
        """Call a named class method to construct an algebra.

        Args:
            name: Name of a classmethod/staticmethod on this class.
            *args: Positional args passed to the method.
            **kwargs: Keyword args passed to the method.

        Returns:
            The algebra returned by the method.

        Raises:
            ValueError: If the method is missing or not callable.
        """
        method = getattr(cls, name, None)
        if method is None or not callable(method):
            raise SyncraftError(f"Method {name} is not defined in {cls.__name__}", offending=method, expect='callable')
        result = CallWith(method, *args, **kwargs)()
        return cast(Algebra[A, S], result)
    
    def cut(self) -> Algebra[A, S]:
        """Commit this branch by marking failures as committed.

        Converts downstream errors into committed errors (``committed=True``),
        which prevents alternatives from being tried in ``or_else``.

        Returns:
            An algebra that commits errors produced by this one.
        """
        def commit_error(e: Any) -> Error:
            match e:
                case Error():
                    return replace(e, committed=True)
                case _:
                    return Error(
                        error=e,
                        this=self,
                        committed=True
                    )
        return self.map_error(commit_error)

    def on_fail(self, 
                func: Callable[
                    [
                        Algebra[A, S], 
                        S, 
                        Left[Any, Tuple[A, S]], 
                        Any
                    ], 
                        Either[Any, Tuple[B, S]]
                    ], 
                ctx: Optional[Any] = None) -> Algebra[A | B, S]:
        """Run a handler only when this algebra fails.

        Args:
            func: Callback ``(alg, input, left, ctx) -> Either`` executed on failure.
            ctx: Optional context object passed to the callback.

        Returns:
            An algebra that intercepts failures and can recover or transform them.
        """
        assert callable(func), "func must be callable"
        def fail_run(input: S, 
                     cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                           SendChannelType, 
                                                                           Either[Any, Tuple[A|B, S]]]:
            result = yield from self.run(input, cache)
            if isinstance(result, Left):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result, ctx))
            else:
                return cast(Either[Any, Tuple[A | B, S]], result)
        return replace(self, run_f=fail_run) # type: ignore
        

    def on_success(self, 
                    func: Callable[
                        [
                            Algebra[A, S], 
                            S, 
                            Right[Any, Tuple[A, S]], 
                            Any
                        ], 
                            Either[Any, Tuple[B, S]]
                        ], 
                    ctx: Optional[Any] = None) -> Algebra[A | B, S]:
        """Run a handler only when this algebra succeeds.

        Args:
            func: Callback ``(alg, input, right, ctx) -> Either`` executed on success.
            ctx: Optional context object passed to the callback.

        Returns:
            An algebra that can transform or post-process successes.
        """
        assert callable(func), "func must be callable"
        def success_run(input: S, 
                        cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                              SendChannelType, 
                                                                              Either[Any, Tuple[A|B, S]]]:
            result = yield from self.run(input, cache)
            if isinstance(result, Right):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result, ctx))
            else:
                return cast(Either[Any, Tuple[A | B, S]], result)
        return replace(self, run_f=success_run) # type: ignore
        


######################################################## map on state ###########################################
    def map_state(self, f: Callable[[S], S]) -> Algebra[A, S]:
        """Map the input state before running this algebra.

        Args:
            f: ``S -> S`` function applied to the state prior to running.

        Returns:
            An algebra that runs with ``f(state)``.
        """
        def map_state_run(state: S, 
                          cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                                SendChannelType, 
                                                                                Either[Any, Tuple[A, S]]]:
            result = yield from self.run(f(state), cache)
            return result
        return replace(self, run_f=map_state_run) 
        


######################################################## fundamental combinators ############################################    
    def map(self, f: Callable[[A], B]) -> Algebra[B, S]:
        """Transform the success value, leaving the state unchanged.

        Args:
            f: Mapper from ``A`` to ``B``.

        Returns:
            An algebra that yields ``B`` with the same resulting state.
        """
        def map_run(input: S, 
                    cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                          SendChannelType, 
                                                                          Either[Any, Tuple[B, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Right):
                return Right((f(parsed.value[0]), parsed.value[1]))            
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        return replace(self, run_f=map_run) # type: ignore

        
    def bimap(self, f: Callable[[A], B], i: Callable[[B], A]) -> Algebra[B, S]:
        """Bidirectionally map values with an inverse, updating the state.

        Applies ``f`` to the success value. The state is pre-mapped with the
        inverse ``i`` via the state's ``map`` method to preserve round-trips.

        Args:
            f: Forward mapping ``A -> B``.
            i: Inverse mapping ``B -> A`` applied to the state.

        Returns:
            An algebra producing ``B`` while keeping value/state alignment.
        
        Note:
            Different subclass of Algebra can override state.map method to change 
            the behavior of bimap. For example, ParserState.map will return the
            state unchanged, and GenState.map will apply the inverse map and update 
            the next AST node for generation.
        """
        return self.map(f).map_state(lambda s: s.map(i))

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Algebra[A, S]:
        """Transform the error payload when this algebra fails.

        Args:
            f: Function applied to the error payload inside ``Left``.

        Returns:
            An algebra that preserves successes and maps failures.
        """
        def map_error_run(input: S, 
                          cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                                SendChannelType, 
                                                                                Either[Any, Tuple[A, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Left):
                return Left(f(parsed.value))
            else:
                return parsed
        return replace(self, run_f=map_error_run) 

    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Algebra[B, S]:
        """Chain computations where the next algebra depends on the value.

        On success, passes the produced value to ``f`` to obtain the next
        algebra, then runs it with the resulting state.

        Args:
            f: Mapper from a value to the next algebra.

        Returns:
            An algebra yielding the result of the chained computation.
        """
        def flat_map_run(input: S, 
                         cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                               SendChannelType, 
                                                                               Either[Any, Tuple[B, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Right):
                result = yield from f(parsed.value[0]).run(parsed.value[1], cache)  
                return result
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        return replace(self, run_f=flat_map_run) # type: ignore

    def map_all(self, f: Callable[[A, S], Tuple[B, S]]) -> Algebra[B, S]:
        """Map both the produced value and the resulting state on success.

        Args:
            f: Function mapping ``(value, state)`` to ``(new_value, new_state)``.

        Returns:
            An algebra producing the transformed value and state.
        """
        def map_all_f(a : A) -> Algebra[B, S]:
            def map_all_run_f(input:S, 
                              cache:Cache[S, Either[Any, Tuple[A, S]]]) -> Generator[YieldChannelType, 
                                                                                  SendChannelType, 
                                                                                  Either[Any, Tuple[B, S]]]:
                yield from ()
                return Right(f(a, input))
            return replace(self, run_f=map_all_run_f) # type: ignore
        return self.flat_map(map_all_f)


    
    def or_else(self: Algebra[A, S], other: Algebra[B, S]) -> Algebra[Choice[A, B], S]:
        def or_else_run(input: S, 
                        cache:Cache[S, Either[Any, Tuple[A, S]]]) -> Generator[YieldChannelType, 
                                                                            SendChannelType, 
                                                                            Either[Any, Tuple[Choice[A, B], S]]]:
            try:
                gen = self.run(input, cache)
                send_value = None
                while True:
                    left = gen.send(send_value) 
                    match left:
                        case InProgress(payload = _):
                            other_result = yield from other.run(input, cache)
                            match other_result:
                                case Right((other_value, other_state)) as right:
                                    send_value = right
                                    continue
                                case Left(other_err):
                                    return Left(other_err)
                            raise SyncraftError(f"Unexpected result type from {other}", offending=other_result, expect=(Left, Right))
                        case _ as anything:
                            send_value = yield anything
            except StopIteration as e:
                match e.value:
                    case Right((value, state)) :
                        return Right((Choice(kind=ChoiceKind.LEFT, value=value), state))            
                    case Left(err):
                        if isinstance(err, Error):
                            if err.committed:
                                return Left(replace(err, committed=False))
                        other_result = yield from other.run(input, cache)
                        match other_result:
                            case Right((other_value, other_state)):
                                return Right((Choice(kind=ChoiceKind.RIGHT, value=other_value), other_state))
                            case Left(other_err):
                                return Left(other_err)
                        raise SyncraftError(f"Unexpected result type from {other}", offending=other_result, expect=(Left, Right))
                raise SyncraftError(f"Unexpected result type from {self}", offending=e.value, expect=(Left, Right))
        return replace(self, run_f=or_else_run, _name=f"({self.name} | {other.name})") # type: ignore
        

    def then_both(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        """Sequence two algebras and keep both values.

        Returns a ``Then(kind=BOTH)`` holding the left and right values.

        Args:
            other: The algebra to run after this one.

        Returns:
            An algebra producing ``Then(left, right, kind=BOTH)``.
        """
        def then_both_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.BOTH)
            return other.map(combine)
        pattern = re.compile(r'\s')
        self_name = self.name.strip() 
        self_name = f"({self_name})" if bool(pattern.search(self_name)) else self_name
        other_name = other.name.strip()
        other_name = f"({other_name})" if bool(pattern.search(other_name)) else other_name
        name = f"{self_name} + {other_name}"
        
        return self.flat_map(then_both_f).named(name)
        

    def then_left(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        """Sequence two algebras, keep the left value in the result.

        Produces ``Then(kind=LEFT)`` with both values attached.

        Args:
            other: The algebra to run after this one.

        Returns:
            An algebra producing ``Then(left, right, kind=LEFT)``.
        """
        def then_left_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.LEFT)
            return other.map(combine)
        pattern = re.compile(r'\s')
        self_name = self.name.strip() 
        self_name = f"({self_name})" if bool(pattern.search(self_name)) else self_name
        other_name = other.name.strip()
        other_name = f"({other_name})" if bool(pattern.search(other_name)) else other_name
        name = f"{self_name} // {other_name}"
        
        return self.flat_map(then_left_f).named(name)
        

    def then_right(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        """Sequence two algebras, keep the right value in the result.

        Produces ``Then(kind=RIGHT)`` with both values attached.

        Args:
            other: The algebra to run after this one.

        Returns:
            An algebra producing ``Then(left, right, kind=RIGHT)``.
        """
        def then_right_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.RIGHT)
            return other.map(combine)
        pattern = re.compile(r'\s')
        self_name = self.name.strip() 
        self_name = f"({self_name})" if bool(pattern.search(self_name)) else self_name
        other_name = other.name.strip()
        other_name = f"({other_name})" if bool(pattern.search(other_name)) else other_name
        name = f"{self_name} >> {other_name}"
        
        return self.flat_map(then_right_f).named(name)
        

    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Many[A], S]:
        """Repeat this algebra and collect results into ``Many``.

        Repeats greedily until failure or no progress. Enforces cardinality
        constraints. If ``at_most`` is ``None``, there is no upper bound.

        Args:
            at_least: Minimum number of matches required (>= 1).
            at_most: Optional maximum number of matches.

        Returns:
            On success, ``Right((Many(values), state))``.
        Note:
            at_most, if given, is enforced strictly, more than at_most matches 
            is treated as an error.
        Raises:
            ValueError: If bounds are invalid (e.g., ``at_least<=0`` or
            ``at_most<at_least``).
        """
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offending=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        def many_run(input: S, 
                     cache:Cache[S, Either[Any, Tuple[A, S]]]) -> Generator[YieldChannelType, 
                                                                         SendChannelType, 
                                                                         Either[Any, Tuple[Many[A], S]]]:
            ret: List[A] = []
            current_input = input
            inner_error = None
            while True:
                result = yield from self.run(current_input, cache)
                match result:
                    case Left(E):
                        inner_error = Left(E)
                        break
                    case Right((value, next_input)):
                        if next_input == current_input:
                            break  # No progress, stop to avoid infinite loop
                        else:
                            ret.append(value)
                        current_input = next_input
                        if at_most is not None and len(ret) > at_most:
                            return Left(Error(
                                    message=f"Expected at most {at_most} matches, got {len(ret)}",
                                    this=self,
                                    state=current_input
                                )) 
            if len(ret) < at_least:
                if inner_error is not None:
                    return inner_error
                else:
                    return Left(Error(
                            message=f"Expected at least {at_least} matches, got {len(ret)}",
                            this=self,
                            state=current_input
                        )) 
            return Right((Many(value=tuple(ret)), current_input))
        return replace(self, run_f=many_run, _name=f'*({self.name})') # type: ignore

    


