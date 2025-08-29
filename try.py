from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import Either, Left, Right, Error
from syncraft.ast import Marked, Then, ThenKind, Many, Nothing
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


def test5_nested_then_many() -> None:
    IF, THEN, END = literal("if"), literal("then"), literal("end")
    syntax = (IF.many() // THEN.many()).many() // END
    sql = "if if then end"
    ast = parse(syntax, sql, dialect="sqlite")
    print("---" * 40)
    print(ast)
    generated = gen.generate(syntax, ast, restore_pruned=True)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    assert gen.generate(syntax, bmap(value), restore_pruned=True) == generated



if __name__ == "__main__":
    pass
    test5_nested_then_many()

