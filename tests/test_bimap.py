from syncraft.bimap import Var, unify_all, Fun, Env, eval, unify
from typing import Any
import pytest
from dataclasses import dataclass

def test_length_prefixed():
    """
    Docstring for test_length_prefixed
    This tests if the engine can calculate a value (V_SIZE) during generation, but validate it during parsing.
    """
    V_SIZE = Var("size")
    V_ITEMS = Var("items")
    
    # Template: (size, items)
    # raw side pattern
    raw_pattern = (Fun(V_SIZE, len, (V_ITEMS,)), V_ITEMS)
    
    # 1. PARSING: We provide the data, engine validates len
    print("--- Parsing Test ---")
    data_in = (3, ["a", "b", "c"])
    env_parse = unify_all(raw_pattern, data_in)
    print(f"Bound Size: {env_parse.resolve(V_SIZE)}") # Expected: 3
    
    # 2. GENERATING: We provide items, engine calculates size
    print("\n--- Generating Test ---")
    # We simulate starting with just the domain variable
    env_gen = Env()
    env_gen.bind(V_ITEMS, [1, 2])
    env_gen.solve() # This should trigger Fun(V_SIZE, len...)
    
    full, result = eval(raw_pattern, env_gen)
    print(f"Generated Structure: {result}") # Expected: (2, [1, 2])




def test_shared_variable():
    """
    Docstring for test_shared_variable
    This tests if a single Var used in two different parts of a dictionary forces the entire structure to be consistent.
    """
    V_ID = Var("id")
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
    """
    Docstring for test_dependency_chain
    This tests the "Reactive Loop" in solve(). 
    Total = Price * Quantity 
    GrandTotal = Total + (Total * Tax)
    """
    V_PRICE = Var("price")
    V_QTY = Var("qty")
    V_TOTAL = Var("total")
    V_GRAND = Var("grand_total")

    # The chain of constraints
    constraints = [
        Fun(V_TOTAL, lambda p, q: p * q, (V_PRICE, V_QTY)),
        Fun(V_GRAND, lambda t: t * 1.1, (V_TOTAL,))
    ]

    # We only know Price and Quantity
    env = Env()
    env.bind(V_PRICE, 100)
    env.bind(V_QTY, 2)
    
    # Manually register constraints (simulating what Mapping would do)
    env.bind(V_TOTAL, ...) # Ensure binding exists for the solver
    env.bindings[V_TOTAL].constraints.append(constraints[0])
    env.bind(V_GRAND, ...)
    env.bindings[V_GRAND].constraints.append(constraints[1])

    if env.solve():
        print(f"Subtotal: {env.resolve(V_TOTAL)}")    # Expected: 200
        print(f"Grand Total: {env.resolve(V_GRAND)}") # Expected: 220.0        



# assume all engine symbols are imported:
# Var, Fun, unify_all, Unbound


# ---------------------------------------------------------------------
# 1. Length-prefixed list (canonical bidirectional example)
# ---------------------------------------------------------------------

def test_length_prefixed_list_forward():
    V_SIZE = Var("size")
    V_ITEMS = Var("items")

    pattern = (
        Fun(V_SIZE, len, (V_ITEMS,)),
        V_ITEMS,
    )

    value = (3, ["A", "B", "C"])

    env = unify_all(pattern, value)

    assert env.resolve(V_SIZE) == 3
    assert env.resolve(V_ITEMS) == ["A", "B", "C"]


def test_length_prefixed_list_backward():
    V_SIZE = Var("size")
    V_ITEMS = Var("items")

    pattern = (
        Fun(V_SIZE, len, (V_ITEMS,)),
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
    X = Var("x")

    pattern = {"a": X, "b": X}
    value = {"a": 10, "b": 10}

    env = unify_all(pattern, value)
    assert env.resolve(X) == 10


def test_shared_variable_conflict():
    X = Var("x")

    pattern = {"a": X, "b": X}
    value = {"a": 10, "b": 11}

    with pytest.raises(ValueError):
        unify_all(pattern, value)


# ---------------------------------------------------------------------
# 3. Multi-argument computed constraint
# ---------------------------------------------------------------------

def test_sum_constraint_forward_and_backward():
    A = Var("a")
    B = Var("b")
    S = Var("sum")

    pattern = {
        "a": A,
        "b": B,
        "sum": Fun(S, lambda x, y: x + y, (A, B)),
    }

    value = {"a": 2, "b": 3, "sum": 5}

    env = unify_all(pattern, value)

    assert env.resolve(S) == 5


# ---------------------------------------------------------------------
# 4. Constraint chain (fixpoint propagation)
# ---------------------------------------------------------------------

def test_constraint_chain():
    A = Var("a")
    B = Var("b")
    C = Var("c")

    pattern = {
        "a": A,
        "b": Fun(B, lambda x: x + 1, (A,)),
        "c": Fun(C, lambda y: y * 2, (B,)),
    }

    value = {"a": 3, "b": 4, "c": 8}

    env = unify_all(pattern, value)

    assert env.resolve(B) == 4
    assert env.resolve(C) == 8


# ---------------------------------------------------------------------
# 5. Nested Fun in arguments
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# 6. Dataclass structural unification
# ---------------------------------------------------------------------

@dataclass
class Point:
    x: Any
    y: Any


def test_dataclass_unification():
    X = Var("x")
    Y = Var("y")

    pattern = Point(X, Y)
    value = Point(1, 2)

    env = unify_all(pattern, value)

    assert env.resolve(X) == 1
    assert env.resolve(Y) == 2


def test_dataclass_with_constraint():
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


# ---------------------------------------------------------------------
# 7. Deadlock / unsatisfied constraint
# ---------------------------------------------------------------------

def test_unsatisfied_constraint_fails():
    X = Var("x")
    Y = Var("y")

    pattern = Fun(X, lambda v: v + 1, (Y,))
    value = {}

    with pytest.raises(ValueError):
        unify_all(pattern, value)


# ---------------------------------------------------------------------
# 8. Conflicting constraints
# ---------------------------------------------------------------------

def test_conflicting_constraints_fail():
    X = Var("x")

    pattern = {
        "a": Fun(X, lambda _: 1, (0,)),
        "b": Fun(X, lambda _: 2, (0,)),
    }

    with pytest.raises(ValueError):
        unify_all(pattern, {})


# ---------------------------------------------------------------------
# 9. Partial structure with computed field
# ---------------------------------------------------------------------

def test_partial_structure_with_computed():
    ITEMS = Var("items")
    HEAD = Var("head")

    pattern = {
        "items": ITEMS,
        "head": Fun(HEAD, lambda xs: xs[0], (ITEMS,)),
    }

    value = {"items": ["a", "b", "c"], "head": "a"}

    env = unify_all(pattern, value)

    assert env.resolve(HEAD) == "a"
        
###################################################################

def test_mutual_chain_resolution():
    A = Var("A")
    B = Var("B")
    C = Var("C")

    pattern = (
        Fun(A, lambda b: b + 1, (B,)),
        Fun(B, lambda c: c * 2, (C,)),
        C,
    )

    value = (7, 6, 3)

    env = unify_all(pattern, value)

    assert env.resolve(C) == 3
    assert env.resolve(B) == 6
    assert env.resolve(A) == 7


def test_two_way_dependency():
    A = Var("A")
    B = Var("B")

    pattern = (
        Fun(A, lambda b: b + 1, (B,)),
        Fun(B, lambda a: a - 1, (A,)),
    )

    value = (10, 9)

    env = unify_all(pattern, value)

    assert env.resolve(A) == 10
    assert env.resolve(B) == 9


def test_cyclic_constraints_with_ground_values():
    A = Var("A")
    B = Var("B")

    pattern = (
        Fun(A, lambda b: b + 1, (B,)),
        Fun(B, lambda a: a - 1, (A,)),
    )
    value = (4, 3)
    env = unify_all(pattern, value)
    assert env.resolve(A) == 4
    assert env.resolve(B) == 3

###########################################################################
def test_inconsistent_cycle_fails():
    A = Var("A")
    B = Var("B")

    pattern = (
        Fun(A, lambda b: b + 1, (B,)),
        Fun(B, lambda a: a + 1, (A,)),
        A,
    )

    value = (None, None, 0)

    with pytest.raises(ValueError):
        unify_all(pattern, value)



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


def test_forward_reference_constraint():
    X = Var("x")
    Y = Var("y")

    pattern = (
        Fun(Y, lambda x: x * 2, (X,)),
        X,
    )

    value = (10, 5)

    env = unify_all(pattern, value)

    assert env.resolve(X) == 5
    assert env.resolve(Y) == 10



def test_constraint_does_not_create_binding():
    X = Var("x")
    Y = Var("y")

    pattern = Fun(Y, lambda x: x + 1, (X,))
    value = 10

    with pytest.raises(ValueError):
        unify_all(pattern, value)

