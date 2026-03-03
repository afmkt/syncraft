# Benchmark Protocol: `Syntax.rp` vs `@grammar`

## 1) Hypothesis

H0: `Syntax.rp` and `@grammar` perform the same for LLM-assisted authoring.

H1: One style is more AI-friendly (higher success or lower cost under fixed constraints).

## 2) Controlled setup

Keep these fixed per pairwise comparison:
- Same model and model version
- Same system prompt and instruction template
- Same token/context budget
- Same tools allowed
- Same stopping rule (e.g., max 6 iterations)
- Same task statement and tests

## 3) Task suite

Use 20–50 tasks spanning:
- Flat token patterns
- Nested groups
- Precedence/associativity
- Recursion (`expr`, list, tree)
- External references and transformations
- Negative/error cases

Each task must have:
- Spec prompt
- Reference tests
- Difficulty tag (`small`, `medium`, `hard`)

## 4) Run procedure

For each task:
1. Run variant `rp` with seed S.
2. Run variant `grammar` with seed S.
3. Repeat for N seeds and M models.
4. Record every run row in `runs_template.csv`.

## 5) Metrics

Primary:
- `first_pass_ok` (0/1)
- `iterations_to_green`
- `time_to_green_sec`
- `tool_calls`

Secondary:
- `manual_edits_lines`
- `tokens_in` / `tokens_out`
- `final_passed` (0/1)

Derived:
- First-pass rate by variant
- Median iterations/time by variant
- Variance (robustness) by variant

## 6) Decision rule

Claim "more AI-friendly" only if all hold:
- Better on at least 2 primary metrics
- Difference is consistent across models and difficulty bins
- No severe regression in correctness on hard tasks

## 7) Reporting template

Include:
- Aggregate table by variant
- Per-model/per-difficulty breakdown
- Failure taxonomy (e.g., reference wiring, recursion, transformation errors)
- Threats to validity
