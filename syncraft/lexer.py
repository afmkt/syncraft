from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Sequence, Tuple, Union, TypeVar, Generic
from syncraft.charset import CodeUniverse
from syncraft.fa import DFA, NFA, FABuilder

from syncraft.ast import SyncraftError


C = TypeVar('C', bound=str | int | Enum | Any)



# Types
Tag = Union[str, Enum]

                

@dataclass(frozen=True)
class ModeAction:
    """Lexical mode transition action triggered by a matched tag."""
    push: Optional[str] = None
    pop: bool = False
    set: Optional[str] = None


@dataclass(frozen=True)
class LexPolicy:
    priority_by_tag: Dict[Tag, int] = field(default_factory=dict)
    skip: frozenset[Tag] = field(default_factory=frozenset)    
    rule_actions: Dict[Tag, ModeAction] = field(default_factory=dict)
    declaration_order: Tuple[Tag, ...] = field(default_factory=tuple)

    def choose_tag(self, candidates: FrozenSet[Tag]) -> Tag:
        if not candidates:
            raise ValueError("empty candidate set")
        pri = self.priority_by_tag
        order_index: Dict[Tag, int] = {t: i for i, t in enumerate(self.declaration_order)}
        def key(t: Tag) -> Tuple[int, int, str]:
            # higher priority first => sort by negative
            return (-pri.get(t, 0), order_index.get(t, 1_000_000_000), str(t))
        return sorted(candidates, key=key)[0]


@dataclass(frozen=True)
class Lexer(Generic[C]):
    universe: CodeUniverse[C]
    policy: LexPolicy = field(default_factory=LexPolicy)

    def build(self, *rules: FABuilder[C]) -> "Matcher[C]":
        if not rules:
            raise SyncraftError("Cannot build a Matcher with no rules", offender=rules, expect="at least one rule")

        combined: Optional[NFA[C]] = None 
        for rule in rules:
            nfa = rule.compile(self.universe).nfa
            nfa = nfa.tagged(rule.tag) if rule.tag is not None else nfa
            combined = nfa if combined is None else combined.union(nfa)

        assert combined is not None

        return Matcher(dfa=combined.dfa.minimize, policy=self.policy)

@dataclass(frozen=True)
class MatchResult:
    end_index: int
    value: Any
    tag: Optional[Tag] = None


@dataclass(frozen=True)
class Matcher(Generic[C]):
    dfa: DFA[C]
    policy: LexPolicy

    def match(
        self,
        text: Union[str, bytes, Sequence[C]],
        index: int,
        *,
        allowed_tags: Optional[FrozenSet[Tag]] = None
    ) -> Optional[MatchResult]:
        if index < 0 or index > len(text):
            return None

        allowed: FrozenSet[Tag] = allowed_tags if allowed_tags is not None else self.dfa.all_tags()
        runner = self.dfa.runner().priority(self.policy.priority_by_tag).skip(self.policy.skip)
        pos = index
        last_accept_pos = None
        last_accept_tags: FrozenSet[Tag] = frozenset()

        while pos < len(text):
            sym = text[pos]
            rr = runner.step(sym, pos)
            runner = rr.runner
            if not runner.is_valid():
                break
            tags_here = runner.tags() & allowed
            if tags_here:
                last_accept_pos = pos + 1
                last_accept_tags = tags_here
            pos += 1

        if last_accept_pos is None:
            return None
        chosen_tag = self.policy.choose_tag(last_accept_tags)
        if last_accept_pos <= index:
            return None
        if isinstance(text, str):
            value: Any = text[index:last_accept_pos]

        elif isinstance(text, (bytes, bytearray)):
            value = bytes(text[index:last_accept_pos])
        else:
            value = list(text[index:last_accept_pos])
        return MatchResult(end_index=last_accept_pos, value=value, tag=chosen_tag)


__all__ = [
    "Lexer",
    "Matcher",
    "LexPolicy",
    "ModeAction",
    "MatchResult",
]





