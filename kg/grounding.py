"""
kg/grounding.py
------------------------------------------------
Turns a corrected graph (kg.correct_graph output, edges annotated with
llm_verdict/llm_confidence/llm_reason) into two research artifacts:

1. A per-clause grounding index: the bSDD classes/properties trusted
   enough to ground rule extraction against, i.e. usable in place of (or
   alongside) bim-guard's current substring-only
   `_search_classes_grounded`/`_search_properties_grounded`. An edge is
   trusted if either:
     - the LLM verification pass marked it llm_verdict="correct", or
     - it was never sent to the LLM at all because its lexical
       composite_score was already above `score_high` (the same band
       boundary kg.correct_graph used to decide what counted as
       "borderline" -- anything above that band was implicitly treated
       as a confident lexical hit and left alone).
   llm_verdict="incorrect" and "uncertain" edges are always excluded.

2. An uncertain-edge review queue: every llm_verdict="uncertain" edge,
   sorted by llm_confidence ascending (most ambiguous first) so a human
   reviewer works through the hardest calls first.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import networkx as nx

from kg.llm_correction import CANDIDATE_KINDS, load_graph_json

GroundingIndex = Dict[str, Dict[str, List[Dict[str, Any]]]]


def build_grounding_index(graph: nx.MultiDiGraph, *, score_high: float = 0.45) -> GroundingIndex:
    """Returns {clause_ref: {"classes": [...], "properties": [...]}} for trusted candidate edges."""
    index: GroundingIndex = defaultdict(lambda: {"classes": [], "properties": []})

    for clause_node, term_node, _key, attrs in graph.edges(keys=True, data=True):
        kind = attrs.get("kind")
        if kind not in CANDIDATE_KINDS:
            continue

        verdict = attrs.get("llm_verdict")
        score = attrs.get("composite_score", 0.0)

        if verdict == "correct":
            source = "llm_verified"
        elif verdict is None and score >= score_high:
            source = "lexical_high_confidence"
        else:
            # verdict == "incorrect", verdict == "uncertain", or an
            # untouched low/mid-score edge below score_high -- none of
            # these are trusted enough to ground extraction against.
            continue

        term = graph.nodes[term_node]
        clause = graph.nodes[clause_node]
        entry = {
            "uri": term.get("uri"),
            "name": term.get("name"),
            "code": term.get("code"),
            "score": round(score, 4),
            "source": source,
            "llm_confidence": attrs.get("llm_confidence"),
        }
        bucket = "classes" if kind == "candidate_class_match" else "properties"
        index[clause.get("ref", clause_node)][bucket].append(entry)

    for clause_ref, buckets in index.items():
        for bucket in buckets.values():
            bucket.sort(key=lambda e: -e["score"])

    return dict(index)


def uncertain_review_queue(graph: nx.MultiDiGraph) -> List[Dict[str, Any]]:
    """Returns every llm_verdict="uncertain" edge as a flat review row, most-ambiguous first."""
    rows: List[Dict[str, Any]] = []

    for clause_node, term_node, _key, attrs in graph.edges(keys=True, data=True):
        if attrs.get("llm_verdict") != "uncertain":
            continue
        clause = graph.nodes[clause_node]
        term = graph.nodes[term_node]
        rows.append(
            {
                "clause_ref": clause.get("ref", clause_node),
                "clause_heading": clause.get("heading", ""),
                "clause_text_excerpt": clause.get("text_excerpt", ""),
                "term_kind": "class" if attrs.get("kind") == "candidate_class_match" else "property",
                "term_name": term.get("name", ""),
                "term_uri": term.get("uri", ""),
                "term_definition": term.get("definition", ""),
                "lexical_score": round(attrs.get("composite_score", 0.0), 4),
                "llm_confidence": attrs.get("llm_confidence"),
                "llm_reason": attrs.get("llm_reason", ""),
                "llm_model": attrs.get("llm_model", ""),
            }
        )

    rows.sort(key=lambda r: r["llm_confidence"] if r["llm_confidence"] is not None else 0.0)
    return rows


def write_grounding_index(index: GroundingIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


def write_review_queue(rows: List[Dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    if not rows:
        return
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


__all__ = [
    "GroundingIndex",
    "build_grounding_index",
    "uncertain_review_queue",
    "write_grounding_index",
    "write_review_queue",
    "load_graph_json",
]
