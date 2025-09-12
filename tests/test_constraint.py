from __future__ import annotations
from typing import Any
from syncraft.parser import parse_sql
from syncraft.constraint import forall, exists
from syncraft.parser import literal
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
    condition = var.sep_by(M).mark('condition').bind() 
    ifthenelse = (IF >> condition
              // THEN 
              + var.sep_by(M).mark('then').bind() 
              // ELSE 
              + var.sep_by(M).mark('otherwise').bind() 
              // END).to(IfThenElse).many()
    syntax = (WHILE >> condition
            + ifthenelse.mark('body').bind()
            // ~END).to(While)
    sql = 'while b if a,b then c,d else a,d end if a,b then c,d else a,d end'
    ast, bound = parse_sql(syntax, sql, dialect='sqlite')
    def p(condition, then, otherwise)->bool:
        # print({'condition':condition, 'then':then, 'otherwise':otherwise})
        return True
    if bound is not None:
        forall(p)(bound)
    g, bound = gen.generate_with(syntax, ast, restore_pruned=True)
