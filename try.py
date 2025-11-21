from __future__ import annotations
from syncraft.regex import parse, parse_regex, group, regex_syntax, lparen, rparen, name, greater, inline_flags, colon
from rich import print
import timeit
from syncraft.regex import benchmark_fair, verify
from syncraft.syntax import Syntax as S
from syncraft.fa import Builder as B
plain = regex_syntax.mark('pattern').between(lparen, rparen)
# group = "(?:" regex ")"
noncapturing = S.seq(S.lex(_=B.lit("(?:")).named('"(?:"'), +regex_syntax.mark('pattern'), rparen)
# group = "(?P<" name ">" regex ")"
named = S.seq(S.lex(gp_named=B.lit("(?P<")).named('"(?P<"'), +name.mark('name'), greater, +regex_syntax.mark('pattern'), rparen)
# group = "(?=" regex ")"
lookahead = S.seq(S.lex(gp_lookahead=B.lit("(?=")).named('"(?="'), +regex_syntax.mark('pattern'), rparen)
# group = "(?!" regex ")"
negative_lookahead = S.seq(S.lex(gp_negative_lookahead=B.lit("(?!")).named('"(?!"'), +regex_syntax.mark('pattern'), rparen)
# group = "(?<=" regex ")"
lookbehind = S.seq(S.lex(gp_lookbehind=B.lit("(?<=")).named('"(?<="'), +regex_syntax.mark('pattern'), rparen)
# group = "(?<!" regex ")"
negative_lookbehind = S.seq(S.lex(gp_negative_lookbehind=B.lit("(?<!" )).named('"(?<!"'), +regex_syntax.mark('pattern'), rparen)
# group = "(?" inline_flags ")"
inline_flag_only = S.seq(S.lex(gp_inline_flags=B.lit("(?")).named('"(?"'), 
                            +inline_flags, 
                            rparen)
# group = "(?" inline_flags ":" regex ")"
inline_flag_with_colon = S.seq(S.lex(gp_inline_flags_colon=B.lit("(?")).named('"(?"'), 
                                +inline_flags, 
                                colon, 
                                +regex_syntax.mark('pattern'), 
                                rparen)
def test():
    cs = """['\"]"""
    pattern = r"""(?:(?P<quote>['\"])(?:(?!\1).)*\1)"""
    name = r"""(?P<quote>['\"])"""
    noncap = r"""(?:(?:(?!\1).)*\1)"""
    neg = r'(?!\1)'
    ret = parse_regex(named, name, raw = False)
    # ret = parse(pattern, raw = False, cache=None)
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
    test()
    # x()
    # r = benchmark_fair()
    # for line in r:
    #     print(line)
