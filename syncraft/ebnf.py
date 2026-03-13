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
from typing import Tuple, Optional, Dict, Callable, Type, Set
from syncraft.grammar import Grammar, lazy, rule, grammar
from syncraft.syntax import Syntax, SyntaxSpec, Graph, SeqSpec, AltSpec, ManySpec, LexSpec, LazySpec
from syncraft.ast import Nothing
from syncraft.fa import Builder
from syncraft.regex import re
from rich import print





@dataclass(frozen=True)
class EBNFExpr:
    def to_str(self) -> str:
        return ""
    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        raise NotImplementedError("syntax() not implemented for EBNFExpr")
    


@dataclass(frozen=True)
class NothingExpr(EBNFExpr):

    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        # print(self)
        return cls.success(Nothing)

@dataclass(frozen=True)
class Ref(EBNFExpr):
    name: str                    # rule reference: ident   
    def to_str(self) -> str:
        return self.name
     
    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        # print(self, 'env:', env, 'visited', visited)
        if self.name not in env:
            raise ValueError(f"Undefined rule reference: {self.name}")
        if self in visited:
            # print(f"Detected left recursion on rule {self.name}, creating lazy reference")
            ret = cls.lazy(lambda: env[self.name]())
            env[self.name] = lambda: ret
            return ret
        visited.add(self)
        try:
            result = env[self.name]()
            env[self.name] = lambda: result
        finally:
            visited.discard(self)
        return result

@dataclass(frozen=True)
class Lit(EBNFExpr):
    literal: str                   # decoded string literal value

    def to_str(self) -> str:
        return f"'{self.literal}'"

    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        # print(self)
        return cls.lit(self.literal)

@dataclass(frozen=True)
class Seq(EBNFExpr):
    seq: Tuple[EBNFExpr, ...]  # empty tuple => epsilon

    def to_str(self) -> str:
        return " ".join(item.to_str() for item in self.seq)

    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        tmp = []
        for item in self.seq:
            s = item.syntax(cls, env, visited)
            tmp.append(s)
        return cls.seq(*tmp)
    
@dataclass(frozen=True)
class Alt(EBNFExpr):
    alt: Tuple[EBNFExpr, ...]  # len >= 2 ideally

    def to_str(self) -> str:
        return " | ".join(opt.to_str() for opt in self.alt)
    
    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        tmp = []
        for opt in self.alt:
            s = opt.syntax(cls, env, visited)
            tmp.append(s)
        return cls.alt(*tmp)

@dataclass(frozen=True)
class Repeat(EBNFExpr):
    expr: EBNFExpr
    minimum: int                 # 0/1/...
    maximum: Optional[int]       # None => unbounded

    def to_str(self) -> str:
        inner = self.expr.to_str()
        if self.minimum == 0 and self.maximum is None:
            return f"{{ {inner} }}"
        elif self.minimum == 0 and self.maximum == 1:
            return f"[ {inner} ]"
        elif self.minimum == 1 and self.maximum is None:
            return f"( {inner} )+"
        elif self.minimum == self.maximum:
            return f"( {inner} ){{{self.minimum}}}"
        elif self.maximum is None:
            return f"( {inner} ){{{self.minimum},}}"
        else:
            return f"( {inner} ){{{self.minimum},{self.maximum}}}"    
    
    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        # print(self)
        s = self.expr.syntax(cls, env, visited)
        return s.many(at_least=self.minimum, at_most=self.maximum)

@dataclass(frozen=True)
class RuleDef(EBNFExpr):
    name: str
    expr: EBNFExpr
    
    def to_str(self) -> str:
        return f"{self.name} = {self.expr.to_str()};"

    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        return self.expr.syntax(cls, env, visited).named(self.name)
    

@dataclass(frozen=True)
class GrammarDef(EBNFExpr):
    rules: Tuple[RuleDef, ...]    
    def to_str(self) -> str:
        return "\n".join(r.to_str() for r in self.rules)

    def syntax(self, cls: Type[Syntax], env: Dict[str, Callable[[], Syntax]], visited: Set[EBNFExpr]) -> Syntax:
        def wrap_rule(r: RuleDef) -> Callable[[], Syntax]:
            def rule_f() -> Syntax:
                return r.expr.syntax(cls, env, visited).named(r.name)
            return rule_f
        
        if not self.rules:
            raise ValueError("Grammar must have at least one rule")
        
        for r in self.rules:
            env[r.name] = wrap_rule(r)
        return env[self.rules[0].name]()


    @classmethod
    def from_graph(cls, graph: Graph[SyntaxSpec]) -> GrammarDef:
        # Map SyntaxSpec nodes to EBNFExprs (memoized to handle cycles)
        spec_to_expr: Dict[SyntaxSpec, EBNFExpr] = {}

        def spec_to_ebnfexpr(spec: SyntaxSpec) -> EBNFExpr:
            # Memoize before recursion to handle cycles
            if spec in spec_to_expr:
                return spec_to_expr[spec]
            # Pre-insert a placeholder to break cycles
            spec_to_expr[spec] = Ref(getattr(spec, 'name', None) or '<anon>')
            if isinstance(spec, SeqSpec):
                items = tuple(spec_to_ebnfexpr(s) for s, keep in spec.steps if keep)
                expr: EBNFExpr = Seq(items)
            elif isinstance(spec, AltSpec):
                options = tuple(spec_to_ebnfexpr(opt) for opt in spec.options)
                expr = Alt(options)
            elif isinstance(spec, ManySpec):
                expr = Repeat(spec_to_ebnfexpr(spec.spec), spec.at_least, spec.at_most)
            elif isinstance(spec, LexSpec):
                p = spec.pattern
                if p is None:
                    raise ValueError(f"LexSpec {spec.fname} has no pattern")
                expr = Lit(p)
            elif isinstance(spec, LazySpec):
                expr = spec_to_ebnfexpr(spec.inner_spec)
            else:
                if spec.name:
                    expr = Ref(spec.name)
                else:
                    raise NotImplementedError(f"Cannot convert {type(spec)} to EBNFExpr")
            spec_to_expr[spec] = expr
            return expr

        # Find all named nodes (rules)
        rules = []
        name_to_rule = {}
        for node in graph.nodes:
            name = getattr(node, "name", None)
            if name:
                expr = spec_to_ebnfexpr(node)
                rule = RuleDef(name, expr)
                rules.append(rule)
                name_to_rule[name] = rule
        # Ensure the root rule is first, if possible
        root_name = getattr(graph.root, "name", None)
        if root_name and root_name in name_to_rule:
            ordered_rules = [name_to_rule[root_name]] + [r for r in rules if r.name != root_name]
        else:
            ordered_rules = rules
        return GrammarDef(tuple(ordered_rules))
            

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



def transform_terminal(cls: Type[Syntax]) -> Syntax:
    return cls.re(r"\s*")



S = Syntax.set(builtin=True)
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
    
    suffix = S.rp(r"(\?|\*|\+|\{(?&int)(,(?&int)?)?\})", int=S.re(r"\d+").bimap(int, str)).case(
        (lambda _: '*', lambda _: (0, None)),
        (lambda _: '?', lambda _: (0, 1)),
        (lambda _: '+', lambda _: (1, None)),
        (lambda env: (env.Min, ()), lambda env: (env.Min, None)),
        (lambda env: (env.Min, ((),)), lambda env: (env.Min, None)),
        (lambda env: (env.Min, ((env.Max,),)), lambda env: (env.Min, env.Max))
    )
    factor = (primary + ~suffix).case(
        (lambda env: (env.P, Nothing),            lambda env: env.P),
        (lambda env: (env.P, (env.Min, env.Max)), lambda env: Repeat(env.P, env.Min, env.Max))
    )


    seq = S.rp(r"(\s*(?&factor)\s*)*", factor=factor).to(lambda env: Seq(env.X))
    
    expr = seq.sep_by(S.re(r"\s*\|\s*"), at_least=1).to(lambda env: Alt(env.X))

    erule = S.rp(
        r"\s*(?&ident)\s*(?:=|::=)\s*(?&expr)\s*;\s*",
        ident=ident,
        expr=expr,
    ).to(lambda env: (env.ident, env.expr), lambda env: RuleDef(env.ident, env.expr))

    grammar = rule(erule.many(at_least=1).to(lambda env: GrammarDef(env.X)), is_root=True)

    

# -- data-transformation-for-EBNF --



