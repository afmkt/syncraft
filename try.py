from __future__ import annotations
from syncraft.walker import walk
from syncraft.ast import TokenSpec, Nothing
from syncraft.generator import TokenGen, generate_with, generate
from syncraft.syntax import lazy, literal, token, regex
from syncraft.parser import parse
from syncraft.nfa import NFA
from rich import print




def test_from_char()->None:
    nfa = NFA.from_char("a").many(2, 4)
    print(nfa)
    assert nfa.run(["a"]) is False      # requires at least two
    assert nfa.run(["a", "a"]) is True
    assert nfa.run(["a", "a", "a"]) is True
    assert nfa.run(["a", "a", "a", "a"]) is True
    assert nfa.run(["a", "a", "a", "a", "a"]) is False # at most four
    assert nfa.run([]) is False         # requires at least two


if __name__ == "__main__":
    test_from_char()
