import random
from syncraft.fa import NFA
from syncraft.charset import CodeUniverse

def test_dfa_reverse_simple():
    # DFA for 'abc' tagged as 'word'
    nfa = NFA.from_string('abc', tag='word', universe=CodeUniverse.ascii())
    dfa = nfa.dfa
    rev = dfa.reverse
    s = rev.gen('word', random.Random(42))
    assert s == 'abc'

def test_dfa_reverse_multiple_tags():
    # DFA for 'a' tagged as 'A', 'b' tagged as 'B'
    nfa = NFA.from_string('a', tag='A', universe=CodeUniverse.ascii()) | NFA.from_string('b', tag='B', universe=CodeUniverse.ascii())
    dfa = nfa.dfa
    rev = dfa.reverse
    s_a = rev.gen('A', random.Random(1))
    s_b = rev.gen('B', random.Random(2))
    assert s_a == 'a'
    assert s_b == 'b'

def test_dfa_reverse_randomness():
    # DFA for 'ab' and 'ac' both tagged as 'X'
    nfa = NFA.from_string('ab', tag='X', universe=CodeUniverse.ascii()) | NFA.from_string('ac', tag='X', universe=CodeUniverse.ascii())
    dfa = nfa.dfa
    rev = dfa.reverse
    # Should be able to generate both 'ab' and 'ac'
    results = set(rev.gen('X', random.Random(seed)) for seed in range(10))
    assert results == {'ab', 'ac'}

def test_dfa_reverse_invalid_tag():
    nfa = NFA.from_string('a', tag='A', universe=CodeUniverse.ascii())
    dfa = nfa.dfa
    rev = dfa.reverse
    try:
        rev.gen('B', random.Random(0))
        assert False, "Should raise for invalid tag"
    except Exception:
        pass
