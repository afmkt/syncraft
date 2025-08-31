from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import Either, Left, Right, Error
from syncraft.ast import Marked, Then, ThenKind, Many, Nothing
from syncraft.parser import literal, variable, parse, Parser, Token
from syncraft.generator import TokenGen
from syncraft.constraint import forall, exists
from rich import print
import syncraft.generator as gen
from dataclasses import dataclass


if __name__ == "__main__":
    from dataclasses import dataclass
    from syncraft import literal

    @dataclass
    class Pair:
            first: Any
            second: Any

    A = literal("a").mark("first")
    B = literal("b").mark("second")
    syntax = (A + B).to(Pair)

    ast, _ = parse(syntax, "a b", dialect="sqlite")
    value, invert = ast.bimap()
    print(value)