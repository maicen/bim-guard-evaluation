#!/usr/bin/env python3
"""
extract_section.py
---------------------------------------------
Pulls one section out of a full-document DocLang (.dclg/.dclx) file and
flattens its numbered-sentence clauses (the <list><ldiv><marker>(N)</marker>
...</list> pattern DocLang uses for code sentences) into a flat JSON list of
{section_ref, article_name, text} records — one per sentence/clause, plus one
per table, ready to feed to build_ls_tasks.py.

Why this exists: nlp_annotation.doclang_annotator.DocLangAnnotator.parse_nodes
only extracts <text>/<paragraph>/<table> tags. Most real code clauses in these
documents live as bare text inside <list>/<ldiv> elements instead (numbered
sentences, lettered sub-items), which parse_nodes silently skips. This script
walks that structure directly.

Usage:
    uv run python extract_section.py \\
        --source sources/OBC_2023.Volume_1_P_9.dclg \\
        --start "Section 9.8." \\
        --end "Section 9.9." \\
        --output /tmp/section_9_8_sentences.json

--end is optional — omit it to extract from --start through the end of the
document. Both --start and --end match the start of a top-level <heading>
element's text (case-sensitive, as it appears in the source).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HEADING_NUM = re.compile(r"^(\d+(?:\.\d+)*[A-Z]?\.)\s*(.*)$")


def strip_ns(tag: str) -> str:
    return tag.split("}")[-1]


def text_of(elem: ET.Element) -> str:
    return "".join(elem.itertext()).strip()


def find_bounds(
    children: list[ET.Element], start: str, end: str | None
) -> tuple[int, int]:
    start_idx = None
    end_idx = None
    for i, el in enumerate(children):
        if strip_ns(el.tag).lower() != "heading":
            continue
        t = re.sub(r"\s+", " ", text_of(el))
        if start_idx is None and t.startswith(start):
            start_idx = i
        elif start_idx is not None and end is not None and t.startswith(end):
            end_idx = i
            break
    if start_idx is None:
        raise SystemExit(
            f"Could not find a heading starting with {start!r}. "
            "Check the exact heading text in the source file — DocLang headings "
            "often carry a trailing revision marker (e.g. ' e8', ' r11.2') and "
            "OCR artifacts, so match on a short, stable prefix."
        )
    if end is not None and end_idx is None:
        raise SystemExit(
            f"Found the start heading but no heading starting with {end!r} "
            "after it. Omit --end to extract through the end of the document, "
            "or check the exact next-section heading text."
        )
    return start_idx, (end_idx if end_idx is not None else len(children))


def flush_sentences(list_elem: ET.Element) -> list[tuple[str | None, str]]:
    """
    Walks one <list> element's children in document order, splitting its text
    into (marker, sentence_text) pairs at each <ldiv><marker>(N)</marker></ldiv>.
    Lettered sub-items (markerless <ldiv/>) and any other inline text append to
    the current sentence rather than starting a new one — matching how OBC/SBC
    clauses nest "(a)/(b)/(c)" options inside a numbered sentence.
    """
    sentences: list[tuple[str | None, str]] = []
    current_marker: str | None = None
    current_parts: list[str] = []

    def flush_current() -> None:
        if current_parts:
            text = re.sub(r"\s+", " ", " ".join(p for p in current_parts if p)).strip()
            if text:
                sentences.append((current_marker, text))

    for child in list_elem:
        tag = strip_ns(child.tag).lower()
        if tag == "ldiv":
            marker_el = None
            for c in child:
                if strip_ns(c.tag).lower() == "marker":
                    marker_el = c
                    break
            marker_text = "".join(marker_el.itertext()).strip() if marker_el is not None else None
            if marker_text:
                flush_current()
                current_marker = marker_text
                current_parts = []
        tail = (child.tail or "").strip()
        if tail:
            current_parts.append(tail)
    flush_current()
    return sentences


def parse_otsl_table_text(elem: ET.Element) -> str:
    """Best-effort flat text of a <table> element (cell text in document order)."""
    return re.sub(r"\s+", " ", "".join(elem.itertext())).strip()


def extract(source: Path, start: str, end: str | None) -> list[dict]:
    tree = ET.parse(source)
    root = tree.getroot()
    children = list(root)
    start_idx, end_idx = find_bounds(children, start, end)
    sliced = children[start_idx:end_idx]

    current_article_num: str | None = None
    current_article_name: str | None = None
    tasks: list[dict] = []

    for elem in sliced:
        tag = strip_ns(elem.tag).lower()

        if tag == "heading":
            text = re.sub(r"\s+", " ", text_of(elem))
            m = HEADING_NUM.match(text)
            if m:
                current_article_num = m.group(1).rstrip(".")
                current_article_name = m.group(2).strip()
            continue

        if tag == "list":
            if current_article_num is None:
                continue
            for marker, text in flush_sentences(elem):
                ref = f"{current_article_num}.{marker}" if marker else current_article_num
                tasks.append(
                    {
                        "data": {
                            "section_ref": ref,
                            "article_name": current_article_name,
                            "text": text,
                        }
                    }
                )
            continue

        if tag == "table":
            text = parse_otsl_table_text(elem)[:2000]
            if text:
                ref = f"Table under {current_article_num}" if current_article_num else "Table"
                tasks.append(
                    {
                        "data": {
                            "section_ref": ref,
                            "article_name": current_article_name,
                            "text": text,
                        }
                    }
                )

    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, type=Path, help="Path to the full-document .dclg/.dclx file")
    parser.add_argument("--start", required=True, help="Prefix of the start heading's text, e.g. 'Section 9.8.'")
    parser.add_argument("--end", default=None, help="Prefix of the end heading's text (exclusive). Omit to go to EOF.")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Where to write the extracted JSON")
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Error: source file not found: {args.source}", file=sys.stderr)
        raise SystemExit(1)

    tasks = extract(args.source, args.start, args.end)
    if not tasks:
        print(
            "Warning: extracted 0 clauses. The heading boundaries matched, but no "
            "<list> or <table> elements were found in between — double-check this "
            "is really where the clause text lives in this document.",
            file=sys.stderr,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

    print(f"Extracted {len(tasks)} clause/table records from {args.start!r} to {args.end or 'EOF'!r}")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
