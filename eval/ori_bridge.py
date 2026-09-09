"""
ori_bridge.py
------------------------------------------------
Subprocess bridge between the Ori Eval TypeScript harness (evals/rule-extraction/)
and BIM-Guard's real LLM rule-extraction code.

Ori Eval (openrouter.ai/docs/guides/ori/eval) runs *.eval.ts files under
`bun test`, and its `setupAgent()`/`agent.run()` surface is built for
coding-agent harnesses (Claude Code, Codex, ...) driven by tool calls in a
working directory. BIM-Guard's rule extractor is not that: it's a single
non-agentic structured-output LLM call
(app.modules.rule_builder.llamaindex_rule_generator.LlamaIndexRuleGenerator),
written and owned by bim-guard, not this repo. So the eval files don't
reimplement that prompt/pipeline in TypeScript — they shell out to this
script, which calls the real Python code, and only use Ori for what it's
built for: OpenRouter's live model catalog (candidateModels) and LLM-as-judge
scoring (setupJudge). Every "model" the eval files iterate is a litellm model
string ("openrouter/<vendor>/<slug>", e.g. "openrouter/openai/gpt-4o-mini")
passed straight through as the `model` override LlamaIndexRuleGenerator
already accepts per-call (the same override the live Rule Extraction UI's
model selector uses) — litellm resolves it against OPENROUTER_API_KEY.

NOTE on bim-guard's dependencies: this script imports bim-guard's
`app.modules.rule_builder` / `app.modules.document_parsing` packages, which
need bim-guard's own venv (ifcopenshell, llama-index, litellm — not
dependencies of this eval repo). Run it with bim-guard's interpreter, e.g.:
    BIMGUARD_PATH=../bim-guard "$BIMGUARD_PATH/.venv/Scripts/python.exe" eval/ori_bridge.py ...
evals/rule-extraction/lib/bridge.ts resolves that interpreter automatically
(BIMGUARD_PYTHON env var, else `<BIMGUARD_PATH>/.venv/{Scripts,bin}/python*`).

Deliberately imports only `app.modules.rule_builder.llamaindex_rule_generator`
and `app.modules.document_parsing.*` — NOT `app.services` or `app.main`.
Importing `app.services` runs `app/services/__init__.py`, which pulls in
`analysis_runner` -> ruleset seeding that hits bim-guard's LIVE Supabase
project at import time (observed while wiring this up). This bridge must
never do that, so it stays scoped to the pure `app.modules.*` extraction
code, which has no such side effect.

Two subcommands, one JSON object on stdout each (errors -> {"error": ...},
exit 1; success -> exit 0). No print()s besides that single JSON document —
the TS side parses stdout directly.

  case  --case-id <id> --model <litellm-model-string>
      Runs LlamaIndexRuleGenerator.extract_rules_from_text() — the live app's
      current single rule-extraction entrypoint — against one of
      eval_harness.EVAL_CASES's hand-authored golden sentences.
      Output: {"generated": <rule dict or null>, "duration_s": ...}

  gold  --model <litellm-model-string> [--limit N]
      Runs the same extractor over the real gold PDF, chunked the same way
      RuleExtractionService.extract_rules_from_text() currently does
      (SectionChunker, falling back to one whole-text chunk — see
      _extract_gold's comment for why this isn't score_rule_extraction.py's
      own chunking), then scores recovered rules against GOLD_RULES using a
      same-repo copy of score_rule_extraction.match_gold_to_extracted's exact
      matching logic (see the "Gold-rule matching" comment below for why it's
      copied rather than imported). Output: {"hits": N, "total_gold": N,
      "recall": 0..1, "extracted_total": N, "missed": [...], "duration_s": ...}

      Caveat inherited from the live extractor's dict adapter (see
      LlamaIndexRuleGenerator.extract_rules_from_text): it does not surface
      value_min_property/value_max_property, so GOLD_RULES entries expressing
      a relative bound (e.g. OBC 9.8.4.3.(3) "Run to Run+25mm") can never
      match and always land in "missed" — a real production gap, not a bug
      in this bridge.

Usage (called by the TS evals via bridge.ts, or directly for debugging):
    BIMGUARD_PATH=../bim-guard <bimguard-python> eval/ori_bridge.py case --case-id stair_width --model openrouter/openai/gpt-4o-mini
    BIMGUARD_PATH=../bim-guard <bimguard-python> eval/ori_bridge.py gold --model openrouter/anthropic/claude-3.5-haiku --limit 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import setup_bimguard_path  # noqa: E402

setup_bimguard_path()


_REAL_STDOUT = sys.stdout


def _emit(payload: dict) -> None:
    """Write the one JSON document this script promises, to the real stdout.

    bim-guard's own code prints diagnostics straight to stdout in places
    (SectionChunker, observed while wiring this up) — outside this script's
    control and not something to patch around in bim-guard. main() redirects
    sys.stdout to stderr for the whole extraction call, so by the time this
    runs, `sys.stdout` is stderr; write to the saved real handle instead so
    the caller's stdout carries exactly one JSON document either way.
    """
    _REAL_STDOUT.write(json.dumps(payload))
    _REAL_STDOUT.flush()


def _rule_generator():
    from app.modules.rule_builder.llamaindex_rule_generator import LlamaIndexRuleGenerator

    return LlamaIndexRuleGenerator()


def cmd_case(case_id: str, model: str) -> dict:
    import eval_harness  # module-level import only reads EVAL_CASES; safe (no app.services touched)

    case = next((c for c in eval_harness.EVAL_CASES if c["id"] == case_id), None)
    if case is None:
        raise ValueError(f"unknown case_id {case_id!r}; available: {[c['id'] for c in eval_harness.EVAL_CASES]}")

    t0 = time.perf_counter()
    extraction_error: str | None = None
    try:
        rules = asyncio.run(_rule_generator().extract_rules_from_text(case["source_text"], model=model))
    except Exception as exc:
        # A malformed field in one model's reply (observed: openai/gpt-4o-mini
        # occasionally returns "" instead of [] for applies_when_materials,
        # failing Pydantic validation) must read as "this model produced no
        # usable rule for this case" to the judge, not crash the whole run —
        # same principle as _extract_gold's per-chunk try/except.
        rules = []
        extraction_error = f"{type(exc).__name__}: {exc}"
    duration_s = time.perf_counter() - t0

    return {
        "case_id": case_id,
        "source_text": case["source_text"],
        "ideal_rule": case["ideal_rule"],
        "generated": rules[0] if rules else None,
        "extraction_error": extraction_error,
        "duration_s": duration_s,
    }


# ── Gold-rule matching ──────────────────────────────────────────────────
# score_rule_extraction.py defines this exact matcher (_same_property /
# _num_close / match_gold_to_extracted) — but that module's own top-level
# imports (KeywordFilter, DependencyParser, ConfidenceScorer, TableRuleBuilder
# from app.modules.document_parsing) no longer resolve: bim-guard's
# "Remove dead legacy NLP extraction modules, consolidate to one LLM
# rule-extraction path" commit deleted those submodules, so `import
# score_rule_extraction` now fails before reaching any of its still-useful
# code (GOLD_RULES, match_gold_to_extracted). Fixing that whole script is a
# separate, larger job (plan-26003.md already tracks it as a known blocker);
# fixing it here would silently paper over the break rather than surface it.
# So this is a deliberate, minimal, same-repo copy of just the matcher,
# kept byte-for-byte in sync with score_rule_extraction.py's version.
def _same_property(a: str, b: str, alias_groups: list[set[str]]) -> bool:
    if not a or not b:
        return False
    a, b = a.strip().lower(), b.strip().lower()
    if a == b:
        return True
    return any(a in {g.lower() for g in grp} and b in {g.lower() for g in grp} for grp in alias_groups)


def _num_close(a, b, tol: float = 0.5) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def _extracted_value(rule: dict):
    return rule.get("value") if rule.get("value") is not None else rule.get("check_value")


def _match_gold_to_extracted(gold: dict, extracted: list[dict], alias_groups: list[set[str]]) -> dict | None:
    for rule in extracted:
        if str(rule.get("target", "")).strip().lower() != gold["target"].lower():
            continue
        if not _same_property(str(rule.get("property_name", "")), gold["property_name"], alias_groups):
            continue
        if "value_min_property" in gold:
            if rule.get("value_min_property") or rule.get("value_max_property"):
                return rule
            continue
        if gold["operator"] == "between":
            if _num_close(rule.get("value_min"), gold.get("value_min")) and _num_close(
                rule.get("value_max"), gold.get("value_max")
            ):
                return rule
        else:
            if _num_close(_extracted_value(rule), gold.get("value")):
                return rule
    return None


async def _extract_gold(model: str, limit: int | None) -> dict:
    import glob

    bimguard_root = setup_bimguard_path()
    os.chdir(bimguard_root)  # the gold PDF's path resolves via a cwd-relative glob
    modules_path = str(bimguard_root / "app" / "modules")
    if modules_path not in sys.path:
        sys.path.insert(0, modules_path)  # document_parsing/ifc_reader are top-level packages under here

    from document_parsing import DocumentReader
    from document_parsing.section_chunker import SectionChunker
    from ifc_reader import _PROPERTY_ALIASES

    try:
        from eval_gold_code_9_8_stairs import GOLD_RULES
    except ImportError:
        from eval.eval_gold_code_9_8_stairs import GOLD_RULES

    alias_groups = [{canon, *aliases} for canon, aliases in _PROPERTY_ALIASES.items()]

    pdf_path = glob.glob("data/uploads/*pdf_stairs_mock.pdf")[0]
    pdf_bytes = open(pdf_path, "rb").read()
    pypdf_text = DocumentReader().parse_pdf(pdf_bytes)

    # Mirrors app.services.rule_extraction_service.RuleExtractionService's
    # CURRENT chunking exactly (SectionChunker, fall back to one whole-text
    # chunk) — the legacy KeywordFilter/DependencyParser/ConfidenceScorer
    # stages this repo's score_rule_extraction.py replicated no longer exist
    # in the live pipeline either, so matching the current one is the more
    # faithful choice, not just the available one.
    structured_chunks = SectionChunker().chunk(pypdf_text)
    chunks = structured_chunks or [{"text": pypdf_text}]
    if limit:
        chunks = chunks[:limit]

    generator = _rule_generator()
    llm_rules: list[dict] = []
    failed_chunks = 0
    for chunk in chunks:
        text = chunk.get("text", "").strip()
        if not text:
            continue
        try:
            rules = await generator.extract_rules_from_text(text, model=model)
        except Exception:
            # A single chunk's malformed LLM reply (e.g. a field the model
            # returned as the wrong JSON type) must not sink the whole
            # model's recall score to "crashed" — score it as 0 rules for
            # that chunk instead, same principle as score_rule_extraction.py's
            # StripThinkingClient.unparseable counter.
            failed_chunks += 1
            continue
        llm_rules.extend(rules)

    hits, misses = [], []
    for gold in GOLD_RULES:
        (hits if _match_gold_to_extracted(gold, llm_rules, alias_groups) else misses).append(gold)

    total_gold = len(GOLD_RULES)
    return {
        "chunks_sent": len(chunks),
        "failed_chunks": failed_chunks,
        "hits": len(hits),
        "total_gold": total_gold,
        "recall": (len(hits) / total_gold) if total_gold else 0.0,
        "extracted_total": len(llm_rules),
        "missed": [g["ref"] for g in misses],
    }


def cmd_gold(model: str, limit: int | None) -> dict:
    t0 = time.perf_counter()
    result = asyncio.run(_extract_gold(model, limit))
    result["duration_s"] = time.perf_counter() - t0
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    case_p = sub.add_parser("case")
    case_p.add_argument("--case-id", required=True)
    case_p.add_argument("--model", required=True)

    gold_p = sub.add_parser("gold")
    gold_p.add_argument("--model", required=True)
    gold_p.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()

    sys.stdout = sys.stderr  # see _emit()'s docstring: keep bim-guard's stray prints off the JSON channel
    try:
        if args.mode == "case":
            payload = cmd_case(args.case_id, args.model)
        else:
            payload = cmd_gold(args.model, args.limit)
    except Exception as exc:  # noqa: BLE001 - bridge boundary: report, don't crash the eval run
        _emit({"error": f"{type(exc).__name__}: {exc}"})
        return 1
    finally:
        sys.stdout = _REAL_STDOUT

    _emit(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
