from __future__ import annotations
from syncraft.ast import Nothing, Token, Lazy
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
from syncraft.cache import LeftRecursionError
from syncraft.cache import Cache
from syncraft.regex import (
    parse_regex, parse,
    
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
import syncraft.fa as fa
import re
import pytest
from typing import Any, Iterable

# fa.forbidden = True  # prevent accidental __str__ use in FAState
# Utility to extract all token texts from a (possibly nested) AST structure produced by parse_word.

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

# S = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token)))
S = Syntax
literal = S.literal
token = S.token
lazy = S.lazy

def from_string(string: str) -> Token:
    return Token(text=string)


def test_direct_left_recursion_unproductive_now_productive()->None:
    """Previously unproductive S → S S | 'a' succeeds; confirm collapse result."""
    S1 = lazy(lambda: (S1 >> S1) | literal('a').named('a')).named('S1')
    v, _ = parse_word(S1, 'a a a a a', cache=Cache())
    ast, _ = v.bimap()
    assert str(ast) == '((((t.a,),),),)'


def test_direct_left_recursion_collapse()->None:
    """Collapse form S → S S | 'a' should yield a single terminal due to '>>' semantics."""
    S1 = lazy(lambda: (S1 >> S1) | literal('a'))
    v, _ = parse_word(S1, 'a', cache=Cache())
    ast, _ = v.bimap()
    assert str(ast) == 't.a'


def test_direct_left_recursion_growth_still_collapses()->None:
    """Additional confirmation of S → S S | 'a' collapse behavior (single terminal)."""
    S1 = lazy(lambda: (S1 >> S1) | literal('a'))
    v, _ = parse_word(S1, 'a a a', cache=Cache())
    ast, _ = v.bimap()
    assert str(ast) == '((t.a,),)'


def test_iteration_cap_metrics_single_head():
    Term = literal('n')
    Expr = lazy(lambda: (Expr + literal('+') + Term) | Term)
    cache = Cache()
    cache.max_growth_iterations = 1
    with pytest.raises(LeftRecursionError) as exc:
        parse_word(Expr, 'n + n + n + n', cache=cache)
    err = exc.value
    assert err.limit == 1
    assert err.reason == 'iteration-cap'
    assert err.group_size == 1



if __name__ == '__main__':
    test_direct_left_recursion_unproductive_now_productive()
    test_direct_left_recursion_collapse()
    test_direct_left_recursion_growth_still_collapses()
    test_iteration_cap_metrics_single_head()
    pass
