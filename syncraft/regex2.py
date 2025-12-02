from __future__ import annotations

from typing import overload, Literal
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any
import unicodedata
from syncraft.ast import AST
from syncraft.algebra import Error
from syncraft.syntax import Syntax
from syncraft.fa import Builder
from syncraft.cache import Cache
from syncraft.grammar import Grammar as G, lazy, rule, root, call, _0, _1, const, at
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

class RE(G, builtin=True):
    dollar = rule(G.lex(B.lit("$")))
    number = rule(G.lex(B.oneof("0123456789").many(at_least=1)).map(int))
    dot = rule(G.lex(B.lit(".")).to(DotAtom))
    or_ = rule(G.lex(B.lit("|")))
    whitespace = rule(G.lex(B.oneof(" \t\n\r\f\v")))
    question = rule(G.lex(B.lit("?")))
    star = rule(G.lex(B.lit("*")))
    plus = rule(G.lex(B.lit("+")))
    lbrace = rule(G.lex(B.lit("{")))
    rbrace = rule(G.lex(B.lit("}")))
    comma = rule(G.lex(B.lit(",")))
    lparen = rule(G.lex(B.lit("(")))
    rparen = rule(G.lex(B.lit(")")))
    lsquare = rule(G.lex(B.lit("[")))
    rsquare = rule(G.lex(B.lit("]")))
    colon = rule(G.lex(B.lit(":")))
    less = rule(G.lex(B.lit("<")))
    greater = rule(G.lex(B.lit(">")))
    equal = rule(G.lex(B.lit("=")))
    bang = rule(G.lex(B.lit("!")))
    caret = rule(G.lex(B.lit("^")))
    backslash = rule(G.lex(B.lit("\\")))
    minus = rule(G.lex(B.lit("-")))
    boundary_escape = rule(G.lex(B.oneof(["\\A", "\\Z", "\\b", "\\B"])))
    escaped_x = rule(G.lex(B.lit("\\x")))
    escaped_u = rule(G.lex(B.lit("\\u")))
    escaped_U = rule(G.lex(B.lit("\\U")))
    escaped_N = rule(G.lex(B.lit("\\N{")))
    escaped_p = rule(G.lex(B.lit("\\p{")))
    escaped_P = rule(G.lex(B.lit("\\P{")))
    underscore = rule(G.lex(B.lit("_")))
    space = rule(G.lex(B.lit(" ")))
    hyphen = rule(G.lex(B.lit("-")))
    unicode_scalar = rule(G.lex(B.range("\u0000", "\U0010FFFF")))
    unicode_category = rule(G.lex(B.oneof(["Lu", "Ll", "Lt", "Lm", "Lo", "L", "M", "N", "Nd", "Nl", "No", "P", "Pd", "Ps", "Pe", "S", "Sm", "Sc", "Z", "Zs", "C"])))
    unicode_letter = rule(G.lex(B.unicode_category(["Lu", "Ll", "Lt", "Lm", "Lo"])))
    unicode_digit = rule(G.lex(B.unicode_category(["Nd"])))
    class_literal = rule(G.lex(B.range("\u0000", "\U0010FFFF") - B.oneof("\\]")))
    literal_char = rule(G.lex(B.range("\u0000", "\U0010FFFF") - B.oneof("\\.[(){}|+*?^$")))

    hex_octa = rule(G.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=8, at_most=8)))
    hex_quad = rule(G.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=4, at_most=4)))
    hex_pair = rule(G.lex(B.oneof("0123456789abcdefABCDEF").many(at_least=2, at_most=2)))
    meta_char = rule(G.lex(B.oneof("\"\\.[](){}|+*?^$")))
    control_escape = rule(G.lex(B.oneof(["\\t", "\\n", "\\r", "\\f", "\\v", "\\0"])))
    shorthand = rule(G.lex(B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"])).map(ShorthandKind.from_literal).to(ShorthandAtom))
    category_name = rule(unicode_category.many().map(tuple))
    unicode_category_escape = rule(G.alt(
        G.seq2(UnicodeCategoryAtom, negated=+escaped_p.map(const(False)), categories=+category_name, _=rbrace),
        G.seq2(UnicodeCategoryAtom, negated=+escaped_P.map(const(True)), categories=+category_name, _=rbrace))
        )
    unicode_name = rule((unicode_letter + G.alt(unicode_letter, underscore, space, hyphen).many()).map((_0.list + _1).apply(''.join)))
    name_continue = rule(unicode_letter | underscore)
    name_start = rule(unicode_letter | underscore)
    name = rule((name_start + name_continue.many()).map((_0.list + _1).apply(''.join)))
    unicode_escape = rule(G.alt((escaped_x >> hex_pair).map(call(int, _0, 16).apply(chr)), 
                    (escaped_u >> hex_quad).map(call(int, _0, 16).apply(chr)),
                    (escaped_U >> hex_octa).map(call(int, _0, 16).apply(chr)), 
                    ((escaped_N >> unicode_name) // rbrace).map(_0.apply(unicodedata.lookup))))
    escaped_metachar = rule((backslash >> meta_char).map(_0))
    escaped_0 = rule(G.lex(B.lit("\\0")))
    octal_digit = rule(G.lex(B.range("0", "7")))
    octal_escape = rule(G.alt(
        (escaped_0 >> octal_digit + octal_digit).map(call(int, _0 + _1, 8).apply(chr)),
        (backslash >> octal_digit.many(at_least=1)).map(call(int, _0.apply(''.join), 8).apply(chr))
    ))
    escaped_literal = rule(octal_escape | control_escape | unicode_escape | escaped_metachar)
    literal = rule(escaped_literal | literal_char)
    class_meta_char = rule(minus | rsquare | backslash)
    escaped_class_meta= rule((backslash >> class_meta_char).map(_0))
    class_atom = rule(G.alt(
                        class_literal,
                        shorthand,
                        escaped_metachar,
                        control_escape,
                        unicode_escape,
                        unicode_category_escape,
                        escaped_class_meta,
                        ))

    irange = rule(G.seq2(CharRange, start=class_atom, _=-minus, end=class_atom))
    class_item = rule(irange | class_atom)
    class_class_items = rule((~(rsquare | minus) + class_item.many()).map(_0.if_then_else(_1 + _0.list, _1)))
    char_class = rule(G.seq2(CharClassAtom, _=-lsquare, negated=(~caret).map(bool), items=class_class_items, __=-rsquare))

    flag = rule(G.lex(B.oneof("iLmsuaxw")))
    flag_seq = rule(flag.many().map(tuple))
    inline_flags = rule(G.seq2(InlineFlags, enabled=+flag_seq, disabled=+(~(minus >> flag_seq)).map(at().if_then_else(_0, None))))
    comment = rule(G.lex(B.range("\u0000", "\U0010FFFF") - B.lit(")").many(at_least=1)))

    

    @lazy
    def group(cls):
        def alternative(kind: GroupKind, prefix: Syntax, pettern: Syntax, postfix: Syntax) -> Syntax:
            return G.seq2(partial(GroupAtom, kind=kind), _=prefix, pattern=+pettern, __=postfix)

        return G.alt(
            alternative(GroupKind.CAPTURE, cls.lparen, cls.regex, cls.rparen),
            alternative(GroupKind.NON_CAPTURE, G.lex(B.lit("(?:")), cls.regex, cls.rparen),

                    G.seq2(partial(GroupAtom, kind=GroupKind.CAPTURE), 
                                 G.lex(B.lit("(?P<")), 
                                 +cls.name, 
                                 cls.greater, 
                                 +cls.regex.mark('pattern'), 
                                 cls.rparen),
            alternative(GroupKind.LOOKAHEAD, G.lex(B.lit("(?=")), cls.regex, cls.rparen),
            alternative(GroupKind.NEG_LOOKAHEAD, G.lex(B.lit("(?!")), cls.regex, cls.rparen),
            alternative(GroupKind.LOOKBEHIND, G.lex(B.lit("(?<=")), cls.regex, cls.rparen),
            alternative(GroupKind.NEG_LOOKBEHIND, G.lex(B.lit("(?<!" )), cls.regex, cls.rparen),
            alternative(GroupKind.FLAGS, G.lex(B.lit("(?")), cls.inline_flags, cls.rparen),
            
                    G.seq2(partial(GroupAtom, kind=GroupKind.FLAGS_SCOPED), 
                                 G.lex(B.lit("(?")), 
                                 +cls.inline_flags, 
                                 cls.colon, 
                                 +cls.regex.mark('pattern'), 
                                 cls.rparen),
                    
                    G.seq(G.lex(B.lit("(?")), 
                                            G.alt(
                                                G.seq(G.lex(B.lit("(?=")), +cls.regex, cls.rparen),
                                                G.seq(G.lex(B.lit("(?!")), +cls.regex, cls.rparen),
                                                G.seq(G.lex(B.lit("(?<=")), +cls.regex, cls.rparen),
                                                G.seq(G.lex(B.lit("(?<!" )), +cls.regex, cls.rparen),
                                            ),
                                            +cls.regex, 
                                            cls.rparen).to(partial(UnsupportedFeature, feature="lookaround assertion group")),
                    G.seq(G.lex(B.lit("(?(")), 
                                cls.number | cls.name, 
                                +cls.regex, 
                                cls.rparen).to(partial(UnsupportedFeature, feature="group existence test")),
                    G.alt(G.seq(G.lex(B.lit("(?&")), +cls.name, cls.rparen),
                                G.seq(G.lex(B.lit("(?")), +cls.number, cls.rparen),
                                G.seq(G.lex(B.lit("(?R")), cls.rparen),
                                G.seq(G.lex(B.lit("(?r")), cls.rparen),
                                G.seq(G.lex(B.lit("(?P")), cls.rparen),            
                                G.seq(G.lex(B.lit("(?p")), cls.rparen),
                                G.seq(G.lex(B.lit("(?0")), cls.rparen),   
                            ).to(partial(UnsupportedFeature, feature="recursive group")),
                    G.seq2(partial(UnsupportedFeature, feature="comment group"), G.lex(B.lit("(?#")), +cls.comment, cls.rparen),
                ).update(group_counter = lambda c, _: c + 1 if c is not ... else 1)



    anchor = rule(G.alt(caret, 
                    dollar,
                    boundary_escape).map(AnchorKind.from_literal).to(AnchorAtom))


    braced_quantifier = rule(G.alt(
        G.seq(lbrace, +number, rbrace).map(call(Quantifier, minimum=_0, maximum=_0)),
        G.seq2(partial(Quantifier, maximum=None), lbrace, +number, comma, rbrace),
        G.seq(lbrace, comma, +number, rbrace).map(call(Quantifier, minimum=0, maximum=_0)),
        G.seq2(Quantifier, lbrace, +number.mark('minimum'), comma, +number.mark('maximum'), rbrace)
    ))


    quantifier = rule((G.alt(
            braced_quantifier,
            question.to(partial(Quantifier,minimum=0, maximum=1)),
            star.to(partial(Quantifier,minimum=0, maximum=None)),
            plus.to(partial(Quantifier,minimum=1, maximum=None)),
        ) + ~question).map(call(replace, _0, greedy=_1.not_)))


    backreference = rule(G.alt(
        (backslash >> number).map(_0),
        (G.lex(B.lit("\\g<")) >> name // greater).map(_0)
    ))

    atom = rule(G.alt(        
            backreference.check(lambda v, group_counter: v == 0 or (group_counter is not ... and len(group_counter) >= v)),
            G.seq2(LiteralAtom, text=literal),
            char_class,
            anchor,
            dot,
            shorthand,
            unicode_category_escape,
            group,
            ))

    piece = rule(G.seq2(Piece, +atom, quantifier=+(~quantifier)))

    branch = rule(G.seq2(Branch, piece.many()))

    regex = rule(G.seq2(Regex, branch.sep_by(or_)))

    regex_full = root((regex // G.eof()).map(_0))







@overload
def parse(data: str, *, raw: Literal[True]) -> AST: ...
@overload
def parse(data: str, *, raw: Literal[False]) -> Regex | Error: ...

def parse(data: str, *, raw:bool=False) -> Regex | Error | AST:
    return RE.parse(data, raw=raw)


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

