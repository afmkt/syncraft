from __future__ import annotations

from rich import print
from pyDatalog import pyDatalog as d
from syncraft.syntax import Syntax as S
from syncraft.fa import Builder as B
from syncraft.algebra import Error
# 
import timeit

from syncraft.ast import Then, ThenKind, Many, OrElse, OrElseKind, Token, Marked, Nothing, Any
from syncraft.algebra import Error
from syncraft.parser import  parse_word
import syncraft.generator as gen
from syncraft.syntax import Syntax
from syncraft.cache import Cache




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
    from syncraft.regex import Regex, parse_regex, regex, rparen, lparen, name, greater, regex_full, inline_flags, colon, GroupAtom, GroupKind, benchmark_fair
    pattern = [
        r'(?r)$|\W{4,}.+\U000FEAE1?u*',
        r'4{1}|e*\b(?0)[FyIn]{4,}',
        r'\U000A231E[^OtVLo]*N{2,5}|T\u966F*.{0,3}.{5}|^\B(?R)',
        r'\U000D6EAF.{2,6}(?r)\U0007CA66*',
        r'.{1}\u2B7B?[ivMe]|(?r)|[rqp\w]{2}[^HqbqM]{0,5}\D{4,}L{2,3}',
        r'(?p)\W^|r?u{2,6}',
    ]
    print(parse_regex(regex_full, pattern[0]))
    print(parse_regex(regex_full, pattern[1]))
    print(parse_regex(regex_full, pattern[2]))
    print(parse_regex(regex_full, pattern[3]))
    print(parse_regex(regex_full, pattern[4]))
    print(parse_regex(regex_full, pattern[5]))


def test():
    from syncraft.regex import Regex, parse_regex, regex, rparen, lparen, name, greater, regex_full, inline_flags, colon, GroupAtom, GroupKind, benchmark_fair
    negative_lookahead = S.lex(gp_negative_lookahead=B.lit("(?!"))
    nl = r"(?!\1)"
    ret = parse_regex(negative_lookahead, nl, raw=False)
    assert not isinstance(ret, Error)



literal = Syntax.lit

def from_string(string: str) -> Token:
    return Token(text=string)

def test1_simple_then() -> None:
    A, B, C = literal("a"), literal("b"), literal("c")
    syntax = A // B // C
    sql = "a b c"
    ast, bound = parse_word(syntax, sql, cache=Cache())
    # print("---" * 40)
    print(ast)
    generated, bound = gen.generate_with(syntax, ast)
    # print("---" * 40)
    print(generated)
    assert ast == generated
    value, bmap = generated.bimap
    # print(value)
    u, v = gen.generate_with(syntax, bmap(value))
    assert u == generated



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
    test1_simple_then()
    # main()