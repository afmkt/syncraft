from syncraft.syntax import Syntax

from syncraft.parser import parse_word

from syncraft.algebra import Error
from syncraft.cache import Cache
from syncraft.generator import validate, generate_with

from rich import print
S = Syntax
def tok(text: str):
    return S.tok(text=text, case_sensitive=True)


def test_validate_and_generate_with_after_bimap_resets_choice_kind():
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast = parse_word(A, 'a a a')
    print(ast)
    assert not isinstance(ast, Error)
    v1 = validate(A, ast)
    assert not isinstance(v1, Error)
    v2 = generate_with(A, ast)
    assert not isinstance(v2, Error)
    



    
if __name__ == "__main__":
    test_validate_and_generate_with_after_bimap_resets_choice_kind()
