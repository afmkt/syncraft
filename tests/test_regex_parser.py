from __future__ import annotations

from typing import Any

from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder
from syncraft.regex import (
    Alternation,
    CharClass,
    Concat,
    Literal,
    Quantifier,
    Repeat,
    compile_regex,
    parse_regex,
)


def _matches(builder: FABuilder[str], text: str) -> bool:
    universe: CodeUniverse[str] = CodeUniverse.ascii()
    fa = builder.compile(universe).dfa
    runner: Any = fa.runner()
    for index, ch in enumerate(text):
        step = runner.step(ch, index)
        runner = step.runner
    return runner.is_accepted()


def test_compile_regex_literal_sequence() -> None:
    builder = compile_regex("abc")
    assert _matches(builder, "abc")
    assert not _matches(builder, "ab")


def test_compile_regex_alternation() -> None:
    builder = compile_regex("a|bc")
    assert _matches(builder, "a")
    assert _matches(builder, "bc")
    assert not _matches(builder, "b")


def test_compile_regex_quantifiers() -> None:
    builder = compile_regex("ab*c")
    assert _matches(builder, "ac")
    assert _matches(builder, "abc")
    assert _matches(builder, "abbbc")
    assert not _matches(builder, "abb")


def test_compile_regex_bounded_quantifier() -> None:
    builder = compile_regex("a{2,3}")
    assert _matches(builder, "aa")
    assert _matches(builder, "aaa")
    assert not _matches(builder, "a")
    assert not _matches(builder, "aaaa")


def test_compile_regex_char_class() -> None:
    builder = compile_regex("[a-c]+d")
    assert _matches(builder, "ad")
    assert _matches(builder, "bbcd")
    assert not _matches(builder, "ed")


def test_compile_regex_escaped_literal() -> None:
    builder = compile_regex("\\?")
    assert _matches(builder, "?")
    assert not _matches(builder, "q")


def test_parse_regex_ast_shapes() -> None:
    expr = parse_regex("(ab|c)+")
    assert isinstance(expr, Repeat)
    assert expr.quant == Quantifier(1, None)
    assert isinstance(expr.expr, Alternation)
    assert len(expr.expr.options) == 2
    concat = expr.expr.options[0]
    assert isinstance(concat, Concat)
    assert all(isinstance(part, Literal) for part in concat.parts)
    assert isinstance(expr.expr.options[1], Literal)


def test_parse_regex_char_class_ast() -> None:
    expr = parse_regex("[^a-c]")
    assert isinstance(expr, CharClass)
    assert expr.negated is True
    assert expr.ranges[0] == ("a", "c")
