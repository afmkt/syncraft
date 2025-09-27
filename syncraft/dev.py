from __future__ import annotations
import builtins
import io
from typing import Tuple, Any, Set, Optional, List, Dict, Mapping, Iterator, Union
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







def syntax2svg(
    syntax: Syntax[Any, Any],
    *,
    max_depth: Optional[int] = None,
) -> Optional[str]:
    try:
        from railroad import (  # type: ignore
            Diagram,
            Terminal,
            Sequence,
            Choice,
            OneOrMore,
            Comment,
            Optional as RROptional,
        )

        try:  # ZeroOrMore is optional in older railroad versions
            from railroad import ZeroOrMore  # type: ignore
        except ImportError:  # pragma: no cover - best effort rendering
            ZeroOrMore = None  # type: ignore
    except ImportError:
        return None

    return None

def ast2svg(ast: Any) -> Optional[str]:
    """
    Generate SVG visualization for a Syncraft AST node using graphviz.
    Returns SVG string or None if graphviz is not available.
    """
    try:
        import graphviz  # type: ignore
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


