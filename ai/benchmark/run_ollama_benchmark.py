from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import json
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib import request


@dataclass
class TaskCase:
    input_text: str
    expected_repr: str


@dataclass
class TaskSpec:
    task_id: str
    title: str
    description: str
    difficulty: str
    test_file: str
    cases: List[TaskCase]


DEFAULT_TASKS: Dict[str, TaskSpec] = {
    "T001": TaskSpec(
        task_id="T001",
        title="Number list parse+generate",
        description="Comma-separated integer list with roundtrip semantics.",
        difficulty="small",
        test_file="tests/test_ai_t001.py",
        cases=[
            TaskCase(input_text="1,2,3", expected_repr="(1, 2, 3)"),
            TaskCase(input_text="10, 20, 30", expected_repr="(10, 20, 30)"),
        ],
    ),
    "T002": TaskSpec(
        task_id="T002",
        title="Arithmetic precedence",
        description="+ and * precedence with nested parens.",
        difficulty="medium",
        test_file="tests/test_ai_t002.py",
        cases=[
            TaskCase(input_text="1+2*3", expected_repr="(1, '+', (2, '*', 3))"),
            TaskCase(input_text="(1+2)*3", expected_repr="((1, '+', 2), '*', 3)"),
        ],
    ),
    "T003": TaskSpec(
        task_id="T003",
        title="JSON-like object pairs",
        description="Key:value pairs with optional whitespace.",
        difficulty="medium",
        test_file="tests/test_ai_t003.py",
        cases=[
            TaskCase(input_text='{"a": 1, "b": 2}', expected_repr='(("a", "1"), ("b", "2"))'),
        ],
    ),
    "T004": TaskSpec(
        task_id="T004",
        title="Recursive binary expr",
        description="num | (expr op expr) with transforms.",
        difficulty="hard",
        test_file="tests/test_ai_t004.py",
        cases=[
            TaskCase(input_text="7", expected_repr="7"),
            TaskCase(input_text="(2+3)", expected_repr="(2, '+', 3)"),
            TaskCase(input_text="((1+2)*3)", expected_repr="((1, '+', 2), '*', 3)"),
        ],
    ),
}


SYSTEM_PROMPT = """You are a Syncraft grammar author.

Write Python code only, no markdown fences.
Use Syncraft syntax API and expose one top-level variable named `grammar`.
The grammar must parse all required input/output examples exactly.
Do not include backreferences like \\1.
Do not use `.transform(...)`; use `.map(...)`, `.check(...)`, `.to(...)`, or `.bimap(...)` when needed.
Do not invent a custom grammar mini-language string (for example, no `start = ...` DSL inside `Syntax.rp`).
When using `.map(...)`, prefer explicit functions/lambdas with clear unary or binary parameters over ambiguous built-in callables.
Keep implementation minimal and deterministic.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paired rp/@grammar benchmark with local Ollama.")
    parser.add_argument(
        "--runs-csv",
        default="ai/benchmark/runs_template.csv",
        help="CSV file to append run rows.",
    )
    parser.add_argument(
        "--output-dir",
        default="ai/benchmark/generated",
        help="Directory for generated code artifacts.",
    )
    parser.add_argument(
        "--model",
        default="gpt-oss:20b",
        help="Ollama model name.",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434/api/chat",
        help="Ollama chat endpoint.",
    )
    parser.add_argument(
        "--task-ids",
        nargs="*",
        default=["T001", "T002", "T003", "T004"],
        help="Task IDs to run.",
    )
    parser.add_argument(
        "--variants",
        nargs="*",
        default=["rp", "grammar"],
        choices=["rp", "grammar"],
        help="Variants to run.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Seed label for logging (Ollama may ignore this for generation behavior).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max generation/repair rounds per task/variant.",
    )
    return parser.parse_args()


def read_prompt_template(variant: str) -> str:
    path = Path(f"ai/benchmark/prompts/{variant}_prompt_template.md")
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_task_spec_text(task: TaskSpec) -> str:
    lines = [
        f"Task ID: {task.task_id}",
        f"Title: {task.title}",
        f"Difficulty: {task.difficulty}",
        "",
        "Functional requirements:",
        f"- {task.description}",
        "- Expose final grammar as variable `grammar`.",
        "",
        "Input/Output examples:",
    ]
    for case in task.cases:
        lines.append(f"- Input: {case.input_text}")
        lines.append(f"  Expected: {case.expected_repr}")
    return "\n".join(lines)


def build_few_shot_text(variant: str) -> str:
    if variant == "grammar":
        return (
            "Few-shot reference (style + API correctness):\n"
            "```python\n"
            "from syncraft import Grammar, Syntax, grammar, rule\n"
            "\n"
            "S = Syntax.set()\n"
            "\n"
            "@grammar\n"
            "class NumberListGrammar(Grammar):\n"
            "    number = S.rp(r\"[0-9]+\").map(int)\n"
            "    comma = S.rp(r\"\\s*,\\s*\")\n"
            "    root = rule(number.sep_by(comma), is_root=True)\n"
            "\n"
            "grammar = NumberListGrammar.root\n"
            "```\n"
            "Notes: use @grammar class + rule(..., is_root=True), avoid non-existent APIs like `.transform` or `.sep_by1`."
        )
    return (
        "Few-shot reference (style + API correctness):\n"
        "```python\n"
        "from syncraft import Syntax\n"
        "\n"
        "S = Syntax.set()\n"
        "number = S.rp(r\"[0-9]+\").map(int)\n"
        "comma = S.rp(r\"\\s*,\\s*\")\n"
        "grammar = number.sep_by(comma)\n"
        "```\n"
        "Notes: use regex++ fragments directly (no `start = ...` mini-DSL), avoid non-existent APIs like `.transform` or `.sep_by1`."
    )


def fill_prompt(template: str, task: TaskSpec, target_file: Path, variant: str) -> str:
    task_spec = build_task_spec_text(task)
    few_shot = build_few_shot_text(variant)
    if variant == "grammar":
        output_contract = (
            "- Return Python code only.\n"
            "- Define one `@grammar` class with a parse entry.\n"
            "- It is optional to expose `grammar`, but if provided it must be parseable by `parse_string`.\n"
            "- Parsing behavior must satisfy all examples exactly.\n"
            "- In `.map(...)`, prefer explicit lambdas/functions with clear parameters.\n"
        )
    else:
        output_contract = (
            "- Return Python code only.\n"
            "- Define one top-level `grammar` variable.\n"
            "- `grammar` must be parseable by `parse_string(grammar, input)`.\n"
            "- Prefer external refs `(?&name)` and combinators over capture-group post-hoc regex parsing.\n"
            "- In `.map(...)`, prefer explicit lambdas/functions with clear parameters.\n"
        )
    return (
        template.replace("{{TARGET_FILES}}", str(target_file))
        .replace("{{TEST_FILE}}", task.test_file)
        .replace("{{TASK_SPEC}}", task_spec)
        + "\n\n"
        + few_shot
        + "\n\nOutput contract:\n"
        + output_contract
    )


def strip_code_fences(text: str) -> str:
    raw = text.strip()
    if raw.startswith("```") and raw.endswith("```"):
        parts = raw.split("\n")
        if len(parts) >= 3:
            return "\n".join(parts[1:-1]).strip()
    return raw


def call_ollama(ollama_url: str, model: str, system_prompt: str, user_prompt: str) -> str:
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = request.Request(
        ollama_url,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )
    with request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    content = ((data.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("Ollama returned empty content")
    return strip_code_fences(content)


def _find_grammar_class(namespace: Dict[str, Any]) -> Any | None:
    for name, value in namespace.items():
        if not isinstance(value, type):
            continue
        if name.startswith("_"):
            continue
        parse_attr = getattr(value, "parse", None)
        if callable(parse_attr):
            return value
    return None


def evaluate_generated_code(code_file: Path, task: TaskSpec, variant: str) -> tuple[bool, str | None]:
    namespace: Dict[str, Any] = {}
    module_name = f"syncraft_bench_{code_file.stem}_{uuid.uuid4().hex[:8]}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, code_file)
        if spec is None or spec.loader is None:
            return False, "module-load-error: could not create import spec"
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        namespace = module.__dict__
    except Exception as exc:
        return False, f"exec-error: {type(exc).__name__}: {exc}"
    finally:
        sys.modules.pop(module_name, None)

    grammar = namespace.get("grammar")
    grammar_class = _find_grammar_class(namespace) if variant == "grammar" else None

    if grammar is None and grammar_class is None:
        if variant == "grammar":
            return False, "missing-grammar-entry: expected `grammar` variable or @grammar class with .parse"
        return False, "missing-grammar-variable"

    try:
        from syncraft.parser import parse_string
    except Exception as exc:
        return False, f"import-error: {type(exc).__name__}: {exc}"

    for case in task.cases:
        expected = ast.literal_eval(case.expected_repr)
        try:
            if grammar is not None:
                got = parse_string(grammar, case.input_text)
            else:
                assert grammar_class is not None
                got = grammar_class.parse(case.input_text)
        except Exception as exc:
            return False, f"parse-error: {type(exc).__name__}: {exc}"
        if got != expected:
            return False, f"mismatch: input={case.input_text!r} expected={expected!r} got={got!r}"
    return True, None


def append_run_row(csv_path: Path, row: Dict[str, Any]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run_id",
                "timestamp",
                "model",
                "variant",
                "task_id",
                "seed",
                "first_pass_ok",
                "final_passed",
                "iterations_to_green",
                "time_to_green_sec",
                "tool_calls",
                "manual_edits_lines",
                "tokens_in",
                "tokens_out",
                "error_type",
                "notes",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def run_variant_task(
    output_dir: Path,
    runs_csv: Path,
    ollama_url: str,
    model: str,
    variant: str,
    task: TaskSpec,
    seed: int,
    max_iterations: int,
) -> Dict[str, Any]:
    started = time.perf_counter()
    first_pass_ok = 0
    final_passed = 0
    error_type = ""
    notes = ""
    tokens_in = 0
    tokens_out = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{task.task_id}_{variant}_{uuid.uuid4().hex[:8]}"
    code_path = output_dir / f"{run_id}.py"

    prompt_template = read_prompt_template(variant)
    prompt = fill_prompt(prompt_template, task, code_path, variant=variant)
    current_prompt = prompt
    iterations_to_green = max_iterations

    for iteration in range(1, max_iterations + 1):
        response = call_ollama(
            ollama_url=ollama_url,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=current_prompt,
        )
        tokens_in += len(current_prompt.split())
        tokens_out += len(response.split())
        code_path.write_text(response + "\n", encoding="utf-8")

        ok, fail_reason = evaluate_generated_code(code_path, task, variant=variant)
        if iteration == 1 and ok:
            first_pass_ok = 1
        if ok:
            final_passed = 1
            iterations_to_green = iteration
            error_type = ""
            notes = f"artifact={code_path}"
            break

        error_type = "evaluation-failed"
        notes = f"artifact={code_path}; reason={fail_reason}"
        extra_hint = ""
        if fail_reason and "Unsupported arity" in fail_reason:
            extra_hint = (
                "\n\nArity hint:\n"
                "- The failure indicates an unsupported callable arity in `.map(...)`.\n"
                "- Replace ambiguous/built-in callables with an explicit lambda/function taking 1 or 2 parameters.\n"
            )
        current_prompt = (
            prompt
            + "\n\nPrevious attempt failed. Repair this code with minimal changes.\n"
            + "Failure:\n"
            + (fail_reason or "unknown")
            + extra_hint
            + "\n\nCurrent code:\n"
            + response
        )

    elapsed = time.perf_counter() - started
    row = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "model": model,
        "variant": variant,
        "task_id": task.task_id,
        "seed": seed,
        "first_pass_ok": first_pass_ok,
        "final_passed": final_passed,
        "iterations_to_green": iterations_to_green,
        "time_to_green_sec": f"{elapsed:.2f}",
        "tool_calls": max_iterations if final_passed == 0 else iterations_to_green,
        "manual_edits_lines": 0,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "error_type": error_type,
        "notes": notes,
    }
    append_run_row(runs_csv, row)
    return row


def validate_task_ids(task_ids: Iterable[str]) -> List[str]:
    resolved: List[str] = []
    for task_id in task_ids:
        if task_id not in DEFAULT_TASKS:
            available = ", ".join(sorted(DEFAULT_TASKS.keys()))
            raise ValueError(f"Unknown task id: {task_id}. Available: {available}")
        resolved.append(task_id)
    return resolved


def main() -> int:
    args = parse_args()
    task_ids = validate_task_ids(args.task_ids)

    output_dir = Path(args.output_dir)
    runs_csv = Path(args.runs_csv)

    print(f"Model: {args.model}")
    print(f"Ollama URL: {args.ollama_url}")
    print(f"Tasks: {', '.join(task_ids)}")
    print(f"Variants: {', '.join(args.variants)}")
    print(f"Max iterations: {args.max_iterations}")

    for task_id in task_ids:
        task = DEFAULT_TASKS[task_id]
        for variant in args.variants:
            row = run_variant_task(
                output_dir=output_dir,
                runs_csv=runs_csv,
                ollama_url=args.ollama_url,
                model=args.model,
                variant=variant,
                task=task,
                seed=args.seed,
                max_iterations=args.max_iterations,
            )
            print(
                f"[{row['task_id']}:{row['variant']}] "
                f"first_pass={row['first_pass_ok']} final_pass={row['final_passed']} "
                f"iter={row['iterations_to_green']} time={row['time_to_green_sec']}s"
            )

    print(f"Appended results to: {runs_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
