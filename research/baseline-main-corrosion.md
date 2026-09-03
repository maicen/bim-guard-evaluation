# Corrosion baseline: `main` @ `8455fa2`

Reference numbers for `data/test_hospital_mep_scenario.ifc` (IFC4, 13,076 bytes,
sha256 `cb6fefbf2b87a407f5a69270b3f9461c3c2b890a9843205c25c81fc4c42c75f7`),
captured over HTTP against a live server, both with and without a seeded
database.

Endpoint `POST /api/analyze/corrosion`, `engines=GC,CC,MC,MM,XM`.

## Results

| | Unseeded | **Seeded** |
| --- | ---: | ---: |
| Audit issues | 12 | **12** |
| Scored | 8 | **8** |
| Data-quality | 4 | **4** |
| Critical | 0 | **2** |
| High | 4 | **2** |
| Medium | 4 | **4** |
| Low (scored) | 0 | **0** |

| Engine | Unseeded | Seeded |
| --- | --- | --- |
| GC-001 galvanic | **0** | **0** |
| CC-001 crevice | 4 medium @ 0.38 | 4 medium @ 0.37 |
| MC-001 MIC | 4 high | **2 high @ 0.719 + 2 critical @ 0.756** |
| MM-001 material-media | 4 data-quality | 4 data-quality |
| XM-001 cross-material | 0 | 0 |

No `compliance_error` in either run; `compliance_is_demo` false. Runs are
deterministic issue-for-issue, allocated ids included.

## GC-001 emits nothing, and that is correct

Every element in this model lacks a `material_b`, so anode and cathode are the
same material and the galvanic gap is 0.0V — no couple to assess. Since
`c2fa9fc` ("skip galvanic scoring for same-material couples"), GC-001 declines
to score these rather than issuing a verdict. Running GC-001 alone returns zero
issues and zero data-quality issues in both modes: it runs cleanly and has
nothing to report.

This replaces the previous baseline at `7a09324`, which recorded **4 GC-001
Medium verdicts @ 0.38**. Those were false positives — the engine had measured
a 0.0V gap and still issued a banded verdict with citations and mitigations,
built from the environment class and a default area ratio alone. They are gone
in both seeded and unseeded modes.

| | Old (`7a09324`, unseeded) | New (`8455fa2`, unseeded) |
| --- | ---: | ---: |
| Audit issues | 16 | **12** |
| Scored | 12 | **8** |
| GC-001 | 4 medium | **0** |

## Seeded vs unseeded still differ, in MC-001

With the migration's rule packs loaded, MC-001 escalates two elements from High
to **Critical**. The offline fallback's `material_susceptibility` carries four
entries (`carbon_steel`, `ss316`, `unknown`, `default`) against the seeded
catalog's full table, which flattens all four elements to one High band.
**Unseeded runs understate MIC severity.** CC-001 shifts only 0.38 -> 0.37.

GC-001 now agrees across both modes, so galvanic risk is no longer a
seeded/unseeded discrepancy.

## MM-001 and XM-001

Unchanged by this baseline's commits, and both are honest non-results:

- **MM-001** returns 4 data-quality issues, all `check=environment_unclassified`.
  The model carries no spatial names, so `classify_environment` cannot infer a
  class, and MM-001 refuses to score an unclassified environment rather than
  treating it as benign.
- **XM-001** returns nothing at all — no findings and no data-quality issues,
  so every element was assessable. The only crossing pair is Copper_C12200
  against Copper_C12200, which is not a dissimilar-metal couple.

## Reproducing

```bash
# Seeded — loads the migration's rule packs through the shipped write path
BIMGUARD_E2E_MODELS='{"1": "data/test_hospital_mep_scenario.ifc"}' \
  uv run python scripts/e2e_server.py --port 8010 --seed-db

# Unseeded — engines fall back to built-in catalogs
BIMGUARD_E2E_MODELS='{"1": "data/test_hospital_mep_scenario.ifc"}' \
  uv run python scripts/e2e_server.py --port 8014

curl -X POST http://127.0.0.1:8010/api/analyze/corrosion \
  -F project_id=1 -F engines=GC -F engines=CC -F engines=MC \
  -F engines=MM -F engines=XM
```

`POST /api/analyze/upload` cannot be used here: it stores through Supabase
Storage and returns HTTP 500 without credentials. `scripts/e2e_server.py`
patches only `analysis_runner.model_bytes`; everything downstream is shipped
code.

Seeding confirmed from the server log — GC-001 50 rules, CC-001 42, MC-001 54,
MM-001 117, XM-001 18, with no `Using hardcoded fallback ruleset` warnings. The
unseeded run logs those warnings for GC/CC/MC and seeds only MM and XM from
`data/rulesets/`.

## Scope

Seeded runs prove the rule packs parse, seed and evaluate, and that the engines
read catalogs from the database rather than from constants. They do not prove
the Supabase network path, its RLS policies, or that a deployed database holds
these rows.
