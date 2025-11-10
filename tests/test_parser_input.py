from __future__ import annotations

from typing import Type

from syncraft.ast import Token
from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder
from syncraft.input import StreamCursor
from syncraft.lexer import ExtLexer, Lexer
from syncraft.parser import parse as parser_run, parse_data
from syncraft.syntax import Syntax
from syncraft.token import Structured, TokenMatcher, matcher, struct


def test_parse_text_input_without_config_infers_lexer() -> None:
    syntax = Syntax.literal("hi")

    value, state = parser_run(syntax=syntax, data=StreamCursor.from_data(["hi"]), cache=None)

    assert value == "hi"
    assert state is not None
    assert state.ended


def test_parse_bytes_input_without_config_infers_lexer() -> None:
    syntax = Syntax.token(text=b"\x01")

    value, state = parser_run(syntax=syntax, data=StreamCursor.from_data([b"\x01"]), cache=None)
    
    assert value == b"\x01"
    assert state is not None
    assert state.ended


def test_parse_token_input_without_config_infers_extlexer() -> None:
    matcher_spec: TokenMatcher[Token] = matcher(
        pred=lambda tok: isinstance(tok, Token) and tok.token_type == "PING",
        gen=lambda _tag, _rng: Token(text="ping", token_type="PING")
    )
    syntax = Syntax.token(PING=matcher_spec)

    tokens: list[Token] = [Token(text="ping", token_type="PING")]
    value, bound = parse_data(syntax=syntax, data=tokens, cache=None)

    assert isinstance(value, Token)
    assert value.token_type == "PING"
    assert bound is not None


def test_run_with_input_stream_handles_incomplete() -> None:
    literal = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).literal
    syntax = literal("if").many()
    tokens = ["if", "if"]
    source = StreamCursor.from_data(tokens)

    value, state = parser_run(
        syntax=syntax,
        data=source,
        cache=None
    )

    assert state is not None
    assert state.ended
    assert len(value.value) == 2
    assert value.value == ("if", "if")


def test_parse_list_accepts_token_spec_from_token_call() -> None:
    lexer_cls: Type[ExtLexer[Token]] = ExtLexer.bind(tkspec=struct(Token))
    token = Syntax.config(lexer_class=lexer_cls).token
    matcher_spec: TokenMatcher[Token] = matcher(
        pred=lambda tok: isinstance(tok, Token) and tok.token_type == "PING" and tok.text == "ping",
        gen=lambda _tag, _rng: Token(text="ping", token_type="PING"),
        tag="PING",
    )
    syntax = token(token_type="PING", PING=matcher_spec)

    tokens: list[Token] = [Token(text="ping", token_type="PING")]
    value, bound = parse_data(syntax=syntax, data=tokens, cache=None)

    assert isinstance(value, Token)
    assert value.text == "ping"
    assert value.token_type == "PING"
    assert bound is not None


def test_parse_string_input_with_lexer_bind() -> None:
    universe: CodeUniverse[str] = CodeUniverse.ascii()
    lexer_cls: Type[Lexer[str]] = Lexer.bind(universe=universe)
    syntax_cls = Syntax.config(lexer_class=lexer_cls)
    word = syntax_cls.lex(WORD=FABuilder.lit("hi").tagged("WORD"))

    value, state = parser_run(syntax=word, data=StreamCursor.from_data("hi"), cache=None)

    assert isinstance(value, Token)
    assert value.token_type == "WORD"
    assert value.text == "hi"
    assert state is not None
    assert state.ended


def test_parse_bytes_input_with_lexer_bind() -> None:
    syntax_cls = Syntax.config(universe=CodeUniverse.byte())
    byte_token = syntax_cls.lex(BYTE=FABuilder.lit(b"\x01").tagged("BYTE"))

    value, state = parser_run(syntax=byte_token, data=StreamCursor.from_data(b"\x01"), cache=None)

    assert isinstance(value, Token)
    assert value.token_type == "BYTE"
    assert isinstance(value.text, bytes)
    assert value.text == b"\x01"
    assert state is not None
    assert state.ended

