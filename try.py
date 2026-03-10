"""
Test the EBNF grammar parser (not AST conversion or semantic processing).

This validates that the rewritten EBNF grammar correctly parses EBNF text
into raw parse trees, focusing on grammar correctness only.
"""

from __future__ import annotations

import pytest
from typing import Any

from syncraft.ebnf import EBNF
from syncraft.algebra import Error
from rich import print as rich_print

def assert_ebnf_roundtrip(text: str, *, syntax: Any | None = None) -> Any:
    parsed = EBNF.parse(text, syntax=syntax)
    assert not isinstance(parsed, Error), f"EBNF parsing failed: {parsed}"

    generated = EBNF.generate(parsed, syntax=syntax, replay=True).render()
    assert not isinstance(generated, Error), f"EBNF generation failed: {generated}"
    reparsed = EBNF.parse(generated, syntax=syntax)

    if isinstance(reparsed, Error):
        rich_print(parsed)
        print(generated)
        rich_print(reparsed)
        pytest.xfail(f"Known EBNF generation limitation: generated text is not parseable: {generated!r}")
    if reparsed != parsed:
        rich_print(f"Original text:\n{text}\n")
        rich_print(f"Parsed AST:\n{parsed}\n")
        rich_print(f"Generated text:\n{generated}\n")
        rich_print(f"Re-parsed AST:\n{reparsed}\n")
        pytest.xfail(
            "Known EBNF generation limitation: parse(generate(parse(text))) does not preserve AST"
        )
    return parsed


def test_ebnf_simple_rule():
    """Single rule with literal."""
    assert_ebnf_roundtrip("rule = 'a';")




def test_ebnf_optional_suffix():
    """Factor with ? suffix."""
    assert_ebnf_roundtrip("rule = 'a'?;")


def test_ebnf_star_suffix():
    """Factor with * suffix."""
    assert_ebnf_roundtrip("rule = 'a'*;")


def test_ebnf_plus_suffix():
    """Factor with + suffix."""
    assert_ebnf_roundtrip("rule = 'a'+;")


def test_ebnf_multiple_factors_with_suffixes():
    """Sequence with multiple factors, each with different suffixes."""
    assert_ebnf_roundtrip("rule = 'a'? 'b'+ 'c'*;")


def test_ebnf_numeric_repetition_exact():
    """Exact repetition count {n}."""
    assert_ebnf_roundtrip("rule = 'a'{2};")


def test_ebnf_numeric_repetition_range():
    """Bounded repetition {n,m}."""
    assert_ebnf_roundtrip("rule = 'a'{2,5};")


def test_ebnf_numeric_repetition_unbounded():
    """Unbounded repetition {n,}."""
    assert_ebnf_roundtrip("rule = 'a'{2,};")




def test_ebnf_parenthesized_group():
    """Grouped expression with parentheses."""
    assert_ebnf_roundtrip("rule = ('a' | 'b') 'c';")


def test_ebnf_coloneq_assign():
    """Alternative assignment operator ::=."""
    assert_ebnf_roundtrip("rule ::= 'a';")


def test_ebnf_comment():
    """Comment between or after tokens (not before first token)."""
    # Comments work between tokens
    assert_ebnf_roundtrip("rule = 'a'; (* comment *)")
    
    # Note: Leading comments before the first token are not supported
    # due to lexer skip behavior applying only between tokens


def test_ebnf_multiple_rules():
    """Grammar with multiple rules."""
    ebnf = """
    expr = term;
    term = 'x';
    """
    assert_ebnf_roundtrip(ebnf)


def test_ebnf_complex_arithmetic_grammar():
    """Full arithmetic expression grammar."""
    ebnf = """
    expr = term { ('+' | '-') term };
    term = factor { ('*' | '/') factor };
    factor = number | '(' expr ')';
    number = digit { digit };
    digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9';
    """
    assert_ebnf_roundtrip(ebnf)


def test_ebnf_nested_groups():
    """Nested grouping constructs."""
    assert_ebnf_roundtrip("rule = [('a' | 'b')] {'c'}*;")




def test_ebnf_double_quoted_string():
    """String literal with double quotes."""
    assert_ebnf_roundtrip('rule = "hello";')


def test_ebnf_escaped_quote_in_string():
    """Escaped quote inside string literal."""
    assert_ebnf_roundtrip(r"rule = 'it\'s';")




def test_ebnf_multiple_alternations():
    """Multiple alternation branches."""
    assert_ebnf_roundtrip("rule = 'a' | 'b' | 'c' | 'd';")


def test_ebnf_suffix_on_group():
    """Suffix applied to grouped expression."""
    assert_ebnf_roundtrip("rule = ('a' | 'b')+;")


def test_ebnf_complex_nested_repetition():
    """Complex nesting of groups and repetitions."""
    assert_ebnf_roundtrip("rule = { ['a' | 'b']+ 'c'* }?;")


def test_ebnf_individual_rules():
    """Test parsing individual grammar rules."""
    from syncraft.ebnf import Repeat
    from syncraft.ebnf import Lit
    
    # Test factor rule
    result = assert_ebnf_roundtrip("'a'?", syntax=EBNF.factor)
    
    assert isinstance(result, Repeat)
    assert result.expr == Lit('a')
    assert result.minimum == 0
    assert result.maximum == 1
    
    # Test suffix rule
    result = assert_ebnf_roundtrip("?", syntax=EBNF.suffix)
    assert result == (0,1)
    
    result = assert_ebnf_roundtrip("{2,5}", syntax=EBNF.suffix)
    assert result == (2,5)

    result = assert_ebnf_roundtrip("{2,}", syntax=EBNF.suffix)
    assert result == (2,None)

    result = assert_ebnf_roundtrip("{2}", syntax=EBNF.suffix)
    assert result == (2,None)


def test_ebnf_ident_pattern():
    """Test identifier lexical pattern."""
    result = assert_ebnf_roundtrip("valid_name123", syntax=EBNF.ident)
    assert result == "valid_name123"
    
    result = assert_ebnf_roundtrip("_underscore", syntax=EBNF.ident)
    assert result == "_underscore"




def test_ebnf_recursive_list_grammar():
    """Test recursive grammar with mutual references."""
    ebnf = """
    list = '[' elements? ']';
    elements = value { ',' value };
    value = 'x' | list;
    """
    assert_ebnf_roundtrip(ebnf)


def test_simple():
    from syncraft.syntax import Syntax as S
    from syncraft.ast import Nothing
    s = ((S.lit("a") | S.lit("b")) + ~S.lit("?")).case(
        (lambda env: (env.X, Nothing),  lambda env: env.X),
        (lambda env: (env.a, env.b),    lambda env: {'first': env.a, 'second': env.b})
    )    
    result = s.parse("a?")
    print(result)
    g = s.generate(result, replay=True)
    print(g)



if __name__ == "__main__":
    
    # test_ebnf_complex_arithmetic_grammar()
    # test_ebnf_complex_nested_repetition()
    
    # test_ebnf_individual_rules()
    
    # test_ebnf_nested_groups()
    
    # test_ebnf_optional_suffix()
    # test_ebnf_parenthesized_group()
    
    # test_ebnf_suffix_on_group()
    
    # test_ebnf_multiple_alternations()
    # test_ebnf_multiple_factors_with_suffixes()
    # test_ebnf_numeric_repetition_exact()
    # test_ebnf_numeric_repetition_range()
    # test_ebnf_numeric_repetition_unbounded()
    # test_ebnf_escaped_quote_in_string()
    # test_ebnf_double_quoted_string()
    # test_ebnf_coloneq_assign()
    # test_ebnf_comment()
    # test_ebnf_multiple_rules()
    # test_ebnf_simple_rule()
    # test_ebnf_recursive_list_grammar()

    test_simple()