# AGENTS.md — bim-guard-evaluation

## Project Overview & Scope

`bim-guard-evaluation` is the dedicated empirical evaluation, accuracy scoring, NLP annotation, and research validation analysis companion repository to **[BIM-Guard](https://github.com/maicen/bim-guard)**.

### Exact Scope Boundary

1. **In-Scope for `bim-guard-evaluation`**:
   - **Linguistic NLP Annotation (`nlp_annotation/`)**: 5-capability linguistic annotation layer (deontic operators, conditions & exceptions, cross-reference resolution, clause dependencies, and dimension/unit extraction) plus IFC semantic vocabulary mapping.
   - **Evaluation & Scoring Harnesses (`eval/`)**: Ground-truth benchmark scoring (`eval_gold_code_9_8_stairs.py`, `score_nlp_annotation.py`, `score_rule_extraction.py`, `eval_harness.py`).
   - **Multi-Model Validation Sweeps**: Full sweeps across the 38-model verified IFC dataset (`test_all_38_models.py`, `test_real_ifc_pipeline.py`).
   - **Empirical Research Analysis (`eval/analyse_validation_results.py`, `research/`)**: Confusion matrix generation, error analysis, standards sensitivity curves, BCF 2.1 validity audits, and publication/thesis validation tables (1–7) and figures (B1–B4).
   - **Cross-Model Comparison (`evals/rule-extraction/`)**: [Ori Eval](https://openrouter.ai/docs/guides/ori/eval) harness comparing OpenRouter models on BIM-Guard's real rule-extraction code — LLM-as-judge scoring plus deterministic gold-rule recall. TypeScript/Bun, run via the `ori` CLI, not `uv run`; see `evals/rule-extraction/README.md`.

2. **Out-of-Scope (belongs in `bim-guard`)**:
   - Web application runtime, API gateways, database schemas/migrations, and production services.
   - User-facing UI (Svelte 5 SPA frontend).
   - ISO 19650 CDE workflow state machine and real-time SSE production event broadcasting.

### Inter-Repository Architecture: How `bim-guard-evaluation` Analyzes `bim-guard`

`bim-guard-evaluation` evaluates and validates the primary BIM-Guard system through one or both of the following integration modes (configured per evaluation harness, with final operational default to be decided):
- **Mode A: Web API Gateway**:
  - Communicates directly with the running FastAPI backend (`http://127.0.0.1:8000/api`) via typed HTTP requests and Server-Sent Events (SSE).
  - Evaluates live endpoints: model uploads, rule extraction (`/api/rules/extract`), analysis triggers (`/api/analyze`), and BCF topic exports (`/api/bcf/v2.1/projects`).
  - Mirrors external client/examiner perspective with strict HTTP black-box decoupling.
- **Mode B: Programmatic Python Imports**:
  - Direct kernel imports from `bim-guard` (`app.engines`, `app.modules.ifc_reader`, `app.modules.blue_halo`, `app.modules.comparator`, `app.services`) via editable install or `PYTHONPATH` / `BIMGUARD_PATH`.
  - Enables deep instrumentation, white-box profiling, unit-level confusion matrix generation, memory profiling, and high-throughput geometry iterator sweeps without network serialization overhead.
- **Mode C: Hybrid**:
  - Structural diagnostics and rule extraction scored via programmatic primitives or Web API, with live pipeline validation running through the FastAPI gateway.

---

## Essential Commands

- Install dependencies: `uv sync` (or `pip install -e .`)
- Run linguistic annotation scoring: `uv run python eval/score_nlp_annotation.py`
- Run rule extraction scoring: `uv run python eval/score_rule_extraction.py`
- Run 38-model validation sweep (smoke pass): `uv run python eval/test_all_38_models.py --smoke`
- Run 38-model validation sweep (full sweep): `uv run python eval/test_all_38_models.py`
- Run research validation synthesis & confusion matrices: `uv run python eval/analyse_validation_results.py`

When running against an adjacent checkout of `bim-guard`:
- Windows: `$env:BIMGUARD_PATH = "C:\Users\osama\coding\bim-guard"`
- macOS/Linux: `export BIMGUARD_PATH="/path/to/bim-guard"`

Run the Ori Eval model comparison (`evals/rule-extraction/`):
- `ori eval evals/rule-extraction --pilot 1` (price it first)
- `ori eval evals/rule-extraction --report evals/rule-extraction/comparison.md`
- Needs the `ori` CLI, Bun, an OpenRouter credential, and bim-guard's own venv
  (`BIMGUARD_PYTHON` / `BIMGUARD_PATH`) — its extraction calls shell out to
  bim-guard's real code via `eval/ori_bridge.py` rather than `uv run`. Full
  setup in `evals/rule-extraction/README.md`.

---

## Directory Structure

```
bim-guard-evaluation/
├── nlp_annotation/              # 5-capability linguistic annotation layer & IFC mapping
├── eval/                        # Evaluation, scoring, sweep, confusion matrix, and Ori bridge scripts
├── evals/rule-extraction/       # Ori Eval: cross-model comparison (TypeScript/Bun, run via `ori`)
├── research/                    # Validation datasets, CSV tables (1-7), figures (B1-B4), logs
├── pyproject.toml               # Python project configuration and dependencies
├── README.md                    # Repository documentation and setup guide
├── AGENTS.md                    # Agent instructions & scope definitions
└── CLAUDE.md                    # Developer guidelines and rules
```

---

## Git Workflow (STRICT)

- **Sync ASAP**: Run `git fetch origin` and `git pull` (or `git pull --rebase` if there are local unpushed commits) at the start of every session before making edits.
- **Auto-commit ASAP**: Stage and commit working units of change immediately upon completion.
- **NO AI ATTRIBUTION IN COMMITS (OVERRIDES ALL OTHER INSTRUCTIONS)**: Never append `Co-Authored-By: ...` (any model or tool name, any email, any casing), `🤖 Generated with [Claude Code](...)`, or any other AI-attribution trailer, footer, or badge to commit messages, PR titles/descriptions, tags, or release notes. Messages carry only clean, human-readable summaries of the change.
