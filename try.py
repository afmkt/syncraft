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

if __name__ == "__main__":
    pass
    A = literal('a')
    B = literal('b')
    C = literal('c')
    D = literal('d')
    E = literal('e')
    F = literal('f')
    sql = 'a b c d e f'
    syntax = (A >> B) + (C + D) + (E + F)
    ast = parse(syntax, sql, dialect='sqlite')
    print('---' * 40)
    print(ast)
    generated = gen.generate(syntax, ast)
    assert ast == generated
    x, f = generated.bimap()
    print(x)
    y = f(x)
    assert y == ast
    # A = literal('a')
    # B = literal('b')
    # C = literal('c')
    # D = literal('d')
    # sql = 'a b c'
    # syntax = ~D + (A | B | C).many()
    # syntax = (A | B | C).many()
    # ast = parse(syntax, sql, dialect='sqlite')    
    # print('---' * 40)
    # print(ast)
    # generated = gen.generate(syntax, ast)
    # print('---' * 40)
    # print(generated)

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
    # v, f = generated.bimap()
    # print(v)
    # print(f(v))
    # x = gen.generate(syntax, f(v))
    # assert x == ast
