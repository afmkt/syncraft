from __future__ import annotations
from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, 
    Dict, Type, Hashable, Generator
)

from dataclasses import dataclass, replace
from syncraft.ast import ThenKind, Then, Choice, Many, ChoiceKind, shallow_dict, SyncraftError
from syncraft.cache import Cache
from syncraft.constraint import Bindable
from rich import print


S = TypeVar('S', bound=Bindable)
    
A = TypeVar('A')  # Result type
B = TypeVar('B')  # Mapped result type


L = TypeVar('L')  # Left type for combined results
R = TypeVar('R')  # Right type for combined results

class Either(Generic[L, R]):
    def is_left(self) -> bool:
        return isinstance(self, Left)
    def is_right(self) -> bool:
        return isinstance(self, Right)

@dataclass(frozen=True)
class Left(Either[L, R]):
    value: Optional[L] = None

@dataclass(frozen=True)
class Right(Either[L, R]):
    value: R


@dataclass(frozen=True)
class Incomplete(Generic[S]):
    state: S

@dataclass(frozen=True)
class Error:
    this: Any
    message: Optional[str] = None
    error: Optional[Any] = None    
    state: Optional[Any] = None
    committed: bool = False
    fatal: bool = False
    previous: Optional[Error] = None
    
    def attach( self, 
                *,
                this: Any, 
                msg: Optional[str] = None,
                err: Optional[str] = None, 
                state: Optional[Any] = None) -> Error:
        return Error(
            this=this,
            error=err,
            message=msg or str(err),
            state=state,
            previous=self
        )
    def to_list(self)->List[Dict[str, Any]]:
        lst = []
        current: Optional[Error] = self
        while current is not None:
            d = shallow_dict(current)
            lst.append({k:v for k,v in d.items() if v is not None and k != 'previous'})
            current = current.previous
        return lst


@dataclass(frozen=True)        
class Algebra(Generic[A, S]):
######################################################## shared among all subclasses ########################################################
    run_f: Callable[[S, bool], Generator[Incomplete[S], S, Either[Any, Tuple[A, S]]]] 
    name: Hashable
    cache: Cache[ S, Either[Any, Tuple[A, S]] ]

    @classmethod
    def state(cls, **kwargs:Any)->Optional[S]: 
        return None
        
    def named(self, name: Hashable) -> 'Algebra[A, S]':
        return replace(self, name=name)
        
    def __call__(self, input: S, use_cache: bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A, S]]]:
        return self.run(input, use_cache=use_cache)

    def run(self, input: S, use_cache: bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A, S]]]:
        return (yield from self.cache.gen(self.run_f, input, use_cache))
        

    def as_(self, typ: Type[B])->B:
        return cast(typ, self) # type: ignore
        
    @classmethod
    def lazy(cls, 
             thunk: Callable[[], Algebra[A, S]], 
             *, 
             cache: Cache) -> Algebra[A, S]:
        def algebra_lazy_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A, S]]]:
            alg = thunk()
            # print('--' * 20, "Algebra.lazy.algebra_lazy_run", '--' * 20)
            # print('thunk', thunk, id(thunk))
            # print('input', input, id(input))
            # print('alg', alg, id(alg))
            result = yield from alg.run(input, use_cache)
            return result
        return cls(algebra_lazy_run, name=cls.__name__ + '.lazy', cache=cache)
    
    @classmethod
    def fail(cls, 
             error: Any,
             *,
             cache: Cache) -> Algebra[Any, S]:
        def fail_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A, S]]]:
            yield from ()
            return Left(Error(
                error=error,
                this=cls,
                state=input
            ))
        return cls(fail_run, name=cls.__name__ + '.fail', cache=cache)
    
    @classmethod
    def success(cls, 
                value: Any, 
                *, 
                cache: Cache) -> Algebra[Any, S]:
        def success_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A, S]]]:
            yield from ()
            return Right((value, input))
        return cls(success_run, name=cls.__name__ + '.success', cache=cache)
    
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
        return cast(Algebra[A, S], method(*args, **kwargs))

    def fatal(self) -> Algebra[A, S]:
        """Commit this branch by marking failures as fatal.

        Converts downstream errors into fatal errors (``fatal=True``),
        which prevents alternatives from being tried in ``or_else``.

        Returns:
            An algebra that fails fatally on errors produced by this one.
        """
        def fail_all_error(e: Any) -> Error:
            match e:
                case Error():
                    return replace(e, fatal=True)
                case _:
                    return Error(
                        error=e,
                        this=self,
                        fatal=True
                    )
        return self.map_error(fail_all_error)

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
        def fail_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A|B, S]]]:
            result = yield from self.run(input, use_cache)
            if isinstance(result, Left):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result, ctx))
            else:
                return cast(Either[Any, Tuple[A | B, S]], result)
        return self.__class__(fail_run, name=self.name, cache=self.cache) # type: ignore

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
        def success_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A|B, S]]]:
            result = yield from self.run(input, use_cache)
            if isinstance(result, Right):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result, ctx))
            else:
                return cast(Either[Any, Tuple[A | B, S]], result)
        return self.__class__(success_run, name=self.name, cache=self.cache) # type: ignore


######################################################## map on state ###########################################
    def map_state(self, f: Callable[[S], S]) -> Algebra[A, S]:
        """Map the input state before running this algebra.

        Args:
            f: ``S -> S`` function applied to the state prior to running.

        Returns:
            An algebra that runs with ``f(state)``.
        """
        def map_state_run(state: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A, S]]]:
            result = yield from self.run(f(state), use_cache)
            return result
        return self.__class__(map_state_run, name=self.name, cache=self.cache) 


######################################################## fundamental combinators ############################################    
    def map(self, f: Callable[[A], B]) -> Algebra[B, S]:
        """Transform the success value, leaving the state unchanged.

        Args:
            f: Mapper from ``A`` to ``B``.

        Returns:
            An algebra that yields ``B`` with the same resulting state.
        """
        def map_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[B, S]]]:
            parsed = yield from self.run(input, use_cache)
            if isinstance(parsed, Right):
                return Right((f(parsed.value[0]), parsed.value[1]))            
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        return self.__class__(map_run, name=self.name, cache=self.cache)  # type: ignore

        
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
        def map_error_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[A, S]]]:
            parsed = yield from self.run(input, use_cache)
            if isinstance(parsed, Left):
                return Left(f(parsed.value))
            else:
                return parsed
        return self.__class__(map_error_run, name=self.name, cache=self.cache)  

    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Algebra[B, S]:
        """Chain computations where the next algebra depends on the value.

        On success, passes the produced value to ``f`` to obtain the next
        algebra, then runs it with the resulting state.

        Args:
            f: Mapper from a value to the next algebra.

        Returns:
            An algebra yielding the result of the chained computation.
        """
        def flat_map_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[B, S]]]:
            parsed = yield from self.run(input, use_cache)
            if isinstance(parsed, Right):
                result = yield from f(parsed.value[0]).run(parsed.value[1], use_cache)  
                return result
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        return self.__class__(flat_map_run, name=self.name, cache=self.cache)  # type: ignore

    def map_all(self, f: Callable[[A, S], Tuple[B, S]]) -> Algebra[B, S]:
        """Map both the produced value and the resulting state on success.

        Args:
            f: Function mapping ``(value, state)`` to ``(new_value, new_state)``.

        Returns:
            An algebra producing the transformed value and state.
        """
        def map_all_f(a : A) -> Algebra[B, S]:
            def map_all_run_f(input:S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[B, S]]]:
                yield from ()
                return Right(f(a, input))
            return self.__class__(map_all_run_f, name=self.name, cache=self.cache) # type: ignore
        return self.flat_map(map_all_f)


    
    def or_else(self: Algebra[A, S], other: Algebra[B, S]) -> Algebra[Choice[A, B], S]:
        """Try this algebra; if it fails uncommitted, try ``other``.

        If the failure is committed (``committed=True``), the alternative is
        not attempted and the error is propagated.

        Args:
            other: Fallback algebra to try from the same input state.

        Returns:
            An algebra producing ``Choice.LEFT`` for this success or
            ``Choice.RIGHT`` for the other's success.
        """
        def or_else_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[Choice[A, B], S]]]:
            self_result = yield from self.run(input, use_cache)
            match self_result:
                case Right((value, state)):
                    return Right((Choice(kind=ChoiceKind.LEFT, value=value), state))
                case Left(err):
                    if isinstance(err, Error):
                        if err.fatal:
                            return Left(err)
                        elif err.committed:
                            return Left(replace(err, committed=False))
                    other_result = yield from other.run(input, use_cache)
                    match other_result:
                        case Right((other_value, other_state)):
                            return Right((Choice(kind=ChoiceKind.RIGHT, value=other_value), other_state))
                        case Left(other_err):
                            return Left(other_err)
                    raise SyncraftError(f"Unexpected result type from {other}", offending=other_result, expect=(Left, Right))
            raise SyncraftError(f"Unexpected result type from {self}", offending=self_result, expect=(Left, Right))
        return self.__class__(or_else_run, name=f'{self.name} | {other.name}', cache=self.cache | other.cache)  # type: ignore

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
        ret = self.flat_map(then_both_f).named(f'{self.name} + {other.name}')
        return replace(ret, cache=self.cache | other.cache)  

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
        ret = self.flat_map(then_left_f).named(f'{self.name} // {other.name}')
        return replace(ret, cache=self.cache | other.cache)  

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
        ret = self.flat_map(then_right_f).named(f'{self.name} >> {other.name}')
        return replace(ret, cache=self.cache | other.cache)  

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
        def many_run(input: S, use_cache:bool) -> Generator[Incomplete[S], S, Either[Any, Tuple[Many[A], S]]]:
            ret: List[A] = []
            current_input = input
            while True:
                result = yield from self.run(current_input, use_cache)
                match result:
                    case Left(_):
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
                return Left(Error(
                        message=f"Expected at least {at_least} matches, got {len(ret)}",
                        this=self,
                        state=current_input
                    )) 
            return Right((Many(value=tuple(ret)), current_input))
        return self.__class__(many_run, name=f'*({self.name})', cache=self.cache) # type: ignore

    


