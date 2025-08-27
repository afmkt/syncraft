from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.ast import Marked, Then, ThenKind, AST
from syncraft.parser import literal, variable, parse, Parser, Token
from syncraft.generator import TokenGen
from rich import print
import syncraft.generator as gen

if __name__ == "__main__":
    # A = literal("a").mark("a")
    # B = literal("b")
    # C = literal("c").mark("c")
    # syntax:Any = ((A + B) | C).many() + B
    # sql = "a b a b c b"
    # ast = parse(syntax, sql, dialect='sqlite')
    # print(ast)
    # generated = gen.generate(syntax, ast)
    # print('---' * 40)
    # print(generated)
    # assert ast == generated
    IF = literal("if")
    ELSE = literal("else")
    THEN = literal("then")
    END = literal("end")
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    ast = parse(syntax, sql, dialect='sqlite')    
    print('---' * 40)
    print(ast)
    generated = gen.generate(syntax, ast)
    print('---' * 40)
    print(generated)
    assert ast == generated

    sql ="if"
    ast = parse(syntax, sql, dialect='sqlite')    
    print('---' * 40)
    print(ast)
    generated = gen.generate(syntax, ast)
    print('---' * 40)
    print(generated)
    assert ast == generated