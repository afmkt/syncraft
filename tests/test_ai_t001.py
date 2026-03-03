from __future__ import annotations

from syncraft import Grammar, Syntax, grammar, rule
from syncraft.parser import parse_string

S = Syntax.set()


def build_t001_rp():
    number = S.rp(r"[0-9]+").map(int)
    comma = S.rp(r"\s*,\s*")
    return number.sep_by(comma)


@grammar
class T001Grammar(Grammar):
    number = S.rp(r"[0-9]+").map(int)
    comma = S.rp(r"\s*,\s*")
    root = rule(number.sep_by(comma), is_root=True)


def test_t001_number_list_rp() -> None:
    syntax = build_t001_rp()
    assert parse_string(syntax, "1,2,3") == (1, 2, 3)
    assert parse_string(syntax, "10, 20, 30") == (10, 20, 30)


def test_t001_number_list_grammar() -> None:
    assert T001Grammar.parse("1,2,3") == (1, 2, 3)
    assert T001Grammar.parse("10, 20, 30") == (10, 20, 30)
