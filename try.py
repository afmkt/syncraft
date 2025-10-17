from __future__ import annotations

from typing import List
import pytest
from syncraft.syntax import (
    Syntax,


)
from syncraft.ast import (
    Token,

)
from syncraft.lexer import ExtLexer
from syncraft.token import Structured

@pytest.mark.xfail(reason="Currently fails due to missing token data in spec")
def test() -> None:
    TestSyntax = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token)))
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