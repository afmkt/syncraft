from __future__ import annotations
from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, 
    Dict, Type, ClassVar, Hashable
)

import traceback
from dataclasses import dataclass, replace
from weakref import WeakKeyDictionary
from abc import ABC
from enum import Enum


A = TypeVar('A')  
B = TypeVar('B')  
C = TypeVar('C')  
S = TypeVar('S')  


@dataclass(frozen=True)
class Biducer(Generic[S, A]):
    forward: Callable[[S, A], S]    
    inverse: Callable[[S], Tuple[A, S]]  
    

@dataclass(frozen=True)
class Bitrans(Generic[S, A, B]):
    trans: Callable[[Biducer[S, B]], Biducer[S, A]]  
    def __call__(self, biducer: Biducer[S, B]) -> Biducer[S, A]:
        return self.trans(biducer)
    def __and__(self, other: Bitrans[S, B, C]) -> Bitrans[S, A, C]:
        def composed(biducer: Biducer[S, C]) -> Biducer[S, A]:
            return self.trans(other.trans(biducer))
        return Bitrans(trans=composed)

    @staticmethod
    def bitrans(value: A) -> Bitrans[S, A, A]:
        def trans(b: Biducer[S, A]) -> Biducer[S, A]:
            def forward(acc: S, node: A) -> S:
                return b.forward(acc, value)
            def inverse(acc: S) -> Tuple[A, S]:
                v, acc = b.inverse(acc)
                return value, acc
            return Biducer(forward=forward, inverse=inverse)
        return Bitrans(trans=trans)
            
        
class StructuralResult:
    def bitrans(self)->Bitrans[Any, Any, Any]:
        return Bitrans(lambda x: x)
    
    def bimap(self, ctx: Any)->Tuple[Any, Callable[[Any], StructuralResult]]:
        return (self, lambda x: self)

        
@dataclass(frozen=True)
class NamedResult(Generic[A], StructuralResult):
    name: str
    value: A
    def bimap(self, ctx: Any)->Tuple[NamedResult[Any], Callable[[NamedResult[Any]], StructuralResult]]:
        value, backward = self.value.bimap(ctx) if isinstance(self.value, StructuralResult) else (self.value, lambda x: x)
        def named_back(data: Any)->NamedResult[Any]:
            v = backward(data)
            if isinstance(v, NamedResult):
                return replace(v, name=self.name)
            else:
                return NamedResult(name=self.name, value=v)
        return NamedResult(self.name, value), named_back

@dataclass(eq=True, frozen=True)
class ManyResult(Generic[A], StructuralResult):
    value: Tuple[A, ...]
    def bimap(self, ctx: Any)->Tuple[List[Any], Callable[[List[Any]], StructuralResult]]:
        transformed = [v.bimap(ctx) if isinstance(v, StructuralResult) else (v, lambda x: x) for v in self.value]
        backmaps = [b for (_, b) in transformed]
        ret = [a for (a, _) in transformed]
        def backward(data: List[Any]) -> StructuralResult:
            if len(data) != len(transformed):
                raise ValueError("Incompatible data length")
            return ManyResult(value=tuple([backmaps[i](x) for i, x in enumerate(data)]))
        return ret, lambda data: backward(data)



@dataclass(eq=True, frozen=True)
class OrResult(Generic[A], StructuralResult):
    value: A
    def bimap(self, ctx: Any) -> Tuple[Any, Callable[[Any], StructuralResult]]:
        value, backward = self.value.bimap(ctx) if isinstance(self.value, StructuralResult) else (self.value, lambda x: x)
        return value, lambda data: OrResult(value=backward(data))


class ThenKind(Enum):
    BOTH = '+'
    LEFT = '//'
    RIGHT = '>>'
    
@dataclass(eq=True, frozen=True)
class ThenResult(Generic[A, B], StructuralResult):
    kind: ThenKind
    left: A
    right: B
    def bitrans(self) -> Bitrans[Any, ThenResult[A, B], ThenResult[A, B]]:
        def trans(b: Biducer[Any, C]) -> Biducer[Any, ThenResult[A, B]]:
            def forward(acc: Any, node: ThenResult[A, B]) -> Any:
                lt = node.left.bitrans() if isinstance(node.left, StructuralResult) else Bitrans.bitrans(node.left)
                acc = lt(b).forward(acc, node.left)
                rt = node.right.bitrans() if isinstance(node.right, StructuralResult) else Bitrans.bitrans(node.right)
                return rt(b).forward(acc, node.right)
            
            def inverse(acc: Any) -> Tuple[ThenResult[A, B], Any]:
                lt = self.left.bitrans() if isinstance(self.left, StructuralResult) else Bitrans.bitrans(self.left)
                left_value, acc = lt(b).inverse(acc)
                rt = self.right.bitrans() if isinstance(self.right, StructuralResult) else Bitrans.bitrans(self.right)
                right_value, acc = rt(b).inverse(acc)
                return ThenResult(self.kind, left_value, right_value), acc
            return Biducer(forward=forward, inverse=inverse)
        return Bitrans(trans=trans)        



    def bimap(self, ctx: Any) -> Tuple[Any, Callable[[Any], StructuralResult]]:
        def branch(b: Any) -> Tuple[Any, Callable[[Any], StructuralResult]]:
            return b.bimap(ctx) if isinstance(b, StructuralResult) else (b, lambda x: x)
        match self.kind:
            case ThenKind.BOTH:
                left_value, left_bmap = branch(self.left)
                right_value, right_bmap = branch(self.right)
                def backward(x: Tuple[Any, Any]) -> StructuralResult:
                    return ThenResult(self.kind, left_bmap(x[0]), right_bmap(x[1]))
                x, y = ThenResult.flat((left_value, right_value))
                return x, lambda data: backward(y(data))
            case ThenKind.LEFT:
                left_value, left_bmap = branch(self.left)
                return left_value, lambda data: ThenResult(self.kind, left_bmap(data), self.right)
            case ThenKind.RIGHT:
                right_value, right_bmap = branch(self.right)
                return right_value, lambda data: ThenResult(self.kind, self.left, right_bmap(data))
    @staticmethod
    def flat(array: Tuple[Any, Any]) -> Tuple[Tuple[Any, ...], Callable[[Tuple[Any, ...]], Tuple[Any, Any]]]:
        index: Dict[int, int] = {}
        ret: List[Any] = []
        for e in array:
            if isinstance(e, tuple):
                index[len(ret)] = len(e)
                ret.extend(e)
            else:
                ret.append(e)
        def backward(data: Tuple[Any, ...]) -> Tuple[Any, Any]:
            tmp: List[Any] = []
            skip: int = 0
            for i, e in enumerate(data):
                if skip <= 0:
                    if i in index:
                        tmp.append(tuple(data[i:i + index[i]]))
                        skip = index[i] - 1
                    else:
                        tmp.append(e)
                else:
                    skip -= 1
            return tuple(tmp)
        return tuple(ret), backward


InProgress = object()  # Marker for in-progress state, used to prevent re-entrance in recursive calls
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
class Error:
    this: Any
    message: Optional[str] = None
    error: Optional[Any] = None    
    state: Optional[Any] = None
    committed: bool = False
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



@dataclass(frozen=True)        
class Algebra(ABC, Generic[A, S]):
######################################################## shared among all subclasses ########################################################
    run_f: Callable[[S, bool], Either[Any, Tuple[A, S]]] 
    name: Hashable
    _cache: ClassVar[WeakKeyDictionary[Any, Dict[Any, object | Either[Any, Tuple[Any, Any]]]]] = WeakKeyDictionary()

    def named(self, name: Hashable) -> 'Algebra[A, S]':
        return replace(self, name=name)

    def __post_init__(self)-> None:
        self._cache.setdefault(self.run_f, dict())
        
    def __call__(self, input: S, use_cache: bool) -> Either[Any, Tuple[A, S]]:
        return self.run(input, use_cache=use_cache)

    
    def run(self, input: S, use_cache: bool) -> Either[Any, Tuple[A, S]]:
        cache = self._cache[self.run_f]
        assert cache is not None, "Cache should be initialized in __post_init__"
        if input in cache:
            v = cache.get(input, None)
            if v is InProgress:
                return Left(
                    Error(
                        message="Left-recursion detected in parser",
                        this=self,
                        state=input
                    ))
            else:
                return cast(Either[Error, Tuple[A, S]], v)
        try:
            cache[input] = InProgress
            result = self.run_f(input, use_cache)
            cache[input] = result
            if not use_cache:
                cache.pop(input, None)  # Clear the cache entry if not using cache
            if isinstance(result, Left):
                if isinstance(result.value, Error):
                    result = Left(result.value.attach(this=self, state=input))
        except Exception as e:
            cache.pop(input, None)  # Clear the cache entry on exception
            traceback.print_exc()
            print(f"Exception from self.run(S): {e}")
            return Left(
                Error(
                    message="Exception from self.run(S): {e}",
                    this=self,
                    state=input,
                    error=e
                ))
        return result

    def as_(self, typ: Type[B])->B:
        return cast(typ, self) # type: ignore
        
    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[A, S]]) -> Algebra[A, S]:
        def lazy_run(input: S, use_cache:bool) -> Either[Any, Tuple[A, S]]:
            return thunk().run(input, use_cache)
        return cls(lazy_run, name=cls.__name__ + '.lazy')




    @classmethod
    def fail(cls, error: Any) -> Algebra[Any, S]:
        def fail_run(input: S, use_cache:bool) -> Either[Any, Tuple[Any, S]]:
            return Left(Error(
                error=error,
                this=cls,
                state=input
            ))
        return cls(fail_run, name=cls.__name__ + '.fail')
    @classmethod
    def success(cls, value: Any) -> Algebra[Any, S]:
        def success_run(input: S, use_cache:bool) -> Either[Any, Tuple[Any, S]]:
            return Right((value, input))
        return cls(success_run, name=cls.__name__ + '.success')
    
    @classmethod
    def factory(cls, name: str, *args: Any, **kwargs: Any) -> Algebra[A, S]:
        method = getattr(cls, name, None)
        if method is None or not callable(method):
            raise ValueError(f"Method {name} is not defined in {cls.__name__}")
        return cast(Algebra[A, S], method(*args, **kwargs))



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
                        Left[Any, Tuple[A, S]], 
                        Any
                    ], 
                    Either[Any, Tuple[B, S]]], 
                    ctx: Optional[Any] = None) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def fail_run(input: S, use_cache:bool) -> Either[Any, Tuple[A | B, S]]:
            result = self.run(input, use_cache)
            if isinstance(result, Left):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result, ctx))
            return cast(Either[Any, Tuple[A | B, S]], result)
        return self.__class__(fail_run, name=self.name) # type: ignore

    def on_success(self, 
                    func: Callable[
                        [
                            Algebra[A, S], 
                            S, 
                            Right[Any, Tuple[A, S]], 
                            Any
                        ], 
                        Either[Any, Tuple[B, S]]], 
                        ctx: Optional[Any] = None) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def success_run(input: S, use_cache:bool) -> Either[Any, Tuple[A | B, S]]:
            result = self.run(input, use_cache)
            if isinstance(result, Right):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result, ctx))
            return cast(Either[Any, Tuple[A | B, S]], result)
        return self.__class__(success_run, name=self.name) # type: ignore

    def debug(self, 
              label: str, 
              formatter: Optional[Callable[[
                  Algebra[Any, S], 
                  S, 
                  Either[Any, Tuple[Any, S]]], None]]=None) -> Algebra[A, S]:
        def default_formatter(alg: Algebra[Any, S], input: S, result: Either[Any, Tuple[Any, S]]) -> None:
            print(f"Debug: {'*' * 40} {alg.name} - State {'*' * 40}")
            print(input)
            print(f"Debug: {'~' * 40} (Result, State) {'~' * 40}")
            print(result)
            print()
            print()
        lazy_self: Algebra[A, S]
        def debug_run(input: S, use_cache:bool) -> Either[Any, Tuple[A, S]]:
            result = self.run(input, use_cache)
            try:
                if formatter is not None:
                    formatter(lazy_self, input, result)
                else:
                    default_formatter(lazy_self, input, result)
            except Exception as e:
                traceback.print_exc()
                print(f"Error occurred while formatting debug information: {e}")
            finally:
                return result
        lazy_self = self.__class__(debug_run, name=label)  
        return lazy_self


######################################################## fundamental combinators ############################################
    def map(self, f: Callable[[A], B]) -> Algebra[B, S]:
        def map_run(input: S, use_cache:bool) -> Either[Any, Tuple[B, S]]:
            parsed = self.run(input, use_cache)
            if isinstance(parsed, Right):
                return Right((f(parsed.value[0]), parsed.value[1]))            
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        return self.__class__(map_run, name=self.name)  # type: ignore

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Algebra[A, S]:
        def map_error_run(input: S, use_cache:bool) -> Either[Any, Tuple[A, S]]:
            parsed = self.run(input, use_cache)
            if isinstance(parsed, Left):
                return Left(f(parsed.value))
            return parsed
        return self.__class__(map_error_run, name=self.name)  

    def map_state(self, f: Callable[[S], S]) -> Algebra[A, S]:
        def map_state_run(state: S, use_cache:bool) -> Either[Any, Tuple[A, S]]:
            return self.run(f(state), use_cache)
        return self.__class__(map_state_run, name=self.name) 


    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Algebra[B, S]:
        def flat_map_run(input: S, use_cache:bool) -> Either[Any, Tuple[B, S]]:
            parsed = self.run(input, use_cache)
            if isinstance(parsed, Right):
                return f(parsed.value[0]).run(parsed.value[1], use_cache)  
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        return self.__class__(flat_map_run, name=self.name)  # type: ignore

    
    def or_else(self: Algebra[A, S], other: Algebra[B, S]) -> Algebra[OrResult[A | B], S]:
        def or_else_run(input: S, use_cache:bool) -> Either[Any, Tuple[OrResult[A | B], S]]:
            match self.run(input, use_cache):
                case Right((value, state)):
                    return Right((OrResult(value=value), state))
                case Left(err):
                    if isinstance(err, Error) and err.committed:
                        return Left(err)
                    match other.run(input, use_cache):
                        case Right((other_value, other_state)):
                            return Right((OrResult(value=other_value), other_state))
                        case Left(other_err):
                            return Left(other_err)
                    raise TypeError(f"Unexpected result type from {other}")
            raise TypeError(f"Unexpected result type from {self}")
        return self.__class__(or_else_run, name=f'{self.name} | {other.name}')  # type: ignore

    def then_both(self, other: 'Algebra[B, S]') -> 'Algebra[ThenResult[A, B], S]':
        def then_both_f(a: A) -> Algebra[ThenResult[A, B], S]:
            def combine(b: B) -> ThenResult[A, B]:
                return ThenResult(left=a, right=b, kind=ThenKind.BOTH)
            return other.map(combine)
        return self.flat_map(then_both_f).named(f'{self.name} + {other.name}')
            
    def then_left(self, other: Algebra[B, S]) -> Algebra[ThenResult[A, B], S]:
        return self.then_both(other).map(lambda b: replace(b, kind = ThenKind.LEFT)).named(f'{self.name} // {other.name}')

    def then_right(self, other: Algebra[B, S]) -> Algebra[ThenResult[A, B], S]:
        return self.then_both(other).map(lambda b: replace(b, kind=ThenKind.RIGHT)).named(f'{self.name} >> {other.name}')


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[ManyResult[A], S]:
        assert at_least > 0, "at_least must be greater than 0"
        assert at_most is None or at_least <= at_most, "at_least must be less than or equal to at_most"
        def many_run(input: S, use_cache:bool) -> Either[Any, Tuple[ManyResult[A], S]]:
            ret: List[A] = []
            current_input = input
            while True:
                match self.run(current_input, use_cache):
                    case Left(_):
                        break
                    case Right((value, next_input)):
                        ret.append(value)
                        if next_input == current_input:
                            break  # No progress, stop to avoid infinite loop
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
            return Right((ManyResult(value=tuple(ret)), current_input))
        return self.__class__(many_run, name=f'*({self.name})') # type: ignore

    


