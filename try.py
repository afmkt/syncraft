from __future__ import annotations
from typing import Any, Iterable
from syncraft.ast import Nothing, Token, Lazy
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
from syncraft.cache import LeftRecursionError
from syncraft.lexer import CacheWithLexer

import re
import pytest
from syncraft.ast import TokenClass


def iter_tokens(ast: Any) -> Iterable[str]:
    if isinstance(ast, Token):
        yield ast.text
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

literal = Syntax.config(token_class = TokenClass.simple()).literal
token = Syntax.config(token_class = TokenClass.simple()).token

def from_string(string: str) -> Token:
    return Token(text=string)




def test_recursion() -> None:
    A = literal('a')
    B = literal('b')
    L = Syntax.lazy(lambda: literal("if") >> (A | B) // literal('then'))

    def parens():
        return A + ~Syntax.lazy(parens) + B
    p_code = 'a a b b'
    LL = parens() | L
    
    v, s = parse_word(LL, p_code, cache=CacheWithLexer())
    ast1, inv = v.bimap()
    assert ast1 == (
            from_string('a'), 
            (
                from_string('a'), 
                Nothing(), 
                from_string('b')
            ), 
            from_string('b')
        )
    x, y = inv(ast1).bimap()
    assert x == ast1

    vv, ss = generate_with(LL, y(x))
    assert vv == v



if __name__ == "__main__":
    test_recursion()