from __future__ import annotations

from syncraft.syntax import Syntax as S














if __name__ == "__main__":
    from syncraft.ebnf import EBNF, Lit
    from syncraft.ebnf import Repeat
    # Test factor rule
    result = EBNF.parse("'a'?", syntax=EBNF.factor)
    
    assert isinstance(result, Repeat)
    assert result.expr == Lit('a')
    assert result.minimum == 0
    assert result.maximum == 1
    
    # Test suffix rule
    result = EBNF.parse("?", syntax=EBNF.suffix)
    assert result == (0,1)
    
    result = EBNF.parse("{2,5}", syntax=EBNF.suffix)
    assert result == (2,5)

    result = EBNF.parse("{2,}", syntax=EBNF.suffix)
    print(result)
    assert result == (2,None)

    result = EBNF.parse("{2}", syntax=EBNF.suffix)
    print(result)
    assert result == (2,None)
