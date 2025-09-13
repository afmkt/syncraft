from __future__ import annotations

from typing import (
    Any, Tuple, Generator as PyGenerator, TypeVar, Optional, Callable, Hashable
)
from dataclasses import dataclass, replace
from syncraft.algebra import (
    Algebra, Either, Right, Incomplete, SyncraftError
)
from syncraft.charset import CodeUniverse, CharSet
from syncraft.fa import NFA
from syncraft.syntax import Syntax

from syncraft.constraint import Bindable
from syncraft.cache import Cache
import re



from rich import print

C = TypeVar('C', bound=str | bytes)



class RecursionNotSupportedError(SyncraftError):
    pass


S = TypeVar('S', bound=Bindable)
A = TypeVar('A')
B = TypeVar('B')
SS = TypeVar('SS', bound=Hashable)


@dataclass(frozen=True)
class RegularState(Bindable):
    pass
        


@dataclass(frozen=True)
class Regular(Algebra[NFA[C], RegularState]):
    @classmethod
    def state(cls, **kwargs: Any)->RegularState:
        return RegularState()
    # error on recursion
    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[Any, RegularState]]) -> Algebra[Any, RegularState]:
        raise RecursionNotSupportedError("Regular language does not support recursion, so lazy is not supported.", offending=thunk)
    

    @classmethod
    def any(cls, universe: CodeUniverse = CodeUniverse.UNICODE)-> Algebra[NFA[C], RegularState]:
        def any_run(input: RegularState, cache:Cache[Either[Any, Tuple[NFA[C], RegularState]]]) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[NFA[C], RegularState]]]:
            a: CharSet[C] = CharSet.any(universe=universe)
            data = NFA.from_charset(a)
            return (yield from cache.return_value(Right((data, input)))) 
        return cls(any_run, _name='.')

    # the primitive NFA
    @classmethod
    def charset(cls, 
                *, 
                text: C, 

                negation:bool = False, 
                universe:CodeUniverse = CodeUniverse.UNICODE)-> Algebra[NFA[C], RegularState]:      
        name = f'[{text!r}]' if not negation else f'[^{text!r}]'
        def charset_run(input: RegularState, cache:Cache[Either[Any, Tuple[NFA[C], RegularState]]]) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[NFA[C], RegularState]]]:
            data = NFA.from_char(text, universe=universe, negation=negation, tag=name)
            return (yield from cache.return_value(Right((data, input)))) 
        return cls(charset_run, _name=name)

    def then_both(self, other: Algebra[Any, RegularState]) -> Algebra[Any, RegularState]:
        name = f"{self.name} > {other.name}"
        def then_run(input: RegularState, cache:Cache[Either[Any, Tuple[Any, RegularState]]]) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            match (yield from self.run(input, cache=cache)):
                case Right((value, from_left)):
                    other_result = yield from other.run(from_left, cache)
                    match other_result:
                        case Right((result, from_right)):
                            data = value.then(result)
                            return (yield from cache.return_value(Right((data, from_right))))
                        case failed:
                            raise SyncraftError("Building NFA from regular language failed.", offending=failed, expect=Right)
                case failed:
                    raise SyncraftError("Building NFA from regular language failed.", offending=failed, expect=Right)
        return replace(self, run_f=then_run, _name=name)
        

    def then_left(self, other: Algebra[Any, RegularState]) -> Algebra[Any, RegularState]:
        return self.then_both(other)

    def then_right(self, other: Algebra[Any, RegularState]) -> Algebra[Any, RegularState]:
        return self.then_both(other)


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[Any, RegularState]:
        if at_least <=0 or (at_most is not None and at_most < at_least):
            raise SyncraftError(f"Invalid arguments for many: at_least={at_least}, at_most={at_most}", offending=(at_least, at_most), expect="at_least>0 and (at_most is None or at_most>=at_least)")
        def many_run(input: RegularState, cache:Cache[Either[Any, Tuple[Any, RegularState]]]) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            match (yield from self.run(input, cache)):
                case Right((nfa, from_self)):
                    data = nfa.many(at_least=at_least, at_most=at_most)
                    return (yield from cache.return_value(Right((data, from_self))))
                case failed:
                    raise SyncraftError("many should always return a value or an error.", offending=failed, expect=Right)
        return replace(self, run_f=many_run, _name=f"{self.name}{{{at_least},{at_most}}}")
        
        
    def star(self) -> Algebra[Any, RegularState]:
        def star_run(input: RegularState, cache:Cache[Either[Any, Tuple[Any, RegularState]]]) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            match (yield from self.run(input, cache=cache)):
                case Right((nfa, from_self)):
                    data = nfa.star()
                    return (yield from cache.return_value(Right((data, from_self))))
                case failed:
                    raise SyncraftError("star should always return a value or an error.", offending=failed, expect=Right)
        return replace(self, run_f=star_run, _name=f"{self.name}*")
        
    
    def plus(self) -> Algebra[Any, RegularState]:
        def plus_run(input: RegularState, cache:Cache[Either[Any, Tuple[Any, RegularState]]]) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            match (yield from self.run(input, cache=cache)):
                case Right((nfa, from_self)):
                    data = nfa.plus()
                    return (yield from cache.return_value(Right((data, from_self))))
                case failed:
                    raise SyncraftError("plus should always return a value or an error.", offending=failed, expect=Right)
        return replace(self, run_f=plus_run, _name=f"{self.name}+")
        

    def optional(self) -> Algebra[Any, RegularState]:
        pattern = re.compile(r'\s')
        self_name = self.name.strip() 
        self_name = f"({self_name})" if bool(pattern.search(self_name)) else self_name
        name = f"{self_name}?"
        def optional_run(input: RegularState, cache:Cache[Either[Any, Tuple[Any, RegularState]]]) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            match (yield from self.run(input, cache=cache)):
                case Right((nfa, from_self)):
                    data = nfa.optional()
                    return (yield from cache.return_value(Right((data, from_self))))
                case failed:
                    raise SyncraftError("optional should always return a value or an error.", offending=failed, expect=Right)
        return replace(self, run_f=optional_run, _name=name)
        
 
    def or_else(self, other: Algebra[Any, RegularState]) -> Algebra[Any, RegularState]: 
        pattern = re.compile(r'\s')
        self_name = self.name.strip() 
        self_name = f"({self_name})" if bool(pattern.search(self_name)) else self_name
        other_name = other.name.strip()
        other_name = f"({other_name})" if bool(pattern.search(other_name)) else other_name
        name = f"{self_name} | {other_name}"
        def or_else_run(input: RegularState, cache:Cache[Either[Any, Tuple[Any, RegularState]]]) -> PyGenerator[Incomplete[RegularState], RegularState, Either[Any, Tuple[Any, RegularState]]]:
            match (yield from self.run(input, cache=cache)):
                case Right((left_nfa, from_left)):
                    match (yield from other.run(from_left, cache)):
                        case Right((right_nfa, from_right)):
                            data = left_nfa.union(right_nfa)
                            return (yield from cache.return_value(Right((data, from_right))))
                        case failed:
                            raise SyncraftError("Building NFA from regular language failed.", offending=failed, expect=Right)
                case failed:    
                    raise SyncraftError("Building NFA from regular language failed.", offending=failed, expect=Right)
        return replace(self, run_f=or_else_run, _name=name)
        


def charset(text: str | bytes, *, negation:bool = False, universe:CodeUniverse = CodeUniverse.UNICODE) -> Syntax[Any, Any]:
    return Syntax(
        lambda cls: cls.factory('charset', 
                                text=text, 
                                negation=negation, 
                                universe=universe)
        ).describe(name=f"{text!r}", fixity='prefix') 

def any(universe:CodeUniverse = CodeUniverse.UNICODE) -> Syntax[Any, Any]:
    return Syntax(
        lambda cls: cls.factory('any', universe=universe)
        ).describe(name='.', fixity='prefix')

def star(this: Syntax[Any, Any]) -> Syntax[Any, Any]:
    return this.algebra('star').describe(name=f"{this.meta.name}*", fixity='postfix', parameter=(this,)) 

def plus(this: Syntax[Any, Any]) -> Syntax[Any, Any]:
    return this.algebra('plus').describe(name=f"{this.meta.name}+", fixity='postfix', parameter=(this,))


def nfa(syntax: Syntax[NFA, Any]) -> NFA:
    from syncraft.syntax import run
    v, s = run(syntax=syntax, alg=Regular, cache=Cache())
    return v
