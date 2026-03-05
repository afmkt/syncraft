"""Layout document vocabulary and renderer.

This module defines a small pretty-printing algebra used by generation APIs.
The goal is to let grammars produce structured formatting intent, not only plain
strings.

LayoutDoc vocabulary
--------------------
- ``Text(value)``: literal text.
- ``Sequence(parts)``: concatenation of child nodes.
- ``Group(body)``: choose between two rendering modes for ``body``:
    - *flat mode*: line-break nodes use fallback text.
    - *break mode*: line-break nodes emit ``\n`` and indentation.
    The renderer picks flat mode when the group's flat rendering fits within the
    available line width at the current column; otherwise it picks break mode.
- ``Line(body, fallback=" ")``: a conditional break.
    - In flat mode: emits ``fallback`` then ``body``.
    - In break mode: emits newline + current indentation then ``body``.
- ``SoftLine(body, fallback="")``: like ``Line`` but default fallback is empty,
    so it collapses to nothing in flat mode by default.
- ``Nest(body, level=1)``: increases indentation depth used by nested breaks in
    ``body`` by ``level`` (non-negative).

Semantics summary
-----------------
- Rendering state tracks ``(column, indent-depth, mode)``.
- ``Group`` performs a width check using the flat projection of its body.
- ``Nest`` only affects indentation of subsequent breaks, not immediate text.
- ``Line``/``SoftLine`` are the only nodes that can materialize line breaks.

``render(...)`` lowers AST-like values to this vocabulary with ``lower_to_layout``
and then renders them under width/indent constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

from syncraft.ast import AST, Alt, Lazy, Many, Nothing, ParseResult, Seq, Token, Unknown
from syncraft.utils import FrozenDict

@dataclass(frozen=True, slots=True)
class LayoutDoc:
    """Base layout document.

    Layout documents are rendered via `render(...)`, not `__str__`, so callers can
    supply constraints like max line width.
    """

    origin: Any | None = field(default=None, kw_only=True, repr=False, compare=False)

    def render(self, *, width: int = 80, indent: str = "    ") -> str:
        renderer = _Renderer(width=width, indent=indent)
        return renderer.render(self)

    @property
    def ast(self) -> Any:
        """Return the underlying AST-like value for this layout doc.

        If this doc was produced by ``lower_to_layout``, the original value is
        preserved and returned. For manually constructed docs without an origin,
        a best-effort structural value is synthesized.
        """
        return self.origin


@dataclass(frozen=True, slots=True)
class Text(LayoutDoc):
    """Literal text fragment."""

    value: str
    @property
    def ast(self) -> Any:
        if self.origin is not None:
            return self.origin
        return self.value


@dataclass(frozen=True, slots=True)
class Sequence(LayoutDoc):
    """Concatenation node: render each part left-to-right."""

    parts: tuple[LayoutDoc, ...]
    @property
    def ast(self) -> Any:
        if self.origin is not None:
            return self.origin
        return Seq(value=tuple((part.ast, True) for part in self.parts))
    




@dataclass(frozen=True, slots=True)
class Group(LayoutDoc):
    """Width-sensitive choice: flat mode if it fits, otherwise break mode."""

    body: LayoutDoc
    @property
    def ast(self) -> Any:
        if self.origin is not None:
            return self.origin
        return self.body.ast


@dataclass(frozen=True, slots=True)
class Line(LayoutDoc):
    """Conditional break: newline in break mode, fallback text in flat mode."""

    body: LayoutDoc
    fallback: str = " "

    @property
    def ast(self) -> Any:
        if self.origin is not None:
            return self.origin
        return self.body.ast


@dataclass(frozen=True, slots=True)
class SoftLine(LayoutDoc):
    """Soft conditional break: same as Line, with empty flat fallback by default."""

    body: LayoutDoc
    fallback: str = ""

    @property
    def ast(self) -> Any:
        if self.origin is not None:
            return self.origin
        return self.body.ast


@dataclass(frozen=True, slots=True)
class Nest(LayoutDoc):
    """Increase indentation depth for nested breaks in ``body``."""

    body: LayoutDoc
    level: int = 1

    @property
    def ast(self) -> Any:
        if self.origin is not None:
            return self.origin
        return self.body.ast


class Breakability(str, Enum):
    NEVER = "never"
    OPTIONAL = "optional"
    REQUIRED = "required"


class Attach(str, Enum):
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


@dataclass(frozen=True)
class FormatSpec:
    """Core formatting specification with rendering semantics and optional policy metadata.
    
    Attributes:
        breakability: Line-break strategy (never, optional, required).
        attach: Token adjacency intent (none, left, right, both).
        indent: Extra indentation depth for nested breaks.
        attrs: Free-form policy metadata dict (e.g., kind, role, precedence, align_group).
    """
    breakability: Breakability = Breakability.NEVER
    attach: Attach = Attach.NONE
    indent: int = 0
    
    @classmethod
    def coerce(cls,
               *,
               breakability: Breakability | str,
               attach: Attach | str,
               indent: int,
               
               ) -> "FormatSpec":
        """Coerce and validate user-provided formatting parameters into FormatSpec.
        
        Args:
            kind, role, precedence: Policy metadata (moved to attrs dict).
            breakability, attach, indent: Core rendering semantics.
            attrs: Additional policy metadata mapping.
        """
        try:
            normalized_breakability = (
                breakability
                if isinstance(breakability, Breakability)
                else Breakability(breakability)
            )
        except ValueError as exc:
            valid = ", ".join(item.value for item in Breakability)
            raise ValueError(f"Invalid breakability {breakability!r}. Expected one of: {valid}") from exc

        try:
            normalized_attach = (
                attach
                if isinstance(attach, Attach)
                else Attach(attach)
            )
        except ValueError as exc:
            valid = ", ".join(item.value for item in Attach)
            raise ValueError(f"Invalid attach {attach!r}. Expected one of: {valid}") from exc

        if indent < 0:
            raise ValueError(f"indent must be >= 0, got {indent}")
        
        return cls(
            breakability=normalized_breakability,
            attach=normalized_attach,
            indent=indent
        )

    def __call__(self, body: LayoutDoc | AST | Any) -> LayoutDoc:
        """Apply this FormatSpec to a LayoutDoc, producing an Annotated node."""
        doc = lower_to_layout(body)
        body = Nest(doc, level=self.indent) if self.indent > 0 else doc

        if self.breakability is Breakability.OPTIONAL:
            wrapped: LayoutDoc = Group(body)
        elif self.breakability is Breakability.REQUIRED:
            raise ValueError("breakability='required' is not implemented yet")
        else:
            wrapped = body

        return wrapped





def text_of(value: Any) -> str:
    """Best-effort conversion of AST-like terminal values to text."""

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
        return replace(lower_to_layout(value.value), origin=value)
    if isinstance(value, Alt):
        if value.value is None:
            return Text("", origin=value)
        return replace(lower_to_layout(value.value), origin=value)
    if isinstance(value, Many):
        return Sequence(tuple(lower_to_layout(item) for item in value.value), origin=value)
    if isinstance(value, Seq):
        return Sequence(tuple(lower_to_layout(item) for item, _keep in value.value), origin=value)
    return Text(text_of(value), origin=value)


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
