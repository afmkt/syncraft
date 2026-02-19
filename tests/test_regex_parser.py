from __future__ import annotations
from syncraft.regex import (
    parse, RE, 
    UnsupportedFeature,
    LiteralAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
from syncraft.algebra import Error

from syncraft.syntax import Syntax as S
from syncraft.fa import Builder as B


def test_literal_characters():
    """Test parsing of literal characters."""
    # Single literal character
    result = parse("a", syntax=RE.literal)
    assert result == "a"


def test_literal_digits():
    """Test parsing of literal digits."""
    result = parse("1", syntax=RE.literal)
    assert result == "1"


def test_literal_special_chars():
    """Test parsing of literal special characters that are not metacharacters."""
    # Characters that are allowed as literals (not in the excluded set)
    result = parse("@", syntax=RE.literal)
    assert result == "@"


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
        result = parse(pattern, syntax=RE.literal)
        print(result)
        assert result == expected
        assert len(result) == 2


def test_unicode_escapes():
    """Test parsing of unicode escape sequences."""
    test_cases = [
        (r"\x41", "A"),  # \x41 = 'A'
        (r"\u0041", "A"),  # \u0041 = 'A'
        (r"\U00000041", "A"),  # \U00000041 = 'A'
        (r"\N{LATIN CAPITAL LETTER A}", "A"),  # Unicode name
    ]

    for pattern, expected in test_cases:
        result = parse(pattern, syntax=RE.literal)
        assert result == expected


def test_escaped_metacharacters():
    """Test parsing of escaped metacharacters."""
    metachars = r"\\\.\[\]\(\)\{\}\|\+\*\?\^\$"
    result = parse(metachars, syntax=RE.literal.many())
    assert len(result) == len(metachars) // 2  # Each escape sequence becomes one piece
    expected_chars = r"\.[](){}|+*?^$"
    for i, expected in enumerate(expected_chars):
        p = result[i]
        assert p == expected


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
        result = parse(pattern, syntax=RE.anchor)
        assert isinstance(result, UnsupportedFeature)
        


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
        # result = parse_regex(shorthand.to(ShorthandAtom), pattern)
        tmp = parse(pattern)
        assert isinstance(tmp, Regex)
        result = tmp.branches[0].pieces[0].atom

        assert result.kind == expected_kind # type: ignore


def test_dot_atom():
    """Test parsing of dot (.) atom."""
    # result = parse_regex(atom, ".")
    tmp = parse(".")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, DotAtom)


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
        result = parse(pattern, syntax=RE.piece)
        tmp = parse(pattern)
        assert isinstance(tmp, Regex)
        result = tmp.branches[0].pieces[0]

        assert isinstance(result, Piece)
        assert result.quantifier == expected_quantifier, f"Failed for pattern: {pattern}, got {result.quantifier}, expected {expected_quantifier}"
        assert result.atom == LiteralAtom(text="a"), f"Failed for pattern: {pattern}, got atom {result.atom}, expected LiteralAtom(text='a')"
        

def test_character_classes_simple():
    """Test parsing of simple character classes."""
    # result = parse_regex(atom, "[]abc]")
    tmp = parse("[]abc]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert not result.negated
    assert set(result.items) == {"]", "a", "b", "c"}
    # result = parse_regex(atom, "[a]bc]")
    pattern = "[a]bc]"
    tmp = parse(pattern)
    assert isinstance(tmp, Regex), f"Parse {pattern} failed, {str(tmp)}"
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert not result.negated
    assert set(result.items) == {"a"}




def test_character_classes_negated():
    """Test parsing of negated character classes."""
    # result = parse_regex(atom, "[^abc]")
    tmp = parse("[^abc]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert result.negated
    assert set(result.items) == {"a", "b", "c"} 

    # result = parse_regex(atom, "[^]abc]")
    tmp = parse("[^]abc]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert result.negated
    assert set(result.items) == {"]", "a", "b", "c"} 

    # result = parse_regex(atom, "[^a]bc]")
    pattern = "[^a]bc]"
    tmp = parse(pattern)
    assert isinstance(tmp, Regex), f"Parse {pattern} failed, {str(tmp)}"
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert result.negated
    assert set(result.items) == {"a"} 

def test_character_classes_with_ranges():
    """Test parsing of character classes with ranges."""
    # result = parse_regex(atom, "[a-zA-Z0-9]")
    tmp = parse("[a-zA-Z0-9]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert not result.negated
    assert len(result.items) == 3
    assert result.items[0] == CharRange(start="a", end="z")
    assert result.items[1] == CharRange(start="A", end="Z")
    assert result.items[2] == CharRange(start="0", end="9")
    # result = parse_regex(atom, "[^a-zA-Z0-9]")
    tmp = parse("[^a-zA-Z0-9]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert result.negated
    assert len(result.items) == 3
    assert result.items[0] == CharRange(start="a", end="z")
    assert result.items[1] == CharRange(start="A", end="Z")
    assert result.items[2] == CharRange(start="0", end="9")


def test_character_classes_with_escaped_chars():
    """Test parsing of character classes with escaped characters."""
    # result = parse_regex(atom, r"[\[\]\-\.\\]")
    tmp = parse(r"[\[\]\-\.\\]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert not result.negated
    assert len(result.items) == 5
    assert set(result.items) == {"[", "]", "-", ".", "\\"}

    # result = parse_regex(atom, r"[^\[\]\-\.\\]")
    tmp = parse(r"[^\[\]\-\.\\]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert result.negated
    assert len(result.items) == 5
    assert set(result.items) == {"[", "]", "-", ".", "\\"}



def test_character_classes_with_shorthands():
    """Test parsing of character classes containing shorthands."""
    # result = parse_regex(atom, r"[\d\s\w]")
    tmp = parse(r"[\d\s\w]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert not result.negated
    assert len(result.items) == 3
    assert result.items[0] == ShorthandAtom(kind=ShorthandKind.DIGIT)
    assert result.items[1] == ShorthandAtom(kind=ShorthandKind.SPACE)
    assert result.items[2] == ShorthandAtom(kind=ShorthandKind.WORD)
    
    # result = parse_regex(atom, r"[^\d\s\w]")
    tmp = parse(r"[^\d\s\w]")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, CharClassAtom)
    assert result.negated
    assert len(result.items) == 3
    assert result.items[0] == ShorthandAtom(kind=ShorthandKind.DIGIT)
    assert result.items[1] == ShorthandAtom(kind=ShorthandKind.SPACE)
    assert result.items[2] == ShorthandAtom(kind=ShorthandKind.WORD)


def test_groups_capture():
    """Test parsing of capturing groups."""
    # result = parse_regex(atom, "(abc)")
    tmp = parse("(abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.CAPTURE
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier

def test_groups_non_capture():
    """Test parsing of non-capturing groups."""
    # result = parse_regex(group, "(?:abc)")
    tmp = parse("(?:abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.NON_CAPTURE
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier


def test_groups_named():
    """Test parsing of named capturing groups."""
    # result = parse_regex(group, "(?P<name>abc)")
    tmp = parse("(?P<name>abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.CAPTURE
    assert result.name == "name"
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier


def test_groups_lookahead():
    """Test parsing of positive lookahead groups."""
    # result = parse_regex(group, "(?=abc)")
    tmp = parse("(?=abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.LOOKAHEAD
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier

def test_groups_negative_lookahead():
    """Test parsing of negative lookahead groups."""
    # result = parse_regex(group, "(?!abc)")
    tmp = parse("(?!abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.NEG_LOOKAHEAD
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier


def test_groups_lookbehind():
    """Test parsing of positive lookbehind groups."""
    # result = parse_regex(group, "(?<=abc)")
    tmp = parse("(?<=abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.LOOKBEHIND
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier


def test_groups_negative_lookbehind():
    """Test parsing of negative lookbehind groups."""
    # result = parse_regex(group, "(?<!abc)")
    tmp = parse("(?<!abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.NEG_LOOKBEHIND
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier


def test_groups_flags_only():
    """Test parsing of flag-only groups."""
    # result = parse_regex(group, "(?i)")
    tmp = parse("(?i)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.FLAGS
    assert result.inline_flags
    assert result.inline_flags.enabled == ("i",)
    assert result.inline_flags.disabled is None
    assert result.regex is None



def test_groups_flags_with_disable():
    """Test parsing of flag groups with disabled flags."""
    # result = parse_regex(group, "(?im-s)")
    tmp = parse("(?im-s)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.FLAGS
    assert result.inline_flags
    assert result.inline_flags.enabled == ("i", "m")
    assert result.inline_flags.disabled == ("s",)
    assert result.regex is None


def test_groups_flags_scoped():
    """Test parsing of scoped flag groups."""
    # result = parse_regex(group, "(?i:abc)")
    tmp = parse("(?i:abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.FLAGS_SCOPED
    assert result.inline_flags
    assert result.inline_flags.enabled == ("i",)
    assert result.inline_flags.disabled is None
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier


def test_groups_flags_scoped_with_disable():
    """Test parsing of scoped flag groups with disabled flags."""
    # result = parse_regex(group, "(?im-s:abc)") --- IGNORE ---
    tmp = parse("(?im-s:abc)")
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom
    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.FLAGS_SCOPED
    assert result.inline_flags
    assert result.inline_flags.enabled == ("i", "m")
    assert result.inline_flags.disabled == ("s",)
    assert isinstance(result.regex, Regex)
    assert len(result.regex.branches[0].pieces) == 3
    for i, char in enumerate("abc"):
        p = result.regex.branches[0].pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier



def test_regex_comprehensive():
    result = parse(r"\p{LuLl}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert not p.atom.negated
    assert p.atom.categories == ("Lu", "Ll")

def test_regex_negated():
    result = parse(r"\P{LuLl}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert p.atom.negated
    assert p.atom.categories == ("Lu", "Ll")

def test_regex_complex():
    result = parse(r"\p{L}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert not p.atom.negated
    assert p.atom.categories == ("L",)



def test_regex_alternation():
    """Test parsing of alternation (OR) expressions."""
    result = parse( "abc|def|ghi")
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


def test_regex_complex_regex():
    """Test parsing of a complex regex combining multiple grammar rules."""
    pattern = r"^(\w+)\s+(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    result = parse(pattern)
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    # Should have: ^ ( \w+ ) \s+ ( \d{1,3} ) \. ( \d{1,3} ) \. ( \d{1,3} ) \. ( \d{1,3} ) $
    assert len(b.pieces) == 11

    # Check anchors
    assert isinstance(b.pieces[0].atom, UnsupportedFeature)
    # assert b.pieces[0].atom.kind == AnchorKind.LINE_START
    assert isinstance(b.pieces[-1].atom, UnsupportedFeature)
    # assert b.pieces[-1].atom.kind == AnchorKind.LINE_END


def test_regex_unicode_category_escape():
    """Test parsing of unicode category escapes."""
    result = parse(r"\p{L}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 1
    b = result.branches[0]
    assert len(b.pieces) == 1
    p = b.pieces[0]
    assert isinstance(p.atom, UnicodeCategoryAtom)
    assert not p.atom.negated
    assert p.atom.categories == ("L",)


def test_neg_lookahead():
    negative_lookahead = S.seq(S.lex(B.lit("(?!")).named('"(?!"'), +RE.regex, RE.rparen)
    nl = r"(?!\1)"
    ret = parse(nl, syntax=negative_lookahead)
    assert not isinstance(ret, Error)

def test_noncap():    
    noncapturing = S.seq(S.lex(B.lit("(?:")).named('"(?:"'), +RE.regex, RE.rparen)
    noncap = r"(?:['\"])"
    ret = parse(noncap, syntax=noncapturing)
    assert not isinstance(ret, Error)
    

def test_named():
    named = S.seq(S.lex(B.lit("(?P<")).named('"(?P<"'), +RE.name, RE.greater, +RE.regex, RE.rparen)
    s = r"(?P<quote>['\"])"
    ret = parse(s, syntax=named)
    assert not isinstance(ret, Error)
    

def test_complex():
    pattern = r"(?:(?P<quote>['\"])(?:(?!\1).)*\1)"
    ret = parse(pattern, syntax=RE.regex)
    assert not isinstance(ret, Error)
    


def test_complex1():
    pattern = r'l*[^UUf\w]?|\w{5}\W{0,5}\w*(?w)|J*\B'
    ret= parse(pattern, syntax=RE.regex)
    assert not isinstance(ret, Error)
    