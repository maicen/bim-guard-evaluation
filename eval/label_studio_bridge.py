"""
eval/label_studio_bridge.py
---------------------------------------------
Bidirectional converter between Label Studio JSON exports/tasks and BIM-Guard
evaluation formats:
1. Label Studio Export -> ParagraphAnnotation (nlp_annotation.annotation_schema)
2. Label Studio Export -> GOLD_RULES list (eval_gold_code_9_8_stairs)
3. GOLD_RULES + Text -> Label Studio Pre-annotated Tasks
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nlp_annotation.annotation_schema import (
    ConditionAnnotation,
    CrossRefAnnotation,
    DeonticAnnotation,
    DependencyAnnotation,
    DimensionAnnotation,
    IFCHintAnnotation,
    ParagraphAnnotation,
)


def extract_numeric_value(text: str) -> Tuple[Optional[float], Optional[str], Optional[float], Optional[float]]:
    """
    Extracts numeric value(s) and unit from span text (e.g., 'not less than 2 050 mm').
    Handles spaces within numbers (e.g. '2 050').
    """
    # Clean up commas or non-breaking spaces
    cleaned = text.replace("\u00a0", " ")
    
    # Check for range: 'between X and Y'
    range_match = re.search(r"between\s+([\d\s]+(?:[\.,]\d+)?)\s*(?:and|-|to)\s*([\d\s]+(?:[\.,]\d+)?)\s*([a-zA-Z]+)?", cleaned, re.IGNORECASE)
    if range_match:
        val1_str = range_match.group(1).replace(" ", "").replace(",", ".")
        val2_str = range_match.group(2).replace(" ", "").replace(",", ".")
        unit_str = range_match.group(3) or "mm"
        try:
            val1 = float(val1_str)
            val2 = float(val2_str)
            return None, unit_str.strip().lower(), min(val1, val2), max(val1, val2)
        except ValueError:
            pass

    # Single number: find digits with optional thousand separators
    matches = list(re.finditer(r"(\d+(?:[\s\.]\d+)?)\s*([a-zA-Z°]+)?", cleaned))
    if not matches:
        return None, None, None, None

    # Pick the last or most prominent number
    last_m = matches[-1]
    raw_num = last_m.group(1).replace(" ", "").replace(",", ".")
    raw_unit = last_m.group(2)

    try:
        val = float(raw_num)
    except ValueError:
        val = None

    unit = raw_unit.strip().lower() if raw_unit else None
    if unit in ("mm", "m", "degrees", "deg", "%", "persons", "person"):
        if unit in ("deg", "degrees"):
            unit = "degrees"
        elif unit in ("person", "persons"):
            unit = "persons"
    else:
        # Check if unit appears anywhere else in text
        for u in ("mm", "m", "degrees", "persons"):
            if re.search(rf"\b{u}\b", cleaned, re.IGNORECASE):
                unit = u
                break

    return val, unit, None, None


def normalize_cross_ref(raw_ref: str) -> Tuple[str, str]:
    """
    Normalizes a regulatory cross-reference (e.g. 'Article 9.8.4.5A.' -> ('article', '9.8.4.5A')).
    """
    ref_type = "clause"
    lower = raw_ref.lower()
    if "table" in lower:
        ref_type = "table"
    elif "article" in lower:
        ref_type = "article"
    elif "sentence" in lower:
        ref_type = "sentence"
    elif "section" in lower:
        ref_type = "section"
    elif "figure" in lower:
        ref_type = "figure"

    norm_match = re.search(r"(\d+(?:\.\d+)+[A-Z]?(?:\.\(\d+\))?)", raw_ref)
    normalized = norm_match.group(1) if norm_match else raw_ref.strip()
    return ref_type, normalized


class LabelStudioBridge:
    """
    Transforms Label Studio export annotations into BIM-Guard NLP annotations & GOLD_RULES.
    """

    @staticmethod
    def parse_task_to_nlp_annotation(task: dict[str, Any]) -> ParagraphAnnotation:
        """
        Parses a single Label Studio task item into a ParagraphAnnotation TypedDict.
        """
        data = task.get("data", {})
        text = data.get("text", "")
        annotations = task.get("annotations", [])
        
        # Merge all results from accepted or latest annotation
        results = []
        if annotations:
            latest = annotations[-1]
            results = latest.get("result", [])

        deontics: list[DeonticAnnotation] = []
        conditions: list[ConditionAnnotation] = []
        cross_refs: list[CrossRefAnnotation] = []
        dimensions: list[DimensionAnnotation] = []
        dependencies: list[DependencyAnnotation] = []
        ifc_hints: list[IFCHintAnnotation] = []
        requirements: list[str] = []
        subject: str | None = None

        for item in results:
            item_type = item.get("type")
            from_name = item.get("from_name")
            value = item.get("value", {})

            if item_type == "labels":
                labels = value.get("labels", [])
                span_text = value.get("text", "")

                for lbl in labels:
                    lbl_upper = lbl.upper()
                    if lbl_upper in ("MANDATORY", "PROHIBITED", "RECOMMENDED", "PERMITTED"):
                        strength_map = {
                            "MANDATORY": "mandatory",
                            "PROHIBITED": "prohibited",
                            "RECOMMENDED": "recommended",
                            "PERMITTED": "permitted",
                        }
                        deontics.append(
                            DeonticAnnotation(
                                operator=span_text.strip().upper(),
                                strength=strength_map[lbl_upper],
                                negated=(lbl_upper == "PROHIBITED"),
                                span=span_text,
                            )
                        )
                    elif lbl_upper in ("APPLICABILITY", "EXCEPTION", "QUALIFICATION"):
                        type_map = {
                            "APPLICABILITY": "applicability",
                            "EXCEPTION": "exception",
                            "QUALIFICATION": "qualification",
                        }
                        marker = span_text.split()[0] if span_text.split() else ""
                        cond = ConditionAnnotation(
                            type=type_map[lbl_upper],
                            marker=marker,
                            text=span_text,
                        )
                        conditions.append(cond)
                        if lbl_upper == "EXCEPTION":
                            dependencies.append(
                                DependencyAnnotation(
                                    dep_type="exception",
                                    marker=marker,
                                    text=span_text,
                                    refs=[],
                                )
                            )
                    elif lbl_upper.startswith("DIM_"):
                        constraint_map = {
                            "DIM_MIN": "min",
                            "DIM_MAX": "max",
                            "DIM_EXACT": "exact",
                            "DIM_RANGE": "range",
                        }
                        constraint = constraint_map.get(lbl_upper, "exact")
                        val, unit, val_min, val_max = extract_numeric_value(span_text)
                        dimensions.append(
                            DimensionAnnotation(
                                value=val if val is not None else 0.0,
                                unit=unit or "mm",
                                constraint=constraint,
                                value_min=val_min,
                                value_max=val_max,
                                span=span_text,
                            )
                        )
                    elif lbl_upper in ("CROSS_REF", "REFERENCE"):
                        ref_type, norm = normalize_cross_ref(span_text)
                        cross_refs.append(
                            CrossRefAnnotation(
                                raw=span_text,
                                ref_type=ref_type,
                                normalized=norm,
                                context=span_text,
                            )
                        )

            elif item_type == "choices":
                choices = value.get("choices", [])
                if not choices:
                    continue
                choice_val = choices[0]

                if from_name == "ifc_entity":
                    ifc_hints.append(
                        IFCHintAnnotation(
                            surface=choice_val.replace("Ifc", "").lower(),
                            ifc_class=choice_val,
                        )
                    )
                    if subject is None:
                        subject = choice_val

        # If any cross-refs were within exception dependencies, nest them
        for dep in dependencies:
            for cr in cross_refs:
                if cr["raw"] in dep["text"]:
                    dep["refs"].append(cr)

        return ParagraphAnnotation(
            deontics=deontics,
            conditions=conditions,
            requirements=requirements,
            cross_refs=cross_refs,
            dimensions=dimensions,
            dependencies=dependencies,
            ifc_hints=ifc_hints,
            subject=subject,
        )

    @staticmethod
    def parse_task_to_gold_rule(task: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Extracts a discrete GOLD_RULE dictionary from a Label Studio annotated task.
        Returns None if the clause does not contain a checkable constraint.
        """
        data = task.get("data", {})
        section_ref = data.get("section_ref", "unknown")
        text = data.get("text", "")
        annotations = task.get("annotations", [])

        results = []
        if annotations:
            latest = annotations[-1]
            results = latest.get("result", [])

        ifc_target = "IfcStairFlight"
        property_name = None
        unit = "mm"
        dim_constraint = None
        dim_span = ""
        applies_when = {}

        for item in results:
            from_name = item.get("from_name")
            value = item.get("value", {})
            item_type = item.get("type")

            if item_type == "choices":
                choices = value.get("choices", [])
                if choices:
                    if from_name == "ifc_entity":
                        ifc_target = choices[0]
                    elif from_name == "property_name":
                        property_name = choices[0]
                    elif from_name == "unit":
                        unit = choices[0] if choices[0] != "none" else None

            elif item_type == "labels":
                labels = value.get("labels", [])
                span_text = value.get("text", "")
                for lbl in labels:
                    if lbl.startswith("DIM_"):
                        dim_constraint = lbl
                        dim_span = span_text
                    elif lbl == "APPLICABILITY":
                        if "residential" in span_text.lower():
                            applies_when["building_use"] = "residential"
                        elif "house" in span_text.lower() or "dwelling unit" in span_text.lower():
                            applies_when["building_use"] = "dwelling_unit"

        if not dim_constraint or not dim_span:
            return None

        val, extracted_unit, val_min, val_max = extract_numeric_value(dim_span)
        if extracted_unit and unit == "mm":
            unit = extracted_unit

        op_map = {
            "DIM_MIN": ">=",
            "DIM_MAX": "<=",
            "DIM_EXACT": "==",
            "DIM_RANGE": "between",
        }
        operator = op_map.get(dim_constraint, ">=")

        rule: dict[str, Any] = {
            "ref": section_ref,
            "target": ifc_target,
            "property_name": property_name or "Width",
            "operator": operator,
            "unit": unit,
            "desc": text[:120].strip() + ("..." if len(text) > 120 else ""),
        }

        if operator == "between":
            rule["value_min"] = val_min
            rule["value_max"] = val_max
        else:
            rule["value"] = val

        if applies_when:
            rule["applies_when"] = applies_when

        return rule

    @classmethod
    def export_annotations_to_nlp(cls, tasks: list[dict[str, Any]]) -> list[ParagraphAnnotation]:
        """Convert a list of Label Studio tasks to ParagraphAnnotation list."""
        return [cls.parse_task_to_nlp_annotation(t) for t in tasks]

    @classmethod
    def export_annotations_to_gold_rules(cls, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert a list of Label Studio tasks to GOLD_RULES list."""
        rules = []
        for t in tasks:
            rule = cls.parse_task_to_gold_rule(t)
            if rule:
                rules.append(rule)
        return rules

    @staticmethod
    def gold_rules_to_preannotated_tasks(
        gold_rules: list[dict[str, Any]],
        clause_texts: Optional[dict[str, str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Converts GOLD_RULES into Label Studio pre-annotated import tasks.
        """
        tasks = []
        clause_texts = clause_texts or {}

        for idx, rule in enumerate(gold_rules, start=1):
            ref = rule.get("ref", f"rule_{idx}")
            text = clause_texts.get(ref, rule.get("desc", f"Rule for {ref}"))
            op = rule.get("operator", ">=")
            val = rule.get("value")
            unit = rule.get("unit", "mm")
            prop = rule.get("property_name", "Width")
            target = rule.get("target", "IfcStairFlight")

            dim_label = "DIM_MIN"
            if op == "<=":
                dim_label = "DIM_MAX"
            elif op == "==":
                dim_label = "DIM_EXACT"
            elif op == "between":
                dim_label = "DIM_RANGE"

            result = [
                {
                    "id": f"choice_ifc_{idx}",
                    "from_name": "ifc_entity",
                    "to_name": "text",
                    "type": "choices",
                    "value": {"choices": [target]},
                },
                {
                    "id": f"choice_prop_{idx}",
                    "from_name": "property_name",
                    "to_name": "text",
                    "type": "choices",
                    "value": {"choices": [prop]},
                },
                {
                    "id": f"choice_unit_{idx}",
                    "from_name": "unit",
                    "to_name": "text",
                    "type": "choices",
                    "value": {"choices": [unit or "none"]},
                },
            ]

            # Try to find dimension substring in text
            dim_str = f"{val} {unit}".strip() if val is not None else ""
            if dim_str and dim_str in text:
                start = text.find(dim_str)
                result.append({
                    "id": f"span_dim_{idx}",
                    "from_name": "linguistic_labels",
                    "to_name": "text",
                    "type": "labels",
                    "value": {
                        "start": start,
                        "end": start + len(dim_str),
                        "text": dim_str,
                        "labels": [dim_label],
                    },
                })

            task = {
                "data": {
                    "section_ref": ref,
                    "text": text,
                },
                "annotations": [
                    {
                        "id": idx,
                        "result": result,
                    }
                ],
            }
            tasks.append(task)

        return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Label Studio Bridge for BIM-Guard Evaluation")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to input JSON file")
    parser.add_argument("--mode", "-m", choices=["nlp", "gold", "preannotate"], default="nlp",
                        help="Conversion mode: 'nlp' (ParagraphAnnotation), 'gold' (GOLD_RULES), 'preannotate' (to Label Studio)")
    parser.add_argument("--output", "-o", type=str, help="Optional output JSON path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    bridge = LabelStudioBridge()

    if args.mode == "nlp":
        tasks = data if isinstance(data, list) else [data]
        out = bridge.export_annotations_to_nlp(tasks)
        print(f"Converted {len(out)} tasks to ParagraphAnnotation format.")
    elif args.mode == "gold":
        tasks = data if isinstance(data, list) else [data]
        out = bridge.export_annotations_to_gold_rules(tasks)
        print(f"Converted {len(out)} checkable rules to GOLD_RULES format.")
    elif args.mode == "preannotate":
        rules = data if isinstance(data, list) else [data]
        out = bridge.gold_rules_to_preannotated_tasks(rules)
        print(f"Generated {len(out)} pre-annotated Label Studio tasks.")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"Saved output to {out_path}")
    else:
        print(json.dumps(out[:2], indent=2))


if __name__ == "__main__":
    main()
