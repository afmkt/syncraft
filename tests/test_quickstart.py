from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from syncraft import Error, Grammar, Syntax, Token, grammar, lazy, rule
import pytest

# -- step-1 --
S = Syntax.set(terminal_cls=Token)


@grammar
class ExprGrammar(Grammar):
    number = S.tok(re.compile(r"\d+"))
    plus = S.tok("+")
    star = S.tok("*")
    lparen = S.tok("(")
    rparen = S.tok(")")

    @lazy(S)
    def expr():  # type: ignore
        return (ExprGrammar.term + ExprGrammar.plus + ExprGrammar.expr) | ExprGrammar.term

    @lazy(S)
    def term():  # type: ignore
        return (ExprGrammar.factor + ExprGrammar.star + ExprGrammar.term) | ExprGrammar.factor

    @lazy(S)
    def factor():  # type: ignore
        return ExprGrammar.number | ExprGrammar.expr.between(ExprGrammar.lparen, ExprGrammar.rparen)

    root = rule(expr, is_root=True)
# -- step-1-end --


# -- step-2 --
@pytest.mark.skip(reason="The library is not ready for this yet")
def test_quickstart_step_2() -> None:
    ast = ExprGrammar.parse("1 + 2 * 3")
    assert ast == (
        (Token(text="1"), Token(text="+")),
        ((Token(text="2"), Token(text="*")), Token(text="3")),
    )
# -- step-2-end --


# -- step-3 --
@dataclass(frozen=True, slots=True)
class Number:
    value: int


@dataclass(frozen=True, slots=True)
class Binary:
    left: Any
    op: str
    right: Any
# -- step-3-end --


# -- step-4 --
@grammar
class ExprAstGrammar(Grammar):
    number = S.tok(re.compile(r"\d+")).bimap(
        lambda t: Number(int(t.text)),
        lambda n: Token(text=str(n.value)),
    )
    plus = S.tok("+").bimap(lambda t: t.text, lambda s: Token(text=s))
    star = S.tok("*").bimap(lambda t: t.text, lambda s: Token(text=s))
    lparen = S.tok("(")
    rparen = S.tok(")")

    @lazy(S)
    def expr():  # type: ignore[override]
        bin_expr = (ExprAstGrammar.term + ExprAstGrammar.plus + ExprAstGrammar.expr).to(
            lambda env: ((env.left, env.op), env.right),
            lambda env: Binary(env.left, env.op, env.right),
        )
        return bin_expr | ExprAstGrammar.term

    @lazy(S)
    def term():  # type: ignore[override]
        bin_term = (ExprAstGrammar.factor + ExprAstGrammar.star + ExprAstGrammar.term).to(
            lambda env: ((env.left, env.op), env.right),
            lambda env: Binary(env.left, env.op, env.right),
        )
        return bin_term | ExprAstGrammar.factor

    @lazy(S)
    def factor():  # type: ignore[override]
        return ExprAstGrammar.number | ExprAstGrammar.expr.between(ExprAstGrammar.lparen, ExprAstGrammar.rparen)

    root = rule(expr, is_root=True)

@pytest.mark.skip(reason="The library is not ready for this yet")
def test_quickstart_step_4() -> None:
    ast = ExprAstGrammar.parse("1 + 2 * 3")
    assert ast == Binary(Number(1), "+", Binary(Number(2), "*", Number(3)))
# -- step-4-end --


# -- step-5 --
@pytest.mark.skip(reason="The library is not ready for this yet")
def test_quickstart_step_5() -> None:
    expr = Binary(Number(1), "+", Binary(Number(2), "*", Number(3)))
    validated = ExprAstGrammar.validate(expr)
    assert not isinstance(validated, Error)

    generated = ExprAstGrammar.generate(expr)
    assert not isinstance(generated, Error)
# -- step-5-end --
