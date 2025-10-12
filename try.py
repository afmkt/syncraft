from __future__ import annotations

from rich import print

from syncraft.syntax import (
    Syntax,
)
from syncraft.ast import (
    TokenClass,
)


def test_spec_preserves_terminal_data_for_lexers() -> None:
    TestSyntax = Syntax.config(token_class=TokenClass.simple())
    literal = TestSyntax.literal
    identifier = TestSyntax.token(text="id", token_type="IDENT")

    grammar = (literal("a") + identifier) | literal("b")

    builders = grammar.fabuilder()
    seen = {(builder.text, builder.tag) for builder in builders}
    assert seen == {("a", 'a'), ("id", "IDENT"), ("b", 'b')}


if __name__ == "__main__":
    test_spec_preserves_terminal_data_for_lexers()