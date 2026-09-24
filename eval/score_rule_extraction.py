"""
score_rule_extraction.py
------------------------------------------------
Phase-1 eval harness for Module 3 rule extraction accuracy, scored against
eval_gold_code_9_8_stairs.py (hand-annotated ground truth for CODE 9.8.2-9.8.4.7,
data/uploads/..._pdf_stairs_mock.pdf).

Mirrors score_nlp_annotation.py's style (plain script, print()-based, no pytest).

  PART A - minimal chunk prep only (see plan-26003.md):
    The original A1/A3/A4/A5 structural diagnostics replicated bim-guard's
    pre-DocLang pipeline (DocumentReader, UnstructuredExtractor, KeywordFilter,
    DependencyParser, ConfidenceScorer, TableRuleBuilder) — none of which exist
    in bim-guard's current Docling/DocLang document_parsing architecture, and
    rebuilding them against it is out of scope here. Part A now only extracts
    the gold PDF's text (via pypdf directly, since bim-guard's own
    extract_document_text() requires a running Docling service with no
    dependency-light fallback) and splits it into SectionChunker chunks, sent
    to the LLM unfiltered — there is no confidence-filtering stage left to
    replicate.

  PART B - LLM accuracy (needs a local Ollama daemon; skipped with
    instructions if absent):
    Runs LlamaIndexRuleGenerator (app.modules.rule_builder.llamaindex_rule_generator
    — replaces the deleted app.services.rule_extractor.LiteLLMRuleExtractor)
    over the chunks from Part A and scores per-field precision/recall +
    property-name grounding against gold. Scored against local Ollama
    (qwen3:14b) by default, so the whole 29-gold-rule sweep costs nothing and
    needs no vendor API key. Set BIM_GUARD_RULE_MODEL to score a hosted model
    instead (the live app default is DEFAULT_LLM_MODEL in app.modules.config).

Usage:
    uv run python score_rule_extraction.py
"""

import argparse
import asyncio
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

from pathlib import Path

_START = time.perf_counter()

# Resolve evaluation dir and core bim-guard repo path
REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
BIMGUARD_CORE = Path(os.getenv("BIMGUARD_PATH", str(REPO_ROOT.parent / "bim-guard")))

for p in [EVAL_DIR, REPO_ROOT, BIMGUARD_CORE, BIMGUARD_CORE / "app" / "modules", Path("app/modules")]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from eval_config import build_result, new_run_id, write_result  # noqa: E402

try:
    from eval_gold_code_9_8_stairs import EXCLUDED_CLAUSES, GOLD_RULES
except ImportError:
    from eval.eval_gold_code_9_8_stairs import EXCLUDED_CLAUSES, GOLD_RULES

from document_parsing.section_chunker import SectionChunker  # noqa: E402
from ifc_reader import _PROPERTY_ALIASES  # noqa: E402

PDF_PATH = glob.glob("data/uploads/*pdf_stairs_mock.pdf")[0]

# ── Part-B model: local Ollama by default (free, no vendor key) ────────────
# LiteLLMClient takes no base_url argument, so the endpoint is handed to litellm
# the way litellm expects for the ollama provider: the OLLAMA_API_BASE env var
# (see litellm/llms/ollama/common_utils.py). Set it before the client is built.
#
# "ollama_chat/" not "ollama/": the plain "ollama/" prefix routes to /api/generate,
# where litellm flattens the system+user messages into one prompt. Measured on this
# box, qwen3:14b then answers "{}" to every chunk — a false 0% score. "ollama_chat/"
# routes to /api/chat, keeps the roles intact, and returns well-formed rule JSON.
OLLAMA_MODEL = "ollama_chat/qwen3:14b"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_API_KEY = "ollama"  # placeholder — Ollama ignores it; litellm just wants a value

# ── Property-name equivalence (mirrors ifc_reader's alias table) ──────
_ALIAS_GROUPS: list[set[str]] = [{canon, *aliases} for canon, aliases in _PROPERTY_ALIASES.items()]


def _same_property(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a, b = a.strip().lower(), b.strip().lower()
    if a == b:
        return True
    return any(a in {g.lower() for g in grp} and b in {g.lower() for g in grp} for grp in _ALIAS_GROUPS)


def _num_close(a, b, tol=0.5) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def _extracted_value(rule: dict):
    return rule.get("value") if rule.get("value") is not None else rule.get("check_value")


def match_gold_to_extracted(gold: dict, extracted: list[dict]) -> dict | None:
    for rule in extracted:
        if str(rule.get("target", "")).strip().lower() != gold["target"].lower():
            continue
        if not _same_property(str(rule.get("property_name", "")), gold["property_name"]):
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


def _extracted_matches_any_gold(rule: dict, gold_rules: list[dict]) -> bool:
    """Mirror match_gold_to_extracted's criteria, from the extracted side, so an
    extracted rule that fails to pair with ANY gold rule counts as a false positive."""
    for gold in gold_rules:
        if match_gold_to_extracted(gold, [rule]) is not None:
            return True
    return False


def _score(label: str, extracted: list[dict]) -> dict:
    hits, misses = [], []
    for gold in GOLD_RULES:
        (hits if match_gold_to_extracted(gold, extracted) else misses).append(gold)

    false_positives = [r for r in extracted if not _extracted_matches_any_gold(r, GOLD_RULES)]

    tp, fn, fp = len(hits), len(misses), len(false_positives)
    recall = tp / len(GOLD_RULES) if GOLD_RULES else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    print(f"\n     {label}:")
    print(f"       confusion matrix — TP={tp}  FP={fp}  FN={fn}  (gold={len(GOLD_RULES)}, extracted={len(extracted)})")
    print(f"       precision={precision:.0%}  recall={recall:.0%}  F1={f1:.0%}")
    if misses:
        print("     missed (false negatives):")
        for g in misses:
            print(f"       - {g['ref']:30s} {g['desc'][:65]}")
    if false_positives:
        print("     hallucinated / unmatched (false positives):")
        for r in false_positives:
            print(f"       - {r.get('target', '?')}.{r.get('property_name', '?')} "
                  f"{r.get('operator', '?')} {_extracted_value(r)}")

    return {
        "label": label, "hits": tp, "total_gold": len(GOLD_RULES),
        "recall": recall, "precision": precision, "f1": f1,
        "extracted_total": len(extracted),
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "missed": [g["ref"] for g in misses],
        "hallucinated": [
            f"{r.get('target', '?')}.{r.get('property_name', '?')}" for r in false_positives
        ],
    }


def prepare_sendable_chunks(text: str) -> list[dict]:
    """Split text into SectionChunker chunks, sent to the LLM unfiltered.

    No longer replicates rule_extraction_service.py's KeywordFilter ->
    DependencyParser -> ConfidenceScorer stage — those classes were removed
    along with the pre-DocLang pipeline (see plan-26003.md), and nothing in
    bim-guard's current architecture confidence-filters chunks before LLM
    extraction the same way.
    """
    code_chunks = SectionChunker().chunk(text)
    chunks_to_process = code_chunks or [{"section_number": "1", "section_name": "Full text", "text": text}]
    return [
        {**c, "filtered_text": c["text"]}
        for c in chunks_to_process
        if c.get("text", "").strip()
    ]


# ══════════════════════════════════════════════════════════════════════════
# PART A
# ══════════════════════════════════════════════════════════════════════════

def part_a():
    print("=" * 70)
    print("  PART A - PDF text extraction + chunk prep (diagnostics disabled)")
    print("=" * 70)
    print("\n  A1/A3/A4/A5 removed: they required DocumentReader, UnstructuredExtractor,")
    print("  KeywordFilter, DependencyParser, ConfidenceScorer and TableRuleBuilder, none")
    print("  of which exist in bim-guard's current Docling/DocLang document_parsing")
    print("  pipeline. Rebuilding them against that architecture is tracked separately")
    print("  (see plan-26003.md) and is out of scope for this fix.")

    print("\n[A2] Extracting PDF text (pypdf directly — bim-guard's own")
    print("     extract_document_text() now requires a running Docling service with no")
    print("     dependency-light fallback) and building SectionChunker chunks")
    from pypdf import PdfReader
    import io
    pdf_bytes = open(PDF_PATH, "rb").read()
    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_bytes)).pages)

    sendable = prepare_sendable_chunks(text)
    print(f"     {len(sendable)} chunk(s) reaching the LLM stage")

    return sendable


# ══════════════════════════════════════════════════════════════════════════
# PART B
# ══════════════════════════════════════════════════════════════════════════

def _ollama_models() -> list[str] | None:
    """Return the model tags the local Ollama daemon serves, or None if it is down."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=5) as resp:
            return [m.get("name", "") for m in json.load(resp).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return None


async def part_b(sendable: list[dict]):
    print("\n" + "=" * 70)
    print("  PART B - LLM extraction accuracy (local Ollama, no API key)")
    print("=" * 70)

    model = os.getenv("BIM_GUARD_RULE_MODEL", OLLAMA_MODEL)
    tag = model.split("/", 1)[1] if "/" in model else model

    served = _ollama_models()
    if served is None:
        print(f"\n     SKIPPED — no Ollama daemon answering at {OLLAMA_BASE_URL}.")
        print(f"     To run this part:")
        print(f"       ollama serve")
        print(f"       ollama pull {tag}")
        print(f"       uv run python score_rule_extraction.py")
        return None
    if tag not in served:
        print(f"\n     SKIPPED — Ollama is up at {OLLAMA_BASE_URL} but does not serve {tag!r}.")
        print(f"     Models currently served: {served or '(none)'}")
        print(f"     Pull it with:  ollama pull {tag}")
        return None

    # litellm resolves the ollama endpoint from this env var; llama_index's LiteLLM
    # binding (app.modules.document_parsing.llamaindex_program.build_llm) exposes no
    # base_url argument to pass it through directly. setdefault so an already-set
    # OLLAMA_API_BASE (e.g. a remote box) still wins.
    os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_BASE_URL)

    from app.modules.rule_builder.llamaindex_rule_generator import LlamaIndexRuleGenerator

    # NOTE: the old StripThinkingClient shim that stripped qwen3's <think>...</think>
    # preamble before JSON parsing has no equivalent here — LlamaIndexRuleGenerator
    # builds its own LLM binding internally with no client-injection point, and (found
    # empirically running this) raises an uncaught pydantic ValidationError on a single
    # malformed reply instead of degrading gracefully — a real robustness gap in that
    # production code, not just an eval quirk. Catch it per-chunk here so one bad chunk
    # doesn't kill the whole run; each is scored as zero rules like the old shim did.
    # NOTE (reproducibility): LlamaIndexRuleGenerator.extract_rules_from_text
    # takes only `model` -- no temperature/seed parameter exists to pin, so
    # every call below is an unrepeated, unparameterized LLM draw. That
    # constraint lives upstream in bim-guard and is out of this repo's scope
    # to fix (see CLAUDE.md's scope delineation and LIMITATIONS.md).
    extractor = LlamaIndexRuleGenerator()
    llm_rules = []
    unparseable = 0
    for idx, chunk in enumerate(sendable, start=1):
        try:
            rules = await extractor.extract_rules_from_text(
                chunk["filtered_text"], chunk_index=idx, total_chunks=len(sendable), model=model
            )
        except Exception as exc:
            unparseable += 1
            print(f"     WARNING: chunk {idx} ({chunk.get('section_number', '?')}) raised {type(exc).__name__}: {exc}")
            rules = []
        llm_rules.extend(rules)

    print(f"\n     model={model}  endpoint={os.environ['OLLAMA_API_BASE']}  chunks_sent={len(sendable)}  rules_returned={len(llm_rules)}")
    if unparseable:
        print(f"     WARNING: {unparseable}/{len(sendable)} chunk(s) raised on extraction and scored as zero rules")
    score = _score(f"LlamaIndexRuleGenerator ({model})", llm_rules)

    canonical = {c.lower() for group in _ALIAS_GROUPS for c in group}
    unresolvable = [r for r in llm_rules if str(r.get("property_name", "")).lower() not in canonical]
    print(f"\n     property_name grounding: {len(llm_rules) - len(unresolvable)}/{len(llm_rules)} "
          f"extracted property names are in ifc_reader's known vocabulary")
    if unresolvable:
        seen = sorted({r.get("property_name") for r in unresolvable})
        print(f"     unresolvable property_names seen: {seen}")

    return score


# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--json", action="store_true", help="write structured results to eval/results/ (Part B LLM score; skipped if Ollama unavailable)")
    cli_args = cli.parse_args()

    print(f"GOLD_RULES: {len(GOLD_RULES)}   EXCLUDED_CLAUSES: {len(EXCLUDED_CLAUSES)}")
    print(f"Source PDF: {PDF_PATH}\n")
    sendable_chunks = part_a()
    llm_score = asyncio.run(part_b(sendable_chunks))

    if cli_args.json:
        if llm_score is None:
            print("\n  --json requested but Part B was skipped (no Ollama) — nothing to write.")
        else:
            result = build_result(
                "score_rule_extraction", tier=2,
                passed=llm_score["true_positives"], failed=llm_score["false_negatives"],
                total=llm_score["total_gold"], duration_s=time.perf_counter() - _START,
                details=llm_score,
            )
            out_path = write_result(result, run_id=new_run_id())
            print(f"\n  JSON result written to {out_path}")
