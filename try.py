from __future__ import annotations
from syncraft.bimap import Env, Scope, let, solve
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
    value = {"value": 20, "doubled": 40}
    result = solve(pattern, value, env)
    
    assert isinstance(result, Env), f"Expected Env, got {result}"
    
    # Solve should fail because constraint is not satisfied
    success, reason = result.solve()
    assert not success, "Constraint should fail when B <= 10"
if __name__ == "__main__":
    test_where_constraint_fails_on_pattern()