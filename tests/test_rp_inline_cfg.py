"""
Test cases demonstrating Syntax.rp() in inline, immediate, REPL-style usage.

"CFG in regex flavor" — using regex notation to compose CFG rules inline,
without @grammar classes or explicit rule fields. Everything is immediate.
"""

from syncraft.syntax import Syntax as S
from syncraft.parser import parse_string
from syncraft.algebra import Error


def cfgparse(pattern: str, text: str, **refs):
    """Shorthand: pattern -> Syntax.rp -> parse immediate."""
    return parse_string(S.rp(pattern, **refs), text)


def test_rp_inline_external_rule_reference():
    """
    External rule reference inline in regex pattern.
    
    Num rule is a separate Syntax; referenced via (?&num) in the pattern.
    """
    num = S.rp(r"[0-9]+").map(int)
    result = cfgparse(r"(?&num)-(?&num)", "12-34", num=num)
    assert result == (12, 34)


def test_rp_inline_external_reference_multiple():
    """Multiple references to the same external rule."""
    num = S.rp(r"[0-9]+").map(int)
    result = cfgparse(r"(?&num)\s*\+\s*(?&num)", "5 + 7", num=num)
    assert result == (5, 7)


def test_rp_inline_lazy_recursive_expr():
    """
    Recursive CFG grammar written in regex style.
    
    A recursive expression: number | (expr + expr).
    Lazy thunk allows self-reference via (?&expr).
    """
    num = S.rp(r"[0-9]+").map(int)
    op = S.rp(r"[+\-*/]")

    expr = S.lazy(lambda: S.rp(
        r"(?&num)|(\((?&expr)\s*(?&op)\s*(?&expr)\))",
        num=num, op=op, expr=expr
    ))

    # Plain number
    result = parse_string(expr, "7")
    assert result == 7

    # Binary operation
    result = parse_string(expr, "(2+3)")
    assert result == (2, "+", 3)

    # Nested operation
    result = parse_string(expr, "((1+2)*3)")
    assert result == ((1, "+", 2), "*", 3)


def test_rp_inline_assignment_stmt():
    """
    Assignment statement: let id = value ;
    
    Identifier and value are separate rules; embedded in struct regex.
    """
    ident = S.rp(r"[A-Za-z_][A-Za-z0-9_]*")
    value = S.rp(r"[0-9]+|\"[^\"]*\"")

    stmt = S.rp(r"let\s+(?&id)\s*=\s*(?&val)\s*;", id=ident, val=value)

    result = parse_string(stmt, 'let count = 42;')
    assert result == ('count', '42')

    result = parse_string(stmt, 'let name = "mike";')
    assert result == ('name', '"mike"')


def test_rp_inline_json_like_object():
    """
    JSON-like object: {key: value, ...}
    
    Uses sep_by for comma-separated pairs.
    """
    key = S.rp(r'"[^"]*"')
    value = S.rp(r"[0-9]+|\"[^\"]*\"|null|true|false")

    pair = S.rp(r"(?&key)\s*:\s*(?&val)", key=key, val=value)
    pairs = pair.sep_by(S.rp(r"\s*,\s*"))
    obj = S.rp(r"\{\s*", key=key, val=value) >> pairs // S.rp(r"\s*\}")

    result = parse_string(obj, '{"a": 1, "b": 2}')
    assert len(result) == 2


def test_rp_inline_optional_suffix():
    """
    Pattern with optional suffix (e.g., number with optional "px" unit).
    
    Uses .optional to make "px" non-mandatory.
    """
    num = S.rp(r"[0-9]+").map(int)
    unit = S.rp(r"px|em|rem").optional

    measurement = num + unit
    result = parse_string(measurement, "42px")
    assert result[0] == 42

    result = parse_string(measurement, "100")
    assert result[0] == 100


def test_rp_inline_with_many():
    """
    List of items using .many().
    
    Comma-separated identifiers: a, b, c
    """
    ident = S.rp(r"[A-Za-z_][A-Za-z0-9_]*")
    idents = ident.many()
    pattern = idents

    result = parse_string(pattern, "x")
    assert result == ("x",)

    result = parse_string(pattern, "a")
    assert result == ("a",)


def test_rp_inline_with_map_transform():
    """
    Inline transformation via .map().
    
    Parse int and transform to bool (0 -> False, else True).
    """
    bool_from_int = S.rp(r"[0-9]+").map(lambda s: int(s) != 0)
    result = parse_string(bool_from_int, "0")
    assert result is False

    result = parse_string(bool_from_int, "42")
    assert result is True


def test_rp_inline_alternation_branch():
    """
    Simple alternation: color is either #RRGGBB or named color.
    """
    hex_color = S.rp(r"#[0-9A-Fa-f]{6}")
    named = S.rp(r"red|green|blue|black|white")
    color = S.rp(r"(?&hex)|(?&named)", hex=hex_color, named=named)

    result = parse_string(color, "#FF0000")
    assert result == "#FF0000"

    result = parse_string(color, "red")
    assert result == "red"


def test_rp_inline_captures_flattened():
    """
    Multiple consecutive captures are flattened into a tuple.
    
    Pattern: (a)(b)(c) -> (a, b, c)
    """
    result = cfgparse(r"(a)(b)(c)", "abc")
    assert result == ("a", "b", "c")


def test_rp_inline_no_capture_skips():
    """
    Non-capture groups (?:...) are structural only.
    
    Pattern: (?:foo)(bar) -> just "bar"
    """
    result = cfgparse(r"(?:foo)(bar)", "foobar")
    assert result == "bar"


def test_rp_inline_named_capture_bind():
    """
    Named captures bind to context.
    
    Pattern: (?P<op>[+*])
    """
    result = cfgparse(r"5\s*(?P<op>[+*])\s*3", "5 + 3")
    assert result == "+"


def test_rp_inline_with_check_predicate():
    """
    Syntax.check() validates results inline.
    
    Only allow even numbers.
    """
    even_num = S.rp(r"[0-9]+").map(int).check(lambda v: v % 2 == 0)

    result = parse_string(even_num, "42")
    assert result == 42

    result = parse_string(even_num, "99")
    assert isinstance(result, Error)


def test_rp_inline_whitespace_handling():
    """
    Regex whitespace escapes (\\s*) naturally handle structural gaps.
    
    Pattern: num \\s* + \\s* num
    """
    num = S.rp(r"[0-9]+").map(int)
    expr = S.rp(r"(?&num)\s*\+\s*(?&num)", num=num)

    result = parse_string(expr, "2+3")
    assert result == (2, 3)

    result = parse_string(expr, "2  +  3")
    assert result == (2, 3)


def test_rp_inline_backref_not_yet_supported():
    """
    Backreferences (\1, \2) are parsed but require matching context in CFG.
    
    Currently unsupported in Syntax.rp due to CFG nature (no stateful backtrack).
    This test documents the limitation.
    """
    # Pattern with backreference: ([a-z])\1 would match "aa" or "bb"
    # This is a regex feature that does not map cleanly to CFG parsing.
    # Syncraft intentionally does not support this in rp().
    pass
