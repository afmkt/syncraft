from __future__ import annotations

from syncraft.ast import TokenClass
from syncraft.parser import parse_data
from syncraft.syntax import Syntax
from syncraft.algebra import Error


def test_syntax_run_returns_error_on_incomplete() -> None:
    literal = Syntax.config(token_class=TokenClass.simple()).literal
    syntax = literal("if")
    from syncraft.lexer import CacheWithLexer
    value, next_state = parse_data(syntax=syntax, tokens=[], cache=CacheWithLexer())

    assert isinstance(value, Error)
    assert next_state is None
    assert value.message and "EOF" in value.message
