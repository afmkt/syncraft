# Bidirectional Parsing: AST Space vs. Parse Subspace

In bidirectional parsing (where both parsing and generation are supported), it is important to understand the distinction between the space of all possible Abstract Syntax Trees (ASTs) and the subset of ASTs that can be produced by parsing valid source code.

**Key Principle:**
- The set of all possible ASTs (AST space) is a superset of the set of ASTs produced by parsing valid input (parse subspace).
- Only ASTs in the parse subspace are guaranteed to be round-trippable (i.e., can be parsed from and generated back to source code without loss).
- ASTs constructed programmatically or transformed from other representations may not be accepted by a bidirectional grammar, and thus may not be generatable.

**Why This Matters:**
- In unidirectional parsing (parse-only), this distinction is less critical: any valid input produces a valid AST.
- In bidirectional parsing (parse and generate), only the parse subspace is safe for roundtripping. Attempting to generate source from an arbitrary AST may fail or produce invalid code.

**Practical Advice:**
- When designing transformations or tools that operate on ASTs, ensure that the resulting ASTs remain within the parse subspace if roundtripping is required.
- Use validation or normalization steps if needed before generation.

---
