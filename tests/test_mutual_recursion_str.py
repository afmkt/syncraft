"""
Test that mutually recursive grammars can be safely stringified without
entering infinite recursion loops.
"""

from syncraft.syntax import Syntax


def test_mutual_recursion_str():
    """Test that mutual recursion in __str__ is properly detected and handled."""
    
    # Create a mutually recursive grammar
    # expr := term ('+' expr)?
    # term := 'a'
    
    expr = Syntax.lazy(lambda: term | (Syntax.lit('a') + expr)).named('expr')
    term = Syntax.lit('a').named('term')
    
    # This should not hang or raise RecursionError
    result = str(expr)
    print(f"expr str: {result}")
    assert isinstance(result, str)
    assert len(result) > 0
    
    # Try with deeper recursion
    # list := '[' (item (',' item)*)? ']'
    # item := list | 'x'
    
    list_syntax = Syntax.lazy(
        lambda: Syntax.lit('[') + (item.sep_by(Syntax.lit(','))).optional + Syntax.lit(']')
    ).named('list')
    
    item = (list_syntax | Syntax.lit('x')).named('item')
    
    result2 = str(list_syntax)
    print(f"list_syntax str: {result2}")
    assert isinstance(result2, str)
    assert len(result2) > 0
    
    # Try a more complex mutual recursion
    a = Syntax.lazy(lambda: Syntax.lit('a') + b).named('a')
    b = Syntax.lazy(lambda: Syntax.lit('b') + a).named('b')
    
    result3 = str(a)
    result4 = str(b)
    print(f"a str: {result3}")
    print(f"b str: {result4}")
    assert isinstance(result3, str)
    assert isinstance(result4, str)
    
    print("\nAll tests passed! Mutual recursion in __str__ is properly handled.")

