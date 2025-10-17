from __future__ import annotations

from syncraft.lexer import ExtLexer
from syncraft.parser import parse_data
from syncraft.syntax import Syntax
from syncraft.algebra import Error
from syncraft.ast import Token
from syncraft.token import Structured
def test_syntax_run_returns_error_on_incomplete() -> None:
    literal = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).literal
    syntax = literal("if")
    from syncraft.lexer import CacheWithLexer
    value, next_state = parse_data(syntax=syntax, tokens=[], cache=CacheWithLexer())

    assert isinstance(value, Error)
    assert next_state is None
    assert value.message and "Cannot match token at end of input" in value.message
