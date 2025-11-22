from __future__ import annotations
from syncraft.regex import parse, parse_regex, group, regex, lparen, rparen, name, greater, inline_flags, colon
from rich import print
import timeit
from syncraft.regex import benchmark_fair, verify
from syncraft.syntax import Syntax as S
from syncraft.fa import Builder as B
plain = regex.mark('pattern').between(lparen, rparen)
noncapturing = S.seq(S.lex(_=B.lit("(?:")).named('"(?:"'), +regex.mark('pattern').debug(disable=True), rparen)
named = S.seq(S.lex(gp_named=B.lit("(?P<")).named('"(?P<"'), +name.mark('name'), greater, +regex.mark('pattern'), rparen)
negative_lookahead = S.seq(S.lex(gp_negative_lookahead=B.lit("(?!")).named('"(?!"'), +regex.mark('pattern'), rparen)

def test_neg_lookahead():
    nl = r"(?!\1)"
    ret = parse_regex(negative_lookahead, nl, raw=False)
    print(str(ret))

def test_noncap():
    pattern = r"""(?:(?P<quote>['\"])(?:(?!\1).)*\1)"""
    
    noncap = r"""(?:['\"])"""
    ret = parse_regex(noncapturing, noncap, raw = False)
    print(str(ret))

def test_named():
    name = r"""(?P<quote>['\"])"""
    ret = parse_regex(named, name, raw = False)
    print(str(ret))


def x():
    size = 1000
    intdict = {k: str(k) for k in range(size)}
    tupledict= {(k, k): str(k) for k in range(size)}

    t1 = timeit.timeit(lambda: all([i in intdict for i in range(size)]), number=10000)
    t2 = timeit.timeit(lambda: all([(i, i) in tupledict for i in range(size)]), number=10000)

    print("int key", t1)
    print('tuple key', t2)
    print('int / tuple', float(t1) / t2)
    

if __name__ == "__main__":
    test_neg_lookahead()
    # x()
    # r = benchmark_fair()
    # for line in r:
    #     print(line)
