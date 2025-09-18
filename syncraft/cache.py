from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, TypeVar, Hashable, Generic, Callable, Any, Generator, List, Optional, Tuple
from weakref import WeakKeyDictionary
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError
from collections import deque
from syncraft.utils import debug_print


L = TypeVar('L')  # Left type for combined results
R = TypeVar('R')  # Right type for combined results
S = TypeVar('S', bound=Bindable)

class Either(Generic[L, R]):
    def is_left(self) -> bool:
        return isinstance(self, Left)
    def is_right(self) -> bool:
        return isinstance(self, Right)

@dataclass(frozen=True)
class Left(Either[L, Any]):
    value: Optional[L] = None

@dataclass(frozen=True)
class Right(Either[Any, R]):
    value: R
    offender: Callable[..., Any] | None = None


@dataclass(frozen=True)
class Incomplete(Generic[S]):
    state: S

class LeftRecursionError(SyncraftError):
    def __init__(self, message: str, offender: Any, expect: Any = None, **kwargs: Any) -> None:
        super().__init__(message, offender, expect, **kwargs)
        self.stack: List[str] = []

    def push(self, name: str) -> LeftRecursionError:
        self.stack.append(name)
        return self
    
    def __repr__(self) -> str:
        stack = "\n-> ".join(reversed(self.stack))
        hint = "Hint: Use right recursion or a repetition combinator to avoid left recursion."
        return f"{self.__class__.__name__}(\n{stack})\n{hint}"
    
    def __str__(self) -> str:
        return self.__repr__()
    
Args = TypeVar('Args', bound=Hashable)
A = TypeVar('A')
Ret = TypeVar('Ret', bound=Either[Any, Tuple[Any, Any]])

@dataclass(frozen=True)
class InProgress(Generic[Ret]):
    offender: Callable[..., Any] | None = None
    payload: Optional[Ret] = None

@dataclass(frozen=True)
class Finalized:
    payload: Optional[Any] = None
    



@dataclass
class Cache(Generic[A, Ret]):
    stack: deque[Tuple[Callable[..., Any], str]] = field(default_factory=deque)
    cache: WeakKeyDictionary[Callable[..., Generator[Any, Any, Ret]], Dict[A, Ret | InProgress[Ret]]] = field(default_factory=WeakKeyDictionary)

    
    def mark(self, in_progress: InProgress[Ret]) -> InProgress[Ret]:
        return replace(in_progress, offender=self.stack[-1][0])

    def push(self, f: Callable[..., Generator[Any, Any, Ret]], name: str) -> Cache[A, Ret]:
        self.stack.append((f, name))
        return self
    def pop(self) -> Tuple[Callable[..., Generator[Any, Any, Ret]], str]:
        return self.stack.pop()

    def __contains__(self, f: Callable[..., Generator[Any, Any, Ret]]) -> bool:
        return f in self.cache

    def __repr__(self) -> str:
        parts = []
        for f, c in self.cache.items():
            for k, v in c.items():
                parts.append(f"{f.__name__}@{k} -> {v}")
        content = "\n".join(parts)
        return f"Cache({content})"

    def __str__(self) -> str:
        return self.__repr__()
    
    def __or__(self, other: Cache[A, Ret]) -> Cache[A, Ret]:
        assert self.cache is other.cache, "There should be only one global cache"
        return self

    def return_value(self, v: Ret, s: A) -> Generator[Any, Any, Ret]:
        def return_value_f(_: A, cache: Cache[A, Ret]) -> Generator[Any, Any, Ret]:
            yield from ()
            return v
        return (yield from self.gen(return_value_f, s))
    

    def gen(self, 
            f: Callable[[A, Cache[A, Ret]], Generator[Any, Any, Ret]], 
            key: A) -> Generator[Any, Any, Ret]:
        def grow_inprogress(d: Dict[A, Ret | InProgress[Ret]], key: A, fix: Ret | Finalized) -> None:
            v = d.get(key, None)
            if isinstance(v, InProgress):
                if isinstance(fix, InProgress):
                    raise LeftRecursionError("Can not fix InProgress with another InProgress", offender=v.offender, expect="a final value")
                elif isinstance(fix, Finalized):
                    if v.payload is None:
                        if fix.payload is None:
                            raise LeftRecursionError("Can not fix InProgress with another InProgress", offender=v.offender, expect="a final value")
                        debug_print(f'Finalizing InProgress at {key} => {fix.payload}')
                        d[key] = fix.payload
                    else:
                        debug_print(f'Finalizing InProgress at {key} => {v.payload}')
                        d[key] = v.payload
                elif v.payload != fix:
                    if v.payload is None:
                        debug_print(f'Growing InProgress at {key} => {fix}')
                        d[key] = replace(v, payload=fix)
                    elif isinstance(fix, Right):
                        assert isinstance(v.payload, Right), "Can only combine Right with Right"
                        assert isinstance(v.payload.value, tuple) and isinstance(fix.value, tuple) and len(v.payload.value) == 2 and len(fix.value) == 2, "Right values should be tuples of length 2"
                        old_value = v.payload.value[0]
                        # old_state = v.payload.value[1]
                        new_value = fix.value[0]
                        # new_state = fix.value[1]
                        if old_value == new_value:
                            debug_print(f'Fixing InProgress at {key} => <{v.payload}>')
                            d[key] = v.payload  # type: ignore
                        else:
                            debug_print(f'Growing InProgress at {key} => {fix}')
                            d[key] = replace(v, payload=fix) # type: ignore
                    else:
                        debug_print(f'Growing InProgress at {key} => {fix}')
                        d[key] = replace(v, payload=fix)
                else:
                    d[key] = fix
            else:
                assert not isinstance(fix, Finalized), "Can not put Finalized into cache"
                d[key] = fix

        if f not in self.cache:
            self.cache.setdefault(f, dict())
        c: Dict[A, Ret | InProgress[Ret]] = self.cache[f]
        if key in c:
            v = c[key]
            while isinstance(v, InProgress):
                v = c[key] = self.mark(v)
                fix = yield v
                grow_inprogress(c, key, fix)
                v = c[key]
            debug_print(f'--- {f} Cache hit ---')
            return v  
        try:
            c[key] = InProgress()
            result = yield from f(key, self)
            assert not isinstance(result, InProgress), "Function should not return InProgress"
            debug_print(f'--- {f} Cache updated ---')
            debug_print(c[key])
            c[key] = result
            debug_print(c[key])
            return result
        except Exception as e:
            c.pop(key, None)
            raise e
        



