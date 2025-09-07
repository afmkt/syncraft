from __future__ import annotations
from syncraft.walker import walk
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
from rich import print


def test_recursion()->None:
    Expr1 = lazy(lambda: literal('a') + ~Expr1)
    v, s = parse(Expr1, 'a a a', dialect='sqlite')
    print(v)



def test_left_recursion()->None:
    Term = literal('n')
    Expr = lazy(lambda: Expr + Term)
    v, s = parse(Expr, 'a n', dialect='sqlite')




def test_indirect_left_recursion()->None:
    NUMBER = regex(r'\d+').map(int)
    PLUS = token(text='+')
    STAR = token(text='*')
    A = lazy(lambda: (B >> PLUS >> A) | B)
    B = lazy(lambda: (A >> STAR >> NUMBER) | NUMBER)
    v, s = parse(A, '1 + 2 * 3', dialect='sqlite')


if __name__ == "__main__":
    # test_recursion()
    # test_left_recursion()
    test_indirect_left_recursion()