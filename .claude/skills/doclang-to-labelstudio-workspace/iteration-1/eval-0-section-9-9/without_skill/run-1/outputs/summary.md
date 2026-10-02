# Section 9.9 (Means of Egress) — Label Studio pre-annotated tasks

## Approach

Followed the same pipeline used for Section 9.8, implemented by the
`doclang-to-labelstudio` skill's two scripts:

1. **Located section boundaries** in the raw DocLang source
   (`sources/OBC_2023.Volume_1_P_9.dclg`) by grepping for the literal heading
   text rather than guessing numbering conventions:
   - Start: `<heading level="2">Section 9.9.  Means of Egress</heading>` (line 11668)
   - End: `<heading level="2">Section 9.10.  Fire Protection</heading>` (line 14446)

2. **Extracted clause text** with
   `.claude/skills/doclang-to-labelstudio/scripts/extract_section.py`
   (`--start "Section 9.9." --end "Section 9.10."`), which walks the
   `<list class="ordered"><ldiv><marker>(N)</marker></ldiv>...</list>` /
   markerless-`<ldiv>` sub-item structure DocLang uses for numbered code
   sentences, tracking `N.N.N. Name`-style headings to build each
   `section_ref` (e.g. `9.9.1.1.(1)`) and `article_name`. This produced
   **85 clause/table records**.

3. **Pre-annotated** each clause with
   `.claude/skills/doclang-to-labelstudio/scripts/build_ls_tasks.py`, which
   runs the repo's own `nlp_annotation.doclang_annotator.DocLangAnnotator`
   regex extractor over each clause and emits Label Studio `predictions` in
   the exact shape `research/label_studio/config.xml` expects:
   `linguistic_labels` (deontic spans like `MANDATORY`/`PROHIBITED`,
   conditions, dimensions, cross-refs), `ifc_entity`, and `unit` choices.

   Result: **85 tasks, 81 with at least one pre-annotation suggestion**
   (4 tasks — mostly table-row fragments and a `Reserved.` placeholder
   clause — had no extractable spans; this matches the expected behaviour
   documented for the 9.8 run).

This run intentionally stopped at producing the tasks JSON — per the task's
scope limit, no live Label Studio instance was started and nothing was
imported over the network.

## Output

`tasks.json` in this directory — 85 Label Studio task objects, each with
`data.text`, `data.section_ref`, `data.meta.article_name`, and a
`predictions` array (model_version `bim-guard-nlp-v1`) ready for
`POST /api/projects/<id>/import`.

## Example records

- `section_ref: "9.9.1.1.(1)"` (Application) —
  "Stairways, handrails and guards in a means of egress shall conform to
  the requirements in Section 9.8. as well as to the requirements in this
  Section." — predictions: `MANDATORY` on "shall", `CROSS_REF` on
  "Section 9.8".
- `section_ref: "9.9.1.3.(1)"` (Occupant Load) —
  "The occupant load of a floor area or part of a floor area, or of a
  building or part of a building not having a floor area, shall be based
  on, (a) two persons per sleeping room ... (b) ... Table 3.1.17.1."
- `section_ref: "9.9.11.5.(1)"` (Floor Numbering) —
  "Arabic numerals indicating the assigned floor number shall be, (a)
  except in hotels, mounted permanently on the stair side of the wall at
  the latch side of doors to exit stair shafts, ..."

## Issues / caveats

- 4 of 85 extracted clauses are table-row fragments or a `Reserved.`
  placeholder and have no predictions — this is expected; a human still
  needs to review/label these manually (or discard them if they're not
  meaningful clauses).
- As with 9.8, `EXCEPTION` and other condition spans from the regex
  extractor are a head start, not ground truth — they tend to over-extend
  and should be trimmed by hand during annotation.
- Section 9.9 cross-references forward into Section 9.10 ("Fire
  Protection") in at least one clause (`9.9.1.2.(1)`); those `CROSS_REF`
  spans are correctly captured as text spans but obviously aren't
  resolvable within this section's own task set.
