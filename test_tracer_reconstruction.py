#!/usr/bin/env python3
"""Test parse tree reconstruction from tracer events."""

from syncraft.tracer import Tracer, ParseNode


class MockState:
    """Mock state object for testing."""
    def __init__(self, cache_key: str, input_str: str):
        self.cache_key = cache_key
        self.input_str = input_str
    
    def str_input(self, ul: bool = False) -> str:
        return self.input_str


class MockRule:
    """Mock rule object for testing."""
    def __init__(self, name: str):
        self.name = name
    
    def __str__(self) -> str:
        return f"Rule({self.name})"


def test_simple_tree_reconstruction():
    """Test reconstructing a simple nested parse tree."""
    tracer = Tracer()
    
    # Create mock objects
    expr_rule = MockRule("expr")
    term_rule = MockRule("term")
    factor_rule = MockRule("factor")
    
    state1 = MockState("key1", "1+2*3")
    state2 = MockState("key2", "2*3")
    state3 = MockState("key3", "2")
    
    # Simulate parsing: expr -> term -> factor
    # Push expr (root)
    idx_expr = tracer.push(expr_rule, None, state1)
    
    # Push term (child of expr)
    idx_term = tracer.push(term_rule, expr_rule, state2)
    
    # Push factor (child of term)
    idx_factor = tracer.push(factor_rule, term_rule, state3)
    
    # Pop in reverse order
    tracer.pop(idx_factor, state3, "2")
    tracer.pop(idx_term, state2, "2*3")
    tracer.pop(idx_expr, state1, "1+2*3")
    
    # Reconstruct tree
    roots = tracer.tree()
    
    # Verify structure
    assert len(roots) == 1, f"Expected 1 root, got {len(roots)}"
    
    expr_node = roots[0]
    assert str(expr_node.rule) == "Rule(expr)"
    assert expr_node.result == "1+2*3"
    assert len(expr_node.children) == 1, f"Expected 1 child of expr, got {len(expr_node.children)}"
    
    term_node = expr_node.children[0]
    assert str(term_node.rule) == "Rule(term)"
    assert term_node.result == "2*3"
    assert len(term_node.children) == 1, f"Expected 1 child of term, got {len(term_node.children)}"
    
    factor_node = term_node.children[0]
    assert str(factor_node.rule) == "Rule(factor)"
    assert factor_node.result == "2"
    assert len(factor_node.children) == 0
    
    # Verify timing
    assert expr_node.duration_ns() is not None
    assert expr_node.duration_ns() > 0
    
    print("✓ Simple tree reconstruction test passed")
    print(f"  Root: {expr_node.rule}")
    print(f"    Child: {term_node.rule}")
    print(f"      Child: {factor_node.rule}")
    print(f"  Parse duration: {expr_node.duration_ns()} ns")


def test_multiple_roots():
    """Test reconstructing multiple independent parse trees."""
    tracer = Tracer()
    
    rule1 = MockRule("rule1")
    rule2 = MockRule("rule2")
    state1 = MockState("k1", "input1")
    state2 = MockState("k2", "input2")
    
    # Two independent root nodes
    idx1 = tracer.push(rule1, None, state1)
    tracer.pop(idx1, state1, "result1")
    
    idx2 = tracer.push(rule2, None, state2)
    tracer.pop(idx2, state2, "result2")
    
    roots = tracer.tree()
    
    assert len(roots) == 2, f"Expected 2 roots, got {len(roots)}"
    assert roots[0].result == "result1"
    assert roots[1].result == "result2"
    
    print("✓ Multiple roots test passed")


def print_tree(node: ParseNode, indent: int = 0) -> None:
    """Pretty-print a parse tree."""
    prefix = "  " * indent
    duration = f" ({node.duration_ns()}ns)" if node.duration_ns() else " (incomplete)"
    print(f"{prefix}{node.rule} → {node.result}{duration}")
    for child in node.children:
        print_tree(child, indent + 1)


def test_recursive_rule():
    """Test reconstructing a tree with recursive/looping rules."""
    tracer = Tracer()
    
    # Create a recursive rule (e.g., expr -> expr + term | term)
    expr_rule = MockRule("expr")
    term_rule = MockRule("term")
    
    state1 = MockState("k1", "1+2+3")
    state2 = MockState("k2", "1+2")
    state3 = MockState("k3", "1")
    state4 = MockState("k4", "2")
    state5 = MockState("k5", "3")
    
    # Parse: expr(1+2+3) -> expr(1+2) -> expr(1) -> term(1)
    #                                  -> term(2)
    #                   -> term(3)
    
    # Push expr (outer, root)
    idx_expr1 = tracer.push(expr_rule, None, state1)
    
    # Push expr (inner, recursive call)
    idx_expr2 = tracer.push(expr_rule, expr_rule, state2)
    
    # Push expr (innermost, recursive call)
    idx_expr3 = tracer.push(expr_rule, expr_rule, state3)
    
    # Push term (child of innermost expr)
    idx_term1 = tracer.push(term_rule, expr_rule, state3)
    tracer.pop(idx_term1, state3, "1")
    
    # Pop innermost expr
    tracer.pop(idx_expr3, state3, "1")
    
    # Push term (child of middle expr)
    idx_term2 = tracer.push(term_rule, expr_rule, state4)
    tracer.pop(idx_term2, state4, "2")
    
    # Pop middle expr
    tracer.pop(idx_expr2, state2, "1+2")
    
    # Push term (child of outer expr)
    idx_term3 = tracer.push(term_rule, expr_rule, state5)
    tracer.pop(idx_term3, state5, "3")
    
    # Pop outer expr
    tracer.pop(idx_expr1, state1, "1+2+3")
    
    # Reconstruct tree
    roots = tracer.tree()
    
    assert len(roots) == 1, f"Expected 1 root, got {len(roots)}"
    
    # Verify structure: expr1 -> expr2 -> expr3 -> term1
    #                                  -> term2
    #                        -> term3
    expr1 = roots[0]
    assert str(expr1.rule) == "Rule(expr)"
    assert expr1.result == "1+2+3"
    assert len(expr1.children) == 2, f"Expected 2 children of outer expr, got {len(expr1.children)}"
    
    expr2 = expr1.children[0]
    assert str(expr2.rule) == "Rule(expr)"
    assert expr2.result == "1+2"
    assert len(expr2.children) == 2, f"Expected 2 children of middle expr, got {len(expr2.children)}"
    
    expr3 = expr2.children[0]
    assert str(expr3.rule) == "Rule(expr)"
    assert expr3.result == "1"
    assert len(expr3.children) == 1, f"Expected 1 child of innermost expr, got {len(expr3.children)}"
    
    term1 = expr3.children[0]
    assert str(term1.rule) == "Rule(term)"
    assert term1.result == "1"
    
    term2 = expr2.children[1]
    assert str(term2.rule) == "Rule(term)"
    assert term2.result == "2"
    
    term3 = expr1.children[1]
    assert str(term3.rule) == "Rule(term)"
    assert term3.result == "3"
    
    print("✓ Recursive rule test passed")
    print("  Tree structure:")
    print_tree(expr1)


if __name__ == "__main__":
    test_simple_tree_reconstruction()
    test_multiple_roots()
    test_recursive_rule()
    print("\n✅ All reconstruction tests passed!")
