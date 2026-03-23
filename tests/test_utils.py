from __future__ import annotations
from typing import Any, Iterable
from syncraft.token import Token

import re
def parse_word(syntax, data: str):
    from syncraft.token import Token
    from typing import List
    import re
    from syncraft.parser import parse_data
    tokens: List[Token]  = [Token(text=t) for t in re.split(r'[\x00-\x1F\x7F\s]+', data)]
    return parse_data(syntax, tokens)

# Utility to extract all token texts from a (possibly nested) AST structure produced by parse_word.

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

__all__ = ['iter_tokens', 'token_multiset']


