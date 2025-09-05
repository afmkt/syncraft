from __future__ import annotations

from typing import (
    Any, Tuple, Generator as PyGenerator, TypeVar, Generic, Optional, Callable
)
from dataclasses import dataclass, replace
from syncraft.algebra import (
    Algebra, Either, Right, Incomplete, Left, Error, SyncraftError
)
from syncraft.ast import Reducer, ParseResult, Token
from syncraft.parser import TokenType
from syncraft.constraint import Bindable

import re
from syncraft.syntax import Syntax


S = TypeVar('S', bound=Bindable)
A = TypeVar('A')
B = TypeVar('B')
SS = TypeVar('SS')

@dataclass(frozen=True)
class WalkerState(Bindable, Generic[SS]):
    reducer: Optional[Reducer[Any, SS]] = None
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

    def state(cls, reducer: Reducer[Any, SS], init: SS )->WalkerState[SS]: # type: ignore
        assert isinstance(reducer, Reducer), f"reducer must be a Reducer or None, got {type(reducer)}"
        return WalkerState(reducer=reducer, acc=init)

    def flat_map(self, f: Callable[[Any], Algebra[Any, WalkerState[SS]]]) -> Algebra[Any, WalkerState[SS]]: 
        def flat_map_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            self_result = yield from self.run(input, use_cache=use_cache)
            match self_result:
                case Left(error):
                    return Left(error)
                case Right((value, from_left)):
                    other_result = yield from f(value).run(from_left.reduce(value), use_cache)
                    match other_result:
                        case Left(e):
                            return Left(e)
                        case Right((result, from_right)):
                            return Right((result, from_right.reduce(result)))
            raise SyncraftError("flat_map should always return a value or an error.", offending=self_result, expect=(Left, Right))
        return self.__class__(run_f = flat_map_run, name=self.name) 


        


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Any, WalkerState[SS]]:
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offending=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        def many_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            self_result = yield from self.run(input, use_cache)
            match self_result:
                case Right((value, from_self)):
                    return Right((value, from_self.reduce(value)))
            raise SyncraftError("many should always return a value or an error.", offending=self_result, expect=(Left, Right))
        return self.__class__(many_run, name=f"many({self.name})")  
    
 
    def or_else(self, 
                other: Algebra[Any, WalkerState[SS]]
                ) -> Algebra[Any, WalkerState[SS]]: 
        def or_else_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            self_result = yield from self.run(input, use_cache=use_cache)
            match self_result:
                case Left(error):
                    return Left(error)
                case Right((value, from_left)):
                    other_result = yield from other.run(from_left.reduce(value), use_cache)
                    match other_result:
                        case Left(e):
                            return Left(e)
                        case Right((result, from_right)):
                            return Right((result, from_right.reduce(result)))
            raise SyncraftError("", offending=self)
        return self.__class__(or_else_run, name=f"or_else({self.name} | {other.name})") 

    @classmethod
    def token(cls, 
              token_type: Optional[TokenType] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None
              )-> Algebra[Any, WalkerState[SS]]:      
        def token_run(input: WalkerState[SS], use_cache:bool) -> PyGenerator[Incomplete[WalkerState[SS]], WalkerState[SS], Either[Any, Tuple[Any, WalkerState[SS]]]]:
            yield from ()
            return Right(((token_type, text, regex, case_sensitive), input))
        return cls(token_run, name=cls.__name__ + f'.token({token_type or text or regex})')  


def walk(syntax: Syntax[Any, Any], reducer: Reducer[Any, Any], init: Any)-> Any:
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Walker, use_cache=False, reducer=reducer, init=init)
    if s is not None:
        return s.acc
    else:
        return None