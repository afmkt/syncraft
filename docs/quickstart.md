# Quickstart

A whirlwind tour of defining a small recursive grammar, mapping it into Python data, and round-tripping with validation and generation.

## 1. Install the library
```bash
uv add syncraft
```
or
```bash
pip install syncraft
```

## 2. Define a grammar and parse some text
We’ll build a recursive expression grammar and parse `1 + 2 * 3` into the default AST (tokens and tuples).

{{ include_code("tests/test_quickstart.py", "python", start="-- step-1 --", end="-- step-1-end --") }}

{{ include_code("tests/test_quickstart.py", "python", start="-- step-2 --", end="-- step-2-end --") }}
See also: `Syntax`, `@grammar`, `lazy`, and `Grammar.parse` in the [API reference](reference.md).

If you want regex terminals directly on character input, use `Syntax.re(pattern)`.

## 3. Define dataclasses for the AST
Create a small, explicit AST model for numbers and binary operators.

{{ include_code("tests/test_quickstart.py", "python", start="-- step-3 --", end="-- step-3-end --") }}

## 4. Add bidirectional data transformation to produce dataclasses
Use `bimap` for leaf values and `to(...)` for structural nodes so parsing yields the dataclass AST.

{{ include_code("tests/test_quickstart.py", "python", start="-- step-4 --", end="-- step-4-end --") }}

## 5. Validate and generate from dataclass AST
Validate and then generate from your dataclass instance.

{{ include_code("tests/test_quickstart.py", "python", start="-- step-5 --", end="-- step-5-end --") }}

See also: `bimap`, `to`, `validate`, and `generate` in the [API reference](reference.md).
