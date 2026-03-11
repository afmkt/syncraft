from syncraft.syntax import Syntax
from syncraft.ast import Token
from syncraft.generator import (
    generate_with,
    generate,

)
from syncraft.algebra import Error

SS = Syntax.set(terminal_constructor=lambda value, tag: Token(**value))


def tok(text: str):
    return SS.tok(text=text, case_sensitive=True)


    


def test_generate_direct_left_recursion_with_base_succeeds():
    A = SS.lazy(lambda: (A + tok('a')) | tok('a'))  # type: ignore[name-defined]
    ast = generate(A)
    assert not isinstance(ast, Error)
    




if __name__ == "__main__":
    
    test_generate_direct_left_recursion_with_base_succeeds()
