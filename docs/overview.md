# Concepts

- Syntax describes structure; Algebra executes it.
- AST nodes: Then, Choice, Many, Marked, Collect, Nothing, Token.
- Operators: `+` (both), `>>` (keep right), `//` (keep left), `|` (choice), `~` (optional), `many()`, `sep_by()`, `between()`.
- Error model: Either[Error, (value, state)], `cut()` commits to a branch.
- Round-trip: `generate()` mirrors `parse()`. Use `ast.bimap()` to get a value and an inverse function.
