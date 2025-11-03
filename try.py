from __future__ import annotations
import pytest
from syncraft.ast import Nothing, Token, Lazy
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
from syncraft.cache import Cache, LeftRecursionError, enable_logging

from syncraft.regex import (
    parse_regex, parse,
    
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
import syncraft.fa as fa
import re
from typing import Any, Iterable
enable_logging()
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


def test_multi_recursion()->None:
    a = literal('a').map(lambda x: x.text, raw=True).named('a')
    b = literal('b').map(lambda x: x.text, raw=True).named('b')
    c = literal('c').map(lambda x: x.text, raw=True).named('c')
    x = literal('x').map(lambda x: x.text, raw=True).named('x')
    y = literal('y').map(lambda x: x.text, raw=True).named('y')
    z = literal('z').map(lambda x: x.text).named('z')
    A = lazy(lambda: (B + x) | a).named('A')
    B = lazy(lambda: (C + y) | b).named('B')
    C = lazy(lambda: (A + z) | c).named('C')

    v, s = parse_word(A, 'a z y x', cache=Cache(logging=True))
    print(v)
    # We care about the raw AST shape (pre-bimap). Extract leaves manually.
    from syncraft.ast import Then, ThenKind
    from syncraft.algebra import Choice, ChoiceKind  # type: ignore

    def leaves(node):
        if isinstance(node, Lazy):
            return leaves(node.value)
        if isinstance(node, Then) and node.kind == ThenKind.BOTH:
            return leaves(node.left) + leaves(node.right)
        if isinstance(node, Choice):
            # For this grammar Choice.RIGHT wraps literal terminal; LEFT wraps a Then chain.
            if node.kind == ChoiceKind.RIGHT:
                return (node.value,)
            else:
                return leaves(node.value)
        if isinstance(node, str):
            return (node,)
        return ()
    print(leaves(v))
    assert leaves(v) == ('a','z','y','x')




def test_mutual_unproductive_cycle_no_progress():
    """Grammar:
        A -> B
        B -> A
    Input: ''
    Expect: LeftRecursionError(reason='no-progress') because there is no productive (non-recursive) base.
    """
    A = lazy(lambda: B)
    B = lazy(lambda: A)
    with pytest.raises(LeftRecursionError) as exc:
        parse_word(A, '', cache=Cache())
    assert exc.value.reason == 'no-progress'



def test_mutual_unproductive_cycle_no_progress_3():
    """Grammar:
        A -> B
        B -> C
        C -> A
    Input: ''
    Expect: LeftRecursionError(reason='no-progress') because there is no productive (non-recursive) base.
    """
    A = lazy(lambda: B)  
    B = lazy(lambda: C)  
    C = lazy(lambda: A)  
    with pytest.raises(LeftRecursionError) as exc:
        parse_word(A, '', cache=Cache())
    assert exc.value.reason == 'no-progress'






if __name__ == '__main__':
    test_multi_recursion()
    pass
