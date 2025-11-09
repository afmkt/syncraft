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
    print(g.str_node)
    # print(g1.str_node)
    assert g1.root == g.root, "Reconstructed graph root should match original"
    assert len(g1.edges) == len(g.edges), "Reconstructed graph should have same number of edges"
    assert g1.nodes == g.nodes, "Reconstructed graph should have same set of nodes"
    assert g1.edges == g.edges, "Reconstructed graph should have same set of edges"
    assert g1 == g, "Reconstructed graph should be equal to original"



def test_alternation_in_group():
    TEST_CASES = [
        ("quoted_string", r"(?:(?P<quote>['\"])(?:(?!\1).)*\1)", True),
        ("flag_all", r"(?aLmsux)", True),
        ('fuzzing', r'.E?|\B\w?(?.{2,3}.)\s{1,5}', True),
        ("flag_disable", r"(?-i)a", True),
        ("invalid_named_group", r"(?P<1name>a)", False),
        ("invalid_flag", r"(?z)", False),
        ("empty_unicode_category", r"\p{}", False),
        ("unclosed_group", r"(", False),
        ("unclosed_class", r"[abc", False),
        ("invalid_quantifier_range", r"{3,2}", False),
        ("incomplete_hex", r"\x4", False),
        ("unclosed_named_group", r"(?P<name>", False),
    ]
    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        if should_pass:
            assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"
        else:
            assert not vr.ok, f"Pattern should have failed but parsed: {pattern}"


def to_raw_literal(s: str) -> str:
    # Count trailing backslashes
    n_backslashes = len(s) - len(s.rstrip("\\"))
    # A valid raw string cannot end with an odd number of backslashes
    if n_backslashes % 2 == 1:
        # fallback to repr
        return repr(s)

    # Pick the safer quote type
    if "'" in s and '"' not in s:
        quote = '"'
    else:
        quote = "'"

    return f"r{quote}{s}{quote}"



if __name__ == "__main__":
    # test_graph()
    test_alternation_in_group()
    s = r".E?|\B\w?(?.{2,3}.)\s{1,5}"
    print(to_raw_literal(s))
