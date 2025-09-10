from __future__ import annotations
from syncraft.nfa import NFA, NFAState

def test_from_char()->None:
    nfa = NFA.from_char('a')
    assert nfa.start in nfa.transitions
    assert 'a' in nfa.transitions[nfa.start]
    assert nfa.transitions[nfa.start]['a'] == frozenset(nfa.accept)
    assert nfa.run(['a'])
    assert not nfa.run(['b'])
    assert not nfa.run([])




def test_then():
    nfa = NFA.from_char("a").then(NFA.from_char("b"))
    assert nfa.run(["a", "b"]) is True
    assert nfa.run(["a"]) is False
    assert nfa.run(["b"]) is False
    assert nfa.run(["a", "c"]) is False
    nfa = NFA.from_char("a").then(NFA.from_char("a"))
    assert nfa.run(["a", "a"]) is True
    assert nfa.run(["a", "a", "a"]) is False
    assert nfa.run(["a", "b"]) is False
    assert nfa.run(["a"]) is False
    assert nfa.run(["b"]) is False
    assert nfa.run(["a", "c"]) is False
    nfa = NFA.from_char("a")
    nfa = nfa.then(nfa).then(nfa)  # aaa
    assert nfa.run(["a", "a", "a"]) is True
    assert nfa.run(["a", "a"]) is False
    assert nfa.run(["a"]) is False
    assert nfa.run([]) is False



def test_or_else():
    nfa = NFA.from_char("a").union(NFA.from_char("b"))
    assert nfa.run(["a"]) is True
    assert nfa.run(["b"]) is True
    assert nfa.run(["c"]) is False
    assert nfa.run([]) is False


def test_optional():
    nfa = NFA.from_char("a").optional()
    assert nfa.run([]) is True          # epsilon path
    assert nfa.run(["a"]) is True       # one "a"
    assert nfa.run(["b"]) is False      # not "a"
    assert nfa.run(["a", "a"]) is False # not "aa"


def test_many():
    nfa = NFA.from_char("a").many()
    assert nfa.run(["a"]) is True
    assert nfa.run(["a", "a"]) is True
    assert nfa.run(["a", "a", "a"]) is True
    assert nfa.run([]) is False         # requires at least one
    nfa = NFA.from_char("a").many(2, 4)
    assert nfa.run(["a"]) is False      # requires at least two
    assert nfa.run(["a", "a"]) is True
    assert nfa.run(["a", "a", "a"]) is True
    assert nfa.run(["a", "a", "a", "a"]) is True
    assert nfa.run(["a", "a", "a", "a", "a"]) is False # at most four
    assert nfa.run([]) is False         # requires at least two

def test_plus():
    nfa = NFA.from_char("a").plus()
    assert nfa.run(["a"]) is True
    assert nfa.run(["a", "a"]) is True
    assert nfa.run(["a", "a", "a"]) is True
    assert nfa.run([]) is False         # requires at least one

def test_star():
    nfa = NFA.from_char("a").star()
    assert nfa.run([]) is True          # epsilon path
    assert nfa.run(["a"]) is True       # one "a"
    assert nfa.run(["a", "a"]) is True  # two "a"
    assert nfa.run(["a", "a", "a"]) is True # three "a"
    assert nfa.run(["b"]) is False      # not "a"
    assert nfa.run(["a", "b"]) is False # not "aa"
    assert nfa.run(["b", "a"]) is False # not "aa"
    assert nfa.run(["a", "a", "b"]) is False # not "aa"
    assert nfa.run(["b", "a", "a"]) is False # not "aa"
    assert nfa.run(["a", "b", "a"]) is False # not "aa"
    assert nfa.run(["b", "a", "b"]) is False # not "aa"
    assert nfa.run(["b", "b", "a"]) is False # not "aa"
    assert nfa.run(["b", "b", "b"]) is False # not "aa"


def test_complex()->None:
    a = NFA.from_char('a')
    b = NFA.from_char('b')
    c = NFA.from_char('c')
    a_or_b = a.union(b)
    a_or_b_then_c = a_or_b.then(c)
    many_a_or_b_then_c = a_or_b_then_c.many(2, 4)
    assert many_a_or_b_then_c.run(['a', 'b', 'c', 'a', 'c']) is False
    assert many_a_or_b_then_c.run(['a', 'b', 'c']) is False
    assert many_a_or_b_then_c.run(['a', 'c', 'b', 'c', 'a', 'c']) is True
    assert many_a_or_b_then_c.run(['a', 'b', 'c', 'a', 'b', 'c', 'a', 'b', 'c']) is False
    assert many_a_or_b_then_c.run(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c']) is True
    assert many_a_or_b_then_c.run(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c', 'b']) is False
    assert many_a_or_b_then_c.run(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c', 'b', 'c']) is False
    assert many_a_or_b_then_c.run(['a', 'b']) is False
    assert many_a_or_b_then_c.run(['c']) is False
    assert many_a_or_b_then_c.run([]) is False
    assert many_a_or_b_then_c.run(['a', 'c', 'b', 'c']) is True
    assert many_a_or_b_then_c.run(['b', 'c', 'a', 'c']) is True
    assert many_a_or_b_then_c.run(['a', 'c', 'a', 'c']) is True
