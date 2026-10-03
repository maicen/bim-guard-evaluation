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


NOTES_HEADING = re.compile(r"^Notes? to (Table \d+(?:\.\d+)*[A-Z]?)\.?:?")
# A sentence marker "(2) " that opens a new sentence: at the start of a chunk, or right
# after a sentence end (". (2) Except ...") or a revision tag ("... r11.2 (3) ..."), but
# not after words such as "Sentence (2)" / "Sentences (2), (4) and (5)".
INLINE_MARKER = re.compile(r"\((\d+(?:\.\d+)?[a-z]?)\)\s")  # (2), (3.1), (2a)
# Whitespace is required before the marker, so "A-9.8.7.2.(1)" is not a sentence start.
_SENTENCE_END = re.compile(r"(?:[.;:]|\br\d+(?:\.\d+)?|\be\d+(?:\.\d+)?)\s+$")
_REVISION_ONLY = re.compile(r"(?:[re]\d+(?:\.\d+)?\s*)+")


def split_inline(text: str) -> list[tuple[str | None, str]]:
    """Split a chunk at sentence markers; a leading unmarked part has marker None."""
    cuts = [m for m in INLINE_MARKER.finditer(text) if m.start() == 0 or _SENTENCE_END.search(text[: m.start()])]
    if not cuts:
        return [(None, text)]
    parts: list[tuple[str | None, str]] = []
    if cuts[0].start() > 0:
        parts.append((None, text[: cuts[0].start()].strip()))
    for i, m in enumerate(cuts):
        stop = cuts[i + 1].start() if i + 1 < len(cuts) else len(text)
        parts.append((f"({m.group(1)})", text[m.end():stop].strip()))
    return [(mk, t) for mk, t in parts if t]


def extract(source: Path, start: str, end: str | None) -> list[dict]:
    """Sentences and tables of one section, in document order.

    Clause text arrives in three shapes in these DocLang files: <list> items with
    <marker>(N)</marker>, bare <text> elements starting "(N) ...", and several sentences
    run together in one element ("... flight . (2) Except ..."). Unmarked chunks (page
    breaks, lettered continuations such as "(b) complies with ...") belong to the
    previous sentence of the same article and are appended to it. Sentences under a
    "Notes to Table X" heading are numbered "Note to Table X.(n)".
    """
    tree = ET.parse(source)
    root = tree.getroot()
    children = list(root)
    start_idx, end_idx = find_bounds(children, start, end)
    sliced = children[start_idx:end_idx]

    context_ref: str | None = None      # article number, or "Note to Table X"
    context_name: str | None = None
    last_sentence: dict | None = None   # task whose text a continuation extends
    tasks: list[dict] = []

    def add_chunk(marker: str | None, text: str) -> None:
        nonlocal last_sentence
        text = re.sub(r"\s+", " ", text).strip()
        if not text or context_ref is None or _REVISION_ONLY.fullmatch(text):
            return
        if marker is None:
            # Continuation of the open sentence; with no open sentence (right after a
            # heading) it is caption/header residue such as "Forming Part of Sentence
            # 9.8.7.1.(1)" and is dropped rather than emitted as a fragment task.
            if last_sentence is not None:
                last_sentence["data"]["text"] = f"{last_sentence['data']['text']} {text}"
            return
        ref = f"{context_ref}.{marker}" if marker else context_ref
        last_sentence = {"data": {"section_ref": ref, "article_name": context_name, "text": text}}
        tasks.append(last_sentence)

    for elem in sliced:
        tag = strip_ns(elem.tag).lower()

        if tag == "heading":
            text = re.sub(r"\s+", " ", text_of(elem))
            m = HEADING_NUM.match(text)
            notes = NOTES_HEADING.match(text)
            last_sentence = None  # any heading (incl. "Table 9.8.7.1.") ends the sentence
            if m:
                context_ref, context_name = m.group(1).rstrip("."), m.group(2).strip()
                last_sentence = None
            elif notes:
                context_ref, context_name = f"Note to {notes.group(1)}", text
                last_sentence = None
            continue

        if tag == "list":
            for marker, text in flush_sentences(elem):
                for i, (inner_marker, inner_text) in enumerate(split_inline(text)):
                    add_chunk(marker if i == 0 and inner_marker is None else inner_marker, inner_text)
            continue

        if tag in ("text", "paragraph"):
            text = re.sub(r"\s+", " ", text_of(elem))
            # Some article headings are tagged <text> ("9.8.6.3. Dimensions of Landings").
            m = HEADING_NUM.match(text)
            if m and m.group(2)[:1].isupper():
                context_ref, context_name = m.group(1).rstrip("."), m.group(2).strip()
                last_sentence = None
                continue
            for marker, chunk in split_inline(text):
                add_chunk(marker, chunk)
            continue

        if tag == "table":
            text = parse_otsl_table_text(elem)[:2000]
            if text:
                ref = f"Table under {context_ref}" if context_ref else "Table"
                tasks.append({"data": {"section_ref": ref, "article_name": context_name, "text": text}})
            continue

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
            "<list>, <text> or <table> elements were found in between — double-check this "
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
