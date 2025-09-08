from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, TypeVar, Hashable, Generic, Callable, Any, Generator, overload, Literal, List
from weakref import WeakKeyDictionary
from syncraft.ast import SyncraftError


class LeftRecursionError(SyncraftError):
    def __init__(self, message: str, offending: Any, expect: Any = None, **kwargs: Any) -> None:
        super().__init__(message, offending, expect, **kwargs)
        self.stack: List[str] = []

    def push(self, name: str) -> LeftRecursionError:
        self.stack.append(name)
        return self
    
    def __repr__(self) -> str:
        stack = "\n-> ".join(reversed(self.stack))
        hint = "Hint: Use right recursion or a repetition combinator (many/chain) to avoid left recursion."
        return f"{self.__class__.__name__}(\n{stack})\n{hint}"
    


    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class InProgress:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InProgress, cls).__new__(cls)
        return cls._instance
    def __str__(self)->str:
        return self.__class__.__name__
    def __repr__(self)->str:
        return self.__str__()




Args = TypeVar('Args', bound=Hashable)
Ret = TypeVar('Ret')

@dataclass
class Cache(Generic[Ret]):
    cache: WeakKeyDictionary[Callable[..., Any], Dict[Hashable, Ret | InProgress]] = field(default_factory=WeakKeyDictionary)

    def __contains__(self, f: Callable[..., Any]) -> bool:
        return f in self.cache

    def __repr__(self) -> str:
        return f"Cache({({f.__name__: list(c.keys()) for f, c in self.cache.items()})})"


    def __or__(self, other: Cache[Any]) -> Cache[Any]:
        assert self.cache is other.cache, "There should be only one global cache"
        return self
    
        
    def gen(self, 
            f: Callable[..., Generator[Any, Any, Ret]], 
            *args: Any, 
            **kwargs: Any) -> Generator[Any, Any, Ret]:
        if f not in self.cache:
            self.cache.setdefault(f, dict())
        c: Dict[Hashable, Ret | InProgress] = self.cache[f]
        key = (tuple(filter(lambda x: not isinstance(x, Cache), args)), tuple(sorted(filter(lambda item: not isinstance(item[1], Cache), kwargs.items()))))        
        if key in c:
            v = c[key]
            if isinstance(v, InProgress):
                raise LeftRecursionError(f"Left-recursion detected in Algebra {f}", offending=f, state=args)
            else:
                return v        
        try:
            c[key] = InProgress()
            result = yield from f(*args, **kwargs)
            c[key] = result
            if kwargs.get('use_cache', True) is False:
                c.pop(key, None)
            return result
        except Exception as e:
            c.pop(key, None)
            raise e
        



