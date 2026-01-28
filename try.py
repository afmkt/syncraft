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



def test_nested_fun_arguments():
    X = Var("x")
    Y = Var("y")

    pattern = Fun(
        Y,
        lambda v: v * 2,
        (Fun(X, lambda z: z + 1, (5,)),),
    )

    env = unify_all(pattern, 12)
    assert X not in env
    assert env.resolve(Y) == 12


def test_dataclass_with_constraint()-> None:
    @dataclass
    class Point:
        x: Any
        y: Any


    X = Var("x")
    Y = Var("y")
    S = Var("sum")

    pattern = {
        "p": Point(X, Y),
        "sum": Fun(S, lambda a, b: a + b, (X, Y)),
    }

    value = {"p": Point(2, 3), "sum": 5}

    env = unify_all(pattern, value)

    assert env.resolve(S) == 5



def test_unsatisfied_constraint_fails():
    X = Var("x")
    Y = Var("y")
    pattern = Fun(X, lambda v: v + 1, (Y,))
    value = {}
    with pytest.raises(ValueError):
        unify_all(pattern, value)


        

if __name__ == '__main__':
    test_unsatisfied_constraint_fails()
    