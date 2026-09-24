# Writing a bidirectional grammar

This guide walks through building a Syncraft grammar that both **parses** text into structured data and **generates** text from that same structure.

The workflow is a fixed 7-step protocol. Follow the steps in order; each one depends on the previous.

**On this page**

1. [Grammar research](#1-grammar-research)
2. [EBNF drafting](#2-ebnf-drafting)
3. [Translate EBNF to Syncraft DSL](#3-translate-ebnf-to-syncraft-dsl)
4. [Verify bidirectional correctness](#4-verify-bidirectional-correctness)
5. [Domain modelling](#5-domain-modelling)
6. [Semantic mapping](#6-semantic-mapping)
7. [Testing and refinement](#7-testing-and-refinement)

---

## 1. Grammar research

Understand the target language before writing any Syncraft code.

- Find an authoritative syntax description (spec, existing grammar, RFCs, dialect docs).
- List the main constructs: terminals, operators, nesting, lists, optional pieces, recursion.
- Decide whether the language is small enough for one grammar class, or needs modules (shared lexical rules, statement vs expression layers, etc.).
- Choose an abstraction level: capture what you need for round-trip, not every obscure production if you do not need it yet.

Goal of this step: a clear inventory of constructs and a sense of how large the grammar will be.

---

## 2. EBNF drafting

Write a pure EBNF blueprint. Keep semantics and Python types out of it.

Example — a minimal EBNF-of-EBNF fragment:

```text
grammar  = rule { rule } ;
rule     = ident assign expr ";" ;
assign   = "=" | "::=" ;

expr     = seq { "|" seq } ;
seq      = { factor } ;

factor   = primary [ suffix ] ;
suffix   = "?" | "*" | "+" | "{" int "}" | "{" int "," [ int ] "}" ;

primary  = ident | string | "(" expr ")" | "[" expr "]" | "{" expr "}" ;
```

Why EBNF first:

- It separates **syntax** from **implementation**.
- It is easy to review and share before committing to Syncraft combinators.
- It becomes the checklist for step 3.

---

## 3. Translate EBNF to Syncraft DSL

Implement the EBNF with Syncraft, still without domain dataclasses. Prefer default parse shapes first; map to rich ASTs in step 6.

### Setup

```python
from syncraft import Grammar, grammar, lazy, rule, Syntax as S
```

### Terminals

| Construct | Syncraft |
| --- | --- |
| Exact text | `S.lit('TEXT')` or `S.lit('TEXT', i=True)` (case-insensitive) |
| Regex | `S.re(r'PATTERN')` or `S.re(r'PATTERN', i=True)` |

### Sequence

| Intent | Syncraft |
| --- | --- |
| Keep both | `A + B` or `S.seq(A, B, C)` |
| Keep only right | `A >> B` |
| Keep only left | `A // B` |
| Drop a part | `S.seq(A, -B, C)` — `-` marks a component to match but not keep |

### Alternation

```python
A | B
S.alt(A, B, C)
```

### Repetition

```python
A.many()                      # 0 or more
A.many(at_least=1)            # 1 or more
A.many(at_least=0, at_most=5) # bounded
~A                            # optional (0 or 1), same idea as A.optional
A.sep_by(S.lit(','), at_least=1)
A.between(S.lit('('), S.lit(')'))
```

### Recursion

Use `S.lazy(...)` or `@lazy` inside a `@grammar` class so rules can refer to each other.

### Regex++ (`S.rp`)

Embed named recursive fragments in a regex-like pattern:

```python
S.rp(
    r"\{(?&int)(,(?&int)?)?\}",
    int=S.re(r"\d+"),
)
```

Only grouped subexpressions appear in the default output, named or not.

### `@grammar` organization

```python
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

Notes:

- `@lazy(S)` is for forward / mutual references in class bodies.
- `rule(..., is_root=True)` marks the entry rule.
- Lexer-backed terminals (`S.lit`, `S.re`) use global skip rules; inside `S.rp(...)`, model spacing yourself when it matters.

### Default parse shapes

When the output shape is unclear, call `.parse(...)` on a small sample.

| Construct | Default result |
| --- | --- |
| Terminal | matched text |
| Sequence (kept parts) | tuple of kept parts |
| Alternation | the matched alternative’s value |
| Repetition | tuple of matches |
| `S.rp` | tuple of grouped subexpressions |

Examples:

```python
S.lit('a').parse('a')                    # 'a'
(S.lit('a') + S.lit('b')).parse('ab')    # ('a', 'b')
S.seq(S.lit('a'), -S.lit('b'), S.lit('c')).parse('abc')  # ('a', 'c')
S.lit('a').many().parse('aaa')           # ('a', 'a', 'a')
```

---

## 4. Verify bidirectional correctness

Before adding domain types, check that the grammar round-trips on default shapes.

A correct bidirectional rule satisfies:

```text
AST = G.parse(input)
G.parse(G.generate(AST)) == AST
```

and, for values you care about generating from scratch, generation then parse should recover an equivalent structure.

Practical loop:

1. Take a small valid input.
2. `ast = rule.parse(input)` — inspect the shape.
3. `text = rule.generate(ast)` — should be valid text for the language (whitespace may differ unless you constrain it).
4. `rule.parse(text)` should match `ast` (or an agreed normal form).

Fix combinator mistakes here. Semantic mapping in step 6 will not salvage a broken structural grammar.

---

## 5. Domain modelling

Define Python `@dataclass` types for the **semantic domain** — the values your application wants, not the raw tuples from step 3.

Design rules:

- Keep enough information to regenerate text (do not drop operators, names, or nesting you need later).
- Prefer explicit variants over overloaded tuples.
- Nest dataclasses the same way the language nests constructs.

Example sketch:

```python
from dataclasses import dataclass

@dataclass
class Lit:
    value: str

@dataclass
class Ref:
    name: str

@dataclass
class Repeat:
    expr: object
    min: int
    max: int | None

@dataclass
class Seq:
    items: tuple

@dataclass
class Alt:
    items: tuple

@dataclass
class RuleDef:
    name: str
    expr: object

@dataclass
class GrammarDef:
    rules: tuple
```

---

## 6. Semantic mapping

Attach bidirectional transformations so parse produces domain objects and generate accepts them.

### Choosing an API

| Method | Direction | Use when |
| --- | --- | --- |
| `.map(f)` | parse only | One-way decoration; **not** for round-trip ASTs |
| `.bimap(fwd, inv)` | both | Leaf or simple value conversions (`int` ↔ `str`) |
| `.to(src, tgt)` | both | Structural reshape via unification of patterns |
| `.case([...])` | both | Several structural alternatives (tagged unions) |

Avoid calling `.imap` directly in grammars; `.bimap` owns that path.

### `.bimap`

```python
S.re(r"\d+").bimap(int, str).parse("123")   # 123
S.re(r"\d+").bimap(int, str).generate(123)  # '123'
```

### `.to`

Unify the parse shape with a source pattern; build the target from bound names:

```python
(S.lit("a") + S.lit("b")).to(
    lambda env: (env.X, env.Y),
    lambda env: {"field1": env.X, "field2": env.Y},
).parse("ab")
# {'field1': 'a', 'field2': 'b'}
```

### `.case`

Ordered cases for alternations and optional shapes:

```python
(S.lit("a") | S.lit("b")).case([
    (lambda env: "a", lambda env: "A"),
    (lambda env: "b", lambda env: "B"),
]).parse("a")  # 'A'
```

Suggested order when mapping a full grammar:

1. Lexical leaves (`int`, `string`, `ident`).
2. Small variants (`suffix` → repetition bounds).
3. Expression nodes (`factor`, `seq`, `expr`).
4. Top-level (`rule`, `grammar`).

Keep parser structure stable while you add mappings; change one layer at a time and re-check round-trips.

---

## 7. Testing and refinement

Exercise the finished grammar end to end.

- Valid inputs: parse → generate → parse (and generate from hand-built dataclasses).
- Invalid inputs: expect clean failure, not silent partial accepts if that matters for your language.
- Edge cases: empty lists, optional suffixes, nested groups, whitespace.
- If generation fails while parse works, inspect inverse mappings (`.bimap` / `.to` / `.case`) and missing fields in dataclasses.
- If parse shapes are surprising, reduce the input and print intermediate `.parse` results before mapping.

Refine until the 7-step chain is stable: research → EBNF → DSL → round-trip → domain types → mapping → tests.

---

## Minimal end-to-end sketch

A tiny expression grammar with domain types (same idea as the library quickstart):

```python
from dataclasses import dataclass
from syncraft.syntax import Syntax as S

num = S.rp(r"[0-9]+").bimap(int, str)
op = S.rp(r"[+\-*/]")

expr = S.lazy(lambda: S.rp(
    r"(?&num)|(\((?&expr)\s*(?&op)\s*(?&expr)\))",
    num=num, op=op, expr=expr,
))

@dataclass
class Number:
    value: int

@dataclass
class BinaryOp:
    left: object
    op: str
    right: object

expr_ast = expr.case(
    (lambda env: env.number, lambda env: Number(env.number)),
    (lambda env: (env.left, env.op, env.right),
     lambda env: BinaryOp(env.left, env.op, env.right)),
)

result = expr_ast.parse("((1+2)*3)")
text = expr_ast.generate(result)
```

Use this pattern when the language is small; use the full `@grammar` + EBNF path when it grows.

---

## See also

- [API Reference](../reference.md) — generated docs for public symbols
- Repository [README](https://github.com/afmkt/syncraft#readme) — install and short quickstart
- `examples/` in the repo — small runnable scripts
