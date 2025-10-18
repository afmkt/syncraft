from typing import Type

import pytest

from syncraft.syntax import Syntax
from syncraft.ast import Token
from syncraft.generator import (
    generate_with,
)
from syncraft.lexer import ExtLexer
from syncraft.token import Structured
from rich import print


S = Syntax



def test_generate_with_infers_text_lexer_without_config() -> None:
    syntax = Syntax.literal("hi")
    ast, bound = generate_with(syntax, seed=123)
    assert ast == Token('hi')



if __name__ == "__main__":
    test_generate_with_infers_text_lexer_without_config()