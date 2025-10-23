from __future__ import annotations

from typing import Type

from syncraft.ast import Token
from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder
from syncraft.input import Input
from syncraft.lexer import ExtLexer, Lexer
from syncraft.parser import parse as parser_run, parse_data
from syncraft.syntax import Syntax
from syncraft.token import Structured, TokenMatcher, matcher, struct
from rich import print


def test_parse_token_input_without_config_infers_extlexer() -> None:
    matcher_spec: TokenMatcher[Token] = matcher(
        pred=lambda tok: isinstance(tok, Token) and tok.token_type == "PING",
        gen=lambda _tag, _rng: Token(text="ping", token_type="PING"),
    )
    syntax = Syntax.token(PING=matcher_spec)

    tokens: list[Token] = [Token(text="ping", token_type="PING")]
    value, bound = parse_data(syntax=syntax, tokens=tokens)
    print(value)
    assert isinstance(value, Token)
    assert value.token_type == "PING"
    assert bound is not None


if __name__ == "__main__":
    test_parse_token_input_without_config_infers_extlexer()
