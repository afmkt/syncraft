# Architecture

Syncraft is built around one core type: `Syntax[A, S]`.

- `A`: semantic value shape (what users care about)
- `S`: runtime parser/generator state

## Core model

1. You compose `Syntax` with combinators (`+`, `|`, `many`, `lazy`, `rp`, etc.).
2. The same syntax can be interpreted by different algebras:
   - parser algebra
   - generator algebra
   - validator algebra
3. Parse/generate/validate stay aligned because they share the same grammar model.

## Grammar layer

`@grammar` collects class-level `Syntax` fields into a declarative grammar.

- `rule(...)` labels rules and root entries.
- `lazy(...)` enables recursion and forward references.
- `Grammar.parse` / `Grammar.generate` / `Grammar.validate` use cached algebra instances.

## Why this design

- Avoid parser/serializer drift by using one source of truth.
- Keep syntax and value mappings close (`map`, `imap`, `bimap`, `to`, `case`).
- Support recursive grammars with direct left-recursion handling.
