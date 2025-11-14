# Internal Design: DFA-based Lexeme Terminals (No Token Stream)

This document records the intended integration of regular-language execution (NFA/DFA) into Syncraft's parser combinators as a lexer layer with a single, shared DFA and no token stream. It is internal-facing design documentation for maintainers.

## Summary

- All lexical rules (declared anywhere) are collected and compiled into one shared DFA (per alphabet/mode) at build time.
- There is no token stream. Each FA node is a normal terminal in the grammar that:
  - runs the shared DFA starting at the current index,
  - picks the longest match among an allowed tag set (if provided),
  - resolves ties via centralized priority,
  - consumes input and produces exactly one AST value (map/bimap-able),
  - applies centralized mode transitions.
- Central policy (skip/priority/modes) is defined once and consulted by all FA terminals.

## Implementation status (as of 2025-09-26)

This section summarizes what is already implemented in the codebase and what is still planned.

Implemented:
- Module `syncraft/lexer.py` containing the core pieces:
  - `LexPolicy` with fields: `priority_by_tag`, `rule_actions`, and `declaration_order`.
  - `LexBuilder` DSL for lexeme IR: literal, concat(+), union(|), optional(~), star, plus, many. Intersection(&)/difference(-) are captured in the IR but not compiled yet.
  - `Lexer` which aggregates `LexRule`s and compiles a combined NFA → DFA → `Matcher`. Each rule can carry an explicit tag; otherwise a synthetic tag is assigned based on declaration order.
  - `Matcher.match(...)` longest-match engine over the shared DFA:
    - Respects an `allowed_tags` filter provided by the terminal call-site.
    - Tag selection tie-break: higher `priority_by_tag`, then `declaration_order`, then lexicographic tag name.
    - Guards against zero-length consumption in the main match.
    - Returns `MatchResult(end_index, value, tag)`; value is the matched slice (str/bytes).
- Build path (current): `_compile_builder_to_nfa` supports LITERAL/CONCAT/UNION/STAR/OPTIONAL/MANY (PLUS desugars). It unions all NFAs, determinizes once to a single DFA, and wraps into a `Matcher`.
- Syntax harvesting: `collect_lexers(root: Syntax, *, alphabet?, policy?) -> Lexer` walks the `Syntax` graph and extracts lexeme specs:
  - `Syntax.token(**kwargs)` now records its kwargs in `Syntax.meta.parameter` (changed in `Syntax.token`) enabling read-only introspection.
  - Currently collects only literal `text` values (str/bytes) into `LexBuilder.literal`. `token_type`, if provided, becomes the tag.
  - Builds a centralized `Lexer` with discovered rules and sets `declaration_order` from discovered tags.

Not yet implemented (planned):
- Regex pattern (`re.Pattern`) support in the collector and regex→FA compilation.
- Case-insensitive matching transform for `token(case_sensitive=False)`.
- Intersection (&) and difference (-) planning in the builder compiler (requires DFA planning step). These IR nodes currently raise `NotImplementedError` during NFA compilation.
- Mode stack application (push/pop/set) during match; placeholders exist in `LexPolicy` to insert this.
- A dedicated `Syntax.lex(...)` terminal wired to use the shared `Matcher` and pass `allowed_tags`.
- Optional DFA minimization threshold and per-mode DFA partitioning.

### Quick usage (current APIs)

```python
from syncraft.syntax import Syntax
from syncraft.lexer import collect_lexers

# Suppose `root` is your grammar Syntax[Any, S] that uses Syntax.token/literal
lex = collect_lexers(root, alphabet=Alphabet(str))
matcher = lex.build()

res = matcher.match("if(x)", 0)
if res:
    print(res.tag, res.value, res.end_index)
```

Terminal integration is pending; for now you can manually probe `matcher.match` to validate combined DFA behavior.

## Goals

- Preserve parser-combinator ergonomics: FA nodes act like any other terminal; they compose with `|`, `>>`, `many`, `map`, `bimap`, etc.
- Make authoring ergonomic (distributed declaration) but compile centrally (single DFA), avoiding repetition of skip/priority/mode settings.
- Provide predictable longest-match semantics per terminal with priority-based tag selection.
- Keep performance characteristics of DFA scanning while retaining parser-driven control (no pre-tokenization pass).

## Non-Goals

- Generating or exposing a token stream.
- Global longest-match across grammar alternatives (the parser decides which FA terminal is attempted; longest-match applies within a terminal call only).

## Model Overview

- Single shared DFA: All lexeme rules (from distributed nodes and/or central definitions) are compiled into a single DFA. Accept states carry tags (and optionally small metadata for actions).
- FA terminal: A grammar node that invokes the shared DFA at the parser's current input position and returns one AST value.
- Centralized policy ("LexPolicy") governs:
  - priority: `tag -> int` (descending priority wins)
  - lexical modes: current mode (stack) and per-tag actions (`push`, `pop`, `set`)
  - optional tag-to-value mapping for default conversions
- Distributed authoring, centralized compilation: Lexemes may be declared inline, but are aggregated into the shared DFA. Each terminal can constrain its allowed tag set for that call site.

## Runtime Behavior of an FA Terminal

Inputs:
- Parser state: underlying character/byte sequence, current index, and mode stack.
- Shared DFA (selected per mode/alphabet).
- LexPolicy (priority and actions).
- Optional `allowed_tags: frozenset[str|Enum]` to restrict what this terminal accepts (if omitted, means any active tag in the current mode).

Outputs:
- On success: `(value, new_index)` where `value` is typically the matched text (or the mapped value) and `new_index = index + matched_len`. The tag can be used by mappers or kept in state if needed.
- On failure: normal terminal failure at the same index.

Algorithm:
1. Match phase:
   - Run the DFA from the current index over the input.
   - Track `last_accept_pos` and `last_accept_tags = {tags at that pos} ∩ allowed_set`.
   - Stop on dead transition or end-of-input. If no accept for the allowed set: fail.
   - Choose one tag by: higher priority first; then declaration order (stable); then tag name as last resort.
   - Ensure matched length > 0 (anchors are zero-width internally and must not cause zero-length user-level matches).
   - Apply mode action (if any) for the chosen tag.
   - Compute the value (default: substring) and return success advancing index.
Notes:
- Longest-match is scoped to the terminal's allowed tags in the current mode, not globally across grammar alternatives.
- Anchors `^`/`$` use sentinel `CharSet.START_CP`/`CharSet.END_CP` and are handled inside the DFA; they do not contribute to `resumable` and should never create zero-length user matches.

## Authoring Modes

- Distributed authoring: Inline FA terminals (e.g., regex literals) appear next to CFG rules. No need to repeat skip/priority/mode attributes; central policy provides them.
- Composite terminals: A terminal may opt to accept multiple tags (i.e., omit `allowed_tags`). The terminal then returns the highest-priority tag among those that accept the longest span. This is useful for places where the grammar wants “the next lexeme by policy” without enumerating each tag.

## Centralized Policy (LexPolicy)

Suggested shape (conceptual):

- `priority_by_tag: dict[str|Enum, int]`
- `value_by_tag: dict[str|Enum, Callable[[str|bytes], Any]]` (optional, defaults to identity)
- `modes: dict[str, DFA]` and/or a single DFA with mode-partitioned accepts
- `rule_actions: dict[str|Enum, dict]` such as `{tag: {"push": "STRING"}}`, `{tag: {"pop": True}}`, or `{tag: {"set": "DEFAULT"}}`
- `declaration_order: list[str|Enum]` for stable tie-breaking

Policy lives in the parser state to avoid repeating attributes on every FA usage. Terminals consult it when matching.

## Data Flow and Artifacts

- Build-time aggregation:
  - Collect regex/FA definitions from the grammar (and optional central additions).
  - Normalize to a small IR; build NFAs via Thompson-like construction for friendly ops; determinize to DFA for DFA-only ops and finally for the unified DFA.
  - Merge accepts: `FAState -> frozenset[tag]`. Track per-tag order for ties.
  - Optionally run `DFA.minimize` when state count exceeds a threshold.

- Runtime:
  - Parser invokes terminals; terminals call the shared DFA with `(index, allowed_tags, mode)`; mode actions are applied per policy.
  - Cache/memoize `(index, allowed_mask, mode) -> (success/failure, end_index, tag, value_fingerprint)` for packrat behavior.

## Mapping and Round-Trip

- `map` and `bimap` on the terminal value behave like any other `Syntax` node.
- Default value is the matched text (or bytes). Central `value_by_tag` can supply defaults (e.g., `INT -> int`), and local `map/bimap` can override.

## Performance Considerations

- Determinization only once (global DFA). Prefer NFA locally but compile to DFA at the end.
- Optional minimization via `DFA.minimize` (already implemented) gated by size threshold.
- Transition merging is preserved via `DFA.merge_adjacent_transitions` to keep tables compact.
- Caching keys include `(index, allowed_tag_mask, mode)`. Allowed-tag mask can be a compact bitset if tags are dense.

## Edge Cases

- Zero-length patterns (other than anchors) are disallowed to prevent infinite match loops.
- If multiple tags accept the same longest span: resolve with `priority_by_tag`, then `declaration_order`, then lexicographical tag name.
- Mixed universes (bytes vs unicode) are disallowed at DFA build time (`MixedUniverseError`).
- End-of-input: `$` matches only at physical end; terminals should not force finalize except at EOF.

## Terminal Matching Pseudocode (conceptual)

```python
# Given: text, index, mode, policy, shared_dfa, allowed_tags (or None)

pos = index
state = shared_dfa.init_for_mode(mode)
last_accept_pos = None
last_accept_tags = frozenset()

while pos < len(text):
    c = text[pos]
    state = shared_dfa.step(state, c)
    if state is None:
        break
    if state in shared_dfa.accept:
        tags = shared_dfa.accept[state]
        tags_allowed = filter_tags(tags, allowed_tags, mode, policy)
        if tags_allowed:
            last_accept_pos = pos + 1
            last_accept_tags = tags_allowed
    pos += 1

if last_accept_pos is None:
    fail()
else:
    chosen = choose_tag(last_accept_tags, policy)
    matched = text[index:last_accept_pos]
    if len(matched) == 0:
        fail_zero_length()
    apply_mode_action(chosen, policy)
    value = map_value(chosen, matched, policy)
    index = last_accept_pos
    succeed(value, index)
```

## Integration Points (existing code)

- Automata and runners: `syncraft/fa.py` (classes `DFA`, `NFA`, `DFARunner`, `NFARunner`, `CharSet.START_CP`, `CharSet.END_CP`).
- Parser core: `syncraft/algebra.py`, `syncraft/syntax.py`, `syncraft/parser.py` (`ParserState`).
- Regular language entry points: `syncraft/regular.py` (extend to produce lexeme IR and feed the global builder).

## Testing Strategy

- Unit tests for:
  - Longest-match inside a terminal (single- and multi-tag allowed sets)
  - Priority tie-breaking
  - Trimming behavior (left/right) and absence of zero-length loops
  - Mode transitions (push/pop/set)
  - Anchors behavior at start/end
  - bimap round-trip for typical tokens (IDENT, INT)
- Property-based or fuzz tests for random strings against reference regex engines for subsets.

## Future Work / Open Questions

- Efficient representation of `allowed_tags` during matching (bitset masks vs set intersection).
- Per-scope policy overrides (temporarily change trims/mode for sub-grammars) as a small `Syntax.map_state` helper.
- Optional multi-alphabet support (bytes/unicode) via multiple DFAs and dynamic selection.
- Streaming inputs via `Algebra.Incomplete` if we later parse very large sources.
