from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import Either, Left, Right, Error
from syncraft.ast import Marked, Then, ThenKind, Many, Nothing
from syncraft.parser import variable, parse, Parser, Token
from syncraft.syntax import literal
from syncraft.generator import TokenGen
from rich import print
import syncraft.generator as gen
from dataclasses import dataclass


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
    sql = 'while b if a,b then c,d else a,d end if a,b then c,d else a,d end'
    ast, bound = parse(syntax, sql, dialect='sqlite')
    print(ast)
    g, bound = gen.generate_with(syntax, ast, restore_pruned=True)
    assert ast == g
    x, f = g.bimap()
    print(1, x)
    u,v = gen.generate_with(syntax, f(x), restore_pruned=True)
    assert u == ast
    x.body.append(x.body[0])
    print(2, x)
    print(f(x))
    ast2, bound = gen.generate_with(syntax, f(x), restore_pruned=True) 
    print(ast2)
    y, fy = ast2.bimap()
    print(3, y)
    assert y == x
    u, v = gen.generate_with(syntax, fy(y), restore_pruned=True)
    assert u == ast2
