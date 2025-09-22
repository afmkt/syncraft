"""Left recursion recovery (principled variant)
================================================

Summary:
  Seed each left-recursive head with left-recursive alternatives blocked, group same-index
  heads, iteratively grow to a local fixed point (consumption-based improvement), and finally
  run a global fixpoint to propagate cross-index improvements (e.g. precedence chains).

Key points:
  - Improvement == strictly more input consumed.
  - Direct and indirect cycles share code via LRGroup.
  - Agenda + global fixpoint revisit earlier heads after later-span growth.
  - Safety caps: per-group iteration limit + global pass limit.
"""

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
    _heads_by_start: Dict[int, List[InProgress[A, Ret]]] = field(default_factory=dict, init=False, repr=False)
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
        # Provisional is a subclass of Right and should be considered success.
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
        # Only consider improvements that consume strictly more input.
        if not self._is_success(new):
            return False
        if old is None or not self._is_success(old):
            return True
        old_c = self._consumed(key, old)
        new_c = self._consumed(key, new)
        return new_c > old_c

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
        # Register head for potential cross-index revisits (agenda scheduling)
        start_index = getattr(key, 'index', None)
        if isinstance(start_index, int):
            self._heads_by_start.setdefault(start_index, []).append(head)
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
            # that share the same starting key. This captures mutually left-recursive
            # heads (multi-head). We assume stack order = call order; earliest becomes leader.
            start_index = getattr(key, 'index', None)
            candidate_frames: list[InProgress[A, Ret]] = [
                frame for frame in self._lr_stack
                if frame.seeding and getattr(frame.key, 'index', None) == start_index
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
            version_on_best = self._lr_version
            # Zero-progress heuristic state: counts consecutive iterations where
            # consumption did not increase and no nested version change occurred.
            same_consumption_runs = 0
            last_best_consumed = self._consumed(member.key, best) if best else -1
            seed_consumed = last_best_consumed
            # Collapse short-circuit: if seed consumed <= 1 token, and the first recursive
            # attempt fails to strictly extend span, we can finalize immediately. We probe once.
            if seed_consumed <= 1 and seed_consumed >= 0:
                self._force = member
                try:
                    probe = yield from member.f(member.key, self)
                finally:
                    self._force = None
                # Process any agenda side-effects (though unlikely here)
                yield from self._process_agenda()
                yield from self._global_fixpoint()
                if not self._improved(member.key, best, probe):
                    member.probing = False
                    self._exit_lr_growth()
                    group.finalized = True
                    member.finalized = True
                    return
            while True:
                iterations += 1
                # Track consecutive stagnation (no improvement, no nested version change, or regressions)
                if iterations == 1:
                    stagnation = 0
                    no_growth_cycles = 0  # counts iterations with no consumption improvement regardless of nested version bumps
                if iterations > self.max_growth_iterations:
                    member.probing = False
                    self._exit_lr_growth()
                    raise LeftRecursionError(
                        "Left recursion growth iteration limit exceeded (single-head)",
                        offender=offender,
                        expect=f"<= {self.max_growth_iterations} iterations"
                    )
                # Run attempt; if nested improvements happen during the run, immediately re-run to pick them up.
                nested_version_before = self._lr_version
                self._force = member
                try:
                    attempt = yield from member.f(member.key, self)
                finally:
                    self._force = None
                # Allow any newly created heads at later indices to grow before evaluating improvement
                yield from self._process_agenda()
                yield from self._global_fixpoint()
                while self._lr_version > nested_version_before:
                    nested_version_before = self._lr_version
                    self._force = member
                    try:
                        refreshed = yield from member.f(member.key, self)
                    finally:
                        self._force = None
                    yield from self._process_agenda()
                    yield from self._global_fixpoint()
                    # Prefer refreshed if it consumes more.
                    from typing import cast as _cast
                    old_for_check = _cast(Optional[Ret], attempt if isinstance(attempt, Right) else None)
                    if self._improved(member.key, old_for_check, refreshed):
                        attempt = refreshed
                if self._improved(member.key, best, attempt):
                    best = attempt
                    member.result = best
                    self._lr_version += 1
                    version_on_best = self._lr_version
                    # Cross-index propagation for single-head improvements
                    self._propagate_improvement(member)
                    stagnation = 0
                    # Reset zero-progress heuristic counters on genuine improvement
                    same_consumption_runs = 0
                    last_best_consumed = self._consumed(member.key, best)
                    no_growth_cycles = 0
                    continue
                else:
                    current_best_consumed_outer = self._consumed(member.key, best) if best else -1
                    # If no improvement and no nested version change occurred during attempt, stop.
                    if self._lr_version == version_on_best:
                        # Early collapse: if consumption never exceeded seed consumption
                        # and current best equals seed, additional iterations can't help.
                        current_best_consumed = self._consumed(member.key, best) if best else -1
                        if current_best_consumed == seed_consumed and seed_consumed >= 0:
                            break
                        stagnation += 1
                        # Zero-progress: if consumption has not increased since last best for 2 consecutive
                        # non-improving iterations, we finalize early. This captures collapse grammars like
                        # S -> S S | 'a' where only the base seed is useful and recursive expansions do not
                        # extend span length (due to a consuming both branches but collapsing structure).
                        current_best_consumed = self._consumed(member.key, best) if best else -1
                        if current_best_consumed == last_best_consumed and current_best_consumed >= 0:
                            same_consumption_runs += 1
                        else:
                            same_consumption_runs = 0
                            last_best_consumed = current_best_consumed
                        if same_consumption_runs >= 2:
                            break
                        if stagnation >= 8:
                            break
                        break
                    # Allow regressions (smaller consumption) to be skipped; they may trigger nested growth.
                    best_consumed = self._consumed(member.key, best) if best else -1
                    att_consumed = self._consumed(member.key, attempt)
                    if att_consumed < best_consumed:
                        stagnation += 1
                        if stagnation >= 8:
                            break
                        # Retry to allow nested groups (e.g., Term inside Expr) to finish growth.
                        continue
                    if self._lr_version > version_on_best:
                        # Even though nested versions changed, if our own consumption has not improved
                        # for several consecutive cycles, break to avoid unproductive looping (collapse grammar).
                        if current_best_consumed_outer == last_best_consumed and current_best_consumed_outer >= 0:
                            no_growth_cycles += 1
                        else:
                            no_growth_cycles = 0
                            last_best_consumed = current_best_consumed_outer
                        if no_growth_cycles >= 4:
                            break
                        stagnation = 0
                        continue
                    break
                # Fallback safeguard: if after several iterations we have *never* exceeded
                # the original seed consumption, further attempts cannot produce additional
                # span growth for purely collapsing recursive alternatives (e.g. S -> S S | 'a').
                if seed_consumed >= 0 and self._consumed(member.key, best) == seed_consumed and iterations >= 4:
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
                    raise LeftRecursionError(
                        "Left recursion growth iteration limit exceeded (multi-head)",
                        offender=offender,
                        expect=f"<= {self.max_growth_iterations} iterations"
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
            self._exit_lr_growth()
        # Finalize
        group.finalized = True
        for member in group.members:
            member.finalized = True
            # Retain InProgress in cache for agenda-driven revisits.
            # (Do NOT overwrite with final Right; callers see result via reentry handler.)
            if member.result is not None:
                # nothing to store; InProgress already holds result
                pass
        # After primary group growth, process any scheduled agenda heads.
        yield from self._process_agenda()
        # Global fixed-point across all heads (cross-index) to incorporate improvements from later spans.
        yield from self._global_fixpoint()
        yield from ()

    # ---------------- Agenda (cross-index propagation) ------------------
    def _propagate_improvement(self, improved: InProgress[A, Ret]) -> None:
        """Schedule earlier-starting finalized heads whose span could extend due to this improvement.

        Heuristic: If an earlier head's current consumed span end index is strictly before the improved
        span end index, re-enqueue it for one more attempt (single forced recompute) in case its rule
        references the improved region (e.g., Expr depending on a longer Term to its right).
        """
        if improved.result is None:
            return
        key = improved.key
        start = getattr(key, 'index', None)
        if not isinstance(start, int):
            return
        end_improved = start + self._consumed(key, improved.result)
        if end_improved <= start:
            return
        # Iterate earlier start indices
        for s_idx, heads in list(self._heads_by_start.items()):
            if s_idx >= start:
                continue
            for h in heads:
                if h is improved:
                    continue
                if h.seeding:
                    continue
                if h.result is None:
                    continue
                # Current end span for h
                h_end = s_idx + self._consumed(h.key, h.result)
                if h_end < end_improved and h.finalized and h not in self._agenda:
                    h.finalized = False  # reopen for revisit
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

        This mitigates cross-index dependency gaps where an earlier head (Expr at 0)
        depends structurally on improvements in a later-start head (Term at 2) whose
        growth completed after the earlier head finalized. We re-open finalized heads
        and force recomputation while any consumption improvements occur.
        """
        passes = 0
        changed = True
        while changed and passes < max_passes:
            passes += 1
            changed = False
            # Iterate start indices ascending for deterministic convergence
            for start_idx in sorted(self._heads_by_start.keys()):
                for head in list(self._heads_by_start.get(start_idx, [])):
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




