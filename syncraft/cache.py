from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, TypeVar, Hashable, Generic, Callable, Any, Generator, List, Optional, Tuple, cast
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


class InProgress:
    pass        

@dataclass
class LeftRecHead(Generic[A, Ret]):
    """Represents a left recursion head entry during seed-and-grow.

    Attributes:
        f: The parsing function (rule) associated with this head.
        key: The input state key for memoization.
        result: The current best (longest consuming) result; None until first seed completes.
        growing: Flag indicating we are currently in a growth iteration.
        improved: Whether any iteration improved (consumed more input) than the seed.
    """
    f: Callable[[A, "Cache[A, Ret]"], Generator[Any, Any, Ret]]
    key: A
    result: Optional[Ret] = None
    growing: bool = False
    improved: bool = False




@dataclass
class Cache(Generic[A, Ret]):
    cache: dict[Callable[..., Any], Dict[A, Ret | InProgress | LeftRecHead[A, Ret]]] = field(default_factory=dict)

    def __contains__(self, f: Callable[..., Generator[Any, Any, Ret]]) -> bool:
        return f in self.cache



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
        return f"Cache(\n    {content})"

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
    


    # ---------- Left recursion recovery helpers ----------
    def _is_success(self, ret: Ret) -> bool:
        return isinstance(ret, Right)

    def _consumed(self, key: Any, ret: Ret) -> int:
        """Calculate how much input was consumed; -1 if not measurable.
        Expects Right((value, next_state)) where states have 'index'."""
        try:
            if isinstance(ret, Right):
                value, state = ret.value  # type: ignore
                if hasattr(key, 'index') and hasattr(state, 'index'):
                    return int(getattr(state, 'index')) - int(getattr(key, 'index'))
        except Exception:
            return -1
        return -1

    def _improved(self, key: Any, old: Optional[Ret], new: Ret) -> bool:
        if not self._is_success(new):
            return False
        if old is None or not self._is_success(old):
            return True
        return self._consumed(key, new) > self._consumed(key, old)

    def gen(self,
            f: Callable[[A, 'Cache[A, Ret]'], Generator[Any, Any, Ret]],
            key: A) -> Generator[Any, Any, Ret]:
        if f not in self.cache:
            self.cache.setdefault(f, dict())
        c: Dict[A, Ret | InProgress | LeftRecHead[A, Ret]] = self.cache[f]  # type: ignore

        entry = c.get(key, None)
        # Case: already have a final value
        if entry is not None and not isinstance(entry, (InProgress, LeftRecHead)):
            return entry  # type: ignore

        # Case: left recursion detected (re-enter rule with same key while in-progress)
        if isinstance(entry, InProgress):
            head = LeftRecHead(f=f, key=key)
            c[key] = head  # promote to head
            # Seed returns a failure-like value; the caller will proceed.
            # We return Left(key) to allow backtracking, consistent with error semantics.
            return Left(key)  # type: ignore

        # Case: during growth phase, return current best result
        if isinstance(entry, LeftRecHead):
            if entry.result is not None:
                return entry.result  # type: ignore
            else:
                return Left(key)  # type: ignore

        # Normal initial invocation: mark InProgress and compute seed
        c[key] = InProgress()
        try:
            seed = yield from f(key, self)
        except Exception as e:
            c.pop(key, None)
            raise e

        # If no left recursion happened, finalize
        if not isinstance(c.get(key), LeftRecHead):
            c[key] = seed
            return seed

        # We have a head created earlier; perform growth iterations
        head = cast(LeftRecHead[A, Ret], c[key])  # type: ignore
        head.result = seed
        improved_once = False
        while True:
            attempt = yield from f(key, self)
            if self._improved(key, head.result, attempt):
                head.result = attempt
                improved_once = True
                continue
            break

        if not improved_once and not self._is_success(head.result):
            # No progress and not successful: mimic original behavior
            raise LeftRecursionError("Left recursion without progress", offender=f, expect="progress")

        c[key] = head.result  # store final best result
        return head.result  # type: ignore
        



