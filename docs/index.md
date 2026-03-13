# Syncraft Docs

Parser/generator combinators with **round-trip semantics**.

Define a grammar once and get:

- parsing
- structured transformation
- text generation

all from the same model.


Current version: {{ version }}

## Why Syncraft?

Most parsing stacks require multiple layers:

- grammar
- AST transformation
- serializer
- validator

Syncraft collapses these into **one grammar model**.

A Syncraft grammar can:

- parse text -> structured data
- transform AST 
- generate text <- structured data


## Quick example
```python
from syncraft import Syntax as S

num = S.rp(r"[0-9]+").bimap(int, str)
op = S.rp(r"[+\-*/]")

expr = S.lazy(lambda: S.rp(
    r"(?&num)|(\((?&expr)\s*(?&op)\s*(?&expr)\))",
    num=num, op=op, expr=expr
))
ast = expr.parse("(2+3)")
print(ast)  
txt = expr.generate(ast, replay=True, seed = 0)
print(txt) 
txt = expr.generate((10, '-', 9), replay=True, seed = 0)
print(txt) 
```

## Start here

- New to Syncraft: [Quickstart](quickstart.md)
- Understand the design: [Concepts](concepts/architecture.md)
- Parse a language: [How-to](how-to/ebnf-bidirectional.md)
- Lookup APIs: [API reference](reference.md)
- Troubleshooting: [FAQ](faq.md)

## Installation

### Using pip
```bash
pip install syncraft
```

### Using uv
```bash
uv add syncraft
```






