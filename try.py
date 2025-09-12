from __future__ import annotations
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with, generate
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
from syncraft.fa import NFA, DFA
from syncraft.constraint import FrozenDict
from rich import print



def assert_both(nfa: NFA[str], dfa: DFA[str], input: list[str], expected: bool)->None:
    nfa_result = nfa.match(input)
    dfa_result = dfa.match(input)
    assert nfa_result == expected, f"NFA failed on input {input}: expected {expected}, got {nfa_result}"
    assert dfa_result == expected, f"DFA failed on input {input}: expected {expected}, got {dfa_result}"

def test_tag_propagation():
    # NFA with multiple accepting states with tags
    nfa_a = NFA.from_char("a").tagged("tag1")
    nfa_b = NFA.from_char("b").tagged("tag2")
    nfa = nfa_a.union(nfa_b)
    dfa = DFA.from_nfa(nfa)
    
    # Every DFA accept state should contain all tags of NFA states it represents
    for fa_state, tags in dfa.accept.items():
        print(tags)
        assert tags == frozenset({'tag1', 'tag2'}), f"Tags not propagated correctly for DFA state {fa_state}"


if __name__ == "__main__":
    test_tag_propagation()
