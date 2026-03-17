from __future__ import annotations
from typing import Any
import re
from syncraft.syntax import Syntax
from syncraft.ast import Alt, Lazy, Many, Seq, Token, Unknown
from syncraft.parser import parse_word
import pytest

from syncraft.format import (
    construct_templated_text,
    LayoutDoc,
    Group,
    Concat,
    Text    
)

def render(value: Any | LayoutDoc | Any, *, width: int = 80, indent: str = "    ") -> str:
    """Render a value to text through the LayoutDoc domain.

    Accepts either an existing LayoutDoc or AST-like values and lowers them
    using the default safe lowering strategy.
    """
    doc = LayoutDoc.from_ast(value)
    return doc.render(width=width)



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
                (Text(value="hello"), True),
                (Text(value="world"), True),
            ),
            flat=construct_templated_text("{0}{@opt}{f? }{1}", is_broken=False),
            broken=construct_templated_text("{0}{@opt}{f? }{1}", is_broken=True)
        )
    )
    txt = doc.render(width=20)
    print(f"Rendered text: {repr(txt)}")
    assert txt == "hello world"


def test_group_breaks_when_not_fit() -> None:
    doc = Group(
        body=Concat(
            parts=(
                (Text(value="hello"), True),
                (Text(value="world"), True),                
            ),
            flat=construct_templated_text("{0}{@opt}{1}", is_broken=False),
            broken=construct_templated_text("{0}{@opt}{1}", is_broken=True)

        )
    )
    
    tmp = doc.render(width=6)
    assert tmp == "hello\nworld"


def test_nest_applies_indentation_on_break() -> None:
    doc = Group(
        body=Concat(
            parts=(
                (Text(value="if"), True),
                (Group(
                    body=Concat(parts=((Text(value="x"), True),)), 
                    indent=2
                ), True)
            ),
            flat=construct_templated_text("{0}{@opt}{b? }{1}", is_broken=False),
            broken=construct_templated_text("{0}{@opt}{b? }{1}", is_broken=True)
        )
    )
    txt = doc.render(width=2)
    print(f"Rendered text:\n{repr(txt)}")
    assert txt == "if\n x"


def test_softline_fallback_and_break() -> None:
    doc = Group(
        body=Concat(
            parts=(
                (Text(value="a"), True),
                (Text(value="b"), True),
            ), 
            flat=construct_templated_text("{0}{@opt}{f? }{1}", is_broken=False),
            broken=construct_templated_text("{0}{@opt}{f? }{1}", is_broken=True)
        )
    )
    assert doc.render(width=10) == "a b"
    tmp = doc.render(width=1)
    print(f"Rendered text with width=1:\n{repr(tmp)}")
    assert tmp == "a\nb"


def test_syntax_generate_renders_layoutdoc_result() -> None:
    syntax: Any = Syntax.success(
        Group(
            body=Concat(
                parts=(
                    (Text(value="select"), True),
                    
                    (Text(value="*"), True),
                    
                    (Text(value="from"), True),
                    
                    (Text(value="tbl"), True),
                ),
                flat=construct_templated_text("{0}{@opt}{f? }{1}{@opt}{f? }{2}{@opt}{f? }{3}", is_broken=False),
                broken=construct_templated_text("{0}{@opt}{f? }{1}{@opt}{f? }{2}{@opt}{f? }{3}", is_broken=True),
            )
        )
    )

    generated = syntax.generate(data=None, seed=0)
    assert isinstance(generated, LayoutDoc)
    tmp = generated.render(width=80)
    print(f"Rendered text:\n{repr(tmp)}")
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
    syntax: Any = Syntax.success("abc").format("{0}{@opt}")

    # Parse path skips formatting (fmt is disabled in Parser.disabled)
    parsed = syntax.parse("ignored")
    assert parsed == "abc"

    # Validation path also skips formatting (fmt is disabled in Validator.disabled)
    validation_result = syntax.validate("abc")
    assert validation_result is True





def test_lower_to_layout_alt_none_and_layoutdoc_passthrough() -> None:
    alt_none_doc = LayoutDoc.from_ast(Alt(index=0, value=None))
    assert isinstance(alt_none_doc, Text)
    assert alt_none_doc.value == ""
    assert isinstance(alt_none_doc.ast, Alt)

    original = Group(body=Concat(parts=((Text(value="x"), True), (Text(value="y"), True))))
    lowered = LayoutDoc.from_ast(original)
    assert lowered is original


def test_layoutdoc_ast_synthesizes_seq_for_manual_sequence() -> None:
    doc = Concat(
        parts=(
            (Text(value="a"), True), 
            (Group(
                body=Concat(
                    parts=(
                        (Text(value="b"), True), 
                        (Group(
                            body=Concat(
                                parts=((Text(value="c"), True),)
                            ), 
                            indent=8
                        ), True)
                    )
                )
            ), True)
        )
    )
    ast = doc.ast
    assert ast is None
    assert doc.render(width=80) == "abc"
    


def test_group_fits_exact_boundary_uses_flat_mode() -> None:
    doc = Group(
        body=Concat(
            parts=(
                (Text(value="ab"), True),
                (Text(value="cd"), True)
                ),
                include_all=True, 
                flat=construct_templated_text("{0}{@opt}{f? }{1}", is_broken=False),
                broken=construct_templated_text("{0}{@opt}{1}", is_broken = True)
                
            )
        )
    assert doc.render(width=5) == "ab cd"
    assert doc.render(width=4) == "ab\ncd"


def test_nest_negative_level_is_clamped_to_zero() -> None:
    doc = Group(
        body=Concat(
            parts=(
                (Text(value="if"), True), 
                (Group(
                    body=Concat(parts=((Text(value="x"), True),)),
                    indent=-6
                ), True),
            ),
            flat=construct_templated_text("{0}{@opt}{1}", is_broken=False),
            broken=construct_templated_text("{0}{@opt}{1}", is_broken=True)
        )
    )
    assert doc.render(width=2) == "if\nx"






def test_render_function_accepts_ast_values() -> None:
    value = Seq(value=((Token(text="a"), True), (Token(text="b"), True)))
    assert render(value, width=80) == "ab"


def test_expression_grammar_integration_with_format_hints_and_rendered_text() -> None:
    """Format hints at grammar level control breaks metadata.
    
    Apply .format() to mark structural decisions. The layout layer composes
    the result based on these hints, not custom callbacks. Spacing must be
    explicit in the grammar—format hints control breaks, not spacing.
    """
    expression_syntax = Syntax

    number = expression_syntax.tok(text=re.compile(r"\d+")).bimap(
        lambda token: token.text,
        lambda text: Token(text=text),
    )

    # Operator is marked as optional breakpoint
    plus = expression_syntax.tok(text="+").bimap(
        lambda token: token.text,
        lambda text: Token(text=text),
    ).format(
        "{0}{@opt}",  
    )

    # Sequence: without spacing rule in grammar, renders as "12+345"
    expr = (number + plus + number).format(
        "{0}{@opt}{f? }{1}{f? }{@opt}{2}",
        indent=2
    )

    parsed = parse_word(expr, "12 + 345")
    assert parsed == ("12", "+", "345")

    generated = expr.generate(parsed, seed=0)
    # Format hints are applied during generation, spacing from grammar (none here)
    result = generated.render(width=80)
    # Without explicit spacing grammar, operator directly adjoins operands
    print(result)
    assert result == "12 + 345"


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
        "{0}{1}{2}{3}{4}"
    )
    
    expected = "f(a, b, c)"
    generated = func_call.generate(('f', '(', 'a', ((', ', 'b'), (', ', 'c')), ')'))
    result = generated.render(width=80)
    print(result)
    assert result == expected


def test_format_multiline_function_call() -> None:
    """Format: f(a, b, c) breaking to multiple lines when too wide."""
    syntax_cls = Syntax
    
    identifier = syntax_cls.rp(r"[a-zA-Z_]\w*").bimap(
        lambda t: t.text if isinstance(t, Token) else t,
        lambda s: s
    )
    
    # Apply format to the separator part (comma + space)
    separator = (syntax_cls.lit(",") + syntax_cls.lit(" ")).format(
        "{0}{@opt}",
        indent=1
    )
    
    arg = identifier
    # Build: arg + (separator + arg).many()
    args = arg + (separator + arg).many()
    func_call = identifier + syntax_cls.lit("(") + args + syntax_cls.lit(")")
    
    # Data matches parse output structure
    generated = func_call.generate(('f', '(', 'a', (((',', ' '), 'b'), ((',', ' '), 'c')), ')'))
    # print("Generated successfully!", generated)
    # Fits on one line with width=80
    result_wide = generated.render(width=80)
    print("Wide:", result_wide)
    assert "," in result_wide
    
    # Breaks to multiple lines with narrow width
    result_narrow = generated.render(width=5)
    print("Narrow:", result_narrow)
    assert "\n" in result_narrow, f"Expected newline in narrow output, got: {repr(result_narrow)}"



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
    
    # Apply format to the operator part (space + plus + space) with attach="left"
    operator = (syntax_cls.lit(" ") + syntax_cls.lit("+") + syntax_cls.lit(" ")).format(
        "{0}{@opt}{1}{@opt}{2}",
        indent=1
    )
    
    # Build: identifier + (operator + identifier).many()
    expr = identifier + (operator + identifier).many()
    generated = expr.generate(("a", (((" ", "+", " "), "b"), ((" ", "+", " "), "c"), ((" ", "+", " "), "d"))))

    # Fits on one line with width=80
    result_wide = generated.render(width=80)
    assert "+" in result_wide
    
    # Breaks to multiple lines with narrow width
    result_narrow = generated.render(width=8)
    assert "\n" in result_narrow, f"Expected newline in narrow output, got: {repr(result_narrow)}"
    # Operator should be on continuation lines
    lines = result_narrow.strip().split("\n")
    assert len(lines) > 1






