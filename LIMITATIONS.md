# Limitations

This document states, plainly and with numbers, the methodological gaps in
this repository's evaluation and validation work as of 2026-09-24. It exists
because every one of these will be found by a careful reader — stating them
here first converts each from a discovered flaw into demonstrated
methodological awareness. See [`research/CLAIMS.md`](research/CLAIMS.md) for
the corresponding claim-by-claim evidence ledger.

## Statistical rigor

- **No confidence intervals, bootstrap estimates, or significance tests
  appear anywhere in this repository.** Every accuracy figure — NLP
  annotation score, rule-extraction recall, LLM-judge precision/recall/F1,
  inter-annotator kappa (where computed at all) — is reported as a single
  point estimate. At the sample sizes involved here (29 gold rules, ~5–8
  LLM-judge golden cases, 37 processed IFC models), point estimates alone
  substantially overstate precision: a proportion like 24/29 read without an
  interval implies far tighter certainty than the underlying n supports.
- **`eval_harness.py`'s LLM judge produces a single, unrepeated draw per
  case.** No repeated sampling, no variance measurement, no confidence
  interval on any correctness/completeness/executability score or on the
  derived precision/recall/F1.
- **`CORRECT_THRESHOLD = 4`** (`eval_harness.py`) binarizes the judge's 1–5
  scale into "correct"/"incorrect" with no stated justification and no
  sensitivity check against neighboring thresholds (2, 3, 5). Whether the
  reported precision/recall would look materially different at threshold 3
  or 5 is currently unknown.
- **The LLM judge has never been calibrated against human ratings.** Its
  scores are treated as ground truth for the confusion-matrix analysis with
  no measurement of judge leniency/severity bias, no agreement statistic
  against a human rater, and no confirmation that its 1–5 scale means the
  same thing a human reviewer would mean by it.

## Reproducibility

- **No inter-annotator agreement (IAA) has been computed on real data.**
  `eval/score_iaa.py` implements Cohen's κ, Fleiss' κ, and span-IoU F1
  correctly (and these are unit-tested), but every gold-standard annotation
  set in this repository — including the 29-rule Part 9.8 stairs gold set
  (`eval/eval_gold_code_9_8_stairs.py`) — was produced by a **single
  annotator**, with no independent second annotation and no adjudication
  protocol. The only Label Studio export committed
  (`research/label_studio/sample_tasks.json`) is 2 synthetic tasks with
  `completed_by: 1`, which is not an agreement pair. If a genuine second
  annotator becomes available, running `score_iaa.py` against a real
  overlap is the single highest-value addition this repository's evaluation
  suite could receive next; until then, no agreement figure is reported or
  implied anywhere.
- **The 38-model IFC validation sweep is not currently re-runnable
  end-to-end.** The source IFC files are no longer cached on disk and were
  never SHA-256 checksummed at acquisition time, so `research/CLAIMS.md`
  marks that result `archived-artifact`, not `reproduced`. A hash-pinned
  dataset manifest is planned to close this gap.
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
- **No environment snapshot accompanies most results.** Python version, OS,
  and installed-package versions were not recorded for the 2026-09-18
  38-model sweep (its `PROVENANCE.md` states this explicitly). Later runs
  through `eval/eval_config.py`'s `build_result()` capture only two git
  commit SHAs, not a full environment fingerprint.

## Corpus and engine coverage

- **MM-001 and XM-001 (material-media and cross-material corrosion engines)
  ran successfully on 13 of 37 processed models (35%), not 37.** The
  remaining 24 report `unavailable`. See `research/CLAIMS.md` §1 for the
  full breakdown.
- **Corrosion-engine material input coverage is 33%** — only 38,012 of
  116,006 piping elements in the 38-model sweep carry explicit material
  data; CC-001/MC-001 scores for the remainder rest on the engines' default
  material assumption.
- **GC-001, MM-001, and XM-001 report exactly zero findings across the
  entire 38-model sweep.** This has not been independently confirmed as a
  true absence of the relevant risk condition versus a non-firing engine
  (e.g. via a synthetic known-positive smoke test). Flagged, not yet
  resolved — see `research/CLAIMS.md` §1.

## Scope

- This document covers `bim-guard-evaluation`'s own evaluation/research
  work. Limitations in `bim-guard`'s production code or architecture are out
  of scope here per `CLAUDE.md`'s repository boundary and are not
  duplicated in this file.
