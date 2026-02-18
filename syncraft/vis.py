from __future__ import annotations
import io
from typing import Tuple, Any, Set, Optional, List, Dict, ClassVar
from dataclasses import dataclass
from syncraft.syntax import (
    SyntaxSpec,
    LazySpec,
    ManySpec,
    LexSpec,    
    SeqSpec,
    AltSpec,
)

import xml.dom.minidom
import xml.etree.ElementTree as ET
@dataclass(frozen=True, slots=True)
class SVGVisualization:
    svg: str
    style: Optional[str]
    RAILROAD_CSS: ClassVar[str] = """
    <style>
    /* CSS based on the railroad-diagrams original style */
    .railroad-diagram svg {
    background-color:hsl(30,20%,95%);
    }
    .railroad-diagram path {
    stroke-width:3;
    stroke:black;
    fill:rgba(0,0,0,0);
    }
    .railroad-diagram text {
    font:bold 14px monospace;
    text-anchor:middle;
    }
    .railroad-diagram text.label {
    text-anchor:start;
    }
    .railroad-diagram text.comment {
    font:italic 12px monospace;
    }
    .railroad-diagram rect {
    stroke-width:3;
    stroke:black;
    fill:hsl(120,100%,90%);
    }
    .railroad-diagram rect.non-terminal {
    fill:hsl(120,100%,90%);
    }
    .railroad-diagram rect.terminal {
    fill:hsl(0,0%,100%);
    }
    .railroad-diagram rect.skip {
    fill: hsl(30, 100%, 90%);
    }
    </style>
    """

    def _repr_svg_(self) -> str:
        if self.style:
            return f"<style>{self.style}</style>\n{self.svg}"
        return self.svg

    def __repr__(self) -> str:
        try:
            root = ET.fromstring(self.svg)
            def clean_element(elem: ET.Element) -> None:
                if elem.text:
                    elem.text = elem.text.strip()
                if elem.tail:
                    elem.tail = elem.tail.strip()
                for child in elem:
                    clean_element(child)

            clean_element(root)
            pretty_svg = ET.tostring(root, encoding='unicode', short_empty_elements=True)
            return f"SVGVisualization({pretty_svg})"
        except ET.ParseError:
            return f"SVGVisualization({str(self)})"

    def __str__(self) -> str:
        try:
            dom = xml.dom.minidom.parseString(self.svg)
            pretty_svg = dom.toprettyxml(indent="  ")
            return pretty_svg.strip()
        except Exception:
            return self.svg
    



def syntax2svg(syntax: SyntaxSpec, max_depth: int) -> Optional[SVGVisualization]:
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

        try:  # NonTerminal is optional depending on version
            from railroad import NonTerminal  # type: ignore
        except ImportError:  # pragma: no cover - best effort rendering
            NonTerminal = None  # type: ignore
    except ImportError:
        return None

    nodes_with_depth: List[Tuple[int, SyntaxSpec]] = list(syntax.walk(max_depth=max_depth))
    if not nodes_with_depth:
        return None

    nodes: List[SyntaxSpec] = [node for _depth, node in nodes_with_depth]

    from collections import defaultdict

    children_map: Dict[SyntaxSpec, List[SyntaxSpec]] = defaultdict(list)
    for parent, s in syntax.graph(max_depth=max_depth).edges.items():
        for child in s:
            children_map[parent].append(child)

    # Tarjan's algorithm to detect strongly connected components
    index_counter = [0]
    indices: Dict[SyntaxSpec, int] = {}
    lowlinks: Dict[SyntaxSpec, int] = {}
    stack: List[SyntaxSpec] = []
    on_stack: Set[SyntaxSpec] = set()
    components: List[Tuple[SyntaxSpec, ...]] = []
    component_of: Dict[SyntaxSpec, int] = {}

    def strongconnect(node: SyntaxSpec) -> None:
        idx = index_counter[0]
        index_counter[0] += 1
        indices[node] = idx
        lowlinks[node] = idx
        stack.append(node)
        on_stack.add(node)

        for child in children_map.get(node, []):
            if child not in indices:
                strongconnect(child)
                lowlinks[node] = min(lowlinks[node], lowlinks[child])
            elif child in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[child])

        if lowlinks[node] == indices[node]:
            component: List[SyntaxSpec] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                component_of[member] = len(components)
                if member is node:
                    break
            components.append(tuple(component))

    for node in nodes:
        if node not in indices:
            strongconnect(node)

    # Cache of constructed diagram items per SyntaxSpec
    diagram_cache: Dict[SyntaxSpec, Any] = {}
    placeholder_cache: Dict[SyntaxSpec, Any] = {}

    def shorten(value: Any, *, limit: int = 40) -> str:
        import re
        from enum import Enum

        if isinstance(value, Enum):
            rep = f"{value.__class__.__name__}.{value.name}"
        elif isinstance(value, (str, bytes)):
            rep = repr(value)
        elif hasattr(value, "pattern") and hasattr(value, "flags"):
            rep = f"/{getattr(value, 'pattern', '')}/"
        else:
            rep = repr(value)
        rep = rep.replace("\n", "\\n")
        rep = re.sub(r"\s+", " ", rep)
        if len(rep) > limit:
            rep = rep[: limit - 1] + "…"
        return rep

    def spec_label(node: SyntaxSpec) -> str:
        if isinstance(node, LexSpec):
            return node.fname
        if isinstance(node, SeqSpec):
            return "Seq"
        if isinstance(node, AltSpec):
            return "Alt"
        if isinstance(node, ManySpec):
            upper = "∞" if node.at_most is None else str(node.at_most)
            return f"Many[{node.at_least},{upper}]"
        if isinstance(node, LazySpec):
            return "Lazy"
        
        return type(node).__name__

    def placeholder(node: SyntaxSpec) -> Any:
        if node not in placeholder_cache:
            label = spec_label(node)
            if NonTerminal is not None:
                placeholder_cache[node] = NonTerminal(label)
            else:
                placeholder_cache[node] = Comment(f"↺ {label}")
        return placeholder_cache[node]

    def build_factory(spec: LexSpec) -> Any:
        kwargs = dict(spec.kwargs)
        if spec.name == "token":
            text = kwargs.get("text")
            token_type = kwargs.get("token_type")
            pieces: List[str] = []
            if text is not None:
                pieces.append(shorten(text))
            if token_type is not None:
                pieces.append(f"<{shorten(token_type)}>")
            label = " ".join(pieces) if pieces else "token"
            return Terminal(label)
        if spec.name == "success":
            return Comment(f"ε ⇒ {shorten(kwargs.get('value'))}" if kwargs else "ε ⇒ value")
        if spec.name == "fail":
            return Comment(f"fail {shorten(kwargs.get('error'))}" if kwargs else "")

        label_parts: List[str] = []
        if kwargs:
            label_parts.extend(f"{key}={shorten(value)}" for key, value in sorted(kwargs.items()))
        label = spec.fname if not label_parts else f"{spec.fname}({', '.join(label_parts)})"
        if NonTerminal is not None:
            return NonTerminal(label)
        return Terminal(label)

    def many_diagram(spec: ManySpec, inner: Any) -> Any:
        at_least, at_most = spec.at_least, spec.at_most
        if at_least == 0 and at_most == 1:
            return RROptional(inner)
        if at_least == 0 and at_most is None:
            if ZeroOrMore is not None:
                return ZeroOrMore(inner)
            return Sequence(Comment("repeat 0+"), inner)
        if at_least == 1 and at_most is None:
            return OneOrMore(inner)
        if at_least == at_most:
            return Sequence(Comment(f"repeat exactly {at_least}"), inner)
        upper = "∞" if at_most is None else str(at_most)
        return Sequence(Comment(f"repeat {at_least}..{upper}"), inner)

    # Process components in the order produced by Tarjan (leaf-most first)
    for comp in components:
        comp_nodes = list(comp)
        comp_idx = component_of[comp_nodes[0]]
        # Determine which children stay inside the component (for recursion placeholders)
        for node in comp_nodes:
            child_items: List[Any] = []
            for child in children_map.get(node, []):
                if component_of.get(child) == comp_idx:
                    child_items.append(placeholder(child))
                else:
                    child_items.append(diagram_cache.get(child, placeholder(child)))

            if isinstance(node, LazySpec):
                diagram_cache[node] = child_items[0] if child_items else Comment("lazy …")
                continue

            if isinstance(node, SeqSpec):
                diagram_cache[node] = Sequence(*child_items)
                continue

            if isinstance(node, AltSpec):
                diagram_cache[node] = Choice(0, *child_items) 
                continue

            if isinstance(node, ManySpec):
                inner = child_items[0] if child_items else Comment("…")
                diagram_cache[node] = many_diagram(node, inner)
                continue

            if isinstance(node, LexSpec):
                diagram_cache[node] = build_factory(node)
                continue

            # Fallback for unknown spec types
            diagram_cache[node] = Comment(spec_label(node))

    root_item = diagram_cache.get(syntax, placeholder(syntax))
    if root_item is None:
        return None

    try:
        diagram = Diagram(root_item)
        write_svg_string = getattr(diagram, "writeSvgString", None)
        if callable(write_svg_string):
            svg_result = write_svg_string()
            if isinstance(svg_result, str):
                return SVGVisualization(svg=svg_result, style=SVGVisualization.RAILROAD_CSS)
                
            if svg_result is not None:
                return SVGVisualization(svg=str(svg_result), style=SVGVisualization.RAILROAD_CSS)
                
        buffer = io.StringIO()
        diagram.writeSvg(buffer.write)  # type: ignore[arg-type]
        return SVGVisualization(svg=buffer.getvalue(), style=SVGVisualization.RAILROAD_CSS)
        
    except TypeError:
        buffer = io.StringIO()
        diagram.writeSvg(buffer.write)  # type: ignore[arg-type]
        return SVGVisualization(svg=buffer.getvalue(), style=SVGVisualization.RAILROAD_CSS)


def ast2svg(ast: Any, max_depth:int) -> Optional[SVGVisualization]:
    """
    Generate SVG visualization for a Syncraft AST node using graphviz.
    Returns SVG string or None if graphviz is not available.
    """
    try:
        import graphviz  # type: ignore
    except ImportError:
        return None

    def node_label(node):
        from syncraft.ast import Nothing, Alt, Many, Seq, Token
        if node is Nothing:
            return "Nothing"
        
        elif isinstance(node, Alt):
            return "Alt"
        elif isinstance(node, Many):
            return "Many"
        elif isinstance(node, Seq):
            return "Seq"
        
        elif isinstance(node, Token):
            return f"Token({str(node)})"
        elif hasattr(node, '__class__'):
            return node.__class__.__name__
        else:
            return str(node)

    def add_nodes_edges(dot, node, *, depth, parent_id=None, node_id_gen=[0]):
        if depth == 0:
            return
        from syncraft.ast import Nothing, Alt, Many, Seq
        node_id = f"n{node_id_gen[0]}"
        node_id_gen[0] += 1
        label = node_label(node)
        dot.node(node_id, label)
        if parent_id is not None:
            dot.edge(parent_id, node_id)

        # Walk children according to AST type
        if node is Nothing:
            return
        elif isinstance(node, Alt):
            if node.value is not None:
                add_nodes_edges(dot, node.value, depth=depth-1, parent_id=node_id, node_id_gen=node_id_gen)
        elif isinstance(node, Many):
            for child in node.value:
                add_nodes_edges(dot, child, depth=depth-1, parent_id=node_id, node_id_gen=node_id_gen)
        elif isinstance(node, Seq):
            for child in node.value:
                add_nodes_edges(dot, child, depth=depth-1, parent_id=node_id, node_id_gen=node_id_gen)

        # Token is a leaf
        # For other types, try to walk __dict__ if they are dataclasses
        elif hasattr(node, '__dataclass_fields__'):
            for f in node.__dataclass_fields__:
                v = getattr(node, f)
                if isinstance(v, (list, tuple)):
                    for item in v:
                        if hasattr(item, '__class__'):
                            add_nodes_edges(dot, item, depth=depth-1, parent_id=node_id, node_id_gen=node_id_gen)
                elif hasattr(v, '__class__') and v is not node:
                    add_nodes_edges(dot, v, depth=depth-1, parent_id=node_id, node_id_gen=node_id_gen)

    dot = graphviz.Digraph(format='svg')
    add_nodes_edges(dot, ast, depth=max_depth)
    return SVGVisualization(svg=dot.pipe().decode('utf-8'), style=None)



