"""
stats_util.py
------------------------------------------------
Statistical rigor utilities for BIM-Guard evaluation harnesses.

Provides:
- Wilson score confidence intervals for binomial proportions (accuracy, recall, precision, specificity).
- Non-parametric bootstrap confidence intervals for arbitrary metrics across paired samples.
- Complete confusion matrix reduction with 95% confidence intervals on all core classification metrics.
- CI formatting helpers for reporting in CLI tables and markdown research ledgers.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Any


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calculate the Wilson score confidence interval for a binomial proportion.

    Handles small sample sizes (n < 30) and extreme proportions (p = 0 or p = 1)
    correctly, unlike the normal approximation (Wald interval).

    Returns:
        (lower_bound, upper_bound) bounded within [0.0, 1.0].
    """
    if total <= 0:
        return (0.0, 0.0)

    p = successes / total

    # Two-tailed standard normal quantiles:
    # 0.90 -> 1.6449, 0.95 -> 1.95996, 0.99 -> 2.5758
    if confidence == 0.95:
        z = 1.95996398454
    elif confidence == 0.90:
        z = 1.64485362695
    elif confidence == 0.99:
        z = 2.57582930355
    else:
        # Approximate standard normal quantile
        z = math.sqrt(2.0) * _erf_inv(confidence)

    denominator = 1.0 + (z**2) / total
    centre_adjusted = p + (z**2) / (2.0 * total)
    variance_term = z * math.sqrt((p * (1.0 - p) / total) + (z**2 / (4.0 * total**2)))

    lower = max(0.0, (centre_adjusted - variance_term) / denominator)
    upper = min(1.0, (centre_adjusted + variance_term) / denominator)
    return round(lower, 4), round(upper, 4)


def _erf_inv(p: float) -> float:
    """Winitzki approximation of inverse error function for arbitrary confidence levels."""
    a = 0.147
    sgn = 1.0 if p >= 0 else -1.0
    p = abs(p)
    term1 = 2.0 / (math.pi * a) + math.log(1.0 - p**2) / 2.0
    term2 = math.log(1.0 - p**2) / a
    val = math.sqrt(term1**2 - term2)
    return sgn * math.sqrt(val - term1)


def bootstrap_ci(
    items: list[Any],
    metric_fn: Callable[[list[Any]], float],
    n_resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Calculate non-parametric bootstrap confidence interval for any metric function.

    Returns:
        (point_estimate, lower_ci, upper_ci)
    """
    if not items:
        return (0.0, 0.0, 0.0)

    point_estimate = metric_fn(items)
    n = len(items)
    if n == 1:
        return (point_estimate, point_estimate, point_estimate)

    rng = random.Random(seed)
    boot_stats: list[float] = []

    for _ in range(n_resamples):
        sample = [items[rng.randint(0, n - 1)] for _ in range(n)]
        try:
            stat = metric_fn(sample)
            if not math.isnan(stat):
                boot_stats.append(stat)
        except Exception:
            continue

    if not boot_stats:
        return (point_estimate, point_estimate, point_estimate)

    boot_stats.sort()
    alpha = (1.0 - confidence) / 2.0
    lower_idx = int(alpha * len(boot_stats))
    upper_idx = int((1.0 - alpha) * len(boot_stats))
    upper_idx = min(upper_idx, len(boot_stats) - 1)

    return (
        round(point_estimate, 4),
        round(boot_stats[lower_idx], 4),
        round(boot_stats[upper_idx], 4),
    )


def format_ci(estimate: float, lower: float, upper: float, as_percent: bool = True) -> str:
    """Format a point estimate with confidence interval for display."""
    if as_percent:
        return f"{estimate:.1%} [95% CI: {lower:.1%} – {upper:.1%}]"
    return f"{estimate:.3f} [95% CI: {lower:.3f} – {upper:.3f}]"


def confusion_matrix_metrics(tp: int, fp: int, fn: int, tn: int, confidence: float = 0.95) -> dict[str, Any]:
    """Compute complete classification performance metrics with Wilson score confidence intervals.

    Convention:
    - Positive (P) = Violation condition (defective/non-compliant element).
    - Negative (N) = Compliant element.
    - TP: Correctly flagged violation.
    - FP: Erroneous false alarm on compliant element.
    - FN: Missed violation.
    - TN: Correctly passed compliant element.
    """
    total = tp + fp + fn + tn
    total_pos = tp + fn
    total_neg = tn + fp
    predicted_pos = tp + fp

    accuracy_pt = (tp + tn) / total if total else 0.0
    acc_lo, acc_hi = wilson_score_interval(tp + tn, total, confidence)

    recall_pt = tp / total_pos if total_pos else 0.0
    rec_lo, rec_hi = wilson_score_interval(tp, total_pos, confidence)

    precision_pt = tp / predicted_pos if predicted_pos else 0.0
    prec_lo, prec_hi = wilson_score_interval(tp, predicted_pos, confidence)

    specificity_pt = tn / total_neg if total_neg else 0.0
    spec_lo, spec_hi = wilson_score_interval(tn, total_neg, confidence)

    f1_pt = (2 * precision_pt * recall_pt / (precision_pt + recall_pt)) if (precision_pt + recall_pt) else 0.0
    # Conservative F1 interval derived from harmonic mean bounds:
    f1_lo = (2 * prec_lo * rec_lo / (prec_lo + rec_lo)) if (prec_lo + rec_lo) else 0.0
    f1_hi = (2 * prec_hi * rec_hi / (prec_hi + rec_hi)) if (prec_hi + rec_hi) else 0.0

    balanced_acc_pt = (recall_pt + specificity_pt) / 2.0
    balanced_acc_lo = (rec_lo + spec_lo) / 2.0
    balanced_acc_hi = (rec_hi + spec_hi) / 2.0

    return {
        "confusion_matrix": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "total": total,
            "actual_positives": total_pos,
            "actual_negatives": total_neg,
        },
        "accuracy": {"point": round(accuracy_pt, 4), "ci_lower": acc_lo, "ci_upper": acc_hi, "formatted": format_ci(accuracy_pt, acc_lo, acc_hi)},
        "recall_sensitivity": {"point": round(recall_pt, 4), "ci_lower": rec_lo, "ci_upper": rec_hi, "formatted": format_ci(recall_pt, rec_lo, rec_hi)},
        "precision": {"point": round(precision_pt, 4), "ci_lower": prec_lo, "ci_upper": prec_hi, "formatted": format_ci(precision_pt, prec_lo, prec_hi)},
        "specificity": {"point": round(specificity_pt, 4), "ci_lower": spec_lo, "ci_upper": spec_hi, "formatted": format_ci(specificity_pt, spec_lo, spec_hi)},
        "f1_score": {"point": round(f1_pt, 4), "ci_lower": round(f1_lo, 4), "ci_upper": round(f1_hi, 4), "formatted": format_ci(f1_pt, f1_lo, f1_hi)},
        "balanced_accuracy": {"point": round(balanced_acc_pt, 4), "ci_lower": round(balanced_acc_lo, 4), "ci_upper": round(balanced_acc_hi, 4), "formatted": format_ci(balanced_acc_pt, balanced_acc_lo, balanced_acc_hi)},
    }
