from __future__ import annotations
import pytest
from syncraft.regex import (
    parse, verify,
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
from rich import print

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
    TEST_CASES = [
        ("quoted_string", r"(?:(?P<quote>['\"])(?:(?!\1).)*\1)", True),
        ("flag_disable", r"(?-i)a", True),
        ('fuzzing', '(?!)', False),
        ('fuzzing', '(?w)e*L+|[^wW]?\\S*\\D+', True),
    ]
    for name, pattern, should_pass in TEST_CASES:
        
        vr = verify(pattern, profile=True)
        assert vr.ok, f"Pattern failed to parse: {pattern}\n\nRe Error: {vr.err_re}\n\nSyncraft Error: {vr.err_syncraft}"

def test_empty_many() -> None:
    A = lit("a")
    syntax = A.many()  # This should allow empty matches
    sql = ""
    ast, bound = parse_word(syntax, sql, cache=None)
    assert ast.mapped == [], "AST mapped value should be an empty list for empty input"

def test_dfa_reverse_multiple_tags():
    # DFA for 'a' tagged as 'A', 'b' tagged as 'B'
    nfa = NFA.from_string('a', tag='A', alphabet=Alphabet(str)) | NFA.from_string('b', tag='B', alphabet=Alphabet(str))
    dfa = nfa.dfa
    rev = dfa.reverse
    s_a = rev.gen('A', random.Random(1))
    s_b = rev.gen('B', random.Random(2))
    assert s_a == 'a'
    assert s_b == 'b'



def test_charset_bytes_mode() -> None:
    b1: CharSet[int] = CharSet.create(b"\x00\x10\x20", alphabet=Alphabet(bytes))
    assert b1(0x00)
    assert not b1(0x01)
    assert b1.interval == ((0x00, 0x00), (0x10, 0x10), (0x20, 0x20))
    comp = -b1
    assert comp(0x01)
    assert not comp(0x10)

def test_codeuniverse_byte():
    u = Alphabet(bytes)
    assert u.codes == ((0, 0xFF),)
    assert u.space is bytes
    assert u.decode(0x41) == b'A'
    assert u.encode(b'A') == 0x41
    assert u.codes == ((0, 0xFF),)
    with pytest.raises(CodepointError):
        u.encode(b'AB')
    with pytest.raises(CodepointError):
        u.decode(0x100)


def test_parse_string_input_with_lexer_bind() -> None:
    alphabet = Alphabet(str)
    lexer_cls: Type[Lexer[str]] = Lexer.bind(alphabet=alphabet)
    syntax_cls = Syntax.config(lexer_class=lexer_cls)
    word = syntax_cls.lex(WORD=Builder.lit("hi").tagged("WORD"))

    value, state = parser_run(syntax=word, data=StreamCursor.from_data("hi"), cache=None)

    assert isinstance(value, Token)
    assert value.token_type == "WORD"
    assert value.text == "hi"
    assert state is not None
    assert state.ended

if __name__ == "__main__":
    
    test_regex()