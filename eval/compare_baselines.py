"""
compare_baselines.py
------------------------------------------------
Priority 3 — Regression baseline system (plan-26003.md).

Standalone comparison tool: loads the most recent eval/results/<eval_id>_*.json
for one or more eval_ids and compares each against its stored
eval/baselines/<eval_id>.baseline.json (see eval_config.compare_to_baseline
for the comparison logic — score delta, per-check regressions/improvements,
and a 1.5x duration tolerance for performance_benchmark).

Baselines only ever change via --update, never as a side effect of running
this tool to compare.

Usage:
    uv run python eval/compare_baselines.py --eval-id score_nlp_annotation
    uv run python eval/compare_baselines.py --all
    uv run python eval/compare_baselines.py --all --update
    uv run python eval/compare_baselines.py --eval-id score_nlp_annotation --tolerance 0.10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import BASELINES_DIR, RESULTS_DIR, compare_to_baseline, load_baseline, update_baseline  # noqa: E402


def latest_result(eval_id: str) -> dict | None:
    """Load the most recent eval/results/<eval_id>_*.json for eval_id, or None."""
    matches = sorted(RESULTS_DIR.glob(f"{eval_id}_*.json"))
    if not matches:
        return None
    with open(matches[-1], encoding="utf-8") as f:
        return json.load(f)


def known_eval_ids() -> list[str]:
    """eval_ids that have at least a stored baseline or a captured result."""
    ids = set()
    if BASELINES_DIR.exists():
        ids.update(p.name.removesuffix(".baseline.json") for p in BASELINES_DIR.glob("*.baseline.json"))
    if RESULTS_DIR.exists():
        ids.update(p.name.rsplit("_", 1)[0] for p in RESULTS_DIR.glob("*.json") if not p.name.startswith("manifest_"))
    return sorted(ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--eval-id", help="compare one eval_id")
    group.add_argument("--all", action="store_true", help="compare every eval_id with a captured result")
    parser.add_argument("--update", action="store_true", help="promote each compared result to its baseline (after comparing)")
    parser.add_argument("--tolerance", type=float, default=0.05, help="score-drop tolerance (default 0.05 = 5%%)")
    args = parser.parse_args()

    eval_ids = known_eval_ids() if args.all else [args.eval_id]
    if not eval_ids:
        print("No eval_ids found — run some eval scripts with --json first.")
        return 1

    any_regressed = False
    any_missing = False

    for eval_id in eval_ids:
        result = latest_result(eval_id)
        if result is None:
            print(f"[{eval_id}] no captured result in eval/results/ — run it with --json first")
            any_missing = True
            continue

        baseline = load_baseline(eval_id)
        if baseline is None:
            print(f"[{eval_id}] no baseline yet (score={result['score']:.1%})")
            if args.update:
                path = update_baseline(eval_id, result)
                print(f"         baseline created -> {path}")
            continue

        cmp = compare_to_baseline(result, baseline, score_tolerance=args.tolerance)
        if cmp["regressed"]:
            any_regressed = True
            print(f"[{eval_id}] REGRESSED  score={result['score']:.1%} (baseline {baseline['score']:.1%})")
            for reason in cmp["reasons"]:
                print(f"         - {reason}")
        else:
            print(f"[{eval_id}] STABLE  score={result['score']:.1%} (delta {cmp['score_delta']:+.1%}, "
                  f"duration {cmp['duration_ratio']:.2f}x baseline)")
        if cmp["improved_checks"]:
            print(f"         {len(cmp['improved_checks'])} check(s) newly passing: {cmp['improved_checks']}")

        if args.update:
            path = update_baseline(eval_id, result)
            print(f"         baseline updated -> {path}")

    if any_regressed:
        return 1
    return 2 if any_missing and not any_regressed else 0


if __name__ == "__main__":
    sys.exit(main())
