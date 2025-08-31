# Quickstart

```python
from dataclasses import dataclass
from syncraft import literal, parse, generate

A = literal("a")
B = literal("b")
syntax = A + B

ast, _ = parse(syntax, "a b", dialect="sqlite")
rt, _ = generate(syntax, ast)
assert ast == rt
```

Collect into dataclasses:

```python
from dataclasses import dataclass
from syncraft import literal

@dataclass
class Pair:
    first: any
    second: any

A = literal("a").mark("first")
B = literal("b").mark("second")
syntax = (A + B).to(Pair)
```
