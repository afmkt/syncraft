from __future__ import annotations
from syncraft.ast import TokenClass
from syncraft.fa import NFA, DFA, CodeUniverse
from rich import print
from syncraft.syntax import Syntax
literal = Syntax.config(TokenClass.simple()).literal


def test_dfa_transition_merge():
    # NFA with overlapping intervals that go to the same target
    nfa_a = NFA.from_char("a", universe=CodeUniverse.ascii())
    nfa_b = NFA.from_char("b", universe=CodeUniverse.ascii())
    nfa = nfa_a.union(nfa_b)
    dfa = DFA.from_nfa(nfa)
    # The DFA should merge the transitions to the same target
    print(dfa)
    for trans in dfa.transitions.values():
        targets = set(trans.values())
        # Multiple intervals pointing to same FAState should exist
        for t in targets:
            intervals = [iv for iv, tgt in trans.items() if tgt == t]
            # There should be no overlapping intervals
            print(intervals)
            for i1, i2 in zip(intervals, intervals[1:]):
                assert i1[1] < i2[0], f"Intervals {i1} and {i2} overlap, not merged properly"
    print('--- After minimization ---')
    m = dfa.minimize
    print(m)
    for trans in m.transitions.values():
        targets = set(trans.values())
        # Multiple intervals pointing to same FAState should exist
        for t in targets:
            intervals = [iv for iv, tgt in trans.items() if tgt == t]
            print(intervals)
            # There should be no overlapping intervals
            for i1, i2 in zip(intervals, intervals[1:]):
                assert i1[1] < i2[0], f"Intervals {i1} and {i2} overlap, not merged properly"


if __name__ == "__main__":
    test_dfa_transition_merge()
