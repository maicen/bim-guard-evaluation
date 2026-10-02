# Draft text for the Final Project Memo — Osama's sections

Source of every number below: `eval/results/e2e/run1_browser/confusion.md` / `confusion.json`
(BIM-Guard extraction run through the live UI at bim-guard.xyz on 2026-10-02, scored by
`eval/score_extraction_vs_human.py` against the human Label Studio gold set for OBC 2023 §9.8).

Items in **[CONFIRM]** need a fact only the team can supply.

---

## 4.0 Development Process — add under "Experiments" (replaces the one-line "Confusion matrix (20 Sep)" bullet) and "Technical challenges"

**Evaluation development: from recall-only to a confusion matrix.** The first extraction scorer
reported recall against a 29-rule gold set for OBC §9.8.2–9.8.4.7. After the plenary feedback that
"false positive/negative is not in place", scoring was rebuilt in three steps. (1) On 20 Sep,
`score_rule_extraction.py` gained TP/FP/FN counts and precision, recall and F1, and a confidently
hallucinated rule was counted as a false positive rather than ignored. (2) The LLM-as-judge harness
(`eval_harness.py`) was binarised at a judge score of 4 on correctness and completeness, with
"no rule should fire" cases flipping the pairing to FP/TN. A threshold sweep over 2–5 (N=5 draws)
showed 4 is the best cutoff, and the judge agreed closely with human ratings (Spearman 0.97).
(3) On 2 Oct the gold set was replaced by a larger human-annotated one: 117 clauses and 89 rules
of OBC §9.8, annotated in Label Studio from the DocLang conversion of the code. Extraction is now
run through the real web interface with a Playwright script, so the scored drafts are exactly what
a reviewer would see, and each draft is mapped back to its clause. Two decisions came out of this.
First, matching is reported in three modes (lenient, normalized, strict), because a single mode
hid whether errors were in the clause, the value or only the property naming. Second, the
clause-level matrix has a true-negative cell (clauses where no checkable rule exists), which the
rule-level matrix cannot, since the number of possible wrong rules is open-ended.

**Supabase-MCP integration.** The Supabase MCP server was registered on 2 May, when rules moved to
Supabase. **[CONFIRM — wording inferred from the memo]** It was used to inspect tables and run SQL against the hosted project while the
schema was designed (documents, `rule_extraction_drafts`, `rules`) and to check row-level security.
One column, `original_proposed_rule`, was added later so the model's pre-edit output is kept next
to the reviewer's correction; this is what lets the evaluation repository compute a correction rate
from the public draft endpoint alone. **[CONFIRM: any other uses, e.g. advisors, logs, generating
types — Shane/Osama.]** The integration also caused the schema-history drift described under
technical challenges: migrations applied through MCP were recorded with apply-time versions, so
local and remote histories diverged. The rule since then is that the migration file is the version
of record, MCP SQL is read-only, and versions are compared before every push.
**[CONFIRM migration filename/date: memo says 20260908214813, `docs/rule-extraction-corrections.md`
says 20260909052852.]**

---

## 5.1 Results — Rule Extraction (Pillar A)  (~400 words)

**Provenance.** Figures are from one extraction run on 2 October 2026 through the live BIM-Guard
interface, scored against the human-annotated gold set for OBC 2023 §9.8 (117 clauses, 89 gold
rules, single annotator for this set; inter-annotator agreement was measured separately on a
30-task corpus, κ = 0.96 for target entity). The run produced 104 draft rules, 58 of them
dimensional (numeric checks, the scope of the gold set). Model: **[CONFIRM — not recorded in the
run output; the runner now pins openai/gpt-5.6-luna-pro]**. This is one draw: the extraction call
accepts no temperature or seed, so run-to-run variance is not controlled **[CONFIRM: add the second
run (48 drafts, clause F1 34%, lenient rule recall 21%) as variance, or explain it]**.

**(a) Information-extraction metrics.** Table 4 reports both levels.

*Table 4. Extraction accuracy against the human gold set, OBC §9.8.*

| Level | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| Clause (does it yield a rule?) | 37 | 0 | 13 | 67 | 100% | 74.0% | 85.1% |
| Rule, lenient (clause, operator, value) | 57 | 1 | 32 | n/a | 98.3% | 64.0% | 77.6% |
| Rule, normalized (+ IFC target/property synonyms) | 42 | 16 | 47 | n/a | 72.4% | 47.2% | 57.1% |
| Rule, strict (exact target and property) | 17 | 41 | 72 | n/a | 29.3% | 19.1% | 23.1% |

At clause level accuracy is 88.9% (95% Wilson CI 81.9–93.4) and specificity 100% (94.6–100): the
pipeline did not invent a rule for any clause that has none. The gap between lenient and strict
shows where the error is. The model usually finds the right clause, operator and number, but it
often names the IFC class or property differently from the canonical vocabulary, which is why
precision falls from 98% to 29%. This is a naming problem, not a hallucination problem, and the
reviewer-correction step is where it is caught.

**(b) Confusion matrix and failure pattern.** *[Insert Figure: the clause-level matrix above, drawn
as a heatmap, and the operator matrix below.]* Of 55 pairs agreeing on clause and value, the
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
