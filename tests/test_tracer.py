from __future__ import annotations

from syncraft.regex import RE
from syncraft.tracer import Tracer
from syncraft.cache import Cache

def test_tracer():
    pattern = r'\U000A231E[^OtVLo]*N{2,5}|T\u966F*.{0,3}.{5}|^\B(?R)'
    with Tracer() as tracer:
        RE.parse(pattern, cache = Cache().with_tracer(tracer))

    
        
    

