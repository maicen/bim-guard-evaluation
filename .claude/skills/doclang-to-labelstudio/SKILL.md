---
name: doclang-to-labelstudio
description: Loads a section of a DocLang-converted source document (the .dclg/.dclx files under sources/) into this repo's Label Studio project (research/label_studio/, config.xml) as pre-annotated human-annotation tasks. Use this whenever the user asks to start, continue, or set up human annotation of a building-code section or dataset for this project — phrases like "load Section 9.X into Label Studio", "I want to annotate [some part of the code] myself", "set up annotation tasks for Part 9", "get human annotations for the confusion matrix", or "digest this document and the template and load it for annotation". Also use it when the user wants to extend an in-progress annotation batch to a new section or a new source document (OBC, SBC, or similar DocLang-converted codes). Don't use this for exporting finished annotations or scoring agreement — that's eval/label_studio_bridge.py and eval/score_iaa.py, which this skill's output feeds into afterward.
---

# DocLang → Label Studio annotation tasks

## What this does and why

`eval/label_studio_bridge.py`'s `doclang_to_label_studio_tasks` only extracts
`<text>`/`<paragraph>`/`<table>` elements from a DocLang file. In the OBC and
SBC source documents under `sources/`, almost none of the actual code text
lives in those tags — it lives inside `<list class="ordered"><ldiv><marker>
(N)</marker></ldiv>...text...</list>` blocks (DocLang's structure for
numbered code sentences, with lettered `(a)/(b)/(c)` sub-items as markerless
`<ldiv/>` continuations). Running the bridge directly on one of these
documents silently returns almost nothing usable.

This skill's two scripts (`scripts/extract_section.py`,
`scripts/build_ls_tasks.py`) replace that step: they pull one section's real
clause text out of the raw XML, sentence by sentence, and pre-annotate each
one using the project's own `nlp_annotation` regex extractors — matching
exactly the labeling schema in `research/label_studio/config.xml` (deontic
spans, conditions, dimensions, cross-refs, IFC entity/property/unit). The
bridge (`label_studio_bridge.py --mode gold` / `--mode nlp`) is still what you
run *afterward*, once a human has reviewed the annotations, to turn them into
gold rules or NLP schema.

## Prerequisites — check before starting

1. **Label Studio is running**: `docker compose -f research/label_studio/docker-compose.yml ps` should show `bim_guard_label_studio` up. If not: `cd research/label_studio && docker compose up -d`, then wait for `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080` to stop returning `000`.
2. **A project exists** with the labeling config from `research/label_studio/config.xml`. If this is the first run, create one (UI: New Project → Labeling Setup → Custom template → paste `config.xml`'s contents). Note its project ID from the URL (`/projects/<id>/data`).
3. **A logged-in browser session** against that Label Studio instance (via the built-in Browser tools), with a user account — create one through the signup flow if needed (this is a local dev instance; see the "Testing the user's own application" exception for entering test credentials into `localhost`). Save any credentials you generate to a file under `research/label_studio/data/` (gitignored) rather than only in chat.

## Step 1 — find the section boundaries in the source

Don't guess the heading text — grep the actual file first, since every source
document formats headings differently (OBC uses `Section 9.8. Name`; others
may use `SECTION 2.4` with no trailing period, or a different convention
entirely):

```bash
grep -n "Section 9\.8\.\|Section 9\.9\." sources/OBC_2023.Volume_1_P_9.dclg
```

Find the **real body heading** (inside a `<heading level="2">` element, not a
table-of-contents `<index>` row — check a few lines of context around each
match) for both the section you want and the section right after it. You need
exact prefixes for `--start` and `--end`.

## Step 2 — extract the clause text

```bash
uv run python .claude/skills/doclang-to-labelstudio/scripts/extract_section.py \
  --source sources/OBC_2023.Volume_1_P_9.dclg \
  --start "Section 9.8." \
  --end "Section 9.9." \
  --output /tmp/section_tasks_raw.json
```

Omit `--end` to extract through the end of the document. If this prints
"extracted 0 clauses" with matched boundaries, the document's headings don't
follow the `N.N.N. Name` numbering pattern this script tracks (see
**Limitations** below) — inspect the raw XML near the target text rather than
assuming the script is broken.

Sanity-check the count and a couple of entries before moving on:

```bash
python3 -c "
import json
d = json.load(open('/tmp/section_tasks_raw.json'))
print(len(d), 'records')
print(d[0]['data'])
"
```

## Step 3 — pre-annotate

```bash
uv run python .claude/skills/doclang-to-labelstudio/scripts/build_ls_tasks.py \
  --input /tmp/section_tasks_raw.json \
  --output /tmp/section_tasks_annotated.json
```

This calls the repo's own `nlp_annotation.doclang_annotator.DocLangAnnotator`
on each clause and builds Label Studio `predictions` in the exact shape
`research/label_studio/config.xml` expects (`from_name: linguistic_labels` /
`ifc_entity` / `unit`). Predictions are suggestions, not ground truth — tell
the user explicitly that `EXCEPTION` spans in particular tend to run too long
(often swallowing the rest of the sentence) and need trimming by hand; don't
try to fix the regex itself mid-task unless asked.

If the project already has tasks imported and you're adding more, pass
`--start-id <max existing id + 1>` so task IDs don't collide.

## Step 4 — import into Label Studio

Chunk into batches of ~30 tasks (large single payloads are harder to debug if
something fails partway) and POST each batch through the authenticated
browser session rather than extracting an API token into your own context —
use the page's own session cookie and CSRF token:

```javascript
function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}
const csrf = getCookie('csrftoken');
const tasks = [ /* one chunk's worth, pasted in */ ];
const res = await fetch('/api/projects/<PROJECT_ID>/import', {
  method: 'POST',
  credentials: 'same-origin',
  headers: {'X-CSRFToken': csrf, 'Content-Type': 'application/json'},
  body: JSON.stringify(tasks)
});
const body = await res.text();
({status: res.status, body: body.slice(0, 300)});
```

Run this via the browser's JS-execution tool, navigated to the Label Studio
origin so the cookie is in scope. Read each chunk's JSON with the file-reading
tool and inline it into the script — don't try to `fetch()` a local file path,
the page can't see your filesystem.

After each chunk, check the response: `task_count` should match the chunk
size, and `prediction_count` should be close to it (a few tasks legitimately
have no extractable spans, e.g. "Reserved" placeholder clauses).

## Step 5 — verify and hand off

1. Reload `/projects/<id>/data` and confirm the total task count.
2. Open one freshly-imported task and visually confirm the clause text and at
   least one pre-annotation span render correctly.
3. Tell the user where to start (the project URL, how to filter/sort by
   `section_ref`) rather than just saying "done" — they're the one annotating,
   so point them at the actual next click.

## Limitations

- **Heading format must be `N.N.N. Name`** (number first, trailing period;
  a lettered article such as `9.8.4.5A.` is fine) for
  `extract_section.py` to track which article a `<list>` belongs to. OBC
  follows this; not every source does (e.g. `SECTION 2.4` / `BUSINESS GROUP B`
  as separate headings, no trailing period) — those won't extract cleanly with
  this script as-is. If you hit this, say so plainly rather than forcing a fix
  silently; extending the heading regex is a reasonable small change if the
  user wants that document supported.
- **Table extraction is coarse** — `<table>` elements become one flattened-text
  task each, not per-cell. Fine for a human to read and label as a block, not
  structured data.
- **Pre-annotation is a regex extractor**, not an LLM — it's fast and
  deterministic but systematically over-extends `EXCEPTION` spans and will
  miss anything phrased unusually. It's a head start, not a result to trust.
