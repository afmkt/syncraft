from __future__ import annotations

from syncraft.parser import parse_data
from syncraft.syntax import Syntax
from syncraft.algebra import Error
def test_syntax_run_returns_error_on_incomplete() -> None:
    
    literal = Syntax.lit
    syntax = literal("if")
    
    value = parse_data(syntax=syntax, data=[])

    assert isinstance(value, Error)
    assert value.message and "Cannot match token at end of input" in value.message
