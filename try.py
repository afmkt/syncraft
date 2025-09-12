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

def test_optional():
    nfa = NFA.from_char("a").optional()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, [], True)          # epsilon path
    assert_both(nfa, dfa, ["a"], True)       # one "a"
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "a"], False) # not "aa"


if __name__ == "__main__":
    test_optional()
