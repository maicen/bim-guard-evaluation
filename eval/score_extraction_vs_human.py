"""
score_extraction_vs_human.py
---------------------------------------------
Scores BIM-Guard's rule extraction against the human-annotated Label Studio
gold set (OBC 2023 Section 9.8, research/label_studio/), and reports three
confusion matrices:

1. Clause-level (binary, has TN): over every annotated clause, does it contain
   at least one checkable requirement?  Human = ground truth, BIM-Guard =
   prediction.  Positive = "clause yields a checkable rule".
2. Rule-level (TP/FP/FN; TN is undefined for open-ended extraction): a human
   rule and an extracted rule match when they cite the same clause, use the
   same operator and agree on the value(s) after unit normalisation.  Scored
   leniently (clause + operator + value) and strictly (+ IFC target and
   property, alias-aware).
3. Operator confusion: for pairs that agree on clause and value, the human
   operator vs. the extracted one (>=, <=, ==, between).

Inputs:
  --human      Label Studio JSON export (tasks with "annotations"), converted
               to gold rules with eval/label_studio_bridge.py.
  --extracted  JSON produced by BIM-Guard extraction: a list of rules, or an
               object with a "rules" list (the shape returned by
               POST /api/rules/extract and the draft-rules endpoints).

Usage:
  uv run python eval/score_extraction_vs_human.py \\
      --human research/label_studio/data/export/project1.json \\
      --extracted eval/results/bimguard_extraction_9_8.json \\
      --json-out eval/results/confusion_9_8.json --md-out eval/results/confusion_9_8.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR.parent) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR.parent))

from eval.label_studio_bridge import LabelStudioBridge  # noqa: E402
from eval.stats_util import confusion_matrix_metrics  # noqa: E402

OPERATORS = (">=", "<=", "==", "between")
_OP_ALIASES = {
    ">=": ">=", "≥": ">=", "gte": ">=", "min": ">=", "minimum": ">=", "at_least": ">=",
    "<=": "<=", "≤": "<=", "lte": "<=", "max": "<=", "maximum": "<=", "at_most": "<=",
    "==": "==", "=": "==", "eq": "==", "exact": "==", "equals": "==",
    "between": "between", "range": "between", "in_range": "between",
    ">": ">", "<": "<",
}
# Scale factors to a base unit per dimension family, so 3.7 m == 3700 mm.
_UNIT_SCALE = {
    "mm": ("length", 1.0), "cm": ("length", 10.0), "m": ("length", 1000.0),
    "kn": ("force", 1.0), "n": ("force", 0.001),
    "kn/m": ("line_load", 1.0), "kpa": ("pressure", 1.0),
    "ratio": ("ratio", 1.0), "%": ("ratio", 0.01),
    "deg": ("angle", 1.0), "degrees": ("angle", 1.0), "°": ("angle", 1.0),
}

# Same alias table the existing extraction scorer uses, when bim-guard is importable.
try:
    from eval.eval_config import setup_bimguard_path

    setup_bimguard_path()
    from ifc_reader import _PROPERTY_ALIASES  # type: ignore[import-not-found]

    _ALIAS_GROUPS = [{c.lower(), *(a.lower() for a in al)} for c, al in _PROPERTY_ALIASES.items()]
except Exception:  # noqa: BLE001 - scorer must run without a bim-guard checkout
    _ALIAS_GROUPS = []


# ── normalisation ────────────────────────────────────────────────────────────

_REF_RE = re.compile(r"(\d+(?:\.\d+)+[A-Z]?)\.?\s*((?:\(\s*\w+\s*\))*)")


def normalize_ref(raw: Any) -> str:
    """'Sentence 9.8.2.1.(1)' / '9.8.2.1(1)' / '9.8.2.1.(1)(a)' -> '9.8.2.1.(1)'.

    Clause letters below the sentence level are dropped so a rule extracted for
    9.8.5.4.(1)(b) pairs with the human rule on 9.8.5.4.(1). Table refs keep a
    'table:' prefix.
    """
    s = str(raw or "")
    m = _REF_RE.search(s)
    if not m:
        return s.strip().lower()
    num = m.group(1).rstrip(".")
    parens = re.findall(r"\(\s*(\w+)\s*\)", m.group(2))
    sentence = next((p for p in parens if p.isdigit() or re.fullmatch(r"\d+[a-z]", p)), None)
    ref = f"{num}.({sentence})" if sentence else num
    low = s.lower()
    if low.startswith("note"):
        return f"note:{ref}"
    return f"table:{num}" if "table" in low and not sentence else ref


def normalize_op(raw: Any) -> str | None:
    return _OP_ALIASES.get(str(raw or "").strip().lower())


def to_base(value: Any, unit: Any) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None, None
    fam, scale = _UNIT_SCALE.get(str(unit or "").strip().lower(), (None, 1.0))
    return v * scale, fam


def same_property(a: Any, b: Any) -> bool:
    a, b = str(a or "").strip().lower(), str(b or "").strip().lower()
    if not a or not b:
        return False
    return a == b or any(a in g and b in g for g in _ALIAS_GROUPS)


def _close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(0.5, 0.01 * max(abs(a), abs(b)))


def rule_values(rule: dict[str, Any]) -> tuple[Any, ...]:
    """Comparable value signature in base units (relative bounds compared by property)."""
    unit = rule.get("unit")
    if "value_min_property" in rule or "value_max_property" in rule:
        return ("rel", str(rule.get("value_min_property") or "").lower(),
                str(rule.get("value_max_property") or "").lower())
    if normalize_op(rule.get("operator")) == "between":
        return (to_base(rule.get("value_min"), unit)[0], to_base(rule.get("value_max"), unit)[0])
    value = rule.get("value", rule.get("check_value"))
    return (to_base(value, unit)[0],)


def values_agree(a: dict[str, Any], b: dict[str, Any]) -> bool:
    va, vb = rule_values(a), rule_values(b)
    if va and va[0] == "rel" or vb and vb[0] == "rel":
        return va == vb
    if len(va) != len(vb):
        return False
    return all(_close(x, y) for x, y in zip(va, vb))


def refs_agree(human_ref: str, extracted_ref: str) -> bool:
    """Exact sentence match, or an article-level extracted ref covering the sentence."""
    if human_ref == extracted_ref:
        return True
    if ":" in human_ref or ":" in extracted_ref:  # tables/notes only match exactly
        return False
    return human_ref.startswith(extracted_ref + ".") and "(" not in extracted_ref


# ── loading ──────────────────────────────────────────────────────────────────

def load_extracted(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("rules", "drafts", "items", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a list of rules or an object with a 'rules' list")
    return [_flatten(r) for r in data]


def _flatten(rule: dict[str, Any]) -> dict[str, Any]:
    """Accept BIM-Guard's nested shapes (rule_json / check / source) as flat gold-style dicts."""
    flat = dict(rule)
    for nested in ("rule_json", "rule", "check", "logic"):
        if isinstance(rule.get(nested), dict):
            for k, v in rule[nested].items():
                flat.setdefault(k, v)
    flat.setdefault("ref", rule.get("source_ref") or rule.get("section_ref") or rule.get("clause_ref")
                    or rule.get("section") or rule.get("citation"))
    flat.setdefault("target", rule.get("ifc_class") or rule.get("ifc_entity") or rule.get("target_entity"))
    flat.setdefault("property_name", rule.get("property") or rule.get("attribute"))
    if flat.get("value") is None and flat.get("check_value") is not None:
        flat["value"] = flat["check_value"]
    return flat


def load_human(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Gold rules plus every annotated clause ref (the clause-level population)."""
    tasks = json.loads(path.read_text(encoding="utf-8"))
    rules = LabelStudioBridge.export_annotations_to_gold_rules(tasks)
    refs = [normalize_ref(t.get("data", {}).get("section_ref")) for t in tasks]
    return rules, refs


# ── scoring ──────────────────────────────────────────────────────────────────

def match_rules(human: list[dict], extracted: list[dict], strict: bool) -> tuple[list, list, list]:
    """Greedy one-to-one matching. Returns (pairs, unmatched_human, unmatched_extracted)."""
    used: set[int] = set()
    pairs, missed = [], []
    for h in human:
        h_ref, h_op = normalize_ref(h["ref"]), normalize_op(h["operator"])
        hit = None
        for i, e in enumerate(extracted):
            if i in used or not refs_agree(h_ref, normalize_ref(e.get("ref"))):
                continue
            if normalize_op(e.get("operator")) != h_op or not values_agree(h, e):
                continue
            if strict and not (str(e.get("target", "")).lower() == h["target"].lower()
                               and same_property(e.get("property_name"), h["property_name"])):
                continue
            hit = i
            break
        if hit is None:
            missed.append(h)
        else:
            used.add(hit)
            pairs.append((h, extracted[hit]))
    false_pos = [e for i, e in enumerate(extracted) if i not in used]
    return pairs, missed, false_pos


def operator_confusion(human: list[dict], extracted: list[dict]) -> dict[str, dict[str, int]]:
    """Human op (rows) vs extracted op (cols) for pairs agreeing on clause and value."""
    table: dict[str, Counter] = defaultdict(Counter)
    for h in human:
        h_ref = normalize_ref(h["ref"])
        hv = rule_values(h)
        for e in extracted:
            if not refs_agree(h_ref, normalize_ref(e.get("ref"))):
                continue
            ev = rule_values(e)
            # compare the scalar part only, so '>= 900' vs '== 900' still pairs
            hs = hv[-1] if hv and hv[0] != "rel" else None
            es = ev[-1] if ev and ev[0] != "rel" else None
            if _close(hs, es):
                table[normalize_op(h["operator"]) or "?"][normalize_op(e.get("operator")) or "?"] += 1
                break
    return {k: dict(v) for k, v in table.items()}


def clause_confusion(clause_refs: list[str], human: list[dict], extracted: list[dict]) -> dict[str, Any]:
    human_pos = {normalize_ref(h["ref"]) for h in human}
    extracted_refs = [normalize_ref(e.get("ref")) for e in extracted]
    tp = fp = fn = tn = 0
    rows = []
    for ref in sorted(set(clause_refs)):
        truth = ref in human_pos
        pred = any(refs_agree(ref, e) for e in extracted_refs)
        tp += truth and pred
        fn += truth and not pred
        fp += pred and not truth
        tn += not truth and not pred
        rows.append({"ref": ref, "human": truth, "extracted": pred})
    out_of_scope = sorted({e for e in extracted_refs if not any(refs_agree(r, e) for r in clause_refs)})
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "clauses": rows, "unmapped_extracted_refs": out_of_scope}


def is_dimensional(rule: dict[str, Any]) -> bool:
    """A rule the human gold can contain: a numeric, range or relative-bound check."""
    if normalize_op(rule.get("operator")) not in OPERATORS:
        return False
    vals = rule_values(rule)
    return bool(vals) and (vals[0] == "rel" or all(v is not None for v in vals))


def score(human_path: Path, extracted_path: Path) -> dict[str, Any]:
    human, clause_refs = load_human(human_path)
    all_extracted = load_extracted(extracted_path)
    # Human annotation only captures dimensional constraints (DIM_* spans), so the
    # comparison is restricted to extracted rules of the same kind; the rest are
    # reported separately rather than counted as false positives.
    extracted = [e for e in all_extracted if is_dimensional(e)]
    non_dimensional = [e for e in all_extracted if not is_dimensional(e)]

    clause = clause_confusion(clause_refs, human, extracted)
    clause["metrics"] = confusion_matrix_metrics(clause["tp"], clause["fp"], clause["fn"], clause["tn"])

    rule_level = {}
    for mode in ("lenient", "strict"):
        pairs, missed, fps = match_rules(human, extracted, strict=(mode == "strict"))
        tp, fn, fp = len(pairs), len(missed), len(fps)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        rule_level[mode] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "missed": [_brief(h) for h in missed],
            "false_positives": [_brief(e) for e in fps],
        }

    return {
        "human_rules": len(human),
        "extracted_rules": len(extracted),
        "extracted_rules_total": len(all_extracted),
        "non_dimensional_extracted": [
            f"{normalize_ref(e.get('ref'))} {e.get('target', '?')}.{e.get('property_name', '?')} "
            f"{e.get('operator', '?')} {e.get('value', e.get('check_value'))}" for e in non_dimensional
        ],
        "clauses": len(set(clause_refs)),
        "clause_level": clause,
        "rule_level": rule_level,
        "operator_confusion": operator_confusion(human, extracted),
    }


def _brief(r: dict[str, Any]) -> str:
    vals = rule_values(r)
    shown = vals[0] if len(vals) == 1 else vals
    return (f"{normalize_ref(r.get('ref'))} {r.get('target', '?')}.{r.get('property_name', '?')} "
            f"{r.get('operator', '?')} {shown} (base units)")


# ── reporting ────────────────────────────────────────────────────────────────

def to_markdown(res: dict[str, Any]) -> str:
    c = res["clause_level"]
    m = c["metrics"]
    lines = [
        "# BIM-Guard rule extraction vs. human annotation — OBC 2023 Section 9.8",
        "",
        f"Human gold rules: **{res['human_rules']}** · Extracted dimensional rules: "
        f"**{res['extracted_rules']}** (of {res.get('extracted_rules_total', res['extracted_rules'])} drafts) · "
        f"Annotated clauses: **{res['clauses']}**",
        "",
        "## 1. Clause-level confusion matrix",
        "Positive = clause yields at least one checkable rule.",
        "",
        "| | Extracted: rule | Extracted: none |",
        "|---|---|---|",
        f"| **Human: rule** | TP {c['tp']} | FN {c['fn']} |",
        f"| **Human: none** | FP {c['fp']} | TN {c['tn']} |",
        "",
    ]
    for k in ("accuracy", "precision", "recall_sensitivity", "specificity", "f1_score", "balanced_accuracy"):
        if k in m:
            v = m[k]
            lines.append(f"- {k}: {v.get('formatted', v) if isinstance(v, dict) else v}")
    lines += ["", "## 2. Rule-level matching", "TN is undefined for open-ended extraction.", "",
              "| Mode | TP | FP | FN | Precision | Recall | F1 |", "|---|---|---|---|---|---|---|"]
    for mode, r in res["rule_level"].items():
        lines.append(f"| {mode} | {r['tp']} | {r['fp']} | {r['fn']} | {r['precision']:.1%} | "
                     f"{r['recall']:.1%} | {r['f1']:.1%} |")
    lines += ["", "Lenient = same clause + operator + value. Strict additionally requires IFC target "
              "and property (alias-aware).", "", "## 3. Operator confusion (pairs agreeing on clause and value)",
              "", "| Human \\ Extracted | " + " | ".join(OPERATORS) + " |", "|---|" + "---|" * len(OPERATORS)]
    for h_op in OPERATORS:
        row = res["operator_confusion"].get(h_op, {})
        lines.append(f"| **{h_op}** | " + " | ".join(str(row.get(e, 0)) for e in OPERATORS) + " |")
    lenient = res["rule_level"]["lenient"]
    lines += ["", "## Missed human rules (lenient FN)", ""] + [f"- {x}" for x in lenient["missed"]]
    lines += ["", "## Unmatched extracted rules (lenient FP)", ""] + [f"- {x}" for x in lenient["false_positives"]]
    if res.get("non_dimensional_extracted"):
        lines += ["", "## Non-dimensional extracted rules (outside the human gold's scope, not scored)", ""]
        lines += [f"- {x}" for x in res["non_dimensional_extracted"]]
    if c["unmapped_extracted_refs"]:
        lines += ["", "## Extracted refs outside the annotated clause set", ""]
        lines += [f"- {x}" for x in c["unmapped_extracted_refs"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--human", type=Path, required=True)
    ap.add_argument("--extracted", type=Path, required=True)
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--md-out", type=Path)
    args = ap.parse_args()

    res = score(args.human, args.extracted)
    md = to_markdown(res)
    print(md)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
