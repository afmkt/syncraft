
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, TypeVar, Hashable, Generic, Callable, Any, Generator, List, Optional, Tuple, cast
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError

from syncraft.utils import callable_str


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
    

@dataclass
class InProgress(Generic[S]):
    rule: Rule
    start_key: int
    result: Optional[Ret] 
    seeding: bool

    def grow(self, new_result: Ret) -> bool:
        if isinstance(new_result, Right):
            new_state = new_result.state            
            if new_state is not None:
                old_state = self.state
                old_cache_key = old_state.cache_key if old_state is not None else -1
                new_cache_key = new_state.cache_key
                if new_cache_key > old_cache_key:
                    self.result = new_result # type: ignore
                    self.seeding = False
                    return True
        return False
    
    @property
    def state(self) -> Optional[S]:
        if self.result is not None:
            if isinstance(self.result, Right):
                return self.result.state  
        return None


@dataclass
class Group(Generic[S]):
    heads: List[InProgress[S]]
    @property
    def leader(self) -> InProgress[S]:
        if not self.heads:
            raise SyncraftError("Group has no heads", offender=self)
        return self.heads[0]
    

@dataclass(frozen=True)
class LazyFrame(Generic[S]):
    func: Rule
    state: S
    inner: Optional[Rule]

@dataclass
class Cache(Generic[S]):
    cache: dict[Rule, Dict[int, Ret | InProgress[S]]] = field(default_factory=dict)
    key_frames: List[ LazyFrame] = field(default_factory=list)
    max_growth_iterations: int = 256  # Protection against runaway single-head growth
    group: Optional[Group[S]] = None

    def enter(self, 
              func: Rule, 
              state: S, 
              *,
              inner: Optional[Rule] = None) -> None:
        frame = LazyFrame(func=func, state=state, inner=inner)
        self.key_frames.append(frame)
        
    def leave(self) -> None:
        if self.key_frames:
            self.key_frames.pop()
    
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
    
    def gc(self, min_position: int) -> int:


        if min_position < 0:
            min_position = 0

        removed = 0
        for f, bucket in list(self.cache.items()):
            victims = [k for k in bucket if k < min_position]
            for k in victims:
                bucket.pop(k, None)
                removed += 1
            if not bucket:
                del self.cache[f]

        return removed
    
    def init_group(self, rule: Rule, key: S) -> Group[S]:
        cache_key = key.cache_key 
        cnt: int = 0
        heads: List[InProgress[S]] = []
        for lazy_frame in self.key_frames[::-1]:
            f = lazy_frame.func
            state = lazy_frame.state
            cache_bucket = self.cache.get(f, {})
            existing = cache_bucket.get(cache_key)
            assert isinstance(existing, InProgress), f"Expected InProgress for {callable_str(f)} at {cache_key}, got {existing}"
            assert existing.start_key == cache_key, f"Start key mismatch for {callable_str(f)} at {cache_key}: {existing.start_key} != {cache_key}"
            assert existing.rule == f, f"Rule mismatch for {callable_str(f)} at {cache_key}: {existing.rule} != {f}"
            assert existing.seeding, f"Expected seeding InProgress for {callable_str(f)} at {cache_key}, got non-seeding"
            assert state.cache_key == cache_key, f"State cache key mismatch for {callable_str(f)} at {cache_key}: {state.cache_key} != {cache_key}"
            heads.append(existing)
            if f == rule:
                cnt += 1
                if cnt >= 2:
                    break
        group = Group(heads=heads)
        self.group = group
        return group

    def exec(self,
            f: Rule,
            key: S) -> Generator[Any, Any, Ret]:
        cache_bucket = self.cache.setdefault(f, {})
        cache_key = key.cache_key 
        existing = cache_bucket.get(cache_key)
        if existing is not None and not isinstance(existing, InProgress):
            # cache hit
            object.__setattr__(existing, "cache_hit", True)
            return existing
        
        if isinstance(existing, InProgress):
            if existing.seeding:
                # re-entry during seeding: handle left recursion
                # Short-circuit to indicate seeding in progress
                # This signals the failure of the current alternative, allowing or_else to try right branch.
                self.init_group(f, key)
                return Left(('SEEDING', key))  # type: ignore
        # Step 3: seed new head
        head : InProgress[S] = InProgress(rule=f, start_key=cache_key, seeding=True, result=None)
        cache_bucket[cache_key] = head
        # Register head for potential cross-position revisits (agenda scheduling)
        start_key: int = key.cache_key # self._start_key(key)
        try:
            # Opportunistic co-seeding: if this rule is an Expr-like head referencing another lazy head
            # at the same starting position (e.g., Expr vs Term), ensure both are seeded so they will be grouped.
            seed = yield from self.run_rule(f, key)
        except Exception as e:
            cache_bucket.pop(cache_key, None)
            raise e
        # Step 4: finalize or prepare for growth
        return (yield from self._complete_seed(head, seed))
    



