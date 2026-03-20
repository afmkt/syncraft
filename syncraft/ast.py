

from __future__ import annotations
from typing import (
    Optional, Any, TypeVar, Tuple,
    Union, Protocol, runtime_checkable, 
    Hashable, Iterator, Callable, List
)
from dataclasses import dataclass
from enum import Enum
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
    def wrapper(a: Any) -> Any:
        if a is Unknown:
            return Unknown
        if a is Nothing:
            return Nothing
        return f(a)
    return wrapper

class WalkEvent(Enum):
    ENTER = "enter"
    EXIT = "exit"
    ATOMIC = "atomic"


@runtime_checkable
class Walkable(Protocol):
    def walk(self, stack: List[Walkable | Any], keep: bool) -> Iterator[Tuple[WalkEvent, List[Walkable | Any], bool]]:
        ...
@dataclass(frozen=True, slots=True)    
class AST(Walkable):
    """
    Base class for all raw AST nodes in Syncraft. 
    """
        
    def walk(self, stack: List[Walkable | Any], keep: bool) -> Iterator[Tuple[WalkEvent, List[Walkable | Any], bool]]:
        """
        Walk the AST, yielding events for entering and exiting nodes, as well as atomic values.
        Args:
            stack: The current traversal stack, which will be modified in-place. 
                   The current node will be appended to the stack before yielding events and popped afterward.
            keep: A boolean flag indicating whether the current node or any of its ancestors is kept in the AST. 
                  Seq node stores its chiildren's keep flags, which are combined with the current keep flag when yielding events for child nodes.
                  
        Yields:
            A tuple of (WalkEvent, current stack, keep flag) for each event during the walk.
        """
        stack.append(self)
        try:
            yield (WalkEvent.ATOMIC, stack, keep)
        finally:
            stack.pop()




@dataclass(frozen=True, slots=True)
class Lazy(AST):
    value: Any
    def walk(self, stack: List[Walkable | Any], keep: bool) -> Iterator[Tuple[WalkEvent, List[Walkable | Any], bool]]:
        stack.append(self)
        try:
            yield (WalkEvent.ENTER, stack, keep)
            if isinstance(self.value, AST):
                yield from self.value.walk(stack, keep)
            else:
                stack.append(self.value)
                try:
                    yield (WalkEvent.ATOMIC, stack, keep)
                finally:
                    stack.pop()
            yield (WalkEvent.EXIT, stack, keep)
        finally:
            stack.pop()
    

@dataclass(frozen=True, slots=True)
class Alt(AST):
    index: Optional[int]
    value: Optional[Any]

    def walk(self, stack: List[Walkable | Any], keep: bool) -> Iterator[Tuple[WalkEvent, List[Walkable | Any], bool]]:
        stack.append(self)
        try:
            yield (WalkEvent.ENTER, stack, keep)
            if isinstance(self.value, AST):
                yield from self.value.walk(stack, keep)
            else:
                stack.append(self.value)
                try:
                    yield (WalkEvent.ATOMIC, stack, keep)
                finally:
                    stack.pop()
            yield (WalkEvent.EXIT, stack, keep)
        finally:
            stack.pop()


@dataclass(frozen=True, slots=True)
class Many(AST):
    
    value: Tuple[Any, ...]
    def walk(self, stack: List[Walkable | Any], keep: bool) -> Iterator[Tuple[WalkEvent, List[Walkable | Any], bool]]:
        stack.append(self)
        try:
            yield (WalkEvent.ENTER, stack, keep)
            for item in self.value:
                if isinstance(item, AST):
                    yield from item.walk(stack, keep)
                else:
                    stack.append(item)
                    try:
                        yield (WalkEvent.ATOMIC, stack, keep)
                    finally:
                        stack.pop()
            yield (WalkEvent.EXIT, stack, keep)
        finally:
            stack.pop()

@dataclass(frozen=True, slots=True)
class Seq(AST):
    value: Tuple[Tuple[Any, bool], ...]
    def walk(self, stack: List[Walkable | Any], keep: bool) -> Iterator[Tuple[WalkEvent, List[Walkable | Any], bool]]:
        stack.append(self)
        try:
            yield (WalkEvent.ENTER, stack, keep)
            for item, _keep in self.value:
                if isinstance(item, AST):
                    yield from item.walk(stack, keep and _keep)
                else:
                    stack.append(item)
                    try:
                        yield (WalkEvent.ATOMIC, stack, keep and _keep)
                    finally:
                        stack.pop()
            yield (WalkEvent.EXIT, stack, keep)
        finally:
            stack.pop()










@dataclass(frozen=True, slots=True)
class Token:
    """
    A typical structureal terminal token
    """
    text: str | bytes | Tuple[Any, ...]
    token_type: Optional[Union[str, Enum]] = None   

    def to_str(self) -> str:
        if isinstance(self.text, str):
            return self.text.strip()
        elif isinstance(self.text, bytes):
            return self.text.decode('utf-8', errors='replace').strip()
        elif isinstance(self.text, tuple):
            return ''.join(str(c) for c in self.text).strip()
        else:
            raise SyncraftError(f"Unsupported type {type(self.text)} for Token text", offender=self.text, expect="str, bytes, or tuple")

    def __repr__(self) -> str:        
        if self.token_type is None:
            return f"Token(text={self.to_str()!r})"
        else:
            return f"Token(text={self.to_str()!r}, token_type={self.token_type!r})"

    def __str__(self) -> str:
        if self.token_type is None:
            return f"t.{self.to_str().strip()}"        
        else:            
            return f"t.({self.to_str().strip()}, {self.token_type})"
        
T = TypeVar('T', bound=Hashable)


#: Union-like type describing the shape of AST parse results across nodes.
ParseResult = Union[
    Lazy,
    Many,
    Alt,
    Seq,
    Nothing,
    Unknown,
    T,
]

def map(f: Callable[[Any], Any]):
    """
    Create a transducer that applies a function to each item before reducing it.
    Args:
    f: A function that takes an item and returns a transformed item.
    Returns:
    A transducer function that can be used to create a new reducer that applies the transformation before reducing.
    """
    def transducer(reducer: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
        """
        Wrap the original reducer to apply the transformation function `f` to each item before reducing it.
        Args:
        reducer: The original reducer function that takes an accumulator and an item and returns a new accumulator.
        Returns:
        A new reducer function that applies the transformation function `f` to each item before reducing it
        """
        def wrapped(acc: Any, item: Any) -> Any:
            return reducer(acc, f(item))
        return wrapped
    return transducer

def filter(pred: Callable[[Any], bool]):
    """
    Create a transducer that filters items based on a predicate function.
    
    Args:
        pred: A function that takes an item and returns True if the item should be kept, False otherwise.
        
    Returns:
        A transducer function that can be used to create a new reducer that only processes items that satisfy the predicate.
    """
    def transducer(reducer: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
        """
        Wrap the original reducer to only apply it to items that satisfy the predicate function `pred`.
        Args:
            reducer: The original reducer function that takes an accumulator and an item and returns a new accumulator.
        Returns:
            A new reducer function that only applies the original reducer to items that satisfy the predicate function `
        """
        def wrapped(acc: Any, item: Any) -> Any:
            if pred(item):
                return reducer(acc, item)
            return acc
        return wrapped
    return transducer


def compose(*transducers: Callable[[Callable[[Any, Any], Any]], Callable[[Any, Any], Any]]) -> Callable[[Callable[[Any, Any], Any]], Callable[[Any, Any], Any]]:
    """Compose multiple transducers into a single transducer that applies them in sequence."""
    def composed(reducer: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
        for transducer in reversed(transducers):
            reducer = transducer(reducer)
        return reducer
    return composed





