from __future__ import annotations
import pytest
from syncraft.regex import (
    parse, verify,
    literal, anchor, shorthand,atom, dot, quantifier, char_class, group, piece, branch, regex_syntax,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
from syncraft.algebra import Error
import random
import string
import re



def test_multi_recursion():
    pattern = "((a|b)c(d|e(f|g(h|i(j|k(l|m(n|o(p|q(r|s(t|u(v|w(x|y(z))))))))))))))"
    ok, myerr, err = verify(pattern)
    assert ok, f"Pattern failed to parse: {pattern}\nRe Error: {err}\nMy Error: {myerr}"

def test_alternation_in_group():
    pattern = "(a|b)"
    ok, myerr, err = verify(pattern)
    assert ok, f"Pattern failed to parse: {pattern}\nRe Error: {err}\nMy Error: {myerr}"

if __name__ == "__main__":
    test_multi_recursion()
    test_alternation_in_group()
