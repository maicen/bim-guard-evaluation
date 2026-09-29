"""
score_arch_engines.py
------------------------------------------------
Phase-2 Empirical Benchmark for BIM-Guard Architectural Compliance Compute Engines
(ARCH-EGRESS-001: EgressAnalysisEngine, ARCH-SPATIAL-001: SpatialDaylightEngine).

Evaluates the active architecture engines against grounded test scenarios with known
ground-truth compliance status, providing:
- Complete confusion matrix (TP / FP / FN / TN)
- Precision, Recall, Specificity, F1-Score, Balanced Accuracy
- Wilson score 95% confidence intervals on all metrics (via stats_util)
- Per-check-type diagnostic breakdown
- Standard JSON result persistence and baseline tracking

Usage:
    uv run python eval/score_arch_engines.py
    uv run python eval/score_arch_engines.py --json
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

_START = time.perf_counter()

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import (  # noqa: E402
    build_result,
    setup_bimguard_path,
    write_result,
)
from generate_arch_test_models import get_architectural_test_cases  # noqa: E402
from stats_util import confusion_matrix_metrics  # noqa: E402

setup_bimguard_path()


class MemoryRuleService:
    """Lightweight in-memory RuleService providing live BUILDING-CODE-PART9 rules
    without requiring an active Supabase database connection."""

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self._rules = rules or self._default_rules()

    def _default_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "id": 1,
                "ruleset_id": "BUILDING-CODE-PART9",
                "reference": "9.9.10.1",
                "property_name": "TravelDistance",
                "operator": "<=",
                "check_value": 25.0,
                "unit": "m",
                "category": "Arch",
            },
            {
                "id": 2,
                "ruleset_id": "BUILDING-CODE-PART9",
                "reference": "9.9.4.1",
                "property_name": "ExitCount",
                "operator": ">=",
                "check_value": 2.0,
                "unit": "count",
                "category": "Arch",
            },
            {
                "id": 3,
                "ruleset_id": "BUILDING-CODE-PART9",
                "reference": "9.9.10.2",
                "property_name": "EgressWindowClearArea",
                "operator": ">=",
                "check_value": 0.35,
                "unit": "m2",
                "category": "Arch",
            },
            {
                "id": 4,
                "ruleset_id": "BUILDING-CODE-PART9",
                "reference": "9.9.10.2",
                "property_name": "EgressWindowClearWidth",
                "operator": ">=",
                "check_value": 380.0,
                "unit": "mm",
                "category": "Arch",
            },
            {
                "id": 5,
                "ruleset_id": "BUILDING-CODE-PART9",
                "reference": "9.9.10.2",
                "property_name": "EgressWindowClearHeight",
                "operator": ">=",
                "check_value": 380.0,
                "unit": "mm",
                "category": "Arch",
            },
            {
                "id": 6,
                "ruleset_id": "BUILDING-CODE-PART9",
                "reference": "9.9.10.2",
                "property_name": "EgressWindowMaxSillHeight",
                "operator": "<=",
                "check_value": 1000.0,
                "unit": "mm",
                "category": "Arch",
            },
            {
                "id": 7,
                "ruleset_id": "BUILDING-CODE-PART9",
                "reference": "9.7.2.3",
                "property_name": "DaylightRatio",
                "operator": ">=",
                "check_value": 0.08,
                "unit": "ratio",
                "category": "Arch",
            },
            {
                "id": 8,
                "ruleset_id": "BUILDING-CODE-PART9",
                "reference": "9.10.9",
                "target_ifc_class": "IfcWall",
                "property_name": "FireRating",
                "operator": ">=",
                "check_value": 45.0,
                "unit": "min",
                "category": "Arch",
            },
        ]

    def list_by_ruleset(self, ruleset_id: str) -> list[dict[str, Any]]:
        return [r for r in self._rules if r.get("ruleset_id") == ruleset_id]


def load_engines():
    """Import and instantiate the architecture compliance engines."""
    from app.engines.bimguard_arch_engine import EgressAnalysisEngine, SpatialDaylightEngine

    rules_service = MemoryRuleService()
    egress_engine = EgressAnalysisEngine(rules_service=rules_service)
    spatial_engine = SpatialDaylightEngine(rules_service=rules_service)
    return egress_engine, spatial_engine


def run_benchmark() -> dict[str, Any]:
    egress_engine, spatial_engine = load_engines()
    cases = get_architectural_test_cases()

    tp = fp = fn = tn = 0
    passed_cases = 0
    failed_cases = 0
    details: list[dict[str, Any]] = []
    by_check_type: dict[str, dict[str, int]] = {}

    for case in cases:
        check_type = case["check_type"]
        if check_type not in by_check_type:
            by_check_type[check_type] = {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "total": 0}
        by_check_type[check_type]["total"] += 1

        engine = egress_engine if case["engine"] == "ARCH-EGRESS-001" else spatial_engine
        eval_res = engine.evaluate(case["element"])

        predicted_status = eval_res.status
        is_violation_predicted = (predicted_status == "FAIL")
        expected_violation = case["expected_violation"]

        is_correct = (predicted_status == case["expected_status"])
        if is_correct:
            passed_cases += 1
        else:
            failed_cases += 1

        if is_violation_predicted and expected_violation:
            tp += 1
            by_check_type[check_type]["tp"] += 1
            outcome = "TP (Correct Violation)"
        elif is_violation_predicted and not expected_violation:
            fp += 1
            by_check_type[check_type]["fp"] += 1
            outcome = "FP (False Alarm)"
        elif not is_violation_predicted and expected_violation:
            fn += 1
            by_check_type[check_type]["fn"] += 1
            outcome = "FN (Missed Violation)"
        else:
            tn += 1
            by_check_type[check_type]["tn"] += 1
            outcome = "TN (Correct Compliant)"

        details.append({
            "id": case["id"],
            "engine": case["engine"],
            "check_type": check_type,
            "expected_status": case["expected_status"],
            "predicted_status": predicted_status,
            "score": eval_res.score,
            "band": eval_res.band,
            "action": eval_res.action,
            "outcome": outcome,
            "correct": is_correct,
        })

    perf_stats = confusion_matrix_metrics(tp=tp, fp=fp, fn=fn, tn=tn, confidence=0.95)

    return {
        "total_cases": len(cases),
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "classification_metrics": perf_stats,
        "by_check_type": by_check_type,
        "details": details,
    }


def print_report(results: dict[str, Any]) -> None:
    cm = results["classification_metrics"]["confusion_matrix"]
    m = results["classification_metrics"]

    print("=" * 70)
    print("  ARCHITECTURAL COMPLIANCE ENGINE BENCHMARK (ARCH-001)")
    print("=" * 70)
    print(f"\nEvaluated Scenarios: {results['total_cases']} cases")
    print(f"Overall Accuracy:   {m['accuracy']['formatted']}")
    print(f"Recall (Sensitivity): {m['recall_sensitivity']['formatted']}")
    print(f"Precision:          {m['precision']['formatted']}")
    print(f"Specificity:        {m['specificity']['formatted']}")
    print(f"F1-Score:           {m['f1_score']['formatted']}")
    print(f"Balanced Accuracy:  {m['balanced_accuracy']['formatted']}")

    print("\nConfusion Matrix:")
    print(f"  True Positives (Violations Caught):    {cm['tp']:2d}")
    print(f"  False Positives (False Alarms):        {cm['fp']:2d}")
    print(f"  False Negatives (Missed Violations):   {cm['fn']:2d}")
    print(f"  True Negatives (Compliant Passed):     {cm['tn']:2d}")

    print("\nPer-Check Performance Breakdown:")
    for ct, counts in results["by_check_type"].items():
        total = counts["total"]
        correct = counts["tp"] + counts["tn"]
        acc = (correct / total) if total else 0.0
        print(f"  - {ct:20s}: {correct}/{total} ({acc:.0%}) [TP={counts['tp']}, TN={counts['tn']}, FP={counts['fp']}, FN={counts['fn']}]")

    print("\nIndividual Case Diagnostics:")
    for d in results["details"]:
        flag = "✓" if d["correct"] else "✗"
        print(f"  [{flag}] {d['id']:32s} -> {d['predicted_status']:4s} ({d['outcome']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="write structured results to eval/results/")
    args = parser.parse_args()

    results = run_benchmark()
    print_report(results)

    duration = time.perf_counter() - _START

    if args.json:
        m = results["classification_metrics"]
        result_dict = build_result(
            "score_arch_engines",
            tier=2,
            passed=results["passed_cases"],
            failed=results["failed_cases"],
            total=results["total_cases"],
            duration_s=duration,
            details=results,
        )
        out_path = write_result(result_dict)
        print(f"\n  JSON result written to {out_path}")
