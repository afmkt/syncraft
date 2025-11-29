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
- [ ]  Static analysis tool based on Syntax.graph, for grammar analysis

- [ ]  regex.py convert Regex to Builder, for grammar authoring

- [ ]  Tiered semantic layer, 1. Raw: Callable[..., bool] 2. Propositional: forall/exists 3. PyDatalog adapter. 
       Propositional: ready
       Raw: ready
       PyDatalog adapter ??

- [ ]  A Grammar or Language module that package Syntax object and perform
       a. auto name for terminal rules
       b. separate map, to, mark, to a transform function
       c. 


Deficiency Planned Improvement

2. parse, generate, validate
3. parser, generator



