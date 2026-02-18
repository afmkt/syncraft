#!/usr/bin/env python3
"""
Test non-recursive (non-lazy) grammar to isolate the asymmetry issue.
"""

from syncraft.syntax import Syntax
from syncraft.ast import Token, Alt, Seq, Lazy, Many
from syncraft.parser import parse_word
from syncraft.generator import generate_with
from syncraft.cache import Cache
from typing import Any
class S:
    @staticmethod
    def lit(text: Any) -> Syntax[Any, Any]:
        return Syntax.lit(text=text)

def test_non_lazy_or_simple():
    """Test OrElse without Then: a | b"""
    A = S.lit('a')
    B = S.lit('b')
    AB_or = A | B
    
    v = parse_word(AB_or, 'a')    
    vv = generate_with(AB_or, v)
    
    expected = Alt(
        index = 0,
        value=Token('a')
    )
    assert vv == expected, f"Expected {expected}, got {vv}"
    v = parse_word(AB_or, 'b')    
    vv = generate_with(AB_or, v)    

    expected = Alt(
        index = 1,
        value=Token('b')
    )
    assert vv == expected, f"Expected {expected}, got {vv}"
        


def test_non_lazy_then():
    """Test Then combinator without lazy: a + b"""
    A = S.lit('a')
    B = S.lit('b')
    AB = A + B
    
    v = parse_word(AB, 'a b')
    vv = generate_with(AB, v)
    
    expected = Seq(
        value=((Token('a'), True), (Token('b'), True))
    )
    assert vv == expected, f"Expected {expected}, got {vv}"
    


def test_non_lazy_or():
    """Test OrElse combinator without lazy: a | b"""
    A = S.lit('a')
    B = S.lit('b')
    AB = A | B
    
    v = parse_word(AB, 'a')
    vv = generate_with(AB, v)
    
    expected = Alt(
        index = 0,
        value=Token('a')
    )
    assert vv == expected, f"Expected {expected}, got {vv}"
    


def test_non_lazy_nested():
    """Test nested combinators without lazy: (a + b) | c"""
    A = S.lit('a')
    B = S.lit('b')
    C = S.lit('c')
    nested = (A + B) | C
    
    v = parse_word(nested, 'a b')
    vv = generate_with(nested, v)
    
    expected = Alt(
        index = 0,
        value=Seq(
            value=((Token('a'), True), (Token('b'), True))
        )
    )
    assert vv == expected, f"Expected {expected}, got {vv}"
    


def test_non_lazy_deep_nesting():
    """Test deeply nested without lazy: ((a + b) | c) + (d | e)"""
    A = S.lit('a')
    B = S.lit('b')
    C = S.lit('c')
    D = S.lit('d')
    E = S.lit('e')
    left = (A + B) | C
    right = D | E
    full = left + right
    
    v = parse_word(full, 'a b d')
    vv = generate_with(full, v)
    

    expected = Seq(value=((Alt(index=0, value=Seq(value=((Token(text='a'), True), (Token(text='b'), True)))), True), (Alt(index=0, value=Token(text='d')), True)))
    assert vv == expected, f"Expected {expected}, got {vv}"
    


def test_or_choice_simple():
    """Test simple alternation: a | b | c"""
    A = S.lit('a')
    B = S.lit('b')
    C = S.lit('c')
    ABC = A | B | C
    
    v = parse_word(ABC, 'b')
    vv = generate_with(ABC, v)
    
    # No lazy combinator, so should reconstruct the raw parsed value
    expected = Alt(index=0, value=Alt(index=1, value=Token('b')))
    assert vv == expected, f"Expected {expected}, got {vv}"
    


def test_many_simple():
    """Test many without Then: a*"""
    A = S.lit('a')
    A_many = A.many()
    
    v= parse_word(A_many, 'a a a')
    vv = generate_with(A_many, v)
    
    # No lazy combinator, so should reconstruct the raw parsed value
    expected = Many(value=(Token(text='a'), Token(text='a'), Token(text='a')))
    assert vv == expected, f"Expected {expected}, got {vv}"
    print("✓ Many test passed")


def test_or_with_many():
    """Test alternation with repetition: (a | b)*"""
    A = S.lit('a')
    B = S.lit('b')
    AB = A | B
    AB_many = AB.many()
    
    v = parse_word(AB_many, 'a b a')
    vv = generate_with(AB_many, v)
    
    # No lazy combinator, so should reconstruct the raw parsed value
    expected = Many(value=(Alt(index=0, value=Token('a')), 
                           Alt(index=1, value=Token('b')), 
                           Alt(index=0, value=Token('a'))))
    assert vv == expected, f"Expected {expected}, got {vv}"


def test_lazy_or():
    """Test lazy alternation with choice"""
    A = S.lit('a')
    B = S.lit('b')
    
    # Recursive: a | b | recursive
    def make_rec():
        return A | B | rec
    
    rec = Syntax.lazy(make_rec)
    
    v = parse_word(rec, 'b')
    vv = generate_with(rec, v)
    
    expected =  Lazy(value=Alt(index=0, value=Alt(index=1, value=Token(text='b'))))
    assert vv == expected, f"Expected {expected}, got {vv}"
    


def test_or_many():
    """Test lazy with many: a | b*"""
    A = S.lit('a')
    B = S.lit('b')
    B_many = B.many()
    
    rec = A | B_many
    v = parse_word(rec, 'b b b')
    vv = generate_with(rec, v)
    
    

    expected = Alt(index=1, value=Many(value=(Token(text='b'), Token(text='b'), Token(text='b'))))
    assert vv == expected, f"Expected {expected}, got {vv}"



