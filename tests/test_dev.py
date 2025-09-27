import builtins
import sys
import types
from typing import Any

import pytest

from syncraft.dev import (
    _short_repr,
    _format_factory_label,
    _is_success_nothing,
    _optional_branch,
    _spec_label,
    _spec_children,
    _spec_tree_lines,
    rich_error,
    rich_parser,
    rich_debug,
    syntax2svg,
    ast2svg,
)
from syncraft.syntax import FactorySpec, ManySpec, ChoiceSpec, ThenSpec, LazySpec, Syntax, SyntaxSpec
from syncraft.ast import Nothing, ThenKind
from syncraft.constraint import FrozenDict
from syncraft.algebra import Error, Left, Right, Algebra
from syncraft.parser import ParserState

def factory(name: str, *args, **kwargs) -> FactorySpec:
    return FactorySpec(name=name, args=tuple(args), kwargs=FrozenDict(kwargs))


def make_syntax(spec: Any) -> Syntax[Any, Any]:
    def dummy_alg(alg_cls: type[Algebra[Any, Any]], **_: Any) -> Algebra[Any, Any]:
        return alg_cls.fail(None)

    return Syntax(dummy_alg, spec=spec)


def make_algebra(name: str = "demo") -> Algebra[Any, ParserState[Any]]:
    def run_fn(state: ParserState[Any], _cache: Any):
        if False:  # pragma: no cover - generator formality
            yield
        return Right((None, state))

    return Algebra(run_fn, _name=name)


@pytest.fixture
def rich_stub(monkeypatch):
    printed: list[str] = []
    tables: list[object] = []

    class DummyTable:
        def __init__(self, *_, **__):
            self.columns: list[tuple[str, str | None]] = []
            self.rows: list[tuple[str, ...]] = []
            tables.append(self)

        def add_column(self, title: str, style: str | None = None) -> None:
            self.columns.append((title, style))

        def add_row(self, *values: str) -> None:
            self.rows.append(tuple(values))

    rich_module = types.ModuleType("rich")
    setattr(rich_module, "print", lambda value: printed.append(value))

    table_module = types.ModuleType("rich.table")
    setattr(table_module, "Table", DummyTable)

    monkeypatch.setitem(sys.modules, "rich", rich_module)
    monkeypatch.setitem(sys.modules, "rich.table", table_module)

    return printed, tables


def test_short_repr_truncates_long_values():
    assert _short_repr("short") == "'short'"
    long_text = "x" * 100
    assert _short_repr(long_text, max_len=10) == "'xxxxxx..."


def test_format_factory_label_handles_special_cases():
    success = factory("success", Nothing())
    assert _format_factory_label(success) == "ε"

    token_spec = factory("token", text="id", token_type="IDENT")
    assert _format_factory_label(token_spec) == "token 'id' :IDENT"

    generic = factory("literal", "value", flag=True)
    assert _format_factory_label(generic) == "literal('value', flag=True)"


def test_is_success_nothing_and_optional_branch():
    success = factory("success", Nothing())
    assert _is_success_nothing(success)

    other = factory("literal", "x")
    choice = ChoiceSpec(left=success, right=other)
    assert _optional_branch(choice) is other
    assert not _is_success_nothing(other)


def test_spec_label_covers_variants():
    lazy_spec = LazySpec(lambda: factory("literal", "x"))
    assert _spec_label(lazy_spec) == "lazy"

    then_left = ThenSpec(kind=ThenKind.LEFT, left=factory("a"), right=factory("b"))
    assert _spec_label(then_left) == "//"

    optional_choice = ChoiceSpec(
        left=factory("success", Nothing()),
        right=factory("literal", "x"),
    )
    assert _spec_label(optional_choice) == "~"

    mandatory_many = ManySpec(spec=factory("literal", "x"), at_least=1, at_most=None)
    assert _spec_label(mandatory_many) == "+"

    ranged_many = ManySpec(spec=factory("literal", "x"), at_least=2, at_most=3)
    assert _spec_label(ranged_many) == "repeat[2,3]"

    literal = factory("literal", "value")
    assert _spec_label(literal).startswith("literal(")


def test_spec_children_lazy_cache():
    calls: list[int] = []
    inner = factory("literal", "x")

    def resolver():
        calls.append(1)
        return inner

    lazy = LazySpec(resolver)
    cache: dict[int, SyntaxSpec] = {}

    assert _spec_children(lazy, lazy_cache=cache) == [inner]
    assert _spec_children(lazy, lazy_cache=cache) == [inner]
    assert len(calls) == 1


def test_spec_tree_lines_respects_limits_and_cycles():
    leaf = factory("literal", "x")

    cyclic_lazy: LazySpec

    def lazy_target():
        return ChoiceSpec(left=leaf, right=cyclic_lazy)

    cyclic_lazy = LazySpec(lazy_target)

    lines = _spec_tree_lines(cyclic_lazy, max_depth=3)
    assert lines[0] == "lazy"
    assert any(line.strip().startswith("lazy") and line.endswith("…") for line in lines)

    limited_lines = _spec_tree_lines(leaf, max_lines=1)
    assert limited_lines[0].endswith("… (truncated)")


def test_rich_error_renders_table_when_rich_available(rich_stub):
    printed, tables = rich_stub
    err = Error(this="parser", message="oops")
    rich_error(err)
    assert printed and printed[0] is tables[0]
    assert tables
    field_names = {row[0] for table in tables for row in table.rows}
    assert "message" in field_names


def test_rich_error_falls_back_without_rich(capsys, monkeypatch):
    original_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name.startswith("rich"):
            raise ImportError("rich not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    err = Error(this="parser", message="oops")
    rich_error(err)
    captured = capsys.readouterr()
    assert "oops" in captured.out


def test_rich_parser_plain_output(capsys):
    spec = ThenSpec(kind=ThenKind.BOTH, left=factory("literal", "x"), right=factory("literal", "y"))
    rich_parser(make_syntax(spec), max_depth=1, use_rich=False)
    output = capsys.readouterr().out
    assert "Parser Debug Information" in output
    assert "+" in output


def test_rich_parser_uses_rich_when_available(rich_stub):
    printed, _ = rich_stub
    spec = ManySpec(spec=factory("literal", "x"), at_least=0, at_most=None)
    rich_parser(make_syntax(spec), max_lines=2, use_rich=True)
    assert printed[0] == "Parser Debug Information:"
    assert len(printed) > 1


def test_rich_debug_records_rows(rich_stub):
    _, tables = rich_stub
    state = ParserState.from_tokens(("a", "b"))
    result = Right(value=("value", state.advance()))
    rich_debug(make_algebra("demo"), state, result)
    assert tables
    row = tables[0].rows[0]
    assert row[0] == "demo"

    tables.clear()
    err_state = Left(value="error")
    rich_debug(make_algebra("demo"), state, err_state)
    row = tables[0].rows[0]
    assert row[-1] == "N/A"


def test_syntax2svg_returns_svg_with_stubbed_railroad(monkeypatch):
    nodes_created: list[str] = []

    class DummyNode:
        def __init__(self, *children):
            self.children = children
            nodes_created.append(self.__class__.__name__)

    class DummyDiagram(DummyNode):
        def writeSvgString(self):
            return "<svg/>"

        def writeSvg(self, writer):
            writer("<svg/>")

    railroad_module = types.ModuleType("railroad")
    setattr(railroad_module, "Diagram", DummyDiagram)
    setattr(railroad_module, "Terminal", type("Terminal", (DummyNode,), {}))
    setattr(railroad_module, "Sequence", type("Sequence", (DummyNode,), {}))
    setattr(railroad_module, "Choice", type("Choice", (DummyNode,), {}))
    setattr(railroad_module, "OneOrMore", type("OneOrMore", (DummyNode,), {}))
    setattr(railroad_module, "Comment", type("Comment", (DummyNode,), {}))
    setattr(railroad_module, "Optional", type("Optional", (DummyNode,), {}))
    setattr(railroad_module, "ZeroOrMore", type("ZeroOrMore", (DummyNode,), {}))

    monkeypatch.setitem(sys.modules, "railroad", railroad_module)

    spec = ManySpec(spec=factory("literal", "x"), at_least=0, at_most=None)
    svg = syntax2svg(make_syntax(spec))
    assert svg == "<svg/>"
    assert any(name.endswith("Diagram") for name in nodes_created)


def test_syntax2svg_returns_none_when_library_missing(monkeypatch):
    original_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "railroad":
            raise ImportError("railroad missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    spec = factory("literal", "x")
    assert syntax2svg(make_syntax(spec)) is None


def test_ast2svg_returns_svg_with_stubbed_graphviz(monkeypatch):
    class DummyDigraph:
        def __init__(self, format: str = "svg") -> None:
            self.format = format
            self.nodes: list[tuple[str, str]] = []
            self.edges: list[tuple[str, str]] = []

        def node(self, name: str, label: str) -> None:
            self.nodes.append((name, label))

        def edge(self, start: str, end: str) -> None:
            self.edges.append((start, end))

        def pipe(self) -> bytes:
            return b"<svg/>"

    graphviz_module = types.ModuleType("graphviz")
    setattr(graphviz_module, "Digraph", DummyDigraph)
    monkeypatch.setitem(sys.modules, "graphviz", graphviz_module)

    svg = ast2svg(Nothing())
    assert svg == "<svg/>"


def test_ast2svg_returns_none_when_graphviz_missing(monkeypatch):
    original_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "graphviz":
            raise ImportError("graphviz missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    assert ast2svg(Nothing()) is None
