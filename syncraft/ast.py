

from __future__ import annotations
import re
from typing import (
    Optional, Any, TypeVar, Tuple, runtime_checkable, 
    Dict, Generic, Callable, Union, Protocol
)


from dataclasses import dataclass
from enum import Enum
from syncraft.constraint import Bindable



A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
S = TypeVar('S', bound=Bindable)  

@dataclass(frozen=True)
class Reducer(Generic[A, S]):
    run_f: Callable[[A, S], S]
    def __call__(self, a: A, s: S) -> S:
        return self.run_f(a, s)
    
    def map(self, f: Callable[[B], A]) -> Reducer[B, S]:
        def map_run(b: B, s: S) -> S:
            return self(f(b), s)
        return Reducer(map_run)
    

    
@dataclass(frozen=True)
class Bimap(Generic[A, B]):
    run_f: Callable[[A], Tuple[B, Callable[[B], A]]]
    def __call__(self, a: A) -> Tuple[B, Callable[[B], A]]:
        return self.run_f(a)    
    def __rshift__(self, other: Bimap[B, C]) -> Bimap[A, C]:
        def then_run(a: A) -> Tuple[C, Callable[[C], A]]:
            b, inv1 = self(a)
            c, inv2 = other(b)
            def inv(c2: C) -> A:
                return inv1(inv2(c2))
            return c, inv
        return Bimap(then_run)
    @staticmethod
    def const(a: B)->Bimap[B, B]:
        return Bimap(lambda _: (a, lambda b: b))

    @staticmethod
    def identity()->Bimap[Any, Any]:
        return Bimap(lambda a: (a, lambda b: b))

    @staticmethod
    def when(cond: Callable[[A], bool],
             then: Bimap[A, B],
             otherwise: Optional[Bimap[A, C]] = None) -> Bimap[A, A | B | C]:
        def when_run(a:A) -> Tuple[A | B | C, Callable[[A | B | C], A]]:
            bimap = then if cond(a) else (otherwise if otherwise is not None else Bimap.identity())
            abc, inv = bimap(a)
            def inv_f(b: Any) -> A:
                return inv(b)
            return abc, inv_f
        return Bimap(when_run)
    
    

@dataclass(frozen=True)
class Biarrow(Generic[S, A, B]):
    forward: Callable[[S, A], Tuple[S, B]]
    inverse: Callable[[S, B], Tuple[S, A]]
    def __rshift__(self, other: Biarrow[S, B, C]) -> Biarrow[S, A, C]:
        def fwd(s: S, a: A) -> Tuple[S, C]:
            s1, b = self.forward(s, a)
            return other.forward(s1, b)
        def inv(s: S, c: C) -> Tuple[S, A]:
            s1, b = other.inverse(s, c)
            return self.inverse(s1, b)
        return Biarrow(
            forward=fwd,
            inverse=inv
        )
    @staticmethod
    def identity()->Biarrow[S, A, A]:
        return Biarrow(
            forward=lambda s, x: (s, x),
            inverse=lambda s, y: (s, y)
        )
            
    @staticmethod
    def when(condition: Callable[..., bool], 
             then: Biarrow[S, A, B], 
             otherwise: Optional[Biarrow[S, A, B]] = None) -> Callable[..., Biarrow[S, A, B]]:
        def _when(*args:Any, **kwargs:Any) -> Biarrow[S, A, B]:
            return then if condition(*args, **kwargs) else (otherwise or Biarrow.identity())
        return _when
    

@dataclass(frozen=True)    
class AST:
    pass

class ChoiceKind(Enum):
    LEFT = 'left'
    RIGHT = 'right'
    
@dataclass(frozen=True)
class Choice(Generic[A, B], AST):
    kind: ChoiceKind
    left: Optional[A] 
    right: Optional[B] 


@dataclass(frozen=True)
class Many(Generic[A], AST):
    value: Tuple[A, ...]

@dataclass(frozen=True)
class Marked(Generic[A], AST):
    name: str
    value: A
class ThenKind(Enum):
    BOTH = '+'
    LEFT = '//'
    RIGHT = '>>'
    
FlatThen = Tuple[Any, ...]
MarkedThen = Tuple[Dict[str, Any] | Any, FlatThen]

@dataclass(eq=True, frozen=True)
class Then(Generic[A, B], AST):
    kind: ThenKind
    left: Optional[A]
    right: Optional[B]
        
@runtime_checkable
class TokenProtocol(Protocol):
    @property
    def token_type(self) -> Enum: ...
    @property
    def text(self) -> str: ...
    

@dataclass(frozen=True)
class Token:
    token_type: Enum
    text: str
    def __str__(self) -> str:
        return f"{self.token_type.name}({self.text})"
    
    def __repr__(self) -> str:
        return self.__str__()

    

@dataclass(frozen=True)
class TokenSpec:
    token_type: Optional[Enum] = None
    text: Optional[str] = None
    case_sensitive: bool = False
    regex: Optional[re.Pattern[str]] = None
        
    def is_valid(self, token: TokenProtocol) -> bool:
        type_match = self.token_type is None or token.token_type == self.token_type
        value_match = self.text is None or (token.text.strip() == self.text.strip() if self.case_sensitive else 
                                                    token.text.strip().upper() == self.text.strip().upper())
        value_match = value_match or (self.regex is not None and self.regex.fullmatch(token.text) is not None)
        return type_match and value_match




T = TypeVar('T', bound=TokenProtocol)  


ParseResult = Union[
    Then['ParseResult[T]', 'ParseResult[T]'], 
    Marked['ParseResult[T]'],
    Choice['ParseResult[T]', 'ParseResult[T]'],
    Many['ParseResult[T]'],
    T,
]



