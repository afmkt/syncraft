from syncraft.bimap import Var, unify_all, Env, evaluate, let, Expr, Scope
from typing import Any
import pytest
from dataclasses import dataclass

def test_length_prefixed():
    scope = Scope()
    V_SIZE = scope.V_SIZE
    V_ITEMS = scope.V_ITEMS
    
    raw_pattern = (let(V_SIZE, Expr.apply(len, V_ITEMS)), V_ITEMS)
    
    
    print("--- Parsing Test ---")
    data_in = (3, ["a", "b", "c"])
    env_parse = unify_all(raw_pattern, data_in)
    print(f"Bound Size: {env_parse.resolve(V_SIZE)}") # Expected: 3
    
    print("\n--- Generating Test ---")
    env_gen = Env()
    env_gen.bind(V_ITEMS, [1, 2])
    env_gen.solve() # This should trigger Fun(V_SIZE, len...)
    
    full, result = evaluate(raw_pattern, env_gen, set())
    print(f"Generated Structure: {result}") # Expected: (2, [1, 2])




def test_shared_variable():
    """
    Docstring for test_shared_variable
    This tests if a single Var used in two different parts of a dictionary forces the entire structure to be consistent.
    """
    scope = Scope()
    V_ID = scope.V_ID
    # A structure where 'request_id' and 'header.log_id' must be identical
    pattern = {
        "request_id": V_ID,
        "header": {"log_id": V_ID}
    }

    # Case A: Valid data
    valid_data = {"request_id": "ABC", "header": {"log_id": "ABC"}}
    env_ok = unify_all(pattern, valid_data)
    print(f"Shared ID: {env_ok.resolve(V_ID)}") # Expected: ABC

    # Case B: Contradictory data
    invalid_data = {"request_id": "ABC", "header": {"log_id": "XYZ"}}
    try:
        unify_all(pattern, invalid_data)
    except ValueError:
        print("Consistency check passed: Rejected mismatching IDs.")


def test_dependency_chain():
    scope = Scope()
    V_PRICE = scope.V_PRICE
    V_QTY = scope.V_QTY
    V_TOTAL = scope.V_TOTAL
    V_GRAND = scope.V_GRAND

    
    constraints = [
        let(V_TOTAL, V_PRICE * V_QTY),
        let(V_GRAND, V_TOTAL * 1.1)
    ]

    
    env = Env()
    env.bind(V_PRICE, 100)
    env.bind(V_QTY, 2)
    
    env = unify_all(constraints, [200, 220.0], env)

    assert env.resolve(V_PRICE) == 100
    assert env.resolve(V_QTY) == 2

    assert env.resolve(V_TOTAL) == 200
    assert env.resolve(V_GRAND) == 220.0


# ---------------------------------------------------------------------
# 1. Length-prefixed list (canonical bidirectional example)
# ---------------------------------------------------------------------

def test_length_prefixed_list_forward():
    scope = Scope()
    V_SIZE = scope.V_SIZE
    V_ITEMS = scope.V_ITEMS

    pattern = (
        let(V_SIZE, Expr.apply(len, V_ITEMS)),
        V_ITEMS,
    )

    value = (3, ["A", "B", "C"])

    env = unify_all(pattern, value)

    assert env.resolve(V_SIZE) == 3
    assert env.resolve(V_ITEMS) == ["A", "B", "C"]


def test_length_prefixed_list_backward():
    scope = Scope()
    V_SIZE = scope.V_SIZE
    V_ITEMS = scope.V_ITEMS

    pattern = (
        let(V_SIZE, Expr.apply(len, V_ITEMS)),
        V_ITEMS,
    )

    value = (2, ["X", "Y"])

    env = unify_all(pattern, value)

    assert env.resolve(V_SIZE) == 2
    assert env.resolve(V_ITEMS) == ["X", "Y"]


# ---------------------------------------------------------------------
# 2. Shared variable / single-assignment consistency
# ---------------------------------------------------------------------

def test_shared_variable_success():
    scope = Scope()
    X = scope.X

    pattern = {"a": X, "b": X}
    value = {"a": 10, "b": 10}

    env = unify_all(pattern, value)
    assert env.resolve(X) == 10


def test_shared_variable_conflict():
    scope = Scope()
    X = scope.X

    pattern = {"a": X, "b": X}
    value = {"a": 10, "b": 11}

    with pytest.raises(ValueError):
        unify_all(pattern, value)


# ---------------------------------------------------------------------
# 3. Multi-argument computed constraint
# ---------------------------------------------------------------------

def test_sum_constraint_forward_and_backward():
    scope = Scope()
    A = scope.A
    B = scope.B
    S = scope.S

    pattern = {
        "a": A,
        "b": B,
        "sum": let(S, A + B),
    }

    value = {"a": 2, "b": 3, "sum": 5}

    env = unify_all(pattern, value)

    assert env.resolve(S) == 5


# ---------------------------------------------------------------------
# 4. Constraint chain (fixpoint propagation)
# ---------------------------------------------------------------------

def test_constraint_chain():
    scope = Scope()
    A = scope.A
    B = scope.B
    C = scope.C

    pattern = {
        "a": A,
        "b": let(B, A + 1),
        "c": let(C, B * 2),
    }

    value = {"a": 3, "b": 4, "c": 8}

    env = unify_all(pattern, value)

    assert env.resolve(B) == 4
    assert env.resolve(C) == 8


# ---------------------------------------------------------------------
# 5. Nested Fun in arguments
# ---------------------------------------------------------------------

def test_nested_fun_arguments():
    scope = Scope()
    X = scope.X
    Y = scope.Y

    pattern = let(
        Y,
        let(X, 5 + 1) * 2,
    )

    env = unify_all(pattern, 12)

    assert X not in env
    assert env.resolve(Y) == 12


# ---------------------------------------------------------------------
# 6. Dataclass structural unification
# ---------------------------------------------------------------------

@dataclass
class Point:
    x: Any
    y: Any


def test_dataclass_unification():
    scope = Scope()
    X = scope.X
    Y = scope.Y

    pattern = Point(X, Y)
    value = Point(1, 2)

    env = unify_all(pattern, value)

    assert env.resolve(X) == 1
    assert env.resolve(Y) == 2


def test_dataclass_with_constraint():
    scope = Scope()
    X = scope.X
    Y = scope.Y
    S = scope.S

    pattern = {
        "p": Point(X, Y),
        "sum": let(S, X + Y),
    }

    value = {"p": Point(2, 3), "sum": 5}

    env = unify_all(pattern, value)

    assert env.resolve(S) == 5


# ---------------------------------------------------------------------
# 7. Deadlock / unsatisfied constraint
# ---------------------------------------------------------------------

def test_unsatisfied_constraint_fails():
    scope = Scope()
    X = scope.X
    Y = scope.Y

    pattern = let(X, Y + 1)
    value = {}

    with pytest.raises(ValueError):
        unify_all(pattern, value)


# ---------------------------------------------------------------------
# 8. Conflicting constraints
# ---------------------------------------------------------------------

def test_conflicting_constraints_fail():
    scope = Scope()
    X = scope.X

    pattern = {
        "a": let(X, Expr.apply(lambda _: 1, 0)),
        "b": let(X, Expr.apply(lambda _: 2, 0)),
    }

    with pytest.raises(ValueError):
        unify_all(pattern, {})


# ---------------------------------------------------------------------
# 9. Partial structure with computed field
# ---------------------------------------------------------------------

def test_partial_structure_with_computed():
    scope = Scope()
    ITEMS = scope.ITEMS
    HEAD = scope.HEAD

    pattern = {
        "items": ITEMS,
        "head": let(HEAD, ITEMS[0]),
    }

    value = {"items": ["a", "b", "c"], "head": "a"}

    env = unify_all(pattern, value)

    assert env.resolve(HEAD) == "a"
        
###################################################################

def test_mutual_chain_resolution():
    scope = Scope()
    A = scope.A
    B = scope.B
    C = scope.C

    pattern = (
        let(A, B + 1),
        let(B, C * 2),
        C,
    )

    value = (7, 6, 3)

    env = unify_all(pattern, value)

    assert env.resolve(C) == 3
    assert env.resolve(B) == 6
    assert env.resolve(A) == 7


def test_two_way_dependency():
    scope = Scope()
    A = scope.A
    B = scope.B

    pattern = (
        let(A, B + 1),
        let(B, A - 1),
    )

    value = (10, 9)

    env = unify_all(pattern, value)

    assert env.resolve(A) == 10
    assert env.resolve(B) == 9


def test_cyclic_constraints_with_ground_values():
    scope = Scope()
    A = scope.A
    B = scope.B

    pattern = (
        let(A, B + 1),
        let(B, A - 1),
    )
    value = (4, 3)
    env = unify_all(pattern, value)
    assert env.resolve(A) == 4
    assert env.resolve(B) == 3

###########################################################################
def test_inconsistent_cycle_fails():
    scope = Scope()
    A = scope.A
    B = scope.B

    pattern = (
        let(A, B + 1),
        let(B, A + 1),
        A,
    )

    value = (None, None, 0)

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


def test_forward_reference_constraint():
    scope = Scope()
    X = scope.X
    Y = scope.Y

    pattern = (
        let(Y, X * 2),
        X,
    )

    value = (10, 5)

    env = unify_all(pattern, value)

    assert env.resolve(X) == 5
    assert env.resolve(Y) == 10



def test_constraint_does_not_create_binding():
    scope = Scope()
    X = scope.X
    Y = scope.Y

    pattern = let(Y, X + 1)
    value = 10

    with pytest.raises(ValueError):
        unify_all(pattern, value)

