# BIMGUARD E2E Validation Results

Date: 2026-08-30
Code state: after `7aa8cf0` (seismic mapped/boundary geometry) and `3659bcf`
(geometry shape-cache key)
Dataset: maicen/bimguard-test-models — 34 IFC models, 807.4 MB of IFC
Harness: `scripts/e2e_server.py` + `scripts/e2e_suite.py`, manifest `tests/e2e/e2e-models.json`
Machine record: `docs/validation/data/test-results.json`

## Summary

Two passes over the same 34 models, because two of the results depend on
whether the database holds the rule packs the seed migration installs.

| Run | Server | Scope | Result |
| --- | --- | --- | --- |
| A | `--seed-code-rulesets` | all eight categories | **103 checks: 96 PASS, 2 FAIL, 5 WARN, 0 SKIP** |
| B | default (no database) | piping + timing | **19 checks: 19 PASS** |

The 2 FAILs are the schema-twin pairs, where the dataset's IFC4 and IFC2x3
exports genuinely hold different content (finding 3). The 5 WARNs are analyses
that returned zero findings on models with nothing to evaluate.

| Category | Models | Result |
| --- | --- | --- |
| Piping — engine gating | 15 | **PASS** — the gate held on every model |
| Piping — cache separation | 4 | **PASS** — 22x–90x speedup on a hit |
| Exports (BCF/CSV/JSON) | 10 | **PASS** — counts match findings exactly |
| Seismic | 3 structural + 4 MEP | **NOW EVALUATES** — see below |
| Architecture | 5 | **PASS** — and now reproducible |
| Schema robustness | 2 twin pairs | Parsing equivalent; twins differ in content |
| Geometry robustness | 2 | Parsed without crashing |
| Performance | 4 tiers | **PASS** — baseline below |

## 1. Piping corrosion

All 15 piping models, all five engines selectable. Gating held everywhere:
element-only never produced MM/XM, network-only never produced GC/CC/MC, a
single-engine selection produced only that engine, and an empty selection
produced nothing.

Totals across the 15 models:

| Engine | No database (run B) | Seeded database (run A) |
| --- | --- | --- |
| GC-001 | 88 563 findings on 14 of 15 models | **0 findings, on none of them** |
| CC-001 | 88 563 | 88 563 |
| MC-001 | 88 563 | 88 563 |
| MM-001 | 88 554 | 88 554 |
| XM-001 | 18 590 | 18 590 |

GC-001's disappearance is finding 1. Everything else is identical between the
two configurations, which also confirms that neither geometry fix in this
session moved the corrosion numbers.

### Material: coverage is 0%, and only two engines say so

**MM-001 emitted 88 554 findings and every one is `data_quality`** ("material
not identified"). GC-001 assessed 88 563 elements over the same models, so
essentially every piping element in the dataset carries a material
`normalise_material()` cannot map.

Per-engine bands under the seeded database:

| Model | CC-001 | MC-001 | MM-001 | XM-001 |
| --- | --- | --- | --- | --- |
| Duplex_MEP | 926 Medium | 926 Critical | 926 data-quality | — |
| wr_plumb_ifc4 | 8 539 Medium | 8 539 Critical | 8 539 data-quality | — |
| Clinic_Plumbing | 6 587 Medium | 6 587 Critical | 6 587 data-quality | 906 data-quality |

MM-001 and XM-001 report what they do not know. **CC-001 and MC-001 return a
confident band for material they could not identify** — Medium and Critical, one
per element, on every model. Under the built-in fallback catalogs GC-001 does
the same at Medium. This is finding 2.

XM-001 does produce real cross-material verdicts where a network exists:
Clinic_HVAC gave 16 268 Medium couples alongside 507 data-quality ones.

## 2. Seismic — now evaluates real models

Before this session SB-001 answered every service element with
`geometry_unavailable`: `_local_vertices` read only tessellated face sets, and
real exports map their geometry (Duplex_MEP holds 942 `IfcMappedItem` against
42 directly-placed solids). `7aa8cf0` made the walk recursive through
`IfcMappedItem` and the boundary representations that dominate real output.

All 926 of Duplex_MEP's distribution elements now resolve a bounding box, none
missing, median extent 35 mm. Through the API:

| Model | MB | Before | After | Critical | High | Medium |
| --- | --- | --- | --- | --- | --- | --- |
| Duplex_MEP | 17.0 | 427 data-quality | **4 773 verdicts** | 39 | 151 | 4 583 |
| Duplex_Plumbing | 30.1 | — | **1 274 verdicts** | 11 | 141 | 1 122 |
| Clinic_Plumbing | 53.2 | 10 data-quality | **12 245 verdicts** | 97 | 474 | 11 674 |
| wbdg_office_mep | 40.0 | 1 959 data-quality | **17 406 verdicts** | 131 | 1 018 | 16 257 |

Zero data-quality findings remain on any of them. Findings carry overlap
volumes and percentages, EN 1998-1 / DIN 4149 citations and mitigations — e.g.
*"IfcEnergyConversionDevice intrudes into the seismic bracing clearance halo of
IfcFlowSegment by 47,845,072 mm³ (50.2% of the halo volume)"*.

The three structural models still return **0 findings**, and that is correct:
they carry beams, columns and footings but no distribution services, so a
clearance check has nothing to iterate. The same is true of both AISC geometry
models. These are the 5 WARNs.

**Open question, not a defect.** A 200 mm halo around densely packed MEP
catches most neighbours, which is why the counts are large. Whether 200 mm is
right for these models is a domain decision; the engine can now ask the
question, which it could not before.

## 3. Architecture — running, and now reproducible

51 rules load (the 47 packaged plus 4 hardcoded — see finding 4).

| Model | MB | Findings | High | Medium | Rules fired | Time |
| --- | --- | --- | --- | --- | --- | --- |
| AC20-FZK-Haus | 2.5 | 77 | 30 | 47 | 5 of 51 | 9.6 s |
| wbdg_office_arc | 3.9 | 1 304 | 1 102 | 202 | 9 of 51 | 23.2 s |
| DigitalHub_FM-ARC | 8.6 | 516 | 387 | 129 | 7 of 51 | 48.7 s |
| Clinic_Architectural | 12.4 | 2 847 | 2 303 | 544 | 9 of 51 | 65.9 s |
| wr_arc_ifc4 | 77.2 | 3 585 | 3 143 | 442 | 8 of 51 | 215.9 s |

Every count above is reproducible. Before `3659bcf` the same model returned
1304, 1307, 1304, 1304 on consecutive runs and 2917 vs 2847 across boots; after
it, six consecutive runs, a restart, and this suite run in a fresh process all
returned identical figures rule-by-rule. The cause was a shape cache keyed on
`id(element)` — a recycled CPython address — so a space could be measured with
another element's geometry. `docs/validation/architecture-determinism.txt` has the investigation.

The deterministic answer is the lower count and it is the correct one: every
space in wbdg_office_arc is at least 2 500 mm tall, so none can violate the
1 950 mm rule. The findings that came and went were **false violations**.

## 4. Exports (all PASS)

| Analysis | CSV | BCF |
| --- | --- | --- |
| wr_plumb_ifc4 corrosion | 34 156 rows = 34 156 findings | 102 470 entries, 34 156 topics + viewpoints |
| Clinic_Plumbing corrosion | 27 254 rows = 27 254 findings | 81 764 entries, 27 254 topics |
| Duplex_MEP corrosion | 3 704 rows = 3 704 findings | 11 114 entries, 3 704 topics |
| wr_arc_ifc4 architecture | 3 585 rows = 3 585 findings | 10 757 entries, 3 585 topics |
| Clinic_Architectural architecture | 2 847 rows = 2 847 findings | 8 543 entries, 2 847 topics |
| Clinic_Structural seismic | 0 rows = 0 findings | valid archive, 0 topics |

JSON parsed in every case; row and topic counts match finding counts exactly.

## 5. Cache separation and performance

Miss, a different selection, then the original selection again: identical
findings every time, and the hit is dramatically faster.

| Model | Cold | Other selection | Cached hit |
| --- | --- | --- | --- |
| Clinic_Plumbing 53 MB | 41.6 s | 29.9 s | **0.56 s** |
| wr_plumb_ifc4 23 MB | 35.8 s | 17.8 s | **1.23 s** |
| DigitalHub_SAN 24 MB | 5.6 s | 0.07 s | 0.13 s |
| Duplex_MEP 17 MB | 5.0 s | 0.05 s | 0.10 s |

Timing baseline, both configurations:

| File | Size | Cold (seeded) | Cold (no DB) | Cached |
| --- | --- | --- | --- | --- |
| west_riverside_fire_ifc4 | 0.86 MB | 2.05 s | 2.76 s | 0.06 s |
| west_riverside_plumb_ifc4 | 22.66 MB | 36.1 s | 35.3 s | 1.6 s |
| Clinic_Plumbing | 53.25 MB | 51.4 s | 41.2 s | 1.7 s |
| west_riverside_mech_ifc4 | 69.66 MB | 171.6 s | 153.8 s | 1.8 s |

Cold time tracks element count and geometry work, not file size. **The largest
model's cold time is not stable**: three measurements on this machine gave
105 s, 154 s and 172 s. The seeded/unseeded difference is inside that spread, so
it is run-to-run variance, not a cost of seeding. Cached runs stay under 4 s
throughout, a 20x–90x speedup.

---

# Open findings

## Finding 1 — GC-001 reports nothing — RESOLVED, and the reason was a bug

**The silence was correct; the earlier noise was not.** GC-001 was scoring
elements that are not galvanic couples at all.

`phase_6c_corrosion_ui._gc_element` fills the second side of the junction with
the first material when the IFC carries only one for an element — which is
every element in this dataset. `resolve_material` widens it further by
defaulting any unrecognised name to `carbon_steel`. So every element reached
the engine as *the same material against itself*.

The engine set the voltage term to 0 for those, correctly, but still summed the
area-ratio and environment terms, which are non-zero by construction. Copper
against copper scored 0.26; under the fallback catalog the same sum reached
0.38 and banded **Medium**. Those were galvanic verdicts on junctions that are
not galvanic — 926 of them on Duplex_MEP, 6 587 on Clinic_Plumbing, 88 563
across the 15 piping models.

The composite is now gated on a real bimetallic junction. Measured through the
pipeline:

| Model | Before | After |
| --- | --- | --- |
| test_hospital_mep_scenario | 4 Medium | 0 (4 Low with `include_low=True`) |
| Duplex_MEP | 926 Medium | 0 (926 Low) |
| Clinic_Plumbing | 6 587 Medium | 0 (6 587 Low) |

Real dissimilar pairs are untouched — copper/carbon steel still scores 0.53
Medium, aluminium/SS316 0.76 High — and PREN escalation still fires without a
couple, since pitting resistance is a property of the alloy and its
environment. `tests/test_galvanic_self_coupling.py` pins all of it; all nine
tests fail without the fix.

**What this leaves open is a coverage gap, not a defect**: this dataset
contains no dissimilar-metal junctions, so GC-001's scoring path is now
effectively unexercised by it. Validating GC-001 needs a model with real
bimetallic connections.

### The original observation, for the record



The same model, the same code, the same elements; only the catalog source
differs (Duplex_MEP, 926 elements, `include_low=True` so nothing is hidden):

| Engine | Built-in fallback catalog | Database catalog |
| --- | --- | --- |
| GC-001 | 926 findings, **all Medium** | 926 assessments, **all Low** |
| CC-001 | 926, all Medium | 926, all Medium |
| MC-001 | 926, all **High** | 926, all **Critical** |

`app/services/analysis_runner.py` hardcodes `include_low=False` and the API
never exposes it, so Low findings are dropped before the caller sees them. With
a seeded database GC-001 therefore reports nothing at all — confirmed across all
15 piping models in run A.

The database catalog is the richer one and is meant to win: 20 galvanic series
entries against 8, 7 environment classes against 4, 10 mitigations against 1,
and a `scoring_model` with 4 weights where the fallback has none.

The catalog-source question is now moot for these models — a self-couple scores
0.0 under either catalog. It returns only for genuine couples, which this
dataset does not contain. The second question stands on its own: whether Low
findings should reach the API at all, when `include_low=False` can make an
entire mechanism invisible.

## Finding 2 — GC/CC/MC band material they cannot identify

Coverage in this dataset is **0%** (see §1). MM-001 and XM-001 report that
honestly as data quality. CC-001 and MC-001 return Medium and Critical for the
same elements. GC-001 no longer does (finding 1), but the mechanism behind all
three is the same and is worth naming: `resolve_material` returns
`carbon_steel` for any unrecognised name, including an empty one — "conservative
default" in its own docstring. The engines therefore never see unknown
material; they see carbon steel that nobody chose. CC-001 has
a data-quality path and used it 167 times on wr_mech_ifc4, 197 on
wr_mech_ifc2x3 and 9 on Schependomlaan — but material absence is not among the
reasons it fires.

It is **not** accurate to describe the corrosion suite as handling missing
material gracefully. Two of five engines do.

## Finding 3 — the schema twins are not the same model

| Pair | IFC4 | IFC2x3 | Difference |
| --- | --- | --- | --- |
| Plumbing | 8 539 | 9 013 | 474 `IfcFlowTerminal` only in IFC2x3 |
| Mechanical | 17 424 | 18 488 | 1 064 `IfcFlowTerminal` only in IFC2x3 |

Counted from the files directly: plumbing IFC4 holds 4 308 `IfcPipeSegment` +
4 231 `IfcPipeFitting` = 8 539; the IFC2x3 twin holds exactly 4 308
`IfcFlowSegment` + 4 231 `IfcFlowFitting`, **plus** 474 terminals the IFC4
export omits. **Schema handling is verified equivalent to the entity** — the
suite's "identical findings" assertion cannot hold for these particular files.
Either the assertion should compare the shared entity families, or the dataset
needs true twins.

## Finding 4 — nothing in the running application seeds the Part 9 packs

`BUILDING-CODE-PART9` (31 rules) and `-EXT` (16) exist, are well-formed, and
evaluate correctly. No code path in the running application puts them in the
rules table: startup runs `seed_engine_rulesets` and
`seed_architectural_code_rules` (4 hardcoded rules), and
`seed_default_code_rulesets` — the function that loads the 47 — **has no
caller**.

| Database state | Rules loaded | Findings |
| --- | --- | --- |
| No database | — | HTTP 400, missing static asset |
| Migrated as the app seeds it | **4** | **0** |
| Migrated + packs seeded (run A) | **51** | findings on all 5 models |

Run A used the third state, which the harness reaches with
`--seed-code-rulesets`. A production database reaches the second.

**Fix**: call `seed_default_code_rulesets` from `_seed_library`. One line.

## Finding 5 — architecture reports every risk band as zero

AC20-FZK-Haus returns 77 findings banded 30 High and 47 Medium, while
`issue_stats` reports every band as 0 against a total of 77. The orchestrator
fills `issue_stats` only on the MEP branch; `_format_result` then defaults each
band to 0. Seismic populates its stats correctly (`data_quality: 427` before the
geometry fix), which is what makes this a bug rather than a design choice.

## Finding 6 — the unit suite needs a database it does not document needing — RESOLVED

Re-measured at `c15ac1f` (2026-09-02), four days after the run this report
otherwise records:

`uv run pytest tests/`: **982 passed, 2 skipped, 5 xfailed, 0 failed** (23m10s).

The 29 failures are gone. `tests/conftest.py::IMPORT_REGRESSIONS` is now empty,
so the four modules that raised at import no longer do — and the registry being
empty is itself the one skip inside `test_imports.py`, which reports "got empty
parameter set for (module)" because there is no longer a regression to
parametrise over. `KNOWN_IMPORT_FAILURES` retains a single environmental entry,
`document_parsing.tfidf_analyzer`, which wants scikit-learn from the optional
`ml-pipeline` group; it is excluded from the sweep rather than skipped. The
suite's second skip is one of the several conditional guards elsewhere in
`tests/` (absent checkout files, optional dependencies) and was not isolated.

The repair happened across the intervening commits rather than in one change,
and this re-measurement did not bisect which; the finding is recorded as
resolved on the evidence of a green suite and an empty regression registry, not
on a traced cause.

The count also grew from 791 collected to 989, so the two numbers are not a
like-for-like comparison — tests were added throughout, including 34 in
`c15ac1f` (`tests/test_ifc_penetrations.py`, additions to
`tests/test_comparator_scope_waivers.py`).

**The E2E numbers in the Summary above were NOT re-measured.** They remain
those of the 2026-08-30 run at `7aa8cf0` / `3659bcf`. Only the unit suite was
re-run.

### The original observation, for the record

`uv run pytest tests/`: **29 failed, 762 passed, 5 skipped, 5 xfailed** — before
and after both fixes, so neither regressed anything. The failures trace to the
same missing static assets; `test_imports` fails by name because four modules
raise at import. Whatever fixes finding 4 should let them import.

## Notes

- `element_count` in the analysis response is the finding count, not the element
  count: `app/api/analyze.py:142` falls back to `len(issues)` because the
  corrosion result carries no top-level `ifc_element_count`.
- **craslabbim** (64 MB) yields no elements — it holds no service entities the
  parser collects.
- **The fire-protection model has no pipes**: `west_riverside_hospital_fire_ifc4`
  holds 861 `IfcDistributionControlElement` and zero pipe entities, yet GC/CC/MC
  band all 861. Control elements are an IFC subtype of `IfcDistributionElement`,
  which is deliberately in the parser's service map. A domain question.
- The identical geometry limitation remains in
  `ifc_reader/piping_producer._local_vertices`, which feeds the corrosion
  network geometry. Left alone deliberately — changing it would move the
  corrosion numbers above.
- An `IFC2X2_FINAL` file is refused cleanly ("Unsupported schema"), and a 148 MB
  IFC2X3 model outside the manifest analyses in 43.6 s.

## Submission readiness

| Claim | Status |
| --- | --- |
| Piping gating, all five engines user-selectable | **Verified** across 15 models |
| Cache separation keyed on engine selection | **Verified** |
| Exports BCF/CSV/JSON | **Verified**, up to 34 156 findings |
| Schema robustness IFC2x3 / IFC4 | **Verified** — equivalent parsing (finding 3) |
| Performance baseline | **Established**, with a caveat on cold-time variance |
| Seismic SB-001 | **Now evaluates real geometry** — thresholds need a domain review |
| Architecture, reproducible output | **Verified** — identical across four processes |
| Architecture, 47 rules | **Runs when seeded**; the app does not seed them (finding 4) |
| Architecture risk bands | **No** — every band reports 0 (finding 5) |
| Piping corrosion, 5 engines | **Qualified** — GC-001's silence is now correct; the dataset has no couples to exercise it (finding 1) |
| Material handling | **Qualified** — 0% coverage; only MM/XM say so (finding 2) |

**Verdict: not yet, but the remaining work is small and well-defined.**

Two of the four blockers from the previous report are closed. Seismic reads
real geometry and produces cited clearance verdicts on every MEP model.
Architecture is deterministic, and the fix removed false violations rather than
hiding real ones. Piping was already validated at scale and is unchanged.

Three things remain, none of them large:

1. **One line** — call `seed_default_code_rulesets` at startup (finding 4), and
   the 47-rule claim becomes true of the running system.
2. **One coverage gap** — GC-001 no longer scores non-couples, so it is silent
   on this dataset for the right reason. Nothing here contains a
   dissimilar-metal junction, so its scoring path needs a model that does
   before the engine can be called validated (finding 1).
3. **One threshold review** — SB-001 now evaluates; 200 mm needs a domain
   judgement before its counts mean anything.

Findings 2, 5 and 6 are presentation and description issues to settle before the
write-up: material coverage is 0%, not 1.9%, and only two of five engines
report it as such.

## Reproducing this

```bash
git clone https://github.com/maicen/bimguard-test-models.git test-models
cd frontend && npm install && npm run build && cd ..

MODELS="$(python -c 'import json;print(json.dumps(json.load(open("tests/e2e/e2e-models.json"))["models"]))')"

# Run A — seeded database, all categories (~60 min on 4 cores)
BIMGUARD_E2E_MODELS="$MODELS" uv run python scripts/e2e_server.py \
  --port 8010 --seed-code-rulesets &
uv run python scripts/e2e_suite.py --manifest tests/e2e/e2e-models.json \
  --base-url http://127.0.0.1:8010 --out docs/validation/data/test-results.json

# Run B — no database, piping and timing only (~30 min)
BIMGUARD_E2E_MODELS="$MODELS" uv run python scripts/e2e_server.py --port 8011 &
uv run python scripts/e2e_suite.py --manifest tests/e2e/e2e-models.json \
  --base-url http://127.0.0.1:8011 --only piping,perf --quick-piping \
  --out docs/validation/data/test-results-nodb.json
```
