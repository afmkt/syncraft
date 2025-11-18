from __future__ import annotations
import pytest
from dataclasses import dataclass, replace
from syncraft.regex import (
    parse, verify, parse_regex,
    literal, anchor, shorthand,atom, dot, char_class, group, piece, branch, regex_syntax,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
from syncraft.regex import Quantifier
from syncraft.charset import CharSet
from syncraft.syntax import Syntax
from syncraft.algebra import Error
from syncraft.alphabet import CodepointError
import random
import string
import re
# from rich import print

from typing import Type

from syncraft.ast import Token
from syncraft.fa import Builder
from syncraft.input import StreamCursor
from syncraft.lexer import ExtLexer, Lexer
from syncraft.parser import parse as parser_run, parse_data
from syncraft.syntax import Syntax
from syncraft.token import Structured, TokenMatcher, matcher, struct


from syncraft.fa import NFA, DFA
from syncraft.alphabet import Alphabet
from syncraft.parser import  parse_word
import syncraft.generator as gen
from rich import print
from syncraft.parser import parse_word




def test1():
    """Test parsing of scoped flag groups with disabled flags."""
    # result = parse_regex(group, "(?im-s:abc)") --- IGNORE ---
    tmp = parse("(?im-s:abc)", raw=False)
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom
    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.FLAGS_SCOPED
    assert result.inline_flags == ("i", "m")
    assert result.disabled_flags == ("s",)
    assert isinstance(result.pattern, Regex)
    assert len(result.pattern.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.pattern.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier

    

def test2():
    A = Syntax.literal("a")
    B = Syntax.literal("b")
    C = Syntax.literal("c")
    S = A // B // C
    x, _ = parse_word(S, "a b c", cache=None)
    print(x)
    print(x.mapped)

if __name__ == "__main__":
    # print(str(regex_syntax.svg(3)))
    test1()