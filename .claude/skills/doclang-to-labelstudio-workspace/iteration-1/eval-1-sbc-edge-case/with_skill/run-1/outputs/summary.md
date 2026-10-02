# SBC-201-2007 Chapter 8 — with_skill run

## Result: extraction did NOT succeed — hit the documented limitation wall

**Section boundaries found** (Step 1, via grep): Chapter 8 "MEANS OF EGRESS" runs from line 32579 to line 41756 in `sources/SBC-201-2007_docling.dclg`, bounded by `CHAPTER 9 ACCESSIBILITY` at line 41757. It contains 24 sections (`SECTION 8.1 ADMINISTRATION` ... `SECTION 8.24 ASSEMBLY`), each with numbered clauses like `8.1.1`, `8.1.2`, plus several data tables and `Exceptions:` sub-blocks.

**Extraction attempt** (Step 2):
```
uv run python .claude/skills/doclang-to-labelstudio/scripts/extract_section.py \
  --source sources/SBC-201-2007_docling.dclg --start "CHAPTER 8" --end "CHAPTER 9" --output ...
```
Output: "Extracted 9 clause/table records" — but all 9 are `<table>` elements. Zero of the ~190+ numbered regulatory clauses were extracted.

### Root cause (verified, not assumed)
`extract_section.py`'s `HEADING_NUM = re.compile(r"^(\d+(?:\.\d+)*\.)\s*(.*)$")` requires a heading to *start* with a bare digit-dot number ending in a trailing period (OBC's `"9.8. Name"` style). SBC-201's actual headings are `CHAPTER 8 MEANS OF EGRESS`, `SECTION 8.1 ADMINISTRATION`, etc. — none start with a digit, so the regex never matches, `current_article_num` stays `None`, and every `<list>` of numbered clauses is silently skipped by the `if current_article_num is None: continue` guard. Only `<table>` elements survive.

**A second, independent mismatch**: SBC's `<marker>` elements already carry the fully-qualified number (e.g. `<marker>8.1.1</marker>`), while the script's ref-building (`f"{current_article_num}.{marker}"`) assumes OBC's bare sub-item marker convention and would produce a doubled/wrong ref (e.g. `8.1.8.1.1`) even if the heading regex were fixed.

### What's in tasks.json
The degenerate 9-table output run through `build_ls_tasks.py` — should NOT be treated as "Chapter 8 ready for annotation." It's only the chapter's data tables with generic "Table" refs; none of the actual deontic/regulatory clause text is present.

### What would be needed instead (not attempted, per the skill's guidance not to patch silently)
1. Extend `HEADING_NUM` to also recognize `CHAPTER N TITLE` / `SECTION N.N TITLE` (no leading digit, no trailing period).
2. Make ref-building detect when a `<marker>` is already a fully-qualified dotted number (SBC) vs. a bare sub-item marker (OBC), and not re-prefix in the former case.
3. Decide how `Exceptions:` headings should be treated (continuation of current section vs. new article) before loosening the regex.

**Summary**: Extraction failed for SBC-201-2007 Chapter 8 — the script's heading-number regex expects OBC's `"N.N.N. Name"` format, but SBC uses `"SECTION 8.1 TITLE"` (no leading digit, no trailing period), so it extracted only 9 incidental data tables and none of the ~190 numbered clauses. This is exactly the edge case SKILL.md's Limitations section warns about; a real fix needs two script changes (heading regex + marker-ref logic) not made here, per the skill's instruction to flag rather than silently patch.
