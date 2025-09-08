from __future__ import annotations
from syncraft.walker import walk
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with, generate
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
from rich import print



def test_mutual_recursion()->None:
    A = lazy(lambda: literal('a') + B)
    B = lazy(lambda: (literal('b') + A) | literal('c'))
    # print(parse(A, 'a b a b a c', dialect='sqlite'))
    # print(generate(A))
    print(walk(A))


if __name__ == "__main__":
    test_mutual_recursion()
