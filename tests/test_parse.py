from __future__ import annotations
from syncraft.parser import  parse_word
from syncraft.syntax import Syntax
import syncraft.generator as gen
from syncraft.ast import Token

from syncraft.lexer import ExtLexer
from syncraft.token import Structured
# literal = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).literal
literal = Syntax.literal


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
    x, f = generated.bimap()
    u, v = gen.generate_with(syntax, f(x))
    assert u == ast


def test_sep_by()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    from syncraft.cache import Cache
    ast, bound = parse_word(syntax, sql, cache=Cache())    
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(syntax, f(x))
    assert u == ast

def test_many_or()->None:
    IF = literal("if")
    THEN = literal("then")
    END = literal("end")
    syntax = (IF.many() + THEN.many()).many() // END
    sql = "if if then end"
    from syncraft.cache import Cache
    ast, bound = parse_word(syntax, sql, cache=Cache())
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(syntax, f(x))
    assert u == ast


def test_optional_many():
    a = literal('a')
    S = a.optional.many()
    sql = "a a"
    from syncraft.cache import Cache
    ast, bound = parse_word(S, sql, cache=Cache())    
    generated, bound = gen.generate_with(S, ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(S, f(x))
    assert u == ast