

from __future__ import annotations
import re
from typing import (
    Optional, Any, TypeVar, Tuple, runtime_checkable, cast,
    Generic, Callable, Union, Protocol, Type, List, ClassVar
)


from dataclasses import dataclass, replace, is_dataclass, asdict, fields
from enum import Enum




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
    run_f: Callable[[A], Tuple[B, Callable[[B], A]]]
    def __call__(self, a: A) -> Tuple[B, Callable[[B], A]]:
        return self.run_f(a)    
    def __rshift__(self, other: Bimap[B, C] | Biarrow[B, C]) -> Bimap[A, C]:
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
            raise TypeError(f"Unsupported type for Bimap >>: {type(other)}")
    def __rrshift__(self, other: Bimap[C, A] | Biarrow[C, A]) -> Bimap[C, B]:
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
            raise TypeError(f"Unsupported type for Bimap <<: {type(other)}")


    @staticmethod
    def const(a: B)->Bimap[B, B]:
        return Bimap(lambda _: (a, lambda b: b))

    @staticmethod
    def identity()->Bimap[A, A]:
        return Bimap(lambda a: (a, lambda b: b))

    @staticmethod
    def when(cond: Callable[[A], bool],
             then: Bimap[A, B],
             otherwise: Optional[Bimap[A, C]] = None) -> Bimap[A, A | B | C]:
        def when_run(a:A) -> Tuple[A | B | C, Callable[[A | B | C], A]]:
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
    def bimap(self, r: Bimap[Any, Any]=Bimap.identity()) -> Tuple[Any, Callable[[Any], Any]]:
        return r(self)

@dataclass(frozen=True)
class Nothing(AST):
    def __str__(self)->str:
        return self.__class__.__name__
    def __repr__(self)->str:
        return self.__str__()


@dataclass(frozen=True)
class Marked(Generic[A], AST):
    name: str
    value: A
    def bimap(self, r: Bimap[A, B]=Bimap.identity()) -> Tuple[Marked[B], Callable[[Marked[B]], Marked[A]]]:
        v, inner_f = self.value.bimap(r) if isinstance(self.value, AST) else r(self.value)
        return Marked(name=self.name, value=v), lambda b: Marked(name = b.name, value=inner_f(b.value))
    
class ChoiceKind(Enum):
    LEFT = 'left'
    RIGHT = 'right'

@dataclass(frozen=True)
class Choice(Generic[A, B], AST):
    kind: Optional[ChoiceKind]
    value: Optional[A | B] = None
    def bimap(self, r: Bimap[A | B, C]=Bimap.identity()) -> Tuple[Optional[C], Callable[[Optional[C]], Choice[A, B]]]:
        if self.value is None:
            return None, lambda c: replace(self, value=None, kind=None)
        else:
            v, inv = self.value.bimap(r) if isinstance(self.value, AST) else r(self.value)
            return v, lambda c: replace(self, value=inv(c) if c is not None else None, kind=None)

@dataclass(frozen=True)
class Many(Generic[A], AST):
    value: Tuple[A, ...]
    def bimap(self, r: Bimap[A, B]=Bimap.identity()) -> Tuple[List[B], Callable[[List[B]], Many[A]]]:
        ret = [v.bimap(r) if isinstance(v, AST) else r(v) for v in self.value]
        def inv(bs: List[B]) -> Many[A]:
            if len(bs) <= len(ret):
                return Many(value = tuple(ret[i][1](bs[i]) for i in range(len(bs)))) 
            else:
                half = [ret[i][1](bs[i]) for i in range(len(bs))]
                tmp = [ret[-1][1](bs[i]) for i in range(len(ret)-1, len(bs))]
                return Many(value = tuple(half + tmp))
        return [v[0] for v in ret], inv

class ThenKind(Enum):
    BOTH = '+'
    LEFT = '//'
    RIGHT = '>>'
    
@dataclass(eq=True, frozen=True)
class Then(Generic[A, B], AST):
    kind: ThenKind
    left: A
    right: B
    def arity(self)->int:
        if self.kind == ThenKind.LEFT:
            return self.left.arity() if isinstance(self.left, Then) else 1
        elif self.kind == ThenKind.RIGHT:
            return self.right.arity() if isinstance(self.right, Then) else 1
        elif self.kind == ThenKind.BOTH:
            left_arity = self.left.arity() if isinstance(self.left, Then) else 1
            right_arity = self.right.arity() if isinstance(self.right, Then) else 1
            return left_arity + right_arity
        else:
            return 1

    def bimap(self, r: Bimap[A|B, Any]=Bimap.identity()) -> Tuple[Any | Tuple[Any, ...], Callable[[Any | Tuple[Any, ...]], Then[A, B]]]:
        def need_wrap(x: Any) -> bool:
            return not (isinstance(x, Then) and x.kind == ThenKind.BOTH)
        match self.kind:
            case ThenKind.LEFT:
                lb, linv = self.left.bimap(r) if isinstance(self.left, AST) else r(self.left)
                return lb, lambda c: replace(self, left=cast(A, linv(c)))
            case ThenKind.RIGHT:
                rb, rinv = self.right.bimap(r) if isinstance(self.right, AST) else r(self.right)
                return rb, lambda c: replace(self, right=cast(B, rinv(c)))
            case ThenKind.BOTH:
                lb, linv = self.left.bimap(r) if isinstance(self.left, AST) else r(self.left)
                rb, rinv = self.right.bimap(r) if isinstance(self.right, AST) else r(self.right)
                left_v = (lb,) if need_wrap(self.left) else lb
                right_v = (rb,) if need_wrap(self.right) else rb
                def invf(b: Tuple[C, ...]) -> Then[A, B]:
                    left_size = self.left.arity() if isinstance(self.left, Then) else 1
                    right_size = self.right.arity() if isinstance(self.right, Then) else 1
                    lraw: Tuple[Any, ...] = b[:left_size]
                    rraw: Tuple[Any, ...] = b[left_size:left_size + right_size]
                    lraw = lraw[0] if left_size == 1 else lraw
                    rraw = rraw[0] if right_size == 1 else rraw
                    la = linv(lraw)
                    ra = rinv(rraw)
                    return replace(self, left=cast(A, la), right=cast(B, ra))
                return left_v + right_v, invf


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


E = TypeVar("E", bound=DataclassInstance)

Collector = Type[E] | Callable[..., E]
@dataclass(frozen=True)
class Collect(Generic[A, E], AST): 
    collector: Collector
    value: A
    def bimap(self, r: Bimap[A, B]=Bimap.identity()) -> Tuple[B | E, Callable[[B | E], Collect[A, E]]]:
        b, inner_f = r(self.value)
        if isinstance(self.value, Then) and self.value.kind == ThenKind.BOTH:
            assert isinstance(b, tuple), f"Expected tuple from Then.BOTH combinator, got {type(b)}"
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
                assert is_dataclass(e), f"Expected dataclass instance for collector inverse, got {type(e)}"
                named_dict = asdict(e)     
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
        else:
            return b, lambda e: replace(self, value=inner_f(e)) # type: ignore

#########################################################################################################################
@dataclass(frozen=True)
class Token(AST):
    token_type: Enum
    text: str
    def __str__(self) -> str:
        return f"{self.token_type.name}({self.text})"
    
    def __repr__(self) -> str:
        return self.__str__()
            
@runtime_checkable
class TokenProtocol(Protocol):
    @property
    def token_type(self) -> Enum: ...
    @property
    def text(self) -> str: ...

T = TypeVar('T', bound=TokenProtocol)  


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


ParseResult = Union[
    Then['ParseResult[T]', 'ParseResult[T]'], 
    Marked['ParseResult[T]'],
    Choice['ParseResult[T]', 'ParseResult[T]'],
    Many['ParseResult[T]'],
    Collect['ParseResult[T]', Any],
    Nothing,
    T,
]



