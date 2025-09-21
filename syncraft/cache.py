from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, TypeVar, Hashable, Generic, Callable, Any, Generator, List, Optional, Tuple
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError
from collections import deque
from syncraft.utils import debug_print, callable_str, TablePrinter

table_printer = TablePrinter()

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
    def __repr__(self) -> str:
        if self.offender is not None:
            return f"Right({self.value}, offender=<{self.offender.__name__} @ {hex(id(self.offender))}>)"
        else:
            return f"Right({self.value})"


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
        return f"\n{stack}\n{hint}"
    
    def __str__(self) -> str:
        return self.__repr__()
    
Args = TypeVar('Args', bound=Hashable)
A = TypeVar('A')
Ret = TypeVar('Ret', bound=Either[Any, Tuple[Any, Any]])

@dataclass(frozen=True)
class InProgress(Generic[Ret]):
    offender: Callable[..., Any] | None = None
    payload: Optional[Ret] = None
    def __repr__(self) -> str:
        parts = []
        if self.offender is not None:
            parts.append(f"offender=<{self.offender.__name__} @ {hex(id(self.offender))}>")
        if self.payload is not None:
            parts.append(f"payload={self.payload}")
        s = '\n, '.join(parts)
        return f"InProgress({s})"
    
    def __str__(self) -> str:
        return self.__repr__()

@dataclass(frozen=True)
class Finalized(Generic[Ret]):
    payload: Optional[Ret] = None
    



@dataclass
class Cache(Generic[A, Ret]):
    stack: deque[Tuple[Callable[..., Any], str]] = field(default_factory=deque)
    cache: dict[Callable[..., Any], Dict[A, Ret | InProgress[Ret]]] = field(default_factory=dict)

    def mark(self, in_progress: InProgress[Ret]) -> InProgress[Ret]:
        return replace(in_progress, offender=self.stack[-1][0])

    def push(self, f: Callable[..., Generator[Any, Any, Ret]], name: str) -> Cache[A, Ret]:
        self.stack.append((f, name))
        return self
    def pop(self) -> Tuple[Callable[..., Generator[Any, Any, Ret]], str]:
        return self.stack.pop()

    def __contains__(self, f: Callable[..., Generator[Any, Any, Ret]]) -> bool:
        return f in self.cache

    def flat_stack(self)->List[Tuple[str, str, str]]:
        parts:List[Tuple[str, str, str]] = [('name', 'id', 'function')]
        if len(self.stack) > 0:
            for s in self.stack:
                parts.append((s[0].__name__, str(hex(id(s[0]))), s[1]))
            return parts
        else:
            return []

    def flat_cache(self)->List[Tuple[str, str, Any, Any]]:
        parts:List[Tuple[str, str, Any, Any]] = [('name', 'id', 'position', 'value')]
        if len(self.cache) > 0:
            for func, c in self.cache.items():
                for k, v in c.items():
                    parts.append((func.__name__, str(hex(id(func))), k, v))
            return parts
        else:
            return []

    def __repr__(self) -> str:
        parts = []
        for f, c in self.cache.items():
            for k, v in c.items():
                parts.append(f"{k} -> {v} ^ {callable_str(f)}")
        content = "\n    ".join(parts)
        sparts = []
        for s in self.stack:
            sparts.append(f"> {s[1]} : {callable_str(s[0])}")
        return f"Cache(\n    {content}, \nStack:\n" + "\n".join(sparts) + ")"

    def __str__(self) -> str:
        return self.__repr__()
    
    def __or__(self, other: Cache[A, Ret]) -> Cache[A, Ret]:
        assert self.cache is other.cache, "There should be only one global cache"
        return self

    def return_value(self, v: Ret, s: A, name: str) -> Generator[Any, Any, Ret]:
        def return_value_f(_: A, cache: Cache[A, Ret]) -> Generator[Any, Any, Ret]:
            yield from ()
            return v
        return_value_f.__name__ = name
        return (yield from self.gen(return_value_f, s))
    
    def update(self, 
               f: Callable[..., Any], 
               key: A, value: Ret | InProgress[Ret] | Finalized[Ret]) -> None:
        self.cache.setdefault(f, dict())
        c: Dict[A, Ret | InProgress[Ret]] = self.cache.get(f, dict())  
        v = c.get(key, None)
        if not isinstance(v, InProgress):
            assert not isinstance(value, Finalized), "Can not put Finalized into cache"
            c[key] = value
        else:
            # v is InProgress and value must NOT be InProgress
            assert not isinstance(value, InProgress), "Can not fix InProgress with another InProgress"
            if isinstance(value, Finalized):
                # v is InProgress and value is Finalized
                assert v.payload is not None or value.payload is not None, "Can not fix InProgress.None with Finalized.None"
                c[key] = v.payload if value.payload is None else value.payload # type: ignore
            elif v.payload != value:
                # v is InProgress and value is Right or Left
                if v.payload is None:
                    if v.offender is not None:
                        c[key] = replace(v, payload=value)
                    else:
                        c[key] = value
                elif isinstance(value, Right):
                    assert isinstance(v.payload, Right), "Can only combine Right with Right"
                    old_value = v.payload.value[0]
                    new_value = value.value[0]
                    if old_value == new_value:
                        c[key] = v.payload  # type: ignore
                    else:
                        c[key] = replace(v, payload=value) # type: ignore
                else:
                    assert False, f"Can grow InProgress with Right only, got {value}"

                
    @staticmethod                
    def grow_inprogress(d: Dict[A, Ret | InProgress[Ret]], key: A, fix: Ret | Finalized) -> None:
        v = d.get(key, None)
        debug_print(f'--- grow_inprogress d@{id(d)}[{key}] ---')
        if isinstance(v, InProgress):
            if isinstance(fix, InProgress):
                raise LeftRecursionError("Can not fix InProgress with another InProgress", offender=v.offender, expect="a final value")
            elif isinstance(fix, Finalized):
                if v.payload is None:
                    if fix.payload is None:
                        raise LeftRecursionError("Can not fix InProgress with another InProgress", offender=v.offender, expect="a final value")
                    d[key] = fix.payload
                else:
                    d[key] = v.payload
            elif v.payload != fix:
                if v.payload is None:
                    if v.offender is not None:
                        d[key] = replace(v, payload=fix)
                    else:
                        d[key] = fix
                elif isinstance(fix, Right):
                    assert isinstance(v.payload, Right), "Can only combine Right with Right"
                    assert isinstance(v.payload.value, tuple) and isinstance(fix.value, tuple) and len(v.payload.value) == 2 and len(fix.value) == 2, "Right values should be tuples of length 2"
                    old_value = v.payload.value[0]
                    new_value = fix.value[0]
                    if old_value == new_value:
                        d[key] = v.payload  # type: ignore
                    else:
                        d[key] = replace(v, payload=fix) # type: ignore
                else:
                    d[key] = replace(v, payload=fix)
            else:
                d[key] = fix
        else:
            assert not isinstance(fix, Finalized), "Can not put Finalized into cache"
            d[key] = fix
                
            

    def gen(self, 
            f: Callable[[A, Cache[A, Ret]], Generator[Any, Any, Ret]], 
            key: A) -> Generator[Any, Any, Ret]:
        if f not in self.cache:
            self.cache.setdefault(f, dict())
        c: Dict[A, Ret | InProgress[Ret]] = self.cache[f]
        if key in c:
            v = c[key]
            if isinstance(v, InProgress):
                raise LeftRecursionError("Left recursion detected", offender=f, expect="a final value")
            return v  
        try:
            c[key] = InProgress()
            result = yield from f(key, self)
            c[key] = result
            return result
        except Exception as e:
            c.pop(key, None)
            raise e
        



