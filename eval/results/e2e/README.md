# End-to-end extraction runs (OBC 2023 §9.8)

Each run drives BIM-Guard's Rule Extraction Studio on https://bim-guard.xyz through the web UI
(`eval/e2e/extraction_confusion_e2e.py`), reads the drafts it created and scores them against the
human Label Studio gold set (`eval/score_extraction_vs_human.py`).

| Run | Directory | Model | Source of model | Drafts | BIM-Guard build | Notes |
|---|---|---|---|---|---|---|
| 1 | `run1_browser/` | GPT-6.1 Sol Pro | reported by the annotator; **not recorded in the run output** | 104 | before the 2026-10-02 21:50 UTC rebuild | UI driven by hand before the runner existed |
| 2 | `run2_playwright/` | GPT-6.1 Sol Pro | reported by the annotator; **not recorded in the run output** | 48 | before the rebuild | first automated run |
| 3 | `run3_variance_a/` | `openai/gpt-5.6-luna-pro` | recorded in `confusion.json` (`run.model`) | 53 | after the rebuild | pinned cheaper model; runner adapted to the new dropdown UI |

All three are scored against `project1_human_2026-10-02b.json` (89 gold rules). That gold file is
not in the repository (the OBC clause text is not redistributed; see `docs/DATA_LICENSING.md`).

**Reading the runs.** Runs 1 and 2 used the same model yet differ widely (lenient rule F1 77.6% vs
32.2%), so single-model run-to-run variance alone is large. Run 3 differs from both in model *and*
build, so it cannot isolate either effect. The extraction call accepts no seed or temperature.
Quote the range, never one run. See `research/CLAIMS.md` §3a.
