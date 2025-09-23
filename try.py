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
from enum import Enum
from syncraft.fa import NFA, DFA, CodeUniverse
from syncraft.utils import debug_print, set_debug
from syncraft.ast import TokenClass

set_debug(True)


literal = Syntax.config(token_class = TokenClass.simple()).literal
token = Syntax.config(token_class = TokenClass.simple()).token
lazy = Syntax.config(token_class = TokenClass.simple()).lazy

class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

def test_enum_tag_nfa():
    u = CodeUniverse.enum(Color)
    nfa = NFA.from_charset([Color.RED], universe=u).tagged('red')
    assert nfa.match([Color.RED])
    assert not nfa.match([Color.GREEN])
    # Tag should be present in accept
    for tags in nfa.accept.values():
        assert 'red' in tags
if __name__ == "__main__":
    test_enum_tag_nfa()
    # test_indirect_left_recursion_2()
