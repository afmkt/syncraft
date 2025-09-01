
# Concepts

This page explains how Syncraft’s high‑level Syntax ties into the underlying Algebras, how bidirectional mapping works, and how to write first‑order logic constraints over AST nodes.

## 1) Syntax and the underlying Algebras

In Syncraft, a `Syntax[A, S]` is a description of structure and value transformation. It’s backend‑agnostic: given an Algebra implementation (the backend), it returns an executable program for that backend.

Informally:

- Syntax: a combinator tree that describes how to recognize/produce structure and values.
- Algebra: a concrete interpreter for that description (e.g., parsing, generation, finding).

Signature sketch:

- `Syntax.alg: (AlgebraClass) -> AlgebraInstance`
- `Algebra.run: S -> Either[Error, (A, S)]`

The Syntax takes an Algebra class and creates an instance for that algebra. Operations are defined on Syntax but delegate to the underlying Algebra to produce results.


Backends in this project include:

- Parser Algebra: consumes a token/state stream to produce an AST/value.
- Generator Algebra: walks an AST/value, possibly modified, to (re)produce structure. 
- Finder Algebra: traverses existing trees to locate matches.

The same Syntax can be “compiled” against different Algebras. Core combinators like `+`, `|`, `many`, `map`, and `bimap` are defined once on `Syntax` and realized by delegating to the chosen Algebra’s operations. This separation lets you write a grammar once and execute it for parsing, generation, or analysis.

## 2) Bidirectional mapping: Bimap vs Iso

Bidirectional mapping appears in two closely related places:

1) On Syntax/Algebra: `syntax.bimap(f, i)` applies a forward mapping `f : A -> B` to produced values and uses the inverse `i : B -> A` to keep the backend state coherent. That coherence is enforced by the Algebra: e.g., Parser and Generator provide different implementations for the inverse mapping over their states. The forward and inverse functions are defined independently. This corresponds to a Biarrow: `Biarrow[A, B] = (A -> B, B -> A)`.

2) On AST nodes: `ast.bimap()` computes a projected value together with a data‑dependent inverse function that can rebuild the original AST from a compatible projection. Every node implements a `bimap` that returns `(value, inverse)`. The signature is `A -> (B, B -> A)`: the forward mapping returns the transformed value `B` along with an inverse function. The forward mapping dictates how the inverse works; they are no longer independent. This corresponds to a Bimap: `Bimap[A, B] = A -> (B, B -> A)`.


3) Why both? Many conversions are projective (they drop information). Reconstructing requires injecting context that was lost. That’s hard with a plain `Biarrow`, but feasible with a `Bimap` which returns a specialized inverse closure carrying the needed context.


How this differs from an Iso (optics):

- An Iso (from optics) is a total, law‑abiding isomorphism between types: a pair of pure functions that are mutual inverses for all values of their domains. Conceptually, an Iso is closer to `Biarrow`.
- Syncraft’s `Bimap` carries information from the forward mapping. It runs on a concrete input to produce `(value, inverse)` where the inverse is a closure specialized to the path/structure encountered. It composes like an Iso but can depend on runtime structure (e.g., which alternative matched), not just static types.


## 3) First‑order logic over AST nodes (constraints)

Syncraft lets you declare constraints over bound AST values using first‑order quantifiers. The typical flow:

1) Bind values during parsing/generation with `mark(...).bind()` or `.bind(name)`.
2) Write predicates in Python and lift them to constraints with `forall`/`exists`.
3) Compose constraints with boolean operators and evaluate them against the collected bindings.

Key pieces:

- `bind(name)`: records the current value under a symbolic name in the state’s bindings.
- `forall(f)` / `exists(f)`: wrap a predicate function. The function’s parameter names define which bindings it needs. The quantifier runs the predicate over the Cartesian product of all bound values for those names.
- `Constraint` composition: `&` (and), `|` (or), `^` (xor), `~` (not). Evaluation returns a `ConstraintResult` with `result: bool` and `unbound: set[str]` for any missing variables.
- Value projection: by default, predicates see the projected value via `bimap()` if the argument provides it, so you can write clean, semantic‑level checks.

Example: ensure all references differ from their declarations (toy grammar, schematic):

```python
from dataclasses import dataclass
from syncraft import literal, parse
from syncraft.constraint import forall

@dataclass
class Pair:
	left: object
	right: object

A = literal("a").mark("decl").bind()
B = literal("b").mark("ref").bind()
syntax = (A + B).to(Pair)

ast, bound = parse(syntax, "a b", dialect="sqlite")  # dialect is required by the tokenizer

# Write a value-level predicate using the parameter names of interest
def distinct(decl, ref) -> bool:
	return decl != ref

if bound is not None:
	ok = forall(distinct)(bound).result
```

The quantifier inspects the function signature `(decl, ref)`, gathers bound tuples for those names, forms combinations, and checks the predicate for each combination. Replace `forall` with `exists` to assert the existence of at least one satisfying pair. You can `&`/`|` multiple constraints and check a single combined result.

## 4) Relationship to sqlglot
Syncraft reuses sqlglot’s tokenizer to obtain a token stream, which is why `parse` requires a `dialect` argument. Parsing/generation logic and combinators are independent of sqlglot; only tokenization depends on it.
