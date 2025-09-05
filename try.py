from __future__ import annotations
from syncraft.parser import literal, token
from syncraft.walker import walk
from syncraft.ast import TokenSpec
from rich import print

def test_walk_case_insensitive() -> None:
    T = token()
    A = literal('a').many()
    B = literal('b').many()
    syntax = literal("if") >> (A | B) // literal('then')
    result = walk(syntax, lambda a, s: s + (a,) if isinstance(a, TokenSpec) else s, ())  
    print(result)
    assert result == (TokenSpec.create(text='Test', case_sensitive=False),)

if __name__ == "__main__":
    test_walk_case_insensitive()