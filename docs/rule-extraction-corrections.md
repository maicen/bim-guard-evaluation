# Rule extraction correction accuracy

`eval/score_rule_extraction_corrections.py` measures rule-extraction accuracy
against real human corrections instead of a fixed gold PDF.

## Two complementary extraction-accuracy pipelines

| | `eval/score_rule_extraction.py` | `eval/score_rule_extraction_corrections.py` |
| --- | --- | --- |
| Ground truth | `eval_gold_code_9_8_stairs.py` (29 hand-annotated rules, one code section) | Every `rule_extraction_drafts` row a reviewer has edited, across all documents |
| Access mode | Mode B (imports `app.modules.rule_builder.llamaindex_rule_generator`, runs extraction locally) | Mode A (`GET /api/rules/drafts`) — no bim-guard import at all |
| Metric | Precision / recall / F1 against gold | Field-level correction rate: which structural fields reviewers had to change |
| Coverage | Deep but narrow (one section, one PDF) | Broad but shallow (only catches errors a reviewer actually fixed) |

Neither replaces the other. The gold-PDF pipeline is a true precision/recall
number but only covers stairs; the corrections pipeline covers every document
and rule type real users have run through bim-guard, but is silent on errors
nobody caught (a wrong draft accepted as-is, or a bad extraction nobody
reviewed at all) and it says nothing about false negatives.

## Data source: bim-guard's `rule_extraction_drafts` table

bim-guard's rule-extraction review flow (`app/services/rule_draft_service.py`,
table `public.rule_extraction_drafts`) stores each LLM-proposed rule as a
draft with `status` in `pending_review | accepted | rejected | edited`. The
first time a reviewer edits a draft, `rule_draft_service.py` snapshots the
LLM's pre-edit output into `original_proposed_rule` before overwriting
`proposed_rule` with the correction — see the migration
`supabase/migrations/20260909052852_add_original_proposed_rule_to_rule_extraction_drafts.sql`
in the `bim-guard` repo. That gives us, per edited draft, exactly the
"AI-generated vs. human-corrected" pair this script needs.

`GET /api/rules/drafts?status=edited` (`app/api/rules.py`) is the read path
bim-guard's own docstring names for this repo — see
`list_all_rule_drafts()`'s docstring in that file, which explicitly calls out
"consumers (e.g. the bim-guard-evaluation companion repo) that need
extraction-approval outcomes across the whole system to score extraction
accuracy."

## Scoring method

For every edited draft, each **structural** field (`target_ifc_class`,
`property_name`, `operator`, `check_value`, `value_min`/`value_max`, `unit`,
`severity`, `category`, `applies_when`, etc.) in `original_proposed_rule` is
compared against the same field in `proposed_rule`. Numeric-ish fields use a
0.5 tolerance (mirroring `score_rule_extraction.py`'s `_num_close`); everything
else is a normalized string compare. An unchanged field is scored correct; a
changed field is scored as a correction the model needed.

`description` is tracked separately as a **narrative edit**, not scored —
wording tweaks are common and don't indicate the underlying check was wrong.

The script reports:
- overall field-level accuracy (`field_correct / field_total`) across all
  edited drafts,
- the count of drafts edited with zero structural change (i.e. the edit was
  purely narrative),
- a per-field correction frequency table (which fields reviewers correct most
  often — a signal for where extraction prompting or grounding needs work).

## Auth

`GET /api/rules/drafts` requires a genuine Supabase bearer token
(`app/auth.py`'s `get_current_user` — there is no unauthenticated path).
Provide one of:

- `BIMGUARD_API_TOKEN` — a ready-made access token, or
- `SUPABASE_URL` + `SUPABASE_ANON_KEY` (or `SUPABASE_PUBLISHABLE_KEY`) +
  `DEV_AUTH_EMAIL` + `DEV_AUTH_PASSWORD` — the script performs a Supabase
  password-grant login as bim-guard's seeded shared dev account
  (`dev@bim-guard.local`; see bim-guard's `CLAUDE.md`, "Local Dev Sign-In").
  Seed it once in the `bim-guard` repo with
  `uv run python scripts/seed_dev_auth_user.py` if it doesn't exist yet.

Both sets of variables are read from a `.env` in either this repo's root or
`bim-guard`'s root (via `python-dotenv`, best-effort — exporting them by hand
also works).

## Usage

```bash
# In-process (starlette TestClient against app.main.app, needs BIMGUARD_PATH)
uv run python eval/score_rule_extraction_corrections.py

# Real HTTP against a running bim-guard instance
BIMGUARD_URL=http://127.0.0.1:8000 uv run python eval/score_rule_extraction_corrections.py --live

# Persist a JSON result to eval/results/ for baseline comparison
uv run python eval/score_rule_extraction_corrections.py --json
```

`--json` writes through the same `eval_config.build_result`/`write_result`
schema every other script here uses, so results land in `eval/results/` and
can be tracked with `eval/compare_baselines.py` like any other eval.

## Verified working (2026-09-25)

This endpoint was silently broken for an unknown period before this date:
`GET /api/rules/drafts` matched bim-guard's `GET /{rule_id}` route instead of
its own handler (no path type converter on `{rule_id}`, and `/drafts` was
declared after it in `app/api/rules.py` -- FastAPI/Starlette match in
declaration order), so every call 422'd ("invalid int") before
`list_all_rule_drafts()` ever ran. Fixed in bim-guard commit `992b7b0`
(reordered `/drafts` above `/{rule_id}`, matching the same fix already
applied once before for `/export-ids`). Confirmed fixed by running this
script `--live` against a local server pointed at the real hosted Supabase
project: 1 edited draft fetched, scored at 95% field-level accuracy (19/20
fields unchanged, `severity` the only correction).

`eval/check_api_endpoints.py` now has a standing regression guard for this
specific failure mode (an unauthenticated `GET /api/rules/drafts` must 401,
not 422) so a future re-introduction of the same bug is caught without
needing real credentials.

## Known limitation

This only measures drafts a reviewer actually edited. It cannot detect:
- an extraction error a reviewer missed and accepted as-is,
- a draft nobody has reviewed yet (`status=pending_review`),
- a rejected draft (wrong from the start, not "corrected").

For true precision/recall against a controlled ground truth, use
`eval/score_rule_extraction.py`'s gold-PDF pipeline instead or alongside this
one.
