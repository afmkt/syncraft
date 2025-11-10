from __future__ import annotations
import pytest
from syncraft.regex import (
    parse, verify,
    literal, anchor, shorthand,atom, dot, quantifier, char_class, group, piece, branch, regex_syntax,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
from syncraft.syntax import Syntax
from syncraft.algebra import Error
import random
import string
import re
from rich import print

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
    print(g.str_node)
    # print(g1.str_node)
    assert g1.root == g.root, "Reconstructed graph root should match original"
    assert len(g1.edges) == len(g.edges), "Reconstructed graph should have same number of edges"
    assert g1.nodes == g.nodes, "Reconstructed graph should have same set of nodes"
    assert g1.edges == g.edges, "Reconstructed graph should have same set of edges"
    assert g1 == g, "Reconstructed graph should be equal to original"


def test_optional_many():
    a = lit('a')
    S = a.optional.many()
    sql = ""
    from syncraft.cache import Cache
    ast, bound = parse_word(S, sql, cache=Cache())    
    generated, bound = gen.generate_with(S, ast)
    print(ast)
    assert ast == generated, "Parsed and generated results do not match."
    x, f = generated.bimap()
    u, v = gen.generate_with(S, f(x))
    assert u == ast


def test_regex():
    TEST_CASES = [
        ("quoted_string", r"(?:(?P<quote>['\"])(?:(?!\1).)*\1)", True),
        ("flag_disable", r"(?-i)a", True),
        ('fuzzing', '(?!)', False),
        ('fuzzing', '(?w)e*L+|[^wW]?\\S*\\D+', True),
    ]
    for name, pattern, should_pass in TEST_CASES:
        
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\n\nRe Error: {vr.err_re}\n\nSyncraft Error: {vr.err_syncraft}"

def test_empty_many() -> None:
    A = lit("a")
    syntax = A.many()  # This should allow empty matches
    sql = ""
    ast, bound = parse_word(syntax, sql, cache=None)
    assert ast.mapped == [], "AST mapped value should be an empty list for empty input"


if __name__ == "__main__":
    # test_graph()
    # test_regex()
    test_empty_many()
