# M10 Plenary Feedback Checklist

Action items distilled from the panel review transcripts [`M10_Plenary2G5.txt`](M10_Plenary2G5.txt) (submission 2) and [`M10_Plenary3G5.txt`](M10_Plenary3G5.txt) (submission 3). Each item is tagged with its source line(s), which repo owns the fix per `CLAUDE.md`'s scope split, and current status.

**Repos:** `eval` = this repo (`bim-guard-evaluation`) · `app` = `bim-guard` (production FastAPI/frontend, out of scope here) · `both` = needs coordination across both.

---

## Reviewer-raised gaps

- [x] **Rule-extraction precision / confusion matrix with false positives and negatives** — `eval`
  Reviewer: *"the central extraction precisions... you still need to put some effort on it"*, *"confusion matrix you have in place and false positive negative is not in place"* (Plenary3 L57, L67).
  **Done:** [`score_rule_extraction.py`](../eval/score_rule_extraction.py) now reports TP/FP/FN + precision/recall/F1 instead of recall only.

- [x] **LLM-as-a-judge table** — `eval`
  Reviewer: *"you still need to put some effort on it"* re. extraction precision / LLM-as-judge (Plenary3 L57).
  **Done:** [`eval_harness.py`](../eval/eval_harness.py) now reduces judge scores to a binary TP/FP/FN/TN table, including hallucination detection on "needs_review" cases.

- [ ] **Corrosion validation relies on a small synthetic dataset — needs a stronger/more solid test set** — `eval`
  Reviewer: *"the corro[sion] validations... relies on a small, uh, synthetic data set"*, *"need a more stronger assumption validation here"*, *"more test, the different... IFC exposure"*, *"more solid... test in here"* (Plenary3 L61-L62, L65-L66).

- [ ] **Traceable BCF examples for corrosion/compliance findings** — `eval` (evidence) / `app` (BCF generation, if missing)
  Reviewer: *"include the traceable, uh, BCF examples"* (Plenary3 L69-L70).

- [ ] **Corrosion program assumption evidence / expert review** — `eval` (research writeup) / possibly external SME
  Reviewer: *"obtain the corrosion expert review... it's still not in here"*, *"validate course [corrosion] program assumption evidence"* (Plenary3 L68-L69).

- [ ] **Main AI components not clearly demonstrated in documentation** — `both`
  Reviewer: *"the main AI components do not demonstrate properly in here, and I cannot see it from documentation"* (Plenary3 L60).

- [ ] **Integrate missing engines into the evaluated/demonstrated set** — `app` (engine implementation) / `eval` (coverage in benchmarks)
  Reviewer: *"integrate the missing engines"* (Plenary3 L68). Cross-check against the known MM-001/XM-001/MC-001 coverage gaps noted in `research/BIMGUARD AI — Dual Repository Pre-Submission Audit.md`.

- [ ] **More complete "production evidence" for final submission** — `both`
  Reviewer: *"make it more complete production, uh, evidence in here for your submission for the final submission"* (Plenary3 L70).

- [ ] **Real extraction-accuracy evidence (earlier submission-2 ask)** — `eval`
  Reviewer: *"very limited... the evidence of your... real extraction, the accuracy"* (Plenary2 L52-L53). Superseded/subsumed by the precision/confusion-matrix work above, but confirm it's now presentable as evidence, not just internal script output.

- [ ] **IFC validation performance evidence** — `eval`
  Reviewer: *"the IFC validation performance"* (Plenary2 L53).

- [ ] **Share test IFC/BCF cases with reviewers for their own testing** — `eval` (provide sample files) / `both`
  Reviewer: *"if you hadn't submit to me my test IMC [IFC] or be [BCF], for example... more petitions or we call, uh, example"* (Plenary2 L54-L56).

- [ ] **Architecture diagrams and API reference** — `app`
  Reviewer: *"the architecture of the dot architecture diagrams and the API reference. That may be good for your next submission"* (Plenary2 L56).

---

## Presenter-acknowledged gaps (self-identified, still worth tracking)

- [ ] **Rule extraction confusion matrix as part of the research deliverable** — `eval`
  Presenter: *"a confusion matrix highlighting the accuracy that will be part of the research, but we haven't covered that yet"* (Plenary3 L46-L47). Overlaps with the reviewer ask above — now partially covered by the two harness changes; confirm it's written up in `research/` as a citable table, not just script output.

- [ ] **"Run analysis" module (architecture ↔ code comparison)** — `app`
  Presenter: still under development end-to-end (Plenary2 L21-L31).

- [ ] **Rule extraction module (LLM path)** — `app`
  Presenter: *"still under development"*, LLM extraction workflow has "a bug here right now" (Plenary2 L36-L40; Plenary3 L26).

- [ ] **Comparator module** — `app`
  Presenter: *"the comparison module under development"* (Plenary2 L30-L31).

- [ ] **Report/export section (analysis summary, document management)** — `app`
  Presenter: PDF/Excel export exists for structured rules; a further cross-software coordination export is still pending (Plenary2 L32-L33; Plenary3 L40-L41).

- [ ] **Unstructured-text rule extraction (natural-language codes/standards)** — `app` (extractor) / `eval` (benchmark once it exists)
  Presenter: *"one of the things under development now is working on unstructured texts"* (Plenary3 L20-L22, L36-L37).

- [ ] **Modeling manual / best-practices guidance module** — `app` / `research`
  Presenter: *"there should be some manuals and the best practices to be followed for the better results"* (Plenary3 L38-L39).

- [ ] **Rules-library UX polish** — `app`
  Presenter: *"still also under some improvement for user experience"* (Plenary3 L32-L33).

---

## Notes

- Items already checked off were completed in this repo on 2026-09-20 (`eval/score_rule_extraction.py`, `eval/eval_harness.py`).
- `app`-tagged items are explicitly out of scope for `bim-guard-evaluation` per this repo's `CLAUDE.md` — track them in the `bim-guard` repo instead; listed here only for completeness against the transcripts.
- The `research/BIMGUARD AI — Dual Repository Pre-Submission Audit.md` document independently corroborates several of these (small synthetic dataset, missing engine coverage in analytics, no committed evidence for large-scale validation claims) — worth cross-referencing when writing up the corrosion-validation and engine-integration items.
