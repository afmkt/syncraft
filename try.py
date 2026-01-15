from __future__ import annotations
from syncraft.parser import  parse_word
from syncraft.syntax import Syntax
import syncraft.generator as gen
from syncraft.ast import Token, Seq, Then, ThenKind, Many, OrElse, OrElseKind
from rich import print

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
    assert ast == Token(text='if')
    assert generated == Seq(value=((Token(text='then'), False), (Token(text='if'), True), (Token(text='then'), False)))


def test_sep_by()->None:
    sql = "if then if then if then if"
    syntax = IF.sep_by(THEN)
    from syncraft.cache import Cache
    ast, bound = parse_word(syntax, sql, cache=Cache())    
    generated, bound = gen.generate_with(syntax, ast)
    assert ast == (Token(text='if'), Token(text='if'), Token(text='if'), Token(text='if'))
    assert generated == Then(
        kind=ThenKind.BOTH,
        left=Token(text='if'),
        right=Many(
            value=(
                Then(kind=ThenKind.RIGHT, left=Token(text='then'), right=Token(text='if')),
                Then(kind=ThenKind.RIGHT, left=Token(text='then'), right=Token(text='if')),
                Then(kind=ThenKind.RIGHT, left=Token(text='then'), right=Token(text='if'))
            )
        )
    )
    

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
    assert ast == ((((Token(text='if'), Token(text='if')), (Token(text='then'),)),),)
    assert generated == Then(
        kind=ThenKind.LEFT,
        left=Many(value=(Then(kind=ThenKind.BOTH, left=Many(value=(Token(text='if'), Token(text='if'))), right=Many(value=(Token(text='then'),))),)),
        right=Token(text='end')
    )


def test_optional_many():
    a = literal('a')
    S = a.optional.many()
    sql = "a a"
    from syncraft.cache import Cache
    ast, bound = parse_word(S, sql, cache=Cache())    
    generated, bound = gen.generate_with(S, ast)
    print(ast)
    print(generated)
    assert ast == (Token(text='a'), Token(text='a'))
    assert generated == Many(value=(OrElse(kind=OrElseKind.LEFT, value=Token(text='a')), OrElse(kind=OrElseKind.LEFT, value=Token(text='a'))))


if __name__ == "__main__":
    test_between()
    test_sep_by()
    test_many_or()
    test_optional_many()