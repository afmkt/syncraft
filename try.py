from __future__ import annotations

from typing import Iterable

from syncraft.alphabet import Alphabet
from syncraft.fa import DFA, NFA
from syncraft.regex import Regex, parse
from rich import print

def _build(pattern: str):
    parsed = parse(pattern)
    assert isinstance(parsed, Regex), f"Parse failed for {pattern!r}: {parsed!r}"
    print(parsed)
    return parsed.builder()


def _match(builder, text: str) -> bool:
    alphabet = Alphabet(str)
    fa = builder.compile(alphabet)
    dfa = fa.dfa
    runner = dfa.runner()
    for i, ch in enumerate(text):
        runner.step(ch, i)
    return runner.is_accepted()


def _assert_matches(builder, good: Iterable[str], bad: Iterable[str]) -> None:
    for text in good:
        assert _match(builder, text), f"Expected match: {text!r}"
    for text in bad:
        assert not _match(builder, text), f"Expected no match: {text!r}"





def test_regex_builder_word_and_space_shorthands() -> None:
    builder = _build(r"\w+\s+\w+")
    _assert_matches(builder, ["a b", "foo\tbar"], ["a", "a  ", "- -"])


if __name__ == "__main__":
    
    
    test_regex_builder_word_and_space_shorthands()
    print("All tests passed!")