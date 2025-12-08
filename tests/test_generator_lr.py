from typing import Type

import pytest

from syncraft.syntax import Syntax
from syncraft.ast import Token, Then, ThenKind, OrElse, OrElseKind, Lazy
from syncraft.generator import (
    generate_with,
    generate,
    validate,
)
from syncraft.algebra import Error
from syncraft.cache import LeftRecursionError
from syncraft.fa import Builder

SS = Syntax.set(terminal_cls=lambda *args, **kwargs: Token(*args, **{**kwargs, "custom_mapping": None}))

def tok(text: str):
    return SS.lit(text=text, case_sensitive=True)

def test_generate_with_direct_left_recursion_with_base_succeeds():
    # A := A + 'a' | 'a'
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast, bound = generate_with(A)
    # Should yield an AST (not Error) and produce a bindings mapping (possibly empty)
    assert not isinstance(ast, Error)
    assert bound is not None


def test_generate_direct_left_recursion_with_base_succeeds():
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast, bound = generate(A)
    assert not isinstance(ast, Error)
    assert bound is not None


def test_validate_direct_left_recursion_with_base_succeeds_single_token():
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    # Validate a simple token AST wrapped in OrElse RIGHT (matches base branch)
    ast, bound = validate(A, Lazy(value=OrElse(kind=OrElseKind.RIGHT, value=Token(text='a',token_type='a', custom_mapping=None), custom_mapping=None), flatten=False, custom_mapping=None))
    assert not isinstance(ast, Error)
    assert bound is not None


def test_validate_direct_left_recursion_with_base_succeeds_nested_then():
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    # Manually build an AST for "aaa" using recursive branches with explicit Choices:
    # A := (A + 'a') | 'a'
    # Structure:
    #   OrElse(LEFT,
    #     Then(BOTH,
    #       OrElse(LEFT,
    #         Then(BOTH,
    #           OrElse(RIGHT, Token('a')),  # base case A -> 'a'
    #           Token('a')
    #         )
    #       ),
    #       Token('a')
    #     )
    #   )
    inner_base = Lazy(value=OrElse(kind=OrElseKind.RIGHT, value=Token(text='a', token_type='a', custom_mapping=None), custom_mapping=None), flatten=False, custom_mapping=None)
    inner_then = Then(kind=ThenKind.BOTH, left=inner_base, right=Token(text='a', token_type='a', custom_mapping=None), custom_mapping=None)
    middle_choice = Lazy(value=OrElse(kind=OrElseKind.LEFT, value=inner_then, custom_mapping=None), flatten=False, custom_mapping=None)
    outer_then = Then(kind=ThenKind.BOTH, left=middle_choice, right=Token(text='a', token_type='a', custom_mapping=None), custom_mapping=None)
    data = Lazy(value=OrElse(kind=OrElseKind.LEFT, value=outer_then, custom_mapping=None), flatten=False, custom_mapping=None)
    ast, bound = validate(A, data)
    assert not isinstance(ast, Error)
    assert bound is not None


# SS = S
def test_generate_with_mutual_left_recursion_without_base_raises():
    # Mutual recursion with no productive base: A := B ; B := A
    A = SS.lazy(lambda: B)  # type: ignore[name-defined]
    B = SS.lazy(lambda: A)  # type: ignore[name-defined]
    with pytest.raises(LeftRecursionError):
        generate_with(A)




def test_generate_with_infers_text_lexer_without_config() -> None:
    syntax = SS.lit("hi")
    ast, bound = generate_with(syntax, seed=123)
    assert ast == Token(text="hi", custom_mapping=None)


def test_generate_with_infers_from_fabuilder_literal() -> None:
    S = Syntax.set(terminal_cls=lambda *args, **kwargs: Token(*args, **{**kwargs, "custom_mapping": None}))
    lex_syntax = S.factory("lex", Builder.lit("go").tagged("WORD"))
    ast, bound = generate_with(lex_syntax, seed=321)
    print(ast)
    assert isinstance(ast, Token)
    assert ast.token_type == "WORD"
    assert ast.text == "go"
    assert bound is not None
    