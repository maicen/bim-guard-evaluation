"""
kg/clause_builder.py
------------------------------------------------
Groups a parsed DocLang document into Clause units (one per heading) and
attaches the existing nlp_annotation/ linguistic signals (deontics,
conditions, dimensions, cross-references, dependencies, IFC hints) to each.

Reuses nlp_annotation.doclang_annotator.DocLangAnnotator for XML parsing and
per-paragraph annotation rather than re-implementing that logic here.

Also derives clause-to-clause edges from cross-references and dependency
markers (override/subject_to/exception/...) resolved against other clauses'
refs in the same document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from nlp_annotation.doclang_annotator import DocLangAnnotator

# OBC-style headings are letter-prefixed decimal hierarchies, e.g.
# "A-1.1.2.  Limit of Application." or "A-1.2.1.1.(1)(b) Compliance ...".
# This intentionally differs from doclang_annotator's plain-digit
# _HEADING_NUM_PATTERN, which never matches an "A-" prefix and would leave
# every OBC App-A heading's section_number as None.
_REF_PATTERN = re.compile(
    r"^([A-Z]?-?\d+(?:\.\d+)*(?:\.\(\d+\))*(?:\([a-z0-9]+\))*)\.?\s*(.*)$",
    re.IGNORECASE,
)


@dataclass
class Clause:
    """A document unit grouped under one heading, with aggregated NLP annotations."""

    ref: str
    heading: str
    section_path: List[str] = field(default_factory=list)
    level: int = 0
    text: str = ""
    element_ids: List[str] = field(default_factory=list)
    deontics: List[Dict[str, Any]] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    dimensions: List[Dict[str, Any]] = field(default_factory=list)
    cross_refs: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    ifc_hints: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ClauseEdge:
    """A directed relationship between two clauses in the same document."""

    source_ref: str
    target_ref: str
    edge_type: str  # "cross_ref" or "depends_on:<dep_type>"
    label: str = ""


def _derive_ref(heading_text: str, fallback_idx: int) -> Tuple[str, str]:
    """Splits a heading into (clause_ref, clean_heading_text)."""
    heading_text = heading_text.strip()
    m = _REF_PATTERN.match(heading_text)
    if m and m.group(1):
        ref = m.group(1).rstrip(".").upper()
        rest = (m.group(2) or "").strip()
        return ref, rest or heading_text
    return f"H{fallback_idx}", heading_text


def _numeric_suffix(ref: str) -> str:
    """Strips a leading letter-prefix from a clause ref for cross-ref matching,
    e.g. "A-1.1.2" -> "1.1.2". Refs with no letter prefix are returned unchanged."""
    return ref.split("-", 1)[-1] if "-" in ref else ref


def build_clauses(xml_content: str) -> List[Clause]:
    """Parses DocLang XML into a flat list of Clause units in document order."""
    annotator = DocLangAnnotator()
    nodes = annotator.parse_nodes(xml_content)

    clauses: List[Clause] = []
    current: Optional[Clause] = None
    heading_idx = 0
    preamble_idx = 0

    def _flush() -> None:
        if current is not None:
            current.text = current.text.strip()
            clauses.append(current)

    for node in nodes:
        if node.tag == "heading":
            _flush()
            heading_idx += 1
            ref, clean_heading = _derive_ref(node.text, heading_idx)
            current = Clause(
                ref=ref,
                heading=clean_heading,
                section_path=node.section_path,
                level=node.level,
            )
            continue

        if current is None:
            preamble_idx += 1
            current = Clause(ref=f"PREAMBLE-{preamble_idx}", heading="", section_path=[], level=0)

        if not node.text.strip():
            continue

        ann = annotator.annotate_text(node.text)
        current.text = f"{current.text}\n\n{node.text}".strip()
        if node.element_id:
            current.element_ids.append(node.element_id)
        current.deontics.extend(ann["deontics"])
        current.conditions.extend(ann["conditions"])
        current.dimensions.extend(ann["dimensions"])
        current.cross_refs.extend(ann["cross_refs"])
        current.dependencies.extend(ann["dependencies"])
        current.ifc_hints.extend(ann["ifc_hints"])

    _flush()
    _dedupe_refs(clauses)
    return clauses


def _dedupe_refs(clauses: List[Clause]) -> None:
    """Appends a numeric suffix to any clause ref that collides with an earlier one
    (e.g. repeated/ambiguous headings), so every clause has a unique graph node id."""
    seen: Dict[str, int] = {}
    for clause in clauses:
        base = clause.ref
        if base not in seen:
            seen[base] = 0
            continue
        seen[base] += 1
        clause.ref = f"{base}#{seen[base]}"


def build_clause_edges(clauses: List[Clause]) -> List[ClauseEdge]:
    """Resolves each clause's cross-references and dependency markers against
    other clauses' refs in the same document to produce clause-to-clause edges."""
    by_numeric: Dict[str, str] = {}
    for clause in clauses:
        by_numeric.setdefault(_numeric_suffix(clause.ref), clause.ref)

    edges: List[ClauseEdge] = []
    for clause in clauses:
        for xref in clause.cross_refs:
            target_ref = by_numeric.get(xref.get("normalized", ""))
            if target_ref and target_ref != clause.ref:
                edges.append(ClauseEdge(clause.ref, target_ref, "cross_ref", xref.get("raw", "")))

        for dep in clause.dependencies:
            for ref in dep.get("refs", []):
                target_ref = by_numeric.get(ref.get("normalized", ""))
                if target_ref and target_ref != clause.ref:
                    edges.append(
                        ClauseEdge(
                            clause.ref,
                            target_ref,
                            f"depends_on:{dep.get('dep_type', 'unknown')}",
                            dep.get("marker", ""),
                        )
                    )

    return edges
