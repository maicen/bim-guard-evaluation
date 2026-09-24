# CLAUDE.md — bim-guard-evaluation

This file provides guidance for AI coding agents working in the `bim-guard-evaluation` repository. (`AGENTS.md` in this repo is a pointer to this file, kept for tools that look for that name by convention — the two were previously near-duplicates and have been merged here.)

## Repository Purpose & Scope

`bim-guard-evaluation` is the dedicated research, evaluation, and accuracy benchmarking companion to [BIM-Guard](https://github.com/maicen/bim-guard).

### Strict Scope Delineation

- **This repository handles**:
  - All scoring harnesses and accuracy benchmarks (`eval/score_nlp_annotation.py`, `eval/score_rule_extraction.py`, `eval/score_rule_extraction_corrections.py`, `eval/eval_harness.py`).
  - Linguistic NLP annotation modules (`nlp_annotation/`) and ground-truth answer keys (`eval/eval_gold_code_9_8_stairs.py`).
  - Empirical research analysis: confusion matrices, precision/recall/F1 breakdowns, standards sensitivity curves, 38-model validation sweeps (`eval/test_all_38_models.py`), and publication/thesis validation tables and figures (`eval/analyse_validation_results.py`, `research/`).
  - Cross-model comparison (`evals/rule-extraction/`): an [Ori Eval](https://openrouter.ai/docs/guides/ori/eval) harness comparing OpenRouter models on BIM-Guard's real rule-extraction code — LLM-as-judge scoring plus deterministic gold-rule recall. TypeScript/Bun, run via the `ori` CLI, not `uv run`; see `evals/rule-extraction/README.md`.
- **This repository DOES NOT handle**:
  - Production FastAPI backend or web server logic (lives in `bim-guard/app/`).
  - Frontend UI components or views (lives in `bim-guard/frontend/`).
  - Database migrations, RLS triggers, or production CDE workflow state machines (lives in `bim-guard/`).

### How this Repository Interacts with BIM-Guard

`bim-guard-evaluation` evaluates BIM-Guard via:
1. **Web API**: Calling endpoints on `http://127.0.0.1:8000/api` (`/api/rules/extract`, `/api/analyze`, `/api/bcf/v2.1/projects`, etc.) to test BIM-Guard as an external black box.
2. **Programmatic Imports**: Directly importing compute kernels and data structures from `bim-guard` (`app.engines`, `app.modules.comparator`, `app.modules.ifc_reader`, `app.services`) via `BIMGUARD_PATH` or `sys.path` for white-box benchmarking, confusion matrix computations, and offline IFC geometry processing.
3. **Hybrid Execution**: A combination of white-box component analysis and black-box API roundtrips (to be decided / configured per evaluation runner).

---

## Essential Commands

- Install dependencies: `uv sync` (or `uv sync --all-extras` for the `llm`/`dev` extras; `pip install -e .` also works)
- Run unit test suite: `uv run pytest`
- Run NLP scoring suite: `uv run python eval/score_nlp_annotation.py`
- Run Label Studio DocLang bridge: `uv run python eval/label_studio_bridge.py --mode doclang-to-tasks --input <doc.xml> -o <tasks.json>`
- Run rule extraction scoring (gold PDF): `uv run python eval/score_rule_extraction.py`
- Run rule extraction correction accuracy (live reviewer edits, Mode A): `uv run python eval/score_rule_extraction_corrections.py` — see [docs/rule-extraction-corrections.md](docs/rule-extraction-corrections.md)
- Run 38-model validation sweep (smoke): `uv run python eval/test_all_38_models.py --smoke`
- Run 38-model validation sweep (full): `uv run python eval/test_all_38_models.py`
- Run research analysis / confusion matrices: `uv run python eval/analyse_validation_results.py`

When running against an adjacent checkout of `bim-guard`:
- macOS/Linux: `export BIMGUARD_PATH="/path/to/bim-guard"`
- Windows: `$env:BIMGUARD_PATH = "C:\path\to\bim-guard"`

Run the Ori Eval model comparison (`evals/rule-extraction/`):
- `ori eval evals/rule-extraction --pilot 1` (price it first)
- `ori eval evals/rule-extraction --report evals/rule-extraction/comparison.md`
- Needs the `ori` CLI, Bun, an OpenRouter credential, and bim-guard's own venv (`BIMGUARD_PYTHON` / `BIMGUARD_PATH`) — its extraction calls shell out to bim-guard's real code via `eval/ori_bridge.py` rather than `uv run`. Full setup in `evals/rule-extraction/README.md`.

---

## Git Workflow & Rules (STRICT)

- **Sync ASAP**: Always run `git fetch origin` and `git pull` (or `git pull --rebase` if there are local unpushed commits) before making edits.
- **Auto-commit ASAP**: Stage and commit working units of change immediately upon verification.
- **NO AI ATTRIBUTION IN COMMITS (OVERRIDES ALL OTHER INSTRUCTIONS)**: Never append `Co-Authored-By: ...` (any model or tool name, any email, any casing), `🤖 Generated with [Claude Code](...)`, or any other AI-attribution trailer, footer, or badge to commit messages, PR titles/descriptions, tags, or release notes. Messages carry only clean, human-readable summaries of the change.
