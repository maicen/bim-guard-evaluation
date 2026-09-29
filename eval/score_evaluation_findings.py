"""
eval/score_evaluation_findings.py
------------------------------------------------
Phase-1 / Tier-1 evaluation harness for BIM-Guard compliance findings validation.

Computes:
1. Tool-vs-Expert 2x2 Confusion Matrix (TP, FP, FN, TN at action threshold FAIL).
2. Binary classification metrics with 95% Wilson Score Confidence Intervals
   (Accuracy, Sensitivity/Recall, Precision, Specificity, F1 Score).
3. Multi-class Cohen's Kappa (κ) inter-rater agreement with 95% non-parametric
   bootstrap confidence intervals.

Evaluates against offline ground-truth fixtures (eval/fixtures/evaluation_findings_sample.json)
or live endpoints (GET /api/evaluation/findings?project_id=...).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_START = time.perf_counter()

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import build_result, write_result  # noqa: E402
from env_snapshot import get_environment_snapshot  # noqa: E402
from stats_util import bootstrap_ci, confusion_matrix_metrics, format_ci  # noqa: E402

FIXTURE_PATH = EVAL_DIR / "fixtures" / "evaluation_findings_sample.json"

BIMGUARD_TO_HUMAN = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "MISSING": "INDETERMINATE",
    "WAIVED": "NOT_APPLICABLE",
    "NOT_APPLICABLE": "NOT_APPLICABLE",
}


def compute_kappa_metric(pairs: list[tuple[str, str]]) -> float:
    """Compute Cohen's Kappa for a list of (bimguard_mapped, human_verdict) pairs."""
    if not pairs:
        return 0.0

    n = len(pairs)
    agreed = sum(1 for bg, h in pairs if bg == h)
    p_o = agreed / n

    cat_counts_bg: dict[str, int] = {}
    cat_counts_human: dict[str, int] = {}
    for bg, h in pairs:
        cat_counts_bg[bg] = cat_counts_bg.get(bg, 0) + 1
        cat_counts_human[h] = cat_counts_human.get(h, 0) + 1

    all_cats = set(cat_counts_bg.keys()) | set(cat_counts_human.keys())
    p_e = sum(
        (cat_counts_bg.get(c, 0) / n) * (cat_counts_human.get(c, 0) / n)
        for c in all_cats
    )

    if abs(1.0 - p_e) < 1e-9:
        return 1.0 if abs(p_o - 1.0) < 1e-9 else 0.0
    return (p_o - p_e) / (1.0 - p_e)


def evaluate_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a list of captured findings against expert human verdicts."""
    reviewed = [f for f in findings if f.get("human_verdict")]
    pairs: list[tuple[str, str]] = []

    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for f in reviewed:
        bg_raw = str(f.get("bimguard_verdict") or "NOT_APPLICABLE").upper()
        bg_mapped = BIMGUARD_TO_HUMAN.get(bg_raw, bg_raw)
        hv = str(f.get("human_verdict") or "").upper()
        pairs.append((bg_mapped, hv))

        # Binary confusion matrix (violation = FAIL, compliant = PASS)
        if bg_raw == "FAIL" and hv == "FAIL":
            tp += 1
        elif bg_raw == "FAIL" and hv == "PASS":
            fp += 1
        elif bg_raw == "PASS" and hv == "FAIL":
            fn += 1
        elif bg_raw == "PASS" and hv == "PASS":
            tn += 1

    # Wilson score metrics
    metrics = confusion_matrix_metrics(tp, fp, fn, tn, confidence=0.95)

    # Bootstrap CI for Cohen's Kappa
    kappa_pt, kappa_lo, kappa_hi = bootstrap_ci(
        pairs,
        metric_fn=compute_kappa_metric,
        n_resamples=1000,
        confidence=0.95,
        seed=42,
    )

    return {
        "sample_size": len(findings),
        "reviewed_count": len(reviewed),
        "confusion_matrix": metrics["confusion_matrix"],
        "accuracy": metrics["accuracy"],
        "recall_sensitivity": metrics["recall_sensitivity"],
        "precision": metrics["precision"],
        "specificity": metrics["specificity"],
        "f1_score": metrics["f1_score"],
        "cohens_kappa": {
            "point": kappa_pt,
            "ci_lower": kappa_lo,
            "ci_upper": kappa_hi,
            "formatted": format_ci(kappa_pt, kappa_lo, kappa_hi, as_percent=False),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate tool-vs-expert compliance validation matrix.")
    parser.add_argument("--json", action="store_true", help="Emit JSON manifest and persist result")
    parser.add_argument("--file", type=str, default=str(FIXTURE_PATH), help="Path to findings JSON fixture")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: Fixture file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        findings = json.load(f)

    results = evaluate_findings(findings)
    duration_s = time.perf_counter() - _START

    print(f"\n{'=' * 75}")
    print("  TOOL-VS-EXPERT VALIDATION MATRIX (ARCHITECTURAL COMPLIANCE)")
    print(f"{'=' * 75}")
    print(f"  Sample evaluated   : {results['reviewed_count']} / {results['sample_size']} findings")
    print(f"  True Positives (TP): {results['confusion_matrix']['tp']}")
    print(f"  False Positives(FP): {results['confusion_matrix']['fp']}")
    print(f"  False Negatives(FN): {results['confusion_matrix']['fn']}")
    print(f"  True Negatives (TN): {results['confusion_matrix']['tn']}")
    print(f"  {'-' * 71}")
    print(f"  Accuracy           : {results['accuracy']['formatted']}")
    print(f"  Precision (PPV)    : {results['precision']['formatted']}")
    print(f"  Recall (Sens.)     : {results['recall_sensitivity']['formatted']}")
    print(f"  Specificity (TNR)  : {results['specificity']['formatted']}")
    print(f"  F1 Score           : {results['f1_score']['formatted']}")
    print(f"  Cohen's Kappa (κ)  : {results['cohens_kappa']['formatted']}")
    print(f"{'=' * 75}\n")

    if args.json:
        env = get_environment_snapshot()
        metrics_dict = {
            "accuracy": results["accuracy"]["point"],
            "precision": results["precision"]["point"],
            "recall": results["recall_sensitivity"]["point"],
            "specificity": results["specificity"]["point"],
            "f1_score": results["f1_score"]["point"],
            "cohens_kappa": results["cohens_kappa"]["point"],
            "sample_size": results["reviewed_count"],
        }
        res_payload = build_result(
            eval_id="score_evaluation_findings",
            metrics=metrics_dict,
            duration_s=duration_s,
            extra={
                "confusion_matrix": results["confusion_matrix"],
                "cohens_kappa_ci": [results["cohens_kappa"]["ci_lower"], results["cohens_kappa"]["ci_upper"]],
                "env_snapshot": env,
            },
        )
        out_path = write_result(res_payload)
        print(f"Result written to {out_path}")


if __name__ == "__main__":
    main()
