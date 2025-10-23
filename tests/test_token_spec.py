from __future__ import annotations

import random
import re
from typing import Any, Type, cast

from syncraft.ast import Token
from syncraft.cache import Left, Right
from syncraft.lexer import ExtLexer, LexerResult
from syncraft.syntax import Syntax
from syncraft.token import Scalar, TokenMatcher, scalar, struct, matcher


def _build_scalar_literal_lexer() -> ExtLexer[Any]:
    scalar_spec: Scalar[str] = scalar(r"[A-Za-z]+")
    lexer_cls: Type[ExtLexer[str]] = ExtLexer.bind(tkspec=scalar_spec)  # type: ignore[type-abstract]
    literal = Syntax.config(lexer_class=lexer_cls).literal

    foo = literal("foo")
    syntax = foo

    lexer = cast(ExtLexer[Any], lexer_cls.from_kwargs(text="foo"))
    assert isinstance(lexer, ExtLexer)
    return lexer


def test_scalar_literal_supports_distinct_tags() -> None:
    lexer = _build_scalar_literal_lexer()

    foo_tags = lexer.tags()
    assert foo_tags == frozenset({r"[A-Za-z]+"})

    foo_result = lexer.match(foo_tags, "foo", 0)
    assert isinstance(foo_result, Right)
    lexeme = foo_result.value
    assert isinstance(lexeme, LexerResult)
    assert lexeme.tag == r"[A-Za-z]+"
    assert lexeme.value == "foo"

    bar_result = lexer.match(foo_tags, "bar", 0)
    assert isinstance(bar_result, Right)
    bar_lexeme = bar_result.value
    assert isinstance(bar_lexeme, LexerResult)
    assert bar_lexeme.value == "bar"

    rng = random.Random(0)
    generated = lexer.gen(r"[A-Za-z]+", rng)
    assert isinstance(generated, str)
    assert re.fullmatch(r"[A-Za-z]+", generated)


def test_scalar_explicit_token_spec_enforces_config() -> None:
    lexer_cls: Type[ExtLexer[Token]] = ExtLexer.bind(tkspec=struct(Token))
    scalar_spec: Scalar[str] = scalar(re.compile(r"[A-Z]+"))
    token = Syntax.config(lexer_class=lexer_cls).token

    syntax = token(
        token_type="IDENT",
        text=re.compile(r"[A-Z]+"),
        IDENT=scalar_spec,
    )
    lexer = cast(ExtLexer[Any], lexer_cls.from_kwargs(token_type="IDENT", text=re.compile(r"[A-Z]+"), IDENT=scalar_spec))
    assert isinstance(lexer, ExtLexer)

    tags = lexer.tags()
    assert tags == frozenset({"IDENT"})

    ok = lexer.match(tags, "FOO", 0)
    assert isinstance(ok, Right)

    bad_case = lexer.match(tags, "foo", 0)
    assert isinstance(bad_case, Left)

    rng = random.Random(1)
    generated = lexer.gen("IDENT", rng)
    assert isinstance(generated, str)
    assert re.fullmatch(r"[A-Z]+", generated)


def _token_matcher_literal_lexer() -> ExtLexer[Token]:
    matcher_spec: TokenMatcher[Token] = matcher(
        pred=lambda tok: isinstance(tok, Token) and tok.text == "ping",
        gen=lambda _tag, _rng: Token(text="ping"),
        tag="ping",
    )
    lexer_cls: Type[ExtLexer[Token]] = ExtLexer.bind(tkspec=matcher_spec)
    literal = Syntax.config(lexer_class=lexer_cls).literal
    syntax = literal("ping")
    lexer = cast(ExtLexer[Any], lexer_cls.from_kwargs(text='ping'))
    assert isinstance(lexer, ExtLexer)
    return lexer


def test_token_matcher_literal_matches_expected_token() -> None:
    lexer = _token_matcher_literal_lexer()

    tags = lexer.tags()
    assert tags == frozenset({"ping"})

    ok = lexer.match(tags, Token(text="ping"), 0)
    assert isinstance(ok, Right)

    mismatch = lexer.match(tags, Token(text="pong"), 0)
    assert isinstance(mismatch, Left)

    rng = random.Random(0)
    generated = lexer.gen("ping", rng)
    assert isinstance(generated, Token)
    assert generated.text == "ping"


def test_token_matcher_explicit_tag_registration() -> None:
    lexer_cls: Type[ExtLexer[Token]] = ExtLexer.bind(tkspec=struct(Token))
    matcher_spec: TokenMatcher[Token] = matcher(
        pred=lambda tok: isinstance(tok, Token)
        and tok.token_type == "PRED"
        and tok.text == "42",
        gen=lambda _tag, _rng: Token(text="42", token_type="PRED"),
        tag=lambda **kwargs: frozenset({kwargs.get("token_type", "PRED")}),
    )

    token = Syntax.config(tkspec=struct(Token)).token
    syntax = token(token_type="PRED", PRED=matcher_spec)
    lexer = lexer_cls.from_kwargs(token_type="PRED", PRED=matcher_spec)
    assert isinstance(lexer, ExtLexer)

    tags = lexer.tags()
    assert tags == frozenset({"PRED"})

    ok = lexer.match(tags, Token(text="42", token_type="PRED"), 0)
    assert isinstance(ok, Right)

    wrong_text = lexer.match(tags, Token(text="43", token_type="PRED"), 0)
    assert isinstance(wrong_text, Left)

    rng = random.Random(3)
    generated = lexer.gen("PRED", rng)
    assert isinstance(generated, Token)
    assert generated.text == "42"
    assert generated.token_type == "PRED"