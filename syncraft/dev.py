from __future__ import annotations
import builtins
import io
from typing import Tuple, Any, Set, Optional, List, Dict, Mapping
from syncraft.syntax import (
    Syntax,
    SyntaxSpec,
    LazySpec,
    ThenSpec,
    ChoiceSpec,
    ManySpec,
    FactorySpec,
)
from syncraft.ast import ThenKind, Nothing
from syncraft.algebra import  Left, Right, Error, Either, Algebra
from syncraft.parser import ParserState, Token


def _short_repr(value: Any, *, max_len: int = 40) -> str:
    text = repr(value)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _format_factory_label(spec: FactorySpec) -> str:
    if spec.name == "success" and spec.args:
        first = spec.args[0]
        if isinstance(first, Nothing):
            return "ε"
    if spec.name == "token":
        kwargs = dict(spec.kwargs)
        parts: list[str] = []
        if "text" in kwargs:
            parts.append(_short_repr(kwargs["text"]))
        if "token_type" in kwargs:
            parts.append(f":{kwargs['token_type']}")
        if parts:
            return f"token {' '.join(parts)}"
    args_str = ", ".join(_short_repr(arg) for arg in spec.args)
    kwargs_str = ", ".join(f"{key}={_short_repr(val)}" for key, val in spec.kwargs.items())
    joined_parts = [part for part in (args_str, kwargs_str) if part]
    joined = ", ".join(joined_parts)
    return spec.name if not joined else f"{spec.name}({joined})"


def _is_success_nothing(spec: SyntaxSpec) -> bool:
    if not isinstance(spec, FactorySpec):
        return False
    if spec.name != "success" or not spec.args:
        return False
    return isinstance(spec.args[0], Nothing)


def _optional_branch(spec: ChoiceSpec) -> Optional[SyntaxSpec]:
    if _is_success_nothing(spec.left):
        return spec.right
    if _is_success_nothing(spec.right):
        return spec.left
    return None


def _spec_label(spec: SyntaxSpec) -> str:
    if isinstance(spec, LazySpec):
        return "lazy"
    if isinstance(spec, ThenSpec):
        return {
            ThenKind.BOTH: "+",
            ThenKind.LEFT: "//",
            ThenKind.RIGHT: ">>",
        }.get(spec.kind, "then")
    if isinstance(spec, ChoiceSpec):
        return "~" if _optional_branch(spec) is not None else "|"
    if isinstance(spec, ManySpec):
        if spec.at_least == 0 and spec.at_most == 1:
            return "~"
        if spec.at_least == 0 and spec.at_most is None:
            return "*"
        if spec.at_least == 1 and spec.at_most is None:
            return "+"
        upper = "∞" if spec.at_most is None else spec.at_most
        return f"repeat[{spec.at_least},{upper}]"
    if isinstance(spec, FactorySpec):
        return _format_factory_label(spec)
    return spec.__class__.__name__


def _spec_children(spec: SyntaxSpec, *, lazy_cache: Dict[int, SyntaxSpec]) -> List[SyntaxSpec]:
    if isinstance(spec, LazySpec):
        key = id(spec)
        if key in lazy_cache:
            return [lazy_cache[key]]
        try:
            target = spec.spec()
        except RecursionError:
            return []
        lazy_cache[key] = target
        return [target]
    if isinstance(spec, ThenSpec):
        return [spec.left, spec.right]
    if isinstance(spec, ChoiceSpec):
        return [spec.left, spec.right]
    if isinstance(spec, ManySpec):
        return [spec.spec]
    return []


def _spec_tree_lines(
    spec: SyntaxSpec,
    *,
    max_depth: Optional[int] = None,
    max_lines: Optional[int] = None,
) -> List[str]:
    lazy_cache: Dict[int, SyntaxSpec] = {}
    lines: List[str] = []
    visiting: Set[int] = set()
    truncated = False

    def append(line: str) -> None:
        nonlocal truncated
        if truncated:
            return
        lines.append(line)
        if max_lines is not None and len(lines) >= max_lines:
            lines[-1] = f"{lines[-1]} … (truncated)"
            truncated = True

    def visit(node: SyntaxSpec, depth: int) -> None:
        nonlocal truncated
        if truncated:
            return
        if max_depth is not None and depth > max_depth:
            append("  " * depth + "…")
            return
        key = id(node)
        label = _spec_label(node)
        indent = "  " * depth
        if key in visiting:
            append(f"{indent}{label} …")
            return
        append(f"{indent}{label}")
        if truncated:
            return
        visiting.add(key)
        try:
            for child in _spec_children(node, lazy_cache=lazy_cache):
                visit(child, depth + 1)
        finally:
            visiting.remove(key)

    visit(spec, 0)
    return lines


def rich_error(err: Error)->None:
    try:
        from rich import print
        from rich.table import Table as RichTable
        lst = err.to_list()
        leaf: Any = lst[0] if lst else {}
        if isinstance(leaf, Mapping):
            leaf_map: Mapping[str, Any] = leaf
        else:
            leaf_map = {
                key: getattr(leaf, key)
                for key in dir(leaf)
                if not key.startswith('_') and hasattr(leaf, key)
            }
        tbl = RichTable(title="Parser Error", show_lines=True)
        tbl.add_column("Leaf Parser Field", style="blue")
        tbl.add_column("Leaf Parser Value", style="yellow")
        flds: Set[str] = {str(fld) for fld in leaf_map.keys()}
        for fld in sorted(flds):
            leaf_value = leaf_map.get(fld, "N/A")
            tbl.add_row(f"{fld}", f"{leaf_value}")
        print(tbl)
    except ImportError:
        builtins.print(err)


def rich_parser(
    p: Syntax,
    *,
    max_lines: Optional[int] = None,
    max_depth: Optional[int] = None,
    use_rich: bool = True,
) -> None:
    lines = _spec_tree_lines(p.spec, max_depth=max_depth, max_lines=max_lines)
    if not use_rich:
        print("Parser Debug Information:")
        print("\n".join(lines))
        return
    try:
        from rich import print as rich_print

        rich_print("Parser Debug Information:")
        for line in lines:
            rich_print(line)
    except ImportError:
        print("Parser Debug Information:")
        print("\n".join(lines))

def rich_debug(this: Algebra[Any, ParserState[Any]], 
               state: ParserState[Any], 
               result: Either[Any, Tuple[Any, ParserState[Any]]])-> None:
    try:
        from rich import print
        from rich.table import Table as RichTable
        def value_to_str(value: Any, prefix:str='') -> str:
            if isinstance(value, (tuple, list)):
                if len(value) == 0:
                    return prefix + str(value)
                else:
                    return '\n'.join(value_to_str(item, prefix=prefix+' - ') for item in value)
            else:                
                sql_method = getattr(value, "sql", None)
                if callable(sql_method):
                    return prefix + str(sql_method())
                elif isinstance(value, Token):
                    return prefix + f"{str(value)}"
                elif isinstance(value, Syntax):
                    return prefix + _spec_label(value.spec)
                else:
                    return prefix + str(value)

        tbl = RichTable(title=f"Debug: {this.name}", show_lines=True)
        tbl.add_column("Parser", style="blue")
        tbl.add_column("Old State", style="cyan")
        tbl.add_column("Result", style="magenta")
        tbl.add_column("New State", style="green")
        tbl.add_column("Consumed", style="green")
        if isinstance(result, Left):
            tbl.add_row(value_to_str(this), value_to_str(state), value_to_str(result.value), 'N/A', 'N/A')
        else:
            assert isinstance(result, Right), f"Expected result to be a Right value, got {type(result)}, {result}"
            value, new_state = result.value
            tbl.add_row(value_to_str(this), 
                        value_to_str(state),
                        value_to_str(value), 
                        value_to_str(new_state))

        print(tbl)
    except ImportError:
        builtins.print(this)
        builtins.print(state)
        builtins.print(result)




def syntax2svg(
    syntax: Syntax[Any, Any],
    *,
    max_nodes: Optional[int] = None,
    max_depth: Optional[int] = None,
) -> Optional[str]:
    try:
        from railroad import Diagram, Terminal, Sequence, Choice, OneOrMore, Comment, Optional as RROptional  # type: ignore[import-not-found]
        try:  # ZeroOrMore is optional in older railroad versions
            from railroad import ZeroOrMore  # type: ignore
        except ImportError:  # pragma: no cover - best effort rendering
            ZeroOrMore = None  # type: ignore

        cache: dict[int, object] = {}
        visiting: Set[int] = set()
        truncated = False
        remaining_nodes = max_nodes

        def budget_exhausted() -> bool:
            nonlocal remaining_nodes, truncated
            if remaining_nodes is None:
                return False
            if remaining_nodes <= 0:
                truncated = True
                return True
            remaining_nodes -= 1
            return False

        def build_many(inner: object, spec: ManySpec[Any]) -> object:
            if spec.at_least == 0 and spec.at_most == 1:
                return RROptional(inner)
            if spec.at_least == 0 and spec.at_most is None:
                if ZeroOrMore is not None:
                    return ZeroOrMore(inner)
                return Choice(0, Terminal("ε"), OneOrMore(inner))

            annotations: list[str] = []
            if spec.at_least not in (0, 1):
                annotations.append(f"≥{spec.at_least}")
            if spec.at_most is not None:
                annotations.append(f"≤{spec.at_most}")
            if annotations:
                return Sequence(Comment(f"repeat {' & '.join(annotations)}"), OneOrMore(inner))
            return OneOrMore(inner)

        def to_railroad_spec(spec: SyntaxSpec, depth: int = 0) -> object:
            nonlocal truncated
            key = id(spec)
            if key in cache:
                return cache[key]

            if max_depth is not None and depth > max_depth:
                truncated = True
                node = Comment("… depth limit …")
                cache[key] = node
                return node

            if budget_exhausted():
                node = Comment("… node limit …")
                cache[key] = node
                return node

            if isinstance(spec, LazySpec):
                if key in visiting:
                    node = Comment("lazy(...)")
                else:
                    visiting.add(key)
                    try:
                        node = to_railroad_spec(spec.spec(), depth + 1)
                    except RecursionError:  # pragma: no cover - defensive
                        node = Comment("lazy(...)")
                    finally:
                        visiting.remove(key)
            elif isinstance(spec, ThenSpec):
                node = Sequence(
                    to_railroad_spec(spec.left, depth + 1),
                    to_railroad_spec(spec.right, depth + 1),
                )
            elif isinstance(spec, ChoiceSpec):
                optional = _optional_branch(spec)
                if optional is not None:
                    node = RROptional(to_railroad_spec(optional, depth + 1))
                else:
                    node = Choice(
                        0,
                        to_railroad_spec(spec.left, depth + 1),
                        to_railroad_spec(spec.right, depth + 1),
                    )
            elif isinstance(spec, ManySpec):
                inner = to_railroad_spec(spec.spec, depth + 1)
                node = build_many(inner, spec)
            elif isinstance(spec, FactorySpec):
                node = Terminal(_format_factory_label(spec))
            else:
                node = Terminal(_spec_label(spec))

            cache[key] = node
            return node

        diagram = Diagram(to_railroad_spec(syntax.spec))
        if truncated:
            diagram = Diagram(Comment("Diagram truncated"), diagram)
        writer = getattr(diagram, "writeSvgString", None)
        if callable(writer):
            return writer()  # type: ignore[no-any-return]
        stream = io.StringIO()
        diagram.writeSvg(stream.write)
        return stream.getvalue()
    except ImportError:
        return None

def ast2svg(ast: Any) -> Optional[str]:
    """
    Generate SVG visualization for a Syncraft AST node using graphviz.
    Returns SVG string or None if graphviz is not available.
    """
    try:
        import graphviz  # type: ignore[import-not-found]
    except ImportError:
        return None

    def node_label(node):
        from syncraft.ast import Nothing, Marked, Choice, Many, Then, Collect, Token
        if isinstance(node, Nothing):
            return "Nothing"
        elif isinstance(node, Marked):
            return f"Marked(name={node.name})"
        elif isinstance(node, Choice):
            return f"Choice(kind={getattr(node.kind, 'name', node.kind)})"
        elif isinstance(node, Many):
            return "Many"
        elif isinstance(node, Then):
            return f"Then(kind={node.kind.name})"
        elif isinstance(node, Collect):
            return f"Collect({getattr(node.collector, '__name__', str(node.collector))})"
        elif isinstance(node, Token):
            return f"Token({str(node)})"
        elif hasattr(node, '__class__'):
            return node.__class__.__name__
        else:
            return str(node)

    def add_nodes_edges(dot, node, parent_id=None, node_id_gen=[0]):
        from syncraft.ast import Nothing, Marked, Choice, Many, Then, Collect
        node_id = f"n{node_id_gen[0]}"
        node_id_gen[0] += 1
        label = node_label(node)
        dot.node(node_id, label)
        if parent_id is not None:
            dot.edge(parent_id, node_id)

        # Walk children according to AST type
        if isinstance(node, Nothing):
            return
        elif isinstance(node, Marked):
            add_nodes_edges(dot, node.value, node_id, node_id_gen)
        elif isinstance(node, Choice):
            if node.value is not None:
                add_nodes_edges(dot, node.value, node_id, node_id_gen)
        elif isinstance(node, Many):
            for child in node.value:
                add_nodes_edges(dot, child, node_id, node_id_gen)
        elif isinstance(node, Then):
            add_nodes_edges(dot, node.left, node_id, node_id_gen)
            add_nodes_edges(dot, node.right, node_id, node_id_gen)
        elif isinstance(node, Collect):
            add_nodes_edges(dot, node.value, node_id, node_id_gen)
        # Token is a leaf
        # For other types, try to walk __dict__ if they are dataclasses
        elif hasattr(node, '__dataclass_fields__'):
            for f in node.__dataclass_fields__:
                v = getattr(node, f)
                if isinstance(v, (list, tuple)):
                    for item in v:
                        if hasattr(item, '__class__'):
                            add_nodes_edges(dot, item, node_id, node_id_gen)
                elif hasattr(v, '__class__') and v is not node:
                    add_nodes_edges(dot, v, node_id, node_id_gen)

    dot = graphviz.Digraph(format='svg')
    add_nodes_edges(dot, ast)
    return dot.pipe().decode('utf-8')


