from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import Either, Left, Right, Error
from syncraft.ast import Marked, Then, ThenKind, Many
from syncraft.parser import literal, variable, parse, Parser, Token
from syncraft.generator import TokenGen
from rich import print
import syncraft.generator as gen
from dataclasses import dataclass

@dataclass
class ACls:
    a: str | None
    b: str | None
    c: str | None


IF = literal("if")
ELSE = literal("else")
THEN = literal("then")
END = literal("end")
var = variable()



def test_sep_by()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    ast = parse(syntax, sql, dialect='sqlite')   
    print(ast) 
    generated = gen.generate(syntax, ast)
    print(generated)
    x, f = ast.bimap()
    print(x)
    print(f(x))
    print(gen.generate(syntax, f(x)))
    assert gen.generate(syntax, f(x)) == ast
    assert ast == generated, "Parsed and generated results do not match."


if __name__ == "__main__":
    pass
    test_sep_by()

