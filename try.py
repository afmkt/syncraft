from __future__ import annotations
from syncraft.walker import walk
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with, generate
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
from syncraft.nfa import NFA
from syncraft.constraint import FrozenDict
from rich import print




def test_from_char()->None:
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


if __name__ == "__main__":
    test_from_char()
