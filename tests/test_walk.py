from __future__ import annotations
from syncraft.syntax import literal
from syncraft.walker import walk
from syncraft.ast import TokenSpec


def test_walk() -> None:
    syntax = literal("test")
    result = walk(syntax, lambda a, s: s + (a,), ())  
    assert result == (TokenSpec.create(text='test', case_sensitive=True),)


def test_walk_case_insensitive() -> None:
    A = literal('a').many()
    B = literal('b').many()
    syntax = literal("if") >> (A | B) + literal('then')
    result = walk(syntax, lambda a, s: s + (a,) if isinstance(a, TokenSpec) else s, ())  
    print(result)
    assert result == (
        TokenSpec.create(text='if', case_sensitive=True),
        TokenSpec.create(text='a', case_sensitive=True),
        TokenSpec.create(text='b', case_sensitive=True),
        TokenSpec.create(text='then', case_sensitive=True),
        )
