from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any
import unicodedata
from syncraft.ast import AST, Token, Nothing, SyncraftError
from syncraft.algebra import Error
from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder
from syncraft.syntax import Syntax
from syncraft.parser import parse_string, parser
from syncraft.input import StreamCursor
try:
    import regex as re
except ImportError:
    import re


r"""
regex             = branch { "|" branch } ;
branch            = piece { piece } ;
piece             = atom [ quantifier ] ;
atom              = literal | char_class | group | anchor | dot | shorthand | unicode_category_escape ;

category_name     = unicode_letter { unicode_letter } ;
unicode_category_escape   = "\p{" category_name "}" | "\P{" category_name "}" ;



dot               = "." ;

quantifier        = "?" | "*" | "+" | braced_quantifier [ "?" ] ;
braced_quantifier = "{" number [ "," [ number ] ] "}" ;
number            = digit { digit } ;
digit             = "0".."9" ;

anchor            = "^" | "$" | boundary_escape ;
boundary_escape   = "\\A" | "\\Z" | "\\b" | "\\B" ;

group             = "(" regex ")"
                  | "(?:" regex ")"
                  | "(?P<" name ">" regex ")"
                  | "(?=" regex ")"
                  | "(?!" regex ")"
                  | "(?<=" regex ")"
                  | "(?<!" regex ")"
                  | "(?" inline_flags ")"
                  | "(?" inline_flags ":" regex ")"
                  ;
inline_flags      = flag_seq [ "-" flag_seq ] ;
flag_seq          = flag { flag } ;
flag              = "a" | "i" | "L" | "m" | "s" | "u" | "x" ;

char_class        = "[" [ "^" ] class_class_items "]" ;
class_class_items = leading_rsquare? class_item { class_item } ;
leading_rsquare   = "]" ;
class_literal     = unicode_scalar - {"\\", "]"} ;

class_item        = range | class_atom ;
range             = class_atom "-" class_atom ;
class_atom        = class_literal | shorthand | control_escape | unicode_escape | escaped_class_meta ;
escaped_class_meta= "\\" class_meta_char ;
class_meta_char   = "-" | "]" | "\\" ;

shorthand         = "\\d" | "\\D" | "\\s" | "\\S" | "\\w" | "\\W" ;

literal           = escaped_literal | literal_char ;
escaped_literal   = control_escape | unicode_escape | escaped_metachar ;
control_escape    = "\\t" | "\\n" | "\\r" | "\\f" | "\\v" ;
escaped_metachar  = "\\" meta_char ;
meta_char         = "\\" | "." | "[" | "]" | "(" | ")" | "{" | "}"
                  | "|" | "+" | "*" | "?" | "^" | "$" ;

unicode_escape    = "\\x" hex_pair | "\\u" hex_quad | "\\U" hex_octa | "\\N{" unicode_name "}" ;
hex_pair          = hex_digit hex_digit ;
hex_quad          = hex_digit hex_digit hex_digit hex_digit ;
hex_octa          = hex_quad hex_quad ;
hex_digit         = "0".."9" | "a".."f" | "A".."F" ;

literal_char      = unicode_scalar - {"\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"} ;

name              = name_start { name_continue } ;
name_start        = unicode_letter | "_" ;
name_continue     = unicode_letter | unicode_digit | "_" ;

unicode_name      = unicode_letter { unicode_letter | unicode_digit | "_" | " " | "-" } ;

unicode_scalar    = any code point U+0000..U+10FFFF ;
unicode_letter    = code point with Unicode category Lu | Ll | Lt | Lm | Lo ;
unicode_digit     = code point with Unicode category Nd ;



"""



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
    





B = FABuilder[str]
S = Syntax.config(universe=CodeUniverse.unicode(), builtin=True)
# number            = digit { digit } ;
number = S.lex(number=B.oneof("0123456789").many(at_least=1)).map(lambda tok: int(tok.text)).named('number')

# dot               = "." ;
dot = S.lex(dot=B.lit(".")).named('"."')
or_ = S.lex(or_=B.lit("|")).named('"|"')
# leading_rsquare   = "]" ;
leading_rsquare   = S.lex(leading_rsquare=B.lit("]")).named('leading_rsquare')

whitespace = S.lex(whitespace=B.oneof([" ", "\t", "\n", "\r", "\f", "\v"])).named('whitespace')
question = S.lex(question=B.lit("?")).named('"?"')
star = S.lex(star=B.lit("*")).named('"*"')
plus = S.lex(plus=B.lit("+")).named('"+"')
lbrace = S.lex(lbrace=B.lit("{")).named('"{"')
rbrace = S.lex(rbrace=B.lit("}")).named('"}"')
comma = S.lex(comma=B.lit(",")).named('","')
lparen = S.lex(lparen=B.lit("(")).named('"("')
rparen = S.lex(rparen=B.lit(")")).named('")"')
lsquare = S.lex(lsquare=B.lit("[")).named('"["')
rsquare = S.lex(rsquare=B.lit("]")).named('"]"')
colon = S.lex(colon=B.lit(":")).named('":"')
less = S.lex(less=B.lit("<")).named('"<"')
greater = S.lex(greater=B.lit(">")).named('">"')
equal = S.lex(equal=B.lit("=")).named('"="')
bang = S.lex(bang=B.lit("!")).named('"!"')
caret = S.lex(caret=B.lit("^")).named('"^"')
dollar = S.lex(dollar=B.lit("$")).named('"$"')
backslash = S.lex(backslash=B.lit("\\")).named('"\\"')
minus = S.lex(minus=B.lit("-")).named('"-"')
# boundary_escape   = "\\A" | "\\Z" | "\\b" | "\\B" ;
boundary_escape = S.lex(boundary_escape=B.oneof(["\\A", "\\Z", "\\b", "\\B"])).named('boundary_escape')
escaped_x = S.lex(escaped_x=B.lit("\\x")).named('"\\x"')
escaped_u = S.lex(escaped_u=B.lit("\\u")).named('"\\u"')
escaped_U = S.lex(escaped_U=B.lit("\\U")).named('"\\U"')
escaped_N = S.lex(escaped_N=B.lit("\\N{")).named('"\\N{"')
escaped_p = S.lex(escaped_p=B.lit("\\p{")).named('"\\p{"')
escaped_P = S.lex(escaped_P=B.lit("\\P{")).named('"\\P{"')
underscore = S.lex(underscore=B.lit("_")).named('"_"')
space = S.lex(space=B.lit(" ")).named('" "')
hyphen = S.lex(hyphen=B.lit("-")).named('"-"')
# unicode_scalar    = any code point U+0000..U+10FFFF ;
unicode_scalar = S.lex(unicode_scalar=B.range("\u0000", "\U0010FFFF")).named('unicode_scalar')
# unicode_letter    = code point with Unicode category Lu | Ll | Lt | Lm | Lo ;
unicode_category = S.lex(unicode_category=B.oneof(["Lu", "Ll", "Lt", "Lm", "Lo", "L", "M", "N", "Nd", "Nl", "No", "P", "Pd", "Ps", "Pe", "S", "Sm", "Sc", "Z", "Zs", "C"])).named('unicode_category')
unicode_letter = S.lex(unicode_letter=B.unicode_category(["Lu", "Ll", "Lt", "Lm", "Lo"])).named('unicode_letter')
# unicode_digit     = code point with Unicode category Nd ;
unicode_digit = S.lex(unicode_digit=B.unicode_category(["Nd"])).named('unicode_digit')
# class_literal     = unicode_scalar - {"\\", "]"} ;
class_literal = S.lex(class_literal=B.range("\u0000", "\U0010FFFF") - B.oneof(["\\", "]"])).named('class_literal')
# literal_char      = unicode_scalar - {"\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"} ;
literal_char = S.lex(literal_char=B.range("\u0000", "\U0010FFFF") - B.oneof(["\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"])).map(lambda x: x.text).named('literal_char')

# hex_octa          = hex_quad hex_quad ;
hex_octa = S.lex(hex_octa=B.oneof("0123456789abcdefABCDEF").many(at_least=8, at_most=8)).map(lambda tok: tok.text).named('hex_octa')
# hex_quad          = hex_digit hex_digit hex_digit hex_digit ;
hex_quad = S.lex(hex_quad=B.oneof("0123456789abcdefABCDEF").many(at_least=4, at_most=4)).map(lambda tok: tok.text).named('hex_quad')
# hex_pair          = hex_digit hex_digit ;
hex_pair = S.lex(hex_pair=B.oneof("0123456789abcdefABCDEF").many(at_least=2, at_most=2)).map(lambda tok: tok.text).named('hex_pair')

# meta_char         = "\\" | "." | "[" | "]" | "(" | ")" | "{" | "}" | "|" | "+" | "*" | "?" | "^" | "$" ;
meta_char = S.lex(meta_char=B.oneof(["\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"])).named('meta_char')
# control_escape    = "\\t" | "\\n" | "\\r" | "\\f" | "\\v" ;
control_escape = S.lex(control_escape=B.oneof(["\\t", "\\n", "\\r", "\\f", "\\v"])).named('control_escape')

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

@dataclass(frozen=True)
class ShorthandAtom:
    kind: ShorthandKind

# shorthand         = "\\d" | "\\D" | "\\s" | "\\S" | "\\w" | "\\W" ;
shorthand = S.lex(shorthand=B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"])).map(lambda t: ShorthandKind.from_literal(t.text)).named('shorthand')

# category_name     = unicode_letter { unicode_letter } ;
category_name = unicode_category.many().map(lambda ts: tuple(t.text for t in ts)).named('category_name')
# unicode_category_escape   = "\p{" category_name "}" | "\P{" category_name "}" ;
unicode_category_escape = (
    (escaped_p.map(lambda _: False).mark('negated') + category_name.mark('categories') // rbrace) 
     |
    (escaped_P.map(lambda _: True).mark('negated') + category_name.mark('categories') // rbrace)
).named('unicode_category_escape')

# unicode_name      = unicode_letter { unicode_letter | unicode_digit | "_" | " " | "-" } ;
unicode_name = (unicode_letter + (unicode_letter | underscore | space | hyphen).many()).map(lambda t: ''.join([t[0].text] + [c.text for c in t[1]])).named('unicode_name')
# name_continue     = unicode_letter | unicode_digit | "_" ;
name_continue = unicode_letter | underscore
# name_start        = unicode_letter | "_" ;
name_start = unicode_letter | underscore
# name              = name_start { name_continue } ;
name = (name_start + name_continue.many()).map(lambda t: ''.join([t[0].text] + [c.text for c in t[1]])).named('name')
# unicode_escape    = "\\x" hex_pair | "\\u" hex_quad | "\\U" hex_octa | "\\N{" unicode_name "}" ;
unicode_escape = ((escaped_x >> hex_pair).map(lambda t: chr(int(t[0], 16))) | 
                  (escaped_u >> hex_quad).map(lambda t: chr(int(t[0], 16))) | 
                  (escaped_U >> hex_octa).map(lambda t: chr(int(t[0], 16))) | 
                  ((escaped_N >> unicode_name) // rbrace).map(lambda t: unicodedata.lookup(t[0]))).named('unicode_escape')
# escaped_metachar  = "\\" meta_char ;
escaped_metachar = (backslash >> meta_char).map(lambda t: t[0]).named('escaped_metachar')
# escaped_literal   = control_escape | unicode_escape | escaped_metachar ;
escaped_literal   = control_escape | unicode_escape | escaped_metachar 
# literal           = escaped_literal | literal_char ;
literal = escaped_literal | literal_char
# class_meta_char   = "-" | "]" | "\\" ;
class_meta_char = minus | rsquare | backslash 
# escaped_class_meta= "\\" class_meta_char ;
escaped_class_meta= (backslash >> class_meta_char).map(lambda t: t[0])


@dataclass(frozen=True)
class UnicodeCategoryAtom:
    categories: Tuple[str, ...]
    negated: bool = False   


# class_atom        = class_literal | shorthand | control_escape | unicode_escape | escaped_class_meta ;
class_atom = S.choice(class_literal,
                    shorthand.to(ShorthandAtom),
                    escaped_metachar,
                    control_escape,
                    unicode_escape,
                    unicode_category_escape.to(UnicodeCategoryAtom),
                    escaped_class_meta).map(lambda t: t.text if isinstance(t, Token) else t).named('class_atom')


@dataclass(frozen=True)
class CharRange:
    start: str
    end: str
@dataclass(frozen=True)
class CharClassAtom:
    items: Tuple[Union[str, CharRange], ...]
    negated: bool = False


# range             = class_atom "-" class_atom ;
range = (class_atom.mark('start') // minus + class_atom.mark('end')).to(CharRange).named('range')

# class_item = range | class_atom ;
class_item = range | class_atom

# class_class_items = leading_rsquare? class_item { class_item } ;
# leading_rsquare == ']' indicates that the first character in the class is a literal ']'
# if ~leading_rsquare is absent, t[0] is Nothing bool(Nothing) → False, we just take the class_item.many() == t[1]
# if ~leading_rsquare is present, t[0] is the leading_rsquare Token bool(Token) → True, we should include ']' in the class_item
# so we append ']' to the list of class_item value in this case
class_class_items = (~leading_rsquare + class_item.many()).map(lambda t: (t[1] + [']']) if t[0] else t[1]).named('class_class_items')
# char_class        = "[" [ "^" ] class_class_items "]" ;
char_class = (lsquare >> (~caret).map(bool).mark('negated') + class_class_items.mark('items') // rsquare).named('char_class')


class GroupKind(Enum):
    CAPTURE = auto()
    NON_CAPTURE = auto()
    LOOKAHEAD = auto()
    NEG_LOOKAHEAD = auto()
    LOOKBEHIND = auto()
    NEG_LOOKBEHIND = auto()
    FLAGS = auto()
    FLAGS_SCOPED = auto()

@dataclass(frozen=True)
class GroupAtom:
    kind: GroupKind
    pattern: Optional[Regex] = None
    name: Optional[str] = None
    inline_flags: Optional[Tuple[str, ...]] = None
    disabled_flags: Optional[Tuple[str, ...]] = None

# flag              = "a" | "i" | "L" | "m" | "s" | "u" | "x" ;
flag = S.lex(flag=B.oneof(["a", "i", "L", "m", "s", "u", "x"])).named('flag')
# flag_seq          = flag { flag } ;
flag_seq = flag.many().map(lambda ts: tuple(t.text for t in ts)).named('flag_seq')
# inline_flags      = flag_seq [ "-" flag_seq ] ;
inline_flags = flag_seq.mark('inline_flags') + (~(minus >> flag_seq)).map(lambda t: t[0] if t is not Nothing else None).mark('disabled_flags').named('inline_flags')


def _group_body() -> Syntax[Any, Any]:
    # Forward reference to regex since groups can contain full regex patterns with alternation
    # group = "(" regex ")"
    plain = lparen >> regex_syntax.mark('pattern') // rparen
    # group = "(?:" regex ")"
    noncapturing = (S.lex(_=B.lit("(?:")).named('"(?:"') >> regex_syntax.mark('pattern') // rparen)
    # group = "(?P<" name ">" regex ")"
    named = S.lex(gp_named=B.lit("(?P<")).named('"(?P<"') >> name.mark('name') // greater + regex_syntax.mark('pattern') // rparen
    # group = "(?=" regex ")"
    lookahead = S.lex(gp_lookahead=B.lit("(?=" )).named('"(?="') >> regex_syntax.mark('pattern') // rparen
    # group = "(?!" regex ")"
    negative_lookahead = S.lex(gp_negative_lookahead=B.lit("(?!")).named('"(?!"') >> regex_syntax.mark('pattern') // rparen
    # group = "(?<=" regex ")"
    lookbehind = S.lex(gp_lookbehind=B.lit("(?<=")).named('"(?<="') >> regex_syntax.mark('pattern') // rparen
    # group = "(?<!" regex ")"
    negative_lookbehind = S.lex(gp_negative_lookbehind=B.lit("(?<!" )).named('"(?<!"') >> regex_syntax.mark('pattern') // rparen
    # group = "(?" inline_flags ")"
    inline_flag_only = S.lex(gp_inline_flags=B.lit("(?")).named('"(?"') >> inline_flags // rparen
    # group = "(?" inline_flags ":" regex ")"
    inline_flag_with_colon = (S.lex(gp_inline_flags_colon=B.lit("(?")).named('"(?"')
                              >> inline_flags
                              // colon 
                              + regex_syntax.mark('pattern') 
                              // rparen)
    return S.choice(
                plain.to(lambda **t: GroupAtom(kind=GroupKind.CAPTURE, **t), id="plain").named('plain').debug(),
                noncapturing.to(lambda **t: GroupAtom(kind=GroupKind.NON_CAPTURE, **t), id="noncapturing").named('noncapturing').debug(),
                named.to(lambda **t: GroupAtom(kind=GroupKind.CAPTURE, **t), id="named").named('named').debug(),
                lookahead.to(lambda **t: GroupAtom(kind=GroupKind.LOOKAHEAD, **t), id="lookahead").named('lookahead').debug(),
                negative_lookahead.to(lambda **t: GroupAtom(kind=GroupKind.NEG_LOOKAHEAD, **t), id="negative_lookahead").named('negative_lookahead').debug(),
                lookbehind.to(lambda **t: GroupAtom(kind=GroupKind.LOOKBEHIND, **t), id="lookbehind").named('lookbehind').debug(),
                negative_lookbehind.to(lambda **t: GroupAtom(kind=GroupKind.NEG_LOOKBEHIND, **t), id="negative_lookbehind").named('negative_lookbehind').debug(),
                inline_flag_only.to(lambda **t: GroupAtom(kind=GroupKind.FLAGS, **t), id="inline_flag_only").named('inline_flag_only').debug(),
                inline_flag_with_colon.to(lambda **t: GroupAtom(kind=GroupKind.FLAGS_SCOPED, **t), id="inline_flag_with_colon").named('inline_flag_with_colon').debug(),
                sort = False
            )


group = S.lazy(_group_body).named('group').debug()

# anchor            = "^" | "$" | boundary_escape ;
# - ^ → LINE_START
# - $ → LINE_END
# - \A → ABSOLUTE_START
# - \Z → ABSOLUTE_END
# - \b → WORD_BOUNDARY
# - \B → NOT_WORD_BOUNDARY
anchor = (caret | 
          dollar | 
          boundary_escape).map(lambda t: AnchorKind.from_literal(t.text)).mark('kind').named('anchor')

@dataclass(frozen=True)
class Quantifier:
    minimum: int
    maximum: Optional[int]     # None → unbounded
    greedy: bool = True

# braced_quantifier = "{" number [ "," [ number ] ] "}" ;
# - {n} → minimum=n, maximum=n
# - {n,} → minimum=n, maximum=None
# - {n,m} → minimum=n, maximum=m
braced_quantifier = S.choice(
    (lbrace >> number // rbrace).map(lambda n: Quantifier(minimum=n[0], maximum=n[0])),
    (lbrace >> number // comma // rbrace).map(lambda t: Quantifier(minimum=t[0], maximum=None)),
    (lbrace >> number.mark('minimum') + (comma >> number.mark('maximum')) // rbrace).to(Quantifier)
)


# quantifier        = "?" | "*" | "+" | braced_quantifier [ "?" ] ;
# - ? → minimum=0, maximum=1
# - * → minimum=0, maximum=None
# - + → minimum=1, maximum=None
# - braced_quantifier followed by ? → same as braced_quantifier but greedy=False
quantifier = (S.choice(
    question.map(lambda _: Quantifier(minimum=0, maximum=1)),
    star.map(lambda _: Quantifier(minimum=0, maximum=None)),
    plus.map(lambda _: Quantifier(minimum=1, maximum=None)),
    braced_quantifier) + ~question).map(lambda t: replace(t[0], greedy=not t[1])).named('quantifier') 


@dataclass(frozen=True)
class LiteralAtom:
    text: str




@dataclass(frozen=True)
class AnchorAtom:
    kind: AnchorKind

@dataclass(frozen=True)
class DotAtom:
    pass


# atom              = literal | char_class | group | anchor | dot | shorthand ;
atom = S.choice(
        literal.mark('text').to(LiteralAtom).named('literal'),
        group,
        dot.to(DotAtom),
        anchor.to(AnchorAtom),
        shorthand.to(ShorthandAtom),
        unicode_category_escape.to(UnicodeCategoryAtom),
        char_class.to(CharClassAtom),
        ).named('atom').debug()


@dataclass(frozen=True)
class Piece:
    atom: Union[LiteralAtom,
                DotAtom,
                AnchorAtom,
                ShorthandAtom,
                UnicodeCategoryAtom,
                CharClassAtom,
                GroupAtom]
    quantifier: Optional[Quantifier] = None

# piece             = atom [ quantifier ] ;
piece = (atom.mark('atom') + (~quantifier).mark('quantifier')).to(Piece).named('piece')

@dataclass(frozen=True)
class Branch:
    pieces: Tuple[Piece, ...]

# branch            = piece { piece } ;
branch = piece.many().mark('pieces').to(Branch).named('branch')

@dataclass(frozen=True)
class Regex:
    branches: Tuple[Branch, ...]


# regex             = branch { "|" branch } ;
regex_syntax = branch.sep_by(or_).named('regex').mark('branches').to(Regex)


regex_parser = parser(syntax=regex_syntax, payload_kind='text')


def parse(data: str, *, raw:bool=False) -> Regex | Error | Any:
    from syncraft.parser import Runner
    runner: Runner[Any] = Runner()
    cursor = StreamCursor.from_data(data)
    for result, s in runner.run(regex_parser, state=None, cursor=cursor, once=True, cache=None):
        if s:
            if isinstance(result, AST):
                return result if raw else result.mapped 
            else:
                return result
        else:
            return result
    raise SyncraftError("Regex did not yield any results", offender=None, expect="at least one result")

def parse_regex(syntax: Syntax[Any, Any], 
                pattern: str, 
                *, 
                raw:bool=False) -> Any:
    result, s = parse_string(syntax, pattern, cache=None)
    if s:
        if isinstance(result, AST):
            return result if raw else result.mapped 
        else:
            return result
    else:
        return result


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
