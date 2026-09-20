"""
kg/export_grounding.py
------------------------------------------------
CLI: turns a corrected graph (kg.correct_graph output) into a per-clause
grounding index (trusted bSDD class/property candidates) and an
uncertain-edge review queue. See kg/grounding.py for the trust rule.

Usage:
    uv run python -m kg.export_grounding \\
        --source research/kg/obc_app_a_corrected.json \\
        --out research/kg/obc_app_a
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kg.grounding import (
    build_grounding_index,
    load_graph_json,
    uncertain_review_queue,
    write_grounding_index,
    write_review_queue,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, type=Path, help="Corrected graph JSON (kg.correct_graph output)")
    parser.add_argument("--out", required=True, type=Path, help="Output path base (no extension)")
    parser.add_argument(
        "--score-high",
        type=float,
        default=0.45,
        help="Lexical composite_score threshold above which an un-LLM-checked edge is still trusted "
        "(should match the --score-high used for the kg.correct_graph run this source came from)",
    )
    args = parser.parse_args(argv)

    print(f"[1/3] Loading corrected graph: {args.source}")
    graph = load_graph_json(args.source)
    print(f"      {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    print(f"[2/3] Building grounding index (score_high={args.score_high})")
    index = build_grounding_index(graph, score_high=args.score_high)
    n_classes = sum(len(v["classes"]) for v in index.values())
    n_properties = sum(len(v["properties"]) for v in index.values())
    grounding_path = args.out.with_name(args.out.name + "_grounding_index.json")
    write_grounding_index(index, grounding_path)
    print(
        f"      {len(index)} clauses grounded, {n_classes} trusted class links, "
        f"{n_properties} trusted property links -> {grounding_path}"
    )

    print("[3/3] Building uncertain-edge review queue")
    review_rows = uncertain_review_queue(graph)
    review_json = args.out.with_name(args.out.name + "_uncertain_review.json")
    review_csv = args.out.with_name(args.out.name + "_uncertain_review.csv")
    write_review_queue(review_rows, review_json, review_csv)
    print(f"      {len(review_rows)} uncertain edges (sorted most-ambiguous first) -> {review_json} / {review_csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
