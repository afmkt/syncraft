from __future__ import annotations
from syncraft.nfa import NFA
from syncraft.constraint import FrozenDict

def test_from_char()->None:
    nfa = NFA.from_char('a')
    assert nfa.start in nfa.transitions
    assert 'a' in nfa.transitions[nfa.start]
    assert nfa.transitions[nfa.start]['a'] == frozenset(nfa.accept)
    assert nfa.match(['a'])
    assert not nfa.match(['b'])
    assert not nfa.match([])




def test_then():
    nfa = NFA.from_char("a").then(NFA.from_char("b"))
    assert nfa.match(["a", "b"]) is True
    assert nfa.match(["a"]) is False
    assert nfa.match(["b"]) is False
    assert nfa.match(["a", "c"]) is False
    nfa = NFA.from_char("a").then(NFA.from_char("a"))
    assert nfa.match(["a", "a"]) is True
    assert nfa.match(["a", "a", "a"]) is False
    assert nfa.match(["a", "b"]) is False
    assert nfa.match(["a"]) is False
    assert nfa.match(["b"]) is False
    assert nfa.match(["a", "c"]) is False
    nfa = NFA.from_char("a")
    nfa = nfa.then(nfa).then(nfa)  # aaa
    assert nfa.match(["a", "a", "a"]) is True
    assert nfa.match(["a", "a"]) is False
    assert nfa.match(["a"]) is False
    assert nfa.match([]) is False



def test_or_else():
    nfa = NFA.from_char("a").union(NFA.from_char("b"))
    assert nfa.match(["a"]) is True
    assert nfa.match(["b"]) is True
    assert nfa.match(["c"]) is False
    assert nfa.match([]) is False


def test_optional():
    nfa = NFA.from_char("a").optional()
    assert nfa.match([]) is True          # epsilon path
    assert nfa.match(["a"]) is True       # one "a"
    assert nfa.match(["b"]) is False      # not "a"
    assert nfa.match(["a", "a"]) is False # not "aa"


def test_many():
    nfa = NFA.from_char("a").many()
    assert nfa.match(["a"]) is True
    assert nfa.match(["a", "a"]) is True
    assert nfa.match(["a", "a", "a"]) is True
    assert nfa.match([]) is False         # requires at least one
    nfa = NFA.from_char("a").many(2, 4)
    assert nfa.match(["a"]) is False      # requires at least two
    assert nfa.match(["a", "a"]) is True
    assert nfa.match(["a", "a", "a"]) is True
    assert nfa.match(["a", "a", "a", "a"]) is True
    assert nfa.match(["a", "a", "a", "a", "a"]) is False # at most four
    assert nfa.match([]) is False         # requires at least two

def test_plus():
    nfa = NFA.from_char("a").plus()
    assert nfa.match(["a"]) is True
    assert nfa.match(["a", "a"]) is True
    assert nfa.match(["a", "a", "a"]) is True
    assert nfa.match([]) is False         # requires at least one

def test_star():
    nfa = NFA.from_char("a").star()
    assert nfa.match([]) is True          # epsilon path
    assert nfa.match(["a"]) is True       # one "a"
    assert nfa.match(["a", "a"]) is True  # two "a"
    assert nfa.match(["a", "a", "a"]) is True # three "a"
    assert nfa.match(["b"]) is False      # not "a"
    assert nfa.match(["a", "b"]) is False # not "aa"
    assert nfa.match(["b", "a"]) is False # not "aa"
    assert nfa.match(["a", "a", "b"]) is False # not "aa"
    assert nfa.match(["b", "a", "a"]) is False # not "aa"
    assert nfa.match(["a", "b", "a"]) is False # not "aa"
    assert nfa.match(["b", "a", "b"]) is False # not "aa"
    assert nfa.match(["b", "b", "a"]) is False # not "aa"
    assert nfa.match(["b", "b", "b"]) is False # not "aa"


def test_complex()->None:
    a = NFA.from_char('a')
    b = NFA.from_char('b')
    c = NFA.from_char('c')
    a_or_b = a.union(b)
    a_or_b_then_c = a_or_b.then(c)
    many_a_or_b_then_c = a_or_b_then_c.many(2, 4)
    assert many_a_or_b_then_c.match(['a', 'b', 'c', 'a', 'c']) is False
    assert many_a_or_b_then_c.match(['a', 'b', 'c']) is False
    assert many_a_or_b_then_c.match(['a', 'c', 'b', 'c', 'a', 'c']) is True
    assert many_a_or_b_then_c.match(['a', 'b', 'c', 'a', 'b', 'c', 'a', 'b', 'c']) is False
    assert many_a_or_b_then_c.match(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c']) is True
    assert many_a_or_b_then_c.match(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c', 'b']) is False
    assert many_a_or_b_then_c.match(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c', 'b', 'c']) is False
    assert many_a_or_b_then_c.match(['a', 'b']) is False
    assert many_a_or_b_then_c.match(['c']) is False
    assert many_a_or_b_then_c.match([]) is False
    assert many_a_or_b_then_c.match(['a', 'c', 'b', 'c']) is True
    assert many_a_or_b_then_c.match(['b', 'c', 'a', 'c']) is True
    assert many_a_or_b_then_c.match(['a', 'c', 'a', 'c']) is True



def test_runner()->None:
    nfa = NFA.from_char("a").then(NFA.from_char("b")).then(NFA.from_char("c"))
    runner = nfa.run(["a", "b", "c"])
    print(runner)
    assert runner.is_accepted(nfa)
    r1 = runner.resumable(nfa)
    print(r1)
    assert not r1
    runner = nfa.run(["a", "b"])
    assert not runner.is_accepted(nfa)
    r2 = runner.resumable(nfa)
    print(r2)
    assert r2 
    runner = nfa.run(["a", "b", "c", "d"])
    print(runner)
    assert len(runner.accepted) == 1
    assert runner.accepted[0][0] == 2
    assert not runner.is_accepted(nfa)
    r3 = runner.resumable(nfa)
    print(r3)
    assert not r3
