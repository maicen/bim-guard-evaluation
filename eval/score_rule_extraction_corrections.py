"""
score_rule_extraction_corrections.py
------------------------------------------------
Live-data companion to score_rule_extraction.py: instead of scoring extraction
against a fixed hand-annotated gold PDF (stairs only), this scores it against
every real correction a human reviewer has made in production.

Ground truth source: bim-guard's `rule_extraction_drafts` table, reached
exclusively via Mode A (`GET /api/rules/drafts`, see app/api/rules.py's
list_all_rule_drafts docstring, which names this repo as that endpoint's
intended read path). Each draft a reviewer edited (status="edited") carries
both:
  - `original_proposed_rule` -- the LLM's first output, frozen the moment a
    reviewer's first edit is saved (app/services/rule_draft_service.py)
  - `proposed_rule`          -- the current, human-corrected rule

This script is intentionally pure Mode A: no `BIMGUARD_PATH` / `sys.path`
juggling, no `app.*` import, no access to bim-guard's Supabase project except
through its own authenticated REST API. That keeps it usable against any
running bim-guard instance (local dev or the hosted one), not just an
adjacent checkout.

Scoring is field-level, not rule-level: for every edited draft, each
structural field (target_ifc_class, property_name, operator, check_value,
value_min/max, ...) in `original_proposed_rule` is compared to the same
field in `proposed_rule`. An unchanged field counts as a correct extraction;
a changed field counts as a correction the model needed. `description` is
tracked separately as a narrative-edit count, not scored -- wording tweaks
are common and not a correctness signal the way a wrong operator or target
class is.

This measures correction rate on drafts a reviewer actually touched. It is
NOT precision/recall against ground truth the way score_rule_extraction.py
is: an extraction error nobody caught, or a draft accepted as-is when it
shouldn't have been, leaves no signal here. Use both scripts together.

Usage:
    uv run python eval/score_rule_extraction_corrections.py
    uv run python eval/score_rule_extraction_corrections.py --live
    BIMGUARD_URL=http://127.0.0.1:8000 uv run python eval/score_rule_extraction_corrections.py --live --json

Auth: `GET /api/rules/drafts` requires a real Supabase bearer token
(app/auth.py's get_current_user). Provide one of:
    BIMGUARD_API_TOKEN               -- a ready-made access token, or
    SUPABASE_URL + SUPABASE_ANON_KEY (or SUPABASE_PUBLISHABLE_KEY)
      + DEV_AUTH_EMAIL + DEV_AUTH_PASSWORD
                                      -- password-grant login as bim-guard's
                                         seeded shared dev account (see
                                         bim-guard's CLAUDE.md, "Local Dev
                                         Sign-In"), read from a `.env` in
                                         either this repo or bim-guard's root.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import bimguard_path, build_result, write_result  # noqa: E402

_START = time.perf_counter()

# ── Fields compared for correction scoring ──────────────────────────────────
# Structural fields that drive rule *evaluation* -- a change here means the
# LLM got the check itself wrong. Numeric-ish fields get a tolerant compare;
# everything else is compared as a normalized string.
NUMERIC_FIELDS = {"check_value", "value_min", "value_max", "value_min_offset", "value_max_offset"}
STRUCTURAL_FIELDS = [
    "target_ifc_class", "property_set", "property_name", "operator",
    *NUMERIC_FIELDS,
    "value_min_property", "value_max_property", "compare_property",
    "name_pattern", "uniqueness_scope", "unit", "severity", "category",
    "rule_category", "mechanism", "applies_when",
]
# Tracked separately -- wording edits, not correctness signals.
NARRATIVE_FIELDS = ["description"]


def _norm(v) -> str:
    if v is None:
        return ""
    return str(v).strip().lower()


def _num_close(a, b, tol: float = 0.5) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return _norm(a) == _norm(b)


def _fields_equal(field: str, a, b) -> bool:
    if field in NUMERIC_FIELDS and (a is not None or b is not None):
        return _num_close(a, b)
    return _norm(a) == _norm(b)


def diff_draft(draft: dict) -> dict:
    """Field-level diff of one edited draft's original vs. corrected rule."""
    original = draft.get("original_proposed_rule") or {}
    corrected = draft.get("proposed_rule") or {}

    changed = [f for f in STRUCTURAL_FIELDS if not _fields_equal(f, original.get(f), corrected.get(f))]
    unchanged = [f for f in STRUCTURAL_FIELDS if f not in changed]
    narrative_changed = [
        f for f in NARRATIVE_FIELDS if _norm(original.get(f)) != _norm(corrected.get(f))
    ]

    return {
        "draft_id": draft.get("id"),
        "source_document_id": draft.get("source_document_id"),
        "extraction_method": draft.get("extraction_method"),
        "rule_id": corrected.get("rule_id") or original.get("rule_id"),
        "changed_fields": changed,
        "unchanged_fields": unchanged,
        "narrative_changed_fields": narrative_changed,
        "field_correct": len(unchanged),
        "field_total": len(STRUCTURAL_FIELDS),
    }


def score(diffs: list[dict]) -> dict:
    field_correct = sum(d["field_correct"] for d in diffs)
    field_total = sum(d["field_total"] for d in diffs)
    field_accuracy = field_correct / field_total if field_total else 0.0

    drafts_with_no_structural_change = sum(1 for d in diffs if not d["changed_fields"])

    from collections import Counter
    field_change_counts = Counter(f for d in diffs for f in d["changed_fields"])

    print(f"\n     edited drafts scored: {len(diffs)}")
    print(f"     field-level accuracy: {field_correct}/{field_total} ({field_accuracy:.0%})")
    print(f"     drafts edited with NO structural field change (narrative-only edit): "
          f"{drafts_with_no_structural_change}/{len(diffs)}")
    if field_change_counts:
        print("     most-corrected fields:")
        for field, count in field_change_counts.most_common(10):
            print(f"       - {field:24s} corrected in {count}/{len(diffs)} drafts")

    return {
        "edited_drafts": len(diffs),
        "field_correct": field_correct,
        "field_total": field_total,
        "field_accuracy": field_accuracy,
        "drafts_with_no_structural_change": drafts_with_no_structural_change,
        "field_change_counts": dict(field_change_counts),
        "diffs": diffs,
    }


# ── Mode A client + auth ─────────────────────────────────────────────────


def _load_dotenv() -> None:
    """Best-effort: load .env from this repo's root and bim-guard's root, so
    SUPABASE_*/DEV_AUTH_* creds don't need to be exported by hand."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in (EVAL_DIR.parent / ".env", bimguard_path() / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)


def get_bearer_token() -> str:
    """Resolve a Supabase access token for `GET /api/rules/drafts`.

    Precedence: an already-minted BIMGUARD_API_TOKEN, else a password-grant
    login as bim-guard's seeded shared dev account (dev@bim-guard.local by
    default -- see bim-guard's CLAUDE.md "Local Dev Sign-In"). Raises with a
    clear remediation message if neither is configured.
    """
    _load_dotenv()

    token = os.getenv("BIMGUARD_API_TOKEN", "").strip()
    if token:
        return token

    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("SUPABASE_ANON_KEY", "").strip() or os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    email = os.getenv("DEV_AUTH_EMAIL", "dev@bim-guard.local").strip()
    password = os.getenv("DEV_AUTH_PASSWORD", "").strip()

    if not (supabase_url and api_key and password):
        raise RuntimeError(
            "No bearer token available for GET /api/rules/drafts. Set either:\n"
            "  BIMGUARD_API_TOKEN=<a valid Supabase access token>\n"
            "or all of:\n"
            "  SUPABASE_URL, SUPABASE_ANON_KEY (or SUPABASE_PUBLISHABLE_KEY),\n"
            "  DEV_AUTH_EMAIL, DEV_AUTH_PASSWORD\n"
            "(the shared dev account from bim-guard's CLAUDE.md 'Local Dev Sign-In';\n"
            "seed it once with `uv run python scripts/seed_dev_auth_user.py` in bim-guard)."
        )

    import httpx

    resp = httpx.post(
        f"{supabase_url}/auth/v1/token",
        params={"grant_type": "password"},
        json={"email": email, "password": password},
        headers={"apikey": api_key, "Content-Type": "application/json"},
        timeout=30.0,
    )
    resp.raise_for_status()
    access_token = resp.json().get("access_token")
    if not access_token:
        raise RuntimeError(f"Supabase password grant returned no access_token: {resp.text[:200]}")
    return access_token


class InProcessClient:
    def __init__(self, token: str):
        from starlette.testclient import TestClient

        sys.path.insert(0, str(bimguard_path()))
        from app.main import app

        self._client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    def get(self, path, **kw):
        return self._client.get(path, **kw)


class LiveClient:
    def __init__(self, base_url: str, token: str):
        import httpx

        self._client = httpx.Client(
            base_url=base_url, timeout=30.0, headers={"Authorization": f"Bearer {token}"}
        )

    def get(self, path, **kw):
        return self._client.get(path, **kw)


def fetch_edited_drafts(client) -> list[dict]:
    resp = client.get("/api/rules/drafts", params={"status": "edited"})
    resp.raise_for_status()
    return resp.json().get("drafts", [])


# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--live", action="store_true", help="use real HTTP (httpx) against BIMGUARD_URL instead of an in-process TestClient")
    cli.add_argument("--json", action="store_true", help="write structured results to eval/results/")
    cli_args = cli.parse_args()

    print("=" * 70)
    print("  Rule extraction correction accuracy (live rule_extraction_drafts)")
    print("=" * 70)

    bearer = get_bearer_token()

    if cli_args.live:
        base_url = os.getenv("BIMGUARD_URL", "http://127.0.0.1:8000")
        print(f"\nMode A -- live HTTP against {base_url}")
        client = LiveClient(base_url, bearer)
    else:
        print("\nMode A -- in-process TestClient")
        client = InProcessClient(bearer)

    drafts = fetch_edited_drafts(client)
    print(f"edited drafts fetched: {len(drafts)}")

    if not drafts:
        print("\n  No edited drafts found -- nothing to score. A draft only carries "
              "original_proposed_rule once a reviewer has edited it at least once.")
        sys.exit(0)

    diffs = [diff_draft(d) for d in drafts]
    result_metrics = score(diffs)

    if cli_args.json:
        result = build_result(
            "score_rule_extraction_corrections", tier=2,
            passed=result_metrics["field_correct"],
            failed=result_metrics["field_total"] - result_metrics["field_correct"],
            total=result_metrics["field_total"],
            duration_s=time.perf_counter() - _START,
            details=result_metrics,
        )
        out_path = write_result(result)  # let write_result() resolve $BGEVAL_RUN_ID (run_all.py) or mint one (standalone)
        print(f"\n  JSON result written to {out_path}")
