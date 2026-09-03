"""
test_real_ifc_pipeline.py
------------------------------------------------
Blue Halo — Phase 5 Part B: end-to-end pipeline test against a real IFC file.

Mirrors score_rule_extraction.py / validate_blue_halo.py in style (plain
script, print()-based, no pytest). Unlike validate_blue_halo.py — which
feeds the algorithm hand-built mock dataclasses — this script drives the
FULL stack through ifcopenshell:

    data/test_hospital_mep_scenario.ifc     (Phase 5 Part A fixture)
        -> ifcopenshell.open
        -> Phase 2  load_clearance_config(hermes_case_study_and_config.json)
        -> Phase 1  generate_halo_volume()   [the IFC-reading entry point]
        -> Phase 1  detect_halo_clash()      [the IFC-reading entry point]
        -> Phase 4  generate_bcf_zip_from_halo_clashes() -> test_output.bcf
        -> Phase 4  generate_pset_halo_reservation()     -> *_halos.json

It deliberately calls generate_halo_volume / detect_halo_clash (the
ifcopenshell wrappers) rather than the *_from_geometry / *_against_geometry
cores that validate_blue_halo.py exercises, so the IFC geometry-extraction
path — placement matrices, tessellated vertices, metre->mm unit scaling —
is covered too. That path is exactly what mock dataclasses cannot test.

Regenerate the fixture with:
    uv run python app/modules/blue_halo/build_test_ifc.py

Usage:
    uv run python test_real_ifc_pipeline.py
"""

import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, ".")

import ifcopenshell  # noqa: E402

from app.modules.blue_halo.halo_volume_generator import (  # noqa: E402
    BraceType,
    ClashReport,
    ClearanceConfig,
    HaloVolume,
    detect_halo_clash,
    generate_halo_volume,
    load_clearance_config,
    unit_scale_to_mm,
)
from app.modules.reporter.blue_halo_bcf_exporter import (  # noqa: E402
    PSET_HALO_RESERVATION,
    generate_bcf_zip_from_halo_clashes,
    generate_pset_halo_reservation,
)

IFC_PATH = Path("data/test_hospital_mep_scenario.ifc")
CONFIG_PATH = Path("hermes_case_study_and_config.json")
BCF_OUTPUT = Path("test_output.bcf")
PSET_OUTPUT = Path("test_hospital_mep_halos.json")

# Braced MEP classes vs. everything the halo must stay clear of. Both lists
# are IFC classes rather than GlobalIds so the script keeps working if the
# fixture gains elements.
MEP_CLASSES = ("IfcPipeSegment", "IfcDuctSegment")
CLASH_CANDIDATE_CLASSES = ("IfcPipeSegment", "IfcDuctSegment", "IfcColumn", "IfcBeam", "IfcSlab")

# The brace variant to evaluate. The real EN 1998-1 + DIN 4149 config gives
# every variant the same clearance (a documented data gap in that config),
# so the choice does not change the numbers here — but it must be an
# ANGLE_IRON variant to represent the rigid bracing these scenarios assume.
BRACE_VARIANT = "angle_fire"

# Scenario expectations, keyed by element Name substring. These encode what
# the Part A fixture was built to demonstrate; the validation section below
# checks the pipeline actually produces them.
EXPECTED_CROSSING = ("CHW Pipe", "HW Pipe")  # halo owner, intruder
EXPECTED_CLEARANCE = ("Fire Sprinkler Riser", "Column C1")


def _out(line: str = "") -> None:
    print(line)


def _name(element) -> str:
    return str(getattr(element, "Name", "") or "")


def _describe_box(bbox) -> str:
    sx, sy, sz = bbox.size
    return (
        f"{sx:.0f}x{sy:.0f}x{sz:.0f}mm @ "
        f"({bbox.min.x:.0f},{bbox.min.y:.0f},{bbox.min.z:.0f})"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Step 1 — load the IFC
# ═══════════════════════════════════════════════════════════════════════════


def load_ifc() -> tuple:
    _out("=" * 74)
    _out("  STEP 1 — Load test IFC")
    _out("=" * 74)

    if not IFC_PATH.exists():
        raise FileNotFoundError(
            f"{IFC_PATH} not found — regenerate it with:\n"
            "  uv run python app/modules/blue_halo/build_test_ifc.py"
        )

    model = ifcopenshell.open(str(IFC_PATH))
    scale = unit_scale_to_mm(model)

    _out(f"\n  File:        {IFC_PATH} ({IFC_PATH.stat().st_size:,} bytes)")
    _out(f"  Schema:      {model.schema}")
    _out(f"  Unit scale:  {scale:g} (model length unit -> mm)")
    _out(f"  Storeys:     {len(model.by_type('IfcBuildingStorey'))}")
    building = model.by_type("IfcBuilding")
    _out(f"  Building:    {_name(building[0]) if building else '(none)'}")
    return model, scale


# ═══════════════════════════════════════════════════════════════════════════
# Step 2 — extract MEP + structural elements
# ═══════════════════════════════════════════════════════════════════════════


def extract_elements(model, scale: float) -> tuple:
    _out("\n" + "=" * 74)
    _out("  STEP 2 — Extract elements")
    _out("=" * 74)

    def collect(classes):
        found, seen = [], set()
        for ifc_class in classes:
            for element in model.by_type(ifc_class):
                guid = element.GlobalId
                if guid not in seen:
                    seen.add(guid)
                    found.append(element)
        return found

    mep = collect(MEP_CLASSES)
    candidates = collect(CLASH_CANDIDATE_CLASSES)

    _out(f"\n  MEP elements to brace ({len(mep)}):")
    from app.modules.blue_halo.halo_volume_generator import element_bbox_mm

    for element in mep:
        bbox = element_bbox_mm(element, scale)
        psets = _read_pset(element, "Pset_BlueHaloTest")
        material = _read_material(element)
        _out(f"    {element.is_a():15s} {_name(element)}")
        _out(f"      guid={element.GlobalId}  material={material}  "
             f"scenario={psets.get('Scenario', '?')}")
        _out(f"      bbox={_describe_box(bbox) if bbox else 'UNRESOLVED'}")

    structure = [e for e in candidates if e.is_a() not in MEP_CLASSES]
    _out(f"\n  Clash candidates ({len(candidates)} total = {len(mep)} MEP + "
         f"{len(structure)} structural):")
    for element in structure:
        bbox = element_bbox_mm(element, scale)
        _out(f"    {element.is_a():15s} {_name(element):32s} "
             f"{_describe_box(bbox) if bbox else 'UNRESOLVED'}")

    return mep, candidates


def _read_pset(element, pset_name: str) -> dict:
    """Read one property set off an element as a flat dict."""
    import ifcopenshell.util.element

    try:
        return (ifcopenshell.util.element.get_psets(element) or {}).get(pset_name, {})
    except Exception:
        return {}


def _read_material(element) -> str:
    import ifcopenshell.util.element

    try:
        materials = ifcopenshell.util.element.get_materials(element)
        return str(getattr(materials[0], "Name", "?")) if materials else "?"
    except Exception:
        return "?"


# ═══════════════════════════════════════════════════════════════════════════
# Step 3 / 4 — config + Phase 1 algorithm
# ═══════════════════════════════════════════════════════════════════════════


def load_config() -> ClearanceConfig:
    _out("\n" + "=" * 74)
    _out("  STEP 3 — Load Phase 2 config")
    _out("=" * 74)

    config = load_clearance_config(CONFIG_PATH)
    rule = config.rules[BRACE_VARIANT]
    _out(f"\n  Config:      {CONFIG_PATH}")
    _out(f"  Jurisdiction:{config.jurisdiction}")
    _out(f"  Standards:   {config.standards_cited}")
    _out(f"  Variants:    {sorted(config.rules)}")
    _out(f"  Using:       {BRACE_VARIANT} (brace_type={rule.brace_type.value})")
    _out(f"    clearance={rule.base_clearance_mm:.0f}mm  "
         f"spacing={rule.spacing_transverse_m:g}/{rule.spacing_longitudinal_m:g}m  "
         f"angle=[{rule.angle_min_degrees:g}-{rule.angle_max_degrees:g}]deg")
    _out(f"  Data gaps:   {len(config.data_gaps)} flagged in this config")
    return config


def run_phase1(model, mep: list, candidates: list, config: ClearanceConfig, scale: float) -> tuple:
    _out("\n" + "=" * 74)
    _out("  STEP 4 — Phase 1: generate halo volumes + detect clashes")
    _out("=" * 74)

    rule = config.rules[BRACE_VARIANT]
    halos: list[HaloVolume] = []
    clashes: list[ClashReport] = []
    per_element: dict[str, list[ClashReport]] = {}

    for element in mep:
        halo = generate_halo_volume(
            element, rule.brace_type, rule, model=model, scale_to_mm=scale
        )
        if halo is None:
            _out(f"\n  {_name(element)}: NO HALO (geometry unresolved)")
            continue
        halos.append(halo)

        found = detect_halo_clash(halo, candidates, model=model, scale_to_mm=scale)
        clashes.extend(found)
        per_element[halo.id] = found

        _out(f"\n  {_name(element)}")
        _out(f"    element bbox: {_describe_box(halo.element_bbox_mm)}")
        _out(f"    halo bbox:    {_describe_box(halo.halo_bbox_mm)}  "
             f"(+{halo.clearance_mm:.0f}mm, {halo.halo_bbox_mm.volume_mm3:,.0f} mm^3)")
        if not found:
            _out("    clashes:      none")
        for clash in found:
            _out(f"    clash:        {clash.severity.upper():8s} vs "
                 f"{clash.clashing_element_class} ({_guid_name(model, clash.clashing_element_id)})"
                 f"  overlap={clash.overlap_volume_mm3:,.0f} mm^3")

    _out(f"\n  TOTAL: {len(halos)} halo volume(s), {len(clashes)} clash(es)")
    return halos, clashes, per_element


def _guid_name(model, guid: str) -> str:
    try:
        return _name(model.by_guid(guid)) or guid
    except Exception:
        return guid


# ═══════════════════════════════════════════════════════════════════════════
# Step 5 — Phase 4 export
# ═══════════════════════════════════════════════════════════════════════════


def run_phase4(halos: list, clashes: list) -> tuple:
    _out("\n" + "=" * 74)
    _out("  STEP 5 — Phase 4: BCF 2.1 + Pset export")
    _out("=" * 74)

    zip_bytes = generate_bcf_zip_from_halo_clashes(
        clashes,
        project_id="BLUE-HALO-TEST-HOSPITAL-001",
        halos={halo.id: halo for halo in halos},
        project_name="BIMGUARD AI - Blue Halo Test Hospital MEP Scenario",
    )
    BCF_OUTPUT.write_bytes(zip_bytes)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
    _out(f"\n  Wrote {BCF_OUTPUT} ({len(zip_bytes):,} bytes, {len(names)} entries)")
    for name in sorted(names):
        _out(f"    {name}")

    psets = {halo.source_element_id: generate_pset_halo_reservation(halo) for halo in halos}
    PSET_OUTPUT.write_text(json.dumps(psets, indent=2), encoding="utf-8")
    _out(f"\n  Wrote {PSET_OUTPUT} ({PSET_OUTPUT.stat().st_size:,} bytes, "
         f"{len(psets)} halo reservation(s))")
    sample_id = next(iter(psets))
    _out(f"\n  Sample {PSET_HALO_RESERVATION} ({sample_id}):")
    for key, value in psets[sample_id][PSET_HALO_RESERVATION].items():
        _out(f"    {key:22s} = {value}")

    return names, psets


# ═══════════════════════════════════════════════════════════════════════════
# Step 6 — validation
# ═══════════════════════════════════════════════════════════════════════════


def validate(model, mep, halos, clashes, zip_names, psets) -> bool:
    _out("\n" + "=" * 74)
    _out("  STEP 6 — Validation")
    _out("=" * 74)

    checks: list[tuple[str, bool, str]] = []

    # 1. IFC loaded (reaching here proves it) with the expected schema.
    checks.append((f"IFC loads without errors (schema {model.schema})", True, ""))

    # 2. Exactly the 4 MEP elements the fixture defines were extracted.
    checks.append((
        f"4 pipe/duct elements extracted (got {len(mep)})",
        len(mep) == 4,
        "" if len(mep) == 4 else f"expected 4, got {len(mep)}",
    ))

    # 3. One halo per MEP element — i.e. IFC geometry resolved for all of
    #    them. A None halo here would mean element_bbox_mm failed, which is
    #    the failure mode mock-dataclass tests structurally cannot catch.
    checks.append((
        f"Phase 1 generated {len(halos)} halo volume(s), one per MEP element",
        len(halos) == len(mep),
        "" if len(halos) == len(mep) else f"{len(mep) - len(halos)} element(s) had unresolved geometry",
    ))

    # 4. The Scenario B crossing clash is present (CHW halo <- HW pipe).
    crossing = _find_clash(model, clashes, halos, *EXPECTED_CROSSING)
    checks.append((
        f"Scenario B crossing clash detected ({EXPECTED_CROSSING[0]} halo vs {EXPECTED_CROSSING[1]})",
        crossing is not None,
        "" if crossing else "no clash found between the crossing pipes",
    ))

    # 5. The Scenario C clearance clash is present (riser halo <- column).
    #    The riser sits 60mm off the column face, inside the config's
    #    clearance, so its halo must intrude on the column.
    clearance = _find_clash(model, clashes, halos, *EXPECTED_CLEARANCE)
    checks.append((
        f"Scenario C clearance clash detected ({EXPECTED_CLEARANCE[0]} halo vs {EXPECTED_CLEARANCE[1]})",
        clearance is not None,
        "" if clearance else "riser halo did not intrude on the column",
    ))

    # 6. Severity banding actually discriminates: the two expected clashes
    #    must land in DIFFERENT bands, with the 60mm-gap clearance breach
    #    scoring strictly worse than the glancing pipe crossing. Asserting
    #    the ordering rather than two literal band names keeps this robust
    #    to the severity thresholds being retuned later.
    if crossing and clearance:
        order = ["minor", "major", "critical"]
        ordered_ok = order.index(clearance.severity) > order.index(crossing.severity)
        detail = (
            f"crossing={crossing.severity.upper()}, clearance={clearance.severity.upper()}"
        )
    else:
        ordered_ok, detail = False, "one or both expected clashes missing"
    checks.append((
        f"Severity banding discriminates ({detail})",
        ordered_ok,
        "" if ordered_ok else "clearance breach did not outrank the crossing",
    ))

    # 7. BCF ZIP structure: bcf.version + project.bcfp at the root, and one
    #    {guid}/{markup.bcf, viewpoint.bcfv, snapshot.png} folder per clash.
    folders: dict[str, set] = {}
    for name in zip_names:
        if "/" in name:
            folder, filename = name.split("/", 1)
            folders.setdefault(folder, set()).add(filename)
    structure_ok = (
        "bcf.version" in zip_names
        and "project.bcfp" in zip_names
        and len(folders) == len(clashes)
        and all(f == {"markup.bcf", "viewpoint.bcfv", "snapshot.png"} for f in folders.values())
    )
    checks.append((
        f"BCF ZIP structure valid (bcf.version + project.bcfp + {len(folders)} topic folder(s) "
        f"for {len(clashes)} clash(es))",
        structure_ok,
        "" if structure_ok else "missing root files or malformed topic folders",
    ))

    # 8. Pset payload round-trips through JSON unchanged and is correctly
    #    Pset_-named — the contract Module 5 / IFC egress depends on.
    try:
        round_tripped = json.loads(json.dumps(psets))
        pset_ok = round_tripped == psets and all(
            list(p) == [PSET_HALO_RESERVATION] and isinstance(p[PSET_HALO_RESERVATION], dict)
            for p in psets.values()
        )
        pset_detail = ""
    except (TypeError, ValueError) as exc:
        pset_ok, pset_detail = False, str(exc)
    checks.append((
        f"{PSET_HALO_RESERVATION} data is valid, JSON-serializable IFC property-set output",
        pset_ok,
        pset_detail,
    ))

    _out("")
    all_passed = True
    for label, passed, detail in checks:
        _out(f"  [{'PASS' if passed else 'FAIL'}] {label}")
        if not passed and detail:
            _out(f"         -> {detail}")
        all_passed = all_passed and passed

    _out(f"\n  {sum(1 for _l, p, _d in checks if p)}/{len(checks)} checks passed")
    return all_passed


def _find_clash(model, clashes: list, halos: list, halo_name: str, intruder_name: str):
    """Find the clash where `halo_name`'s halo is intruded on by `intruder_name`."""
    halo_ids = {
        halo.id
        for halo in halos
        if halo_name.lower() in _guid_name(model, halo.source_element_id).lower()
    }
    for clash in clashes:
        if clash.halo_id in halo_ids and intruder_name.lower() in _guid_name(
            model, clash.clashing_element_id
        ).lower():
            return clash
    return None


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _out("=" * 74)
    _out("  Blue Halo Phase 5 — end-to-end pipeline test on a real IFC model")
    _out("=" * 74)

    model, scale = load_ifc()
    mep, candidates = extract_elements(model, scale)
    config = load_config()
    halos, clashes, _per_element = run_phase1(model, mep, candidates, config, scale)
    zip_names, psets = run_phase4(halos, clashes)
    passed = validate(model, mep, halos, clashes, zip_names, psets)

    _out("\n" + "=" * 74)
    _out(f"  OVERALL: {'ALL CHECKS PASSED' if passed else 'SOME CHECKS FAILED'}")
    _out("=" * 74)
    _out(f"\n  Outputs: {BCF_OUTPUT}, {PSET_OUTPUT}")

    sys.exit(0 if passed else 1)
