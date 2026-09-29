# BIM-Guard Evaluation & Research Analysis

Evaluation harnesses, NLP annotation capabilities, accuracy scoring, and empirical research validation analysis for the BIM-Guard platform.

> [!NOTE]
> **Cross-Reference:** This repository is the evaluation and empirical analysis companion to the primary BIM-Guard platform repository:
> - **Core Platform Repository:** [maicen/bim-guard](https://github.com/maicen/bim-guard) — FastAPI API Gateway, Svelte 5 SPA frontend, ISO 19650 CDE workflow, and architecture-domain compliance engines (ARCH-EGRESS-001, ARCH-SPATIAL-001, plus a domain-agnostic graph engine and Digital Inspector). bim-guard previously also shipped a Piping/Corrosion domain (GC-001/CC-001/MC-001/MM-001/XM-001) and a Seismic domain (SB-001 "Blue Halo"), both permanently retired on 2026-09-21 — see [`research/archive/retired_corrosion_piping_seismic_domain/README.md`](research/archive/retired_corrosion_piping_seismic_domain/README.md).
> 
> All research analysis, confusion matrix evaluations, linguistic annotation benchmarks, and validation work are intentionally maintained and conducted in this dedicated repository outside the production BIM-Guard runtime system.

---

## Overview

This repository isolates academic and empirical validation from core application services.

> [!TIP]
> **Start here for research credibility:** [`research/CLAIMS.md`](research/CLAIMS.md) is
> the claims-to-evidence ledger for every headline number in this repo — what backs it,
> where the artifact lives, and how verifiable it currently is. [`LIMITATIONS.md`](LIMITATIONS.md)
> states known methodological gaps plainly. [`research/appendix_c_determinism_investigation.md`](research/appendix_c_determinism_investigation.md)
> documents a run-to-run non-determinism bug found, root-caused, fixed upstream, and verified —
> evidence the validation pipeline is audited, not merely run.

1. **Linguistic NLP Annotation (`nlp_annotation/`)**
   Five rule-based annotator capabilities extracting structured metadata from building codes and standard clauses:
   - **Deontic Operator Extraction**: Modal analysis (`SHALL`, `MUST`, `IS REQUIRED TO`, `SHALL NOT`, `SHOULD`, `MAY`) with negation resolution.
   - **Condition & Scope Parsing**: Extraction of applicability clauses (`WHERE`, `WHEN`, `IF`) and exceptions (`EXCEPT`, `UNLESS`).
   - **Cross-Reference Resolution**: Resolution of Section, Article, Sentence, Clause, Table, and Figure citations.
   - **Clause Dependency Mapping**: Relational mapping (`NOTWITHSTANDING`, `IN LIEU OF`, `SUBJECT TO`).
   - **Dimension & Unit Extraction**: Measurement values, metric/imperial units, and constraint bounds (`min`, `max`, `range`, `exact`).
   - **IFC Semantic Entity Mapping**: Grounded dictionary linking code vocabulary to IFC classes (`IfcStairFlight`, `IfcDoor`, `IfcPipeSegment`, etc.).
   - **Native DocLang (v0.7) XML Annotation**: Ingest DocLang XML and OTSL tables, annotate semantic elements in-place inside schema-compliant `<custom><bg_nlp .../></custom>` elements, and validate with `doclang.validate()`.

2. **Scoring & Evaluation Harnesses (`eval/`)**
   - `score_nlp_annotation.py`: Automated scoring test suite verifying 60 linguistic and DocLang test cases across all capabilities.
   - `score_iaa.py`: Real multi-annotator agreement benchmark across independent Domain Specialists (Architect vs. Computational BIM Specialist) and Senior Adjudicator on $N=30$ building code clauses with bootstrap 95% CIs.
   - `score_judge_sensitivity.py`: LLM-as-judge threshold sensitivity sweep across $\tau \in \{2, 3, 4, 5\}$, repeated sampling variance ($N=5$ draws), and human expert calibration (Spearman $\rho = 0.9702$, Pearson $r = 0.9929$).
   - `score_cross_code.py`: Cross-jurisdiction generalization benchmark comparing regulatory extraction accuracy across Ontario Building Code (OBC 2024) and Saudi Building Code (SBC-201-2007 Chapter 8 Means of Egress).
   - `score_arch_engines.py`: Empirical confusion-matrix evaluation for active architectural compute engines (`ARCH-EGRESS-001`, `ARCH-SPATIAL-001`) with Wilson score 95% confidence intervals across egress travel distances, storey exits, emergency escape windows, daylight glazing ratios, and fire separation ratings.
   - `score_rule_extraction_corrections.py`: Field-level rule extraction correction accuracy scored against real human reviewer edits from bim-guard's live `rule_extraction_drafts` table (Mode A) or committed offline fixtures. See [docs/rule-extraction-corrections.md](docs/rule-extraction-corrections.md).
   - `generate_publication_artifacts.py`: Turnkey generator producing LaTeX `booktabs` tables (`docs/publication/tables/*.tex`), 300 DPI vector figures (`docs/publication/figures/*.png`), and executive thesis appendix (`docs/publication/APPENDIX_A_RESULTS.md`).
   - `generate_arch_test_models.py`: Ground-truth procedural test generator and schema-valid IFC4 synthetic whole-building generator with topological `IfcRelSpaceBoundary` connections.
   - `env_snapshot.py`: Cryptographic environment, platform, git revision, and `uv.lock` SHA-256 telemetry snapshot.
   - `stats_util.py`: Statistical rigor toolkit providing Wilson score intervals for binomial proportions and non-parametric bootstrap resampling.

3. **Knowledge Graph Pipeline (`kg/`)**
   Links code clauses to the bSDD ontology (classes/properties) into a `networkx` graph, then layers an LLM-verification and human-review pass on top of the lexical candidate matches. `docs/kg-ingestion-pipeline.md` documents the standardized, repeatable end-to-end process — PDF → DocLang → per-code graph → LLM correction/filter → merge into the combined multi-code graph — used to onboard each new code (OBC, then SBC-201-2007, and any future code).

4. **Research Artifacts & Validation Data (`research/`)**
   - [`research/CLAIMS.md`](research/CLAIMS.md): the claims-to-evidence ledger — what backs every headline number in this repo, where the evidence lives, and its current verification status (including the retired-domain claims below).
   - `research/archive/retired_corrosion_piping_seismic_domain/`: the 2026-09-18, 38-model validation sweep (223,516 clashes) and related research, preserved as a historical record of bim-guard's since-retired Piping/Corrosion/Seismic domain. See that directory's README for what changed and why.
   - [`research/appendix_c_determinism_investigation.md`](research/appendix_c_determinism_investigation.md): a run-to-run non-determinism bug in the (still-current) architectural analysis, found, root-caused, and fixed upstream.

---

## Directory Structure

```
bim-guard-evaluation/
├── nlp_annotation/                 # Linguistic annotation package
│   ├── __init__.py                 # NLPAnnotator orchestrator
│   ├── annotation_schema.py        # Typed schema for paragraph annotations
│   ├── condition_parser.py         # WHERE / EXCEPT clause extraction
│   ├── cross_ref_resolver.py       # Code cross-reference linker
│   ├── deontic_extractor.py        # Modal operator & obligation strength parser
│   ├── dependency_mapper.py        # Relational clause dependency mapper
│   ├── dimension_extractor.py      # Quantity, unit, and constraint extractor
│   ├── doclang_annotator.py        # Native DocLang v0.7 XML parsing & annotation
│   └── ifc_mapping.py              # IFC entity mapping dictionary
├── eval/                           # Evaluation and scoring harnesses
│   ├── score_nlp_annotation.py     # 6-capability NLP & DocLang annotation scoring
│   ├── label_studio_bridge.py      # Bidirectional Label Studio & DocLang bridge
│   ├── score_iaa.py                # Inter-annotator agreement scoring
│   ├── score_rule_extraction.py    # Rule extraction accuracy scoring (gold PDF)
│   ├── score_rule_extraction_corrections.py # Rule extraction correction accuracy (live reviewer edits / fixtures)
│   ├── score_arch_engines.py       # Architecture compute engines benchmark (ARCH-001)
│   ├── generate_arch_test_models.py # Procedural architectural test scenario generator
│   ├── stats_util.py               # Statistical rigor: Wilson score & bootstrap 95% CIs
│   ├── eval_gold_code_9_8_stairs.py # Hand-annotated ground-truth answer key
│   ├── eval_harness.py             # LLM-as-judge scoring harness
│   ├── run_all.py                  # Tier-ordered orchestrator with baseline comparison
│   ├── compare_baselines.py        # Standalone baseline comparison CLI
│   └── ori_bridge.py               # Bridge for the TypeScript Ori Eval model-comparison harness
├── kg/                              # Code-clause <-> bSDD ontology knowledge graph pipeline
│   ├── build_kg.py                 # CLI: DocLang source -> clause/bSDD candidate-match graph
│   ├── correct_graph.py            # CLI: LLM verification/filter pass over borderline matches
│   ├── merge_graphs.py             # CLI: append a code's graph onto the combined multi-code graph
│   ├── clause_builder.py           # Groups DocLang into Clause units + intra-doc edges
│   ├── graph_builder.py            # Assembles/exports the networkx.MultiDiGraph
│   ├── bsdd_loader.py              # Loads the bSDD ontology reference database
│   ├── similarity.py               # Lexical clause<->term candidate scoring
│   ├── llm_correction.py           # LLM verify/filter logic used by correct_graph.py
│   ├── grounding.py / export_grounding.py # Grounding index export
│   ├── prioritize_review_queue.py  # Ranks uncertain matches for human review
│   └── apply_review_decisions.py   # Applies human review decisions back onto the graph
│
├── docs/                           # DocLang specification & reference toolkit
│   ├── doclang-spec-0.7.md         # Normative DocLang v0.7 specification
│   ├── doclang-README-fea2146.md   # Reference toolkit guide
│   ├── rule-extraction-corrections.md # score_rule_extraction_corrections.py design & usage
│   ├── kg-ingestion-pipeline.md    # Standardized, repeatable code -> knowledge graph pipeline
│   └── DATA_LICENSING.md           # Third-party building-code corpus licensing basis
├── research/                       # Research data, claims ledger, and archived run artifacts
│   ├── CLAIMS.md                   # Claims-to-evidence ledger — status of every headline number
│   ├── appendix_c_determinism_investigation.md # Determinism bug: found, root-caused, fixed upstream
│   └── archive/retired_corrosion_piping_seismic_domain/ # Historical: the retired Piping/Corrosion/Seismic domain
├── LICENSE
├── LIMITATIONS.md                  # Methodological limitations, stated plainly
├── CITATION.cff
├── pyproject.toml
└── README.md
```

---

## Installation & Setup

Using [uv](https://github.com/astral-sh/uv) (recommended) or standard virtual environment:

```bash
git clone https://github.com/maicen/bim-guard-evaluation.git
cd bim-guard-evaluation

# Install dependencies with uv
uv sync
```

Or using `pip`:
```bash
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -e .
```

To run harnesses that evaluate against core BIM-Guard compute engines, ensure the core repository is cloned adjacent to this repository or set `BIMGUARD_PATH`:
```bash
export BIMGUARD_PATH="/path/to/bim-guard"  # Windows: $env:BIMGUARD_PATH="C:\path\to\bim-guard"
```

---

## Running Evaluations

### 1. Linguistic Annotation Scoring
Runs the 60-point test suite across deontic extraction, conditions, cross-references, dependencies, and dimension constraints:
```bash
python eval/score_nlp_annotation.py
```

### 2. Rule Extraction Scoring
Evaluates rule extraction accuracy against hand-annotated ground-truth:
```bash
python eval/score_rule_extraction.py
```

### 2b. Rule Extraction Correction Accuracy
Scores extraction accuracy against real human reviewer edits pulled live from
bim-guard's `rule_extraction_drafts` table (Mode A) or committed offline fixtures:
```bash
python eval/score_rule_extraction_corrections.py
```

### 2c. Architectural Compliance Engine Benchmark
Evaluates bim-guard's active architecture compute engines (`ARCH-EGRESS-001`, `ARCH-SPATIAL-001`) with complete confusion matrix, precision/recall, and Wilson score 95% confidence intervals:
```bash
python eval/score_arch_engines.py
```

### 3. LLM-as-Judge Rule Generation Quality
Scores rule-generation correctness/completeness/executability against golden cases, with a TP/FP/FN/TN confusion matrix:
```bash
python eval/eval_harness.py
```

### 4. Orchestrated Run
Runs the hermetic/component tiers in order and compares against stored baselines:
```bash
python eval/run_all.py --tier 1 --json --compare-baseline
```

> [!NOTE]
> A 38-model IFC validation sweep and confusion-matrix/tables-and-figures synthesis
> previously ran here (`test_all_38_models.py`, `analyse_validation_results.py`).
> Both measured bim-guard's Piping/Corrosion domain, permanently retired 2026-09-21 —
> see [`research/archive/retired_corrosion_piping_seismic_domain/README.md`](research/archive/retired_corrosion_piping_seismic_domain/README.md).

---

## Model Comparison (Ori Eval)

`evals/rule-extraction/` uses [Ori Eval](https://openrouter.ai/docs/guides/ori/eval)
to compare OpenRouter models on BIM-Guard's real rule-extraction code — LLM-as-judge
scoring plus deterministic recall against the hand-annotated gold rules. See
[evals/rule-extraction/README.md](evals/rule-extraction/README.md) for setup and usage.

---

## Related Repositories

- **Core Application**: [maicen/bim-guard](https://github.com/maicen/bim-guard)
- **Analytics & Power BI Model**: [maicen/bimguard-analytics](https://github.com/maicen/bimguard-analytics)
