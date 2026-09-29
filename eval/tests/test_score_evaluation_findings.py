"""
eval/tests/test_score_evaluation_findings.py
---------------------------------------------
Unit tests for the tool-vs-expert compliance validation matrix scoring.
"""

from pathlib import Path
import json

from eval.score_evaluation_findings import (
    evaluate_findings,
    compute_kappa_metric,
    BIMGUARD_TO_HUMAN,
)


def test_bimguard_to_human_mapping():
    assert BIMGUARD_TO_HUMAN["PASS"] == "PASS"
    assert BIMGUARD_TO_HUMAN["FAIL"] == "FAIL"
    assert BIMGUARD_TO_HUMAN["MISSING"] == "INDETERMINATE"
    assert BIMGUARD_TO_HUMAN["WAIVED"] == "NOT_APPLICABLE"
    assert BIMGUARD_TO_HUMAN["NOT_APPLICABLE"] == "NOT_APPLICABLE"


def test_compute_kappa_metric_perfect():
    pairs = [("PASS", "PASS"), ("FAIL", "FAIL"), ("PASS", "PASS")]
    assert compute_kappa_metric(pairs) == 1.0


def test_evaluate_findings_sample_fixture():
    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "evaluation_findings_sample.json"
    assert fixture_path.exists(), "Sample fixture must exist"

    with open(fixture_path, "r", encoding="utf-8") as f:
        findings = json.load(f)

    res = evaluate_findings(findings)

    assert res["sample_size"] == 38
    assert res["reviewed_count"] == 38
    cm = res["confusion_matrix"]
    assert cm["tp"] == 18
    assert cm["fp"] == 1
    assert cm["fn"] == 0
    assert cm["tn"] == 19

    assert res["accuracy"]["point"] > 0.95
    assert res["recall_sensitivity"]["point"] == 1.0
    assert res["precision"]["point"] > 0.90
    assert res["f1_score"]["point"] > 0.95
    assert res["cohens_kappa"]["point"] > 0.90
