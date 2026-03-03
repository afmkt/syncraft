# Syncraft

Syncraft is a parser/generator combinator library for Python. 

## Core capabilities in 1.0

Syncraft 1.0 focuses on two capabilities:

1. **Bidirectional grammar + transformation**
	- Define grammar and data transformation together.
	- Parse text into structured values.
	- Generate text back from structured values from the same grammar model.

2. **Regex-style CFG composition**
	- Use regex-flavored grammar fragments through `Syntax.rp`.
	- Compose those fragments with grammar combinators.

## Scope

Syncraft is a good fit when you need:

- A single grammar model for parse and generate workflows
- Rule-level transformations integrated into grammar definitions
- DSL/config/protocol pipelines where roundtrip behavior matters
- Regex-style CFG authoring that supports improvisational parsing of context-free languages

Syncraft is also a strong fit for parsing-only/extraction workflows.
Generation and roundtrip constraints become additional advantages when you need them, not requirements for adoption.

## Quick example: regex++ parsing for a common mini-language

This style is useful when you want to sketch and evolve a small language quickly.
Here, we parse a recursive expression grammar:

- `expr := number | '(' expr op expr ')'`
- `op := + | - | * | /`

```python
from syncraft.syntax import Syntax as S
from syncraft.parser import parse_string

num = S.rp(r"[0-9]+").bimap(int, str)
op = S.rp(r"[+\-*/]")

expr = S.lazy(lambda: S.rp(
	r"(?&num)|(\((?&expr)\s*(?&op)\s*(?&expr)\))",
	num=num, op=op, expr=expr
))

print(parse_string(expr, "7"))
print(parse_string(expr, "(2+3)"))
print(parse_string(expr, "((1+2)*3)"))
```

Expected output:

```python
7
(2, '+', 3)
((1, '+', 2), '*', 3)
```

## Comparison matrix (workflow-oriented)

| Capability | Syncraft 1.0 | Lark | pyparsing | Parsimonious |
|---|---|---|---|---|
| Combinator-style grammar construction in Python | ✅ Primary workflow | ⚠️ Available; grammar-string workflows are common | ✅ Primary workflow | ⚠️ Primarily PEG grammar strings |
| Rule-level parse transformations | ✅ | ✅ | ✅ | ⚠️ Usually done via visitors/processing pass |
| Parse + generate from one grammar model | ✅ Primary workflow | ⚠️ Possible in some designs | ⚠️ Possible in some designs | ❌ Not a primary built-in workflow |
| Regex-flavored CFG fragments integrated with combinators (`Syntax.rp`) | ✅ | ❌ | ❌ | ❌ |
| Grammar model reused for roundtrip/validation pipelines | ✅ Primary workflow | ⚠️ Requires custom architecture | ⚠️ Requires custom architecture | ⚠️ Requires custom architecture |

Notes:
- Matrix entries describe default workflow fit, not every possible extension.
- “⚠️” means feasible, but not typically the core out-of-the-box workflow.


## Installation

Python 3.10+ is required.

### With pip
```bash
pip install syncraft
```

### With uv
```bash
uv sync 
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
- [ ]  Interactive parse tree visualizer
- [ ]  Static analysis tool


















       


