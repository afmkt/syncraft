from __future__ import annotations

from rich import print
from pyDatalog import pyDatalog as d
from syncraft.syntax import Syntax as S
from syncraft.fa import Builder as B
from syncraft.algebra import Error
from syncraft.regex import Regex, parse_regex, regex, rparen, lparen, name, greater, regex_full, inline_flags, colon, GroupAtom, GroupKind, benchmark_fair
import timeit




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
        

plain = regex.mark('pattern').between(lparen, rparen)
# group = "(?:" regex ")"
noncapturing = S.seq(S.lex(gp_noncap=B.lit("(?:")).named('"(?:"'), +regex.mark('pattern'), rparen)
# group = "(?P<" name ">" regex ")"
named = S.seq(S.lex(gp_named=B.lit("(?P<")).named('"(?P<"'), +name.mark('name'), greater, +regex.mark('pattern'), rparen)
# group = "(?=" regex ")"
lookahead = S.seq(S.lex(gp_lh=B.lit("(?=")).named('"(?="'), +regex.mark('pattern'), rparen)
# group = "(?!" regex ")"
negative_lookahead = S.seq(S.lex(gp_neglh=B.lit("(?!")).named('"(?!"'), +regex.mark('pattern'), rparen)
# group = "(?<=" regex ")"
lookbehind = S.seq(S.lex(gp_lb=B.lit("(?<=")).named('"(?<="'), +regex.mark('pattern'), rparen)
# group = "(?<!" regex ")"
negative_lookbehind = S.seq(S.lex(gp_neglb=B.lit("(?<!" )).named('"(?<!"'), +regex.mark('pattern'), rparen)
# group = "(?" inline_flags ")"
inline_flag_only = S.seq(S.lex(gp_inline_flags=B.lit("(?")).named('"(?"'), 
                            +inline_flags, 
                            rparen)
# group = "(?" inline_flags ":" regex ")"
inline_flag_with_colon = S.seq(S.lex(gp_inline_flags_colon=B.lit("(?")).named('"(?"'), 
                                +inline_flags, 
                                colon, 
                                +regex.mark('pattern'), 
                                rparen)


grp_body= S.choice(
            plain.to(lambda **t: GroupAtom(kind=GroupKind.CAPTURE, **t), id="plain").named('plain'),
            noncapturing.to(lambda **t: GroupAtom(kind=GroupKind.NON_CAPTURE, **t), id="noncapturing").named('noncapturing'),
            named.to(lambda **t: GroupAtom(kind=GroupKind.CAPTURE, **t), id="named").named('named'),
            lookahead.to(lambda **t: GroupAtom(kind=GroupKind.LOOKAHEAD, **t), id="lookahead").named('lookahead'),
            negative_lookahead.to(lambda **t: GroupAtom(kind=GroupKind.NEG_LOOKAHEAD, **t), id="negative_lookahead").named('negative_lookahead'),
            lookbehind.to(lambda **t: GroupAtom(kind=GroupKind.LOOKBEHIND, **t), id="lookbehind").named('lookbehind'),
            negative_lookbehind.to(lambda **t: GroupAtom(kind=GroupKind.NEG_LOOKBEHIND, **t), id="negative_lookbehind").named('negative_lookbehind'),
            inline_flag_only.to(lambda **t: GroupAtom(kind=GroupKind.FLAGS, **t), id="inline_flag_only").named('inline_flag_only'),
            inline_flag_with_colon.to(lambda **t: GroupAtom(kind=GroupKind.FLAGS_SCOPED, **t), id="inline_flag_with_colon").named('inline_flag_with_colon'),
        ).update(group_counter = lambda c, _: c + 1 if c is not ... else 1)


def main():
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
    negative_lookahead = S.lex(gp_negative_lookahead=B.lit("(?!"))
    nl = r"(?!\1)"
    ret = parse_regex(negative_lookahead, nl, raw=False)
    assert not isinstance(ret, Error)

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
    main()