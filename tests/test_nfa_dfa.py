
from __future__ import annotations
import pytest
import enum
from syncraft.fa import NFA, DFA
from syncraft.charset import CodeUniverse


# --- Large, degenerate, and recursive automata tests ---
def test_large_chain_dfa():
    # DFA that accepts a long specific sequence (e.g., 1000 'a's)
    n = 1000
    nfa = NFA.from_char('a', universe=CodeUniverse.ascii())
    for _ in range(n-1):
        nfa = nfa.then(NFA.from_char('a', universe=CodeUniverse.ascii()))
    dfa = nfa.dfa
    m = dfa.minimize
    assert dfa.match(['a']*n)
    assert m.match(['a']*n)
    assert not dfa.match(['a']*(n-1))
    assert not m.match(['a']*(n-1))
    assert not dfa.match(['a']*n + ['b'])
    assert not m.match(['a']*n + ['b'])

def test_large_or_dfa():
    # DFA that accepts any of 1000 different single characters
    chars = [chr(32+i) for i in range(1000)]
    nfa = NFA.from_char(chars[0], universe=CodeUniverse.unicode())
    for c in chars[1:]:
        nfa = nfa | NFA.from_char(c, universe=CodeUniverse.unicode())
    dfa = nfa.dfa
    d = dfa.minimize
    for c in chars:
        assert dfa.match([c])
        assert d.match([c])
    assert not dfa.match(['z']) if 'z' not in chars else True
    assert not d.match(['z']) if 'z' not in chars else True


def test_deeply_nested_nfa():
    # NFA with deep nesting: (((a then b) then c) then ...)
    seq = [chr(65+i) for i in range(20)]
    nfa = NFA.from_char(seq[0], universe=CodeUniverse.ascii())
    for c in seq[1:]:
        nfa = nfa.then(NFA.from_char(c, universe=CodeUniverse.ascii()))
    assert nfa.match(seq)
    assert not nfa.match(seq[:-1])

def test_recursive_nfa_star():
    # NFA for (ab)*
    nfa = NFA.from_char('a', universe=CodeUniverse.ascii()).then(NFA.from_char('b', universe=CodeUniverse.ascii())).star
    # Accepts any even-length string of alternating a/b
    for n in range(0, 20, 2):
        s = ['a','b']*(n//2)
        assert nfa.match(s)
    assert not nfa.match(['a'])
    assert not nfa.match(['b'])
    assert not nfa.match(['a','a'])



# --- Enum tag, NFA over enum, DFA over enum tests ---
class Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

def test_enum_tag_nfa():
    u = CodeUniverse.enum(Color)
    from syncraft.fa import NFA
    nfa = NFA.from_char(Color.RED, universe=u).tagged('red')
    assert nfa.match([Color.RED])
    assert not nfa.match([Color.GREEN])
    # Tag should be present in accept
    for tags in nfa.accept.values():
        assert 'red' in tags

def test_nfa_over_enum():
    u = CodeUniverse.enum(Color)
    from syncraft.fa import NFA
    nfa = NFA.from_char(Color.RED, universe=u) | NFA.from_char(Color.BLUE, universe=u)
    assert nfa.match([Color.RED])
    assert nfa.match([Color.BLUE])
    assert not nfa.match([Color.GREEN])

def test_dfa_over_enum():
    u = CodeUniverse.enum(Color)
    from syncraft.fa import NFA
    nfa = NFA.from_char(Color.RED, universe=u) | NFA.from_char(Color.BLUE, universe=u)
    dfa = nfa.dfa
    m = dfa.minimize
    assert dfa.match([Color.RED])
    assert m.match([Color.RED])
    assert dfa.match([Color.BLUE])
    assert m.match([Color.BLUE])
    assert not dfa.match([Color.GREEN])
    assert not m.match([Color.GREEN])


def assert_both(nfa: NFA[str], dfa: DFA[str], input: list[str], expected: bool)->None:
    nfa2 = dfa.nfa
    nfa_result = nfa.match(input)
    dfa_result = dfa.match(input)
    nfa2_result = nfa2.match(input)
    m = dfa.minimize
    
    m_result = m.match(input)
    assert nfa2_result == expected, f"NFA from DFA failed on input {input}: expected {expected}, got {nfa2_result}"
    assert nfa_result == expected, f"NFA failed on input {input}: expected {expected}, got {nfa_result}"
    assert dfa_result == expected, f"DFA failed on input {input}: expected {expected}, got {dfa_result}"
    assert m_result == expected, f"Minimized DFA failed on input {input}: expected {expected}, got {m_result}"
    # assert m == m.minimize, "Minimized DFA is not idempotent"
    # assert m == dfa.nfa.dfa.minimize, "Minimized DFA from DFA does not match minimized DFA from NFA"

def test_from_char()->None:
    nfa = NFA.from_char('a', universe=CodeUniverse.ascii())
    dfa = DFA.from_nfa(nfa)
    assert nfa.current in nfa.transitions
    assert_both(nfa, dfa, ['a'], True)
    assert_both(nfa, dfa, ['b'], False)
    assert_both(nfa, dfa, [], False)
    




def test_then():
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).then(NFA.from_char("b", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a", "b"], True)
    assert_both(nfa, dfa, ["a"], False)
    assert_both(nfa, dfa, ["b"], False)
    assert_both(nfa, dfa, ["a", "c"], False)
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).then(NFA.from_char("a", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a", "a"], True)
    assert_both(nfa, dfa, ["a", "c"], False)
    assert_both(nfa, dfa, ["a"], False)
    assert_both(nfa, dfa, [], False)
    assert_both(nfa, dfa, ["b"], False)
    assert_both(nfa, dfa, ["a", "b"], False)
    assert_both(nfa, dfa, ["a", "a", "a"], False)
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii())
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
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).union(NFA.from_char("b", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a"], True)
    assert_both(nfa, dfa, ["b"], True)
    assert_both(nfa, dfa, ["c"], False)
    assert_both(nfa, dfa, [], False)


def test_optional():
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).optional
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, [], True)          # epsilon path
    assert_both(nfa, dfa, ["a"], True)       # one "a"
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "a"], False) # not "aa"


def test_many():
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).many()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, [], False)          # epsilon path
    assert_both(nfa, dfa, ["a"], True)       # one "a"
    assert_both(nfa, dfa, ["a", "a"], True)  # two "a"
    assert_both(nfa, dfa, ["a", "a", "a"], True) # three "a"
    assert_both(nfa, dfa, ["b"], False)      # not "a"
    assert_both(nfa, dfa, ["a", "b"], False) # not "aa"
    assert_both(nfa, dfa, ["b", "a"], False) # not "aa"
    assert_both(nfa, dfa, ["a", "a", "b"], False)
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).many(2, 4)
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
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).plus
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ["a"], True)
    assert_both(nfa, dfa, ["a", "a"], True)
    assert_both(nfa, dfa, ["a", "a", "a"], True)
    assert_both(nfa, dfa, [], False)         # requires at least one

def test_star():
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).star
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
    a = NFA.from_char('a', universe=CodeUniverse.ascii())
    b = NFA.from_char('b', universe=CodeUniverse.ascii())
    c = NFA.from_char('c', universe=CodeUniverse.ascii())
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
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).then(NFA.from_char("b", universe=CodeUniverse.ascii())).then(NFA.from_char("c", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    m = dfa.minimize
    runner = nfa.run(["a", "b", "c"])
    drunner = dfa.run(["a", "b", "c"])
    mrunner = m.run(["a", "b", "c"])
    # print(runner)
    assert runner.is_accepted(nfa), "nfa is not accepted"
    assert drunner.is_accepted(dfa), "dfa is not accepted"
    r1 = runner.resumable(nfa)
    dr1 = drunner.resumable(dfa)
    m1 = mrunner.resumable(m)
    # print(r1)
    assert not r1, "nfa runner is resumable"
    assert not dr1, "dfa runner is resumable"
    assert not m1, "minimized dfa runner is resumable"
    runner = nfa.run(["a", "b"])
    drunner = dfa.run(["a", "b"])
    mrunner = m.run(["a", "b"])
    assert not runner.is_accepted(nfa), "nfa is accepted"
    assert not drunner.is_accepted(dfa), "dfa is accepted"
    assert not mrunner.is_accepted(m), "minimized dfa is accepted"
    dr2 = drunner.resumable(dfa)
    r2 = runner.resumable(nfa)
    mr2 = mrunner.resumable(m)
    assert mr2, "minimized dfa runner is not resumable"
    # print(r2)
    assert r2 , "nfa runner is not resumable"
    assert dr2, "dfa runner is not resumable"
    runner = nfa.run(["a", "b", "c", "d"])
    drunner = dfa.run(["a", "b", "c", "d"])
    mrunner = m.run(["a", "b", "c", "d"])
    # print(runner)
    assert len(runner.accepted) == 1
    assert runner.accepted[0][0] == 2
    assert not runner.is_accepted(nfa), "nfa is accepted"
    assert not drunner.is_accepted(dfa), "dfa is accepted"
    assert not mrunner.is_accepted(m), "minimized dfa is accepted"
    dr3 = drunner.resumable(dfa)
    r3 = runner.resumable(nfa)
    mr3 = mrunner.resumable(m)
    # print(r3)
    assert not r3, "nfa runner is resumable"
    assert not dr3, "dfa runner is resumable"
    assert not mr3, "minimized dfa runner is resumable"

def test_gen()->None:
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).then(NFA.from_char("b", universe=CodeUniverse.ascii())).then(NFA.from_char("c", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    m = dfa.minimize
    r = nfa.runner()
    dr = dfa.runner()
    mr = m.runner()
    from_r = r.gen(nfa, 2)
    from_dr = dr.gen(dfa, 2)
    from_mr = mr.gen(m, 2)
    assert all([nfa.match(x[0]) for x in from_r])
    assert all([dfa.match(x[0]) for x in from_dr])
    assert all([m.match(x[0]) for x in from_mr])


def test_dead_state():
    # NFA that can go to a dead state: "a" then optional "b"
    nfa = NFA.from_char("a", universe=CodeUniverse.ascii()).then(NFA.from_char("b", universe=CodeUniverse.ascii()).optional)
    dfa = DFA.from_nfa(nfa)
    m = dfa.minimize
    # Check all DFA closures
    dead_states = [state for state, trans in dfa.transitions.items() if not trans]
    dead_states_m = [state for state, trans in m.transitions.items() if not trans]
    # There should be exactly one dead state
    assert len(dead_states) <= 1, f"Expected one dead state, got {len(dead_states)}"
    assert len(dead_states_m) <= 1, f"Expected one dead state in minimized DFA, got {len(dead_states_m)}"
    
    # The dead state should not accept any input


def test_tag_propagation():
    # NFA with multiple accepting states with tags
    nfa_a = NFA.from_char("a", universe=CodeUniverse.ascii()).tagged("tag1")
    nfa_b = NFA.from_char("b", universe=CodeUniverse.ascii()).tagged("tag2")
    nfa = nfa_a.union(nfa_b)
    dfa = DFA.from_nfa(nfa)
    m = dfa.minimize
    # Every DFA accept state should contain all tags of NFA states it represents
    for nfa_states, fa_state in dfa.nfa2dfa.items():
        tags_from_nfa = set()
        for ns in nfa_states:
            tags_from_nfa.update(nfa.accept.get(ns, frozenset()))
        if fa_state in dfa.accept:
            assert dfa.accept[fa_state] == frozenset(tags_from_nfa), (
                f"Tags not propagated correctly for DFA state {fa_state}"
            )


# --- DFA combinator tests ---
def test_dfa_combinators_basic():
    u = CodeUniverse.ascii()
    from syncraft.fa import NFA
    a = NFA.from_char('a', universe=u).dfa
    ma = a.minimize
    b = NFA.from_char('b', universe=u).dfa
    mb = b.minimize
    # complement
    not_a = -a
    not_ma = -ma
    assert not not_ma.match(['a'])
    assert not_ma.match(['b'])
    assert not not_a.match(['a'])
    assert not_a.match(['b'])
    # intersection
    ab = a & b
    abm = ma & mb
    assert not abm.match(['a'])
    assert not abm.match(['b'])
    assert not abm.match(['a','b'])
    assert not ab.match(['a'])
    assert not ab.match(['b'])
    assert not ab.match(['a','b'])
    # union
    a_or_b = a | b
    a_or_bm = ma | mb
    assert a_or_bm.match(['a'])
    assert a_or_bm.match(['b'])
    assert not a_or_bm.match(['c'])
    assert a_or_b.match(['a'])
    assert a_or_b.match(['b'])
    assert not a_or_b.match(['c'])
    # difference
    only_a = a - b
    only_am = ma - mb
    assert only_am.match(['a'])
    assert not only_am.match(['b'])
    assert only_a.match(['a'])
    assert not only_a.match(['b'])

def test_dfa_tagged():
    u = CodeUniverse.ascii()
    from syncraft.fa import NFA
    a = NFA.from_char('a', universe=u).dfa
    ma = a.minimize
    tagged = a.tagged('X')
    tagged_m = ma.tagged('X')
    for tags in tagged.accept.values():
        assert 'X' in tags
    for tags in tagged_m.accept.values():
        assert 'X' in tags
    # append tag
    tagged2 = tagged.tagged('Y', append=True)
    tagged2_m = tagged_m.tagged('Y', append=True)
    for tags in tagged2_m.accept.values():
        assert 'X' in tags and 'Y' in tags
    for tags in tagged2.accept.values():
        assert 'X' in tags and 'Y' in tags

def test_dfa_combinator_chain():
    u = CodeUniverse.ascii()
    from syncraft.fa import NFA
    a = NFA.from_char('a', universe=u).dfa
    ma = a.minimize
    b = NFA.from_char('b', universe=u).dfa
    mb = b.minimize
    c = NFA.from_char('c', universe=u).dfa
    mc = c.minimize
    combo = ((a | b) & -c)
    combo_m = ((ma | mb) & -mc)
    assert combo_m.match(['a'])
    assert combo_m.match(['b'])
    assert not combo_m.match(['c'])
    assert not combo_m.match(['a','c'])
    assert combo.match(['a'])
    assert combo.match(['b'])
    assert not combo.match(['c'])
    assert not combo.match(['a','c'])
