# End-to-end extraction runs (OBC 2023 §9.8)

Each run drives BIM-Guard's Rule Extraction Studio on https://bim-guard.xyz through the web UI
(`eval/e2e/extraction_confusion_e2e.py`), reads the drafts it created and scores them against the
human Label Studio gold set (`eval/score_extraction_vs_human.py`).

| Run | Directory | Model | Source of model | Drafts | BIM-Guard build | Notes |
|---|---|---|---|---|---|---|
| 1 | `run1_browser/` | `openai/gpt-5.6-luna-pro` (page default at the time) | observed by the operator in the extract-drafts request (`model=openrouter/openai/gpt-5.6-luna-pro`) and the backend LiteLLM log, 2026-10-02 18:17–18:27 UTC; **not recorded in the run output**, and the container logs were lost in the 21:50 rebuild | 104 | before the 2026-10-02 21:50 UTC rebuild | UI driven by hand before the runner existed |
| 2 | `run2_playwright/` | `openai/gpt-5.6-luna-pro` | runner stdout, kept as `run2_playwright/run.log` ("Model: OpenAI: GPT-5.6 Luna Pro") | 48 | before the rebuild | first automated run |
| 3 | `run3_variance_a/` | `openai/gpt-5.6-luna-pro` | recorded in `confusion.json` (`run.model`) | 53 | after the rebuild | pinned cheaper model; runner adapted to the new dropdown UI |
| 4 | `run4_corrected_gold/` | `openai/gpt-5.6-luna-pro` | recorded in `confusion.json` (`run.model`) | 42 | after bim-guard `1938d2b` (cross-worker cache fix) | corrected clause text uploaded as a new document (`…_66ab9356.txt`, #1545); scored on gold 2026-10-03 |

Runs 1–3 are scored against `project1_human_2026-10-02b.json` (89 gold rules, 117 clauses; clause
text `obc_9_8_clauses_2026-10-02b.txt`), run 4 against `project1_human_2026-10-03.json` (116 rules,
129 clauses) — the gold revision is described in `research/CLAIMS.md` §3a; do not compare across it. That gold file is
not in the repository (the OBC clause text is not redistributed; see `docs/DATA_LICENSING.md`).

An earlier version of this table attributed runs 1 and 2 to "GPT-6.1 Sol Pro" as reported by the
annotator; the evidence above shows both used `openai/gpt-5.6-luna-pro`, the same model as run 3.

**Reading the runs.** Runs 1 and 2 used the same model yet differ widely (lenient rule F1 77.6% vs
32.2%), so single-model run-to-run variance alone is large. Run 3 differs from both in model *and*
build, so it cannot isolate either effect. The extraction call accepts no seed or temperature.
Quote the range, never one run. See `research/CLAIMS.md` §3a.
