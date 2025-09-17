from __future__ import annotations
from syncraft.ast import Nothing, Token
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
import pytest
from syncraft.cache import LeftRecursionError
import re
from syncraft.ast import TokenClass
literal = Syntax.config(token_class = TokenClass.simple()).literal
token = Syntax.config(token_class = TokenClass.simple()).token

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
    NUMBER = literal(re.compile(r'\d+')).map(lambda x: int(x.text))
    PLUS = token(text='+')
    STAR = token(text='*')
    A = Syntax.lazy(lambda: (B >> PLUS >> A) | B)
    B = Syntax.lazy(lambda: (A >> STAR >> NUMBER) | NUMBER)
    with pytest.raises(LeftRecursionError):
        v, s = parse_word(A, '1 + 2 * 3')




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
    PLUS = token(text='+')
    STAR = token(text='*')
    LPAREN = token(text='(')
    RPAREN = token(text=')')
    Expr = Syntax.lazy(lambda: (Expr >> PLUS >> Term) | Term)
    Term = Syntax.lazy(lambda: (Term >> STAR >> Factor) | Factor)
    Factor = Syntax.lazy(lambda: (LPAREN >> Expr >> RPAREN) | NUMBER)
    v, s = parse_word(Expr, '1 + 2 * 3')
    v, s = parse_word(Expr, '(1 + 2) * 3')
    v, s = parse_word(Expr, '1 + (2 * 3)')
    v, s = parse_word(Expr, '((1 + 2) * 3) + 4 * 5 + 6')

    # print(v)



def test_indirect_left_recursion_3()->None:
    """
    Grammar:
        List → List "," Item | Item
        Item → "a" | "b"    
    Positive examples:
        a
        b
        a , b
        b , a
        a , b , a
        a , a , a
        b , b , b
        b , a , b , b
    Negative examples:
        ''
        , a
        a ,
        a , , b
        c
        , a ,
        a , b ,
        a , b ,
    """    
    A = token(text='a')
    B = token(text='b')
    Item = Syntax.lazy(lambda: A | B)
    List = Syntax.lazy(lambda: (List >> token(text=',') >> Item) | Item)
    with pytest.raises(LeftRecursionError):
        v, s = parse_word(List, 'a,b,a')



def test_indirect_left_recursion_4()->None:
    """
    Grammar:
        A → B "x" | "a"
        B → A "y" | "b"
    Positive examples:
        a
        b
        a x
        a y
        b x
        b y
        a y x
        a y b x
        b x a y
        a y a y b x x
        a x b y a x
        b y a x b y b x
    Negative examples:
        ''
        x x
        y y
        a b
        x a
        a x
        a y x b
        c
        x a y
        a y b x x
        a y b x x
    """
    A = Syntax.lazy(lambda: (B >> token(text='x')) | token(text='a'))
    B = Syntax.lazy(lambda: (A >> token(text='y')) | token(text='b'))
    with pytest.raises(LeftRecursionError):
        v, s = parse_word(A, 'a y b x')



def test_indirect_left_recursion_5()->None:
    """
    Grammar:
        Chain → Chain "->" Name | Name
        Name → identifier    
    Positive examples:
        a
        b
        c
        a -> b
        a -> b -> c
        x -> y -> z -> a -> b -> c
    Negative examples:
        ''
        -> a
        a ->
        a -> ->
        a b
        a -> b c
        a -> b ->
        a -> b -> c ->
        a -> b -> c -> ->
        -> a ->
        a -> -> b
        a --> b
        123
    """
    Name = token(text=re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*'))
    Chain = Syntax.lazy(lambda: (Chain >> token(text='->') >> Name) | Name)
    with pytest.raises(LeftRecursionError):
        v, s = parse_word(Chain, 'a -> b -> c')


def test_direct_left_recursion_2()->None:
    """
    Grammar:
        S → S S | "a"
    Positive examples:
        a
        a a
        a a a
        a a a a
    Negative examples:
        ''
        b
        ab
    """
    S = Syntax.lazy(lambda: (S >> S) | literal('a'))
    with pytest.raises(LeftRecursionError):
        v, s = parse_word(S, 'a a a')