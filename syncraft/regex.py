from __future__ import annotations
"""Regex subset grammar documentation placeholder."""
# (Former sqlglot TokenType import removed; regex parser will become backend-agnostic.)



"""BNF (planned) for the regex subset (currently documentation only):
regex        ::= alt
alt          ::= concat ('|' concat)*
concat       ::= repeat+
repeat       ::= atom quantifier?
quantifier   ::= '*' | '+' | '?' | '{' number (',' number?)? '}'
atom         ::= literal | '.' | char_class | '(' regex ')'
char_class   ::= '[' '^'? class_items ']'
class_items  ::= class_item+
class_item   ::= literal | literal '-' literal
literal      ::= escaped | non_special
escaped      ::= '\\' any_char
non_special  ::= any_char_except("()[]{}*+?|.^$\\")
number       ::= [0-9]+
"""
