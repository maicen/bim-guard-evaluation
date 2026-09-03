"""
score_rule_extraction.py
------------------------------------------------
Phase-1 eval harness for Module 3 rule extraction accuracy, scored against
eval_gold_code_9_8_stairs.py (hand-annotated ground truth for CODE 9.8.2-9.8.4.7,
data/uploads/..._pdf_stairs_mock.pdf).

Mirrors score_nlp_annotation.py's style (plain script, print()-based, no pytest).

Runs the REAL PDF through the REAL extraction primitives — not a hand-typed
stand-in — so results reflect what actually happens today, not a best case.

  PART A - structural diagnostics (free, no API key, always runs):
    A1. Heading detection   - does SectionChunker recognise CODE numbering in
                               the text the live document-upload flow actually
                               stores (pypdf), vs. the Unstructured markdown path?
    A2. sendable-chunk prep - replicate rule_extraction_service.py's chunk
                               pipeline (SectionChunker -> generic fallback ->
                               KeywordFilter -> DependencyParser ->
                               ConfidenceScorer) on the REAL live-path text.
    A3. SKIP leakage        - does the confidence scorer drop gold-bearing
                               text before the LLM ever sees it?
    A4. Table pipeline      - does TableRuleBuilder work on Unstructured's tables,
                               and does the live route ever call it?
    A5. Regex baseline      - free-extractor recall/precision vs gold, on the
                               real sendable chunks from A2.

  PART B - LLM accuracy (needs a local Ollama daemon; skipped with
    instructions if absent):
    Runs LiteLLMRuleExtractor over the same real sendable chunks from A2 and
    scores per-field precision/recall + property-name grounding against gold.
    Scored against local Ollama (qwen3:14b) by default, so the whole 29-gold-rule
    sweep costs nothing and needs no vendor API key. Set BIM_GUARD_RULE_MODEL to
    score a hosted model instead (the live app default is "gpt-4o-mini").

Usage:
    uv run python score_rule_extraction.py
"""

import argparse
import asyncio
import glob
import json
import os
import re
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

from document_parsing import DocumentReader  # noqa: E402
from document_parsing.unstructured_extractor import UnstructuredExtractor  # noqa: E402
from document_parsing.section_chunker import SectionChunker  # noqa: E402
from document_parsing.keyword_filter import KeywordFilter  # noqa: E402
from document_parsing.dependency_parser import DependencyParser  # noqa: E402
from document_parsing.confidence_scorer import ConfidenceScorer  # noqa: E402
from document_parsing.table_rule_builder import TableRuleBuilder  # noqa: E402
from rule_builder.regex_rule_converter import RegexRuleConverter  # noqa: E402
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


def _score(label: str, extracted: list[dict]) -> dict:
    hits, misses = [], []
    for gold in GOLD_RULES:
        (hits if match_gold_to_extracted(gold, extracted) else misses).append(gold)
    recall = len(hits) / len(GOLD_RULES) if GOLD_RULES else 0.0
    print(f"\n     {label}: {len(hits)}/{len(GOLD_RULES)} gold rules recovered "
          f"({recall:.0%} recall), {len(extracted)} rules extracted total")
    if misses:
        print("     missed:")
        for g in misses:
            print(f"       - {g['ref']:30s} {g['desc'][:65]}")
    return {
        "label": label, "hits": len(hits), "total_gold": len(GOLD_RULES),
        "recall": recall, "extracted_total": len(extracted),
        "missed": [g["ref"] for g in misses],
    }


def prepare_sendable_chunks(text: str) -> list[dict]:
    """Replicates rule_extraction_service.py's steps 3-7 (deterministic part,
    BERT/NLPAnnotator omitted — no fine-tuned model on disk / annotation-only)."""
    code_chunks = SectionChunker().chunk(text)
    if code_chunks:
        chunks_to_process = code_chunks
    else:
        generic = DocumentReader().extract_text_sections(text)
        chunks_to_process = [
            {"section_number": str(i + 1), "section_name": f"Section {i + 1}",
             "text": t, "char_count": len(t)}
            for i, t in enumerate(generic)
        ]

    filtered = KeywordFilter().score_chunks(chunks_to_process)
    dep = DependencyParser().analyse_chunks(filtered)
    final = ConfidenceScorer().combine(filtered_chunks=filtered, dep_chunks=dep, bert_chunks=None)
    return [c for c in final if c.get("filtered_text", "").strip()]


# ══════════════════════════════════════════════════════════════════════════
# PART A
# ══════════════════════════════════════════════════════════════════════════

def part_a():
    print("=" * 70)
    print("  PART A - structural diagnostics (no LLM, no API key)")
    print("=" * 70)

    pdf_bytes = open(PDF_PATH, "rb").read()
    pypdf_text = DocumentReader().parse_pdf(pdf_bytes)
    unstructured_text, unstructured_tables = UnstructuredExtractor().extract(PDF_PATH)

    # ── A1: heading detection gap ────────────────────────────────────────
    print("\n[A1] SectionChunker heading detection — live path (pypdf) vs Unstructured path")
    chunks_pypdf = SectionChunker().chunk(pypdf_text)
    chunks_unstructured = SectionChunker().chunk(unstructured_text)
    print(f"     pypdf-extracted text   (what document-upload stores as extracted_text): "
          f"{len(chunks_pypdf)} sections detected")
    print(f"     Unstructured-extracted text (only used by the parallel-race extract_rules(bytes) path): "
          f"{len(chunks_unstructured)} sections detected")
    if len(chunks_pypdf) == 0 and len(chunks_unstructured) > 0:
        print("     -> CONFIRMED: the live document-upload -> extract-rules flow stores pypdf text,")
        print("        whose CODE headings ('9.8.2.  Stair Dimensions') match none of SectionChunker's")
        print("        3 heading patterns (needs markdown '#', a bare top-level digit+space, or the")
        print("        literal word 'SECTION'/'CHAPTER'/'PART'). It silently falls back to the")
        print("        generic size-bounded chunker, losing real section_number/section_name context.")

    # ── A2: build the real sendable chunks (live path) ──────────────────
    print("\n[A2] Building sendable chunks exactly as rule_extraction_service.py does, "
          "on the REAL live-path text (pypdf)")
    sendable = prepare_sendable_chunks(pypdf_text)
    total_send = sum(c.get("count_send", 0) for c in sendable) or len(sendable)
    print(f"     {len(sendable)} chunk(s) with non-empty filtered_text reaching the LLM stage")

    # ── A3: SKIP leakage ──────────────────────────────────────────────────
    print("\n[A3] Confidence-scorer SKIP check — does filtering drop gold-bearing text?")
    sent_all = " ".join(c.get("filtered_text", "") for c in sendable)
    full_all = pypdf_text
    leaked = 0
    for gold in GOLD_RULES:
        needles = []
        for key in ("value", "value_min", "value_max"):
            v = gold.get(key)
            if v is not None:
                needles.append(str(int(v)) if float(v).is_integer() else str(v))
        if not needles:
            continue
        norm = lambda s: s.replace(",", " ")
        in_full = any(n in norm(full_all) for n in needles)
        in_sent = any(n in norm(sent_all) for n in needles)
        if in_full and not in_sent:
            leaked += 1
            print(f"     DROPPED before LLM: {gold['ref']:30s} ({gold['desc'][:60]})")
    if leaked == 0:
        print("     none — all gold clauses' numbers survive into filtered_text")
    else:
        print(f"     {leaked}/{len(GOLD_RULES)} gold rules had their source text filtered out "
              f"by the spaCy confidence scorer before the LLM ever saw them")

    # ── A4: table pipeline ────────────────────────────────────────────────
    print("\n[A4] Table pipeline — TableRuleBuilder vs live route")
    table_gold = [g for g in GOLD_RULES if g["ref"].startswith("Table ")]
    print(f"     Unstructured found {len(unstructured_tables)} table(s) in the source PDF")
    table_rules = TableRuleBuilder().extract_all_as_dicts(unstructured_tables)
    print(f"     TableRuleBuilder produced {len(table_rules)} rule(s) from those tables")
    found = sum(1 for g in table_gold if match_gold_to_extracted(g, table_rules))
    print(f"     matched {found}/{len(table_gold)} Table 9.8.4.1 gold rules "
          f"when TableRuleBuilder IS invoked directly on Unstructured's tables")
    print("\n     BUT app/services/rule_extraction_service.py's extract_rules_from_text() —")
    print("     the method app/routes/library.py:786 calls for the document-upload -> extract")
    print("     UI flow — always passes table_rules=[] and never invokes TableRuleBuilder.")
    print(f"     -> structurally, all {len(table_gold)} Table-9.8.4.1-sourced gold rules above")
    print("        can NEVER be produced by that code path, regardless of LLM quality.")

    # ── A5: regex baseline on the REAL sendable chunks ───────────────────
    print("\n[A5] Regex converter (free baseline) vs GOLD_RULES, on the real live-path chunks")
    regex_rules = []
    for chunk in sendable:
        regex_rules.extend(RegexRuleConverter().extract_rules(chunk))
    print(f"     RegexRuleConverter produced {len(regex_rules)} rule(s) total")
    regex_score = _score("Regex converter (live-path chunks)", regex_rules)

    return sendable, regex_score


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


class StripThinkingClient:
    """Decorator that drops a reasoning model's <think>...</think> preamble.

    qwen3 is a thinking model.  ``response_format={"type": "json_object"}`` maps to
    Ollama's ``format: "json"`` grammar, which normally suppresses the block, but
    ``rule_extractor._parse`` fails closed (silently returns zero rules) on any
    non-JSON prefix — so strip it defensively rather than mis-score a run as 0%.

    Satisfies the LLMClient protocol, so it substitutes anywhere a client is taken.
    """

    def __init__(self, inner) -> None:
        """Wrap *inner*, any object satisfying the LLMClient protocol."""
        self._inner = inner
        self.unparseable = 0

    async def complete(self, messages: list[dict], *, response_format: dict | None = None) -> str:
        """Delegate to the wrapped client and return its reply without think tags."""
        raw = await self._inner.complete(messages, response_format=response_format)
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        try:
            json.loads(cleaned)
        except json.JSONDecodeError:
            # Usually max_tokens truncation mid-object. Counted so a run that scores
            # 0% for transport reasons is distinguishable from one the model failed.
            self.unparseable += 1
        return cleaned


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
        return
    if tag not in served:
        print(f"\n     SKIPPED — Ollama is up at {OLLAMA_BASE_URL} but does not serve {tag!r}.")
        print(f"     Models currently served: {served or '(none)'}")
        print(f"     Pull it with:  ollama pull {tag}")
        return

    # litellm resolves the ollama endpoint from this env var; LiteLLMClient exposes
    # no base_url argument to pass it through directly.  setdefault so an already-set
    # OLLAMA_API_BASE (e.g. a remote box) still wins.
    os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_BASE_URL)

    from app.modules.config import MAX_TOKENS_COMPLIANCE
    from app.services.rule_extractor import LiteLLMRuleExtractor
    from app.services.llm_client import LiteLLMClient

    client = StripThinkingClient(LiteLLMClient(model=model, api_key=OLLAMA_API_KEY))
    extractor = LiteLLMRuleExtractor(client=client)
    llm_rules = []
    for idx, chunk in enumerate(sendable, start=1):
        rules = await extractor.extract_rules_from_text(
            chunk["filtered_text"], chunk_index=idx, total_chunks=len(sendable)
        )
        llm_rules.extend(rules)

    print(f"\n     model={model}  endpoint={os.environ['OLLAMA_API_BASE']}  chunks_sent={len(sendable)}  rules_returned={len(llm_rules)}")
    if client.unparseable:
        print(f"     WARNING: {client.unparseable}/{len(sendable)} replies were not valid JSON "
              f"(likely max_tokens={MAX_TOKENS_COMPLIANCE} truncation) and scored as zero rules")
    _score(f"LiteLLMRuleExtractor ({model}) — live-path chunks", llm_rules)

    canonical = {c.lower() for group in _ALIAS_GROUPS for c in group}
    unresolvable = [r for r in llm_rules if str(r.get("property_name", "")).lower() not in canonical]
    print(f"\n     property_name grounding: {len(llm_rules) - len(unresolvable)}/{len(llm_rules)} "
          f"extracted property names are in ifc_reader's known vocabulary")
    if unresolvable:
        seen = sorted({r.get("property_name") for r in unresolvable})
        print(f"     unresolvable property_names seen: {seen}")


# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--json", action="store_true", help="write structured results to eval/results/ (Part A regex baseline only)")
    cli_args = cli.parse_args()

    print(f"GOLD_RULES: {len(GOLD_RULES)}   EXCLUDED_CLAUSES: {len(EXCLUDED_CLAUSES)}")
    print(f"Source PDF: {PDF_PATH}\n")
    sendable_chunks, regex_score = part_a()
    asyncio.run(part_b(sendable_chunks))

    if cli_args.json:
        result = build_result(
            "score_rule_extraction", tier=2,
            passed=regex_score["hits"], failed=regex_score["total_gold"] - regex_score["hits"],
            total=regex_score["total_gold"], duration_s=time.perf_counter() - _START,
            details=regex_score,
        )
        out_path = write_result(result, run_id=new_run_id())
        print(f"\n  JSON result written to {out_path} (Part A regex baseline only — Part B/LLM not scored)")
