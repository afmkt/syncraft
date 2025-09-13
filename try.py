from __future__ import annotations
from syncraft.ast import TokenClass, Nothing
from syncraft.generator import generate_with, generate
from syncraft.parser import parse
from syncraft.fa import NFA, DFA, CodeUniverse
from syncraft.constraint import FrozenDict
from rich import print
from syncraft.ast import Then, ThenKind, Many, Choice, ChoiceKind, Token, Marked, Nothing, TokenClass
from syncraft.algebra import Error
from syncraft.parser import  parse_word
import syncraft.generator as gen
from syncraft.syntax import Syntax
from typing import Any
from dataclasses import dataclass
literal = Syntax.config(TokenClass.simple()).literal


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
    ast, bound = parse_word(syntax, sql)
    print(ast)
    g, bound = gen.generate_with(syntax, ast, restore_pruned=True)
    print(g)
    assert ast == g
    x, f = g.bimap()
    # print(1, x)
    u,v = gen.generate_with(syntax, f(x), restore_pruned=True)
    assert u == ast
    x.body.append(x.body[0])
    # print(2, x)
    # print(f(x))
    ast2, bound = gen.generate_with(syntax, f(x), restore_pruned=True) 
    # print(ast2)
    y, fy = ast2.bimap()
    # print(3, y)
    assert y == x
    u, v = gen.generate_with(syntax, fy(y), restore_pruned=True)
    assert u == ast2

if __name__ == "__main__":
    test_to()
