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

### With pip
```bash
pip install syncraft[dev]
```

### With uv
```bash
uv sync --group dev 
```

TODO
- [ ]  Merge DFA/NFA into CFG parsing pipeline. Make lex node in Algebra, take FA builder.
- [ ]  Refine the left-recursion handling, recover at or_else, or add Warth in Cache.
- [ ]  Visualization (railroad diagrams + AST).
- [ ]  Interactive dev (Jupyter).
- [ ]  Semantic layer (datalog + unification).