"""
kg/correct_graph.py
------------------------------------------------
CLI: runs the LLM verification/filter pass (kg/llm_correction.py) over a
built knowledge graph's borderline-confidence candidate_class_match /
candidate_property_match edges, via OpenRouter (litellm).

This spends real money against your OpenRouter account (OPENROUTER_API_KEY,
loaded from bim-guard/.env). It ALWAYS prints the number of clauses/edges/
LLM calls it would make and exits without calling anything -- pass --yes to
actually run it.

Usage:
    # dry run: see how many calls this would make, and with what model
    uv run python -m kg.correct_graph --source research/kg/obc_app_a.json

    # for real, against a specific OpenRouter model
    uv run python -m kg.correct_graph --source research/kg/obc_app_a.json \\
        --out research/kg/obc_app_a_corrected \\
        --model openrouter/anthropic/claude-3.5-haiku \\
        --yes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from eval_config import setup_bimguard_path  # noqa: E402

from kg.graph_builder import export_graph  # noqa: E402
from kg.llm_correction import (  # noqa: E402
    ClauseTask,
    apply_results,
    drop_rejected,
    load_bimguard_env,
    load_graph_json,
    select_tasks,
    verify_task,
)

DEFAULT_MODEL = "openrouter/anthropic/claude-3.5-haiku"


async def _run(tasks: List[ClauseTask], model: str, concurrency: int) -> List[Any]:
    import litellm

    litellm.suppress_debug_info = True
    semaphore = asyncio.Semaphore(concurrency)
    coros = [verify_task(task, model, semaphore) for task in tasks]
    return await asyncio.gather(*coros, return_exceptions=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, type=Path, help="Path to a graph JSON export from kg.build_kg")
    parser.add_argument("--out", type=Path, default=None, help="Output path base for the corrected graph (no extension)")
    parser.add_argument("--report", type=Path, default=None, help="Path for the JSON correction report")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="litellm model string, e.g. openrouter/<vendor>/<slug>")
    parser.add_argument("--top-k", type=int, default=5, help="Max candidates per kind (class/property) per clause")
    parser.add_argument("--score-low", type=float, default=0.15, help="Lower bound of the borderline score band")
    parser.add_argument("--score-high", type=float, default=0.45, help="Upper bound of the borderline score band")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent LLM calls")
    parser.add_argument(
        "--drop-rejected",
        action="store_true",
        help="Also write a second graph with llm_verdict=incorrect edges removed",
    )
    parser.add_argument("--yes", action="store_true", help="Actually make the LLM calls (costs money). Without this, dry-run only.")
    args = parser.parse_args(argv)

    out_base = args.out or args.source.with_name(args.source.stem + "_corrected")
    report_path = args.report or out_base.with_name(out_base.name + "_correction_report.json")

    print(f"[1/4] Loading graph: {args.source}")
    graph = load_graph_json(args.source)
    print(f"      {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    print(
        f"[2/4] Selecting borderline candidates "
        f"(score in [{args.score_low}, {args.score_high}], top {args.top_k} per kind per clause)"
    )
    tasks = select_tasks(graph, top_k=args.top_k, score_low=args.score_low, score_high=args.score_high)
    total_candidates = sum(len(t.candidates) for t in tasks)
    print(f"      {len(tasks)} clauses selected, {total_candidates} candidate edges, {len(tasks)} LLM calls planned")

    if not tasks:
        print("Nothing in the borderline band -- nothing to do. Adjust --score-low/--score-high/--top-k.")
        return 0

    if not args.yes:
        print(
            f"\nDRY RUN (no --yes passed): would make {len(tasks)} calls to model "
            f"'{args.model}' via OpenRouter, covering {total_candidates} candidate edges, "
            f"billed to whatever OPENROUTER_API_KEY resolves to. Re-run with --yes to actually run it."
        )
        return 0

    bimguard_root = setup_bimguard_path()
    env_path = load_bimguard_env(bimguard_root)
    print(f"[3/4] Calling {args.model} via OpenRouter ({len(tasks)} calls, concurrency={args.concurrency})")
    if env_path is None:
        print(f"      WARNING: no .env found at {bimguard_root / '.env'} -- relying on process env for OPENROUTER_API_KEY")

    t0 = time.time()
    results = asyncio.run(_run(tasks, args.model, args.concurrency))

    updated_edges = 0
    errors: List[Dict[str, Any]] = []
    for task, outcome in zip(tasks, results):
        if isinstance(outcome, BaseException):
            errors.append({"clause_id": task.clause_id, "error": repr(outcome)})
            continue
        _, verdicts = outcome
        updated_edges += apply_results(graph, task, verdicts, args.model)

    print(
        f"      done in {time.time() - t0:.1f}s -- {updated_edges} edges annotated, "
        f"{len(errors)} clause calls failed"
    )

    print("[4/4] Exporting corrected graph")
    paths = export_graph(graph, out_base)
    for kind, path in paths.items():
        print(f"      {kind}: {path}")

    dropped = 0
    if args.drop_rejected:
        rejected_base = out_base.with_name(out_base.name + "_filtered")
        filtered = graph.copy()
        dropped = drop_rejected(filtered)
        filtered_paths = export_graph(filtered, rejected_base)
        print(f"      dropped {dropped} llm-rejected edges -> {filtered_paths['graphml']} / {filtered_paths['json']}")

    report = {
        "source": str(args.source),
        "model": args.model,
        "top_k": args.top_k,
        "score_low": args.score_low,
        "score_high": args.score_high,
        "clauses_selected": len(tasks),
        "candidate_edges_selected": total_candidates,
        "edges_annotated": updated_edges,
        "edges_dropped_if_filtered": dropped,
        "failed_calls": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
