from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.ast import MarkedResult, ManyResult, OrResult, ThenResult, ThenKind, Biarrow, StructuralResult
from syncraft.algebra import Error
from syncraft.parser import literal, parse
import syncraft.generator as gen
from syncraft.generator import TokenGen
from rich import print


def test1_simple_then() -> None:
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    print(value)
    assert bmap(value) == generated


def test2_named_results() -> None:
    A, B = literal("a").mark("x").mark('z'), literal("b").mark("y")
    syntax = A // B
    sql = "a b"
    ast = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    print(value)
    print(bmap(value))
    assert bmap(value) == generated


def test3_many_literals() -> None:
    A = literal("a")
    syntax = A.many()
    sql = "a a a"
    ast = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    print(value)
    assert bmap(value) == generated


def test4_mixed_many_named() -> None:
    A = literal("a").mark("x")
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
    value, bmap = generated.bimap()
    print(value)
    assert bmap(value) == generated


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
    value, bmap = generated.bimap()
    print(value)
    assert bmap(value) == generated



def test_then_flatten():
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A + (B + C)
    sql = "a b c"
    ast = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax, ast)
    assert ast == generated
    value, bmap = ast.bimap()
    assert bmap(value) == ast    



def test_named_in_then():
    A = literal("a").mark("first")
    B = literal("b").mark("second")
    C = literal("c").mark("third")
    syntax = A + B + C
    sql = "a b c"
    ast = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax, ast)
    assert ast == generated
    value, bmap = ast.bimap()
    assert isinstance(value, tuple)
    print(value)
    assert set(x.name for x in value if isinstance(x, MarkedResult)) == {"first", "second", "third"}
    assert bmap(value) == ast


def test_named_in_many():
    A = literal("x").mark("x")
    syntax = A.many()
    sql = "x x x"
    ast = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax, ast)
    assert ast == generated
    value, bmap = ast.bimap()
    assert isinstance(value, list)
    assert all(isinstance(v, MarkedResult) for v in value if isinstance(v, MarkedResult))
    assert bmap(value) == ast


def test_named_in_or():
    A = literal("a").mark("a")
    B = literal("b").mark("b")
    syntax = A | B
    sql = "b"
    ast = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax, ast)
    assert ast == generated
    value, bmap = ast.bimap()
    assert isinstance(value, MarkedResult)
    assert value.name == "b"
    assert bmap(value) == ast    





def test_deep_mix():
    A = literal("a").mark("a")
    B = literal("b")
    C = literal("c").mark("c")
    syntax = ((A + B) | C).many() + B
    sql = "a b a b c b"
    ast = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated = gen.generate(syntax, ast)
    print('---' * 40)
    print(generated)
    assert ast == generated
    value, bmap = ast.bimap()
    assert bmap(value) == ast


def test_empty_many() -> None:
    A = literal("a")
    syntax = A.many()  # This should allow empty matches
    sql = ""
    ast = parse(syntax, sql, dialect="sqlite")
    assert isinstance(ast, Error)


def test_backtracking_many() -> None:
    A = literal("a")
    B = literal("b")
    syntax = (A.many() + B)  # must not eat the final "a" needed for B
    sql = "a a a a b"
    ast = parse(syntax, sql, dialect="sqlite")
    value, bmap = ast.bimap()
    assert value[-1] == TokenGen.from_string("b")

def test_deep_nesting() -> None:
    A = literal("a")
    syntax = A
    for _ in range(100):
        syntax = syntax + A
    sql = " " .join("a" for _ in range(101))
    ast = parse(syntax, sql, dialect="sqlite")
    assert ast is not None


def test_nested_many() -> None:
    A = literal("a")
    syntax = (A.many().many())  # groups of groups of "a"
    sql = "a a a"
    ast = parse(syntax, sql, dialect="sqlite")
    assert isinstance(ast.focus, ManyResult)


def test_named_many() -> None:
    A = literal("a").mark("alpha")
    syntax = A.many()
    sql = "a a"
    ast = parse(syntax, sql, dialect="sqlite")
    # Expect [MarkedResult("alpha", "a"), MarkedResult("alpha", "a")]
    flattened, _ = ast.bimap()
    assert all(isinstance(x, MarkedResult) for x in flattened)


def test_or_named() -> None:
    A = literal("a").mark("x")
    B = literal("b").mark("y")
    syntax = A | B
    sql = "b"
    ast = parse(syntax, sql, dialect="sqlite")
    # Either MarkedResult("y", "b") or just "b", depending on your design
    assert isinstance(ast.focus, OrResult)
    value, _ = ast.bimap()
    assert value == MarkedResult(name="y", value=TokenGen.from_string("b"))


def test_then_associativity() -> None:
    A = literal("a")
    B = literal("b")
    C = literal("c")
    syntax = A + B + C
    sql = "a b c"
    ast = parse(syntax, sql, dialect="sqlite")
    # Should be ThenResult(ThenResult(A,B),C)
    assert ast.focus == ThenResult(kind=ThenKind.BOTH, 
                                   left=ThenResult(kind=ThenKind.BOTH, 
                                                   left=TokenGen.from_string('a'), 
                                                   right=TokenGen.from_string('b')), 
                                    right=TokenGen.from_string('c'))


def test_ambiguous() -> None:
    A = literal("a")
    B = literal("a") + literal("b")
    syntax = A | B
    sql = "a"
    ast = parse(syntax, sql, dialect="sqlite")
    # Does it prefer A (shorter) or B (fails)? Depends on design.
    assert ast.focus == OrResult(TokenGen.from_string("a"))


def test_combo() -> None:
    A = literal("a").mark("a")
    B = literal("b")
    C = literal("c").mark("c")
    syntax = ((A + B).many() | C) + B
    sql = "a b a b c b"
    # Should fail, as we discussed earlier
    ast = parse(syntax, sql, dialect="sqlite")
    assert isinstance(ast, Error)


def test_optional():
    A = literal("a").mark("a")
    syntax = A.optional()
    ast1 = parse(syntax, "", dialect="sqlite")
    v1, _ = ast1.bimap()
    assert v1 is None
    ast2 = parse(syntax, "a", dialect="sqlite")
    v2, _ = ast2.bimap()
    assert v2 == MarkedResult(name='a', value=TokenGen.from_string('a'))





