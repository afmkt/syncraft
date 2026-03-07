from __future__ import annotations

from syncraft.ast import Token
from syncraft.syntax import Syntax







def test_format_nested_indentation() -> None:
    """Format: nested if statements with proper indentation."""
    S = Syntax
    r = S.rp('(A)(B)(C)').map(tuple).parse('ABC')
    print(r)







if __name__ == "__main__":

    test_format_nested_indentation()