from __future__ import annotations
from syncraft.syntax import Syntax
from rich import print

def test_recursion() -> None:
    literal = Syntax.literal
    A = literal('a')
    B = literal('b')
    L = Syntax.lazy(lambda: literal("if") >> (A | B) // literal('then'))

    def parens():
        return A + ~Syntax.lazy(parens) + B
    LL = parens() | L
    
    for _, node in LL.spec.walk():
        print(node)



if __name__ == "__main__":
    test_recursion()