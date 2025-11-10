
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, TypeVar, Generic, Callable, Any, Generator, List, Optional, Tuple, ClassVar, DefaultDict
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError
from rich import print
from syncraft.utils import callable_str
from collections import defaultdict
import copy
import random

def is_lazy(func: Callable[..., Any]) -> bool:
    return hasattr(func, 'is_lazy') and func.is_lazy

def is_choice(func: Callable[..., Any]) -> bool:
    return hasattr(func, 'is_choice') and func.is_choice

def randomized(collection, enable_randomization=True):
    """Helper function to randomize iteration order of sets and other collections."""
    if not enable_randomization:
        # When randomization is disabled, return the original collection to preserve original iteration behavior
        return collection
    items = list(collection)
    random.shuffle(items)
    return items

L = TypeVar('L')  # Left type for combined results
R = TypeVar('R')  # Right type for combined results
S = TypeVar('S', bound=Bindable)

@dataclass(frozen=True)
class Either(Generic[L, R]):
    def __bool__(self) -> bool:
        return isinstance(self, Right)
    
    @property
    def ok(self) -> bool:
        return isinstance(self, Right)

Ret = Either[Any, Tuple[Any, S]]
Rule = Callable[[S, "Cache[S]"], Generator[Any, Any, Ret]]

@dataclass(frozen=True)
class Left(Either[L, Any]):
    value: Optional[L] = None


@dataclass(frozen=True)
class Right(Either[Any, R]):
    value: R

    @property
    def state(self)->Optional[Any]:
        if isinstance(self.value, tuple):
            if len(self.value) >= 2:
                return self.value[1]
        return None


@dataclass(frozen=True)
class Incomplete(Generic[S]):
    state: S

class LeftRecursionError(SyncraftError):

    def __init__(self, 
                 message: str, 
                 offender: Any, 
                 expect: Any = None, 
                 **kwargs: Any) -> None:
        super().__init__(message, offender, expect, **kwargs)
        self.stack: List[str] = []
        self.reason: str | None = kwargs.get('reason')

    def push(self, name: str) -> LeftRecursionError:
        self.stack.append(name)
        return self

    def _format_metrics(self) -> str:
        parts: List[str] = []
        if self.reason:
            parts.append(f"reason={self.reason}")
        return ("; ".join(parts)) if parts else ""

    def __str__(self) -> str:
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
    
@dataclass(frozen=True)
class InProgress(Generic[S]):
    rule: Rule
    revision: int = 0   # the number of successful growth attempts so far
    growing: bool = False # if the lastest growth attempt was successful
    result: Optional[Ret] = None

    def grow(self, rule: Rule, cache_key: int, new_result: Ret) -> InProgress[S]:
        assert rule is self.rule, f"Rule mismatch during grow: {rule} != {self.rule}"

        if isinstance(new_result, Right):
            new_state = new_result.state   
            assert new_state is not None, "New state is None during grow"         
            new_cache_key = new_state.cache_key
            old_state = self.state
            if old_state is None or new_cache_key > old_state.cache_key:
                return replace(self, result=new_result, revision = self.revision + 1, growing=True)
        return replace(self, growing=False)
    
    def __str__(self) -> str:
        return f"InProgress(rule={callable_str(self.rule)}, result={self.result})"
        

    @property
    def state(self) -> Optional[S]:
        if self.result is not None:
            if isinstance(self.result, Right):
                return self.result.state  
        return None


@dataclass
class CacheEntry(Generic[S]):
    payload: Ret | InProgress[S]
    state: S
    @property
    def start_key(self) -> int:
        return self.state.cache_key
    @property
    def end_key(self) -> Optional[int]:
        if isinstance(self.payload, Right):
            state = self.payload.state
            if state is not None:
                return state.cache_key
        elif isinstance(self.payload, InProgress):
            state = self.payload.state
            if state is not None:
                return state.cache_key
        return None


@dataclass(frozen=True)
class Group(Generic[S]):
    leader: Tuple[Rule, int]
    members: frozenset[Tuple[Rule, int]] = field(default_factory=frozenset)
    def __bool__(self) -> bool:
        assert ((self.leader is None and len(self.members) == 0) or 
                (self.leader is not None and len(self.members) > 0)), "Group must have either no leader and no members, or one leader and members"
        return self.leader is not None and len(self.members) > 0


def logging(log: bool | Callable[..., Any]) -> None:
    Cache.DEFAULT_LOGGING = log

def set_randomization(enabled: bool) -> None:
    """Enable or disable randomization globally for all Cache instances."""
    Cache.DEFAULT_RANDOMIZATION = enabled

def set_random_seed(seed: int) -> None:
    """Set the random seed for reproducible randomized testing."""
    random.seed(seed)
@dataclass
class Cache(Generic[S]):
    DEFAULT_LOGGING: ClassVar[bool | Callable[..., Any]] = False
    DEFAULT_RANDOMIZATION: ClassVar[bool] = False  # Default to False to be less intrusive

    logging: bool | Callable[..., Any] = field(default_factory=lambda: Cache.DEFAULT_LOGGING)
    enable_randomization: bool = field(default_factory=lambda: Cache.DEFAULT_RANDOMIZATION)

    stack: list[Tuple[Rule, int]] = field(default_factory=list)
    cache: DefaultDict[Rule, Dict[int, CacheEntry[S]]] = field(default_factory=lambda: defaultdict(dict))
    start2rules: DefaultDict[int, set[Rule]] = field(default_factory=lambda: defaultdict(set))
    end2rules: DefaultDict[int, set[Rule]] = field(default_factory=lambda: defaultdict(set))

    groups: dict[int, Group[S]] = field(default_factory=dict)  # Groups per position
    max_revision: int = 512  # Protection against runaway single-head growth
    max_agenda_size: int = 1000  # Protection against agenda explosion
    max_agenda_depth: int = 50   # Protection against deep agenda recursion


    def clone(self) -> Cache[S]:
        return copy.deepcopy(self)

    @property
    def max_growth_iterations(self) -> int:
        """Alias for max_revision to match test interface"""
        return self.max_revision
    
    @max_growth_iterations.setter
    def max_growth_iterations(self, value: int) -> None:
        """Alias for max_revision to match test interface"""
        self.max_revision = value


    def build_group(self, offender: Rule, pos: int) -> None:
        members: list[Tuple[Rule, int]] = []
        has_choice = False
        has_lazy = False
        for rule in randomized(self.start2rules[pos], self.enable_randomization):
            entry = self.cache[rule].get(pos)
            if entry and isinstance(entry.payload, InProgress):
                members.append((rule, pos))
                if is_choice(rule):
                    has_choice = True
                if is_lazy(rule):
                    has_lazy = True

        existing_group = self.groups.get(pos)
        if existing_group is None:
            if not has_lazy:
                return None
            ret: Group[S] = Group(leader=(offender, pos), members=frozenset(members))
            if not has_choice:
                raise LeftRecursionError(
                    "Left recursion detected but no Choice rule found in group",
                    offender,
                    reason='no-choice'
                )            
        else:
            ret = replace(existing_group, members=existing_group.members | frozenset(members))
        self.groups[pos] = ret
        

    
    def log(self, *args: Any, **kwargs: Any) -> None:
        if callable(self.logging):
            self.logging(*args, **kwargs)
        elif self.logging is True:
            print("[Cache]    ", *args, **kwargs)
    
    def run_rule(self, rule: Rule, key: S) -> Generator[Any, Any, Ret]:
        result = yield from rule(key, self)
        return result
    
    def __str__(self) -> str:
        parts = []
        for f, c in self.cache.items():
            for k, v in c.items():
                parts.append(f"{k} -> {v} ^ {callable_str(f)}")
        content = "\n    ".join(parts)
        return f"Cache(\n    {content})"
    
    
    def gc(self, min_position: int) -> None:
        if min_position < 0:
            min_position = 0    
        for f, bucket in list(self.cache.items()):
            bucket = {k: v for k, v in bucket.items() if k >= min_position}
            if not bucket:
                self.cache.pop(f, None)
        self.start2rules = defaultdict(set, {k: v for k, v in self.start2rules.items() if k >= min_position})
        self.end2rules = defaultdict(set, {k: v for k, v in self.end2rules.items() if k >= min_position})

    def exec(self,
            f: Rule,
            key: S) -> Generator[Any, Any, Ret]:
        
        cache_key = key.cache_key 
        self.stack.append((f, cache_key))
        try:
            cache_bucket = self.cache[f]
            existing = cache_bucket.get(cache_key)
            if existing is not None:
                if not isinstance(existing.payload, InProgress):
                    return existing.payload
                else:
                    assert existing.payload.rule is f, f"Rule mismatch for {callable_str(f)} at {cache_key}: {existing.payload.rule} != {f}"
                    if existing.payload.result is not None:
                        return existing.payload.result
                    else:
                        self.build_group(f, cache_key)  # Group is stored in self.groups[cache_key]
                        return Left() 
            
            head: InProgress[S] = InProgress(rule=f)
            entry = CacheEntry(payload=head, state=key)
            cache_bucket[cache_key] = entry
            self.start2rules[cache_key].add(f)
            seed = yield from self.run_rule(f, key)
            self.install_seed(entry, seed)
            seed = yield from self.post_process(f, seed)
            return seed
        finally:
            self.stack.pop()


    def install_seed(self, entry: CacheEntry, seed: Ret) -> None:
        assert isinstance(entry.payload, InProgress), "install_seed called on non-InProgress payload"
        if isinstance(seed, Right):
            state = seed.state
            assert state is not None, "State is None when installing seed"
            end_key = state.cache_key
            self.end2rules[end_key].add(entry.payload.rule)
            new_payload = entry.payload.grow(entry.payload.rule, entry.start_key, seed)
            if new_payload.growing:
                new_entry = replace(entry, payload=new_payload)
                self.cache[entry.payload.rule][entry.start_key] = new_entry

    def post_process(self, rule: Rule, seed: Ret) -> Generator[Any, Any, Ret]:
        # Find the group where this rule is the leader
        current_group = None
        group_pos = None
        for pos, group in self.groups.items():
            if group.leader[0] is rule:
                current_group = group
                group_pos = pos
                break
        
        # Only the leader should drive the growing process
        if current_group is not None:
            agenda: list[tuple[Rule, int]] = []  # Local agenda
            agenda_set: set[tuple[Rule, int]] = set()  # Deduplication set
    
            # Error detection: track iterations and progress
            iteration_count = 0            
            while True:
                # Check iteration cap before attempting growth
                if iteration_count >= self.max_revision:
                    raise LeftRecursionError("Left recursion iteration cap exceeded",
                                             rule, reason='iteration-cap', revision=iteration_count)
                changed = False
                # Process all group members, but handle cross-position dependencies immediately
                for f, pos in randomized(current_group.members, self.enable_randomization):
                    entry = self.cache[f].get(pos)
                    assert entry is not None, f"No cache entry found for {callable_str(f)} at {pos} during group resolution"
                    payload = entry.payload
                    assert isinstance(payload, InProgress), f"Cache entry payload is not InProgress for {callable_str(f)} at {pos} during group resolution"
                    assert payload.rule is f, f"Cache entry rule is not {callable_str(f)} for {callable_str(f)} at {pos} during group resolution"
                    new_result = yield from self.run_rule(f, entry.state)  # Use f, not rule
                    new_payload = payload.grow(f, pos, new_result)  # Use f, not rule
                    if new_payload.growing:
                        self.cache[f][pos] = replace(entry, payload=new_payload)
                        changed = True

                        if new_payload.result is not None:
                            new_agenda_items = self.build_agenda(pos, new_payload.result)
                            # Add to agenda with deduplication
                            for item in new_agenda_items:
                                if item not in agenda_set:
                                    agenda_set.add(item)
                                    agenda.append(item)
                if not changed:
                    break
                iteration_count += 1
            
            # Check if we're in a non-productive left-recursive situation:
            # - We made no progress (iteration_count == 0)  
            # - All group members still have no result (indicating all choices failed)
            if iteration_count == 0:
                all_failed = True
                for f, pos in randomized(current_group.members, self.enable_randomization):
                    entry = self.cache[f].get(pos)
                    if entry and isinstance(entry.payload, InProgress):
                        if entry.payload.result is not None:
                            all_failed = False
                            break
                
                if all_failed:
                    raise LeftRecursionError(
                        "Left recursion detected with non-productive choices",
                        rule,
                        reason='no-progress'
                    )
                
            group_bak = current_group
            if group_pos is not None and group_pos in self.groups:
                del self.groups[group_pos]  # Remove the group from active groups
            yield from self.process_agenda(agenda)

            leader_entry = self.cache.get(group_bak.leader[0], {}).get(group_bak.leader[1])
            if leader_entry and isinstance(leader_entry.payload, InProgress):
                if leader_entry.payload.result is not None:
                    return leader_entry.payload.result

            agenda.clear()
        
        return seed

    def build_agenda(self, improved_pos: int, improved_result: Ret) -> list[tuple[Rule, int]]:
        """Find rules that could benefit from this improvement and return agenda items"""
        agenda: list[tuple[Rule, int]] = []
        agenda_set: set[tuple[Rule, int]] = set()  # O(1) deduplication
        if not isinstance(improved_result, Right) or improved_result.state is None:
            return agenda
            
        improved_end = improved_result.state.cache_key
                
        # Find rules that ended before this improvement
        for end_pos in range(improved_end):
            rules_at_end = self.end2rules.get(end_pos, set())
            for rule in randomized(rules_at_end, self.enable_randomization):
                # Find all start positions for this rule that could benefit
                for start_pos, entry in self.cache.get(rule, {}).items():
                    # FIXED: Allow rules at the same position or earlier positions to benefit
                    # The key insight: if a rule at position X improves to reach position Y,
                    # then rules that started at position <= X and ended before Y might now
                    # be able to consume more input by incorporating this improvement
                    if start_pos <= improved_pos and entry.end_key == end_pos:
                        # This rule ended before the improvement, might benefit
                        agenda_item = (rule, start_pos)
                        if agenda_item not in agenda_set:  # O(1) set lookup
                            agenda_set.add(agenda_item)
                            agenda.append(agenda_item)
                            
                            # Safety limit: prevent agenda explosion
                            if len(agenda) >= self.max_agenda_size:
                                return agenda
        
        return agenda

    def process_agenda(self, agenda: list[tuple[Rule, int]]) -> Generator[Any, Any, None]:
        """Process all agenda items - re-run rules that might benefit from improvements"""
        depth = 0
        processed_count = 0
        
        while agenda and depth < self.max_agenda_depth:
            rule, pos = agenda.pop(0)
            processed_count += 1
            
            # Safety limit: prevent processing too many items
            if processed_count > self.max_agenda_size:
                break
            
            # Retrieve entry from cache
            entry = self.cache.get(rule, {}).get(pos)
            if entry is None:
                continue  # Entry was already garbage collected or doesn't exist
            
            if not isinstance(entry.payload, InProgress):
                continue  # Entry is already finalized
            
            state = entry.state
            old_result = entry.payload.result
            agenda_size_before = len(agenda)
                        
            # Re-run the rule WITHOUT clearing the cache entry
            # This allows the rule to see and benefit from existing InProgress improvements
            new_result = yield from self.run_rule(rule, state)
            
            # Check if we got an improvement
            if isinstance(new_result, Right) and new_result.state is not None:
                new_end = new_result.state.cache_key
                old_end = None
                if isinstance(old_result, Right) and old_result.state is not None:
                    old_end = old_result.state.cache_key
                
                if old_end is None or new_end > old_end:
                    # Update the InProgress entry with the improved result
                    new_payload = entry.payload.grow(rule, pos, new_result)
                    new_entry = replace(entry, payload=new_payload)
                    self.cache[rule][pos] = new_entry
                    
                    # Update end2rules mapping if needed
                    if old_end is not None:
                        self.end2rules[old_end].discard(rule)
                    self.end2rules[new_end].add(rule)
                    
                    # Build new agenda items for this improvement
                    new_agenda_items = self.build_agenda(pos, new_result)
                    agenda.extend(new_agenda_items)
                    
                    # Increment depth if agenda grew significantly
                    if len(agenda) > agenda_size_before + 5:
                        depth += 1
