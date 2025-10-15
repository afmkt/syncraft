from __future__ import annotations
from syncraft.syntax import Syntax
from rich import print

import pytest
from syncraft.ast import TokenClass
from syncraft.parser import parse_word
from syncraft.generator import validate, generate_with
from syncraft.algebra import Error
from syncraft.lexer import CacheWithLexer


def tok(text: str):
    return Syntax.token(token_class=TokenClass.simple(), text=text, case_sensitive=True)


def test():
    # Grammar: A := (A + 'a') | 'a'
    A = Syntax.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]

    # Parse concrete input "a a a"
    ast, _ = parse_word(A, 'a a a', cache=CacheWithLexer())
    assert not isinstance(ast, Error)
    print(ast)
    # Apply bimap then reconstruct the AST. Choice.bimap resets kind to None.
    x, invf = ast.bimap()  # x is a flattened tuple-like view; invf reconstructs AST with kind=None in Choice nodes
    reconstructed = invf(x)

    # validate() should succeed even when Choice.kind is None
    v1, b1 = validate(A, reconstructed)
    assert not isinstance(v1, Error)
    assert b1 is not None

    # generate_with() should also respect kind=None and succeed
    v2, b2 = generate_with(A, reconstructed)
    assert not isinstance(v2, Error)
    assert b2 is not None


def test_recursion() -> None:
    literal = Syntax.literal
    A = literal('a')
    B = literal('b')
    L = Syntax.lazy(lambda: literal("if") >> (A | B) // literal('then'))

    def parens():
        return A + ~Syntax.lazy(parens) + B
    LL = parens() | L
    
    for _, node in LL.spec.walk():
        print(node)



if __name__ == "__main__":
    test()