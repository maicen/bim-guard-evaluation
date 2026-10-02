"""Tests for the extraction-vs-human scorer and the e2e draft->clause mapping."""

import json

from eval.e2e.extraction_confusion_e2e import drafts_to_rules, newest_run, resolve_clause
from eval.score_extraction_vs_human import (
    is_dimensional,
    normalize_ref,
    refs_agree,
    score,
    values_agree,
)


def test_normalize_ref_variants():
    assert normalize_ref("Sentence 9.8.2.1.(1)") == "9.8.2.1.(1)"
    assert normalize_ref("9.8.2.1(1)") == "9.8.2.1.(1)"
    assert normalize_ref("9.8.5.4.(1)(b)") == "9.8.5.4.(1)"
    assert normalize_ref("Table under 9.8.8.2") == "table:9.8.8.2"
    assert normalize_ref("Note to Table 9.8.4.1.(1)") == "note:9.8.4.1.(1)"


def test_refs_agree_article_covers_sentence_but_tables_match_exactly():
    assert refs_agree("9.8.2.1.(1)", "9.8.2.1")
    assert not refs_agree("9.8.8.2.(1)", "table:9.8.8.2")
    assert not refs_agree("9.8.2.1.(1)", "9.8.2.1.(2)")


def test_values_agree_across_units():
    assert values_agree({"operator": "<=", "value": 3.7, "unit": "m"},
                        {"operator": "<=", "check_value": 3700, "unit": "mm"})
    assert not values_agree({"operator": ">=", "value": 900, "unit": "mm"},
                            {"operator": ">=", "value": 860, "unit": "mm"})


def test_is_dimensional():
    assert is_dimensional({"operator": ">=", "value": 900, "unit": "mm"})
    assert is_dimensional({"operator": "between", "value_min": 865, "value_max": 1070, "unit": "mm"})
    assert not is_dimensional({"operator": "exists", "value": None})


def _human_export(tmp_path):
    text = "Required exit stairs shall have a width of not less than 860 mm."
    start = text.index("not less than 860 mm")
    tasks = [
        {"data": {"section_ref": "9.8.2.1.(2)", "text": text}, "annotations": [{"result": [
            {"type": "labels", "from_name": "linguistic_labels", "to_name": "text",
             "value": {"start": start, "end": start + 20, "text": "not less than 860 mm", "labels": ["DIM_MIN"]}},
            {"type": "choices", "from_name": "property_name", "to_name": "text", "value": {"choices": ["Width"]}},
        ]}]},
        {"data": {"section_ref": "9.8.4.7.(1)", "text": "Interior stairways shall be protected from ice."},
         "annotations": [{"result": []}]},
    ]
    path = tmp_path / "human.json"
    path.write_text(json.dumps(tasks))
    return path


def test_score_confusion_matrices(tmp_path):
    human = _human_export(tmp_path)
    extracted = tmp_path / "extracted.json"
    extracted.write_text(json.dumps({"rules": [
        {"ref": "9.8.2.1.(2)", "target_ifc_class": "IfcStairFlight", "property_name": "Width",
         "operator": ">=", "check_value": 860, "unit": "mm"},
        {"ref": "9.8.4.7.(1)", "target_ifc_class": "IfcStairFlight", "property_name": "Width",
         "operator": "<=", "check_value": 1, "unit": "mm"},
        {"ref": "9.8.4.7.(1)", "operator": "exists", "property_name": "IceProtection"},
    ]}))
    res = score(human, extracted)
    c = res["clause_level"]
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (1, 1, 0, 0)
    assert res["rule_level"]["lenient"]["tp"] == 1
    assert res["rule_level"]["lenient"]["fp"] == 1
    assert res["extracted_rules_total"] == 3 and res["extracted_rules"] == 2


def test_resolve_clause_and_newest_run():
    index = [("9.8.3.3.(1)", "The vertical height of a flight shall not exceed 3.7 m.")]
    by_id = {"clause": {"clause_id": "9.8.3.3.(1)"}, "proposed_rule": {"rule_id": "REQ-AI-x"}}
    by_snippet = {"source_snippet": "height of a flight shall not exceed 3.7 m", "proposed_rule": {"rule_id": "REQ-AI-y"}}
    assert resolve_clause(by_id, index) == "9.8.3.3.(1)"
    assert resolve_clause(by_snippet, index) == "9.8.3.3.(1)"

    old = {"proposed_rule": {"ruleset_id": "EXTRACTED-20261002T100000", "check_value": 1}}
    new = {"proposed_rule": {"ruleset_id": "EXTRACTED-20261002T110000", "operator": "<=", "check_value": 3.7,
                             "unit": "m"}, "source_snippet": "height of a flight shall not exceed 3.7 m"}
    (rule,) = drafts_to_rules(newest_run([old, new]), index)
    assert rule["ref"] == "9.8.3.3.(1)" and rule["value"] == 3.7
