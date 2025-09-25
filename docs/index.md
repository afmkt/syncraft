# Syncraft

Current version: {{ version }}

Syncraft is a parser/generator combinator library for Python with round‑trip support.
You describe syntax once, parse text into a structured AST, transform or map it to data, and generate the original text back.

> Important limitation
> Left‑recursive grammars are supported by the Parser via principled LR recovery, but they are not generally round‑tripable after `ast.bimap()` because branch (`Choice`) information is dropped. The Generator cannot reliably re‑thread LR `Then` chains back into the original choice points without explicit hints. If round‑tripping is required, prefer right‑recursive/iterative encodings (e.g., `Term (op Term)*`) or preserve/re‑introduce branch kinds before `validate()`/`generate_with()`. See the left‑recursion how‑to for details.

## Why Syncraft?

- One grammar, two directions. Parse and generate from the same syntax.
- Select pieces with marks and map them to dataclasses.
- Transform data and regenerate text.
- Constraints to validate AST/data.
- Search utilities to locate data in AST.



## Installation

### Using pip
```bash
pip install syncraft
```

### Using uv
```bash
uv add syncraft
```



Links:

- Concepts: [concepts](concept.md)
- Quickstart: [Quickstart](quickstart.md)
- Reference: [API reference](reference.md)




