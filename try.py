from __future__ import annotations

from syncraft.ast import Token
from syncraft.syntax import Syntax







def test_format_nested_indentation() -> None:
    """Format: nested if statements with proper indentation."""
    syntax_cls = Syntax

    keyword = syntax_cls.lit("if")
    space = syntax_cls.lit(" ")
    colon = syntax_cls.lit(":")

    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )

    head = keyword + space + identifier + colon
    stmt = identifier

    sep = space.format(breakability="optional", indent=1)

    if_stmt = (head + sep + stmt).format(indent=1)
    nested = head + sep + if_stmt

    generated = nested.generate(("if", " ", "x", ":", " ", ("if", " ", "y", ":", " ", "z")))
    result = generated.render(width=6, indent="    ")

    print("Result:")
    print(result)
    print("\nLines:")
    lines = result.split("\n")
    for i, line in enumerate(lines):
        print(f"  {i}: {repr(line)}")

    assert len(lines) >= 3
    assert lines[0].startswith("if x:")
    assert lines[1].startswith("    if y:")
    assert lines[2].startswith("        z")






if __name__ == "__main__":

    test_format_nested_indentation()