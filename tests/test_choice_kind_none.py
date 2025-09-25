import pytest
from syncraft.syntax import Syntax
from syncraft.ast import TokenClass
from syncraft.parser import parse_word
from syncraft.generator import validate, generate_with
from syncraft.algebra import Error


def tok(text: str):
    return Syntax.token(token_class=TokenClass.simple(), text=text, case_sensitive=True)


def test_validate_and_generate_with_after_bimap_resets_choice_kind():
    # Grammar: A := (A + 'a') | 'a'
    A = Syntax.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]

    # Parse concrete input "a a a"
    ast, _ = parse_word(A, 'a a a')
    assert not isinstance(ast, Error)

    # Apply bimap then reconstruct the AST. Choice.bimap resets kind to None.
    x, invf = ast.bimap()  # x is a flattened tuple-like view; invf reconstructs AST with kind=None in Choice nodes
    reconstructed = invf(x)

    # validate() should succeed even when Choice.kind is None
    v1, b1 = validate(A, reconstructed)
    assert not isinstance(v1, Error)
    assert b1 is not None

    # generate_with() should also respect kind=None and succeed
    v2, b2 = generate_with(A, reconstructed)
    assert not isinstance(v2, Error)
    assert b2 is not None


@pytest.mark.xfail(reason="Mutual left recursion currently requires Choice.kind guidance after bimap clears kinds.")
def test_mutual_left_recursion_with_base_after_bimap_A():
    # Grammar: A := (A + 'b') | 'a'  and  B := (B + 'a') | 'b' would not alternate as intended.
    # Use standard mutual LR with base on each:
    #   A := (B + 'a') | 'a'
    #   B := (A + 'b') | 'b'
    A = Syntax.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = Syntax.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]

    # Parse a sequence that fits A: 'a b a' via A -> B + 'a', B -> A + 'b', A -> 'a'
    ast, _ = parse_word(A, 'a b a')
    assert not isinstance(ast, Error)

    x, invf = ast.bimap()
    reconstructed = invf(x)

    v1, b1 = validate(A, reconstructed)
    assert not isinstance(v1, Error)
    assert b1 is not None

    v2, b2 = generate_with(A, reconstructed)
    assert not isinstance(v2, Error)
    assert b2 is not None


@pytest.mark.xfail(reason="Mutual left recursion currently requires Choice.kind guidance after bimap clears kinds.")
def test_mutual_left_recursion_with_base_after_bimap_B():
    # Same grammar, start from B and parse 'b a b': B -> A + 'b', A -> B + 'a', B -> 'b'
    A = Syntax.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = Syntax.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]

    ast, _ = parse_word(B, 'b a b')
    assert not isinstance(ast, Error)

    x, invf = ast.bimap()
    reconstructed = invf(x)

    v1, b1 = validate(B, reconstructed)
    assert not isinstance(v1, Error)
    assert b1 is not None

    v2, b2 = generate_with(B, reconstructed)
    assert not isinstance(v2, Error)
    assert b2 is not None
