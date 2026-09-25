"""
eval/tests/test_grounding.py
---------------------------------------------
Unit tests for kg.grounding.build_grounding_index's per-clause "deontic" and
"dependencies" signal, added so bim-guard's extraction prompt can be informed
by the knowledge graph instead of only corrected by it after the fact.
"""

from __future__ import annotations

import networkx as nx

from kg.grounding import build_grounding_index


def _base_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_node(
        "clause::9.8.4",
        kind="clause",
        ref="9.8.4",
        text_excerpt="Every flight of stairs shall have a minimum run of 280 mm.",
        deontic_operators=["SHALL"],
    )
    graph.add_node(
        "clause::9.8.4.2",
        kind="clause",
        ref="9.8.4.2",
        text_excerpt="Sentence (1) does not apply where a sprinkler system is installed.",
        deontic_operators=[],
    )
    graph.add_edge(
        "clause::9.8.4",
        "clause::9.8.4.2",
        key=0,
        kind="depends_on:exception",
        label="Sentence (2)",
    )
    return graph


def test_deontic_hint_maps_single_clean_operator():
    index = build_grounding_index(_base_graph())
    assert index["clause::9.8.4"]["deontic"] == {
        "modality": "shall",
        "text": "Every flight of stairs shall have a minimum run of 280 mm.",
    }


def test_deontic_hint_absent_when_no_operator():
    index = build_grounding_index(_base_graph())
    assert index["clause::9.8.4.2"]["deontic"] is None


def test_deontic_hint_skips_negated_or_mixed_operators():
    graph = _base_graph()
    graph.nodes["clause::9.8.4"]["deontic_operators"] = ["SHALL", "SHALL NOT"]
    index = build_grounding_index(graph)
    assert index["clause::9.8.4"]["deontic"] is None


def test_dependencies_resolve_target_clause_text():
    index = build_grounding_index(_base_graph())
    deps = index["clause::9.8.4"]["dependencies"]
    assert deps == [
        {
            "edge_type": "depends_on:exception",
            "label": "Sentence (2)",
            "target_ref": "9.8.4.2",
            "target_text_excerpt": "Sentence (1) does not apply where a sprinkler system is installed.",
        }
    ]
    # The target clause has no outgoing dependency edges of its own.
    assert index["clause::9.8.4.2"]["dependencies"] == []


def test_every_clause_gets_an_entry_even_without_a_trusted_candidate():
    index = build_grounding_index(_base_graph())
    assert set(index) == {"clause::9.8.4", "clause::9.8.4.2"}
    assert index["clause::9.8.4"]["classes"] == []
    assert index["clause::9.8.4"]["properties"] == []
