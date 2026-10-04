#!/usr/bin/env python3
"""
Offline eval runner — runs all trajectory rule checks and saves results.

No AWS credentials or LLM required. Uses pre-recorded golden trajectories
from evals/dataset/returns_refunds.jsonl and the in-memory mock tools.

Usage:
    python3 evals/run_evals.py                        # run all, save results
    python3 evals/run_evals.py --ids tc-001 tc-003    # run specific examples
    python3 evals/run_evals.py --no-save              # print only, no file
    python3 evals/run_evals.py --results-dir /tmp     # custom output dir
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow importing evals package from repo root
sys.path.insert(0, str(Path(__file__).parents[1]))

from evals.mocks.tools import TraceRecorder, set_recorder


# ─── Dataset ──────────────────────────────────────────────────────────────────

def load_dataset(ids: list[str] | None = None) -> list[dict]:
    path = Path(__file__).parent / "dataset" / "returns_refunds.jsonl"
    examples = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if ids:
        examples = [ex for ex in examples if ex["id"] in ids]
    return examples


# ─── Rule evaluation ──────────────────────────────────────────────────────────

def evaluate_example(example: dict) -> dict:
    """Run the recorded trajectory through mock tools and check all rules."""
    rec = TraceRecorder()
    set_recorder(rec)
    t0 = time.perf_counter()
    rec.replay(example["recorded_trajectory"])
    set_recorder(None)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    rule_results: list[dict] = []

    for tool_name in example["rules"]["must_call"]:
        passed = rec.was_called(tool_name)
        rule_results.append({
            "rule": "must_call",
            "detail": tool_name,
            "passed": passed,
            "message": f"'{tool_name}' was{'not ' if not passed else ' '}called",
        })

    for tool_name in example["rules"]["must_not_call"]:
        passed = not rec.was_called(tool_name)
        rule_results.append({
            "rule": "must_not_call",
            "detail": tool_name,
            "passed": passed,
            "message": f"'{tool_name}' {'incorrectly ' if not passed else 'correctly '}absent",
        })

    for first, second in example["rules"]["order_before"]:
        passed = rec.called_before(first, second)
        rule_results.append({
            "rule": "order_before",
            "detail": f"{first} → {second}",
            "passed": passed,
            "message": (
                f"'{first}' correctly called before '{second}'"
                if passed
                else f"'{first}' NOT called before '{second}'"
            ),
        })

    all_passed = all(r["passed"] for r in rule_results)

    return {
        "id": example["id"],
        "description": example["description"],
        "passed": all_passed,
        "trajectory": rec.names(),
        "rule_results": rule_results,
        "elapsed_ms": elapsed_ms,
    }


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_all(examples: list[dict]) -> dict:
    results = []
    for ex in examples:
        result = evaluate_example(ex)
        results.append(result)
        status = "✓" if result["passed"] else "✗"
        print(f"  {status} {result['id']:10s}  {result['description'][:60]}")
        if not result["passed"]:
            for r in result["rule_results"]:
                if not r["passed"]:
                    print(f"           ↳ FAIL [{r['rule']}] {r['message']}")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "suite": "offline_trajectory",
        "results": results,
    }
    return summary


def save_results(summary: dict, results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    out_path = results_dir / f"run_{ts}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    return out_path


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline agentic evals")
    parser.add_argument("--ids", nargs="*", help="Specific example IDs to run")
    parser.add_argument("--no-save", action="store_true", help="Skip saving results")
    parser.add_argument(
        "--results-dir",
        default=str(Path(__file__).parent / "results"),
        help="Directory to write result files",
    )
    args = parser.parse_args()

    examples = load_dataset(ids=args.ids)
    if not examples:
        print("No examples found.")
        sys.exit(1)

    print(f"\n{'─'*60}")
    print(f"  Eval suite: offline trajectory rules")
    print(f"  Examples:   {len(examples)}")
    print(f"{'─'*60}")
    summary = run_all(examples)
    print(f"{'─'*60}")
    print(f"  Result: {summary['passed']}/{summary['total']} passed  ({summary['pass_rate']*100:.1f}%)")

    if not args.no_save:
        out_path = save_results(summary, Path(args.results_dir))
        print(f"  Saved:  {out_path}")
    print(f"{'─'*60}\n")

    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
