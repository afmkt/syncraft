from __future__ import annotations
from syncraft.ast import Nothing
from syncraft.regex import (
    parse_regex, S, B,
    literal, atom, shorthand, dot, quantifier, char_class, group, piece, branch, regex,
    braced_quantifier, lsquare, rsquare, caret, class_item, leading_rsquare,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
from syncraft.ast import Token
from rich import print




def test_groups_capture():
    """Test parsing of capturing groups."""
    result = parse_regex(group, "(abc)")
    print(result)

def test_groups_non_capture():
    """Test parsing of non-capturing groups."""
    result = parse_regex(literal, "(?:abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.NON_CAPTURE
    assert isinstance(p.atom.pattern, Regex)


def test_groups_named():
    """Test parsing of named capturing groups."""
    result = parse_regex(literal, "(?P<name>abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.CAPTURE
    assert p.atom.name == "name"
    assert isinstance(p.atom.pattern, Regex)

def test_groups_lookahead():
    """Test parsing of positive lookahead groups."""
    result = parse_regex(literal, "(?=abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.LOOKAHEAD
    assert isinstance(p.atom.pattern, Regex)


def test_groups_negative_lookahead():
    """Test parsing of negative lookahead groups."""
    result = parse_regex(literal, "(?!abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.NEG_LOOKAHEAD
    assert isinstance(p.atom.pattern, Regex)


def test_groups_lookbehind():
    """Test parsing of positive lookbehind groups."""
    result = parse_regex(literal, "(?<=abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.LOOKBEHIND
    assert isinstance(p.atom.pattern, Regex)


def test_groups_negative_lookbehind():
    """Test parsing of negative lookbehind groups."""
    result = parse_regex(literal, "(?<!abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.NEG_LOOKBEHIND
    assert isinstance(p.atom.pattern, Regex)


def test_groups_flags_only():
    """Test parsing of flag-only groups."""
    result = parse_regex(literal, "(?i)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.FLAGS
    assert p.atom.inline_flags == ("i",)
    assert p.atom.disabled_flags is None
    assert p.atom.pattern is None


def test_groups_flags_with_disable():
    """Test parsing of flag groups with disabled flags."""
    result = parse_regex(literal, "(?im-s)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.FLAGS
    assert p.atom.inline_flags == ("i", "m")
    assert p.atom.disabled_flags == ("s",)
    assert p.atom.pattern is None


def test_groups_flags_scoped():
    """Test parsing of scoped flag groups."""
    result = parse_regex(literal, "(?i:abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.FLAGS_SCOPED
    assert p.atom.inline_flags == ("i",)
    assert p.atom.disabled_flags is None
    assert isinstance(p.atom.pattern, Regex)


def test_groups_flags_scoped_with_disable():
    """Test parsing of scoped flag groups with disabled flags."""
    result = parse_regex(literal, "(?im-s:abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.FLAGS_SCOPED
    assert p.atom.inline_flags == ("i", "m")
    assert p.atom.disabled_flags == ("s",)
    assert isinstance(p.atom.pattern, Regex)


def test_alternation():
    """Test parsing of alternation (OR) expressions."""
    result = parse_regex(literal, "abc|def|ghi")
    assert isinstance(result, Regex)
    assert len(result.branches) == 3

    # Check first branch
    branch1 = result.branches[0]
    assert len(branch1.pieces) == 3
    for i, char in enumerate("abc"):
        p = branch1.pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char

    # Check second branch
    branch2 = result.branches[1]
    assert len(branch2.pieces) == 3
    for i, char in enumerate("def"):
        p = branch2.pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char

    # Check third branch
    branch3 = result.branches[2]
    assert len(branch3.pieces) == 3
    for i, char in enumerate("ghi"):
        p = branch3.pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char


def test_complex_regex():
    """Test parsing of a complex regex combining multiple grammar rules."""
    pattern = r"^(\w+)\s+(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    result = parse_regex(literal, pattern)
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    # Should have: ^ ( \w+ ) \s+ ( \d{1,3} ) \. ( \d{1,3} ) \. ( \d{1,3} ) \. ( \d{1,3} ) $
    assert len(b.pieces) == 11

    # Check anchors
    assert isinstance(b.pieces[0].atom, AnchorAtom)
    assert b.pieces[0].atom.kind == AnchorKind.LINE_START
    assert isinstance(b.pieces[-1].atom, AnchorAtom)
    assert b.pieces[-1].atom.kind == AnchorKind.LINE_END


def test_unicode_category_escape():
    """Test parsing of unicode category escapes."""
    result = parse_regex(literal, r"\p{L}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert not p.atom.negated
    assert p.atom.categories == ("L",)


def test_unicode_category_escape_negated():
    """Test parsing of negated unicode category escapes."""
    result = parse_regex(literal, r"\P{L}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert p.atom.negated
    assert p.atom.categories == ("L",)


def test_unicode_category_escape_multiple():
    """Test parsing of unicode category escapes with multiple categories."""
    result = parse_regex(literal, r"\p{LuLl}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert not p.atom.negated
    assert p.atom.categories == ("Lu", "Ll")


if __name__ == "__main__":
    test_groups_capture()