from __future__ import annotations
from syncraft.regex import parse, parse_regex, group, regex, lparen, rparen, name, greater, inline_flags, colon
from rich import print
import timeit
from syncraft.regex import benchmark_fair, verify
from syncraft.syntax import Syntax as S
from syncraft.fa import Builder as B
plain = regex.mark('pattern').between(lparen, rparen)
noncapturing = S.seq(S.lex(_=B.lit("(?:")).named('"(?:"'), +regex.mark('pattern'), rparen)
named = S.seq(S.lex(gp_named=B.lit("(?P<")).named('"(?P<"'), +name.mark('name'), greater, +regex.mark('pattern'), rparen)
negative_lookahead = S.seq(S.lex(gp_negative_lookahead=B.lit("(?!")).named('"(?!"'), +regex.mark('pattern'), rparen)

def test_neg_lookahead():
    nl = r"(?!\1)"
    ret = parse_regex(negative_lookahead, nl, raw=False)
    print(str(ret))

def test_noncap():    
    noncap = r"(?:['\"])"
    ret = parse_regex(noncapturing, noncap, raw = False)
    print(str(ret))

def test_named():
    name = r"(?P<quote>['\"])"
    ret = parse_regex(named, name, raw = False)
    print(str(ret))

def test_all():
    pattern = r"(?:(?P<quote>['\"])(?:(?!\1).)*\1)"
    ret = parse_regex(regex, pattern, raw = False)
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
    
def y():
    class A:
        def __init__(self):
            self.id = 1

    class B:
        def __init__(self):
            self.id = 2

    a = A()
    b = B()


    t1 = timeit.timeit(lambda: isinstance(a, A) and isinstance(b, B) and (isinstance(a, B) or isinstance(b, A)), number=1000000)
    t2 = timeit.timeit(lambda: a.id==1 and b.id == 2 and (a.id == 2 or b.id == 1), number=1000000)
    print("isinstance", t1)
    print("id check", t2)
    print("id check / isinstance", float(t2) / t1)


def z():
    callable_dict = {}
    tuple_key_dict = {}
    callables = []
    tuples = []
    for i in range(1000):
        callables.append((lambda x: x + i, i))
        tuples.append((i, i))
        callable_dict[callables[-1]] = 'hello'
        tuple_key_dict[tuples[-1]] = 'hello'

    t1 = timeit.timeit(lambda: [callable_dict[tmp] for tmp in callables], number=100000)
    t2 = timeit.timeit(lambda: [tuple_key_dict[tmp] for tmp in tuples], number=100000)
    print("callable key", t1)
    print("tuple key", t2)
    print("tuple / callable", float(t2) / t1)
        

def test():
    pattern = r'l*[^UUf\w]?|\w{5}\W{0,5}\w*(?w)|J*\B'
    ret = verify(pattern)
    print(ret)
    print(str(ret.err_syncraft))


if __name__ == "__main__":
    # test_noncap()
    # test_named()
    # test_neg_lookahead()
    # test_all()
    # x()
    # y()
    # z()
    # r = benchmark_fair()
    # for line in r:
    #     print(line)
    test()