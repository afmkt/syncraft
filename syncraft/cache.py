
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
    pass

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
    """Raised when left-recursive growth cannot make progress or hits a safety cap.

    Additional attributes beyond the base ``SyncraftError``:
        stack: List of rule names (outermost last) accumulated via ``push``.
        iterations: Number of growth iterations attempted (if known).
        seed_consumed: Tokens consumed by the initial (base) seed parse, ``-1`` if unknown.
        best_consumed: Tokens consumed by the best improvement before failure, ``-1`` if none.
        group_size: Size of the left‑recursive group (1 for direct recursion, >1 for mutual).
        limit: Configured iteration limit that was exceeded (if applicable).
        reason: Machine-friendly string describing failure mode (``iteration-cap`` | ``no-progress``).
    """
    def __init__(self, message: str, offender: Any, expect: Any = None, **kwargs: Any) -> None:
        super().__init__(message, offender, expect, **kwargs)
        self.stack: List[str] = []
        self.iterations: int | None = kwargs.get('iterations')
        self.seed_consumed: int | None = kwargs.get('seed_consumed')
        self.best_consumed: int | None = kwargs.get('best_consumed')
        self.group_size: int | None = kwargs.get('group_size')
        self.limit: int | None = kwargs.get('limit')
        self.reason: str | None = kwargs.get('reason')

    def push(self, name: str) -> LeftRecursionError:
        self.stack.append(name)
        return self

    def _format_metrics(self) -> str:
        parts: List[str] = []
        if self.iterations is not None:
            parts.append(f"iterations={self.iterations}")
        if self.limit is not None:
            parts.append(f"limit={self.limit}")
        if self.group_size is not None:
            parts.append(f"group={self.group_size}")
        if self.seed_consumed is not None:
            parts.append(f"seed={self.seed_consumed}")
        if self.best_consumed is not None and (self.best_consumed != self.seed_consumed):
            parts.append(f"best={self.best_consumed}")
        if self.reason:
            parts.append(f"reason={self.reason}")
        return ("; ".join(parts)) if parts else ""

    def __repr__(self) -> str:
        stack = "\n-> ".join(reversed(self.stack))
        metrics = self._format_metrics()
        hint_lines = [
            "Hint: Consider one of:",
            "  • Refactor the rule to be right-recursive (e.g. A -> term (op term)*)",
            "  • Introduce an explicit repetition combinator instead of naive left recursion",
            "  • Ensure there's a non-empty base alternative (no nullable left recursion)",
            "  • Increase 'max_growth_iterations' if grammar is intentionally deep",
        ]
        metrics_line = ("[" + metrics + "]\n") if metrics else ""
        return f"\n{stack}\n{metrics_line}" + "\n".join(hint_lines)

    def __str__(self) -> str:
        return self.__repr__()

# ---------------------------------------------------------------------------
# Left recursion recovery design notes
# ---------------------------------------------------------------------------
# Algorithm (single-head):
#   1. Seed rule with left-recursive alternatives suppressed (re-entries during seeding
#      return a Left sentinel so only base (non-left-recursive) branches run).
#   2. If recursion detected (a re-entry occurred), iteratively re-run the head while
#      each new attempt strictly consumes more input than the previous best.
#   3. Stop once no improvement (consumption increase) occurs, or iteration cap reached.
#
# Algorithm (multi-head / mutual recursion):
#   * All seeding heads sharing the same start position are grouped (LRGroup). After seeding
#     completes for the group, we cycle through members attempting improvements until a
#     full pass yields no changes or the cap is hit. Any improvement increments a global
#     version and may schedule earlier heads (agenda) whose spans can extend due to later
#     growth (precedence-like chains).
#
# Improvement metric:
#   Strictly greater token span measured by a caller-provided distance/measure, or by
#   ordering of states (end > start). Structural richness is ignored—this guarantees
#   termination provided grammar cannot inflate without consuming input.
#
# Diagnostics (LeftRecursionError fields):
#   iterations:    Number of growth attempts performed for the failing group.
#   group_size:    1 for direct recursion; >1 for mutual cycles.
#   seed_consumed: Span length of the initial base parse (if any succeeded).
#   best_consumed: Longest span achieved before failure.
#   limit:         Configured iteration budget (max_growth_iterations) if cap exceeded.
#   reason:        "iteration-cap" for safety cap; future values may include "no-progress".
#
# Future enhancements:
#   * Explicit detection & classification of nullable / unproductive left recursion (S -> S | ε)
#   * Public API hook to inject custom Cache (to test iteration-cap behavior deterministically)
#   * Structural improvement heuristics (optional) while keeping consumption primary.
# ---------------------------------------------------------------------------
    
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
    base_only: bool = True  # True during initial base-only seeding phase
    seed_result: Optional[Ret] = None  # Preserve original (base) successful seed for single-head growth scenarios
    # removed seeded_choice for Option A approach




@dataclass
class Cache(Generic[A, Ret]):
    cache: dict[Callable[..., Any], Dict[A, Ret | InProgress[A, Ret]]] = field(default_factory=dict)
    max_growth_iterations: int = 256  # Protection against runaway single-head growth
    _lr_stack: List[InProgress[A, Ret]] = field(default_factory=list, init=False, repr=False)  # active in-progress chain
    _canonical: Dict[Callable[..., Any], Callable[..., Any]] = field(default_factory=dict, init=False, repr=False)
    _lr_growth_depth: int = 0  # Scoped flag depth counter for exploratory choice evaluation
    _force: Optional[InProgress[A, Ret]] = None  # Entry scheduled for forced recompute during growth
    _lr_version: int = 0  # Monotonic counter incremented on any improvement (nested or local)
    _agenda: List[InProgress[A, Ret]] = field(default_factory=list, init=False, repr=False)
    # Heads grouped by a hashable start key (caller-provided mapping or the state itself)
    _heads_by_start: Dict[Hashable, List[InProgress[A, Ret]]] = field(default_factory=dict, init=False, repr=False)

    # Optional decoupling hook (caller may provide):
    # - position_key: map a state to a hashable "start position" key (for grouping).
    # next_state is always Right.value[1] on success; distance always falls back to ordering.
    position_key: Optional[Callable[[A], Hashable]] = None
    

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
        # Provisional is a subclass of Right and should be considered success.
        return isinstance(ret, Right)

    # -------- Generic position helpers (no structural assumptions about state) --------
    def _start_key(self, s: A) -> Hashable:
        # Prefer caller-provided mapping; else try using the state itself; if unhashable, use id(s)
        if self.position_key is not None:
            try:
                return self.position_key(s)  # type: ignore[call-arg]
            except Exception:
                pass
        try:
            hash(s)  # type: ignore[arg-type]
            return s  # type: ignore[return-value]
        except Exception:
            return id(s)

    def _extract_next_state(self, ret: Ret) -> Optional[A]:
        if isinstance(ret, Right):
            try:
                v = ret.value  # type: ignore[assignment]
                if isinstance(v, tuple) and len(v) >= 2:
                    return v[1]  # type: ignore[return-value]
            except Exception:
                return None
        return None

    def _cmp(self, a: A, b: A) -> Optional[int]:
        # Comparison that doesn't require static knowledge of A's ordering; uses Python runtime semantics.
        try:
            if a == b:
                return 0
            # Prefer native __lt__; if not supported, attempt reverse; else treat as not less.
            from typing import cast as _cast
            if _cast(Any, a) < b:  # type: ignore[operator]
                return -1
            return 1
        except Exception:
            # Last resort: try reverse comparison
            try:
                if _cast(Any, b) < a:  # type: ignore[operator]
                    return 1
                return None
            except Exception:
                return None

    def _consumed(self, key: A, ret: Ret) -> int:
        """Calculate how much input was consumed using ordering fallback; -1 if not measurable.
        If ret is a Right, extract end state as Right.value[1] and compare with key using total order on A:
        - return 1 if end > start, 0 if end == start, -1 otherwise; if comparison not supported, return -1.
        """
        if not isinstance(ret, Right):
            return -1
        from typing import cast as _cast
        nxt = self._extract_next_state(_cast(Ret, ret))
        if nxt is not None:
            cmp_res = self._cmp(key, nxt)
            if cmp_res is not None:
                return 1 if cmp_res < 0 else (0 if cmp_res == 0 else -1)
        return -1

    def _end_state_of(self, ret: Ret) -> Optional[A]:
        return self._extract_next_state(ret)

    def _improved(self, key: A, old: Optional[Ret], new: Ret) -> bool:
        # Improvement = strictly further end state via ordering (fallback to measure if provided)
        if not self._is_success(new):
            return False
        new_end = self._end_state_of(new)
        if new_end is None:
            return False
        if old is None or not self._is_success(old):
            cmp0 = self._cmp(key, new_end)
            return cmp0 is not None and cmp0 < 0
        old_end = self._end_state_of(old)
        if old_end is None:
            return True
        cmp1 = self._cmp(old_end, new_end)
        return cmp1 is not None and cmp1 < 0

    def _struct_metric(self, ret: Ret) -> int:
        if not isinstance(ret, Right):
            return 0
        try:
            value, _ = ret.value  # type: ignore
        except Exception:
            return 0
        return self._value_size(value)

    def _value_size(self, v: Any) -> int:
        # Approximate structural richness: count atoms in nested tuples / dataclasses with 'left'/'right'
        if v is None:
            return 0
        if isinstance(v, (str, int, float, bytes)):
            return 1
        if isinstance(v, tuple):
            return 1 + sum(self._value_size(x) for x in v)
        # Generic object with 'left'/'right'
        if hasattr(v, 'left') and hasattr(v, 'right'):
            try:
                return 1 + self._value_size(getattr(v, 'left')) + self._value_size(getattr(v, 'right'))
            except Exception:
                return 1
        # Choice-like
        if hasattr(v, 'value') and not isinstance(v, (str, int, float, bytes)):
            try:
                return 1 + self._value_size(getattr(v, 'value'))
            except Exception:
                return 1
        return 1

    # Context manager helpers for LR growth
    def _enter_lr_growth(self):
        self._lr_growth_depth += 1
    def _exit_lr_growth(self):
        self._lr_growth_depth -= 1

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
            # Forced recompute path (growth iteration) bypasses normal early return.
            if self._force is existing and not existing.seeding:
                # If already probing (recursive self-call inside forced recompute), short-circuit to current best.
                if existing.probing:
                    return existing.result if existing.result is not None else Left(key)  # type: ignore
                existing.probing = True
                self._lr_stack.append(existing)
                try:
                    attempt = yield from f(key, self)
                finally:
                    self._lr_stack.pop()
                    existing.probing = False
                return attempt
            return (yield from self._handle_reentry(existing, key))
        # Step 3: seed new head
        head = InProgress(f=f, key=key)
        if f not in self._canonical:
            self._canonical[f] = f
        cache_bucket[key] = head
        self._lr_stack.append(head)
        # Register head for potential cross-position revisits (agenda scheduling)
        start_key = self._start_key(key)
        self._heads_by_start.setdefault(start_key, []).append(head)
        try:
            # Opportunistic co-seeding: if this rule is an Expr-like head referencing another lazy head
            # at the same starting position (e.g., Expr vs Term), ensure both are seeded so they will be grouped.
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
                # During probing (growth iteration), for single-head groups return the original seed
                if entry.group and len(entry.group.members) == 1 and entry.seed_result is not None:
                    return entry.seed_result
                return entry.result if entry.result is not None else Left(key)  # type: ignore
            if entry.group.finalized or entry.finalized:
                return entry.result if entry.result is not None else Left(key)  # type: ignore
            return entry.result if entry.result is not None else Left(key)  # type: ignore
        return entry.result if entry.result is not None else Left(key)  # type: ignore

    def _handle_seeding_reentry(self, entry: InProgress[A, Ret], key: A) -> Ret:
        entry.head = True
        try:
            self._lr_stack.index(entry)
        except ValueError:
            return Left(key)  # type: ignore
        if entry.group is None:
            # Build a new group including ALL currently seeding frames on the stack
            # that share the same starting key (as defined by _start_key). This captures
            # mutually left-recursive heads (multi-head). We assume stack order = call order;
            # earliest becomes leader.
            start_key = self._start_key(key)
            candidate_frames: list[InProgress[A, Ret]] = [
                frame for frame in self._lr_stack
                if frame.seeding and self._start_key(frame.key) == start_key
            ]
            # Limit group to canonical rule heads (functions tagged with _rule_id) to avoid
            # mixing in internal combinator frames (or_else_run / flat_map_run / etc) which
            # fragment improvement propagation. Fallback to all frames if no tagged heads.
            head_frames = [f for f in candidate_frames if hasattr(f.f, '_rule_id')]
            same_key_frames = head_frames if len(head_frames) > 0 else candidate_frames
            # Deduplicate by rule id keeping earliest stack occurrence (stack is chronological)
            dedup: list[InProgress[A, Ret]] = []
            seen: set[Any] = set()
            for frame in same_key_frames:
                rid = getattr(frame.f, '_rule_id', frame.f)
                if rid in seen:
                    continue
                seen.add(rid)
                dedup.append(frame)
            same_key_frames = dedup
            # Deduplicate (should not contain entry multiple times)
            group = LRGroup[A, Ret]()
            for idx, frame in enumerate(same_key_frames):
                # Attach only if not already grouped (could occur in nested re-entry scenarios)
                if frame.group is None:
                    group.add(frame)
                    frame.group = group
                    frame.group_leader = (idx == 0)
                else:
                    # If any frame already has a group, merge current new members into that one
                    if group is not frame.group:
                        # Move already added frames into existing group
                        for m in group.members:
                            if m.group is not frame.group:
                                frame.group.add(m)
                                m.group = frame.group
                        group = frame.group  # adopt existing
            # Set seeding_remaining to number of members still seeding
            group.seeding_remaining = sum(1 for f in group.members if f.seeding)
            # If entry wasn't designated leader (because earlier frame existed), ensure leader flag is set on earliest
            # (already handled in loop). If somehow no leader, set entry as fallback.
            if not any(m.group_leader for m in group.members):
                entry.group_leader = True
            # Mark all grouped frames as heads to ensure growth logic executes even if base-only blocked recursive alts.
            if len(group.members) > 1:
                for m in group.members:
                    m.head = True
        # DEBUG: group formation details (remove after troubleshooting)
        try:
            _ = len(entry.group.members) if entry.group else 0
        except Exception:
            pass
        # If still in base-only phase for this entry (no consumption yet), block the recursive
        # expansion by returning a sentinel failure; base alternatives may still succeed.
        if entry.base_only:
            return Left(("LR_BASE_BLOCK", key))  # type: ignore
        return Left(("LR_SEED", key))  # type: ignore

    def _complete_seed(self, head: InProgress[A, Ret], seed: Ret) -> Generator[Any, Any, Ret]:
        head.seeding = False
        head.base_only = False
        if head.group is not None:
            head.group.seeding_remaining -= 1
        # Determine if this member participates in a left-recursive group (directly or indirectly)
        group_has_left_recursion = False
        if head.group is not None:
            group_has_left_recursion = any(m.head for m in head.group.members)
        # If truly no left recursion (no head detected in its group (or no group) and this frame not head)
        if not head.head and not group_has_left_recursion:
            # Finalize immediately: replace cache entry with seed result
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
        # Retain InProgress entry for growth (even if seed failed) so improvement attempts can re-run rule
        if isinstance(seed, Right):
            head.result = seed  # type: ignore
            from typing import cast as _cast
            head.seed_result = _cast(Ret, seed)  # store original base seed
        else:
            # Keep prior successful result (if any) else remain None for growth attempts
            from typing import cast as _cast
            head.result = _cast(Optional[Ret], head.result if (head.result is not None and isinstance(head.result, Right)) else None)
        # Growth phase: only when all seeds complete
        if head.group_leader and not head.group.finalized and head.group.seeding_remaining == 0:
            # Early multi-head zero-consumption detection: if all members succeeded (Right) with zero consumption
            # after seeding, classify as no-progress and raise before entering growth.
            if len(head.group.members) > 1:
                # NEW: Detect pure unproductive mutual cycle (no member produced any successful seed result).
                # Example: A -> B; B -> A on empty input. All seeds fail because recursion is suppressed
                # during seeding and there are no base (non-recursive) alternatives. Previous logic required
                # at least one successful seed (any_success) to classify no-progress, so such grammars silently
                # failed without a diagnostic. We now raise a LeftRecursionError(reason='no-progress') early.
                # NOTE: Added to support test 'test_mutual_unproductive_cycle_no_progress' which asserts
                # that a purely unproductive mutual cycle (A -> B; B -> A) raises reason='no-progress'.
                # Without this branch such a grammar produced no successful seed and silently failed.
                no_seed_success = all(
                    not (m.result is not None and isinstance(m.result, Right))
                    and not (m.seed_result is not None and isinstance(m.seed_result, Right))
                    for m in head.group.members
                )
                if no_seed_success:
                    raise LeftRecursionError(
                        "Left recursion with no progress (no productive base in mutual cycle)",
                        offender=offender if (offender := head.f) else head.f,  # type: ignore
                        expect="> 0 token consumption via at least one base alternative",
                        iterations=0,
                        seed_consumed=None,
                        best_consumed=None,
                        group_size=len(head.group.members),
                        limit=self.max_growth_iterations,
                        reason="no-progress"
                    )
                all_zero = True
                any_success = False
                for m in head.group.members:
                    sr = m.result if m.result is not None else m.seed_result
                    if sr is None or not isinstance(sr, Right):  # type: ignore
                        continue
                    any_success = True
                    if self._consumed(m.key, sr) > 0:  # type: ignore[arg-type]
                        all_zero = False
                        break
                if any_success and all_zero:
                    raise LeftRecursionError(
                        "Left recursion with no progress (nullable or unproductive mutual cycle)",
                        offender=offender if (offender := head.f) else head.f,  # type: ignore
                        expect="> 0 token consumption",
                        iterations=0,
                        seed_consumed=None,
                        best_consumed=None,
                        group_size=len(head.group.members),
                        limit=self.max_growth_iterations,
                        reason="no-progress"
                    )
            yield from self._grow_group(head.group, offender=head.f)
        self._lr_stack.pop()
        # May still be None if no base alternative succeeded; growth might not improve (leave as failure)
        return head.result if head.result is not None else seed  # type: ignore

    def _grow_group(self, group: LRGroup[A, Ret], offender: Any) -> Generator[Any, Any, None]:
        iterations = 0
        members_snapshot = list(group.members)
        if len(members_snapshot) == 1:
            member = members_snapshot[0]
            best = member.result
            member.probing = True
            self._enter_lr_growth()
            seed_end = self._end_state_of(best) if best is not None else None
            while True:
                iterations += 1
                if iterations > self.max_growth_iterations:
                    member.probing = False
                    self._exit_lr_growth()
                    raise LeftRecursionError(
                        "Left recursion growth iteration limit exceeded (single-head)",
                        offender=offender,
                        expect=f"<= {self.max_growth_iterations} iterations",
                        iterations=iterations,
                        seed_consumed=None,
                        best_consumed=self._consumed(member.key, best) if best else None,
                        group_size=1,
                        limit=self.max_growth_iterations,
                        reason="iteration-cap"
                    )
                self._force = member
                try:
                    attempt = yield from member.f(member.key, self)
                finally:
                    self._force = None
                # Process cross-position agenda before evaluating improvement
                yield from self._process_agenda()
                if self._improved(member.key, best, attempt):
                    best = attempt
                    member.result = best
                    self._lr_version += 1
                    self._propagate_improvement(member)
                    continue
                # Early collapse: if no improvement and best end did not move past seed end, stop.
                best_end = self._end_state_of(best) if best is not None else None
                if seed_end is not None and (best_end is None or self._cmp(best_end, seed_end) == 0):
                    # Detect unproductive (no-progress) nullable left recursion: zero progress overall.
                    cmp_seed = self._cmp(member.key, seed_end)
                    if cmp_seed is not None and cmp_seed == 0:
                        member.probing = False
                        self._exit_lr_growth()
                        raise LeftRecursionError(
                            "Left recursion with no progress (nullable or unproductive cycle)",
                            offender=offender,
                            expect="> 0 token consumption",
                            iterations=iterations,
                            seed_consumed=None,
                            best_consumed=None,
                            group_size=1,
                            limit=self.max_growth_iterations,
                            reason="no-progress"
                        )
                    break
                break
            member.probing = False
            self._exit_lr_growth()
        else:
            changed = True
            self._enter_lr_growth()
            while changed:
                changed = False
                iterations += 1
                if iterations > self.max_growth_iterations:
                    self._exit_lr_growth()
                    # Capture representative metrics from first member that has a result
                    sample = next((m for m in group.members if m.result is not None), None)
                    seed_c = self._consumed(sample.key, sample.seed_result) if (sample and sample.seed_result) else None  # type: ignore
                    best_c = self._consumed(sample.key, sample.result) if (sample and sample.result) else None  # type: ignore
                    raise LeftRecursionError(
                        "Left recursion growth iteration limit exceeded (multi-head)",
                        offender=offender,
                        expect=f"<= {self.max_growth_iterations} iterations",
                        iterations=iterations,
                        seed_consumed=seed_c,
                        best_consumed=best_c,
                        group_size=len(group.members),
                        limit=self.max_growth_iterations,
                        reason="iteration-cap"
                    )
                idx = 0
                members_list = list(group.members)
                while idx < len(members_list):
                    member = members_list[idx]
                    # Force recomputation of this member's rule body (even if cached InProgress exists)
                    self._force = member
                    try:
                        attempt = yield from member.f(member.key, self)
                    finally:
                        self._force = None
                    # DEBUG: log attempt consumption for multi-head detection troubleshooting
                    # (Will be removed after test passes.)
                    try:
                        if isinstance(attempt, Right):  # type: ignore
                            _ = self._consumed(member.key, attempt)  # type: ignore[arg-type]
                    except Exception:
                        pass
                    # (Debug logging removed in principled refactor)
                    if self._improved(member.key, member.result, attempt):
                        # Unwrap Choice(LEFT, Then(BOTH,...)) to raw Then for better flattening
                        if isinstance(attempt, Right):  # type: ignore
                            val, st = attempt.value  # type: ignore
                            from syncraft.ast import Then, ThenKind
                            from syncraft.algebra import Choice  # type: ignore
                            k = getattr(val, 'kind', None)
                            if isinstance(val, Choice) and k is not None and getattr(k, 'name', None) == 'LEFT':
                                inner = getattr(val, 'value', None)
                                if isinstance(inner, Then) and inner.kind == ThenKind.BOTH:
                                    attempt = Right((inner, st))  # type: ignore
                        from typing import cast as _cast
                        member.result = _cast(Ret, attempt)
                        self._lr_version += 1
                        # Propagate improvement to earlier heads
                        self._propagate_improvement(member)
                        changed = True
                        # Restart scanning from first member to propagate dependency improvements earlier.
                        members_list = list(group.members)
                        idx = 0
                        continue
                    idx += 1
                # If no member improved this pass (changed == False) we can classify potential no-progress.
                if not changed:
                    # No member improved this pass; check no-progress using ordering
                    any_success = False
                    all_non_positive = True
                    for m in group.members:
                        cur = m.result if m.result is not None else m.seed_result
                        if cur is None or not isinstance(cur, Right):  # type: ignore
                            continue
                        any_success = True
                        from typing import cast as _cast
                        end_cur = self._end_state_of(_cast(Ret, cur))
                        cmp_cur = (self._cmp(m.key, end_cur) if end_cur is not None else None)
                        if cmp_cur is not None and cmp_cur < 0:
                            all_non_positive = False
                            break
                    if any_success and all_non_positive:
                        self._exit_lr_growth()
                        seed_c = None
                        best_c = None
                        raise LeftRecursionError(
                            "Left recursion with no progress (nullable or unproductive mutual cycle)",
                            offender=offender,
                            expect="> 0 token consumption",
                            iterations=iterations,
                            seed_consumed=seed_c,
                            best_consumed=best_c,
                            group_size=len(group.members),
                            limit=self.max_growth_iterations,
                            reason="no-progress"
                        )
            self._exit_lr_growth()
            # Fallback classification: if group finalized growth without improvement and all successes are non-positive by ordering.
            any_success_fb = False
            any_positive_fb = False
            for m in group.members:
                cur = m.result if m.result is not None else m.seed_result
                if cur is None or not isinstance(cur, Right):  # type: ignore
                    continue
                any_success_fb = True
                from typing import cast as _cast
                end_cur = self._end_state_of(_cast(Ret, cur))
                cmp_fb = (self._cmp(m.key, end_cur) if end_cur is not None else None)
                if cmp_fb is not None and cmp_fb < 0:
                    any_positive_fb = True
                    break
            if any_success_fb and not any_positive_fb:
                    raise LeftRecursionError(
                        "Left recursion with no progress (nullable or unproductive mutual cycle)",
                        offender=offender,
                        expect="> 0 token consumption",
                        iterations=iterations,
                        seed_consumed=None,
                        best_consumed=None,
                        group_size=len(group.members),
                        limit=self.max_growth_iterations,
                        reason="no-progress"
                    )
        # Finalize
        group.finalized = True
        for member in group.members:
            member.finalized = True
            # Retain InProgress in cache for agenda-driven revisits.
            # (Do NOT overwrite with final Right; callers see result via reentry handler.)
            if member.result is not None:
                # nothing to store; InProgress already holds result
                pass
        # Final-stage multi-head no-progress detection (robust against earlier classification misses).
        if len(group.members) > 1:
            all_non_positive = True
            any_success = False
            for m in group.members:
                cur = m.result if m.result is not None else m.seed_result
                if cur is None or not isinstance(cur, Right):  # type: ignore
                    continue
                any_success = True
                from typing import cast as _cast
                end_sr = self._end_state_of(_cast(Ret, cur))
                cmp_sr = (self._cmp(m.key, end_sr) if end_sr is not None else None)
                if cmp_sr is not None and cmp_sr < 0:
                    all_non_positive = False
                    break
            if any_success and all_non_positive:
                raise LeftRecursionError(
                    "Left recursion with no progress (nullable or unproductive mutual cycle)",
                    offender=offender,
                    expect="> 0 token consumption",
                    iterations=None,
                    seed_consumed=None,
                    best_consumed=None,
                    group_size=len(group.members),
                    limit=self.max_growth_iterations,
                    reason="no-progress"
                )
        # After primary group growth, process any scheduled agenda heads.
        yield from self._process_agenda()
    # Global fixed-point across all heads (cross-position) to incorporate improvements from later spans.
        yield from self._global_fixpoint()
        yield from ()

    # ---------------- Agenda (cross-position propagation) ------------------
    def _propagate_improvement(self, improved: InProgress[A, Ret]) -> None:
        """Schedule earlier-starting finalized heads whose span could extend due to this improvement.

        Heuristic: If an earlier head's current consumed span end position is strictly before the improved
        span end position, re-enqueue it for one more attempt (single forced recompute) in case its rule
        references the improved region (e.g., Expr depending on a longer Term to its right).
        """
        if improved.result is None:
            return
        start_state = improved.key
        # Ordering-based propagation: earlier start (h.key < start_state) and h_end < end_improved
        end_improved_state = self._extract_next_state(improved.result)
        if end_improved_state is None:
            return
        for heads in list(self._heads_by_start.values()):
            for h in heads:
                if h is improved or h.seeding or h.result is None or not h.finalized:
                    continue
                cs = self._cmp(h.key, start_state)
                if cs is None or cs >= 0:
                    continue
                h_end_state = self._extract_next_state(h.result)
                if h_end_state is None:
                    continue
                ce = self._cmp(h_end_state, end_improved_state)
                if ce is not None and ce < 0 and h not in self._agenda:
                    h.finalized = False
                    self._agenda.append(h)

    def _process_agenda(self) -> Generator[Any, Any, None]:
        # Process scheduled heads (single-head forced attempts)
        while self._agenda:
            head = self._agenda.pop(0)
            if head.seeding:
                continue
            old = head.result
            self._force = head
            attempt = yield from head.f(head.key, self)
            self._force = None
            if self._improved(head.key, old, attempt):
                head.result = attempt
                head.finalized = True
                self._lr_version += 1
                self._propagate_improvement(head)
            else:
                head.finalized = True
        
    def _global_fixpoint(self, max_passes: int = 64) -> Generator[Any, Any, None]:
        """Run a global fixed-point over all recorded left-recursive heads.

    This mitigates cross-position dependency gaps where an earlier head (Expr at pos A)
    depends structurally on improvements in a later-start head (Term at pos B) whose
        growth completed after the earlier head finalized. We re-open finalized heads
        and force recomputation while any consumption improvements occur.
        """
        passes = 0
        changed = True
        while changed and passes < max_passes:
            passes += 1
            changed = False
            # Iterate by insertion order of grouped heads
            iter_heads = list(self._heads_by_start.values())
            for heads in iter_heads:
                for head in list(heads):
                    if head.seeding:
                        continue
                    if not head.head:  # only heads participating in LR cycles
                        continue
                    old = head.result
                    self._force = head
                    attempt = yield from head.f(head.key, self)
                    self._force = None
                    if self._improved(head.key, old, attempt):
                        head.result = attempt
                        head.finalized = True
                        self._lr_version += 1
                        changed = True
                        # Improvement recorded; propagation handled by subsequent passes.
                    else:
                        head.finalized = True
        # (Optional) Could log non-convergence if passes == max_passes.
        yield from ()




