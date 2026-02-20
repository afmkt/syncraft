# Quickstart

A whirlwind tour of defining a tiny grammar, mapping it into Python data, round-tripping it, and seeing how invalid data is handled.

## 1. Install the library
```bash
uv add syncraft
```
or
```bash
pip install syncraft
```

## 2. Define a grammar and parse some text
We’ll parse a list of pairs like "a b, a b, a b" separated by commas.

{{ include_code("tests/test_quickstart_examples.py", "python", start="-- step-2 --", end="-- step-2-end --") }}
See also: `literal`, combinators like `+` and `.sep_by`, and `parse_word` in the [API reference](reference.md).

## 3. Convert AST to a friendlier value with bimap
`AST.bimap` returns a pair `(value, inverse)` where:
- `value` is a simplified Python structure; and
- `inverse` maps a value back to an AST for round-tripping.

{{ include_code("tests/test_quickstart_examples.py", "python", start="-- step-3 --", end="-- step-3-end --") }}

## 4. Mark nodes and collect into a dataclass
Marks let you label parts of the AST. `.to(Pair)` collects labeled parts into your own type.

{{ include_code("tests/test_quickstart_examples.py", "python", start="-- step-4 --", end="-- step-4-end --") }}

## 5. Round-trip your data back to an AST
You can modify the value, send it through `inverse`, and inspect the resulting AST.

{{ include_code("tests/test_quickstart_examples.py", "python", start="-- step-5 --", end="-- step-5-end --") }}

See also: `bimap` on AST and `generate` in the [API reference](reference.md).

> Note
> `ast.bimap` drops `OrElse.kind` to `None` by design. For left‑recursive grammars, the Parser’s LR recovery
> produces `Then(kind=BOTH, ...)` chains that the Generator cannot generally re‑thread without those branch hints.
> Therefore, left‑recursive grammars are not guaranteed to round‑trip after `bimap`; mutually left‑recursive
> cases are especially prone to failure. If round‑trip is a requirement, prefer right‑recursive/iterative forms
> (e.g., `Term (op Term)*`), or preserve/re‑introduce explicit branch kinds before `validate()`/`generate_with()`.
> See the left‑recursion how‑to for details.

## 6. Add illegal data and see what happens on generation
When you include values that don’t fit the grammar, they’ll be dropped during generation.

{{ include_code("tests/test_quickstart_examples.py", "python", start="-- step-6 --", end="-- step-6-end --") }}

The illegal data entry got dropped in the generation.
