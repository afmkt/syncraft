from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, TypeVar, Hashable, Generic, Callable, Any, Generator, List, Optional, Tuple
from weakref import WeakKeyDictionary
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError
from rich import print
L = TypeVar('L')  # Left type for combined results
R = TypeVar('R')  # Right type for combined results
S = TypeVar('S', bound=Bindable)

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
class Incomplete(Generic[S]):
    state: S

class LeftRecursionError(SyncraftError):
    def __init__(self, message: str, offending: Any, expect: Any = None, **kwargs: Any) -> None:
        super().__init__(message, offending, expect, **kwargs)
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
Ret = TypeVar('Ret')

@dataclass(frozen=True)
class InProgress(Generic[Ret]):
    payload: Optional[Ret] = None
    
@dataclass
class Cache(Generic[A, Ret]):
    cache: WeakKeyDictionary[Callable[[A, Cache[A, Ret]], Any], Dict[A, Ret | InProgress[Ret]]] = field(default_factory=WeakKeyDictionary)

    def __contains__(self, f: Callable[[A, Cache[A, Ret]], Any]) -> bool:
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
            key: A, 
            ) -> Generator[Any, Any, Ret]:
        def grow_inprogress(d: Dict[A, Ret | InProgress[Ret]], key: A, fix: Ret) -> None:
            v = d.get(key, None)
            if isinstance(v, InProgress):
                if v.payload != fix:
                    d[key] = InProgress(fix)
                else:
                    d[key] = fix
            else:
                d[key] = fix

        if f not in self.cache:
            self.cache.setdefault(f, dict())
        c: Dict[A, Ret | InProgress[Ret]] = self.cache[f]
        if key in c:
            v = c[key]
            while isinstance(v, InProgress):
                fix = yield v
                if isinstance(fix, InProgress):
                    raise LeftRecursionError("Can not fix InProgress with another InProgress", offending=fix, expect="a final value")
                grow_inprogress(c, key, fix)
                v = c[key]
            return v  
        try:
            c[key] = InProgress()
            result = yield from f(key, self)
            assert not isinstance(result, InProgress), "Function should not return InProgress"
            c[key] = result
            return result
        except Exception as e:
            c.pop(key, None)
            raise e
        



