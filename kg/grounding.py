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

   Each clause entry also carries two signals already computed by
   `clause_builder.build_clauses`/`build_clause_edges` and stored on the
   graph, so bim-guard's extraction prompt can be *informed* by them
   instead of only being corrected after the fact:
     - "deontic": the clause's own rule-based modality (from
       `nlp_annotation.deontic_extractor`), reused instead of paying for a
       second, LLM-based deontic-detection call per clause. Only exposed
       for a single, one-word, non-negated operator (SHALL/MUST/SHOULD/
       MAY) -- a clause with a "SHALL NOT" or multiple conflicting
       operators is left for the LLM, since bim-guard's DeonticStatement
       modality enum has no prohibited/mixed case to map either into.
     - "dependencies": the clause's outgoing cross_ref/depends_on edges to
       other clauses in the same document (e.g. a sprinkler exception
       overriding a base threshold), each resolved to the target clause's
       own text so the relationship doesn't have to be re-inferred blind.

2. An uncertain-edge review queue: every llm_verdict="uncertain" edge,
   sorted by llm_confidence ascending (most ambiguous first) so a human
   reviewer works through the hardest calls first. Each row carries the
   (clause_id, term_id, edge_key) triple `apply_review_decisions.py` needs
   to look the exact edge back up in the graph once a human fills in its
   `human_verdict` column -- this is what closes the loop: LLM correction
   pass -> human review of what the LLM couldn't decide -> re-applied to
   the graph -> a grounding index that includes the human's calls, not
   just the LLM's and the lexical-only ones. See apply_review_decisions.py.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import networkx as nx

from kg.llm_correction import CANDIDATE_KINDS, load_graph_json

GroundingIndex = dict[str, dict[str, Any]]  # {clause_node_id: {"ref": str, "classes": [...], "properties": [...]}}


_DEONTIC_MODALITY_PRIORITY = ("SHALL", "MUST", "SHOULD", "MAY")


def _deontic_hint(clause_attrs: dict[str, Any]) -> dict[str, str] | None:
    """The clause's single clearest modality, reused from clause_builder's rule-based pass.

    `deontic_operators` is the sorted *set* of canonical operator strings
    graph_builder.py recorded on the clause node (see
    `nlp_annotation.deontic_extractor.DeonticExtractor`), e.g. {"SHALL",
    "SHALL NOT"}. Only a bare, single-word, non-negated operator maps
    cleanly onto bim-guard's DeonticStatement.modality enum ("shall",
    "must", "should", "may") -- a negated form ("SHALL NOT") or a clause
    mixing multiple operators is left to the LLM rather than guessed at.
    """
    operators = set(clause_attrs.get("deontic_operators") or [])
    if len(operators) != 1:
        return None
    (operator,) = operators
    if operator not in _DEONTIC_MODALITY_PRIORITY:
        return None
    return {"modality": operator.lower(), "text": clause_attrs.get("text_excerpt", "")}


def _dependencies_for(graph: nx.MultiDiGraph, clause_node: str) -> list[dict[str, Any]]:
    """This clause's outgoing cross_ref/depends_on edges, resolved to the target's own text.

    Lets a prompt say "this clause is subject to an exception in clause X:
    '<X's text>'" instead of asking the LLM to infer that structure blind
    from ref numbers alone.
    """
    deps: list[dict[str, Any]] = []
    for _source, target_node, attrs in graph.out_edges(clause_node, data=True):
        kind = attrs.get("kind", "")
        if kind != "cross_ref" and not kind.startswith("depends_on:"):
            continue
        target = graph.nodes.get(target_node, {})
        deps.append(
            {
                "edge_type": kind,
                "label": attrs.get("label", ""),
                "target_ref": target.get("ref", target_node),
                "target_text_excerpt": target.get("text_excerpt", ""),
            }
        )
    return deps


def build_grounding_index(graph: nx.MultiDiGraph, *, score_high: float = 0.45) -> GroundingIndex:
    """Returns {clause_node_id: {"classes": [...], "properties": [...], ...}} for every clause.

    Keyed by the graph node id (e.g. "clause::4.4.1", or
    "sbc_201::clause::4.4.1" in a kg.merge_graphs-combined multi-code
    graph), not the bare clause ref -- refs are only unique *within* one
    document. A fallback ref like "H1" is common to every document (it's
    clause_builder.py's generic "heading had no parseable section
    number" placeholder), so keying by bare ref would silently collide
    two different documents' clauses into the same entry, discarding one
    of them. The clause's own "ref" field is still available on each
    entry's source clause node for display.

    Every clause node gets an entry (even one with no trusted bSDD
    candidate at all), because "deontic"/"dependencies" are useful prompt
    signal on their own; only "classes"/"properties" require a trusted
    candidate edge to populate.
    """
    index: GroundingIndex = {}
    for clause_node, attrs in graph.nodes(data=True):
        if attrs.get("kind") != "clause":
            continue
        index[clause_node] = {
            "ref": attrs.get("ref", clause_node),
            "classes": [],
            "properties": [],
            "deontic": _deontic_hint(attrs),
            "dependencies": _dependencies_for(graph, clause_node),
        }

    for clause_node, term_node, _key, attrs in graph.edges(keys=True, data=True):
        kind = attrs.get("kind")
        if kind not in CANDIDATE_KINDS:
            continue
        if clause_node not in index:
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
            # (A human-reviewed edge always has llm_verdict set to the
            # human's decision by apply_review_decisions.py, so a
            # "correct" human call already took the first branch above --
            # this continue only ever discards genuinely undecided edges.)
            continue

        term = graph.nodes[term_node]
        entry = {
            "uri": term.get("uri"),
            "name": term.get("name"),
            "code": term.get("code"),
            "score": round(score, 4),
            "source": "human_verified" if attrs.get("human_reviewed") else source,
            "llm_confidence": attrs.get("llm_confidence"),
        }
        bucket = "classes" if kind == "candidate_class_match" else "properties"
        index[clause_node][bucket].append(entry)

    for entries in index.values():
        for bucket_key in ("classes", "properties"):
            entries[bucket_key].sort(key=lambda e: -e["score"])

    return index


def uncertain_review_queue(graph: nx.MultiDiGraph) -> list[dict[str, Any]]:
    """Returns every llm_verdict="uncertain" edge as a flat review row, most-ambiguous first.

    Each row carries clause_id/term_id/edge_key -- the exact
    graph.edges[u, v, key] triple -- so a human's filled-in `human_verdict`
    can be applied back to precisely this edge by
    apply_review_decisions.py, rather than re-matched by the display-only
    clause_ref/term_uri columns (which are not guaranteed unique: two
    distinct edges could in principle share both).
    """
    rows: list[dict[str, Any]] = []

    for clause_node, term_node, key, attrs in graph.edges(keys=True, data=True):
        if attrs.get("llm_verdict") != "uncertain":
            continue
        clause = graph.nodes[clause_node]
        term = graph.nodes[term_node]
        rows.append(
            {
                "clause_id": clause_node,
                "term_id": term_node,
                "edge_key": key,
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
                "human_verdict": "",
                "human_reviewer": "",
                "human_reason": "",
            }
        )

    rows.sort(key=lambda r: r["llm_confidence"] if r["llm_confidence"] is not None else 0.0)
    return rows


def write_grounding_index(index: GroundingIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


def write_review_queue(rows: list[dict[str, Any]], json_path: Path, csv_path: Path) -> None:
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
