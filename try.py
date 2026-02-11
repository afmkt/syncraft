from __future__ import annotations

from syncraft.bimap import let, Env, Scope, evaluate, Expr, Iso, Not
from dataclasses import dataclass
from typing import Any, Optional

def test_transformation()->None:
    @dataclass(frozen=True, slots=True)
    class Quantifier:
        minimum: int
        maximum: Optional[int]     # None → unbounded
        greedy: bool = True


    iso = Iso.derive(lambda env: (Quantifier(minimum=env.minimum, maximum=env.maximum), env.greedy), 
                    lambda env: Quantifier(minimum=env.minimum, maximum=env.maximum, greedy=Not(env.greedy)))

    a = (Quantifier(1, 5, True), False)
    b = iso.forward(a, None)
    assert b == Quantifier(1, 5, True)
    c = iso.inverse(b, None)
    assert c == (Quantifier(1, 5, True), False)


if __name__ == '__main__':
    test_transformation()    
    
    
    
    
    