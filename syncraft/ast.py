

from __future__ import annotations
from typing import (
    Optional, Any, TypeVar, Tuple, cast,
    Generic, Callable, Union, Protocol, Type, List, ClassVar, TYPE_CHECKING,
    Dict, Hashable, overload, Literal
)
if TYPE_CHECKING:
    from syncraft.vis import SVGVisualization
from syncraft.utils import Record
from dataclasses import dataclass, replace, is_dataclass, fields, field
from enum import Enum
from syncraft.utils import CallWith, MISSING

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


    
def identity(x: Any) -> Any:
    return x

class Reversible(Generic[A, B]):
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
    

@dataclass(frozen=True, slots=True)    
class AST:
    @property
    def custom_mapping(self) -> Optional[Bimap[Any, Any]]: ...

    
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return self

    _bimmapped_cache: Reversible[Any, Any] = field(default=MISSING, init=False, repr=False, compare=False, hash=False)
    @property
    def arity(self)->int:
        return 1
    @property
    def is_then(self)->bool:
        return False
    
    def _bimap(self) -> Reversible[Any, Any]:
        return Reversible(self)
    
    @property
    def bimap(self) -> Reversible[Any, Any]:
        if self._bimmapped_cache is MISSING:
            tmp = self._bimap()
            if self.custom_mapping is not None:
                value, invf = tmp
                v, f = self.custom_mapping(value)
                def composed_inv(c: Any) -> Any:
                    return invf(f(c))
                tmp = Reversible(v, composed_inv)
            object.__setattr__(self, '_bimmapped_cache', tmp)
        return self._bimmapped_cache
    
    @property
    def mapped(self) -> Any:
        return self.bimap.value
    
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
    flatten: bool 
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False)

    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 
        

    @property
    def arity(self)->int:
        if self.flatten:
            if isinstance(self.value, AST):
                return self.value.arity
        return 1
    
    @property
    def is_then(self) -> bool:
        return self.flatten and isinstance(self.value, AST) and self.value.is_then
    
    def _bimap(self) -> Reversible[Lazy[A], Any]:
        """Defer to the provided mapping ``r``."""
        tmp: Reversible[A, Any] = self.value.bimap if isinstance(self.value, AST) else Reversible(self.value)
        def invf(c: Any) -> Lazy[A]:
            return replace(self, value=tmp.mapper(c))    
        return Reversible(tmp.value, invf)


@dataclass(frozen=True, slots=True)
class Marked(AST, Generic[A]):
    """Annotate a AST node with a name.

    Used to tag subtrees so they can be collected by name later (e.g., in
    collectors) without altering the structural shape.
    """
    
    name: str
    value: A
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False)
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 

    def _bimap(self) -> Reversible[Marked[A], Marked[Any]]:
        """Transform the inner value while preserving the mark name.

        Returns a new ``Marked`` with transformed value and an inverse that
        expects a ``Marked`` to recover the original.
        """
        tmp : Reversible[A, Any] = self.value.bimap if isinstance(self.value, AST) else Reversible(self.value)
        def invf(m: Marked[Any]) -> Marked[A]:
            return Marked(name = m.name, value = tmp.mapper(m.value), custom_mapping=None)
        return Reversible(Marked(name=self.name, value=tmp.value, custom_mapping=None), invf)

    
class OrElseKind(Enum):
    LEFT = 'left'
    RIGHT = 'right'

OrElseKind.__str__ = lambda self: self.value   # type: ignore


@dataclass(frozen=True, slots=True)
class OrElse(AST, Generic[A, B]):
    """Represent a binary alternative between left and right values.

    ``kind`` indicates which branch was taken, or ``None`` when unknown.
    """
    
    kind: Optional[OrElseKind]
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False)
    value: Optional[A | B] = None
    
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 

    @property
    def arity(self)->int:
        if isinstance(self.value, AST):
            return self.value.arity
        return 1
    
    @property
    def is_then(self) -> bool:
        return isinstance(self.value, AST) and self.value.is_then

    def _bimap(self) -> Reversible[OrElse[A, B], Optional[Any]]:
        """Map over the held value if present; propagate ``None`` otherwise.

        The inverse resets ``kind`` to ``None`` to avoid biasing the result.
        When user edit the data we cannot assume which branch the data should go
        back to. Set ``kind`` to ``None`` to indicate this situation.
        """
        if self.value is None:
            return Reversible(None, lambda c: replace(self, value=None, kind=None))
        else:
            tmp: Reversible[A|B, Any] = self.value.bimap if isinstance(self.value, AST) else Reversible(self.value)
            def invf(c: Optional[Any]) -> OrElse[A, B]:
                return replace(self, value=tmp.mapper(c) if c is not None else None, kind=None)
            return Reversible(tmp.value, lambda c: invf(c))


@dataclass(frozen=True, slots=True)
class Choice(AST, Generic[A]):
    index: Optional[int]
    value: Optional[A]
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False)
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 

    @property
    def arity(self)->int:
        if isinstance(self.value, AST):
            return self.value.arity
        return 1
    
    @property
    def is_then(self) -> bool:
        return isinstance(self.value, AST) and self.value.is_then

    def _bimap(self) -> Reversible[Choice[A], Optional[Any]]:
        """Map over the held value if present; propagate ``None`` otherwise.

        The inverse resets ``index`` to ``None`` to avoid biasing the result.
        When user edit the data we cannot assume which branch the data should go
        back to. Set ``index`` to ``None`` to indicate this situation.
        """
        if self.value is None:
            return Reversible(None, lambda c: replace(self, value=None, index=None))
        else:
            tmp: Reversible[A, Any] = self.value.bimap if isinstance(self.value, AST) else Reversible(self.value)
            def invf(c: Optional[Any]) -> Choice[A]:
                return replace(self, value=tmp.mapper(c) if c is not None else None, index=None)
            return Reversible(tmp.value, invf)

@dataclass(frozen=True, slots=True)
class Many(AST, Generic[A]):
    """A finite sequence of values within the AST."""
    value: Tuple[A, ...]
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False)
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 

    def _bimap(self) -> Reversible[Many[A], List[Any]]:
        """Map each element to a list and provide an inverse.

        The inverse accepts a list of transformed elements. If the provided
        list is shorter than the original, only the prefix is used. If longer,
        the extra values are inverted using the last element's inverse.
        """
        ret : List[Reversible[A, Any]] = [v.bimap if isinstance(v, AST) else Reversible(v) for v in self.value]
        def inv(bs: List[Any]) -> Many[A]:
            if len(bs) <= len(ret):
                return Many(value = tuple(ret[i].mapper(bs[i]) for i in range(len(bs))), custom_mapping=self.custom_mapping) 
            else:
                half = [ret[i].mapper(bs[i]) for i in range(len(ret))]
                tmp = [ret[-1].mapper(bs[i]) for i in range(len(ret), len(bs))]
                return Many(value = tuple(half + tmp), custom_mapping=self.custom_mapping)
        return Reversible([v.value for v in ret], inv)




@dataclass(frozen=True, slots=True)
class Seq(AST):
    value: Tuple[Tuple[Any, bool], ...]
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False)
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 

    @property
    def arity(self)->int:
        count = 0
        for data, include in self.value:
            if include:
                if isinstance(data, AST):
                    count += data.arity
                else:
                    count += 1
        return count
    @property
    def is_then(self) -> bool:
        return True
    
    def _bimap(self) -> Reversible[Seq, Tuple[Any, ...]]:
        vs = []
        invs = []
        for data, include in self.value:
            if include:
                if isinstance(data, AST):
                    rev = data.bimap
                    invs.append(rev.mapper)
                    if data.is_then:
                        vs.extend(rev.value)
                    else:
                        vs.append(rev.value)
                else:
                    rev = Reversible(data)
                    invs.append(rev.mapper)
                    vs.append(rev.value)

        def invf(bs: Tuple[Any, ...]) -> Seq:
            new_elements = []
            b_index = 0
            for data, include in self.value:
                if include:
                    if isinstance(data, AST) and data.is_then:
                        size = data.arity
                        new_elements.append((invs[b_index](bs[b_index:b_index + size]), True))
                        b_index += size
                    else:
                        new_elements.append((invs[b_index](bs[b_index]), True))
                        b_index += 1
                else:
                    new_elements.append((data, False))
            return replace(self, value=tuple(new_elements))
        return Reversible(tuple(vs), invf)


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
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False)
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 

    @property
    def is_then(self)->bool:
        return True
    
    @property
    def arity(self)->int:
        if self.kind == ThenKind.LEFT:
            return self.left.arity if isinstance(self.left, AST) else 1
        elif self.kind == ThenKind.RIGHT:
            return self.right.arity if isinstance(self.right, AST) else 1
        elif self.kind == ThenKind.BOTH:
            left_arity = self.left.arity if isinstance(self.left, AST) else 1
            right_arity = self.right.arity if isinstance(self.right, AST) else 1
            return left_arity + right_arity
        else:
            return 1

    @property
    def left_arity(self) -> int:
        if isinstance(self.left, AST):
            return self.left.arity
        return 1
        
    @property
    def right_arity(self) -> int:
        if isinstance(self.right, AST):
            return self.right.arity
        return 1
    @property
    def left_is_then(self) -> bool:
        if isinstance(self.left, AST):
            return self.left.is_then
        return False
    
    @property
    def right_is_then(self)->bool:
        if isinstance(self.right, AST):
            return self.right.is_then
        return False


    def _bimap(self) -> Reversible[Then[A, B], Any | Tuple[Any, ...]]:
        """Transform the left/right values according to ``kind``.

        - ``LEFT``: map and return the left value; inverse sets only ``left``.
        - ``RIGHT``: map and return the right value; inverse sets only ``right``.
        - ``BOTH``: return a flattened tuple of mapped left values followed by
          mapped right values. The inverse expects a tuple whose length equals
          ``left.arity() + right.arity()`` and reconstructs the structure.
        """
        # left_size = self.left.arity if isinstance(self.left, Then) else 1
        # right_size = self.right.arity if isinstance(self.right, Then) else 1
        left_size = self.left_arity
        right_size = self.right_arity
        match self.kind:
            case ThenKind.LEFT:
                left = self.left.bimap if isinstance(self.left, AST) else Reversible(self.left)
                def invl(c: Any) -> Then[A, B]:
                    return replace(self, left=cast(A, left.mapper(c)))
                def invl0(c: Any) -> Then[A, B]:
                    return replace(self, left=cast(A, left.mapper(c[0])))
                
                # if isinstance(self.left, Then):
                if self.left_is_then:
                    return Reversible(left.value, invl)
                else:
                    return Reversible((left.value,), invl0)
            case ThenKind.RIGHT:
                right = self.right.bimap if isinstance(self.right, AST) else Reversible(self.right)
                def invr(c: Any) -> Then[A, B]:
                    return replace(self, right=cast(B, right.mapper(c)))
                
                def invr0(c: Any) -> Then[A, B]:
                    return replace(self, right=cast(B, right.mapper(c[0])))
                # if isinstance(self.right, Then):
                if self.right_is_then:
                    return Reversible(right.value, invr)
                else:
                    return Reversible((right.value,), invr0)
            case ThenKind.BOTH:
                left = self.left.bimap if isinstance(self.left, AST) else Reversible(self.left)
                right = self.right.bimap if isinstance(self.right, AST) else Reversible(self.right)
                # if isinstance(self.left, Then):
                if self.left_is_then:
                    left_v = left.value
                else:   
                    left_v = (left.value,)
                # if isinstance(self.right, Then):
                if self.right_is_then:
                    right_v = right.value
                else:   
                    right_v = (right.value,)
                def invf(b: Tuple[C, ...]) -> Then[A, B]:
                    lraw: Tuple[Any, ...] = b[:left_size]
                    rraw: Tuple[Any, ...] = b[left_size:left_size + right_size]
                    lraw = lraw[0] if not self.left_is_then else lraw
                    rraw = rraw[0] if not self.right_is_then else rraw
                    la = left.mapper(lraw)
                    ra = right.mapper(rraw)
                    return replace(self, left=cast(A, la), right=cast(B, ra))
                
                return Reversible(left_v + right_v, invf) # type: ignore


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


E = TypeVar("E", bound=DataclassInstance)

Collector = Type[Any] | Callable[..., Any]
@dataclass(frozen=True, slots=True)
class Collect(AST, Generic[A, E]):
    collector: Collector
    value: A
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False)
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 

    def _bimap(self) -> Reversible[Collect[A, E], E]:
        b, inner_f = self.value.bimap if isinstance(self.value, AST) else Reversible(self.value)
        inner_then = isinstance(self.value, AST) and self.value.is_then
        if inner_then and isinstance(b, tuple):
            index: List[str | int] = []
            named_count = 0
            for i, v in enumerate(b):
                if isinstance(v, Marked):
                    index.append(v.name)
                    named_count += 1
                else:
                    index.append(i - named_count)
            named = {v.name: v.value for v in b if isinstance(v, Marked)}
            unnamed = [v for v in b if not isinstance(v, Marked)]
            c = CallWith(self.collector, *unnamed, **named)
            if c.missing_args or c.missing_kwargs:
                raise SyncraftError("Collector cannot be called with provided arguments", 
                                     offender=self.collector, 
                                     expect="callable with matching signature")
            ret: E = c()
            def invf(e: E) -> Tuple[Any, ...]:
                if is_dataclass(e):
                    named_dict = {f.name: getattr(e, f.name) for f in fields(e)}
                    unnamed = []
                    for f in fields(e):
                        if f.name not in named:
                            unnamed.append(named_dict[f.name])
                elif isinstance(e, Record):
                    named_dict = e._named
                    unnamed = e._unnamed
                else:
                    raise SyncraftError("Collector returned unsupported type", offender=e, expect="dataclass or Record")
                tmp = []
                for x in index:
                    if isinstance(x, str):
                        tmp.append(Marked(name=x, value=named_dict[x], custom_mapping=None))
                    else:
                        tmp.append(unnamed[x])
                return tuple(tmp)
            return Reversible(ret, lambda e: replace(self, value=inner_f(invf(e)))) # type: ignore
        elif isinstance(b, Marked):
            named = {b.name: b.value}
            ret1: E = self.collector(**named)
            def invf1(e: E) -> Marked:
                if is_dataclass(e):
                    named_dict = {f.name: getattr(e, f.name) for f in fields(e)}
                    for k, v in named_dict.items():
                        return Marked(name=k, value=v, custom_mapping=None)
                elif isinstance(e, Record):
                    for n, v in e._named.items():
                        return Marked(name=n, value=v, custom_mapping=None)
                raise SyncraftError("Collector returned unsupported type", offender=e, expect="dataclass or Record")   
                
            return Reversible(ret1, lambda e: replace(self, value=inner_f(invf1(e)))) # type: ignore
        else:
            def build_inv(d: B) -> Callable[[E], B]:
                def inv_one_positional(e: E) -> B:
                    if is_dataclass(e):
                        return getattr(e, fields(e)[0].name)
                    elif isinstance(e, Record):
                        return e._unnamed[0]
                    raise SyncraftError("Collector returned unsupported type", offender=e, expect="dataclass or Record")
                return inv_one_positional
            c = CallWith(self.collector, b)
            if c.missing_args or c.missing_kwargs:
                raise SyncraftError("Collector cannot be called with provided arguments", 
                                     offender=self.collector, 
                                     expect="callable with matching signature")
            
            if c.unused_args:
                inv_first = build_inv(c.unused_args[0])
            else:
                inv_first = build_inv(b)  # type: ignore
            ret3 = c()
            return Reversible(ret3, lambda e: replace(self, value=inner_f(inv_first(e)))) # type: ignore
    


Char = TypeVar('Char', bound=Hashable)
@dataclass(frozen=True, slots=True)
class Token(AST, Generic[Char]):
    text: str | bytes | Tuple[Char, ...]
    token_type: Optional[Union[str, Enum]] = None
    custom_mapping: Optional[Bimap[Any, Any]] = field(compare=False, hash=False, repr=False, default=None)
    def mapping(self, f: Optional[Bimap[Any, Any]]) -> AST:
        return replace(self, custom_mapping=f) 

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
    OrElse['ParseResult[T]', 'ParseResult[T]'],
    Many['ParseResult[T]'],
    Collect['ParseResult[T]', Any],
    Marked['ParseResult[T]'],
    Nothing,
    Token,
    T,
]



