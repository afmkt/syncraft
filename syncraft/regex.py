from __future__ import annotations

from typing import overload, Literal, List
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any
import unicodedata
from syncraft.ast import AST
from syncraft.algebra import Error
from syncraft.syntax import Syntax
from syncraft.fa import Builder
from syncraft.cache import Cache
from syncraft.grammar import Grammar as G, lazy, rule, grammar
from syncraft.mapper import call, _0, _1, const, at
from functools import partial

try:
    import regex as re
except ImportError:
    import re



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
class UnsupportedFeature:
    feature: str
    message: Optional[str] = None

    def __str__(self) -> str:
        return f"Unsupported feature: {self.feature}" + (f" - {self.message}" if self.message else "")
    


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



@dataclass(frozen=True, slots=True)
class UnicodeCategoryAtom:
    categories: Tuple[str, ...]
    negated: bool = False   


@dataclass(frozen=True, slots=True)
class CharRange:
    start: str
    end: str

@dataclass(frozen=True, slots=True)
class CharClassAtom:
    items: Tuple[Union[str, CharRange], ...]
    negated: bool = False




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
    RECURSION= auto()

@dataclass(frozen=True, slots=True)
class InlineFlags:
    enabled: Tuple[str, ...]
    disabled: Optional[Tuple[str, ...]] = None


@dataclass(frozen=True, slots=True)
class GroupAtom:
    kind: GroupKind
    pattern: Optional[Regex] = None
    name: Optional[str] = None
    inline_flags: Optional[InlineFlags] = None

    




@dataclass(frozen=True, slots=True)
class Quantifier:
    minimum: int
    maximum: Optional[int]     # None → unbounded
    greedy: bool = True

@dataclass(frozen=True, slots=True)
class LiteralAtom:
    text: str


@dataclass(frozen=True, slots=True)
class AnchorAtom:
    kind: AnchorKind

@dataclass(frozen=True, slots=True)
class DotAtom:
    pass


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


@dataclass(frozen=True, slots=True)
class Branch:
    pieces: Tuple[Piece, ...]


@dataclass(frozen=True, slots=True)
class Regex:
    branches: Tuple[Branch, ...]

B = Builder[str]
S = Syntax.set(builtin=True)
@grammar
class RE(G):
    dollar = S.lex(B.lit("$"))
    number = S.lex(B.oneof("0123456789").many(at_least=1)).iso(int, str)
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
    shorthand = S.lex(B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"])).iso(ShorthandKind.from_literal, ShorthandKind.to_literal).to(ShorthandAtom)
    category_name = unicode_category.many().map(tuple)
    unicode_category_escape = S.alt(
        S.seq(escaped_p.map(const(False)).fld('negated'), category_name.fld('categories'), rbrace).to(UnicodeCategoryAtom),
        S.seq(escaped_P.map(const(True)).fld('negated'), category_name.fld('categories'), rbrace).to(UnicodeCategoryAtom)
        )
        
    unicode_name = (unicode_letter + S.alt(unicode_letter, underscore, space, hyphen).many()).map((_0.list + _1).apply(''.join))
    name_continue = unicode_letter | underscore
    name_start = unicode_letter | underscore
    name = (name_start + name_continue.many()).map((_0.list + _1).apply(''.join))
    unicode_escape = S.alt((escaped_x >> hex_pair).map(call(int, _0, 16).apply(chr)), 
                    (escaped_u >> hex_quad).map(call(int, _0, 16).apply(chr)),
                    (escaped_U >> hex_octa).map(call(int, _0, 16).apply(chr)), 
                    ((escaped_N >> unicode_name) // rbrace).map(_0.apply(unicodedata.lookup)))
    escaped_metachar = (backslash >> meta_char).map(_0)
    escaped_0 = S.lex(B.lit("\\0"))
    octal_digit = S.lex(B.range("0", "7"))
    octal_escape = S.alt(
        (escaped_0 >> octal_digit + octal_digit).map(call(int, _0 + _1, 8).apply(chr)),
        (backslash >> octal_digit.many(at_least=1)).map(call(int, _0.apply(''.join), 8).apply(chr))
    )
    escaped_literal = octal_escape | control_escape | unicode_escape | escaped_metachar
    literal = escaped_literal | literal_char
    class_meta_char = minus | rsquare | backslash
    escaped_class_meta= (backslash >> class_meta_char).map(_0)
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
    char_class = S.seq(lsquare, (~caret).map(bool).fld('negated'), class_class_items.fld('items'), rsquare).to(CharClassAtom)

    flag = S.lex(B.oneof("iLmsuaxw"))
    flag_seq = flag.many().map(tuple)
    inline_flags = S.seq(flag_seq.fld('enabled'), (~(minus >> flag_seq)).map(at().if_then_else(_0, None)).fld('disabled')).to(InlineFlags)
    comment = S.lex(B.range("\u0000", "\U0010FFFF") - B.lit(")").many(at_least=1))

    @lazy(S)
    def group(): # type: ignore
        def alternative(kind: GroupKind, prefix: Syntax, pettern: Syntax, postfix: Syntax) -> Syntax:
            return S.seq(prefix, pettern.fld('pattern'), postfix).to(partial(GroupAtom, kind=kind))


        return S.alt(
            alternative(GroupKind.CAPTURE, RE.lparen, RE.regex, RE.rparen),
            alternative(GroupKind.NON_CAPTURE, S.lex(B.lit("(?:")), RE.regex, RE.rparen),
            alternative(GroupKind.LOOKAHEAD, S.lex(B.lit("(?=")), RE.regex, RE.rparen),
            alternative(GroupKind.NEG_LOOKAHEAD, S.lex(B.lit("(?!")), RE.regex, RE.rparen),
            alternative(GroupKind.LOOKBEHIND, S.lex(B.lit("(?<=")), RE.regex, RE.rparen),
            alternative(GroupKind.NEG_LOOKBEHIND, S.lex(B.lit("(?<!" )), RE.regex, RE.rparen),
            S.seq(S.lex(B.lit("(?")), RE.inline_flags.fld(), RE.rparen).to(partial(GroupAtom, kind=GroupKind.FLAGS)),

            S.seq(S.lex(B.lit("(?P<")), RE.name.fld(), RE.greater, RE.regex.fld('pattern'), RE.rparen).to(partial(GroupAtom, kind=GroupKind.CAPTURE)),

            S.seq( S.lex(B.lit("(?")), RE.inline_flags.fld(), RE.colon, RE.regex.fld('pattern'), RE.rparen).to(partial(GroupAtom, kind=GroupKind.FLAGS_SCOPED)),
            
            S.seq(S.lex(B.lit("(?")), 
                        S.alt(
                            S.seq(S.lex(B.lit("(?=")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?!")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?<=")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?<!" )), +RE.regex, RE.rparen),
                        ), 
                        +RE.regex, 
                        RE.rparen).to(partial(UnsupportedFeature, feature="lookaround assertion group")),

            S.seq(S.lex(B.lit("(?(")), RE.number | RE.name, +RE.regex, RE.rparen).to(partial(UnsupportedFeature, feature="group existence test")),

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
                ).named("group_alternatives").update(group_counter = lambda c, _: c + 1 if c is not ... else 1)


    anchor = S.alt(caret, dollar, boundary_escape).map(AnchorKind.from_literal).to(AnchorAtom)


    braced_quantifier = S.alt(
        S.seq(lbrace, +number, rbrace).map(call(Quantifier, minimum=_0, maximum=_0)),
        S.seq(lbrace, +number, comma, rbrace).map(call(Quantifier, minimum=_0, maximum=None)),
        S.seq(lbrace, comma, +number, rbrace).map(call(Quantifier, minimum=0, maximum=_0)),
        S.seq(lbrace, number.fld('minimum'), comma, number.fld('maximum'), rbrace).to(Quantifier)
    )


    quantifier = (S.alt(
            braced_quantifier,
            question.to(partial(Quantifier,minimum=0, maximum=1)),
            star.to(partial(Quantifier,minimum=0, maximum=None)),
            plus.to(partial(Quantifier,minimum=1, maximum=None)),
        ) + ~question).map(call(replace, _0, greedy=_1.not_))


    backreference = S.alt(
        (backslash >> number).map(_0),
        (S.lex(B.lit("\\g<")) >> name // greater).map(_0)
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
    regex_full = rule((regex // S.eof()).map(_0), is_root=True)










@overload
def parse(data: str, *, raw: Literal[True], cache: Optional[Cache[Any]] = None) -> AST: ...
@overload
def parse(data: str, *, raw: Literal[False], cache: Optional[Cache[Any]] = None) -> Regex | Error: ...

def parse(data: str, *, raw:bool=False, cache: Optional[Cache[Any]] = None) -> Regex | Error | AST:
    return RE.parse(data, raw=raw, cache=cache)


def parse_regex(syntax: Syntax, 
                pattern: str, 
                *, 
                raw:bool=False) -> Any:
    return RE.parse(pattern, syntax=syntax, raw=raw)

@dataclass
class VerifyResult:
    ok: bool
    pattern: str
    syncraft: Any
    re:Any
    err_syncraft: Any
    err_re: Any




def verify(pattern: str, profile: bool = False) -> VerifyResult:
    import timeit
    timeit.timeit(lambda: None, number=1)  # Warm up timer
    myerr = None
    err = None
    cache: Cache[Any] = Cache()
    if profile:
        cache = cache.with_profiler()
    
    parsed = parse(pattern, raw=False, cache=cache)
    if cache.profiler is not None:
        cache.profiler.report()
        
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



