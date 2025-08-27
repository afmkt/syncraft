from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.ast import Marked, Then, ThenKind, Many
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
    generated = gen.generate(syntax, ast, restore_pruned=True)
    print("---" * 40)
    print(generated)
    assert ast == generated

if __name__ == "__main__":
    test5_nested_then_many()
    pass
    # IF = literal("if")
    # ELSE = literal("else")
    # THEN = literal("then")
    # END = literal("end")
    # sql = "if then if then if then if"
    # syntax = IF.sep_by(THEN)
    # ast = parse(syntax, sql, dialect='sqlite')    
    # print('---' * 40)
    # print(ast)
    # generated = gen.generate(syntax, ast)
    # print('---' * 40)
    # print(generated)
    # assert ast == generated

    # sql ="if"
    # ast = parse(syntax, sql, dialect='sqlite')    
    # print('---' * 40)
    # print(ast)
    # generated = gen.generate(syntax, ast)
    # print('---' * 40)
    # print(generated)
    # assert ast == generated