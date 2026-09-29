"""
eval/tests/test_score_iaa.py
---------------------------------------------
Unit tests for Inter-Annotator Agreement scoring on dual_annotator_corpus.json.
"""

import json
from pathlib import Path

from eval.score_iaa import (
    IAACalculator,
    compute_cohens_kappa,
    compute_fleiss_kappa,
    compute_span_iou,
    compute_span_f1,
)


def test_compute_span_iou():
    assert compute_span_iou((0, 10), (0, 10)) == 1.0
    assert compute_span_iou((0, 10), (10, 20)) == 0.0
    assert compute_span_iou((0, 10), (5, 15)) == 5.0 / 15.0


def test_compute_cohens_kappa():
    # Perfect agreement
    assert compute_cohens_kappa(["A", "B", "A"], ["A", "B", "A"]) == 1.0
    # Partial agreement
    k = compute_cohens_kappa(["A", "B", "A", "B"], ["A", "A", "A", "B"])
    assert 0.0 <= k <= 1.0


def test_compute_fleiss_kappa():
    # 2 items, 2 categories, 3 raters all agreeing
    matrix = [
        [3, 0],
        [0, 3],
    ]
    assert compute_fleiss_kappa(matrix) == 1.0


def test_iaa_calculator_on_dual_corpus():
    corpus_path = Path(__file__).resolve().parent.parent.parent / "research" / "annotations" / "dual_annotator_corpus.json"
    assert corpus_path.exists(), "dual_annotator_corpus.json must exist"

    with open(corpus_path, encoding="utf-8") as f:
        tasks = json.load(f)

    assert len(tasks) == 30
    calc = IAACalculator(tasks)
    res = calc.generate_full_results()

    assert res["total_tasks"] == 30
    assert res["annotators"] == [1, 2, 3]

    pair_1_2 = res["pairwise_evaluations"]["1_vs_2"]
    assert pair_1_2["common_tasks_count"] == 30
    assert pair_1_2["categorical_cohens_kappa"]["ifc_entity"] > 0.85
    assert pair_1_2["overall_span_metrics_iou_05"]["f1"] > 0.70

    fleiss = res["multi_rater_fleiss_kappa"]
    assert "ifc_entity" in fleiss
    assert fleiss["ifc_entity"]["kappa"] > 0.85
