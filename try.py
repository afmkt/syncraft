from __future__ import annotations
from syncraft.syntax import Syntax
from rich import print

import pytest
from syncraft.ast import TokenClass
from syncraft.parser import parse_word
from syncraft.generator import validate, generate_with
from syncraft.algebra import Error
from syncraft.lexer import CacheWithLexer
from syncraft.cache import LeftRecursionError



def test():
    literal = Syntax.config(token_class=TokenClass.simple()).literal
    Term = literal('n')
    Expr = Syntax.lazy(lambda: (Expr + literal('+') + Term) | Term)
    cache = CacheWithLexer()
    cache.max_growth_iterations = 1
    with pytest.raises(LeftRecursionError) as exc:
        parse_word(Expr, 'n + n + n + n', cache=cache)
    err = exc.value
    assert err.limit == 1
    assert err.reason == 'iteration-cap'
    assert err.group_size == 1



def test_recursion() -> None:
    literal = Syntax.literal
    A = literal('a')
    B = literal('b')
    L = Syntax.lazy(lambda: literal("if") >> (A | B) // literal('then'))

    def parens():
        return A + ~Syntax.lazy(parens) + B
    LL = parens() | L
    
    for _, node in LL.spec.walk():
        print(node)



if __name__ == "__main__":
    test()