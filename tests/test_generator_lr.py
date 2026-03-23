

import pytest

from syncraft.syntax import Syntax

from syncraft.generator import (
    generate_with,
    generate,
    validate,
)
from syncraft.algebra import Error
from syncraft.cache import LeftRecursionError
from syncraft.token import Str, Token

SS = Syntax

def tok(text: str):
    return SS.tok(Token(text=Str(text, i=True)))

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
    syntax = SS.tok(Token(text=Str("hi", i=True)))
    ast = generate_with(syntax, seed=123)
    assert ast == Token(text="hi")



    
    
