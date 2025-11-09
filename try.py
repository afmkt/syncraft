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
    
    # Test structural consistency (the main fix validation)
    assert g1.root == g.root, "Reconstructed graph root should match original"
    assert len(g1.edges) == len(g.edges), "Reconstructed graph should have same number of edges"
    assert g1.nodes == g.nodes, "Reconstructed graph should have same set of nodes"
    assert g1.edges == g.edges, "Reconstructed graph should have same set of edges"
    assert g1 == g, "Reconstructed graph should be equal to original"



def test_alternation_in_group():
    pattern = "(a|b)"
    ok, myerr, err = verify(pattern)
    print(str(myerr))
    assert ok

if __name__ == "__main__":
    test_graph()
    test_alternation_in_group()
