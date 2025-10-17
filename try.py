import pytest
from syncraft.syntax import Syntax
from syncraft.lexer import ExtLexer
from syncraft.parser import parse_word
from syncraft.generator import validate, generate_with
from syncraft.algebra import Error
from syncraft.lexer import CacheWithLexer
from syncraft.ast import Token
S = Syntax.config(lexer_class=ExtLexer.bind(token_class=Token))
def tok(text: str):
    return S.config(lexer_class=ExtLexer.bind(token_class=Token)).token(text=text, case_sensitive=True)


def test_validate_and_generate_with_after_bimap_resets_choice_kind():
    # Grammar: A := (A + 'a') | 'a'
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]

    # Parse concrete input "a a a"
    ast, _ = parse_word(A, 'a a a', cache=CacheWithLexer())
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

if __name__ == "__main__":
    test_validate_and_generate_with_after_bimap_resets_choice_kind()