from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import NamedResult, ManyResult, OrResult, ThenResult, Error, ThenKind, Biarrow
from syncraft.parser import literal, variable, parse, Parser, Token
from syncraft.generator import TokenGen
from rich import print
import syncraft.generator as gen

def test5_nested_then_many() -> None:
    IF, THEN, END = literal("if"), literal("then"), literal("end")
    syntax = (IF.many() // THEN.many()).many() // END
    sql = "if if then end"
    ast = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax, ast)
    print("---" * 40)
    print(generated)
    # assert ast == generated
    value, bmap = generated.bimap(None)
    print(value)
    assert bmap(value) == generated



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


def test_deep_mix():
    A = literal("a").bind("a")
    B = literal("b")
    C = literal("c").bind("c")
    syntax = ((A + B) | C).many() + B
    sql = "a b a b c b"
    ast = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax, ast)
    print('---' * 40)
    print(generated)
    assert ast == generated
    value, bmap = ast.bimap(None)
    assert bmap(value) == ast

if __name__ == "__main__":
    test4_mixed_many_named()
