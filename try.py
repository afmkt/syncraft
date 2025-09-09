from __future__ import annotations
from syncraft.walker import walk
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with, generate
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
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
    assert ast1 == (
            TokenGen.from_string('a'), 
            (
                TokenGen.from_string('a'), 
                Nothing(), 
                TokenGen.from_string('b')
            ), 
            TokenGen.from_string('b')
        )
    x, y = inv(ast1).bimap()
    assert x == ast1

    vv, ss = generate_with(LL, y(x), restore_pruned=True)
    print(ast1)
    print(vv)
    assert vv == v

if __name__ == "__main__":
    test_recursion()
