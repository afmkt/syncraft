from __future__ import annotations

from typing import Iterable
import random
import re
import pytest

from syncraft.alphabet import Alphabet
from syncraft.fa import DFA, NFA
from syncraft.regex import Regex, parse, rstr, match


def _build(pattern: str):
    parsed = parse(pattern)
    assert isinstance(parsed, Regex), f"Parse failed for {pattern!r}: {parsed!r}"
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


def test_regex_builder_literals_and_concat() -> None:
    builder = _build("abc")
    _assert_matches(builder, ["abc"], ["", "ab", "abcd", "xbc"])


def test_regex_builder_alternation_and_grouping() -> None:
    builder = _build("(ab|cd)+")
    _assert_matches(builder, ["ab", "cd", "abcd"], ["", "a", "ac", "abccd"])


def test_regex_builder_quantifiers() -> None:
    builder = _build("ab{2,3}")
    _assert_matches(builder, ["abb", "abbb"], ["ab", "abbbb", "a"])


def test_regex_builder_char_class_ranges() -> None:
    builder = _build("[a-c]+")
    _assert_matches(builder, ["a", "abc", "cba"], ["", "d", "abxd"])


def test_regex_builder_negated_char_class() -> None:
    builder = _build("[^a]+")
    _assert_matches(builder, ["b", "xyz"], ["", "a", "ba"])


def test_regex_builder_dot() -> None:
    builder = _build("a.c")
    _assert_matches(builder, ["abc", "a c"], ["ac", "abdc"])


def test_regex_builder_shorthand_digit() -> None:
    builder = _build(r"\d+")
    _assert_matches(builder, ["0", "123"], ["", "a1", "x"])


def test_regex_builder_optional_and_star() -> None:
    builder = _build("ab?c*")
    _assert_matches(builder, ["a", "ab", "ac", "abccc"], ["", "b", "abb"])


def test_regex_builder_word_and_space_shorthands() -> None:
    builder = _build(r"\w+\s+\w+")
    _assert_matches(builder, ["a b", "foo\tbar"], ["a", "a  ", "- -"])


def test_regex_builder_unicode_category() -> None:
    builder = _build(r"\p{Lu}+")
    _assert_matches(builder, ["A", "AZ"], ["", "a", "Aa"])


def test_regex_builder_class_escaped_chars() -> None:
    builder = _build(r"[\[\]\\-]+")
    _assert_matches(builder, ["[]", "[\\-]"], ["a", "[]a"])


def test_regex_builder_class_shorthand_items() -> None:
    builder = _build(r"[\w\d]+")
    _assert_matches(builder, ["abc_123"], ["-", " "])


def test_regex_builder_case_insensitive_literals() -> None:
    builder = _build(r"(?i:AbC)")
    _assert_matches(builder, ["abc", "ABC", "aBc"], ["ab", "abcd", "abx"])


def test_regex_builder_case_insensitive_char_class_range() -> None:
    builder = _build(r"(?i:[a-c]+)")
    _assert_matches(builder, ["A", "bC", "cBA"], ["", "d", "abx"])


def test_regex_builder_case_insensitive_class_literal() -> None:
    builder = _build(r"(?i:[xZ]+)")
    _assert_matches(builder, ["x", "X", "z", "Z"], ["a", "xzA"])


def test_regex_builder_case_insensitive_unicode_category_noop() -> None:
    builder = _build(r"(?i:\p{Lu}+)")
    _assert_matches(builder, ["A", "AZ"], ["", "a", "Aa"])


def test_regex_rstr_generates_matching_text() -> None:
    pattern = r"(ab|cd)+\d{2}"
    generator = rstr(pattern, rnd=random.Random(0))
    sample = generator()
    assert _match(_build(pattern), sample)


def test_regex_rstr_accepts_compiled_pattern() -> None:
    compiled = re.compile(r"[A-C]{3}")
    generator = rstr(compiled, seed=1)
    sample = generator()
    assert compiled.fullmatch(sample) is not None


def test_regex_rstr_rejects_seed_and_rng_together() -> None:
    with pytest.raises(ValueError):
        rstr(r"abc", rnd=random.Random(0), seed=0)


def test_match_function() -> None:
    pattern = r"foo\d+"
    matcher = match(pattern)
    assert matcher("foo123")


def test_match_function_ci() -> None:
    pattern = r"foo\d+"
    matcher_ci = match(pattern, case_insensitive=True)
    assert matcher_ci("FOO456")
    assert not matcher_ci("BAR123")

def test_match_function_fullmatch() -> None:
    pattern = r"foo\d+"
    matcher_full = match(pattern, fullmatch=True)
    assert not matcher_full("foo789x")
    assert matcher_full("foo789")
    
