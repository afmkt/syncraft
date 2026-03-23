from syncraft.syntax import Syntax



from syncraft.algebra import Error

from syncraft.generator import validate, generate_with
from syncraft.token import Str, Token

def parse_word(syntax: Syntax, data: str):
    from syncraft.token import Token
    from typing import List
    import re
    from syncraft.parser import parse_data
    tokens: List[Token]  = [Token(text=t) for t in re.split(r'[\x00-\x1F\x7F\s]+', data)]
    return parse_data(syntax, tokens)


S = Syntax
def tok(text: str):
    return S.tok(Token(text=Str(text, i=True)))


def test_validate_and_generate_with_after_bimap_resets_choice_kind():
    A = S.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast = parse_word(A, 'a a a')
    assert not isinstance(ast, Error)
    v1 = validate(A, ast)
    assert not isinstance(v1, Error)
    v2 = generate_with(A, ast)
    assert not isinstance(v2, Error)
    


# @pytest.mark.xfail(reason="Mutual LR with OrElse.kind=None after bimap is ambiguous without explicit branch tags; validation requires a hint (set kind) or disambiguation.")
def test_mutual_left_recursion_with_base_after_bimap_A():
    A = S.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = S.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]
    ast = parse_word(A, 'a b a')
    assert not isinstance(ast, Error)
    v1 = validate(A, ast)
    assert not isinstance(v1, Error)
    
    v2 = generate_with(A, ast)
    assert not isinstance(v2, Error)
    


# @pytest.mark.xfail(reason="Mutual LR with OrElse.kind=None after bimap is ambiguous without explicit branch tags; validation requires a hint (set kind) or disambiguation.")
def test_mutual_left_recursion_with_base_after_bimap_B():
    A = S.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = S.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]
    ast = parse_word(B, 'b a b')
    assert not isinstance(ast, Error)
    v1 = validate(B, ast)
    assert not isinstance(v1, Error)
    
    v2 = generate_with(B, ast)
    assert not isinstance(v2, Error)
    
