"""
Syncraft EBNF support.

This module supports a compact EBNF dialect and provides:
- Parsing EBNF text to `Grammar` / `Rule` / `EBNFExpr` AST.
- Printing AST back to canonical EBNF text.
- Converting between EBNF AST and Syncraft `Syntax` trees.

Supported grammar (in EBNF):

    grammar      = rule { rule } ;
    rule         = ident assign expr ";" ;
    assign       = "=" | "::=" ;

    expr         = seq { "|" seq } ;
    seq          = { factor } ;

    factor       = primary [ suffix ] ;
    suffix       = "?"
                 | "*"
                 | "+"
                 | "{" int "}"
                 | "{" int "," [ int ] "}" ;

    primary      = ident
                 | string
                 | "(" expr ")"
                 | "[" expr "]"
                 | "{" expr "}" ;

    ident        = letter_or_underscore { letter_or_digit_or_underscore } ;
    int          = digit { digit } ;
    string       = single_quoted_string | double_quoted_string ;
    single_quoted_string = "'" { escaped_char | non_quote_char } "'" ;
    double_quoted_string = '"' { escaped_char | non_dquote_char } '"' ;
    escaped_char = "\\" any_char ;

"""

from __future__ import annotations

from typing import Dict, Tuple, Any
from syncraft.grammar import Grammar, lazy, rule, grammar
from syncraft.syntax import Syntax, SyntaxSpec, LazySpec
from syncraft.ast import SyncraftError, Nothing

S = Syntax.set(builtin=True)

@grammar
class EBNF(Grammar):
    str_ = S.re(r"'([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\"")
    ident = S.re(r"[A-Za-z_][A-Za-z0-9_]*")

    @lazy(S)
    def grouped(_):
        return S.rp(r"\[\s*(?&expr)\s*\]|\(\s*(?&expr)\s*\)|\{\s*(?&expr)\s*\}", expr=EBNF.expr)

    primary = S.alt(ident, str_, grouped)
    suffix = S.rp(r"(\?|\*|\+|\{(?&int)(,(?&int)?)?\})", int=S.re(r"\d+"))
    factor = primary + ~suffix
        
    seq = S.rp(r"(?:(?&factor)\s*)*", factor=factor)
    
    expr = S.rp(r"(?&seq)(?:\|\s*(?&seq))*", seq=seq)

    erule = S.rp(
        r"\s*(?&ident)\s*(?:=|::=)\s*(?&expr)\s*;\s*",
        ident=ident,
        expr=expr,
    )

    grammar = rule(erule.many(at_least=1), is_root=True)




@grammar
class ToSyntax(Grammar):
    """Convert EBNF AST to Syncraft Syntax objects."""

    pass
