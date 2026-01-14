from syncraft.syntax import Syntax

from syncraft.parser import parse_word
from syncraft.generator import validate, generate_with
from syncraft.algebra import Error
from syncraft.cache import Cache
S = Syntax
def tok(text: str):
    return S.lit(text=text, case_sensitive=True)


def test_validate_and_generate_with_after_bimap_resets_choice_kind():
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast, _ = parse_word(A, 'a a a', cache=Cache())
    assert not isinstance(ast, Error)
    v1, b1 = validate(A, ast)
    assert not isinstance(v1, Error)
    assert b1 is not None
    v2, b2 = generate_with(A, ast)
    assert not isinstance(v2, Error)
    assert b2 is not None


# @pytest.mark.xfail(reason="Mutual LR with OrElse.kind=None after bimap is ambiguous without explicit branch tags; validation requires a hint (set kind) or disambiguation.")
def test_mutual_left_recursion_with_base_after_bimap_A():
    A = S.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = S.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]
    ast, _ = parse_word(A, 'a b a', cache=Cache())
    assert not isinstance(ast, Error)
    v1, b1 = validate(A, ast)
    assert not isinstance(v1, Error)
    assert b1 is not None
    v2, b2 = generate_with(A, ast)
    assert not isinstance(v2, Error)
    assert b2 is not None


# @pytest.mark.xfail(reason="Mutual LR with OrElse.kind=None after bimap is ambiguous without explicit branch tags; validation requires a hint (set kind) or disambiguation.")
def test_mutual_left_recursion_with_base_after_bimap_B():
    A = S.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = S.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]
    ast, _ = parse_word(B, 'b a b', cache=Cache())
    assert not isinstance(ast, Error)
    v1, b1 = validate(B, ast)
    assert not isinstance(v1, Error)
    assert b1 is not None
    v2, b2 = generate_with(B, ast)
    assert not isinstance(v2, Error)
    assert b2 is not None
