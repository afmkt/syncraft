from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence as TypingSequence, Tuple

from syncraft.ast import SyncraftError
from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder

__all__ = [
    "RegexExpr",
    "Literal",
    "Dot",
    "Concat",
    "Alternation",
    "Repeat",
    "CharClass",
    "Quantifier",
    "parse_regex",
    "compile_regex",
]


# --------------------------------------------------------------------------------------
# AST nodes representing the supported regex subset. Keeping the tree explicit makes it
# easier to transform into FABuilder instances (or future backends) and provides a place
# to hang diagnostics.
# --------------------------------------------------------------------------------------


class RegexExpr:
    """Marker base class for regex AST nodes."""


@dataclass
class Literal(RegexExpr):
    value: str


@dataclass
class Dot(RegexExpr):
    pass


@dataclass
class Concat(RegexExpr):
    parts: Tuple[RegexExpr, ...]


@dataclass
class Alternation(RegexExpr):
    options: Tuple[RegexExpr, ...]


@dataclass
class Quantifier:
    minimum: int
    maximum: Optional[int]

    def apply(self, builder: FABuilder[str]) -> FABuilder[str]:
        if self.minimum == 0 and self.maximum is None:
            return builder.star
        if self.minimum == 1 and self.maximum is None:
            return builder.plus
        if self.minimum == 0 and self.maximum == 1:
            return ~builder
        return builder.many(at_least=self.minimum, at_most=self.maximum)


@dataclass
class Repeat(RegexExpr):
    expr: RegexExpr
    quant: Quantifier


@dataclass
class CharClass(RegexExpr):
    negated: bool
    ranges: Tuple[Tuple[str, str], ...]


# --------------------------------------------------------------------------------------
# Lexer configuration.
# --------------------------------------------------------------------------------------


def _make_concat(parts: TypingSequence[RegexExpr]) -> RegexExpr:
    if not parts:
        return Literal("")
    if len(parts) == 1:
        return parts[0]
    return Concat(tuple(parts))


def _combine_alt(base: RegexExpr, rest: TypingSequence[RegexExpr]) -> RegexExpr:
    if not rest:
        return base
    return Alternation((base,) + tuple(rest))


def _range_tuple(start: str, end: Optional[str]) -> Tuple[str, str]:
    finish = start if end is None else end
    return start, finish


def _char_class_builder(
    negated: bool,
    ranges: TypingSequence[Tuple[str, str]],
    universe: CodeUniverse[str],
) -> FABuilder[str]:
    baseline = set(_ASCII_PRINTABLE) | {"\n", "\r", "\t"}
    allowed: set[str] = set()
    for start, end in ranges:
        lower = ord(start)
        upper = ord(end)
        if upper < lower:
            raise SyncraftError(
                "Character range upper bound must be >= lower bound",
                offender=(start, end),
                expect="start <= end",
            )
        allowed.update(chr(code) for code in range(lower, upper + 1))
    if not allowed:
        raise SyncraftError("Character class is empty", offender=ranges, expect="at least one literal")
    if negated:
        allowed = baseline.difference(allowed)
        if not allowed:
            raise SyncraftError("Negated character class removed every candidate", offender=ranges)
    return FABuilder.oneof("".join(sorted(allowed, key=lambda c: (ord(c), c))))


_ASCII_PRINTABLE = tuple(chr(i) for i in range(32, 127))
_DOT_CHARS = "".join(_ASCII_PRINTABLE)


class _RegexParser:
    def __init__(self, pattern: str) -> None:
        self._pattern = pattern
        self._length = len(pattern)
        self._index = 0

    def parse(self) -> RegexExpr:
        expr = self._parse_alternation()
        if self._index != self._length:
            raise SyncraftError(
                "Unexpected trailing input in regex",
                offender=self._pattern[self._index :],
                expect="end of pattern",
            )
        return expr

    def _parse_alternation(self) -> RegexExpr:
        terms: List[RegexExpr] = [self._parse_concat()]
        while self._match("|"):
            terms.append(self._parse_concat())
        return _combine_alt(terms[0], terms[1:])

    def _parse_concat(self) -> RegexExpr:
        parts: List[RegexExpr] = []
        while not self._at_end() and self._peek() not in ")|":
            parts.append(self._parse_repeat())
        return _make_concat(parts)

    def _parse_repeat(self) -> RegexExpr:
        base = self._parse_atom()
        quant = self._parse_quantifier()
        if quant is None:
            return base
        return Repeat(expr=base, quant=quant)

    def _parse_quantifier(self) -> Optional[Quantifier]:
        if self._match("*"):
            return Quantifier(0, None)
        if self._match("+"):
            return Quantifier(1, None)
        if self._match("?"):
            return Quantifier(0, 1)
        if not self._match("{"):
            return None
        start_index = self._index
        minimum = self._parse_number(message="Quantifier requires a number", index=start_index)
        if self._match(","):
            if self._match("}"):
                return Quantifier(minimum, None)
            maximum = self._parse_number(
                message="Quantifier upper bound requires a number",
                index=self._index,
            )
            if maximum < minimum:
                raise SyncraftError(
                    "Quantifier upper bound must be >= lower bound",
                    offender=(minimum, maximum),
                )
            self._expect("}")
            return Quantifier(minimum, maximum)
        self._expect("}")
        return Quantifier(minimum, minimum)

    def _parse_atom(self) -> RegexExpr:
        if self._at_end():
            raise SyncraftError("Unexpected end of pattern", offender=self._pattern)
        if self._match("("):
            expr = self._parse_alternation()
            self._expect(")")
            return expr
        if self._match("."):
            return Dot()
        if self._match("["):
            return self._parse_char_class()
        if self._match("\\"):
            return Literal(self._parse_escape())
        ch = self._consume()
        if ch in ")|":
            self._raise("Unexpected reserved character", self._index - 1)
        return Literal(ch)

    def _parse_char_class(self) -> CharClass:
        negated = self._match("^")
        ranges: List[Tuple[str, str]] = []
        while True:
            if self._at_end():
                raise SyncraftError("Unterminated character class", offender=self._pattern)
            if self._peek() == "]" and not ranges:
                literal = self._consume()
                ranges.append(_range_tuple(literal, None))
                continue
            if self._peek() == "]":
                break
            start = self._class_char(allow_dash=True)
            if self._match("-") and not self._peek_equals("]"):
                end = self._class_char(allow_dash=False)
                ranges.append(_range_tuple(start, end))
            else:
                ranges.append(_range_tuple(start, None))
        self._expect("]")
        return CharClass(negated=negated, ranges=tuple(ranges))

    def _class_char(self, *, allow_dash: bool) -> str:
        if self._match("\\"):
            return self._parse_escape()
        ch = self._consume()
        if ch == "-" and not allow_dash:
            self._raise("Unexpected '-' in character class", self._index - 1)
        if ch == "]":
            self._raise("Unexpected ']' in character class", self._index - 1)
        return ch

    def _parse_escape(self) -> str:
        if self._at_end():
            raise SyncraftError("Incomplete escape sequence", offender=self._pattern)
        ch = self._consume()
        if ch == "n":
            return "\n"
        if ch == "r":
            return "\r"
        if ch == "t":
            return "\t"
        return ch

    def _parse_number(self, *, message: str, index: int) -> int:
        start = self._index
        while not self._at_end() and self._peek().isdigit():
            self._index += 1
        if start == self._index:
            self._raise(message, index)
        return int(self._pattern[start:self._index])

    def _match(self, symbol: str) -> bool:
        if self._peek_equals(symbol):
            self._index += len(symbol)
            return True
        return False

    def _peek_equals(self, symbol: str) -> bool:
        return self._pattern.startswith(symbol, self._index)

    def _peek(self) -> str:
        return self._pattern[self._index]

    def _consume(self) -> str:
        ch = self._pattern[self._index]
        self._index += 1
        return ch

    def _expect(self, symbol: str) -> None:
        if not self._match(symbol):
            self._raise(f"Expected '{symbol}'", self._index)

    def _raise(self, message: str, index: int) -> None:
        snippet = self._pattern[index : index + 10]
        raise SyncraftError(message, offender=snippet, expect=self._pattern)

    def _at_end(self) -> bool:
        return self._index >= self._length


def _expr_to_builder(expr: RegexExpr, universe: CodeUniverse[str]) -> FABuilder[str]:
    if isinstance(expr, Literal):
        return FABuilder.literal(expr.value)
    if isinstance(expr, Dot):
        return FABuilder.oneof(_DOT_CHARS)
    if isinstance(expr, Concat):
        builders = [_expr_to_builder(part, universe) for part in expr.parts]
        result = builders[0]
        for builder in builders[1:]:
            result = result + builder
        return result
    if isinstance(expr, Alternation):
        builders = [_expr_to_builder(option, universe) for option in expr.options]
        result = builders[0]
        for builder in builders[1:]:
            result = result | builder
        return result
    if isinstance(expr, Repeat):
        inner = _expr_to_builder(expr.expr, universe)
        return expr.quant.apply(inner)
    if isinstance(expr, CharClass):
        return _char_class_builder(expr.negated, expr.ranges, universe)
    raise SyncraftError("Unsupported regex expression node", offender=expr)


def parse_regex(pattern: str, *, universe: CodeUniverse[str] | None = None) -> RegexExpr:
    if not isinstance(pattern, str):
        raise SyncraftError("Regex pattern must be a string", offender=pattern, expect="str")
    _ = universe or CodeUniverse.ascii()
    parser = _RegexParser(pattern)
    return parser.parse()


def compile_regex(
    pattern: str,
    *,
    universe: CodeUniverse[str] | None = None,
    tag: Optional[str] = None,
) -> FABuilder[str]:
    uni = universe or CodeUniverse.ascii()
    expr = parse_regex(pattern, universe=uni)
    builder = _expr_to_builder(expr, uni)
    return builder.tagged(tag) if tag is not None else builder
