from __future__ import annotations

from syncraft import Error, Syntax
from syncraft.lexer import GlobalLexerBuilder


def test_skip_flag_not_applied_across_local_terminals() -> None:
    """In default LocalLexerBuilder mode, skip rules are not globally unioned."""
    _ws = Syntax.re(r"\s+", skip=True)
    expr = Syntax.lit("a") + Syntax.lit("b")

    result = expr.parse("a b")
    assert isinstance(result, Error)


def test_skip_flag_not_dropping_explicit_local_node() -> None:
    """Even explicit skip=True nodes still produce their lexical text in local mode."""
    ws = Syntax.re(r"\s+", skip=True)
    expr = Syntax.lit("a") + ws + Syntax.lit("b")

    result = expr.parse("a b")
    assert result == ("a", " ", "b")


def test_skip_flag_global_lexer_behavior_differs_from_local() -> None:
    """Global builder behavior differs; this test documents the contrast."""
    G = Syntax.set_lexer(GlobalLexerBuilder())
    _ws = G.re(r"\s+", skip=True)
    expr = G.lit("a") + G.lit("b")

    result = expr.parse("a b")
    assert not isinstance(result, Error)
