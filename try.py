from syncraft.ebnf import EBNF, GrammarDef
from syncraft.syntax import Syntax
import pytest
from rich import print
def test_ebnf_to_syntax_and_back():
    ebnf_text = """
    expr = term { ('+' | '-') term };
    term = factor { ('*' | '/') factor };
    factor = number | '(' expr ')';
    number = digit { digit };
    digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9';
    """
    # Parse EBNF to AST
    ast = EBNF.parse(ebnf_text)
    assert isinstance(ast, GrammarDef)
    # Convert AST to Syntax
    syntax = ast.syntax(Syntax, {}, set())
    # Convert Syntax back to EBNF (via GrammarDef.from_syntax)
    graph = syntax.graph()
    roundtrip_ast = GrammarDef.from_graph(graph)
    # The roundtrip AST should have the same rule names
    assert set(r.name for r in ast.rules) == set(r.name for r in roundtrip_ast.rules)
    # Optionally, check that converting back to Syntax yields equivalent structure
    roundtrip_syntax = roundtrip_ast.syntax(Syntax, {}, set())
    assert str(syntax) == str(roundtrip_syntax)

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



if __name__ == "__main__":
    test_single_rule_ebnf_to_syntax()
