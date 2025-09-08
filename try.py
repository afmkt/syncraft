from __future__ import annotations
from syncraft.walker import walk
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with, generate
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
from rich import print





def test_indirect_left_recursion()->None:
    NUMBER = regex(r'\d+').map(int).named('NUMBER')
    PLUS = token(text='+').named('PLUS')
    STAR = token(text='*').named('STAR')
    A = lazy(lambda: (B >> PLUS >> A) | B).named('A')
    B = lazy(lambda: (A >> STAR >> NUMBER) | NUMBER).named('B')
    
    v, s = parse(A, '1 + 2 * 3', dialect='sqlite')   
if __name__ == "__main__":
    test_indirect_left_recursion()
