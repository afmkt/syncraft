from __future__ import annotations

from syncraft import Grammar, Syntax, grammar, rule
from syncraft.parser import parse_string

S = Syntax.set()


def build_t003_rp():
    key = S.rp(r'"[^"]*"')
    value = S.rp(r"[0-9]+|\"[^\"]*\"|null|true|false")
    pair = S.rp(r"(?&key)\s*:\s*(?&val)", key=key, val=value)
    pairs = pair.sep_by(S.rp(r"\s*,\s*"))
    return S.rp(r"\{\s*") >> pairs // S.rp(r"\s*\}")


@grammar
class T003Grammar(Grammar):
    key = S.rp(r'"[^"]*"')
    value = S.rp(r"[0-9]+|\"[^\"]*\"|null|true|false")
    pair = S.rp(r"(?&key)\s*:\s*(?&val)", key=key, val=value)
    pairs = pair.sep_by(S.rp(r"\s*,\s*"))
    root = rule(S.rp(r"\{\s*") >> pairs // S.rp(r"\s*\}"), is_root=True)


def test_t003_json_like_object_rp() -> None:
    syntax = build_t003_rp()
    result = parse_string(syntax, '{"a": 1, "b": 2}')
    assert len(result) == 2


def test_t003_json_like_object_grammar() -> None:
    result = T003Grammar.parse('{"a": 1, "b": 2}')
    assert len(result) == 2
