from __future__ import annotations
from syncraft.walker import walk
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with, generate
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
from syncraft.fa import NFA, DFA
from syncraft.constraint import FrozenDict
from rich import print




def test_from_char()->None:

    nfa = NFA.from_char('a')
    print(nfa)
    dfa = DFA.from_nfa(nfa)
    print(dfa)
    assert nfa.start in nfa.transitions
    assert 'a' in nfa.transitions[nfa.start]
    assert nfa.transitions[nfa.start]['a'] == frozenset(nfa.accept)
    assert dfa.match(['a'])
    assert nfa.match(['a'])
    assert not dfa.match(['b'])
    assert not nfa.match(['b'])
    assert not nfa.match([])
    assert not dfa.match([])
    


if __name__ == "__main__":
    test_from_char()
