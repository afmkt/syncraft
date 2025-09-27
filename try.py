import pytest

from syncraft.syntax import Syntax
from syncraft.ast import TokenClass, Token, Then, ThenKind, Choice, ChoiceKind, Lazy
from syncraft.generator import generate_with, generate, validate
from syncraft.algebra import Error
from syncraft.cache import LeftRecursionError
from rich import print


def tok(text: str):
    return Syntax.token(token_class=TokenClass.simple(), text=text, case_sensitive=True)

def test()->None:
    RA = Syntax.lazy(lambda: A + tok("a")).named("A")
    A = Syntax.lazy(lambda: B + tok("a")).named("A")
    B = Syntax.lazy(lambda: A + tok("b")).named("B")
    print(RA.spec.spec())

if __name__ == "__main__":
    
    
    test()