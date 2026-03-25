

import pytest

from syncraft.syntax import Syntax

from syncraft.generator import (
    generate_with,
)
from syncraft.algebra import Error
from rich import print
SS = Syntax


def test_generate_with_direct_left_recursion_with_base_succeeds():
    # A := A + 'a' | 'a'
    a = SS.tok('a').named('a')
    A = SS.lazy(lambda: (A + a) | a).named('A')  # type: ignore[name-defined]
    print("START PARSING", '=='*80)
    P = A.parse(['a'])
    print("START GENERATING", '=='*80)
    ast = generate_with(A)
    # Should yield an AST (not Error) and produce a bindings mapping (possibly empty)
    assert not isinstance(ast, Error)
    



if __name__ == "__main__":
    test_generate_with_direct_left_recursion_with_base_succeeds()