#!/usr/bin/env python3
"""
Test cases for LazyState structural equality and graph consistency.

These tests validate the fix for the LazyState hash/equality contract issue
that was causing graph reconstruction to create inconsistent edge counts.
"""

import pytest
from syncraft.syntax import LazyState, Syntax
from syncraft.regex import regex_syntax


def test_lazy_state_hash_equality_contract():
    """Test that LazyState properly implements the hash/equality contract."""
    
    def thunk1():
        return Syntax.literal("hello")
    
    def thunk2():
        return Syntax.literal("hello")
    
    # Create two LazyState objects with same content but different thunk functions
    state1 = LazyState(flatten=False, thunk=thunk1)
    state2 = LazyState(flatten=False, thunk=thunk2)
    
    # Test structural equality - they should NOT be equal because thunks are different
    assert state1 != state2, "LazyState objects with different thunks should not be equal"
    
    # Test hash consistency - different objects should have different hashes
    assert hash(state1) != hash(state2), "LazyState objects with different thunks should have different hashes"
    
    # Test same object equality
    state3 = state1
    assert state1 == state3, "Same LazyState object should be equal to itself"
    assert hash(state1) == hash(state3), "Same LazyState object should have same hash"


def test_lazy_state_equality_with_same_thunk():
    """Test LazyState equality when using the same thunk function."""
    
    def shared_thunk():
        return Syntax.literal("shared")
    
    # Create two LazyState objects with the same thunk function reference
    state1 = LazyState(flatten=False, thunk=shared_thunk)
    state2 = LazyState(flatten=False, thunk=shared_thunk)
    
    # They should be equal because they have the same thunk reference
    assert state1 == state2, "LazyState objects with same thunk should be equal"
    assert hash(state1) == hash(state2), "LazyState objects with same thunk should have same hash"


def test_lazy_state_flatten_affects_equality():
    """Test that the flatten parameter affects LazyState equality."""
    
    def thunk():
        return Syntax.literal("test")
    
    state1 = LazyState(flatten=True, thunk=thunk)
    state2 = LazyState(flatten=False, thunk=thunk)
    
    # They should NOT be equal because flatten differs
    assert state1 != state2, "LazyState objects with different flatten should not be equal"
    assert hash(state1) != hash(state2), "LazyState objects with different flatten should have different hashes"


def test_lazy_state_type_checking():
    """Test LazyState equality with non-LazyState objects."""
    
    def thunk():
        return Syntax.literal("test")
    
    state = LazyState(flatten=False, thunk=thunk)
    
    # Should not be equal to non-LazyState objects
    assert state != "not a LazyState"
    assert state != 42
    assert state is not None
    assert state != {}


def test_graph_edge_count_consistency():
    """Test that graph reconstruction maintains consistent edge counts."""
    
    # This is the main regression test for the original bug
    g = regex_syntax.graph()
    syntax2 = Syntax.from_graph(g)
    g1 = syntax2.graph()
    
    # The critical assertions that were initially failing
    assert len(g.edges) == len(g1.edges), f"Edge count mismatch: original={len(g.edges)}, reconstructed={len(g1.edges)}"
    assert g.root == g1.root, "Graph roots should be structurally equal"


def test_simple_lazy_graph_reconstruction():
    """Test graph reconstruction with simple lazy syntax."""
    
    def make_lazy_syntax():
        return Syntax.literal("hello").named("greeting")
    
    # Create syntax with lazy reference
    lazy_syntax = Syntax.lazy(make_lazy_syntax).named("lazy_greeting")
    
    # Test graph reconstruction
    g = lazy_syntax.graph()
    syntax2 = Syntax.from_graph(g)
    g1 = syntax2.graph()
    
    # Verify consistency
    assert len(g.edges) == len(g1.edges), "Simple lazy syntax should maintain edge count"
    assert g.root == g1.root, "Simple lazy syntax roots should be equal"


def test_recursive_lazy_graph_reconstruction():
    """Test graph reconstruction with recursive lazy patterns."""
    
    def make_atom():
        return Syntax.literal("x")
    
    def make_piece():
        return atom | group
    
    def make_branch():
        return piece.many().named('branch')
    
    def make_group_body():
        return (Syntax.literal("(") >> branch // Syntax.literal(")")).named('group_body')
    
    # Create the recursive definitions
    group = Syntax.lazy(make_group_body).named('group')
    atom = Syntax.lazy(make_atom).named('atom')
    piece = Syntax.lazy(make_piece).named('piece')
    branch = Syntax.lazy(make_branch).named('branch')
    
    # Test with the recursive structure
    syntax = atom
    
    # Get the original graph
    g = syntax.graph()
    
    # Reconstruct syntax from graph  
    syntax2 = Syntax.from_graph(g)
    
    # Get the reconstructed graph
    g1 = syntax2.graph()
    
    # Test edge count consistency
    assert len(g.edges) == len(g1.edges), f"Recursive pattern edge count mismatch: original={len(g.edges)}, reconstructed={len(g1.edges)}"
    assert g.root == g1.root, "Recursive pattern graph roots should be identical"


def test_lazy_state_cache_independence():
    """Test that LazyState cache fields don't affect equality."""
    
    def thunk():
        return Syntax.literal("cached")
    
    state1 = LazyState(flatten=False, thunk=thunk)
    state2 = LazyState(flatten=False, thunk=thunk)
    
    # Force cache population in state1
    _ = state1.cached
    
    # state2 cache is still empty, but they should still be equal
    assert state1 == state2, "LazyState equality should not depend on cache state"
    assert hash(state1) == hash(state2), "LazyState hash should not depend on cache state"


def test_function_identity_vs_structural_equivalence():
    """Test that demonstrates the core function identity issue we fixed."""
    
    def create_same_function():
        """Create the same logical function twice"""
        def inner():
            return Syntax.literal("hello")
        return inner
    
    # Same function created twice - different objects
    f1 = create_same_function()
    f2 = create_same_function()
    
    # Functions with identical code are not equal by default in Python
    assert f1 != f2, "Functions with identical code are different objects"
    assert hash(f1) != hash(f2), "Functions with identical code have different hashes"
    
    # But their code is structurally the same
    assert f1.__code__.co_code == f2.__code__.co_code, "Function code should be identical"
    assert f1.__name__ == f2.__name__, "Function names should be identical"
    
    # This is why LazyState objects with "equivalent" thunks are not equal
    state1 = LazyState(flatten=False, thunk=f1)
    state2 = LazyState(flatten=False, thunk=f2)
    
    assert state1 != state2, "LazyState with different thunk objects should not be equal"
    assert hash(state1) != hash(state2), "LazyState with different thunk objects should have different hashes"


if __name__ == "__main__":
    # Run the tests directly if executed as a script
    pytest.main([__file__, "-v"])