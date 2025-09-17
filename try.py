from __future__ import annotations
from syncraft.ast import Nothing, Token
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax

from syncraft.cache import LeftRecursionError
import re
from rich import print
from syncraft.ast import TokenClass
literal = Syntax.config(token_class = TokenClass.simple()).literal


def test_direct_recursion()->None:
    Expr1 = Syntax.lazy(lambda: literal('a') + ~Expr1)
    v, s = parse_word(Expr1, 'a a a')
    x, _ = v.bimap()
    assert x == (
        Token( text='a'), 
        (
            Token( text='a'), 
            (
                Token( text='a'), 
                Nothing()
            )
        )
    )

def test_mutual_recursion()->None:
    A = Syntax.lazy(lambda: literal('a') + ~B | literal('a'))
    B = Syntax.lazy(lambda: literal('b') + ~A | literal('b'))
    v, s = parse_word(A, 'a b a b a')
    ast1, inv = v.bimap()
    assert ast1 == (
        Token( text='a'), 
        (
            Token( text='b'), 
            (
                Token( text='a'), 
                (
                    Token( text='b'), 
                    (
                        Token( text='a'), 
                        Nothing()
                    )
                )
            )
        )
    )
    x, y = inv(ast1).bimap()
    assert x == ast1
    vv, ss = generate_with(A, y(x))
    assert vv == v

def test_fake_left_recursion()->None:
    Expr1 = Syntax.lazy(lambda: ~Expr1 + literal('a'))
    v, s = parse_word(Expr1, 'a a a')
    print(v)
    print(s)

def test_fake_left_recovery()->None:
    Expr1 = Syntax.lazy(lambda: ~Expr1 + literal('a'))
    v, s = parse_word(Expr1, 'a a a')
    print(v)
    print(s)

def test_left_recursion_error()->None:
    """
    need better error message here, currently it is
    LeftRecursionError(), should take the stack into consideration
    """
    Expr1 = Syntax.lazy(lambda: Expr1 + literal('a'))
    v, s = parse_word(Expr1, 'a a a')
    print(v)
    print(s)


def test_left_recursion_recover()->None:
    a = literal('a')
    Expr1 = Syntax.lazy(lambda: (Expr1 + a) | a)
    v, s = parse_word(Expr1, 'a a a')
    print("---" * 100)
    print(v)
    print(s)


def test_indirect_left_recursion_error()->None:
    A = Syntax.lazy(lambda: ~B + literal('a'))
    B = Syntax.lazy(lambda: ~A + literal('b'))
    v, s = parse_word(A, 'a b a b a')


def test_indirect_left_recursion_recover()->None:
    A = Syntax.lazy(lambda: ~B + literal('a') | literal('a'))
    B = Syntax.lazy(lambda: ~A + literal('b') | literal('b'))
    v, s = parse_word(A, 'a b a b a')    


if __name__ == "__main__":
    # test_direct_recursion()
    # test_mutual_recursion()
    # test_left_recursion_error()
    # test_fake_left_recursion()
    test_left_recursion_recover()
    # test_indirect_left_recursion_error()
    # test_indirect_left_recursion_recover()