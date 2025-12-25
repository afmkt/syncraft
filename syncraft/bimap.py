from __future__ import annotations
from typing import (
    Any, TypeVar, Tuple, 
    Generic, Callable,
    overload, Literal
)
from dataclasses import dataclass


A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
    
def identity(x: Any) -> Any:
    return x

class Reversible(Generic[A, B]):
    """A value paired with a function to reverse/invert a transformation.
    
    Reversible wraps a forward-transformed value along with a mapper function
    that can reverse the transformation. This is essential for bidirectional
    parsing and generation, enabling round-trip conversions between AST and
    data structures.
    
    The Reversible is used extensively with Syntax.bimap() and Syntax.iso()
    to maintain invertibility of transformations during parsing and generation.
    
    Type Parameters:
        A: The original type before transformation.
        B: The transformed type.
    
    Args:
        value: The forward-transformed value of type B.
        mapper: Function that reverses the transformation (B -> A).
                Defaults to identity function.
    
    Example:
        >>> # Transform string to int, with reverse function
        >>> rev = Reversible(42, lambda x: str(x))
        >>> rev.value  # 42
        >>> rev.mapper(100)  # "100"
        
        >>> # Used in grammar for bidirectional mapping
        >>> syntax.bimap(lambda s: Reversible(int(s), str))
    """
    def __init__(self, value: B, mapper: Callable[[B], A] = identity) -> None:
        self._data: Tuple[B, Callable[[B], A]] = (value, mapper)

    def __iter__(self):
        yield from self._data

    def __len__(self) -> int:
        return len(self._data)
    
    @overload
    def __getitem__(self, index: Literal[0]) -> B: ...
    @overload
    def __getitem__(self, index: Literal[1]) -> Callable[[B], A]: ...
    def __getitem__(self, index: int | slice) -> Any:
        return self._data[index]
    @property
    def value(self) -> B:
        return self._data[0]
    @property
    def mapper(self) -> Callable[[B], A]:
        return self._data[1]
    
    

@dataclass(frozen=True, slots=True)
class Bimap(Generic[A, B]):
    """A reversible mapping that returns both a forward value and an inverse function.

    ``Bimap`` is like a function ``A -> B`` paired with a way to map a value
    of type ``B`` back into an ``A``. It composes with other ``Bimap``s or a
    ``Biarrow`` using ``>>`` and ``<<``-style operations, preserving an
    automatically derived inverse.
    """
    run_f: Callable[[A], Reversible[A, B]]
    def __call__(self, a: A) -> Reversible[A, B]:
        """Apply the mapping to ``a``.

        Returns:
            tuple: ``(forward_value, inverse)`` where ``inverse`` maps
            a compatible ``B`` back into an ``A``.
        """
        return self.run_f(a)    
    
    def __rshift__(self, other: Bimap[B, C]) -> Bimap[A, C]:
        """Compose this mapping with another mapping/arrow.

        ``self >> other`` first applies ``self``, then ``other``. The produced
        inverse runs ``other``'s inverse followed by ``self``'s inverse.
        """
        def bimap_then_run(a: A) -> Reversible[A, C]:
            a2b = self(a)
            b2c = other(a2b.value)
            def inv(c2: C) -> A:
                return a2b.mapper(b2c.mapper(c2))
            return Reversible(b2c.value, inv)
        return Bimap(bimap_then_run)

    def __rrshift__(self, other: Bimap[C, A]) -> Bimap[C, B]:
        """Right-composition so arrows or bimaps can be on the left of ``>>``."""
        def bimap_then_run(c: C)->Reversible[C, B]:
            c2a = other(c)
            a2b = self(c2a.value)
            def inv(b: B) -> C:
                return c2a.mapper(a2b.mapper(b))
            return Reversible(a2b.value, inv)
        return Bimap(bimap_then_run)


    @staticmethod
    def const(a: B) -> Bimap[B, B]:
        """Return a bimap that ignores input and always yields ``a``.

        The inverse is identity for the output type.
        """
        return Bimap(lambda _: Reversible(a, lambda b: b))

    @staticmethod
    def identity() -> Bimap[A, A]:
        """The identity bimap where forward and inverse are no-ops."""
        return Bimap(lambda a: Reversible(a, lambda b: b))
    
    @staticmethod
    def iso(f: Callable[[A], B], i: Callable[[B], A]) -> Bimap[A, B]:
        """Create a bimap from a pair of inverse functions."""
        def iso_f(a: A) -> Reversible[A, B]:
            return Reversible(f(a), i)
        return Bimap(iso_f)
