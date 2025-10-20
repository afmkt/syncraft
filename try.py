from __future__ import annotations
from typing import Any
from dataclasses import dataclass

import pytest

from syncraft.finder import find, anything
from syncraft.parser import parse_word
from syncraft.syntax import Syntax
from syncraft.ast import Nothing

from syncraft.generator import (
    generate_with,
    generate,
)

from syncraft.cache import LeftRecursionError
from rich import print
from syncraft.lexer import CacheWithLexer

# literal = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).literal
literal = Syntax.literal

# @pytest.mark.xfail(reason="Finder integration is pending")
def test_find()->None:
    @dataclass
    class IfThenElse:
        condition: Any
        then: Any
        otherwise: Any

    @dataclass
    class While:
        condition:Any
        body:IfThenElse

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

    ast, _ = parse_word(A + ~B, 'a')    
    print(ast.mapped)
    print(ast.mapped[1] is Nothing())
    quit()
    ifthenelse = (IF >> condition
              // THEN 
              + var.sep_by(M).map(lambda x: x).mark('then') 
              // ELSE 
              + var.sep_by(M).mark('otherwise') 
              // END).to(IfThenElse)
    syntax = (WHILE >> condition
            + ifthenelse.mark('body')
            // ~END).to(While)
    sql = 'while b if a , b then c , d else a , d end'
    

    ast, bound = parse_word(syntax, sql)

    print(ast.mapped)




if __name__ == "__main__":
    test_find()