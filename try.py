from __future__ import annotations

from typing import List
import pytest
from syncraft.syntax import (
    Syntax,
    SyntaxSpec,
    LazySpec,
    ThenSpec,
    ChoiceSpec,

)
from syncraft.ast import (
    Token,
    Then,
    Choice,
    Many,
    Marked,
    Collect,
    Nothing,
    Lazy,
)
from syncraft.lexer import ExtLexer
from syncraft.input import Input
from syncraft.parser import parse as parser_run
from syncraft.parser import parse_word


@pytest.mark.xfail(reason="Currently fails due to missing token data in spec")
def test() -> None:
    TestSyntax = Syntax.config(lexer_class=ExtLexer.bind(token_class=Token))
    literal = TestSyntax.literal
    identifier = TestSyntax.token(text="id", token_type="IDENT")

    grammar = (literal("a") + identifier) | literal("b")

    builders = grammar.fabuilder()
    seen = {(builder.text, builder.tag) for builder in builders}
    from rich import print
    print(seen)
    assert seen == {("a", 'a'), ("id", "IDENT"), ("b", 'b')}


if __name__ == "__main__":
    test()