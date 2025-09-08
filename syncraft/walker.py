from __future__ import annotations

from typing import (
    Any, Tuple, Generator as PyGenerator, TypeVar, Generic, Optional, Callable, Hashable
)
from dataclasses import dataclass, replace, field
from syncraft.algebra import (
    Algebra, Either, Right, Incomplete, Left, SyncraftError
)
from syncraft.ast import TokenSpec, ThenSpec, ManySpec, ChoiceSpec, LazySpec, ThenKind
from syncraft.parser import TokenType
from syncraft.constraint import Bindable, FrozenDict

import re
from syncraft.syntax import Syntax
from syncraft.cache import Cache, RecursionError
from rich import print


S = TypeVar('S', bound=Bindable)
A = TypeVar('A')
B = TypeVar('B')
SS = TypeVar('SS', bound=Hashable)


@dataclass(frozen=True)
class WalkerState(Bindable, Generic[SS]):
    reducer: Optional[Callable[[Any, SS], SS]] = None
    acc: Optional[SS] = None

    def reduce(self, value: Any) -> WalkerState[SS]:
        if self.reducer:
            new_acc = self.reducer(value, self.acc) if self.acc is not None else value
            return replace(self, acc=new_acc)
        else:
            return replace(self, acc=value)
        

@dataclass(frozen=True)
class Walker(Algebra[SS, WalkerState[SS]]):
    @classmethod
    def state(cls, reducer: Callable[[Any, SS], SS], init: SS )->WalkerState[SS]: # type: ignore
        assert callable(reducer), f"reducer must be a Reducer or None, got {type(reducer)}"
        return WalkerState(reducer=reducer, acc=init)



    @classmethod
    def token(cls, 
              *,
              cache: Cache,
              token_type: Optional[TokenType] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None
              )-> Algebra[Any, WalkerState[SS]]:      
        def token_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            yield from ()
            data = TokenSpec(token_type=token_type, text=text, regex=regex, case_sensitive=case_sensitive)
            return Right((data, input.reduce(data)))
        return cls(token_run, name=cls.__name__ + f'.token({token_type or text or regex})', cache=cache)  

    @classmethod
    def lazy(cls, 
             thunk: Callable[[], Algebra[Any, WalkerState[SS]]], 
             cache: Cache) -> Algebra[Any, WalkerState[SS]]:
        def algebra_lazy_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            alg = thunk()
            # print('--' * 20, "Walker.lazy.algebra_lazy_run", '--' * 20)
            # print('thunk', thunk, id(thunk))
            # print('input', input, id(input))
            # print('alg', alg, id(alg))
            try:
                thunk_result = yield from alg.run(input, use_cache)
                match thunk_result:
                    case Right((value, from_thunk)):
                        data: LazySpec[Any] = LazySpec(value=value)
                        return Right((data, from_thunk.reduce(data)))
                raise SyncraftError("flat_map should always return a value or an error.", offending=thunk_result, expect=(Left, Right))
            except RecursionError as e:
                return Right((LazySpec(value=None), input))
        return cls(algebra_lazy_run, name=cls.__name__ + '.lazy', cache=cache)



    def then_both(self, other: Algebra[Any, WalkerState[SS]]) -> Algebra[Any, WalkerState[SS]]:
        def then_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            self_result = yield from self.run(input, use_cache=use_cache)
            match self_result:
                case Right((value, from_left)):
                    other_result = yield from other.run(from_left, use_cache)
                    match other_result:
                        case Right((result, from_right)):
                            data = ThenSpec(kind=ThenKind.BOTH, left=value, right=result)
                            return Right((data, from_right.reduce(data)))
            raise SyncraftError("flat_map should always return a value or an error.", offending=self_result, expect=(Left, Right))
        return self.__class__(then_run, name=self.name, cache=self.cache | other.cache) 

    def then_left(self, other: Algebra[Any, WalkerState[SS]]) -> Algebra[Any, WalkerState[SS]]:
        return self.then_both(other).map(lambda t: replace(t, kind=ThenKind.LEFT))

    def then_right(self, other: Algebra[Any, WalkerState[SS]]) -> Algebra[Any, WalkerState[SS]]:
        return self.then_both(other).map(lambda t: replace(t, kind=ThenKind.RIGHT))


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Any, WalkerState[SS]]:
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offending=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        def many_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            self_result = yield from self.run(input, use_cache)
            match self_result:
                case Right((value, from_self)):
                    data = ManySpec(value=value, at_least=at_least, at_most=at_most)
                    return Right((data, from_self.reduce(data)))
            raise SyncraftError("many should always return a value or an error.", offending=self_result, expect=(Left, Right))
        return self.__class__(many_run, name=f"many({self.name})", cache=self.cache)  
    
 
    def or_else(self, other: Algebra[Any, WalkerState[SS]]) -> Algebra[Any, WalkerState[SS]]: 
        def or_else_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            self_result = yield from self.run(input, use_cache=use_cache)
            match self_result:
                case Right((value, from_left)):
                    other_result = yield from other.run(from_left, use_cache)
                    match other_result:
                        case Right((result, from_right)):
                            data = ChoiceSpec(left=value, right=result)
                            return Right((data, from_right.reduce(data)))
            raise SyncraftError("", offending=self)
        return self.__class__(or_else_run, name=f"or_else({self.name} | {other.name})", cache=self.cache | other.cache) 



def walk(syntax: Syntax[Any, Any], reducer: Optional[Callable[[Any, Any], SS]] = None, init: Optional[SS] = None) -> Any:
    from syncraft.syntax import run
    v, s = run(syntax=syntax, 
               alg=Walker, 
               use_cache=True, 
               reducer=reducer or (lambda a, s: s), 
               init=init)
    if reducer is None:
        return v
    else:
        if s is not None:
            return s.acc
        else:
            return None
