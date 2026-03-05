# Syncraft Formatting API RFC (Draft)

## Goal
Design a **predictable, safe, and ergonomic user-facing formatting API** based on subtree-attached `.format(...)` annotations, lowered to `LayoutDoc`.

## Non-goals
- Replacing current core renderer internals.
- Exposing raw `LayoutDoc` constructors as the default user API.
- Introducing a public formatting DSL in this phase.

---

## 1) Proposed Public API (idea 1)

Formatting is attached to grammar subtrees, not expressed as free-form `LayoutDoc` programs.

### User-facing shape

- `.format(...)` is available on grammar rules / combinators.
- Users provide a constrained `FormatSpec` (typed attributes), not arbitrary callbacks returning arbitrary values.
- Users do not manipulate raw AST directly.

### Example API sketch

```python
rule = value.sep_by(comma).format(
  kind="list",
  role="items",
  breakability="optional",
  indent=1,
  attach="none",
)
```

### `FormatSpec` vocabulary (v1)

- `kind`: structural class (`token`, `list`, `block`, `kv`, `call`, ...)
- `role`: semantic role (`item`, `separator`, `operator`, `open`, `close`, `key`, `value`, ...)
- `breakability`: `never | optional | required`
- `attach`: `none | left | right | both`
- `indent`: non-negative integer
- `precedence` (optional): numeric metadata for operator-like layout
- `attrs` (optional): reserved metadata bag with validation gate

All string-like fields should be modeled as enums in implementation for safety.

Canonical naming in this RFC is: `breakability` (not `breakable`) and `attach` (not `sticky_left/sticky_right`).

---

## 2) Predictability Contract

For AI friendliness, document this explicitly:

1. Same grammar + same `FormatSpec` + same render options => same output.
2. Lowering preserves semantic token order; punctuation/separators never silently disappear or reorder.
3. Width changes only affect line-breaking/indentation decisions, not token sequence.
4. Default rendering mode is deterministic and test-friendly.

---

## 3) Example Usage (target user experience)

```python
order = ORDER.format(kind="call", breakability="optional")
lp = LPAR.format(role="open", attach="right")
rp = RPAR.format(role="close", attach="left")
items = ITEM.sep_by(COMMA).format(
  kind="list",
  role="items",
  breakability="optional",
  indent=1,
)
comma = COMMA.format(role="separator", attach="left")

# Internally: grammar + FormatSpec --lower--> LayoutDoc --render--> str
```

---

## 4) Comparison With External Inspirations

| Resource | What it does well | What we should adopt | What we should avoid |
|---|---|---|---|
| Wadler/Leijen combinators | Minimal algebra with strong semantics (`group`, `nest`, `line`) | Keep these as the low-level core model | Exposing only low-level combinators to end users |
| Prettier Doc model | Practical, stable formatting behavior | Borrow deterministic layout philosophy | Coupling public API directly to low-level doc combinators |
| Black | Opinionated, deterministic, low-configuration UX | Default `stable` mode, minimal knobs | Over-coupling to Python-specific style choices |
| Rust fmt ecosystem | Reproducibility and CI-friendly formatting expectations | Explicit determinism contract and snapshot testing | Excessive configuration permutations |
| Elm/Haskell pretty libraries | Elegant law-like semantics | Keep algebraic rigor in lowering/invariants | Public API that is too abstract for typical grammar authors |

---

## 5) Why this design for Syncraft

- Syncraft users often come from parser/generator workflows and need predictable roundtrip verification.
- Existing low-level `LayoutDoc` is powerful but not the right default user surface.
- Subtree-attached `.format(...)` provides:
  - local intent declaration,
  - early validation of invalid combinations,
  - deterministic lowering behavior,
  - a safer API boundary (no arbitrary output values).

---

## 6) Rollout Plan

### Phase 1: Annotation API introduction
- Add `.format(...)` with validated `FormatSpec` on grammar subtrees.
- Keep current `fmt` mechanism behind the new API boundary.

### Phase 2: Docs + migration examples
- Add short cookbook entries in `docs/quickstart.md` and `docs/reference.md`.
- Convert one internal grammar example to annotation-first usage.

### Phase 3: Stability tests
- Snapshot tests for representative grammars at widths: 40 / 80 / 120.
- Invariant tests: token order, separator integrity, annotation preservation.

---

## 7) Open Questions

1. Which `FormatSpec` fields are mandatory in v1 vs optional?
2. Should `attrs` be allowed in v1, or postponed for stricter schema control?
3. Should unknown `kind`/`role` values raise immediately or be feature-gated?

---

## 8) Annotated Low-level IR Design (`FmtNode`)

### Context

Syncraft formatting runs from a **low-level token tree with annotations** produced by `.format(...)` on grammar rules (not from user dataclasses directly). The design must therefore be:

- independent of high-level domain classes,
- structurally composable from low-level rules,
- stable for deterministic lowering and AI generation.

### Proposed IR

```python
from dataclasses import dataclass, field
from typing import Any, Literal

@dataclass(frozen=True, slots=True)
class FmtAnn:
  kind: str                       # e.g. "item", "separator", "operator", "block"
  role: str | None = None         # e.g. "comma", "colon", "open", "close"
  precedence: int | None = None   # optional precedence metadata
  breakability: Literal["never", "optional", "required"] = "never"
  attach: Literal["none", "left", "right", "both"] = "none"
  indent: int = 0
  source_rule: str | None = None  # grammar rule/spec name
  source_span: tuple[int, int] | None = None
  attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FmtNode:
  text: str | None                # terminal payload; None for interior nodes
  ann: FmtAnn
  children: tuple["FmtNode", ...] = ()
```

### Why this shape

- Lowering consumes stable metadata (`kind`, `role`, `breakability`, `attach`) rather than matching emitted text.
- Rule-local `.format(...)` declares intent once; lowering composes it deterministically.
- Works for parser/generator flows regardless of whether a high-level AST layer exists.

### Lowering contract over `FmtNode`

The lowering pass maps annotated `FmtNode` trees to fully-typed `LayoutDoc` trees:

- unannotated nodes -> neutral `LayoutDoc.Raw(node)`;
- annotated nodes -> `Group/Line/Nest/Sequence` patterns based on canonical `FormatSpec` fields;
- output invariant: render input is always `LayoutDoc` (no arbitrary user return types).

No lowering rule should rely on substring matching to infer separators or operators.

---

## 9) Composition Laws (must-haves)

To make formatting predictable and AI-friendly, define and test these laws.

### Law 1 — Annotation preservation

For lowering from annotated tree to `LayoutDoc`, every leaf input token must appear exactly once in output (unless an explicitly documented transform says otherwise), and its `source_rule`/`role` metadata must be preserved.

### Law 2 — Separator integrity

If input contains `n` separator-role nodes in an accepted sequence, output must preserve separator count and relative order. Width/layout decisions may only change whitespace and line breaks.

### Law 3 — Width monotonicity of structure

Changing width may switch flat vs broken layout, but must not reorder semantic tokens or mutate annotation topology.

---

## Recommendation
Adopt idea 1 as the public contract: a **small, typed `.format(...)` annotation API** lowered deterministically to `LayoutDoc`, with strict invariants and validation.

---

## 10) Expressiveness Matrix for `.format` (local annotation model)

This section makes explicit what a rule-attached `.format(...)` API can express when formatting is anchored to a grammar subtree.

### Assumed model

- Users do **not** manipulate raw AST directly.
- Users annotate grammar subtrees via `.format(...)`.
- Lowering compiles annotations into `LayoutDoc`.
- Unannotated subtrees are promoted to neutral `LayoutDoc.Raw` before render.

### Baseline attribute vocabulary

The matrix below assumes a constrained, typed vocabulary (not arbitrary strings):

- `breakability`: `never | optional | required`
- `attach`: `none | left | right | both` (replaces two sticky booleans)
- `role`: controlled enum (`item`, `separator`, `operator`, `open`, `close`, `key`, `value`, ...)
- `kind`: controlled enum (`token`, `list`, `block`, `kv`, `call`, ...)
- `indent`: non-negative integer (or small enum)
- `precedence`: optional numeric metadata for operator-like layout

### Capability matrix

| Layout intent / constructor family | Encodable by local `.format`? | Conditions / required fields | Notes |
|---|---|---|---|
| `group` (flat-or-break choice) | Yes | `breakability=optional` + subtree boundary | Group args are implicit from subtree attachment |
| `line` / `softline` / hard break | Yes | `breakability=required/optional` + separator/operator roles | Hard vs soft must be explicit in schema |
| `nest` / indentation | Yes | `indent` + block/list/kv kind | Indent is local and compositional |
| `join` with separators | Yes | child ordering + `role=separator` + attach semantics | Separator count/order invariants should be enforced |
| Surrounders (`paren`, `brace`, `bracket`) | Yes | `role=open/close` (or `kind=surround`) | Works well with local subtree |
| Operator spacing policy | Yes | `role=operator` + attach + precedence | Must avoid text-based heuristics |
| `if_break`-style token variants | Yes (bounded) | explicit alternate token attrs for flat/broken | Needs typed alternate fields; still local |
| `align` to local anchor | Yes (local) | anchor role in same subtree | Local-column alignment is encodable |
| Cross-subtree/global alignment | Usually no | requires global context/table pass | Not purely local unless extra global phase added |
| Reordering children for style | No (by default) | would violate token-order law | Keep non-expressible for safety |
| Duplicating/eliding semantic tokens | No (by default) | would violate annotation preservation law | Only allow via explicit advanced transform phase |
| Conditional layout from external state | No (local model) | needs external env/context input | Keep out of v1 for determinism |

### Read of the matrix

Under Syncraft's subtree-attached model, most practical pretty-printing power is available through local attributes because combinator arguments are implicit in grammar structure. The model is therefore close to full `LayoutDoc` power for **structure-preserving** transforms.

The boundary is not "combinators vs attributes"; the boundary is **local, structure-preserving semantics** vs **non-local or semantics-changing transforms**.

### Acceptance criteria for “full enough”

Treat `.format` as sufficiently expressive if all are true:

1. Every target style in docs/examples can be lowered using only local annotations.
2. Lowering can realize required `group/line/nest/join/surround/operator` behavior without text matching.
3. Invariants from Section 9 remain true (annotation preservation, separator integrity, width monotonicity).
4. Any case that needs cross-subtree coupling is explicitly marked as out-of-scope or handled by a separate advanced pass.

### Optional extension point (without weakening v1 safety)

If future use-cases require non-local behavior, add a second, explicit phase:

- Phase A (v1): local `.format` lowering, structure-preserving only.
- Phase B (advanced, opt-in): validated rewrite pass over `LayoutDoc` with strict contracts.

This preserves ergonomic/safe defaults while allowing targeted growth in expressiveness.
