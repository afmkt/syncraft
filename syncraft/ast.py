

from __future__ import annotations
import re
from typing import (
    Optional, Any, TypeVar, Tuple, runtime_checkable, Self,
    Dict, Generic, Callable, Union, Protocol, Type
)


from dataclasses import dataclass
from enum import Enum
from syncraft.constraint import Bindable



A = TypeVar('A')
B = TypeVar('B')  
C = TypeVar('C')  
D = TypeVar('D')
S = TypeVar('S', bound=Bindable)  

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
class AST:
    def walk(self, r: Reducer[Any, S], s: S) -> S:
        return s

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
    def walk(self, r: Reducer[A, S], s: S) -> S:
        return self.value.walk(r, s) if isinstance(self.value, AST) else r(self.value, s)


class DataclassProtocol(Protocol):
    __dataclass_fields__: dict

E = TypeVar("E")
@dataclass(frozen=True)
class Collect(Generic[A, E], AST): 
    collector: Type[E]
    value: A

class ChoiceKind(Enum):
    LEFT = 'left'
    RIGHT = 'right'

@dataclass(frozen=True)
class Choice(Generic[A, B], AST):
    kind: Optional[ChoiceKind]
    value: Optional[A | B] = None
    def walk(self, r: Reducer[A | B, S], s: S) -> S:
        if self.value is not None:
            if isinstance(self.value, AST):
                return self.value.walk(r, s)
            else:
                return r(self.value, s)
        return s

@dataclass(frozen=True)
class Many(Generic[A], AST):
    value: Tuple[A, ...]
    def walk(self, r: Reducer[A, S], s: S) -> S:
        for item in self.value:
            if isinstance(item, AST):
                s = item.walk(r, s)
            else:
                s = r(item, s)
        return s

class ThenKind(Enum):
    BOTH = '+'
    LEFT = '//'
    RIGHT = '>>'
    
FlatThen = Tuple[Any, ...]
MarkedThen = Tuple[Dict[str, Any] | Any, FlatThen]

@dataclass(eq=True, frozen=True)
class Then(Generic[A, B], AST):
    kind: ThenKind
    left: A
    right: B
    def walk(self, r: Reducer[A | B, S], s: S) -> S:
        if isinstance(self.left, AST):
            s = self.left.walk(r, s)
        else:
            s = r(self.left, s)
        if isinstance(self.right, AST):
            s = self.right.walk(r, s)
        else:
            s = r(self.right, s)
        return s

@dataclass(frozen=True)
class Token(AST):
    token_type: Enum
    text: str
    def __str__(self) -> str:
        return f"{self.token_type.name}({self.text})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def walk(self, r: Reducer['Token', S], s: S) -> S:
        return r(self, s)

        
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
    Nothing,
    T,
]



"""
    @staticmethod
    def collect_marked(a: FlatThen, f: Optional[Callable[..., Any]] = None)->Tuple[MarkedThen, Callable[[MarkedThen], FlatThen]]:
        index: List[str | int] = []
        named_count = 0
        for i, v in enumerate(a):
            if isinstance(v, Marked):
                index.append(v.name)
                named_count += 1
            else:
                index.append(i - named_count)
        named = {v.name: v.value for v in a if isinstance(v, Marked)}
        unnamed = [v for v in a if not isinstance(v, Marked)]
        if f is None:
            ret = (named, tuple(unnamed))
        else:
            ret = (f(**named), tuple(unnamed))
        def invf(b: MarkedThen) -> Tuple[Any, ...]:
            named_value, unnamed_value = b 
            assert isinstance(named_value, dict) or is_dataclass(named_value), f"Expected dict or dataclass for named values, got {type(named_value)}"
            if is_dataclass(named_value):
                named_dict = named | asdict(cast(Any, named_value))    
            else:
                named_dict = named | named_value
            ret = []
            for x in index:
                if isinstance(x, str):
                    assert x in named_dict, f"Missing named value: {x}"
                    ret.append(named_dict[x])
                else:
                    assert 0 <= x < len(unnamed_value), f"Missing unnamed value at index: {x}"
                    ret.append(unnamed_value[x])
            return tuple(ret)
        return ret, invf

    def bimap(self, f: Bimap[Any, Any]=Bimap.identity()) -> Tuple[FlatThen, Callable[[FlatThen], Then[A, B]]]:
        match self.kind:
            case ThenKind.LEFT:
                lb, linv = self.left.bimap(f) if isinstance(self.left, AST) else f(self.left)
                return lb, lambda b: replace(self, left=linv(b))
            case ThenKind.RIGHT:
                rb, rinv = self.right.bimap(f) if isinstance(self.right, AST) else f(self.right)
                return rb, lambda b: replace(self, right=rinv(b))
            case ThenKind.BOTH:
                lb, linv = self.left.bimap(f) if isinstance(self.left, AST) else f(self.left)
                rb, rinv = self.right.bimap(f) if isinstance(self.right, AST) else f(self.right)
                left_v = (lb,) if not isinstance(self.left, Then) else lb
                right_v = (rb,) if not isinstance(self.right, Then) else rb
                def invf(b: Tuple[Any, ...]) -> Then[A, B]:
                    left_size = self.left.arity() if isinstance(self.left, Then) else 1
                    right_size = self.right.arity() if isinstance(self.right, Then) else 1
                    lraw = b[:left_size]
                    rraw = b[left_size:left_size + right_size]
                    lraw = lraw[0] if left_size == 1 else lraw
                    rraw = rraw[0] if right_size == 1 else rraw
                    la = linv(lraw)
                    ra = rinv(rraw)
                    return replace(self, left=la, right=ra)
                return left_v + right_v, invf
            
    def bimap_collected(self, f: Bimap[Any, Any]=Bimap.identity()) -> Tuple[MarkedThen, Callable[[MarkedThen], Then[A, B]]]:
        data, invf = self.bimap(f)                
        data, func = Then.collect_marked(data)
        return data, lambda d: invf(func(d))


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


"""