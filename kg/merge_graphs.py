"""
kg/merge_graphs.py
------------------------------------------------
CLI: appends one or more per-code knowledge graphs (from kg.build_kg, and
usually kg.correct_graph's *_corrected_filtered output) onto a combined,
multi-code graph. Third/fourth step of the repeatable code-ingestion
pipeline documented in docs/kg-ingestion-pipeline.md.

Every clause node is namespaced by its doc_id ("<doc_id>::clause::<ref>")
so that two codes' clause numbering (e.g. two documents both having a
clause "1.1") can never collide. bSDD ontology nodes ("bsdd::<uri>") are
NOT namespaced -- they are the same shared ontology across every code, so
composing two graphs naturally unions/dedupes them onto the same node,
which is the whole point of putting multiple codes in one graph (you can
see which codes reference the same bSDD class/property).

Usage:
    # bootstrap a combined graph from the first code (tags its clauses
    # with doc_id "obc_app_a" since the source graph predates this script)
    uv run python -m kg.merge_graphs \\
        --base research/kg/obc_app_a_corrected_filtered.json --base-doc-id obc_app_a \\
        --add sbc_201=research/kg/sbc_201/sbc_201_corrected_filtered.json \\
        --out research/kg/combined/combined

    # append a third code onto the already-combined graph later
    uv run python -m kg.merge_graphs \\
        --base research/kg/combined/combined.json \\
        --add nbc_2020=research/kg/nbc_2020/nbc_2020_corrected_filtered.json \\
        --out research/kg/combined/combined
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import networkx as nx

from kg.graph_builder import export_graph
from kg.llm_correction import load_graph_json

_CLAUSE_PREFIX = "clause::"


def _namespace_clause_nodes(graph: nx.MultiDiGraph, doc_id: str) -> nx.MultiDiGraph:
    """Returns a copy of graph with every clause:: node renamed to
    <doc_id>::clause::<ref>, tagged with a doc_id attribute. bsdd:: nodes
    (and any node already tagged with a doc_id, i.e. already namespaced by
    a prior merge) are left untouched so they union by shared node id."""
    mapping = {}
    for node, attrs in graph.nodes(data=True):
        if node.startswith(_CLAUSE_PREFIX) and "doc_id" not in attrs:
            mapping[node] = f"{doc_id}::{node}"
    renamed = nx.relabel_nodes(graph, mapping, copy=True)
    for node in mapping.values():
        renamed.nodes[node]["doc_id"] = doc_id
    return renamed


def _reassign_edge_keys(graph: nx.MultiDiGraph, start: int) -> nx.MultiDiGraph:
    """MultiDiGraph edge keys must be unique across the whole graph (see
    kg/graph_builder.py's edge_ids counter) -- re-key with a fresh counter
    offset past whatever the base graph already used, so composing two
    graphs that each started their own counter at 0 can't collide."""
    fresh = nx.MultiDiGraph()
    fresh.add_nodes_from(graph.nodes(data=True))
    counter = itertools.count(start)
    for u, v, attrs in graph.edges(data=True):
        fresh.add_edge(u, v, key=next(counter), **attrs)
    return fresh, next(counter)


def merge(
    base: nx.MultiDiGraph | None,
    additions: list[tuple[str, nx.MultiDiGraph]],
) -> nx.MultiDiGraph:
    combined = base.copy() if base is not None else nx.MultiDiGraph()
    next_key = max((k for *_, k in combined.edges(keys=True)), default=-1) + 1

    for doc_id, graph in additions:
        existing_doc_ids = {attrs.get("doc_id") for _, attrs in combined.nodes(data=True)}
        if doc_id in existing_doc_ids:
            raise ValueError(f"doc_id '{doc_id}' is already present in the base graph -- pick a distinct doc_id")
        namespaced = _namespace_clause_nodes(graph, doc_id)
        namespaced, next_key = _reassign_edge_keys(namespaced, next_key)
        combined = nx.compose(combined, namespaced)

    return combined


def _parse_add_arg(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"--add must be DOC_ID=PATH, got: {raw!r}")
    doc_id, _, path_str = raw.partition("=")
    doc_id, path_str = doc_id.strip(), path_str.strip()
    if not doc_id or not path_str:
        raise argparse.ArgumentTypeError(f"--add must be DOC_ID=PATH, got: {raw!r}")
    return doc_id, Path(path_str)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base", type=Path, default=None,
        help="Existing combined (or single-code) graph JSON to append onto. Omit to start a fresh combined graph.",
    )
    parser.add_argument(
        "--base-doc-id", default=None,
        help="doc_id to tag the base graph's clauses with, if they aren't already tagged "
             "(needed the first time you fold in a pre-merge_graphs.py graph, e.g. obc_app_a).",
    )
    parser.add_argument(
        "--add", action="append", required=True, type=_parse_add_arg, metavar="DOC_ID=PATH",
        help="One code's graph JSON to append, as doc_id=path. Repeatable.",
    )
    parser.add_argument("--out", required=True, type=Path, help="Output path base for the combined graph (no extension)")
    args = parser.parse_args(argv)

    base_graph = None
    if args.base is not None:
        print(f"[1/3] Loading base graph: {args.base}")
        base_graph = load_graph_json(args.base)
        tagged = sum(1 for _, attrs in base_graph.nodes(data=True) if attrs.get("doc_id"))
        if tagged == 0:
            if not args.base_doc_id:
                parser.error(
                    f"{args.base} has no doc_id-tagged nodes yet (predates kg.merge_graphs) -- "
                    "pass --base-doc-id to tag it on first merge"
                )
            base_graph = _namespace_clause_nodes(base_graph, args.base_doc_id)
        print(f"      {base_graph.number_of_nodes()} nodes, {base_graph.number_of_edges()} edges")
    else:
        print("[1/3] No --base given -- starting a fresh combined graph")

    print(f"[2/3] Loading {len(args.add)} graph(s) to append: {', '.join(d for d, _ in args.add)}")
    additions = []
    for doc_id, path in args.add:
        graph = load_graph_json(path)
        print(f"      {doc_id}: {path} -- {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        additions.append((doc_id, graph))

    combined = merge(base_graph, additions)

    print("[3/3] Exporting combined graph")
    paths = export_graph(combined, args.out)
    print(
        f"Done -- combined graph has {combined.number_of_nodes()} nodes, "
        f"{combined.number_of_edges()} edges"
    )
    for kind, path in paths.items():
        print(f"  {kind}: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
