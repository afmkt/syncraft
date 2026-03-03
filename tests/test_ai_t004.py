from __future__ import annotations

# pyright: reportSelfClsParameterName=false

from syncraft import Grammar, Syntax, grammar, lazy, rule
from syncraft.parser import parse_string

S = Syntax.set()


def build_t004_rp():
    num = S.rp(r"[0-9]+").map(int)
    op = S.rp(r"[+\-*/]")
    expr = S.lazy(lambda: S.rp(
        r"(?&num)|(\((?&expr)\s*(?&op)\s*(?&expr)\))",
        num=num,
        op=op,
        expr=expr,
    ))
    return expr


@grammar
class T004Grammar(Grammar):
    num = S.rp(r"[0-9]+").map(int)
    op = S.rp(r"[+\-*/]")
    lparen = S.rp(r"\(")
    rparen = S.rp(r"\)")

    @lazy(S)
    def expr(_=None):
        return T004Grammar.num | (
            T004Grammar.lparen
            >> (T004Grammar.expr + T004Grammar.op + T004Grammar.expr)
            // T004Grammar.rparen
        )

    root = rule(expr, is_root=True)


def test_t004_recursive_expr_rp() -> None:
    expr = build_t004_rp()
    assert parse_string(expr, "7") == 7
    assert parse_string(expr, "(2+3)") == (2, "+", 3)
    assert parse_string(expr, "((1+2)*3)") == ((1, "+", 2), "*", 3)


def test_t004_recursive_expr_grammar() -> None:
    assert T004Grammar.parse("7") == 7
    assert T004Grammar.parse("(2+3)") == (2, "+", 3)
    assert T004Grammar.parse("((1+2)*3)") == ((1, "+", 2), "*", 3)
