from __future__ import annotations
from syncraft.parser import literal, variable, parse, Parser
from syncraft.ast import AST
import syncraft.generator as gen
from typing import Any
from rich import print


def test1_simple_then() -> None:
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast = parse(syntax(Parser), sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap(None)
    print(value)
    assert bmap(value) == generated


def test2_named_results() -> None:
    A, B = literal("a").bind("x").bind('z'), literal("b").bind("y")
    syntax = A // B
    sql = "a b"
    ast = parse(syntax(Parser), sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap(None)
    print(value)
    print(bmap(value))
    assert bmap(value) == generated


def test3_many_literals() -> None:
    A = literal("a")
    syntax = A.many()
    sql = "a a a"
    ast = parse(syntax(Parser), sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap(None)
    print(value)
    assert bmap(value) == generated


def test4_mixed_many_named() -> None:
    A = literal("a").bind("x")
    B = literal("b")
    syntax = (A | B).many()
    sql = "a b a"
    ast = parse(syntax(Parser), sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap(None)
    print(value)
    assert bmap(value) == generated


def test5_nested_then_many() -> None:
    IF, THEN, END = literal("if"), literal("then"), literal("end")
    syntax = (IF.many() // THEN.many()).many() // END
    sql = "if if then end"
    ast = parse(syntax(Parser), sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    print("---" * 40)
    print(generated)
    # assert ast == generated
    value, bmap = generated.bimap(None)
    print(value)
    assert bmap(value) == generated