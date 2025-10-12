from __future__ import annotations
from typing import Any
from dataclasses import dataclass
from rich import print
import pytest

from syncraft.finder import find, anything
from syncraft.parser import parse_word
from syncraft.syntax import Syntax

from syncraft.ast import TokenClass
from syncraft.lexer import CacheWithLexer
import syncraft.generator as gen
literal = Syntax.config(token_class = TokenClass.simple()).literal

# @pytest.mark.xfail(reason="Finder integration is pending")
def test1_simple_then() -> None:
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast, bound = parse_word(syntax, sql, cache=CacheWithLexer())
    print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap()
    # print(value)
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated


if __name__ == "__main__":
    test1_simple_then()