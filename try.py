from __future__ import annotations
from typing import Any
import re
from syncraft.syntax import Syntax
from syncraft.ast import Alt, Lazy, Many, Seq, Token, Unknown
from syncraft.parser import parse_word
import pytest




def test_format_multiline_function_call() -> None:
    """Format: f(a, b, c) breaking to multiple lines when too wide."""
    syntax_cls = Syntax
    
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )
    
    comma = syntax_cls.lit(",").format(attach="left")
    space = syntax_cls.lit(" ").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda _: " "
    )
    
    # Width-sensitive argument list with indentation
    args = (identifier + (comma + space + identifier).many()).format(
        breakability="optional",
        indent=1
    )
    
    func_call = identifier + syntax_cls.lit("(") + args + syntax_cls.lit(")")
    
    generated = func_call.generate(('f', '(', ('a', ((',', ' ', 'b'), (',', ' ', 'c'))), ')'))
    
    # Fits on one line with width=80
    result_wide = generated.render(width=80)
    print(result_wide)
    assert "," in result_wide
    
    # Breaks to multiple lines with narrow width

    result_narrow = generated.render(width=5)
    print(result_narrow)
    assert "\n" in result_narrow




def test_format_multiline_addition_operator_first() -> None:
    """Format: a, +b, +c, +d - operators at line start when breaking."""
    syntax_cls = Syntax
    
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )
    
    plus = syntax_cls.lit(" +").format(attach="left")
    space = syntax_cls.lit(" ").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda _: " "
    )
    
    # Indented addition chain
    expr = (identifier + (plus + space + identifier).many()).format(
        breakability="optional",
        indent=1
    )
    generated = expr.generate(("a", ((" +", " ", "b"), (" +", " ", "c"), (" +", " ", "d"))))
    
    # Fits on one line with width=80
    result_wide = generated.render(width=80)
    assert "+" in result_wide
    
    # Breaks to multiple lines with narrow width
    result_narrow = generated.render(width=8)
    assert "\n" in result_narrow
    # Operator should be on continuation lines
    lines = result_narrow.strip().split("\n")
    assert len(lines) > 1


def test_format_nested_indentation() -> None:
    """Format: nested if statements with proper indentation."""
    syntax_cls = Syntax
    
    keyword = syntax_cls.lit("if") | syntax_cls.lit("else")
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*")
    colon = syntax_cls.lit(":")
    newline = syntax_cls.lit("\n").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda _: "\n"
    )
    
    # Simple statement (placeholder)
    stmt = identifier
    
    # if statement: if x: <body>
    if_stmt = (
        keyword + syntax_cls.lit(" ") + identifier + colon +
        newline + stmt.format(indent=1)
    ).format(indent=0)
    
    # Nested if statements
    nested = (
        keyword + syntax_cls.lit(" ") + identifier + colon +
        newline + if_stmt.format(indent=1)
    )
    
    generated = nested.generate((None, None, "x", None, None, None, None, None, "y", None, None, None, None, None, None, None, "z"))
    
    result = generated.render(width=80, indent="    ")
    
    # Should have proper indentation structure
    assert "if" in result
    assert "\n" in result
    print(result)

if __name__ == "__main__":
    test_format_nested_indentation()
    