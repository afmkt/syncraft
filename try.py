from __future__ import annotations
import pytest
from dataclasses import dataclass, replace
# from syncraft.regex import (
#     parse, verify, parse_regex,
#     literal, anchor, shorthand,atom, dot, char_class, group, piece, branch, regex_syntax,
#     LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
#     CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
# )
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


lit = Syntax.literal


number = lit('3').many(at_least=1).map(lambda m: int(m[0].text)).named('number')
lbrace = lit('{').named('"{"')
rbrace = lit('}').named('"}"')
question = lit('?').named('"?"')
star = lit('*').named('"*"')
plus = lit('+').named('"+"')

braced_quantifier = Syntax.ochoice(
    lbrace >> number // rbrace).map(lambda n: Quantifier(minimum=n[0], maximum=n[0])
)
quantifier = (Syntax.ochoice(braced_quantifier) + ~question).map(lambda t: replace(t[0], greedy=not t[1]))



def test_regex():
    e, _ = parse_word(quantifier, '{ 3 }', cache=None)
    if isinstance(e, Error):
        print(e.deepest.error)
        print('-' * 100)
    else:
        print(e)
        print('+' * 100)

    

    # TEST_CASES = [
    #     ("quoted_string", r"(?:(?P<quote>['\"])(?:(?!\1).)*\1)", True),
    #     ("flag_disable", r"(?-i)a", True),
    #     ('fuzzing', '(?!)', False),
    #     ('fuzzing', '(?w)e*L+|[^wW]?\\S*\\D+', True),
    # ]
    # for name, pattern, should_pass in TEST_CASES:
        
    #     vr = verify(pattern, profile=True)
    #     assert vr.ok, f"Pattern failed to parse: {pattern}\n\nRe Error: {vr.err_re}\n\nSyncraft Error: {vr.err_syncraft}"





if __name__ == "__main__":
    # print(str(regex_syntax.svg(3)))
    test_regex()