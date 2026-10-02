# Section 9.9 — with_skill run

**Task count:** 85 tasks extracted from Section 9.9 (Means of Egress), 81 with at least one pre-annotation suggestion.

## What happened
Followed the skill's Steps 1–3 exactly:
1. Grepped `sources/OBC_2023.Volume_1_P_9.dclg` for `Section 9.9.` / `Section 9.10.` and confirmed both matches at lines 11668 and 14446 are real `<heading level="2">` body headings (not TOC rows).
2. Ran `extract_section.py --start "Section 9.9." --end "Section 9.10."` → 85 clause/table records.
3. Ran `build_ls_tasks.py` on that output → 85 Label Studio tasks, 81 with `predictions` (4 clauses had no extractable spans).

## Example records
- `section_ref: "9.9.1.1.(1)"` (Application): "Stairways, handrails and guards in a means of egress shall conform to the requirements in Section 9.8. as well as to the requirements in this Section." — pre-annotated with MANDATORY on "shall", CROSS_REF on "Section 9.8", and an IfcDoor choice.
- `section_ref: "9.9.11.5.(1)"` (Floor Numbering): a multi-sub-item clause with dimensions like "60 mm", "1 500 mm", "300 mm" — a good one for the human annotator to spot-check since dimension/EXCEPTION extraction is regex-based and not fully reliable.

No deviations from the skill otherwise. Per the explicit scope limit, Label Studio/docker/browser tools were not touched.

**Import step (Step 4), for real:** start/confirm the Label Studio project using `research/label_studio/config.xml`, pick a `--start-id` offset if Section 9.8's tasks are already loaded in the same project (this run used default IDs starting at 1), split `tasks.json`'s 85 tasks into ~30-task chunks, and POST each chunk to `/api/projects/<PROJECT_ID>/import` via an authenticated browser session using the page's own CSRF cookie (not an extracted API token) — then verify `task_count`/`prediction_count` per chunk and spot-check one imported task in the UI before handing the project URL to the annotator.
