from syncraft.syntax import Syntax

from syncraft.parser import parse_word
from syncraft.generator import validate, generate_with
from syncraft.algebra import Error
from syncraft.cache import Cache
# S = Syntax.config(lexer_class=ExtLexer.bind(tkspec=Structured(Token)))
S = Syntax
def tok(text: str):
    return S.token(text=text, case_sensitive=True)


def test_validate_and_generate_with_after_bimap_resets_choice_kind():
    # Grammar: A := (A + 'a') | 'a'
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]

    # Parse concrete input "a a a"
    ast, _ = parse_word(A, 'a a a', cache=Cache())
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


# @pytest.mark.xfail(reason="Mutual LR with Choice.kind=None after bimap is ambiguous without explicit branch tags; validation requires a hint (set kind) or disambiguation.")
def test_mutual_left_recursion_with_base_after_bimap_A():
    # Grammar: A := (A + 'b') | 'a'  and  B := (B + 'a') | 'b' would not alternate as intended.
    # Use standard mutual LR with base on each:
    #   A := (B + 'a') | 'a'
    #   B := (A + 'b') | 'b'
    A = S.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = S.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]

    # Parse a sequence that fits A: 'a b a' via A -> B + 'a', B -> A + 'b', A -> 'a'
    ast, _ = parse_word(A, 'a b a', cache=Cache())
    assert not isinstance(ast, Error)

    x, invf = ast.bimap()
    reconstructed = invf(x)

    v1, b1 = validate(A, reconstructed)
    assert not isinstance(v1, Error)
    assert b1 is not None

    v2, b2 = generate_with(A, reconstructed)
    assert not isinstance(v2, Error)
    assert b2 is not None


# @pytest.mark.xfail(reason="Mutual LR with Choice.kind=None after bimap is ambiguous without explicit branch tags; validation requires a hint (set kind) or disambiguation.")
def test_mutual_left_recursion_with_base_after_bimap_B():
    # Same grammar, start from B and parse 'b a b': B -> A + 'b', A -> B + 'a', B -> 'b'
    A = S.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = S.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]

    ast, _ = parse_word(B, 'b a b', cache=Cache())
    assert not isinstance(ast, Error)

    x, invf = ast.bimap()
    reconstructed = invf(x)

    v1, b1 = validate(B, reconstructed)
    assert not isinstance(v1, Error)
    assert b1 is not None

    v2, b2 = generate_with(B, reconstructed)
    assert not isinstance(v2, Error)
    assert b2 is not None
