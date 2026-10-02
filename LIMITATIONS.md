# Limitations

This document states, plainly and with numbers, the methodological gaps in
this repository's evaluation and validation work as of 2026-09-24. It exists
because every one of these will be found by a careful reader — stating them
here first converts each from a discovered flaw into demonstrated
methodological awareness. See [`research/CLAIMS.md`](research/CLAIMS.md) for
the corresponding claim-by-claim evidence ledger.

## Statistical rigor

- **Confidence intervals (done for real data only).** Wilson 95% intervals in
  [`eval/stats_util.py`](eval/stats_util.py) are applied to the architecture benchmark
  and to the e2e extraction run (`eval/results/e2e/`). Bootstrap CIs exist in `score_iaa.py`.
- **LLM-judge sweep, variance and human calibration: NOT DONE (corrected 2026-10-03).**
  An earlier version of this file called these RESOLVED. `eval/score_judge_sensitivity.py`
  scores hard-coded, simulated judge ratings, so its Spearman/Pearson figures and the claim
  that τ = 4 is optimal are not evidence. `CORRECT_THRESHOLD = 4` remains an unvalidated
  design choice until a live judge is run on the gold cases and compared to human ratings.

## Reproducibility & Ground Truth

- **Inter-annotator agreement: NOT DONE (corrected 2026-10-03).** The 30-task
  `research/annotations/dual_annotator_corpus.json` is produced by
  `research/annotations/generate_corpus.py` (hard-coded labels for both "annotators"), so the
  κ values derived from it are not measurements of human agreement. The real ground truth, the
  Label Studio set for OBC 9.8, has a single annotator and no adjudication. A two-person
  annotation of a subset is still needed.
- **Cross-jurisdiction generalization: NOT DONE (corrected 2026-10-03).**
  `eval/score_cross_code.py` simulates extraction from the gold rules themselves, so the
  reported F1 = 100% and ΔF1 = 0 carry no information. The SBC-201 gold rule set is real and
  is available for a genuine run.
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
