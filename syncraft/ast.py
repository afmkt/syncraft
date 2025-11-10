

from __future__ import annotations
from typing import (
    Optional, Any, TypeVar, Tuple, cast,
    Generic, Callable, Union, Protocol, Type, List, ClassVar,
    Dict, Hashable
)
from functools import cached_property

from dataclasses import dataclass, replace, is_dataclass, fields
from enum import Enum
from syncraft.utils import CallWith

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

def shallow_dict(a: Any)->Dict[str, Any]:
    if not is_dataclass(a):
        raise SyncraftError("Expected dataclass instance for collector inverse", offender=a, expect="dataclass")
    return {f.name: getattr(a, f.name) for f in fields(a)}




A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
D = TypeVar('D')
S = TypeVar('S')  
S1 = TypeVar('S1')


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
class Lens(Generic[C, A]):
    get: Callable[[C], A]
    set: Callable[[C, A], C]    

    def modify(self, source: C, f: Callable[[A], A]) -> C:
        return self.set(source, f(self.get(source)))
    
    def bimap(self, ff: Callable[[A], B], bf: Callable[[B], A]) -> Lens[C, B]:
        def getf(data: C) -> B:
            return ff(self.get(data))

        def setf(data: C, value: B) -> C:
            return self.set(data, bf(value))

        return Lens(get=getf, set=setf)

    def __truediv__(self, other: Lens[A, B]) -> Lens[C, B]:
        def get_composed(obj: C) -> B:
            return other.get(self.get(obj))        
        def set_composed(obj: C, value: B) -> C:
            return self.set(obj, other.set(self.get(obj), value))
        return Lens(get=get_composed, set=set_composed)
    
    def __rtruediv__(self, other: Lens[B, C])->Lens[B, A]:
        return other.__truediv__(self)
    

@dataclass(frozen=True)
class Bimap(Generic[A, B]):
    """A reversible mapping that returns both a forward value and an inverse function.

    ``Bimap`` is like a function ``A -> B`` paired with a way to map a value
    of type ``B`` back into an ``A``. It composes with other ``Bimap``s or a
    ``Biarrow`` using ``>>`` and ``<<``-style operations, preserving an
    automatically derived inverse.
    """
    run_f: Callable[[A], Tuple[B, Callable[[B], A]]]
    def __call__(self, a: A) -> Tuple[B, Callable[[B], A]]:
        """Apply the mapping to ``a``.

        Returns:
            tuple: ``(forward_value, inverse)`` where ``inverse`` maps
            a compatible ``B`` back into an ``A``.
        """
        return self.run_f(a)    
    def __rshift__(self, other: Bimap[B, C] | Biarrow[B, C]) -> Bimap[A, C]:
        """Compose this mapping with another mapping/arrow.

        ``self >> other`` first applies ``self``, then ``other``. The produced
        inverse runs ``other``'s inverse followed by ``self``'s inverse.
        """
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
            raise SyncraftError("Unsupported type for Bimap >>", offender=other, expect=(Bimap , Biarrow))
    def __rrshift__(self, other: Bimap[C, A] | Biarrow[C, A]) -> Bimap[C, B]:
        """Right-composition so arrows or bimaps can be on the left of ``>>``."""
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
            raise SyncraftError("Unsupported type for Bimap <<", offender=other, expect=(Bimap , Biarrow))


    @staticmethod
    def const(a: B) -> Bimap[B, B]:
        """Return a bimap that ignores input and always yields ``a``.

        The inverse is identity for the output type.
        """
        return Bimap(lambda _: (a, lambda b: b))

    @staticmethod
    def identity() -> Bimap[A, A]:
        """The identity bimap where forward and inverse are no-ops."""
        return Bimap(lambda a: (a, lambda b: b))

    @staticmethod
    def when(cond: Callable[[A], bool],
             then: Bimap[A, B],
             otherwise: Optional[Bimap[A, C]] = None) -> Bimap[A, A | B | C]:
        """Choose a mapping depending on the input value.

        Applies ``then`` when ``cond(a)`` is true; otherwise applies
        ``otherwise`` if provided, or ``identity``.
        """
        def when_run(a: A) -> Tuple[A | B | C, Callable[[A | B | C], A]]:
            bimap = then if cond(a) else (otherwise if otherwise is not None else Bimap.identity())
            abc, inv = bimap(a)
            def inv_f(b: Any) -> A:
                return inv(b)
            return abc, inv_f
        return Bimap(when_run)
    

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
    
    def zip(self, other: Reducer[A, S1])-> Reducer[A, Tuple[S, S1]]:
        return Reducer(lambda a, s: (self(a, s[0]), other(a, s[1])))
    
    def diff(self, other: Reducer[B, S]) -> Reducer[Tuple[A, B], S]:
        return Reducer(lambda ab, s: other(ab[1], self(ab[0], s)))
    
    def filter(self, f: Callable[[A, S], bool]) -> Reducer[A, S]:
        return Reducer(lambda a, s: self(a, s) if f(a, s) else s)



@dataclass(frozen=True)    
class AST:
    """Base class for all Syncraft AST nodes.

    Nodes implement ``bimap`` to transform contained values while providing an
    inverse that can reconstruct the original node from transformed output.
    """
    @property
    def arity(self)->int:
        return 1
    @property
    def is_then(self)->bool:
        return False
    def bimap(self, r: Bimap[Any, Any]=Bimap.identity()) -> Tuple[Any, Callable[[Any], Any]]:
        """Apply a bimap to this node, returning a value and an inverse.

        The default behavior defers to the provided mapping ``r`` with the
        node itself as input. The ``r`` only applies to the leaf node of AST tree.
        """
        return r(self)
    
    @cached_property
    def mapped(self) -> Any:
        """Apply the default bimap and return only the forward value."""
        v, _ = self.bimap()
        return v
    
    def _repr_html_(self) -> str | None:
        """
        Jupyter/VS Code notebook integration: automatically display AST as SVG tree diagram.
        This enables beautiful AST visualization by simply typing the AST object name.
        Uses _repr_html_ for broader compatibility (VS Code notebooks support HTML but not SVG display).
        """
        try:
            from syncraft.dev import ast2svg
            svg_content = ast2svg(self)
            if not svg_content:
                return None
                
            # Include CSS styles for proper AST tree rendering
            css_styles = """
            <style>
            .ast-diagram {
                font-family: monospace;
                background-color: hsl(210,20%,98%);
            }
            .ast-diagram .node {
                fill: hsl(200,80%,90%);
                stroke: hsl(200,80%,40%);
                stroke-width: 2;
            }
            .ast-diagram .edge {
                stroke: hsl(200,60%,50%);
                stroke-width: 1.5;
                fill: none;
            }
            .ast-diagram text {
                font: 12px monospace;
                text-anchor: middle;
                dominant-baseline: central;
            }
            .ast-diagram .node-label {
                font-weight: bold;
                fill: hsl(200,80%,30%);
            }
            .ast-diagram .value-label {
                font-style: italic;
                fill: hsl(0,0%,40%);
            }
            </style>
            """
            
            return css_styles + svg_content
        except ImportError:
            # Gracefully handle case where dev dependencies aren't available
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
@dataclass(frozen=True)
class Nothing(AST, metaclass=MetaNothing):
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


class MetaIgnore(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        return instance is cls or super().__instancecheck__(instance)
    def __str__(cls)->str:
        return "Ignore"
    def __repr__(cls)->str:
        return "Ignore"
    def __bool__(cls)->bool:
        return False
@dataclass(frozen=True)
class Ignore(AST, metaclass=MetaIgnore):
    """Singleton sentinel representing the absence of a value in the AST."""
    def __call__(self)-> Ignore:
        return self
    def __new__(cls):
        return cls
    def __bool__(self)->bool:
        return False
    def __str__(self)->str:
        return "Ignore"
    def __repr__(self)->str:
        return "Ignore"
    


@dataclass(frozen=True)
class Lazy(AST, Generic[A]):
    value: A
    flatten: bool 
    @property
    def arity(self)->int:
        if self.flatten:
            if isinstance(self.value, AST):
                return self.value.arity
        return 1
    
    @property
    def is_then(self) -> bool:
        if self.flatten: 
            if isinstance(self.value, AST):
                return self.value.is_then
        return False
    
    def bimap(self, r: Bimap[A, C]=Bimap.identity()) -> Tuple[C, Callable[[C], Lazy[A]]]:
        """Defer to the provided mapping ``r``."""
        v, inv = self.value.bimap(r) if isinstance(self.value, AST) else r(self.value)
        return v, lambda b: replace(self, value=inv(b))


@dataclass(frozen=True)
class Marked(AST, Generic[A]):
    """Annotate a AST node with a name.

    Used to tag subtrees so they can be collected by name later (e.g., in
    collectors) without altering the structural shape.
    """
    name: str
    value: A
    def bimap(self, r: Bimap[A, B]=Bimap.identity()) -> Tuple[Marked[B], Callable[[Marked[B]], Marked[A]]]:
        """Transform the inner value while preserving the mark name.

        Returns a new ``Marked`` with transformed value and an inverse that
        expects a ``Marked`` to recover the original.
        """
        v, inner_f = self.value.bimap(r) if isinstance(self.value, AST) else r(self.value)
        return Marked(name=self.name, value=v), lambda b: Marked(name = b.name, value=inner_f(b.value))
    
class ChoiceKind(Enum):
    LEFT = 'left'
    RIGHT = 'right'

ChoiceKind.__str__ = lambda self: self.value   # type: ignore


@dataclass(frozen=True)
class Choice(AST, Generic[A, B]):
    """Represent a binary alternative between left and right values.

    ``kind`` indicates which branch was taken, or ``None`` when unknown.
    """
    kind: Optional[ChoiceKind]
    value: Optional[A | B] = None
    @property
    def arity(self)->int:
        if isinstance(self.value, AST):
            return self.value.arity
        return 1
    
    @property
    def is_then(self) -> bool:
        if isinstance(self.value, AST):
            return self.value.is_then
        return False

    def bimap(self, r: Bimap[A | B, C]=Bimap.identity()) -> Tuple[Optional[C], Callable[[Optional[C]], Choice[A, B]]]:
        """Map over the held value if present; propagate ``None`` otherwise.

        The inverse resets ``kind`` to ``None`` to avoid biasing the result.
        When user edit the data we cannot assume which branch the data should go
        back to. Set ``kind`` to ``None`` to indicate this situation.
        """
        if self.value is None:
            return None, lambda c: replace(self, value=None, kind=None)
        else:
            v, inv = self.value.bimap(r) if isinstance(self.value, AST) else r(self.value)
            return v, lambda c: replace(self, value=inv(c) if c is not None else None, kind=None)

@dataclass(frozen=True)
class Many(AST, Generic[A]):
    """A finite sequence of values within the AST."""
    value: Tuple[A, ...]
    def bimap(self, r: Bimap[A, B]=Bimap.identity()) -> Tuple[List[B], Callable[[List[B]], Many[A]]]:
        """Map each element to a list and provide an inverse.

        The inverse accepts a list of transformed elements. If the provided
        list is shorter than the original, only the prefix is used. If longer,
        the extra values are inverted using the last element's inverse.
        """
        ret = [v.bimap(r) if isinstance(v, AST) else r(v) for v in self.value]
        def inv(bs: List[B]) -> Many[A]:
            if len(bs) <= len(ret):
                return Many(value = tuple(ret[i][1](bs[i]) for i in range(len(bs)))) 
            else:
                half = [ret[i][1](bs[i]) for i in range(len(ret))]
                tmp = [ret[-1][1](bs[i]) for i in range(len(ret), len(bs))]
                return Many(value = tuple(half + tmp))
        return [v[0] for v in ret], inv

class ThenKind(Enum):
    BOTH = '+'
    LEFT = '//'
    RIGHT = '>>'

ThenKind.__str__ = lambda self: self.value   # type: ignore

@dataclass(eq=True, frozen=True)
class Then(AST, Generic[A, B]):
    """Pair two values with a composition kind (both, left, or right).

    The ``kind`` determines how values are combined.
    ``LEFT``/``RIGHT`` indicate single-sided results; ``BOTH`` flattens both
    sides.
    """
    kind: ThenKind
    left: A
    right: B
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


    def bimap(self, r: Bimap[A | B, Any] = Bimap.identity()) -> Tuple[Any | Tuple[Any, ...], Callable[[Any | Tuple[Any, ...]], Then[A, B]]]:
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
                lb, linv = self.left.bimap(r) if isinstance(self.left, AST) else r(self.left)
                def invl(c: Any) -> Then[A, B]:
                    return replace(self, left=cast(A, linv(c)))
                def invl0(c: Any) -> Then[A, B]:
                    return replace(self, left=cast(A, linv(c[0])))
                
                # if isinstance(self.left, Then):
                if self.left_is_then:
                    return lb, invl
                else:
                    return (lb,), invl0
            case ThenKind.RIGHT:
                rb, rinv = self.right.bimap(r) if isinstance(self.right, AST) else r(self.right)
                def invr(c: Any) -> Then[A, B]:
                    return replace(self, right=cast(B, rinv(c)))
                
                def invr0(c: Any) -> Then[A, B]:
                    return replace(self, right=cast(B, rinv(c[0])))
                # if isinstance(self.right, Then):
                if self.right_is_then:
                    return rb, invr
                else:
                    return (rb,), invr0
            case ThenKind.BOTH:
                lb, linv = self.left.bimap(r) if isinstance(self.left, AST) else r(self.left)
                rb, rinv = self.right.bimap(r) if isinstance(self.right, AST) else r(self.right)
                # if isinstance(self.left, Then):
                if self.left_is_then:
                    left_v = lb
                else:   
                    left_v = (lb,)
                # if isinstance(self.right, Then):
                if self.right_is_then:
                    right_v = rb
                else:   
                    right_v = (rb,)
                def invf(b: Tuple[C, ...]) -> Then[A, B]:
                    lraw: Tuple[Any, ...] = b[:left_size]
                    rraw: Tuple[Any, ...] = b[left_size:left_size + right_size]
                    # lraw = lraw[0] if not isinstance(self.left, Then) else lraw
                    # rraw = rraw[0] if not isinstance(self.right, Then) else rraw
                    lraw = lraw[0] if not self.left_is_then else lraw
                    rraw = rraw[0] if not self.right_is_then else rraw
                    la = linv(lraw)
                    ra = rinv(rraw)
                    return replace(self, left=cast(A, la), right=cast(B, ra))
                return left_v + right_v, invf


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


E = TypeVar("E", bound=DataclassInstance)

Collector = Type[E] | Callable[..., E]
@dataclass(frozen=True)
class Collect(AST, Generic[A, E]):
    """Apply a collector to a value to build a dataclass-like instance.

    When the inner value is a ``Then`` and the forward result is a tuple, any
    ``Marked`` elements become named arguments to the collector; the remainder
    are passed positionally. The inverse breaks the produced instance back into
    a structure compatible with the original ``Then``.
    """
    collector: Collector
    value: A
    def bimap(self, r: Bimap[A, B]=Bimap.identity()) -> Tuple[B | E, Callable[[B | E], Collect[A, E]]]:
        """Map the inner value, collect it, and supply a matching inverse.

        For multi-field tuples derived from ``Then``, the inverse rebuilds the
        appropriate mix of ``Marked`` and positional elements using the
        collector's dataclass fields. For single-argument collectors, the first
        field of the dataclass is used.
        """
        
        b, inner_f = self.value.bimap(r) if isinstance(self.value, AST) else r(self.value) 
        if isinstance(b, tuple):
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
            ret: E = self.collector(*unnamed, **named)
            def invf(e: E) -> Tuple[Any, ...]:
                if not is_dataclass(e):
                    raise SyncraftError("Expected dataclass instance for collector inverse", offender=e, expect="dataclass")
                named_dict = shallow_dict(e)     
                unnamed = []           
                for f in fields(e):
                    if f.name not in named:
                        unnamed.append(named_dict[f.name])
                tmp = []
                for x in index:
                    if isinstance(x, str):
                        tmp.append(Marked(name=x, value=named_dict[x]))
                    else:
                        tmp.append(unnamed[x])
                return tuple(tmp)
            return ret, lambda e: replace(self, value=inner_f(invf(e))) # type: ignore
        elif isinstance(b, Marked):
            named = {b.name: b.value}
            ret1: E = self.collector(**named)
            def invf1(e: E) -> Marked:
                if not is_dataclass(e):
                    raise SyncraftError("Expected dataclass instance for collector inverse", offender=e, expect="dataclass")
                named_dict = shallow_dict(e)     
                return Marked(name=fields(e)[0].name, value=named_dict[fields(e)[0].name])
            return ret1, lambda e: replace(self, value=inner_f(invf1(e))) # type: ignore
        else:
            def build_inv(d:B):
                def inv_one_positional(e: E) -> B:
                    if not is_dataclass(e):
                        raise SyncraftError("Expected dataclass instance for collector inverse", offender=e, expect="dataclass")
                    if len(fields(e)) == 1:
                        return d
                    else:
                        named_dict = shallow_dict(e)
                        return named_dict[fields(e)[0].name]
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
            return ret3, lambda e: replace(self, value=inner_f(inv_first(e))) # type: ignore
    


Char = TypeVar('Char', bound=Hashable)
@dataclass(frozen=True)
class Token(AST, Generic[Char]):
    text: str | bytes | Tuple[Char, ...]
    token_type: Optional[Union[str, Enum]] = None
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
    Choice['ParseResult[T]', 'ParseResult[T]'],
    Many['ParseResult[T]'],
    Collect['ParseResult[T]', Any],
    Marked['ParseResult[T]'],
    Nothing,
    T,
]



