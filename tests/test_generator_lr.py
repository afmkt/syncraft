from typing import Type

import pytest

from syncraft.syntax import Syntax
from syncraft.ast import Token, Seq, Alt, Lazy
from syncraft.generator import (
    generate_with,
    generate,
    validate,
)
from syncraft.algebra import Error
from syncraft.cache import LeftRecursionError
from syncraft.fa import Builder

SS = Syntax.set(terminal_cls=Token)

def tok(text: str):
    return SS.tok(text=text, case_sensitive=True)

def test_generate_with_direct_left_recursion_with_base_succeeds():
    # A := A + 'a' | 'a'
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast = generate_with(A)
    # Should yield an AST (not Error) and produce a bindings mapping (possibly empty)
    assert not isinstance(ast, Error)
    


def test_generate_direct_left_recursion_with_base_succeeds():
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast = generate(A)
    assert not isinstance(ast, Error)
    



def test_validate_direct_left_recursion_with_base_succeeds_single_token():
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast = validate(A, (Token(text='a'), Token(text='a')))
    assert not isinstance(ast, Error)
    


def test_validate_direct_left_recursion_with_base_succeeds_nested_then():
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast = validate(A, Token(text='a'))
    assert not isinstance(ast, Error)
    


# SS = S
def test_generate_with_mutual_left_recursion_without_base_raises():
    # Mutual recursion with no productive base: A := B ; B := A
    A = SS.lazy(lambda: B)  # type: ignore[name-defined]
    B = SS.lazy(lambda: A)  # type: ignore[name-defined]
    with pytest.raises(LeftRecursionError):
        generate_with(A)




def test_generate_with_infers_text_lexer_without_config() -> None:
    syntax = SS.tok("hi")
    ast = generate_with(syntax, seed=123)
    assert ast == Token(text="hi")


def test_generate_with_infers_from_fabuilder_literal() -> None:
    S = Syntax.set(terminal_cls=Token)
    lex_syntax = S.factory("lex", Builder.lit("go").tagged("WORD"))
    ast = generate_with(lex_syntax, seed=321)
    print(ast)
    assert isinstance(ast, Token)
    assert ast.token_type == "WORD" 
    assert ast.text == "go"


def test_validate_lex_token_uses_varify_full_match() -> None:
    S = Syntax.set(terminal_cls=Token)
    lex_syntax = S.factory("lex", Builder.lit("ab").tagged("AB"))

    ast = validate(lex_syntax, Token(text="ab", token_type="AB"))
    assert isinstance(ast, Token)
    assert ast.token_type == "AB"
    assert ast.text == "ab"
    
    