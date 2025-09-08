from __future__ import annotations

from typing import (
    Any, Tuple, Generator as PyGenerator, TypeVar, Generic, Optional, Callable, Hashable
)
from dataclasses import dataclass, replace, field
from syncraft.algebra import (
    Algebra, Either, Right, Incomplete, Left, SyncraftError
)
from syncraft.ast import TokenSpec, ThenSpec, ManySpec, ChoiceSpec, LazySpec, ThenKind, RefSpec
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
class WalkerState(Bindable):
    visited: FrozenDict = field(default_factory=FrozenDict)
    def visit(self, algebra: Algebra, data: Hashable) -> WalkerState:
        return replace(self, visited=self.visited | FrozenDict({algebra.hashable: data}))

        

@dataclass(frozen=True)
class Walker(Algebra[Any, WalkerState]):
    @classmethod
    def state(cls, **kwargs: Any)->WalkerState:
        return WalkerState()

    def map(self, f: Callable[[Any], Any]) -> Algebra[Any, WalkerState]:
        return self

    def map_state(self, f: Callable[[WalkerState], WalkerState]) -> Algebra[Any, WalkerState]:
        return self
    
    def bimap(self, f: Callable[[Any], Any], g: Callable[[Any], Any]) -> Algebra[Any, WalkerState]:
        return self

    def map_all(self, f: Callable[[Any, WalkerState], Tuple[Any, WalkerState]]) -> Algebra[Any, WalkerState]:
        return self
    
    def flat_map(self, f: Callable[[Any], Algebra[Any, WalkerState]]) -> Algebra[Any, WalkerState]:
        return self

    def run(self, 
            input: WalkerState, 
            use_cache: bool = True
            ) -> PyGenerator[Incomplete[WalkerState], WalkerState, Either[Any, Tuple[Any, WalkerState]]]:
        try:
            if self.hashable in input.visited:
                ref = input.visited[self.hashable]
                return Right((RefSpec(ref=id(ref), referent= '' if not hasattr(ref, 'name') else ref.name), input))
            return (yield from self.cache.gen(self.run_f, input, use_cache))
        except RecursionError as e:
            if self.hashable in input.visited:
                ref = input.visited[self.hashable]
                return Right((RefSpec(ref=id(ref), referent= '' if not hasattr(ref, 'name') else ref.name), input))
            else:
                return Right((RefSpec(ref=e.offending, referent=''), input))
        
    @classmethod
    def token(cls, 
              *,
              cache: Cache,
              token_type: Optional[TokenType] = None, 
              text: Optional[str] = None, 
              case_sensitive: bool = False,
              regex: Optional[re.Pattern[str]] = None
              )-> Algebra[Any, WalkerState]:      
        name = f'Token({token_type or text or (regex.pattern if regex else "")})'
        this: None | Algebra[Any, WalkerState] = None
        def token_run(input: WalkerState, use_cache:bool) -> PyGenerator[Incomplete[WalkerState], WalkerState, Either[Any, Tuple[Any, WalkerState]]]:
            yield from ()
            data = TokenSpec(token_type=token_type, text=text, regex=regex, case_sensitive=case_sensitive)
            return Right((data, input.visit(this, data) if this is not None else input))
        this = cls(token_run, name=name, cache=cache)  
        return this

    @classmethod
    def lazy(cls, 
             thunk: Callable[[], Algebra[Any, WalkerState]], 
             cache: Cache) -> Algebra[Any, WalkerState]:
        this: None | Algebra[Any, WalkerState] = None
        def algebra_lazy_run(input: WalkerState, use_cache:bool) -> PyGenerator[Incomplete[WalkerState], WalkerState, Either[Any, Tuple[Any, WalkerState]]]:
            alg = thunk()
            thunk_result = yield from alg.run(input, use_cache)
            match thunk_result:
                case Right((value, from_thunk)):
                    data: LazySpec[Any] = LazySpec(name=alg.name, value=value)
                    from_thunk = from_thunk.visit(alg, value) 
                    return Right((data, from_thunk.visit(this, data) if this is not None else from_thunk))
            raise SyncraftError("flat_map should always return a value or an error.", offending=thunk_result, expect=(Left, Right))
        this = cls(algebra_lazy_run, name='lazy(?)', cache=cache)
        return this


    def then_all(self, other: Algebra[Any, WalkerState], kind: ThenKind) -> Algebra[Any, WalkerState]:
        name = f"{self.name} {kind.value} {other.name}"
        this: None | Algebra[Any, WalkerState] = None
        def then_run(input: WalkerState, use_cache:bool) -> PyGenerator[Incomplete[WalkerState], WalkerState, Either[Any, Tuple[Any, WalkerState]]]:
            self_result = yield from self.run(input, use_cache=use_cache)
            match self_result:
                case Right((value, from_left)):
                    other_result = yield from other.run(from_left.visit(self, value), use_cache)
                    match other_result:
                        case Right((result, from_right)):
                            data = ThenSpec(name=name, kind=kind, left=value, right=result)
                            from_right = from_right.visit(other, result) 
                            return Right((data, from_right.visit(this, data) if this is not None else from_right))
            raise SyncraftError("flat_map should always return a value or an error.", offending=self_result, expect=(Left, Right))
        this = self.__class__(then_run, name=name, cache=self.cache | other.cache) 
        return this



    def then_both(self, other: Algebra[Any, WalkerState]) -> Algebra[Any, WalkerState]:
        return self.then_all(other, ThenKind.BOTH)

    def then_left(self, other: Algebra[Any, WalkerState]) -> Algebra[Any, WalkerState]:
        return self.then_all(other, ThenKind.LEFT)

    def then_right(self, other: Algebra[Any, WalkerState]) -> Algebra[Any, WalkerState]:
        return self.then_all(other, ThenKind.RIGHT)


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Any, WalkerState]:
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offending=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        this: None | Algebra[Any, WalkerState] = None
        def many_run(input: WalkerState, use_cache:bool) -> PyGenerator[Incomplete[WalkerState], WalkerState, Either[Any, Tuple[Any, WalkerState]]]:
            self_result = yield from self.run(input, use_cache)
            match self_result:
                case Right((value, from_self)):
                    data = ManySpec(name=f"*({self.name})", value=value, at_least=at_least, at_most=at_most)
                    from_self = from_self.visit(self, value)
                    return Right((data, from_self.visit(this, data) if this is not None else from_self))
            raise SyncraftError("many should always return a value or an error.", offending=self_result, expect=(Left, Right))
        this = self.__class__(many_run, name=self.name, cache=self.cache)  
        return this
    
 
    def or_else(self, other: Algebra[Any, WalkerState]) -> Algebra[Any, WalkerState]: 
        pattern = re.compile(r'\s')
        self_name = self.name.strip() 
        self_name = f"({self_name})" if bool(pattern.search(self_name)) else self_name
        other_name = other.name.strip()
        other_name = f"({other_name})" if bool(pattern.search(other_name)) else other_name
        name = f"{self_name} | {other_name}"
        this: None | Algebra[Any, WalkerState] = None
        def or_else_run(input: WalkerState, use_cache:bool) -> PyGenerator[Incomplete[WalkerState], WalkerState, Either[Any, Tuple[Any, WalkerState]]]:
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
        this = self.__class__(or_else_run, name=name, cache=self.cache | other.cache) 
        return this



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
