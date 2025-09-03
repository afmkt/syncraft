from __future__ import annotations
from typing import Any, List, Tuple
from syncraft.algebra import Either, Left, Right, Error
from syncraft.ast import Marked, Then, ThenKind, Many, Nothing
from syncraft.parser import literal, variable, parse, Parser, Token, until
from syncraft.generator import TokenGen
from syncraft.constraint import forall, exists, test
from rich import print
import syncraft.generator as gen
from dataclasses import dataclass


if __name__ == "__main__":
    test()