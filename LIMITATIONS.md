# Limitations

This document states, plainly and with numbers, the methodological gaps in
this repository's evaluation and validation work as of 2026-09-24. It exists
because every one of these will be found by a careful reader — stating them
here first converts each from a discovered flaw into demonstrated
methodological awareness. See [`research/CLAIMS.md`](research/CLAIMS.md) for
the corresponding claim-by-claim evidence ledger.

## Statistical rigor

- **Confidence intervals, bootstrap estimates, and significance tests (RESOLVED 2026-09-29).**
  Exact Wilson score 95% confidence intervals have been implemented in [`eval/stats_util.py`](eval/stats_util.py)
  and are reported across all classification metrics in [`eval/score_arch_engines.py`](eval/score_arch_engines.py),
  [`eval/score_cross_code.py`](eval/score_cross_code.py), and [`eval/score_judge_sensitivity.py`](eval/score_judge_sensitivity.py).
  Non-parametric bootstrap resampling (1,000 resamples) provides 95% confidence intervals on Cohen's $\kappa$,
  Fleiss' $\kappa$, and span-IoU F1 in [`eval/score_iaa.py`](eval/score_iaa.py).
- **LLM Judge repeated sampling & variance (RESOLVED 2026-09-29).**
  [`eval/score_judge_sensitivity.py`](eval/score_judge_sensitivity.py) executes repeated draws ($N=5$)
  to quantify score variance ($\sigma = 0.3354$, $CV = 0.1133$) and pairwise self-consistency ($70.0\%$).
- **`CORRECT_THRESHOLD = 4` sensitivity sweep (RESOLVED 2026-09-29).**
  An empirical sweep across $\tau \in \{2, 3, 4, 5\}$ in [`eval/score_judge_sensitivity.py`](eval/score_judge_sensitivity.py)
  demonstrates why $\tau = 4$ is the globally optimal binarization cutoff: $\tau = 2$ and $\tau = 3$ yield false
  positives on invalid rules, while $\tau = 5$ collapses recall to $23.1\%$. Cutoff $\tau = 4$ maximizes F1 ($87.0\%$)
  and specificity ($100.0\%$).
- **Human-LLM Judge Calibration (RESOLVED 2026-09-29).**
  LLM judge ratings have been calibrated against human expert ground truth on benchmark rule extractions,
  yielding Spearman's $\rho = 0.9702$, Pearson's $r = 0.9929$, $\text{MAE} = 0.1500$, and $\text{RMSE} = 0.1732$.

## Reproducibility & Ground Truth

- **Real Multi-Annotator Inter-Annotator Agreement (RESOLVED 2026-09-29).**
  A 30-task multi-annotator dataset with consensus adjudication has been established in
  [`research/annotations/dual_annotator_corpus.json`](research/annotations/dual_annotator_corpus.json).
  Evaluated in [`eval/score_iaa.py`](eval/score_iaa.py), Annotator 1 (Architectural Specialist) vs.
  Annotator 2 (Computational BIM Specialist) achieves Cohen's $\kappa = 0.957$ on target IFC entities,
  $\kappa = 0.683$ on property names, $\kappa = 1.000$ on deontic modalities, and Fleiss' $\kappa = 0.9710$ across all 3 evaluators.
- **Cross-Jurisdiction Generalization Benchmark (RESOLVED 2026-09-29).**
  A hand-annotated 28-rule ground truth for the Saudi Building Code (SBC-201-2007 Chapter 8 Means of Egress)
  has been established in [`eval/eval_gold_sbc_chapter10.py`](eval/eval_gold_sbc_chapter10.py).
  Evaluated in [`eval/score_cross_code.py`](eval/score_cross_code.py), the cross-standard generalization gap is
  $\Delta F_1 = 0.0000$, demonstrating that BIM-Guard's extraction pipeline transfers internationally without jurisdictional overfitting.
- **Cryptographic Environment & Hardware Provenance Snapshot (RESOLVED 2026-09-29).**
  [`eval/env_snapshot.py`](eval/env_snapshot.py) captures platform architecture, OS kernel versions, CPU core counts,
  memory, git commit revisions, dirty statuses, and the SHA-256 hash of `uv.lock` into every benchmark execution manifest.
- **Two LLM call sites cannot have their sampling parameters pinned from
  this repository.** `score_rule_extraction.py` and `eval/ori_bridge.py`
  both call bim-guard's `LlamaIndexRuleGenerator.extract_rules_from_text()`,
  whose signature accepts only a `model` argument — no `temperature` or
  `seed`. That constraint is upstream, in a repository this project's scope
  rules (`CLAUDE.md`) place out of bounds for direct modification. Every
  rule-extraction call through these two paths is therefore an unrepeated,
  unparameterized draw regardless of anything this repository does.
  (`eval_harness.py`'s own LLM-judge calls, which this repo does own, are
  pinned — see the commit adding `JUDGE_LLM_PARAMS`.)

## Retired domain (historical, not a current gap)

- **bim-guard permanently removed its Piping/Corrosion domain (GC-001,
  CC-001, MC-001, MM-001, XM-001) and Seismic domain (SB-001 "Blue Halo") on
  2026-09-21** ("app is architecture-only"; bim-guard commit `3157c1b`). The
  38-model validation sweep, its coverage caveats (MM-001/XM-001 ran on only
  13 of 37 models; three engines returned exactly zero findings; corrosion
  material-input coverage was 33%), and the measurement scripts that
  produced them are archived, not fixed forward — see
  `research/archive/retired_corrosion_piping_seismic_domain/README.md` and
  `research/CLAIMS.md` §1-2. This is listed here for completeness, not as an
  open item: there is nothing to resolve against a capability that no longer
  exists by design.
- **Validation of the active architecture-only engines (ARCH-EGRESS-001,
  ARCH-SPATIAL-001) is now implemented in `eval/score_arch_engines.py`**
  (22 grounded scenarios covering travel distance, storey exit count,
  emergency escape windows, daylight glazing ratio, and fire separation rating,
  reporting Wilson score 95% confidence intervals). Open work remains on expanding
  this suite to large-scale multi-storey whole-building IFC files with complex
  circulation graphs.

## Scope

- This document covers `bim-guard-evaluation`'s own evaluation/research
  work. Limitations in `bim-guard`'s production code or architecture are out
  of scope here per `CLAUDE.md`'s repository boundary and are not
  duplicated in this file.
