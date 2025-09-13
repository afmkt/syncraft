from __future__ import annotations

"""Regex subset grammar documentation placeholder."""



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

"""
LITERAL      = any character except: "(", ")", "[", "]", "{", "}", "*", "+", "?", "|", ".", "^", "$", "\", ",", or whitespace ;
ESCAPED      = "\" any character ;
NUMBER       = digit { digit } ;
DOT          = "." ;
STAR         = "*" ;
PLUS         = "+" ;
QUESTION     = "?" ;
PIPE         = "|" ;
LPAREN       = "(" ;
RPAREN       = ")" ;
LBRACKET     = "[" ;
RBRACKET     = "]" ;
LBRACE       = "{" ;
RBRACE       = "}" ;
CARET        = "^" ;
DOLLAR       = "$" ;
COMMA        = "," ;
DASH         = "-" ;
WHITESPACE   = " " | "\t" | "\n" | "\r" ;
"""


"""
regex        = alt ;

alt          = concat { PIPE concat } ;

concat       = repeat { repeat } ;

repeat       = atom [ quantifier ] ;

quantifier   = STAR
             | PLUS
             | QUESTION
             | LBRACE NUMBER [ COMMA [ NUMBER ] ] RBRACE ;

atom         = literal
             | DOT
             | char_class
             | LPAREN regex RPAREN ;

char_class   = LBRACKET [ CARET ] class_items RBRACKET ;

class_items  = class_item { class_item } ;

class_item   = literal
             | literal DASH literal ;

literal      = ESCAPED
             | LITERAL ;
"""