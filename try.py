from __future__ import annotations

# from rich import print
from pyDatalog import pyDatalog as d
from syncraft.regex import (
    parse_regex, parse, RE, parse_regex,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)

from syncraft.tracer import Tracer
from syncraft.cache import Cache

from rich import print

import timeit



def benchmark_fair():
    from syncraft.regex import parse as parse3
    count = 500
    result = []
    base_patterns = [
        r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        r'(?r)$|\W{4,}.+\U000FEAE1?u*',
        r'4{1}|e*\b(?0)[FyIn]{4,}',
        r'\U000A231E[^OtVLo]*N{2,5}|T\u966F*.{0,3}.{5}|^\B(?R)',
        r'\U000D6EAF.{2,6}(?r)\U0007CA66*',
        r'.{1}\u2B7B?[ivMe]|(?r)|[rqp\w]{2}[^HqbqM]{0,5}\D{4,}L{2,3}',
        r'(?p)\W^|r?u{2,6}',
        r'(?f)',
        r'(?b)',
        r'(?r)$|\W{4,}.+\U000FEAE1?u*',
        r'4{1}|e*\b(?0)[FyIn]{4,}',
        r'\U000A231E[^OtVLo]*N{2,5}|T\u966F*.{0,3}.{5}|^\B(?R)',
        r'\U000D6EAF.{2,6}(?r)\U0007CA66*',
        r'.{1}\u2B7B?[ivMe]|(?r)|[rqp\w]{2}[^HqbqM]{0,5}\D{4,}L{2,3}',

    ]
    t = 0
    t3 = 0
    for base_pattern in base_patterns:
        def run3():
            try:
                parse3(base_pattern, raw=False) 
            except StopIteration:
                pass


        def run():
            try:
                parse(base_pattern, raw=False) 
            except StopIteration:
                pass


        t += timeit.timeit(run3, number=count)
        t3 += timeit.timeit(run, number=count)

    result.append("--- FAIR COMPARISON (Cold Start) ---")
    
    result.append(f"Regex: {t/count:.5f} s/parse")
    result.append(f"Regex3:    {t3/count:.5f} s/parse")
    
    ratio = (t) / (t3)
    result.append(f"Multiplier: Syncraft is {ratio:.5f}x slower than C-compiled Regex")
    return result



def test_tracer():

    pattern = r'\U000A231E[^OtVLo]*N{2,5}|T\u966F*.{0,3}.{5}|^\B(?R)'
    with Tracer() as tracer:
        RE.parse(pattern, raw=False, cache = Cache().with_tracer(tracer))
        # print(tracer.tree())
        
    



if __name__ == "__main__":
    test_tracer()
    

