from __future__ import annotations
from syncraft.ast import Nothing, TokenSpec, Token
from syncraft.syntax import lazy
from syncraft.parser import parse_sql, literal, regex, token
from syncraft.generator import generate_with
from syncraft.sqlglot_adapter import SQLGLOT_TokenType as TokenType, SQLGLOT_AVAILABLE
import pytest
from syncraft.cache import LeftRecursionError
if not SQLGLOT_AVAILABLE:  # pragma: no cover - conditional skip
    pytest.skip("sqlglot not installed; skipping sqlglot-dependent tests", allow_module_level=True)



def from_string(string: str) -> Token:
    tt = TokenSpec.guess_type(string, 
                                _type=TokenType, 
                                escape_type=TokenType.VAR, 
                                token_type=None, 
                                case_sensitive=False)
    return Token(token_type=tt, text=string)



def test_simple_recursion()->None:
    A = lazy(lambda: literal('a') + ~A | literal('a'))
    v, s = parse_sql(A, 'a a a', dialect='sqlite')
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
    Expr1 = lazy(lambda: literal('a') + ~Expr1)
    v, s = parse_sql(Expr1, 'a a a', dialect='sqlite')
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
    A = lazy(lambda: literal('a') + B)
    B = lazy(lambda: (literal('b') + A) | (literal('c')))
    v, s = parse_sql(A, 'a b a b a c', dialect='sqlite')
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
    L = lazy(lambda: literal("if") >> (A | B) // literal('then'))

    def parens():
        return A + ~lazy(parens) + B
    p_code = 'a a b b'
    LL = parens() | L
    
    v, s = parse_sql(LL, p_code, dialect='sqlite')
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
    Expr = lazy(lambda: Expr + literal('+') + Term | Term)
    with pytest.raises(LeftRecursionError):
        v, s = parse_sql(Expr, 'n+n+n', dialect='sqlite')



def test_indirect_left_recursion()->None:
    NUMBER = regex(r'\d+').map(int)
    PLUS = token(text='+')
    STAR = token(text='*')
    A = lazy(lambda: (B >> PLUS >> A) | B)
    B = lazy(lambda: (A >> STAR >> NUMBER) | NUMBER)
    with pytest.raises(LeftRecursionError):
        v, s = parse_sql(A, '1 + 2 * 3', dialect='sqlite')