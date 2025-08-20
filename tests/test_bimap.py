from __future__ import annotations
from syncraft.algebra import NamedResult
from syncraft.parser import literal, parse, Parser
import syncraft.generator as gen
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



def test_then_flatten():
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A + (B + C)
    sql = "a b c"
    ast = parse(syntax(Parser), sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    assert ast == generated
    value, bmap = ast.bimap(None)
    assert bmap(value) == ast    



def test_named_in_then():
    A = literal("a").bind("first")
    B = literal("b").bind("second")
    C = literal("c").bind("third")
    syntax = A + B + C
    sql = "a b c"
    ast = parse(syntax(Parser), sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    assert ast == generated
    value, bmap = ast.bimap(None)
    assert isinstance(value, tuple)
    print(value)
    assert set(x.name for x in value if isinstance(x, NamedResult)) == {"first", "second", "third"}
    assert bmap(value) == ast


def test_named_in_many():
    A = literal("x").bind("x")
    syntax = A.many()
    sql = "x x x"
    ast = parse(syntax(Parser), sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    assert ast == generated
    value, bmap = ast.bimap(None)
    assert isinstance(value, list)
    assert all(isinstance(v, NamedResult) for v in value if isinstance(v, NamedResult))
    assert bmap(value) == ast


def test_named_in_or():
    A = literal("a").bind("a")
    B = literal("b").bind("b")
    syntax = A | B
    sql = "b"
    ast = parse(syntax(Parser), sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    assert ast == generated
    value, bmap = ast.bimap(None)
    assert isinstance(value, NamedResult)
    assert value.name == "b"
    assert bmap(value) == ast    





def test_deep_mix():
    A = literal("a").bind("a")
    B = literal("b")
    C = literal("c").bind("c")
    syntax = ((A + B) | C).many() + B
    sql = "a b a b c b"
    ast = parse(syntax(Parser), sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax(gen.Generator), ast)
    print('---' * 40)
    print(generated)
    assert ast == generated
    value, bmap = ast.bimap(None)
    assert bmap(value) == ast
