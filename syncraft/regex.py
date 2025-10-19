from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence as TypingSequence, Tuple

from syncraft.ast import Choice, Lazy, Many, Nothing, SyncraftError, Then, ThenKind, Token
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


