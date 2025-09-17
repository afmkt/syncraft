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
class Cache(Generic[Ret]):
    cache: WeakKeyDictionary[Callable[..., Any], Dict[Hashable, Ret | InProgress[Ret]]] = field(default_factory=WeakKeyDictionary)

    def __contains__(self, f: Callable[..., Any]) -> bool:
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
    
    def __or__(self, other: Cache[Any]) -> Cache[Any]:
        assert self.cache is other.cache, "There should be only one global cache"
        return self
    
    def return_value(self, v: Ret) -> Generator[Any, Any, Ret]:
        def return_value_f()->Generator[Any, Any, Ret]:
            yield from ()
            return v
        return (yield from self.gen(return_value_f))
    

    def gen(self, 
            f: Callable[..., Generator[Any, Any, Ret]], 
            *args: Any, 
            **kwargs: Any) -> Generator[Any, Any, Ret]:
        
        if f not in self.cache:
            self.cache.setdefault(f, dict())
        c: Dict[Hashable, Ret | InProgress[Ret]] = self.cache[f]
        key = (tuple(filter(lambda x: not isinstance(x, Cache), args)), tuple(sorted(filter(lambda item: not isinstance(item[1], Cache), kwargs.items()))))        
        if key in c:
            while True:
                v = c[key]
                if not isinstance(v, InProgress):
                    return v
                else:
                    fix = yield v
                    match fix:
                        case InProgress(payload=_):
                            # can not fix in progress with another in progress
                            raise LeftRecursionError(f"Left-recursion detected in Algebra {f}", offending=f, state=args)
                    c[key] = fix
                    return fix
        try:
            c[key] = InProgress()
            result = yield from f(*args, **kwargs)
            assert not isinstance(result, InProgress), "Function should not return InProgress"
            c[key] = result
            return result
        except Exception as e:
            c.pop(key, None)
            raise e
        



