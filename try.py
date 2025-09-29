import pytest

from syncraft.syntax import Syntax
from syncraft.ast import TokenClass, Token, Then, ThenKind, Choice, ChoiceKind, Lazy
from syncraft.generator import generate_with, generate, validate
from syncraft.algebra import Error
from syncraft.cache import LeftRecursionError
from rich import print


def tok(text: str):
    return Syntax.token(token_class=TokenClass.simple(), text=text, case_sensitive=True)

def test_spec_preserves_terminal_data_for_lexers() -> None:
    TestSyntax = Syntax.config(token_class=TokenClass.simple())
    literal = TestSyntax.literal
    identifier = TestSyntax.token(text="id", token_type="IDENT")

    grammar = (literal("a") + identifier) | literal("b")

    builders = grammar.fabuilder()
    seen = {(builder.text, builder.tag) for builder in builders}

    assert seen == {("a", None), ("id", "IDENT"), ("b", None)}

if __name__ == "__main__":
    test_spec_preserves_terminal_data_for_lexers()