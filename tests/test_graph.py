from __future__ import annotations

from syncraft.ast import Then, ThenKind, Many, Choice, ChoiceKind, Token, Marked, Nothing, Any
from syncraft.algebra import Error
from syncraft.parser import  parse_word
import syncraft.generator as gen
from syncraft.syntax import Syntax
from syncraft.cache import Cache
import pytest


literal = Syntax.literal
lazy = Syntax.lazy


def test1_simple_then() -> None:
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    g = syntax.graph()
    syntax2 = Syntax.from_graph(g)
    ast2, bound2 = parse_word(syntax2, sql, cache=Cache())
    assert ast == ast2, "ASTs from original and reconstructed syntax should match"
    assert g == syntax2.graph(), "Original and reconstructed syntax graphs should match"


def test2_choice()->None:
    A, B = literal("a"), literal("b")
    syntax = A | B
    sql = "b"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    g = syntax.graph()
    syntax2 = Syntax.from_graph(g)
    ast2, bound2 = parse_word(syntax2, sql, cache=Cache())
    assert ast == ast2, "ASTs from original and reconstructed syntax should match"
    assert g == syntax2.graph(), "Original and reconstructed syntax graphs should match"


def test3_many_literals() -> None:
    A = literal("a")
    syntax = A.many()
    sql = "a a a"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    g = syntax.graph()
    syntax2 = Syntax.from_graph(g)
    ast2, bound2 = parse_word(syntax2, sql, cache=Cache())
    assert ast == ast2, "ASTs from original and reconstructed syntax should match"
    assert g == syntax2.graph(), "Original and reconstructed syntax graphs should match"


def test4_complex_syntax() -> None:
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = (A // B.many() // C) | (B // C.many() // A)
    sql = "a b b c"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    g = syntax.graph()
    syntax2 = Syntax.from_graph(g)
    ast2, bound2 = parse_word(syntax2, sql, cache=Cache())
    assert ast == ast2, "ASTs from original and reconstructed syntax should match"
    assert g == syntax2.graph(), "Original and reconstructed syntax graphs should match"

def test5_marked_tokens() -> None:
    A = literal("a").mark("x").mark("y")
    syntax = A.many()
    sql = "a a a"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    g = syntax.graph()
    syntax2 = Syntax.from_graph(g)
    ast2, bound2 = parse_word(syntax2, sql, cache=Cache())
    assert ast == ast2, "ASTs from original and reconstructed syntax should match"
    assert g == syntax2.graph(), "Original and reconstructed syntax graphs should match"

def test6_lazy() -> None:
    A = literal("a")
    syntax = lazy(lambda: syntax + A | A)
    sql = "a a a"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    g = syntax.graph()
    syntax2 = Syntax.from_graph(g)
    ast2, bound2 = parse_word(syntax2, sql, cache=Cache())
    assert ast == ast2, "ASTs from original and reconstructed syntax should match"
    assert g == syntax2.graph(), "Original and reconstructed syntax graphs should match"


def test7_edge_count_consistency() -> None:
    """Test that graph reconstruction preserves edge count (tests structural equivalence fix)."""
    # Create a complex choice structure similar to regex grammar
    A = literal("a").named("literal_a")
    B = literal("b").named("literal_b") 
    C = literal("c").named("literal_c")
    D = literal("d").named("literal_d")
    E = literal("e").named("literal_e")
    
    # Build a choice with named components
    syntax = A | B | C | D | E
    
    # Get the original graph
    g = syntax.graph()
    
    # Reconstruct syntax from graph
    syntax2 = Syntax.from_graph(g)
    
    # Get the reconstructed graph
    g1 = syntax2.graph()
    
    # The main test: edge counts should be identical
    assert len(g.edges) == len(g1.edges), f"Edge count mismatch: original={len(g.edges)}, reconstructed={len(g1.edges)}"
    assert g.root == g1.root, "Graph roots should be identical"


def test8_many_alternatives_edge_count() -> None:
    """Test edge count consistency with many alternatives."""
    # Create many alternatives to stress test the structural equivalence
    literals = [Syntax.literal(c).named(f"lit_{c}") for c in "abcdefghij"]
    
    # Build a large choice: A | B | C | D | E | F | G | H | I | J
    syntax = literals[0]
    for lit in literals[1:]:
        syntax = syntax | lit
    
    # Get the original graph
    g = syntax.graph()
    
    # Reconstruct syntax from graph
    syntax2 = Syntax.from_graph(g)
    
    # Get the reconstructed graph
    g1 = syntax2.graph()
    
    # Test edge count consistency
    assert len(g.edges) == len(g1.edges), f"Edge count mismatch with many alternatives: original={len(g.edges)}, reconstructed={len(g1.edges)}"
    assert g.root == g1.root, "Graph roots should be identical"


def test9_recursive_lazy_pattern() -> None:
    """Test recursive lazy pattern that mimics complex grammar structures."""
    # Create a recursive pattern similar to grammar structures
    def make_atom():
        """atom = literal | group | ..."""
        literal_node = Syntax.literal("x").named('literal')
        # Include the lazy group in atom choice (creates recursion)
        return Syntax.choice(literal_node, group).named('atom')
    
    def make_piece():
        """piece = atom [quantifier]"""
        quantifier = Syntax.literal("?").named('quantifier')
        return (atom + (~quantifier)).named('piece')
    
    def make_branch():
        """branch = piece+"""
        return piece.many().named('branch')
    
    def make_group_body():
        """group body that refers back to branch"""
        return (Syntax.literal("(") >> branch // Syntax.literal(")")).named('group_body')
    
    # Create the recursive definitions
    group = Syntax.lazy(make_group_body).named('group')
    atom = Syntax.lazy(make_atom)
    piece = Syntax.lazy(make_piece)
    branch = Syntax.lazy(make_branch)
    
    # Test with the recursive structure
    syntax = atom
    
    # Get the original graph
    g = syntax.graph()
    
    # Reconstruct syntax from graph  
    syntax2 = Syntax.from_graph(g)
    
    # Get the reconstructed graph
    g1 = syntax2.graph()
    
    # Test edge count consistency
    assert len(g.edges) == len(g1.edges), f"Edge count mismatch in recursive pattern: original={len(g.edges)}, reconstructed={len(g1.edges)}"
    assert g.root == g1.root, "Graph roots should be identical"


def test10_regex_syntax_edge_count() -> None:
    """Test that the actual regex syntax maintains edge count consistency."""
    from syncraft.regex import regex_syntax
    
    # Get the original graph
    g = regex_syntax.graph()
    
    # Reconstruct syntax from graph
    syntax2 = Syntax.from_graph(g)
    
    # Get the reconstructed graph
    g1 = syntax2.graph()
    
    # The critical test that was initially failing - this is the main fix validation
    assert len(g.edges) == len(g1.edges), f"Regex grammar edge count mismatch: original={len(g.edges)}, reconstructed={len(g1.edges)}"
    assert g.root == g1.root, "Regex grammar graph roots should be identical"
