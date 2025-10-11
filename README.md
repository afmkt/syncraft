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
- [ ]  Visualization (railroad diagrams + AST).
- [ ]  Interactive dev (Jupyter).
- [ ]  Semantic layer (datalog + unification).


Collect FABuilder instances during Syntax.run: extend Syntax.fabuilder() coverage (regex, case-insensitive literals) and ensure builders carry tags/actions/modes.
Build shared Lexer: compile aggregated builders once per run, store result in Syntax.config, propagate with existing transform/config pipeline.
Add Syntax.lex(builder: FABuilder) combinator: captures the builder and marks call sites for direct DFA execution.
Introduce Algebra.lex: access lexer from config, request matches with allowed tags, integrate with mode stack, and return matched slice for downstream transformations.
Update ParserState: support streaming input extension, generic position tracker (text/bytes/enum), mode stack, and caching hooks for lexing results.
Implement longest-match loop in Algebra.lex: reuse DFA runner, guard zero-length matches, apply mode actions, memoize (index, mode, allowed_tags) to cooperate with packrat cache.
Enhance error reporting: structure lexing failures with index, optional line/column, offending symbol, active tags/mode; surface via parser diagnostics.
Align tests/docs: migrate parser combinators to Syntax.lex, adjust existing token-based tests, add coverage for modes, streaming, and diagnostics; update internal docs, README, quickstart.