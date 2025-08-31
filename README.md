# Syncraft

Syncraft is a parser/generator combinator library for Python. It helps you

- Build grammars
- Parse SQL statement to AST
- Search AST by grammar
- Convert AST to dataclass
- Check constraints over the AST/dataclass
- Change dataclass and convert back to AST


## Installation

### pip
```bash
pip install syncraft
```

### uv
```bash
uv add syncraft
```

Python 3.10+ is required.

## Quickstart

!. Define grammar 

```python
from dataclasses import dataclass
from syncraft import literal, parse, generate

A = literal("a")
B = literal("b")
syntax = A + B  # sequence

ast, _ = parse(syntax, "a b", dialect="sqlite")
gen, _ = generate(syntax, ast)
assert ast == gen
```

Collect parsed pieces into dataclasses using marks and `.to()`:

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

ast, _ = parse(syntax, "a b", dialect="sqlite")
value, invert = ast.bimap()
# value is Pair(first=VAR(a), second=VAR(b))
round_tripped, _ = generate(syntax, invert(value))
assert round_tripped == ast
```

Use the built‑in SQLite grammar snippets to parse statements:

```python
from syncraft import parse
from syncraft.sqlite3 import select_stmt

ast, _ = parse(select_stmt, "select a from t where a > 1", dialect="sqlite")
```

## Core ideas

- Syntax describes structure and transforms values; Algebra executes it.
- AST types: Then, Choice, Many, Marked, Collect, Nothing, Token.
- Operators: `+` (both), `>>` (keep right), `//` (keep left), `|` (choice), `~` (optional), `many()`, `sep_by()`, `between()`.
- Error model supports backtracking and commit (`cut()`).

## Documentation

- Tutorials and API reference are in the docs site (MkDocs). To build locally:
	1) install dev deps (see `pyproject.toml` dev group)
	2) run `mkdocs serve`

## Contributing / Roadmap

- Improve performance and add benchmarks
- Expand tutorials and SQLite coverage examples
