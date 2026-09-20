"""
kg/build_kg.py
------------------------------------------------
CLI entrypoint: builds a knowledge graph from a DocLang source document
(.dclx or .dclg) linked to the bSDD ontology reference database.

Usage:
    uv run python -m kg.build_kg \\
        --source sources/OBC_2023.App-A_docling.dclx \\
        --out research/kg/obc_app_a

Produces <out>.graphml and <out>.json.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from kg.bsdd_loader import DEFAULT_DICTIONARIES, load_ontology
from kg.clause_builder import build_clause_edges, build_clauses
from kg.dclx_loader import load_dclx_document_xml
from kg.graph_builder import build_graph, export_graph
from kg.similarity import DEFAULT_WEIGHTS, score_candidates


def _load_source_xml(source: Path) -> str:
    if source.suffix.lower() == ".dclx":
        return load_dclx_document_xml(source)
    return source.read_text(encoding="utf-8")


def _term_blob(row: dict) -> str:
    return f"{row.get('name') or ''}. {row.get('definition') or ''} {row.get('description') or ''}".strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Path to a .dclx or .dclg document")
    parser.add_argument("--out", required=True, type=Path, help="Output path base (no extension)")
    parser.add_argument("--bsdd-db", type=Path, default=None, help="Override path to bsdd_ontology.duckdb")
    parser.add_argument(
        "--dictionaries",
        default=",".join(sorted(DEFAULT_DICTIONARIES)),
        help="Comma-separated bSDD dictionary_uri filter, or 'all' for no filter",
    )
    parser.add_argument("--top-k", type=int, default=15, help="Max candidate bSDD terms scored per clause")
    parser.add_argument("--min-score", type=float, default=0.05, help="Minimum composite score to keep a candidate match")
    args = parser.parse_args(argv)

    dictionaries = None if args.dictionaries.strip().lower() == "all" else {
        d.strip() for d in args.dictionaries.split(",") if d.strip()
    }

    t0 = time.time()
    print(f"[1/5] Loading source document: {args.source}")
    xml_content = _load_source_xml(args.source)

    print("[2/5] Building clauses + intra-document edges")
    clauses = build_clauses(xml_content)
    clause_edges = build_clause_edges(clauses)
    print(f"      {len(clauses)} clauses, {len(clause_edges)} clause-to-clause edges")

    print(f"[3/5] Loading bSDD ontology (dictionaries={dictionaries or 'all'})")
    classes, properties, class_property_edges = load_ontology(args.bsdd_db, dictionaries)
    print(f"      {len(classes)} classes, {len(properties)} properties, {len(class_property_edges)} class-property edges")

    print("[4/5] Scoring clause <-> bSDD candidate matches")
    clause_refs = [c.ref for c in clauses]
    clause_texts = [c.text for c in clauses]
    clause_headings = [c.heading for c in clauses]

    class_uris = list(classes)
    class_matches = score_candidates(
        clause_refs, clause_texts, clause_headings,
        class_uris, [classes[u].get("name") or "" for u in class_uris], [_term_blob(classes[u]) for u in class_uris],
        term_kind="class", top_k=args.top_k, min_composite=args.min_score, weights=DEFAULT_WEIGHTS,
    )

    property_uris = list(properties)
    property_matches = score_candidates(
        clause_refs, clause_texts, clause_headings,
        property_uris, [properties[u].get("name") or "" for u in property_uris], [_term_blob(properties[u]) for u in property_uris],
        term_kind="property", top_k=args.top_k, min_composite=args.min_score, weights=DEFAULT_WEIGHTS,
    )
    print(f"      {len(class_matches)} candidate class matches, {len(property_matches)} candidate property matches")

    print("[5/5] Assembling and exporting the graph")
    graph = build_graph(
        clauses, clause_edges, classes, properties, class_property_edges, class_matches, property_matches,
    )
    paths = export_graph(graph, args.out)

    print(
        f"Done in {time.time() - t0:.1f}s — {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges"
    )
    for kind, path in paths.items():
        print(f"  {kind}: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
