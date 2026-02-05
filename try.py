from __future__ import annotations
from syncraft.syntax import Syntax
from syncraft.bimap import unify_all, let, Env, Scope, evaluate, Expr
import pytest

literal = Syntax.lit

def test_constraint_chain():
    scope = Scope()
    A = scope.A
    B = scope.B
    C = scope.C

    pattern = {
        "a": A,
        "b": let(B, A + 1),
        "c": let(C, B * 2),
        "d": A
    }

    value = {"a": 3, "b": 4, "c": 8, "d": 30}

    env = unify_all(pattern, value)

    assert env.resolve(B) == 4
    assert env.resolve(C) == 8


if __name__ == '__main__':
    test_constraint_chain()    
    
    
    
    
    