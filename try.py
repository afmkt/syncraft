from __future__ import annotations
from syncraft.walker import walk
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with
from syncraft.syntax import lazy, literal, token
from syncraft.parser import parse
from rich import print

def test_left_recursion()->None:
    Term = literal('n')
    Expr1 = lazy(lambda: literal('a') + Expr1 + Term | Term)
    # Expr = lazy(lambda: Expr + Term | lazy(lambda: Term))
    v, s = parse(Expr1, 'a n n n', dialect='sqlite')



def test1_simple_then() -> None:
    syntax = literal("test")
    result = walk(syntax, lambda a, s: s + (a,), ())  
    assert result == (TokenSpec.create(text='test', case_sensitive=True),)



def test() -> None:
    A = literal('a')
    B = literal('b')
    L = lazy(lambda: literal("if") >> (A | B) // literal('then'))
    l_code = 'if a then'

    def parens():
        return A + ~lazy(parens) + B
    LL = parens() | L


    # p_code = 'a a b b'
    # v, s = parse(LL, p_code, dialect='sqlite')
    # print(v.bimap(), s)


    
    # result = walk(LL, lambda a, s: s + (a,) if isinstance(a, TokenSpec) else s, ())  
    # print(result)
    # assert result == (TokenSpec.create(text='Test', case_sensitive=False),)

if __name__ == "__main__":
    test1_simple_then()