from __future__ import annotations
from syncraft.ast import Token
from syncraft.regex import (
    parse_regex, unicode_category_escape, unicode_letter,unicode_escape,
    literal, anchor, shorthand,atom, dot, quantifier, char_class, group, piece, branch, regex,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)

from rich import print

def test_groups_named():
    """Test parsing of named capturing groups."""
    result = parse_regex(group, "(?P<name>abc)")
    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.CAPTURE
    assert result.name == "name"
    assert isinstance(result.pattern, Branch)
    assert len(result.pattern.pieces) == 3
    for i, char in enumerate("abc"):
        p = result.pattern.pieces[i]
        assert isinstance(p.atom, LiteralAtom)
        assert p.atom.text == char
        assert not p.quantifier


def test_unicode_escapes():
    """Test parsing of unicode escape sequences."""
    test_cases = [
        # (r"\x41", "A"),  # \x41 = 'A'
        # (r"\u0041", "A"),  # \u0041 = 'A'
        # (r"\U00000041", "A"),  # \U00000041 = 'A'
        (r"\N{LATIN CAPITAL LETTER A}", "A"),  # Unicode name
    ]

    for pattern, expected in test_cases:
        result = parse_regex(unicode_escape, pattern)
        print(result)
        assert result == expected

if __name__ == "__main__":
    
    test_unicode_escapes()
    