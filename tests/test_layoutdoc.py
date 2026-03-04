from __future__ import annotations

from syncraft.ast import Alt, Lazy, Many, Seq, Token, Unknown
from syncraft.format import Group, Line, Nest, Sequence, SoftLine, Text, lower_to_layout, render, text_of


def test_text_of_terminals() -> None:
    assert text_of("abc") == "abc"
    assert text_of(b"abc") == "abc"
    assert text_of(Token(text="x")) == "x"
    assert text_of(Token(text=("a", "b", "c"))) == "abc"
    assert text_of(("a", b"b", 3)) == "ab3"
    assert text_of(Unknown()) == ""


def test_lower_to_layout_seq_many_alt_lazy() -> None:
    seq = Seq(value=((Token(text="a"), True), (Token(text="b"), True)))
    many = Many(value=(Token(text="x"), Token(text="y")))
    alt = Alt(index=0, value=Token(text="z"))
    lazy = Lazy(value=Token(text="q"))

    seq_doc = lower_to_layout(seq)
    many_doc = lower_to_layout(many)
    alt_doc = lower_to_layout(alt)
    lazy_doc = lower_to_layout(lazy)

    assert isinstance(seq_doc, Sequence)
    assert isinstance(many_doc, Sequence)
    assert isinstance(alt_doc, Text)
    assert isinstance(lazy_doc, Text)

    assert render(seq_doc) == "ab"
    assert render(many_doc) == "xy"
    assert render(alt_doc) == "z"
    assert render(lazy_doc) == "q"


def test_group_prefers_flat_when_fits() -> None:
    doc = Group(
        Sequence(
            (
                Text("hello"),
                Line(Text("world"), fallback=" "),
            )
        )
    )
    assert doc.render(width=20) == "hello world"


def test_group_breaks_when_not_fit() -> None:
    doc = Group(
        Sequence(
            (
                Text("hello"),
                Line(Text("world"), fallback=" "),
            )
        )
    )
    assert doc.render(width=6) == "hello\nworld"


def test_nest_applies_indentation_on_break() -> None:
    doc = Group(
        Sequence(
            (
                Text("if"),
                Nest(Line(Text("x"), fallback=" "), level=1),
            )
        )
    )
    assert doc.render(width=2, indent="  ") == "if\n  x"


def test_softline_fallback_and_break() -> None:
    doc = Group(
        Sequence(
            (
                Text("a"),
                SoftLine(Text("b"), fallback=""),
            )
        )
    )
    assert doc.render(width=10) == "ab"
    assert doc.render(width=1) == "a\nb"
