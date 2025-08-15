from __future__ import annotations
from syncraft.parser import AST, literal, variable, parse, Parser
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

def test1()->None:
    sql = "if"
    ast:AST[Any] = parse(IF(Parser), sql, dialect='sqlite')
    print(ast)
    x = gen.generate(IF(gen.Generator), ast)
    print(x)

def test2()->None:
    sql = "if if a a a then b b b else c c c end"
    ast:AST[Any] = parse(ifif(Parser), sql, dialect='sqlite')
    print(ast)
    # x = gen.generate(ifif(gen.Generator), tmp)
    # print(x)

def test3()->None:
    sql = "then if then"
    syntax = IF.between(THEN, THEN)
    ast:AST[Any] = parse(syntax(Parser), sql, dialect='sqlite')    

def test4()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    ast:AST[Any] = parse(syntax(Parser), sql, dialect='sqlite')    

def test5()->None:
    sql = "if if a a a then b b b else c c c end"
    ast:AST[Any] = parse(ifif(Parser), sql, dialect='sqlite')
    x = gen.generate(ifif(gen.Generator), ast)
    print('---' * 40)
    print(x)

def test6()->None:
    sql = "if if a a a then b b b else c c c end"
    syntax = ifif
    print(syntax._string)
    ast:AST[Any] = parse(syntax(Parser), sql, dialect='sqlite')
    
    # print(state)
    # while not state.ended():
    #     print('*' * 40)
    #     print(state.ast.focus)
    #     print('-' * 40)
    #     # print(state)
    #     state = state.advance()

    x = gen.generate(syntax(gen.Generator), ast)
    # print(x)

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
    test7()
