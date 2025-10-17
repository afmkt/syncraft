from __future__ import annotations

from syncraft.lexer import ExtLexer
from syncraft.input import Input
from syncraft.parser import parse as parser_run
from syncraft.syntax import Syntax
from syncraft.ast import Token
import pytest

@pytest.mark.xfail(reason="Currently fails due to missing token data in spec")
def test_run_with_input_stream_handles_incomplete() -> None:
    literal = Syntax.config(lexer_class=ExtLexer.bind(token_class=Token)).literal
    syntax = literal("if").many()
    tokens = ["if", "if"]
    source = Input.from_data(tokens)

    value, state = parser_run(
        syntax=syntax,
        input=source
    )

    assert state is not None
    assert state.pending()
    assert len(value.value) == 2
    assert tuple(token.text for token in value.value) == ("if", "if")

@pytest.mark.xfail(reason="Currently fails due to missing token data in spec")
def test_run_with_input_reads_all_when_unbounded() -> None:
    literal = Syntax.config(lexer_class=ExtLexer.bind(token_class=Token)).literal
    syntax = literal("if").many()
    tokens = ["if", "if"]
    source = Input.from_data(tokens)

    value, state = parser_run(
        syntax=syntax,
        input=source
    )

    assert state is not None
    assert state.ended()
    assert len(value.value) == 2
    assert tuple(token.text for token in value.value) == ("if", "if")
