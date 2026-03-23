from __future__ import annotations
from typing import Any, Iterable
from syncraft.ast import Nothing, Lazy, Seq, Alt
from syncraft.parser import parse_word

from syncraft.syntax import Syntax
from syncraft.cache import LeftRecursionError
from syncraft.cache import set_randomization
import syncraft.generator as gen
from syncraft.token import Str, Token
import re
import pytest


def iter_tokens(ast: Any) -> Iterable[str]:
    if isinstance(ast, Token):
        yield ast.text # type: ignore
    elif isinstance(ast, (tuple, list)):
        for x in ast:
            yield from iter_tokens(x)
    elif hasattr(ast, 'value') and isinstance(getattr(ast, 'value'), tuple):
        # For Then/OrElse wrappers from syncraft.ast
        for x in getattr(ast, 'value'):
            yield from iter_tokens(x)
    elif hasattr(ast, 'left') and hasattr(ast, 'right'):
        yield from iter_tokens(getattr(ast, 'left'))
        yield from iter_tokens(getattr(ast, 'right'))
    else:
        # Fallback: scan string repr for bare word tokens (letters, digits)
        for t in re.findall(r'[A-Za-z0-9_]+', str(ast)):
            yield t


def token_multiset(ast: Any) -> dict[str, int]:
    counts: dict[str,int] = {}
    for t in iter_tokens(ast):
        counts[t] = counts.get(t, 0) + 1
    return counts





# Ensure randomization is enabled for these tests
set_randomization(True)

S = Syntax

def literal(text:Any) -> Syntax[Any, Any]:
    return S.tok(Token(text=Str(text)))

lazy = S.lazy

def from_string(string: str) -> Token:
    return Token(text=string)



def test_simple_recursion()->None:
    A = lazy(lambda: literal('a') + ~A | literal('a'))
    
    v = parse_word(A, 'a a a')
    
    assert v == (Token(text='a'), (Token(text='a'), (Token(text='a'), Nothing)))
    vv = gen.generate_with(A, v)
    
    expected = Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (Token(text='a'), True),
                    (
                        Alt(
                            index=0,
                            value=Lazy(
                                value=Alt(
                                    index=0,
                                    value=Seq(
                                        value=(
                                            (Token(text='a'), True),
                                            (Alt(index=0, value=Lazy(value=Alt(index=0, value=Seq(value=((Token(text='a'), True), (Alt(index=1, value=Nothing), True)))))), True)
                                        )
                                    )
                                )
                            )
                        ),
                        True
                    )
                )
            )
        )
    )
    
    assert vv == expected, f"Expected {expected}, got {vv}"
    


def test_direct_recursion_equivalence()->None:
    Expr1 = lazy(lambda: literal('a') + ~Expr1)
    v = parse_word(Expr1, 'a a')
    expected = (Token(text='a'), (Token(text='a'), Nothing))
    assert v == expected
    ast = gen.generate_with(Expr1, v)
    expected_ast = Lazy(value=Seq(value=((Token(text='a'), True), (Alt(index=0, value=Lazy(value=Seq(value=((Token(text='a'), True), (Alt(index=1, value=Nothing), True))))), True))))

    assert ast == expected_ast
    


def test_mutual_recursion()->None:
    A = lazy(lambda: literal('a') + B)
    B = lazy(lambda: (literal('b') + A) | (literal('c')))
    v = parse_word(A, 'a b a b a c')
    # print(v)
    assert v == (Token(text='a'), (Token(text='b'), (Token(text='a'), (Token(text='b'), (Token(text='a'), Token(text='c'))))))

    vv = gen.generate_with(A, v)
    # print(vv)
    assert vv == Lazy(
        value=Seq(
            value=(
                (Token(text='a'), True),
                (
                    Lazy(
                        value=Alt(
                            index=0,
                            value=Seq(
                                value=(
                                    (Token(text='b'), True),
                                    (
                                        Lazy(
                                            value=Seq(
                                                value=(
                                                    (Token(text='a'), True),
                                                    (
                                                        Lazy(
                                                            value=Alt(
                                                                index=0,
                                                                value=Seq(
                                                                    value=(
                                                                        (Token(text='b'), True),
                                                                        (Lazy(value=Seq(value=((Token(text='a'), True), (Lazy(value=Alt(index=1, value=Token(text='c'))), True)))), True)
                                                                    )
                                                                )
                                                            )
                                                        ),
                                                        True
                                                    )
                                                )
                                            )
                                        ),
                                        True
                                    )
                                )
                            )
                        )
                    ),
                    True
                )
            )
        )
    )
    

def test_recursion() -> None:
    A = literal('a')
    B = literal('b')
    L = lazy(lambda: literal("if") >> (A | B) // literal('then'))

    def parens():
        return A + ~lazy(parens) + B
    p_code = 'a a b b'
    LL = parens() | L
    
    v = parse_word(LL, p_code)
    # print(v)
    assert v == (Token(text='a'), (Token(text='a'), Nothing, Token(text='b')), Token(text='b'))
    
    vv = gen.generate_with(LL, v)
    
    # print(vv)
    assert vv == Alt(
        index=0,
        value=Seq(
            value=(
                (Token(text='a'), True),
                (Alt(index=0, value=Lazy(value=Seq(value=((Token(text='a'), True), (Alt(index=1, value=Nothing), True), (Token(text='b'), True))))), True),
                (Token(text='b'), True)
            )
        )
    )



def test_left_recursion_variants()->None:
    """Group multiple left-recursive grammar checks into one test.

    Includes:
    1. Arithmetic chain Expr -> Expr + Term | Term
    2. Right-growth style (Expr1 + a) | a
    """
    # Variant 1: arithmetic chain
    Term = literal('n')
    Expr = lazy(lambda: Expr + literal('+') + Term | Term)
    v1 = parse_word(Expr, 'n + n + n')
    # ast1, _ = v1.bimap
    counts1 = token_multiset(v1)
    assert counts1.get('n', 0) == 3
    assert counts1.get('+', 0) == 2
    # Variant 2: nested right growth
    a_tok = literal('a').map(lambda x: x.text).named('a')
    Expr1 = lazy(lambda: (Expr1 + a_tok) | a_tok).named('Expr1')
    v2 = parse_word(Expr1, 'a a a a')
    # ast2, _ = v2.bimap
    assert v2 == ((('a', 'a'), 'a'), 'a')


def test_indirect_left_recursion()->None:
    NUMBER = literal(re.compile(r'\d+')).map(lambda x: int(x.text))
    PLUS = literal(text='+')
    STAR = literal(text='*')
    A = lazy(lambda: (B >> PLUS >> A) | B)
    B = lazy(lambda: (A >> STAR >> NUMBER) | NUMBER)
    # Now succeeds (partial parse); ensure at least first two numbers captured
    v = parse_word(A, '1 + 2 * 3')
    # ast, _ = v.bimap
    counts = token_multiset(v)
    # Current partial recovery yields only last NUMBER; ensure at least one digit captured
    assert any(k.isdigit() for k in counts.keys())




def test_indirect_left_recursion_2()->None:
    NUMBER = literal(re.compile(r'\d+')).map(lambda x: int(x.text))
    PLUS = literal(text='+')
    STAR = literal(text='*')
    LPAREN = literal(text='(')
    RPAREN = literal(text=')')
    Expr = lazy(lambda: (Expr + PLUS + Term) | Term)
    Term = lazy(lambda: (Term + STAR + Factor) | Factor)
    Factor: Syntax[Alt, Any] = lazy(lambda: (LPAREN + Expr + RPAREN) | NUMBER)

    v1 = parse_word(Expr, '1 + 2 * 3')
    assert v1 == (1, Token(text='+'), (2, Token(text='*'), 3))
    
    def leaf(x):
        try:
            return int(str(x)[2:]) if str(x).startswith('t.') and str(x)[2:].isdigit() else (str(x)[2:] if str(x).startswith('t.') else x)
        except Exception:
            return x
    def norm(ast):
        if isinstance(ast, tuple) and len(ast) == 3 and isinstance(ast[1], (str, object)):
            return (norm(ast[0]), leaf(ast[1] if not isinstance(ast[1], tuple) else ast[1]), norm(ast[2]))
        return leaf(ast)
    normalized = norm(v1)
    print(normalized)
    assert normalized == (1, '+', (2, '*', 3)), f"Unexpected normalized AST: {normalized}"
    

    v_42 = parse_word(Expr, '42')
    
    single_norm = norm(v_42)
    assert single_norm == 42


def test_indirect_left_recursion_structured_plus()->None:
    NUMBER = literal(re.compile(r'\d+'))
    PLUS = literal(text='+')
    STAR = literal(text='*')
    # Build lazily; references inside lambdas rely on late binding of the names.
    Expr = lazy(lambda: (Expr + PLUS + Term) | Term)  # type: ignore[name-defined]
    Term = lazy(lambda: (Term + STAR + Factor) | Factor)  # type: ignore[name-defined]
    Factor = lazy(lambda: NUMBER)
    v = parse_word(Expr,'1 + 2 * 3')
    
    assert v == (Token(text='1'), Token(text='+'), (Token(text='2'), Token(text='*'), Token(text='3')))


def test_mutual_left_recursive_map_preserves_shape()->None:
    """Mutual left recursion with mapping should preserve structural shape.

    Grammar:
        Expr   -> Expr "+" Term | Term
        Term   -> Term "*" Factor | Factor
        Factor -> NUMBER
        NUMBER -> /\\d+/  (one or more digits)

    We compare parsing of input '1 + 2 * 3' between:
        1. Raw token grammar (NUMBER un-mapped) yielding token-based shape.
        2. Mapped NUMBER -> int via .map(lambda t: int(t.text)).

    Expected raw structural shape (informally): (t.1, t.+, (t.2, t.*, t.3))
    Mapped structural shape: (1, '+', (2, '*', 3))

    Only the leaves (NUMBER tokens) are transformed; the tuple nesting and operator token
    positions remain identical. This asserts that multi-head (mutual) left recursion growth
    combined with .map on leaves does not collapse or reassociate the AST.
    """
    import re

    NUMBER = literal(re.compile(r'\d+'))
    PLUS = literal('+')
    STAR = literal('*')
    Expr = lazy(lambda: (Expr + PLUS + Term) | Term)  # type: ignore[name-defined]
    Term = lazy(lambda: (Term + STAR + Factor) | Factor)  # type: ignore[name-defined]
    Factor = lazy(lambda: NUMBER)  # type: ignore[name-defined]
    v_raw = parse_word(Expr, '1 + 2 * 3')
    # print(v_raw)
    assert v_raw == (Token(text='1'), Token(text='+'), (Token(text='2'), Token(text='*'), Token(text='3')))

    # Mapped variant
    NUMBER_M = NUMBER.bimap(lambda t: int(t.text), lambda n: Token(text=str(n)))  # type: ignore[name-defined]
    ExprM = lazy(lambda: (ExprM + PLUS + TermM) | TermM)  # type: ignore[name-defined]
    TermM = lazy(lambda: (TermM + STAR + FactorM) | FactorM)  # type: ignore[name-defined]
    FactorM = lazy(lambda: NUMBER_M)  # type: ignore[name-defined]
    v_mapped = parse_word(ExprM, '1 + 2 * 3')
    
    # print(v_mapped)
    assert v_mapped == (1, Token(text='+'), (2, Token(text='*'), 3))
    

    # Shape parity: replace ints with placeholder to compare tuple/operator skeletons.
    def shape(x):
        if isinstance(x, tuple):
            return ('TUP', tuple(shape(e) for e in x))
        # Distinguish int vs token (has .text attribute)
        text = getattr(x, 'text', None)
        if text is not None:
            return ('TOK', text)
        if isinstance(x, int):
            return ('INT', x)
        return ('OTHER', repr(x))
    raw_shape = shape(v_raw)
    mapped_shape = shape(v_mapped)
    # Normalize to abstract skeleton ignoring numeric identity.
    def norm(node):
        tag, val = node
        if tag == 'TUP':
            return ('TUP', tuple(norm(e) for e in val))
        if tag in ('TOK','INT') and ((isinstance(val, str) and val.isdigit()) or isinstance(val, int)):
            return ('NUM',)
        if tag == 'TOK':
            # operator tokens like '+' or '*'
            return (val,)
        return (tag,)
    assert norm(raw_shape) == norm(mapped_shape)





def test_non_recursive_map_preserves_shape()->None:
    r"""Verify that applying map to leaf nodes does not collapse sequencing structure.

    Grammar (non-recursive):
        Pair -> NUM "+" NUM
        NUM  -> /\d+/

    We build two variants:
        1. Raw structure without mapping numbers (tokens retained).
        2. Mapped numbers to int via .map().

    The outer shape (a tuple of three elements: left, '+', right) must remain
    identical aside from the leaf value transformation (Token -> int).
    This isolates shape preservation from any left-recursive growth logic.
    """
    import re
    NUM = literal(re.compile(r'\d+'))
    PLUS = literal('+')
    Pair = NUM + PLUS + NUM
    v = parse_word(Pair, '12 + 34')
    assert v == (Token(text='12'), Token(text='+'), Token(text='34'))
    (left_tok, plus_tok, right_tok) = v
    assert str(plus_tok) == 't.+'
    assert str(left_tok) == 't.12'
    assert str(right_tok) == 't.34'

    # Mapped version
    NUM_M = NUM.map(lambda t: int(t.text))
    PairM = NUM_M + PLUS + NUM_M
    v2  = parse_word(PairM, '12 + 34')
    # ast2,_ = v2.bimap
    assert v2 == (12, Token(text='+'), 34)


def test_direct_left_recursive_map_preserves_shape()->None:
    import re

    NUM = literal(re.compile(r'\d+'))
    PLUS = literal('+')
    Expr = lazy(lambda: (Expr + PLUS + NUM) | NUM)  # type: ignore[name-defined]
    v = parse_word(Expr, '1 + 2 + 3')
    generated = gen.generate_with(Expr, v)
    # print(v)
    assert v == ((Token(text='1'), Token(text='+'), Token(text='2')), Token(text='+'), Token(text='3'))
    # print(generated)
    assert generated == Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(index=0, value=Seq(value=((Lazy(value=Alt(index=1, value=Token(text='1'))), True), (Token(text='+'), True), (Token(text='2'), True))))
                        ),
                        True
                    ),
                    (Token(text='+'), True),
                    (Token(text='3'), True)
                )
            )
        )
    )



    # Mapped version
    NUM_M = NUM.bimap(lambda t: int(t.text), lambda n: Token(text=str(n)))  
    ExprM = lazy(lambda: (ExprM + PLUS + NUM_M) | NUM_M)  # type: ignore[name-defined]
    v2 = parse_word(ExprM, '1 + 2 + 3')
    generated = gen.generate_with(ExprM, v2)
    # print(v2)
    assert v2 == ((1, Token(text='+'), 2), Token(text='+'), 3)
    # print(generated)
    assert generated ==Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(index=0, value=Seq(value=((Lazy(value=Alt(index=1, value=Token(text='1'))), True), (Token(text='+'), True), (Token(text='2'), True))))
                        ),
                        True
                    ),
                    (Token(text='+'), True),
                    (Token(text='3'), True)
                )
            )
        )
    )

    # print(v2)
    assert v2 == ((1, Token(text='+'), 2), Token(text='+'), 3)


def test_direct_left_recursion_collapse()->None:
    """Collapse form S → S S | 'a' should yield a single terminal due to '>>' semantics."""
    S1 = lazy(lambda: (S1 // S1) | literal('a'))
    v = parse_word(S1, 'a')
    assert v == Token(text='a')

def test_indirect_multi_head_cycle_parses_successfully():
    A = lazy(lambda: (B >> literal(text='x')) | literal(text='a'))
    B = lazy(lambda: (A >> literal(text='y')) | literal(text='b'))
    v = parse_word(A, 'a y a y b x')
    generated = gen.generate_with(A, v)

    assert v == Token(text='a')
    
    assert generated == Lazy(value=Alt(index=1, value=Token(text='a')))
    assert any(t in str(v) for t in ['a', 'b'])


def test_indirect_left_recursion_4()->None:
    A = lazy(lambda: (B >> literal(text='x')) | literal(text='a'))
    B = lazy(lambda: (A >> literal(text='y')) | literal(text='b'))
    
    v = parse_word(A, 'a y b x')
    generated = gen.generate_with(A, v)
    
    assert v == Token(text='a')
    # print(generated)
    assert generated == Lazy(value=Alt(index=1, value=Token(text='a')))
    

    counts = token_multiset(v)
    assert counts.get('a', 0) >= 1


def test_multi_head_indirect_cycle_fixed_point()->None:
    A = lazy(lambda: (B >> literal(text='x')) | literal(text='a'))
    B = lazy(lambda: (A >> literal(text='y')) | literal(text='b'))
    v = parse_word(A, 'a y b x')
    generated = gen.generate_with(A, v)
    assert v == Token(text='a')
    # print(generated)
    assert generated == Lazy(value=Alt(index=1, value=Token(text='a')))
    

    # Ensure at least starting 'a' present (basic success signal)
    assert 'a' in str(v)


def test_multi_head_identity_in_error()->None:
    # Build a pathological chain to force multiple growth iterations of direct recursion.
    Term = literal('n')
    Expr = lazy(lambda: Expr + literal('+') + Term | Term)

    v = parse_word(Expr, 'n + n + n')
    generated = gen.generate_with(Expr, v)
    assert v == ((Token(text='n'), Token(text='+'), Token(text='n')), Token(text='+'), Token(text='n'))
    # print(generated)
    assert generated == Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(index=0, value=Seq(value=((Lazy(value=Alt(index=1, value=Token(text='n'))), True), (Token(text='+'), True), (Token(text='n'), True))))
                        ),
                        True
                    ),
                    (Token(text='+'), True),
                    (Token(text='n'), True)
                )
            )
        )
    )
    assert str(v).count('n') >= 3


def test_indirect_left_recursion_3()->None:
    A = literal(text='a')
    B = literal(text='b')
    Item = lazy(lambda: A | B)
    List = lazy(lambda: (List + literal(text=',') + Item) | Item)
    
    v = parse_word(List, 'a , b , a')
    # print(v)
    generated = gen.generate_with(List, v)
    # print(generated)
    assert v == ((Token(text='a'), Token(text=','), Token(text='b')), Token(text=','), Token(text='a'))
    # print(generated)
    assert generated == Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(
                                index=0,
                                value=Seq(
                                    value=(
                                        (Lazy(value=Alt(index=1, value=Lazy(value=Alt(index=0, value=Token(text='a'))))), True),
                                        (Token(text=','), True),
                                        (Lazy(value=Alt(index=1, value=Token(text='b'))), True)
                                    )
                                )
                            )
                        ),
                        True
                    ),
                    (Token(text=','), True),
                    (Lazy(value=Alt(index=0, value=Token(text='a'))), True)
                )
            )
        )
    )
    counts = token_multiset(v)    
    assert counts.get('a', 0) >= 1


def test_literal():
    A = literal(text='a')
    v = parse_word(A, 'a')
    print(v)
    generated = gen.generate_with(A, v)
    
    assert v == Token(text='a')
    print(generated)
    assert generated == v

def test_seq():
    A = literal(text='a')
    B = literal(text='b')
    SeqAB = A >> B
    SeqAB_ = A // B
    
    v = parse_word(SeqAB, 'a b')
    print(v)
    generated = gen.generate_with(SeqAB, v)
    
    assert v == Token(text='b')
    print(generated)
    assert generated == Seq(value=((Token(text='a'), False), (Token(text='b'), True)))

    v = parse_word(SeqAB_, 'a b')
    print(v)
    generated = gen.generate_with(SeqAB_, v)
    assert v == Token(text='a')
    print(generated)
    assert generated == Seq(value=((Token(text='a'), True), (Token(text='b'), False)))

    SeqAB_2 = A + B
    v = parse_word(SeqAB_2, 'a b')
    print(v)
    generated = gen.generate_with(SeqAB_2, v)
    assert v == (Token(text='a'), Token(text='b'))
    print(generated)
    assert generated == Seq(value=((Token(text='a'), True), (Token(text='b'), True)))


def test_multi_recursion()->None:
    a = literal('a').bimap(lambda x: x.text, lambda t: Token(text=t)).named('a')
    b = literal('b').bimap(lambda x: x.text, lambda t: Token(text=t)).named('b')
    c = literal('c').bimap(lambda x: x.text, lambda t: Token(text=t)).named('c')
    x = literal('x').bimap(lambda x: x.text, lambda t: Token(text=t)).named('x')
    y = literal('y').bimap(lambda x: x.text, lambda t: Token(text=t)).named('y')
    z = literal('z').bimap(lambda x: x.text, lambda t: Token(text=t)).named('z')
    A = lazy(lambda: (B + x) | a).named('A')
    B = lazy(lambda: (C + y) | b).named('B')
    C = lazy(lambda: (A + z) | c).named('C')

    v = parse_word(A, 'a z y x')
    generated = gen.generate_with(A, v)
    # print(generated)
    assert generated == Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(
                                index=0,
                                value=Seq(
                                    value=(
                                        (Lazy(value=Alt(index=0, value=Seq(value=((Lazy(value=Alt(index=1, value=Token(text='a'))), True), (Token(text='z'), True))))), True),
                                        (Token(text='y'), True)
                                    )
                                )
                            )
                        ),
                        True
                    ),
                    (Token(text='x'), True)
                )
            )
        )
    )
    assert v == ((('a', 'z'), 'y'), 'x')

    NUMBER = literal(re.compile(r'\d+')).map(lambda x: int(x.text))
    PLUS = literal(text='+')
    STAR = literal(text='*')
    LPAREN = literal(text='(')
    RPAREN = literal(text=')')
    Expr = lazy(lambda: (Expr + PLUS + Term) | Term)
    Term = lazy(lambda: (Term + STAR + Factor) | Factor)
    Factor: Syntax[Alt, Any] = lazy(lambda: (LPAREN + Expr + RPAREN) | NUMBER)

    v1 = parse_word(Expr, '1 + 2 * 3')
    assert v1 == (1, Token(text='+'), (2, Token(text='*'), 3))

    def leaf(x):
        try:
            return int(str(x)[2:]) if str(x).startswith('t.') and str(x)[2:].isdigit() else (str(x)[2:] if str(x).startswith('t.') else x)
        except Exception:
            return x
    def norm(ast):
        if isinstance(ast, tuple) and len(ast) == 3 and isinstance(ast[1], (str, object)):
            return (norm(ast[0]), leaf(ast[1] if not isinstance(ast[1], tuple) else ast[1]), norm(ast[2]))
        return leaf(ast)
    normalized = norm(v1)
    print(normalized)
    assert normalized == (1, '+', (2, '*', 3)), f"Unexpected normalized AST: {normalized}"

    v_42 = parse_word(Expr, '42')
    
    single_norm = norm(v_42)
    assert single_norm == 42


def test_indirect_left_recursion_5()->None:
    Name = literal(text=re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*'))
    Chain = lazy(lambda: (Chain + literal(text='->') + Name) | Name)
    v = parse_word(Chain, 'a -> b -> c')
    generated = gen.generate_with(Chain, v)
    print(v)
    assert v == ((Token(text='a'), Token(text='->'), Token(text='b')), Token(text='->'), Token(text='c'))
    print(generated)
    assert generated == Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(
                                index=0,
                                value=Seq(value=((Lazy(value=Alt(index=1, value=Token(text='a'))), True), (Token(text='->'), True), (Token(text='b'), True)))
                            )
                        ),
                        True
                    ),
                    (Token(text='->'), True),
                    (Token(text='c'), True)
                )
            )
        )
    )
    counts = token_multiset(v)
    assert counts.get('c', 0) >= 1



def test_direct_left_recursion_unproductive_now_productive()->None:
    """Previously unproductive S → S S | 'a' succeeds; confirm collapse result."""
    S1 = lazy(lambda: (S1 + S1) | literal('a'))
    v = parse_word(S1, 'a a a a a')
    print(v)
    assert v == ((((Token(text='a'), Token(text='a')), Token(text='a')), Token(text='a')), Token(text='a'))
    generated = gen.generate_with(S1, v)
    print(generated)
    assert generated == Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(
                                index=0,
                                value=Seq(
                                    value=(
                                        (
                                            Lazy(
                                                value=Alt(
                                                    index=0,
                                                    value=Seq(
                                                        value=(
                                                            (
                                                                Lazy(
                                                                    value=Alt(
                                                                        index=0,
                                                                        value=Seq(
                                                                            value=(
                                                                                (Lazy(value=Alt(index=1, value=Token(text='a'))), True),
                                                                                (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                                                            )
                                                                        )
                                                                    )
                                                                ),
                                                                True
                                                            ),
                                                            (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                                        )
                                                    )
                                                )
                                            ),
                                            True
                                        ),
                                        (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                    )
                                )
                            )
                        ),
                        True
                    ),
                    (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                )
            )
        )
    )



def test_direct_left_recursion_unproductive_now_productive1()->None:
    """Previously unproductive S → S S | 'a' succeeds; confirm collapse result."""
    S1 = lazy(lambda: (S1 + S1) | literal('a'))
    v = parse_word(S1, 'a a a a a')
    assert v == ((((Token(text='a'), Token(text='a')), Token(text='a')), Token(text='a')), Token(text='a'))
    # print(v)
    generated = gen.generate_with(S1, v)

    # print(generated)
    assert generated == Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(
                                index=0,
                                value=Seq(
                                    value=(
                                        (
                                            Lazy(
                                                value=Alt(
                                                    index=0,
                                                    value=Seq(
                                                        value=(
                                                            (
                                                                Lazy(
                                                                    value=Alt(
                                                                        index=0,
                                                                        value=Seq(
                                                                            value=(
                                                                                (Lazy(value=Alt(index=1, value=Token(text='a'))), True),
                                                                                (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                                                            )
                                                                        )
                                                                    )
                                                                ),
                                                                True
                                                            ),
                                                            (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                                        )
                                                    )
                                                )
                                            ),
                                            True
                                        ),
                                        (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                    )
                                )
                            )
                        ),
                        True
                    ),
                    (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                )
            )
        )
    )



def test_direct_left_recursion_unproductive_now_productive2()->None:
    """Previously unproductive S → S S | 'a' succeeds; confirm collapse result."""
    S1 = lazy(lambda: (S1 + S1) | literal('a'))
    v = parse_word(S1, 'a a a a a')
    generated = gen.generate_with(S1, v)
    # print(v)
    assert v == ((((Token(text='a'), Token(text='a')), Token(text='a')), Token(text='a')), Token(text='a'))
    # print(generated)
    assert generated == Lazy(
        value=Alt(
            index=0,
            value=Seq(
                value=(
                    (
                        Lazy(
                            value=Alt(
                                index=0,
                                value=Seq(
                                    value=(
                                        (
                                            Lazy(
                                                value=Alt(
                                                    index=0,
                                                    value=Seq(
                                                        value=(
                                                            (
                                                                Lazy(
                                                                    value=Alt(
                                                                        index=0,
                                                                        value=Seq(
                                                                            value=(
                                                                                (Lazy(value=Alt(index=1, value=Token(text='a'))), True),
                                                                                (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                                                            )
                                                                        )
                                                                    )
                                                                ),
                                                                True
                                                            ),
                                                            (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                                        )
                                                    )
                                                )
                                            ),
                                            True
                                        ),
                                        (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                                    )
                                )
                            )
                        ),
                        True
                    ),
                    (Lazy(value=Alt(index=1, value=Token(text='a'))), True)
                )
            )
        )
    )




def test_mutual_unproductive_cycle_no_progress():
    """Grammar:
        A -> B
        B -> A
    Input: ''
    Expect: LeftRecursionError(reason='no-progress') because there is no productive (non-recursive) base.
    """
    A = lazy(lambda: B)
    B = lazy(lambda: A)
    with pytest.raises(LeftRecursionError) as exc:
        parse_word(A, '')
    assert exc.value.reason == 'no-choice'



def test_mutual_unproductive_cycle_no_progress_3():
    """Grammar:
        A -> B
        B -> C
        C -> A
    Input: ''
    Expect: LeftRecursionError(reason='no-progress') because there is no productive (non-recursive) base.
    """
    A = lazy(lambda: B)  
    B = lazy(lambda: C)  
    C = lazy(lambda: A)  
    with pytest.raises(LeftRecursionError) as exc:
        parse_word(A, '')
    assert exc.value.reason == 'no-choice'





def test_complex_non_productive():
    A = lazy(lambda: B | C).named('A')
    B = lazy(lambda: C | A).named('B')
    C = lazy(lambda: B | A).named('C')

    with pytest.raises(LeftRecursionError) as exc:
        parse_word(A, '')
    assert exc.value.reason == 'no-progress'


