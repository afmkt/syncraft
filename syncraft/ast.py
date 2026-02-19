

from __future__ import annotations
from typing import (
    Optional, Any, TypeVar, Tuple,
    Union, TYPE_CHECKING, 
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
class Unknown(AST):
    pass


@dataclass(frozen=True, slots=True)
class Lazy(AST):
    value: Any
    

@dataclass(frozen=True, slots=True)
class Alt(AST):
    index: Optional[int]
    value: Optional[Any]




@dataclass(frozen=True, slots=True)
class Many(AST):
    """A finite sequence of values within the AST."""
    value: Tuple[Any, ...]

@dataclass(frozen=True, slots=True)
class Seq(AST):
    value: Tuple[Tuple[Any, bool], ...]










@dataclass(frozen=True, slots=True)
class Token(AST):
    text: str | bytes | Tuple[Any, ...]
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
    Lazy,
    Many,
    Alt,
    Seq,
    Nothing,
    Token,
    Unknown,
    T,
]



                



    

