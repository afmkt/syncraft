from __future__ import annotations
from syncraft.ast import Token
from syncraft.regex import (
    parse_regex, unicode_category_escape, unicode_letter,
    literal, anchor, shorthand,atom, dot, quantifier, char_class, group, piece, branch, regex,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)

from rich import print

def test_unicode_letter():
    """Test parsing of unicode letters."""
    result = parse_regex(unicode_letter, "Lu")
    print(result)
    assert isinstance(result, Token)
    

def test_unicode_category_escape():
    """Test parsing of unicode category escapes."""
    result = parse_regex(unicode_category_escape, r"\p{L}")
    print(result)
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert not p.atom.negated
    assert p.atom.categories == ("Lu",)


def test_unicode_category_escape_negated():
    """Test parsing of negated unicode category escapes."""
    result = parse_regex(regex, r"\P{Lm}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert p.atom.negated
    assert p.atom.categories == ("Lm",)


def test_unicode_category_escape_multiple():
    """Test parsing of unicode category escapes with multiple categories."""
    result = parse_regex(regex, r"\p{LuLl}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert not p.atom.negated
    assert p.atom.categories == ("Lu", "Ll")

if __name__ == "__main__":
    test_unicode_letter()
    # test_unicode_category_escape()
    # test_unicode_category_escape_negated()
    # test_unicode_category_escape_multiple()