# AI-Friendliness Benchmark (rp vs @grammar)

This folder contains a practical benchmark scaffold to measure whether `Syntax.rp` is more AI-friendly than `@grammar` classes.

## Goal

Evaluate which style is easier for LLMs to produce correctly and iterate to green under fixed constraints.

## Definitions

AI-friendly means better on one or more of:
- First-pass correctness
- Fewer iterations to pass tests
- Lower time/tool-call cost to pass tests
- Lower human/manual correction effort

## Folder contents

- `protocol.md` — experiment design and decision criteria
- `task_catalog.csv` — task definitions and complexity labels
- `runs_template.csv` — per-run logging schema (append one row per run)
- `analyze_results.py` — aggregates metrics from `runs_template.csv`
- `prompts/` — prompt templates for paired `rp` vs `@grammar` runs

## Suggested workflow

1. Fill `task_catalog.csv` with benchmark tasks.
2. For each task, run both variants (`rp`, `grammar`) across models/seeds.
3. Log each run in `runs_template.csv`.
4. Run analysis:

```bash
python ai/benchmark/analyze_results.py ai/benchmark/runs_template.csv
```

Or explicitly pass task catalog for difficulty breakdown:

```bash
python ai/benchmark/analyze_results.py ai/benchmark/runs_template.csv ai/benchmark/task_catalog.csv
```

## Automated local run (Ollama)

Use the local runner to execute paired `rp`/`@grammar` generations and append benchmark rows.

```bash
python ai/benchmark/run_ollama_benchmark.py
```

Useful options:

```bash
# single task, both variants
python ai/benchmark/run_ollama_benchmark.py --task-ids T001

# custom model
python ai/benchmark/run_ollama_benchmark.py --model gpt-oss:20b

# more repair iterations per run
python ai/benchmark/run_ollama_benchmark.py --max-iterations 4
```

Generated artifacts are stored in `ai/benchmark/generated/`.

## Notes

- Keep prompts and budgets identical between variants.
- Use the same test oracle for both implementations.
- Do not mix manual and automatic fixes within the same run unless logged explicitly.
