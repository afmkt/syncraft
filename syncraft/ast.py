

from __future__ import annotations
from typing import (
    Optional, Any, TypeVar, Tuple,
    Generic, Union, TYPE_CHECKING,
    Hashable
)
if TYPE_CHECKING:
    from syncraft.vis import SVGVisualization
from dataclasses import dataclass
from enum import Enum
class SyncraftError(Exception):
    def __init__(self, message: str, offender: Any, expect: Any = None, **kwargs: Any) -> None:
        super().__init__(message)
        self.offender = offender
        self.expect = expect
        self.data = kwargs

    def __str__(self) -> str:
        base = super().__str__()
        details = f"Offender: {self.offender!r}"
        if self.expect is not None:
            details += f", Expected: {self.expect!r}"
        if self.data:
            details += ", " + ", ".join(f"{k}={v!r}" for k, v in self.data.items())
        return f"{base} ({details})"
    



A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
D = TypeVar('D')
S = TypeVar('S')  
S1 = TypeVar('S1')




@dataclass(frozen=True, slots=True)    
class AST:
    def vis(self, depth: int = 5) -> Optional[SVGVisualization]:
        try:
            from syncraft.vis import ast2svg
            svg_content = ast2svg(self, max_depth=depth)
            return svg_content
        except ImportError:
            return None
        
class MetaNothing(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        return instance is cls or super().__instancecheck__(instance)
    def __str__(cls)->str:
        return "Nothing"
    def __repr__(cls)->str:
        return "Nothing"
    def __bool__(cls)->bool:
        return False
@dataclass(frozen=True, slots=True)
class Nothing(metaclass=MetaNothing):
    """Singleton sentinel representing the absence of a value in the AST."""
    def __call__(self)-> Nothing:
        return self
    def __new__(cls):
        return cls
    def __bool__(self)->bool:
        return False
    def __str__(self)->str:
        return "Nothing"
    def __repr__(self)->str:
        return "Nothing"
    
@dataclass(frozen=True, slots=True)
class Lazy(AST, Generic[A]):
    value: A
    
    
class OrElseKind(Enum):
    LEFT = 'left'
    RIGHT = 'right'

OrElseKind.__str__ = lambda self: self.value   # type: ignore


@dataclass(frozen=True, slots=True)
class OrElse(AST):
    """Represent a binary alternative between left and right values.

    ``kind`` indicates which branch was taken, or ``None`` when unknown.
    """
    
    kind: Optional[OrElseKind]

    value: Optional[Any] = None


@dataclass(frozen=True, slots=True)
class Choice(AST, Generic[A]):
    index: Optional[int]
    value: Optional[A]




@dataclass(frozen=True, slots=True)
class Many(AST, Generic[A]):
    """A finite sequence of values within the AST."""
    value: Tuple[A, ...]







@dataclass(frozen=True, slots=True)
class Seq(AST):
    value: Tuple[Tuple[Any, bool], ...]





class ThenKind(Enum):
    BOTH = '+'
    LEFT = '//'
    RIGHT = '>>'

ThenKind.__str__ = lambda self: self.value   # type: ignore

@dataclass(frozen=True, slots=True)
class Then(AST, Generic[A, B]):
    """Pair two values with a composition kind (both, left, or right).

    The ``kind`` determines how values are combined.
    ``LEFT``/``RIGHT`` indicate single-sided results; ``BOTH`` flattens both
    sides.
    """
    kind: ThenKind
    left: A
    right: B


Char = TypeVar('Char', bound=Hashable)
@dataclass(frozen=True, slots=True)
class Token(AST, Generic[Char]):
    text: str | bytes | Tuple[Char, ...]
    token_type: Optional[Union[str, Enum]] = None    

    def __repr__(self) -> str:
        if isinstance(self.text, str):
            if self.token_type is None:
                return f"Token(text={self.text.strip()!r})"
            else:
                return f"Token(text={self.text.strip()!r}, token_type={self.token_type!r})"
        elif isinstance(self.text, bytes):
            if self.token_type is None:
                return f"Token(text={self.text.decode(errors='replace').strip()!r})"
            else:
                return f"Token(text={self.text.decode(errors='replace').strip()!r}, token_type={self.token_type!r})"
        elif isinstance(self.text, tuple):
            if self.token_type is None:
                return f"Token(text={''.join(str(c) for c in self.text).strip()!r})"
            else:
                return f"Token(text={''.join(str(c) for c in self.text).strip()!r}, token_type={self.token_type!r})"
        else:
            raise SyncraftError("Unsupported type for Token text", offender=self.text, expect="str, bytes, or tuple")

    def __str__(self) -> str:
        if isinstance(self.text, str):
            if self.token_type is None:
                return f"t.{self.text.strip()}"
            else:
                return f"t.({self.text.strip()}, {self.token_type})"
        elif isinstance(self.text, bytes):
            if self.token_type is None:
                return f"t.{self.text.decode(errors='replace').strip()}"
            else:
                return f"t.({self.text.decode(errors='replace').strip()}, {self.token_type})"
        elif isinstance(self.text, tuple):
            if self.token_type is None:
                return f"t.({''.join(str(c) for c in self.text).strip()})"
            else:
                return f"t.({''.join(str(c) for c in self.text).strip()}, {self.token_type})"
        else:
            raise SyncraftError("Unsupported type for Token text", offender=self.text, expect="str, bytes, or tuple")
        
T = TypeVar('T', bound=Hashable)


#: Union-like type describing the shape of AST parse results across nodes.
ParseResult = Union[
    Lazy['ParseResult[T]'],
    Then['ParseResult[T]', 'ParseResult[T]'], 
    OrElse,
    Many['ParseResult[T]'],
    Nothing,
    Token,
    T,
]



