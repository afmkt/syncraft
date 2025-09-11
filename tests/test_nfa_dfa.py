from __future__ import annotations
from syncraft.fa import NFA, DFA
from syncraft.constraint import FrozenDict


def assert_both(nfa: NFA[str], dfa: DFA[str], input: list[str], expected: bool)->None:
    nfa_result = nfa.match(input)
    dfa_result = dfa.match(input)
    assert nfa_result == expected, f"NFA failed on input {input}: expected {expected}, got {nfa_result}"
    assert dfa_result == expected, f"DFA failed on input {input}: expected {expected}, got {dfa_result}"

def test_from_char()->None:
    nfa = NFA.from_char('a')
    dfa = DFA.from_nfa(nfa)
    assert nfa.start in nfa.transitions
    assert 'a' in nfa.transitions[nfa.start]
    assert nfa.transitions[nfa.start]['a'] == frozenset(nfa.accept)
    assert_both(nfa, dfa, ['a'], True)
    assert_both(nfa, dfa, ['b'], False)
    assert_both(nfa, dfa, [], False)
    




def test_then():
    nfa = NFA.from_char("a").then(NFA.from_char("b"))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a", "b"], True)
    assert_both(nfa, dfa, ["a"], False)
    assert_both(nfa, dfa, ["b"], False)
    assert_both(nfa, dfa, ["a", "c"], False)
    nfa = NFA.from_char("a").then(NFA.from_char("a"))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a", "a"], True)
    assert_both(nfa, dfa, ["a", "c"], False)
    assert_both(nfa, dfa, ["a"], False)
    assert_both(nfa, dfa, [], False)
    assert_both(nfa, dfa, ["b"], False)
    assert_both(nfa, dfa, ["a", "b"], False)
    assert_both(nfa, dfa, ["a", "a", "a"], False)
    nfa = NFA.from_char("a")
    nfa = nfa.then(nfa).then(nfa)  # aaa
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a", "a", "a"], True)
    assert_both(nfa, dfa, ["a", "a"], False)
    assert_both(nfa, dfa, ["a"], False)
    assert_both(nfa, dfa, [], False)
    assert_both(nfa, dfa, ["b"], False)
    assert_both(nfa, dfa, ["a", "b"], False)
    assert_both(nfa, dfa, ["a", "a", "a", "a"], False)



def test_or_else():
    nfa = NFA.from_char("a").union(NFA.from_char("b"))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a"], True)
    assert_both(nfa, dfa, ["b"], True)
    assert_both(nfa, dfa, ["c"], False)
    assert_both(nfa, dfa, [], False)


def test_optional():
    nfa = NFA.from_char("a").optional()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, [], True)          # epsilon path
    assert_both(nfa, dfa, ["a"], True)       # one "a"
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "a"], False) # not "aa"


def test_many():
    nfa = NFA.from_char("a").many()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, [], False)          # epsilon path
    assert_both(nfa, dfa, ["a"], True)       # one "a"
    assert_both(nfa, dfa, ["a", "a"], True)  # two "a"
    assert_both(nfa, dfa, ["a", "a", "a"], True) # three "a"
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "b"], False) # not "aa"
    assert_both(nfa, dfa, ["b", "a"], False) # not "aa"
    assert_both(nfa, dfa, ["a", "a", "b"], False)
    nfa = NFA.from_char("a").many(2, 4)
    dfa = DFA.from_nfa(nfa)

    assert_both(nfa, dfa, [], False)         # requires at least two
    assert_both(nfa, dfa, ["a"], False)      # requires at least two
    assert_both(nfa, dfa, ["a", "a"], True)
    assert_both(nfa, dfa, ["a", "a", "a"], True)
    assert_both(nfa, dfa, ["a", "a", "a", "a"], True)
    assert_both(nfa, dfa, ["a", "a", "a", "a", "a"], False) # at most four
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "b"], False)
    assert_both(nfa, dfa, ["a", "a", "b"], False)
    assert_both(nfa, dfa, ["a", "a", "a", "b"], False)
    assert_both(nfa, dfa, ["a", "a", "a", "a", "b"], False)
    assert_both(nfa, dfa, ["a", "a", "a", "a", "a", "b"], False)

def test_plus():
    nfa = NFA.from_char("a").plus()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a"], True)
    assert_both(nfa, dfa, ["a", "a"], True)
    assert_both(nfa, dfa, ["a", "a", "a"], True)
    assert_both(nfa, dfa, [], False)         # requires at least one

def test_star():
    nfa = NFA.from_char("a").star()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, [], True)          # epsilon path
    assert_both(nfa, dfa, ["a"], True)       # one "a"
    assert_both(nfa, dfa, ["a", "a"], True)  # two "a"
    assert_both(nfa, dfa, ["a", "a", "a"], True) # three "a"
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "b"], False) # not "aa"
    assert_both(nfa, dfa, ["b", "a"], False) # not "aa"
    assert_both(nfa, dfa, ["a", "a", "b"], False) # not "aa"
    assert_both(nfa, dfa, ["b", "a", "a"], False) # not "aa"
    assert_both(nfa, dfa, ["a", "b", "a"], False) # not "aa"
    assert_both(nfa, dfa, ["b", "a", "b"], False) # not "aa"
    assert_both(nfa, dfa, ["b", "b", "a"], False) # not "aa"
    assert_both(nfa, dfa, ["b", "b", "b"], False) # not "aa"


def test_complex()->None:
    a = NFA.from_char('a')
    b = NFA.from_char('b')
    c = NFA.from_char('c')
    a_or_b = a.union(b)
    a_or_b_then_c = a_or_b.then(c)
    nfa = a_or_b_then_c.many(2, 4)
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ['a', 'b', 'c', 'a', 'c'], False)
    assert_both(nfa, dfa, ['a', 'b', 'c'], False)
    assert_both(nfa, dfa, ['a', 'c', 'b', 'c', 'a', 'c'], True)
    assert_both(nfa, dfa, ['a', 'b', 'c', 'a', 'b', 'c', 'a', 'b', 'c'], False)
    assert_both(nfa, dfa, ['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c'], True)
    assert_both(nfa, dfa, ['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c', 'b'], False)
    assert_both(nfa, dfa, ['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c', 'b', 'c'], False)
    assert_both(nfa, dfa, ['a', 'b'], False)
    assert_both(nfa, dfa, ['c'], False)
    assert_both(nfa, dfa, [], False)
    assert_both(nfa, dfa, ['a', 'c', 'b', 'c'], True)
    assert_both(nfa, dfa, ['b', 'c', 'a', 'c'], True)
    assert_both(nfa, dfa, ['a', 'c', 'a', 'c'], True)



def test_runner()->None:
    nfa = NFA.from_char("a").then(NFA.from_char("b")).then(NFA.from_char("c"))
    dfa = DFA.from_nfa(nfa)
    runner = nfa.run(["a", "b", "c"])
    drunner = dfa.run(["a", "b", "c"])
    # print(runner)
    assert runner.is_accepted(nfa)
    assert drunner.is_accepted(dfa)
    r1 = runner.resumable(nfa)
    dr1 = drunner.resumable(dfa)
    # print(r1)
    assert not r1
    assert not dr1
    runner = nfa.run(["a", "b"])
    drunner = dfa.run(["a", "b"])
    assert not runner.is_accepted(nfa)
    assert not drunner.is_accepted(dfa)
    dr2 = drunner.resumable(dfa)
    r2 = runner.resumable(nfa)
    # print(r2)
    assert r2 
    assert dr2
    runner = nfa.run(["a", "b", "c", "d"])
    drunner = dfa.run(["a", "b", "c", "d"])
    # print(runner)
    assert len(runner.accepted) == 1
    assert runner.accepted[0][0] == 2
    assert not runner.is_accepted(nfa)
    assert not drunner.is_accepted(dfa)
    dr3 = drunner.resumable(dfa)
    r3 = runner.resumable(nfa)
    # print(r3)
    assert not r3
    assert not dr3

def test_gen()->None:
    nfa = NFA.from_char("a").then(NFA.from_char("b")).then(NFA.from_char("c"))
    dfa = DFA.from_nfa(nfa)
    r = nfa.runner()
    dr = dfa.runner()

    from_r = r.gen(nfa, 2)
    from_dr = dr.gen(dfa, 2)

    assert all([nfa.match(x[0]) for x in from_r])
    assert all([dfa.match(x[0]) for x in from_dr])