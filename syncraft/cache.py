
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, TypeVar, Generic, Callable, Any, Generator, List, Optional, Tuple
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError
from rich import print
from syncraft.utils import callable_str

def is_lazy(func: Callable[..., Any]) -> bool:
    return hasattr(func, 'is_lazy') and func.is_lazy

DEFAULT_LOGGING = False

def enable_logging() -> None:
    global DEFAULT_LOGGING
    DEFAULT_LOGGING = True

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
    def grow(self, rule: Rule, cache_key: int, new_result: Ret) -> bool:
        assert rule is self.rule, f"Rule mismatch during grow: {rule} != {self.rule}"
        assert cache_key == self.start_key, f"Cache key mismatch during grow: {cache_key} != {self.start_key}"
        if isinstance(new_result, Right):
            new_state = new_result.state   
            assert new_state is not None, "New state is None during grow"         
            new_cache_key = new_state.cache_key
            old_state = self.state
            if old_state is None or new_cache_key > old_state.cache_key:
                self.result = new_result # type: ignore
                return True
        return False
    
    def __str__(self) -> str:
        return f"InProgress(rule={callable_str(self.rule)}, start_key={self.start_key}, result={self.result})"
    
    def __repr__(self) -> str:
        return self.__str__()
    

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
    
    def __contains__(self, rule: Rule) -> bool:
        return any(rule is head.rule for head in self.heads)


@dataclass(frozen=True)
class Frame:
    rule: Rule
    def __str__(self) -> str:
        return f"LazyFrame(rule={callable_str(self.rule)})"
    
    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class Cache(Generic[S]):
    cache: dict[Rule, Dict[int, Ret | InProgress[S]]] = field(default_factory=dict)
    stack: List[ Frame] = field(default_factory=list)
    max_growth_iterations: int = 256  # Protection against runaway single-head growth
    group: Dict[int, Group[S]] = field(default_factory=dict)
    growing: bool = False
    logging: bool = field(default_factory=lambda: DEFAULT_LOGGING)


    def log(self, *args: Any, **kwargs: Any) -> None:
        if self.logging:
            print(f"[Cache]{'    ' * len(self.stack)}", *args, **kwargs)

    def enter(self, rule: Rule) -> None:
        self.log(f"Enter: {callable_str(rule)}")
        frame = Frame(rule=rule)
        self.stack.append(frame)
        
    def leave(self) -> None:
        if self.stack:
            self.stack.pop()
        self.log("Leave")
    
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

        if cache_key not in self.group:
            heads: List[InProgress[S]] = []
            cache_bucket = self.cache.get(rule, {})
            existing = cache_bucket.get(cache_key)
            assert isinstance(existing, InProgress), f"Expected InProgress for {callable_str(rule)} at {cache_key}, got {existing}"
            heads.append(existing)
            group = Group(heads=heads)
            self.group[cache_key] = group
        else:
            group = self.group[cache_key]
            cache_bucket = self.cache.get(rule, {})
            existing = cache_bucket.get(cache_key)
            if existing not in group.heads:
                group.heads.append(existing)
        return group

    def exec(self,
            f: Rule,
            key: S) -> Generator[Any, Any, Ret]:
        self.enter(f)
        try:        
            cache_bucket = self.cache.setdefault(f, {})
            cache_key = key.cache_key 
            existing = cache_bucket.get(cache_key)
            self.log(f"Rule: {callable_str(f)} at {cache_key}: existing={existing}")
            self.log(f"Key: {key}")
            if existing is not None and not isinstance(existing, InProgress) and not self.group:
                self.log(f"Cache hit for {callable_str(f)} at {cache_key}: {existing}")
                object.__setattr__(existing, "cache_hit", True)
                return existing
            
            if isinstance(existing, InProgress):
                if existing.start_key == cache_key:
                    if self.growing and self.group and any(f in g for g in self.group.values()):
                        if existing.result is not None:
                            self.log(f"Returning current result for {callable_str(f)} at {cache_key}: {existing.result}")
                            return existing.result
                        else:
                            self.init_group(f, key)
                            self.log(f"Left recursion detected for {callable_str(f)} at {cache_key}")
                            return Left(('SEEDING', key))  # type: ignore
                    else:
                        self.init_group(f, key)
                        self.log(f"Left recursion detected for {callable_str(f)} at {cache_key}")
                        return Left(('SEEDING', key))  # type: ignore
                else:
                    raise SyncraftError(f"Unexpected InProgress for {callable_str(f)} at {cache_key} with start_key {existing.start_key}", offender=existing)
                

            if is_lazy(f):
                cache_bucket[cache_key] = InProgress(rule=f, start_key=cache_key, result=None)
                seed = yield from self.run_rule(f, key)
                seed = yield from self.install_seed(f, seed, key, cache_bucket)
            else:
                seed = yield from self.run_rule(f, key)
                if isinstance(seed, Left):
                    pass
                else:
                    cache_bucket[cache_key] = seed
            return seed
        finally:
            self.leave()

    def install_seed(self,
                     f: Rule,
                     seed: Ret,
                     state: S,
                     cache_bucket: Dict[int, Ret | InProgress[S]]
                     ) -> Generator[Any, Any, Ret]:
        cache_key = state.cache_key
        existing = cache_bucket.get(cache_key)
        assert isinstance(existing, InProgress), f"Expected InProgress for {callable_str(f)} at {cache_key}, got {existing}"
        assert existing.rule is f, f"Rule mismatch for {callable_str(f)} at {cache_key}: {existing.rule} != {f}"
        if not self.group:
            if isinstance(seed, Left):
                pass
            else:
                cache_bucket[cache_key] = seed  # type: ignore
        else:
            group = self.group.get(cache_key)
            if group is None:
                if isinstance(seed, Left):
                    pass
                else:
                    cache_bucket[cache_key] = seed  # type: ignore
            else:
                if is_lazy(f):
                    iteration_count = 0
                    while existing.grow(f, cache_key, seed):
                        iteration_count += 1
                        if iteration_count > self.max_growth_iterations:
                            raise LeftRecursionError(
                                f"Left recursion iteration cap exceeded for {callable_str(f)} at {cache_key}",
                                f,
                                iterations=iteration_count,
                                limit=self.max_growth_iterations,
                                reason='iteration-cap',
                                group_size=len(group.heads)
                            )
                        self.log('GROWING: ', callable_str(f), 'at', cache_key, 'from', seed)
                        self.growing = True
                        seed = yield from self.run_rule(f, state)
                        self.growing = False
                        self.log('to', seed)
                    result = existing.result if existing.result is not None else seed
                    cache_bucket[cache_key] = result  # type: ignore
                    if cache_key in self.group:
                        del self.group[cache_key]
                    return result
                else:
                    if isinstance(seed, Left):
                        pass
                    else:
                        cache_bucket[cache_key] = seed  # type: ignore
        return seed


