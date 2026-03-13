

from __future__ import annotations
from typing import Any, Tuple
from dataclasses import dataclass, field, replace

from syncraft.ast import AST, Alt, Lazy, Many, ParseResult, Seq, Nothing, EOF, Unknown







@dataclass(frozen=True, slots=True)
class LayoutDoc:
    """Base layout document.

    Layout documents are rendered via `render(...)`, callers can
    supply constraints like max line width.
    """
    template: str = field(default="{0}", kw_only=True, repr=False, compare=False)
    ast: AST | Any = field(default=None, kw_only=True, repr=False, compare=False)

    @classmethod
    def from_ast(cls, value: Any) -> LayoutDoc:
        """
        Build LayoutDoc from AST tree
        """
        def terminal(value: Any) -> str:
            if isinstance(value, str):
                return value
            elif isinstance(value, bytes):
                return value.decode('utf-8', errors='replace')
            elif hasattr(value, "text"):
                return value.text
            elif isinstance(value, (Nothing, EOF, Unknown)):
                return ""
            else:
                return str(value)
                                  
        if isinstance(value, LayoutDoc):
            return value
        elif isinstance(value, Lazy):
            return replace(LayoutDoc.from_ast(value.value), ast=value)
        elif isinstance(value, Alt):
            if value.value is None:
                return Text(value="", ast=value)
            return replace(LayoutDoc.from_ast(value.value), ast=value)
        elif isinstance(value, Many):
            return Concat(parts=tuple(LayoutDoc.from_ast(item) for item in value.value), ast=value)
        elif isinstance(value, Seq):
            return Concat(parts=tuple(LayoutDoc.from_ast(item) for item, _keep in value.value), ast=value)
        return Text(value=terminal(value), ast=value)

    def render(self, *, width: int = 80, indent: str = "    ") -> str:
        renderer = _Renderer(width=width, indent=indent)
        return renderer.render(self).strip()
    
    def __str__(self) -> str:
        return self.render()

@dataclass(frozen=True, slots=True)
class Text(LayoutDoc):
    """
    Literal text fragment.
    Unbreakable: it always renders as-is, without line breaks, 
    even if it exceeds the available width.

    This is the atomic unit of rendering: 
    it has a fixed width equal to the length of its text content.
    """
    value: str = ""

@dataclass(frozen=True, slots=True)
class Concat(LayoutDoc):
    """
    Concatenation node: render each part left-to-right.
    The width of a Concat is the sum of the widths of its parts 
    if it doesn't contain Line.

    If it contains Line, its width is unbounded, 
    since Line can break into multiple lines.

    This class doesn't break lines by itself, but it can contain Line nodes that do.
    """
    parts: Tuple[LayoutDoc, ...]

    


@dataclass(frozen=True, slots=True)
class Group(LayoutDoc):
    """
    Width-sensitive choice: flat mode if it fits, otherwise break mode.
    """
    body: LayoutDoc = field(kw_only=True)
    


@dataclass(frozen=True, slots=True)
class Line(LayoutDoc):
    """
    Conditional break: newline in break mode, flat text in flat mode.
    flat: emitted in flat mode (default: "" = self.flat).
    broken: emitted in break mode (default: "\n" + indentation + "" = self.broken).

    its ast should be None, since it doesn't correspond to a specific AST node, 
    but rather a formatting intent.
    """
    flat: str = " "
    broken: str = ""



@dataclass(frozen=True, slots=True)
class Nest(LayoutDoc):
    """Increase indentation depth for nested breaks in ``body``."""
    body: LayoutDoc = field(kw_only=True)
    level: int = 0






class _Renderer:
    @dataclass(frozen=True, slots=True)
    class RenderState:
        col: int
        depth: int
        flat: bool

    def __init__(self, *, width: int, indent: str) -> None:
        self.width = width
        self.indent = indent

    def render(self, doc: LayoutDoc) -> str:
        out, _ = self._render(doc, state=self.RenderState(col=0, depth=0, flat=False))
        return out

    def _flat_text(self, doc: LayoutDoc) -> str:
        out, _ = self._render(doc, state=self.RenderState(col=0, depth=0, flat=True))
        return out

    def _fits(self, doc: LayoutDoc, state: RenderState) -> bool:
        return state.col + len(self._flat_text(doc)) <= self.width

    def _render(self, doc: LayoutDoc, *, state: RenderState) -> tuple[str, RenderState]:
        if isinstance(doc, Text):
            s = doc.template.format(doc.value)
            next_state = self.RenderState(col=state.col + len(s), depth=state.depth, flat=state.flat)
            return s, next_state

        if isinstance(doc, Concat):
            chunks: list[str] = []
            cur_state = state
            for part in doc.parts:
                txt, cur_state = self._render(part, state=cur_state)
                chunks.append(txt)
            
            return doc.template.format("".join(chunks)), cur_state

        if isinstance(doc, Group):
            use_flat = state.flat or self._fits(doc.body, state)
            group_state = self.RenderState(col=state.col, depth=state.depth, flat=use_flat)
            txt, rendered_state = self._render(doc.body, state=group_state)
            return doc.template.format(txt), self.RenderState(col=rendered_state.col, depth=rendered_state.depth, flat=state.flat)

        if isinstance(doc, Nest):
            nested_state = self.RenderState(col=state.col, depth=state.depth + max(0, doc.level), flat=state.flat)
            txt, rendered_state = self._render(doc.body, state=nested_state)
            return doc.template.format(txt), self.RenderState(col=rendered_state.col, depth=state.depth, flat=state.flat)

        if isinstance(doc, Line):            
            if state.flat:
                s = doc.flat
                s = doc.template.format(s)
                next_state = self.RenderState(col=state.col + len(s), depth=state.depth, flat=state.flat)
                return s, next_state
            else:
                s = doc.broken
                pad = self.indent * state.depth
                s = doc.template.format(s)
                next_state = self.RenderState(col=len(pad) + len(s), depth=state.depth, flat=state.flat)
                return "\n" + pad + s, next_state

        
        raise TypeError(f"Unsupported LayoutDoc node: {type(doc)!r}")


def render(value: ParseResult | LayoutDoc | Any, *, width: int = 80, indent: str = "    ") -> str:
    """Render a value to text through the LayoutDoc domain.

    Accepts either an existing LayoutDoc or AST-like values and lowers them
    using the default safe lowering strategy.
    """
    doc = LayoutDoc.from_ast(value)
    return doc.render(width=width, indent=indent)


