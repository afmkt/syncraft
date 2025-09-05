from __future__ import annotations
from typing import Tuple, Any, Set, Optional
from sqlglot.expressions import Expression
from syncraft.syntax import Syntax
from syncraft.algebra import  Left, Right, Error, Either, Algebra
from syncraft.parser import ParserState, Token


def rich_error(err: Error)->None:
    try:
        from rich import print
        from rich.table import Table as RichTable
        lst = err.to_list()
        leaf = lst[0]
        tbl = RichTable(title="Parser Error", show_lines=True)
        tbl.add_column("Leaf Parser Field", style="blue")
        tbl.add_column("Leaf Parser Value", style="yellow")
        flds: Set[str] = set(leaf.keys())
        for fld in sorted(flds):
            leaf_value = leaf.get(fld, "N/A")
            tbl.add_row(f"{fld}", f"{leaf_value}")
        print(tbl)
    except ImportError:
        print(err)


def rich_parser(p: Syntax)-> None:
    try:
        from rich import print
        print("Parser Debug Information:")
        print(repr(p))
    except ImportError:
        print(p)

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
                if isinstance(value, Expression):
                    return prefix + value.sql()
                elif isinstance(value, Token):
                    return prefix + f"{value.token_type.name}({value.text})"
                elif isinstance(value, Syntax):
                    return prefix + (value.meta.name or 'N/A')
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
        print(this)
        print(state)
        print(result)




def syntax2svg(syntax: Syntax[Any, Any]) -> Optional[str]:
    try:
        from railroad import Diagram, Terminal, Sequence, Choice, OneOrMore, Comment, Group, Optional as RROptional
        def to_railroad(s: Syntax[Any, Any]):
            meta = s.meta
            if meta is None or meta.name is None:
                return Terminal(str(s))
            children = [to_railroad(p) for p in meta.parameter]
            if meta.name in ('>>', '//', '+'):
                assert len(children) == 2
                return Sequence(children[0], children[1])
            elif meta.name == '|':
                assert len(children) == 2
                return Choice(0, children[0], children[1])
            elif meta.name in ('*',):
                assert len(children) == 1
                return OneOrMore(children[0])
            elif meta.name in ('~',):
                assert len(children) == 1
                return RROptional(children[0])
            elif meta.name.startswith('token'):
                return Terminal(meta.name)
            elif meta.name == "sep_by":
                assert len(children) == 2
                return Sequence(children[0], OneOrMore(Sequence(children[1], children[0])))
            elif meta.name.startswith('to'):
                assert len(children) == 1
                return Sequence(Comment(meta.name), children[0])
            elif meta.name.startswith('bind'):
                assert len(children) == 1
                return Sequence(Comment(meta.name), children[0])
            elif meta.name.startswith('mark'):
                assert len(children) == 1
                return Sequence(Comment(meta.name), children[0])
            elif meta.name.startswith('when'):
                assert len(children) == 2
                return Group(Choice(0, children[0], children[1]), 
                             label="Conditional on env/config")
            elif meta.name.startswith('success'):
                return Terminal(meta.name)
            elif meta.name.startswith('fail'):
                return Terminal(meta.name)
            elif meta.name.startswith('lazy'):
                return Terminal(meta.name)
            elif meta.name == 'anything':
                return Terminal(meta.name)
            elif meta.name == 'until':
                return Terminal(meta.name)
            else:
                return Sequence(Terminal(meta.name), *(children if children else []))

        diagram = Diagram(to_railroad(syntax))
        return diagram.writeSvgString()
    except ImportError:
        return None

def ast2svg(ast: Any) -> Optional[str]:
    """
    Generate SVG visualization for a Syncraft AST node using graphviz.
    Returns SVG string or None if graphviz is not available.
    """
    try:
        import graphviz
    except ImportError:
        return None

    def node_label(node):
        from syncraft.ast import Nothing, Marked, Choice, Many, Then, Collect, Custom, Token
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
        elif isinstance(node, Custom):
            return f"Custom(meta={node.meta})"
        elif isinstance(node, Token):
            return f"Token({node.token_type.name}: {node.text})"
        elif hasattr(node, '__class__'):
            return node.__class__.__name__
        else:
            return str(node)

    def add_nodes_edges(dot, node, parent_id=None, node_id_gen=[0]):
        from syncraft.ast import Nothing, Marked, Choice, Many, Then, Collect, Custom, Token
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
        elif isinstance(node, Custom):
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


