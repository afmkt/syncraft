from enum import Enum
from syncraft.charset import CodeUniverse, CharSet
from syncraft.fa import NFA, FAState
from syncraft.utils import FrozenDict


def test_start_anchor_simple():
    uni = CodeUniverse.ascii()
    base = NFA.from_charset('a', uni)
    anchored = base.start()
    r = anchored.runner().start().runner
    # At beginning, consuming 'a' should accept
    res = r.step('a', 0)
    assert res.accepted
    # If any prefix exists, it should fail
    r2 = anchored.runner()
    res2 = r2.step('b', 0)
    assert not res2.accepted


def test_end_anchor_simple():
    uni = CodeUniverse.ascii()
    base = NFA.from_charset('a', uni)
    anchored = base.end()
    r = anchored.runner()
    # After consuming 'a', not yet accepted until finalize()
    res = r.step('a', 0)
    assert not res.accepted
    fin = res.runner.finalize()
    assert fin.accepted
    # If extra trailing symbol exists, finalize should not help
    r2 = anchored.runner()
    res2 = r2.step('a', 0)
    res2b = res2.runner.step('b', 1)
    fin2 = res2b.runner.finalize()
    assert not fin2.accepted


def test_both_anchors_empty():
    # ^$ should match empty only. Construct NFA with epsilon accept and then add both anchors.
    uni = CodeUniverse.ascii()
    # Build empty-match NFA: init is also accept, no transitions.
    init = FAState()
    empty = NFA(
        universe=uni,
        init=init,
        accept=FrozenDict({init: frozenset()}),
        transitions=FrozenDict(),
        epsilon=FrozenDict(),
    )
    # Now anchor at both ends
    start_anchored = empty.start()
    both = start_anchored.end()
    r = both.runner().start().runner

    # Without consuming anything, finalize should accept (consumes END)
    fin = r.finalize()
    assert fin.accepted
    # With any symbol, it should fail
    r2 = both.runner()
    res2 = r2.step('x', 0)
    fin2 = res2.runner.finalize()
    assert not fin2.accepted
def test_anchor_feature_placeholder():
    assert True
