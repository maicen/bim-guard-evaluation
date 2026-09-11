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
from nlp_annotation.doclang_annotator import (
    DOCLANG_NS,
    _HEAD_TAG_ORDER,
    _strip_ns,
    DocLangAnnotator,
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
        
        # Merge all results from accepted or latest annotation (or fallback to predictions)
        results = []
        if annotations:
            latest = annotations[-1]
            results = latest.get("result", [])
        elif task.get("predictions"):
            results = task["predictions"][-1].get("result", [])

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

    @classmethod
    def doclang_to_label_studio_tasks(
        cls,
        doclang_xml: str,
        pre_annotate: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Converts DocLang XML into Label Studio tasks, preserving element IDs,
        section hierarchy, and optionally attaching pre-annotations.
        """
        import xml.etree.ElementTree as ET
        annotator = DocLangAnnotator()
        nodes = annotator.parse_nodes(doclang_xml)
        tasks = []

        for idx, node in enumerate(nodes, start=1):
            if not node.text.strip():
                continue

            sec_ref = node.section_number or (node.section_path[-1] if node.section_path else f"node_{idx}")
            task: dict[str, Any] = {
                "id": idx,
                "data": {
                    "text": node.text,
                    "section_ref": sec_ref,
                    "meta": {
                        "element_id": node.element_id,
                        "tag": node.tag,
                        "level": node.level,
                        "section_number": node.section_number,
                        "section_name": node.section_name,
                        "section_path": node.section_path,
                    },
                },
            }

            if pre_annotate:
                ann = annotator.annotate_text(node.text)
                results = []
                r_idx = 1

                for d in ann.get("deontics", []):
                    span = d.get("span", "")
                    if span and span in node.text:
                        start = node.text.find(span)
                        end = start + len(span)
                        label_map = {
                            "mandatory": "MANDATORY",
                            "prohibited": "PROHIBITED",
                            "recommended": "RECOMMENDED",
                            "permitted": "PERMITTED",
                        }
                        lbl = label_map.get(d.get("strength", ""), "MANDATORY")
                        results.append({
                            "id": f"deon_{idx}_{r_idx}",
                            "from_name": "label",
                            "to_name": "text",
                            "type": "labels",
                            "value": {
                                "start": start,
                                "end": end,
                                "text": span,
                                "labels": [lbl],
                            },
                        })
                        r_idx += 1

                for dim in ann.get("dimensions", []):
                    span = dim.get("span", "")
                    if span and span in node.text:
                        start = node.text.find(span)
                        end = start + len(span)
                        c_map = {
                            "min": "DIM_MIN",
                            "max": "DIM_MAX",
                            "exact": "DIM_EXACT",
                            "range": "DIM_RANGE",
                        }
                        lbl = c_map.get(dim.get("constraint", ""), "DIM_MIN")
                        results.append({
                            "id": f"dim_{idx}_{r_idx}",
                            "from_name": "label",
                            "to_name": "text",
                            "type": "labels",
                            "value": {
                                "start": start,
                                "end": end,
                                "text": span,
                                "labels": [lbl],
                            },
                        })
                        r_idx += 1

                for xref in ann.get("cross_refs", []):
                    raw = xref.get("raw", "")
                    if raw and raw in node.text:
                        start = node.text.find(raw)
                        end = start + len(raw)
                        results.append({
                            "id": f"xref_{idx}_{r_idx}",
                            "from_name": "label",
                            "to_name": "text",
                            "type": "labels",
                            "value": {
                                "start": start,
                                "end": end,
                                "text": raw,
                                "labels": ["CROSS_REF"],
                            },
                        })
                        r_idx += 1

                for c in ann.get("conditions", []):
                    c_text = c.get("text", "") if isinstance(c, dict) else str(c)
                    if isinstance(c_text, str) and c_text and c_text in node.text:
                        start = node.text.find(c_text)
                        end = start + len(c_text)
                        lbl = "EXCEPTION" if c.get("type") == "exception" else "APPLICABILITY"
                        results.append({
                            "id": f"cond_{idx}_{r_idx}",
                            "from_name": "label",
                            "to_name": "text",
                            "type": "labels",
                            "value": {
                                "start": start,
                                "end": end,
                                "text": c_text,
                                "labels": [lbl],
                            },
                        })
                        r_idx += 1

                if ann.get("ifc_hints"):
                    results.append({
                        "id": f"ifc_{idx}",
                        "from_name": "ifc_entity",
                        "to_name": "text",
                        "type": "choices",
                        "value": {"choices": [ann["ifc_hints"][0]["ifc_class"]]},
                    })
                if ann.get("dimensions") and ann["dimensions"][0].get("unit"):
                    results.append({
                        "id": f"unit_{idx}",
                        "from_name": "unit",
                        "to_name": "text",
                        "type": "choices",
                        "value": {"choices": [ann["dimensions"][0]["unit"]]},
                    })

                task["predictions"] = [
                    {
                        "model_version": "bim-guard-nlp-v1",
                        "result": results,
                    }
                ]

            tasks.append(task)

        return tasks

    @classmethod
    def label_studio_to_doclang(
        cls,
        tasks: list[dict[str, Any]],
        base_doclang_xml: str,
        validate_xsd: bool = True,
    ) -> str:
        """
        Injects human-reviewed Label Studio annotations back into DocLang XML,
        matching by element_id or text, and validates schema compliance.
        """
        import xml.etree.ElementTree as ET

        if not base_doclang_xml or not base_doclang_xml.strip():
            return base_doclang_xml

        ET.register_namespace("", DOCLANG_NS)
        root = ET.fromstring(base_doclang_xml)
        annotator = DocLangAnnotator()
        nodes = annotator.parse_nodes(root=root)

        task_by_elem_id: dict[str, dict[str, Any]] = {}
        task_by_text: dict[str, dict[str, Any]] = {}
        for t in tasks:
            meta = t.get("data", {}).get("meta", {})
            eid = meta.get("element_id")
            if eid:
                task_by_elem_id[str(eid)] = t
            txt = t.get("data", {}).get("text", "").strip()
            if txt:
                task_by_text[txt] = t

        for node in nodes:
            if node.elem is None:
                continue

            matched_task = None
            if node.element_id and str(node.element_id) in task_by_elem_id:
                matched_task = task_by_elem_id[str(node.element_id)]
            elif node.text.strip() in task_by_text:
                matched_task = task_by_text[node.text.strip()]

            if not matched_task:
                continue

            ann = cls.parse_task_to_nlp_annotation(matched_task)

            elem = node.elem
            custom_el = None
            for child in elem:
                if _strip_ns(child.tag).lower() == "custom":
                    custom_el = child
                    break

            if custom_el is None:
                custom_el = ET.Element(f"{{{DOCLANG_NS}}}custom" if "}" in elem.tag else "custom")
                insert_idx = 0
                for i, child in enumerate(list(elem)):
                    tag_name = _strip_ns(child.tag).lower()
                    if tag_name in _HEAD_TAG_ORDER:
                        insert_idx = i + 1
                    else:
                        break
                elem.insert(insert_idx, custom_el)

            for child in list(custom_el):
                if _strip_ns(child.tag).lower() == "bg_nlp":
                    custom_el.remove(child)

            bg_nlp = ET.SubElement(custom_el, "bg_nlp")
            if ann.get("subject"):
                bg_nlp.set("subject", str(ann["subject"]))

            for d in ann.get("deontics", []):
                ET.SubElement(
                    bg_nlp,
                    "deontic",
                    attrib={
                        "operator": d.get("operator", ""),
                        "strength": d.get("strength", ""),
                        "negated": "true" if d.get("negated") else "false",
                        "span": d.get("span", ""),
                    },
                )

            for dim in ann.get("dimensions", []):
                ET.SubElement(
                    bg_nlp,
                    "dimension",
                    attrib={
                        "value": str(dim.get("value", "")),
                        "unit": dim.get("unit", "") or "",
                        "constraint": dim.get("constraint", "") or "",
                        "span": dim.get("span", ""),
                    },
                )

            for xref in ann.get("cross_refs", []):
                ET.SubElement(
                    bg_nlp,
                    "cross_ref",
                    attrib={
                        "raw": xref.get("raw", ""),
                        "ref_type": xref.get("ref_type", ""),
                        "normalized": xref.get("normalized", ""),
                    },
                )

            for c in ann.get("conditions", []):
                ET.SubElement(
                    bg_nlp,
                    "condition",
                    attrib={
                        "type": c.get("type", ""),
                        "marker": c.get("marker", ""),
                        "text": c.get("text", "")[:120],
                    },
                )

        updated_xml = ET.tostring(root, encoding="utf-8").decode("utf-8")

        if validate_xsd:
            annotator.validate_xml(updated_xml)

        return updated_xml


def main() -> None:
    parser = argparse.ArgumentParser(description="Label Studio Bridge for BIM-Guard Evaluation")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to input JSON or DocLang XML file")
    parser.add_argument(
        "--mode",
        "-m",
        choices=["nlp", "gold", "preannotate", "doclang-to-tasks", "tasks-to-doclang"],
        default="nlp",
        help="Conversion mode: 'nlp' (ParagraphAnnotation), 'gold' (GOLD_RULES), 'preannotate' (to Label Studio), 'doclang-to-tasks' (DocLang XML -> Label Studio), 'tasks-to-doclang' (Label Studio -> DocLang XML)",
    )
    parser.add_argument("--base-doclang", type=str, help="Path to base DocLang XML file (required for 'tasks-to-doclang')")
    parser.add_argument("--output", "-o", type=str, help="Optional output path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        return

    bridge = LabelStudioBridge()

    if args.mode == "doclang-to-tasks":
        with open(input_path, "r", encoding="utf-8") as f:
            xml_content = f.read()
        tasks = bridge.doclang_to_label_studio_tasks(xml_content, pre_annotate=True)
        print(f"Generated {len(tasks)} Label Studio tasks from DocLang XML.")
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=2)
            print(f"Saved tasks to {out_path}")
        else:
            print(json.dumps(tasks[:2], indent=2))
        return

    elif args.mode == "tasks-to-doclang":
        if not args.base_doclang or not Path(args.base_doclang).exists():
            print("Error: --base-doclang must point to an existing DocLang XML file.")
            return
        with open(input_path, "r", encoding="utf-8") as f:
            tasks_data = json.load(f)
        with open(args.base_doclang, "r", encoding="utf-8") as f:
            base_xml = f.read()
        tasks = tasks_data if isinstance(tasks_data, list) else [tasks_data]
        updated_xml = bridge.label_studio_to_doclang(tasks, base_xml, validate_xsd=True)
        print("Successfully injected annotations into DocLang XML and verified XSD compliance.")
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(updated_xml)
            print(f"Saved annotated DocLang XML to {out_path}")
        else:
            print(updated_xml[:500] + "...")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

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
