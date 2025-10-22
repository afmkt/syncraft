from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Optional, Tuple, Union, Any



from syncraft.charset import CodeUniverse
from syncraft.fa import FABuilder
from syncraft.lexer import Lexer
from syncraft.syntax import Syntax


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





B = FABuilder[str]
S = Syntax.config(lexer_class = Lexer.bind(CodeUniverse.unicode()))
# number            = digit { digit } ;
number = S.lex(number=B.oneof("0123456789").many(at_least=1)).map(lambda tok: int(tok.text))
# flag              = "a" | "i" | "L" | "m" | "s" | "u" | "x" ;
flag = S.lex(flag=B.oneof(["a", "i", "L", "m", "s", "u", "x"]))
# dot               = "." ;
dot = S.lex(dot=B.lit("."))
or_ = S.lex(or_=B.lit("|"))
# leading_rsquare   = "]" ;
leading_rsquare   = S.lex(leading_rsquare=B.lit("]")) 

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
# boundary_escape   = "\\A" | "\\Z" | "\\b" | "\\B" ;
boundary_escape = S.lex(boundary_escape=B.oneof(["\\A", "\\Z", "\\b", "\\B"]))
escaped_x = S.lex(escaped_x=B.lit("\\x")) 
escaped_u = S.lex(escaped_u=B.lit("\\u")) 
escaped_U = S.lex(escaped_U=B.lit("\\U")) 
escaped_N = S.lex(escaped_N=B.lit("\\N{"))
escaped_p = S.lex(escaped_p=B.lit("\\p{"))
escaped_P = S.lex(escaped_P=B.lit("\\P{"))
underscore = S.lex(underscore=B.lit("_"))
space = S.lex(space=B.lit(" "))
hyphen = S.lex(hyphen=B.lit("-"))
# unicode_scalar    = any code point U+0000..U+10FFFF ;
unicode_scalar = S.lex(unicode_scalar=B.range("\u0000", "\U0010FFFF"))
# unicode_letter    = code point with Unicode category Lu | Ll | Lt | Lm | Lo ;
unicode_letter = S.lex(unicode_letter=B.unicode_category(["Lu", "Ll", "Lt", "Lm", "Lo"]))
# unicode_digit     = code point with Unicode category Nd ;
unicode_digit = S.lex(unicode_digit=B.unicode_category(["Nd"]))
# class_literal     = unicode_scalar - {"\\", "]"} ;
class_literal = S.lex(class_literal=B.range("\u0000", "\U0010FFFF") - B.oneof(["\\", "]"]))
# literal_char      = unicode_scalar - {"\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"} ;
literal_char = S.lex(literal_char=B.range("\u0000", "\U0010FFFF") - B.oneof(["\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"]))

# hex_octa          = hex_quad hex_quad ;
hex_octa = S.lex(hex_octa=B.oneof("0123456789abcdefABCDEF").many(at_least=8, at_most=8)).map(lambda tok: tok.text)
# hex_quad          = hex_digit hex_digit hex_digit hex_digit ;
hex_quad = S.lex(hex_quad=B.oneof("0123456789abcdefABCDEF").many(at_least=4, at_most=4)).map(lambda tok: tok.text)
# hex_pair          = hex_digit hex_digit ;
hex_pair = S.lex(hex_pair=B.oneof("0123456789abcdefABCDEF").many(at_least=2, at_most=2)).map(lambda tok: tok.text)

# meta_char         = "\\" | "." | "[" | "]" | "(" | ")" | "{" | "}" | "|" | "+" | "*" | "?" | "^" | "$" ;
meta_char = S.lex(meta_char=B.oneof(["\\", ".", "[", "]", "(", ")", "{", "}", "|", "+", "*", "?", "^", "$"]))
# control_escape    = "\\t" | "\\n" | "\\r" | "\\f" | "\\v" ;
control_escape = S.lex(control_escape=B.oneof(["\\t", "\\n", "\\r", "\\f", "\\v"]))
# shorthand         = "\\d" | "\\D" | "\\s" | "\\S" | "\\w" | "\\W" ;
shorthand = S.lex(shorthand=B.oneof(["\\d", "\\D", "\\s", "\\S", "\\w", "\\W"]))

# category_name     = unicode_letter { unicode_letter } ;
category_name = unicode_letter + unicode_letter.many()
# unicode_category_escape   = "\p{" category_name "}" | "\P{" category_name "}" ;
unicode_category_escape = (
    (escaped_p.map(lambda _: False).mark('negated') + category_name.mark('categories') // rbrace) |
    (escaped_P.map(lambda _: True).mark('negated') + category_name.mark('categories') // rbrace)
)

# unicode_name      = unicode_letter { unicode_letter | unicode_digit | "_" | " " | "-" } ;
unicode_name = unicode_letter + (unicode_letter | unicode_digit | underscore | space | hyphen).many()
# name_continue     = unicode_letter | unicode_digit | "_" ;
name_continue = unicode_letter | unicode_digit | underscore
# name_start        = unicode_letter | "_" ;
name_start = unicode_letter | underscore
# name              = name_start { name_continue } ;
name = name_start + name_continue.many()
# unicode_escape    = "\\x" hex_pair | "\\u" hex_quad | "\\U" hex_octa | "\\N{" unicode_name "}" ;
unicode_escape = ((escaped_x + hex_pair).mark('escaped_x') | 
                  (escaped_u + hex_quad).mark('escaped_u') | 
                  (escaped_U + hex_octa).mark('escaped_U') | 
                  (escaped_N + unicode_name).mark('escaped_N') // rbrace)
# escaped_metachar  = "\\" meta_char ;
escaped_metachar = backslash >> meta_char 
# escaped_literal   = control_escape | unicode_escape | escaped_metachar ;
escaped_literal   = control_escape | unicode_escape | escaped_metachar 
# literal           = escaped_literal | literal_char ;
literal = escaped_literal | literal_char
# class_meta_char   = "-" | "]" | "\\" ;
class_meta_char = minus | rsquare | backslash 
# escaped_class_meta= "\\" class_meta_char ;
escaped_class_meta= backslash >> class_meta_char 


@dataclass(frozen=True)
class UnicodeCategoryAtom:
    categories: Tuple[str, ...]
    negated: bool = False   


# class_atom        = class_literal | shorthand | control_escape | unicode_escape | escaped_class_meta ;
class_atom = (class_literal | 
              shorthand | 
              control_escape | 
              unicode_escape | 
              unicode_category_escape.to(UnicodeCategoryAtom)  |
              escaped_class_meta).map(lambda t: t.mapped.text)


@dataclass(frozen=True)
class CharRange:
    start: str
    end: str
@dataclass(frozen=True)
class CharClassAtom:
    items: Tuple[Union[str, CharRange], ...]
    negated: bool = False


# range             = class_atom "-" class_atom ;
range = (class_atom.mark('start') // minus >> class_atom.mark('end')).to(CharRange)

# class_item = range | class_atom ;
class_item = range | class_atom

# class_class_items = leading_rsquare? class_item { class_item } ;
class_class_items = ~leading_rsquare + class_item.many(at_least=1)
# char_class        = "[" [ "^" ] class_class_items "]" ;
char_class = lsquare >> (~caret).map(bool).mark('negated') + class_class_items.mark('items') // rsquare


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


# flag_seq          = flag { flag } ;
flag_seq = flag.many(at_least=1)
# inline_flags      = flag_seq [ "-" flag_seq ] ;
inline_flags = flag_seq.mark('inline_flags') + ~(minus >> flag_seq.mark('disabled_flags'))


def _group_body() -> Syntax[Any, Any]:
    # group = "(" branch ")"
    plain = lparen >> branch.mark('pattern') // rparen
    # group = "(?:" branch ")"
    noncapturing = S.lex(_=B.lit("(?:" )) >> branch.mark('pattern') // rparen
    # group = "(?P<" name ">" branch ")"
    named = S.lex(_=B.lit("(?P<")) >> name.mark('name') // greater >> branch.mark('pattern') // rparen
    # group = "(?=" branch ")"
    lookahead = S.lex(_=B.lit("(?=" )) >> branch.mark('pattern') // rparen
    # group = "(?!" branch ")"
    negative_lookahead = S.lex(_=B.lit("(?!" )) >> branch.mark('pattern') // rparen
    # group = "(?<=" branch ")"
    lookbehind = S.lex(_=B.lit("(?<=" )) >> branch.mark('pattern') // rparen
    # group = "(?<!" branch ")"
    negative_lookbehind = S.lex(_=B.lit("(?<!" )) >> branch.mark('pattern') // rparen
    # group = "(?" inline_flags ")"
    inline_flag_only = S.lex(_=B.lit("(?")) >> inline_flags // rparen
    # group = "(?" inline_flags ":" branch ")"
    inline_flag_with_colon = (S.lex(_=B.lit("(?")) 
                              >> inline_flags
                              + colon 
                              + branch.mark('pattern') 
                              // rparen)
    return (plain.to(lambda **t: GroupAtom(kind=GroupKind.CAPTURE, **t)) | 
            noncapturing.to(lambda **t: GroupAtom(kind=GroupKind.NON_CAPTURE, **t)) | 
            named.to(lambda **t: GroupAtom(kind=GroupKind.CAPTURE, **t)) | 
            lookahead.to(lambda **t: GroupAtom(kind=GroupKind.LOOKAHEAD, **t)) | 
            negative_lookahead.to(lambda **t: GroupAtom(kind=GroupKind.NEG_LOOKAHEAD, **t)) | 
            lookbehind.to(lambda **t: GroupAtom(kind=GroupKind.LOOKBEHIND, **t)) | 
            negative_lookbehind.to(lambda **t: GroupAtom(kind=GroupKind.NEG_LOOKBEHIND, **t)) | 
            inline_flag_only.to(lambda **t: GroupAtom(kind=GroupKind.FLAGS, **t)) | 
            inline_flag_with_colon.to(lambda **t: GroupAtom(kind=GroupKind.FLAGS_SCOPED, **t)))


group = S.lazy(_group_body)

# anchor            = "^" | "$" | boundary_escape ;
# - ^ → LINE_START
# - $ → LINE_END
# - \A → ABSOLUTE_START
# - \Z → ABSOLUTE_END
# - \b → WORD_BOUNDARY
# - \B → NOT_WORD_BOUNDARY
anchor = (caret | 
          dollar | 
          boundary_escape).map(lambda t: AnchorKind.from_literal(t.mapped.text)).mark('kind')

@dataclass(frozen=True)
class Quantifier:
    minimum: int
    maximum: Optional[int]     # None → unbounded
    greedy: bool = True

# braced_quantifier = "{" number [ "," [ number ] ] "}" ;
# - {n} → minimum=n, maximum=n
# - {n,} → minimum=n, maximum=None
# - {n,m} → minimum=n, maximum=m
braced_quantifier = ((lbrace >> number // rbrace).map(lambda n: Quantifier(minimum=n.mapped[0], maximum=n.mapped[0])) | 
                     (lbrace >> number // comma // rbrace).map(lambda t: Quantifier(minimum=t.mapped[0], maximum=None)) | 
                     (lbrace >> number.mark('minimum') + (comma >> number.mark('maximum')) // rbrace).to(Quantifier))


# quantifier        = "?" | "*" | "+" | braced_quantifier [ "?" ] ;
# - ? → minimum=0, maximum=1
# - * → minimum=0, maximum=None
# - + → minimum=1, maximum=None
# - braced_quantifier followed by ? → same as braced_quantifier but greedy=False
quantifier = (question.map(lambda _: Quantifier(minimum=0, maximum=1)) | 
              star.map(lambda _: Quantifier(minimum=0, maximum=None)) | 
              plus.map(lambda _: Quantifier(minimum=1, maximum=None)) | 
              (braced_quantifier + ~question).map(lambda t: replace(t.mapped[0], greedy=bool(t.mapped[1]))) )


@dataclass(frozen=True)
class LiteralAtom:
    text: str


@dataclass(frozen=True)
class ShorthandAtom:
    kind: ShorthandKind


@dataclass(frozen=True)
class AnchorAtom:
    kind: AnchorKind

@dataclass(frozen=True)
class DotAtom:
    pass


# atom              = literal | char_class | group | anchor | dot | shorthand ;
atom = (literal.map(lambda x: x.mapped.text).mark('text').to(LiteralAtom) | 
        char_class.to(CharClassAtom) | 
        group.to(GroupAtom) | 
        anchor.to(AnchorAtom) | 
        dot.to(DotAtom) | 
        unicode_category_escape.to(UnicodeCategoryAtom) |
        shorthand.map(lambda t: ShorthandKind.from_literal(t.mapped.text)).mark('kind').to(ShorthandAtom) )


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
piece = (atom.mark('atom') + (~quantifier).mark('quantifier')).to(Piece)

@dataclass(frozen=True)
class Branch:
    pieces: Tuple[Piece, ...]

# branch            = piece { piece } ;
branch = piece.many().mark('pieces').to(Branch)

@dataclass(frozen=True)
class Regex:
    branches: Tuple[Branch, ...]


# regex             = branch { "|" branch } ;
regex = branch.sep_by(or_).mark('branches').to(Regex)



def parse_regex(syntax: Syntax[Any, Any], pattern: str) -> Any:
    from syncraft.parser import parse_string
    result, s = parse_string(syntax, pattern)
    if s:
        from rich import print
        print(result)
        return result.mapped
    else:
        return result


