from syncraft.bimap import solve, Env, evaluate, let, Expr, Scope, transform, Iso, Not, Match, FrozenDict
from typing import Any, Optional
import pytest
from dataclasses import dataclass

def unify_all(pattern: Any, value: Any, env: Env | None = None) -> Env:
    if env is None:
        env = Env()
    result = solve(pattern, value, env)
    if isinstance(result, list):
        raise ValueError(f"Unification failed: {result}")
    return env


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


def test_transformation()->None:
    @dataclass(frozen=True, slots=True)
    class Quantifier:
        minimum: int
        maximum: Optional[int]     # None → unbounded
        greedy: bool = True


    iso = Iso.derive(lambda env: (Quantifier(minimum=env.minimum, maximum=env.maximum), env.greedy), 
                    lambda env: Quantifier(minimum=env.minimum, maximum=env.maximum, greedy=Not(env.greedy)))

    a = (Quantifier(1, 5, True), False)
    b = iso.forward(a, None)
    assert b == Quantifier(1, 5, True)
    c = iso.inverse(b, None)
    assert c == (Quantifier(1, 5, True), False)


@dataclass(frozen=True)
class _CaseNode:
    primary: Any
    minimum: int
    maximum: Optional[int]


def test_match_inverse_prefers_more_specific_target_pattern() -> None:
    # Branch 1 target is generic (env.X), branch 2 target is structured dataclass.
    m = Match(
        lambda env: (env.primary, env.tag),
        lambda env: env.X,
    ).case(
        lambda env: (env.primary, (env.minimum, env.maximum)),
        lambda env: _CaseNode(env.primary, env.minimum, env.maximum),
    )

    inv = m.inverse(strict=False, passthrough=False)
    assert inv(_CaseNode("a", 0, 1), None) == ("a", (0, 1))


def test_match_forward_uses_source_order() -> None:
    # Forward direction uses declaration order (first match wins).
    # Branch 1: generic pattern (matches anything)
    # Branch 2: more specific pattern (matches question marks)
    m = Match(
        lambda env: (env.a, env.b),
        lambda env: "generic",
    ).case(
        lambda env: (env.a, "?"),
        lambda env: "question",
    )

    fwd = m.forward(strict=False, passthrough=False)
    # First pattern wins in forward direction
    assert fwd(("x", "?"), None) == "generic"
    
    # Flip order: specific pattern first
    m2 = Match(
        lambda env: (env.a, "?"),
        lambda env: "question",
    ).case(
        lambda env: (env.a, env.b),
        lambda env: "generic",
    )
    
    fwd2 = m2.forward(strict=False, passthrough=False)
    # Now specific pattern wins because it's first
    assert fwd2(("x", "?"), None) == "question"


def test_match_passthrough_catches_unmatched() -> None:
    # With passthrough=True, unmatched values pass through unchanged
    m = Match(
        lambda env: ("binary", env.op, env.left, env.right),
        lambda env: {"type": "binary", "op": env.op, "left": env.left, "right": env.right},
    ).case(
        lambda env: ("variable", env.name),
        lambda env: {"type": "variable", "name": env.name},
    )
    
    # Forward: unmatched pattern passes through
    fwd = m.forward(strict=False, passthrough=True)
    assert fwd(("binary", "+", 1, 2), None) == {"type": "binary", "op": "+", "left": 1, "right": 2}
    assert fwd(("variable", "x"), None) == {"type": "variable", "name": "x"}
    assert fwd(("unhandled", "data"), None) == ("unhandled", "data")  # passes through
    
    # Inverse: unmatched target passes through
    inv = m.inverse(strict=False, passthrough=True)
    assert inv({"type": "binary", "op": "+", "left": 1, "right": 2}, None) == ("binary", "+", 1, 2)
    assert inv({"type": "variable", "name": "x"}, None) == ("variable", "x")
    assert inv({"type": "unknown"}, None) == {"type": "unknown"}  # passes through


# ---------------------------------------------------------------------
# Tests for Env.where (constraints API)
# ---------------------------------------------------------------------

def test_where_with_callable_condition():
    """Test Env.where with a callable function condition."""
    scope = Scope()
    X = scope.X
    Y = scope.Y
    
    # Create an environment with bindings
    env = Env()
    env.bind(X, 10)
    env.bind(Y, 20)
    
    # Add a constraint: X + Y must equal 30
    def sum_check(e: Env) -> bool:
        return e.resolve(X) + e.resolve(Y) == 30
    
    env.where(sum_check)
    
    # Solve should succeed
    success, reason = env.solve()
    assert success, f"Constraint should be satisfied: {reason}"


def test_where_with_callable_condition_fails():
    """Test Env.where with a callable that returns False."""
    scope = Scope()
    X = scope.X
    Y = scope.Y
    
    # Create an environment with bindings
    env = Env()
    env.bind(X, 10)
    env.bind(Y, 20)
    
    # Add a constraint that will fail: X + Y must equal 100
    def sum_check(e: Env) -> bool:
        return e.resolve(X) + e.resolve(Y) == 100
    
    env.where(sum_check)
    
    # Solve should fail
    success, reason = env.solve()
    assert not success, "Constraint should fail"


def test_where_with_expr_condition():
    """Test Env.where with an Expr condition."""
    scope = Scope()
    X = scope.X
    Y = scope.Y
    
    # Create an environment with bindings
    env = Env()
    env.bind(X, 5)
    env.bind(Y, 10)
    
    # Create an Expr using the .eq() method (not Python's == operator)
    # X * 2 creates an Expr, then we compare with Y using .eq()
    expr_x_times_2 = X * 2
    expr_condition = expr_x_times_2.eq(Y)  # This creates an Expr that compares X*2 to Y
    
    env.where(expr_condition)
    
    # Solve should succeed (5 * 2 == 10)
    success, reason = env.solve()
    assert success, f"Constraint should be satisfied: {reason}"


def test_where_with_expr_fails():
    """Test Env.where with an Expr that evaluates to False."""
    scope = Scope()
    X = scope.X
    Y = scope.Y
    
    # Create an environment with bindings
    env = Env()
    env.bind(X, 5)
    env.bind(Y, 15)
    
    # Create an Expr: X * 2 == Y (but 5 * 2 != 15)
    expr_x_times_2 = X * 2
    expr_condition = expr_x_times_2.eq(Y)
    
    env.where(expr_condition)
    
    # Solve should fail
    success, reason = env.solve()
    assert not success, "Constraint should fail"


def test_where_combined_with_pattern():
    """Test Env.where combined with pattern matching."""
    scope = Scope()
    A = scope.A
    B = scope.B
    
    pattern = {
        "value": A,
        "doubled": let(B, A * 2),
    }
    
    # Create env and add where constraint
    env = Env()
    env.where(lambda e: e.resolve(B) > 10)
    
    # Match against data
    value = {"value": 6, "doubled": 12}
    result = solve(pattern, value, env)
    
    assert isinstance(result, Env), f"Expected Env, got {result}"
    assert result.resolve(A) == 6
    assert result.resolve(B) == 12
    
    # Verify constraint is satisfied (B = 12 > 10)
    success, reason = result.solve()
    assert success, f"Constraint should be satisfied: {reason}"


def test_where_constraint_fails_on_pattern():
    """Test that Env.where constraint fails when pattern doesn't satisfy it."""
    scope = Scope()
    A = scope.A
    B = scope.B
    
    pattern = {
        "value": A,
        "doubled": let(B, A * 2),
    }
    
    # Create env and add where constraint: B must be > 10
    env = Env()
    env.where(lambda e: e.resolve(B) > 10)
    
    # Match against data where B = 4 (not > 10)
    value = {"value": 2, "doubled": 4}
    result = solve(pattern, value, env)
    
    # The solve should fail because constraint B > 10 is not satisfied
    # Returns a list of errors, not an Env
    assert isinstance(result, list), f"Expected list of errors, got {result}"


def test_where_multiple_constraints():
    """Test Env.where with multiple constraints."""
    scope = Scope()
    X = scope.X
    Y = scope.Y
    
    env = Env()
    env.bind(X, 10)
    env.bind(Y, 20)
    
    # Add multiple constraints
    env.where(lambda e: e.resolve(X) > 5)
    env.where(lambda e: e.resolve(Y) > 15)
    env.where(lambda e: e.resolve(X) + e.resolve(Y) == 30)
    
    # All constraints should be satisfied
    success, reason = env.solve()
    assert success, f"All constraints should be satisfied: {reason}"


def test_where_with_where_method_in_create():
    """Test Env.where used within Env.create method."""
    scope = Scope()
    NAME = scope.NAME
    AGE = scope.AGE
    
    # Use Env.create with where parameter
    env = Env.create(
        scope=scope,
        constants=FrozenDict({"NAME": "Alice", "AGE": 30}),
    )
    
    # Add constraint
    env.where(lambda e: e.resolve(AGE) >= 18)
    
    success, reason = env.solve()
    assert success, f"Constraint should be satisfied: {reason}"


def test_where_chaining_returns_env():
    """Test that Env.where returns Env for method chaining."""
    scope = Scope()
    X = scope.X
    
    env = Env()
    env.bind(X, 5)
    
    # Method chaining should work
    result = env.where(lambda e: e.resolve(X) > 0)
    
    assert result is env, "where() should return the same Env instance"


def test_where_constraint_on_unbound_variable():
    """Test Env.where when constraint references an unbound variable."""
    scope = Scope()
    X = scope.X
    Y = scope.Y
    
    env = Env()
    env.bind(X, 10)
    # Y is not bound
    
    # Add a constraint that checks Y but Y is not resolved yet
    # The constraint function should still be added but will be evaluated during solve
    def check_y(e: Env) -> bool:
        y_val = e.resolve(Y)
        return y_val is not ... and y_val > 0
    
    env.where(check_y)
    
    # Bind Y to a value
    env.bind(Y, 5)
    
    # Now solve should succeed
    success, reason = env.solve()
    assert success, f"Constraint should be satisfied after Y is bound: {reason}"


