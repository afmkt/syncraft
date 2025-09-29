from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple, Union, TypeVar, Generic
from syncraft.charset import CodeUniverse
from syncraft.fa import DFA, NFA, FABuilder, Runner

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

        # Build NFA per rule (limited to the subset we can do cheaply now: literal/concat/union/quantifiers)
        combined: Optional[NFA[C]] = None  # type: ignore[name-defined]
        for idx, rule in enumerate(rules):
            nfa = rule.compile(self.universe).nfa
            if rule.tag is not None:
                nfa = nfa.tagged(rule.tag)
            else:
                # Fallback: assign a stable synthetic tag using declaration order
                synth_tag: Tag = f"RULE#{idx}"
                nfa = nfa.tagged(synth_tag)
            combined = nfa if combined is None else combined.union(nfa)

        assert combined is not None
        # Note: minimization and advanced ops (intersect/diff) will be planned later.
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
        """Find the longest match starting at index respecting allowed tags and policy.

        This is a placeholder that will be implemented alongside parser integration.
        For now, it returns None to indicate no match, so importing this module is safe.
        """
        n = len(text)
        if index < 0 or index > n:
            return None

        # Compute effective allowed sets
        all_tags: FrozenSet[Tag] = self.dfa.all_tags()
        allowed: FrozenSet[Tag] = allowed_tags if allowed_tags is not None else all_tags

        # Left trim loop (consume zero or more skip tokens)
        if self.policy.skip:
            trim_allowed = allowed & self.policy.skip
            while trim_allowed:
                m = self._longest(text, index, trim_allowed)
                if m is None:
                    break
                end_pos, chosen_tag = m
                if end_pos <= index:  # guard zero-length
                    break
                index = end_pos
                # Apply mode actions here in future (policy.rule_actions.get(chosen_tag))
                # Recompute trim_allowed in case modes/actions change visibility; keep simple for now
                trim_allowed = allowed & self.policy.skip

        # Main match with allowed tags
        main = self._longest(text, index, allowed)
        if main is None:
            return None
        end_pos, chosen_tag = main
        if end_pos <= index:
            return None
        
        def _slice_value(text: Union[str, bytes, Sequence[C]], i: int, j: int) -> Union[str, bytes, List[C]]:
            if isinstance(text, str):
                return text[i:j]
            elif isinstance(text, (bytes, bytearray)):
                return bytes(text[i:j])
            else:
                return list(text[i:j])

        value = _slice_value(text, index, end_pos)
        return MatchResult(end_index=end_pos, value=value, tag=chosen_tag)



    def _longest(
        self,
        text: Union[str, bytes, Sequence[C]],
        index: int,
        allowed: FrozenSet[Tag],
    ) -> Optional[Tuple[int, Tag]]:
        """Run DFA from index and return (end_pos, chosen_tag) for allowed tags on the longest span.

        Chooses tag by policy priority, then declaration order, then tag name.
        """
        if not allowed:
            return None
        runner: Runner[C, DFA[C]] = self.dfa.runner()
        pos = index
        last_accept_pos: Optional[int] = None
        last_accept_tags: FrozenSet[Tag] = frozenset()

        for sym in text[pos:]:
            rr = runner.step(sym, pos)
            runner = rr.runner
            if not runner.is_valid():
                break
            tags_here = runner.tags()
            if tags_here:
                allowed_here = frozenset(t for t in tags_here if t in allowed)
                if allowed_here:
                    last_accept_pos = pos + 1
                    last_accept_tags = allowed_here
            pos += 1

        if last_accept_pos is None or not last_accept_tags:
            return None
        chosen = self.policy.choose_tag(last_accept_tags)
        return (last_accept_pos, chosen)









__all__ = [
    "Lexer",

    "Matcher",
    "LexPolicy",
    "ModeAction",
    "MatchResult",
]





