# Syncraft

Syncraft is a bidirectional parser/generator combinator library for Python.

Define a grammar once.
- Parse text into structured data.
- Generate text back from that same structure.
- Keep both directions consistent by construction.

It provides Packrat-style performance and supports direct left recursion.


## Philosophy

Syncraft is built on three beliefs.

### 1. One source of truth

Parsing, generation, and validation should come from a single grammar model.

If you define a language once, you should not need:
- a parser,
- a transformer,
- a serializer,
- and a separate validator.

A single definition should unify all directions.  
Roundtripping should fall out of the model, not be manually maintained.

---

### 2. Shape matters

A parsing library should deliver values in the shape the user actually wants.

Not:
- raw parse trees,
- intermediate ASTs that require post-processing,
- or mandatory visitor passes.

Transformation is not an afterthought — it is part of the grammar definition.  
Grammars describe both structure *and* meaning.

---

### 3. CFGs should feel like regex

Context-free grammars shouldn’t feel heavier than regular expressions.

If you can sketch a regex, you should be able to sketch a recursive grammar just as quickly.

`Syntax.rp` exists to make recursive grammar fragments feel as lightweight and composable as regex — without giving up context-free power.


## Core capabilities

Syncraft provides two core capabilities:

1. **Bidirectional grammar + transformation**
	- Define grammar and data transformation together.
	- Parse text into structured values.
	- Generate text back from structured values from the same grammar model.

2. **Regex++**
	- Embed named recursive grammar fragments inside a regex-like syntax, effectively turning regular expressions into composable context-free grammar fragments.
	- Compose those fragments with grammar combinators.


## Scope

Syncraft is a strong fit when you need:

| If you need...                       | Syncraft provides...                                  |
| ------------------------------------ | ----------------------------------------------------- |
| A small DSL or config language       | Regex++ grammar sketching + structured AST generation |
| Strict roundtrip guarantees          | One grammar model for parse() and generate()          |
| Evolving grammars during prototyping | Combinator + fragment composition model               |


Syncraft is also good for parsing-only/extraction workflows.
Generation and roundtrip constraints become additional advantages when you need them, not requirements for adoption.


## Quick example: regex++ parsing for a common mini-language

This style is useful when you want to sketch and evolve a small language quickly.
Here, we parse a recursive expression grammar:

- `expr := number | '(' expr op expr ')'`
- `op := + | - | * | /`

```python
from syncraft.syntax import Syntax as S

num = S.rp(r"[0-9]+").bimap(int, str)
op = S.rp(r"[+\-*/]")

expr = S.lazy(lambda: S.rp(
	r"(?&num)|(\((?&expr)\s*(?&op)\s*(?&expr)\))",
	num=num, op=op, expr=expr
))

print(expr.parse("7"))
print(expr.parse("(2+3)"))
print(expr.parse("((1+2)*3)"))
```

Expected output:

```python
7
(2, '+', 3)
((1, '+', 2), '*', 3)
```

### Adding structured data transformations

Transform parsed tuples into dataclasses and generate text back from those dataclasses:
The `case()` combinator defines bidirectional structural mappings. Each case provides a pair of functions: one to extract values from parsed tuples, and one to construct domain objects."

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
    (lambda env: (env.left, env.op, env.right), lambda env: BinaryOp(env.left, env.op, env.right))
)

# Parse into dataclasses
result = expr_ast.parse("((1+2)*3)")
print(result)
# Output: BinaryOp(left=BinaryOp(left=Number(value=1), op='+', right=Number(value=2)), op='*', right=Number(value=3))

# Generate text back from dataclasses
text = expr_ast.generate(result)
print(text)
# Output: ((1+2)*3)
```


## Installation

Python 3.10+ is required.

### With pip
```bash
pip install syncraft
```

### With uv
```bash
uv add syncraft
```



















       


