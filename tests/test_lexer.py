from __future__ import annotations

import random

from syncraft.fa import Builder, ModeAction, ModeActionEnum
from syncraft.lexer import Lexer, LexerResult, GeneratedToken, VerifiedToken
import pytest
from syncraft.ast import SyncraftError

def _lexer_with_parentheses() -> Lexer[str]:
    
    base: Builder[str] = Builder.lit("a").tagged("IDENT")
    open_paren: Builder[str] = Builder.lit("(").tagged("OPEN").act(
        ModeAction.push(mode="paren")
        
    )
    close_paren: Builder[str] = Builder.lit(")").tagged("CLOSE").act(
        ModeAction.pop("paren")
        
    )
    inner: Builder[str] = Builder.lit("b").tagged("INNER").act(
        ModeAction.of("paren")
        
    )
    return Lexer.from_builders(
        base,
        open_paren,
        close_paren,
        inner,
    )


def _collect_tokens(lexer: Lexer[str], text: str) -> list[LexerResult[str]]:
    tokens: list[LexerResult[str]] = []
    for idx, ch in enumerate(text):
        result = lexer.match(ch, idx)
        if result is None:
            continue
        if isinstance(result, LexerResult):
            if not result.skip:  # Filter out skip tokens
                tokens.append(result)
        else:
            assert False, f"Lexing failed on {ch!r}: {result}"
    return tokens


def test_mode_actions_should_emit_mode_specific_tags() -> None:
    lexer = _lexer_with_parentheses()
    tokens = _collect_tokens(lexer, "a(b)")

    observed_tags = [tok.tag for tok in tokens]
    assert observed_tags == ["IDENT", "OPEN", "INNER", "CLOSE"]

    rng = random.Random(0)
    generated = _lexer_with_parentheses().gen("OPEN", rng)
    assert generated == GeneratedToken("(", "OPEN", 1)


def test_skip_rules_should_suppress_tokens() -> None:
    
    rule_a: Builder[str] = Builder.lit("a").tagged("A")
    rule_b: Builder[str] = Builder.lit("b").tagged("B")
    whitespace: Builder[str] = Builder.lit(" ").tagged("WS").skipped()
    lexer = Lexer.from_builders(rule_a, rule_b, whitespace)

    tokens = _collect_tokens(lexer, "a b")
    assert [tok.tag for tok in tokens] == ["A", "B"]



def _lexer_with_skip() -> Lexer[str]:
    letter: Builder[str] = Builder.lit("a").tagged("A")
    skip_ws: Builder[str] = Builder.lit(" ").tagged("WS").skipped()
    return Lexer.from_builders(letter, skip_ws)


def _lexer_with_modes() -> Lexer[str]:
    base: Builder[str] = Builder.lit("a").tagged("IDENT")
    open_paren: Builder[str] = Builder.lit("(").tagged("OPEN").act(
        ModeAction.push(mode="paren")
    )
    close_paren: Builder[str] = Builder.lit(")").tagged("CLOSE").act(
        ModeAction.pop("paren")
    )
    inner: Builder[str] = Builder.lit("b").tagged("INNER").act(
        ModeAction.of("paren")
    )
    return Lexer.from_builders(base, open_paren, close_paren, inner)


def test_skip_rules_return_none_when_selected() -> None:
    lexer = _lexer_with_skip()
    results: list[LexerResult[str]] = []
    for idx, ch in enumerate(" a a"):
        out = lexer.match(ch, idx)
        if out is None:
            continue
        if isinstance(out, LexerResult):
            if not out.skip:  # Filter out skip tokens
                results.append(out)
        else:
            assert False, f"Lexing failed on {ch!r}: {out}"

    tags = [token.tag for token in results]
    assert tags == ["A", "A"]



def test_mode_actions_update_stack_in_generation() -> None:
    lexer = _lexer_with_modes()
    rng = random.Random(0)

    assert lexer.gen("OPEN", rng) == GeneratedToken("(", "OPEN", 1)
    assert lexer.current_mode is lexer.modes["paren"]

    assert lexer.gen("INNER", rng) == GeneratedToken("b", "INNER", 1)

    assert lexer.gen("CLOSE", rng) == GeneratedToken(")", "CLOSE", 1)
    assert lexer.current_mode is lexer.modes[None]


def test_pop_mode_requires_known_mode() -> None:
    lexer = _lexer_with_skip()
    with pytest.raises(SyncraftError):
        lexer.pop_mode("missing")


def test_match_reports_correct_span_boundaries() -> None:
    
    rule: Builder[str] = Builder.lit("ab").tagged("AB")
    lexer = Lexer.from_builders(rule)

    tokens = _collect_tokens(lexer, "ab")
    assert len(tokens) == 1
    token = tokens[0]

    assert token.start == 0
    assert token.end == 2


def test_greedy_rule_short_circuits_longer_match() -> None:
    
    long_rule: Builder[str] = Builder.lit("ab").tagged("LONG")
    short_rule: Builder[str] = Builder.lit("a").tagged("SHORT").with_non_greedy()
    trailing: Builder[str] = Builder.lit("b").tagged("B")

    greedy_lexer = Lexer.from_builders(long_rule, short_rule, trailing)
    tokens = _collect_tokens(greedy_lexer, "ab")
    assert [tok.tag for tok in tokens] == ["SHORT", "B"]


def test_default_lexer_still_prefers_maximal_munch() -> None:
    
    long_rule: Builder[str] = Builder.lit("ab").tagged("LONG")
    short_rule: Builder[str] = Builder.lit("a").tagged("SHORT")

    lexer = Lexer.from_builders(long_rule, short_rule)
    tokens = _collect_tokens(lexer, "ab")
    assert [tok.tag for tok in tokens] == ["LONG"]


def test_verify_accepts_full_match() -> None:
    rule: Builder[str] = Builder.lit("ab").tagged("AB")
    lexer = Lexer.from_builders(rule)

    assert lexer.verify(frozenset({"AB"}), "ab") == VerifiedToken(True, 2)
