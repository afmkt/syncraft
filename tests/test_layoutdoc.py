from __future__ import annotations
from typing import Any
from syncraft.syntax import Syntax
from syncraft.ast import Alt, Lazy, Many, Seq, Token, Unknown
import pytest

from syncraft.format import (
    Annotated,
    Attach,
    Breakability,
    FormatSpec,
    LayoutDoc,
    Group,
    Line,
    Nest,
    Sequence,
    SoftLine,
    Text,
    lower_to_layout,
    render,
    text_of,
)


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

    assert seq_doc.ast == seq
    assert many_doc.ast == many
    assert alt_doc.ast == alt
    assert lazy_doc.ast == lazy


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


def test_syntax_generate_renders_layoutdoc_result() -> None:
    syntax: Any = Syntax.success(
        Group(
            Sequence(
                (
                    Text("select"),
                    Line(Text("*"), fallback=" "),
                    Line(Text("from"), fallback=" "),
                    Line(Text("tbl"), fallback=" "),
                )
            )
        )
    )

    generated = syntax.generate(data=None, seed=0)
    assert isinstance(generated, LayoutDoc)
    assert generated.render(width=80) == "select * from tbl"


def test_syntax_generate_wraps_non_layoutdoc_in_default_group() -> None:
    syntax: Any = Syntax.success("abc")

    generated = syntax.generate(data=None, seed=0)
    assert isinstance(generated, Group)
    assert generated.render(width=80) == "abc"
    assert generated.ast == "abc"


def test_syntax_format_generates_annotated_layoutdoc() -> None:
    syntax: Any = Syntax.success("abc").format(
        kind="token",
        role="value",
        breakability="optional",
        attach="right",
        indent=1,
        precedence=10,
        attrs={"x": 1},
    )

    generated = syntax.generate(data=None, seed=0)
    assert isinstance(generated, Annotated)
    assert generated.render(width=80) == "abc"
    assert generated.spec.kind == "token"
    assert generated.spec.role == "value"
    assert generated.spec.breakability is Breakability.OPTIONAL
    assert generated.spec.attach is Attach.RIGHT
    assert generated.spec.indent == 1
    assert generated.spec.precedence == 10
    assert dict(generated.spec.attrs) == {"x": 1}


def test_syntax_format_is_disabled_in_parse_and_validate() -> None:
    """Format spec is intentionally disabled in parse and validation paths.
    
    Only generation applies formatting transformations. Parse, validation, and
    replay use the raw algebra without fmt/map, preserving structural round-trip
    integrity.
    """
    syntax: Any = Syntax.success("abc").format(kind="token", breakability="optional")

    # Parse path skips formatting (fmt is disabled in Parser.disabled)
    parsed = syntax.parse("ignored")
    assert parsed == "abc"

    # Validation path also skips formatting (fmt is disabled in Validator.disabled)
    validation_result = syntax.validate("abc")
    assert validation_result is True


def test_format_spec_validation_errors() -> None:
    with pytest.raises(ValueError, match="Invalid breakability"):
        FormatSpec.coerce(
            kind=None,
            role=None,
            breakability="sometimes",
            attach="none",
            indent=0,
            precedence=None,
            attrs=None,
        )

    with pytest.raises(ValueError, match="indent must be >= 0"):
        Syntax.success("abc").format(indent=-1)
