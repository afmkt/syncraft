from __future__ import annotations
from syncraft.parser import literal, variable, parse, Parser
from syncraft.ast import AST
import syncraft.generator as gen
from typing import Any
from rich import print

IF = literal("if")
ELSE = literal("else")
THEN = literal("then")
END = literal("end")
var = variable()

if_stmt = (IF
           + var.many().bind('condition')
           // THEN 
           + var.many().bind('then')
           + ELSE 
           + var.many().bind('else')
           + END)

ifif = IF >> if_stmt.many().bind('ifif')


def test6()->None:
    sql = "if then if"
    syntax = IF.sep_by(THEN)
    ast:AST[Any] = parse(syntax(Parser), sql, dialect='sqlite')    
    print('---' * 40)
    print(ast)   

    generated = gen.generate(syntax(gen.Generator), ast)
    print('---' * 40)
    print(generated)

    assert ast == generated, "Parsed and generated results do not match."


def test7()->None:
    IF = literal("if")
    THEN = literal("then")
    END = literal("end")
    syntax = (IF.many() | THEN.many()).many() // END
    sql = "if if then end"
    ast:AST[Any] = parse(syntax(Parser), sql, dialect='sqlite')
    print('---' * 40)
    print(ast)   
    generated = gen.generate(syntax(gen.Generator))
    print('---' * 40)
    print(generated)
    assert ast == generated, "Parsed and generated results do not match."

if __name__ == "__main__":
    test6()
