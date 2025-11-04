from __future__ import annotations

from typing import Any
from syncraft.fa import DFA, FAState  # type: ignore
from syncraft.charset import CharSet, CodeUniverse
from syncraft.utils import FrozenDict

# Reproduction of a known minimization flaw: current DFA.minimize merges states that
# differ only by which symbol leads to acceptance. Hopcroft refinement should split
# these states because their transition structure relative to the accepting partition
# differs per symbol, but the current implementation unions all predecessors across
# symbols, losing that information.
#
# DFA structure (alphabet {a,b}):
#   S --a--> P, S --b--> Q
#   P --a--> F, P --b--> P
#   Q --a--> Q, Q --b--> F
#   F --a--> F, F --b--> F   (single accepting state F)
#
# Language recognized by this DFA (derived empirically):
#   Accepts strings of length >=2 that either end with a doubled symbol at the end reached via the side that
#   sets up that doubling. Minimal distinguishing behaviors:
#     P path (came from an 'a'): accepts when next symbol is 'a'.
#     Q path (came from a 'b'): accepts when next symbol is 'b'.
#   Example accepts: 'aa', 'bb', 'aab', 'bba', 'aaa', 'bbb'. Rejects: 'ab', 'ba', 'abb', 'baa'.
# Critical distinguishing string pair for states P and Q:
#   From P: 'a' leads to acceptance next step; 'b' does not.
#   From Q: 'b' leads to acceptance next step; 'a' does not.
# They are not equivalent and must not be merged.
# Current minimize erroneously merges P and Q, breaking acceptance of 'bb'.


def _build_dfa():
    u = CodeUniverse.ascii()
    a = CharSet.create('a', u)
    b = CharSet.create('b', u)
    S = FAState()
    P = FAState()
    Q = FAState()
    F = FAState()
    transitions = {
        S: {a: P, b: Q},
        P: {a: F, b: P},
        Q: {a: Q, b: F},
        F: {a: F, b: F},
    }
    accept = {F: frozenset()}  # no tags needed
    return DFA(
        universe=u,
        init=S,
        accept=FrozenDict(accept),
        transitions=FrozenDict({s: FrozenDict(m) for s, m in transitions.items()}),
    )


def _accept(dfa: DFA[str], s: str) -> bool:
    r: Any = dfa.runner()
    for i, ch in enumerate(s):
        rr = r.step(ch, i)
        r = rr.runner
    return r.is_accepted()


def test_minimize_distinguishes_symbol_predecessors():
    dfa = _build_dfa()
    # Sanity checks original DFA language expectations
    assert not _accept(dfa, '')
    assert not _accept(dfa, 'a')
    assert not _accept(dfa, 'b')
    assert _accept(dfa, 'aa')
    assert _accept(dfa, 'bb')
    assert not _accept(dfa, 'ab')
    assert not _accept(dfa, 'ba')
    assert not _accept(dfa, 'abb')
    assert not _accept(dfa, 'baa')
    assert _accept(dfa, 'aab')
    assert _accept(dfa, 'bba')

    m = dfa.minimize

    # If minimization were correct, these should remain accepted.
    # Current implementation likely rejects 'bb' (and possibly other patterns) due to
    # merging P & Q and taking only one representative's transitions.
    assert _accept(m, 'aa')
    assert _accept(m, 'bb')
    assert not _accept(m, 'abb')
    assert not _accept(m, 'baa')
    assert _accept(m, 'aab')
    assert _accept(m, 'bba')

    # Additionally, minimized DFA should still reject mismatched pairs
    assert not _accept(m, 'ab')
    assert not _accept(m, 'ba')


def test_minimize_state_count_partition_issue():
    dfa = _build_dfa()
    # Original DFA has 4 states
    assert len(dfa.transitions) == 4, "Construction sanity: expected 4 transition maps"
    m = dfa.minimize
    # Correct Hopcroft would keep 4 states (S, P, Q, F). Current algorithm collapses P,Q.
    assert len(m.transitions) == 4, f"Incorrect minimization merged distinguishable states: got {len(m.transitions)}"


def _all_strings(alphabet: str, max_len: int):
    if max_len == 0:
        yield ''
        return
    yield ''
    level = ['']
    for _ in range(max_len):
        next_level = []
        for prefix in level:
            for ch in alphabet:
                s = prefix + ch
                yield s
                next_level.append(s)
        level = next_level


def test_minimize_preserves_language_small():
    """Property: Minimized DFA must agree with original on all strings up to length 3."""
    u = CodeUniverse.ascii()
    # Build a DFA from an NFA for pattern: (ab|ba) a?  (just some branching / optional)
    from syncraft.fa import NFA
    a = NFA.from_charset('a', universe=u)
    b = NFA.from_charset('b', universe=u)
    pattern = (a.then(b) | b.then(a)).then(a.optional)
    dfa = pattern.dfa
    m = dfa.minimize
    for s in _all_strings('ab', 3):
        # Compare acceptance
        assert _accept(dfa, s) == _accept(m, s), f"Language changed on input {s!r}"
