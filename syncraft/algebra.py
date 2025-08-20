"""
We want to parse a token stream into an AST, and then generate a new token stream from that AST.
The generation should be a dual to the parsing. By 'dual' we mean that the generation algebra should be 
as close as possible to the parsing algebra. The closest algebra to the parsing algebra is the parsing 
algebra itself. 

Given:
AST = Syntax(Parser)(ParserState([Token, ...]))
AST =?= Syntax(Parser)(GenState(AST))

where =?= means the LHS and RHS induce the same text output, e.g. the same token stream 
inspite of the token metadata, token types, and/or potentially different structure of the AST.

With the above setting, Generator as a dual to Parser, can reuse most of the parsing combinator, the 
change needed is to introduce randomness in the generation process, e.g. to generate a random variable name, etc.

[Token, ...] == Syntax(Generator)(GenState(AST))

"""


from __future__ import annotations

from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, 
    Dict, Type, ClassVar, Hashable,
    Mapping, Iterator
)

import traceback
from dataclasses import dataclass, fields, replace, field
from functools import cached_property
from weakref import WeakKeyDictionary
from abc import ABC, abstractmethod
from enum import Enum




class Insptectable(ABC):
    @abstractmethod
    def to_string(self, interested: Callable[[Any], bool]) -> Optional[str]:
        raise NotImplementedError("Subclasses must implement to_string")
    
    @cached_property
    def _string(self)->Optional[str]:
        return self.to_string(lambda _: True)

    def __repr__(self) -> str:
        return self._string or self.__class__.__name__
    def __str__(self) -> str:
        return self._string or self.__class__.__name__


A = TypeVar('A')  # Result type
B = TypeVar('B')  # Result type for mapping

S = TypeVar('S')  # State type for the Algebra

    
    
class FrozenDict(Generic[A]):
    def __init__(self, items: Mapping[str, A]):
        for k, v in items.items():
            if not isinstance(k, Hashable) or not isinstance(v, Hashable):
                raise TypeError(f"Metadata key or value not hashable: {k} = {v}")
        self._items = tuple(sorted(items.items()))

    def __getitem__(self, key: str) -> A:
        return dict(self._items)[key]

    def __contains__(self, key: str) -> bool:
        return key in dict(self._items)

    def items(self) -> Iterator[tuple[str, A]]:
        return iter(self._items)

    def to_dict(self) -> dict[str, A]:
        return dict(self._items)

    def __hash__(self) -> int:
        return hash(self._items)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FrozenDict) and self._items == other._items

    def __repr__(self) -> str:
        return f"FrozenDict({dict(self._items)})"



@dataclass(frozen=True)
class Lens(Generic[S, A]):
    get: Callable[[S], A]
    set: Callable[[S, A], S]    

    def modify(self, source: S, f: Callable[[A], A]) -> S:
        return self.set(source, f(self.get(source)))
    
    def bimap(self, ff: Callable[[A], B], bf: Callable[[B], A]) -> Lens[S, B]:
        def getf(data: S) -> B:
            return ff(self.get(data))

        def setf(data: S, value: B) -> S:
            return self.set(data, bf(value))

        return Lens(get=getf, set=setf)

    def __truediv__(self, other: Lens[A, B]) -> Lens[S, B]:
        def get_composed(obj: S) -> B:
            return other.get(self.get(obj))        
        def set_composed(obj: S, value: B) -> S:
            return self.set(obj, other.set(self.get(obj), value))
        return Lens(get=get_composed, set=set_composed)
    
    def __rtruediv__(self, other: Lens[B, S])->Lens[B, A]:
        return other.__truediv__(self)
        
class StructuralResult:
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
class Error(Insptectable):
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
    



    def to_list(self, interested: Callable[[Any], bool]) -> List[Dict[str, str]]:

        def to_dict() -> Dict[str, str]:
            data: Dict[str, str] = {}
            for f in fields(self):
                value = getattr(self, f.name)
                if isinstance(value, Error):
                    # self.previous
                    pass
                elif isinstance(value, Insptectable):
                    # self.this
                    def inst(x: Any) -> bool:
                        return x in self.algebras
                    s = value.to_string(inst) 
                    data[f.name] = s if s is not None else repr(value)
                elif value is not None:
                    # self.committed, self.message, self.expect, self.exception
                    data[f.name] = repr(value)
            return data
        ret = []
        tmp : None | Error = self
        while tmp is not None:
            ret.append(to_dict())
            tmp = tmp.previous
        return ret

    def find(self, predicate: Callable[[Error], bool]) -> Optional[Error]:
        if predicate(self):
            return self
        if self.previous is not None:
            return self.previous.find(predicate)
        return None
    
    def to_string(self, interested: Callable[[Any], bool])->str:
        lst = self.to_list(interested)
        root, leaf = lst[0], lst[-1]
        root_fields = ',\n  '.join([f"{key}: {value}" for key, value in root.items() if value is not None])
        leaf_fields = ',\n  '.join([f"{key}: {value}" for key, value in leaf.items() if value is not None])

        return  f"{self.__class__.__name__}: ROOT\n"\
                f"  {root_fields}\n"\
                f"\u25cf \u25cf \u25cf  LEAF\n"\
                f"  {leaf_fields}\n"


    @cached_property
    def algebras(self) -> List[Any]:
        return [self.this] + (self.previous.algebras if self.previous is not None else [])
        
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

    


