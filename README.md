# BIM-Guard Evaluation & Research Analysis

Evaluation harnesses, NLP annotation capabilities, accuracy scoring, and empirical research validation analysis for the BIM-Guard platform.

> [!NOTE]
> **Cross-Reference:** This repository is the evaluation and empirical analysis companion to the primary BIM-Guard platform repository:
> - **Core Platform Repository:** [maicen/bim-guard](https://github.com/maicen/bim-guard) — FastAPI API Gateway, Svelte 5 SPA frontend, ISO 19650 CDE workflow, and modular compliance/corrosion physics engines (GC-001, CC-001, MC-001, MM-001, XM-001).
> 
> All research analysis, confusion matrix evaluations, linguistic annotation benchmarks, and multi-model validation sweeps are intentionally maintained and conducted in this dedicated repository outside the production BIM-Guard runtime system.

---

## Overview

This repository isolates academic and empirical validation from core application services:

1. **Linguistic NLP Annotation (`nlp_annotation/`)**
   Five rule-based annotator capabilities extracting structured metadata from building codes and standard clauses:
   - **Deontic Operator Extraction**: Modal analysis (`SHALL`, `MUST`, `IS REQUIRED TO`, `SHALL NOT`, `SHOULD`, `MAY`) with negation resolution.
   - **Condition & Scope Parsing**: Extraction of applicability clauses (`WHERE`, `WHEN`, `IF`) and exceptions (`EXCEPT`, `UNLESS`).
   - **Cross-Reference Resolution**: Resolution of Section, Article, Sentence, Clause, Table, and Figure citations.
   - **Clause Dependency Mapping**: Relational mapping (`NOTWITHSTANDING`, `IN LIEU OF`, `SUBJECT TO`).
   - **Dimension & Unit Extraction**: Measurement values, metric/imperial units, and constraint bounds (`min`, `max`, `range`, `exact`).
   - **IFC Semantic Entity Mapping**: Grounded dictionary linking code vocabulary to IFC classes (`IfcStairFlight`, `IfcDoor`, `IfcPipeSegment`, etc.).

2. **Scoring & Evaluation Harnesses (`eval/`)**
   - `score_nlp_annotation.py`: Automated scoring test suite verifying 54 linguistic test cases across all 5 annotator capabilities.
   - `score_rule_extraction.py`: Structural diagnostics (heading detection, skip leakage, table coverage, regex baseline) and LLM-based rule extraction accuracy against hand-annotated gold standards.
   - `eval_gold_code_9_8_stairs.py`: Hand-annotated ground-truth dataset for Part 9 code requirements.
   - `eval_harness.py`: LLM-as-judge evaluation harness tracking correctness, completeness, and executability.
   - `test_all_38_models.py`: Automated validation sweep over the 38-model verified IFC dataset, extracting geometry, generating halo volumes, and executing corrosion compliance engines.
   - `analyse_validation_results.py`: Research synthesis script generating confusion matrices, empirical distributions, standards sensitivity curves, BCF validity checks, and thesis validation tables and figures.

3. **Research Artifacts & Validation Data (`research/`)**
   - **Tables**: `table1_per_model.csv` through `table7b_schema_twins.csv`
   - **Figures**: `figB1_clash_severity.png` through `figB4_schema_scatter.png`
   - **Empirical Reports & Methodology**: Appendix B validation specifications, baseline corrosion findings, BCF 2.1 GUID typing audits, and dataset inventories.

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
│   └── ifc_mapping.py              # IFC entity mapping dictionary
├── eval/                           # Evaluation and scoring harnesses
│   ├── score_nlp_annotation.py     # 5-capability NLP annotation scoring
│   ├── score_rule_extraction.py    # Rule extraction accuracy scoring
│   ├── eval_gold_code_9_8_stairs.py # Hand-annotated ground-truth answer key
│   ├── eval_harness.py             # LLM-as-judge scoring harness
│   ├── analyse_validation_results.py # Confusion matrices, 7 tables, 4 figures
│   ├── test_all_38_models.py       # 38-model validation sweep harness
│   └── test_real_ifc_pipeline.py   # Real IFC end-to-end pipeline validation
├── research/                       # Research data, CSV tables, figures & logs
│   ├── table1_per_model.csv        # Validation sweep summary table
│   ├── table2_severity.csv         # Clash severity distribution
│   ├── table3_material_engine.csv  # Material cross-tabulation
│   ├── table4_engine_coverage.csv  # Engine input coverage
│   ├── table5_bcf_validity.csv     # BCF 2.1 archive XML/viewpoint audit
│   ├── table6_standards_sensitivity.csv # Threshold sensitivity
│   ├── table7_schema.csv           # IFC2X3 vs IFC4 fidelity
│   ├── figB1_clash_severity.png    # Histogram
│   ├── figB2_material_heatmap.png  # Risk heatmap
│   ├── figB3_engine_radar.png      # Engine coverage radar
│   └── figB4_schema_scatter.png    # Schema comparison scatter
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
Runs the 54-point test suite across deontic extraction, conditions, cross-references, dependencies, and dimension constraints:
```bash
python eval/score_nlp_annotation.py
```

### 2. Rule Extraction Scoring
Evaluates rule extraction accuracy against hand-annotated ground-truth:
```bash
python eval/score_rule_extraction.py
```

### 3. Full 38-Model Validation Sweep
Runs the automated geometry extraction, halo clash generation, and compliance checks across the dataset:
```bash
python eval/test_all_38_models.py --smoke   # Quick smoke test on 3 models
python eval/test_all_38_models.py           # Full 38-model sweep
```

### 4. Empirical Research & Confusion Matrix Analysis
Synthesizes validation results into confusion matrices, sensitivity analyses, 7 tables, and 4 figures:
```bash
python eval/analyse_validation_results.py
```

---

## Related Repositories

- **Core Application**: [maicen/bim-guard](https://github.com/maicen/bim-guard)
- **Analytics & Power BI Model**: [maicen/bimguard-analytics](https://github.com/maicen/bimguard-analytics)
