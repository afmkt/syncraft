from __future__ import annotations

from typing import List
import pytest
from syncraft.syntax import (
    Syntax,
    SyntaxSpec,
    LazySpec,
    ThenSpec,
    ChoiceSpec,

)
from syncraft.ast import (
    Token,
    Then,
    Choice,
    Many,
    Marked,
    Collect,
    Nothing,
    Lazy,
)

from syncraft.parser import parse_word
from syncraft.lexer import ExtLexer
from syncraft.token import Structured
from syncraft.regex import regex_syntax




def _flatten_choices(spec: SyntaxSpec) -> List[SyntaxSpec]:
    if isinstance(spec, ChoiceSpec):
        return _flatten_choices(spec.left) + _flatten_choices(spec.right)
    return [spec]


def _is_left_recursive(alt: SyntaxSpec, root: SyntaxSpec) -> bool:
    current = alt
    while isinstance(current, ThenSpec):
        candidate = current.left
        if candidate is root:
            return True
        current = candidate
    return False


def _strip_left_recursion(alt: SyntaxSpec, root: SyntaxSpec) -> SyntaxSpec:
    if not isinstance(alt, ThenSpec):  # pragma: no cover - defensive guard
        raise AssertionError("Left-recursive alternative must be a ThenSpec")
    if alt.left is root:
        return alt.right
    if isinstance(alt.left, ThenSpec):
        new_left = _strip_left_recursion(alt.left, root)
        return ThenSpec(kind=alt.kind, left=new_left, right=alt.right, name=None, file=None, line=None, func=None)
    raise AssertionError("Unable to strip root from left-recursive branch")


def _grammar_is_left_recursive(spec: SyntaxSpec) -> bool:
    inner = spec.inner_spec if isinstance(spec, LazySpec) else spec
    return any(_is_left_recursive(alt, spec) for alt in _flatten_choices(inner))


def _flatten_token_text(node: object) -> List[str]:
    if isinstance(node, Token):
        return [str(node.text)]
    if isinstance(node, Then):
        return _flatten_token_text(node.left) + _flatten_token_text(node.right)
    if isinstance(node, Choice):
        return _flatten_token_text(node.value) if node.value is not None else []
    if isinstance(node, Many):
        items: List[str] = []
        for child in node.value:
            items.extend(_flatten_token_text(child))
        return items
    if isinstance(node, Lazy):
        return _flatten_token_text(node.value)
    if isinstance(node, Marked):
        return _flatten_token_text(node.value)
    if isinstance(node, Collect):
        return _flatten_token_text(node.value)
    if isinstance(node, Nothing):
        return []
    return []



def test_spec_can_drive_left_recursion_elimination() -> None:
    TestSyntax = Syntax.config(tkspec=Structured(Token))
    literal = TestSyntax.literal

    Expr = TestSyntax.lazy(lambda: (Expr + literal("+") + literal("n")) | literal("n"))  # type: ignore[name-defined]

    assert _grammar_is_left_recursive(Expr.spec)

    root_spec = Expr.spec
    inner = root_spec.inner_spec if isinstance(root_spec, LazySpec) else root_spec
    alternatives = _flatten_choices(inner)

    recursive_alts = [alt for alt in alternatives if _is_left_recursive(alt, root_spec)]
    base_alts = [alt for alt in alternatives if not _is_left_recursive(alt, root_spec)]

    assert recursive_alts, "Expected at least one left-recursive alternative"
    assert base_alts, "Expected at least one non-left-recursive alternative"

    base_nodes = [TestSyntax.from_spec(alt) for alt in base_alts]
    base_syntax = base_nodes[0] if len(base_nodes) == 1 else TestSyntax.choice(*base_nodes)

    suffix_nodes = [
        TestSyntax.from_spec(_strip_left_recursion(alt, root_spec)) for alt in recursive_alts
    ]
    suffix_choice = suffix_nodes[0] if len(suffix_nodes) == 1 else TestSyntax.choice(*suffix_nodes)

    transformed = base_syntax + suffix_choice.many().optional
    from syncraft.cache import Cache

    original_ast, _ = parse_word(Expr, "n + n + n", cache=Cache())
    transformed_ast, _ = parse_word(transformed, "n + n + n", cache=Cache())

    assert _flatten_token_text(original_ast) == ["n", "+", "n", "+", "n"]
    assert _flatten_token_text(transformed_ast) == ["n", "+", "n", "+", "n"]
    assert not _grammar_is_left_recursive(transformed.spec)


def test_walk_handles_recursive_grammar() -> None:
    TestSyntax = Syntax.config(tkspec=Structured(Token))
    literal = TestSyntax.literal

    Expr = TestSyntax.lazy(lambda: (Expr + literal("+") + literal("n")) | literal("n"))  # type: ignore[name-defined]

    nodes = list(Expr.walk(max_depth=4))

    assert nodes, "Expected walk to yield at least one node"
    unique_nodes = {id(node) for _, node in nodes}
    assert len(unique_nodes) == len(nodes), "Walk should not revisit nodes in recursive grammars"
    