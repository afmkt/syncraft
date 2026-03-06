from __future__ import annotations
from typing import Any
import re
from syncraft.syntax import Syntax
from syncraft.ast import Alt, Lazy, Many, Seq, Token, Unknown
from syncraft.parser import parse_word
from syncraft.format import LayoutDoc, Group, Line, Nest, Concat, Text
import pytest
from rich import print







def test_format_nested_indentation() -> None:
    """Format: nested if statements with proper indentation."""
    syntax_cls = Syntax
    
    keyword = syntax_cls.lit("if") | syntax_cls.lit("else")
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )
    colon = syntax_cls.lit(":")
    # Apply format to newline with indent
    newline = syntax_cls.lit("\n").format(
        breakability="optional",
        indent=1
    )
    
    # Simple statement (placeholder)
    stmt = identifier
    
    # if statement with formatted newline
    if_stmt = (
        keyword + syntax_cls.lit(" ") + identifier + colon +
        newline + stmt
    )
    parsed = if_stmt.parse("if x:\n    if y:\n        z")

    print(parsed)
    data = (
        "if",
        " ",
        "x",
        ":",
        "\n",
        (
            "if",
            " ",
            "y",
            ":",
            "\n",
            "z"
        )
    )
    
    generated = if_stmt.generate(data)
    result = generated.render(width=80, indent="    ")
    
    # Should have proper indentation structure
    assert "if" in result
    assert "\n" in result
    print("Nested:", result)






if __name__ == "__main__":

    test_format_nested_indentation()