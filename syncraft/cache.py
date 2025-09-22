from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, TypeVar, Hashable, Generic, Callable, Any, Generator, List, Optional, Tuple
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError
from syncraft.utils import callable_str, TablePrinter

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




@dataclass
class InProgress(Generic[A, Ret]):
    """Represents (and now replaces) all intermediate left-recursion states.

    This single structure subsumes the previous two-state approach that used a
    dedicated `InProgress` sentinel plus a separate `InProgress` instance.

    Lifecycle / flags:
      1. Initial call stores a InProgress with `seeding=True`, `head=False`.
         (Previously: an `InProgress` marker.)
      2. A recursive re-entry while `seeding` flips `head=True` and returns a
         failure-like `Left` to allow the seed to finish. (Previously: promote
         from `InProgress` to `InProgress`.)
      3. After the seed completes (`seeding` set False):
           - If `head` never became True, no left recursion occurred; we simply
             replace the cache entry with the final seed result.
           - If `head` is True, we enter the growth iterations, updating
             `result` when improvements are found (longer consumption).

    Attributes:
        f: Parsing function / rule.
        key: The input position key.
        result: Best successful result so far (None until seed done).
        growing: (Retained for potential diagnostics; not strictly required.)
        improved: Whether at least one growth iteration improved past the seed.
        seeding: True only during the very first (seed) evaluation.
        head: Becomes True if left recursion is detected (a re-entry during seed).
    """
    f: Callable[[A, "Cache[A, Ret]"], Generator[Any, Any, Ret]]
    key: A
    result: Optional[Ret] = None
    growing: bool = False
    improved: bool = False
    seeding: bool = True
    head: bool = False




@dataclass
class Cache(Generic[A, Ret]):
    cache: dict[Callable[..., Any], Dict[A, Ret | InProgress[A, Ret]]] = field(default_factory=dict)

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
            f: Callable[[A, Cache[A, Ret]], Generator[Any, Any, Ret]],
            key: A) -> Generator[Any, Any, Ret]:
        if f not in self.cache:
            self.cache.setdefault(f, dict())
        c: Dict[A, Ret | InProgress[A, Ret]] = self.cache[f]  

        entry = c.get(key, None)
        # Case: already have a final value
        if entry is not None and not isinstance(entry, InProgress):
            return entry  
        
        if isinstance(entry, InProgress):
            # Re-entry. If still seeding, mark as head and return failure-like Left.
            if entry.seeding:
                entry.head = True
                return Left(key)  # type: ignore
            # Growth phase: return current best (may be None prior to seed finalization, but in practice seed sets result first)
            if entry.result is not None:
                return entry.result  
            return Left(key)  # type: ignore  # fallback: Left works as failure sentinel

        # Initial invocation: create seeding head placeholder
        head = InProgress(f=f, key=key)
        c[key] = head
        try:
            seed = yield from f(key, self)
        except Exception as e:
            # Clean up on exception
            c.pop(key, None)
            raise e

        # Mark seeding done
        head.seeding = False

        # If no recursion occurred, finalize with seed result directly
        if not head.head:
            c[key] = seed
            return seed

        # Left recursion detected: perform growth iterations starting from seed
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

            raise LeftRecursionError("Left recursion without progress", offender=f, expect="progress")

        c[key] = head.result  # store final result
        return head.result  
        



