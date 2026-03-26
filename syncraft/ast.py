

from __future__ import annotations
from typing import (
    Optional, Any, TypeVar, Tuple,
    Union, 
    Hashable, Callable
)
from dataclasses import dataclass

class SyncraftError(Exception):
    """
    Custom exception class for errors encountered during AST processing in Syncraft.
    Attributes:
        message: A descriptive error message.
        offender: The value or node that caused the error.
        expect: An optional value or type that was expected instead of the offender.
        soft_failure: A boolean flag indicating whether this error should be treated as a soft failure (i.e., non-fatal and backtracking) or a hard failure (i.e., critical error that should halt processing).
    """
    def __init__(self, message: str, offender: Any, expect: Any = None, soft_failure: bool = False, **kwargs: Any) -> None:
        super().__init__(message)
        self.offender = offender
        self.expect = expect
        self.data = kwargs
        self.soft_failure = soft_failure

    def __str__(self) -> str:
        base = super().__str__()
        details = f"Offender: {self.offender!r}"
        if self.expect is not None:
            details += f", Expected: {self.expect!r}"
        if self.data:
            details += ", " + ", ".join(f"{k}={v!r}" for k, v in self.data.items())
        return f"{base} ({details})"


class _SingletonBase:
    def __call__(self) -> Any:
        return self

    def __new__(cls) -> Any:
        return cls

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return type(self).__name__

    def __repr__(self) -> str:
        return type(self).__name__


def singleton(name: str, doc: str, boolean: bool = False) -> type[_SingletonBase]:
    class _SingletonMeta(type):
        def __instancecheck__(cls, instance: Any) -> bool:
            return instance is cls or super().__instancecheck__(instance)

        def __str__(cls) -> str:
            return name

        def __repr__(cls) -> str:
            return name

        def __bool__(cls) -> bool:
            return boolean

    class _Singleton(_SingletonBase, metaclass=_SingletonMeta):
        __doc__ = doc

    _SingletonMeta.__name__ = f"Meta{name}"
    _Singleton.__name__ = name
    _Singleton.__qualname__ = name
    return _Singleton


Nothing = singleton(
    "Nothing",
    """
    Singleton sentinel representing the absence of a value in the AST.

    This is a VALID result meaning: "I know there's a node, and it has no value."
    Used when parsing optional grammar rules that didn't match.
    """
)
EOF = singleton("EOF", "Singleton sentinel representing end of input.")
Unknown = singleton(
    "Unknown",
    """
    Singleton sentinel representing an unknown value.

    This is STRONGER than Nothing: it means "zero information about the AST,
    not even the existence of the node is known." Used in generation when
    no input data is provided - the system doesn't know if there's supposed
    to be a node here at all.

    Key difference from Nothing:
    - Nothing: Node exists, but value is empty (known absence)
    - Unknown: Node existence is unknown (no information)
    """
)

def guard(f: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """
    Decorator to guard a function against Unknown and Nothing values.
    If the input is Unknown or Nothing, the function will return the same sentinel value.
    """
    def wrapper(a: Any) -> Any:
        if a is Unknown:
            return Unknown
        if a is Nothing:
            return Nothing
        return f(a)
    return wrapper



@dataclass(frozen=True, slots=True)    
class AST:
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
    
    value: Tuple[Any, ...]

@dataclass(frozen=True, slots=True)
class Seq(AST):
    value: Tuple[Tuple[Any, bool], ...]

        
T = TypeVar('T', bound=Hashable)


#: Union-like type describing the shape of AST parse results across nodes.
ParseResult = Union[
    Lazy,
    Many,
    Alt,
    Seq,
    Unknown, Nothing, # type: ignore
    T,
]



