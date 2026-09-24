# Archive — Retired Corrosion / Piping / Seismic Domain

**Status: historical record only. None of this reflects bim-guard's current
capabilities or product direction.**

On **2026-09-21**, bim-guard deliberately and permanently removed its entire
Piping/Corrosion domain (the GC-001 galvanic, CC-001 crevice, MC-001
microbial, MM-001 material-media, and XM-001 cross-material engines) and its
Seismic domain (the SB-001 "Blue Halo" nonstructural bracing-clearance
kernel), along with the piping IFC parsing both depended on — see bim-guard
commit
[`3157c1b`](https://github.com/maicen/bim-guard/commit/3157c1be56544106ed161fad90d6031ad2f5dd94)
("Remove piping and seismic analysis domains; app is architecture-only") and
the accompanying series of cleanup commits the same week. bim-guard is now
**architecture-only**: ARCH-EGRESS-001, ARCH-SPATIAL-001, a domain-agnostic
graph engine, and the Digital Inspector.

Every file in this directory was produced by, or documents, the retired
domain. All of it predates the 2026-09-21 pivot. It is archived here — not
deleted, since it is real, dated, completed empirical work — but it must not
be read as describing what bim-guard does today, and it must not be cited in
the thesis or elsewhere as an active or reproducible capability without this
context attached.

## What's here

| Path | What it is |
|---|---|
| `appendix_b/run_20260918/` | The 38-model IFC validation sweep: `validation_sweep_summary.json` (223,516 clashes, 37/38 models processed), the 7 derived thesis tables, the 4 Appendix B figures, and `PROVENANCE.md`. Restored from git history in this repository's Phase 0 triage (2026-09-24), before the scale of the domain retirement was understood — see the git log for that restoration's commit message. |
| `appendix_b_validation.md` | Prose write-up of the sweep above (B.0-B.1.1: run provenance, material-coverage detail). |
| `baseline-main-corrosion.md` | Corrosion-engine (`GC,CC,MC,MM,XM`) API baseline against a single test IFC. |
| `BIMGUARD AI Validation Dataset — Verified Downloadable IFC Models.md` | The 38-IFC-model catalogue the sweep downloaded from (buildingSMART, HuggingFace, RWTH-E3D, Zenodo, TIB DuraArk, Generalitat Valenciana). |
| `Seismic Bracing Clearance Volumes for MEP Systems in BIM.md`, `Seismic_Bracing_Clearance_Volumes_MEP_BIM_Research.md`, `seismic_bracing_clearance_volumes_mep_bim.md` | Research behind the Blue Halo seismic-bracing clearance model (EN 1998-1 / DIN 4149). |
| `gc001-mil-std-889b-validation.md` | GC-001 galvanic engine validation against MIL-STD-889B dissimilar-metal tables. |
| `hermes_comparison_matrix.md` | Cross-standard comparison behind the combined seismic jurisdiction config. |
| `analysis_run.txt` | Console transcript of an `analyse_validation_results.py` run. |
| `data/hermes_standards_research_summary.json` | Standards research backing the seismic config. |
| `data/{GC,CC,MC}-001_validation_demo_asset_register.csv` | Demo asset registers for the three corrosion engines. |
| `logs/*.log`, `logs/*.txt` | Raw console output from `test_all_38_models.py` and `analyse_validation_results.py` runs, and a `validate_blue_halo.py` run against a "REAL_CONFIG". |
| `benchmarks/` | `performance_benchmark.py`'s halo-generation timing study: 7 figures, raw per-repeat CSVs, and the rendered summary/analysis markdown. |

## What was removed from `eval/` (not archived — dead code, not data)

The measurement scripts that produced the artifacts above called bim-guard
modules that no longer exist and can never run again against current
bim-guard. Unlike the research data above, this is not a historical record
worth preserving in place — it is deleted from `eval/`, mirroring bim-guard's
own choice to delete rather than archive the equivalent production code
(nothing is lost: git history has it at any prior commit):

- `eval/test_all_38_models.py` — the 38-model sweep harness (`app.modules.blue_halo`, corrosion engines).
- `eval/validate_blue_halo.py` — Blue Halo synthetic-scenario validation.
- `eval/performance_benchmark.py` — halo-generation performance benchmark (`app.modules.ifc_reader.piping_schema`).
- `eval/test_real_ifc_pipeline.py` — real-IFC Blue Halo end-to-end pipeline test.
- `eval/test_e2e_roundtrip.py` — end-to-end roundtrip through the now-removed `/api/analyze/seismic` endpoint (current bim-guard exposes `/api/analyze/arch` instead; no replacement e2e harness has been written yet — see `LIMITATIONS.md`).

## What this means for the thesis

The 223,516-clash / 38-model validation was real, dated (2026-09-18), and
executed against bim-guard as it existed at that time. It is **not** evidence
of bim-guard's current capability, because that capability was intentionally
removed three days after the sweep ran. `research/CLAIMS.md` reflects this:
the claim is marked `retired-domain`, not `archived-artifact`, and the
repository's active, currently-verifiable claims (NLP annotation accuracy,
rule-extraction accuracy against the Part 9.8 gold set) are the ones that
should anchor the thesis's present-tense validation narrative. Per the
decision recorded when this archive was created, the thesis's empirical
claims should reflect what current analysis actually supports, not be forced
to retroactively justify a since-retired product direction.
