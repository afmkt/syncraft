from dataclasses import dataclass
from typing import Any

from syncraft import Syntax, parse_word, generate


# -- step-2 --
def test_quickstart_step_2() -> None:
    literal = Syntax.lit
    A = literal("a")
    B = literal("b")
    C = literal(",")
    syntax = (A + B).sep_by(C)
    ast = parse_word(syntax, "a b, a b, a b")
    assert ast is not None
# -- step-2-end --


# -- step-3 --
def test_quickstart_step_3() -> None:
    literal = Syntax.lit
    A = literal("a")
    B = literal("b")
    C = literal(",")
    syntax = (A + B).sep_by(C)
    ast = parse_word(syntax, "a b, a b, a b")

    value, _ = ast.bimap
    assert len(value) == 3
# -- step-3-end --


# -- step-4 --
@dataclass
class Pair:
    first: Any
    second: Any


def test_quickstart_step_4() -> None:
    literal = Syntax.lit
    A = literal("a").mark("first")
    B = literal("b").mark("second")
    C = literal(",")
    syntax = (A + B).to(Pair).sep_by(C)

    ast, _ = parse_word(syntax, "a b, a b, a b")
    value, _ = ast.bimap
    assert len(value) == 3
# -- step-4-end --


# -- step-5 --
def test_quickstart_step_5() -> None:
    literal = Syntax.lit
    A = literal("a").mark("first")
    B = literal("b").mark("second")
    C = literal(",")
    syntax = (A + B).to(Pair).sep_by(C)

    ast, _ = parse_word(syntax, "a b, a b, a b")
    value, inverse = ast.bimap

    value.append(value[1])
    ast2 = inverse(value)
    assert ast2 is not None
# -- step-5-end --


# -- step-6 --
def test_quickstart_step_6() -> None:
    literal = Syntax.lit
    A = literal("a").mark("first")
    B = literal("b").mark("second")
    C = literal(",")
    syntax = (A + B).to(Pair).sep_by(C)

    ast, _ = parse_word(syntax, "a b, a b, a b")
    value, inverse = ast.bimap

    value.append(Pair("x", "y"))
    ast3 = inverse(value)
    rt, _ = generate(syntax, ast3)
    assert rt is not None
# -- step-6-end --
