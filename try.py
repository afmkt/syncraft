from enum import Enum
from syncraft.charset import CodeUniverse, CharSet
from syncraft.fa import NFA, FAState
from syncraft.constraint import FrozenDict


def make_start_anchored(nfa: NFA[str]) -> NFA[str]:
    # New synthetic start state with a START-labeled edge into original init
    new_start = FAState()
    # Build transitions with the same FrozenDict shape
    trans: dict[FAState, dict[CharSet[str], frozenset[FAState]]] = {s: dict(m) for s, m in nfa.transitions.items()}
    trans[new_start] = {CharSet.start(nfa.universe): frozenset({nfa.init})}
    frozen_trans: FrozenDict[FAState, FrozenDict[CharSet[str], frozenset[FAState]]] = FrozenDict({s: FrozenDict(m) for s, m in trans.items()})
    return NFA(
        universe=nfa.universe,
        init=new_start,
        accept=nfa.accept,
        transitions=frozen_trans,
        epsilon=nfa.epsilon,
    )


def make_end_anchored(nfa: NFA[str]) -> NFA[str]:
    # Create a new accept state reachable via END from all previous accepts
    new_accept = FAState()
    trans: dict[FAState, dict[CharSet[str], frozenset[FAState]]] = {s: dict(m) for s, m in nfa.transitions.items()}
    # Add END edge from each old accept to new_accept
    for acc in nfa.accept.keys():
        mapping = trans.get(acc, {})
        mapping[CharSet.end(nfa.universe)] = frozenset({new_accept})
        trans[acc] = mapping
    # Only the new_accept carries tags (union of all old tags)
    tags = set()
    for t in nfa.accept.values():
        tags.update(t)
    accept_fd: FrozenDict[FAState, frozenset[str | Enum]] = FrozenDict({new_accept: frozenset(tags)})
    frozen_trans: FrozenDict[FAState, FrozenDict[CharSet[str], frozenset[FAState]]] = FrozenDict({s: FrozenDict(m) for s, m in trans.items()})
    return NFA(
        universe=nfa.universe,
        init=nfa.init,
        accept=accept_fd,
        transitions=frozen_trans,
        epsilon=nfa.epsilon,
    )


def test_start_anchor_simple():
    uni = CodeUniverse.ascii()
    base = NFA.from_charset('a', uni)
    anchored = make_start_anchored(base)
    r = anchored.runner()
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
    anchored = make_end_anchored(base)
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
    start_anchored = make_start_anchored(empty)
    both = make_end_anchored(start_anchored)
    r = both.runner()
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


if __name__ == '__main__':
    test_end_anchor_simple()
    # test_both_anchors_empty()
