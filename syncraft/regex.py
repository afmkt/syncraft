from __future__ import annotations
from typing import Any
from syncraft.syntax import Syntax, lazy, choice
import syncraft.parser as dsl
from syncraft.utils import rich_error, rich_debug, rich_parser
from sqlglot import TokenType


regex        ::= alt

alt          ::= concat ('|' concat)*

concat       ::= repeat+

repeat       ::= atom quantifier?

quantifier   ::= '*' | '+' | '?' | '{' number (',' number?)? '}'

atom         ::= literal
               | '.'
               | char_class
               | '(' regex ')'

char_class   ::= '[' '^'? class_items ']'
class_items  ::= class_item+
class_item   ::= literal
               | literal '-' literal

literal      ::= escaped | non_special

escaped      ::= '\' any_char
non_special  ::= any_char_except("()[]{}*+?|.^$\")
number       ::= [0-9]+
