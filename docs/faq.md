# FAQ

## How do I find out the shape of parsing results?

- Start with a small sample input and inspect `parse(...)` output directly.
- Use named captures/bindings and `to(...)`/`bimap(...)` to control the value shape.
- If tuple nesting is surprising, check whether normalization and sequencing operators (`+`, `>>`, `//`) are affecting structure.

## How do I fix parsing errors?

1. Reduce to the smallest failing input.
2. Enable parser debugging and inspect the failing branch.
3. Check token boundaries, separators, and whitespace handling first.
4. Confirm recursive rules have a non-recursive base case.

For deeper workflows, use the how-to pages in `docs/how-to/`.

## Should I keep FAQ if there are how-to docs?

Yes. Keep both with clear roles:

- FAQ: short answers and decision guidance.
- How-to: step-by-step procedures.

## Why does generation fail when parsing works?

Generation runs the inverse mapping path. Ensure inverse functions (`imap`/`bimap`) are valid and total for the values you provide.

## How do I validate data without generating text?

Use `validate(...)`. It returns `True` on success or an `Error` object describing failure.
