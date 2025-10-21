from __future__ import annotations

import random

from syncraft.cache import Left, Right
from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder, ModeAction, ModeActionEnum
from syncraft.lexer import Lexer, LexerResult
import pytest
from syncraft.ast import SyncraftError

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
        result = lexer.match(frozenset(),ch, idx)
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



def _lexer_with_skip() -> Lexer[str]:
    universe: CodeUniverse[str] = CodeUniverse.ascii()
    letter: FABuilder[str] = FABuilder.lit("a").tagged("A")
    skip_ws: FABuilder[str] = FABuilder.lit(" ").tagged("WS").skipped()
    return Lexer.from_builders(universe, letter, skip_ws)


def _lexer_with_modes() -> Lexer[str]:
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
    return Lexer.from_builders(universe, base, open_paren, close_paren, inner)


def test_skip_rules_return_none_when_selected() -> None:
    lexer = _lexer_with_skip()
    results: list[LexerResult[str]] = []
    for idx, ch in enumerate(" a a"):
        out = lexer.match(frozenset(), ch, idx)
        assert not isinstance(out, Left), f"Lexing produced error at {idx}: {out}"
        if isinstance(out, Right) and out.value is not None:
            results.append(out.value)

    tags = [token.tag for token in results]
    assert tags == ["A", "A"]


def test_mode_actions_update_stack_in_generation() -> None:
    lexer = _lexer_with_modes()
    rng = random.Random(0)

    assert lexer.gen("OPEN", rng) == "("
    assert lexer.current_mode is lexer.modes["paren"]

    assert lexer.gen("INNER", rng) == "b"

    assert lexer.gen("CLOSE", rng) == ")"
    assert lexer.current_mode is lexer.modes[None]


def test_pop_mode_requires_known_mode() -> None:
    lexer = _lexer_with_skip()
    with pytest.raises(SyncraftError):
        lexer.pop_mode("missing")


def test_match_reports_correct_span_boundaries() -> None:
    universe: CodeUniverse[str] = CodeUniverse.ascii()
    rule: FABuilder[str] = FABuilder.lit("ab").tagged("AB")
    lexer = Lexer.from_builders(universe, rule)

    tokens = _collect_tokens(lexer, "ab")
    assert len(tokens) == 1
    token = tokens[0]

    assert token.start == 0
    assert token.end == 2


def test_greedy_rule_short_circuits_longer_match() -> None:
    universe: CodeUniverse[str] = CodeUniverse.ascii()
    long_rule: FABuilder[str] = FABuilder.lit("ab").tagged("LONG")
    short_rule: FABuilder[str] = FABuilder.lit("a", tag="SHORT", non_greedy=True)
    trailing: FABuilder[str] = FABuilder.lit("b").tagged("B")

    greedy_lexer = Lexer.from_builders(universe, long_rule, short_rule, trailing)
    tokens = _collect_tokens(greedy_lexer, "ab")
    assert [tok.tag for tok in tokens] == ["SHORT", "B"]


def test_default_lexer_still_prefers_maximal_munch() -> None:
    universe: CodeUniverse[str] = CodeUniverse.ascii()
    long_rule: FABuilder[str] = FABuilder.lit("ab").tagged("LONG")
    short_rule: FABuilder[str] = FABuilder.lit("a").tagged("SHORT")

    lexer = Lexer.from_builders(universe, long_rule, short_rule)
    tokens = _collect_tokens(lexer, "ab")
    assert [tok.tag for tok in tokens] == ["LONG"]
