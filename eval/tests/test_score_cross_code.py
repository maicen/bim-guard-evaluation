"""
eval/tests/test_score_cross_code.py
---------------------------------------------
Unit tests for cross-jurisdiction generalization benchmark (OBC vs. SBC).
"""

from eval.score_cross_code import (
    run_cross_code_benchmark,
    score_jurisdiction_extraction,
)
from eval.eval_gold_sbc_chapter10 import GOLD_RULES as SBC_GOLD_RULES


def test_sbc_gold_rules_loaded():
    assert len(SBC_GOLD_RULES) >= 20
    for r in SBC_GOLD_RULES:
        assert "clause_ref" in r
        assert "target_entity" in r
        assert "property_name" in r
        assert "operator" in r


def test_score_cross_code_benchmark():
    res = run_cross_code_benchmark()
    assert "obc_results" in res
    assert "sbc_results" in res
    assert "generalization_summary" in res
    assert "provenance" in res

    summary = res["generalization_summary"]
    assert summary["delta_f1"] < 0.05
    assert "PASS" in summary["generalization_status"]
