# Contributing to bim-guard-evaluation

Thanks for your interest in contributing! This repository is the research, evaluation,
and accuracy-benchmarking companion to [bim-guard](https://github.com/maicen/bim-guard)
(the core platform). See the README's "Overview" and "Related Repositories" sections for
how the two fit together, and `CLAUDE.md`'s "Strict Scope Delineation" for what belongs
here vs. in `bim-guard` itself.

This repo does **not** use Docker — it's a Python (and, for one harness, TypeScript/Bun)
research toolkit that runs directly on your machine.

## Prerequisites

- **Python 3.12+** and [`uv`](https://docs.astral.sh/uv/) (recommended), or a standard
  `venv` + `pip` if you'd rather not install `uv`. `uv` itself installs the same way on
  macOS, Linux, and Windows — see the [official install instructions](https://docs.astral.sh/uv/getting-started/installation/)
  (`curl -LsSf https://astral.sh/uv/install.sh | sh` on macOS/Linux, or the PowerShell
  one-liner on Windows).
- **A `bim-guard` checkout**, *only* if you're running harnesses that evaluate against
  the core platform's compute engines or live API (most of them). Clone it as a sibling
  directory, or point `BIMGUARD_PATH` at wherever it lives:
  ```bash
  git clone https://github.com/maicen/bim-guard.git  # as a sibling of this repo
  # or, if it's elsewhere:
  export BIMGUARD_PATH="/path/to/bim-guard"           # Windows (PowerShell): $env:BIMGUARD_PATH="C:\path\to\bim-guard"
  ```
  Some harnesses call `bim-guard`'s running web API (`http://127.0.0.1:8000/api`) —
  see that repo's own `CONTRIBUTING.md` to get it running locally (Docker Compose is the
  fastest path there). Others import its Python modules directly and only need the
  checkout on disk, not a running server.
- **Bun**, only for the Ori Eval model-comparison harness (`evals/rule-extraction/`) —
  see [evals/rule-extraction/README.md](evals/rule-extraction/README.md) for that
  specific setup (Bun install, `ori` CLI, OpenRouter credential).

## Setup

```bash
git clone https://github.com/maicen/bim-guard-evaluation.git
cd bim-guard-evaluation

uv sync                    # or: uv sync --all-extras for the llm/dev extras
# pip alternative:
#   python -m venv .venv && source .venv/bin/activate   (Windows: .venv\Scripts\activate)
#   pip install -e .
```

## Running the test suite

```bash
uv run pytest
```

## Running an evaluation harness

Pick the one relevant to your change — see the README's "Running Evaluations" section
for the full list (NLP annotation scoring, rule extraction scoring, architectural
compliance engine benchmark, LLM-as-judge scoring, the orchestrated tiered run, etc.):

```bash
uv run python eval/score_nlp_annotation.py          # fast, no bim-guard needed
uv run python eval/score_arch_engines.py            # needs BIMGUARD_PATH
uv run python eval/run_all.py --tier 1 --json --compare-baseline
```

Harnesses that are cheap and self-contained (like NLP annotation scoring) are a good
smoke test that your environment is set up correctly before running anything that
depends on `bim-guard`.

## Coding conventions

- **Lint**: `uv run ruff check .` (see `[tool.ruff]` in `pyproject.toml` for the
  configured rules).
- **Retired domains**: the Piping/Corrosion and Seismic domains were permanently retired
  from `bim-guard` on 2026-09-21. Anything related to them in this repo is historical —
  see `research/archive/retired_corrosion_piping_seismic_domain/README.md` — don't extend
  it or treat it as current.
- **Claims need evidence**: if your change adds or updates a headline accuracy/benchmark
  number, update [`research/CLAIMS.md`](research/CLAIMS.md) (the claims-to-evidence
  ledger) and, if it's a methodological limitation rather than a strength, state it
  plainly in [`LIMITATIONS.md`](LIMITATIONS.md) too.
- **No AI attribution in commits**: see `CLAUDE.md`'s "Git Workflow & Rules" section —
  never append `Co-Authored-By`, "Generated with...", or similar trailers.

## Dependency management

All Python dependencies go in `pyproject.toml` (including optional extras) and are
managed via `uv` — don't add a separate `requirements.txt`. The Ori Eval harness
(`evals/rule-extraction/`) manages its own TypeScript/Bun dependencies separately; see
its own README.

## Submitting changes

1. Commit with a clear, human-readable message (no AI-attribution trailer).
2. Push directly to `main` (this repo doesn't use feature branches — see `CLAUDE.md`)
   or open a pull request if you'd like review first.
3. If you touched a scoring harness, include the harness's output (or a summary of it)
   in your commit message or PR description so the result is reviewable without
   re-running everything.
