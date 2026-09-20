"""
kg/llm_correction.py
------------------------------------------------
Uses an LLM (via litellm, targeting OpenRouter) to verify/filter the
knowledge graph's lexical candidate_class_match / candidate_property_match
edges (see kg/similarity.py) -- "verify & filter only", per the scoping
decision: this never invents new edges, it only judges edges the lexical
scorer already proposed.

Scope: for each clause, take its top-K candidate edges (per kind: class or
property) whose composite score falls inside a mid-confidence band --
edges scoring above that band look like confident lexical hits (near-exact
name matches) and edges below it look like clear noise (near the
score_candidates() floor), so an LLM call adds the least value there and
the most value on the ambiguous middle. One LLM call covers a whole
clause's remaining candidates (class + property together) rather than one
call per edge, since it's cheaper and gives the model full clause context.

Corrections are written as NEW edge attributes (llm_verdict, llm_confidence,
llm_reason, llm_model) -- the original composite_score/signal_* attributes
from the lexical pass are left untouched, so a corrected graph stays
inspectable: you can always see what the lexical scorer said vs. what the
LLM said.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from networkx.readwrite import json_graph

_BIMGUARD_ENV_LOADED = False


def load_bimguard_env(bimguard_root: Path) -> Optional[Path]:
    """Loads OPENROUTER_API_KEY (and friends) from bim-guard's own .env file.

    Mirrors bim-guard's own app.environment.load_env_file (override=False:
    a value already set in the process environment always wins), but is
    implemented standalone here rather than imported, since it's a two-line
    stdlib+dotenv operation and importing app.environment would pull in
    bim-guard's `app` package for no real reuse benefit.
    """
    global _BIMGUARD_ENV_LOADED
    from dotenv import load_dotenv

    env_path = bimguard_root / ".env"
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path, override=False)
        _BIMGUARD_ENV_LOADED = True
        return env_path
    return None


def load_graph_json(path: Path) -> nx.MultiDiGraph:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return json_graph.node_link_graph(data, directed=True, multigraph=True, edges="edges")


CANDIDATE_KINDS = ("candidate_class_match", "candidate_property_match")


@dataclass
class Candidate:
    edge_key: Any
    target_id: str
    kind: str  # candidate_class_match | candidate_property_match
    composite_score: float
    target_attrs: Dict[str, Any]


@dataclass
class ClauseTask:
    clause_id: str
    clause_attrs: Dict[str, Any]
    candidates: List[Candidate] = field(default_factory=list)


def select_tasks(
    graph: nx.MultiDiGraph,
    *,
    top_k: int = 5,
    score_low: float = 0.15,
    score_high: float = 0.45,
) -> List[ClauseTask]:
    """Builds one ClauseTask per clause that has >=1 borderline-score candidate.

    Per clause and per candidate kind, candidates are sorted by
    composite_score descending, filtered to [score_low, score_high], and
    capped at top_k -- so a clause contributes at most 2*top_k candidates
    (top_k class + top_k property) to its single LLM call.
    """
    tasks: List[ClauseTask] = []
    for node, attrs in graph.nodes(data=True):
        if attrs.get("kind") != "clause":
            continue

        by_kind: Dict[str, List[Candidate]] = {k: [] for k in CANDIDATE_KINDS}
        for _, target, key, edge_attrs in graph.out_edges(node, keys=True, data=True):
            kind = edge_attrs.get("kind")
            if kind not in CANDIDATE_KINDS:
                continue
            score = edge_attrs.get("composite_score", 0.0)
            if not (score_low <= score <= score_high):
                continue
            by_kind[kind].append(
                Candidate(
                    edge_key=key,
                    target_id=target,
                    kind=kind,
                    composite_score=score,
                    target_attrs=dict(graph.nodes[target]),
                )
            )

        candidates: List[Candidate] = []
        for kind, cands in by_kind.items():
            cands.sort(key=lambda c: -c.composite_score)
            candidates.extend(cands[:top_k])

        if candidates:
            tasks.append(ClauseTask(clause_id=node, clause_attrs=dict(attrs), candidates=candidates))

    return tasks


_SYSTEM_PROMPT = (
    "You are verifying candidate links in a knowledge graph between clauses of a "
    "building code document and terms (classes/properties) from the bSDD "
    "(buildingSMART Data Dictionary) ontology. The candidate links were proposed by "
    "a cheap lexical similarity scorer (TF-IDF cosine, token Jaccard, fuzzy string "
    "match, substring match) and are frequently wrong -- your job is to judge each "
    "one on meaning, not surface similarity. A clause and a bSDD term are a genuine "
    "match only if the clause is substantively about the real-world thing the bSDD "
    "term denotes (e.g. a clause discussing curtain wall glazing requirements "
    "genuinely relates to the bSDD class 'Curtain Wall'; a clause that merely "
    "contains an administrative word that happens to share letters with a bSDD term "
    "name does not). Respond with strict JSON only, no prose outside the JSON."
)


def build_prompt(task: ClauseTask) -> str:
    clause = task.clause_attrs
    lines = [
        f"CLAUSE {clause.get('ref', task.clause_id)}: {clause.get('heading', '')}",
        (clause.get("text_excerpt") or "").strip(),
        "",
        "CANDIDATE TERMS (lexical scorer's rough similarity score is shown for reference only "
        "-- do not simply trust it):",
    ]
    for i, cand in enumerate(task.candidates):
        term = cand.target_attrs
        term_kind = "bSDD class" if cand.kind == "candidate_class_match" else "bSDD property"
        definition = (term.get("definition") or "").strip()
        lines.append(
            f"[{i}] ({term_kind}, lexical_score={cand.composite_score:.3f}) "
            f"name=\"{term.get('name', '')}\" code=\"{term.get('code', '')}\" "
            f"definition=\"{definition[:300]}\""
        )
    lines.append("")
    lines.append(
        "Return a JSON object: "
        '{"results": [{"index": <int>, "verdict": "correct"|"incorrect"|"uncertain", '
        '"confidence": <0.0-1.0>, "reason": "<one short sentence>"}, ...]} '
        "with exactly one entry per candidate index above."
    )
    return "\n".join(lines)


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_llm_response(text: str) -> Dict[int, Dict[str, Any]]:
    """Parses the model's JSON reply into {candidate_index: {verdict, confidence, reason}}.

    Lenient: strips markdown code fences and grabs the first {...} block,
    since not every OpenRouter-routed model honors response_format strictly.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    match = _JSON_OBJECT_RE.search(cleaned)
    if not match:
        raise ValueError(f"no JSON object found in LLM response: {text[:200]!r}")
    payload = json.loads(match.group(0))
    results = payload.get("results", [])
    out: Dict[int, Dict[str, Any]] = {}
    for item in results:
        idx = item.get("index")
        if idx is None:
            continue
        out[int(idx)] = {
            "verdict": item.get("verdict", "uncertain"),
            "confidence": float(item.get("confidence", 0.0)),
            "reason": item.get("reason", ""),
        }
    return out


async def verify_task(task: ClauseTask, model: str, semaphore: "Any") -> Tuple[ClauseTask, Dict[int, Dict[str, Any]]]:
    import litellm

    prompt = build_prompt(task)
    async with semaphore:
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=1200,
        )
    text = response["choices"][0]["message"]["content"]
    return task, parse_llm_response(text)


def apply_results(graph: nx.MultiDiGraph, task: ClauseTask, results: Dict[int, Dict[str, Any]], model: str) -> int:
    """Writes llm_verdict/llm_confidence/llm_reason/llm_model onto each verified edge.
    Returns the number of edges updated."""
    updated = 0
    for i, cand in enumerate(task.candidates):
        verdict = results.get(i)
        if verdict is None:
            continue
        graph.edges[task.clause_id, cand.target_id, cand.edge_key]["llm_verdict"] = verdict["verdict"]
        graph.edges[task.clause_id, cand.target_id, cand.edge_key]["llm_confidence"] = round(
            float(verdict["confidence"]), 4
        )
        graph.edges[task.clause_id, cand.target_id, cand.edge_key]["llm_reason"] = verdict["reason"]
        graph.edges[task.clause_id, cand.target_id, cand.edge_key]["llm_model"] = model
        updated += 1
    return updated


def drop_rejected(graph: nx.MultiDiGraph, verdicts: Tuple[str, ...] = ("incorrect",)) -> int:
    """Returns a count of (and, if called, removes) edges whose llm_verdict is in `verdicts`.
    Call this on a graph you're about to export as the "corrected" version."""
    to_remove = [
        (u, v, k)
        for u, v, k, attrs in graph.edges(keys=True, data=True)
        if attrs.get("llm_verdict") in verdicts
    ]
    graph.remove_edges_from(to_remove)
    return len(to_remove)
