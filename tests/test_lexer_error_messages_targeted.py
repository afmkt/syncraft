from __future__ import annotations

from syncraft.fa import Builder
from syncraft.lexer import Lexer
from syncraft.lexerprotocol import LexerError


def test_summarize_expected_large_set_is_compact() -> None:
    values = frozenset({f"x{i}" for i in range(11)})
    summary = Lexer._summarize_expected(values)

    assert summary.startswith("one of ")
    assert summary.endswith("11 valid inputs")
    assert "frozenset(" not in summary


def test_match_mismatch_message_is_compact() -> None:
    lexer: Lexer[str] = Lexer.from_builders(Builder.lit("a").tagged("A"))

    result = lexer.match("\\", 0)

    assert isinstance(result, LexerError)
    assert "Lexing mismatch '\\' at index 0, expected 'a'" == result.message
    assert "frozenset(" not in result.message
