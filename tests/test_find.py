from __future__ import annotations
from typing import Any
from dataclasses import dataclass

import pytest

from syncraft.finder import find, anything
from syncraft.parser import parse_word
from syncraft.syntax import Syntax
from syncraft.lexer import ExtLexer
from syncraft.ast import Token
from syncraft.token import Structured
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
    from syncraft.cache import Cache
    ast, bound = parse_word(syntax, sql, cache=Cache())
    nodes = list(find(anything(syntax), ast))

    assert nodes[0] == ast
    # assert any(isinstance(node, IfThenElse) for node in nodes)
    # assert any(isinstance(node, While) for node in nodes)
