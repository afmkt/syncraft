"""
Internal scaffolding for DFA-based lexeme terminals without a token stream.

This module defines three main concepts:
- Lexer (centralized): holds CodeUniverse and non-local lexical policies (priority, skip/trim, modes).
- LexBuilder (distributed): a small DSL to build lexeme patterns; later aggregated by the Lexer.
- Matcher: the shared, DFA-based matcher built from a set of LexBuilder rules; used by terminals at runtime.

Nothing here is user-facing yet; these are contracts and placeholders for integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple, Union

from .charset import CodeUniverse
from .fa import DFA, NFA, FAState
from . import syntax as _syntax


# Types
Tag = Union[str, Enum]


@dataclass(frozen=True)
class ModeAction:
    """Describes a mode transition to apply after a successful match of a tag.

    Exactly one of push, pop, or set should normally be used.
    """
    push: Optional[str] = None
    pop: bool = False
    set: Optional[str] = None


@dataclass(frozen=True)
class LexPolicy:
    """Centralized lexical policy shared by all FA terminals.

    - priority_by_tag: higher number wins when multiple tags accept the same longest span
    - left_trim/right_trim: tags to consume silently before/after a terminal match
    - rule_actions: mode transitions keyed by tag
    - declaration_order: stable ordering for tie-breaks after priority
    """
    priority_by_tag: Dict[Tag, int] = field(default_factory=dict)
    left_trim: FrozenSet[Tag] = field(default_factory=frozenset)
    right_trim: FrozenSet[Tag] = field(default_factory=frozenset)
    rule_actions: Dict[Tag, ModeAction] = field(default_factory=dict)
    declaration_order: Tuple[Tag, ...] = field(default_factory=tuple)


class _NodeKind(str, Enum):
    LITERAL = "LITERAL"
    CONCAT = "CONCAT"
    UNION = "UNION"
    INTERSECT = "INTERSECT"  # DFA-only
    DIFF = "DIFF"            # DFA-only (A - B)
    STAR = "STAR"
    PLUS = "PLUS"
    OPTIONAL = "OPTIONAL"
    MANY = "MANY"


@dataclass(frozen=True)
class LexBuilder:
    """Distributed lexeme builder DSL node.

    Users create via:
      - LexBuilder.literal(text)
      - DSL operators: + (concat), | (union), ~ (optional), .star, .many(...)
      - Intersection (&) and difference (-) are captured in the IR and handled during build planning

    A LexBuilder does NOT itself execute; it is compiled by a Lexer into a shared DFA.
    """
    kind: _NodeKind
    children: Tuple["LexBuilder", ...] = field(default_factory=tuple)
    text: Optional[Union[str, bytes]] = None
    at_least: int = 1
    at_most: Optional[int] = None
    suggested_tag: Optional[Tag] = None

    # ---- Factory entry points ----
    @classmethod
    def literal(cls, text: Union[str, bytes], *, tag: Optional[Tag] = None) -> "LexBuilder":
        return cls(kind=_NodeKind.LITERAL, text=text, suggested_tag=tag)

    # Alias for convenience
    @classmethod
    def lit(cls, text: Union[str, bytes], *, tag: Optional[Tag] = None) -> "LexBuilder":
        return cls.literal(text, tag=tag)

    # ---- DSL operators ----
    def __add__(self, other: "LexBuilder") -> "LexBuilder":
        return LexBuilder(kind=_NodeKind.CONCAT, children=(self, other))

    def __or__(self, other: "LexBuilder") -> "LexBuilder":
        return LexBuilder(kind=_NodeKind.UNION, children=(self, other))

    def __and__(self, other: "LexBuilder") -> "LexBuilder":
        return LexBuilder(kind=_NodeKind.INTERSECT, children=(self, other))

    def __sub__(self, other: "LexBuilder") -> "LexBuilder":
        return LexBuilder(kind=_NodeKind.DIFF, children=(self, other))

    def __invert__(self) -> "LexBuilder":  # optional (~)
        return LexBuilder(kind=_NodeKind.OPTIONAL, children=(self,))

    @property
    def star(self) -> "LexBuilder":
        return LexBuilder(kind=_NodeKind.STAR, children=(self,))

    @property
    def plus(self) -> "LexBuilder":
        # desugar plus -> concat(self, self.star)
        return (self + self.star)

    def many(self, *, at_least: int = 1, at_most: Optional[int] = None) -> "LexBuilder":
        return LexBuilder(kind=_NodeKind.MANY, children=(self,), at_least=at_least, at_most=at_most)

    def tag(self, value: Tag) -> "LexBuilder":
        return replace(self, suggested_tag=value)






@dataclass(frozen=True)
class Lexer:
    """Centralized holder of universe and non-local lexical policies.

    A Lexer aggregates distributed rules (LexBuilder) and compiles them into a shared DFA-based Matcher.
    """
    universe: CodeUniverse
    policy: LexPolicy = field(default_factory=LexPolicy)
    rules: Tuple[LexBuilder, ...] = field(default_factory=tuple)

    def add(self, *rules: LexBuilder) -> "Lexer":
        return replace(self, rules=self.rules + tuple(rules))


    def build(self) -> "Matcher":
        """Compile the current rules into a shared DFA-based Matcher.

        Outline:
          - Convert each LexBuilder to an NFA (Thompson-like) where possible
          - Union all NFAs, tagging accept states with rule tag (if provided)
          - Determinize to a single DFA
          - Optionally minimize (policy-driven threshold; not implemented here)
        """
        if not self.rules:
            # Empty matcher that always fails
            return Matcher(universe=self.universe, dfa=DFA(self.universe, init=FAState()), policy=self.policy)

        # Build NFA per rule (limited to the subset we can do cheaply now: literal/concat/union/quantifiers)
        combined: Optional[NFA[Any]] = None  # type: ignore[name-defined]
        for idx, rule in enumerate(self.rules):
            nfa = _compile_builder_to_nfa(rule, self.universe)
            if rule.suggested_tag is not None:
                nfa = nfa.tagged(rule.suggested_tag)
            else:
                # Fallback: assign a stable synthetic tag using declaration order
                synth_tag: Tag = f"RULE#{idx}"
                nfa = nfa.tagged(synth_tag)
            combined = nfa if combined is None else combined.union(nfa)

        assert combined is not None
        # Note: minimization and advanced ops (intersect/diff) will be planned later.
        return Matcher(universe=self.universe, dfa=combined.dfa, policy=self.policy)


@dataclass(frozen=True)
class MatchResult:
    end_index: int
    value: Any
    tag: Optional[Tag] = None


@dataclass(frozen=True)
class Matcher:
    """Shared DFA-based matcher.

    This is the single, centralized matcher that all FA-terminal nodes consult at runtime.
    It owns the DFA and the policy; terminals provide the input text/index and optional allowed tag set.
    """
    universe: CodeUniverse
    dfa: DFA[Any]
    policy: LexPolicy = field(default_factory=LexPolicy)

    def match(
        self,
        text: Union[str, bytes, Sequence[int]],
        index: int,
        *,
        allowed_tags: Optional[FrozenSet[Tag]] = None,
        left_trim: bool = True,
        right_trim: bool = False,
    ) -> Optional[MatchResult]:
        """Find the longest match starting at index respecting allowed tags and policy.

        This is a placeholder that will be implemented alongside parser integration.
        For now, it returns None to indicate no match, so importing this module is safe.
        """
        n = _length(text)
        if index < 0 or index > n:
            return None

        # Compute effective allowed sets
        all_tags: FrozenSet[Tag] = self._all_tags()
        allowed: FrozenSet[Tag] = allowed_tags if allowed_tags is not None else all_tags

        # Left trim loop (consume zero or more skip tokens)
        if left_trim and self.policy.left_trim:
            trim_allowed = allowed & self.policy.left_trim
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
                trim_allowed = allowed & self.policy.left_trim

        # Main match with allowed tags
        main = self._longest(text, index, allowed)
        if main is None:
            return None
        end_pos, chosen_tag = main
        if end_pos <= index:
            return None

        value = _slice_value(text, index, end_pos)
        result = MatchResult(end_index=end_pos, value=value, tag=chosen_tag)

        # Right trim (optional)
        if right_trim and self.policy.right_trim:
            trim_allowed = allowed & self.policy.right_trim
            pos = end_pos
            while trim_allowed:
                m = self._longest(text, pos, trim_allowed)
                if m is None:
                    break
                new_end, t2 = m
                if new_end <= pos:
                    break
                pos = new_end
                # Apply actions later if needed
                trim_allowed = allowed & self.policy.right_trim
            # Extend consumed range but keep the value from main match only
            result = replace(result, end_index=pos)

        return result

    # ---- helpers ----
    def _all_tags(self) -> FrozenSet[Tag]:
        seen: set[Tag] = set()
        for tags in self.dfa.accept.values():
            seen.update(tags)
        return frozenset(seen)

    def _longest(
        self,
        text: Union[str, bytes, Sequence[int]],
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


# ---- Internal helpers ----

def _compile_builder_to_nfa(builder: LexBuilder, universe: CodeUniverse) -> NFA[Any]:  # type: ignore[name-defined]
    """Compile a LexBuilder to an NFA for the subset of ops we can cheaply support now.

    Supported: LITERAL, CONCAT, UNION, STAR, OPTIONAL, MANY, (PLUS via desugaring).
    Not yet: INTERSECT, DIFF (these will be planned to DFA and back as needed).
    """
    kind = builder.kind
    if kind is _NodeKind.LITERAL:
        text = builder.text
        assert isinstance(text, (str, bytes)), "literal text must be str or bytes"
        # Build by concatenating single-char NFAs
        nfa: Optional[NFA[Any]] = None  # type: ignore[name-defined]
        if isinstance(text, str):
            for ch in text:
                part = NFA.from_charset(ch, universe=universe)
                nfa = part if nfa is None else nfa.then(part)
        else:  # bytes
            for b in text:
                part = NFA.from_charset(bytes([b]), universe=universe)
                nfa = part if nfa is None else nfa.then(part)
        assert nfa is not None, "empty literal not allowed"
        return nfa
    elif kind is _NodeKind.CONCAT:
        assert len(builder.children) == 2
        left = _compile_builder_to_nfa(builder.children[0], universe)
        right = _compile_builder_to_nfa(builder.children[1], universe)
        return left.then(right)
    elif kind is _NodeKind.UNION:
        assert len(builder.children) == 2
        left = _compile_builder_to_nfa(builder.children[0], universe)
        right = _compile_builder_to_nfa(builder.children[1], universe)
        return left.union(right)
    elif kind is _NodeKind.STAR:
        assert len(builder.children) == 1
        inner = _compile_builder_to_nfa(builder.children[0], universe)
        return inner.star
    elif kind is _NodeKind.OPTIONAL:
        assert len(builder.children) == 1
        inner = _compile_builder_to_nfa(builder.children[0], universe)
        return inner.optional
    elif kind is _NodeKind.MANY:
        assert len(builder.children) == 1
        inner = _compile_builder_to_nfa(builder.children[0], universe)
        return inner.many(at_least=builder.at_least, at_most=builder.at_most)
    elif kind in (_NodeKind.INTERSECT, _NodeKind.DIFF):
        # Will require DFA planning; not yet supported in this helper.
        raise NotImplementedError(f"{kind} requires DFA planning; will be supported in the planner.")
    else:
        raise NotImplementedError(f"Unhandled LexBuilder kind: {kind}")


# ---- local utilities (no external deps) ----

def _length(text: Union[str, bytes, Sequence[int]]) -> int:
    return len(text)


def _iter_symbols(text: Union[str, bytes, Sequence[int]], start: int):
    """Yield (symbol, width) from text[start:].

    - For str: symbol is a one-character string, width=1.
    - For bytes: symbol is an int (0..255), width=1.
    - For Sequence[int]: symbol is the int value, width=1.
    """
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


def _slice_value(text: Union[str, bytes, Sequence[int]], i: int, j: int) -> Union[str, bytes, List[int]]:
    if isinstance(text, str):
        return text[i:j]
    elif isinstance(text, (bytes, bytearray)):
        return bytes(text[i:j])
    else:
        # Return bytes for sequences of ints to keep it consumable by downstream charsets
        return bytes(text[i:j])


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
    root: _syntax.Syntax[Any, Any],
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
        if isinstance(spec, _syntax.FactorySpec):
            if spec.name == 'token':
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
    order = tuple(r.suggested_tag for r in rules if r.suggested_tag is not None)
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
