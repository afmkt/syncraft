from __future__ import annotations


from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any, Type, Mapping
import unicodedata
import random
import re as pyre

from syncraft.algebra import Error, EntryCategory 
from syncraft.syntax import Syntax
from syncraft.fa import Builder, DEFAULT_TAG
from syncraft.alphabet import Alphabet
from syncraft.grammar import Grammar, lazy, rule, grammar
from functools import reduce
from syncraft.bimap import DataError, Not
from syncraft.ast import Nothing, SyncraftError
from functools import cached_property




class RegexError(SyncraftError):
    pass


@dataclass(frozen=True)
class RegexNode:
    @staticmethod
    def _casefold_variants(ch: str) -> Tuple[str, ...]:
        variants = []
        for candidate in (ch, ch.casefold(), ch.lower(), ch.upper()):
            if len(candidate) != 1:
                continue
            if candidate not in variants:
                variants.append(candidate)
        return tuple(variants)

    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        raise RegexError("Unsupported regex feature in lexer", offender=self)

    @cached_property
    def has_group(self) -> bool:
        return False

    @cached_property
    def effective(self) -> bool:
        """Whether this node can match any empty or non-empty string."""
        return True

    def syntax(
        self,
        *,
        syntax_cls: Type[Syntax],
        case_insensitive: bool = False,
        references: Mapping[str, Tuple[Syntax[Any, Any], bool]] | None = None,
    ) -> Tuple[Syntax[Any, Any], bool]:
        b = self.builder(case_insensitive=case_insensitive)
        return syntax_cls.lex(b), True


@dataclass(frozen=True)
class UnsupportedFeature(RegexNode):
    feature: str
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"Unsupported feature: {self.feature}" + (f" with args: {self.args}" if self.args else "") + (f" and kwargs: {self.kwargs}" if self.kwargs else "")
    


def unsuppoerted(feature: str, *args: Any, **kwargs: Any) -> UnsupportedFeature:
    return UnsupportedFeature(feature=feature, args=args, kwargs=kwargs)
    


class ShorthandKind(Enum):
    DIGIT = r'\d'
    NOT_DIGIT = r'\D'
    WORD = r'\w'
    NOT_WORD = r'\W'
    SPACE = r'\s'
    NOT_SPACE = r'\S'
    @classmethod
    def from_literal(cls, literal: str) -> ShorthandKind:        
        for kind in cls:
            if kind.value == literal:
                return kind
        raise RegexError(f"Unknown shorthand literal: {literal}", offender=literal, expect="One of \\d, \\D, \\w, \\W, \\s, \\S")

    @classmethod
    def to_literal(cls, kind: ShorthandKind) -> str:
        return kind.value    

@dataclass(frozen=True)
class ShorthandAtom(RegexNode):
    kind: ShorthandKind

    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        self.validate()
        if self.kind == ShorthandKind.DIGIT:
            return Builder.unicode_category(["Nd"])
        elif self.kind == ShorthandKind.NOT_DIGIT:
            return Builder.any(Alphabet(str)) - Builder.unicode_category(["Nd"])
        elif self.kind == ShorthandKind.WORD:
            return Builder.unicode_category(["Lu", "Ll", "Lt", "Lm", "Lo"]) | Builder.unicode_category(["Nd"]) | Builder.lit("_")
        elif self.kind == ShorthandKind.NOT_WORD:
            return Builder.any(Alphabet(str)) - (Builder.unicode_category(["Lu", "Ll", "Lt", "Lm", "Lo"]) | Builder.unicode_category(["Nd"]) | Builder.lit("_"))
        elif self.kind == ShorthandKind.SPACE:
            return Builder.unicode_category(["Zs"]) | Builder.oneof("\t\n\r\f\v")
        elif self.kind == ShorthandKind.NOT_SPACE:
            return Builder.any(Alphabet(str)) - (Builder.unicode_category(["Zs"]) | Builder.oneof("\t\n\r\f\v"))
        else:
            return super().builder()  # will raise RegexError for unsupported features

    def validate(self) -> None:
        if self.kind not in ShorthandKind:
            raise RegexError(f"Unsupported shorthand kind: {self.kind}", offender=self)


@dataclass(frozen=True)
class UnicodeCategoryAtom(RegexNode):
    categories: Tuple[str, ...]
    negated: bool = False   
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        self.validate()
        b: Builder[str] = Builder.none()
        for category in self.categories:
            b = b | Builder.unicode_category([category])
        if self.negated:
            b = Builder.any(Alphabet(str)) - b
        return b
    
    def validate(self) -> None:
        for category in self.categories:
            if category not in ["Lu", "Ll", "Lt", "Lm", "Lo", "L", "M", "N", "Nd", "Nl", "No", "P", "Pd", "Ps", "Pe", "S", "Sm", "Sc", "Z", "Zs", "C"]:
                raise RegexError("Unknown Unicode category in \\p{}", offender=category, expect="One of Lu, Ll, Lt, Lm, Lo, L, M, N, Nd, Nl, No, P, Pd, Ps, Pe, S, Sm, Sc, Z, Zs, C")


@dataclass(frozen=True)
class CharRange(RegexNode):
    start: str
    end: str
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        self.validate()
        return Builder.range(self.start, self.end)
    
    def validate(self) -> None:
        if self.start > self.end:
            raise RegexError(
                "Reversed range in character class",
                offender=self,
                expect="start <= end")



@dataclass(frozen=True)
class CharClassAtom(RegexNode):
    items: Tuple[Union[str, CharRange, ShorthandAtom, UnicodeCategoryAtom], ...]
    negated: bool = False
    @staticmethod
    def _builder_range_case_insensitive(start: str, end: str) -> Builder[str]:
        b: Builder[str] = Builder.none()
        for codepoint in range(ord(start), ord(end) + 1):
            ch = chr(codepoint)
            for variant in RegexNode._casefold_variants(ch):
                b = b | Builder.lit(variant)
        return b

    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        self.validate()
        b: Builder[str] = Builder.none()
        for item in self.items:
            if isinstance(item, str):
                if case_insensitive:
                    for variant in RegexNode._casefold_variants(item):
                        b = b | Builder.lit(variant)
                else:
                    b = b | Builder.lit(item)
            elif isinstance(item, CharRange):
                if case_insensitive:
                    b = b | self._builder_range_case_insensitive(item.start, item.end)
                else:
                    b = b | item.builder()
            else:
                b = b | item.builder(case_insensitive=case_insensitive)
        if self.negated:
            b = Builder.any(Alphabet(str)) - b
        return b

    def validate(self) -> None:
        for item in self.items:
            if isinstance(item, str):
                if item == "":
                    raise RegexError("Empty character in class", offender=item)
            elif not isinstance(item, (CharRange, ShorthandAtom, UnicodeCategoryAtom)):
                raise RegexError("Unsupported item in character class", offender=item)



    def syntax(
        self,
        *,
        syntax_cls: Type[Syntax],
        case_insensitive: bool = False,
        references: Mapping[str, Tuple[Syntax[Any, Any], bool]] | None = None,
    ) -> Tuple[Syntax[Any, Any], bool]:
        b = self.builder(case_insensitive=case_insensitive)
        # return syntax_cls.lex(b).bimap(_rp_forward, _rp_inverse)
        return syntax_cls.lex(b), True



class GroupKind(Enum):
    CAPTURE = auto()
    NON_CAPTURE = auto()
    SYNTAX_REF = auto()
    LOOKAHEAD = auto()
    NEG_LOOKAHEAD = auto()
    LOOKBEHIND = auto()
    NEG_LOOKBEHIND = auto()
    FLAGS = auto()
    FLAGS_SCOPED = auto()
    CONDITION_ASSERTION = auto()
    CONDITION_GROUP = auto()
    COMMENT= auto()

@dataclass(frozen=True)
class InlineFlags:
    enabled: Tuple[str, ...]
    disabled: Optional[Tuple[str, ...]] = None


@dataclass(frozen=True)
class GroupAtom(RegexNode):
    kind: GroupKind
    regex: Optional[Regex] = None
    name: Optional[str] = None
    inline_flags: Optional[InlineFlags] = None
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        self.validate()
        if self.kind in (GroupKind.CAPTURE, GroupKind.NON_CAPTURE):
            if self.regex is not None:
                inner = self.regex.builder(case_insensitive=case_insensitive)
                if self.name is not None:
                    return inner.tagged(self.name)
                else:
                    return inner
            else:
                raise NotImplementedError(f"Cannot build GroupAtom of kind: {self.kind}")
        elif self.kind == GroupKind.COMMENT:
            return Builder.none()
        elif self.kind == GroupKind.SYNTAX_REF:
            raise RegexError("Syntax references are only supported in Syntax.rp", offender=self)
        elif self.kind == GroupKind.FLAGS_SCOPED:
            if self.regex is None or self.inline_flags is None:
                raise RegexError("Invalid inline flags group", offender=self)
            flags = set(self.inline_flags.enabled)
            disabled = set(self.inline_flags.disabled or ())
            if disabled:
                raise RegexError("Inline flag disabling is not supported", offender=self, expect="Only (?i:...) is supported")
            if flags - {"i"}:
                raise RegexError("Unsupported inline flags", offender=self, expect="Only (?i:...) is supported")
            return self.regex.builder(case_insensitive=True)
        else:
            return super().builder()  # will raise RegexError for unsupported features
        
    def validate(self) -> None:
        if self.kind not in (GroupKind.CAPTURE, GroupKind.COMMENT, GroupKind.NON_CAPTURE, GroupKind.FLAGS_SCOPED, GroupKind.SYNTAX_REF):
            raise RegexError("Unsupported group type in lexer regex", offender=self)

    @cached_property
    def has_group(self) -> bool:
        if self.kind == GroupKind.NON_CAPTURE:
            # Non-capture groups themselves don't create a group, but inner groups do
            return self.regex.has_group if self.regex is not None else False
        return True

    @cached_property
    def effective(self) -> bool:
        if self.kind == GroupKind.SYNTAX_REF:
            return True
        return self.regex.effective if self.regex is not None else False

    def syntax(
        self,
        *,
        syntax_cls: Type[Syntax],
        case_insensitive: bool = False,
        references: Mapping[str, Tuple[Syntax[Any, Any], bool]] | None = None,
    ) -> Tuple[Syntax[Any, Any], bool]:
        self.validate()
        if self.kind == GroupKind.FLAGS_SCOPED:
            if self.regex is None or self.inline_flags is None:
                raise RegexError("Invalid inline flags group", offender=self)
            enabled = set(self.inline_flags.enabled)
            disabled = set(self.inline_flags.disabled or ())
            if disabled:
                raise RegexError("Inline flag disabling is not supported", offender=self, expect="Only (?i:...) is supported")
            if enabled - {"i"}:
                raise RegexError("Unsupported inline flags", offender=self, expect="Only (?i:...) is supported")
            return self.regex.syntax(syntax_cls=syntax_cls, case_insensitive=True, references=references)

        if self.kind == GroupKind.SYNTAX_REF:
            if self.name is None:
                raise RegexError("Syntax reference group is missing a name", offender=self)
            if references is None or self.name not in references:
                # Technically, we could resolve this at runtime against the parsing context.
                # However, that requires building Syntax at runtime as well(the parsing context only available at runtiime)
                # A dynamic syntax rule will break the round-tripping property of Syntax.rp, so we require explicit references to be provided at compile time.
                # Moreover, pattern reusing is fullfilled by external reference ready.
                # So we just raise error here to avoid the complexity of supporting dynamic references.
                raise RegexError("Unknown syntax reference in Syntax.rp", offender=self.name, expect="Provide refs={'name': Syntax(...)}")
            referenced = references[self.name]
            if not isinstance(referenced, (Syntax, tuple)):
                raise RegexError("Invalid syntax reference in Syntax.rp", offender=referenced, expect="Syntax instance")
            if isinstance(referenced, tuple):
                if len(referenced) != 2 or not isinstance(referenced[0], Syntax) or not isinstance(referenced[1], bool):
                    raise RegexError("Invalid syntax reference tuple in Syntax.rp", offender=referenced, expect="Tuple[Syntax, bool]")
            return referenced

        if self.kind == GroupKind.COMMENT:
            raise RegexError("Comments are not supported in Syntax.rp yet", offender=self)
            

        if self.regex is None:
            raise RegexError("Group has no inner regex", offender=self)

        inner = self.regex.syntax(syntax_cls=syntax_cls, case_insensitive=case_insensitive, references=references)
        if self.kind == GroupKind.NON_CAPTURE:
            return inner[0], False  # non-capture groups don't keep the match result

        if self.kind == GroupKind.CAPTURE:
            captured = inner if isinstance(inner, Syntax) else inner[0]
            if self.name:
                return captured.bind(EntryCategory.Parse, **{self.name: lambda m, _: m}), True
            return captured, True

        raise RegexError("Unsupported group type in parser regex", offender=self)
        

@dataclass(frozen=True)
class LiteralAtom(RegexNode):
    text: str
    @staticmethod
    def _builder_char_case_insensitive(ch: str) -> Builder[str]:
        variants = RegexNode._casefold_variants(ch)
        if len(variants) == 1:
            return Builder.lit(variants[0])
        return Builder.oneof("".join(variants))

    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        self.validate()
        if not case_insensitive:
            return Builder.lit(self.text)
        pieces = [self._builder_char_case_insensitive(ch) for ch in self.text]
        return reduce(lambda a, b: a + b, pieces) if pieces else Builder.none()
    
    def validate(self) -> None:
        if self.text == "":
            raise RegexError("Empty literal is not allowed", offender=self)



class AnchorKind(Enum):
    LINE_START = auto()
    LINE_END = auto()
    ABSOLUTE_START = auto()
    ABSOLUTE_END = auto()
    WORD_BOUNDARY = auto()
    NOT_WORD_BOUNDARY = auto()
    @classmethod
    def from_literal(cls, literal: str) -> AnchorKind:        
        return {
            "^": cls.LINE_START,
            "$": cls.LINE_END,
            r"\A": cls.ABSOLUTE_START,
            r"\Z": cls.ABSOLUTE_END,
            r"\b": cls.WORD_BOUNDARY,
            r"\B": cls.NOT_WORD_BOUNDARY,
        }[literal]

@dataclass(frozen=True)
class AnchorAtom(RegexNode):
    kind: AnchorKind

    def builder(self, case_insensitive:bool = False) -> Builder[str]:
        raise RegexError("Anchors are not supported in Syntax.rp yet", offender=self)
    
    def syntax(
        self,
        *,
        syntax_cls: Type[Syntax],
        case_insensitive: bool = False,
        references: Mapping[str, Tuple[Syntax[Any, Any], bool]] | None = None,
    ) -> Tuple[Syntax[Any, Any], bool]:
        raise RegexError("Anchors are not supported in Syntax.rp yet", offender=self)
    

@dataclass(frozen=True)
class DotAtom(RegexNode):
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        return Builder.any(Alphabet(str))

@dataclass(frozen=True)
class Quantifier:
    minimum: int
    maximum: Optional[int]     # None → unbounded
    greedy: bool = True

@dataclass(frozen=True)
class Piece(RegexNode):
    atom: Union[LiteralAtom,
                DotAtom,
                AnchorAtom,
                ShorthandAtom,
                UnicodeCategoryAtom,
                CharClassAtom,
                GroupAtom]
    quantifier: Optional[Quantifier] = None
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        b = self.atom.builder(case_insensitive=case_insensitive)
        if self.quantifier is not None and self.quantifier is not Nothing:
            q = self.quantifier
            b = b.many(at_least=q.minimum, at_most=q.maximum).with_non_greedy(not q.greedy)        
        return b
    @cached_property
    def effective(self) -> bool:
        if self.quantifier is not None and self.quantifier is not Nothing and self.quantifier.minimum == 0:
            return True
        return self.atom.effective

    @cached_property
    def has_group(self) -> bool:
        return self.atom.has_group

    def syntax(
        self,
        *,
        syntax_cls: Type[Syntax],
        case_insensitive: bool = False,
        references: Mapping[str, Tuple[Syntax[Any, Any], bool]] | None = None,
    ) -> Tuple[Syntax[Any, Any], bool]:
        if not self.has_group:
            return RegexNode.syntax(self, syntax_cls=syntax_cls, case_insensitive=case_insensitive, references=references)

        atom_syntax = self.atom.syntax(syntax_cls=syntax_cls, case_insensitive=case_insensitive, references=references)
        if self.quantifier is None or self.quantifier is Nothing:
            return atom_syntax

        q = self.quantifier
        s, keep = atom_syntax
        repeated = s.many(at_least=q.minimum, at_most=q.maximum)
        return repeated, keep



@dataclass(frozen=True)
class Branch(RegexNode):
    pieces: Tuple[Piece, ...]
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        ret = [p.builder(case_insensitive=case_insensitive) for p in self.pieces]
        return reduce(lambda a, b: a + b, ret) if len(ret) > 0 else Builder.none()
    
    @cached_property
    def effective(self) -> bool:
        if len(self.pieces) == 0:
            return True
        return any(piece.effective for piece in self.pieces)

    @cached_property
    def has_group(self) -> bool:
        return any(piece.has_group for piece in self.pieces)

    def syntax(
        self,
        *,
        syntax_cls: Type[Syntax],
        case_insensitive: bool = False,
        references: Mapping[str, Tuple[Syntax[Any, Any], bool]] | None = None,
    ) -> Tuple[Syntax[Any, Any], bool]:
        if not self.has_group:
            return RegexNode.syntax(self, syntax_cls=syntax_cls, case_insensitive=case_insensitive, references=references)
        
        pieces = [p for p in self.pieces if p.effective]
        parts_list: list[Tuple[Syntax[Any, Any], bool]] = []
        buffered_builders: list[Builder[str]] = []

        def flush_buffered_builders() -> None:
            nonlocal buffered_builders
            if buffered_builders:
                merged = reduce(lambda a, b: a + b, buffered_builders)
                parts_list.append(-syntax_cls.lex(merged))
                buffered_builders = []

        for piece in pieces:
            if piece.has_group:
                flush_buffered_builders()
                item = piece.syntax(syntax_cls=syntax_cls, case_insensitive=case_insensitive, references=references)
                parts_list.append(item if isinstance(item, tuple) else (item, True))
            else:
                q = piece.quantifier
                if q is not None and q is not Nothing and q.minimum == 0:
                    # nullable piece without a group
                    flush_buffered_builders()
                    atom_builder = piece.atom.builder(case_insensitive=case_insensitive)
                
                    repeated = syntax_cls.lex(atom_builder).many(at_least=q.minimum, at_most=q.maximum)
                    parts_list.append(-repeated)
                else:
                    buffered_builders.append(piece.builder(case_insensitive=case_insensitive))

        flush_buffered_builders()

        seq = syntax_cls.seq(*parts_list)
        return seq, True
    



@dataclass(frozen=True)
class Regex(RegexNode):
    branches: Tuple[Branch, ...]
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        ret = [b.builder(case_insensitive=case_insensitive) for b in self.branches if b.effective]
        return reduce(lambda a, b: a | b, ret) if len(ret) > 0 else Builder.none()
    @cached_property
    def effective(self) -> bool:
        return any(branch.effective for branch in self.branches)

    @cached_property    
    def has_group(self) -> bool:
        return any(branch.has_group for branch in self.branches if branch.effective)

    def syntax(
        self,
        *,
        syntax_cls: Type[Syntax],
        case_insensitive: bool = False,
        references: Mapping[str, Tuple[Syntax[Any, Any], bool]] | None = None,
    ) -> Tuple[Syntax[Any, Any], bool]:

        if not self.has_group:
            return RegexNode.syntax(self, syntax_cls=syntax_cls, case_insensitive=case_insensitive, references=references)

        group_branches = [branch for branch in self.branches if branch.has_group and branch.effective]
        plain_branches = [branch for branch in self.branches if not branch.has_group and branch.effective]

        alternatives: list[Tuple[Syntax[Any, Any], bool]] = []
        alternatives.extend(branch.syntax(syntax_cls=syntax_cls, case_insensitive=case_insensitive, references=references) for branch in group_branches)

        if plain_branches:
            has_plain_empty = any(len(branch.pieces) == 0 for branch in plain_branches)
            plain_non_empty = [branch for branch in plain_branches if len(branch.pieces) > 0]

            if plain_non_empty:
                plain_builders = [branch.builder(case_insensitive=case_insensitive) for branch in plain_non_empty]
                plain_merged = reduce(lambda a, b: a | b, plain_builders)
                alternatives.append(+syntax_cls.lex(plain_merged))

            if has_plain_empty:
                alternatives.append(-syntax_cls.success(""))

        if len(alternatives) == 1:
            return alternatives[0]
        return syntax_cls.alt(*(item[0] for item in alternatives)), True
    










B = Builder[str]
S = Syntax.set(builtin=True)



@grammar
class RE(Grammar):
    dollar = S.lit("$")
    number = S.lex(B.oneof("0123456789").many(at_least=1)).bimap(int, str)
    dot = S.lit(".").to(lambda _: ".", 
                        lambda _: DotAtom())
    or_ = S.lit("|")
    whitespace = S.lex(B.oneof(" \t\n\r\f\v"))
    question = S.lit("?")
    star = S.lit("*")
    plus = S.lit("+")
    lbrace = S.lit("{")
    rbrace = S.lit("}")
    comma = S.lit(",")
    lparen = S.lit("(")
    rparen = S.lit(")")
    lsquare = S.lit("[")
    rsquare = S.lit("]")
    colon = S.lit(":")
    less = S.lit("<")
    greater = S.lit(">")
    equal = S.lit("=")
    bang = S.lit("!")
    caret = S.lit("^")
    backslash = S.lit("\\")
    minus = S.lit("-")
    boundary_escape = S.alt(S.lit("\\A"), S.lit("\\Z"), S.lit("\\b"), S.lit("\\B"))
    escaped_x = S.lit("\\x")
    escaped_u = S.lit("\\u")
    escaped_U = S.lit("\\U")
    escaped_N = S.lit("\\N{")
    escaped_p = S.lit("\\p{")
    escaped_P = S.lit("\\P{")
    underscore = S.lit("_")
    space = S.lit(" ")
    hyphen = S.lit("-")
    unicode_scalar = S.lex(B.range("\u0000", "\U0010FFFF"))
    unicode_category = S.lex(B.oneof(["Lu", "Ll", "Lt", "Lm", "Lo", "L", "M", "N", "Nd", "Nl", "No", "P", "Pd", "Ps", "Pe", "S", "Sm", "Sc", "Z", "Zs", "C"]))
    unicode_letter = S.lex(B.unicode_category(["Lu", "Ll", "Lt", "Lm", "Lo"]))
    unicode_digit = S.lex(B.unicode_category(["Nd"]))
    class_literal = S.lex(B.range("\u0000", "\U0010FFFF") - B.oneof("\\]"))
    literal_char = S.lex(B.range("\u0000", "\U0010FFFF") - B.oneof("\\.[(){}|+*?^$"))

    hex_octa = S.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=8, at_most=8))
    hex_quad = S.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=4, at_most=4))
    hex_pair = S.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=2, at_most=2))
    meta_char = S.lex(B.oneof("\"\\.[](){}|+*?^$"))
    control_escape = S.lex(B.oneof(["\\t", "\\n", "\\r", "\\f", "\\v", "\\0"]))
    shorthand = S.lex(B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"])).bimap(ShorthandKind.from_literal, 
                                                                                 ShorthandKind.to_literal).to(lambda env: ShorthandAtom(env.X))
    category_name = unicode_category.many()
    positive_unicode_category = S.seq(-escaped_p, +category_name, -rbrace).to(lambda env: UnicodeCategoryAtom(env.C, False))
    negative_unicode_category = S.seq(-escaped_P, +category_name, -rbrace).to(lambda env: UnicodeCategoryAtom(env.C, True))

    unicode_category_escape = S.alt(positive_unicode_category, negative_unicode_category)
        
    unicode_name = (unicode_letter + S.alt(unicode_letter, underscore, space, hyphen).many()).bimap(lambda x: ''.join([x[0]] + list(x[1])), 
                                                                                                    lambda s: (s[0], list(s[1:])))
    name_continue = unicode_letter | underscore
    name_start = unicode_letter | underscore
    name = name_continue.many(at_least=1).bimap(lambda x: ''.join(x), lambda s: tuple(s))
    unicode_escape = S.alt(
                    (escaped_x >> hex_pair).bimap(lambda x: chr(int(x, 16)), 
                                                  lambda x: format(ord(x), '02x')), 
                    (escaped_u >> hex_quad).bimap(lambda x: chr(int(x, 16)), 
                                                  lambda x: format(ord(x), '04x')),
                    (escaped_U >> hex_octa).bimap(lambda x: chr(int(x, 16)), 
                                                  lambda x: format(ord(x), '08x')), 
                    (escaped_N >> unicode_name // rbrace).bimap(lambda x: unicodedata.lookup(x), 
                                                                lambda x: unicodedata.name(x)))
    escaped_metachar = backslash >> meta_char
    escaped_0 = S.lit("\\0")
    octal_digit = S.lex(B.range("0", "7"))
    octal_escape = S.alt(
        (escaped_0 >> octal_digit + octal_digit).bimap(lambda x: chr(int(x[0] + x[1], 8)), 
                                                       lambda c: tuple(format(ord(c), '02o'))),
        (backslash >> octal_digit.many(at_least=1)).bimap(lambda x: chr(int(''.join(x), 8)), 
                                                          lambda c: tuple(digit for digit in format(ord(c), 'o')))
    )
    escaped_literal = octal_escape | control_escape | unicode_escape | escaped_metachar
    literal = escaped_literal | literal_char
    class_meta_char = minus | rsquare | backslash
    escaped_class_meta= backslash >> class_meta_char
    class_atom = class_literal | shorthand | escaped_metachar | control_escape | unicode_escape | unicode_category_escape | escaped_class_meta

    irange = S.seq(+class_atom, -minus, +class_atom).to(lambda env: (env.S, env.E), 
                                                       lambda env: CharRange(env.S, env.E))
    class_item = irange | class_atom
    
    class_class_items = (~(rsquare | minus) + class_item.many()).bimap(lambda x: (x[0],) + x[1] if x[0] else x[1], 
                                                                       lambda items: (items[0], tuple(items[1:])) if items and isinstance(items[0], str) and items[0] in '-]' else (Nothing,tuple(items)))


    char_class = S.seq(-lsquare, +(~caret), +class_class_items, -rsquare).to(lambda env: (env.negated, env.items), 
                                                                           lambda env: CharClassAtom(negated=env.negated, items=env.items))

    flag_text = S.lex(B.oneof("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    flag_soft = flag_text.check(lambda v: v in "iLmsuaxw")
    flag_strict = flag_text.check(
        lambda v: v in "iLmsuaxw",
        message="Unsupported inline flag: {{0}}. Supported flags: `iLmsuaxw`"
    )
    enabled_flags = flag_soft.many()
    enabled_flags_strict = flag_strict.many()
    # disabled_flags = (~(minus >> flag_soft.many())).bimap(lambda x: x[0] if x else None, lambda flags: (flags,) if flags is not None else Nothing)
    disabled_flags = (~(minus >> flag_soft.many())).case((lambda _: Nothing, lambda _: None), 
                                                         (lambda env: env.flags, lambda env: env.flags))
    
    # disabled_flags_strict = (~(minus >> flag_strict.many())).bimap(lambda x: x[0] if x else None, lambda flags: (flags,) if flags is not None else Nothing)
    disabled_flags_strict = (~(minus >> flag_strict.many())).case((lambda _: Nothing, lambda _: None),
                                                                  (lambda env: env.flags, lambda env: env.flags))
    
    inline_flags = S.seq(+enabled_flags, +disabled_flags).to(
        lambda env: (env.enabled_flags, env.disabled_flags),
        lambda env: InlineFlags(env.enabled_flags, env.disabled_flags),
    )
    inline_flags_strict = S.seq(+enabled_flags_strict, +disabled_flags_strict).to(
        lambda env: (env.enabled_flags, env.disabled_flags),
        lambda env: InlineFlags(env.enabled_flags, env.disabled_flags),
    )
    comment = S.lex(B.range("\u0000", "\U0010FFFF") - B.lit(")").many(at_least=1))

    @lazy(S)
    def group(_): 
        return S.alt(
            S.seq(-RE.lparen, +RE.regex, -RE.rparen).to(lambda env: GroupAtom(regex=env.X, kind=GroupKind.CAPTURE)),
            S.seq(-RE.lparen, -RE.question, -RE.colon, +RE.regex, -RE.rparen).to(lambda env: GroupAtom(regex=env.X, kind=GroupKind.NON_CAPTURE)),
            S.seq(-S.lit("(?&"), +RE.name, -RE.rparen).to(lambda env: GroupAtom(name=env.X, kind=GroupKind.SYNTAX_REF)),
            S.seq(-S.lit("(?="), +RE.regex, -RE.rparen).to(lambda env: GroupAtom(regex=env.X, kind=GroupKind.LOOKAHEAD)),
            S.seq(-S.lit("(?!"), +RE.regex, -RE.rparen).to(lambda env: GroupAtom(regex=env.X, kind=GroupKind.NEG_LOOKAHEAD)),
            S.seq(-S.lit("(?<="), +RE.regex, -RE.rparen).to(lambda env: GroupAtom(regex=env.X, kind=GroupKind.LOOKBEHIND)),
            S.seq(-S.lit("(?<!"), +RE.regex, -RE.rparen).to(lambda env: GroupAtom(regex=env.X, kind=GroupKind.NEG_LOOKBEHIND)),
            S.alt(      S.seq(-S.lit("(?"), +RE.number, -RE.rparen),
                        S.seq(-S.lit("(?R"), -RE.rparen),
                        S.seq(-S.lit("(?r"), -RE.rparen),
                        S.seq(-S.lit("(?P"), -RE.rparen),            
                        S.seq(-S.lit("(?p"), -RE.rparen),
                        S.seq(-S.lit("(?0"), -RE.rparen),
                    ).to(lambda env: unsuppoerted(regex=env.regex, feature="recursive group")),

            S.seq(-S.lit("(?P<"), +RE.name, -RE.greater, +RE.regex, -RE.rparen).to(lambda env: (env.name, env.regex), 
                                                                                   lambda env: GroupAtom(name=env.name, 
                                                                                                      regex=env.regex, 
                                                                                                      kind=GroupKind.CAPTURE)),
            S.seq(-S.lit("(?"), +RE.inline_flags_strict, -RE.rparen).to(lambda env: GroupAtom(inline_flags=env.inline_flags, 
                                                                                            kind=GroupKind.FLAGS)),
            S.seq(-S.lit("(?"), +RE.inline_flags_strict, -RE.colon, +RE.regex, -RE.rparen).to(lambda env: (env.inline_flags, env.regex), 
                                                                                            lambda env: GroupAtom(inline_flags=env.inline_flags, 
                                                                                                                  regex=env.regex, 
                                                                                                                  kind=GroupKind.FLAGS_SCOPED)),

            
            S.seq(
                -(S.lit("(?") | S.lit("(?=") | S.lit("(?!") | S.lit("(?<=") | S.lit("(?<!")), +RE.regex, -RE.rparen
                ).to(lambda env: unsuppoerted(regex=env.regex, 
                                              feature="lookaround assertion group")),

            S.seq(-S.lit("(?("), -(RE.number | RE.name), +RE.regex, -RE.rparen).to(lambda env:  unsuppoerted(regex=env.regex, 
                                                                                                    feature="group existence test")),

            S.seq(-S.lit("(?#"), 
                  +RE.comment,
                  -RE.rparen).to(lambda env: unsuppoerted(regex=env.regex, feature="comment group")),
                  
                ).bind(group_counter = lambda _, c: c + 1 if c is not ... else 1)


    anchor = S.alt(caret, dollar, boundary_escape).to(lambda env: unsuppoerted(regex=env.regex, 
                                                                               feature="group existence test"))


    braced_quantifier = S.alt(
        S.seq(-lbrace, +number, -rbrace).to(lambda env: Quantifier(minimum=env.M, maximum=env.M)),
        S.seq(-lbrace, +number, -comma, -rbrace).to(lambda env: Quantifier(minimum=env.M, maximum=None)),
        S.seq(-lbrace, -comma, +number, -rbrace).to(lambda env: Quantifier(minimum=0, maximum=env.M)),
        S.seq(-lbrace, +number, -comma, +number, -rbrace).to(lambda env: (env.M, env.N), 
                                                          lambda env: Quantifier(env.M, env.N))
    )


    quantifier = (S.alt(
            braced_quantifier,
            question.to(lambda _: "?", 
                        lambda _: Quantifier(minimum=0, maximum=1)),
            star.to(lambda _: "*", 
                    lambda _: Quantifier(minimum=0, maximum=None)),
            plus.to(lambda _: "+", 
                    lambda _: Quantifier(minimum=1, maximum=None)),
        ) + ~question).to(lambda env: (Quantifier(minimum=env.M, maximum=env.N), env.greedy), 
                          lambda env: Quantifier(minimum=env.M, maximum=env.N, greedy=Not(env.greedy)) )


    backreference = S.alt(
        backslash >> number,
        S.lit("\\g<") >> name // greater
    )

    atom = S.alt(        
            backreference.check(lambda v, group_counter: v == 0 or (group_counter is not ... and group_counter >= v)),
            literal.to(lambda env: LiteralAtom(env.text)),
            char_class,
            anchor,
            dot,
            shorthand,
            unicode_category_escape,
            group,
            )

    piece = S.seq(+atom, ~quantifier).to(lambda env: (env.atom, env.quantifier), 
                                        lambda env: Piece(env.atom, env.quantifier))

    branch = piece.many().to(lambda env: Branch(env.piece))

    regex = branch.sep_by(or_).to(lambda env: Regex(env.branch))
    regex_full = rule((regex // S.eof()), is_root=True)






def parse(data: str, *, syntax: Syntax | None = None) -> Any:
    try:
        return RE.parse(data, syntax=syntax)
    except DataError as e:
        return Error.new(this=syntax or RE.regex_full, message=str(e), error=e)


def re(pattern: str) -> Builder[str]:
    parsed = parse(pattern)
    if not isinstance(parsed, Regex):
        if isinstance(parsed, Error):
            raise RegexError("Regex parse failed", offender=parsed, expect=parsed.summary)
        raise RegexError("Regex parse failed", offender=parsed)
    return parsed.builder()


def xeger(
    pattern: str | pyre.Pattern[str],
    *,
    rnd: random.Random | None = None,
    seed: int | None = None,
) -> str:
    if rnd is not None and seed is not None:
        raise ValueError("Provide either 'rnd' or 'seed', not both")

    pattern_text = pattern.pattern if isinstance(pattern, pyre.Pattern) else pattern
    parsed = parse(pattern_text)
    if not isinstance(parsed, Regex):
        if isinstance(parsed, Error):
            raise RegexError("Regex parse failed", offender=parsed, expect=parsed.summary)
        raise RegexError("Regex parse failed", offender=parsed)

    alphabet = Alphabet(str)
    dfa = parsed.builder().compile(alphabet).dfa.with_default_tag_invariant()
    rng = rnd if rnd is not None else random.Random(seed)
    result = dfa.reverse.gen(DEFAULT_TAG, rng)

    # For text alphabet, gen() always returns str after internal concat
    if not isinstance(result, str):
        raise RegexError(
            f"Expected string from text DFA generation, got {type(result).__name__}",
            offender=result
        )
    return result


def rp(pattern: str, *, syntax_cls: Type[Syntax] | None = None, **refs: Syntax[Any, Any] | Tuple[Syntax[Any, Any], bool]) -> Syntax[Any, Any]:
    parsed = parse(pattern)
    if not isinstance(parsed, Regex):
        if isinstance(parsed, Error):
            raise RegexError("Regex parse failed", offender=parsed, expect=parsed.summary)
        raise RegexError("Regex parse failed", offender=parsed)
    if syntax_cls is None:
        if len(refs) > 0:
            for ref in refs.values():
                if isinstance(ref, Syntax):
                    syntax_cls = type(ref)
                elif isinstance(ref, tuple) and len(ref) == 2 and isinstance(ref[0], Syntax):
                    syntax_cls = type(ref[0])
                else:
                    raise RegexError("Invalid reference provided to rp()", offender=ref, expect="Syntax instance or (Syntax instance, bool) tuple")
        else:
            syntax_cls = Syntax
    assert syntax_cls is not None  # for mypy

    converted = parsed.syntax(syntax_cls=syntax_cls, references={k: v if isinstance(v, tuple) else (v, True) for k, v in refs.items()})
    return converted[0]
    

@dataclass
class VerifyResult:
    ok: bool
    pattern: str
    syncraft: Any
    re:Any
    err_syncraft: Any
    err_re: Any




def verify(pattern: str) -> VerifyResult:
    try:
        import regex as re
    except ImportError:
        import re # type: ignore

    myerr = None
    err = None
    
    
    parsed = parse(pattern)
        
    if not isinstance(parsed, Regex):
        myerr = parsed
    try:
        pyparsed = re.compile(pattern)
    except Exception as e:
        pyparsed = None
        err = e
    consistent = (pyparsed is not None and isinstance(parsed, Regex)) or (pyparsed is None and isinstance(parsed, Error))
    return VerifyResult(
        ok=consistent or myerr is None,
        pattern=pattern,
        syncraft=parsed,
        re=pyparsed,
        err_syncraft=myerr,
        err_re=err
    )



