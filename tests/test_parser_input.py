from __future__ import annotations

from typing import Type

from syncraft.ast import Token
from syncraft.alphabet import Alphabet, AlphabetProtocol
from syncraft.fa import Builder
from syncraft.input import StreamCursor
from syncraft.lexer import ExtLexer, Lexer
from syncraft.parser import parse as parser_run, parse_data
from syncraft.syntax import Syntax

import pytest

def test_parse_text_input_without_config_infers_lexer() -> None:
    syntax = Syntax.lit("hi")

    value, state = parser_run(syntax=syntax, data=StreamCursor.from_data(["hi"]), cache=None)

    assert value == "hi"
    assert state is not None
    assert state.ended


def test_parse_bytes_input_without_config_infers_lexer() -> None:
    syntax = Syntax.lit(text=b"\x01")

    value, state = parser_run(syntax=syntax, data=StreamCursor.from_data([b"\x01"]), cache=None)
    
    assert value == b"\x01"
    assert state is not None
    assert state.ended


def test_parse_bytes_input_with_lexer_bind() -> None:
    syntax_cls = Syntax.config(alphabet=Alphabet(bytes))
    byte_token = syntax_cls.lex(Builder.lit(b"\x01").tagged("BYTE"))

    value, state = parser_run(syntax=byte_token, data=StreamCursor.from_data(b"\x01"), cache=None)

    assert isinstance(value, Token)
    assert value.token_type == "BYTE"
    assert isinstance(value.text, bytes)
    assert value.text == b"\x01"
    assert state is not None
    assert state.ended

