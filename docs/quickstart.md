# Quickstart

A whirlwind tour of defining a small recursive grammar, mapping it into Python data, and round-tripping with validation and generation.

## Core concepts

### 1) Grammar

A grammar in Syncraft is a named, reusable entry point built from `Syntax` values. Use `@grammar` and `lazy` to define recursive grammars and to expose a single parse/generate entry.

### 2) Syntax

`Syntax[A, S]` is the type of grammar values that also carry value-level transformations. You can think of it as a grammar plus a mapping to a semantic value `A`.

Key ideas:

- `map` transforms produced values.
- `to` maps tupled structures into dataclasses or other domain objects.
- `mark` / `bind` label parts of the structure so you can access or reuse them during transformation.

Syntax is also where the building blocks live:

- `literal("...")` and `charset(...)` describe terminals.
- `+` sequences two pieces (concatenation).
- `|` picks between alternatives.
- `many` / `many1` repeat a piece.

### 3) Unification-based bidirectional data transformation

Syncraft treats parsing and generation as two directions of the same specification. The data layer uses unification to reconcile structure with values, so constraints are enforced by the unification process itself instead of a separate constraint module.

What this means in practice:

- When parsing, structure produces values.
- When generating, values must unify with the structure; incompatible values fail early.
- `bimap` lets you define forward and inverse projections that stay consistent with unification.

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
