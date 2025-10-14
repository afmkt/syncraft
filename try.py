from __future__ import annotations

from syncraft.ast import Then, ThenKind, Many, Choice, ChoiceKind, Token, Marked, Nothing, TokenClass
from syncraft.algebra import Error
from syncraft.parser import  parse_word
import syncraft.generator as gen
from syncraft.syntax import Syntax
from syncraft.lexer import CacheWithLexer

from rich import print

def from_string(string: str) -> Token:
    return Token(text=string)


literal = Syntax.config(token_class = TokenClass.simple()).literal

def test_optional():
    A = literal("a").mark("a")
    syntax = A.optional()
    ast1, bound = parse_word(syntax, "", cache=CacheWithLexer())
    v1, _ = ast1.bimap()
    assert isinstance(v1, Nothing)
    ast2, bound = parse_word(syntax, "a", cache=CacheWithLexer())
    v2, _ = ast2.bimap()
    assert v2 == Marked(name='a', value=from_string('a'))



def test_many_optional():
    A = literal("a")
    syntax = A.optional().many()
    ast1, _ = parse_word(syntax, "a a b", cache=CacheWithLexer())
    # print(ast1)
    ast2, inv = ast1.bimap()
    assert Many(value=(Choice(kind=None, value=from_string('a')), Choice(kind=None, value=from_string('a')))) == inv(ast2)


if __name__ == "__main__":
    test_many_optional()