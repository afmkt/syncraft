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
    condition: Any
    then: Any
    otherwise: Any




def test() -> None:
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
    syntax = (IF >> var.sep_by(M).mark('condition') 
              // THEN 
              + var.sep_by(M).mark('then') 
              // ELSE 
              + var.sep_by(M).mark('otherwise') 
              // END).to(ACls).many()
    sql = 'if a,b then c,d else a,d end'
    ast = parse(syntax, sql, dialect='sqlite')
    g = gen.generate(syntax, ast, restore_pruned=True)
    assert ast == g
    x, f = g.bimap()
    print(x)
    print(f(x))
    assert gen.generate(syntax, f(x), restore_pruned=True) == ast






if __name__ == "__main__":
    pass
    test()

