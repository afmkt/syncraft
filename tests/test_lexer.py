from __future__ import annotations

import random

from syncraft.cache import Left, Right
from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder, ModeAction, ModeActionEnum
from syncraft.lexer import Lexer, LexerResult


def _lexer_with_parentheses() -> Lexer[str]:
    universe: CodeUniverse[str] = CodeUniverse.ascii()
    base: FABuilder[str] = FABuilder.lit("a").tagged("IDENT")
    open_paren: FABuilder[str] = FABuilder.lit("(").tagged("OPEN").act(
        ModeAction(ModeActionEnum.PUSH, mode="paren")
    )
    close_paren: FABuilder[str] = FABuilder.lit(")").tagged("CLOSE").act(
        ModeAction(ModeActionEnum.POP, mode="paren")
    )
    inner: FABuilder[str] = FABuilder.lit("b").tagged("INNER").act(
        ModeAction(ModeActionEnum.BELONG, mode="paren")
    )
    return Lexer.from_builders(
        universe,
        base,
        open_paren,
        close_paren,
        inner,
    )


def _collect_tokens(lexer: Lexer[str], text: str) -> list[LexerResult[str]]:
    tokens: list[LexerResult[str]] = []
    for idx, ch in enumerate(text):
        result = lexer.match(ch, idx)
        assert not isinstance(result, Left), f"Lexing failed on {ch!r}: {result}"
        if isinstance(result, Right) and result.value is not None:
            tokens.append(result.value)
    return tokens


def test_mode_actions_should_emit_mode_specific_tags() -> None:
    lexer = _lexer_with_parentheses()
    tokens = _collect_tokens(lexer, "a(b)")

    observed_tags = [tok.tag for tok in tokens]
    assert observed_tags == ["IDENT", "OPEN", "INNER", "CLOSE"]

    rng = random.Random(0)
    generated = _lexer_with_parentheses().gen("OPEN", rng)
    assert generated == "("


def test_skip_rules_should_suppress_tokens() -> None:
    universe: CodeUniverse[str] = CodeUniverse.ascii()
    rule_a: FABuilder[str] = FABuilder.lit("a").tagged("A")
    rule_b: FABuilder[str] = FABuilder.lit("b").tagged("B")
    whitespace: FABuilder[str] = FABuilder.lit(" ").tagged("WS").skipped()
    lexer = Lexer.from_builders(universe, rule_a, rule_b, whitespace)

    tokens = _collect_tokens(lexer, "a b")
    assert [tok.tag for tok in tokens] == ["A", "B"]
