from __future__ import annotations
from syncraft.parser import  parse_word
from syncraft.syntax import Syntax
import syncraft.generator as gen


from syncraft.ast import TokenClass
literal = Syntax.config(token_class = TokenClass.simple()).literal


IF = literal("if")
ELSE = literal("else")
THEN = literal("then")
END = literal("end")


def test_between()->None:
    sql = "then if then"
    syntax = IF.between(THEN, THEN)
    ast, bound = parse_word(syntax, sql)    
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(syntax, f(x))
    assert u == ast


def test_sep_by()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    ast, bound = parse_word(syntax, sql)    
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(syntax, f(x))
    assert u == ast

def test_many_or()->None:
    IF = literal("if")
    THEN = literal("then")
    END = literal("end")
    syntax = (IF.many() | THEN.many()).many() // END
    sql = "if if then end"
    ast, bound = parse_word(syntax, sql)
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(syntax, f(x))
    assert u == ast
