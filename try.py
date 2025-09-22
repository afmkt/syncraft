from __future__ import annotations
from syncraft.ast import Nothing, Token
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
from dataclasses import dataclass
import syncraft.generator as gen
from typing import Any, Callable, TypeVar, Generic, Generator, cast
from syncraft.cache import LeftRecursionError
import re
from syncraft.utils import debug_print, set_debug
from syncraft.ast import TokenClass

set_debug(True)


literal = Syntax.config(token_class = TokenClass.simple()).literal
token = Syntax.config(token_class = TokenClass.simple()).token
lazy = Syntax.config(token_class = TokenClass.simple()).lazy



def test_indirect_left_recursion_2()->None:
    """
    Grammar:
        Expr → Expr "+" Term | Term
        Term → Term "*" Factor | Factor
        Factor → "(" Expr ")" | number    
    Positive examples:
        42
        1 + 2
        3 * 4
        ( 1 )
        1 + 2 * 3
        ( 1 + 2 ) * 3
        1 + 2 + 3 * 4
    Negative examples:
        + 1
        1 *
        1 + *
        ( 1 + 2
        1 + 2 )
        ( )
        1 * ( 2 + )
    """
    NUMBER = literal(re.compile(r'\d+')).map(lambda x: int(x.text))
    PLUS = literal('+').map(lambda x: x.text)
    STAR = literal('*').map(lambda x: x.text)
    LPAREN = literal('(').map(lambda x: x.text)
    RPAREN = literal(')').map(lambda x: x.text)
    Expr = lazy(lambda: (Expr + PLUS + Term) | Term)
    Term = lazy(lambda: (Term + STAR + Factor) | Factor)
    Factor = lazy(lambda: (LPAREN + Expr + RPAREN) | NUMBER)    
            
    v, _ = parse_word(Expr, '1 + 2 * 3')
    print('Raw AST repr:', repr(v))
    if hasattr(v, 'bimap'):
        x, y = v.bimap()
        print('Simplified (bimap) AST value:', x)
        assert x == (1, '+', (2, '*', 3))
    else:
        raise AssertionError(f"Unexpected AST type without bimap: {type(v)}")
    # p, _ = y(x).bimap()
    # assert p == x
    
    # v, s = parse_word(Expr, '( 1 + 2 ) * 3')
    # x, y = v.bimap()
    # assert x == (('(', (1, '+', 2), ')'), '*', 3)
    # p, _ = y(x).bimap()
    # assert p == x

    # v, s = parse_word(Expr, '1 + ( 2 * 3 )')
    # x, y = v.bimap()
    # assert x == (1, '+', ('(', (2, '*', 3), ')'))
    # p, _ = y(x).bimap()
    # assert p == x

    # v, s = parse_word(Expr, '( ( 1 + 2 ) * 3 ) + 4 * 5 + 6')
    # x, y = v.bimap()
    # print(x)
    # assert x == (('(', (('(', (1, '+', 2), ')'), '*', 3), ')'), '+', 4), f"Unexpected AST: {x}"
    # p, _ = y(x).bimap()
    # assert p == x



def test_multi_recursion()->None:
    a = literal('a').map(lambda x: x.text).named('a')
    b = literal('b').map(lambda x: x.text).named('b')
    c = literal('c').map(lambda x: x.text).named('c')
    x = literal('x').map(lambda x: x.text).named('x')
    y = literal('y').map(lambda x: x.text).named('y')
    z = literal('z').map(lambda x: x.text).named('z')
    A = lazy(lambda: (B + x) | a).named('A')
    B = lazy(lambda: (C + y) | b).named('B')
    C = lazy(lambda: (A + z) | c).named('C')

    v, s = parse_word(A, 'a z y x')
    print(v)
    x, y = v.bimap()
    assert x == ('a', 'z', 'y', 'x')


if __name__ == "__main__":
    test_multi_recursion()
    # test_indirect_left_recursion_2()
