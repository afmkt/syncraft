from __future__ import annotations
from typing import Any, Callable, Dict, Type

class Mapper:
    @staticmethod
    def eval(func: Any, value: Any) -> Any:
        if isinstance(func, Mapper):
            return func(value)
        else:
            return func
    def __init__(self, func: Callable[[Any], Any]):
        self.func = func

    def __call__(self, value: Any) -> Any:
        return self.func(value)
    
    def __add__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) + Mapper.eval(other, t))
    
    def __radd__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) + self.func(t))
    
    def __mul__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) * Mapper.eval(other, t))
    
    def __rmul__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) * self.func(t))
    
    def __div__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) / Mapper.eval(other, t))
    
    def __rdiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) / self.func(t))
    
    def __floordiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) // Mapper.eval(other, t))
    
    def __rfloordiv__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) // self.func(t))
    
    def __sub__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) - Mapper.eval(other, t))
    
    def __rsub__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) - self.func(t))
    
    def __neg__(self) -> Mapper:
        return Mapper(lambda t: -self.func(t))
    
    def __pos__(self) -> Mapper:
        return Mapper(lambda t: +self.func(t))  
    
    def __abs__(self) -> Mapper:
        return Mapper(lambda t: abs(self.func(t)))
    
    def __getitem__(self, index: Any ) -> Mapper:
        return Mapper(lambda t: self.func(t)[Mapper.eval(index, t)])
    
    def __or__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) | Mapper.eval(other, t))
    
    def __ror__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) | self.func(t))
    
    def __and__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) & Mapper.eval(other, t))
    
    def __rand__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) & self.func(t))
    
    def __invert__(self) -> Mapper:
        return Mapper(lambda t: ~self.func(t))  
    
    @property
    def not_(self) -> Mapper:
        return Mapper(lambda t: not self.func(t))
    
    def __xor__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: self.func(t) ^ Mapper.eval(other, t))
    
    def __rxor__(self, other: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(other, t) ^ self.func(t))
    
    def bool(self) -> Mapper:
        return Mapper(lambda t: bool(self.func(t)))
    
    def __not__(self) -> Mapper:
        return Mapper(lambda t: not self.func(t))
    
    def __int__(self) -> Mapper:
        return Mapper(lambda t: int(self.func(t)))
    
    def __float__(self) -> Mapper:
        return Mapper(lambda t: float(self.func(t)))
        
    def __length_hint__(self) -> Mapper:
        return Mapper(lambda t: len(self.func(t)))
    
    def __len__(self) -> Mapper:
        return Mapper(lambda t: len(self.func(t)))  
    
    def __contains__(self, item: Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(item, t) in self.func(t))
    
    def __iter__(self) -> Mapper:
        return Mapper(lambda t: iter(self.func(t)))
    
    def __reversed__(self) -> Mapper:
        return Mapper(lambda t: reversed(self.func(t)))
    
    def __eq__(self, other: Any):
        return Mapper(lambda t: self.func(t) == Mapper.eval(other, t))
    
    def __ne__(self, other: Any):
        return Mapper(lambda t: self.func(t) != Mapper.eval(other, t))
    
    def __lt__(self, other: Any) -> Mapper:
        return Mapper(lambda t: self.func(t) < Mapper.eval(other, t))
    
    def __le__(self, other: Any) -> Mapper:
        return Mapper(lambda t: self.func(t) <= Mapper.eval(other, t))
    
    def __gt__(self, other: Any) -> Mapper:
        return Mapper(lambda t: self.func(t) > Mapper.eval(other, t))
    
    def __ge__(self, other: Any) -> Mapper:
        return Mapper(lambda t: self.func(t) >= Mapper.eval(other, t))
    
    def apply(self, func: Callable[[Any], Any]) -> Mapper:
        return Mapper(lambda t: func(self.func(t)))
    
    def if_then_else(self, then_mapper: Mapper | Any, else_mapper: Mapper | Any) -> Mapper:
        return Mapper(lambda t: Mapper.eval(then_mapper, t) if self.func(t) else Mapper.eval(else_mapper, t))
    
    @property
    def list(self) -> Mapper:
        def to_list(t: Any) -> list:
            return [self.func(t)]
        return Mapper(to_list)
    
    @property
    def tuple(self) -> Mapper:
        def to_tuple(t: Any) -> tuple:
            return (self.func(t),)
        return Mapper(to_tuple)
    
    def dict(self, d: Dict) -> Mapper:
        def as_index_f(t: Any) -> Any:
            y = Mapper.eval(d, t)
            return y[self.func(t)]
        return Mapper(as_index_f)

def at(index: Any | None = None) -> Mapper:
    if index is None:
        return Mapper(lambda t: t)
    else:
        return Mapper(lambda t: t[index])

def const(value: Any) -> Mapper:
    return Mapper(lambda t: value)

_0 = at(0)
_1 = at(1)
_2 = at(2)
_3 = at(3)
_4 = at(4)
_5 = at(5)
_6 = at(6)
_7 = at(7)
_8 = at(8)
_9 = at(9)

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

class Record:
    def __init__(self, *unnamed: Any, **named: Any)->None:
        self._named = named
        self._unnamed = unnamed

    @property
    def unnamed(self):
        return self._unnamed

    def __repr__(self) -> str:
        parts = []
        if self._unnamed:
            parts.append(", ".join(repr(v) for v in self._unnamed))
        if self._named:
            parts.append(", ".join(f"{k}={v!r}" for k, v in self._named.items()))
        return f"{self.__class__.__name__}({', '.join(parts)})"

    def __getattr__(self, key: Any) -> Any:
        try:
            return self._named[key]
        except KeyError as e:
            raise AttributeError(f"'DotDict' object has no attribute '{key}'") from e
        
    def __getitem__(self, index: int | str | Mapper) -> Any:
        if isinstance(index, int):
            return self._unnamed[index]
        elif isinstance(index, str):
            return self._named[index]
        elif isinstance(index, Mapper):
            return index.dict(self._named)
        else:
            raise TypeError("Index must be an integer or string")

    @classmethod
    def create_cls(cls, name: str, base: type | None = None) -> Type[Record]:
        return type(name, (base, cls), {}) if base is not None else type(name, (cls,), {})
