

from __future__ import annotations
import re
from typing import (
    Optional, Any, TypeVar, Tuple, runtime_checkable, 
    Protocol, Generic, Callable, Union, cast, List
)


from dataclasses import dataclass, replace, is_dataclass, asdict
from enum import Enum
from functools import cached_property
from syncraft.constraint import Binding, Variable, Bindable



A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
S = TypeVar('S', bound=Bindable)  


@dataclass(frozen=True)
class Bimap(Generic[A, B]):
    run_f: Callable[[A, Any], Tuple[B, Any, Callable[[B, Any], Tuple[A, Any]]]]
    def __call__(self, a: A, s: Any) -> Tuple[B, Any, Callable[[B, Any], Tuple[A, Any]]]:
        return self.run_f(a, s)    
    def __rshift__(self, other: Bimap[B, C]) -> Bimap[A, C]:
        def then_run(a: A, s: Any) -> Tuple[C, Any, Callable[[C, Any], Tuple[A, Any]]]:
            b, s1, inv1 = self(a, s)
            c, s2, inv2 = other(b, s1)
            def inv(c2: C, s3: Any) -> Tuple[A, Any]:
                b2, s4 = inv2(c2, s3)
                a2, s5 = inv1(b2, s4)
                return a2, s5
            return c, s2, inv
        return Bimap(then_run)
    @staticmethod
    def const(a: B)->Bimap[B, B]:
        return Bimap(lambda _, s: (a, s, lambda b, s1: (b, s1)))

    @staticmethod
    def identity()->Bimap[Any, Any]:
        return Bimap(lambda a, s: (a, s, lambda b, s1: (b, s1)))

    @staticmethod
    def when(cond: Callable[[A, Any], bool],
             then: Bimap[A, B],
             otherwise: Optional[Bimap[A, C]] = None) -> Bimap[A, A | B | C]:
        def when_run(a:A, s:Any) -> Tuple[A | B | C, Any, Callable[[A | B | C, Any], Tuple[A, Any]]]:
            bimap = then if cond(a, s) else (otherwise if otherwise is not None else Bimap.identity())
            abc, s1, inv = bimap(a, s)
            def inv_f(b: Any, s2: Any) -> Tuple[A, Any]:
                return inv(b, s2)
            return abc, s1, inv_f
        return Bimap(when_run)
    
    @staticmethod
    def aggregate(f: Callable[[A, Any], Any])->Bimap[A, A]:
        def agg_run(a: A, s: Any) -> Tuple[A, Any, Callable[[A, Any], Tuple[A, Any]]]:
            s1 = f(a, s)
            return a, s1, lambda b, s2: (b, s2)
        return Bimap(agg_run)
    
    @staticmethod
    def peek(f: Callable[[A, Any], None]) -> Bimap[A, A]:
        def peek_run(a: A, s: Any) -> Tuple[A, Any, Callable[[A, Any], Tuple[A, Any]]]:
            f(a, s)
            return a, s, lambda b, s1: (b, s1)
        return Bimap(peek_run)
    
    @staticmethod
    def map(f: Callable[[A], B], g: Callable[[B], A]) -> Bimap[A, B]:
        def map_run(a: A, s: Any) -> Tuple[B, Any, Callable[[B, Any], Tuple[A, Any]]]:
            b = f(a)
            return b, s, lambda b2, s1: (g(b2), s1)
        return Bimap(map_run)
    
    @staticmethod
    def zip(f: Bimap[A, B], g: Bimap[A, C]) -> Bimap[A, Tuple[B, C]]:
        def zip_run(a: A, s: Any) -> Tuple[Tuple[B, C], Any, Callable[[Tuple[B, C], Any], Tuple[A, Any]]]:
            a1, s1, inv1 = f(a, s)
            a2, s2, inv2 = g(a, s1)
            def inv(aa: Tuple[B, C], ss)->Tuple[A, Any]:
                a1b, a2b = aa
                a1c, s5 = inv1(a1b, ss)
                a2c, s6 = inv2(a2b, s5)
                assert a1c == a2c, f"Expected {a1c} == {a2c}"
                return a1c, s6
            return (a1, a2), s2, inv
        return Bimap(zip_run)

@dataclass(frozen=True)
class Biarrow(Generic[S, A, B]):
    forward: Callable[[S, A], Tuple[S, B]]
    inverse: Callable[[S, B], Tuple[S, A]]
    def __rshift__(self, other: Biarrow[S, B, C]) -> Biarrow[S, A, C]:
        def fwd(s: S, a: A) -> Tuple[S, C]:
            s1, b = self.forward(s, a)
            return other.forward(s1, b)
        def inv(s: S, c: C) -> Tuple[S, A]:
            s1, b = other.inverse(s, c)
            return self.inverse(s1, b)
        return Biarrow(
            forward=fwd,
            inverse=inv
        )
    @staticmethod
    def identity()->Biarrow[S, A, A]:
        return Biarrow(
            forward=lambda s, x: (s, x),
            inverse=lambda s, y: (s, y)
        )
            
    @staticmethod
    def when(condition: Callable[..., bool], 
             then: Biarrow[S, A, B], 
             otherwise: Optional[Biarrow[S, A, B]] = None) -> Callable[..., Biarrow[S, A, B]]:
        def _when(*args:Any, **kwargs:Any) -> Biarrow[S, A, B]:
            return then if condition(*args, **kwargs) else (otherwise or Biarrow.identity())
        return _when
    

    
class StructuralResult:
    def biarrow(self, 
              before: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity(),
              after: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity()
              ) -> Biarrow[Any, Any, Any]:
        return Biarrow.identity()
    @classmethod
    def bimap(cls, f: Bimap[Any, Any])->Bimap[Any, Any]:
        return Bimap.identity()
        
@dataclass(frozen=True)
class MarkedResult(Generic[A], StructuralResult):
    name: str
    value: A
    @classmethod
    def bimap(cls, f: Bimap[A, B])->Bimap[MarkedResult[A], MarkedResult[B]]:
        def namedf(a: MarkedResult[A], s: Any) -> Tuple[MarkedResult[B], Any, Callable[[MarkedResult[B], Any], Tuple[MarkedResult[A], Any]]]:
            newf = a.value.bimap(f) if isinstance(a.value, StructuralResult) else f                
            b, s1, inv = newf(a.value, s)
            def invf(b: MarkedResult[B], s2: Any) -> Tuple[MarkedResult[A], Any]:
                a2, s3 = inv(b.value, s2)
                return MarkedResult(name=a.name, value=a2), s3
            return MarkedResult(name=a.name, value=b), s1, invf
        return Bimap(namedf)
    
    def biarrow(self, 
              before: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity(),
              after: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity()
              ) -> Biarrow[Any, MarkedResult[A], MarkedResult[Any]]:
        
        inner_b = self.value.biarrow(before, after) if isinstance(self.value, StructuralResult) else before(self.value) >> after(self.value)
        def fwd(s: S, a: MarkedResult[A])-> Tuple[S, MarkedResult[Any]]:
            assert a == self, f"Expected {self}, got {a}"
            inner_s, inner_v = inner_b.forward(s, a.value)
            return (inner_s, replace(a, value=inner_v)) if not isinstance(inner_v, MarkedResult) else (inner_s, inner_v)
        
        def inv(s: S, a: MarkedResult[Any]) -> Tuple[S, MarkedResult[A]]:
            assert isinstance(a, MarkedResult), f"Expected MarkedResult, got {type(a)}"
            inner_s, inner_v = inner_b.inverse(s, a.value)
            return (inner_s, replace(self, value=inner_v)) if not isinstance(inner_v, MarkedResult) else (inner_s, replace(self, value=inner_v.value))
        ret: Biarrow[Any, Any, Any]  = Biarrow(
            forward=fwd,
            inverse=inv
        )    
        return before(self) >> ret >> after(self)
@dataclass(eq=True, frozen=True)
class ManyResult(Generic[A], StructuralResult):
    value: Tuple[A, ...]
    @classmethod
    def bimap(cls, f: Bimap[A, B])->Bimap[ManyResult[A], List[B]]:
        def manyf(a: ManyResult[A], s: Any) -> Tuple[List[B], Any, Callable[[List[B], Any], Tuple[ManyResult[A], Any]]]:
            assert len(a.value) > 0, "ManyResult must have at least one element"
            newf = a.value.bimap(f) if isinstance(a.value, StructuralResult) else f
            forward = []
            for item in a.value:
                b, s, inv = newf(item, s)
                forward.append((b, s, inv))
            def invf(b: List[B], s2: Any) -> Tuple[ManyResult[A], Any]:
                if len(b) <= len(forward):
                    ret = []
                    for i, item in enumerate(b):
                        aa, s2 = forward[i][2](item, s2)
                        ret.append(aa)
                    return ManyResult(value=tuple(ret)), s2
                else: 
                    ret = []
                    for i in range(len(forward)):
                        aa, s2 = forward[i][2](b[i], s2)
                        ret.append(aa)

                    for item in b[len(forward):]:
                        aa, s2 = forward[-1][2](item, s2)
                    return ManyResult(value=tuple(ret)), s2
            return [b for b, s, inv in forward], s, invf
        return Bimap(manyf)

    def biarrow(self, 
              before: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity(),
              after: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity()
              ) -> Biarrow[Any, ManyResult[A], List[A]]:
        # We don't allow zero length ManyResult e.g. many(at_least >= 1) at the syntax level
        # so inner_b has at least 1 element
        assert len(self.value) > 0, "ManyResult must have at least one element"
        inner_b = [v.biarrow(before, after) if isinstance(v, StructuralResult) else before(v) >> after(v) for v in self.value]
        def fwd(s: Any, a: ManyResult[A]) -> Tuple[Any, List[A]]:
            assert a == self, f"Expected {self}, got {a}"
            return s, [inner_b[i].forward(s, v)[1] for i, v in enumerate(a.value)]
            
        def inv(s: Any, a: List[A]) -> Tuple[Any, ManyResult[A]]:
            assert isinstance(a, list), f"Expected list, got {type(a)}"
            ret = [inner_b[i].inverse(s, v)[1] for i, v in enumerate(a)]
            if len(ret) <= len(inner_b):
                return s, ManyResult(value=tuple(ret))
            else:
                extra = [inner_b[-1].inverse(s, v)[1] for v in a[len(inner_b):]]
                return s, ManyResult(value=tuple(ret + extra))

        ret = Biarrow(
            forward=fwd,
            inverse=inv
        )    
        return before(self) >> ret >> after(self)

@dataclass(eq=True, frozen=True)
class OrResult(Generic[A], StructuralResult):
    value: A
    @classmethod
    def bimap(cls, f: Bimap[A, B])->Bimap[OrResult[A], B]:
        def orf(a: OrResult[A], s: Any) -> Tuple[B, Any, Callable[[B, Any], Tuple[OrResult[A], Any]]]:
            newf = a.value.bimap(f) if isinstance(a.value, StructuralResult) else f
            b, s1, inv = newf(a.value, s)
            def invf(b2: B, s2: Any) -> Tuple[OrResult[A], Any]:
                a2, s3 = inv(b2, s2)
                return OrResult(value=a2), s3
            return b, s1, invf
        return Bimap(orf)
        

    def biarrow(self, 
              before: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity(),
              after: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity()              
              ) -> Biarrow[Any, OrResult[A], Any]:
        inner_b = self.value.biarrow(before, after) if isinstance(self.value, StructuralResult) else before(self.value) >> after(self.value)
        def fwd(s: Any, a: OrResult[A]) -> Tuple[Any, Any]:
            assert a == self, f"Expected {self}, got {a}"
            return inner_b.forward(s, a.value)
        
        def inv(s: Any, a: Any) -> Tuple[Any, OrResult[A]]:
            inner_s, inner_v = inner_b.inverse(s, a)
            return inner_s, OrResult(value=inner_v) 
        
        ret = Biarrow(
            forward=fwd,
            inverse=inv
        )    
        return before(self) >> ret >> after(self)
class ThenKind(Enum):
    BOTH = '+'
    LEFT = '//'
    RIGHT = '>>'
    
@dataclass(eq=True, frozen=True)
class ThenResult(Generic[A, B], StructuralResult):
    kind: ThenKind
    left: A
    right: B
    @classmethod
    def bimap(cls, f: Bimap[Any, Any]) -> Bimap[Any, Any]:
        def thenf(a: ThenResult[A, B], s: Any)->Tuple[Any, Any, Callable[[Any, Any], Tuple[ThenResult[A, B], Any]]]:
            left_size = a.left.arity() if isinstance(a.left, ThenResult) else 1
            right_size = a.right.arity() if isinstance(a.right, ThenResult) else 1
            new_leftf = a.left.bimap(f) if isinstance(a.left, StructuralResult) else f
            new_rightf = a.right.bimap(f) if isinstance(a.right, StructuralResult) else f
            match a.kind:
                case ThenKind.LEFT:
                    lb, ls, linv = new_leftf(a.left, s)
                    def invf_left(aa: Any, s: Any) -> Tuple[ThenResult[A, B], Any]:
                        ll, s = linv(aa, s)
                        return ThenResult(kind=ThenKind.LEFT, left=ll, right=a.right), s
                    return lb, ls, invf_left
                case ThenKind.RIGHT:
                    rb, rs, rinv = new_rightf(a.right, s)
                    def invf_right(aa: Any, s: Any) -> Tuple[ThenResult[A, B], Any]:
                        rr, s = rinv(aa, s)
                        return ThenResult(kind=ThenKind.RIGHT, left=a.left, right=rr), s
                    return rb, rs, invf_right
                case ThenKind.BOTH:
                    lb, ls, linv = new_leftf(a.left, s)
                    rb, rs, rinv = new_rightf(a.right, ls)
                    left_v = (lb,) if not isinstance(a.left, ThenResult) else lb
                    right_v = (rb,) if not isinstance(a.right, ThenResult) else rb
                    def invf(b: Tuple[Any, ...], s: Any) -> Tuple[ThenResult[A, B], Any]:
                        lraw = b[:left_size]
                        rraw = b[left_size:left_size + right_size]
                        lraw = lraw[0] if left_size == 1 else lraw
                        rraw = rraw[0] if right_size == 1 else rraw
                        la, ls = linv(lraw, s)
                        ra, rs = rinv(rraw, ls)
                        return ThenResult(kind=a.kind, left=la, right=ra), rs
                    return left_v + right_v, s, invf
        return Bimap(thenf)


    def arity(self)->int:
        if self.kind == ThenKind.LEFT:
            return self.left.arity() if isinstance(self.left, ThenResult) else 1
        elif self.kind == ThenKind.RIGHT:
            return self.right.arity() if isinstance(self.right, ThenResult) else 1
        elif self.kind == ThenKind.BOTH:
            left_arity = self.left.arity() if isinstance(self.left, ThenResult) else 1
            right_arity = self.right.arity() if isinstance(self.right, ThenResult) else 1
            return left_arity + right_arity
        else:
            return 1
                
    def biarrow(self, 
              before: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity(),
              after: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity()            
              ) -> Biarrow[Any, ThenResult[A, B], Tuple[Any, ...] | Any]:
        kind = self.kind
        lb = self.left.biarrow(before, after) if isinstance(self.left, StructuralResult) else before(self.left) >> after(self.left)
        rb = self.right.biarrow(before, after) if isinstance(self.right, StructuralResult) else before(self.right) >> after(self.right)
        left_size = self.left.arity() if isinstance(self.left, ThenResult) else 1
        right_size = self.right.arity() if isinstance(self.right, ThenResult) else 1
        def fwd(s : S, a : ThenResult[A, B]) -> Tuple[S, Tuple[Any, ...] | Any]:
            assert a == self, f"Expected {self}, got {a}"
            match kind:
                case ThenKind.LEFT:
                    return lb.forward(s, a.left)
                case ThenKind.RIGHT:
                    return rb.forward(s, a.right)
                case ThenKind.BOTH:
                    s1, left_v = lb.forward(s, a.left)
                    s2, right_v = rb.forward(s1, a.right)
                    left_v = (left_v,) if not isinstance(a.left, ThenResult) else left_v
                    right_v = (right_v,) if not isinstance(a.right, ThenResult) else right_v
                    return s2, left_v + right_v

        def inv(s: S, b: Tuple[Any, ...] | Any) -> Tuple[S, ThenResult[A, B]]:
            match kind:
                case ThenKind.LEFT:
                    s1, lv = lb.inverse(s, b)
                    return s1, replace(self, left=lv)
                case ThenKind.RIGHT:
                    s1, rv = rb.inverse(s, b)
                    return s1, replace(self, right=rv)
                case ThenKind.BOTH:
                    lraw = b[:left_size]
                    rraw = b[left_size:left_size + right_size]
                    lraw = lraw[0] if left_size == 1 else lraw
                    rraw = rraw[0] if right_size == 1 else rraw
                    s1, lv = lb.inverse(s, lraw)
                    s2, rv = rb.inverse(s1, rraw)
                    return s2, replace(self, left=lv, right=rv)
            
        ret: Biarrow[Any, Any, Any] = Biarrow(
            forward=fwd,
            inverse=inv
        )
        return before(self) >> ret >> after(self)

@runtime_checkable
class TokenProtocol(Protocol):
    @property
    def token_type(self) -> Enum: ...
    @property
    def text(self) -> str: ...
    

@dataclass(frozen=True)
class Token:
    token_type: Enum
    text: str
    def __str__(self) -> str:
        return f"{self.token_type.name}({self.text})"
    
    def __repr__(self) -> str:
        return self.__str__()

    

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




T = TypeVar('T', bound=TokenProtocol)  


ParseResult = Union[
    ThenResult['ParseResult[T]', 'ParseResult[T]'], 
    MarkedResult['ParseResult[T]'],
    ManyResult['ParseResult[T]'],
    OrResult['ParseResult[T]'],
    T,
]



@dataclass(frozen=True)
class AST(Generic[T]):
    focus: ParseResult[T]
    pruned: bool = False
    parent: Optional[AST[T]] = None

    def bimap(self)->Tuple[Any, Callable[[Any], AST[T]]]:
        if isinstance(self.focus, StructuralResult):
            b = self.focus.biarrow() 
            s, v = b.forward(None, self.focus)
            def inverse(data: Any) -> AST[T]:
                s1, v1 = b.inverse(None, data)
                return replace(self, focus=v1)
            return v, inverse
        else:
            return self.focus, lambda x: replace(self, focus=x)
        
    def wrapper(self)-> Callable[[Any], Any]:
        if isinstance(self.focus, MarkedResult):
            focus = cast(MarkedResult[Any], self.focus)
            return lambda x: MarkedResult(name = focus.name, value = x)
        else:
            return lambda x: x
        
    def is_named(self) -> bool: 
        return isinstance(self.focus, MarkedResult)

    def left(self) -> Optional[AST[T]]:
        match self.focus:
            case ThenResult(left=left, kind=kind):
                return replace(self, focus=left, parent=self, pruned = self.pruned or kind == ThenKind.RIGHT)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for left traversal")

    def right(self) -> Optional[AST[T]]:
        match self.focus:
            case ThenResult(right=right, kind=kind):
                return replace(self, focus=right, parent=self, pruned = self.pruned or kind == ThenKind.LEFT)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for right traversal")


    def down(self, index: int) -> Optional[AST[T]]:
        match self.focus:
            case ManyResult(value=children):
                if 0 <= index < len(children):
                    return replace(self, focus=children[index], parent=self, pruned=self.pruned)
                else:
                    raise IndexError(f"Index {index} out of bounds for ManyResult with {len(children)} children")
            case OrResult(value=value):
                if index == 0:
                    return replace(self, focus=value, parent=self, pruned=self.pruned)
                else:
                    raise IndexError(f"Index {index} out of bounds for OrResult")
            case MarkedResult(value=value):
                return replace(self, focus=value, parent=self, pruned=self.pruned)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for down traversal")

    def how_many(self)->int:
        focus = self.focus.value if isinstance(self.focus, MarkedResult) else self.focus
        match focus:
            case ManyResult(value=children):
                return len(children)
            case _:
                raise TypeError(f"Invalid focus type({self.focus}) for how_many")
            
    

    @cached_property
    def root(self) -> AST[T]:
        while self.parent is not None:
            self = self.parent  
        return self
    
