from syncraft.ast import AST
from syncraft.parser import variable, parse
from syncraft.syntax import literal
import syncraft.generator as gen
from typing import Any

IF = literal("if")
ELSE = literal("else")
THEN = literal("then")
END = literal("end")
var = variable()


def test_between()->None:
    sql = "then if then"
    syntax = IF.between(THEN, THEN)
    ast, bound = parse(syntax, sql, dialect='sqlite')    
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(syntax, f(x))
    assert u == ast


def test_sep_by()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    ast, bound = parse(syntax, sql, dialect='sqlite')    
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
    ast, bound = parse(syntax, sql, dialect='sqlite')
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(syntax, f(x))
    assert u == ast
