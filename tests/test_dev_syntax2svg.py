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
    LexSpec,
    ThenSpec,
    ChoiceSpec,
    LazySpec,
)
from syncraft.ast import ThenKind
from syncraft.utils import FrozenDict


def token_spec(label: str) -> LexSpec:
    return LexSpec(fname="token", kwargs=FrozenDict({"text": label}), name=None, file=None, line=None, func=None)


def test_syntax2svg_simple_sequence():
    token_a = token_spec("A")
    token_b = token_spec("B")
    sequence = ThenSpec(kind=ThenKind.BOTH, left=token_a, right=token_b, name=None, file=None, line=None, func=None)

    svg = syntax2svg(sequence)

    assert isinstance(svg, str)
    assert "<svg" in svg
    assert "A" in svg or "token" in svg


