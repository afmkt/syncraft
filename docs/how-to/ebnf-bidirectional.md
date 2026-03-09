# How to write an EBNF bidirectional grammar

This guide shows a practical workflow to write a bidirectional grammar in Syncraft,
starting from an EBNF specification of EBNF itself.

## 1) Start from the language spec

Write the target language first in EBNF form:

```text
grammar      = rule { rule } ;
rule         = ident assign expr ";" ;
assign       = "=" | "::=" ;

expr         = seq { "|" seq } ;
seq          = { factor } ;

factor       = primary [ suffix ] ;
suffix       = "?" | "*" | "+" | "{" int "}" | "{" int "," [ int ] "}" ;

primary      = ident | string | "(" expr ")" | "[" expr "]" | "{" expr "}" ;
```

This keeps parser design driven by language intent, not implementation details.

## 2) Translate into `@grammar` + Regex++ (`S.rp`)

Use declarative rules for readability and `S.rp(...)` for compact recursive fragments.

```python
from syncraft.grammar import Grammar, lazy, rule, grammar
from syncraft.syntax import Syntax

S = Syntax.set(builtin=True)


@grammar
class EBNF(Grammar):
    str_ = S.re(r"'([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\"")
    ident = S.re(r"[A-Za-z_][A-Za-z0-9_]*")

    @lazy(S)
    def grouped(_):
        return S.rp(
            r"\[\s*(?&expr)\s*\]|\(\s*(?&expr)\s*\)|\{\s*(?&expr)\s*\}",
            expr=EBNF.expr,
        )

    primary = S.alt(ident, str_, grouped)
    suffix = S.rp(r"(\?|\*|\+|\{(?&int)(,(?&int)?)?\})", int=S.re(r"\d+"))
    factor = primary + ~suffix
    seq = S.rp(r"(?:(?&factor)\s*)*", factor=factor)
    expr = S.rp(r"(?&seq)(?:\|\s*(?&seq))*", seq=seq)

    erule = S.rp(
        r"\s*(?&ident)\s*(::=|=)\s*(?&expr)\s*;\s*",
        ident=ident,
        expr=expr,
    )
    grammar = rule(erule.many(at_least=1), is_root=True)
```

This is a good example of two readability axes:

- `@grammar` rules for structure and naming.
- `S.rp(...)` for dense local patterns.

## 3) Validate parser behavior first

Before adding semantic transformations, validate shape and coverage.

```bash
source .venv/bin/activate
pytest -q tests/test_ebnf_grammar.py
```

## 4) Add bidirectional mappings in stage 2

After parser correctness is stable, add bidirectional mappings (`.bimap`, `.to`, `.case`) to move from raw parse shapes to domain structures and back.

Suggested order:

1. Map lexical terminals (`int`, `string`, `ident`).
2. Map `suffix` variants into explicit repetition records.
3. Map `factor`, `seq`, `expr` into typed expression nodes.
4. Map `erule` and `grammar` into typed rule/grammar models.

Keeping parser-first and mapping-second usually gives faster iteration and easier debugging.

## Notes

- Forward references in class bodies should use `@lazy(S)`.
- Global lexer skip behavior applies to lexer-backed terminals (`S.re`, `S.lit`).
- For `S.rp(...)`, model spacing explicitly inside regex++ fragments when needed.
