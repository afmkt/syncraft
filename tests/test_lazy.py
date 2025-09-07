from __future__ import annotations
from syncraft.parser import token

from syncraft.walker import walk
from syncraft.ast import Nothing
from syncraft.syntax import lazy, literal, regex
from syncraft.parser import parse
from syncraft.generator import TokenGen

from rich import print


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
    v, s = parse(Expr, 'n+n+n', dialect='sqlite')



def test_indirect_left_recursion()->None:
    NUMBER = regex(r'\d+').map(int)
    PLUS = token(text='+')
    STAR = token(text='*')
    A = lazy(lambda: (B >> PLUS >> A) | B)
    B = lazy(lambda: (A >> STAR >> NUMBER) | NUMBER)
    v, s = parse(A, '1 + 2 * 3', dialect='sqlite')