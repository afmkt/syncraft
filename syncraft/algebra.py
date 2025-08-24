from __future__ import annotations
from typing import (
    Optional, List, Any, TypeVar, Generic, Callable, Tuple, cast, 
    Dict, Type, ClassVar, Hashable
)

import traceback
from dataclasses import dataclass, replace
from weakref import WeakKeyDictionary
from abc import ABC
from enum import Enum
from functools import reduce


A = TypeVar('A')  
B = TypeVar('B')  
C = TypeVar('C')  
S = TypeVar('S')  


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
class NamedResult(Generic[A], StructuralResult):
    name: str
    value: A
    @classmethod
    def bimap(cls, f: Bimap[A, B])->Bimap[NamedResult[A], NamedResult[B]]:
        def namedf(a: NamedResult[A], s: Any) -> Tuple[NamedResult[B], Any, Callable[[NamedResult[B], Any], Tuple[NamedResult[A], Any]]]:
            newf = a.value.bimap(f) if isinstance(a.value, StructuralResult) else f                
            b, s1, inv = newf(a.value, s)
            def invf(b: NamedResult[B], s2: Any) -> Tuple[NamedResult[A], Any]:
                a2, s3 = inv(b.value, s2)
                return NamedResult(name=a.name, value=a2), s3
            return NamedResult(name=a.name, value=b), s1, invf
        return Bimap(namedf)
    
    def biarrow(self, 
              before: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity(),
              after: Callable[[Any], Biarrow[Any, Any, Any]] = lambda _: Biarrow.identity()
              ) -> Biarrow[Any, NamedResult[A], NamedResult[Any]]:
        
        inner_b = self.value.biarrow(before, after) if isinstance(self.value, StructuralResult) else before(self.value) >> after(self.value)
        def fwd(s: S, a: NamedResult[A])-> Tuple[S, NamedResult[Any]]:
            assert a == self, f"Expected {self}, got {a}"
            inner_s, inner_v = inner_b.forward(s, a.value)
            return (inner_s, replace(a, value=inner_v)) if not isinstance(inner_v, NamedResult) else (inner_s, inner_v)
        
        def inv(s: S, a: NamedResult[Any]) -> Tuple[S, NamedResult[A]]:
            assert isinstance(a, NamedResult), f"Expected NamedResult, got {type(a)}"
            inner_s, inner_v = inner_b.inverse(s, a.value)
            return (inner_s, replace(self, value=inner_v)) if not isinstance(inner_v, NamedResult) else (inner_s, replace(self, value=inner_v.value))
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
    
InProgress = object()  # Marker for in-progress state, used to prevent re-entrance in recursive calls
L = TypeVar('L')  # Left type for combined results
R = TypeVar('R')  # Right type for combined results

class Either(Generic[L, R]):
    def is_left(self) -> bool:
        return isinstance(self, Left)
    def is_right(self) -> bool:
        return isinstance(self, Right)

@dataclass(frozen=True)
class Left(Either[L, R]):
    value: Optional[L] = None

@dataclass(frozen=True)
class Right(Either[L, R]):
    value: R




@dataclass(frozen=True)
class Error:
    this: Any
    message: Optional[str] = None
    error: Optional[Any] = None    
    state: Optional[Any] = None
    committed: bool = False
    previous: Optional[Error] = None
    
    def attach( self, 
                *,
                this: Any, 
                msg: Optional[str] = None,
                err: Optional[str] = None, 
                state: Optional[Any] = None) -> Error:
        return Error(
            this=this,
            error=err,
            message=msg or str(err),
            state=state,
            previous=self
        )



@dataclass(frozen=True)        
class Algebra(ABC, Generic[A, S]):
######################################################## shared among all subclasses ########################################################
    run_f: Callable[[S, bool], Either[Any, Tuple[A, S]]] 
    name: Hashable
    _cache: ClassVar[WeakKeyDictionary[Any, Dict[Any, object | Either[Any, Tuple[Any, Any]]]]] = WeakKeyDictionary()

    def named(self, name: Hashable) -> 'Algebra[A, S]':
        return replace(self, name=name)

    def __post_init__(self)-> None:
        self._cache.setdefault(self.run_f, dict())
        
    def __call__(self, input: S, use_cache: bool) -> Either[Any, Tuple[A, S]]:
        return self.run(input, use_cache=use_cache)

    
    def run(self, input: S, use_cache: bool) -> Either[Any, Tuple[A, S]]:
        cache = self._cache[self.run_f]
        assert cache is not None, "Cache should be initialized in __post_init__"
        if input in cache:
            v = cache.get(input, None)
            if v is InProgress:
                return Left(
                    Error(
                        message="Left-recursion detected in parser",
                        this=self,
                        state=input
                    ))
            else:
                return cast(Either[Error, Tuple[A, S]], v)
        try:
            cache[input] = InProgress
            result = self.run_f(input, use_cache)
            cache[input] = result
            if not use_cache:
                cache.pop(input, None)  # Clear the cache entry if not using cache
            if isinstance(result, Left):
                if isinstance(result.value, Error):
                    result = Left(result.value.attach(this=self, state=input))
        except Exception as e:
            cache.pop(input, None)  # Clear the cache entry on exception
            traceback.print_exc()
            print(f"Exception from self.run(S): {e}")
            return Left(
                Error(
                    message="Exception from self.run(S): {e}",
                    this=self,
                    state=input,
                    error=e
                ))
        return result

    def as_(self, typ: Type[B])->B:
        return cast(typ, self) # type: ignore
        
    @classmethod
    def lazy(cls, thunk: Callable[[], Algebra[A, S]]) -> Algebra[A, S]:
        def lazy_run(input: S, use_cache:bool) -> Either[Any, Tuple[A, S]]:
            return thunk().run(input, use_cache)
        return cls(lazy_run, name=cls.__name__ + '.lazy')




    @classmethod
    def fail(cls, error: Any) -> Algebra[Any, S]:
        def fail_run(input: S, use_cache:bool) -> Either[Any, Tuple[Any, S]]:
            return Left(Error(
                error=error,
                this=cls,
                state=input
            ))
        return cls(fail_run, name=cls.__name__ + '.fail')
    @classmethod
    def success(cls, value: Any) -> Algebra[Any, S]:
        def success_run(input: S, use_cache:bool) -> Either[Any, Tuple[Any, S]]:
            return Right((value, input))
        return cls(success_run, name=cls.__name__ + '.success')
    
    @classmethod
    def factory(cls, name: str, *args: Any, **kwargs: Any) -> Algebra[A, S]:
        method = getattr(cls, name, None)
        if method is None or not callable(method):
            raise ValueError(f"Method {name} is not defined in {cls.__name__}")
        return cast(Algebra[A, S], method(*args, **kwargs))



    def cut(self) -> Algebra[A, S]:
        def commit_error(e: Any) -> Error:
            match e:
                case Error():
                    return replace(e, committed=True)
                case _:
                    return Error(
                        error=e,
                        this=self,
                        committed=True
                    )
        return self.map_error(commit_error)

    def on_fail(self, 
                func: Callable[
                    [
                        Algebra[A, S], 
                        S, 
                        Left[Any, Tuple[A, S]], 
                        Any
                    ], 
                    Either[Any, Tuple[B, S]]], 
                    ctx: Optional[Any] = None) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def fail_run(input: S, use_cache:bool) -> Either[Any, Tuple[A | B, S]]:
            result = self.run(input, use_cache)
            if isinstance(result, Left):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result, ctx))
            return cast(Either[Any, Tuple[A | B, S]], result)
        return self.__class__(fail_run, name=self.name) # type: ignore

    def on_success(self, 
                    func: Callable[
                        [
                            Algebra[A, S], 
                            S, 
                            Right[Any, Tuple[A, S]], 
                            Any
                        ], 
                        Either[Any, Tuple[B, S]]], 
                        ctx: Optional[Any] = None) -> Algebra[A | B, S]:
        assert callable(func), "func must be callable"
        def success_run(input: S, use_cache:bool) -> Either[Any, Tuple[A | B, S]]:
            result = self.run(input, use_cache)
            if isinstance(result, Right):
                return cast(Either[Any, Tuple[A | B, S]], func(self, input, result, ctx))
            return cast(Either[Any, Tuple[A | B, S]], result)
        return self.__class__(success_run, name=self.name) # type: ignore

    def debug(self, 
              label: str, 
              formatter: Optional[Callable[[
                  Algebra[Any, S], 
                  S, 
                  Either[Any, Tuple[Any, S]]], None]]=None) -> Algebra[A, S]:
        def default_formatter(alg: Algebra[Any, S], input: S, result: Either[Any, Tuple[Any, S]]) -> None:
            print(f"Debug: {'*' * 40} {alg.name} - State {'*' * 40}")
            print(input)
            print(f"Debug: {'~' * 40} (Result, State) {'~' * 40}")
            print(result)
            print()
            print()
        lazy_self: Algebra[A, S]
        def debug_run(input: S, use_cache:bool) -> Either[Any, Tuple[A, S]]:
            result = self.run(input, use_cache)
            try:
                if formatter is not None:
                    formatter(lazy_self, input, result)
                else:
                    default_formatter(lazy_self, input, result)
            except Exception as e:
                traceback.print_exc()
                print(f"Error occurred while formatting debug information: {e}")
            finally:
                return result
        lazy_self = self.__class__(debug_run, name=label)  
        return lazy_self


######################################################## fundamental combinators ############################################
    def map(self, f: Callable[[A], B]) -> Algebra[B, S]:
        def map_run(input: S, use_cache:bool) -> Either[Any, Tuple[B, S]]:
            parsed = self.run(input, use_cache)
            if isinstance(parsed, Right):
                return Right((f(parsed.value[0]), parsed.value[1]))            
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        return self.__class__(map_run, name=self.name)  # type: ignore

    def map_error(self, f: Callable[[Optional[Any]], Any]) -> Algebra[A, S]:
        def map_error_run(input: S, use_cache:bool) -> Either[Any, Tuple[A, S]]:
            parsed = self.run(input, use_cache)
            if isinstance(parsed, Left):
                return Left(f(parsed.value))
            return parsed
        return self.__class__(map_error_run, name=self.name)  

    def map_state(self, f: Callable[[S], S]) -> Algebra[A, S]:
        def map_state_run(state: S, use_cache:bool) -> Either[Any, Tuple[A, S]]:
            return self.run(f(state), use_cache)
        return self.__class__(map_state_run, name=self.name) 


    def flat_map(self, f: Callable[[A], Algebra[B, S]]) -> Algebra[B, S]:
        def flat_map_run(input: S, use_cache:bool) -> Either[Any, Tuple[B, S]]:
            parsed = self.run(input, use_cache)
            if isinstance(parsed, Right):
                return f(parsed.value[0]).run(parsed.value[1], use_cache)  
            else:
                return cast(Either[Any, Tuple[B, S]], parsed)
        return self.__class__(flat_map_run, name=self.name)  # type: ignore

    
    def or_else(self: Algebra[A, S], other: Algebra[B, S]) -> Algebra[OrResult[A | B], S]:
        def or_else_run(input: S, use_cache:bool) -> Either[Any, Tuple[OrResult[A | B], S]]:
            match self.run(input, use_cache):
                case Right((value, state)):
                    return Right((OrResult(value=value), state))
                case Left(err):
                    if isinstance(err, Error) and err.committed:
                        return Left(err)
                    match other.run(input, use_cache):
                        case Right((other_value, other_state)):
                            return Right((OrResult(value=other_value), other_state))
                        case Left(other_err):
                            return Left(other_err)
                    raise TypeError(f"Unexpected result type from {other}")
            raise TypeError(f"Unexpected result type from {self}")
        return self.__class__(or_else_run, name=f'{self.name} | {other.name}')  # type: ignore

    def then_both(self, other: 'Algebra[B, S]') -> 'Algebra[ThenResult[A, B], S]':
        def then_both_f(a: A) -> Algebra[ThenResult[A, B], S]:
            def combine(b: B) -> ThenResult[A, B]:
                return ThenResult(left=a, right=b, kind=ThenKind.BOTH)
            return other.map(combine)
        return self.flat_map(then_both_f).named(f'{self.name} + {other.name}')
            
    def then_left(self, other: Algebra[B, S]) -> Algebra[ThenResult[A, B], S]:
        return self.then_both(other).map(lambda b: replace(b, kind = ThenKind.LEFT)).named(f'{self.name} // {other.name}')

    def then_right(self, other: Algebra[B, S]) -> Algebra[ThenResult[A, B], S]:
        return self.then_both(other).map(lambda b: replace(b, kind=ThenKind.RIGHT)).named(f'{self.name} >> {other.name}')


    def many(self, *, at_least: int, at_most: Optional[int]) -> Algebra[ManyResult[A], S]:
        assert at_least > 0, "at_least must be greater than 0"
        assert at_most is None or at_least <= at_most, "at_least must be less than or equal to at_most"
        def many_run(input: S, use_cache:bool) -> Either[Any, Tuple[ManyResult[A], S]]:
            ret: List[A] = []
            current_input = input
            while True:
                match self.run(current_input, use_cache):
                    case Left(_):
                        break
                    case Right((value, next_input)):
                        ret.append(value)
                        if next_input == current_input:
                            break  # No progress, stop to avoid infinite loop
                        current_input = next_input
                        if at_most is not None and len(ret) > at_most:
                            return Left(Error(
                                    message=f"Expected at most {at_most} matches, got {len(ret)}",
                                    this=self,
                                    state=current_input
                                )) 
            if len(ret) < at_least:
                return Left(Error(
                        message=f"Expected at least {at_least} matches, got {len(ret)}",
                        this=self,
                        state=current_input
                    )) 
            return Right((ManyResult(value=tuple(ret)), current_input))
        return self.__class__(many_run, name=f'*({self.name})') # type: ignore

    


