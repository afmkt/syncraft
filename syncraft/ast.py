

from __future__ import annotations
import re
from typing import (
    Optional, Any, TypeVar, Tuple, runtime_checkable, 
    Dict, Generic, Callable, Union, cast, List, Protocol, Type
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
class Reducer(Generic[A, S]):
    run_f: Callable[[A, S], S]
    def __call__(self, a: A, s: S) -> S:
        return self.run_f(a, s)
    
    def map(self, f: Callable[[B], A]) -> Reducer[B, S]:
        def map_run(b: B, s: S) -> S:
            return self(f(b), s)
        return Reducer(map_run)
    

    
@dataclass(frozen=True)
class Bimap(Generic[A, B]):
    run_f: Callable[[A], Tuple[B, Callable[[B], A]]]
    def __call__(self, a: A) -> Tuple[B, Callable[[B], A]]:
        return self.run_f(a)    
    def __rshift__(self, other: Bimap[B, C]) -> Bimap[A, C]:
        def then_run(a: A) -> Tuple[C, Callable[[C], A]]:
            b, inv1 = self(a)
            c, inv2 = other(b)
            def inv(c2: C) -> A:
                return inv1(inv2(c2))
            return c, inv
        return Bimap(then_run)
    @staticmethod
    def const(a: B)->Bimap[B, B]:
        return Bimap(lambda _: (a, lambda b: b))

    @staticmethod
    def identity()->Bimap[Any, Any]:
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

    def bimap(self, f: Bimap[Any, Any]=Bimap.identity())->Tuple[Any, Callable[[Any], Any]]:
        return f(self)

    
@dataclass(frozen=True)
class MarkedResult(Generic[A], StructuralResult):
    name: str
    value: A
    def bimap(self, f: Bimap[A, B]=Bimap.identity())->Tuple[MarkedResult[B], Callable[[MarkedResult[B]], MarkedResult[A]]]:
        b, inv = self.value.bimap(f) if isinstance(self.value, StructuralResult) else f(self.value)
        return MarkedResult(name=self.name, value=b), lambda b: replace(self, value=inv(b.value))


@dataclass(eq=True, frozen=True)
class ManyResult(Generic[A], StructuralResult):
    value: Tuple[A, ...]
    def bimap(self, f: Bimap[A, B]=Bimap.identity())->Tuple[List[B], Callable[[List[B]], ManyResult[A]]]:
        assert self.value
        forward = [v.bimap(f) if isinstance(v, StructuralResult) else f(v) for v in self.value]
        def invf(b: List[B]) -> ManyResult[A]:
            assert len(b) <= len(forward)
            return replace(self, value=tuple([forward[i][1](bb) for i, bb in enumerate(b)]))
        return [b for b, _ in forward], invf



@dataclass(eq=True, frozen=True)
class OrResult(Generic[A], StructuralResult):
    value: A
    def bimap(self, f: Bimap[A, B]=Bimap.identity())->Tuple[B, Callable[[B], OrResult[A]]]:
        b, inv = self.value.bimap(f) if isinstance(self.value, StructuralResult) else f(self.value)
        return b, lambda b: replace(self, value=inv(b))

class ThenKind(Enum):
    BOTH = '+'
    LEFT = '//'
    RIGHT = '>>'
    
FlatThen = Tuple[Any, ...]
MarkedThen = Tuple[Dict[str, Any] | Any, FlatThen]

@dataclass(eq=True, frozen=True)
class ThenResult(Generic[A, B], StructuralResult):
    kind: ThenKind
    left: A
    right: B
    @staticmethod
    def collect_marked(a: FlatThen, f: Optional[Callable[..., Any]] = None)->Tuple[MarkedThen, Callable[[MarkedThen], FlatThen]]:
        index: List[str | int] = []
        named_count = 0
        for i, v in enumerate(a):
            if isinstance(v, MarkedResult):
                index.append(v.name)
                named_count += 1
            else:
                index.append(i - named_count)
        named = {v.name: v.value for v in a if isinstance(v, MarkedResult)}
        unnamed = [v for v in a if not isinstance(v, MarkedResult)]
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

    def bimap(self, f: Bimap[Any, Any]=Bimap.identity()) -> Tuple[FlatThen, Callable[[FlatThen], ThenResult[A, B]]]:
        match self.kind:
            case ThenKind.LEFT:
                lb, linv = self.left.bimap(f) if isinstance(self.left, StructuralResult) else f(self.left)
                return lb, lambda b: replace(self, left=linv(b))
            case ThenKind.RIGHT:
                rb, rinv = self.right.bimap(f) if isinstance(self.right, StructuralResult) else f(self.right)
                return rb, lambda b: replace(self, right=rinv(b))
            case ThenKind.BOTH:
                lb, linv = self.left.bimap(f) if isinstance(self.left, StructuralResult) else f(self.left)
                rb, rinv = self.right.bimap(f) if isinstance(self.right, StructuralResult) else f(self.right)
                left_v = (lb,) if not isinstance(self.left, ThenResult) else lb
                right_v = (rb,) if not isinstance(self.right, ThenResult) else rb
                def invf(b: Tuple[Any, ...]) -> ThenResult[A, B]:
                    left_size = self.left.arity() if isinstance(self.left, ThenResult) else 1
                    right_size = self.right.arity() if isinstance(self.right, ThenResult) else 1
                    lraw = b[:left_size]
                    rraw = b[left_size:left_size + right_size]
                    lraw = lraw[0] if left_size == 1 else lraw
                    rraw = rraw[0] if right_size == 1 else rraw
                    la = linv(lraw)
                    ra = rinv(rraw)
                    return replace(self, left=la, right=ra)
                return left_v + right_v, invf
            
    def bimap_collected(self, f: Bimap[Any, Any]=Bimap.identity()) -> Tuple[MarkedThen, Callable[[MarkedThen], ThenResult[A, B]]]:
        data, invf = self.bimap(f)                
        data, func = ThenResult.collect_marked(data)
        return data, lambda d: invf(func(d))


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
            data, invf = self.focus.bimap()
            return data, lambda x: replace(self, focus=invf(x))
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
    
