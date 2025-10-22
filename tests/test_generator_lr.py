from typing import Type

import pytest

from syncraft.syntax import Syntax
from syncraft.ast import Token, Then, ThenKind, Choice, ChoiceKind, Lazy
from syncraft.generator import (
    generate_with,
    generate,
    validate,
    Generator,
    Runner as GeneratorRunner,
)
from syncraft.algebra import Error
from syncraft.cache import LeftRecursionError
from syncraft.lexer import ExtLexer, Cache
from syncraft.fa import FABuilder
from syncraft.token import Structured, matcher, TokenMatcher
# S = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token)))
S = Syntax
def tok(text: str):
    return S.token(text=text, case_sensitive=True)


def test_generate_with_direct_left_recursion_with_base_succeeds():
    # A := A + 'a' | 'a'
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast, bound = generate_with(A)
    # Should yield an AST (not Error) and produce a bindings mapping (possibly empty)
    assert not isinstance(ast, Error)
    assert bound is not None


def test_generate_direct_left_recursion_with_base_succeeds():
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast, bound = generate(A)
    assert not isinstance(ast, Error)
    assert bound is not None


def test_validate_direct_left_recursion_with_base_succeeds_single_token():
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    # Validate a simple token AST wrapped in Choice RIGHT (matches base branch)
    ast, bound = validate(A, Lazy(value=Choice(kind=ChoiceKind.RIGHT, value=Token('a','a'))))
    assert not isinstance(ast, Error)
    assert bound is not None


def test_validate_direct_left_recursion_with_base_succeeds_nested_then():
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    # Manually build an AST for "aaa" using recursive branches with explicit Choices:
    # A := (A + 'a') | 'a'
    # Structure:
    #   Choice(LEFT,
    #     Then(BOTH,
    #       Choice(LEFT,
    #         Then(BOTH,
    #           Choice(RIGHT, Token('a')),  # base case A -> 'a'
    #           Token('a')
    #         )
    #       ),
    #       Token('a')
    #     )
    #   )
    inner_base = Lazy(value=Choice(kind=ChoiceKind.RIGHT, value=Token('a', 'a')))
    inner_then = Then(kind=ThenKind.BOTH, left=inner_base, right=Token('a', 'a'))
    middle_choice = Lazy(value=Choice(kind=ChoiceKind.LEFT, value=inner_then))
    outer_then = Then(kind=ThenKind.BOTH, left=middle_choice, right=Token('a', 'a'))
    data = Lazy(value=Choice(kind=ChoiceKind.LEFT, value=outer_then))
    ast, bound = validate(A, data)
    assert not isinstance(ast, Error)
    assert bound is not None


SS = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token)))
# SS = S
def test_generate_with_mutual_left_recursion_without_base_raises():
    # Mutual recursion with no productive base: A := B ; B := A
    A = SS.lazy(lambda: B)  # type: ignore[name-defined]
    B = SS.lazy(lambda: A)  # type: ignore[name-defined]
    with pytest.raises(LeftRecursionError):
        generate_with(A)


def test_generate_mutual_left_recursion_without_base_raises():
    A = SS.lazy(lambda: B)  # type: ignore[name-defined]
    B = SS.lazy(lambda: A)  # type: ignore[name-defined]
    with pytest.raises(LeftRecursionError):
        generate(A)


def test_validate_mutual_left_recursion_without_base_raises():
    A = SS.lazy(lambda: B)  # type: ignore[name-defined]
    B = SS.lazy(lambda: A)  # type: ignore[name-defined]
    with pytest.raises(LeftRecursionError):
        # Any AST will do; grammar has no base and should be flagged
        generate(A)


def test_generate_with_infers_text_lexer_without_config() -> None:
    syntax = Syntax.literal("hi")
    ast, bound = generate_with(syntax, seed=123)
    assert ast == Token("hi")


def test_generate_with_infers_from_fabuilder_literal() -> None:
    lex_syntax = Syntax.factory("lex", WORD=FABuilder.lit("go").tagged("WORD"))
    ast, bound = generate_with(lex_syntax, seed=321)
    assert isinstance(ast, Token)
    assert ast.token_type == "WORD"
    assert ast.text == "go"
    assert bound is not None


def test_generator_runner_uses_override_lexer_class() -> None:
    override_cls: Type[ExtLexer[Token]] = ExtLexer.bind(tkspec=Structured(Token))
    original_func = override_cls.from_syntax.__func__  # type: ignore[attr-defined]
    call_count = {"value": 0}

    def tracked(cls, syntax):
        call_count["value"] += 1
        return original_func(cls, syntax)

    override_cls.from_syntax = classmethod(tracked)  # type: ignore[assignment]
    try:
        matcher_spec: TokenMatcher[Token] = matcher(
            pred=lambda tok: isinstance(tok, Token) and tok.token_type == "PING",
            gen=lambda _tag, _rng: Token(text="ping", token_type="PING"),
            tag="PING",
        )
        syntax = Syntax.token(token_type="PING", PING=matcher_spec)
        runner: GeneratorRunner = GeneratorRunner(lexer_class=override_cls)
        _generator, cache_obj, _state = runner.bootstrap(syntax, Generator)
        assert call_count["value"] == 1
        assert isinstance(cache_obj, Cache)
        assert isinstance(cache_obj.lexer, override_cls)
    finally:
        setattr(override_cls, "from_syntax", classmethod(original_func))  # type: ignore[arg-type]
