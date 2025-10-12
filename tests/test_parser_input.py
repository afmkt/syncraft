from __future__ import annotations

from syncraft.ast import TokenClass
from syncraft.input import Input
from syncraft.parser import Parser, run as parser_run, word_lexer
from syncraft.syntax import Syntax
from syncraft.charset import CodeUniverse

def test_run_with_input_stream_handles_incomplete() -> None:
    literal = Syntax.config(token_class=TokenClass.simple()).literal
    syntax = literal("if").many()
    tokens = word_lexer("if if")
    source = Input.from_data(tokens)

    value, state = parser_run(
        syntax=syntax,
        alg=Parser,
        source=source,
        chunk_size=1,
        universe=CodeUniverse.ascii()
    )

    assert state is not None
    assert state.pending()
    assert len(value.value) == 2
    assert tuple(token.text for token in value.value) == ("if", "if")


def test_run_with_input_reads_all_when_unbounded() -> None:
    literal = Syntax.config(token_class=TokenClass.simple()).literal
    syntax = literal("if").many()
    tokens = word_lexer("if if")
    source = Input.from_data(tokens)

    value, state = parser_run(
        syntax=syntax,
        alg=Parser,
        source=source,
        universe=CodeUniverse.ascii()
    )

    assert state is not None
    assert state.ended()
    assert len(value.value) == 2
    assert tuple(token.text for token in value.value) == ("if", "if")
