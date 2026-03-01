# Syncraft

Syncraft is a parser/generator combinator library for Python. It helps you

- Build grammars
- Parse text to AST
- Convert AST to dataclass
- Check constraints over the AST/dataclass
- Convert dataclass back to AST


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

## Testing

Run the regex fuzz test:

```bash
pytest -q tests/test_regex.py -k test_fuzzing
```

To reproduce a fuzz failure, set a fixed seed:

```bash
SYNCRAFT_REGEX_FUZZ_SEED=12345 pytest -q tests/test_regex.py -k test_fuzzing
```

TODO
- [ ]  Interactive parse tree visualizer based on rich.live and Tracer.tree
- [ ]  Static analysis tool based on Syntax.graph, for grammar analysis


















       


