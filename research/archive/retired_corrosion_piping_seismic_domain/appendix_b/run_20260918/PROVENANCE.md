# Provenance — `run_20260918`

This directory holds the artifacts of the 38-model IFC validation sweep referenced
throughout the thesis and README as the "38-model validation" / "223,516 clashes"
result. It was produced on **2026-09-18**, committed the same week, then
**accidentally deleted from the working tree** by commit
[`750ae73`](https://github.com/maicen/bim-guard-evaluation/commit/750ae73c235aee334e53ae6a2b98f8394d3e6158)
("Remove obsolete research tables and test results", 2026-09-21) during an
unrelated cleanup pass. It was restored from `750ae73^` on 2026-09-24 — see
[`research/CLAIMS.md`](../CLAIMS.md) for the full claims-to-evidence ledger and
the supersession note on the pre-submission audit that (correctly, at the time)
flagged this data as unverifiable from the repo.

## What produced this

- **Script:** `eval/test_all_38_models.py` (bim-guard-evaluation)
- **Config:** [`hermes_case_study_and_config.json`](hermes_case_study_and_config.json)
  — a jurisdiction config for EN 1998-1:2020 + DIN 4149:2022 seismic bracing
  clearance, combined per-standard with the conservative (governing) value on
  each axis; see the config's own `metadata.data_gaps` for exactly which values
  are researched vs. defaulted.
- **Host:** Windows, path prefix `D:\Zigurat Masters\bim-guard\` (visible in the
  one recorded traceback below) — **not** the machine this restoration was
  performed on (macOS). No further host detail (Python/package versions, OS
  build) was captured by the original run; this is itself one of the
  reproducibility gaps tracked in `LIMITATIONS.md`.
- **Wall time:** 3593.7 s (`totals.seconds`) for the full 38-model sweep.
- **Dataset:** the 38 IFC models catalogued in
  [`research/BIMGUARD AI Validation Dataset — Verified Downloadable IFC Models.md`](../BIMGUARD%20AI%20Validation%20Dataset%20—%20Verified%20Downloadable%20IFC%20Models.md).
  The local copies of these files no longer exist on disk and were never
  hashed at acquisition time — the dataset is **not currently re-verifiable
  byte-for-byte**. A hash-pinned manifest with a documented fetch/verify
  pipeline is planned (Phase 2 of the repository rebuild); until then, this
  artifact's own per-model `actual_size_mb` / `schema` / element-count fields
  serve as a weak "witness" fingerprint for future re-acquisition.

## Headline totals (`validation_sweep_summary.json` → `totals`)

| Metric | Value |
|---|---|
| Models attempted | 38 |
| Models processed OK | 37 |
| Models failed | 1 — row 35, `SGD_BODO_ifc.zip (ARC+PLB+VENT)`, `ifcopenshell.SchemaError: Unsupported schema: IFC2X2_FINAL` |
| MEP elements | 49,736 |
| Structural elements | 26,970 (26,808 with geometry) |
| Piping elements | 116,006 |
| Piping elements with material data | 38,012 (33%) |
| Halo volumes generated | 49,736 |
| **Clashes (total)** | **223,516** — minor 211,581 / major 6,699 / critical 5,236 |
| Engine status | GC-001 ok:37 · CC-001 ok:37 · MC-001 ok:37 · MM-001 ok:13/unavailable:24 · XM-001 ok:13/unavailable:24 |
| Engine findings | GC-001: 0 · CC-001: 116,006 · MC-001: 116,006 · MM-001: 0 · XM-001: 0 |

**Read these numbers with `research/CLAIMS.md` open next to them.** In
particular: `CC-001` and `MC-001` findings are exactly equal to
`piping_elements` (116,006) — these are per-element evaluation counts, not
per-violation counts. `GC-001`, `MM-001`, and `XM-001` returning exactly zero
findings is not itself evidence of a bug, but it is not obviously *not* one
either — see the claims ledger for the current assessment of each.

## Files in this directory

| File | Description |
|---|---|
| `validation_sweep_summary.json` | Per-model sweep output (38 records) + `totals` block above |
| `hermes_case_study_and_config.json` | The jurisdiction config the sweep ran against |
| `test-results.json` / `test-results.md` | Supporting test-run records from the same sweep |
| `material-coverage.json` | Per-model material-coverage detail behind the 33% figure above |
| `final-e2e-34models.json` | An earlier/partial (34-model) end-to-end run predating the full 38-model sweep |
| `table1_per_model.csv` … `table7b_schema_twins.csv` | The 7 thesis validation tables generated from this sweep |
| `figB1_clash_severity.png` … `figB4_schema_scatter.png` | The 4 Appendix B figures generated from this sweep |

## Verification status

Marked **`archived-artifact`** in `research/CLAIMS.md`, not `reproduced`: the
sweep is not currently re-runnable end-to-end because (a) the source IFC files
are no longer cached locally and were never checksummed, and (b) the host
environment (package versions, OS) was not captured. The JSON above is the
original, unmodified output of the 2026-09-18 run.
