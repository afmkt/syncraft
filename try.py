from __future__ import annotations

# from rich import print
from pyDatalog import pyDatalog as d
from syncraft.regex import (
    parse_regex, parse, RE, parse_regex,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
from rich import print

import timeit



def benchmark_fair():
    from syncraft.regex import parse as parse3
    count = 500
    result = []
    base_patterns = [
        r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        r'(?r)$|\W{4,}.+\U000FEAE1?u*',
        r'4{1}|e*\b(?0)[FyIn]{4,}',
        r'\U000A231E[^OtVLo]*N{2,5}|T\u966F*.{0,3}.{5}|^\B(?R)',
        r'\U000D6EAF.{2,6}(?r)\U0007CA66*',
        r'.{1}\u2B7B?[ivMe]|(?r)|[rqp\w]{2}[^HqbqM]{0,5}\D{4,}L{2,3}',
        r'(?p)\W^|r?u{2,6}',
        r'(?f)',
        r'(?b)',
        r'(?r)$|\W{4,}.+\U000FEAE1?u*',
        r'4{1}|e*\b(?0)[FyIn]{4,}',
        r'\U000A231E[^OtVLo]*N{2,5}|T\u966F*.{0,3}.{5}|^\B(?R)',
        r'\U000D6EAF.{2,6}(?r)\U0007CA66*',
        r'.{1}\u2B7B?[ivMe]|(?r)|[rqp\w]{2}[^HqbqM]{0,5}\D{4,}L{2,3}',

    ]
    t = 0
    t3 = 0
    for base_pattern in base_patterns:
        def run3():
            try:
                parse3(base_pattern, raw=False) 
            except StopIteration:
                pass


        def run():
            try:
                parse(base_pattern, raw=False) 
            except StopIteration:
                pass


        t += timeit.timeit(run3, number=count)
        t3 += timeit.timeit(run, number=count)

    result.append("--- FAIR COMPARISON (Cold Start) ---")
    
    result.append(f"Regex: {t/count:.5f} s/parse")
    result.append(f"Regex3:    {t3/count:.5f} s/parse")
    
    ratio = (t) / (t3)
    result.append(f"Multiplier: Syncraft is {ratio:.5f}x slower than C-compiled Regex")
    return result


def test_direct_left_recursive_map_preserves_shape()->None:
        from syncraft.ast import Token
        import syncraft.generator as gen
        from syncraft.parser import parse_word
        from syncraft.syntax import Syntax
        """Direct left recursion: Expr -> Expr "+" NUM | NUM

        We compare:
            1. Raw token version (NUM un-mapped) parsing '1 + 2 + 3'.
            2. Mapped NUM to int version.

        Structural expectation (raw): ((t.1, t.+, t.2), t.+, t.3)
        Mapped: ((1, '+', 2), '+', 3)
        The nested triple shape must be preserved; only leaves (tokens -> ints) differ.
        """
        import re
        literal = Syntax.lit
        lazy = Syntax.lazy

        NUM = literal(re.compile(r'\d+'))
        PLUS = literal('+')
        Expr = lazy(lambda: (Expr + PLUS + NUM) | NUM)  # type: ignore[name-defined]
        v,_ = parse_word(Expr, '1 + 2 + 3', cache=None)
        generated, bound = gen.generate_with(Expr, v)
        assert v.mapped == generated.mapped
        ast, back = v.bimap
        assert ast == back(ast).mapped

        raw,_ = v.bimap
        # Raw structure assertions
        assert isinstance(raw, tuple) and len(raw) == 3
        assert isinstance(raw[0], tuple) and len(raw[0]) == 3  # left nested
        
        assert raw[1] == Token(text='+')
        assert raw[2] == Token(text='3')

        # Mapped version
        NUM_M = NUM.iso(lambda t: int(t.text), lambda n: Token(text=str(n)))  
        ExprM = lazy(lambda: (ExprM + PLUS + NUM_M) | NUM_M)  # type: ignore[name-defined]
        v2,_ = parse_word(ExprM, '1 + 2 + 3', cache=None)
        generated, bound = gen.generate_with(ExprM, v2)


        assert v2.mapped == generated.mapped
        ast, back = v2.bimap
        assert ast == back(ast).mapped

        mapped,_ = v2.bimap
        assert isinstance(mapped, tuple) and len(mapped) == 3
        left_nested, mid_op, right_leaf = mapped
        assert isinstance(left_nested, tuple) and len(left_nested) == 3
        assert mid_op.text == '+'
        assert right_leaf == 3
        # Check leaves inside nested left part transformed properly
        assert left_nested[0] == 1
        assert left_nested[1].text == '+'
        assert left_nested[2] == 2



def test_multi_recursion()->None:
    from syncraft.ast import Token, Lazy
    import syncraft.generator as gen
    from syncraft.parser import parse_word
    from syncraft.syntax import Syntax
    literal = Syntax.lit
    lazy = Syntax.lazy

    a = literal('a').iso(lambda x: x.text, lambda t: Token(text=t)).named('a')
    b = literal('b').iso(lambda x: x.text, lambda t: Token(text=t)).named('b')
    c = literal('c').iso(lambda x: x.text, lambda t: Token(text=t)).named('c')
    x = literal('x').iso(lambda x: x.text, lambda t: Token(text=t)).named('x')
    y = literal('y').iso(lambda x: x.text, lambda t: Token(text=t)).named('y')
    z = literal('z').iso(lambda x: x.text, lambda t: Token(text=t)).named('z')
    A = lazy(lambda: (B + x) | a).named('A')
    B = lazy(lambda: (C + y) | b).named('B')
    C = lazy(lambda: (A + z) | c).named('C')

    v, s = parse_word(A, 'a z y x', cache=None)
    generated, bound = gen.generate_with(A, v)
    assert v.mapped == generated.mapped
    ast, back = v.bimap
    assert ast == back(ast).mapped

    print(v)
    # We care about the raw AST shape (pre-bimap). Extract leaves manually.
    from syncraft.ast import Then, ThenKind
    from syncraft.algebra import OrElse, OrElseKind  # type: ignore

    def leaves(node):
        if isinstance(node, Lazy):
            return leaves(node.value)
        if isinstance(node, Then) and node.kind == ThenKind.BOTH:
            return leaves(node.left) + leaves(node.right)
        if isinstance(node, OrElse):
            # For this grammar OrElse.RIGHT wraps literal terminal; LEFT wraps a Then chain.
            if node.kind == OrElseKind.RIGHT:
                return (node.value,)
            else:
                return leaves(node.value)
        if isinstance(node, str):
            return (node,)
        return ()

    assert leaves(v) == ('a','z','y','x')



def test():
    from syncraft.ast import Token
    import syncraft.generator as gen
    from syncraft.parser import parse_word
    from syncraft.syntax import Syntax
    import re
    literal = Syntax.lit
    lazy = Syntax.lazy

    NUM = literal(re.compile(r'\d+'))
    NUM_M = NUM.iso(lambda t: int(t.text), lambda n: Token(text=str(n)))  

    v2 , _ = parse_word(NUM_M, '123', cache=None)
    print(v2)
    generated, bound = gen.generate_with(NUM_M, v2)



if __name__ == "__main__":
    test_direct_left_recursive_map_preserves_shape()
    

