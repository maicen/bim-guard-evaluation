# SBC-201-2007 — Chapter 8 "Means of Egress" — Label Studio task extraction

## Result: extraction succeeded, but only after bypassing a broken step in the existing pipeline

`tasks.json` in this directory contains **733 pre-annotated Label Studio tasks**
covering all of Chapter 8 (Sections 8.1 Administration through the end of
8.25, i.e. everything between the `CHAPTER 8 MEANS OF EGRESS` heading and the
`CHAPTER 9 ACCESSIBILITY` heading in `sources/SBC-201-2007_docling.dclg`). It
is directly importable into a Label Studio project using
`research/label_studio/config.xml` as-is (same `linguistic_labels` /
`ifc_entity` / `unit` `from_name` keys the interface expects).

## Section boundaries used

Found by searching the rendered `sources/SBC-201-2007.md` and confirming the
matching headings in the raw `.dclg`:
- Start: `<heading level="2">CHAPTER 8 MEANS OF EGRESS</heading>`
- End (exclusive): `<heading level="2">CHAPTER 9 ACCESSIBILITY</heading>`
- Covers Sections 8.1–8.25 (Administration, Definitions, General Means of
  Egress, Occupant Load, Egress Width, Illumination, Accessible Means of
  Egress, Doors/Gates/Turnstiles, Stairways and Handrails, Ramps, Exit Signs,
  Guards, Exit Access, Exit/Exit Access Doorways, Travel Distance,
  Corridors, Exits, Number of Exits, Vertical Exit Enclosures, Exit
  Passageways, Horizontal Exits, Exterior Exit Ramps/Stairways, Exit
  Discharge, plus two more trailing sections).

## The problem I ran into, and why I didn't just run the existing bridge

`eval/label_studio_bridge.py` already ships a `doclang-to-tasks` CLI mode
(`LabelStudioBridge.doclang_to_label_studio_tasks`), which is clearly the
intended way to do this. It delegates node extraction to
`nlp_annotation/doclang_annotator.py::DocLangAnnotator.parse_nodes()`.

**`parse_nodes()` only has branches for `<heading>`, `<text>`/`<paragraph>`/`<p>`,
and `<table>` tags.** It has no branch for `<list>`. In this document (and,
from spot-checking, in the rest of SBC-201-2007 generally), Docling encodes
essentially every numbered regulatory clause — the actual "shall / shall not
/ not less than X mm" requirements — as an OTSL-style structure:

```xml
<list class="ordered">
  <ldiv><marker>8.1.1</marker></ldiv>
  <location value="61"/><location value="88"/><location value="454"/>
  <location value="120"/>
  General. Buildings or portions thereof shall be provided with a means
  of egress system as required by this chapter. ...
  <ldiv><marker>8.1.2</marker></ldiv>
  ...
</list>
```

The clause text isn't a child's `.text` — it's the XML `.tail` of the last
`<location/>` sibling before the next `<ldiv>`. Since `parse_nodes()` never
visits `<list>` at all, it drops **577 of 578** numbered clauses in Chapter 8
(I counted `<marker>` tags directly in the raw XML to confirm). Running
`doclang-to-tasks` on this file as documented would silently produce a task
set containing only:
- 84 headings (not annotatable text)
- 146 `<text>` nodes — almost entirely the Section 8.2 glossary/definitions
  block (e.g. "ACCESSIBLE MEANS OF EGRESS. A continuous and unobstructed
  way..."), which happens to use plain `<text>` elements instead of `<list>`
- 10 tables

i.e. all of the actual deontic/dimensional requirements for means of egress
(door widths, stair riser/tread dimensions, travel distances, occupant
loads, exception clauses, etc.) would be missing from the annotation batch.
I confirmed this isn't specific to how I was slicing the file — it's a gap
in `parse_nodes()` itself, and nothing else in `nlp_annotation/` or `eval/`
has any code that understands `<list>`/`<ldiv>`/`<marker>`.

## What I did instead

Rather than stop at "the extractor is broken," I wrote a standalone script
(`extract_egress.py`, scratch-only, not added to the repo, run via
`uv run python`) that:

1. Parses the full `.dclg` with the same `defusedxml` loader the repo uses.
2. Walks `root.iter()` like `parse_nodes()` does, but adds a proper branch
   for `<list>`: it pairs each `<ldiv><marker>...</marker></ldiv>` with the
   clause text reconstructed from the `.tail` of the following `<location/>`
   siblings, up to the next `<ldiv>`.
3. Tracks section context from headings, handling both the chapter's
   `CHAPTER 8 ...` / `SECTION 8.x ...` numbered headings and the (unnumbered)
   `Exceptions:` sub-headings that appear inline inside sections — bare
   markers like `1.`, `2.`, `a.`, `b.` under an `Exceptions:` block get
   composed into refs like `8.3.2-exception.1` rather than being left as
   bare, ambiguous `"1"` strings or incorrectly resetting the section
   context.
4. Reuses `DocLangAnnotator.annotate_text()` **unchanged** for the actual
   NLP pre-annotation (deontic extractor, dimension extractor, condition
   parser, cross-ref resolver, IFC entity mapping) — that part of the
   pipeline works fine; only the node-extraction step needed a workaround.
5. Emits tasks in the exact same JSON shape as
   `doclang_to_label_studio_tasks` (`data.text`, `data.section_ref`,
   `data.meta.{tag,section_number,section_name,section_path}`,
   `predictions[0].result[...]` with `labels`/`choices` items keyed to
   `linguistic_labels` / `ifc_entity` / `unit`, matching
   `research/label_studio/config.xml`), so it drops into Label Studio import
   with no config changes.

## Output stats

- 733 tasks total: 577 numbered clauses (`list_item`), 146 glossary/plain
  text nodes, 10 tables (e.g. `TABLE 8.14.1 SPACES WITH ONE MEANS OF EGRESS`).
- 696 / 733 tasks (95%) received at least one pre-annotation span or choice.
- Label/choice yield across the batch: MANDATORY 740, ifc_entity 594,
  CROSS_REF 274, DIM_EXACT 294, unit 259, PROHIBITED 176, APPLICABILITY 80,
  EXCEPTION 71, DIM_MIN 85, DIM_MAX 62, PERMITTED 118, DIM_RANGE 3,
  RECOMMENDED 2.
- 12 of 733 tasks (~1.6%) have a slightly degraded `section_ref` (prefixed
  `ch8.*` / `ch8-exception.*` instead of a precise clause number) — these
  are lettered/numbered sub-items that immediately follow a `TABLE` heading
  (e.g. table footnotes `a.`/`b.`/`c.`) rather than a numbered section
  heading, so the section-context tracker had nothing numeric to anchor to.
  Clause text itself is unaffected; only the `section_ref` label is
  approximate for this small subset.

## What's NOT done (per scope)

No Label Studio instance was started, no docker, no network calls to
`localhost:8080`. `tasks.json` is a static file ready for import via
Label Studio's "Import" button or API, but that last step was intentionally
not performed here.

## Recommendation

The underlying gap is in `nlp_annotation/doclang_annotator.py::DocLangAnnotator.parse_nodes()`
— it should grow a `<list>` branch (the logic in `extract_egress.py`'s
`iter_list_clauses()`/`build_section_ref()` is a working reference) so that
`eval/label_studio_bridge.py --mode doclang-to-tasks` produces correct output
for this document family generally, not just for this one chapter extracted
by hand here.
