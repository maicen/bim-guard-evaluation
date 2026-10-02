"""
eval/tests/test_label_studio_bridge.py
---------------------------------------------
Unit tests for Label Studio Bridge and Inter-Annotator Agreement (IAA) scoring.
"""

import json
from pathlib import Path

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


def test_extract_numeric_value_to_range():
    assert extract_numeric_value("865 mm to 1 070 mm") == (None, "mm", 865.0, 1070.0)
    assert extract_numeric_value("30-45 degrees") == (None, "degrees", 30.0, 45.0)


def test_extract_numeric_value_slope_ratio():
    assert extract_numeric_value("not exceed 1 in 50") == (0.02, "ratio", None, None)
    assert extract_numeric_value("1 in 8") == (0.125, "ratio", None, None)


def test_extract_numeric_value_load_units():
    assert extract_numeric_value("not less than 0.7 kN/m") == (0.7, "kN/m", None, None)
    assert extract_numeric_value("1.9 kPa") == (1.9, "kPa", None, None)
    # The first quantity with a unit is the constrained one, not the trailing dimension.
    val, unit, _, _ = extract_numeric_value("0.5 kN applied over a maximum width of 300 mm")
    assert (val, unit) == (0.5, "kN")


def test_extract_numeric_value_counts_and_rates():
    assert extract_numeric_value("at least three risers") == (3.0, None, None, None)
    assert extract_numeric_value("no fewer than two No. 8 wood screws") == (2.0, None, None, None)
    assert extract_numeric_value("8 mm per person") == (8.0, "mm/person", None, None)


def _span(text, sub, label, nth=1):
    start = -1
    for _ in range(nth):
        start = text.index(sub, start + 1)
    return {"type": "labels", "from_name": "linguistic_labels", "to_name": "text",
            "value": {"start": start, "end": start + len(sub), "text": sub, "labels": [label]}}


def _choice(name, value):
    return {"type": "choices", "from_name": name, "to_name": "text", "value": {"choices": [value]}}


def _task(ref, text, result):
    return {"data": {"section_ref": ref, "text": text}, "annotations": [{"result": result}]}


def test_gold_rules_one_per_dimension_with_bound_conditions():
    text = ("The clear height over ramps shall be not less than, (a) 1 950 mm for ramps serving a "
            "house or an individual dwelling unit , and (b) 2 050 mm for ramps not serving a house "
            "or an individual dwelling unit .")
    task = _task("9.8.5.3.(1)", text, [
        _span(text, "shall", "MANDATORY"),
        _span(text, "1 950 mm", "DIM_MIN"),
        _span(text, "for ramps serving a house or an individual dwelling unit", "APPLICABILITY"),
        _span(text, "2 050 mm", "DIM_MIN"),
        _span(text, "for ramps not serving a house or an individual dwelling unit", "APPLICABILITY"),
        _choice("ifc_entity", "IfcRampFlight"),
        _choice("property_name", "RequiredHeadroom"),
        _choice("unit", "mm"),
    ])
    rules = LabelStudioBridge.export_annotations_to_gold_rules([task])
    assert [(r["value"], r["applies_when"]["building_use"]) for r in rules] == [
        (1950.0, "dwelling_unit"),
        (2050.0, "non_dwelling_unit"),
    ]
    assert rules[1]["conditions"] == ["for ramps not serving a house or an individual dwelling unit"]


def test_gold_rules_preamble_scope_applies_to_every_dimension():
    text = ("Stair treads within dwelling units shall be not less than 25 mm actual thickness, except "
            "that if open risers are used, the treads shall be not less than 38 mm actual thickness.")
    task = _task("9.8.9.5.(1)", text, [
        _span(text, "within dwelling units", "APPLICABILITY"),
        _span(text, "not less than 25 mm", "DIM_MIN"),
        _span(text, "except that if open risers are used", "EXCEPTION"),
        _span(text, "not less than 38 mm", "DIM_MIN"),
        _choice("property_name", "TreadThickness"),
    ])
    r25, r38 = LabelStudioBridge.parse_task_to_gold_rules(task)
    assert r25["applies_when"] == r38["applies_when"] == {"building_use": "dwelling_unit"}
    assert r25["exceptions"] == ["except that if open risers are used"]
    assert "exceptions" not in r38


def test_gold_rules_negated_residential_scope():
    text = "Public stairs serving buildings of other than residential occupancy shall be not less than 900 mm wide."
    task = _task("9.8.2.1.(3)", text, [
        _span(text, "serving buildings of other than residential occupancy", "APPLICABILITY"),
        _span(text, "not less than 900 mm", "DIM_MIN"),
    ])
    (rule,) = LabelStudioBridge.parse_task_to_gold_rules(task)
    assert rule["applies_when"] == {"building_use": "non_residential"}


def test_gold_rules_range_and_relative_bounds():
    rng_text = "Handrails shall be 865 mm to 1 070 mm high."
    (rng,) = LabelStudioBridge.parse_task_to_gold_rules(
        _task("9.8.7.4.(2)", rng_text, [_span(rng_text, "865 mm to 1 070 mm", "DIM_RANGE")]))
    assert (rng["operator"], rng["value_min"], rng["value_max"]) == ("between", 865.0, 1070.0)

    rel_text = "The depth of a rectangular tread shall be not less than its run and not more than its run plus 25 mm."
    (rel,) = LabelStudioBridge.parse_task_to_gold_rules(_task("9.8.4.2.(2)", rel_text, [
        _span(rel_text, "not less than its run", "DIM_MIN"),
        _span(rel_text, "not more than its run plus 25 mm", "DIM_MAX"),
        _choice("property_name", "TreadLength"),
    ]))
    assert rel["operator"] == "between"
    assert (rel["value_min_property"], rel["value_min_offset"]) == ("Run", 0)
    assert (rel["value_max_property"], rel["value_max_offset"]) == ("Run", 25.0)
    assert "value" not in rel


def test_gold_rules_table_row_labels_bind_forward():
    text = ("Guards within dwelling units 0.5 kN/m or concentrated load of 1.0 kN "
            "All other guards 0.75 kN/m or concentrated load of 1.0 kN")
    task = _task("Table under 9.8.8.2", text, [
        _span(text, "Guards within dwelling units", "APPLICABILITY"),
        _span(text, "0.5 kN/m", "DIM_MIN"),
        _span(text, "1.0 kN", "DIM_MIN", 1),
        _span(text, "All other guards", "APPLICABILITY"),
        _span(text, "0.75 kN/m", "DIM_MIN"),
        _span(text, "1.0 kN", "DIM_MIN", 2),
    ])
    rules = LabelStudioBridge.parse_task_to_gold_rules(task)
    assert [(r["value"], r["unit"], r["conditions"][0]) for r in rules] == [
        (0.5, "kN/m", "Guards within dwelling units"),
        (1.0, "kN", "Guards within dwelling units"),
        (0.75, "kN/m", "All other guards"),
        (1.0, "kN", "All other guards"),
    ]


def _dim_prop(span_item, prop, with_id=True):
    item = {"type": "choices", "from_name": "dim_property", "to_name": "text",
            "value": {**{k: span_item["value"][k] for k in ("start", "end", "text")}, "choices": [prop]}}
    if with_id:
        item["id"] = span_item["id"]
    return item


def test_gold_rules_per_dimension_property_overrides_task_property():
    text = ("Spiral stairs shall have, (a) handrails on both sides, the outer handrail being not less "
            "than 1 070 mm high, (b) a clear width not less than 660 mm between handrails, (c) risers "
            "that are not more than 240 mm high.")
    handrail = {**_span(text, "not less than 1 070 mm", "DIM_MIN"), "id": "r1"}
    width = {**_span(text, "not less than 660 mm", "DIM_MIN"), "id": "r2"}
    riser = {**_span(text, "not more than 240 mm", "DIM_MAX"), "id": "r3"}
    task = _task("9.8.4.5A.(1)", text, [
        handrail, width, riser,
        _dim_prop(handrail, "HandrailHeight"),
        _dim_prop(riser, "RiserHeight", with_id=False),  # offsets-only fallback
        _choice("property_name", "ClearWidth"),
    ])
    rules = LabelStudioBridge.parse_task_to_gold_rules(task)
    assert [(r["property_name"], r["value"]) for r in rules] == [
        ("HandrailHeight", 1070.0),
        ("ClearWidth", 660.0),  # no per-dimension choice -> task-level property
        ("RiserHeight", 240.0),
    ]

    nlp = LabelStudioBridge.parse_task_to_nlp_annotation(task)
    assert [d.get("property_name") for d in nlp["dimensions"]] == ["HandrailHeight", None, "RiserHeight"]


def test_gold_rules_roundtrip_keeps_dimension_property():
    gold = [{"ref": "9.8.9.4.(1)", "target": "IfcStairFlight", "property_name": "StringerDepth",
             "operator": ">=", "value": 235, "unit": "mm"}]
    tasks = LabelStudioBridge.gold_rules_to_preannotated_tasks(
        gold, clause_texts={"9.8.9.4.(1)": "an overall depth of not less than 235 mm"})
    (rule,) = LabelStudioBridge.export_annotations_to_gold_rules(tasks)
    assert (rule["property_name"], rule["value"]) == ("StringerDepth", 235.0)


def test_iaa_ignores_per_region_choices_at_task_level():
    task = {"id": "t1", "data": {"text": "not less than 900 mm"}, "annotations": [{
        "completed_by": 1,
        "result": [
            _choice("property_name", "Width"),
            {"type": "choices", "from_name": "dim_property", "id": "r1",
             "value": {"start": 0, "end": 20, "text": "not less than 900 mm", "choices": ["GuardHeight"]}},
        ],
    }]}
    ratings = IAACalculator([task]).extract_annotator_ratings()
    assert ratings[1]["t1"]["choices"] == {"property_name": "Width"}


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

    with open(sample_tasks_path, encoding="utf-8") as f:
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
    with open(sample_tasks_path, encoding="utf-8") as f:
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


def test_gold_rules_bound_relative_to_another_element():
    text = ("Landings shall be, (a) at least as wide as the width of the stair or ramp in which they occur, "
            "and (b) at least as long as the width of the stair or ramp in which they occur.")
    task = _task("9.8.6.2.(1)", text, [
        _span(text, "at least as wide as the width of the stair or ramp in which they occur", "DIM_MIN"),
        _span(text, "at least as long as the width of the stair or ramp in which they occur", "DIM_MIN"),
        _choice("ifc_entity", "IfcSlab"),
        _choice("property_name", "LandingDimension"),
    ])
    rules = LabelStudioBridge.parse_task_to_gold_rules(task)
    assert [(r["operator"], r["value_min_property"], r["value_min_offset"]) for r in rules] == [
        (">=", "StairOrRampWidth", 0),
        (">=", "StairOrRampWidth", 0),
    ]
    assert all("value" not in r for r in rules)


def test_gold_rules_handrail_count_from_words():
    text = "Spiral stairs shall have, (a) handrails on both sides, the outer handrail being not less than 1 070 mm high."
    task = _task("9.8.4.5A.(1)", text, [
        {**_span(text, "handrails on both sides", "DIM_MIN"), "id": "c1"},
        _span(text, "not less than 1 070 mm", "DIM_MIN"),
        {"id": "c1", "type": "choices", "from_name": "dim_property", "to_name": "text",
         "value": {"start": text.index("handrails on both sides"), "end": text.index("handrails on both sides") + 23,
                   "choices": ["HandrailCount"]}},
        _choice("property_name", "HandrailHeight"),
        _choice("unit", "mm"),
    ])
    count, height = LabelStudioBridge.parse_task_to_gold_rules(task)
    assert (count["property_name"], count["value"], count["unit"]) == ("HandrailCount", 2.0, None)
    assert (height["property_name"], height["value"]) == ("HandrailHeight", 1070.0)
