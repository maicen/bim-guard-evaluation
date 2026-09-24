"""
kg/apply_review_decisions.py
------------------------------------------------
Closes the KG correction loop: applies a human's decisions from a reviewed
uncertain-edge queue (kg.grounding.uncertain_review_queue's CSV output, with
the `human_verdict` column filled in) back onto the graph, then re-exports
an updated grounding index and a shrunk uncertain-review queue containing
only whatever the human didn't get to.

Pipeline this completes:

    kg.build_kg        -- build the initial candidate-match graph
    kg.correct_graph   -- LLM verification pass on borderline candidates
    kg.export_grounding -- grounding index (trusted) + uncertain queue (not)
    kg.apply_review_decisions  <-- YOU ARE HERE: human resolves the queue
    kg.export_grounding (again) -- re-run to promote the human's calls

A row's `human_verdict` must be exactly "correct" or "incorrect" (matching
the same two-value vocabulary kg.llm_correction.verify_task uses for the LLM
pass) to be applied; blank means "still undecided, still in the queue next
time". Anything else is rejected with an error naming the row and value,
rather than silently ignored -- a typo in a hand-edited CSV should not read
as "not yet reviewed".

Usage:
    uv run python -m kg.apply_review_decisions \\
        --source research/kg/obc_app_a_corrected.json \\
        --reviewed research/kg/obc_app_a_uncertain_review.csv \\
        --out research/kg/obc_app_a_reviewed \\
        --reviewer "osama.ata"
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import networkx as nx

from kg.graph_builder import export_graph
from kg.grounding import (
    build_grounding_index,
    load_graph_json,
    uncertain_review_queue,
    write_grounding_index,
    write_review_queue,
)

VALID_VERDICTS = ("correct", "incorrect")


def load_decisions(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows):
        verdict = (row.get("human_verdict") or "").strip().lower()
        if verdict and verdict not in VALID_VERDICTS:
            raise ValueError(
                f"row {i} ({row.get('clause_ref')} / {row.get('term_name')}): "
                f"human_verdict={row.get('human_verdict')!r} is not one of {VALID_VERDICTS} "
                "or blank. Fix the CSV rather than skip this row silently."
            )
    return rows


def apply_decisions(
    graph: nx.MultiDiGraph, decisions: list[dict[str, Any]], *, reviewer: str = ""
) -> tuple[int, int]:
    """Applies every non-blank human_verdict onto its exact graph edge.

    Returns (n_applied, n_missing) -- n_missing counts rows whose
    (clause_id, term_id, edge_key) no longer exists in `graph` (e.g. the
    review CSV was generated from a different graph export than the one
    passed here). Those are reported, not silently dropped.
    """
    applied = 0
    missing = 0
    for row in decisions:
        verdict = (row.get("human_verdict") or "").strip().lower()
        if not verdict:
            continue

        clause_id, term_id, edge_key = row.get("clause_id"), row.get("term_id"), row.get("edge_key")
        try:
            edge_key = int(edge_key)
        except (TypeError, ValueError):
            pass
        if not graph.has_edge(clause_id, term_id, edge_key):
            missing += 1
            continue

        edge = graph.edges[clause_id, term_id, edge_key]
        edge["llm_verdict"] = verdict
        edge["human_reviewed"] = True
        edge["human_reviewer"] = row.get("human_reviewer") or reviewer or None
        edge["human_reason"] = row.get("human_reason") or None
        applied += 1

    return applied, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, type=Path, help="Graph JSON the reviewed CSV's row ids were exported from")
    parser.add_argument("--reviewed", required=True, type=Path, help="uncertain_review CSV with human_verdict filled in")
    parser.add_argument("--out", required=True, type=Path, help="Output path base (no extension)")
    parser.add_argument("--reviewer", default="", help="Default reviewer name for rows with no per-row human_reviewer")
    parser.add_argument(
        "--score-high", type=float, default=0.45,
        help="Must match the --score-high used to build the grounding index this review queue came from",
    )
    args = parser.parse_args(argv)

    print(f"[1/4] Loading graph: {args.source}")
    graph = load_graph_json(args.source)
    print(f"      {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    print(f"[2/4] Loading reviewed queue: {args.reviewed}")
    decisions = load_decisions(args.reviewed)
    n_decided = sum(1 for d in decisions if (d.get("human_verdict") or "").strip())
    print(f"      {len(decisions)} row(s) in queue, {n_decided} with a human_verdict")

    print("[3/4] Applying decisions")
    applied, missing = apply_decisions(graph, decisions, reviewer=args.reviewer)
    print(f"      {applied} edge(s) updated" + (f", {missing} row(s) had no matching edge (stale export?)" if missing else ""))

    print("[4/4] Re-exporting graph, grounding index, and remaining uncertain queue")
    written = export_graph(graph, args.out)
    print(f"      graph        -> {written['json']} (+ {written['graphml']})")

    index = build_grounding_index(graph, score_high=args.score_high)
    n_classes = sum(len(v["classes"]) for v in index.values())
    n_properties = sum(len(v["properties"]) for v in index.values())
    grounding_path = args.out.with_name(args.out.name + "_grounding_index.json")
    write_grounding_index(index, grounding_path)
    print(f"      grounding    -> {grounding_path}  ({n_classes} classes, {n_properties} properties trusted)")

    remaining = uncertain_review_queue(graph)
    review_json = args.out.with_name(args.out.name + "_uncertain_review.json")
    review_csv = args.out.with_name(args.out.name + "_uncertain_review.csv")
    write_review_queue(remaining, review_json, review_csv)
    print(f"      remaining    -> {review_csv}  ({len(remaining)} still uncertain, was {len(decisions)})")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
