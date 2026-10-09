"""Score LLM rule drafts against the rule table of the PDF they were extracted from.

The door and window MVP rule sheets list each rule as a table row (rule ID,
property, operator, value, unit, applicability), so the sheet itself is the
answer key. Drafts are paired with gold rows by rule ID and compared field by
field; a draft whose rule ID is not in the sheet counts as invented.

Usage: uv run python eval/score_mvp_pdf_extraction.py --pack window \
           --drafts eval/results/mvp_pdf_extraction/window_2026-10-02/drafts.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
GOLD_PATH = EVAL_DIR / "fixtures" / "mvp_door_window_pdf_gold.json"

OPERATORS = {"=": "==", "exist": "exists"}
NOT_A_UNIT = {"", "-", "boolean", "enum", "count", "project-defined"}
UNCONDITIONAL = {"", "all modeled windows", "all modeled doors"}
FIELDS = ("target", "property", "operator", "value", "unit")


def _op(raw: Any) -> str:
    op = str(raw or "").strip().lower()
    return OPERATORS.get(op, op)


def _value(raw: Any) -> float | str:
    text = str(raw if raw is not None else "").strip()
    try:
        return float(text)
    except ValueError:
        return text.lower()


def _unit(raw: Any) -> str:
    unit = str(raw or "").strip().lower().replace("²", "2")
    return "" if unit in NOT_A_UNIT else unit


def compare(gold: dict[str, Any], rule: dict[str, Any], target: str) -> dict[str, bool]:
    """Which structured fields of one drafted rule agree with its gold row."""
    names = {gold["property"].lower(), *(n.lower() for n in gold.get("ifc_names", []))}
    return {
        "target": str(rule.get("target_ifc_class") or "").lower() == target.lower(),
        "property": str(rule.get("property_name") or "").lower() in names,
        "operator": _op(rule.get("operator")) == _op(gold["operator"]),
        "value": _value(rule.get("check_value")) == _value(gold["value"]),
        "unit": _unit(rule.get("unit")) == _unit(gold["unit"]),
    }


def score(pack: dict[str, Any], drafts: list[dict[str, Any]]) -> dict[str, Any]:
    gold = {r["rule_id"]: r for r in pack["rules"]}
    rules = [d.get("proposed_rule") or {} for d in drafts]
    by_id = {str(r.get("rule_id") or "").strip(): r for r in rules}
    matched = [rid for rid in gold if rid in by_id]

    per_rule, wrong = [], {f: [] for f in FIELDS}
    for rid in matched:
        checks = compare(gold[rid], by_id[rid], pack["target_ifc_class"])
        per_rule.append({"rule_id": rid, **checks})
        for field, ok in checks.items():
            if not ok:
                wrong[field].append(rid)

    conditional = [rid for rid in matched if gold[rid]["applicability"].strip().lower() not in UNCONDITIONAL]
    return {
        "document": pack["document"],
        "gold_rules": len(gold),
        "drafts": len(drafts),
        "found": len(matched),
        "missed": [rid for rid in gold if rid not in by_id],
        "invented": [rid or "(no rule ID)" for rid in by_id if rid not in gold],
        "duplicates": len(rules) - len(by_id),
        "fields": {f: {"right": len(matched) - len(wrong[f]), "wrong": wrong[f]} for f in FIELDS},
        "all_fields_right": sum(all(r[f] for f in FIELDS) for r in per_rule),
        "applicability": {
            "conditional_rules": len(conditional),
            # The condition was written down somewhere in the draft (RASE notes) ...
            "noted": sum(bool(by_id[rid].get("rase_applicability") or by_id[rid].get("rase_selection")) for rid in conditional),
            # ... versus stored in applies_when, the only field the audit engine filters on.
            "executable": sum(bool(by_id[rid].get("applies_when")) for rid in conditional),
        },
        "per_rule": per_rule,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", choices=("door", "window"), required=True)
    ap.add_argument("--drafts", type=Path, required=True, help="drafts.json (rule_extraction_drafts rows)")
    ap.add_argument("--gold", type=Path, default=GOLD_PATH)
    ap.add_argument("-o", "--out", type=Path, help="default: confusion.json beside the drafts file")
    a = ap.parse_args()

    pack = json.loads(a.gold.read_text(encoding="utf-8"))["packs"][a.pack]
    res = score(pack, json.loads(a.drafts.read_text(encoding="utf-8")))
    out = a.out or a.drafts.with_name("confusion.json")
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")

    print(f"{res['document']}: {res['found']} of {res['gold_rules']} rules found, "
          f"{len(res['missed'])} missed, {len(res['invented'])} invented")
    for field, r in res["fields"].items():
        print(f"  {field:9s} {r['right']:>2} / {res['found']}  wrong: {', '.join(r['wrong']) or '-'}")
    appl = res["applicability"]
    print(f"  applicability noted {appl['noted']} / {appl['conditional_rules']}, "
          f"executable {appl['executable']} / {appl['conditional_rules']}")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
