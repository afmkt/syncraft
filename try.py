from __future__ import annotations
from syncraft.ast import Nothing, Token
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.syntax import Syntax
from syncraft.parser import ParserState
from dataclasses import dataclass
import syncraft.generator as gen
from typing import Any, Callable, TypeVar, Generic, Generator, cast
from syncraft.cache import LeftRecursionError
import re
from syncraft.utils import debug_print, set_debug
from syncraft.ast import TokenClass

set_debug(True)


literal = Syntax.config(token_class = TokenClass.simple()).literal
token = Syntax.config(token_class = TokenClass.simple()).token
lazy = Syntax.config(token_class = TokenClass.simple()).lazy



def test()->None:
    s: ParserState[str] = ParserState(input=tuple(), final=True)
    


    print(s)



if __name__ == "__main__":
    test()
    # test_indirect_left_recursion_2()
