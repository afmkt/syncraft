from __future__ import annotations
from typing import Any
import re
from syncraft.syntax import Syntax
from syncraft.ast import Alt, Lazy, Many, Seq, Token, Unknown
from syncraft.parser import parse_word
import pytest

from syncraft.format import (
    
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



def test_syntax_format_is_disabled_in_parse_and_validate() -> None:
    """Format spec is intentionally disabled in parse and validation paths.
    
    Only generation applies formatting transformations. Parse, validation, and
    replay use the raw algebra without fmt/map, preserving structural round-trip
    integrity.
    """
    syntax: Any = Syntax.success("abc").format(breakability="optional")

    # Parse path skips formatting (fmt is disabled in Parser.disabled)
    parsed = syntax.parse("ignored")
    assert parsed == "abc"

    # Validation path also skips formatting (fmt is disabled in Validator.disabled)
    validation_result = syntax.validate("abc")
    assert validation_result is True


def test_format_spec_validation_errors() -> None:
    with pytest.raises(ValueError, match="Invalid breakability"):
        FormatSpec.coerce(
            breakability="sometimes",
            attach="none",
            indent=0,
            
        )

    with pytest.raises(ValueError, match="indent must be >= 0"):
        Syntax.success("abc").format(indent=-1)


def test_lower_to_layout_alt_none_and_layoutdoc_passthrough() -> None:
    alt_none_doc = lower_to_layout(Alt(index=0, value=None))
    assert isinstance(alt_none_doc, Text)
    assert alt_none_doc.value == ""
    assert isinstance(alt_none_doc.ast, Alt)

    original = Group(Sequence((Text("x"), SoftLine(Text("y"), fallback=""))))
    lowered = lower_to_layout(original)
    assert lowered is original


def test_layoutdoc_ast_synthesizes_seq_for_manual_sequence() -> None:
    doc = Sequence((Text("a"), Group(Text("b")), Nest(Text("c"), level=2)))
    ast = doc.ast

    assert isinstance(ast, Seq)
    assert ast.value == (("a", True), ("b", True), ("c", True))


def test_group_fits_exact_boundary_uses_flat_mode() -> None:
    doc = Group(Sequence((Text("ab"), Line(Text("cd"), fallback=" "))))
    assert doc.render(width=5) == "ab cd"
    assert doc.render(width=4) == "ab\ncd"


def test_nest_negative_level_is_clamped_to_zero() -> None:
    doc = Group(Sequence((Text("if"), Nest(Line(Text("x"), fallback=" "), level=-3))))
    assert doc.render(width=2, indent="  ") == "if\nx"


def test_apply_format_spec_optional_wraps_and_preserves_origin() -> None:
    spec = FormatSpec.coerce(
        breakability="optional",
        attach="none",
        indent=2,
    )
    doc = spec("abc")

    assert isinstance(doc, Group)
    assert isinstance(doc.body, Nest)
    assert doc.ast == "abc"
    assert doc.render(width=80, indent=" ") == "abc"


def test_apply_format_spec_required_not_implemented() -> None:
    spec = FormatSpec.coerce(
        breakability=Breakability.REQUIRED,
        attach=Attach.NONE,
        indent=0,
        
    )
    with pytest.raises(ValueError, match="not implemented"):
        spec("abc")


def test_format_spec_additional_validation_errors() -> None:
    with pytest.raises(ValueError, match="Invalid attach"):
        FormatSpec.coerce(
            breakability="never",
            attach="middle",
            indent=0,
            
        )


def test_render_function_accepts_ast_values() -> None:
    value = Seq(value=((Token(text="a"), True), (Token(text="b"), True)))
    assert render(value, width=80) == "ab"


def test_expression_grammar_integration_with_format_hints_and_rendered_text() -> None:
    """Format hints at grammar level control breakability metadata.
    
    Apply .format() to mark structural decisions. The layout layer composes
    the result based on these hints, not custom callbacks. Spacing must be
    explicit in the grammar—format hints control breaks, not spacing.
    """
    expression_syntax = Syntax.set(terminal_constructor=Token)

    number = expression_syntax.tok(text=re.compile(r"\d+")).bimap(
        lambda token: token.text,
        lambda text: Token(text=text),
    )

    # Operator is marked as optional breakpoint
    plus = expression_syntax.tok(text="+").bimap(
        lambda token: token.text,
        lambda text: Token(text=text),
    ).format(
        attach="both",
        breakability="optional",
    )

    # Sequence: without spacing rule in grammar, renders as "12+345"
    expr = (number + plus + number).format(
        breakability="optional",
        indent=1
    )

    parsed = parse_word(expr, "12 + 345")
    assert parsed == ("12", "+", "345")

    generated = expr.generate(parsed, seed=0)
    # Format hints are applied during generation, spacing from grammar (none here)
    result = generated.render(width=80, indent="  ")
    # Without explicit spacing grammar, operator directly adjoins operands
    assert result == "12+345"
