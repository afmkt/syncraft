# -- EBNF-of-EBNF --
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
# -- EBNF-of-EBNF-end --

# -- syncraft-grammar-for-EBNF --
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
from syncraft.grammar import Grammar, lazy, rule, grammar
from syncraft.syntax import Syntax
from syncraft.ast import Nothing

S = Syntax.set(builtin=True)



@grammar
class EBNF0(Grammar):
    sqstr = S.re(r"'([^'\\]|\\.)*'")
    dqstr = S.re(r'"([^"\\]|\\.)*"')
    str_ = S.alt(sqstr, dqstr)
    ident = S.re(r"[A-Za-z_][A-Za-z0-9_]*")

    @lazy(S)
    def grouped(_):
        return S.rp(r"\[\s*(?&expr)\s*\]|\(\s*(?&expr)\s*\)|\{\s*(?&expr)\s*\}", expr=EBNF0.expr)

    primary = S.alt(ident, str_, grouped)
    suffix = S.rp(r"(\?|\*|\+|\{(?&int)(,(?&int)?)?\})", int=S.re(r"\d+"))
    factor = primary + ~suffix
        
    seq = S.rp(r"(\s*(?&factor)\s*)*", factor=factor)
    
    expr = seq.sep_by(S.re(r"\s*\|\s*"), at_least=1)

    erule = S.rp(
        r"\s*(?&ident)\s*(?:=|::=)\s*(?&expr)\s*;\s*",
        ident=ident,
        expr=expr,
    )

    grammar = rule(erule.many(at_least=1), is_root=True)


# -- syncraft-grammar-for-EBNF-end --



# -- dataclass-for-EBNF --
@dataclass(frozen=True)
class EBNFExpr:
    pass

@dataclass(frozen=True)
class Ref(EBNFExpr):
    name: str                    # rule reference: ident

@dataclass(frozen=True)
class Lit(EBNFExpr):
    value: str                   # decoded string literal value

@dataclass(frozen=True)
class Seq(EBNFExpr):
    items: Tuple[EBNFExpr, ...]  # empty tuple => epsilon
    
@dataclass(frozen=True)
class Alt(EBNFExpr):
    options: Tuple[EBNFExpr, ...]  # len >= 2 ideally

@dataclass(frozen=True)
class Repeat(EBNFExpr):
    expr: EBNFExpr
    minimum: int                 # 0/1/...
    maximum: Optional[int]       # None => unbounded

@dataclass(frozen=True)
class RuleDef:
    name: str
    expr: EBNFExpr

@dataclass(frozen=True)
class GrammarDef:
    rules: Tuple[RuleDef, ...]


# -- dataclass-for-EBNF-end --

# -- data-transformation-for-EBNF --

def _decode_literal(value: str) -> str:
    inner = value[1:-1]
    chars: list[str] = []
    index = 0
    while index < len(inner):
        ch = inner[index]
        if ch == "\\" and index + 1 < len(inner):
            chars.append(inner[index + 1])
            index += 2
            continue
        chars.append(ch)
        index += 1
    return "".join(chars)


def _encode_sq_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _encode_dq_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'

@grammar
class EBNF(Grammar):
    sqstr = S.re(r"'([^'\\]|\\.)*'").bimap(_decode_literal, _encode_sq_literal)
    dqstr = S.re(r'"([^"\\]|\\.)*"').bimap(_decode_literal, _encode_dq_literal)
    str_ = (sqstr | dqstr).to(lambda env: Lit(env.X))
    ident = S.re(r"[A-Za-z_][A-Za-z0-9_]*")

    @lazy(S)
    def grouped(_):
        optional = S.rp(r"\[\s*(?&expr)\s*\]", 
                        expr=EBNF.expr).to(lambda env: Repeat(env.expr, 0, 1))
        group = S.rp(r"\(\s*(?&expr)\s*\)", 
                     expr=EBNF.expr)

        repeat = S.rp(r"\{\s*(?&expr)\s*\}", 
                      expr=EBNF.expr).to(lambda env: Repeat(env.expr, 0, None))
        return optional | group | repeat

    ref = ident.to(lambda env: Ref(env.X))

    primary = ref | str_ | grouped
    
    suffix = S.rp(r"(\?|\*|\+|\{(?&int)(,(?&int)?)?\})", int=S.re(r"\d+")).case(
        (lambda _: '*', lambda _: (0, None)),
        (lambda _: '?', lambda _: (0, 1)),
        (lambda _: '+', lambda _: (1, None)),
        (lambda env: (env.Min, ), lambda env: (env.Min, None)),
        (lambda env: (env.Min, env.Max), lambda env: (env.Min, env.Max))
    )
    factor = (primary + ~suffix).case(( lambda env: (env.primary, Nothing), 
                                        lambda env: env.primary),
                                      ( lambda env: (env.primary, (env.Min, env.Max)), 
                                        lambda env: Repeat(env.primary, env.Min, env.Max)))


    seq = S.rp(r"(\s*(?&factor)\s*)*", factor=factor).to(lambda env: Seq(env.X))
    
    expr = seq.sep_by(S.re(r"\s*\|\s*"), at_least=1).to(lambda env: Alt(env.X))

    erule = S.rp(
        r"\s*(?&ident)\s*(?:=|::=)\s*(?&expr)\s*;\s*",
        ident=ident,
        expr=expr,
    ).to(lambda env: (env.ident, env.expr),
         lambda env: RuleDef(env.ident, env.expr))

    grammar = rule(erule.many(at_least=1).to(lambda env: GrammarDef(env.X)), 
                    is_root=True)

    


# -- data-transformation-for-EBNF --



