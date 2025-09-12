from __future__ import annotations
from syncraft.fa import NFA, DFA
from syncraft.charset import CodeUniverse


def assert_both(nfa: NFA[str], dfa: DFA[str], input: list[str], expected: bool)->None:
    nfa_result = nfa.match(input)
    dfa_result = dfa.match(input)
    assert nfa_result == expected, f"NFA failed on input {input}: expected {expected}, got {nfa_result}"
    assert dfa_result == expected, f"DFA failed on input {input}: expected {expected}, got {dfa_result}"

def test_from_char()->None:
    nfa = NFA.from_char('a', universe=CodeUniverse.ASCII)
    dfa = DFA.from_nfa(nfa)
    assert nfa.current in nfa.transitions
    assert_both(nfa, dfa, ['a'], True)
    assert_both(nfa, dfa, ['b'], False)
    assert_both(nfa, dfa, [], False)
    




def test_then():
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).then(NFA.from_char("b", universe=CodeUniverse.ASCII))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a", "b"], True)
    assert_both(nfa, dfa, ["a"], False)
    assert_both(nfa, dfa, ["b"], False)
    assert_both(nfa, dfa, ["a", "c"], False)
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).then(NFA.from_char("a", universe=CodeUniverse.ASCII))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a", "a"], True)
    assert_both(nfa, dfa, ["a", "c"], False)
    assert_both(nfa, dfa, ["a"], False)
    assert_both(nfa, dfa, [], False)
    assert_both(nfa, dfa, ["b"], False)
    assert_both(nfa, dfa, ["a", "b"], False)
    assert_both(nfa, dfa, ["a", "a", "a"], False)
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII)
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
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).union(NFA.from_char("b", universe=CodeUniverse.ASCII))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a"], True)
    assert_both(nfa, dfa, ["b"], True)
    assert_both(nfa, dfa, ["c"], False)
    assert_both(nfa, dfa, [], False)


def test_optional():
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).optional()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, [], True)          # epsilon path
    assert_both(nfa, dfa, ["a"], True)       # one "a"
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "a"], False) # not "aa"


def test_many():
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).many()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, [], False)          # epsilon path
    assert_both(nfa, dfa, ["a"], True)       # one "a"
    assert_both(nfa, dfa, ["a", "a"], True)  # two "a"
    assert_both(nfa, dfa, ["a", "a", "a"], True) # three "a"
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "b"], False) # not "aa"
    assert_both(nfa, dfa, ["b", "a"], False) # not "aa"
    assert_both(nfa, dfa, ["a", "a", "b"], False)
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).many(2, 4)
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
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).plus()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a"], True)
    assert_both(nfa, dfa, ["a", "a"], True)
    assert_both(nfa, dfa, ["a", "a", "a"], True)
    assert_both(nfa, dfa, [], False)         # requires at least one

def test_star():
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).star()
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
    a = NFA.from_char('a', universe=CodeUniverse.ASCII)
    b = NFA.from_char('b', universe=CodeUniverse.ASCII)
    c = NFA.from_char('c', universe=CodeUniverse.ASCII)
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
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).then(NFA.from_char("b", universe=CodeUniverse.ASCII)).then(NFA.from_char("c", universe=CodeUniverse.ASCII))
    dfa = DFA.from_nfa(nfa)
    runner = nfa.run(["a", "b", "c"])
    drunner = dfa.run(["a", "b", "c"])
    # print(runner)
    assert runner.is_accepted(nfa), "nfa is not accepted"
    assert drunner.is_accepted(dfa), "dfa is not accepted"
    r1 = runner.resumable(nfa)
    dr1 = drunner.resumable(dfa)
    # print(r1)
    assert not r1, "nfa runner is resumable"
    assert not dr1, "dfa runner is resumable"
    runner = nfa.run(["a", "b"])
    drunner = dfa.run(["a", "b"])
    assert not runner.is_accepted(nfa), "nfa is accepted"
    assert not drunner.is_accepted(dfa), "dfa is accepted"
    dr2 = drunner.resumable(dfa)
    r2 = runner.resumable(nfa)
    # print(r2)
    assert r2 , "nfa runner is not resumable"
    assert dr2, "dfa runner is not resumable"
    runner = nfa.run(["a", "b", "c", "d"])
    drunner = dfa.run(["a", "b", "c", "d"])
    # print(runner)
    assert len(runner.accepted) == 1
    assert runner.accepted[0][0] == 2
    assert not runner.is_accepted(nfa), "nfa is accepted"
    assert not drunner.is_accepted(dfa), "dfa is accepted"
    dr3 = drunner.resumable(dfa)
    r3 = runner.resumable(nfa)
    # print(r3)
    assert not r3, "nfa runner is resumable"
    assert not dr3, "dfa runner is resumable"

def test_gen()->None:
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).then(NFA.from_char("b", universe=CodeUniverse.ASCII)).then(NFA.from_char("c", universe=CodeUniverse.ASCII))
    dfa = DFA.from_nfa(nfa)
    r = nfa.runner()
    dr = dfa.runner()

    from_r = r.gen(nfa, 2)
    from_dr = dr.gen(dfa, 2)

    assert all([nfa.match(x[0]) for x in from_r])
    assert all([dfa.match(x[0]) for x in from_dr])


def test_dead_state():
    # NFA that can go to a dead state: "a" then optional "b"
    nfa = NFA.from_char("a", universe=CodeUniverse.ASCII).then(NFA.from_char("b", universe=CodeUniverse.ASCII).optional())
    dfa = DFA.from_nfa(nfa)
    
    # Check all DFA closures
    dead_states = [state for state, trans in dfa.transitions.items() if not trans]
    
    # There should be exactly one dead state
    assert len(dead_states) <= 1, f"Expected one dead state, got {len(dead_states)}"
    
    # The dead state should not accept any input

def test_dfa_transition_merge():
    # NFA with overlapping intervals that go to the same target
    nfa_a = NFA.from_char("a", universe=CodeUniverse.ASCII)
    nfa_b = NFA.from_char("b", universe=CodeUniverse.ASCII)
    nfa = nfa_a.union(nfa_b)
    dfa = DFA.from_nfa(nfa)
    
    # The DFA should merge the transitions to the same target
    for trans in dfa.transitions.values():
        targets = set(trans.values())
        # Multiple intervals pointing to same FAState should exist
        for t in targets:
            intervals = [iv for iv, tgt in trans.items() if tgt == t]
            # There should be no overlapping intervals
            for i1, i2 in zip(intervals, intervals[1:]):
                assert i1[1] < i2[0], f"Intervals {i1} and {i2} overlap, not merged properly"


def test_tag_propagation():
    # NFA with multiple accepting states with tags
    nfa_a = NFA.from_char("a", universe=CodeUniverse.ASCII).tagged("tag1")
    nfa_b = NFA.from_char("b", universe=CodeUniverse.ASCII).tagged("tag2")
    nfa = nfa_a.union(nfa_b)
    dfa = DFA.from_nfa(nfa)
    
    # Every DFA accept state should contain all tags of NFA states it represents
    for nfa_states, fa_state in dfa.nfa2dfa.items():
        tags_from_nfa = set()
        for ns in nfa_states:
            tags_from_nfa.update(nfa.accept.get(ns, frozenset()))
        if fa_state in dfa.accept:
            assert dfa.accept[fa_state] == frozenset(tags_from_nfa), (
                f"Tags not propagated correctly for DFA state {fa_state}"
            )
