from __future__ import annotations
from syncraft.syntax import Syntax
from syncraft.bimap import unify_all, let, Env, Scope, evaluate, Expr
import pytest

literal = Syntax.lit


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



if __name__ == '__main__':
    test_length_prefixed()    
    
    
    
    
    