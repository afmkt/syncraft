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
class LRGroup(Generic[A, Ret]):
    """Represents a mutually (indirect) left-recursive group of rule invocations at one input key.

    All members share the same starting key (position). After seeding all members, we perform
    a fixed-point growth pass: iteratively attempt each member; if any improves (consumes more
    input), we repeat until no member improves.

    Attributes:
        members: InProgress entries participating in the cycle.
        seeding_remaining: Countdown of how many members still in seeding phase.
        finalized: Whether fixed-point growth has already been performed.
    """
    members: List["InProgress[A, Ret]"] = field(default_factory=list)
    seeding_remaining: int = 0
    finalized: bool = False

    def add(self, ip: "InProgress[A, Ret]") -> None:
        self.members.append(ip)

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
    group: Optional[LRGroup[A, Ret]] = None  # Multi-head group reference (if indirect cycle)
    group_leader: bool = False  # True for first detected member in a cycle slice
    finalized: bool = False  # Unified path: marks that growth completed (group may also mark finalized)
    probing: bool = False  # True during growth iteration attempts
    # removed seeded_choice for Option A approach




@dataclass
class Cache(Generic[A, Ret]):
    cache: dict[Callable[..., Any], Dict[A, Ret | InProgress[A, Ret]]] = field(default_factory=dict)
    max_growth_iterations: int = 256  # Protection against runaway single-head growth
    _lr_stack: List[InProgress[A, Ret]] = field(default_factory=list, init=False, repr=False)  # active in-progress chain
    _canonical: Dict[Callable[..., Any], Callable[..., Any]] = field(default_factory=dict, init=False, repr=False)
    # _best removed (Option A does not need cross-wrapper substitution)

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
        # Step 1: canonicalize function identity
        f = self._canonicalize(f)
        # Step 2: fetch or initialize entry
        cache_bucket = self.cache.setdefault(f, {})
        existing = cache_bucket.get(key)
        if existing is not None and not isinstance(existing, InProgress):
            return existing
        if isinstance(existing, InProgress):
            return (yield from self._handle_reentry(existing, key))
        # Step 3: seed new head
        head = InProgress(f=f, key=key)
        if f not in self._canonical:
            self._canonical[f] = f
        cache_bucket[key] = head
        self._lr_stack.append(head)
        try:
            seed = yield from f(key, self)
        except Exception as e:
            cache_bucket.pop(key, None)
            self._lr_stack.pop()
            raise e
        # Step 4: finalize or prepare for growth
        return (yield from self._complete_seed(head, seed))

    # --------------------- Helper Methods (Refactor) ---------------------
    def _canonicalize(self, f: Callable[[A, Cache[A, Ret]], Generator[Any, Any, Ret]]):
        rule_id = getattr(f, '_rule_id', None)
        if rule_id is not None:
            for existing_f, rep in self._canonical.items():
                if getattr(existing_f, '_rule_id', None) is rule_id:
                    return rep
            self._canonical[f] = f
        return f

    def _handle_reentry(self, entry: InProgress[A, Ret], key: A) -> Generator[Any, Any, Ret]:
        # Make this a generator-friendly helper (even if we don't currently yield diagnostic info)
        yield from ()
        if entry.seeding:
            return self._handle_seeding_reentry(entry, key)
        # Post-seeding
        if entry.group is not None:
            if entry.probing:
                return entry.result if entry.result is not None else Left(key)  # type: ignore
            if entry.group.finalized or entry.finalized:
                assert entry.result is not None
                return entry.result
            return entry.result if entry.result is not None else Left(key)  # type: ignore
        return entry.result if entry.result is not None else Left(key)  # type: ignore

    def _handle_seeding_reentry(self, entry: InProgress[A, Ret], key: A) -> Ret:
        entry.head = True
        try:
            self._lr_stack.index(entry)
        except ValueError:
            return Left(key)  # type: ignore
        if entry.group is None:
            # Attempt to detect existing compatible groups on the stack (same key) to merge into.
            # For now, linear scan from top (closest) downward until different key encountered.
            merged = False
            for other in reversed(self._lr_stack):
                if other is entry:
                    continue
                if other.key != key:
                    continue
                if other.group is not None:
                    # Reuse other's group
                    other.group.add(entry)
                    entry.group = other.group
                    merged = True
                    break
            if not merged:
                group = LRGroup[A, Ret]()
                group.add(entry)
                group.seeding_remaining = 1
                entry.group = group
                entry.group_leader = True
        return Left(("LR_SEED", key))  # type: ignore

    def _complete_seed(self, head: InProgress[A, Ret], seed: Ret) -> Generator[Any, Any, Ret]:
        head.seeding = False
        if head.group is not None:
            head.group.seeding_remaining -= 1
        # No left recursion observed
        if not head.head:
            self.cache[head.f][head.key] = seed
            self._lr_stack.pop()
            return seed
        # Ensure group exists
        if head.group is None:
            group = LRGroup[A, Ret]()
            head.group = group
            head.group_leader = True
            group.add(head)
            group.seeding_remaining = 0
        head.result = seed
        # Growth phase (single-head now; multi-head hook later)
        if head.group_leader and not head.group.finalized:
            yield from self._grow_group(head.group, offender=head.f)
        self._lr_stack.pop()
        assert head.result is not None
        return head.result  # type: ignore

    def _grow_group(self, group: LRGroup[A, Ret], offender: Any) -> Generator[Any, Any, None]:
        iterations = 0
        members_snapshot = list(group.members)
        if len(members_snapshot) == 1:
            member = members_snapshot[0]
            best = member.result
            member.probing = True
            while True:
                iterations += 1
                if iterations > self.max_growth_iterations:
                    member.probing = False
                    raise LeftRecursionError(
                        "Left recursion growth iteration limit exceeded (single-head)",
                        offender=offender,
                        expect=f"<= {self.max_growth_iterations} iterations"
                    )
                attempt = yield from member.f(member.key, self)
                if self._improved(member.key, best, attempt):
                    best = attempt
                    member.result = best
                    continue
                else:
                    break
            member.probing = False
        else:
            changed = True
            while changed:
                changed = False
                iterations += 1
                if iterations > self.max_growth_iterations:
                    raise LeftRecursionError(
                        "Left recursion growth iteration limit exceeded (multi-head)",
                        offender=offender,
                        expect=f"<= {self.max_growth_iterations} iterations"
                    )
                for member in list(group.members):
                    attempt = yield from member.f(member.key, self)
                    if self._improved(member.key, member.result, attempt):
                        member.result = attempt
                        changed = True
        # Finalize
        group.finalized = True
        finalized_members = [m for m in group.members if m.result is not None]
        group.members = finalized_members
        for member in finalized_members:
            member.finalized = True
            assert member.result is not None
            self.cache[member.f][member.key] = member.result
        yield from ()
        



