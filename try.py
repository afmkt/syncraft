from __future__ import annotations
import pytest
from syncraft.regex import (
    parse, verify, parse_regex,
    literal, anchor, shorthand,atom, dot, quantifier, char_class, group, piece, branch, regex_syntax,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
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

lit = Syntax.literal


def test_graph():
    g = regex_syntax.graph()
    assert g.edges, "Graph should have edges"
    assert g.root, "Graph should have roots"
    s = Syntax.from_graph(g)
    assert s is not None, "Should be able to reconstruct syntax from graph"
    g1 = s.graph()
    
    # Test structural consistency (the main fix validation)
    # print(g1.str_node)
    assert g1.root == g.root, "Reconstructed graph root should match original"
    assert len(g1.edges) == len(g.edges), "Reconstructed graph should have same number of edges"
    assert g1.nodes == g.nodes, "Reconstructed graph should have same set of nodes"
    assert g1.edges == g.edges, "Reconstructed graph should have same set of edges"
    assert g1 == g, "Reconstructed graph should be equal to original"



def test_regex():
    pattern, expected_quantifier = ("a{3}", Quantifier(minimum=3, maximum=3, greedy=True))
    print(parse_regex(quantifier, '{3}'))
    result = parse_regex(piece, pattern)
    assert isinstance(result, Piece)
    assert result.quantifier == expected_quantifier, f"Failed for pattern: {pattern}, got {result.quantifier}, expected {expected_quantifier}"
    assert result.atom == LiteralAtom(text="a"), f"Failed for pattern: {pattern}, got atom {result.atom}, expected LiteralAtom(text='a')"


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
    print(regex_syntax.svg(3))
    test_regex()