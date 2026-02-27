from __future__ import annotations


from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any
import unicodedata

from syncraft.algebra import Error
from syncraft.syntax import Syntax
from syncraft.fa import Builder
from syncraft.alphabet import Alphabet
from syncraft.grammar import Grammar, lazy, rule, grammar
from functools import reduce
from syncraft.bimap import DataError, Not
from syncraft.ast import Nothing, SyncraftError




class RegexError(SyncraftError):
    pass


def _casefold_variants(ch: str) -> Tuple[str, ...]:
    variants = []
    for candidate in (ch, ch.casefold(), ch.lower(), ch.upper()):
        if len(candidate) != 1:
            continue
        if candidate not in variants:
            variants.append(candidate)
    return tuple(variants)


def _builder_char_case_insensitive(ch: str) -> Builder[str]:
    variants = _casefold_variants(ch)
    if len(variants) == 1:
        return Builder.lit(variants[0])
    return Builder.oneof("".join(variants))


def _builder_range_case_insensitive(start: str, end: str) -> Builder[str]:
    b: Builder[str] = Builder.none()
    for codepoint in range(ord(start), ord(end) + 1):
        ch = chr(codepoint)
        for variant in _casefold_variants(ch):
            b = b | Builder.lit(variant)
    return b



@dataclass(frozen=True, slots=True)
class RegexNode:
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        raise RegexError("Unsupported regex feature in lexer", offender=self)


@dataclass(frozen=True, slots=True)
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
        raise ValueError(f"Unknown shorthand literal: {literal}")

    @classmethod
    def to_literal(cls, kind: ShorthandKind) -> str:
        return kind.value    

@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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



@dataclass(frozen=True, slots=True)
class CharClassAtom:
    items: Tuple[Union[str, CharRange, ShorthandAtom, UnicodeCategoryAtom], ...]
    negated: bool = False
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        self.validate()
        b: Builder[str] = Builder.none()
        for item in self.items:
            if isinstance(item, str):
                if case_insensitive:
                    for variant in _casefold_variants(item):
                        b = b | Builder.lit(variant)
                else:
                    b = b | Builder.lit(item)
            elif isinstance(item, CharRange):
                if case_insensitive:
                    b = b | _builder_range_case_insensitive(item.start, item.end)
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



class GroupKind(Enum):
    CAPTURE = auto()
    NON_CAPTURE = auto()
    LOOKAHEAD = auto()
    NEG_LOOKAHEAD = auto()
    LOOKBEHIND = auto()
    NEG_LOOKBEHIND = auto()
    FLAGS = auto()
    FLAGS_SCOPED = auto()
    CONDITION_ASSERTION = auto()
    CONDITION_GROUP = auto()
    COMMENT= auto()

@dataclass(frozen=True, slots=True)
class InlineFlags:
    enabled: Tuple[str, ...]
    disabled: Optional[Tuple[str, ...]] = None


@dataclass(frozen=True, slots=True)
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
        if self.kind not in (GroupKind.CAPTURE, GroupKind.COMMENT, GroupKind.NON_CAPTURE, GroupKind.FLAGS_SCOPED):
            raise RegexError("Unsupported group type in lexer regex", offender=self)
        

@dataclass(frozen=True, slots=True)
class LiteralAtom(RegexNode):
    text: str
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        self.validate()
        if not case_insensitive:
            return Builder.lit(self.text)
        pieces = [_builder_char_case_insensitive(ch) for ch in self.text]
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

@dataclass(frozen=True, slots=True)
class AnchorAtom(RegexNode):
    kind: AnchorKind    
    

@dataclass(frozen=True, slots=True)
class DotAtom(RegexNode):
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        return Builder.any(Alphabet(str))

@dataclass(frozen=True, slots=True)
class Quantifier:
    minimum: int
    maximum: Optional[int]     # None → unbounded
    greedy: bool = True

@dataclass(frozen=True, slots=True)
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



@dataclass(frozen=True, slots=True)
class Branch(RegexNode):
    pieces: Tuple[Piece, ...]
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        ret = [p.builder(case_insensitive=case_insensitive) for p in self.pieces]
        return reduce(lambda a, b: a + b, ret) if len(ret) > 0 else Builder.none()
    



@dataclass(frozen=True, slots=True)
class Regex(RegexNode):
    branches: Tuple[Branch, ...]
    def builder(self, *, case_insensitive: bool = False) -> Builder[str]:
        ret = [b.builder(case_insensitive=case_insensitive) for b in self.branches]
        return reduce(lambda a, b: a | b, ret) if len(ret) > 0 else Builder.none()











B = Builder[str]
S = Syntax.set(builtin=True)

INLINE_FLAGS = "iLmsuaxw"
INLINE_FLAG_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
@grammar
class RE(Grammar):
    dollar = S.lex(B.lit("$"))
    number = S.lex(B.oneof("0123456789").many(at_least=1)).bimap(int, str)
    dot = S.lex(B.lit(".")).to(lambda env, x: x, lambda env, x: DotAtom())
    or_ = S.lex(B.lit("|"))
    whitespace = S.lex(B.oneof(" \t\n\r\f\v"))
    question = S.lex(B.lit("?"))
    star = S.lex(B.lit("*"))
    plus = S.lex(B.lit("+"))
    lbrace = S.lex(B.lit("{"))
    rbrace = S.lex(B.lit("}"))
    comma = S.lex(B.lit(","))
    lparen = S.lex(B.lit("("))
    rparen = S.lex(B.lit(")"))
    lsquare = S.lex(B.lit("["))
    rsquare = S.lex(B.lit("]"))
    colon = S.lex(B.lit(":"))
    less = S.lex(B.lit("<"))
    greater = S.lex(B.lit(">"))
    equal = S.lex(B.lit("="))
    bang = S.lex(B.lit("!"))
    caret = S.lex(B.lit("^"))
    backslash = S.lex(B.lit("\\"))
    minus = S.lex(B.lit("-"))
    boundary_escape = S.lex(B.oneof(["\\A", "\\Z", "\\b", "\\B"]))
    escaped_x = S.lex(B.lit("\\x"))
    escaped_u = S.lex(B.lit("\\u"))
    escaped_U = S.lex(B.lit("\\U"))
    escaped_N = S.lex(B.lit("\\N{"))
    escaped_p = S.lex(B.lit("\\p{"))
    escaped_P = S.lex(B.lit("\\P{"))
    underscore = S.lex(B.lit("_"))
    space = S.lex(B.lit(" "))
    hyphen = S.lex(B.lit("-"))
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
    shorthand = S.lex(B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"])).bimap(ShorthandKind.from_literal, ShorthandKind.to_literal).to(lambda env, X: X, lambda env, X: ShorthandAtom(X))
    category_name = unicode_category.many()
    positive_unicode_category = S.seq(+escaped_p, +category_name, rbrace).to(lambda env: (env.negated, env.categories), lambda env: UnicodeCategoryAtom(env.categories, False))
    negative_unicode_category = S.seq(+escaped_P, +category_name, rbrace).to(lambda env: (env.negated, env.categories), lambda env: UnicodeCategoryAtom(env.categories, True))

    unicode_category_escape = S.alt(positive_unicode_category, negative_unicode_category)
        
    unicode_name = (unicode_letter + S.alt(unicode_letter, underscore, space, hyphen).many()).bimap(lambda x: ''.join([x[0]] + list(x[1])), lambda s: (s[0], list(s[1:])))
    name_continue = unicode_letter | underscore
    name_start = unicode_letter | underscore
    name = (name_start + name_continue.many()).bimap(lambda x: ''.join([x[0]] + list(x[1])), lambda s: (s[0], list(s[1:])))
    unicode_escape = S.alt((escaped_x >> hex_pair).bimap(lambda x: chr(int(x[0], 16)), lambda x: (format(ord(x), '02x'),)), 
                    (escaped_u >> hex_quad).bimap(lambda x: chr(int(x[0], 16)), lambda x: (format(ord(x), '04x'),)),
                    (escaped_U >> hex_octa).bimap(lambda x: chr(int(x[0], 16)), lambda x: (format(ord(x), '08x'),)), 
                    ((escaped_N >> unicode_name) // rbrace).bimap(lambda x: unicodedata.lookup(x[0][0]), lambda x: ((unicodedata.name(x),),)))
    escaped_metachar = (backslash >> meta_char).to(lambda env: (env.X,), lambda env: env.X)
    escaped_0 = S.lex(B.lit("\\0"))
    octal_digit = S.lex(B.range("0", "7"))
    octal_escape = S.alt(
        (escaped_0 >> octal_digit + octal_digit).bimap(lambda x: chr(int(x[0] + x[1], 8)), lambda c: (tuple(format(ord(c), '02o')),)),
        (backslash >> octal_digit.many(at_least=1)).bimap(lambda x: chr(int(''.join(x[0]), 8)), lambda c: (tuple(digit for digit in format(ord(c), 'o')),))
    )
    escaped_literal = octal_escape | control_escape | unicode_escape | escaped_metachar
    literal = escaped_literal | literal_char
    class_meta_char = minus | rsquare | backslash
    escaped_class_meta= (backslash >> class_meta_char).to(lambda env: (env.X,), lambda env: env.X)
    class_atom = S.alt(
                        class_literal,
                        shorthand,
                        escaped_metachar,
                        control_escape,
                        unicode_escape,
                        unicode_category_escape,
                        escaped_class_meta,
                        )

    irange = S.seq(+class_atom, minus, +class_atom).to(lambda env: (env.start, env.end), lambda env: CharRange(env.start, env.end))
    class_item = irange | class_atom
    
    class_class_items = (~(rsquare | minus) + class_item.many()).bimap(lambda x: (x[0],) + x[1] if x[0] else x[1], 
                                                                       lambda items: (items[0], tuple(items[1:])) if items and isinstance(items[0], str) and items[0] in '-]' else tuple(items))
    char_class = S.seq(lsquare, +(~caret), +class_class_items, rsquare).to(lambda env: (env.negated, env.items), lambda env: CharClassAtom(negated=env.negated, items=env.items))

    flag_text = S.lex(B.oneof(INLINE_FLAG_LETTERS))
    flag_soft = flag_text.check(lambda v: v in INLINE_FLAGS)
    flag_strict = flag_text.check(
        lambda v: v in INLINE_FLAGS,
        message=f"Unsupported inline flag: {{0}}. Supported flags: {INLINE_FLAGS}",
    )
    enabled_flags = flag_soft.many()
    enabled_flags_strict = flag_strict.many()
    disabled_flags = (~(minus >> flag_soft.many())).bimap(lambda x: x[0] if x else None, lambda flags: (flags,) if flags is not None else Nothing)
    disabled_flags_strict = (~(minus >> flag_strict.many())).bimap(lambda x: x[0] if x else None, lambda flags: (flags,) if flags is not None else Nothing)
    
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
    def group(): # type: ignore
        return S.alt(
            S.seq(RE.lparen, +RE.regex, RE.rparen).to(lambda env: (env.X,), lambda env: GroupAtom(regex=env.X, kind=GroupKind.CAPTURE)),
            S.seq(RE.lparen, RE.question, RE.colon, +RE.regex, RE.rparen).to(lambda env: (env.X,), lambda env: GroupAtom(regex=env.X, kind=GroupKind.NON_CAPTURE)),
            S.seq(S.lex(B.lit("(?=")), +RE.regex, RE.rparen).to(lambda env: (env.X,), lambda env: GroupAtom(regex=env.X, kind=GroupKind.LOOKAHEAD)),
            S.seq(S.lex(B.lit("(?!")), +RE.regex, RE.rparen).to(lambda env: (env.X,), lambda env: GroupAtom(regex=env.X, kind=GroupKind.NEG_LOOKAHEAD)),
            S.seq(S.lex(B.lit("(?<=")), +RE.regex, RE.rparen).to(lambda env: (env.X,), lambda env: GroupAtom(regex=env.X, kind=GroupKind.LOOKBEHIND)),
            S.seq(S.lex(B.lit("(?<!")), +RE.regex, RE.rparen).to(lambda env: (env.X,), lambda env: GroupAtom(regex=env.X, kind=GroupKind.NEG_LOOKBEHIND)),
            S.alt(      S.seq(S.lex(B.lit("(?&")), +RE.name, RE.rparen),
                        S.seq(S.lex(B.lit("(?")), +RE.number, RE.rparen),
                        S.seq(S.lex(B.lit("(?R")), RE.rparen),
                        S.seq(S.lex(B.lit("(?r")), RE.rparen),
                        S.seq(S.lex(B.lit("(?P")), RE.rparen),            
                        S.seq(S.lex(B.lit("(?p")), RE.rparen),
                        S.seq(S.lex(B.lit("(?0")), RE.rparen),   
                    ).to(lambda env: env.regex, lambda env: unsuppoerted(regex=env.regex, feature="recursive group")),

            S.seq(S.lex(B.lit("(?P<")), +RE.name, RE.greater, +RE.regex, RE.rparen).to(lambda env: (env.name, env.regex), lambda env: GroupAtom(name=env.name, regex=env.regex, kind=GroupKind.CAPTURE)),
            S.seq(S.lex(B.lit("(?")), +RE.inline_flags_strict, RE.rparen).to(lambda env: (env.inline_flags,), lambda env: GroupAtom(inline_flags=env.inline_flags, kind=GroupKind.FLAGS)),
            S.seq( S.lex(B.lit("(?")), +RE.inline_flags_strict, RE.colon, +RE.regex, RE.rparen).to(lambda env: (env.inline_flags, env.regex), lambda env: GroupAtom(inline_flags=env.inline_flags, regex=env.regex, kind=GroupKind.FLAGS_SCOPED)),

            S.seq(S.lex(B.lit("(?")), 
                        S.alt(
                            S.seq(S.lex(B.lit("(?=")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?!")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?<=")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?<!" )), +RE.regex, RE.rparen),
                        ), 
                        +RE.regex, 
                        RE.rparen).to(lambda env: env.regex, lambda env: unsuppoerted(regex=env.regex, feature="lookaround assertion group")),

            S.seq(S.lex(B.lit("(?(")), RE.number | RE.name, +RE.regex, RE.rparen).to(lambda env: (env.regex,), lambda env:  unsuppoerted(regex=env.regex, feature="group existence test")),

            S.seq(S.lex(B.lit("(?#")), 
                  +RE.comment,
                  RE.rparen).to(lambda env: env.regex, lambda env: unsuppoerted(regex=env.regex, feature="comment group")),
                  
                ).named("group_alternatives").bind(group_counter = lambda _, c: c + 1 if c is not ... else 1)


    anchor = S.alt(caret, dollar, boundary_escape).to(lambda env: env.regex, lambda env: unsuppoerted(regex=env.regex, feature="group existence test"))


    braced_quantifier = S.alt(
        S.seq(lbrace, +number, rbrace).to(lambda env: (env.M,), lambda env: Quantifier(minimum=env.M, maximum=env.M)),
        S.seq(lbrace, +number, comma, rbrace).to(lambda env: (env.M,), lambda env: Quantifier(minimum=env.M, maximum=None)),
        S.seq(lbrace, comma, +number, rbrace).to(lambda env: (env.M,), lambda env: Quantifier(minimum=0, maximum=env.M)),
        S.seq(lbrace, +number, comma, +number, rbrace).to(lambda env: (env.M, env.N), lambda env: Quantifier(env.M, env.N))
    )


    quantifier = (S.alt(
            braced_quantifier,
            question.to(lambda env: "?", lambda env: Quantifier(minimum=0, maximum=1)),
            star.to(lambda env: "*", lambda env: Quantifier(minimum=0, maximum=None)),
            plus.to(lambda env: "+", lambda env: Quantifier(minimum=1, maximum=None)),
        ) + ~question).to(lambda env: (Quantifier(minimum=env.M, maximum=env.N), env.greedy), 
                          lambda env: Quantifier(minimum=env.M, maximum=env.N, greedy=Not(env.greedy)) )


    backreference = S.alt(
        (backslash >> number).to(lambda env: (env.X,), lambda env: env.X),
        (S.lex(B.lit("\\g<")) >> name // greater).to(lambda env: (env.X,), lambda env: env.X)
    )

    atom = S.alt(        
            backreference.check(lambda v, group_counter: v == 0 or (group_counter is not ... and group_counter >= v)),
            S.seq(+literal).to(lambda env: (env.text,), lambda env: LiteralAtom(env.text)),
            char_class,
            anchor,
            dot,
            shorthand,
            unicode_category_escape,
            group,
            )

    piece = S.seq(+atom, +(~quantifier)).to(lambda env: (env.atom, env.quantifier), lambda env: Piece(env.atom, env.quantifier))

    branch = S.seq(+(piece.many())).to(lambda env: (env.piece,), lambda env: Branch(env.piece))

    regex = S.seq(+(branch.sep_by(or_))).to(lambda env: (env.branch,), lambda env: Regex(env.branch))
    regex_full = rule((regex // S.eof()).to(lambda env: (env.X,), lambda env: env.X), is_root=True)






def parse(data: str, *, syntax: Syntax | None = None) -> Any:
    try:
        return RE.parse(data, syntax=syntax)
    except DataError as e:
        return Error.new(this=syntax or RE.regex_full, message=str(e), error=e)


def re(pattern: str) -> Builder[str]:
    parsed = parse(pattern)
    if not isinstance(parsed, Regex):
        if isinstance(parsed, Error):
            raise SyncraftError("Regex parse failed", offender=parsed, expect=parsed.summary)
        raise SyncraftError("Regex parse failed", offender=parsed)
    return parsed.builder()


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



