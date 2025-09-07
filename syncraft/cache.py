from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, TypeVar, Hashable, Generic, Callable, Any, Generator, overload, Literal
from weakref import WeakKeyDictionary
from syncraft.ast import SyncraftError


class RecursionError(SyncraftError):
    def __init__(self, message: str, offending: Any, expect: Any = None, **kwargs: Any) -> None:
        super().__init__(message, offending, expect, **kwargs)


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
class Cache(Generic[Args, Ret]):
    cache: WeakKeyDictionary[Callable[..., Any], Dict[Args, Ret | InProgress]] = field(default_factory=WeakKeyDictionary)

    def __contains__(self, f: Callable[..., Any]) -> bool:
        return f in self.cache

    def __repr__(self) -> str:
        return f"Cache({({f.__name__: list(c.keys()) for f, c in self.cache.items()})})"


    def __or__(self, other: Cache[Args, Any]) -> Cache[Args, Any]:
        assert self.cache is other.cache, "There should be only one global cache"
        if self.cache is other.cache:
            return self
        elif len(self.cache) == 0:
            return other
        elif len(other.cache) == 0:
            return self
        merged = Cache[Args, Ret]()
        for f, c in self.cache.items():
            merged.cache[f] = c.copy()
        for f, c in other.cache.items():
            merged.cache.setdefault(f, {}).update(c)
        return merged

    @overload
    def _execute(self, 
                 f: Callable[[Args, bool], Ret], 
                 args: Args, 
                 use_cache: bool, 
                 is_gen: Literal[False]) -> Ret: ...
    @overload
    def _execute(self, 
                 f: Callable[[Args, bool], Generator[Any, Any, Ret]], 
                 args: Args, 
                 use_cache: bool, 
                 is_gen: Literal[True]) -> Generator[Any, Any, Ret]: ...


    def _execute(self, 
            f: Callable[[Args, bool], Any], 
            args: Args, 
            use_cache:bool,
            is_gen: bool
            ) -> Ret | Generator[Any, Any, Ret]:
        if f not in self.cache:
            self.cache.setdefault(f, dict())
        c: Dict[Args, Ret | InProgress] = self.cache[f]
        if args in c:
            v = c[args]
            if isinstance(v, InProgress):
                raise RecursionError("Left-recursion detected in parser", offending=f, state=args)
            else:
                return v        
        try:
            c[args] = InProgress()
            if is_gen:
                result = yield from f(args, use_cache)
            else:
                result = f(args, use_cache)
            c[args] = result
            if not use_cache:
                c.pop(args, None)
            return result
        except Exception as e:
            c.pop(args, None)  
            raise e
        
    def gen(self, 
            f: Callable[[Args, bool], Generator[Any, Any, Ret]], 
            args: Args, 
            use_cache:bool) -> Generator[Any, Any, Ret]:
        return (yield from self._execute(f, args, use_cache, is_gen=True)) 

    def call(self, 
            f: Callable[[Args, bool], Ret], 
            args: Args, 
            use_cache:bool) -> Ret:
        return self._execute(f, args, use_cache, is_gen=False) 


