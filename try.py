from __future__ import annotations
from syncraft.ast import TokenClass, Nothing
from syncraft.generator import generate_with, generate
from syncraft.parser import parse
from syncraft.fa import NFA, DFA, CodeUniverse
from syncraft.constraint import FrozenDict
from rich import print
from syncraft.ast import Then, ThenKind, Many, Choice, ChoiceKind, Token, Marked, Nothing, TokenClass
from syncraft.algebra import Error
from syncraft.parser import  parse_word
import syncraft.generator as gen
from syncraft.syntax import Syntax
from typing import Any
from syncraft.fa import NFA, DFA, CodeUniverse
from syncraft.charset import CharSet
from dataclasses import dataclass
literal = Syntax.config(TokenClass.simple()).literal


def test_charset_invalid_length_error() -> None:
    cc: CharSet[str] = CharSet.create("A", universe=CodeUniverse.ascii())
    # cc("AB")  # multi-character should raise
    cc_bytes: CharSet[bytes] = CharSet.create(b"A", universe=CodeUniverse.byte())
    cc_bytes(b"AB")

if __name__ == "__main__":
    test_charset_invalid_length_error()
