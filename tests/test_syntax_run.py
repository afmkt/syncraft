from __future__ import annotations

from syncraft.ast import TokenClass
from syncraft.parser import Parser, ParserState
from syncraft.syntax import Syntax, run_state
from syncraft.algebra import Error


def test_syntax_run_returns_error_on_incomplete() -> None:
    literal = Syntax.config(token_class=TokenClass.simple()).literal
    syntax = literal("if")
    state: ParserState[str] = ParserState(input=tuple(), index=0, base=0, final=False)
    from syncraft.lexer import CacheWithLexer
    value, next_state = run_state(syntax=syntax, alg=Parser, state=state, cache=CacheWithLexer())

    assert isinstance(value, Error)
    assert next_state is None
    assert value.message and "additional input" in value.message
    assert value.state == state
