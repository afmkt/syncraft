from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class RunRow:
    variant: str
    model: str
    task_id: str
    first_pass_ok: int
    final_passed: int
    iterations_to_green: int
    time_to_green_sec: float
    tool_calls: int


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def load_runs(csv_path: Path) -> List[RunRow]:
    rows: List[RunRow] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rows.append(
                RunRow(
                    variant=(raw.get("variant") or "").strip(),
                    model=(raw.get("model") or "").strip(),
                    task_id=(raw.get("task_id") or "").strip(),
                    first_pass_ok=_to_int(raw.get("first_pass_ok", "0")),
                    final_passed=_to_int(raw.get("final_passed", "0")),
                    iterations_to_green=_to_int(raw.get("iterations_to_green", "0")),
                    time_to_green_sec=_to_float(raw.get("time_to_green_sec", "0")),
                    tool_calls=_to_int(raw.get("tool_calls", "0")),
                )
            )
    return rows


def load_task_difficulty(task_catalog_path: Path) -> Dict[str, str]:
    if not task_catalog_path.exists():
        return {}
    mapping: Dict[str, str] = {}
    with task_catalog_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            task_id = (raw.get("task_id") or "").strip()
            difficulty = (raw.get("difficulty") or "").strip()
            if task_id:
                mapping[task_id] = difficulty or "unknown"
    return mapping


def pct(values: List[int]) -> float:
    if not values:
        return 0.0
    return 100.0 * sum(values) / len(values)


def median(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def summarize(rows: List[RunRow]) -> Dict[str, dict]:
    by_variant: Dict[str, List[RunRow]] = defaultdict(list)
    for row in rows:
        by_variant[row.variant].append(row)

    summary: Dict[str, dict] = {}
    for variant, group in by_variant.items():
        summary[variant] = {
            "runs": len(group),
            "first_pass_rate": pct([r.first_pass_ok for r in group]),
            "final_pass_rate": pct([r.final_passed for r in group]),
            "median_iterations": median([float(r.iterations_to_green) for r in group]),
            "median_time_sec": median([r.time_to_green_sec for r in group]),
            "median_tool_calls": median([float(r.tool_calls) for r in group]),
        }
    return summary


def summarize_by_key(rows: List[RunRow], key_fn) -> Dict[Tuple[str, str], dict]:
    grouped: Dict[Tuple[str, str], List[RunRow]] = defaultdict(list)
    for row in rows:
        key = (key_fn(row), row.variant)
        grouped[key].append(row)

    summary: Dict[Tuple[str, str], dict] = {}
    for (bucket, variant), group in grouped.items():
        summary[(bucket, variant)] = {
            "runs": len(group),
            "first_pass_rate": pct([r.first_pass_ok for r in group]),
            "final_pass_rate": pct([r.final_passed for r in group]),
            "median_iterations": median([float(r.iterations_to_green) for r in group]),
            "median_time_sec": median([r.time_to_green_sec for r in group]),
            "median_tool_calls": median([float(r.tool_calls) for r in group]),
        }
    return summary


def print_summary(summary: Dict[str, dict]) -> None:
    headers = [
        "variant",
        "runs",
        "first_pass_rate(%)",
        "final_pass_rate(%)",
        "median_iterations",
        "median_time_sec",
        "median_tool_calls",
    ]
    print(",".join(headers))
    for variant in sorted(summary.keys()):
        s = summary[variant]
        print(
            f"{variant},{s['runs']},{s['first_pass_rate']:.1f},{s['final_pass_rate']:.1f},"
            f"{s['median_iterations']:.2f},{s['median_time_sec']:.2f},{s['median_tool_calls']:.2f}"
        )


def print_breakdown(title: str, summary: Dict[Tuple[str, str], dict], bucket_name: str) -> None:
    print()
    print(f"# {title}")
    headers = [
        bucket_name,
        "variant",
        "runs",
        "first_pass_rate(%)",
        "final_pass_rate(%)",
        "median_iterations",
        "median_time_sec",
        "median_tool_calls",
    ]
    print(",".join(headers))
    for (bucket, variant) in sorted(summary.keys()):
        s = summary[(bucket, variant)]
        print(
            f"{bucket},{variant},{s['runs']},{s['first_pass_rate']:.1f},{s['final_pass_rate']:.1f},"
            f"{s['median_iterations']:.2f},{s['median_time_sec']:.2f},{s['median_tool_calls']:.2f}"
        )


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python ai/benchmark/analyze_results.py ai/benchmark/runs_template.csv [ai/benchmark/task_catalog.csv]")
        return 2

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return 2

    rows = load_runs(csv_path)
    if not rows:
        print("No rows found.")
        return 1

    if len(sys.argv) >= 3:
        task_catalog_path = Path(sys.argv[2])
    else:
        task_catalog_path = csv_path.parent / "task_catalog.csv"

    task_difficulty = load_task_difficulty(task_catalog_path)

    summary = summarize(rows)
    by_model = summarize_by_key(rows, key_fn=lambda r: r.model or "unknown-model")
    by_difficulty = summarize_by_key(
        rows,
        key_fn=lambda r: task_difficulty.get(r.task_id, "unknown"),
    )

    print_summary(summary)
    print_breakdown("By model", by_model, "model")
    print_breakdown("By difficulty", by_difficulty, "difficulty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
