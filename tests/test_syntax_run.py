from __future__ import annotations

from syncraft.parser import parse_data
from syncraft.syntax import AltSpec
from syncraft.syntax import Syntax
from syncraft.algebra import Error


def test_syntax_run_returns_error_on_incomplete() -> None:
    
    literal = Syntax.tok
    syntax = literal("if")
    
    value = parse_data(syntax=syntax, data=[])

    assert isinstance(value, Error)
    assert value.message and "Cannot match token at end of input" in value.message


def test_seq_default_mode_keeps_nested_shape() -> None:
    a = Syntax.tok("a")
    b = Syntax.tok("b")
    c = Syntax.tok("c")

    value = parse_data(syntax=(a + b) + c, data=["a", "b", "c"])

    assert isinstance(value, tuple)
    assert len(value) == 2
    assert isinstance(value[0], tuple)


def test_seq_opt_in_normalize_seq_flattens_one_level() -> None:
    SNorm = Syntax.set(normalize_seq=True)
    a = SNorm.tok("a")
    b = SNorm.tok("b")
    c = SNorm.tok("c")

    left = parse_data(syntax=(a + b) + c, data=["a", "b", "c"])
    right = parse_data(syntax=a + (b + c), data=["a", "b", "c"])

    assert left == right
    assert isinstance(left, tuple)
    assert len(left) == 3


def test_unary_seq_default_mode_keeps_singleton_tuple() -> None:
    unary = Syntax.seq(+Syntax.tok("x"))
    value = parse_data(syntax=unary, data=["x"])

    assert isinstance(value, tuple)
    assert value == ("x",)


def test_unary_seq_opt_in_unwraps_scalar() -> None:
    U = Syntax.set(unwrap_unary_seq=True)
    unary = U.seq(+U.tok("x"))
    value = parse_data(syntax=unary, data=["x"])

    assert value == "x"


def test_alt_default_mode_keeps_nested_choice_shape() -> None:
    a = Syntax.tok("a")
    b = Syntax.tok("b")
    c = Syntax.tok("c")

    left = (a | b) | c
    right = a | (b | c)

    assert isinstance(left.spec, AltSpec)
    assert isinstance(right.spec, AltSpec)
    assert len(left.spec.options) == 2
    assert len(right.spec.options) == 2
    assert isinstance(left.spec.options[0], AltSpec)
    assert isinstance(right.spec.options[1], AltSpec)


def test_alt_opt_in_normalize_alt_flattens_one_level() -> None:
    ANorm = Syntax.set(normalize_alt=True)
    a = ANorm.tok("a")
    b = ANorm.tok("b")
    c = ANorm.tok("c")

    left = (a | b) | c
    right = a | (b | c)

    assert isinstance(left.spec, AltSpec)
    assert isinstance(right.spec, AltSpec)
    assert len(left.spec.options) == 3
    assert len(right.spec.options) == 3
    assert all(not isinstance(opt, AltSpec) for opt in left.spec.options)
    assert all(not isinstance(opt, AltSpec) for opt in right.spec.options)
