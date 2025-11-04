from __future__ import annotations
import enum
from syncraft.fa import NFA, DFA
from syncraft.charset import CodeUniverse
from syncraft.utils import FrozenDict
from dataclasses import dataclass
from typing import Any, List, Tuple

# ---------------------------------------------------------------------------
# Compatibility layer for removed NFA.match / DFA.match / .run APIs
# ---------------------------------------------------------------------------

def _normalize_input(inp):
    if isinstance(inp, (str, bytes)):
        return inp
    return list(inp)

@dataclass
class LegacyRun:
    _runner: Any
    accepted: List[Tuple[int, Tuple[enum.Enum | str, ...]]]
    def is_accepted(self, _fa):
        return self._runner.is_accepted()
    def resumable(self, _fa):
        # Under new Runner API, resumable is a cached_property (frozenset of CharSet)
        return self._runner.resumable

def run(fa: NFA | DFA, inp) -> LegacyRun:
    """Simulate legacy .run(). Returns object with:
        - accepted: list[(position, tags_tuple)] for each position that ended in accept
        - is_accepted(fa) -> bool
        - resumable(fa) -> frozenset[CharSet]
    Behavior matches expectations of existing tests.
    """
    seq = _normalize_input(inp)
    runner: Any = fa.runner()
    accepted: list[tuple[int, tuple[enum.Enum | str, ...]]] = []
    for i, sym in enumerate(seq):
        rr = runner.step(sym, i)
        runner = rr.runner
        if runner.is_accepted():
            # store sorted tags for determinism
            accepted.append((i, tuple(sorted(runner.tags(), key=str))))

    return LegacyRun(runner, accepted)

def match(fa: NFA | DFA, inp) -> bool:
    return run(fa, inp).is_accepted(fa)


# --- Large, degenerate, and recursive automata tests ---
def test_large_chain_dfa():
    n = 1000
    nfa = NFA.from_charset('a', universe=CodeUniverse.ascii())
    for _ in range(n-1):
        nfa = nfa.then(NFA.from_charset('a', universe=CodeUniverse.ascii()))
    dfa = nfa.dfa
    m = dfa.minimize
    assert match(dfa, 'a'*n)
    assert match(m, 'a'*n)
    assert not match(dfa, 'a'*(n-1))
    assert not match(m, 'a'*(n-1))
    assert not match(dfa, 'a'*n + 'b')
    assert not match(m, 'a'*n + 'b')

def test_large_or_dfa():
    chars = [chr(32+i) for i in range(1000)]
    nfa = NFA.from_charset(chars[0], universe=CodeUniverse.unicode())
    for c in chars[1:]:
        nfa = nfa | NFA.from_charset(c, universe=CodeUniverse.unicode())
    dfa = nfa.dfa
    d = dfa.minimize
    for c in chars:
        assert match(dfa, c)
        assert match(d, c)
    assert (not match(dfa, 'z')) if 'z' not in chars else True
    assert (not match(d, 'z')) if 'z' not in chars else True


def test_deeply_nested_nfa():
    seq = [chr(65+i) for i in range(20)]
    nfa = NFA.from_charset(seq[0], universe=CodeUniverse.ascii())
    for c in seq[1:]:
        nfa = nfa.then(NFA.from_charset(c, universe=CodeUniverse.ascii()))
    assert match(nfa, ''.join(seq))
    assert not match(nfa, ''.join(seq[:-1]))

def test_recursive_nfa_star():
    nfa = NFA.from_charset('a', universe=CodeUniverse.ascii()).then(NFA.from_charset('b', universe=CodeUniverse.ascii())).star
    for n in range(0, 20, 2):
        s = ['a','b']*(n//2)
        assert match(nfa, ''.join(s))
    assert not match(nfa, 'a')
    assert not match(nfa, 'b')
    assert not match(nfa, 'aa')


# --- Enum tag, NFA over enum, DFA over enum tests ---
class Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

def test_enum_tag_nfa():
    u = CodeUniverse.enum(Color)
    nfa = NFA.from_charset([Color.RED], universe=u).tagged('red')
    assert match(nfa, [Color.RED])
    assert not match(nfa, [Color.GREEN])
    for tags in nfa.accept.values():
        assert 'red' in tags

def test_nfa_over_enum():
    u = CodeUniverse.enum(Color)
    nfa = NFA.from_charset([Color.RED], universe=u) | NFA.from_charset([Color.BLUE], universe=u)
    assert match(nfa, [Color.RED])
    assert match(nfa, [Color.BLUE])
    assert not match(nfa, [Color.GREEN])

def test_dfa_over_enum():
    u = CodeUniverse.enum(Color)
    nfa = NFA.from_charset([Color.RED], universe=u) | NFA.from_charset([Color.BLUE], universe=u)
    dfa = nfa.dfa
    m = dfa.minimize
    assert match(dfa, [Color.RED])
    assert match(m, [Color.RED])
    assert match(dfa, [Color.BLUE])
    assert match(m, [Color.BLUE])
    assert not match(dfa, [Color.GREEN])
    assert not match(m, [Color.GREEN])


def assert_both(nfa: NFA[str], dfa: DFA[str], input: str, expected: bool)->None:
    nfa2 = dfa.nfa
    nfa_result = match(nfa, input)
    dfa_result = match(dfa, input)
    nfa2_result = match(nfa2, input)
    m = dfa.minimize
    m_result = match(m, input)
    assert nfa2_result == expected, f"NFA from DFA failed on input {input}: expected {expected}, got {nfa2_result}"
    assert nfa_result == expected, f"NFA failed on input {input}: expected {expected}, got {nfa_result}"
    assert dfa_result == expected, f"DFA failed on input {input}: expected {expected}, got {dfa_result}"
    assert m_result == expected, f"Minimized DFA failed on input {input}: expected {expected}, got {m_result}"

def test_from_char()->None:
    nfa: NFA[str] = NFA.from_charset('a', universe=CodeUniverse.ascii())
    dfa = DFA.from_nfa(nfa)
    assert nfa.init in nfa.transitions
    assert_both(nfa, dfa, 'a', True)
    assert_both(nfa, dfa, 'b', False)
    assert_both(nfa, dfa, '', False)

def test_then():
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii()).then(NFA.from_charset("b", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, "ab", True)
    assert_both(nfa, dfa, "a", False)
    assert_both(nfa, dfa, "b", False)
    assert_both(nfa, dfa, "ac", False)
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii()).then(NFA.from_charset("a", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, "aa", True)
    assert_both(nfa, dfa, "ac", False)
    assert_both(nfa, dfa, "a", False)
    assert_both(nfa, dfa, '', False)
    assert_both(nfa, dfa, "b", False)
    assert_both(nfa, dfa, "ab", False)
    assert_both(nfa, dfa, "aaa", False)
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii())
    nfa = nfa.then(nfa).then(nfa)  # aaa
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, "aaa", True)
    assert_both(nfa, dfa, "aa", False)
    assert_both(nfa, dfa, "a", False)
    assert_both(nfa, dfa, '', False)
    assert_both(nfa, dfa, "b", False)
    assert_both(nfa, dfa, "ab", False)
    assert_both(nfa, dfa, "aaaa", False)

def test_or_else():
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii()).union(NFA.from_charset("b", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, "a", True)
    assert_both(nfa, dfa, "b", True)
    assert_both(nfa, dfa, "c", False)
    assert_both(nfa, dfa, '', False)

def test_optional():
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii()).optional
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, '', True)
    assert_both(nfa, dfa, "a", True)
    assert_both(nfa, dfa, "b", False)
    assert_both(nfa, dfa, "aa", False)

def test_many():
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii()).many()
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, '', False)
    assert_both(nfa, dfa, "a", True)
    assert_both(nfa, dfa, "aa", True)
    assert_both(nfa, dfa, "aaa", True)
    assert_both(nfa, dfa, "b", False)
    assert_both(nfa, dfa, "ab", False)
    assert_both(nfa, dfa, "ba", False)
    assert_both(nfa, dfa, "aab", False)
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii()).many(2, 4)
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, '', False)
    assert_both(nfa, dfa, "a", False)
    assert_both(nfa, dfa, "aa", True)
    assert_both(nfa, dfa, 'aaa', True)
    assert_both(nfa, dfa, 'aaaa', True)
    assert_both(nfa, dfa, 'aaaaa', False)
    assert_both(nfa, dfa, "b", False)
    assert_both(nfa, dfa, "ab", False)
    assert_both(nfa, dfa, 'aab', False)
    assert_both(nfa, dfa, 'aaab', False)
    assert_both(nfa, dfa, 'aaaab', False)
    assert_both(nfa, dfa, 'aaaaab', False)

def test_plus():
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii()).plus
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, "a", True)
    assert_both(nfa, dfa, "aa", True)
    assert_both(nfa, dfa, "aaa", True)
    assert_both(nfa, dfa, '', False)

def test_star():
    nfa = NFA.from_charset("a", universe=CodeUniverse.ascii()).star
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, '', True)
    assert_both(nfa, dfa, "a", True)
    assert_both(nfa, dfa, "aa", True)
    assert_both(nfa, dfa, "aaa", True)
    for bad in ["b", "ab", "ba", "aab", "baa", "aba", "bab", "bba", "bbb"]:
        assert_both(nfa, dfa, bad, False)

def test_complex()->None:
    a: NFA[str] = NFA.from_charset('a', universe=CodeUniverse.ascii())
    b: NFA[str] = NFA.from_charset('b', universe=CodeUniverse.ascii())
    c: NFA[str] = NFA.from_charset('c', universe=CodeUniverse.ascii())
    a_or_b = a.union(b)
    a_or_b_then_c = a_or_b.then(c)
    nfa = a_or_b_then_c.many(2, 4)
    dfa = DFA.from_nfa(nfa)
    assert_both(nfa, dfa, ''.join(['a', 'b', 'c', 'a', 'c']), False)
    assert_both(nfa, dfa, ''.join(['a', 'b', 'c']), False)
    assert_both(nfa, dfa, ''.join(['a', 'c', 'b', 'c', 'a', 'c']), True)
    assert_both(nfa, dfa, ''.join(['a', 'b', 'c', 'a', 'b', 'c', 'a', 'b', 'c']), False)
    assert_both(nfa, dfa, ''.join(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c']), True)
    assert_both(nfa, dfa, ''.join(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c', 'b']), False)
    assert_both(nfa, dfa, ''.join(['a', 'c', 'b', 'c', 'b', 'c', 'a', 'c', 'b', 'c']), False)
    assert_both(nfa, dfa, ''.join(['a', 'b']), False)
    assert_both(nfa, dfa, ''.join(['c']), False)
    assert_both(nfa, dfa, '', False)
    assert_both(nfa, dfa, ''.join(['a', 'c', 'b', 'c']), True)
    assert_both(nfa, dfa, ''.join(['b', 'c', 'a', 'c']), True)
    assert_both(nfa, dfa, ''.join(['a', 'c', 'a', 'c']), True)

def test_runner()->None:
    nfa: NFA[str] = NFA.from_charset("a", universe=CodeUniverse.ascii()).then(NFA.from_charset("b", universe=CodeUniverse.ascii())).then(NFA.from_charset("c", universe=CodeUniverse.ascii()))
    dfa = DFA.from_nfa(nfa)
    m = dfa.minimize
    runner = run(nfa, "abc")
    drunner = run(dfa, "abc")
    mrunner = run(m, "abc")
    assert runner.is_accepted(nfa), "nfa is not accepted"
    assert drunner.is_accepted(dfa), "dfa is not accepted"
    r1 = runner.resumable(nfa)
    dr1 = drunner.resumable(dfa)
    m1 = mrunner.resumable(m)
    assert not r1
    assert not dr1
    assert not m1
    # partial input
    runner2 = run(nfa, "ab")
    drunner2 = run(dfa, "ab")
    mrunner2 = run(m, "ab")
    assert not runner2.is_accepted(nfa)
    assert not drunner2.is_accepted(dfa)
    assert not mrunner2.is_accepted(m)
    assert runner2.resumable(nfa)
    assert drunner2.resumable(dfa)
    assert mrunner2.resumable(m)
    # longer input (extra symbol)
    runner3 = run(nfa, "abcd")
    drunner3 = run(dfa, "abcd")
    mrunner3 = run(m, "abcd")
    assert len(runner3.accepted) == 1 and runner3.accepted[0][0] == 2
    assert not runner3.is_accepted(nfa)
    assert not drunner3.is_accepted(dfa)
    assert not mrunner3.is_accepted(m)

def test_dfa_tagged():
    u = CodeUniverse.ascii()
    a = NFA.from_charset('a', universe=u).dfa
    ma = a.minimize
    tagged = a.tagged('X')
    tagged_m = ma.tagged('X')
    for tags in tagged.accept.values():
        assert 'X' in tags
    for tags in tagged_m.accept.values():
        assert 'X' in tags

def test_dfa_combinator_chain():
    u = CodeUniverse.ascii()
    a = NFA.from_charset('a', universe=u).dfa
    ma = a.minimize
    b = NFA.from_charset('b', universe=u).dfa
    mb = b.minimize
    c = NFA.from_charset('c', universe=u).dfa
    mc = c.minimize
    combo = ((a | b) & -c)
    combo_m = ((ma | mb) & -mc)
    assert match(combo_m, 'a')
    assert match(combo_m, 'b')
    assert not match(combo_m, 'c')
    assert not match(combo_m, 'ac')
    assert match(combo, 'a')
    assert match(combo, 'b')
    assert not match(combo, 'c')
    assert not match(combo, 'ac')
    # end test

# --- Additional DFA algebra tests using helper match ---
def test_dfa_combinators_basic():
    u = CodeUniverse.ascii()
    a = NFA.from_charset('a', universe=u).dfa
    ma = a.minimize
    b = NFA.from_charset('b', universe=u).dfa
    mb = b.minimize
    # complement
    not_a = -a
    not_ma = -ma
    assert not match(not_ma, 'a')
    assert match(not_ma, 'b')
    assert not match(not_a, 'a')
    assert match(not_a, 'b')
    # intersection
    ab = a & b
    abm = ma & mb
    assert not match(abm, 'a')
    assert not match(abm, 'b')
    assert not match(abm, 'ab')
    assert not match(ab, 'a')
    assert not match(ab, 'b')
    assert not match(ab, 'ab')
    # union
    a_or_b = a | b
    a_or_bm = ma | mb
    assert match(a_or_bm, 'a')
    assert match(a_or_bm, 'b')
    assert not match(a_or_bm, 'c')
    assert match(a_or_b, 'a')
    assert match(a_or_b, 'b')
    assert not match(a_or_b, 'c')
    # difference
    only_a = a - b
    only_am = ma - mb
    assert match(only_am, 'a')
    assert not match(only_am, 'b')
    assert match(only_a, 'a')
    assert not match(only_a, 'b')



def test_dead_state():
    nfa = NFA.from_charset('a', universe=CodeUniverse.ascii()).then(NFA.from_charset('b', universe=CodeUniverse.ascii()).optional)
    dfa = nfa.dfa
    m = dfa.minimize
    dead_states = [state for state, trans in dfa.transitions.items() if not trans]
    dead_states_m = [state for state, trans in m.transitions.items() if not trans]
    assert len(dead_states) <= 1
    assert len(dead_states_m) <= 1


def test_dfa_combinator_chain_again():
    # sanity duplicate-like test ensuring no accidental state sharing issues
    u = CodeUniverse.ascii()
    a = NFA.from_charset('a', universe=u).dfa
    b = NFA.from_charset('b', universe=u).dfa
    c = NFA.from_charset('c', universe=u).dfa
    combo = ((a | b) & -c)
    assert match(combo, 'a')
    assert match(combo, 'b')
    assert not match(combo, 'c')
    assert not match(combo, 'ac')


