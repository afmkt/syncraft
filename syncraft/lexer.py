from __future__ import annotations

from typing import (
    Any, Tuple, Generator as PyGenerator, TypeVar, Optional, Callable, Hashable, Dict, Set, Generic
)
from dataclasses import dataclass, replace, field
from syncraft.algebra import (
    Algebra, Either, Right, Incomplete, Left, SyncraftError
)
from syncraft.fa import NFA, NFAState
from syncraft.ast import TokenSpec, ThenSpec, ManySpec, ChoiceSpec, ThenKind
from syncraft.parser import TokenType
from syncraft.constraint import Bindable, FrozenDict
from syncraft.cache import Cache
import re
from syncraft.syntax import Syntax

from rich import print

C = TypeVar('C', bound=Hashable)
class RecursionNotSupportedError(SyncraftError):
    pass


S = TypeVar('S', bound=Bindable)
A = TypeVar('A')
B = TypeVar('B')
SS = TypeVar('SS', bound=Hashable)


@dataclass(frozen=True)
class RegularState(Bindable):
    visited: FrozenDict = field(default_factory=FrozenDict)
    def visit(self, algebra: Algebra, data: Hashable) -> RegularState:
        return replace(self, visited=self.visited | FrozenDict({algebra.hashable: data}))

        


@dataclass(frozen=True)
class Regular(Algebra[NFA[C], RegularState]):
    @classmethod
    def state(cls, **kwargs: Any)->RegularState:
        return RegularState()

    # error on recursion
    @classmethod
    def lazy(cls, 
             thunk: Callable[[], Algebra[Any, RegularState]], 
             cache: Cache) -> Algebra[Any, RegularState]:
        raise RecursionNotSupportedError("Regular language does not support recursion, so lazy is not supported.", offending=thunk)


    def run(self, 
            input: RegularState, 
            use_cache: bool = True
            ) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[NFA[C], RegularState]]]:
        # we don't use cache for regular language.
        # because regular language is not recursive.
        # and NFA/DFA execution is no slower than memoized execution.
        return (yield from self.run_f(input, use_cache))
    
    # disable data transformation methods
    def map(self, f: Callable[[NFA[C]], Any]) -> Algebra[Any, RegularState]:
        return self

    def map_state(self, f: Callable[[RegularState], RegularState]) -> Algebra[NFA[C], RegularState]:
        return self
    
    def bimap(self, f: Callable[[NFA[C]], Any], g: Callable[[Any], NFA[C]]) -> Algebra[Any, RegularState]:
        return self

    def map_all(self, f: Callable[[NFA[C], RegularState], Tuple[Any, RegularState]]) -> Algebra[Any, RegularState]:
        return self
    
    def flat_map(self, f: Callable[[NFA[C]], Algebra[Any, RegularState]]) -> Algebra[Any, RegularState]:
        return self


    # the primitive NFA
    @classmethod
    def token(cls, 
              *,
              cache: Cache,
              text: C              
              )-> Algebra[NFA[C], RegularState]:      
        name = f'Token({text})'
        this: None | Algebra[NFA[C], RegularState] = None
        def token_run(input: RegularState, use_cache:bool) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[NFA[C], RegularState]]]:
            yield from ()
            data = NFA.from_char(text)
            return Right((data, input))
        this = cls(token_run, _name=name, cache=cache)  
        return this



    def then_all(self, other: Algebra[NFA[C], RegularState], kind: ThenKind) -> Algebra[NFA[C], RegularState]:
        name = f"{self.name} {kind.value} {other.name}"
        this: None | Algebra[Any, RegularState] = None
        def then_run(input: RegularState, use_cache:bool) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            self_result = yield from self.run(input, use_cache=use_cache)
            match self_result:
                case Right((value, from_left)):
                    other_result = yield from other.run(from_left.visit(self, value), use_cache)
                    match other_result:
                        case Right((result, from_right)):
                            data = ThenSpec(name=name, kind=kind, left=value, right=result)
                            from_right = from_right.visit(other, result) 
                            return Right((data, from_right.visit(this, data) if this is not None else from_right))
            raise SyncraftError("Building NFA from regular language should not fail.", offending=self_result, expect=Right)
        this = self.__class__(then_run, _name=name, cache=self.cache | other.cache) 
        return this



    def then_both(self, other: Algebra[Any, RegularState]) -> Algebra[Any, RegularState]:
        return self.then_all(other, ThenKind.BOTH)

    def then_left(self, other: Algebra[Any, RegularState]) -> Algebra[Any, RegularState]:
        return self.then_all(other, ThenKind.LEFT)

    def then_right(self, other: Algebra[Any, RegularState]) -> Algebra[Any, RegularState]:
        return self.then_all(other, ThenKind.RIGHT)


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Any, RegularState]:
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offending=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        this: None | Algebra[Any, RegularState] = None
        def many_run(input: RegularState, use_cache:bool) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            self_result = yield from self.run(input, use_cache)
            match self_result:
                case Right((value, from_self)):
                    data = ManySpec(name=f"*({self.name})", value=value, at_least=at_least, at_most=at_most)
                    from_self = from_self.visit(self, value)
                    return Right((data, from_self.visit(this, data) if this is not None else from_self))
            raise SyncraftError("many should always return a value or an error.", offending=self_result, expect=(Left, Right))
        this = self.__class__(many_run, _name=self.name, cache=self.cache)  
        return this
    
 
    def or_else(self, other: Algebra[Any, RegularState]) -> Algebra[Any, RegularState]: 
        pattern = re.compile(r'\s')
        self_name = self.name.strip() 
        self_name = f"({self_name})" if bool(pattern.search(self_name)) else self_name
        other_name = other.name.strip()
        other_name = f"({other_name})" if bool(pattern.search(other_name)) else other_name
        name = f"{self_name} | {other_name}"
        this: None | Algebra[Any, RegularState] = None
        def or_else_run(input: RegularState, use_cache:bool) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            self_result = yield from self.run(input, use_cache=use_cache)
            match self_result:
                case Right((value, from_left)):
                    other_result = yield from other.run(from_left.visit(self, value), use_cache)
                    match other_result:
                        case Right((result, from_right)):
                            data = ChoiceSpec(name=name, left=value, right=result)
                            from_right = from_right.visit(other, result) 
                            return Right((data, from_right.visit(this, data) if this is not None else from_right))
            raise SyncraftError("", offending=self)
        this = self.__class__(or_else_run, _name=name, cache=self.cache | other.cache) 
        return this



def walk(syntax: Syntax[Any, Any]) -> Any:
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Regular, use_cache=True)
    return v
