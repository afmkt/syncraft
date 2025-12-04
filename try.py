from __future__ import annotations

# from rich import print
from pyDatalog import pyDatalog as d
from syncraft.regex import (
    parse_regex, parse, RE, parse_regex,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
from rich import print

# 
import timeit
# from syncraft.regex2 import verify

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
        



def benchmark_fair():
    # ITERATOR to feed unique patterns
    from syncraft.regex import parse as parse3
    from syncraft.regex import parse 
    import timeit
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





def test_groups_flags_with_disable():
    """Test parsing of flag groups with disabled flags."""
    # result = parse_regex(group, "(?im-s)")
    tmp = parse("(?im-s)", raw=False)
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.FLAGS
    assert result.inline_flags
    assert result.inline_flags.enabled == ("i", "m")
    assert result.inline_flags.disabled == ("s",)
    assert result.pattern is None



def test_groups_flags_only():
    """Test parsing of flag-only groups."""
    # result = parse_regex(group, "(?i)")
    tmp = parse("(?i)", raw=False)
    assert isinstance(tmp, Regex)
    result = tmp.branches[0].pieces[0].atom

    assert isinstance(result, GroupAtom)
    assert result.kind == GroupKind.FLAGS
    print(result)
    assert result.inline_flags
    assert result.inline_flags.enabled == ("i",)
    assert result.inline_flags.disabled is None
    assert result.pattern is None





if __name__ == "__main__":
    test_groups_flags_only()
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
    # test()
    # test1_simple_then()
    # main()

    # test_graph()
    

    

