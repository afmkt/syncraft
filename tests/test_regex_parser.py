from __future__ import annotations
from syncraft.regex import (
    parse_regex, 
    literal, anchor, shorthand, dot, quantifier, char_class, group, piece, branch, regex,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex
)


def test_literal_characters():
    """Test parsing of literal characters."""
    # Single literal character
    result = parse_regex(literal, "a")
    assert result.text == "a"


def test_literal_digits():
    """Test parsing of literal digits."""
    result = parse_regex(literal, "1")
    assert result.text == "1"


def test_literal_special_chars():
    """Test parsing of literal special characters that are not metacharacters."""
    # Characters that are allowed as literals (not in the excluded set)
    result = parse_regex(literal, "@")
    assert result.text == "@"


def test_control_escapes():
    """Test parsing of control escape sequences."""
    test_cases = [
        (r"\t", r"\t"),
        (r"\n", r"\n"),
        (r"\r", r"\r"),
        (r"\f", r"\f"),
        (r"\v", r"\v"),
    ]

    for pattern, expected in test_cases:
        result = parse_regex(literal, pattern)
        print(result)
        assert result.text == expected
        assert len(result.text) == 2
        assert result.token_type == 'control_escape'


def test_unicode_escapes():
    """Test parsing of unicode escape sequences."""
    test_cases = [
        (r"\x41", "A"),  # \x41 = 'A'
        (r"\u0041", "A"),  # \u0041 = 'A'
        (r"\U00000041", "A"),  # \U00000041 = 'A'
        (r"\N{LATIN CAPITAL LETTER A}", "A"),  # Unicode name
    ]

    for pattern, expected in test_cases:
        result = parse_regex(literal, pattern)
        assert result == expected


def test_escaped_metacharacters():
    """Test parsing of escaped metacharacters."""
    metachars = r"\\\.\[\]\(\)\{\}\|\+\*\?\^\$"
    result = parse_regex(literal.many(), metachars)
    assert len(result) == len(metachars) // 2  # Each escape sequence becomes one piece
    expected_chars = r"\.[](){}|+*?^$"
    for i, expected in enumerate(expected_chars):
        p = result[i]
        assert p.text == expected


def test_anchors():
    """Test parsing of anchor atoms."""
    test_cases = [
        ("^", AnchorKind.LINE_START),
        ("$", AnchorKind.LINE_END),
        (r"\A", AnchorKind.ABSOLUTE_START),
        (r"\Z", AnchorKind.ABSOLUTE_END),
        (r"\b", AnchorKind.WORD_BOUNDARY),
        (r"\B", AnchorKind.NOT_WORD_BOUNDARY),
    ]

    for pattern, expected_kind in test_cases:
        result = parse_regex(literal, pattern)
        assert isinstance(result, Regex)
        assert len(result.branches) == 1
        b = result.branches[0]
        assert len(b.pieces) == 1
        p = b.pieces[0]
        assert isinstance(p.atom, AnchorAtom)
        assert p.atom.kind == expected_kind

def test_shorthands():
    """Test parsing of shorthand character classes."""
    test_cases = [
        (r"\d", ShorthandKind.DIGIT),
        (r"\D", ShorthandKind.NOT_DIGIT),
        (r"\w", ShorthandKind.WORD),
        (r"\W", ShorthandKind.NOT_WORD),
        (r"\s", ShorthandKind.SPACE),
        (r"\S", ShorthandKind.NOT_SPACE),
    ]

    for pattern, expected_kind in test_cases:
        result = parse_regex(literal, pattern)
        assert isinstance(result, Regex)
        assert len(result.branches) == 1
        b = result.branches[0]
        assert len(b.pieces) == 1
        p = b.pieces[0]
        assert isinstance(p.atom, ShorthandAtom)
        assert p.atom.kind == expected_kind

def test_dot_atom():
    """Test parsing of dot (.) atom."""
    result = parse_regex(literal, ".")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, DotAtom)


def test_quantifiers():
    """Test parsing of quantifiers."""
    test_cases = [
        ("a?", Quantifier(minimum=0, maximum=1, greedy=True)),
        ("a*", Quantifier(minimum=0, maximum=None, greedy=True)),
        ("a+", Quantifier(minimum=1, maximum=None, greedy=True)),
        ("a{3}", Quantifier(minimum=3, maximum=3, greedy=True)),
        ("a{3,}", Quantifier(minimum=3, maximum=None, greedy=True)),
        ("a{3,5}", Quantifier(minimum=3, maximum=5, greedy=True)),
        ("a??", Quantifier(minimum=0, maximum=1, greedy=False)),
        ("a*?", Quantifier(minimum=0, maximum=None, greedy=False)),
        ("a+?", Quantifier(minimum=1, maximum=None, greedy=False)),
        ("a{3}?", Quantifier(minimum=3, maximum=3, greedy=False)),
        ("a{3,}?", Quantifier(minimum=3, maximum=None, greedy=False)),
        ("a{3,5}?", Quantifier(minimum=3, maximum=5, greedy=False)),
    ]

    for pattern, expected_quantifier in test_cases:
        result = parse_regex(literal, pattern)
        assert isinstance(result, Regex)
        assert len(result.branches) == 1
        b = result.branches[0]
        assert len(b.pieces) == 1
        p = b.pieces[0]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == "a"
        assert p.quantifier == expected_quantifier


def test_character_classes_simple():
    """Test parsing of simple character classes."""
    result = parse_regex(literal, "[abc]")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, CharClassAtom)
    assert not p.atom.negated
    assert len(p.atom.items) == 3
    assert p.atom.items == ("a", "b", "c")


def test_character_classes_negated():
    """Test parsing of negated character classes."""
    result = parse_regex(literal, "[^abc]")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, CharClassAtom)
    assert p.atom.negated
    assert len(p.atom.items) == 3
    assert p.atom.items == ("a", "b", "c")


def test_character_classes_with_ranges():
    """Test parsing of character classes with ranges."""
    result = parse_regex(literal, "[a-zA-Z0-9]")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, CharClassAtom)
    assert not p.atom.negated
    assert len(p.atom.items) == 3
    assert p.atom.items[0] == CharRange(start="a", end="z")
    assert p.atom.items[1] == CharRange(start="A", end="Z")
    assert p.atom.items[2] == CharRange(start="0", end="9")


def test_character_classes_with_escaped_chars():
    """Test parsing of character classes with escaped characters."""
    result = parse_regex(literal, r"[\[\]\-\.\\]")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, CharClassAtom)
    assert not p.atom.negated
    assert len(p.atom.items) == 4
    assert p.atom.items == ("[", "]", "-", "\\")


def test_character_classes_with_shorthands():
    """Test parsing of character classes containing shorthands."""
    result = parse_regex(literal, r"[\d\s\w]")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, CharClassAtom)
    assert not p.atom.negated
    assert len(p.atom.items) == 3
    # Note: shorthands in character classes are treated as literal atoms
    assert p.atom.items == (r"\d", r"\s", r"\w")


def test_groups_capture():
    """Test parsing of capturing groups."""
    result = parse_regex(literal, "(abc)")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, GroupAtom)
    assert p.atom.kind == GroupKind.CAPTURE
    assert p.atom.name is None
    assert isinstance(p.atom.pattern, Regex)
    # Check the inner pattern
    inner_branch = p.atom.pattern.branches[0]
    assert len(inner_branch.pieces) == 3
    for i, char in enumerate("abc"):
        inner_piece = inner_branch.pieces[i]
        assert isinstance(inner_piece.atom, LiteralAtom)
        assert inner_piece.atom.text == char


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
