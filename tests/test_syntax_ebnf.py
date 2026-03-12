import pytest
from syncraft.syntax import Syntax

def test_syntax_ebnf_and_from_ebnf_roundtrip():
    ebnf_text = '''
    expr = term { ('+' | '-') term };
    term = factor { ('*' | '/') factor };
    factor = number | '(' expr ')';
    number = digit { digit };
    digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9';
    '''
    # Build Syntax from EBNF
    syntax = Syntax.from_ebnf(ebnf_text)
    # Export back to EBNF
    ebnf_out = syntax.ebnf()
    # Re-import and check equivalence
    syntax2 = Syntax.from_ebnf(ebnf_out)
    # The exported EBNF should parse the same language
    assert str(syntax) == str(syntax2)
    # The roundtripped EBNF should contain all rule names
    for rule in ["expr", "term", "factor", "number", "digit"]:
        assert rule in ebnf_out

def test_syntax_from_ebnf_parse():
    ebnf_text = "word = 'a' 'b'*;"
    syntax = Syntax.from_ebnf(ebnf_text)
    result = syntax.parse("abbb")
    assert result is not None
    # Should parse 'abbb' as a sequence
    assert "a" in str(result)
    assert "b" in str(result)


def test_syntax_ebnf_export_simple():
    ebnf_text = "rule = 'x' | 'y';"
    syntax = Syntax.from_ebnf(ebnf_text)
    ebnf_out = syntax.ebnf()
    assert "rule" in ebnf_out
    assert "'x'" in ebnf_out and "'y'" in ebnf_out
