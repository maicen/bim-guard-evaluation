"""
eval/tests/test_stats_util.py
-----------------------------
Unit tests for stats_util.py: Wilson score intervals, bootstrap CIs, and confusion matrix reductions.
"""

import pytest

from eval.stats_util import (
    bootstrap_ci,
    confusion_matrix_metrics,
    format_ci,
    wilson_score_interval,
)


def test_wilson_score_interval_bounds():
    # 0/10 -> lower should be 0.0, upper > 0
    lo, hi = wilson_score_interval(0, 10, confidence=0.95)
    assert lo == 0.0
    assert 0.0 < hi <= 0.35

    # 10/10 -> lower < 1.0, upper should be 1.0
    lo, hi = wilson_score_interval(10, 10, confidence=0.95)
    assert 0.65 <= lo < 1.0
    assert hi == 1.0

    # 50/100 -> symmetric around 0.50
    lo, hi = wilson_score_interval(50, 100, confidence=0.95)
    assert 0.39 <= lo <= 0.41
    assert 0.59 <= hi <= 0.61
    assert lo < 0.50 < hi


def test_wilson_score_empty():
    lo, hi = wilson_score_interval(0, 0)
    assert lo == 0.0
    assert hi == 0.0


def test_bootstrap_ci():
    items = [1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0]

    def mean_fn(vals):
        return sum(vals) / len(vals)

    pt, lo, hi = bootstrap_ci(items, mean_fn, n_resamples=500, confidence=0.95, seed=123)
    assert pt == 0.75
    assert 0.40 <= lo <= 0.75
    assert 0.75 <= hi <= 1.0


def test_confusion_matrix_metrics():
    # TP=20, FP=2, FN=5, TN=23 (Total=50)
    metrics = confusion_matrix_metrics(tp=20, fp=2, fn=5, tn=23)

    assert metrics["confusion_matrix"]["tp"] == 20
    assert metrics["confusion_matrix"]["actual_positives"] == 25
    assert metrics["confusion_matrix"]["actual_negatives"] == 25

    # Recall: 20/25 = 0.80
    assert metrics["recall_sensitivity"]["point"] == 0.80
    assert metrics["recall_sensitivity"]["ci_lower"] < 0.80 < metrics["recall_sensitivity"]["ci_upper"]

    # Precision: 20/22 = 0.9091
    assert pytest.approx(metrics["precision"]["point"], 0.001) == 0.9091
    assert metrics["precision"]["ci_lower"] < 0.9091 < metrics["precision"]["ci_upper"]

    # F1 score should be between recall and precision
    assert 0.80 <= metrics["f1_score"]["point"] <= 0.91

    # Formatted strings exist
    assert "95% CI:" in metrics["f1_score"]["formatted"]


def test_format_ci():
    s_pct = format_ci(0.852, 0.713, 0.931, as_percent=True)
    assert s_pct == "85.2% [95% CI: 71.3% – 93.1%]"

    s_num = format_ci(0.852, 0.713, 0.931, as_percent=False)
    assert s_num == "0.852 [95% CI: 0.713 – 0.931]"
