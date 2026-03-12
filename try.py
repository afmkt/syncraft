from syncraft.ebnf import EBNF, GrammarDef
from syncraft.syntax import Syntax
import pytest
from rich import print

def test_single_rule_ebnf_to_syntax():
    ebnf_text = "rule = 'a' 'b' | 'c';"
    ast = EBNF.parse(ebnf_text)
    print(ast)
    syntax = ast.syntax(Syntax, {}, set())
    print(syntax)
    assert syntax is not None
    # Should have a sequence and alternation in the structure
    s = syntax.ebnf()
    print(s)
    print(EBNF.generate(s))
    assert "'a'" in s and "'b'" in s and "'c'" in s

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

def test_syntax_ebnf_export_simple():
    ebnf_text = "rule = 'x' | 'y';"
    ast1 = EBNF.parse(ebnf_text)  # Ensure it parses without error
    # print(ast1)
    syntax = ast1.syntax(Syntax, {}, set())
    # print(syntax.graph())
    ast2 = syntax.ebnf()
    print(ast2)




if __name__ == "__main__":
    # test_single_rule_ebnf_to_syntax()
    # test_syntax_ebnf_and_from_ebnf_roundtrip()
    test_syntax_ebnf_export_simple()
