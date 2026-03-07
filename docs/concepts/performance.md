# Performance

Syncraft uses memoization and structured recursion handling to make practical grammars efficient.

## What to expect

- Typical parser-combinator ergonomics with cache-backed execution.
- Left-recursive grammars are handled with growth/fixpoint logic.
- Deterministic behavior is favored over ambiguous tie-breaking.

## Performance tips

1. Order alternatives from simple to complex so cheap/high-probability branches are tried first.
2. Avoid left recursion when possible.
3. Prefer iterative forms such as `.many(...)` or right-recursive grammar patterns.
4. Treat Syncraft's left-recursion handling as a safety net, not as the primary authoring style.
