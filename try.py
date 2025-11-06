from __future__ import annotations
import pytest
# LeftRecursionError no longer imported; xfail test does not enforce error path.
from syncraft.syntax import Syntax
from syncraft.ast import Many
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
def t0()->None:
    """Previously unproductive S → S S | 'a' succeeds; confirm collapse result."""
    S1 = lazy(lambda: (S1 >> S1) | literal('a'))
    v, _ = parse_word(S1, 'a a a a a', cache=Cache())
    ast, _ = v.bimap()
    assert str(ast) == '((((t.a,),),),)'



def t1()->None:
    """Additional confirmation of S → S S | 'a' collapse behavior (single terminal)."""
    S1 = lazy(lambda: (S1 >> S1) | literal('a'))
    v, _ = parse_word(S1, 'a a a', cache=Cache())
    ast, _ = v.bimap()
    print(v, ast)
    assert str(ast) == '((t.a,),)'



if __name__ == "__main__":
    t1()
