

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
    return SS.tok(Token(text=text))

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
    

if __name__ == "__main__":
    test_generate_direct_left_recursion_with_base_succeeds()
    test_generate_with_direct_left_recursion_with_base_succeeds()