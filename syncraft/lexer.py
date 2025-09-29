from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple, Union, TypeVar, Generic, Callable
from syncraft.ast import SyncraftError
from syncraft.charset import CodeUniverse
from syncraft.fa import DFA, NFA, FAState
from syncraft.syntax import Syntax, FactorySpec 


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

@dataclass(frozen=True)
class Lexer(Generic[C]):
    universe: CodeUniverse[C]
    policy: LexPolicy = field(default_factory=LexPolicy)
    rules: Tuple[LexBuilder[C], ...] = field(default_factory=tuple)

    def add(self, *rules: LexBuilder[C]) -> "Lexer[C]":
        return replace(self, rules=self.rules + tuple(rules))


    def build(self, ) -> "Matcher[C]":
        if not self.rules:
            # Empty matcher that always fails
            return Matcher(dfa=DFA(self.universe, init=FAState()), policy=self.policy)

        # Build NFA per rule (limited to the subset we can do cheaply now: literal/concat/union/quantifiers)
        combined: Optional[NFA[C]] = None  # type: ignore[name-defined]
        for idx, rule in enumerate(self.rules):
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
    policy: LexPolicy = field(default_factory=LexPolicy)

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
        all_tags: FrozenSet[Tag] = self._all_tags()
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

        value = _slice_value(text, index, end_pos)
        result = MatchResult(end_index=end_pos, value=value, tag=chosen_tag)


        return result

    # ---- helpers ----
    def _all_tags(self) -> FrozenSet[Tag]:
        seen: set[Tag] = set()
        for tags in self.dfa.accept.values():
            seen.update(tags)
        return frozenset(seen)

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
        runner: Any = self.dfa.runner()
        pos = index
        last_accept_pos: Optional[int] = None
        last_accept_tags: FrozenSet[Tag] = frozenset()

        for sym, step_width in _iter_symbols(text, pos):
            rr = runner.step(sym, pos)
            runner = rr.runner
            if not runner.is_valid():
                break
            # Accept tags at this position intersect allowed
            tags_here = runner.tags()
            if tags_here:
                allowed_here = frozenset(t for t in tags_here if t in allowed)
                if allowed_here:
                    last_accept_pos = pos + step_width
                    last_accept_tags = allowed_here
            pos += step_width

        if last_accept_pos is None or not last_accept_tags:
            return None
        chosen = _choose_tag(last_accept_tags, self.policy)
        return (last_accept_pos, chosen)






# ---- local utilities (no external deps) ----




def _iter_symbols(text: Union[str, bytes, Sequence[C]], start: int):

    if isinstance(text, str):
        for i in range(start, len(text)):
            yield text[i], 1
    elif isinstance(text, (bytes, bytearray)):
        b = text
        for i in range(start, len(b)):
            yield b[i], 1
    else:
        # Generic sequence of ints
        for i in range(start, len(text)):
            yield text[i], 1


def _slice_value(text: Union[str, bytes, Sequence[C]], i: int, j: int) -> Union[str, bytes, List[C]]:
    if isinstance(text, str):
        return text[i:j]
    elif isinstance(text, (bytes, bytearray)):
        return bytes(text[i:j])
    else:
        # Return bytes for sequences of ints to keep it consumable by downstream charsets
        return list(text[i:j])


def _choose_tag(candidates: FrozenSet[Tag], policy: LexPolicy) -> Tag:
    if not candidates:
        raise ValueError("empty candidate set")
    pri = policy.priority_by_tag
    order_index: Dict[Tag, int] = {t: i for i, t in enumerate(policy.declaration_order)}
    def key(t: Tag) -> Tuple[int, int, str]:
        # higher priority first => sort by negative
        return (-pri.get(t, 0), order_index.get(t, 1_000_000_000), str(t))
    return sorted(candidates, key=key)[0]


__all__ = [
    "Lexer",
    "LexBuilder",
    "Matcher",
    "LexPolicy",
    "ModeAction",
    "MatchResult",
    "Tag",
    "collect_lexers",
]


# ---------------------- Syntax integration: collect builders ----------------------

def collect_lexers(
    root: Syntax[Any, Any],
    *,
    universe: Optional[CodeUniverse] = None,
    policy: Optional[LexPolicy] = None,
) -> Lexer:
    """Traverse a Syntax graph to collect distributed LexBuilder specs into a centralized Lexer.

    Rules of thumb:
    - Syntax.literal(x) encodes as LexBuilder.literal(x) with suggested tag None.
    - Syntax.token(text=..., token_type=..., case_sensitive=...):
        • If 'text' is str/bytes/Pattern[str], convert concrete literals to LexBuilder.literal; for Pattern keep for future regex->FA.
        • If 'token_type' is provided, use it as the tag; otherwise None and a synthetic order tag will be assigned during build.
    - We do not execute algebra; we traverse the Syntax spec tree to find nested Syntax children.

    This returns a Lexer with all rules aggregated. Call .build() to obtain a Matcher.
    """
    pol = policy or LexPolicy()

    # Determine universe default: favor ASCII for str, BYTE for bytes; fallback to ASCII
    uni = universe or CodeUniverse.ascii()

    rules: list[LexBuilder] = []

    for _depth, spec in root.walk():
        if isinstance(spec, FactorySpec):
            if spec.name == 're':
                kwargs = dict(spec.kwargs)
                lb = _kwargs_to_builder(kwargs)
                if lb is not None:
                    tag = kwargs.get('token_type')
                    rules.append(lb.tag(tag) if tag is not None else lb)
            elif spec.name == 'success' and spec.args:
                lit_candidate = spec.args[0]
                if isinstance(lit_candidate, (str, bytes)):
                    lb = LexBuilder.literal(lit_candidate)
                    rules.append(lb)

    # Build declaration order into policy for deterministic tie-breaking
    order = tuple(r.tag for r in rules if r.tag is not None)
    pol = replace(pol, declaration_order=order)

    lex = Lexer(universe=uni, policy=pol).add(*rules)
    return lex


def _kwargs_to_builder(kwargs: Mapping[str, Any]) -> Optional[LexBuilder]:
    """Translate Syntax.token kwargs to a LexBuilder when possible.

    Supported forms:
    - text=str or bytes: literal
    - text=re.Pattern: not yet compiled; return None for now (placeholder for future regex->FA)
    """
    text = kwargs.get('text')
    if text is None:
        return None
    if isinstance(text, (str, bytes)):
        # NOTE: ignore case_sensitive for now; case-insensitive will require a char-class transform
        return LexBuilder.literal(text)
    # TODO: handle regex to builder translation using regex -> AST -> NFA
    return None
