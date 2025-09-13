from __future__ import annotations
from syncraft.ast import TokenClass
from syncraft.fa import NFA, DFA, CodeUniverse
from rich import print
from syncraft.syntax import Syntax
literal = Syntax.config(TokenClass.simple()).literal


def test_charset_invalid_length_error() -> None:
    u:CodeUniverse[str] = CodeUniverse.ascii()
    a: DFA[str] = NFA.from_char('a', universe=u).dfa
    b: DFA[str] = NFA.from_char('b', universe=u).dfa
    # union
    a_or_b = a | b
    print('DFA a transitions:', a.transitions)
    print('DFA a accept:', a.accept)
    print('DFA b transitions:', b.transitions)
    print('DFA b accept:', b.accept)
    print('DFA a|b transitions:', a_or_b.transitions)
    print('DFA a|b accept:', a_or_b.accept)
    assert a_or_b.match(['a'])
    assert a_or_b.match(['b'])
    assert not a_or_b.match(['c'])

if __name__ == "__main__":
    test_charset_invalid_length_error()
