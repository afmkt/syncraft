from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import Either, Left, Right, Error
from syncraft.ast import Marked, Then, ThenKind, Many
from syncraft.parser import literal, variable, parse, Parser, Token
from syncraft.generator import TokenGen
from rich import print
import syncraft.generator as gen
from dataclasses import dataclass

@dataclass
class ACls:
    a: str | None
    b: str | None
    c: str | None


IF = literal("if")
ELSE = literal("else")
THEN = literal("then")
END = literal("end")
var = variable()





if __name__ == "__main__":
    pass

