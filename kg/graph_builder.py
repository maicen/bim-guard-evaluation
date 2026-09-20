"""
kg/graph_builder.py
------------------------------------------------
Assembles the final knowledge graph (networkx.MultiDiGraph) from clause
units, clause-to-clause edges, bSDD ontology terms, and scored
clause<->ontology candidate matches. Exports to GraphML (for Gephi/Cytoscape/
yEd "maps") and node-link JSON (for programmatic reuse/scoring).
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List

import networkx as nx
from networkx.readwrite import json_graph

from kg.bsdd_loader import ClassRow, EdgeRow, PropertyRow
from kg.clause_builder import Clause, ClauseEdge
from kg.similarity import CandidateMatch


def build_graph(
    clauses: List[Clause],
    clause_edges: List[ClauseEdge],
    classes: Dict[str, ClassRow],
    properties: Dict[str, PropertyRow],
    class_property_edges: List[EdgeRow],
    class_matches: List[CandidateMatch],
    property_matches: List[CandidateMatch],
) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    # GraphML writes each MultiDiGraph edge's `key` straight through as the
    # document-wide <edge id="...">, so keys must be unique across the WHOLE
    # graph, not just per (u, v) pair. A single shared counter guarantees
    # that; the old scheme (e.g. f"{kind}:{score}") let unrelated edges with
    # the same rounded score or label collide, silently dropping edges on
    # import into GraphML tools such as Gephi.
    edge_ids: Iterator[int] = itertools.count()

    for clause in clauses:
        graph.add_node(
            _clause_node_id(clause.ref),
            kind="clause",
            ref=clause.ref,
            heading=clause.heading,
            level=clause.level,
            section_path=list(clause.section_path),
            text_excerpt=clause.text[:500],
            char_count=len(clause.text),
            element_ids=list(clause.element_ids),
            deontic_operators=sorted({d.get("operator", "") for d in clause.deontics if d.get("operator")}),
            has_conditions=bool(clause.conditions),
            dimension_count=len(clause.dimensions),
            ifc_hints=sorted({h.get("ifc_class", "") for h in clause.ifc_hints if h.get("ifc_class")}),
        )

    for edge in clause_edges:
        graph.add_edge(
            _clause_node_id(edge.source_ref),
            _clause_node_id(edge.target_ref),
            key=next(edge_ids),
            kind=edge.edge_type,
            label=edge.label,
        )

    referenced_class_uris = {m.term_uri for m in class_matches}
    referenced_property_uris = {m.term_uri for m in property_matches} | {
        e["property_uri"] for e in class_property_edges if e["class_uri"] in referenced_class_uris
    }

    for uri in referenced_class_uris:
        row = classes.get(uri)
        if row is None:
            continue
        graph.add_node(
            _bsdd_node_id(uri),
            kind="bsdd_class",
            uri=uri,
            code=row.get("code") or "",
            name=row.get("name") or "",
            dictionary_uri=row.get("dictionary_uri") or "",
            class_type=row.get("class_type") or "",
            definition=(row.get("definition") or "")[:500],
        )

    for uri in referenced_property_uris:
        row = properties.get(uri)
        if row is None:
            continue
        graph.add_node(
            _bsdd_node_id(uri),
            kind="bsdd_property",
            uri=uri,
            code=row.get("code") or "",
            name=row.get("name") or "",
            data_type=row.get("data_type") or "",
            definition=(row.get("definition") or "")[:500],
        )

    for edge in class_property_edges:
        if edge["class_uri"] not in referenced_class_uris:
            continue
        if edge["property_uri"] not in referenced_property_uris:
            continue
        graph.add_edge(
            _bsdd_node_id(edge["class_uri"]),
            _bsdd_node_id(edge["property_uri"]),
            key=next(edge_ids),
            kind="class_has_property",
            property_set=edge.get("property_set") or "",
        )

    for match in class_matches:
        _add_candidate_edge(graph, match, "candidate_class_match", edge_ids)

    for match in property_matches:
        _add_candidate_edge(graph, match, "candidate_property_match", edge_ids)

    return graph


def _add_candidate_edge(
    graph: nx.MultiDiGraph, match: CandidateMatch, edge_kind: str, edge_ids: Iterator[int]
) -> None:
    source = _clause_node_id(match.clause_ref)
    target = _bsdd_node_id(match.term_uri)
    if source not in graph or target not in graph:
        return
    graph.add_edge(
        source,
        target,
        key=next(edge_ids),
        kind=edge_kind,
        composite_score=round(match.composite, 4),
        **{f"signal_{name}": round(value, 4) for name, value in match.signals.items()},
    )


def _clause_node_id(ref: str) -> str:
    return f"clause::{ref}"


def _bsdd_node_id(uri: str) -> str:
    return f"bsdd::{uri}"


def export_graph(graph: nx.MultiDiGraph, out_base: Path) -> Dict[str, Path]:
    """Writes <out_base>.graphml and <out_base>.json. Returns the written paths."""
    out_base.parent.mkdir(parents=True, exist_ok=True)

    graphml_path = out_base.with_suffix(".graphml")
    nx.write_graphml(_graphml_safe_copy(graph), graphml_path)

    json_path = out_base.with_suffix(".json")
    data = json_graph.node_link_data(graph, edges="edges")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    return {"graphml": graphml_path, "json": json_path}


def _graphml_safe_copy(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """GraphML attributes must be scalar (str/int/float/bool); this returns a
    copy with list/None attributes flattened to strings, leaving the original
    graph (used for the richer JSON export) untouched."""
    safe = nx.MultiDiGraph()
    for node, attrs in graph.nodes(data=True):
        safe.add_node(node, **{k: _flatten(v) for k, v in attrs.items()})
    for u, v, key, attrs in graph.edges(keys=True, data=True):
        safe.add_edge(u, v, key=key, **{k: _flatten(val) for k, val in attrs.items()})
    return safe


def _flatten(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return value
