# BCF 2.1 schema validation: GUID typing fixes

Date: 2026-09-02
Scope: `app/modules/reporter/bcf_generator.py`, `app/services/bcf_exporter.py`,
`app/modules/reporter/blue_halo_bcf_exporter.py`
Schemas: official buildingSMART BCF 2.1 `markup.xsd` and `visinfo.xsd`, vendored verbatim
under `tests/schemas/bcf21/` (see `NOTICE.md` there).

## What was asked versus what the code contained

The task listed six violations (`findViewpoint`, `viewpointIndex`, a text placeholder
PNG, braced component GUIDs, a `History` block, and nested comment `Reply` objects),
assuming a JSON `markup.bcf`. BCF 2.1 is XML, and none of those constructs exist in
the generator. The six *structural* XSD violations the generator once had (labels
wrapper, element order, comment GUID as child element, missing `Visibility`, sliced
synthetic GUIDs) were already fixed and are pinned by named regression tests in
`tests/test_bcf_generator.py`.

Validating the generator against the XSDs with the inputs production callers really
pass exposed a different family of violations, all in GUID typing:

| # | Attribute | Schema type | Offending input | Source |
|---|-----------|-------------|-----------------|--------|
| 1 | `Header/File/@IfcProject` | `IfcGuid` (exactly 22 chars `[0-9A-Za-z_$]`) | ISO 19650 project code (`PRJ1`, `ZIG-001`) or the literal `BIMGuard` | `BCFIssue.project_code`; `BCFExporter` header |
| 2 | `Component/@IfcGuid` | `IfcGuid` | empty string when a failure has no GlobalId | `ComplianceReporter.bcf_issues_for_results`, `ReportArtifactService` |
| 3 | `Component/@IfcGuid` | `IfcGuid` | random 36-char UUID minted as a fallback | `issues_from_results` |
| 4 | `Component/@IfcGuid` | `IfcGuid` | labels such as `COMP-001`, braced GUIDs | callers and tests |
| 5 | `Topic/@Guid` and folder name | `Guid` (hyphenated UUID) | Module 4 finding ids (`BGR-0001`), IFC GUIDs used as topic ids | `BCFExporter.build_archive`, `phase_6e_export`, `ReportArtifactService` |

Two archives already committed under `docs/bcf_exports/` (written by the services
exporter) carry exactly these violations in every one of their 15 256 and 4 533 topics.

## Fix

* `bcf_topic_guid(raw_id)`: a valid UUID passes through verbatim (braces stripped,
  case preserved because the pipeline and BCF sync compare topic GUIDs as strings);
  any other id maps to a deterministic UUID5 under a fixed namespace, so a finding
  re-exports to the same topic every time. The original id is kept in the comment
  body (`Source finding id: …`) or description (`Finding ID: …`).
* `is_ifc_guid(value)`: the 22-character IFC GlobalId test. `Component/@IfcGuid` and
  `File/@IfcProject` are only written when the value passes; otherwise the attribute
  is omitted (legal per the XSD) and the raw id stays in `AuthoringToolId`.
* Topic folder names are now always the schema-legal topic GUID, in all three writers.
* `issues_from_results` no longer invents a random UUID for a missing GlobalId.

## Evidence

Unit tests (`uv run pytest tests/test_bcf_generator.py tests/test_bcf_exporter_archive.py
tests/test_bcf_exporter.py tests/test_report_artifacts.py tests/test_phase_6e_export.py -v`):

```
108 passed in 3.75s
```

Across all seven BCF-related test files (adds `tests/test_bcf_routes.py` and
`app/modules/tests/test_iso19650_cde.py`): 121 passed, 1 failed. The failure,
`test_ids_exporter_xml_generation`, is an IDS namespace-prefix assertion that also
fails on `main` before this change and is unrelated to BCF.

End-to-end proof (every production entry point, each `markup.bcf` and `viewpoint.bcfv`
validated by both `xmlschema` and `lxml` against the vendored XSDs):

```
== reporter.bcf_generator.generate_bcf ==
  OK  clean issue                                                topics=  1
  OK  ISO 19650 metadata (project_code=ZIG-001)                  topics=  1
  OK  real IfcProject GlobalId                                   topics=  1
  OK  awkward ids: BGR-0007 topic, '' / UUID / label / braced    topics=  5
  OK  issues_from_results (engine results, with/without guid)    topics=  4
  OK  BGR-0007 re-export is folder-stable
== services.bcf_exporter.BCFExporter.build_archive ==
  OK  Module 4 findings incl. project code, blank/UUID/label ids topics=  3
  OK  empty finding list                                         topics=  0
== services.report_artifacts (pipeline topics -> generate_bcf) ==
  OK  persist_bcf (lower-case uuid5 + legacy non-uuid topic id)  topics=  2
ALL ARCHIVES VALID against buildingSMART BCF 2.1 markup.xsd + visinfo.xsd
```

The same sweep also confirmed the snapshot in every folder is a decodable PNG, every
`Comment` carries `Guid` as an attribute with `Date, Author, Comment` children, and
no `findViewpoint`, `viewpointIndex`, `History` or `Reply` constructs are emitted.

## Not verified

Opening the archives in Navisworks, Revit, ArchiCAD or Solibri was not possible from
this environment. Schema validity is necessary for those imports, not proof of them.

## Out of scope, flagged separately

* The pre-existing `test_ids_exporter_xml_generation` failure.

---

# Follow-up (2026-09-03): engine-level BCF writers

Scope: `generate_gc_bcf`, `generate_cc_bcf`, `generate_mic_bcf` in `app/engines/`,
their `run_validation_demo()` entry points, `scripts/regenerate_demo_bcf.py`,
`tests/test_engine_bcf_export.py`.

## Correction to the note above

The 38 archives under `data/validation_bcf/` did **not** come from the engine
writers. They are written by the 38-model sweep (`scripts/eval/test_all_38_models.py`)
through the Blue Halo path, which calls `bcf_generator.generate_bcf`, and the
directory is gitignored (404 MB, regenerable). Their violations are the generator's
old structural ones, fixed earlier; the archives on disk simply predate that fix. The
sweep only re-exports BCF under `--refresh`, which recomputes geometry for every
cached model, so they were not regenerated here. Every archive the sweep writes from
now on goes through the validated generator.

## What the engine writers did wrong

Each wrote its own `markup.bcf` and `viewpoint.bcfv` by hand. Measured on the same
two-scenario input before and after, validating with `xmlschema` against the vendored
XSDs:

| Engine | Before (HEAD `74b8b16`) | After |
|---|---|---|
| GC-001 | 11 violations across 2 topics | 0 |
| CC-001 | 9 violations across 2 topics | 0 |
| MC-001 | 9 violations across 2 topics | 0 |

The violations were the same in all three: a `Components` block inside `Topic`
(not in `markup.xsd`), `viewpoint.bcfv` without the mandatory `Visibility` element,
no `bcf.version` or `project.bcfp` descriptor, no `Viewpoints` link or `snapshot.png`,
and demo ids such as `GC-VAL-001B` written as `IfcGuid`, which fails the
22-character facet. The demos also wrote to a root-level `output/` directory, which
CLAUDE.md forbids.

## Fix

* Each writer now maps its result dataclass onto `BCFIssue` and delegates to
  `generate_bcf`. The full assessment text (sub-scores, formula, mitigations,
  standards) moved into the topic description unchanged, plus the assessment date.
* `BCFIssue` gained `related_component_guids`, so a GC-001 topic selects and
  colours both the anode (primary) and the cathode. Blanks and duplicates collapse;
  ids that are not IFC GlobalIds keep a `Component` without `IfcGuid`, with the raw
  id in `AuthoringToolId`.
* Demo outputs moved to `docs/bcf_exports/<ENGINE>_validation_demo.bcfzip` and
  `docs/validation/data/<ENGINE>_validation_demo_asset_register.csv`, exposed as
  `DEMO_BCF_PATH` / `DEMO_CSV_PATH` on each engine module.
* `scripts/regenerate_demo_bcf.py` reruns the three demos and validates the result;
  `--sweep` additionally reports on `data/validation_bcf/*.bcf` without regenerating.

## Evidence

```
$ uv run python scripts/regenerate_demo_bcf.py
  OK  topics=    4 docs/bcf_exports/GC-001_validation_demo.bcfzip
  OK  topics=   10 docs/bcf_exports/CC-001_validation_demo.bcfzip
  OK  topics=    6 docs/bcf_exports/MC-001_validation_demo.bcfzip
  3/3 demo archives valid
```

`uv run pytest tests/test_engine_bcf_export.py tests/test_bcf_generator.py
tests/test_bcf_exporter_archive.py tests/test_bcf_exporter.py tests/test_report_artifacts.py
tests/test_phase_6e_export.py tests/test_pipeline_tracker.py`: 139 passed.

Topic counts are lower than scenario counts by design: Low-band results do not raise
BCF topics, matching the writers' previous behaviour.
