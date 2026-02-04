from __future__ import annotations
from syncraft.syntax import Syntax
from syncraft.bimap import unify_all, let, Env, Scope
import pytest

literal = Syntax.lit


def test_constraint_does_not_create_binding():
    scope = Scope()
    X = scope.X
    Y = scope.Y

    pattern = let(Y, X + 1)
    value = 10

    with pytest.raises(ValueError):
        unify_all(pattern, value)


def test_recursive_structure_constraints():
    scope = Scope()
    X = scope.X
    Y = scope.Y
    Z = scope.Z

    pattern = {
        "left": X,
        "right": {
            "value": Y,
            "sum": let(Z, X + Y),
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
    
    test_constraint_does_not_create_binding()
    test_recursive_structure_constraints()
    
    
    
    
    