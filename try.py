from __future__ import annotations
from syncraft.algebra import NamedResult
from syncraft.parser import literal, variable, parse, Parser
from syncraft.ast import AST
import syncraft.generator as gen
from typing import Any
from rich import print

IF = literal("if")
ELSE = literal("else")
THEN = literal("then")
END = literal("end")
var = variable()

if_stmt = (IF
           + var.many().bind('condition')
           // THEN 
           + var.many().bind('then')
           + ELSE 
           + var.many().bind('else')
           + END)

ifif = IF >> if_stmt.many().bind('ifif')


def test6()->None:
    sql = "if then if"
    syntax = IF.sep_by(THEN)
    ast:AST[Any] = parse(syntax(Parser), sql, dialect='sqlite')    
    print('---' * 40)
    print(ast)   

    generated = gen.generate(syntax(gen.Generator), ast)
    print('---' * 40)
    print(generated)

    assert ast == generated, "Parsed and generated results do not match."


def test7()->None:
    IF = literal("if")
    THEN = literal("then")
    END = literal("end")
    syntax = (IF.many() | THEN.many()).many() // END
    sql = "if if then end"
    ast:AST[Any] = parse(syntax(Parser), sql, dialect='sqlite')
    print('---' * 40)
    print(ast)   
    generated = gen.generate(syntax(gen.Generator), ast)
    print('---' * 40)
    print(generated)
    assert ast == generated, "Parsed and generated results do not match."
    value, bmap = generated.bimap(None)
    assert value is not generated 
    print(value)
    assert bmap(value) == generated, "Bimap value should be different from generated"

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
    back = bmap(value)
    print(value, back)
    assert back == ast

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

if __name__ == "__main__":
    test_deep_mix()
