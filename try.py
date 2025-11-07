from __future__ import annotations
import pytest
# LeftRecursionError no longer imported; xfail test does not enforce error path.
from syncraft.syntax import Syntax
from syncraft.ast import Token
from syncraft.parser import parse_word
from syncraft.cache import logging
from syncraft.cache import Cache
from rich import print
import re
from typing import Any, Iterable
import syncraft.generator as gen

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



logging(True)
literal = Syntax.literal
token = Syntax.token
lazy = Syntax.lazy
success = Syntax.success



def t0()->None:
    """Previously unproductive S → S S | 'a' succeeds; confirm collapse result."""
    S1 = lazy(lambda: (S1 // S1) | literal('a'), flatten=True)
    v, _ = parse_word(S1, 'a a a a a', cache=Cache())
    generated, bound = gen.generate_with(S1, v)
    assert v.mapped == generated.mapped
    ast, back = v.bimap()
    assert ast == back(ast).mapped
    print(ast)
    
    




def t1()->None:
    """Previously unproductive S → S S | 'a' succeeds; confirm collapse result."""
    S1 = lazy(lambda: (S1 >> S1) | literal('a'), flatten=True)
    v, _ = parse_word(S1, 'a a a a a', cache=Cache())
    generated, bound = gen.generate_with(S1, v)
    assert v.mapped == generated.mapped
    ast, back = v.bimap()
    assert ast == back(ast).mapped
    print(ast)

def t2()->None:
    """Previously unproductive S → S S | 'a' succeeds; confirm collapse result."""
    S1 = lazy(lambda: (S1 + S1) | literal('a'), flatten=True)
    v, _ = parse_word(S1, 'a a a a a', cache=Cache())
    generated, bound = gen.generate_with(S1, v)
    assert v.mapped == generated.mapped
    ast, back = v.bimap()
    assert ast == back(ast).mapped
    print(ast)



def test_multi_recursion()->None:
    NUM = literal(re.compile(r'\d+'))
    PLUS = literal('+')
    Expr = lazy(lambda: (Expr + PLUS + NUM) | NUM) 
    v,_ = parse_word(Expr, '1 + 2 + 3', cache=Cache())
    generated, bound = gen.generate_with(Expr, v)
    assert v.mapped == generated.mapped
    ast, back = v.bimap()
    assert ast == back(ast).mapped

    raw,_ = v.bimap()
    # Raw structure assertions
    assert isinstance(raw, tuple) and len(raw) == 3
    assert isinstance(raw[0], tuple) and len(raw[0]) == 3  # left nested
    assert str(raw[1]) == 't.+'
    assert str(raw[2]) == 't.3'

    NUM_M = NUM.iso(lambda t: int(t.text), lambda n: Token(text=str(n)))  
    ExprM = lazy(lambda: (ExprM + PLUS + NUM_M) | NUM_M) 
    v2,_ = parse_word(ExprM, '1 + 2 + 3', cache=Cache())
    generated, bound = gen.generate_with(ExprM, v2)

    print(generated)
    assert v2.mapped == generated.mapped

    ast, back = v2.bimap()
    assert ast == back(ast).mapped



if __name__ == "__main__":
    test_multi_recursion()
