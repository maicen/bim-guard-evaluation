#!/usr/bin/env python3
"""
build_ls_tasks.py
---------------------------------------------
Turns the flat clause JSON from extract_section.py into Label Studio import
tasks, pre-annotated with nlp_annotation's regex extractors (deontics,
dimensions, cross-refs, conditions, IFC entity/unit guesses) so a human
annotator is confirming/correcting rather than labeling from a blank page.

The label names and from_name keys ("linguistic_labels", "ifc_entity", "unit")
are hardcoded to match research/label_studio/config.xml in this repo — if that
config changes, update the label maps below to match.

Usage:
    uv run python build_ls_tasks.py \\
        --input /tmp/section_9_8_sentences.json \\
        --output /tmp/section_9_8_tasks.json \\
        [--no-predictions] [--start-id 1]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from nlp_annotation.doclang_annotator import DocLangAnnotator  # noqa: E402

DEONTIC_LABEL_MAP = {
    "mandatory": "MANDATORY",
    "prohibited": "PROHIBITED",
    "recommended": "RECOMMENDED",
    "permitted": "PERMITTED",
}
DIMENSION_LABEL_MAP = {
    "min": "DIM_MIN",
    "max": "DIM_MAX",
    "exact": "DIM_EXACT",
    "range": "DIM_RANGE",
}


def build_predictions(annotator: DocLangAnnotator, text: str, idx: int) -> list[dict]:
    ann = annotator.annotate_text(text)
    results: list[dict] = []
    r = 0

    for d in ann.get("deontics", []):
        span = d.get("span", "")
        if span and span in text:
            start = text.find(span)
            r += 1
            results.append(
                {
                    "id": f"deon_{idx}_{r}",
                    "from_name": "linguistic_labels",
                    "to_name": "text",
                    "type": "labels",
                    "value": {
                        "start": start,
                        "end": start + len(span),
                        "text": span,
                        "labels": [DEONTIC_LABEL_MAP.get(d.get("strength", ""), "MANDATORY")],
                    },
                }
            )

    for dim in ann.get("dimensions", []):
        span = dim.get("span", "")
        if span and span in text:
            start = text.find(span)
            r += 1
            results.append(
                {
                    "id": f"dim_{idx}_{r}",
                    "from_name": "linguistic_labels",
                    "to_name": "text",
                    "type": "labels",
                    "value": {
                        "start": start,
                        "end": start + len(span),
                        "text": span,
                        "labels": [DIMENSION_LABEL_MAP.get(dim.get("constraint", ""), "DIM_MIN")],
                    },
                }
            )

    for xref in ann.get("cross_refs", []):
        raw = xref.get("raw", "")
        if raw and raw in text:
            start = text.find(raw)
            r += 1
            results.append(
                {
                    "id": f"xref_{idx}_{r}",
                    "from_name": "linguistic_labels",
                    "to_name": "text",
                    "type": "labels",
                    "value": {
                        "start": start,
                        "end": start + len(raw),
                        "text": raw,
                        "labels": ["CROSS_REF"],
                    },
                }
            )

    for c in ann.get("conditions", []):
        c_text = c.get("text", "") if isinstance(c, dict) else str(c)
        if isinstance(c_text, str) and c_text and c_text in text:
            start = text.find(c_text)
            r += 1
            lbl = "EXCEPTION" if isinstance(c, dict) and c.get("type") == "exception" else "APPLICABILITY"
            results.append(
                {
                    "id": f"cond_{idx}_{r}",
                    "from_name": "linguistic_labels",
                    "to_name": "text",
                    "type": "labels",
                    "value": {
                        "start": start,
                        "end": start + len(c_text),
                        "text": c_text,
                        "labels": [lbl],
                    },
                }
            )

    if ann.get("ifc_hints"):
        results.append(
            {
                "id": f"ifc_{idx}",
                "from_name": "ifc_entity",
                "to_name": "text",
                "type": "choices",
                "value": {"choices": [ann["ifc_hints"][0]["ifc_class"]]},
            }
        )
    if ann.get("dimensions") and ann["dimensions"][0].get("unit"):
        results.append(
            {
                "id": f"unit_{idx}",
                "from_name": "unit",
                "to_name": "text",
                "type": "choices",
                "value": {"choices": [ann["dimensions"][0]["unit"]]},
            }
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", "-i", required=True, type=Path)
    parser.add_argument("--output", "-o", required=True, type=Path)
    parser.add_argument("--no-predictions", action="store_true", help="Skip pre-annotation; produce bare tasks")
    parser.add_argument("--start-id", type=int, default=1)
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    annotator = DocLangAnnotator()

    tasks = []
    for offset, item in enumerate(raw):
        idx = args.start_id + offset
        text = item["data"]["text"]
        task = {
            "id": idx,
            "data": {
                "text": text,
                "section_ref": item["data"].get("section_ref"),
                "meta": {"article_name": item["data"].get("article_name")},
            },
        }
        if not args.no_predictions:
            results = build_predictions(annotator, text, idx)
            if results:
                task["predictions"] = [{"model_version": "bim-guard-nlp-v1", "result": results}]
        tasks.append(task)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(tasks, indent=2), encoding="utf-8")

    with_preds = sum(1 for t in tasks if "predictions" in t)
    print(f"Built {len(tasks)} tasks, {with_preds} with pre-annotation suggestions")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
