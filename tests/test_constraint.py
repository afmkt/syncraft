from __future__ import annotations
from typing import Any
from syncraft.parser import parse_word
from syncraft.constraint import forall
from syncraft.syntax import Syntax
import syncraft.generator as gen
from dataclasses import dataclass
from syncraft.cache import set_randomization

# Ensure randomization is enabled for these tests
set_randomization(True)

literal = Syntax.literal

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
    sql = 'while b if a , b then c , d else a , d end if a , b then c , d else a , d end'
    from syncraft.cache import Cache

    ast, bound = parse_word(syntax, sql, cache=Cache())
    def p(condition, then, otherwise)->bool:
        return True
    if bound is not None:
        forall(p)(bound)
    g, bound = gen.generate_with(syntax, ast, restore_pruned=True)
