import random

import pytest

from syncraft.fa import NFA
from syncraft.alphabet import Alphabet, AlphabetProtocol
from syncraft.charset import CharSet, CharSetFactory




def test_dfa_reverse_simple():
    # DFA for 'abc' tagged as 'word'
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    nfa = NFA.seq(s='abc', tag='word', cs_factory=cs_factory)
    dfa = nfa.dfa
    rev = dfa.reverse
    s = rev.gen('word', random.Random(42))
    assert s == 'abc'

def test_dfa_reverse_multiple_tags():
    # DFA for 'a' tagged as 'A', 'b' tagged as 'B'
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    nfa = NFA.seq(s='a', tag='A', cs_factory=cs_factory) | NFA.seq(s='b', tag='B', cs_factory=cs_factory)
    dfa = nfa.dfa
    rev = dfa.reverse
    s_a = rev.gen('A', random.Random(1))
    s_b = rev.gen('B', random.Random(2))
    assert s_a == 'a'
    assert s_b == 'b'

def test_dfa_reverse_randomness():
    # DFA for 'ab' and 'ac' both tagged as 'X'
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    nfa = NFA.seq(s='ab', tag='X', cs_factory=cs_factory) | NFA.seq(s='ac', tag='X', cs_factory=cs_factory)
    dfa = nfa.dfa
    rev = dfa.reverse
    # Should be able to generate both 'ab' and 'ac'
    results = set(rev.gen('X', random.Random(seed)) for seed in range(10))
    assert results == {'ab', 'ac'}

def test_dfa_reverse_invalid_tag():
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    nfa = NFA.seq(s='a', tag='A', cs_factory=cs_factory)
    dfa = nfa.dfa
    rev = dfa.reverse
    try:
        rev.gen('B', random.Random(0))
        assert False, "Should raise for invalid tag"
    except Exception:
        pass


def test_dfa_reverse_none_tag_rejected():
    cs_factory = CharSetFactory(alphabet=Alphabet(str))
    nfa = NFA.seq(s='a', tag='A', cs_factory=cs_factory)
    rev = nfa.dfa.reverse
    with pytest.raises(AssertionError):
        rev.gen(None, random.Random(0))
