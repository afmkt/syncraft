# Syncraft

Syncraft is a parser/generator combinator library for Python. It helps you

- Build grammars
- Parse SQL statement to AST
- Search AST by grammar
- Convert AST to dataclass
- Check constraints over the AST/dataclass
- Change dataclass and convert back to AST


## AI ready checklist

If you want to use Syncraft inside AI workflows (LLM tools, agents, or copilots), aim for:

- A small, stable public API surface with clear versioning
- Short, deterministic examples with expected outputs
- Strong docstrings and type hints for public functions
- Actionable error messages and recovery hints
- A concise reference of common tasks and pitfalls

See [docs/ai-ready.md](docs/ai-ready.md) for concrete guidance and doc templates.


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
- [ ]  Interactive parse tree visualizer based on rich.live and Tracer.tree
- [ ]  Static analysis tool based on Syntax.graph, for grammar analysis
- [ ]  regex.py convert Regex to Builder, for grammar authoring

















       


