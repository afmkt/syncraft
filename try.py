from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.ast import Marked, Then, ThenKind
from syncraft.parser import literal, variable, parse, Parser, Token
from syncraft.generator import TokenGen
from rich import print
import syncraft.generator as gen

if __name__ == "__main__":
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
    # value, bmap = ast.bimap()
    # print('---' * 40)
    # print(value)
    # assert bmap(value) == ast

