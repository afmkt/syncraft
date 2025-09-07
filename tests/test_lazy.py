from __future__ import annotations
from syncraft.parser import token
import pytest
from syncraft.walker import walk
from syncraft.ast import Nothing
from syncraft.syntax import lazy, literal, regex
from syncraft.parser import parse
from syncraft.generator import TokenGen
from syncraft.cache import RecursionError
from rich import print

def test_simple_recursion()->None:
    A = lazy(lambda: literal('a') + ~A | literal('a'))
    v, s = parse(A, 'a a a', dialect='sqlite')
    print(v)
    ast1, inv = v.bimap()
    print(ast1)
    assert ast1 == (
        TokenGen.from_string('a'), 
        (
            TokenGen.from_string('a'), 
            (
                TokenGen.from_string('a'), 
                Nothing()
            )
        )
    )

def test_direct_recursion()->None:
    Expr1 = lazy(lambda: literal('a') + ~Expr1)
    v, s = parse(Expr1, 'a a a', dialect='sqlite')
    x, _ = v.bimap()
    assert x == (
        TokenGen.from_string('a'), 
        (
            TokenGen.from_string('a'), 
            (
                TokenGen.from_string('a'), 
                Nothing()
            )
        )
    )


def test_mutual_recursion()->None:
    A = lazy(lambda: literal('a') + B)
    B = lazy(lambda: (literal('b') + A) | (literal('c')))
    v, s = parse(A, 'a b a b a c', dialect='sqlite')
    print('--' * 20, "test_mutual_recursion", '--' * 20)
    print(v)
    ast1, inv = v.bimap()
    print(ast1)
    assert ast1 == (
        TokenGen.from_string('a'), 
        (
            TokenGen.from_string('b'), 
            TokenGen.from_string('a'), 
            (
                TokenGen.from_string('b'), 
                TokenGen.from_string('a'), 
                TokenGen.from_string('c')
            )
        )
    )



def test_recursion() -> None:
    A = literal('a')
    B = literal('b')
    L = lazy(lambda: literal("if") >> (A | B) // literal('then'))

    def parens():
        return A + ~lazy(parens) + B
    p_code = 'a a b b'
    LL = parens() | L
    
    v, s = parse(LL, p_code, dialect='sqlite')
    ast1, inv = v.bimap()
    print(v)
    print(ast1)
    assert ast1 == (
            TokenGen.from_string('a'), 
            (
                TokenGen.from_string('a'), 
                Nothing(), 
                TokenGen.from_string('b')
            ), 
            TokenGen.from_string('b')
        )

def test_direct_left_recursion()->None:
    Term = literal('n')
    Expr = lazy(lambda: Expr + literal('+') + Term | Term)
    with pytest.raises(RecursionError):
        v, s = parse(Expr, 'n+n+n', dialect='sqlite')



def test_indirect_left_recursion()->None:
    NUMBER = regex(r'\d+').map(int)
    PLUS = token(text='+')
    STAR = token(text='*')
    A = lazy(lambda: (B >> PLUS >> A) | B)
    B = lazy(lambda: (A >> STAR >> NUMBER) | NUMBER)
    with pytest.raises(RecursionError):
        v, s = parse(A, '1 + 2 * 3', dialect='sqlite')