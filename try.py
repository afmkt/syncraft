from __future__ import annotations
from typing import Any, Tuple, Iterable
from syncraft.ast import Nothing, Token, Lazy
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
from syncraft.cache import LeftRecursionError
from syncraft.cache import Cache, set_randomization
import syncraft.generator as gen
from rich import print
import re


def iter_tokens(ast: Any) -> Iterable[str]:
    if isinstance(ast, Token):
        yield ast.text # type: ignore
    elif isinstance(ast, (tuple, list)):
        for x in ast:
            yield from iter_tokens(x)
    elif hasattr(ast, 'value') and isinstance(getattr(ast, 'value'), tuple):
        # For Then/OrElse wrappers from syncraft.ast
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





# Ensure randomization is enabled for these tests
set_randomization(True)

S = Syntax
literal = S.lit
token = S.token
lazy = S.lazy

def from_string(string: str) -> Token:
    return Token(text=string)

    

    
    









def test_generate_with_mutual_left_recursion_without_base_raises():
    # Mutual recursion with no productive base: A := B ; B := A
    A = Syntax.lazy(lambda: B)  # type: ignore[name-defined]
    B = Syntax.lazy(lambda: A)  # type: ignore[name-defined]
    try:
        generate_with(A)
    except Exception as e:
        assert isinstance(e, LeftRecursionError)


if __name__ == "__main__":
    
    test_generate_with_mutual_left_recursion_without_base_raises()
    
    # test_direct_left_recursion_unproductive_now_productive1_flatten()
    
    