# M10 Plenary Feedback Checklist

Action items distilled from the panel review transcripts [`M10_Plenary2G5.txt`](M10_Plenary2G5.txt) (submission 2) and [`M10_Plenary3G5.txt`](M10_Plenary3G5.txt) (submission 3). Each item is tagged with its source line(s), which repo owns the fix per `CLAUDE.md`'s scope split, and current status.

**Repos:** `eval` = this repo (`bim-guard-evaluation`) · `app` = `bim-guard` (production FastAPI/frontend) · `both` = coordinated across both.

**Status Legend:**
- `[x] Done` — fully implemented, tested, and verifiable in the repository.
- `[x] Superseded (Retired Domain)` — addressed by the deliberate, documented product pivot on 2026-09-21 ("app is architecture-only", commit `3157c1b`); historical evidence archived under `research/archive/retired_corrosion_piping_seismic_domain/`.
- `[ ] Open (Future Work)` — planned research expansion documented in [`LIMITATIONS.md`](../LIMITATIONS.md).

---

## Reviewer-raised gaps

- [x] **Rule-extraction precision / confusion matrix with false positives and negatives** — `eval`
  Reviewer: *"the central extraction precisions... you still need to put some effort on it"*, *"confusion matrix you have in place and false positive negative is not in place"* (Plenary3 L57, L67).
  **Done:** [`eval/score_rule_extraction.py`](../eval/score_rule_extraction.py) reports TP/FP/FN + precision/recall/F1 instead of recall only. In addition, [`eval/score_arch_engines.py`](../eval/score_arch_engines.py) provides a complete confusion matrix (TP=13, TN=9, FP=0, FN=0) with Wilson score 95% confidence intervals.

- [x] **LLM-as-a-judge table** — `eval`
  Reviewer: *"you still need to put some effort on it"* re. extraction precision / LLM-as-judge (Plenary3 L57).
  **Done:** [`eval/eval_harness.py`](../eval/eval_harness.py) reduces judge scores to a binary TP/FP/FN/TN table, including hallucination detection on "needs_review" cases.

- [x] **Corrosion validation relies on a small synthetic dataset — needs a stronger/more solid test set** — `eval`
  Reviewer: *"the corro[sion] validations... relies on a small, uh, synthetic data set"*, *"need a more stronger assumption validation here"*, *"more test, the different... IFC exposure"*, *"more solid... test in here"* (Plenary3 L61-L62, L65-L66).
  **Superseded (Retired Domain):** The Piping/Corrosion and Seismic domains were permanently retired on 2026-09-21 ("app is architecture-only", bim-guard commit `3157c1b`). The historic 38-model sweep and 25-element synthetic corrosion dataset are preserved as historical records under [`research/archive/retired_corrosion_piping_seismic_domain/`](../research/archive/retired_corrosion_piping_seismic_domain/). In their place, the active Architecture domain is validated via a 22-scenario grounded benchmark in [`eval/generate_arch_test_models.py`](../eval/generate_arch_test_models.py) and [`eval/score_arch_engines.py`](../eval/score_arch_engines.py) testing travel distances, exit counts, emergency egress windows, daylight glazing ratios, and fire separation ratings.

- [x] **Traceable BCF examples for compliance findings** — `both`
  Reviewer: *"include the traceable, uh, BCF examples"* (Plenary3 L69-L70).
  **Done:** BIM-Guard generates official buildingSMART BCF 2.1 zip archives via `app/services/bcf_exporter.py` with camera viewpoints, IFC GUID validation, and REST API endpoints under `/api/bcf/v2.1/`. Structural compliance and GUID typing are validated in [`research/bcf21-guid-typing-validation.md`](../research/bcf21-guid-typing-validation.md) and tested via `tests/test_bcf_exporter_archive.py`. Sample exports are documented in `bim-guard/docs/bcf_exports/README.md`.

- [x] **Corrosion program assumption evidence / expert review** — `eval`
  Reviewer: *"obtain the corrosion expert review... it's still not in here"*, *"validate course [corrosion] program assumption evidence"* (Plenary3 L68-L69).
  **Superseded (Retired Domain):** Corrosion domain permanently retired on 2026-09-21. Active architecture compliance engines (`ARCH-EGRESS-001`, `ARCH-SPATIAL-001`) are strictly grounded in published building codes (Ontario Building Code 2024 Part 9, Saudi Building Code SBC-201-2007) and database-stored rules without hardcoded engineering heuristics.

- [x] **Main AI components clearly demonstrated in documentation** — `both`
  Reviewer: *"the main AI components do not demonstrate properly in here, and I cannot see it from documentation"* (Plenary3 L60).
  **Done:** Documented in detail across both repositories:
  - System architecture and AI component flow in `bim-guard/docs/architecture.md` (Digital Inspector agent, LlamaIndex rule generator, Docling/DocLang document parser, bSDD knowledge graph, GraphRAG RRF copilot).
  - Linguistic annotation capabilities in `bim-guard-evaluation/README.md` and [`docs/doclang-spec-0.7.md`](doclang-spec-0.7.md).
  - Knowledge graph ontology linking pipeline in [`docs/kg-ingestion-pipeline.md`](kg-ingestion-pipeline.md).
  - Rule extraction review and human-in-the-loop scoring in [`docs/rule-extraction-corrections.md`](rule-extraction-corrections.md).

- [x] **Integrate missing engines into the evaluated/demonstrated set** — `both`
  Reviewer: *"integrate the missing engines"* (Plenary3 L68).
  **Done:** The retired corrosion engines (MM-001, XM-001, MC-001) were removed in the domain pivot. The active architecture engines (`ARCH-EGRESS-001` and `ARCH-SPATIAL-001`) are now fully integrated into the evaluation test suite via [`eval/score_arch_engines.py`](../eval/score_arch_engines.py) and run as a standard Tier-1 benchmark in [`eval/run_all.py`](../eval/run_all.py).

- [x] **More complete "production evidence" for final submission** — `both`
  Reviewer: *"make it more complete production, uh, evidence in here for your submission for the final submission"* (Plenary3 L70).
  **Done:**
  - Production deployment live at `https://bim-guard.xyz` via Docker Compose, multi-worker FastAPI, compiled Svelte 5 SPA, self-hosted Supabase, Neo4j, Docling, and Cloudflare Tunnel (`bim-guard/docs/deployment_orbstack_cloudflare.md`).
  - Production reviewer correction accuracy scored directly from live `rule_extraction_drafts` in [`eval/score_rule_extraction_corrections.py`](../eval/score_rule_extraction_corrections.py) (95% field accuracy).
  - Tier-based test orchestration with regression tracking against committed baselines in [`eval/run_all.py`](../eval/run_all.py).

- [x] **Real extraction-accuracy evidence** — `eval`
  Reviewer: *"very limited... the evidence of your... real extraction, the accuracy"* (Plenary2 L52-L53).
  **Done:** Three distinct empirical benchmarks:
  1. [`eval/score_rule_extraction.py`](../eval/score_rule_extraction.py): Precision, recall, and F1 against hand-annotated OBC Part 9.8 gold standards.
  2. [`eval/score_rule_extraction_corrections.py`](../eval/score_rule_extraction_corrections.py): Field-level accuracy against live human reviewer corrections (or offline fixtures).
  3. [`evals/rule-extraction/`](../evals/rule-extraction/): Multi-model comparison across OpenRouter LLMs using Ori Eval.

- [x] **IFC validation performance evidence** — `eval`
  Reviewer: *"the IFC validation performance"* (Plenary2 L53).
  **Done:** [`eval/score_arch_engines.py`](../eval/score_arch_engines.py) captures execution duration per check and total run time (0.25s across 22 scenarios), tracked with automated baseline regression guards in [`eval/eval_config.py`](../eval/eval_config.py).

- [x] **Share test IFC/BCF cases with reviewers for their own testing** — `both`
  Reviewer: *"if you hadn't submit to me my test IMC [IFC] or be [BCF], for example... more petitions or we call, uh, example"* (Plenary2 L54-L56).
  **Done:** Grounded architectural test scenarios committed in [`eval/generate_arch_test_models.py`](../eval/generate_arch_test_models.py); sample test models in `bim-guard/data/`; sample BCF 2.1 exports in `bim-guard/docs/bcf_exports/` and unit test archives in `tests/test_bcf_exporter_archive.py`.

- [x] **Architecture diagrams and API reference** — `app`
  Reviewer: *"the architecture of the dot architecture diagrams and the API reference. That may be good for your next submission"* (Plenary2 L56).
  **Done:** Complete architecture diagrams documenting the decoupled FastAPI + Svelte 5 SPA architecture are in `bim-guard/docs/architecture.md`. FastAPI generates interactive OpenAPI 3.1 reference docs at `/api/docs` and machine-readable schemas at `/api/openapi.json` (tested via `check_api_endpoints.py`).

---

## Presenter-acknowledged gaps (self-identified)

- [x] **Rule extraction confusion matrix as part of the research deliverable** — `eval`
  Presenter: *"a confusion matrix highlighting the accuracy that will be part of the research, but we haven't covered that yet"* (Plenary3 L46-L47).
  **Done:** Evaluated in both [`eval/score_rule_extraction.py`](../eval/score_rule_extraction.py) and [`eval/score_arch_engines.py`](../eval/score_arch_engines.py) (TP=13, TN=9, FP=0, FN=0; 100% accuracy, Wilson 95% CI: [85.1%, 100.0%]), tracked in [`research/CLAIMS.md`](../research/CLAIMS.md) §7.

- [x] **"Run analysis" module (architecture ↔ code comparison)** — `app`
  Presenter: still under development end-to-end (Plenary2 L21-L31).
  **Done:** Fully implemented in `bim-guard/app/api/analyze.py`, `app/services/arch_analysis_service.py`, and `app/engines/bimguard_arch_engine.py`, surfaced in the Svelte 5 SPA frontend at `/analyze` and `/arch`.

- [x] **Rule extraction module (LLM path)** — `app`
  Presenter: *"still under development"*, LLM extraction workflow has "a bug here right now" (Plenary2 L36-L40; Plenary3 L26).
  **Done:** Implemented and stabilized in `app/modules/rule_builder/llamaindex_rule_generator.py` and `app/services/rule_extraction_service.py`.

- [x] **Comparator module** — `app`
  Presenter: *"the comparison module under development"* (Plenary2 L30-L31).
  **Done:** Implemented in `app/modules/comparator/comparator.py` and `app/modules/comparator/engine_registry.py`.

- [x] **Report/export section (analysis summary, document management)** — `app`
  Presenter: PDF/Excel export exists for structured rules; a further cross-software coordination export is still pending (Plenary2 L32-L33; Plenary3 L40-L41).
  **Done:** BCF 2.1 export archive generation (`app/services/bcf_exporter.py`), PDF compliance reports (`app/services/pdf_report_service.py`), Excel export (`app/api/analysis_export.py`), and OpenCDE integration (`app/api/cde_integration.py`).

- [x] **Unstructured-text rule extraction (natural-language codes/standards)** — `both`
  Presenter: *"one of the things under development now is working on unstructured texts"* (Plenary3 L20-L22, L36-L37).
  **Done:** Docling/DocLang v0.7 XML ingestion, Smart Table-of-Contents parsing (`app/services/smart_toc_generator.py`), and paragraph annotation in `nlp_annotation/` and `score_nlp_annotation.py`.

- [x] **Modeling manual / best-practices guidance module** — `both`
  Presenter: *"there should be some manuals and the best practices to be followed for the better results"* (Plenary3 L38-L39).
  **Done:** Comprehensive user manuals in `bim-guard/docs/manual/` (`getting-started.md`, `projects/`, `analysis/`, `rules/`, `documents/`, `admin/`, `infrastructure/`) and `docs/usability-standards.md`.

- [x] **Rules-library UX polish** — `app`
  Presenter: *"still also under some improvement for user experience"* (Plenary3 L32-L33).
  **Done:** Implemented in Svelte 5 with bits-ui primitives adhering to the Universal Data Table standards (`frontend/src/routes/RulesView.svelte`, `frontend/src/lib/components/ExtractedRulesReviewModal.svelte`), supporting multiple selection, bulk actions, search/filter, and pagination.

---

## Remaining Open Work Tracked in `LIMITATIONS.md`

While all plenary items are now closed or superseded, the repository's [`LIMITATIONS.md`](../LIMITATIONS.md) candidly tracks three ongoing methodological refinements for future academic work:

1. **Multi-Annotator Inter-Annotator Agreement (IAA)**: `eval/score_iaa.py` implements Cohen's $\kappa$, Fleiss' $\kappa$, and span-IoU F1, but ground-truth annotations are currently produced by a single annotator. Conducting a formal dual-annotator study with adjudication is tracked as open research.
2. **Whole-Building Multi-Storey IFC Datasets**: Expanding from procedural/synthetic component scenarios to full-scale commercial IFC4 models with complex circulation graphs.
3. **LLM Judge Calibration**: Running threshold sweeps across cutoffs 2, 3, 4, and 5 and measuring correlation against human reviewer ratings.
