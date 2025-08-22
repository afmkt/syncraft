from __future__ import annotations
from syncraft.algebra import NamedResult, ManyResult, OrResult, ThenResult, Error, ThenKind
from syncraft.parser import literal, variable, parse, Parser, Token
from syncraft.generator import TokenGen
from rich import print
import syncraft.generator as gen



def test4_mixed_many_named() -> None:
    A = literal("a").bind("x")
    B = literal("b")
    syntax = (A | B).many()
    sql = "a b a"
    ast = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap(None)
    print("---" * 40)
    print(value)
    print("---" * 40)
    print(bmap(value))
    assert bmap(value) == generated



if __name__ == "__main__":
    test4_mixed_many_named()
