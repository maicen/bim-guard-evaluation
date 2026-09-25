# Knowledge-graph code-ingestion pipeline

Standardized, repeatable process for turning a new building/construction
code PDF into a knowledge graph linked to the bSDD ontology, and folding
it into the combined multi-code graph. Follow this exactly the same way
for every new code so results stay comparable across codes.

Every step writes its own artifact to disk before the next step reads it,
so the pipeline can be resumed or re-run from any stage without redoing
earlier (and, for the LLM step, costly) work.

## Status — SBC-201-2007 ingestion (in progress, 2026-09-25)

Picking this back up on another machine: this is the first code being
run through the pipeline since `kg.merge_graphs` was added, appending
onto the existing OBC graph.

- **Done: Step 1.** `sources/SBC-201-2007_docling.dclg` (372 pages,
  2.4MB, verified: single well-formed `<doclang>` root, content spanning
  front matter through the back index) is committed. Took ~44 minutes
  end to end on the (CPU-only, restarted-clean) docling-serve instance —
  most of that is real per-chunk processing time, not overhead. Getting
  here involved several real bugs and one operational incident (client
  didn't trust the OrbStack cert; the websocket status-watcher hung;
  the client's `job_timeout` fired on jobs still legitimately running
  and a 0-page result was wrongly treated as success; and a backlog of
  duplicate queued jobs from repeated debugging attempts, since
  `/v1/convert/file/async` doesn't cancel on client disconnect) — all
  fixed in `scripts/pdf_to_dclg.py` and explained inline there and in
  the "On timeouts" note under Step 1 below. Not follow-ups.
- **Next: Step 2** (`kg.build_kg`) — not yet run.
- **Not yet run: Steps 3–4** (`kg.correct_graph`, `kg.merge_graphs`) —
  Step 3 spends real OpenRouter money; always run its dry run first and
  confirm the call count/model before adding `--yes`.
- **Already done and merged:** `kg/merge_graphs.py` itself (unit-tested
  standalone: collision-safe clause namespacing, shared bSDD-node union,
  duplicate-`doc_id` rejection — not yet exercised against a real second
  graph).
- **Target merge command once Steps 2–3 produce
  `research/kg/sbc_201/sbc_201_corrected_filtered.json`:**
  ```bash
  uv run python -m kg.merge_graphs \
      --base research/kg/obc_app_a_corrected_filtered.json --base-doc-id obc_app_a \
      --add sbc_201=research/kg/sbc_201/sbc_201_corrected_filtered.json \
      --out research/kg/combined/combined
  ```

## Pipeline overview

```
sources/<CODE>.pdf
      │  scripts/pdf_to_dclg.py
      ▼
sources/<CODE>_docling.dclg
      │  kg.build_kg
      ▼
research/kg/<code_id>/<code_id>.graphml + .json
      │  kg.correct_graph  (dry run, then --yes --drop-rejected)
      ▼
research/kg/<code_id>/<code_id>_corrected.{graphml,json}
research/kg/<code_id>/<code_id>_corrected_filtered.{graphml,json}   <- use this one downstream
research/kg/<code_id>/<code_id>_corrected_correction_report.json
      │  kg.merge_graphs
      ▼
research/kg/combined/combined.graphml + .json
```

`research/kg/` is gitignored (large, regeneratable exports) — the PDFs and
`.dclg`/`.dclx` DocLang files under `sources/` are the tracked, durable
inputs. Re-running any step from its input artifact reproduces the rest.

Pick a short, stable `<code_id>` per code (e.g. `obc_app_a`, `sbc_201`) —
it becomes both the output directory name and the `doc_id` namespace used
to keep that code's clause nodes distinct in the combined graph. Reuse
the exact same `<code_id>` on every re-run of a given code; `merge_graphs`
refuses to add a `doc_id` that's already present in the base graph, so
re-ingesting a code means re-running the merge from a base that doesn't
already contain it (or dropping it from the base first).

## Step 1 — PDF → DocLang (`.dclg`)

```bash
uv run python scripts/pdf_to_dclg.py --input sources/<CODE>.pdf
```

Sends the PDF to a local `docling-serve` instance (default:
`https://docling-serve.bim-guard.orb.local/`, OrbStack's local Docker DNS)
and saves the result as plain DocLang markup next to the input, as
`sources/<CODE>_docling.dclg`. Pass `--output` to override the path, or
`--ocr` for a scanned (non text-native) PDF.

`*.orb.local` serves a self-signed cert that macOS/curl trust via the
system keychain but Python's `certifi` bundle doesn't — the script
handles this itself (`_trust_orb_local_cert`) by fetching that host's cert
chain over TLS and trusting it for the duration of the run; verification
stays on, nothing is done with `verify=False`. No action needed unless
you point `--url` at a non-`.orb.local` host with its own cert problem.

**Large PDFs are chunked automatically**, using docling-serve's own
`page_range` option (see `ConvertDocumentsOptions` in `<url>/openapi.json`)
rather than splitting the PDF client-side: the whole file is uploaded once
per chunk, and the server slices out just that page range. The script
sends `--chunk-pages`-sized ranges (default 40) one request at a time.
Each chunk's `.dclg` is cached to `<output>.chunks/` the moment it's
produced, and each chunk gets its own retry-with-backoff
(`MAX_ATTEMPTS_PER_CHUNK`, default 3) before the run gives up — so a
flaky connection costs you a retry, not the whole document. If a run
does give up, **just re-run the same command**: every already-cached
chunk is skipped, so it only retries what's missing. Once every chunk
succeeds they're stitched into one `.dclg` with a single `<doclang>`
root (identical in content to one unbounded request), and the chunk
cache is deleted — pass `--keep-chunk-cache` to keep it anyway, and note
it's kept automatically whenever a run fails partway. `--chunk-pages 0`
disables chunking for a PDF small enough to convert in one request.

**On timeouts — read this before changing `--document-timeout` /
`--job-timeout`.** `/v1/convert/file/async` is fire-and-forget
server-side: once a chunk is submitted, giving up on it client-side
(the process being killed, or the client's own wait timing out) does
**not** cancel the job on docling-serve — it keeps running, and a retry
or a second run just queues a duplicate conversion behind it. On a
CPU-only, small-worker-pool instance, a duplicate queued behind another
duplicate is how a ~5 minute chunk turns into a 40+ minute one (this
happened during development — see the Status section above). So:
`--document-timeout` (server-enforced per chunk, default 1800s) and
`--job-timeout` (client-side wait per chunk, default 3600s, deliberately
above `--document-timeout`) are both generous on purpose. Lowering them
to "fail faster" makes a congested run *worse*, not better — if a chunk
is genuinely stuck, let it hit `--document-timeout` server-side rather
than tightening `--job-timeout` to abandon it early.

**Verify before moving on:** open the `.dclg` file and confirm it has real
content and a page count > 0 (`grep -c '<heading' sources/<CODE>_docling.dclg`
is a quick sanity check). A 0-page/near-empty output means the conversion
failed silently server-side — check the printed status before proceeding.

## Step 2 — Build the per-code graph

```bash
uv run python -m kg.build_kg \
    --source sources/<CODE>_docling.dclg \
    --out research/kg/<code_id>/<code_id>
```

Parses the DocLang into `Clause` units (`kg/clause_builder.py`), scores
each clause against the bSDD ontology (`kg/similarity.py`), and exports
`research/kg/<code_id>/<code_id>.graphml` + `.json`
(`kg/graph_builder.py`). `--dictionaries all` scores against the full bSDD
reference set instead of the architecture-domain default; `--top-k` /
`--min-score` tune how many candidate matches survive per clause.

## Step 3 — LLM correction + filter pass

```bash
# 1. dry run first -- always. Prints call count/model, makes no calls, costs nothing.
uv run python -m kg.correct_graph --source research/kg/<code_id>/<code_id>.json

# 2. for real, once the call count/cost look reasonable
uv run python -m kg.correct_graph \
    --source research/kg/<code_id>/<code_id>.json \
    --out research/kg/<code_id>/<code_id>_corrected \
    --drop-rejected \
    --yes
```

This calls an LLM via OpenRouter (`OPENROUTER_API_KEY`, from
`bim-guard/.env`) for every clause with borderline-confidence candidate
matches — **this spends real money**, so always run the dry run first and
get an explicit go-ahead before adding `--yes`. `--drop-rejected` also
writes `<out>_filtered.{graphml,json}` with LLM-rejected edges removed;
**that filtered graph is the one that feeds the merge step**, matching how
the existing OBC graph (`research/kg/obc_app_a_corrected_filtered.json`)
was produced.

## Step 4 — Merge into the combined graph

```bash
# first time: bootstrap the combined graph from the existing OBC graph
uv run python -m kg.merge_graphs \
    --base research/kg/obc_app_a_corrected_filtered.json --base-doc-id obc_app_a \
    --add <code_id>=research/kg/<code_id>/<code_id>_corrected_filtered.json \
    --out research/kg/combined/combined

# every subsequent code: append onto the combined graph that already exists
uv run python -m kg.merge_graphs \
    --base research/kg/combined/combined.json \
    --add <code_id>=research/kg/<code_id>/<code_id>_corrected_filtered.json \
    --out research/kg/combined/combined
```

`kg/merge_graphs.py` namespaces every `clause::` node as
`<doc_id>::clause::<ref>` so two codes' clause numbering can never
collide, while leaving `bsdd::` ontology nodes un-namespaced so they union
across codes by shared bSDD URI — that union is the actual point of a
combined graph: it shows which bSDD class/property multiple codes both
reference. `--base-doc-id` is only needed the first time you fold in a
graph that predates this script (i.e. one with no `doc_id` node
attribute yet, like the original `obc_app_a*` exports); every graph
`merge_graphs.py` itself has written already carries `doc_id`, so later
merges never need it.

## Step 5 — Downstream artifacts (optional, per graph)

Run on either a single code's graph or the combined graph:

```bash
uv run python -m kg.export_grounding --source <graph>.json --out <base>
uv run python -m kg.prioritize_review_queue --source <graph>.json --out <base>_review_queue
```

## Onboarding a new code — checklist

1. Drop the PDF at `sources/<CODE>.pdf`.
2. Pick a `<code_id>` (short, stable, unique across codes already merged).
3. Step 1: `scripts/pdf_to_dclg.py` → verify the `.dclg` output.
4. Step 2: `kg.build_kg` → inspect node/edge counts in the printed summary.
5. Step 3: `kg.correct_graph` dry run → confirm call count/model with
   whoever owns the OpenRouter budget → re-run with `--yes --drop-rejected`.
6. Step 4: `kg.merge_graphs --base <existing combined>.json --add <code_id>=...`.
7. Commit the new `sources/<CODE>.pdf` and `sources/<CODE>_docling.dclg`
   (tracked; `research/kg/` output is gitignored and regeneratable from
   these two committed inputs plus the bSDD ontology).
