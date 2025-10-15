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
from syncraft.parser import parse_data



def test():
    literal = Syntax.config(token_class=TokenClass.simple()).literal
    syntax = literal("if")
    value, next_state = parse_data(syntax=syntax, tokens=[], cache=CacheWithLexer())

    assert isinstance(value, Error)
    assert next_state is None
    print(value)

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