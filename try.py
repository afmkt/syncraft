from __future__ import annotations

from syncraft.ast import Then, ThenKind, Many, Choice, ChoiceKind, Token, Marked, Nothing, Any
from syncraft.algebra import Error
from syncraft.parser import  parse_word
import syncraft.generator as gen
from syncraft.syntax import Syntax
from syncraft.cache import Cache



literal = Syntax.literal

def from_string(string: str) -> Token:
    return Token(text=string)

def test1_simple_then() -> None:
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    # print("---" * 40)
    # print(ast)
    # generated, bound = gen.generate_with(syntax, ast)
    # print("---" * 40)
    # print(generated)
    # assert ast == generated
    # value, bmap = generated.bimap()
    # print(value)
    # u, v = gen.generate_with(syntax, bmap(value))
    # assert u == generated


if __name__ == "__main__":
    test1_simple_then()