import pytest

try:  # pragma: no cover - guard optional test dependencies
    import rstr  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover - tests skipped when optional deps missing
    pytest.skip("rstr is required for syntax spec construction", allow_module_level=True)

try:  # pragma: no cover - guard optional test dependencies
    import railroad  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover - tests skipped when optional deps missing
    pytest.skip("railroad-diagrams is required for SVG rendering", allow_module_level=True)

from syncraft.vis import syntax2svg
from syncraft.syntax import (
    LexSpec,
    
)

from syncraft.utils import FrozenDict
from syncraft.vis import SVGVisualization
from syncraft.syntax import Syntax, SyntaxSpec, LazySpec, SeqSpec, AltSpec

def token_spec(label: str) -> LexSpec:
    return LexSpec(fname="token", kwargs=FrozenDict({"text": label}), name=None, file=None, line=None, func=None, MAX_NAME_LENGTH=30)


def test_syntax2svg_simple_sequence():
    token_a = token_spec("A")
    token_b = token_spec("B")
    
    sequence = SeqSpec(steps=((token_a, True), (token_b, True)), name=None, file=None, line=None, func=None)

    svg = syntax2svg(sequence, 5)

    assert isinstance(svg, SVGVisualization)


