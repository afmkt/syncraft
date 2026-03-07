# Left Recursion Handling & Diagnostics

This document explains how Syncraft detects and recovers from left recursion, how
it decides when to stop growing a left‑recursive parse, and what the diagnostic
fields in `LeftRecursionError` mean.

## Overview

Syncraft employs a *principled growth algorithm* inspired by classical PEG left
recursion recovery techniques:

1. **Seeding Phase**: A rule is first evaluated with left‑recursive alternatives
   suppressed. Re‑entries during this phase indicate potential left recursion and
   return a temporary failure (sentinel) so only base (non‑recursive) branches run.
2. **Grouping**: All seeding heads that share the same input start index are grouped
   into an `LRGroup` (covering direct and indirect/mutual cycles). The earliest head
   becomes the group leader.
3. **Growth Iteration**: Once all members finish seeding, the group repeatedly re‑runs
   each member. Any attempt that **strictly consumes more input** than the current best
   result replaces the member’s result and restarts a pass. Consumption is the only
   improvement metric; structural richness is ignored for determinism and termination.
4. **Propagation**: Consumption improvements may unlock earlier heads whose spans now
   can extend (e.g., precedence patterns). Such heads are scheduled via an agenda and
   a limited global fixpoint pass ensures cross‑index consistency.
5. **Termination**: Growth stops when a full pass produces no consumption improvements
   or a safety iteration cap (`max_growth_iterations`) is reached.

### Lazy wrappers

Rules defined with `Syntax.lazy(...)` (and the matching algebra helpers) yield AST values wrapped in a lightweight
`Lazy` node. The wrapper just marks the lazy boundary so the parser, validator, generator, and finder can revisit it
consistently. In typical workflows it behaves transparently—you only need to construct it manually when building ASTs
by hand.

## Why Only “More Input Consumed” Counts

Using span length as the sole improvement metric guarantees termination for grammars
that cannot produce infinite structure without progress. It also avoids ambiguous tie‑breaking
among structurally different but equally long parses—preserving PEG determinism.

## Error Diagnostics

`LeftRecursionError` is raised when either:

1. The safety cap is exceeded during growth (`reason='iteration-cap'`).
2. A left‑recursive group (single or mutual) reaches a fixed point with **zero net consumption**
   (nullable / unproductive cycle) (`reason='no-progress'`). This now applies to both direct
   and mutual cycles that succeed only via ε (empty) alternatives.

- `iterations`: Number of growth attempts executed for the group.
- `group_size`: 1 for direct recursion; >1 for mutual cycles.
- `seed_consumed`: Length (in tokens) of the base seed parse (if any).
- `best_consumed`: Longest length reached before failure.
- `limit`: Configured iteration cap (`Cache.max_growth_iterations`).
- `reason`: Currently `iteration-cap`; future: `no-progress`.

The printable representation also shows the rule stack (innermost at bottom) and a
list of remediation hints.

## Nullable / Unproductive Left Recursion

Grammars like `S -> S | ε` or mutual forms:

```
A -> B | ε
B -> A | ε
```

produce infinite recursive expansions without consuming input. Syncraft now
detects these and raises `LeftRecursionError(reason='no-progress')` for:

- Single‑head nullable recursion (direct).
- Multi‑head nullable or mutually unproductive cycles where every successful
   member’s best span length is 0.

If you truly intend a nullable nonterminal, refactor to isolate the nullable
part outside the left‑recursive position, e.g.:

```
List -> Item Rest
Rest -> (',' Item Rest) | ε
```

## Customizing Iteration Limits

Use `Cache.max_growth_iterations` to tune the safety ceiling. You can also inject a
custom `Cache` when calling `parse_word(..., cache=Cache())` to set a low iteration
limit for deterministic testing (see `test_iteration_cap_metrics_single_head`).

## When Things Go Wrong

If you see `iteration-cap`:

1. Inspect `seed_consumed` vs `best_consumed`: zero or unchanged often points to nullable
   recursion or missing a non‑recursive base case.
2. Consider refactoring to a right‑recursive or iterative form: `Expr -> Term (op Term)*`.
3. Increase `max_growth_iterations` only if the grammar legitimately requires deep chains.

## Planned Enhancements

- Grammar linting to highlight nullable LR patterns pre-parse.
- Structured (`dict`) export helper on `LeftRecursionError`.
- Optional structural secondary heuristic (opt‑in) while retaining consumption as primary.

---
For further reference see inline comments in `syncraft/cache.py` near the definition of
`LeftRecursionError` and `_grow_group`.
