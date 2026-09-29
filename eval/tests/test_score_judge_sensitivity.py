"""
eval/tests/test_score_judge_sensitivity.py
---------------------------------------------
Unit tests for score_judge_sensitivity.py.
"""

from eval.score_judge_sensitivity import (
    calculate_pearson_r,
    calculate_spearman_rho,
    evaluate_human_calibration,
    evaluate_threshold_sweep,
    evaluate_variance_and_stability,
    generate_benchmark_report,
)


import pytest

def test_correlations():
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert calculate_pearson_r(x, y) == pytest.approx(1.0)
    assert calculate_spearman_rho(x, y) == pytest.approx(1.0)


def test_benchmark_report_generation():
    res = generate_benchmark_report()
    assert "calibration" in res
    assert "variance_and_stability" in res
    assert "threshold_sensitivity_sweep" in res
    assert "provenance" in res

    cal = res["calibration"]
    assert cal["spearman_rho"] > 0.90
    assert cal["pearson_r"] > 0.90

    sweep = res["threshold_sensitivity_sweep"]
    assert 2 in sweep and 3 in sweep and 4 in sweep and 5 in sweep
    # At tau=4, precision should be higher than at tau=2
    assert sweep[4]["precision"]["point"] >= sweep[2]["precision"]["point"]
