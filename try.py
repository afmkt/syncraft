from __future__ import annotations
from syncraft.syntax import Syntax
from dataclasses import dataclass
from typing import Any, List, Tuple
from enum import Enum
from syncraft.algebra import Error
from syncraft.generator import generate_with, generate, validate
from syncraft.parser import parse_word
from syncraft.fa import NFA, DFA, CodeUniverse
from syncraft.utils import set_debug
from syncraft.ast import TokenClass
from rich import print
set_debug(True)


literal = Syntax.config(token_class = TokenClass.simple()).literal
token = Syntax.config(token_class = TokenClass.simple()).token
lazy = Syntax.config(token_class = TokenClass.simple()).lazy



def _normalize_input(inp):
    if isinstance(inp, (str, bytes)):
        return inp
    return list(inp)

@dataclass
class LegacyRun:
    _runner: Any
    accepted: List[Tuple[int, Tuple[Enum | str, ...]]]
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
    accepted: list[tuple[int, tuple[Enum | str, ...]]] = []
    for i, sym in enumerate(seq):
        rr = runner.step(sym, i)
        runner = rr.runner
        if runner.is_accepted():
            # store sorted tags for determinism
            accepted.append((i, tuple(sorted(runner.tags(), key=str))))

    return LegacyRun(runner, accepted)

def match(fa: NFA | DFA, inp) -> bool:
    return run(fa, inp).is_accepted(fa)




class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

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

def test_gen():
    import random as _random
    a = NFA.from_charset('a', universe=CodeUniverse.ascii())
    b = NFA.from_charset('b', universe=CodeUniverse.ascii())
    c = NFA.from_charset('c', universe=CodeUniverse.ascii())
    nfa = a >> b >> c
    dfa = nfa.dfa
    m = dfa.minimize
    r = nfa.runner()
    dr = dfa.runner()
    mr = m.runner()

    def collect_samples(runner, count=3):
        out = []
        for _ in range(count):
            sample = runner.gen(_random.Random())
            if sample is not None:
                out.append(sample)
        return out

    from_r = collect_samples(r)
    from_dr = collect_samples(dr)
    from_mr = collect_samples(mr)

    assert from_r, "Expected at least one generated sample for NFA"
    assert from_dr, "Expected at least one generated sample for DFA"
    assert from_mr, "Expected at least one generated sample for minimized DFA"

    assert all(match(nfa, s) for s, _ in from_r)
    assert all(match(dfa, s) for s, _ in from_dr)
    assert all(match(m, s) for s, _ in from_mr)


def tok(text: str):
    return Syntax.token(token_class=TokenClass.simple(), text=text, case_sensitive=True)


def test_mutual_left_recursion_with_base_after_bimap_A():
    # Grammar: A := (A + 'b') | 'a'  and  B := (B + 'a') | 'b' would not alternate as intended.
    # Use standard mutual LR with base on each:
    #   A := (B + 'a') | 'a'
    #   B := (A + 'b') | 'b'
    A = Syntax.lazy(lambda: (B + tok('a')) | tok('a'))  # type: ignore[name-defined]
    B = Syntax.lazy(lambda: (A + tok('b')) | tok('b'))  # type: ignore[name-defined]

    # Parse a sequence that fits A: 'a b a' via A -> B + 'a', B -> A + 'b', A -> 'a'
    ast, _ = parse_word(A, 'a b a')
    assert not isinstance(ast, Error)

    x, invf = ast.bimap()
    reconstructed = invf(x)

    v1, b1 = validate(A, reconstructed)
    print(v1, b1)
    assert not isinstance(v1, Error)
    assert b1 is not None

    v2, b2 = generate_with(A, reconstructed)
    assert not isinstance(v2, Error)
    assert b2 is not None



if __name__ == "__main__":
    test_mutual_left_recursion_with_base_after_bimap_A()
