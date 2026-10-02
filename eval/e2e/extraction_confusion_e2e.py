"""
eval/e2e/extraction_confusion_e2e.py
---------------------------------------------
Playwright automation: run BIM-Guard rule extraction through the real web UI
(https://bim-guard.xyz by default) on the human-annotated OBC 2023 Section 9.8
clauses, then score the resulting drafts against the Label Studio gold set and
write the confusion matrices.

Steps (all through the UI, like a user would):
  1. Open /#/extract (Rule Extraction Studio) with a saved signed-in session.
  2. Reuse the clause document if it is already in the library, otherwise upload
     it via "Add / Upload Document" (file input, doc type Specification), then
     convert it to DocLang from the Documents page if it is not converted yet.
  3. Optionally pick the extraction model, click "Extract Compliance Rules" and
     wait for the extract-drafts stream to finish.
  4. Read the drafts this run created (GET /api/documents/{id}/rules/drafts,
     newest EXTRACTED-* ruleset), map each to its clause, and score with
     eval/score_extraction_vs_human.py.

Outputs (in --out-dir, default eval/results/e2e/<UTC timestamp>/):
  drafts.json, extracted_rules.json, confusion.json, confusion.md,
  draft_review.png, trace.zip (open with `uv run playwright show-trace trace.zip`).

One-time sign-in (opens a browser; sign in by hand, the session is saved):
  uv run python eval/e2e/extraction_confusion_e2e.py --login

Run:
  uv run python eval/e2e/extraction_confusion_e2e.py \\
      --human research/label_studio/data/export/project1_human_2026-10-02.json \\
      --clauses research/label_studio/data/export/obc_9_8_clauses.txt

Re-score an earlier run without touching the site:
  uv run python eval/e2e/extraction_confusion_e2e.py --rescore eval/results/e2e/<ts>/drafts.json ...

Requires the `e2e` extra: `uv sync --extra e2e && uv run playwright install chromium`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from eval.score_extraction_vs_human import score, to_markdown  # noqa: E402

DEFAULT_BASE_URL = "https://bim-guard.xyz"
DEFAULT_STATE = REPO / ".auth" / "bimguard_storage_state.json"
DEFAULT_TITLE = "OBC_2023_9.8_annotated_clauses"
EXTRACT_TIMEOUT_MS = 45 * 60 * 1000


# ── clause mapping ───────────────────────────────────────────────────────────

def load_clause_index(clauses_path: Path) -> list[tuple[str, str]]:
    """[(raw section_ref, clause text)] from the '<ref> <text>' lines of the clause file."""
    index = []
    ref_re = re.compile(r"^((?:Table under |Note to Table )?\d+(?:\.\d+)+[A-Z]?\.?(?:\(\w+\))*)\s+(.*)$")
    for line in clauses_path.read_text(encoding="utf-8").splitlines():
        m = ref_re.match(line.strip())
        if m:
            index.append((m.group(1), m.group(2)))
    return index


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def resolve_clause(draft: dict[str, Any], index: list[tuple[str, str]]) -> str | None:
    """Which annotated clause a draft came from: clause_id, else a code ref in rule_id /
    description, else the clause whose text best contains the draft's source snippet."""
    clause = draft.get("clause") or {}
    rule = draft.get("proposed_rule") or {}
    for candidate in (clause.get("clause_id"), rule.get("rule_id"), rule.get("description")):
        if candidate and re.search(r"\d+\.\d+\.\d+", str(candidate)):
            return str(candidate)
    snippet = (draft.get("source_snippet") or "").strip()
    if not snippet:
        return None
    flat = re.sub(r"\s+", " ", snippet)
    for ref, text in index:
        if flat in text:
            return ref
    sw = _words(snippet)
    best = max(index, key=lambda rt: len(sw & _words(rt[1])) / (len(sw) or 1), default=None)
    if best and len(sw & _words(best[1])) >= max(3, 0.6 * len(sw)):
        return best[0]
    return None


def drafts_to_rules(drafts: list[dict[str, Any]], index: list[tuple[str, str]]) -> list[dict[str, Any]]:
    rules = []
    for d in drafts:
        r = dict(d.get("proposed_rule") or {})
        r["ref"] = resolve_clause(d, index) or r.get("rule_id")
        r["target"] = r.get("target_ifc_class")
        if r.get("value") is None and r.get("check_value") is not None:
            r["value"] = r["check_value"]
        r["_draft_id"] = d.get("id")
        r["_snippet"] = d.get("source_snippet")
        rules.append(r)
    return rules


def newest_run(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drafts of the most recent extraction run (newest EXTRACTED-* ruleset)."""
    rulesets = {(d.get("proposed_rule") or {}).get("ruleset_id") for d in drafts}
    rulesets.discard(None)
    if not rulesets:
        return drafts
    latest = max(rulesets)
    return [d for d in drafts if (d.get("proposed_rule") or {}).get("ruleset_id") == latest]


# ── browser flow ─────────────────────────────────────────────────────────────

def login(base_url: str, state_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    state_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{base_url}/#/login")
        print("Sign in in the opened browser window; waiting for the dashboard...")
        page.wait_for_url(re.compile(r"#/(dashboard|projects|extract)"), timeout=10 * 60 * 1000)
        page.wait_for_timeout(2000)
        context.storage_state(path=str(state_path))
        browser.close()
    print(f"Saved signed-in session to {state_path} (keep it private; it is gitignored).")


def run_extraction(args: argparse.Namespace, out_dir: Path) -> list[dict[str, Any]]:
    from playwright.sync_api import expect, sync_playwright

    if not args.storage_state.exists():
        sys.exit(f"No saved session at {args.storage_state}. Run with --login first.")

    upload_file = out_dir / f"{args.doc_title}.txt"
    shutil.copyfile(args.clauses, upload_file)
    option_label = f"{upload_file.name} (Specification)"
    api_headers: dict[str, str] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(storage_state=str(args.storage_state), viewport={"width": 1440, "height": 1000})
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()

        def remember_auth(request):
            if "/api/" in request.url and "authorization" in request.headers and not api_headers:
                api_headers["Authorization"] = request.headers["authorization"]
                if "x-organization-id" in request.headers:
                    api_headers["X-Organization-Id"] = request.headers["x-organization-id"]

        page.on("request", remember_auth)
        try:
            page.goto(f"{args.base_url}/#/extract")
            expect(page.get_by_text("Rule Extraction Engine")).to_be_visible(timeout=60_000)
            if "login" in page.url:
                sys.exit("Saved session has expired. Run with --login again.")

            doc_select = page.locator("#rule-doc-source")
            expect(doc_select).to_be_visible()
            if page.locator("#rule-doc-source option", has_text=option_label).count() == 0:
                print(f"Uploading {upload_file.name} ...")
                page.get_by_text("Add / Upload Document", exact=True).first.click()
                page.locator('input[type="file"]').set_input_files(str(upload_file))
                page.get_by_role("button", name=re.compile(r"^(Upload|Add) Document$")).click()
                expect(page.locator("#rule-doc-source option", has_text=option_label)).to_have_count(1, timeout=180_000)
            doc_select.select_option(label=option_label)
            doc_id = doc_select.input_value()
            print(f"Document id {doc_id}: {option_label}")

            # The upload dialog stores the file without text (generate_doclang=false);
            # extraction needs DocLang, so convert it from the Documents page if needed.
            page.goto(f"{args.base_url}/#/documents")
            row = page.locator("tr", has_text=upload_file.name)
            expect(row).to_be_visible(timeout=60_000)
            convert = row.get_by_role("button", name=re.compile(r"^Not converted"))
            if convert.count():
                print("Converting to DocLang ...")
                convert.click()
                page.get_by_role("button", name="Convert to DocLang").click()
                expect(row.get_by_title(re.compile(r"DocLang XML ready"))).to_be_visible(timeout=10 * 60 * 1000)
            page.goto(f"{args.base_url}/#/extract?doc_id={doc_id}")
            expect(page.locator("#rule-doc-source")).to_have_value(doc_id, timeout=60_000)

            if args.model:
                model_select = page.locator("#rule-ai-model")
                label = next((o for o in model_select.locator("option").all_inner_texts() if args.model.lower() in o.lower()), None)
                if not label:
                    sys.exit(f"No extraction model matching {args.model!r}")
                model_select.select_option(label=label)
            print(f"Model: {page.locator('#rule-ai-model option:checked').inner_text()}")

            extract_btn = page.get_by_role("button", name="Extract Compliance Rules")
            expect(extract_btn).to_be_enabled(timeout=60_000)
            print("Extracting (this can take several minutes) ...")
            with page.expect_response(lambda r: "/rules/extract-drafts" in r.url and r.request.method == "POST",
                                      timeout=EXTRACT_TIMEOUT_MS) as resp_info:
                extract_btn.click()
            resp = resp_info.value
            if not resp.ok:
                sys.exit(f"extract-drafts failed: HTTP {resp.status} {resp.text()[:300]}")
            expect(page.get_by_text(re.compile(r"Extracting Rules via AI"))).to_have_count(0, timeout=EXTRACT_TIMEOUT_MS)
            expect(page.get_by_text(re.compile(r"Draft Review \(\d+ drafts?\)"))).to_be_visible(timeout=120_000)
            page.screenshot(path=str(out_dir / "draft_review.png"), full_page=True)

            drafts_resp = page.request.get(f"{args.base_url}/api/documents/{doc_id}/rules/drafts", headers=api_headers)
            if not drafts_resp.ok:
                sys.exit(f"Could not read drafts: HTTP {drafts_resp.status}")
            payload = drafts_resp.json()
            drafts = payload.get("drafts", payload) if isinstance(payload, dict) else payload
        finally:
            context.tracing.stop(path=str(out_dir / "trace.zip"))
            browser.close()
    return drafts


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--storage-state", type=Path, default=DEFAULT_STATE)
    ap.add_argument("--login", action="store_true", help="sign in by hand once and save the session")
    ap.add_argument("--human", type=Path, help="Label Studio JSON export (gold)")
    ap.add_argument("--clauses", type=Path, help="clause text file uploaded for extraction")
    ap.add_argument("--doc-title", default=DEFAULT_TITLE)
    ap.add_argument("--model", help="substring of the extraction model option to select (default: site default)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--rescore", type=Path, help="score an existing drafts.json instead of running the UI")
    args = ap.parse_args()

    if args.login:
        login(args.base_url, args.storage_state)
        return
    if not args.human or not args.clauses:
        ap.error("--human and --clauses are required")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or (REPO / "eval" / "results" / "e2e" / stamp)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.rescore:
        drafts = json.loads(args.rescore.read_text(encoding="utf-8"))
    else:
        drafts = newest_run(run_extraction(args, out_dir))
    (out_dir / "drafts.json").write_text(json.dumps(drafts, indent=2, default=str), encoding="utf-8")

    rules = drafts_to_rules(drafts, load_clause_index(args.clauses))
    extracted_path = out_dir / "extracted_rules.json"
    extracted_path.write_text(json.dumps(rules, indent=2, default=str), encoding="utf-8")
    unmapped = [r for r in rules if not re.search(r"\d+\.\d+\.\d+", str(r.get("ref") or ""))]

    res = score(args.human, extracted_path)
    res["run"] = {"base_url": args.base_url, "drafts": len(drafts), "unmapped_drafts": len(unmapped),
                  "out_dir": str(out_dir)}
    md = to_markdown(res)
    if unmapped:
        md += "\n## Drafts that could not be mapped to a clause\n\n" + "\n".join(
            f"- {r.get('rule_id')}: {str(r.get('_snippet') or r.get('description'))[:100]}" for r in unmapped) + "\n"
    (out_dir / "confusion.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    (out_dir / "confusion.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote results to {out_dir}")


if __name__ == "__main__":
    main()
