from __future__ import annotations
from syncraft.parser import  parse_word
from syncraft.syntax import Syntax
import syncraft.generator as gen
from syncraft.ast import Token


literal = Syntax.set(terminal_cls=Token).lit



IF = literal("if")
ELSE = literal("else")
THEN = literal("then")
END = literal("end")


def test_between()->None:
    sql = "then if then"
    syntax = IF.between(THEN, THEN)
    from syncraft.cache import Cache
    ast, bound = parse_word(syntax, sql, cache=Cache())    
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    u, v = gen.generate_with(syntax, generated)
    assert u == ast


def test_sep_by()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    from syncraft.cache import Cache
    ast, bound = parse_word(syntax, sql, cache=Cache())    
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    u, v = gen.generate_with(syntax, generated)
    assert u == ast

def test_many_or()->None:
    literal = Syntax.set(terminal_cls=Token).lit
    IF = literal("if")
    THEN = literal("then")
    END = literal("end")
    syntax = (IF.many() + THEN.many()).many() // END
    sql = "if if then end"
    from syncraft.cache import Cache
    ast, bound = parse_word(syntax, sql, cache=Cache())
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    u, v = gen.generate_with(syntax, generated)
    assert u == ast


def test_optional_many():
    a = literal('a')
    S = a.optional.many()
    sql = "a a"
    from syncraft.cache import Cache
    ast, bound = parse_word(S, sql, cache=Cache())    
    generated, bound = gen.generate_with(S, ast)
    assert ast == generated, "Parsed and generated results do not match."

    u, v = gen.generate_with(S, generated)
    assert u == ast