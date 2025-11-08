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


def test_graph():
    g = regex_syntax.graph()
    assert g.edges, "Graph should have edges"
    assert g.root, "Graph should have roots"
    s = Syntax.from_graph(g)
    assert s is not None, "Should be able to reconstruct syntax from graph"
    g1 = s.graph()
    # assert g1.edges == g.edges, "Reconstructed graph should match original"
    # print(g1.root)
    print(g.root)
    assert g1.root == g.root, "Reconstructed graph root should match original"
    assert len(g1.edges) == len(g.edges), "Reconstructed graph should have same number of edges"
    assert g == g1, "Graphs should be equal"


def test_alternation_in_group():
    pattern = "(a|b)"
    ok, myerr, err = verify(pattern)
    g = regex_syntax.graph()
    g1 = myerr.graph
    assert g == g1, f"Graphs do not match for pattern: {pattern}"
    print(g)
    assert ok, f"Pattern failed to parse: {pattern}\nRe Error: {err}\nMy Error: {myerr}"

if __name__ == "__main__":
    test_graph()
    # test_alternation_in_group()
