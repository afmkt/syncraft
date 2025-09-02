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
        from syncraft import literal, parse, generate, generate_with
        @dataclass
        class Pair:
                first:Any
                second:Any

        A = literal("a").mark('first')
        B = literal("b").mark('second')
        C = literal(",")
        syntax = (A + B).to(Pair).sep_by(C)
        ast, _ = parse(syntax, "a b, a b, a b", dialect="sqlite")
        value, inverse = ast.bimap()
        print(value)
        value.append(Pair('x', 'y'))
        print(value)
        ast3 = inverse(value)
        rt, _ = generate_with(syntax, ast3)
        print(rt)
        print(syntax.meta.to_string())
