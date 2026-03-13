# Syncraft

Syncraft is a bidirectional parser/generator combinator library for Python.

Define a grammar once.
- Parse text into structured data.
- Generate text back from that same structure.
- Keep both directions consistent by construction.

It provides Packrat-style performance and supports direct left recursion.

## Status

Pre-1.0 (Release Candidate) — APIs may change before 1.0.


## Philosophy

Syncraft is built around three ideas:

- one grammar = parse + generate
- structure and transformation together
- grammars should feel like regex

## Core capabilities

Syncraft provides two core capabilities:

1. **Bidirectional grammar + transformation**
	- Define grammar and data transformation together.
	- Parse text into structured values.
	- Generate text back from structured values from the same grammar model.

2. **Regex++**
	- Embed named recursive grammar fragments inside a regex-like syntax, effectively turning regular expressions into composable context-free grammar fragments.
	- Compose those fragments with grammar combinators.





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


## Documentation

Full documentation is available at: [https://afmkt.github.io/syncraft/](https://afmkt.github.io/syncraft/)