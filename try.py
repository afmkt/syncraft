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



logging(True)
literal = Syntax.literal
token = Syntax.token
lazy = Syntax.lazy
success = Syntax.success



def t3():
    A = lazy(lambda: B | C).named('A')
    B = lazy(lambda: C | A).named('B')
    C = lazy(lambda: B | A).named('C')

    with pytest.raises(LeftRecursionError) as exc:
        parse_word(A, '', cache=Cache())
    assert exc.value.reason == 'no-progress'

if __name__ == "__main__":
    t3()
