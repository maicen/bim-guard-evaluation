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
import bisect
import json
import re
from pathlib import Path
from typing import Any

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
    _HEAD_TAG_ORDER,
    DOCLANG_NS,
    DocLangAnnotator,
    _strip_ns,
)

# A number with optional SI-style space thousands separators ("2 050", "1 070.5").
_NUM = r"\d{1,3}(?: \d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
# Longest alternatives first so "kN/m" wins over "kN" and "mm" over "m".
_UNIT = r"(kN/m|kN|kPa|mm|m|°|degrees?|deg|persons?|%)(?![A-Za-z/])"
_UNIT_CANON = {
    "kn/m": "kN/m", "kn": "kN", "kpa": "kPa", "mm": "mm", "m": "m",
    "°": "degrees", "degree": "degrees", "degrees": "degrees", "deg": "degrees",
    "person": "persons", "persons": "persons", "%": "%",
}
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


# List-item markers inside a clause: "(a) ", "(b) ", "(iii) ".
_LIST_MARKER = re.compile(r"\((?:[a-z]|[ivx]+)\)\s")
_NEGATION = re.compile(r"\b(?:other than|not|except|excluding)\b")
# Bound relative to another property of the same element: "not more than its run plus 25 mm".
_RELATIVE = re.compile(rf"\bits\s+([a-z]+)(?:\s+plus)?(?:\s+({_NUM})\s*(?:{_UNIT})?)?", re.IGNORECASE)

_COUNT_WORD = re.compile(rf"\b(?:{'|'.join(_NUMBER_WORDS)})\b", re.IGNORECASE)


def _to_float(raw: str) -> float:
    return float(raw.replace(" ", ""))


def _canon_unit(raw: str | None) -> str | None:
    return _UNIT_CANON.get(raw.lower()) if raw else None


def extract_numeric_value(text: str) -> tuple[float | None, str | None, float | None, float | None]:
    """
    Extracts numeric value(s) and unit from span text (e.g., 'not less than 2 050 mm').

    Returns (value, unit, value_min, value_max). Handles:
    - space thousands separators ('2 050 mm')
    - ranges: 'between 125 and 200 mm', '865 mm to 1 070 mm', '30-45 degrees'
    - slopes: '1 in 50' -> 0.02 with unit 'ratio'
    - load units: kN, kN/m, kPa
    - counts written as words: 'at least three risers' -> 3 (unit None)
    When a span holds several quantities ('0.5 kN applied over ... 300 mm'), the first
    quantity carrying a unit is the constrained value.
    """
    cleaned = text.replace(" ", " ")

    ratio = re.search(rf"\b({_NUM})\s+in\s+({_NUM})\b", cleaned)
    if ratio:
        denom = _to_float(ratio.group(2))
        if denom:
            return round(_to_float(ratio.group(1)) / denom, 6), "ratio", None, None

    range_match = re.search(
        rf"(?:\bbetween\s+({_NUM})\s*(?:{_UNIT})?\s*and"
        rf"|({_NUM})\s*(?:{_UNIT})?\s*(?:to|-|–))\s*({_NUM})\s*(?:{_UNIT})?",
        cleaned,
        re.IGNORECASE,
    )
    if range_match:
        g = range_match.groups()
        lo_raw, lo_unit = (g[0], g[1]) if g[0] else (g[2], g[3])
        v1, v2 = _to_float(lo_raw), _to_float(g[4])
        unit = _canon_unit(g[5]) or _canon_unit(lo_unit) or "mm"
        return None, unit, min(v1, v2), max(v1, v2)

    with_unit = re.search(rf"({_NUM})\s*{_UNIT}(\s+per\s+person)?", cleaned, re.IGNORECASE)
    if with_unit:
        unit = _canon_unit(with_unit.group(2))
        if with_unit.group(3):
            unit = f"{unit}/person"  # occupant-load rate, e.g. '8 mm per person'
        return _to_float(with_unit.group(1)), unit, None, None

    word = _COUNT_WORD.search(cleaned)
    if word:
        return float(_NUMBER_WORDS[word.group(0).lower()]), None, None, None

    bare = list(re.finditer(_NUM, cleaned))
    if bare:
        return _to_float(bare[-1].group(0)), None, None, None

    return None, None, None, None


def normalize_cross_ref(raw_ref: str) -> tuple[str, str]:
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
    def _building_use(span_text: str) -> str | None:
        """Map a scope span to a building_use tag, honouring negation.

        'serving a house or an individual dwelling unit' -> 'dwelling_unit'
        'for ramps not serving a house ...'              -> 'non_dwelling_unit'
        'buildings of other than residential occupancy'  -> 'non_residential'
        """
        low = span_text.lower()
        for keyword, use in (("residential", "residential"), ("dwelling unit", "dwelling_unit"),
                             ("house", "dwelling_unit")):
            pos = low.find(keyword)
            if pos >= 0:
                return f"non_{use}" if _NEGATION.search(low[:pos]) else use
        return None

    @staticmethod
    def _bind_conditions(
        text: str,
        dim_starts: list[int],
        cond_starts: list[int],
        rows_lead: bool,
    ) -> tuple[list[int], dict[int, list[int]]]:
        """Decide which dimension each condition span qualifies.

        Returns (global condition indices, {dim index: [condition indices]}).

        Prose clauses: the text is split into list items at '(a) ', '(b) ', '(i) '...
        A condition in the preamble before the first dimension applies to every
        dimension; a condition in an item with no dimensions also applies to every
        dimension (it is one of the clause's alternative triggers). Otherwise a
        condition binds to the closest preceding dimension in its item ('1 950 mm for
        ramps serving a house'), or the next one if none precedes it.

        Tables (rows_lead=True): a row/column label precedes its values, so a condition
        binds to every dimension between it and the next condition.
        """
        bound: dict[int, list[int]] = {i: [] for i in range(len(dim_starts))}
        global_conds: list[int] = []
        if not dim_starts:
            return list(range(len(cond_starts))), bound

        if rows_lead:
            ordered = sorted(range(len(cond_starts)), key=lambda c: cond_starts[c])
            for n, c in enumerate(ordered):
                stop = cond_starts[ordered[n + 1]] if n + 1 < len(ordered) else len(text) + 1
                hits = [d for d, s in enumerate(dim_starts) if cond_starts[c] < s < stop]
                if not hits:
                    global_conds.append(c)
                for d in hits:
                    bound[d].append(c)
            return global_conds, bound

        markers = [m.start() for m in _LIST_MARKER.finditer(text)]
        seg = lambda pos: bisect.bisect_right(markers, pos)  # noqa: E731
        first_dim = min(dim_starts)
        for c, c_start in enumerate(cond_starts):
            same = [d for d, s in enumerate(dim_starts) if seg(s) == seg(c_start)]
            if not same or (seg(c_start) == 0 and c_start < first_dim):
                global_conds.append(c)
                continue
            before = [d for d in same if dim_starts[d] < c_start]
            target = (max(before, key=lambda d: dim_starts[d]) if before
                      else min(same, key=lambda d: dim_starts[d]))
            bound[target].append(c)
        return global_conds, bound

    @classmethod
    def parse_task_to_gold_rules(cls, task: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extracts GOLD_RULE dictionaries from a Label Studio annotated task: one rule
        per DIM_* span, each carrying the conditions that qualify that value.
        Returns [] if the clause does not contain a checkable constraint.
        """
        data = task.get("data", {})
        section_ref = data.get("section_ref", "unknown")
        text = data.get("text", "")
        annotations = task.get("annotations", [])
        results = annotations[-1].get("result", []) if annotations else []

        ifc_target = "IfcStairFlight"
        property_name = None
        unit_choice: str | None = None
        dims: list[tuple[int, str, str]] = []    # (start, label, span text)
        conds: list[tuple[int, str, str]] = []   # (start, label, span text)

        for item in results:
            value = item.get("value", {})
            if item.get("type") == "choices":
                choices = value.get("choices", [])
                if not choices:
                    continue
                from_name = item.get("from_name")
                if from_name == "ifc_entity":
                    ifc_target = choices[0]
                elif from_name == "property_name":
                    property_name = choices[0]
                elif from_name == "unit":
                    unit_choice = choices[0] if choices[0] != "none" else None
            elif item.get("type") == "labels":
                span_text = value.get("text", "")
                start = value.get("start", text.find(span_text))
                for lbl in value.get("labels", []):
                    if lbl.startswith("DIM_"):
                        dims.append((start, lbl, span_text))
                    elif lbl in ("APPLICABILITY", "QUALIFICATION", "EXCEPTION"):
                        conds.append((start, lbl, span_text))

        dims.sort()
        conds.sort()
        global_conds, bound = cls._bind_conditions(
            text,
            [d[0] for d in dims],
            [c[0] for c in conds],
            rows_lead=section_ref.lower().startswith("table"),
        )

        op_map = {"DIM_MIN": ">=", "DIM_MAX": "<=", "DIM_EXACT": "==", "DIM_RANGE": "between"}
        desc = text[:120].strip() + ("..." if len(text) > 120 else "")
        rules: list[dict[str, Any]] = []

        for d, (_, label, span_text) in enumerate(dims):
            operator = op_map[label]
            rule: dict[str, Any] = {
                "ref": section_ref,
                "target": ifc_target,
                "property_name": property_name or "Width",
                "operator": operator,
            }

            relative = _RELATIVE.search(span_text)
            if relative:
                side = "min" if operator == ">=" else "max"
                offset = _to_float(relative.group(2)) if relative.group(2) else 0
                rule[f"value_{side}_property"] = relative.group(1).capitalize()
                rule[f"value_{side}_offset"] = offset
                rule["unit"] = _canon_unit(relative.group(3)) or unit_choice
            else:
                val, unit, val_min, val_max = extract_numeric_value(span_text)
                if operator == "between":
                    if val_min is None:
                        continue
                    rule["value_min"], rule["value_max"] = val_min, val_max
                else:
                    if val is None:
                        continue  # e.g. 'at least as wide as the stair' — not machine-checkable
                    rule["value"] = val
                # A count written in words ('at least three risers', 'two No. 8 screws')
                # has no unit, so the task-level unit choice doesn't apply to it.
                rule["unit"] = unit or (None if _COUNT_WORD.search(span_text) else unit_choice)
            rule["desc"] = desc

            applies = [conds[c] for c in global_conds + bound[d]]
            applies_when = {}
            for _, lbl, c_text in applies:
                use = cls._building_use(c_text) if lbl == "APPLICABILITY" else None
                if use and "building_use" not in applies_when:
                    applies_when["building_use"] = use
            if applies_when:
                rule["applies_when"] = applies_when
            conditions = [c_text for _, lbl, c_text in applies if lbl != "EXCEPTION"]
            exceptions = [c_text for _, lbl, c_text in applies if lbl == "EXCEPTION"]
            if conditions:
                rule["conditions"] = conditions
            if exceptions:
                rule["exceptions"] = exceptions
            rules.append(rule)

        return cls._merge_relative_bounds(rules)

    @staticmethod
    def _merge_relative_bounds(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fold a relative >= / <= pair on the same property ('not less than its run and
        not more than its run plus 25 mm') into one 'between' rule, matching the
        GOLD_RULES convention for 9.8.4.2.(2) / 9.8.4.3.(3)."""
        mins = [r for r in rules if "value_min_property" in r]
        maxs = [r for r in rules if "value_max_property" in r]
        if len(mins) != 1 or len(maxs) != 1:
            return rules
        lo, hi = mins[0], maxs[0]
        if (lo["target"], lo["property_name"]) != (hi["target"], hi["property_name"]):
            return rules
        merged = {**lo, **hi, "operator": "between"}
        merged["value_min_property"] = lo["value_min_property"]
        merged["value_min_offset"] = lo["value_min_offset"]
        merged["unit"] = hi.get("unit") or lo.get("unit")
        return [merged if r is lo else r for r in rules if r is not hi]

    @classmethod
    def parse_task_to_gold_rule(cls, task: dict[str, Any]) -> dict[str, Any] | None:
        """
        Backward-compatible single-rule accessor: the first rule from
        parse_task_to_gold_rules, or None if the clause has no checkable constraint.
        """
        rules = cls.parse_task_to_gold_rules(task)
        return rules[0] if rules else None

    @classmethod
    def export_annotations_to_nlp(cls, tasks: list[dict[str, Any]]) -> list[ParagraphAnnotation]:
        """Convert a list of Label Studio tasks to ParagraphAnnotation list."""
        return [cls.parse_task_to_nlp_annotation(t) for t in tasks]

    @classmethod
    def export_annotations_to_gold_rules(cls, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert a list of Label Studio tasks to GOLD_RULES list."""
        rules = []
        for t in tasks:
            rules.extend(cls.parse_task_to_gold_rules(t))
        return rules

    @staticmethod
    def gold_rules_to_preannotated_tasks(
        gold_rules: list[dict[str, Any]],
        clause_texts: dict[str, str] | None = None,
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
        with open(input_path, encoding="utf-8") as f:
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
        with open(input_path, encoding="utf-8") as f:
            tasks_data = json.load(f)
        with open(args.base_doclang, encoding="utf-8") as f:
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

    with open(input_path, encoding="utf-8") as f:
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
