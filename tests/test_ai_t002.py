from __future__ import annotations

# pyright: reportSelfClsParameterName=false

from syncraft import Grammar, Syntax, grammar, lazy, rule
from syncraft.parser import parse_string

S = Syntax.set()


def build_t002_rp():
    number = S.rp(r"[0-9]+").map(int)
    plus = S.rp(r"\s*\+\s*").map(lambda _: "+")
    star = S.rp(r"\s*\*\s*").map(lambda _: "*")
    lparen = S.rp(r"\s*\(\s*")
    rparen = S.rp(r"\s*\)\s*")

    expr = S.lazy(lambda: (term + plus + expr) | term)
    term = S.lazy(lambda: (factor + star + term) | factor)
    factor = S.lazy(lambda: number | expr.between(lparen, rparen))
    return expr


@grammar
class T002Grammar(Grammar):
    number = S.rp(r"[0-9]+").map(int)
    plus = S.rp(r"\s*\+\s*").map(lambda _: "+")
    star = S.rp(r"\s*\*\s*").map(lambda _: "*")
    lparen = S.rp(r"\s*\(\s*")
    rparen = S.rp(r"\s*\)\s*")

    @lazy(S)
    def expr(_=None):
        return (T002Grammar.term + T002Grammar.plus + T002Grammar.expr) | T002Grammar.term

    @lazy(S)
    def term(_=None):
        return (T002Grammar.factor + T002Grammar.star + T002Grammar.term) | T002Grammar.factor

    @lazy(S)
    def factor(_=None):
        return T002Grammar.number | T002Grammar.expr.between(T002Grammar.lparen, T002Grammar.rparen)

    root = rule(expr, is_root=True)


def test_t002_precedence_rp() -> None:
    expr = build_t002_rp()
    assert parse_string(expr, "1+2*3") == (1, "+", (2, "*", 3))
    assert parse_string(expr, "(1+2)*3") == ((1, "+", 2), "*", 3)


def test_t002_precedence_grammar() -> None:
    assert T002Grammar.parse("1+2*3") == (1, "+", (2, "*", 3))
    assert T002Grammar.parse("(1+2)*3") == ((1, "+", 2), "*", 3)
