# Draft text for the Final Project Memo — Osama's sections

Source of every number below: `eval/results/e2e/run1_browser/confusion.md` / `confusion.json`
(BIM-Guard extraction run through the live UI at bim-guard.xyz on 2026-10-02, scored by
`eval/score_extraction_vs_human.py` against the human Label Studio gold set for OBC 2023 §9.8).

Items in **[CONFIRM]** need a fact only the author can supply.

---

## 4.0 Development Process — add under "Experiments" (replaces the one-line "Confusion matrix (20 Sep)" bullet)

**Evaluation development: from recall-only to a confusion matrix.** The first extraction scorer
reported recall against a 29-rule gold set for OBC §9.8.2–9.8.4.7. After the plenary feedback that
"false positive/negative is not in place", scoring was rebuilt in three steps. (1) On 20 Sep,
`score_rule_extraction.py` gained TP/FP/FN counts and precision, recall and F1, and a confidently
hallucinated rule was counted as a false positive rather than ignored. (2) The LLM-as-judge harness
(`eval_harness.py`) was binarised at a judge score of 4 on correctness and completeness, with
"no rule should fire" cases flipping the pairing to FP/TN. The cutoff of 4 is a design choice that
has not yet been validated on live judge output **[CONFIRM: run eval_harness.py before claiming a sweep]**.
(3) On 2 Oct the gold set was replaced by a larger human-annotated one: 117 clauses and 89 rules
of OBC §9.8, annotated in Label Studio from the DocLang conversion of the code. Extraction is now
run through the real web interface with a Playwright script, so the scored drafts are exactly what
a reviewer would see, and each draft is mapped back to its clause. Two decisions came out of this.
First, matching is reported in three modes (lenient, normalized, strict), because a single mode
hid whether errors were in the clause, the value or only the property naming. Second, the
clause-level matrix has a true-negative cell (clauses where no checkable rule exists), which the
rule-level matrix cannot, since the number of possible wrong rules is open-ended.

---

## 5.1 Results — Rule Extraction (Pillar A)  (~400 words)

**Provenance.** Figures are from one extraction run on 2 October 2026 through the live BIM-Guard
interface, scored against the human-annotated gold set for OBC 2023 §9.8 (117 clauses, 89 gold
rules, single annotator, no adjudication). Three runs produced 104, 48 and 53 draft rules. Models: GPT-6.1 Sol Pro for runs 1 and 2 (as reported; not recorded in the run output) and openai/gpt-5.6-luna-pro for run 3. The extraction call accepts no temperature or
seed, so run-to-run variance is not controlled; runs 1 and 2 share a model and still differ widely.

**(a) Information-extraction metrics.** Table 4 reports both levels.

*Table 4. Extraction accuracy against the human gold set, OBC §9.8, three runs.*

| Run (model) | Drafts | Clause TP / FP / FN / TN | Lenient P / R / F1 | Normalized F1 | Strict F1 |
| :---- | :---- | :---- | :---- | :---- | :---- |
| 1 (GPT-6.1 Sol Pro) | 104 | 37 / 0 / 13 / 67 | 98.3% / 64.0% / 77.6% | 57.1% | 23.1% |
| 2 (GPT-6.1 Sol Pro) | 48 | 11 / 3 / 39 / 64 | 65.5% / 21.3% / 32.2% | 20.3% | 11.9% |
| 3 (GPT-5.6 Luna Pro, after an app rebuild) | 53 | 13 / 4 / 37 / 63 | 65.2% / 16.9% / 26.8% | 8.9% | 8.9% |

Runs 1 and 2 used the same model and still differ widely (lenient F1 77.6% vs 32.2%); run 3 used a cheaper model after an application rebuild. Report the range, not run 1 alone. For run 1, clause-level accuracy is 88.9% (95% Wilson CI 81.9–93.4) and specificity 100% (94.6–100): the
pipeline did not invent a rule for any clause that has none. The gap between lenient and strict
shows where the error is. The model usually finds the right clause, operator and number, but it
often names the IFC class or property differently from the canonical vocabulary, which is why
precision falls from 98% to 29%. This is a naming problem, not a hallucination problem, and the
reviewer-correction step is where it is caught.

**(b) Confusion matrix and failure pattern.** *(Figure 3: `docs/publication/figures/fig_extraction_confusion_run1.png` — (a) clause-level TP/FN/FP/TN heatmap, (b) operator agreement. Drive copy: https://drive.google.com/file/d/1FCzFwneUO700oAL_kgwTOe-Z3XZCy_PJ/view)* Of 55 pairs agreeing on clause and value, the
operator was correct in 54: 37 ≥, 16 ≤ and 1 range were right, and one ≥ was read as =. The
32 missed rules are concentrated, not random: 11 are guard-load table rows, 8 land on an
unspecific "Other" property, 6 are landing-dimension and headroom rules, and 4 are relative
ranges ("between … of the riser"). These are table-structured and relational clauses, the
extractor's expected weak spot. There was one false positive (a handrail count read as =1 instead
of ≥1). No dimensional rule was extracted for 13 of 50 rule-bearing clauses.

**(c) Reviewer corrections.** A second, independent measure reads live reviewer edits (see
Section 3.1): 1 edited draft, 19 of 20 fields unchanged (95%). With n = 1 this validates the
pipeline, not extraction accuracy, and it cannot see unreviewed drafts or wrong drafts accepted
as they are.

**(d) Architectural audit.** On the 22-scenario benchmark the egress and spatial engines gave
TP 13, TN 9, FP 0, FN 0 (Wilson 95% CI 85.1–100%), in 0.25 s. This is a small synthetic set and
shows the engines behave on known cases, not in general.

**Reading.** The precision/recall pair answers the plenary's request: extraction is conservative
(few false positives) but incomplete (about one rule in three missed at best), so human review
remains essential and the evaluation supports the human-in-the-loop design.

---

## 6.1 Limitations — extraction and evaluation (replaces items 2 and 5; keep numbering to match the memo)

(2) **Rule extraction is validated on one code section.** The gold set covers OBC 2023 §9.8
(stairs, ramps, handrails and guards): 117 clauses and 89 rules. Results do not show how the
pipeline behaves on other parts of the OBC, on other jurisdictions, or on clauses that are not
dimensional. The gold set is also dimensional only; 46 extracted rules that state non-numeric
requirements (for example "continuously graspable" or material lists) are outside its scope and
are not scored.

(2a) **Single-annotator ground truth.** The 89-rule set was annotated by one person with no
adjudication. No inter-annotator agreement has been measured on this set, so the
property-naming disagreement that dominates our strict-match errors may partly reflect ambiguity
in the gold, not only model error.

(2b) **Three runs, large uncontrolled variance.** The extraction call accepts no temperature or
seed. Runs 1 and 2 used the same model yet gave lenient rule F1 of 77.6% and 32.2%; run 3 (a cheaper
model, after an application rebuild) gave 26.8%. Results are reported as a range, and the cause of the
run-1 outlier is unexplained.

(2c) **Scoring choices change the headline.** Lenient, normalized and strict matching give F1 of
78%, 57% and 23% on the same drafts. We report all three; lenient depends on a hand-written
synonym table and strict penalises valid naming variants. The rule-level matrix has no true
negatives, so specificity is reported only at clause level, where the "no rule" label is defined
by the annotator.

(2d) **Correction-based accuracy is not a sample.** The reviewer-correction measure rests on one
edited draft (95% field accuracy). It confirms the pipeline works, cannot see drafts nobody
reviewed or wrong drafts accepted unchanged, and says nothing about false negatives.

(2e) **Architectural benchmark is synthetic.** The 22-scenario audit benchmark (13 TP, 9 TN, no
errors) uses procedurally generated models with known answers. It shows the engines behave on
those cases; it is not a measure of accuracy on real project models.

(5) **LLM accuracy depends on the model and prompt, and review is always required.** Extraction
was conservative (no false-positive clauses) but missed about a quarter of rule-bearing clauses
and a third of rules even under lenient matching, concentrated in table-structured and relative
clauses. Human review is therefore a requirement of the design, not an optional safeguard. The
LLM-as-judge cutoff has not been validated on live judge output.

---

## 7.0 Contributions to AECO Practice and Future Research (my part, ~300 words)

**Contributions — extraction and evaluation.**

*A reproducible way to measure AI rule extraction in AECO.* Most ACCC work reports that an NLP or
LLM method "works"; few publish a false-positive/false-negative breakdown against a human
gold set. This project provides one: a clause-level confusion matrix with confidence intervals, a
rule-level matrix at three matching strictness levels, and an operator confusion matrix, all
generated by committed scripts from a run of the production interface. The results show where
the pipeline fails (table-structured and relative clauses, and property naming) rather than a
single accuracy figure, which is what a design office needs to decide where review effort goes.

*Evidence that human-in-the-loop review is justified.* High precision with incomplete recall, and
frequent naming differences from canonical IFC vocabulary, are the pattern that mandatory review
and source-clause traceability are designed to catch. The `original_proposed_rule` column stores
the model's output beside the reviewer's correction, so every future review adds measurable
evidence without a second table, and extraction accuracy can be tracked through the public API
without access to production code.

*A transferable evaluation pipeline.* Evaluation lives in a separate repository, with a
hand-annotated gold set, an LLM judge harness and a multi-model
comparison harness. Another jurisdiction's code can be loaded, annotated and scored with the same
tools, and the annotation workflow converts a DocLang document into pre-annotated tasks.

**Future research (replaces items 2 and 4 of the memo's list).**
(1) Annotate further OBC parts and other codes with two annotators and adjudication, so
generalisation is measured, not assumed. (2) Repeat extraction runs across several models with a
fixed seed where the API allows, and report variance. (3) Reduce the property-naming gap by
teaching the extractor canonical IFC names and by learning from stored draft/correction pairs
(active learning). (4) Extend the gold set and scorer to non-dimensional and relational clauses,
the main source of missed rules. (5) Replace the synthetic audit benchmark with real project
models and expert-labelled outcomes.
