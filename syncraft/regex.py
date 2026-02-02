from __future__ import annotations

from typing import overload, Literal
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any
import unicodedata

from syncraft.algebra import Error
from syncraft.syntax import Syntax
from syncraft.fa import Builder
from syncraft.cache import Cache
from syncraft.alphabet import Alphabet
from syncraft.grammar import Grammar, lazy, rule, grammar
from syncraft.mapper import call, _0, _1, at
from functools import partial, reduce

try:
    import regex as re
except ImportError:
    import re




class UnsupportedFeature:
    def __init__(self, feature: str, message: Optional[str] = None, *args, **kwargs) -> None:
        self.feature = feature
        self.message = message

    def __str__(self) -> str:
        return f"Unsupported feature: {self.feature}" + (f" - {self.message}" if self.message else "")
    
    def builder(self) -> Builder[str]:
        raise NotImplementedError(f"Cannot build UnsupportedFeature: {self.feature}")
    


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
class ShorthandAtom:
    kind: ShorthandKind

    def builder(self) -> Builder[str]:
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
            raise ValueError(f"Unknown shorthand kind: {self.kind}")



@dataclass(frozen=True, slots=True)
class UnicodeCategoryAtom:
    categories: Tuple[str, ...]
    negated: bool = False   
    def builder(self) -> Builder[str]:
        b = Builder.none(Alphabet(str))
        for category in self.categories:
            b = b | Builder.unicode_category([category])
        if self.negated:
            b = Builder.any(Alphabet(str)) - b
        return b


@dataclass(frozen=True, slots=True)
class CharRange:
    start: str
    end: str

@dataclass(frozen=True, slots=True)
class CharClassAtom:
    items: Tuple[Union[str, CharRange], ...]
    negated: bool = False
    def builder(self) -> Builder[str]:
        b = Builder.none(Alphabet(str))
        for item in self.items:
            if isinstance(item, CharRange):
                b = b | Builder.range(item.start, item.end)
            else:
                b = b | Builder.lit(item)
        if self.negated:
            b = Builder.any(Alphabet(str)) - b
        return b




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
class GroupAtom:
    kind: GroupKind
    regex: Optional[Regex] = None
    name: Optional[str] = None
    inline_flags: Optional[InlineFlags] = None
    def builder(self) -> Builder[str]:
        if self.kind in (GroupKind.CAPTURE, GroupKind.NON_CAPTURE):
            if self.regex is not None:
                inner = self.regex.builder()
                if self.name is not None:
                    return inner.tagged(self.name)
                else:
                    return inner
            else:
                raise NotImplementedError(f"Cannot build GroupAtom of kind: {self.kind}")
        elif self.kind == GroupKind.COMMENT:
            return Builder.none(Alphabet(str))
        else:
            raise NotImplementedError(f"Cannot build GroupAtom of kind: {self.kind}")

@dataclass(frozen=True, slots=True)
class LiteralAtom:
    text: str
    def builder(self) -> Builder[str]:
        return Builder.lit(self.text)



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
class AnchorAtom:
    kind: AnchorKind
    def builder(self) -> Builder[str]:
        raise NotImplementedError(f"Cannot build AnchorAtom of kind: {self.kind}")

@dataclass(frozen=True, slots=True)
class DotAtom:
    def builder(self) -> Builder[str]:
        return Builder.any(Alphabet(str))

@dataclass(frozen=True, slots=True)
class Quantifier:
    minimum: int
    maximum: Optional[int]     # None → unbounded
    greedy: bool = True

@dataclass(frozen=True, slots=True)
class Piece:
    atom: Union[LiteralAtom,
                DotAtom,
                AnchorAtom,
                ShorthandAtom,
                UnicodeCategoryAtom,
                CharClassAtom,
                GroupAtom]
    quantifier: Optional[Quantifier] = None
    def builder(self) -> Builder[str]:
        b = self.atom.builder()
        if self.quantifier is not None:
            q = self.quantifier
            b = b.many(at_least=q.minimum, at_most=q.maximum).with_non_greedy(not q.greedy)        
        return b


@dataclass(frozen=True, slots=True)
class Branch:
    pieces: Tuple[Piece, ...]
    def builder(self) -> Builder[str]:
        ret = [p.builder() for p in self.pieces]
        return reduce(lambda a, b: a + b, ret) if len(ret) > 0 else Builder.none(Alphabet(str))
    


@dataclass(frozen=True, slots=True)
class Regex:
    branches: Tuple[Branch, ...]
    def builder(self) -> Builder[str]:
        ret = [b.builder() for b in self.branches]
        return reduce(lambda a, b: a | b, ret) if len(ret) > 0 else Builder.none(Alphabet(str))


B = Builder[str]
S = Syntax.set(builtin=True)
@grammar
class RE(Grammar):
    dollar = S.lex(B.lit("$"))
    number = S.lex(B.oneof("0123456789").many(at_least=1)).bimap(int, str)
    dot = S.lex(B.lit(".")).to(DotAtom)
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
    shorthand = S.lex(B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"])).bimap(ShorthandKind.from_literal, ShorthandKind.to_literal).to(ShorthandAtom)
    category_name = unicode_category.many().bimap(tuple, list)
    # positive_unicode_category = S.seq(escaped_p.bimap(lambda x: Reversible(False, lambda _: x)).fld('negated'), category_name.fld('categories'), rbrace)
    # negative_unicode_category = S.seq(escaped_P.bimap(lambda x: Reversible(True, lambda _: x)).fld('negated'), category_name.fld('categories'), rbrace)
    positive_unicode_category = S.seq(escaped_p.fld('negated'), category_name.fld('categories'), rbrace)
    negative_unicode_category = S.seq(escaped_P.fld('negated'), category_name.fld('categories'), rbrace)

    unicode_category_escape = S.alt(positive_unicode_category, negative_unicode_category).to(UnicodeCategoryAtom)
        
    unicode_name = (unicode_letter + S.alt(unicode_letter, underscore, space, hyphen).many()).bimap((_0.list + _1).apply(''.join), lambda s: (s[0], list(s[1:])))
    name_continue = unicode_letter | underscore
    name_start = unicode_letter | underscore
    name = (name_start + name_continue.many()).bimap((_0.list + _1).apply(''.join), lambda s: (s[0], list(s[1:])))
    unicode_escape = S.alt((escaped_x >> hex_pair).bimap(call(int, _0, 16).apply(chr), lambda x: (format(ord(x), '02x'),)), 
                    (escaped_u >> hex_quad).bimap(call(int, _0, 16).apply(chr), lambda x: (format(ord(x), '04x'),)),
                    (escaped_U >> hex_octa).bimap(call(int, _0, 16).apply(chr), lambda x: (format(ord(x), '08x'),)), 
                    ((escaped_N >> unicode_name) // rbrace).map(_0.apply(unicodedata.lookup)))
    escaped_metachar = (backslash >> meta_char).bimap(_0, lambda x: (x,))
    escaped_0 = S.lex(B.lit("\\0"))
    octal_digit = S.lex(B.range("0", "7"))
    octal_escape = S.alt(
        (escaped_0 >> octal_digit + octal_digit).bimap(call(int, _0 + _1, 8).apply(chr), lambda x: (format(ord(x), '03o'),)),
        (backslash >> octal_digit.many(at_least=1)).bimap(call(int, _0.apply(''.join), 8).apply(chr), lambda x: (format(ord(x), 'o'),))
    )
    escaped_literal = octal_escape | control_escape | unicode_escape | escaped_metachar
    literal = escaped_literal | literal_char
    class_meta_char = minus | rsquare | backslash
    escaped_class_meta= (backslash >> class_meta_char).bimap(_0, lambda x: (x,))
    class_atom = S.alt(
                        class_literal,
                        shorthand,
                        escaped_metachar,
                        control_escape,
                        unicode_escape,
                        unicode_category_escape,
                        escaped_class_meta,
                        )

    irange = S.seq(class_atom.fld('start'), minus, class_atom.fld('end')).to(CharRange)
    class_item = irange | class_atom
    class_class_items = (~(rsquare | minus) + class_item.many()).map(_0.if_then_else(_1 + _0.list, _1))
    # char_class = S.seq(lsquare, (~caret).bimap(lambda x: Reversible(bool(x), lambda _: x)).fld('negated'), class_class_items.fld('items'), rsquare).to(CharClassAtom)
    char_class = S.seq(lsquare, (~caret).fld('negated'), class_class_items.fld('items'), rsquare).to(CharClassAtom)

    flag = S.lex(B.oneof("iLmsuaxw"))
    flag_seq = flag.many().bimap(tuple, list)
    inline_flags = S.seq(flag_seq.fld('enabled'), (~(minus >> flag_seq)).map(at().if_then_else(_0, None)).fld('disabled')).to(InlineFlags)
    comment = S.lex(B.range("\u0000", "\U0010FFFF") - B.lit(")").many(at_least=1))

    @lazy(S)
    def group(): # type: ignore
        return S.alt(
            S.seq(RE.lparen, RE.regex.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.CAPTURE)),
            S.seq(RE.lparen, RE.question, RE.colon, RE.regex.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.NON_CAPTURE)),
            S.seq(S.lex(B.lit("(?=")), RE.regex.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.LOOKAHEAD)),
            S.seq(S.lex(B.lit("(?!")), RE.regex.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.NEG_LOOKAHEAD)),
            S.seq(S.lex(B.lit("(?<=")), RE.regex.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.LOOKBEHIND)),
            S.seq(S.lex(B.lit("(?<!")), RE.regex.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.NEG_LOOKBEHIND)),
            S.seq(S.lex(B.lit("(?")), RE.inline_flags.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.FLAGS)),
            S.seq(S.lex(B.lit("(?P<")), RE.name.fld(), RE.greater, RE.regex.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.CAPTURE)),
            S.seq( S.lex(B.lit("(?")), RE.inline_flags.fld(), RE.colon, RE.regex.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.FLAGS_SCOPED)),

            S.seq(S.lex(B.lit("(?")), 
                        S.alt(
                            S.seq(S.lex(B.lit("(?=")), RE.regex.fld(), RE.rparen),
                            S.seq(S.lex(B.lit("(?!")), RE.regex.fld(), RE.rparen),
                            S.seq(S.lex(B.lit("(?<=")), RE.regex.fld(), RE.rparen),
                            S.seq(S.lex(B.lit("(?<!" )), RE.regex.fld(), RE.rparen),
                        ), 
                        RE.regex.fld(), 
                        RE.rparen).to(partial(UnsupportedFeature, feature="lookaround assertion group")),

            S.seq(S.lex(B.lit("(?(")), RE.number | RE.name, RE.regex.fld(), RE.rparen).to(partial(UnsupportedFeature, feature="group existence test")),

            S.alt(S.seq(S.lex(B.lit("(?&")), RE.name.fld(), RE.rparen),
                        S.seq(S.lex(B.lit("(?")), RE.number.fld(), RE.rparen),
                        S.seq(S.lex(B.lit("(?R")), RE.rparen),
                        S.seq(S.lex(B.lit("(?r")), RE.rparen),
                        S.seq(S.lex(B.lit("(?P")), RE.rparen),            
                        S.seq(S.lex(B.lit("(?p")), RE.rparen),
                        S.seq(S.lex(B.lit("(?0")), RE.rparen),   
                    ).to(partial(UnsupportedFeature, feature="recursive group")),

            S.seq(S.lex(B.lit("(?#")), 
                  RE.comment.fld(),
                  RE.rparen).to(partial(UnsupportedFeature, feature="comment group")),
                  
                ).named("group_alternatives").bind(group_counter = lambda _, c: c + 1 if c is not ... else 1)


    anchor = S.alt(caret, dollar, boundary_escape).to(partial(UnsupportedFeature, feature="group existence test"))


    braced_quantifier = S.alt(
        S.seq(lbrace, +number, rbrace).bimap(call(Quantifier, minimum=_0, maximum=_0), lambda q: (q.minimum,)),
        S.seq(lbrace, +number, comma, rbrace).bimap(call(Quantifier, minimum=_0, maximum=None), lambda q: (q.minimum,)),
        S.seq(lbrace, comma, +number, rbrace).bimap(call(Quantifier, minimum=0, maximum=_0), lambda q: (q.maximum,)),
        S.seq(lbrace, number.fld('minimum'), comma, number.fld('maximum'), rbrace).to(Quantifier)
    )


    quantifier = (S.alt(
            braced_quantifier,
            question.to(partial(Quantifier,minimum=0, maximum=1)),
            star.to(partial(Quantifier,minimum=0, maximum=None)),
            plus.to(partial(Quantifier,minimum=1, maximum=None)),
        ) + ~question).map(call(replace, _0, greedy=_1.not_))


    backreference = S.alt(
        (backslash >> number).bimap(_0, lambda x: (x,)),
        (S.lex(B.lit("\\g<")) >> name // greater).bimap(_0, lambda x: (x,))
    )

    atom = S.alt(        
            backreference.check(lambda v, group_counter: v == 0 or (group_counter is not ... and len(group_counter) >= v)),
            S.seq(literal.fld('text')).to(LiteralAtom),
            char_class,
            anchor,
            dot,
            shorthand,
            unicode_category_escape,
            group,
            )

    piece = S.seq(atom.fld(), (~quantifier).fld('quantifier')).to(Piece)

    branch = S.seq((piece.many().fld('pieces'))).to(Branch)

    regex = S.seq(branch.sep_by(or_).fld('branches')).to(Regex)
    regex_full = rule((regex // S.eof()).bimap(_0, lambda x: (x,)), is_root=True)






def parse(data: str, *, syntax: Syntax | None = None, cache: Optional[Cache[Any]] = None) -> Any:
    return RE.parse(data, syntax=syntax, cache=cache)


@dataclass
class VerifyResult:
    ok: bool
    pattern: str
    syncraft: Any
    re:Any
    err_syncraft: Any
    err_re: Any




def verify(pattern: str, profile: bool = False) -> VerifyResult:

    myerr = None
    err = None
    cache: Cache[Any] = Cache()
    if profile:
        cache = cache.with_tracer()
    
    parsed = parse(pattern, cache=cache)
    if cache.tracer is not None:
        cache.tracer
        
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



