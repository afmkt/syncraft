
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


@dataclass
class CacheRecord(Generic[S]):
    entries: list[CacheEntry[S]] = field(default_factory=list)
    @property
    def group(self) -> list[CacheEntry[S]]:
        heads: list[CacheEntry[S]] = []
        for entry in self.entries:
            if isinstance(entry.payload, InProgress):
                heads.append(entry)
        return heads
    def add(self, entry: CacheEntry[S]) -> None:
        self.entries.append(entry)


def logging(log: bool | Callable[..., Any]) -> None:
    Cache.DEFAULT_LOGGING = log
@dataclass
class Cache(Generic[S]):
    DEFAULT_LOGGING: ClassVar[bool | Callable[..., Any]] = False

    logging: bool | Callable[..., Any] = field(default_factory=lambda: Cache.DEFAULT_LOGGING)

    cache: DefaultDict[Rule, Dict[int, CacheEntry[S]]] = field(default_factory=lambda: defaultdict(dict))
    start2rules: DefaultDict[int, set[Rule]] = field(default_factory=lambda: defaultdict(set))
    end2rules: DefaultDict[int, set[Rule]] = field(default_factory=lambda: defaultdict(set))

    max_revision: int = 256  # Protection against runaway single-head growth

    def entry_at(self, pos: int, start: bool = True) -> List[CacheEntry[S]]:
        entries: List[CacheEntry[S]] = []
        if start:
            rules = self.start2rules[pos]
            for rule in rules:
                bucket = self.cache[rule]
                entry = bucket.get(pos)
                if entry is not None:
                    entries.append(entry)
        else:
            rules = self.end2rules[pos]
            for rule in rules:
                bucket = self.cache[rule]
                for entry in bucket.values():
                    end_key = entry.end_key
                    if end_key == pos:
                        entries.append(entry)
        return entries

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
        cache_bucket = self.cache[f]
        cache_key = key.cache_key 
        existing = cache_bucket.get(cache_key)
        self.log(f"Rule: {callable_str(f)} at {cache_key}: existing={existing}")
        if existing is not None:
            if not isinstance(existing.payload, InProgress):
                return existing.payload
            else:
                assert existing.payload.rule is f, f"Rule mismatch for {callable_str(f)} at {cache_key}: {existing.payload.rule} != {f}"
                if existing.payload.result is not None:
                    self.log(f"Returning current result for {callable_str(f)} at {cache_key}: {existing.payload.result}")
                    return existing.payload.result.flags(GROWING=True)
                self.log(f"Left recursion detected for {callable_str(f)} at {cache_key}")
                return Left(key).flags(SEEDING=True)  # type: ignore
        head: InProgress[S] = InProgress(rule=f)
        entry = CacheEntry(payload=head, state=key)
        cache_bucket[cache_key] = entry
        self.start2rules[cache_key].add(f)
        seed = yield from self.run_rule(f, key)
        return seed
    