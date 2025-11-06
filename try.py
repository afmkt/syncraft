from __future__ import annotations
from syncraft.regex import (
    parse_regex, parse,
    literal, anchor, shorthand,atom, dot, quantifier, char_class, group, piece, branch, regex_syntax,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)

def test_load():
    """Test parsing of unicode category escapes."""
    result = parse(r"\p{L}")
    assert isinstance(result, Regex)
    assert len(result.branches) == 2


if __name__ == "__main__":
    test_load()
