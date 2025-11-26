from enum import Enum
from syncraft.charset import CharSet, CharSetFactory
from syncraft.alphabet import Alphabet
from syncraft.fa import NFA, FAStateFactory
from syncraft.utils import FrozenDict


def test_start_anchor_simple():
    uni = CharSetFactory(alphabet=Alphabet(str))
    base = NFA.oneof(s='a', cs_factory=uni)
    anchored = base.start()
    r = anchored.dfa.runner()
    r.start()
    # At beginning, consuming 'a' should accept
    res = r.step('a', 0)
    assert res.accepted
    # If any prefix exists, it should fail
    r2 = anchored.dfa.runner()
    res2 = r2.step('b', 0)
    assert not res2.accepted


def test_end_anchor_simple():
    uni = CharSetFactory(alphabet=Alphabet(str))
    base = NFA.oneof(s='a', cs_factory=uni)
    anchored = base.end()
    r = anchored.dfa.runner()
    # After consuming 'a', not yet accepted until finalize()
    res = r.step('a', 0)
    assert not res.accepted
    fin = r.finalize()
    assert fin.accepted
    # If extra trailing symbol exists, finalize should not help
    r2 = anchored.dfa.runner()
    res2 = r2.step('a', 0)
    res2b = r2.step('b', 1)
    fin2 = r2.finalize()
    assert not fin2.accepted


def test_both_anchors_empty():
    # ^$ should match empty only. Construct NFA with epsilon accept and then add both anchors.
    uni = CharSetFactory(alphabet=Alphabet(str))
    # Build empty-match NFA: init is also accept, no transitions.
    init = FAStateFactory.next()
    empty = NFA(
        cs_factory=uni,
        init=init,
        accept=FrozenDict({init: frozenset()}),
        transitions=FrozenDict(),
        epsilon=FrozenDict(),
    )
    # Now anchor at both ends
    start_anchored = empty.start()
    both = start_anchored.end()
    r = both.dfa.runner()
    r.start()

    # Without consuming anything, finalize should accept (consumes END)
    fin = r.finalize()
    assert fin.accepted
    # With any symbol, it should fail
    r2 = both.dfa.runner()
    res2 = r2.step('x', 0)
    fin2 = r2.finalize()
    assert not fin2.accepted
def test_anchor_feature_placeholder():
    assert True
