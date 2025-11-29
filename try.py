from __future__ import annotations

from rich import print
from pyDatalog import pyDatalog as d
from syncraft.syntax import Syntax as S
from syncraft.fa import Builder as B
from syncraft.algebra import Error
# 
import timeit
from syncraft.algebra import Left, Right
from syncraft.ast import Token
from syncraft.lexer import Lexer, LexerResult
from syncraft.syntax import Syntax
from syncraft.regex import benchmark_fair
from syncraft.grammar import Grammar, lazy, rule, AUTUO_NAME


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
        

def main():
    from syncraft.regex import Regex, parse_regex, group, regex, rparen, lparen, name, greater, regex_full, inline_flags, colon, GroupAtom, GroupKind, benchmark_fair
    pattern = [
        r'(?r)$|\W{4,}.+\U000FEAE1?u*',
        r'4{1}|e*\b(?0)[FyIn]{4,}',
        r'\U000A231E[^OtVLo]*N{2,5}|T\u966F*.{0,3}.{5}|^\B(?R)',
        r'\U000D6EAF.{2,6}(?r)\U0007CA66*',
        r'.{1}\u2B7B?[ivMe]|(?r)|[rqp\w]{2}[^HqbqM]{0,5}\D{4,}L{2,3}',
        r'(?p)\W^|r?u{2,6}',
        r'(?f)',
        r'(?b)',
    ]
    print(parse_regex(regex_full, pattern[0]))
    print(parse_regex(regex_full, pattern[1]))
    print(parse_regex(regex_full, pattern[2]))
    print(parse_regex(regex_full, pattern[3]))
    print(parse_regex(regex_full, pattern[4]))
    print(parse_regex(regex_full, pattern[5]))
    print(str(parse_regex(group, pattern[6])))
    print(str(parse_regex(group, pattern[7])))



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
    # test()
    # test1_simple_then()
    # main()


    
    class G(Grammar, builtin=True, max_name_length=10):
        a = rule(Grammar.lit(text="a"))
        b = rule(Grammar.lit(text="b"), "B")
        @lazy(False)
        def c(cls):
            return cls.f.optional
        f = rule(a >> b)
    

    print(str(G.a), G.a.location)
    print(str(G.b), G.b.location)
    print(str(G.c), G.c.location)
    print(str(G.f), G.f.location)

