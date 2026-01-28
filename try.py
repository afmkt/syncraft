from __future__ import annotations
from typing import Any
from syncraft.parser import parse_word
from syncraft.syntax import Syntax
import syncraft.generator as gen
from syncraft.cache import Cache
from dataclasses import dataclass
from rich import print
from syncraft.bimap import Var, unify_all, Fun, Env, eval, unify, Unbound
import pytest
literal = Syntax.lit


def test_recursive_structure_constraints():
    X = Var("x")
    Y = Var("y")
    Z = Var("z")

    pattern = {
        "left": X,
        "right": {
            "value": Y,
            "sum": Fun(Z, lambda a, b: a + b, (X, Y)),
        }
    }

    value = {
        "left": 4,
        "right": {
            "value": 6,
            "sum": 10,
        }
    }

    env = unify_all(pattern, value)

    assert env.resolve(X) == 4
    assert env.resolve(Y) == 6
    assert env.resolve(Z) == 10


if __name__ == '__main__':
    
    test_recursive_structure_constraints()
    
    
    
    
    