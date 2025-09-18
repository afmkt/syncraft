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
    debug_print(v)
    debug_print(s)

def test_fake_left_recovery()->None:
    Expr1 = Syntax.lazy(lambda: ~Expr1 + literal('a'))
    v, s = parse_word(Expr1, 'a a a')
    debug_print(v)
    debug_print(s)

def test_left_recursion_error()->None:
    """
    need better error message here, currently it is
    LeftRecursionError(), should take the stack into consideration
    """
    Expr1 = Syntax.lazy(lambda: Expr1 + literal('a'))
    v, s = parse_word(Expr1, 'a a a')
    debug_print(v)
    debug_print(s)


def test_left_recursion_recover()->None:
    a = literal('a')
    Expr1 = Syntax.lazy(lambda: (Expr1 + a) | a)
    v, s = parse_word(Expr1, 'a a a')
    debug_print("---" * 20, "Parsed AST", "---" * 20)
    debug_print(v)


def test_indirect_left_recursion_error()->None:
    A = Syntax.lazy(lambda: ~B + literal('a'))
    B = Syntax.lazy(lambda: ~A + literal('b'))
    v, s = parse_word(A, 'a b a b a')


def test_indirect_left_recursion_recover()->None:
    A = Syntax.lazy(lambda: ~B + literal('a') | literal('a'))
    B = Syntax.lazy(lambda: ~A + literal('b') | literal('b'))
    v, s = parse_word(A, 'a b a b a')    


def test_to() -> None:
    @dataclass
    class IfThenElse:
        condition: Any
        then: Any
        otherwise: Any

    @dataclass
    class While:
        condition:Any
        body:Any

    WHILE = literal("while")
    IF = literal("if")
    ELSE = literal("else")
    THEN = literal("then")
    END = literal("end")
    A = literal('a')
    B = literal('b')
    C = literal('c')
    D = literal('d')
    M = literal(',')
    var = A | B | C | D
    condition = var.sep_by(M).mark('condition') 
    ifthenelse = (IF >> condition
              // THEN 
              + var.sep_by(M).mark('then') 
              // ELSE 
              + var.sep_by(M).mark('otherwise') 
              // END).to(IfThenElse).many()
    syntax = (WHILE >> condition
            + ifthenelse.mark('body')
            // ~END).to(While)
    sql = 'while b if a , b then c , d else a , d end if a , b then c , d else a , d end'
    ast, bound = parse_word(syntax, sql)
    # debug_print(ast)
    g, bound = gen.generate_with(syntax, ast, restore_pruned=True)
    assert ast == g
    x, f = g.bimap()
    # debug_print(1, x)
    u,v = gen.generate_with(syntax, f(x), restore_pruned=True)
    assert u == ast
    x.body.append(x.body[0])
    # debug_print(2, x)
    # debug_print(f(x))
    ast2, bound = gen.generate_with(syntax, f(x), restore_pruned=True) 
    # debug_print(ast2)
    y, fy = ast2.bimap()
    # debug_print(3, y)
    assert y == x
    u, v = gen.generate_with(syntax, fy(y), restore_pruned=True)
    assert u == ast2

if __name__ == "__main__":
    # test_to()
    # test_direct_recursion()
    # test_mutual_recursion()
    # test_left_recursion_error()
    # test_fake_left_recursion()
    test_left_recursion_recover()
    # test_indirect_left_recursion_error()
    # test_indirect_left_recursion_recover()