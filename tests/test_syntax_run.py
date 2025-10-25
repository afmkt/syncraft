from __future__ import annotations

from syncraft.parser import parse_data
from syncraft.syntax import Syntax
from syncraft.algebra import Error
def test_syntax_run_returns_error_on_incomplete() -> None:
    # literal = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).literal
    literal = Syntax.literal
    syntax = literal("if")
    from syncraft.cache import Cache
    value, next_state = parse_data(syntax=syntax, data=[], cache=Cache())

    assert isinstance(value, Error)
    value = value.deepest
    assert next_state is None
    assert value.message and "Cannot match token at end of input" in value.message
