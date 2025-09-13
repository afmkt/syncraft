from __future__ import annotations
from syncraft.ast import Nothing, Token
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
import pytest
from syncraft.cache import LeftRecursionError
import re
from syncraft.ast import TokenClass
literal = Syntax.config(TokenClass.simple()).literal
token = Syntax.config(TokenClass.simple()).token

def from_string(string: str) -> Token:
    return Token( text=string)



def test_simple_recursion()->None:
    A = Syntax.lazy(lambda: literal('a') + ~A | literal('a'))
    v, s = parse_word(A, 'a a a')
    # print(v)
    ast1, inv = v.bimap()
    # print(ast1)
    assert ast1 == (
        from_string('a'), 
        (
            from_string('a'), 
            (
                from_string('a'), 
                Nothing()
            )
        )
    )
    # print(v)
    # print(ast1)    
    # print(inv(ast1))
    x, y = inv(ast1).bimap()
    assert x == ast1

    vv, ss = generate_with(A, y(x))
    assert vv == v


def test_direct_recursion()->None:
    Expr1 = Syntax.lazy(lambda: literal('a') + ~Expr1)
    v, s = parse_word(Expr1, 'a a a')
    x, _ = v.bimap()
    assert x == (
        from_string('a'), 
        (
            from_string('a'), 
            (
                from_string('a'), 
                Nothing()
            )
        )
    )


def test_mutual_recursion()->None:
    A = Syntax.lazy(lambda: literal('a') + B)
    B = Syntax.lazy(lambda: (literal('b') + A) | (literal('c')))
    v, s = parse_word(A, 'a b a b a c')
    # print('--' * 20, "test_mutual_recursion", '--' * 20)
    # print(v)
    ast1, inv = v.bimap()
    # print(ast1)
    assert ast1 == (
        from_string('a'), 
        (
            from_string('b'), 
            from_string('a'), 
            (
                from_string('b'), 
                from_string('a'), 
                from_string('c')
            )
        )
    )

    # print(v)
    # print(ast1)    
    # print(inv(ast1))
    x, y = inv(ast1).bimap()
    assert x == ast1

    vv, ss = generate_with(A, y(x))
    assert vv == v


def test_recursion() -> None:
    A = literal('a')
    B = literal('b')
    L = Syntax.lazy(lambda: literal("if") >> (A | B) // literal('then'))

    def parens():
        return A + ~Syntax.lazy(parens) + B
    p_code = 'a a b b'
    LL = parens() | L
    
    v, s = parse_word(LL, p_code)
    ast1, inv = v.bimap()
    assert ast1 == (
            from_string('a'), 
            (
                from_string('a'), 
                Nothing(), 
                from_string('b')
            ), 
            from_string('b')
        )
    # print(v)
    # print(ast1)    
    # print(inv(ast1))
    x, y = inv(ast1).bimap()
    assert x == ast1

    vv, ss = generate_with(LL, y(x))
    assert vv == v




def test_direct_left_recursion()->None:
    Term = literal('n')
    Expr = Syntax.lazy(lambda: Expr + literal('+') + Term | Term)
    with pytest.raises(LeftRecursionError):
        v, s = parse_word(Expr, 'n+n+n')



def test_indirect_left_recursion()->None:
    NUMBER = literal(re.compile(r'\d+')).map(int)
    PLUS = token(text='+')
    STAR = token(text='*')
    A = Syntax.lazy(lambda: (B >> PLUS >> A) | B)
    B = Syntax.lazy(lambda: (A >> STAR >> NUMBER) | NUMBER)
    with pytest.raises(LeftRecursionError):
        v, s = parse_word(A, '1 + 2 * 3')