from __future__ import annotations

from syncraft.ast import Then, ThenKind, Many, Choice, ChoiceKind, Token, Marked, Nothing
from syncraft.algebra import Error
from syncraft.parser import  parse
import syncraft.generator as gen
from syncraft.syntax import literal
from syncraft.generator import TokenGen
from rich import print


def test1_simple_then() -> None:
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    print(value)
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


def test2_named_results() -> None:
    A, B = literal("a").mark("x").mark('z'), literal("b").mark("y")
    syntax = A // B
    sql = "a b"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    u,v = gen.generate_with(syntax, bmap(value))
    assert u == generated
    


def test3_many_literals() -> None:
    A = literal("a")
    syntax = A.many()
    sql = "a a a"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


def test4_mixed_many_named() -> None:
    A = literal("a").mark("x")
    B = literal("b")
    syntax = (A | B).many()
    sql = "a b a"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


def test5_nested_then_many() -> None:
    IF, THEN, END = literal("if"), literal("then"), literal("end")
    syntax = (IF.many() // THEN.many()).many() // END
    sql = "if if then end"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast, restore_pruned=True)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    u, v = gen.generate_with(syntax, bmap(value), restore_pruned=True)
    assert u == generated



def test_then_flatten():
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A + (B + C)
    sql = "a b c"
    ast, bound = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated
    value, bmap = generated.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated



def test_named_in_then():
    A = literal("a").mark("first")
    B = literal("b").mark("second")
    C = literal("c").mark("third")
    syntax = A + B + C
    sql = "a b c"
    ast, bound = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated
    value, bmap = generated.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


def test_named_in_many():
    A = literal("x").mark("x")
    syntax = A.many()
    sql = "x x x"
    ast, bound = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated
    value, bmap = generated.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


def test_named_in_or():
    A = literal("a").mark("a")
    B = literal("b").mark("b")
    syntax = A | B
    sql = "b"
    ast, bound = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated
    value, bmap = generated.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated





def test_deep_mix():
    A = literal("a").mark("a")
    B = literal("b")
    C = literal("c").mark("c")
    syntax = ((A + B) | C).many() + B
    sql = "a b a b c b"
    ast, bound = parse(syntax, sql, dialect='sqlite')
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    print('---' * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


def test_empty_many() -> None:
    A = literal("a")
    syntax = A.many()  # This should allow empty matches
    sql = ""
    ast, bound = parse(syntax, sql, dialect="sqlite")
    assert isinstance(ast, Error)


def test_backtracking_many() -> None:
    A = literal("a")
    B = literal("b")
    syntax = (A.many() + B)  # must not eat the final "a" needed for B
    sql = "a a a a b"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    value, bmap = ast.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == ast

def test_deep_nesting() -> None:
    A = literal("a")
    syntax = A
    for _ in range(100):
        syntax = syntax + A
    sql = " " .join("a" for _ in range(101))
    ast, bound = parse(syntax, sql, dialect="sqlite")
    assert ast is not None


def test_nested_many() -> None:
    A = literal("a")
    syntax = (A.many().many())  # groups of groups of "a"
    sql = "a a a"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    assert isinstance(ast, Many)


def test_named_many() -> None:
    A = literal("a").mark("alpha")
    syntax = A.many()
    sql = "a a"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    value, bmap = ast.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == ast


def test_or_named() -> None:
    A = literal("a").mark("x")
    B = literal("b").mark("y")
    syntax = A | B
    sql = "b"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    value, bmap = ast.bimap()
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == ast


def test_then_associativity() -> None:
    A = literal("a")
    B = literal("b")
    C = literal("c")
    syntax = A + B + C
    sql = "a b c"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    # Should be Then(Then(A,B),C)
    assert ast == Then(kind=ThenKind.BOTH, 
                                   left=Then(kind=ThenKind.BOTH, 
                                                   left=TokenGen.from_string('a'), 
                                                   right=TokenGen.from_string('b')), 
                                    right=TokenGen.from_string('c'))


def test_ambiguous() -> None:
    A = literal("a")
    B = literal("a") + literal("b")
    syntax = A | B
    sql = "a"
    ast, bound = parse(syntax, sql, dialect="sqlite")
    # Does it prefer A (shorter) or B (fails)? Depends on design.
    assert ast == Choice[Token, Token](value=TokenGen.from_string("a"), kind=ChoiceKind.LEFT)


def test_combo() -> None:
    A = literal("a").mark("a")
    B = literal("b")
    C = literal("c").mark("c")
    syntax = ((A + B).many() | C) + B
    sql = "a b a b c b"
    # Should fail, as we discussed earlier
    # the working syntax should be ((A + B) | C).many() + B
    ast, bound = parse(syntax, sql, dialect="sqlite")
    assert isinstance(ast, Error)
    ast, bound = parse(((A + B) | C).many() + B, sql, dialect="sqlite")
    assert not isinstance(ast, Error)


def test_optional():
    A = literal("a").mark("a")
    syntax = A.optional()
    ast1, bound = parse(syntax, "", dialect="sqlite")
    v1, _ = ast1.bimap()
    assert isinstance(v1, Nothing)
    ast2, bound = parse(syntax, "a", dialect="sqlite")
    v2, _ = ast2.bimap()
    assert v2 == Marked(name='a', value=TokenGen.from_string('a'))



def test_many_optional():
    A = literal("a")
    syntax = A.optional().many()
    ast1, _ = parse(syntax, "a a b", dialect="sqlite")
    print(ast1)
    ast2, inv = ast1.bimap()
    assert Many(value=(Choice(kind=None, value=TokenGen.from_string('a')), Choice(kind=None, value=TokenGen.from_string('a')))) == inv(ast2)

