from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import Either, Left, Right, Error
from syncraft.ast import Marked, Then, ThenKind, Many, Nothing
from syncraft.parser import literal, variable, parse, Parser, Token
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
    ast = parse(syntax, sql, dialect='sqlite')
    print(ast)
    g = gen.generate(syntax, ast, restore_pruned=True)
    assert ast == g
    x, f = g.bimap()
    print(1, x)
    assert gen.generate(syntax, f(x), restore_pruned=True) == ast
    x.condition.append(x.condition[0])
    print(2, x)
    print(f(x))
    ast2 = gen.generate(syntax, f(x), restore_pruned=True) 
    # print(ast2)
    # y, fy = ast2.bimap()
    # print(3, y)
    # assert y == x
    # assert gen.generate(syntax, fy(y), restore_pruned=True) == ast2


if __name__ == "__main__":
    pass
    A = literal('a')
    B = literal('b')
    C = literal('c')
    s = (A | C).sep_by(B)
    ast = parse(s, 'a b a b c', dialect='sqlite')
    print(ast)
    x, f = ast.bimap()
    print(x)
    x[1] = x[2]
    ast2 = gen.generate(s, f(x), restore_pruned=True)
    y, f = ast2.bimap()
    print(y)


