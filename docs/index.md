# Syncraft

Syncraft is a bidirectional parser/generator combinator library for Python.

Define a grammar once.

- Parse text into structured data.
- Generate text back from that same structure.
- Keep both directions consistent by construction.

It provides Packrat-style performance and supports direct left recursion.

Current version: {{ version }} · Pre-1.0 (Release Candidate) — APIs may change before 1.0.

## Philosophy

- **One grammar = parse + generate**
- **Structure and transformation together**
- **Grammars should feel like regex**

## Core capabilities

1. **Bidirectional grammar + transformation**  
   Define grammar and value mappings together. Parse text → structured values; generate text ← the same model.

2. **Regex++**  
   Embed named recursive grammar fragments in a regex-like syntax, then compose them with combinators.

## Installation

Python 3.10+ is required.

```bash
pip install syncraft
```

or

```bash
uv add syncraft
```

## Quickstart

### 1. Parse with Regex++

A small recursive expression language:

- `expr := number | '(' expr op expr ')'`
- `op := + | - | * | /`

```python
from syncraft.syntax import Syntax as S

num = S.rp(r"[0-9]+").bimap(int, str)
op = S.rp(r"[+\-*/]")

expr = S.lazy(lambda: S.rp(
    r"(?&num)|(\((?&expr)\s*(?&op)\s*(?&expr)\))",
    num=num, op=op, expr=expr,
))

print(expr.parse("7"))           # 7
print(expr.parse("(2+3)"))       # (2, '+', 3)
print(expr.parse("((1+2)*3)"))   # ((1, '+', 2), '*', 3)
```

### 2. Map to dataclasses and generate

`.case()` defines bidirectional structural mappings: extract from the parse shape, build domain objects, and invert for generation.

```python
from dataclasses import dataclass

@dataclass
class Number:
    value: int

@dataclass
class BinaryOp:
    left: Number | BinaryOp
    op: str
    right: Number | BinaryOp

expr_ast = expr.case(
    (lambda env: env.number, lambda env: Number(env.number)),
    (lambda env: (env.left, env.op, env.right),
     lambda env: BinaryOp(env.left, env.op, env.right)),
)

result = expr_ast.parse("((1+2)*3)")
print(result)
# BinaryOp(left=BinaryOp(left=Number(value=1), op='+', right=Number(value=2)),
#          op='*', right=Number(value=3))

text = expr_ast.generate(result)
print(text)
# ((1+2)*3)
```

## Next steps

- **[How-To: Writing a bidirectional grammar](how-to/bidirectional-grammar.md)** — full 7-step workflow (research → EBNF → DSL → round-trip → domain types → mapping → tests)
- **[API Reference](reference.md)** — public symbols from source
