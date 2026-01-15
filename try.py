from __future__ import annotations
from typing import Any
from syncraft.parser import parse_word
from syncraft.syntax import Syntax
import syncraft.generator as gen
from syncraft.cache import Cache
from dataclasses import dataclass
from syncraft.lexer import ExtLexer
from syncraft.ast import Token
from syncraft.token import Structured
from rich import print
literal = Syntax.lit


def test_to() -> None:
    @dataclass
    class IfThenElse:
        condition: Any
        then: Any
        otherwise: Any

    @dataclass
    class While:
        condition:Any
        body:Any

    WHILE = literal("while")
    IF = literal("if")
    ELSE = literal("else")
    THEN = literal("then")
    END = literal("end")
    A = literal('a')
    B = literal('b')
    C = literal('c')
    D = literal('d')
    M = literal(',')
    var = A | B | C | D
    condition = var.sep_by(M).mark('condition') 
    ifthenelse = (IF >> condition
              // THEN 
              + var.sep_by(M).mark('then') 
              // ELSE 
              + var.sep_by(M).mark('otherwise') 
              // END).to(IfThenElse).many()
    syntax = (WHILE >> condition
            + ifthenelse.mark('body')
            // ~END).to(While)
    sql = 'while b if a , b then c , d else a , d end if a , b then c , d else a , d end'
    ast, _ = parse_word(syntax, sql, cache=Cache())
    # print(ast)
    g, _ = gen.generate_with(syntax, ast, restore_pruned=True)
    assert ast == g
    # print(1, x)
    u, _ = gen.generate_with(syntax, g, restore_pruned=True)
    assert u == ast
    print(g)
    g.body.append(g.body[0])
    # print(2, x)
    # print(f(x))
    ast2, _ = gen.generate_with(syntax, g, restore_pruned=True) 
    # print(ast2)``
    # print(3, y)
    assert ast2 == g
    u, v = gen.generate_with(syntax, ast2, restore_pruned=True)
    assert u == ast2

if __name__ == "__main__":
    test_to()