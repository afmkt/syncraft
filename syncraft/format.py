from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from syncraft.ast import Alt, Lazy, Many, Nothing, ParseResult, Seq, Token, Unknown


@dataclass(frozen=True, slots=True)
class LayoutDoc:
    """Base layout document.

    Layout documents are rendered via `render(...)`, not `__str__`, so callers can
    supply constraints like max line width.
    """

    def render(self, *, width: int = 80, indent: str = "    ") -> str:
        renderer = _Renderer(width=width, indent=indent)
        return renderer.render(self)


@dataclass(frozen=True, slots=True)
class Text(LayoutDoc):
    value: str


@dataclass(frozen=True, slots=True)
class Sequence(LayoutDoc):
    """Internal concatenation node (not intended for direct user construction)."""

    parts: tuple[LayoutDoc, ...]


@dataclass(frozen=True, slots=True)
class Group(LayoutDoc):
    """Try to render flat; if it does not fit, render in break mode."""

    body: LayoutDoc


@dataclass(frozen=True, slots=True)
class Line(LayoutDoc):
    """Hard line break in break mode, fallback text in flat mode."""

    body: LayoutDoc
    fallback: str = " "


@dataclass(frozen=True, slots=True)
class SoftLine(LayoutDoc):
    """Soft line break; similar to Line but defaults to empty fallback."""

    body: LayoutDoc
    fallback: str = ""


@dataclass(frozen=True, slots=True)
class Nest(LayoutDoc):
    """Increase indentation in break mode for nested content."""

    body: LayoutDoc
    level: int = 1


def text_of(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Token):
        return text_of(value.text)
    if isinstance(value, tuple):
        return "".join(text_of(x) for x in value)
    if value is Nothing:
        return ""
    if isinstance(value, Unknown):
        return ""
    return str(value)


def lower_to_layout(value: Any) -> LayoutDoc:
    """Lower parser/generator values to a LayoutDoc tree.

    Safe default lowering owned by the library:
    - Seq -> Sequence(children)
    - Many -> Sequence(children)
    - Alt/Lazy -> unwrap
    - terminals -> Text
    """
    if isinstance(value, LayoutDoc):
        return value
    if isinstance(value, Lazy):
        return lower_to_layout(value.value)
    if isinstance(value, Alt):
        if value.value is None:
            return Text("")
        return lower_to_layout(value.value)
    if isinstance(value, Many):
        return Sequence(tuple(lower_to_layout(item) for item in value.value))
    if isinstance(value, Seq):
        return Sequence(tuple(lower_to_layout(item) for item, _keep in value.value))
    return Text(text_of(value))


class _Renderer:
    def __init__(self, *, width: int, indent: str) -> None:
        self.width = width
        self.indent = indent

    def render(self, doc: LayoutDoc) -> str:
        out, _, _ = self._render(doc, col=0, depth=0, flat=False)
        return out

    def _flat_text(self, doc: LayoutDoc) -> str:
        out, _, _ = self._render(doc, col=0, depth=0, flat=True)
        return out

    def _fits(self, doc: LayoutDoc, col: int) -> bool:
        return col + len(self._flat_text(doc)) <= self.width

    def _render(self, doc: LayoutDoc, *, col: int, depth: int, flat: bool) -> tuple[str, int, int]:
        if isinstance(doc, Text):
            s = doc.value
            return s, col + len(s), depth

        if isinstance(doc, Sequence):
            chunks: list[str] = []
            cur_col = col
            cur_depth = depth
            for part in doc.parts:
                txt, cur_col, cur_depth = self._render(part, col=cur_col, depth=cur_depth, flat=flat)
                chunks.append(txt)
            return "".join(chunks), cur_col, cur_depth

        if isinstance(doc, Group):
            use_flat = flat or self._fits(doc.body, col)
            return self._render(doc.body, col=col, depth=depth, flat=use_flat)

        if isinstance(doc, Nest):
            next_depth = depth + max(0, doc.level)
            return self._render(doc.body, col=col, depth=next_depth, flat=flat)

        if isinstance(doc, Line):
            if flat:
                s = doc.fallback
                txt, next_col, next_depth = self._render(doc.body, col=col + len(s), depth=depth, flat=flat)
                return s + txt, next_col, next_depth
            pad = self.indent * depth
            txt, next_col, next_depth = self._render(doc.body, col=len(pad), depth=depth, flat=flat)
            return "\n" + pad + txt, next_col, next_depth

        if isinstance(doc, SoftLine):
            if flat:
                s = doc.fallback
                txt, next_col, next_depth = self._render(doc.body, col=col + len(s), depth=depth, flat=flat)
                return s + txt, next_col, next_depth
            pad = self.indent * depth
            txt, next_col, next_depth = self._render(doc.body, col=len(pad), depth=depth, flat=flat)
            return "\n" + pad + txt, next_col, next_depth

        raise TypeError(f"Unsupported LayoutDoc node: {type(doc)!r}")


def render(value: ParseResult | LayoutDoc | Any, *, width: int = 80, indent: str = "    ") -> str:
    """Render a value to text through the LayoutDoc domain.

    Accepts either an existing LayoutDoc or AST-like values and lowers them
    using the default safe lowering strategy.
    """
    doc = lower_to_layout(value)
    return doc.render(width=width, indent=indent)
