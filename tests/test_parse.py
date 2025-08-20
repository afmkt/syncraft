from syncraft.parser import AST, literal, variable, parse
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
    ast:AST[Any] = parse(syntax, sql, dialect='sqlite')    
    generated = gen.generate(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."


def test_sep_by()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    ast:AST[Any] = parse(syntax, sql, dialect='sqlite')    
    generated = gen.generate(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."

def test_many_or()->None:
    IF = literal("if")
    THEN = literal("then")
    END = literal("end")
    syntax = (IF.many() | THEN.many()).many() // END
    sql = "if if then end"
    ast:AST[Any] = parse(syntax, sql, dialect='sqlite')
    generated = gen.generate(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
