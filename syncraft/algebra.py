from __future__ import annotations
from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, Mapping,
    Type, Generator, Union, Hashable
)
from syncraft.ast import AST
from dataclasses import dataclass, replace
from syncraft.ast import ThenKind, Lazy, Then, Choice, Many, ChoiceKind, SyncraftError
from syncraft.cache import Cache, LeftRecursionError, Right, Left, Incomplete, Either
from syncraft.constraint import Bindable


S = TypeVar('S', bound=Bindable)    
A = TypeVar('A')  # Result type
B = TypeVar('B')  # Mapped result type

SYNCRAFT_CONFIG_KEY = "__syncraft_config__"



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
            message=message,
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
    @property
    def deepest(self) -> Error:
        current: Error = self
        while current.previous is not None:
            current = current.previous
        return current

YieldChannelType = Incomplete[S] 
SendChannelType = Union[S, Either[Any, Tuple[A, S]]]
@dataclass(frozen=True)        
class Algebra(Generic[A, S]):
######################################################## shared among all subclasses ########################################################
    run_f: Callable[[S, Cache[S, Either[Any, Tuple[A, S]]]], Generator[YieldChannelType, SendChannelType, Either[Any, Tuple[A, S]]]]
    _name: Hashable | None = None
    
    def config(self) -> dict[str, Any]:
        cfg = getattr(self, SYNCRAFT_CONFIG_KEY, {})
        return dict(cfg) if isinstance(cfg, Mapping) else {}

    def named(self, name: Hashable) -> Algebra[A, S]:
        return replace(self, _name=name)


    @property
    def name(self) -> str:    
        return str(self._name)
    
    
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
            if cache is None:
                return (yield from self.run_f(input, cache))
            else:
                result = (yield from cache.exec(self.run_f, input))
                match result:
                    case Left(Error() as e):
                        return Left(e.push(this=self, state=input))
                    case _:
                        return result
        except LeftRecursionError as e:
            if e.offender is self.run_f  or len(e.stack) == 0:
                e = e.push(f"\u25cf {self.name}")
            else:
                e = e.push(self.name)
            raise e
        

    def as_(self, typ: Type[B])->B:
        return cast(typ, self) # type: ignore
        
    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[A, S]]) -> Algebra[A, S]:
        def algebra_lazy_run(input: S,
                             cache: Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType,
                                                                                         SendChannelType,
                                                                                         Either[Any, Tuple[Any, S]]]:
            # Defer acquiring the underlying algebra until invocation time.
            alg = thunk()
            cache.enter(algebra_lazy_run, input, inner=alg.run_f)
            try:
                result = (yield from alg.run(input, cache))
                match result:
                    case Left(err):
                        return Left(err)
                    case Right((value, state)):
                        return Right((Lazy(value), state))
                    case _:
                        raise SyncraftError(f"Unexpected result type from lazy algebra {alg}", offender=result)
            finally:
                cache.leave()
        return cls(algebra_lazy_run)
    
    @classmethod
    def fail(cls, error: Any) -> Algebra[Any, S]:
        def fail_run(input: S, 
                     cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                           SendChannelType, 
                                                                           Either[Any, Tuple[A, S]]]:
            yield from ()
            return Left(Error(
                error=error,
                this=cls,
                state=input
            ))
        return cls(fail_run)
    
    @classmethod
    def success(cls, value: Any) -> Algebra[Any, S]:
        def success_run(input: S, 
                        cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                              SendChannelType, 
                                                                              Either[Any, Tuple[A, S]]]:
            yield from ()
            return Right((value, input))
        return cls(success_run)
    
    
    def cut(self) -> Algebra[A, S]:
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
                        Left[Any]
                    ], 
                        Either[Any, Tuple[B, S]]
                    ]) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def fail_run(input: S, 
                     cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                           SendChannelType, 
                                                                           Either[Any, Tuple[A|B, S]]]:
            result = yield from self.run(input, cache)
            if isinstance(result, Left):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result))
            else:
                return cast(Either[Any, Tuple[A | B, S]], result)
        return replace(self, run_f=fail_run) # type: ignore
        

    def on_success(self, 
                    func: Callable[
                        [
                            Algebra[A, S], 
                            S, 
                            Right[Tuple[A, S]], 
                        ], 
                            Either[Any, Tuple[B, S]]
                        ]) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def success_run(input: S, 
                        cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                              SendChannelType, 
                                                                              Either[Any, Tuple[A|B, S]]]:
            result = yield from self.run(input, cache)
            if isinstance(result, Right):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result))
            else:
                return cast(Either[Any, Tuple[A | B, S]], result)
        return replace(self, run_f=success_run) # type: ignore
        


######################################################## map on state ###########################################
    def map_state(self, f: Callable[[S], S]) -> Algebra[A, S]:
        def map_state_run(state: S, 
                          cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                                SendChannelType, 
                                                                                Either[Any, Tuple[A, S]]]:
            result = yield from self.run(f(state), cache)
            return result
        return replace(self, run_f=map_state_run) 
        


######################################################## fundamental combinators ############################################    
    def map(self, f: Callable[[A], B], *, raw:bool) -> Algebra[B, S]:
        def map_run(input: S, 
                    cache:Cache[S, Either[Any, Tuple[Any, S]]]) -> Generator[YieldChannelType, 
                                                                          SendChannelType, 
                                                                          Either[Any, Tuple[B, S]]]:
            parsed = yield from self.run(input, cache)
            if isinstance(parsed, Right):
                ast, s = parsed.value
                if not raw and isinstance(ast, AST):
                    data:Any = ast.mapped
                else:
                    data = ast 
                return Right((f(data), s))            
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        alg = replace(self, run_f=map_run) # type: ignore
        return cast(Algebra[B, S], alg)

        
    def bimap(self, f: Callable[[A], B], i: Callable[[B], A]) -> Algebra[B, S]:
        return self.map(f, raw=True).map_state(lambda s: s.map(i))

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Algebra[A, S]:
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
        alg = replace(self, run_f=flat_map_run) # type: ignore
        from typing import cast as _cast
        return _cast(Algebra[B, S], alg)

    def map_all(self, f: Callable[[A, S], Tuple[B, S]]) -> Algebra[B, S]:
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
            # cache.enter(or_else_run, input, left=self.run_f, right=other.run_f)
            # try:
                inp = input.enter()
                left = yield from self.run(inp, cache)
                match left:
                    case Right((value, state)):
                        return Right((Choice(kind=ChoiceKind.LEFT, value=value), state.leave()))
                    case Left(err):
                        if isinstance(err, Error) and err.committed:
                            return Left(replace(err, committed=False))
                        other_result = yield from other.run(inp, cache)
                        match other_result:
                            case Right((other_value, other_state)):
                                return Right((Choice(kind=ChoiceKind.RIGHT, value=other_value), other_state.leave()))
                            case Left(other_err):
                                return Left(other_err)
                        raise SyncraftError(f"Unexpected result type from {other}", offender=other_result, expect=(Left, Right))
                raise SyncraftError(f"Unexpected result type from {self}", offender=left, expect=(Left, Right))
            # finally:
            #     cache.leave()
        
        alg = replace(self, run_f=or_else_run) # type: ignore
        from typing import cast as _cast
        return _cast(Algebra[Choice[A, B], S], alg)
        

    def then_both(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_both_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.BOTH)
            return other.map(combine, raw=True)        
        return self.flat_map(then_both_f)
        

    def then_left(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_left_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.LEFT)
            return other.map(combine, raw=True)
        return self.flat_map(then_left_f)
        

    def then_right(self, other: Algebra[B, S]) -> Algebra[Then[A, B], S]:
        def then_right_f(a: A) -> Algebra[Then[A, B], S]:
            def combine(b: B) -> Then[A, B]:
                return Then(left=a, right=b, kind=ThenKind.RIGHT)
            return other.map(combine, raw=True)        
        return self.flat_map(then_right_f)
        

    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Many[A], S]:
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offender=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
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
        return replace(self, run_f=many_run) # type: ignore

    


