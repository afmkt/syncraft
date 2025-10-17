from __future__ import annotations

from syncraft.lexer import ExtLexer
from syncraft.input import Input
from syncraft.parser import parse as parser_run
from syncraft.syntax import Syntax
from syncraft.ast import Token
import pytest
from syncraft.token import Structured
def test_run_with_input_stream_handles_incomplete() -> None:
    literal = Syntax.config(lexer_class=ExtLexer.bind(token_protocol=Structured(Token))).literal
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
    assert value.value == ("if", "if")

