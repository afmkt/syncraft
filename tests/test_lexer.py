from __future__ import annotations

import random

from syncraft.fa import Builder, ModeAction
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
            tokens.append(result)
        else:
            assert False, f"Lexing failed on {ch!r}: {result}"
    return tokens




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




def test_match_reports_correct_span_boundaries() -> None:
    
    rule: Builder[str] = Builder.lit("ab").tagged("AB")
    lexer = Lexer.from_builders(rule)

    tokens = _collect_tokens(lexer, "ab")
    assert len(tokens) == 1
    token = tokens[0]

    assert token.start == 0
    assert token.end == 2



def test_verify_accepts_full_match() -> None:
    rule: Builder[str] = Builder.lit("ab").tagged("AB")
    lexer = Lexer.from_builders(rule)

    assert lexer.verify("ab") == VerifiedToken(True, 2)
