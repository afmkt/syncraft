from __future__ import annotations

from typing import (
    Any, TypeVar, 
    Generic, Callable, overload, Literal
)
from dataclasses import dataclass,field


A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
    
def identity(x: Any) -> Any:
    return x

@dataclass(frozen=True, slots=True)
class Iso(Generic[A, B]):
    forward: Callable[[A], B] = field(default=identity)
    inverse: Callable[[B], A] = field(default=identity)


    def __iter__(self):
        yield from (self.forward, self.inverse)

    def __len__(self) -> int:
        return 2
    

    @overload
    def __getitem__(self, index: Literal[0]) -> Callable[[A], B]: ...
    @overload
    def __getitem__(self, index: Literal[1]) -> Callable[[B], A]: ...
    def __getitem__(self, index: int | slice) -> Any:
        if index == 0:
            return self.forward
        elif index == 1:
            return self.inverse
        else:
            raise IndexError("Index out of range for Iso, valid indices are 0 and 1")

    def fmap(self, a : A) -> B:
        return self.forward(a)
    
    def imap(self, b : B) -> A:
        return self.inverse(b)

    def __rshift__(self, other: Iso[B, C]) -> Iso[A, C]:
        return Iso(lambda a: other.forward(self.forward(a)),
                   lambda c: self.inverse(other.inverse(c)))

    def __rrshift__(self, other: Iso[C, A]) -> Iso[C, B]:
        return Iso(lambda c: self.forward(other.forward(c)),
                   lambda b: other.inverse(self.inverse(b)))
    
    def __neg__(self) -> Iso[B, A]:
        return Iso(self.inverse, self.forward)

    @classmethod
    def const(cls, a: A, b: B) -> Iso[A, B]:
        return cls(lambda _: b, lambda _: a)


class Mapper:
    @staticmethod
    def eval(func: Callable[..., Any], *args, **kwargs) -> Any:
        if isinstance(func, Mapper):
            return func(*args, **kwargs)
        else:
            return func
        
    def __init__(self, func: Callable[..., Any]):
        self.func = func

    def __call__(self, *args, **kwargs) -> Any:
        return self.func(*args, **kwargs)
    
    def __add__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) + Mapper.eval(other, *args, **kwargs))
    
    def __radd__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(other, *args, **kwargs) + self.func(*args, **kwargs))
    
    def __mul__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) * Mapper.eval(other, *args, **kwargs))
    
    def __rmul__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(other, *args, **kwargs) * self.func(*args, **kwargs))
    
    def __div__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) / Mapper.eval(other, *args, **kwargs))
    
    def __rdiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(other, *args, **kwargs) / self.func(*args, **kwargs))
    
    def __floordiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) // Mapper.eval(other, *args, **kwargs))
    
    def __rfloordiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(other, *args, **kwargs) // self.func(*args, **kwargs))
    
    def __sub__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) - Mapper.eval(other, *args, **kwargs))
    
    def __rsub__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(other, *args, **kwargs) - self.func(*args, **kwargs))
    
    def __neg__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: -self.func(*args, **kwargs))
    
    def __pos__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: +self.func(*args, **kwargs))  
    
    def __abs__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: abs(self.func(*args, **kwargs)))
    
    def __getitem__(self, index: Any ) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs)[Mapper.eval(index, *args, **kwargs)])
    
    def __or__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) | Mapper.eval(other, *args, **kwargs))
    
    def __ror__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(other, *args, **kwargs) | self.func(*args, **kwargs))
    
    def __and__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) & Mapper.eval(other, *args, **kwargs))
    
    def __rand__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(other, *args, **kwargs) & self.func(*args, **kwargs))
    
    def __invert__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: ~self.func(*args, **kwargs))  
    
    @property
    def not_(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: not self.func(*args, **kwargs))
    
    def __xor__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) ^ Mapper.eval(other, *args, **kwargs))
    
    def __rxor__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(other, *args, **kwargs) ^ self.func(*args, **kwargs))
    
    def bool(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: bool(self.func(*args, **kwargs)))
    
    def __not__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: not self.func(*args, **kwargs))
    
    def __int__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: int(self.func(*args, **kwargs)))
    
    def __float__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: float(self.func(*args, **kwargs)))
        
    def __length_hint__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: len(self.func(*args, **kwargs)))
    
    def __len__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: len(self.func(*args, **kwargs)))  
    
    def __contains__(self, item: Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(item, *args, **kwargs) in self.func(*args, **kwargs))
    
    def __iter__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: iter(self.func(*args, **kwargs)))
    
    def __reversed__(self) -> Mapper:
        return Mapper(lambda *args, **kwargs: reversed(self.func(*args, **kwargs)))
    
    def __eq__(self, other: Any):
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) == Mapper.eval(other, *args, **kwargs))
    
    def __ne__(self, other: Any):
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) != Mapper.eval(other, *args, **kwargs))
    
    def __lt__(self, other: Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) < Mapper.eval(other, *args, **kwargs))
    
    def __le__(self, other: Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) <= Mapper.eval(other, *args, **kwargs))
    
    def __gt__(self, other: Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) > Mapper.eval(other, *args, **kwargs))
    
    def __ge__(self, other: Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: self.func(*args, **kwargs) >= Mapper.eval(other, *args, **kwargs))
        
    def if_then_else(self, then_mapper: Mapper | Any, else_mapper: Mapper | Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: Mapper.eval(then_mapper, *args, **kwargs) if self.func(*args, **kwargs) else Mapper.eval(else_mapper, *args, **kwargs))
    
    @staticmethod
    def arg(index: int | str) -> Mapper:
        if isinstance(index, str):
            return Mapper(lambda *args, **kwargs: kwargs[index])
        elif isinstance(index, int):
            return Mapper(lambda *args, **kwargs: args[index])
        else:
            raise TypeError("Index must be an integer or string")

    @staticmethod
    def const(value: Any) -> Mapper:
        return Mapper(lambda *args, **kwargs: value)
    

    @staticmethod
    def callable(func: Callable[..., Any]) -> Mapper:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            unnamed_args = []
            named_args = {}
            for v in args:
                if isinstance(v, Mapper):
                    unnamed_args.append(v(*args, **kwargs))
                else:
                    unnamed_args.append(v)
            for k, v in kwargs.items():
                if isinstance(v, Mapper):
                    named_args[k] = v(*args, **kwargs)
                else:
                    named_args[k] = v
            return func(*unnamed_args, **named_args)
        return Mapper(wrapped)


def call(c: Callable[..., Any], *args: Any, **kwargs: Any) -> Mapper:
    def bound(t: list|tuple) -> Any:
        unnamed_args = []
        named_args = {}
        for v in args:
            if isinstance(v, Mapper):
                unnamed_args.append(v(t))
            else:
                unnamed_args.append(v)
        for k, v in kwargs.items():
            if isinstance(v, Mapper):
                named_args[k] = v(t)
            else:
                named_args[k] = v
        return c(*unnamed_args, **named_args)
    return Mapper(bound)

