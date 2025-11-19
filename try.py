from __future__ import annotations
import pytest
from dataclasses import dataclass, replace

from syncraft.cache import Cache
from syncraft.regex import Quantifier
from syncraft.charset import CharSet
from syncraft.syntax import Syntax
from syncraft.algebra import Error
from syncraft.alphabet import CodepointError
import random
import string
import re
# from rich import print

from typing import Type

from syncraft.ast import Token
from syncraft.fa import Builder
from syncraft.input import StreamCursor
from syncraft.lexer import ExtLexer, Lexer
from syncraft.parser import parse as parser_run, parse_data
from syncraft.syntax import Syntax
from syncraft.token import Structured, TokenMatcher, matcher, struct


from syncraft.fa import NFA, DFA
from syncraft.alphabet import Alphabet
from syncraft.parser import  parse_word
import syncraft.generator as gen
from rich import print
from syncraft.parser import parse_word

from syncraft.regex import benchmark_fair, verify



    

def test1_simple_then() -> None:
    A, B, C = Syntax.literal("a"), Syntax.literal("b"), Syntax.literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap
    # print(value)
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


def test_parse_bytes_input_with_lexer_bind() -> None:
    syntax_cls = Syntax.config(alphabet=Alphabet(bytes))
    byte_token = syntax_cls.lex(BYTE=Builder.lit(b"\x01"))

    value, state = parser_run(syntax=byte_token, data=StreamCursor.from_data(b"\x01"), cache=None)

    assert isinstance(value, Token)
    assert value.token_type == "BYTE"
    assert isinstance(value.text, bytes)
    assert value.text == b"\x01"
    assert state is not None
    assert state.ended

if __name__ == "__main__":
    benchmark_fair()
    # test1_simple_then()
