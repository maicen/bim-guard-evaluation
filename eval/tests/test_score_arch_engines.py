"""
eval/tests/test_score_arch_engines.py
-------------------------------------
Unit tests for the architectural compliance benchmark suite (ARCH-EGRESS-001, ARCH-SPATIAL-001).
"""

from eval.score_arch_engines import run_benchmark


def test_arch_engine_benchmark_accuracy():
    results = run_benchmark()

    assert results["total_cases"] >= 20
    assert results["passed_cases"] == results["total_cases"]
    assert results["failed_cases"] == 0

    m = results["classification_metrics"]
    cm = m["confusion_matrix"]

    # Must catch all defects with zero false alarms
    assert cm["tp"] >= 10
    assert cm["tn"] >= 5
    assert cm["fp"] == 0
    assert cm["fn"] == 0

    assert m["accuracy"]["point"] == 1.0
    assert m["recall_sensitivity"]["point"] == 1.0
    assert m["precision"]["point"] == 1.0
    assert m["f1_score"]["point"] == 1.0

    # Check types coverage
    by_type = results["by_check_type"]
    assert "travel_distance" in by_type
    assert "exit_count" in by_type
    assert "egress_window" in by_type
    assert "daylight_ratio" in by_type
    assert "fire_separation" in by_type
