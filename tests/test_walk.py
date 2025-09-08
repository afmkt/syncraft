from __future__ import annotations
from syncraft.syntax import literal
from syncraft.walker import walk
from syncraft.ast import TokenSpec


def test_walk() -> None:
    syntax = literal("test")
    result = walk(syntax)  
    print(result)

def test_walk_case_insensitive() -> None:
    A = literal('a').many()
    B = literal('b').many()
    syntax = literal("if") >> (A | B) + literal('then')
    result = walk(syntax)  
    print(result)
