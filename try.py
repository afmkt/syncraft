from __future__ import annotations
from typing import Any
import re
from syncraft.syntax import Syntax
from syncraft.ast import Alt, Lazy, Many, Seq, Token, Unknown
from syncraft.parser import parse_word
import pytest

from syncraft.format import (
    construct_templated_text,
    LayoutDoc,
    Group,
    Concat,
    Text    
)

def render(value: Any | LayoutDoc | Any, *, width: int = 80, indent: str = "    ") -> str:
    """Render a value to text through the LayoutDoc domain.

    Accepts either an existing LayoutDoc or AST-like values and lowers them
    using the default safe lowering strategy.
    """
    doc = LayoutDoc.from_ast(value)
    return doc.render(width=width)





def test_format_nested_indentation() -> None:
    """Format: nested if statements with proper indentation."""
    S = Syntax
    
    space = S.lit(" ")
    identifier = S.rp(r"[a-zA-Z_]\w*")

    head = S.lit("if") + space + identifier + S.lit(":")

    sep = space.format("{f? }{@opt}", indent=1)

    if_stmt = (head + sep + identifier).format(indent=4)
    nested = head + sep + if_stmt

    generated = nested.generate(("if", " ", "x", ":", " ", ("if", " ", "y", ":", " ", "z")))
    result = generated.render(width=6)

    lines = result.split("\n")
    for i, line in enumerate(lines):
        print(f"  {i}: {repr(line)}")

    assert len(lines) >= 3
    assert lines[0].startswith("if x:")
    assert lines[1].startswith("    if y:")
    assert lines[2].startswith("        z")



if __name__ == "__main__":
    test_format_nested_indentation()