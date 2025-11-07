import pytest

try:  # pragma: no cover - guard optional test dependencies
    import rstr  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover - tests skipped when optional deps missing
    pytest.skip("rstr is required for syntax spec construction", allow_module_level=True)

try:  # pragma: no cover - guard optional test dependencies
    import railroad  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover - tests skipped when optional deps missing
    pytest.skip("railroad-diagrams is required for SVG rendering", allow_module_level=True)

from syncraft.dev import syntax2svg
from syncraft.syntax import (
    FactorySpec,
    ThenSpec,
    ChoiceSpec,
    LazySpec,
)
from syncraft.ast import ThenKind
from syncraft.utils import FrozenDict


def token_spec(label: str) -> FactorySpec:
    return FactorySpec(fname="token", kwargs=FrozenDict({"text": label}), name=None, file=None, line=None, func=None)


def test_syntax2svg_simple_sequence():
    token_a = token_spec("A")
    token_b = token_spec("B")
    sequence = ThenSpec(kind=ThenKind.BOTH, left=token_a, right=token_b, name=None, file=None, line=None, func=None)

    svg = syntax2svg(sequence)

    assert isinstance(svg, str)
    assert "<svg" in svg
    assert "A" in svg or "token" in svg


def test_syntax2svg_handles_direct_recursion():
    token_digit = token_spec("digit")

    def deferred() -> ChoiceSpec:
        return recursive_choice

    lazy = LazySpec(spec=deferred, name=None, file=None, line=None, func=None)
    recursive_choice = ChoiceSpec(left=token_digit, right=lazy, name=None, file=None, line=None, func=None)

    svg = syntax2svg(recursive_choice)

    assert isinstance(svg, str)
    assert "digit" in svg or "Choice" in svg
