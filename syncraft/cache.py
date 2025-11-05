
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, TypeVar, Generic, Callable, Any, Generator, List, Optional, Tuple, ClassVar, DefaultDict, Set
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError
from rich import print
from syncraft.utils import callable_str
from collections import defaultdict
def is_lazy(func: Callable[..., Any]) -> bool:
    return hasattr(func, 'is_lazy') and func.is_lazy


L = TypeVar('L')  # Left type for combined results
R = TypeVar('R')  # Right type for combined results
S = TypeVar('S', bound=Bindable)

@dataclass(frozen=True)
class Either(Generic[L, R]):
    def __bool__(self) -> bool:
        return isinstance(self, Right)

    def is_flagged(self, **kwargs: bool) -> bool:
        if isinstance(self, (Left, Right)):
            flags: Set[str] = set()
            for k, v in kwargs.items():
                if v:
                    flags.add(k)
            return not self._flags.isdisjoint(flags)
        raise NotImplementedError("is_flagged method not implemented for this Either subtype")

    def flags(self, *args: str, **kwargs: bool) -> Either[L, R]:
        if len(args) > 0 and len(kwargs) > 0:
            raise ValueError("Cannot mix positional and keyword arguments in flags()")
        if isinstance(self, (Left, Right)):
            if len(kwargs) == 0:
                return replace(self, _flags = self._flags | frozenset(args))
            else:
                return replace(self, _flags = frozenset(kwargs.keys()))
        raise NotImplementedError("flags method not implemented for this Either subtype")

    @property
    def ok(self) -> bool:
        return isinstance(self, Right)

Ret = Either[Any, Tuple[Any, S]]
Rule = Callable[[S, "Cache[S]"], Generator[Any, Any, Ret]]

@dataclass(frozen=True)
class Left(Either[L, Any]):
    value: Optional[L] = None
    _flags: frozenset[str] = field(default_factory=frozenset)

@dataclass(frozen=True)
class Right(Either[Any, R]):
    value: R
    _flags: frozenset[str] = field(default_factory=frozenset)
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
        self.revision: int | None = kwargs.get('revision')
        self.reason: str | None = kwargs.get('reason')

    def push(self, name: str) -> LeftRecursionError:
        self.stack.append(name)
        return self

    def _format_metrics(self) -> str:
        parts: List[str] = []
        if self.revision is not None:
            parts.append(f"revision={self.revision}")
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
    
    def __repr__(self) -> str:
        return self.__str__()
    

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
    members: list[Tuple[Rule, int]] = field(default_factory=list)

    @property
    def leader(self) -> Tuple[Rule, int]:
        return self.members[-1]



def logging(log: bool | Callable[..., Any]) -> None:
    Cache.DEFAULT_LOGGING = log
@dataclass
class Cache(Generic[S]):
    DEFAULT_LOGGING: ClassVar[bool | Callable[..., Any]] = False
    lazy_stack: list[Tuple[Rule, int]] = field(default_factory=list)
    logging: bool | Callable[..., Any] = field(default_factory=lambda: Cache.DEFAULT_LOGGING)

    cache: DefaultDict[Rule, Dict[int, CacheEntry[S]]] = field(default_factory=lambda: defaultdict(dict))
    start2rules: DefaultDict[int, set[Rule]] = field(default_factory=lambda: defaultdict(set))
    end2rules: DefaultDict[int, set[Rule]] = field(default_factory=lambda: defaultdict(set))
    agenda: list[tuple[Rule, int]] = field(default_factory=list)

    group: Optional[Group[S]] = None
    max_revision: int = 256  # Protection against runaway single-head growth

    def build_group(self, offender: Rule, pos: int) -> Group[S]:
        """Build group of all InProgress entries at the same position"""
        members: list[Tuple[Rule, int]] = []
        
        # Find all rules with InProgress entries at this position
        for rule in self.start2rules[pos]:
            entry = self.cache[rule].get(pos)
            if entry and isinstance(entry.payload, InProgress):
                members.append((rule, pos))
        
        return Group(members=members)
    
    def log(self, *args: Any, **kwargs: Any) -> None:
        if callable(self.logging):
            self.logging(*args, **kwargs)
        elif self.logging is True:
            print("[Cache]    ", *args, **kwargs)
    
    def run_rule(self, rule: Rule, key: S) -> Generator[Any, Any, Ret]:
        result = yield from rule(key, self)
        return result
    
    def __repr__(self) -> str:
        parts = []
        for f, c in self.cache.items():
            for k, v in c.items():
                parts.append(f"{k} -> {v} ^ {callable_str(f)}")
        content = "\n    ".join(parts)
        return f"Cache(\n    {content})"

    def __str__(self) -> str:
        return self.__repr__()
    
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
        if is_lazy(f):
            self.lazy_stack.append((f, cache_key))
        try:
            cache_bucket = self.cache[f]
            existing = cache_bucket.get(cache_key)
            if existing is not None:
                if not isinstance(existing.payload, InProgress):
                    return existing.payload
                else:
                    assert existing.payload.rule is f, f"Rule mismatch for {callable_str(f)} at {cache_key}: {existing.payload.rule} != {f}"
                    if existing.payload.result is not None:
                        self.log(f"Returning current result for {callable_str(f)} at {cache_key}: {existing.payload.result}")
                        return existing.payload.result.flags(SEEDING=True)
                    else:
                        self.group = self.build_group(f, cache_key)
                        return Left().flags(SEEDING=True)  
            head: InProgress[S] = InProgress(rule=f)
            entry = CacheEntry(payload=head, state=key)
            cache_bucket[cache_key] = entry
            self.start2rules[cache_key].add(f)
            seed = yield from self.run_rule(f, key)
            self.install_seed(entry, seed)
            seed = yield from self.post_process(f, seed)
            return seed
        finally:
            if is_lazy(f):
                self.lazy_stack.pop()
    
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
        if self.group and self.group.leader[0] is rule:
            while True:
                changed = False
                for f, pos in self.group.members:
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
                        # Build agenda when rule improves
                        if new_payload.result is not None:
                            self.build_agenda_for_improvement(f, pos, new_payload.result)
                if not changed:
                    break
            
            # Process cross-position dependencies via agenda
            yield from self.process_agenda()
            
            # Unwrap all InProgress entries in the group to their final results
            for f, pos in self.group.members:
                entry = self.cache[f].get(pos)
                if entry and isinstance(entry.payload, InProgress):
                    if entry.payload.result is not None:
                        # Replace InProgress with final result
                        final_entry = replace(entry, payload=entry.payload.result)
                        self.cache[f][pos] = final_entry
                    else:
                        # No result - remove the entry
                        del self.cache[f][pos]
                        self.start2rules[pos].discard(f)
            
            # Clear group after both same-position growth and cross-position propagation
            self.group = None
            
            # Agenda is automatically cleared by process_agenda(), but clear any remaining items on error
            self.agenda.clear()
            # ?what to return here?
        
        return seed

    def build_agenda_for_improvement(self, improved_rule: Rule, improved_pos: int, improved_result: Ret) -> None:
        """Find rules that could benefit from this improvement and add them to agenda"""
        if not isinstance(improved_result, Right) or improved_result.state is None:
            return
            
        improved_end = improved_result.state.cache_key
        
        # Find rules that ended before this improvement
        for end_pos in range(improved_end):
            for rule in self.end2rules.get(end_pos, set()):
                # Find all start positions for this rule that could benefit
                for start_pos, entry in self.cache.get(rule, {}).items():
                    if start_pos < improved_pos and entry.end_key == end_pos:
                        # This rule ended before the improvement, might benefit
                        if (rule, start_pos) not in self.agenda:
                            self.agenda.append((rule, start_pos))

    def process_agenda(self) -> Generator[Any, Any, None]:
        """Process all agenda items - re-run rules that might benefit from improvements"""
        while self.agenda:
            rule, pos = self.agenda.pop(0)
            
            # Retrieve state from cache
            entry = self.cache.get(rule, {}).get(pos)
            if entry is None:
                continue  # Entry was already garbage collected or doesn't exist
            
            state = entry.state
            
            # Clear the old cache entry to force re-computation
            del self.cache[rule][pos]
            
            # Remove from end2rules mapping
            if entry.end_key is not None:
                self.end2rules[entry.end_key].discard(rule)
            
            # Re-run the rule
            yield from self.exec(rule, state)
