

from __future__ import annotations
import re
from typing import (
    Optional, Any, TypeVar, Tuple, runtime_checkable, Self,
    Dict, Generic, Callable, Union, Protocol
)


from dataclasses import dataclass
from enum import Enum
from syncraft.constraint import Bindable



A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
D = TypeVar('D')
S = TypeVar('S', bound=Bindable)  

@dataclass(frozen=True)
class Biarrow(Generic[A, B]):
    forward: Callable[[A], B]
    inverse: Callable[[B], A]
    def __rshift__(self, other: Biarrow[B, C]) -> Biarrow[A, C]:
        def fwd(a: A) -> C:
            b = self.forward(a)
            return other.forward(b)
        def inv(c: C) -> A:
            b = other.inverse(c)
            return self.inverse(b)
        return Biarrow(
            forward=fwd,
            inverse=inv
        )
    @staticmethod
    def identity()->Biarrow[A, A]:
        return Biarrow(
            forward=lambda x: x,
            inverse=lambda y: y
        )
            
    @staticmethod
    def when(condition: Callable[..., bool], 
             then: Biarrow[A, B], 
             otherwise: Optional[Biarrow[A, B]] = None) -> Callable[..., Biarrow[A, B]]:
        def _when(*args:Any, **kwargs:Any) -> Biarrow[A, B]:
            return then if condition(*args, **kwargs) else (otherwise or Biarrow.identity())
        return _when

@dataclass(frozen=True)
class Reducer(Generic[A, S]):
    run_f: Callable[[A, S], S]
    def __call__(self, a: A, s: S) -> S:
        return self.run_f(a, s)
    
    def map(self, f: Callable[[B], A]) -> Reducer[B, S]:
        def map_run(b: B, s: S) -> S:
            return self(f(b), s)
        return Reducer(map_run)
    
    def __rshift__(self, other: Reducer[A, S]) -> Reducer[A, S]:
        return Reducer(lambda a, s: other(a, self(a, s)))
    
@dataclass(frozen=True)
class Bimap(Generic[A, B]):
    run_f: Callable[[A], Tuple[B, Callable[[B], A]]]
    def __call__(self, a: A) -> Tuple[B, Callable[[B], A]]:
        return self.run_f(a)    
    def __rshift__(self, other: Bimap[B, C] | Biarrow[B, C]) -> Bimap[A, C]:
        if isinstance(other, Biarrow):
            def biarrow_then_run(a: A) -> Tuple[C, Callable[[C], A]]:
                b, inv1 = self(a)
                c = other.forward(b)
                def inv(c2: C) -> A:
                    b2 = other.inverse(c2)
                    return inv1(b2)
                return c, inv
            return Bimap(biarrow_then_run)
        elif isinstance(other, Bimap):
            def bimap_then_run(a: A) -> Tuple[C, Callable[[C], A]]:
                b, inv1 = self(a)
                c, inv2 = other(b)
                def inv(c2: C) -> A:
                    return inv1(inv2(c2))
                return c, inv
            return Bimap(bimap_then_run)
        else:
            raise TypeError(f"Unsupported type for Bimap >>: {type(other)}")
    def __rrshift__(self, other: Bimap[C, A] | Biarrow[C, A]) -> Bimap[C, B]:
        if isinstance(other, Biarrow):
            def biarrow_then_run(c: C) -> Tuple[B, Callable[[B], C]]:
                a = other.forward(c)
                b2, inv1 = self(a)
                def inv(a2: B) -> C:
                    a3 = inv1(a2)
                    return other.inverse(a3)
                return b2, inv
            return Bimap(biarrow_then_run)
        elif isinstance(other, Bimap):
            def bimap_then_run(c: C)->Tuple[B, Callable[[B], C]]:
                a, a2c = other(c)
                b2, b2a = self(a)
                def inv(b3: B) -> C:
                    a2 = b2a(b3)
                    return a2c(a2)
                return b2, inv
            return Bimap(bimap_then_run)
        else:
            raise TypeError(f"Unsupported type for Bimap <<: {type(other)}")


    @staticmethod
    def const(a: B)->Bimap[B, B]:
        return Bimap(lambda _: (a, lambda b: b))

    @staticmethod
    def identity()->Bimap[A, A]:
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
class AST:
    pass

@dataclass(frozen=True)
class Nothing(AST):
    def __str__(self)->str:
        return self.__class__.__name__
    def __repr__(self)->str:
        return self.__str__()
    


class ChoiceKind(Enum):
    LEFT = 'left'
    RIGHT = 'right'
    
@dataclass(frozen=True)
class Choice(Generic[A, B], AST):
    kind: Optional[ChoiceKind]
    value: Optional[A | B] = None


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
    left: A
    right: B


@dataclass(frozen=True)
class Token(AST):
    token_type: Enum
    text: str
    def __str__(self) -> str:
        return f"{self.token_type.name}({self.text})"
    
    def __repr__(self) -> str:
        return self.__str__()

        
@runtime_checkable
class TokenProtocol(Protocol):
    @property
    def token_type(self) -> Enum: ...
    @property
    def text(self) -> str: ...

T = TypeVar('T', bound=TokenProtocol)  


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


ParseResult = Union[
    Then['ParseResult[T]', 'ParseResult[T]'], 
    Marked['ParseResult[T]'],
    Choice['ParseResult[T]', 'ParseResult[T]'],
    Many['ParseResult[T]'],
    Nothing,
    T,
]



