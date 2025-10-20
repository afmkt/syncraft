from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any



from syncraft.ast import Nothing
from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder
from syncraft.lexer import Lexer
from syncraft.syntax import Syntax


r"""
regex             = branch { "|" branch } ;
branch            = piece { piece } ;
piece             = atom [ quantifier ] ;
atom              = literal | char_class | group | anchor | dot | shorthand ;
dot               = "." ;

quantifier        = "?" | "*" | "+" | braced_quantifier [ "?" ] ;
braced_quantifier = "{" number [ "," [ number ] ] "}" ;
number            = digit { digit } ;
digit             = "0".."9" ;

anchor            = "^" | "$" | boundary_escape ;
boundary_escape   = "\\A" | "\\Z" | "\\b" | "\\B" ;

group             = "(" branch ")"
                  | "(?:" branch ")"
                  | "(?P<" name ">" branch ")"
                  | "(?=" branch ")"
                  | "(?!" branch ")"
                  | "(?<=" branch ")"
                  | "(?<!" branch ")"
                  | "(?" inline_flags ")"
                  | "(?" inline_flags ":" branch ")"
                  ;
inline_flags      = flag_seq [ "-" flag_seq ] ;
flag_seq          = flag { flag } ;
flag              = "a" | "i" | "L" | "m" | "s" | "u" | "x" ;

char_class        = "[" [ "^" ] class_item { class_item } "]" ;
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
class_literal     = unicode_scalar - {"\\", "-", "]"} ;

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

class ShorthandKind(Enum):
    DIGIT = auto()
    NOT_DIGIT = auto()
    WORD = auto()
    NOT_WORD = auto()
    SPACE = auto()
    NOT_SPACE = auto()

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
class Quantifier:
    minimum: int
    maximum: Optional[int]     # None → unbounded
    greedy: bool = True

@dataclass(frozen=True)
class Piece:
    atom: "Atom"
    quantifier: Optional[Quantifier] = None

@dataclass(frozen=True)
class Branch:
    pieces: Tuple[Piece, ...]

@dataclass(frozen=True)
class Regex:
    branches: Tuple[Branch, ...]

@dataclass(frozen=True)
class LiteralAtom:
    text: str

@dataclass(frozen=True)
class DotAtom:
    pass

@dataclass(frozen=True)
class AnchorAtom:
    kind: AnchorKind

@dataclass(frozen=True)
class ShorthandAtom:
    kind: ShorthandKind

@dataclass(frozen=True)
class UnicodeCategoryAtom:
    categories: Tuple[str, ...]

@dataclass(frozen=True)
class CharRange:
    start: str
    end: str

@dataclass(frozen=True)
class CharClassAtom:
    items: Tuple[Union[str, CharRange], ...]
    negated: bool = False

@dataclass(frozen=True)
class GroupAtom:
    kind: GroupKind
    pattern: Regex
    name: Optional[str] = None
    inline_flags: Optional[Tuple[str, ...]] = None
    disabled_flags: Optional[Tuple[str, ...]] = None

Atom = Union[
    LiteralAtom,
    DotAtom,
    AnchorAtom,
    ShorthandAtom,
    UnicodeCategoryAtom,
    CharClassAtom,
    GroupAtom,
]



B = FABuilder[str]
S = Syntax.config(lexer_class = Lexer.bind(CodeUniverse.unicode()))
number = S.lex(number=B.oneof("0123456789").many()).map(lambda tok: int(tok.text))
flag = S.lex(flag=B.oneof(["a", "i", "L", "m", "s", "u", "x"]))
dot = S.lex(dot=B.lit("."))
or_ = S.lex(or_=B.lit("|"))
whitespace = S.lex(whitespace=B.oneof([" ", "\t", "\n", "\r", "\f", "\v"]))
question = S.lex(question=B.lit("?"))
star = S.lex(star=B.lit("*"))
plus = S.lex(plus=B.lit("+"))
lbrace = S.lex(lbrace=B.lit("{"))
rbrace = S.lex(rbrace=B.lit("}"))
comma = S.lex(comma=B.lit(","))
lparen = S.lex(lparen=B.lit("("))
rparen = S.lex(rparen=B.lit(")"))
lsquare = S.lex(lsquare=B.lit("["))
rsquare = S.lex(rsquare=B.lit("]"))
colon = S.lex(colon=B.lit(":"))
less = S.lex(less=B.lit("<"))
greater = S.lex(greater=B.lit(">"))
equal = S.lex(equal=B.lit("="))
bang = S.lex(bang=B.lit("!"))
caret = S.lex(caret=B.lit("^"))
dollar = S.lex(dollar=B.lit("$"))
backslash = S.lex(backslash=B.lit("\\"))
minus = S.lex(minus=B.lit("-"))
boundary_escape = S.lex(boundary_escape=B.oneof(["\\A", "\\Z", "\\b", "\\B"]))
escaped_x = S.lex(escaped_x=B.lit("\\x")) 
escaped_u = S.lex(escaped_u=B.lit("\\u")) 
escaped_U = S.lex(escaped_U=B.lit("\\U")) 
escaped_N = S.lex(escaped_N=B.lit("\\N{"))
underscore = S.lex(underscore=B.lit("_"))
space = S.lex(space=B.lit(" "))
hyphen = S.lex(hyphen=B.lit("-"))
unicode_scalar = S.lex(unicode_scalar=B.range("\u0000", "\U0010FFFF"))
unicode_letter = S.lex(unicode_letter=B.unicode_category(["Lu", "Ll", "Lt", "Lm", "Lo"]))
unicode_digit = S.lex(unicode_digit=B.unicode_category(["Nd"]))

unicode_name = unicode_letter + (unicode_letter | unicode_digit | underscore | space | hyphen).many()
name_continue = unicode_letter | unicode_digit | underscore
name_start = unicode_letter | underscore
name = name_start + name_continue.many()
class_literal = S.lex(class_literal=B.range("\u0000", "\U0010FFFF") - B.oneof(["\\", "-", "]"]))
literal_char = S.lex(literal_char=B.range("\u0000", "\U0010FFFF") - B.oneof(["\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"]))
hex_octa = S.lex(hex_octa=B.oneof("0123456789abcdefABCDEF").many(at_least=8, at_most=8)).map(lambda tok: tok.text)
hex_quad = S.lex(hex_quad=B.oneof("0123456789abcdefABCDEF").many(at_least=4, at_most=4)).map(lambda tok: tok.text)
hex_pair = S.lex(hex_pair=B.oneof("0123456789abcdefABCDEF").many(at_least=2, at_most=2)).map(lambda tok: tok.text)
unicode_escape = (escaped_x >> hex_pair) | (escaped_u >> hex_quad) | (escaped_U >> hex_octa) | (escaped_N >> unicode_name // rbrace)
meta_char = S.lex(meta_char=B.oneof(["\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"]))
escaped_metachar = backslash >> meta_char 
control_escape = S.lex(control_escape=B.oneof(["\\t", "\\n", "\\r", "\\f", "\\v"]))
escaped_literal   = control_escape | unicode_escape | escaped_metachar 
literal = escaped_literal | literal_char
shorthand = S.lex(shorthand=B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"]))
class_meta_char = minus | rsquare | backslash 
escaped_class_meta= backslash >> class_meta_char 
class_atom = class_literal | shorthand | control_escape | unicode_escape | escaped_class_meta 

range = (class_atom.mark('start') // minus >> class_atom.mark('end')).to(CharRange)
class_item = class_atom.map(lambda t: t.mapped.text) | range
char_class = lsquare >> ~caret.map(lambda t: t.mapped is not Nothing()).mark('negated') + class_item.many().mark('items') // rsquare
flag_seq = flag.many()
inline_flags = flag_seq + ~(minus + flag_seq)


def _group_body() -> Syntax[Any, Any]:
    plain = lparen >> branch // rparen
    noncapturing = S.lex(_=B.lit("(?:" )) >> branch // rparen
    named = S.lex(_=B.lit("(?P<")) >> name // greater >> branch // rparen
    lookahead = S.lex(_=B.lit("(?=" )) >> branch // rparen
    negative_lookahead = S.lex(_=B.lit("(?!" )) >> branch // rparen
    lookbehind = S.lex(_=B.lit("(?<=" )) >> branch // rparen
    negative_lookbehind = S.lex(_=B.lit("(?<!" )) >> branch // rparen
    inline_flag_only = S.lex(_=B.lit("(?")) >> inline_flags // rparen
    inline_flag_with_colon = S.lex(_=B.lit("(?")) >> inline_flags + colon >> branch // rparen
    return plain | noncapturing | named | lookahead | negative_lookahead | lookbehind | negative_lookbehind | inline_flag_only | inline_flag_with_colon


group = S.lazy(_group_body)

anchor = (caret.map(lambda _: AnchorKind.LINE_START) | 
          dollar.map(lambda _: AnchorKind.LINE_END) | 
          boundary_escape.map(lambda t: {"\\A": AnchorKind.ABSOLUTE_START,
                                        "\\Z": AnchorKind.ABSOLUTE_END,
                                        "\\b": AnchorKind.WORD_BOUNDARY,
                                        "\\B": AnchorKind.NOT_WORD_BOUNDARY}[t.mapped.text])).mark('kind')


exact = lbrace >> number // rbrace
open_range = lbrace >> number // comma // rbrace
closed_range = lbrace >> number.mark('minimum') + (comma >> number.mark('maximum')) // rbrace
braced_quantifier = (exact.map(lambda n: Quantifier(minimum=n.mapped[0], maximum=n.mapped[0])) | 
                     open_range.map(lambda t: Quantifier(minimum=t.mapped[0], maximum=None)) | 
                     closed_range.to(Quantifier))

quantifier = (question.map(lambda _: Quantifier(minimum=0, maximum=1)) | 
              star.map(lambda _: Quantifier(minimum=0, maximum=None)) | 
              plus.map(lambda _: Quantifier(minimum=1, maximum=None)) | 
              (braced_quantifier + ~question).map(lambda t: replace(t.mapped[0], greedy=t.mapped[1] is not Nothing())) )
atom = (literal.map(lambda x: x.mapped.text).mark('text').to(LiteralAtom) | 
        char_class.to(CharClassAtom) | 
        group.to(GroupAtom) | 
        anchor.to(AnchorAtom) | 
        dot.map(lambda _: DotAtom()) | 
        shorthand.map(lambda t: ShorthandAtom(kind={"\\d": ShorthandKind.DIGIT,
                                               "\\D": ShorthandKind.NOT_DIGIT,
                                               "\\w": ShorthandKind.WORD,
                                               "\\W": ShorthandKind.NOT_WORD,
                                               "\\s": ShorthandKind.SPACE,
                                               "\\S": ShorthandKind.NOT_SPACE}[t.mapped.text])) )
piece = atom + ~quantifier
branch = piece.many()
regex = branch.sep_by(or_)


