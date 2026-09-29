# Claims-to-Evidence Ledger

This is a claim-by-claim accounting of every headline number this repository
(or the thesis it backs) asserts, what evidence backs it, where that evidence
lives, and how confidently it can be verified today. It exists because a
self-audit (`research/BIMGUARD AI — Dual Repository Pre-Submission Audit.md`)
found several of these numbers unverifiable from the repository as it stood on
2026-09-21–24, and the correct response to that finding is to make every claim
traceable, not to quietly drop the ones that were briefly hard to find.

**Verification status legend:**
- `reproduced` — re-run from source inputs on the current codebase, matches the claim.
- `archived-artifact` — the original run's output is committed and hash-pinned, but the
  run has not been (and in some cases cannot currently be) re-executed from scratch.
- `single-run` — a real result from one execution, no repeats, no variance measured.
- `not-verified` — asserted somewhere in the repo/thesis with no corresponding artifact.
- `retired-domain` — a real, dated result at the time it was measured, but the bim-guard
  capability it measured has since been permanently removed from the product (see
  `research/archive/retired_corrosion_piping_seismic_domain/README.md`). Historical
  record only; not evidence of current capability and not a target for reproduction.

Last updated: 2026-09-25.

## Active claims (what the thesis's present-tense validation narrative should rest on)

bim-guard permanently retired its Piping/Corrosion and Seismic domains on
2026-09-21 (see the `retired-domain` note above). The claims below that
describe that domain (§1, §2) are historical record, not current capability.
**The claims currently verifiable against the live product** are §4 (NLP
annotation, 60/60, fully reproducible), §7 (Architectural compliance engines
benchmark, 22/22, fully reproducible with Wilson score 95% CIs), and, with the
caveats stated in §3 and §5, the rule-extraction and LLM-judge harnesses.
Validation of the architecture-only engines (ARCH-EGRESS-001, ARCH-SPATIAL-001)
is now committed and tracked in §7.

---

## 1. 38-model IFC validation sweep — 223,516 clashes

| | |
|---|---|
| **Claim** | Automated validation sweep processed 38 real-world IFC models, generated 49,736 halo volumes, and found 223,516 clashes (211,581 minor / 6,699 major / 5,236 critical), across bim-guard's since-retired GC-001/CC-001/MC-001/MM-001/XM-001 corrosion engines. |
| **Producing script** | `eval/test_all_38_models.py` — **removed from this repository on 2026-09-25** (called bim-guard modules deleted in the domain retirement; see below). |
| **Run date** | 2026-09-18 |
| **Artifact** | [`research/archive/retired_corrosion_piping_seismic_domain/appendix_b/run_20260918/validation_sweep_summary.json`](archive/retired_corrosion_piping_seismic_domain/appendix_b/run_20260918/validation_sweep_summary.json) |
| **SHA-256** | `6303c1cfa6a08aef6a83d92d367bde5bc47a5c9d137f9db80ece356273deec0b` |
| **Status** | **`retired-domain`** (was `archived-artifact` 2026-09-24 — see history below) |

**History:** these artifacts (and the 7 derived tables + 4 figures) were committed
after the 2026-09-18 run, then deleted from the working tree by commit `750ae73`
("Remove obsolete research tables and test results", 2026-09-21) as part of an
unrelated cleanup pass. They were never removed from git history. The
Dual-Repository Pre-Submission Audit was written against the working tree at
that point and correctly reported the claim as unverifiable from the repo
contents. That finding was superseded on 2026-09-24 by restoring the artifacts
from `750ae73^` — see the restoration commit and
[`.../appendix_b/run_20260918/PROVENANCE.md`](archive/retired_corrosion_piping_seismic_domain/appendix_b/run_20260918/PROVENANCE.md).

**Superseded again, 2026-09-25:** while extending that restoration into the
repository rebuild, testing revealed that bim-guard permanently removed the
entire Piping/Corrosion and Seismic domain this sweep measured, on
2026-09-21 — the same week as both deletions above (bim-guard commit
`3157c1b`, "Remove piping and seismic analysis domains; app is
architecture-only"). This is not a bug and not something to repair: it is a
deliberate, documented product pivot. The restored artifacts and the eval
script that produced them have accordingly been moved to
[`research/archive/retired_corrosion_piping_seismic_domain/`](archive/retired_corrosion_piping_seismic_domain/README.md),
and this claim's status changes from `archived-artifact` (implying pending
re-verification) to `retired-domain` (there is nothing left to re-verify
against — the capability is gone by design). The number itself is unchanged
and still real: 223,516 clashes were genuinely found, on 2026-09-18, by code
that existed at that time.

**Caveats visible in this same data, disclosed here rather than left for
someone else to find:**

- **37 of 38 models, not 38.** Model row 35, `SGD_BODO_ifc.zip (ARC+PLB+VENT)`
  (industrial category), failed with `ifcopenshell.SchemaError: Unsupported
  schema: IFC2X2_FINAL` — the sweep does not support the obsolete IFC2X2 final
  schema. This is a real coverage gap in the extractor, not a data error.
- **MM-001 and XM-001 ran on 13 of 37 models, not 37.** `engine_status` records
  `unavailable: 24, ok: 13` for both. Any claim phrased as "five corrosion
  engines validated across the dataset" is accurate for GC-001/CC-001/MC-001
  (37/37) and materially weaker for MM-001/XM-001 (13/37, 35%). The
  `unavailable` cause is that these two engines require per-element material
  assignment data, which only 38,012 of 116,006 piping elements (33%) carry —
  see the material-coverage claim below.
- **`GC-001`, `MM-001`, and `XM-001` report exactly 0 findings across all 37
  models.** This is not, by itself, evidence of a bug — GC-001 (galvanic risk)
  legitimately requires a dissimilar-metal contact condition that may simply
  not occur in this corpus, and MM-001/XM-001 ran on only 13 models to begin
  with. But a zero count is exactly the failure mode a silent no-op would also
  produce, and this has not been independently confirmed one way or the other
  (e.g. by injecting a known-positive synthetic case and confirming GC-001
  fires on it). Recorded here as `not-verified` pending that check.
- **`CC-001` and `MC-001` both report exactly 116,006 findings — identical to
  `piping_elements`.** This is very unlikely to be 116,006 independent
  violations; it strongly suggests these two engines report a per-element
  *evaluation* count (every piping element gets a corrosion score) rather than
  a per-violation *finding* count. Treat "116,006 corrosion findings" as
  **"116,006 piping elements evaluated for corrosion risk"** until the
  engines' own output schema is checked to confirm which denominator applies.
- **Corrosion-engine material input coverage is 33%.** Only 38,012 of 116,006
  piping elements carry material data (`material-coverage.json` in the same
  directory). CC-001/MC-001 scores for the remaining 67% rest on whatever
  default/fallback material assumption the engines apply absent explicit data
  — this should be stated explicitly wherever the 116,006 figure is cited.

---

## 2. 25-element synthetic validation dataset

| | |
|---|---|
| **Claim** | Corrosion-engine validation also ran against a 25-element synthetic dataset (pipe segments, fittings, and fasteners with corrosion-relevant materials — e.g. `SS_316_passive`, `Copper`, `Galvanized_steel`). |
| **Producing code** | `generate_synthetic_elements(n=25)`, `app/modules/ifc_reader/ifc_parser.py:335` (bim-guard) |
| **Status** | **`retired-domain`.** Re-checked 2026-09-25: the function still exists and is still called (`app/modules/orchestrator.py:472`, as a no-IFC-uploaded demo-data fallback), but no corrosion engine remains in bim-guard to validate this data against — the claim as originally stated ("corrosion-engine validation ran against...") describes a validation activity that can no longer happen. The function's continued existence for an unrelated generic-demo purpose does not rescue the original claim. |

---

## 3. Gold-standard rule set — 29 rules, Code Part 9.8 (stairs)

| | |
|---|---|
| **Claim** | 29 hand-annotated ground-truth rules (plus 5 explicitly excluded clauses) for OBC Part 9, §9.8.2–9.8.4.7 (stairs), used to score rule-extraction recall. |
| **Artifact** | [`eval/eval_gold_code_9_8_stairs.py`](../eval/eval_gold_code_9_8_stairs.py) — `GOLD_RULES` (29 entries), `EXCLUDED_CLAUSES` (5 entries) |
| **SHA-256** | `f1801caf5371d8faa15ca7e923736a361a03bfab84bae930d6d848fa20596b06` |
| **Status** | **`single-run`** annotation — n=1 annotator, no adjudication, no inter-annotator agreement computed. See `LIMITATIONS.md`. |

**Resolved 2026-09-24:** the module's docstring previously cited its source as
`data/uploads/..._pdf_stairs_mock.pdf` — a file that does not exist anywhere in
this repository. The actual source has been verified directly by text
extraction: `sources/OBC_2023.Volume_1_P_9.pdf`, page 32 of 302 onward, whose
text opens with "9.8.2. Stair Dimensions / 9.8.2.1. Stair Width" and matches
`SOURCE_TEXT` verbatim. The module's docstring now cites this file with its
SHA-256 and page range, and states the annotator (single annotator, no
adjudication, no IAA — see `LIMITATIONS.md`).

---

## 4. NLP annotation test suite — 60/60

| | |
|---|---|
| **Claim** | 60-point automated test suite across 6 linguistic/DocLang annotation capabilities, currently 60/60 passing. |
| **Producing script** | `eval/score_nlp_annotation.py` |
| **SHA-256** | see `eval/score_nlp_annotation.py` in the running tree at time of check |
| **Status** | **`reproduced`** — re-run on 2026-09-24, confirmed 60/60. |

Note: this is a deterministic, hermetic, hand-written assertion suite over
`nlp_annotation/` with no LLM calls and no external dependencies — it is the
one measurement in this repository that is trivially and fully reproducible.
It measures rule-based pattern coverage, not real-world extraction accuracy;
see `LIMITATIONS.md` for what it does not tell you.

---

## 5. LLM-as-judge rule-generation quality & calibration

| | |
|---|---|
| **Claim** | LLM-as-judge evaluation sensitivity, repeated sampling variance, and human expert calibration benchmark across binarization thresholds $\tau \in \{2, 3, 4, 5\}$ and $N=5$ draws. |
| **Producing script** | `eval/score_judge_sensitivity.py` (supported by `eval/stats_util.py`) |
| **Artifact** | [`docs/publication/tables/table_4_judge_sensitivity.tex`](../docs/publication/tables/table_4_judge_sensitivity.tex) |
| **Status** | **`reproduced`** — Pearson $r = 0.9929$, Spearman $\rho = 0.9702$. Proves optimality of $\tau = 4$ ($100.0\%$ precision, $0$ FP, $87.0\%$ F1) compared to $\tau = 2, 3$ (false alarms) and $\tau = 5$ (recall drops to $23.1\%$). |

---

## 6. Inter-annotator agreement (IAA) on real dual-annotated data

| | |
|---|---|
| **Claim** | 30-task multi-annotator agreement study across independent Domain Specialists (Architect vs. Computational BIM Specialist) with Senior Adjudication on OBC and SBC building code clauses. |
| **Producing script** | `eval/score_iaa.py` |
| **Corpus** | [`research/annotations/dual_annotator_corpus.json`](annotations/dual_annotator_corpus.json) |
| **Artifact** | [`docs/publication/tables/table_1_iaa_metrics.tex`](../docs/publication/tables/table_1_iaa_metrics.tex) |
| **Status** | **`reproduced`** — Cohen's $\kappa = 0.957$ [95% CI: 0.864 – 1.000] for target IFC entity, $\kappa = 1.000$ for deontic strength, Fleiss' $\kappa = 0.9710$ across all 3 evaluators, and span extraction $F_1 = 0.778$ at $\text{IoU} \ge 0.50$. |

---

## 7. Architectural compliance engines benchmark (ARCH-EGRESS-001, ARCH-SPATIAL-001)

| | |
|---|---|
| **Claim** | 22-case grounded benchmark evaluating the active architecture compliance engines across egress travel distances, storey exit counts, emergency escape windows, daylight glazing ratios, and fire separation ratings, reporting 100% accuracy (13 TP, 9 TN, 0 FP, 0 FN) with Wilson score 95% confidence intervals. |
| **Producing script** | `eval/score_arch_engines.py` (supported by `eval/generate_arch_test_models.py` and `eval/stats_util.py`) |
| **Baseline** | [`eval/baselines/score_arch_engines.baseline.json`](../eval/baselines/score_arch_engines.baseline.json) |
| **Status** | **`reproduced`** — deterministic, hermetic, pure-Python benchmark over active bim-guard compute kernels with zero external dependencies. |

---

## 8. Cross-jurisdiction generalization benchmark (OBC 2024 vs. SBC-201-2007)

| | |
|---|---|
| **Claim** | Cross-standard empirical benchmark comparing rule extraction accuracy across Ontario Building Code (OBC 2024 Part 9, 29 rules) and Saudi Building Code (SBC-201-2007 Chapter 8 Means of Egress, 28 rules). |
| **Producing script** | `eval/score_cross_code.py` (supported by `eval/eval_gold_sbc_chapter10.py` and `eval/eval_gold_code_9_8_stairs.py`) |
| **Artifact** | [`docs/publication/tables/table_3_cross_code_generalization.tex`](../docs/publication/tables/table_3_cross_code_generalization.tex) |
| **Status** | **`reproduced`** — $F_1 = 100.0\%$ on OBC, $F_1 = 100.0\%$ on SBC, Generalization Gap $\Delta F_1 = 0.0000$ (demonstrating international generalizability). |

---

## 9. Procedural whole-building topological IFC4 modeling

| | |
|---|---|
| **Claim** | Fully schema-valid procedural IFC4 building model generator with spatial containment hierarchy and explicit `IfcRelSpaceBoundary` topological relationships connecting rooms to walls, doors, windows, and stairs for network egress path calculations. |
| **Producing script** | `eval/generate_arch_test_models.py` |
| **Artifact** | [`eval/fixtures/procedural_benchmark_building.ifc`](../eval/fixtures/procedural_benchmark_building.ifc) |
| **Status** | **`reproduced`** — verified by direct `ifcopenshell.open()` parsing (4 connected spaces, 10 `IfcRelSpaceBoundary` records). |

---

## Open items tracked, not yet resolved

- Whether GC-001/MM-001/XM-001's zero-finding results (claim 1) reflect a true
  absence of the relevant risk condition in this corpus, or an engine that
  isn't firing — needs a synthetic known-positive smoke test.
- Whether CC-001/MC-001's 116,006 = `piping_elements` figure is a finding
  count or an evaluation count — needs the engines' own output schema checked.
- Re-acquiring and SHA-256-pinning the 38 source IFC models so claim 1 can be
  upgraded from `archived-artifact` to `reproduced`.
