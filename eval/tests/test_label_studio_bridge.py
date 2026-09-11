"""
eval/tests/test_label_studio_bridge.py
---------------------------------------------
Unit tests for Label Studio Bridge and Inter-Annotator Agreement (IAA) scoring.
"""

import json
from pathlib import Path

import pytest

from eval.label_studio_bridge import (
    LabelStudioBridge,
    extract_numeric_value,
    normalize_cross_ref,
)
from eval.score_iaa import (
    IAACalculator,
    compute_cohens_kappa,
    compute_fleiss_kappa,
    compute_span_f1,
    compute_span_iou,
)


def test_extract_numeric_value_single():
    val, unit, val_min, val_max = extract_numeric_value("not less than 860 mm")
    assert val == 860.0
    assert unit == "mm"
    assert val_min is None
    assert val_max is None


def test_extract_numeric_value_with_spaces():
    val, unit, val_min, val_max = extract_numeric_value("shall not be less than 2 050 mm")
    assert val == 2050.0
    assert unit == "mm"


def test_extract_numeric_value_meters():
    val, unit, val_min, val_max = extract_numeric_value("shall not exceed 3.7 m")
    assert val == 3.7
    assert unit == "m"


def test_extract_numeric_value_range():
    val, unit, val_min, val_max = extract_numeric_value("between 125 and 200 mm")
    assert val is None
    assert unit == "mm"
    assert val_min == 125.0
    assert val_max == 200.0


def test_normalize_cross_ref():
    ref_type, norm = normalize_cross_ref("Article 9.8.4.5A.")
    assert ref_type == "article"
    assert norm == "9.8.4.5A"

    ref_type2, norm2 = normalize_cross_ref("Table 3.1.17.1")
    assert ref_type2 == "table"
    assert norm2 == "3.1.17.1"


def test_sample_tasks_conversion_to_nlp():
    sample_tasks_path = Path(__file__).resolve().parent.parent.parent / "research" / "label_studio" / "sample_tasks.json"
    assert sample_tasks_path.exists()

    with open(sample_tasks_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    bridge = LabelStudioBridge()
    nlp_annotations = bridge.export_annotations_to_nlp(tasks)
    assert len(nlp_annotations) == len(tasks)

    # First task has 9.8.2.1.(1) annotations
    ann1 = nlp_annotations[0]
    assert len(ann1["deontics"]) >= 1
    assert ann1["deontics"][0]["operator"] == "SHALL"
    assert ann1["deontics"][0]["strength"] == "mandatory"
    assert len(ann1["dimensions"]) >= 1
    assert ann1["dimensions"][0]["value"] == 900.0
    assert ann1["dimensions"][0]["unit"] == "mm"
    assert ann1["dimensions"][0]["constraint"] == "min"
    assert ann1["subject"] == "IfcStairFlight"


def test_sample_tasks_conversion_to_gold_rules():
    sample_tasks_path = Path(__file__).resolve().parent.parent.parent / "research" / "label_studio" / "sample_tasks.json"
    with open(sample_tasks_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    bridge = LabelStudioBridge()
    rules = bridge.export_annotations_to_gold_rules(tasks)

    # Tasks 1, 2, and 3 have valid checkable annotations
    assert len(rules) >= 3

    r1 = rules[0]
    assert r1["ref"] == "9.8.2.1.(1)"
    assert r1["target"] == "IfcStairFlight"
    assert r1["property_name"] == "Width"
    assert r1["operator"] == ">="
    assert r1["value"] == 900.0
    assert r1["unit"] == "mm"
    assert r1["applies_when"] == {"building_use": "residential"}

    r3 = rules[2]
    assert r3["ref"] == "9.8.2.2.(2)"
    assert r3["property_name"] == "RequiredHeadroom"
    assert r3["operator"] == ">="
    assert r3["value"] == 2050.0


def test_gold_rules_to_preannotated_tasks():
    bridge = LabelStudioBridge()
    sample_gold = [
        {
            "ref": "9.8.2.1.(2)",
            "target": "IfcStairFlight",
            "property_name": "Width",
            "operator": ">=",
            "value": 860,
            "unit": "mm",
            "desc": "Required exit stairs serving a house - 860 mm",
        }
    ]

    tasks = bridge.gold_rules_to_preannotated_tasks(
        sample_gold,
        clause_texts={"9.8.2.1.(2)": "Required exit stairs serving a house shall have a width of not less than 860 mm."},
    )
    assert len(tasks) == 1
    assert tasks[0]["data"]["section_ref"] == "9.8.2.1.(2)"
    result = tasks[0]["annotations"][0]["result"]
    assert any(r.get("value", {}).get("choices") == ["IfcStairFlight"] for r in result)
    assert any(r.get("value", {}).get("choices") == ["Width"] for r in result)
    assert any("860 mm" in r.get("value", {}).get("text", "") for r in result)


def test_iaa_metrics_computation():
    # 1. Span IoU
    assert compute_span_iou((0, 10), (0, 10)) == 1.0
    assert compute_span_iou((0, 5), (5, 10)) == 0.0
    assert compute_span_iou((0, 10), (5, 15)) == 5.0 / 15.0

    # 2. Cohen's Kappa
    rater_a = ["IfcStairFlight", "IfcRailing", "IfcStairFlight", "IfcDoor"]
    rater_b = ["IfcStairFlight", "IfcRailing", "IfcStairFlight", "IfcDoor"]
    assert compute_cohens_kappa(rater_a, rater_b) == 1.0

    rater_c = ["IfcStairFlight", "IfcStairFlight", "IfcDoor", "IfcDoor"]
    kappa_ac = compute_cohens_kappa(rater_a, rater_c)
    assert -1.0 <= kappa_ac < 1.0

    # 3. Fleiss' Kappa
    # Matrix: 3 subjects, 3 raters, 2 categories
    matrix = [
        [3, 0],
        [3, 0],
        [0, 3],
    ]
    assert compute_fleiss_kappa(matrix) == 1.0

    # 4. Span F1
    spans1 = [(0, 5, "MANDATORY"), (10, 25, "DIM_MIN")]
    spans2 = [(0, 5, "MANDATORY"), (12, 25, "DIM_MIN")]
    metrics = compute_span_f1(spans1, spans2, iou_threshold=0.5)
    assert metrics["f1"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_multi_annotator_iaa_calculator():
    # Construct synthetic tasks with 2 annotators
    task = {
        "id": "t1",
        "data": {"section_ref": "9.8.2.1.(1)", "text": "shall have a clear width of not less than 900 mm"},
        "annotations": [
            {
                "id": 1,
                "completed_by": 1,
                "result": [
                    {"type": "choices", "from_name": "ifc_entity", "value": {"choices": ["IfcStairFlight"]}},
                    {"type": "choices", "from_name": "property_name", "value": {"choices": ["Width"]}},
                    {"type": "labels", "from_name": "linguistic_labels", "value": {"start": 0, "end": 5, "labels": ["MANDATORY"]}},
                ],
            },
            {
                "id": 2,
                "completed_by": 2,
                "result": [
                    {"type": "choices", "from_name": "ifc_entity", "value": {"choices": ["IfcStairFlight"]}},
                    {"type": "choices", "from_name": "property_name", "value": {"choices": ["Width"]}},
                    {"type": "labels", "from_name": "linguistic_labels", "value": {"start": 0, "end": 5, "labels": ["MANDATORY"]}},
                ],
            },
        ],
    }

    calc = IAACalculator([task])
    eval_res = calc.evaluate_pairwise(1, 2)
    assert eval_res["common_tasks_count"] == 1
    assert eval_res["categorical_cohens_kappa"]["ifc_entity"] == 1.0
    assert eval_res["categorical_cohens_kappa"]["property_name"] == 1.0
    assert eval_res["overall_span_metrics"]["f1"] == 1.0

    report = calc.print_summary_report()
    assert "# Inter-Annotator Agreement (IAA) Report" in report
    assert "Annotator 1 vs 2" in report
