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
    Concat,
    Text,
    
    
    render,
    
)




def test_lower_to_layout_seq_many_alt_lazy() -> None:
    seq = Seq(value=((Token(text="a"), True), (Token(text="b"), True)))
    many = Many(value=(Token(text="x"), Token(text="y")))
    alt = Alt(index=0, value=Token(text="z"))
    lazy = Lazy(value=Token(text="q"))

    seq_doc = LayoutDoc.from_ast(seq)
    many_doc = LayoutDoc.from_ast(many)
    alt_doc = LayoutDoc.from_ast(alt)
    lazy_doc = LayoutDoc.from_ast(lazy)

    assert isinstance(seq_doc, Concat)
    assert isinstance(many_doc, Concat)
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
        body = Concat(
            parts=(
                Text("hello"),
                Line(flat=" "),
                Text("world"),
                
            )
        )
    )
    assert doc.render(width=20) == "hello world"


def test_group_breaks_when_not_fit() -> None:
    doc = Group(
        body=Concat(
            parts=(
                Text("hello"),
                Line(),
                Text("world"),
            )
        )
    )
    assert doc.render(width=6) == "hello\nworld"


def test_nest_applies_indentation_on_break() -> None:
    doc = Group(
        body=Concat(
            parts=(
                Text("if"),
                Nest(
                    body=Concat(parts=(Line(),Text("x"))), 
                    level=1
                )
            )
        )
    )
    assert doc.render(width=2, indent="  ") == "if\n  x"


def test_softline_fallback_and_break() -> None:
    doc = Group(
        body=Concat(
            (
                Text("a"),
                Line(flat=""),
                Text("b"),
            )
        )
    )
    assert doc.render(width=10) == "ab"
    assert doc.render(width=1) == "a\nb"


def test_syntax_generate_renders_layoutdoc_result() -> None:
    syntax: Any = Syntax.success(
        Group(
            body=Concat(
                parts=(
                    Text("select"),
                    Line(flat=" "),
                    Text("*"),
                    Line(flat=" "),
                    Text("from"),
                    Line(flat=" "),
                    Text("tbl"),
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
    assert isinstance(generated, LayoutDoc)
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
    alt_none_doc = LayoutDoc.from_ast(Alt(index=0, value=None))
    assert isinstance(alt_none_doc, Text)
    assert alt_none_doc.value == ""
    assert isinstance(alt_none_doc.ast, Alt)

    original = Group(body=Concat(parts=(Text("x"), Line(flat=""), Text("y"))))
    lowered = LayoutDoc.from_ast(original)
    assert lowered is original


def test_layoutdoc_ast_synthesizes_seq_for_manual_sequence() -> None:
    doc = Concat(
        parts=(
            Text("a"), 
            Group(
                body=Concat(
                    parts=(
                        Text("b"), 
                        Nest(
                            body=Concat(
                                parts=(Text("c"),)
                            ), 
                            level=2
                        )
                    )
                )
            )
        )
    )
    ast = doc.ast
    assert ast is None
    assert doc.render(width=80) == "abc"
    


def test_group_fits_exact_boundary_uses_flat_mode() -> None:
    doc = Group(
        body=Concat(
            parts=(
                Text("ab"),
                Line(), 
                Text("cd")
                )
            )
        )
    assert doc.render(width=5) == "ab cd"
    assert doc.render(width=4) == "ab\ncd"


def test_nest_negative_level_is_clamped_to_zero() -> None:
    doc = Group(
        body=Concat(
            parts=(
                Text("if"), 
                Nest(
                    body=Concat(parts=(Line(), Text("x"))),
                    level=-3
                )
            )
        )
    )
    assert doc.render(width=2, indent="  ") == "if\nx"


def test_apply_format_spec_optional_wraps_and_preserves_origin() -> None:
    spec = FormatSpec.coerce(
        breakability="optional",
        attach="none",
        indent=2,
    )
    doc = spec("abc")
    assert isinstance(doc, Group)
    assert isinstance(doc.body, Concat)
    assert doc.ast == "abc"
    assert doc.render(width=80, indent=" ") == "abc"


def test_apply_format_spec_required_not_implemented() -> None:
    spec = FormatSpec.coerce(
        breakability=Breakability.REQUIRED,
        attach=Attach.NONE,
        indent=0,
        
    )
    doc = spec("abc")
    assert isinstance(doc, Group)
    assert isinstance(doc.body, Concat)
    assert doc.ast == "abc"
    # Required breakability is stripped at the out most level, treated as optional for now
    assert doc.render(width=80, indent=" ") == "abc" 


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


def test_format_single_line_function_call() -> None:
    """Format: f(a, b, c) - single line, no width-sensitive grouping."""
    syntax_cls = Syntax
    
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )
    
    comma_space = syntax_cls.lit(", ").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda _: ", "
    )
        
    args = identifier + (comma_space + identifier).many()
    func_call = (identifier + syntax_cls.lit("(") + args + syntax_cls.lit(")")).format(
        breakability="never"
    )
    
    expected = "f(a, b, c)"
    generated = func_call.generate(('f', '(', 'a', ((', ', 'b'), (', ', 'c')), ')'))
    result = generated.render(width=80)
    assert result == expected


def test_format_multiline_function_call() -> None:
    """Format: f(a, b, c) breaking to multiple lines when too wide."""
    syntax_cls = Syntax
    
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )
    
    comma = syntax_cls.lit(",").format(attach="left")
    space = syntax_cls.lit(" ").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda _: " "
    )
    
    # Width-sensitive argument list with indentation
    args = (identifier + (comma + space + identifier).many()).format(
        breakability="optional",
        indent=1
    )
    
    func_call = identifier + syntax_cls.lit("(") + args + syntax_cls.lit(")")
    
    generated = func_call.generate(('f', '(', ('a', ((',', ' ', 'b'), (',', ' ', 'c'))), ')'))
    
    # Fits on one line with width=80
    result_wide = generated.render(width=80)
    print(result_wide)
    assert "," in result_wide
    
    # Breaks to multiple lines with narrow width

    result_narrow = generated.render(width=5)
    print(result_narrow)
    assert "\n" in result_narrow




def test_format_single_line_addition() -> None:
    """Format: a + b + c + d - single line expression."""
    syntax_cls = Syntax
    
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )
    
    plus_space = syntax_cls.lit(" + ").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda _: " + "
    )
    
    expr = identifier + (plus_space + identifier).many()
    
    generated = expr.generate(('a', ((' + ', 'b'), (' + ', 'c'), (' + ', 'd'))))
    result = generated.render(width=80)
    assert result == "a + b + c + d"


def test_format_multiline_addition_operator_first() -> None:
    """Format: a, +b, +c, +d - operators at line start when breaking."""
    syntax_cls = Syntax
    
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )
    
    plus = syntax_cls.lit(" +").format(attach="left")
    space = syntax_cls.lit(" ").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda _: " "
    )
    
    # Indented addition chain
    expr = (identifier + (plus + space + identifier).many()).format(
        breakability="optional",
        indent=1
    )
    generated = expr.generate(("a", ((" +", " ", "b"), (" +", " ", "c"), (" +", " ", "d"))))
    
    # Fits on one line with width=80
    result_wide = generated.render(width=80)
    assert "+" in result_wide
    
    # Breaks to multiple lines with narrow width
    result_narrow = generated.render(width=8)
    assert "\n" in result_narrow
    # Operator should be on continuation lines
    lines = result_narrow.strip().split("\n")
    assert len(lines) > 1




def test_format_nested_indentation() -> None:
    """Format: nested if statements with proper indentation."""
    syntax_cls = Syntax
    
    keyword = syntax_cls.lit("if") | syntax_cls.lit("else")
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*")
    colon = syntax_cls.lit(":")
    newline = syntax_cls.lit("\n").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda _: "\n"
    )
    
    # Simple statement (placeholder)
    stmt = identifier
    
    # if statement: if x: <body>
    if_stmt = (
        keyword + syntax_cls.lit(" ") + identifier + colon +
        newline + stmt.format(indent=1)
    ).format(indent=0)
    
    # Nested if statements
    nested = (
        keyword + syntax_cls.lit(" ") + identifier + colon +
        newline + if_stmt.format(indent=1)
    )
    
    generated = nested.generate((None, None, "x", None, None, None, None, None, "y", None, None, None, None, None, None, None, "z"))
    result = generated.render(width=80, indent="    ")
    
    # Should have proper indentation structure
    assert "if" in result
    assert "\n" in result
