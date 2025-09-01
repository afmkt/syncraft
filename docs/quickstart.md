# Quickstart

A whirlwind tour of defining a tiny grammar, mapping it into Python data, round-tripping it, and seeing how invalid data is handled.

## 1. Install the library
```bash
uv add syncraft
```
or
```bash
pip install syncraft
```

## 2. Define a grammar and parse some text
We’ll parse a list of pairs like "a b, a b, a b" separated by commas.

```python
from syncraft import literal, parse, generate  # see: syntax & parser in API reference

A = literal("a")
B = literal("b")
C = literal(",")
syntax = (A + B).sep_by(C)
ast, _ = parse(syntax, "a b, a b, a b", dialect="sqlite")

```
See also: `literal`, combinators like `+` and `.sep_by`, and `parse` in the [API reference](reference.md).

## 3. Convert AST to a friendlier value with bimap
`AST.bimap()` returns a pair `(value, inverse)` where:
- `value` is a simplified Python structure; and
- `inverse` maps a value back to an AST for round-tripping.

```python
value, inverse = ast.bimap()
print(value)
```

Expected output:
```text
[
    (VAR(a), VAR(b)),
    (VAR(a), VAR(b)),
    (VAR(a), VAR(b))
]
```

## 4. Mark nodes and collect into a dataclass
Marks let you label parts of the AST. `.to(Pair)` collects labeled parts into your own type.

```python
from dataclasses import dataclass
from typing import Any
from syncraft import literal, parse

@dataclass
class Pair:
        first: Any
        second: Any

A = literal("a").mark("first")
B = literal("b").mark("second")
C = literal(",")
syntax = (A + B).to(Pair).sep_by(C)

ast, _ = parse(syntax, "a b, a b, a b", dialect="sqlite")
value, inverse = ast.bimap()
print(value)
```

Expected output:
```text
[
    Pair(first=VAR(a), second=VAR(b)),
    Pair(first=VAR(a), second=VAR(b)),
    Pair(first=VAR(a), second=VAR(b))
]
```

## 5. Round-trip your data back to an AST
You can modify the value, send it through `inverse`, and inspect the resulting AST.

```python
value.append(value[1])
print(value)

ast2 = inverse(value)
print(ast2)
```

Expected output (abridged for readability):
```text
[
    Pair(first=VAR(a), second=VAR(b)),
    Pair(first=VAR(a), second=VAR(b)),
    Pair(first=VAR(a), second=VAR(b)),
    Pair(first=VAR(a), second=VAR(b))
]

Many(
    value=(
        Collect(collector=<class '__main__.Pair'>, ...),
        Collect(collector=<class '__main__.Pair'>, ...),
        Collect(collector=<class '__main__.Pair'>, ...),
        Collect(collector=<class '__main__.Pair'>, ...)
    )
)
```

See also: `bimap` on AST and `generate` in the [API reference](reference.md).

## 6. Add illegal data and see what happens on generation
When you include values that don’t fit the grammar, they’ll be dropped during generation.

```python
from syncraft import generate

value.append(Pair("x", "y"))
print(value)

ast3 = inverse(value)
rt, _ = generate(syntax, ast3)
print(rt)
```

Expected output (note the invalid pair is not present in the result):
```text
Many(
    value=(
        Collect(collector=<class '__main__.Pair'>, ...),
        Collect(collector=<class '__main__.Pair'>, ...),
        Collect(collector=<class '__main__.Pair'>, ...)
    )
)
```

The illegal data entry got dropped in the generation.
