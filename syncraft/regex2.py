from __future__ import annotations

from typing import overload, Literal
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any
import unicodedata
from syncraft.ast import AST, Token, Nothing
from syncraft.algebra import Error
from syncraft.syntax import Syntax
from syncraft.fa import Builder
from syncraft.cache import Cache
from syncraft.grammar import Grammar, lazy, rule, root

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
    DIGIT = auto()
    NOT_DIGIT = auto()
    WORD = auto()
    NOT_WORD = auto()
    SPACE = auto()
    NOT_SPACE = auto()
    @classmethod
    def from_literal(cls, literal: str) -> ShorthandKind:        
        return {
            r"\d": cls.DIGIT,
            r"\D": cls.NOT_DIGIT,
            r"\w": cls.WORD,
            r"\W": cls.NOT_WORD,
            r"\s": cls.SPACE,
            r"\S": cls.NOT_SPACE,
        }[literal]

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

class RE(Grammar, builtin=True):
    dollar = rule(Grammar.lex(B.lit("$")))
    number = rule(Grammar.lex(B.oneof("0123456789").many(at_least=1)).map(lambda m: int(m.text)))
    dot = rule(Grammar.lex(B.lit(".")).to(DotAtom))
    or_ = rule(Grammar.lex(B.lit("|")))
    whitespace = rule(Grammar.lex(B.oneof(" \t\n\r\f\v")))
    question = rule(Grammar.lex(B.lit("?")))
    star = rule(Grammar.lex(B.lit("*")))
    plus = rule(Grammar.lex(B.lit("+")))
    lbrace = rule(Grammar.lex(B.lit("{")))
    rbrace = rule(Grammar.lex(B.lit("}")))
    comma = rule(Grammar.lex(B.lit(",")))
    lparen = rule(Grammar.lex(B.lit("(")))
    rparen = rule(Grammar.lex(B.lit(")")))
    lsquare = rule(Grammar.lex(B.lit("[")))
    rsquare = rule(Grammar.lex(B.lit("]")))
    colon = rule(Grammar.lex(B.lit(":")))
    less = rule(Grammar.lex(B.lit("<")))
    greater = rule(Grammar.lex(B.lit(">")))
    equal = rule(Grammar.lex(B.lit("=")))
    bang = rule(Grammar.lex(B.lit("!")))
    caret = rule(Grammar.lex(B.lit("^")))
    backslash = rule(Grammar.lex(B.lit("\\")))
    minus = rule(Grammar.lex(B.lit("-")))
    boundary_escape = rule(Grammar.lex(B.oneof(["\\A", "\\Z", "\\b", "\\B"])))
    escaped_x = rule(Grammar.lex(B.lit("\\x")))
    escaped_u = rule(Grammar.lex(B.lit("\\u")))
    escaped_U = rule(Grammar.lex(B.lit("\\U")))
    escaped_N = rule(Grammar.lex(B.lit("\\N{")))
    escaped_p = rule(Grammar.lex(B.lit("\\p{")))
    escaped_P = rule(Grammar.lex(B.lit("\\P{")))
    underscore = rule(Grammar.lex(B.lit("_")))
    space = rule(Grammar.lex(B.lit(" ")))
    hyphen = rule(Grammar.lex(B.lit("-")))
    unicode_scalar = rule(Grammar.lex(B.range("\u0000", "\U0010FFFF")))
    unicode_category = rule(Grammar.lex(B.oneof(["Lu", "Ll", "Lt", "Lm", "Lo", "L", "M", "N", "Nd", "Nl", "No", "P", "Pd", "Ps", "Pe", "S", "Sm", "Sc", "Z", "Zs", "C"])))
    unicode_letter = rule(Grammar.lex(B.unicode_category(["Lu", "Ll", "Lt", "Lm", "Lo"])))
    unicode_digit = rule(Grammar.lex(B.unicode_category(["Nd"])))
    class_literal = rule(Grammar.lex(B.range("\u0000", "\U0010FFFF") - B.oneof("\\]")))
    literal_char = rule(Grammar.lex(B.range("\u0000", "\U0010FFFF") - B.oneof("\\.[(){}|+*?^$")).map(lambda x: x.text))

    hex_octa = rule(Grammar.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=8, at_most=8)).map(lambda tok: tok.text))
    hex_quad = rule(Grammar.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=4, at_most=4)).map(lambda tok: tok.text))
    hex_pair = rule(Grammar.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=2, at_most=2)).map(lambda tok: tok.text))
    meta_char = rule(Grammar.lex(B.oneof("\"\\.[](){}|+*?^$")))
    control_escape = rule(Grammar.lex(B.oneof(["\\t", "\\n", "\\r", "\\f", "\\v", "\\0"])))
    shorthand = rule(Grammar.lex(B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"])).map(lambda t: ShorthandKind.from_literal(t.text)).to(ShorthandAtom))
    category_name = rule(unicode_category.many().map(lambda ts: tuple(t.text for t in ts)))
    unicode_category_escape = rule(Grammar.alt(
        Grammar.seq2(UnicodeCategoryAtom, negated=+escaped_p.map(lambda _: False), categories=+category_name, _=rbrace),
        Grammar.seq2(UnicodeCategoryAtom, negated=+escaped_P.map(lambda _: True), categories=+category_name, _=rbrace))
        )
    unicode_name = rule((unicode_letter + Grammar.alt(unicode_letter, underscore, space, hyphen).many()).map(lambda t: ''.join([t[0].text] + [c.text for c in t[1]])))
    name_continue = rule(unicode_letter | underscore)
    name_start = rule(unicode_letter | underscore)
    name = rule((name_start + name_continue.many()).map(lambda t: ''.join([t[0].text] + [c.text for c in t[1]])))
    unicode_escape = rule(Grammar.alt((escaped_x >> hex_pair).map(lambda t: chr(int(t[0], 16))), 
                    (escaped_u >> hex_quad).map(lambda t: chr(int(t[0], 16))),
                    (escaped_U >> hex_octa).map(lambda t: chr(int(t[0], 16))), 
                    ((escaped_N >> unicode_name) // rbrace).map(lambda t: unicodedata.lookup(t[0]))))
    escaped_metachar = rule((backslash >> meta_char).map(lambda t: t[0]))
    escaped_0 = rule(Grammar.lex(B.lit("\\0")))
    octal_digit = rule(Grammar.lex(B.range("0", "7")))
    octal_escape = rule(Grammar.alt(
        (escaped_0 >> octal_digit + octal_digit).map(lambda t: chr(int(t[0].text + t[1].text, 8))),
        (backslash >> octal_digit.many(at_least=1)).map(lambda t: chr(int(''.join([tt.text for tt in t[0]]), 8)))
    ))
    escaped_literal = rule(octal_escape | control_escape | unicode_escape | escaped_metachar)
    literal = rule(escaped_literal | literal_char)
    class_meta_char = rule(minus | rsquare | backslash)
    escaped_class_meta= rule((backslash >> class_meta_char).map(lambda t: t[0]))
    class_atom = rule(Grammar.choice(
                        class_literal,
                        shorthand,
                        escaped_metachar,
                        control_escape,
                        unicode_escape,
                        unicode_category_escape,
                        escaped_class_meta,
                        ).map(lambda t: t.text if isinstance(t, Token) else t))

    irange = rule(Grammar.seq2(CharRange, start=class_atom, _=-minus, end=class_atom))
    class_item = rule(irange | class_atom)
    class_class_items = rule((~(rsquare | minus) + class_item.many()).map(lambda t: (t[1] + [t[0].text]) if t[0] else t[1]))
    char_class = rule(Grammar.seq2(_=-lsquare, negated=(~caret).map(bool), items=class_class_items, __=-rsquare).to(CharClassAtom))

    flag = rule(Grammar.lex(B.oneof("iLmsuaxw")))
    flag_seq = rule(flag.many().map(lambda ts: tuple(t.text for t in ts)))
    inline_flags = rule(Grammar.seq2(InlineFlags, enabled=+flag_seq, disabled=+(~(minus >> flag_seq)).map(lambda t: t[0] if t is not Nothing else None)))
    comment = rule(Grammar.lex(B.range("\u0000", "\U0010FFFF") - B.lit(")").many(at_least=1)).map(lambda tok: tok.text))

    

    @lazy
    def group(cls):
        return Grammar.alt(
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.CAPTURE), 
                                 _=cls.lparen, 
                                 pattern=+cls.regex, 
                                 __=cls.rparen),
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.NON_CAPTURE), 
                                 __=Grammar.lex(B.lit("(?:")), 
                                 pattern=+cls.regex, 
                                 _=cls.rparen),
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.CAPTURE), 
                                 _=Grammar.lex(B.lit("(?P<")), 
                                 name=+cls.name, 
                                 _1=cls.greater, 
                                 pattern=+cls.regex, 
                                 _2=cls.rparen),
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.LOOKAHEAD), 
                                 _=Grammar.lex(B.lit("(?=")), 
                                 pattern=+cls.regex, 
                                 __=cls.rparen),                    
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.NEG_LOOKAHEAD), 
                                 _=Grammar.lex(B.lit("(?!")), 
                                 pattern=+cls.regex, 
                                 __=cls.rparen),
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.LOOKBEHIND), 
                                 _=Grammar.lex(B.lit("(?<=")), 
                                 pattern=+cls.regex, 
                                 __=cls.rparen),
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.NEG_LOOKBEHIND), 
                                 _=Grammar.lex(B.lit("(?<!" )), 
                                 pattern=+cls.regex, 
                                 __=cls.rparen),
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.FLAGS), 
                                 _=Grammar.lex(B.lit("(?")), 
                                 inline_flags=+cls.inline_flags, 
                                 _2=cls.rparen),
                    Grammar.seq2(partial(GroupAtom, kind=GroupKind.FLAGS_SCOPED), 
                                 _=Grammar.lex(B.lit("(?")), 
                                 inline_flags=+cls.inline_flags, 
                                 _2=cls.colon, 
                                 pattern=+cls.regex, 
                                 _3=cls.rparen),
                    
                    Grammar.seq(Grammar.lex(B.lit("(?")), 
                                            Grammar.alt(
                                                Grammar.seq(Grammar.lex(B.lit("(?=")), +cls.regex, cls.rparen),
                                                Grammar.seq(Grammar.lex(B.lit("(?!")), +cls.regex, cls.rparen),
                                                Grammar.seq(Grammar.lex(B.lit("(?<=")), +cls.regex, cls.rparen),
                                                Grammar.seq(Grammar.lex(B.lit("(?<!" )), +cls.regex, cls.rparen),
                                            ),
                                            +cls.regex, 
                                            cls.rparen).to(partial(UnsupportedFeature, feature="lookaround assertion group")),
                    Grammar.seq(Grammar.lex(B.lit("(?(")), 
                                cls.number | cls.name, 
                                +cls.regex, 
                                cls.rparen).to(partial(UnsupportedFeature, feature="group existence test")),
                    Grammar.alt(Grammar.seq(Grammar.lex(B.lit("(?&")), +cls.name, cls.rparen),
                                Grammar.seq(Grammar.lex(B.lit("(?")), +cls.number, cls.rparen),
                                Grammar.seq(Grammar.lex(B.lit("(?R")), cls.rparen),
                                Grammar.seq(Grammar.lex(B.lit("(?r")), cls.rparen),
                                Grammar.seq(Grammar.lex(B.lit("(?P")), cls.rparen),            
                                Grammar.seq(Grammar.lex(B.lit("(?p")), cls.rparen),
                                Grammar.seq(Grammar.lex(B.lit("(?0")), cls.rparen),   
                            ).to(partial(UnsupportedFeature, feature="recursive group")),
                    Grammar.seq2(partial(UnsupportedFeature, feature="comment group"), _=Grammar.lex(B.lit("(?#")), comment=+cls.comment, __=cls.rparen),
                ).update(group_counter = lambda c, _: c + 1 if c is not ... else 1)



    anchor = rule(Grammar.alt(caret, 
                    dollar,
                    boundary_escape).map(lambda t: AnchorKind.from_literal(t.text)).to(AnchorAtom))


    braced_quantifier = rule(Grammar.alt(
        Grammar.seq(lbrace, +number, rbrace).map(lambda n: Quantifier(minimum=n[0], maximum=n[0])),
        Grammar.seq(lbrace, +number, comma, rbrace).map(lambda t: Quantifier(minimum=t[0], maximum=None)),
        Grammar.seq(lbrace, comma, +number, rbrace).map(lambda t: Quantifier(minimum=0, maximum=t[0])),
        Grammar.seq(lbrace, +number.mark('minimum'), comma, +number.mark('maximum'), rbrace).to(Quantifier)
    ))


    quantifier = rule((Grammar.alt(
            braced_quantifier,
            question.to(partial(Quantifier,minimum=0, maximum=1)),
            star.to(partial(Quantifier,minimum=0, maximum=None)),
            plus.to(partial(Quantifier,minimum=1, maximum=None)),
        ) + ~question).map(lambda t: replace(t[0], greedy=not t[1])))


    backreference = rule(Grammar.alt(
        (backslash >> number).map(lambda n: n[0]),
        (Grammar.lex(B.lit("\\g<")) >> name // greater).map(lambda n: n[0])
    ))

    atom = Grammar.alt(        
            backreference.check(lambda v, group_counter: v == 0 or (group_counter is not ... and len(group_counter) >= v)),
            Grammar.seq2(LiteralAtom, text=literal),
            char_class,
            anchor,
            dot,
            shorthand,
            unicode_category_escape,
            group,
            ).named('atom')

    piece = rule(Grammar.seq2(Piece, atom=+atom, quantifier=+(~quantifier)))

    branch = rule(Grammar.seq2(Branch, pieces=piece.many()))

    regex = rule(Grammar.seq2(Regex, branches=branch.sep_by(or_)))

    regex_full = root((regex // Grammar.eof()).map(lambda r: r[0]))







@overload
def parse(data: str, *, raw: Literal[True]) -> AST: ...
@overload
def parse(data: str, *, raw: Literal[False]) -> Regex | Error: ...

def parse(data: str, *, raw:bool=False) -> Regex | Error | AST:
    return RE.parse(data, raw=raw)


def parse_regex(syntax: Syntax[Any, Any], 
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
    
    parsed = parse(pattern, raw=False)
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


def benchmark_fair():
    # ITERATOR to feed unique patterns
    import timeit
    result = []
    base_pattern = r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    unique_patterns = [f"{base_pattern}(?#{i})" for i in range(1000)]    
    pat_iter = iter(unique_patterns)
    
    def run_syncraft():
        try:
            p = next(pat_iter)
            # You are already correctly passing a new cache here
            parse(p, raw=False) 
        except StopIteration:
            pass

    # Reset iterator for the second test
    pat_iter_re = iter(unique_patterns)

    def run_re():
        try:
            p = next(pat_iter_re)
            # This forces a compile because 'p' has never been seen before
            re.compile(p)
        except StopIteration:
            pass

    # 2. Run Benchmark (1000 loops for 1000 patterns)
    t_syncraft = timeit.timeit(run_syncraft, number=1000)
    t_re = timeit.timeit(run_re, number=1000)

    result.append("--- FAIR COMPARISON (Cold Start) ---")
    
    result.append(f"Syncraft: {t_syncraft/1000:.5f} s/parse")
    result.append(f"Regex:    {t_re/1000:.5f} s/compile")
    
    ratio = (t_syncraft) / (t_re)
    result.append(f"Multiplier: Syncraft is {ratio:.1f}x slower than C-compiled Regex")
    return result

