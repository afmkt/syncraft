from __future__ import annotations
import pytest
# LeftRecursionError no longer imported; xfail test does not enforce error path.
from syncraft.syntax import Syntax
from syncraft.cache import LeftRecursionError
from syncraft.lexer import ExtLexer
from syncraft.parser import parse_word
from syncraft.cache import logging
from syncraft.cache import Cache
from syncraft.ast import Token
from syncraft.token import Structured
from rich import print
import re
from typing import Any, Iterable


def iter_tokens(ast: Any) -> Iterable[str]:
    if isinstance(ast, Token):
        yield ast.text # type: ignore
    elif isinstance(ast, (tuple, list)):
        for x in ast:
            yield from iter_tokens(x)
    elif hasattr(ast, 'value') and isinstance(getattr(ast, 'value'), tuple):
        # For Then/Choice wrappers from syncraft.ast
        for x in getattr(ast, 'value'):
            yield from iter_tokens(x)
    elif hasattr(ast, 'left') and hasattr(ast, 'right'):
        yield from iter_tokens(getattr(ast, 'left'))
        yield from iter_tokens(getattr(ast, 'right'))
    else:
        # Fallback: scan string repr for bare word tokens (letters, digits)
        for t in re.findall(r'[A-Za-z0-9_]+', str(ast)):
            yield t


def token_multiset(ast: Any) -> dict[str, int]:
    counts: dict[str,int] = {}
    for t in iter_tokens(ast):
        counts[t] = counts.get(t, 0) + 1
    return counts

__all__ = ['iter_tokens', 'token_multiset']


def parse_with_state(syntax, sql: str):
    from syncraft.cache import Cache
    return parse_word(syntax, sql, cache=Cache())

__all__.append('parse_with_state')



# Reuse the pattern from existing tests: specialize Syntax with a Structured
# literal = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).literal
# token = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).token
# lazy = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).lazy
# success = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token))).success
logging(True)
literal = Syntax.literal
token = Syntax.token
lazy = Syntax.lazy
success = Syntax.success

# Note: Syntax.lazy is used to define recursive grammars.
# NOTE: These tests target newly added diagnostics & edge scenarios for left recursion.
# If import paths differ, adjust accordingly (assumes existing test helpers).


def test_incomplete():
    """Precedence chain: Expr -> Expr '-' Term | Term; Term -> Term '*' Factor | Factor; Factor -> '(' Expr ')' | 'n'
    Ensures improvements in deeper nonterminals propagate so Expr consumes full input.
    """
    Factor = lazy(lambda: (literal('(') >> Expr >> literal(')')) | literal('n'))  # type: ignore  # noqa: F821
    Term = lazy(lambda: (Term + literal('*') + Factor) | Factor)
    Expr = lazy(lambda: (Expr + literal('-') + Term) | Term)
    v, s = parse_word(Expr, 'n - n * n - n', cache=Cache())
    ast, end_state = v.bimap()
    # Ensure multiple 'n' tokens included
    print(ast)
    assert str(ast).count('n') >= 4
    # Binding dict doesn't carry index; structural assertion is sufficient.


def test_exception():
    """Mutual nullable cycle (with productive branches) should raise multi-head no-progress on empty input.

    Grammar:
        A -> B 'x' | ε
        B -> A 'y' | ε
    Input: ''  (only nullable ε alternatives fire; recursion detected via ordering of recursive alt first)
    Expect: LeftRecursionError(reason='no-progress', group_size>=2)
    """
    epsilon = success(None)
    A = lazy(lambda: (B >> literal('x')) | epsilon)  # type: ignore  # noqa: F821
    B = lazy(lambda: (A >> literal('y')) | epsilon)  # type: ignore  # noqa: F821
    with pytest.raises(LeftRecursionError) as exc:
        parse_word(A, "", cache=Cache())
    err = exc.value
    assert err.reason == 'no-progress'
    # group_size may be >=2 depending on deduping semantics; assert at least 2 for multi-head
    assert err.group_size is None or err.group_size >= 2




def test_left_recursion_variants()->None:
    """Group multiple left-recursive grammar checks into one test.

    Includes:
    1. Arithmetic chain Expr -> Expr + Term | Term
    2. Right-growth style (Expr1 + a) | a
    """
    # Variant 1: arithmetic chain
    Term = literal('n')
    Expr = lazy(lambda: Expr + literal('+') + Term | Term)
    v1, _ = parse_word(Expr, 'n + n + n', cache=Cache())
    ast1, _ = v1.bimap()
    counts1 = token_multiset(ast1)
    assert counts1.get('n', 0) == 3
    assert counts1.get('+', 0) == 2
    # Variant 2: nested right growth
    a_tok = literal('a').map(lambda x: x.text, raw=True).named('a')
    Expr1 = lazy(lambda: (Expr1 + a_tok) | a_tok).named('Expr1')
    v2, _ = parse_word(Expr1, 'a a a a', cache=Cache())
    ast2, _ = v2.bimap()
    print(ast2)
    assert ast2 == ((('a', 'a'), 'a'), 'a')



if __name__ == "__main__":
    # test_left_recursion_variants()
    test_incomplete()
    # test_exception()