from __future__ import annotations




from syncraft.alphabet import Alphabet
from syncraft.fa import Builder
from syncraft.input import StreamCursor

from syncraft.parser import parse as parser_run
from syncraft.syntax import Syntax



def test_parse_text_input_without_config_infers_lexer() -> None:
    syntax = Syntax.tok("hi")

    value = parser_run(syntax=syntax, data=StreamCursor.from_data(["hi"]))

    assert value == "hi"


def test_parse_bytes_input_without_config_infers_lexer() -> None:
    syntax = Syntax.tok(b"\x01")

    value = parser_run(syntax=syntax, data=StreamCursor.from_data([b"\x01"]))
    
    assert value == b"\x01"


def test_parse_bytes_input_with_lexer_bind() -> None:
    syntax_cls = Syntax
    byte_token = syntax_cls.lex(Builder.lit(b"\x01"))

    value = parser_run(syntax=byte_token, data=StreamCursor.from_data(b"\x01"))

    assert isinstance(value, bytes)
    assert value == b"\x01"

