from __future__ import annotations


from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any
import unicodedata

from syncraft.algebra import Error
from syncraft.syntax import Syntax
from syncraft.fa import Builder
from syncraft.alphabet import Alphabet
from syncraft.grammar import Grammar, lazy, rule, grammar
from functools import reduce
from syncraft.bimap import Not
try:
    import regex as re
except ImportError:
    import re




class UnsupportedFeature:
    def __init__(self, feature: str, *args, **kwargs) -> None:
        self.feature = feature
        self.args = args
        self.kwargs = kwargs

    def __str__(self) -> str:
        return f"Unsupported feature: {self.feature}" + (f" with args: {self.args}" if self.args else "") + (f" and kwargs: {self.kwargs}" if self.kwargs else "")
    
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
    
    class_class_items = (~(rsquare | minus) + class_item.many()).map(lambda x: x[1] + (x[0],) if x[0] else x[1])
    char_class = S.seq(lsquare, +(~caret), +class_class_items, rsquare).to(lambda env: (env.negated, env.items), lambda env: CharClassAtom(negated=env.negated, items=env.items))

    flag = S.lex(B.oneof("iLmsuaxw"))
    enabled_flags = flag.many()
    disabled_flags = (~(minus >> flag.many())).map(lambda x: x[0] if x else None)
    
    inline_flags = S.seq(+enabled_flags, +disabled_flags).to(lambda env: (env.enabled_flags, env.disabled_flags), lambda env: InlineFlags(env.enabled_flags, env.disabled_flags))
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
            S.seq(S.lex(B.lit("(?")), +RE.inline_flags, RE.rparen).to(lambda env: (env.inline_flags,), lambda env: GroupAtom(inline_flags=env.inline_flags, kind=GroupKind.FLAGS)),
            S.seq(S.lex(B.lit("(?P<")), +RE.name, RE.greater, +RE.regex, RE.rparen).to(lambda env: (env.name, env.regex), lambda env: GroupAtom(name=env.name, regex=env.regex, kind=GroupKind.CAPTURE)),
            S.seq( S.lex(B.lit("(?")), +RE.inline_flags, RE.colon, +RE.regex, RE.rparen).to(lambda env: (env.inline_flags, env.regex), lambda env: GroupAtom(inline_flags=env.inline_flags, regex=env.regex, kind=GroupKind.FLAGS_SCOPED)),

            S.seq(S.lex(B.lit("(?")), 
                        S.alt(
                            S.seq(S.lex(B.lit("(?=")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?!")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?<=")), +RE.regex, RE.rparen),
                            S.seq(S.lex(B.lit("(?<!" )), +RE.regex, RE.rparen),
                        ), 
                        +RE.regex, 
                        RE.rparen).to(lambda env: env.regex, lambda env: UnsupportedFeature(regex=env.regex, feature="lookaround assertion group")),

            S.seq(S.lex(B.lit("(?(")), RE.number | RE.name, +RE.regex, RE.rparen).to(lambda env: (env.regex,), lambda env:  UnsupportedFeature(regex=env.regex, feature="group existence test")),

            S.alt(      S.seq(S.lex(B.lit("(?&")), +RE.name, RE.rparen),
                        S.seq(S.lex(B.lit("(?")), +RE.number, RE.rparen),
                        S.seq(S.lex(B.lit("(?R")), RE.rparen),
                        S.seq(S.lex(B.lit("(?r")), RE.rparen),
                        S.seq(S.lex(B.lit("(?P")), RE.rparen),            
                        S.seq(S.lex(B.lit("(?p")), RE.rparen),
                        S.seq(S.lex(B.lit("(?0")), RE.rparen),   
                    ).to(lambda env: env.regex, lambda env: UnsupportedFeature(regex=env.regex, feature="recursive group")),

            S.seq(S.lex(B.lit("(?#")), 
                  +RE.comment,
                  RE.rparen).to(lambda env: env.regex, lambda env: UnsupportedFeature(regex=env.regex, feature="comment group")),
                  
                ).named("group_alternatives").bind(group_counter = lambda _, c: c + 1 if c is not ... else 1)


    anchor = S.alt(caret, dollar, boundary_escape).to(lambda env: env.regex, lambda env: UnsupportedFeature(regex=env.regex, feature="group existence test"))


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
    return RE.parse(data, syntax=syntax)


@dataclass
class VerifyResult:
    ok: bool
    pattern: str
    syncraft: Any
    re:Any
    err_syncraft: Any
    err_re: Any




def verify(pattern: str) -> VerifyResult:

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



