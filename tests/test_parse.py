from __future__ import annotations

from syncraft.syntax import Syntax
import syncraft.generator as gen
from syncraft.ast import Seq, Many, Alt
from typing import Any
from syncraft.token import Str, Token

def parse_word(syntax: Syntax, data: str):
    from syncraft.token import Token
    from typing import List
    import re
    from syncraft.parser import parse_data
    tokens: List[Token]  = [Token(text=t) for t in re.split(r'[\x00-\x1F\x7F\s]+', data)]
    return parse_data(syntax, tokens)

S = Syntax
def literal(text: Any) -> Syntax[Any, Any]:
    return S.tok(Token(text=Str(text)))


IF = literal("if")
ELSE = literal("else")
THEN = literal("then")
END = literal("end")

def test_between()->None:
    sql = "then if then"
    syntax = IF.between(THEN, THEN)
    
    ast = parse_word(syntax, sql)    
    generated = gen.generate_with(syntax, ast)
    assert ast == Token(text='if')
    assert generated == Seq(value=((Token(text='then'), False), (Token(text='if'), True), (Token(text='then'), False)))


def test_sep_by()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    
    ast = parse_word(syntax, sql)    
    generated = gen.generate_with(syntax, ast)
    assert ast == (Token(text='if'), Token(text='if'), Token(text='if'), Token(text='if'))
    
    assert generated == Seq(
        value=(
            (Token(text='if'), True),
            (
                Many(
                    value=(
                        Seq(value=((Token(text='then'), False), (Token(text='if'), True))),
                        Seq(value=((Token(text='then'), False), (Token(text='if'), True))),
                        Seq(value=((Token(text='then'), False), (Token(text='if'), True)))
                    )
                ),
                True
            )
        )
    )
    

def test_many_or()->None:
    literal = Syntax.tok
    
    IF = literal(Token(text=Str("if")))
    THEN = literal(Token(text=Str("then")))
    END = literal(Token(text=Str("end")))
    syntax = (IF.many() + THEN.many()).many() // END
    sql = "if if then end"
    ast = parse_word(syntax, sql)
    generated = gen.generate_with(syntax, ast)
    
    assert ast == (((Token(text='if'), Token(text='if')), (Token(text='then'),)),)
    assert generated == Seq(
        value=(
            (Many(value=(Seq(value=((Many(value=(Token(text='if'), Token(text='if'))), True), (Many(value=(Token(text='then'),)), True))),)), True),
            (Token(text='end'), False)
        )
    )


def test_optional_many():
    a = literal('a')
    S = a.optional.many()
    sql = "a a"
    
    ast = parse_word(S, sql)    
    generated = gen.generate_with(S, ast)
    
    
    assert ast == (Token(text='a'), Token(text='a'))
    assert generated == Many(value=(Alt(index=0,value=Token(text='a')), Alt(index=0, value=Token(text='a'))))


