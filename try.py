from __future__ import annotations
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with, generate
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
from syncraft.fa import NFA, DFA
from syncraft.constraint import FrozenDict
from rich import print




def test_from_char()->None:

    nfa = NFA.from_char("a").then(NFA.from_char("b")).then(NFA.from_char("c")).union(NFA.from_char("d")).then(NFA.from_char("e")).star()
    # dfa = DFA.from_nfa(nfa)
    r = nfa.runner()
    # dr = dfa.runner()

    from_r = r.gen(nfa, 12)
    # from_dr = dr.gen(dfa, 12)

    print(from_r)
    print('---' * 20)
    # print(from_dr)    


if __name__ == "__main__":
    test_from_char()
