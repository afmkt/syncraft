from __future__ import annotations
from syncraft.parser import literal, token
from syncraft.walker import walk
from syncraft.ast import TokenSpec
from syncraft.syntax import lazy
from syncraft.parser import parse
from rich import print


def test() -> None:
    A = literal('a')
    B = literal('b')
    L = lazy(lambda: literal("if") >> (A | B) // literal('then'))
    l_code = 'if a then'

    def parens():
        return A + ~lazy(parens) + B
    p_code = 'a a b b'
    LL = parens() | L

    v, s = parse(LL, p_code, dialect='sqlite')
    print(v.bimap(), s)

