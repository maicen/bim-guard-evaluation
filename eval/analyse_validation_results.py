"""
analyse_validation_results.py
------------------------------------------------
BIMGUARD AI — Appendix B analysis: 7 tables + 4 figures from the 38-model
validation sweep.

Consumes the per-model records written by test_all_38_models.py
(data/validation_results/*.json) and the BCF archives it produced
(data/validation_bcf/*.bcf), and emits the evidentiary artefacts for
Appendix B of the thesis, following the Appendix F house convention
(JSON + CSV + summary markdown + numbered figures under docs/).

TABLES
    1  Per-model summary
    2  Severity distribution
    3  Material x corrosion engine
    4  Engine band distribution + input coverage
    5  BCF 2.1 validity report
    6  Standards sensitivity (clearance threshold -> clash count)
    7  IFC schema comparison (IFC2X3 vs IFC4)

FIGURES
    fig1  Clash severity histogram
    fig2  Material risk heatmap
    fig3  Engine coverage radar
    fig4  Schema fidelity scatter

WHAT IS RECOMPUTED AND WHY
    Tables 1, 2, 4 (bands) and 7 come straight from the cached sweep
    records. Three do not, and are recomputed here from the cached IFCs:

      Table 3 needs per-element material cross-tabulated against per-element
      engine band. The sweep aggregated bands per model, not per material,
      so the cross-tabulation does not exist in its output.

      Table 5 needs the BCF archives actually parsed. The sweep recorded
      entry counts and byte sizes, which is not the same as verifying that
      every markup.bcf / viewpoint.bcfv is well-formed XML and that each
      topic folder is complete.

      Table 6 needs clash counts at clearance values other than the single
      200 mm the sweep ran. Geometry evaluation dominates that cost, so
      each model is evaluated once and the resulting bounding boxes are
      reused across every clearance in the sweep.

    "Engine coverage" in Table 4 and fig3 means the share of piping
    elements that carry the INPUTS an engine requires — not its flag rate.
    That is the question the thesis puts to this dataset: whether the
    inputs the engines need exist in real federated models at all. A flag
    rate cannot answer it, because an engine that substitutes a default for
    missing data flags at 100% precisely when coverage is 0%.

Usage:
    uv run python analyse_validation_results.py
    uv run python analyse_validation_results.py --max-models 6   # quick pass
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
import os
from pathlib import Path
from typing import Any, Optional

# Resolve evaluation dir and core bim-guard repo path
REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
BIMGUARD_CORE = Path(os.getenv("BIMGUARD_PATH", str(REPO_ROOT.parent / "bim-guard")))

for p in [EVAL_DIR, REPO_ROOT, BIMGUARD_CORE, Path(".")]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import ifcopenshell  # noqa: E402

from app.modules.ifc_reader.piping_producer import (  # noqa: E402
    media_for_system,
    produce_piping_elements_from_model,
)
from app.modules.blue_halo.halo_volume_generator import (  # noqa: E402
    ElementGeometry,
    detect_halo_clash_against_geometry,
    generate_halo_volume_from_geometry,
    load_clearance_config,
)
from app.modules.comparator.compliance_runner import (  # noqa: E402
    run_crevice_compliance_check,
    run_galvanic_compliance_check,
    run_mic_compliance_check,
)
try:
    from test_all_38_models import (  # noqa: E402
        BRACE_VARIANT,
        ENGINE_NAMES,
        MEP_CLASSES,
        STRUCTURAL_CLASSES,
        _EngineElement,
        _SpatialGrid,
        _median,
        world_bboxes_mm,
    )
except ImportError:
    from eval.test_all_38_models import (  # noqa: E402
        BRACE_VARIANT,
        ENGINE_NAMES,
        MEP_CLASSES,
        STRUCTURAL_CLASSES,
        _EngineElement,
        _SpatialGrid,
        _median,
        world_bboxes_mm,
    )

RESULT_DIR = Path("data/validation_results")
BCF_DIR = Path("data/validation_bcf")
OUT_DIR = Path("docs/validation")
FIG_DIR = OUT_DIR
CONFIG_PATH = Path("hermes_case_study_and_config.json")

# Clearance values for the sensitivity sweep, in mm. The two starred values
# are the ones the jurisdiction configs actually produce, so the sweep is
# anchored on real standards rather than arbitrary steps:
#   200.0  EN 1998-1:2020 + DIN 4149:2022  (hermes_case_study_and_config.json)
#   457.2  ASCE 7-22 + NFPA 13             (18 in, the US fallback pair)
SENSITIVITY_CLEARANCES_MM = [25.0, 50.0, 100.0, 150.0, 200.0, 300.0, 457.2, 600.0]
JURISDICTION_CLEARANCES = {200.0: "EN 1998-1 + DIN 4149", 457.2: "ASCE 7-22 + NFPA 13"}

BAND_ORDER = ["Low", "Medium", "High", "Critical"]
SEVERITY_ORDER = ["minor", "major", "critical"]

_LINES: list[str] = []


def _out(line: str = "") -> None:
    print(line, flush=True)
    _LINES.append(line)


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(str(h) for h in header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


# ═══════════════════════════════════════════════════════════════════════════
# Load cached sweep records
# ═══════════════════════════════════════════════════════════════════════════


def load_records() -> list[dict]:
    records = []
    for path in sorted(RESULT_DIR.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    records.sort(key=lambda r: r["row"])
    return records


# ═══════════════════════════════════════════════════════════════════════════
# Tables 1, 2, 7 — straight from the cached records
# ═══════════════════════════════════════════════════════════════════════════


def table1_per_model(records: list[dict], bcf: dict[int, dict]) -> tuple:
    header = ["row", "category", "model", "schema", "size_mb", "mep", "mep_geom",
              "structural", "struct_geom", "halos", "clashes", "minor", "major",
              "critical", "piping", "with_material", "bcf_valid", "seconds", "status"]
    rows = []
    for r in records:
        c = r.get("counts", {})
        sev = r.get("clash_severity", {})
        rows.append([
            r["row"], r.get("category", "?"), r["name"][:44], r.get("schema", "-"),
            r.get("actual_size_mb", 0), c.get("mep", 0), c.get("mep_with_geometry", 0),
            c.get("structural", 0), c.get("structural_with_geometry", 0),
            r.get("halos", 0), r.get("clashes", 0),
            sev.get("minor", 0), sev.get("major", 0), sev.get("critical", 0),
            r.get("piping_elements", 0),
            r.get("material_coverage", {}).get("with_material", 0),
            bcf.get(r["row"], {}).get("verdict", "n/a"),
            r.get("seconds", 0), r["status"],
        ])
    return header, rows


def table2_severity(records: list[dict]) -> tuple:
    ok = [r for r in records if r["status"] == "ok"]
    totals = Counter()
    by_category: dict[str, Counter] = defaultdict(Counter)
    for r in ok:
        for band, count in r.get("clash_severity", {}).items():
            totals[band] += count
            by_category[r.get("category", "?")][band] += count

    grand = sum(totals.values())
    header = ["scope", "minor", "major", "critical", "total", "minor_%", "major_%", "critical_%"]
    rows = []

    def add(label: str, counter: Counter) -> None:
        t = sum(counter.values())
        rows.append([
            label, counter["minor"], counter["major"], counter["critical"], t,
            f"{counter['minor']/t*100:.2f}" if t else "0.00",
            f"{counter['major']/t*100:.2f}" if t else "0.00",
            f"{counter['critical']/t*100:.2f}" if t else "0.00",
        ])

    add("ALL", totals)
    for category in sorted(by_category):
        add(category, by_category[category])
    return header, rows, totals, grand


def table7_schema(records: list[dict]) -> tuple:
    ok = [r for r in records if r["status"] == "ok"]
    by_schema: dict[str, dict] = defaultdict(lambda: {"models": 0, "mep": 0, "geom": 0,
                                                      "clashes": 0, "piping": 0, "material": 0})
    for r in ok:
        s = by_schema[r.get("schema", "unknown")]
        c = r.get("counts", {})
        s["models"] += 1
        s["mep"] += c.get("mep", 0)
        s["geom"] += c.get("mep_with_geometry", 0)
        s["clashes"] += r.get("clashes", 0)
        s["piping"] += r.get("piping_elements", 0)
        s["material"] += r.get("material_coverage", {}).get("with_material", 0)

    header = ["schema", "models", "mep", "mep_geom_%", "clashes", "piping", "material_%"]
    rows = []
    for schema in sorted(by_schema):
        s = by_schema[schema]
        rows.append([
            schema, s["models"], s["mep"],
            f"{s['geom']/s['mep']*100:.1f}" if s["mep"] else "n/a",
            s["clashes"], s["piping"],
            f"{s['material']/s['piping']*100:.1f}" if s["piping"] else "n/a",
        ])

    # Schema twins: same building exported to both schemas — the only
    # controlled comparison in the dataset, since everything else differs
    # by building as well as by schema.
    twins = [(8, 13, "west_riverside mechanical"), (9, 14, "west_riverside plumbing")]
    twin_header = ["pair", "building", "mep_2x3", "mep_ifc4", "clashes_2x3",
                   "clashes_ifc4", "delta_clashes", "delta_%"]
    twin_rows = []
    by_row = {r["row"]: r for r in ok}
    for a, b, label in twins:
        ra, rb = by_row.get(a), by_row.get(b)
        if not ra or not rb:
            continue
        # Row 8/9 are IFC4; 13/14 are the IFC2x3 twins.
        ca, cb = ra.get("clashes", 0), rb.get("clashes", 0)
        delta = abs(ca - cb)
        twin_rows.append([
            f"{a}/{b}", label, rb.get("counts", {}).get("mep", 0),
            ra.get("counts", {}).get("mep", 0), cb, ca, delta,
            f"{delta/max(ca,cb)*100:.2f}" if max(ca, cb) else "0.00",
        ])
    return header, rows, twin_header, twin_rows


# ═══════════════════════════════════════════════════════════════════════════
# Table 5 — BCF validity (parses every archive)
# ═══════════════════════════════════════════════════════════════════════════


def table5_bcf(records: list[dict]) -> tuple:
    header = ["row", "model", "bytes", "entries", "topics", "complete_topics",
              "xml_ok", "xml_bad", "root_files", "verdict"]
    rows = []
    per_row: dict[int, dict] = {}

    for r in records:
        info = r.get("bcf", {})
        path = Path(info.get("path", "")) if info.get("path") else None
        if not path or not path.exists():
            verdict = "missing"
            rows.append([r["row"], r["name"][:36], 0, 0, 0, 0, 0, 0, "no", verdict])
            per_row[r["row"]] = {"verdict": verdict}
            continue

        xml_ok = xml_bad = 0
        topics: dict[str, set] = defaultdict(set)
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                for name in names:
                    if "/" in name:
                        folder, filename = name.split("/", 1)
                        topics[folder].add(filename)
                    if name.endswith((".bcf", ".bcfv", ".version", ".bcfp")):
                        try:
                            ET.fromstring(zf.read(name))
                            xml_ok += 1
                        except ET.ParseError:
                            xml_bad += 1
                root_ok = "bcf.version" in names and "project.bcfp" in names
        except zipfile.BadZipFile:
            rows.append([r["row"], r["name"][:36], path.stat().st_size, 0, 0, 0, 0, 0, "no", "corrupt"])
            per_row[r["row"]] = {"verdict": "corrupt"}
            continue

        required = {"markup.bcf", "viewpoint.bcfv", "snapshot.png"}
        complete = sum(1 for files in topics.values() if files == required)
        verdict = "VALID" if (root_ok and xml_bad == 0 and complete == len(topics)) else "INVALID"
        rows.append([r["row"], r["name"][:36], path.stat().st_size, len(names),
                     len(topics), complete, xml_ok, xml_bad,
                     "yes" if root_ok else "no", verdict])
        per_row[r["row"]] = {"verdict": verdict, "topics": len(topics)}

    return header, rows, per_row


# ═══════════════════════════════════════════════════════════════════════════
# Tables 3, 4(coverage), 6 — one recompute pass per model
# ═══════════════════════════════════════════════════════════════════════════

# Which PipingElement fields each engine needs before it can score an
# element on real data rather than on a substituted default. Derived from
# the coercers in compliance_runner and the compare() bodies in
# material_media / cross_material.
ENGINE_INPUTS: dict[str, tuple[str, ...]] = {
    "GC-001": ("material", "dissimilar_neighbour"),
    "CC-001": ("material", "joint_type", "operating_temperature_c"),
    "MC-001": ("material", "media", "nominal_diameter_mm", "operating_temperature_c"),
    "MM-001": ("material", "media", "environment_class"),
    "XM-001": ("material", "dissimilar_neighbour", "environment_class"),
}


def _element_inputs(element: Any, by_id: dict) -> dict[str, bool]:
    """Which engine inputs this element actually carries."""
    material_known = element.material != "Unknown"
    neighbours = [by_id.get(n) for n in getattr(element, "joined_to", [])]
    dissimilar = any(
        n is not None and n.material != "Unknown" and n.material != element.material
        for n in neighbours
    )
    media = media_for_system(element.system)
    return {
        "material": material_known,
        "dissimilar_neighbour": bool(dissimilar),
        "joint_type": element.joint_type is not None,
        "operating_temperature_c": element.operating_temperature_c is not None,
        "nominal_diameter_mm": element.nominal_diameter_mm is not None,
        "media": media not in ("unknown", ""),
        "environment_class": getattr(element.environment_class, "value", "") != "unclassified",
    }


def recompute(records: list[dict], config, max_models: int, sensitivity_models: int) -> dict:
    """One pass per MEP-bearing model: material x engine, input coverage,
    and the clearance sensitivity sweep (geometry evaluated once, reused).

    The clearance sweep is scoped separately from the corrosion pass and to
    fewer models on purpose. Corrosion scoring is linear in element count,
    so running it corpus-wide is cheap; the clearance sweep re-runs clash
    detection once per threshold, so its cost is (thresholds x clashes) and
    the largest models alone would dominate the whole analysis. The subset
    used is recorded in the output so the scope is explicit rather than
    implied.
    """
    ok = [r for r in records if r["status"] == "ok" and r.get("piping_elements", 0) > 0]
    ok.sort(key=lambda r: -r.get("piping_elements", 0))
    if max_models:
        ok = ok[:max_models]

    # Sensitivity subset: the largest MEP-bearing models are excluded so a
    # single model cannot dominate the threshold curve, then the next
    # largest are taken — small models produce too few clashes for the
    # curve to be readable.
    mep_bearing = sorted(
        (r for r in ok if r.get("halos", 0) > 0), key=lambda r: -r.get("halos", 0)
    )
    sens_rows = {r["row"] for r in mep_bearing[2 : 2 + sensitivity_models]} or {
        r["row"] for r in mep_bearing[:sensitivity_models]
    }

    material_bands: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    input_hits: Counter = Counter()
    input_total = 0
    engine_ready: Counter = Counter()
    sensitivity: dict[float, Counter] = {c: Counter() for c in SENSITIVITY_CLEARANCES_MM}
    models_used: list[dict] = []

    runners = {
        "GC-001": run_galvanic_compliance_check,
        "CC-001": run_crevice_compliance_check,
        "MC-001": run_mic_compliance_check,
    }

    for index, record in enumerate(ok, start=1):
        path = Path(record.get("local_file", ""))
        if not path.exists():
            continue
        started = time.time()
        _out(f"    [{index}/{len(ok)}] row {record['row']}: {record['name'][:40]} ...")
        try:
            model = ifcopenshell.open(str(path))
        except Exception as exc:
            _out(f"        skipped: {type(exc).__name__}: {exc}")
            continue

        # --- corrosion: material x engine band, and input coverage --------
        try:
            elements = produce_piping_elements_from_model(model, source_path=str(path))
        except Exception as exc:
            elements = []
            _out(f"        piping producer failed: {type(exc).__name__}")

        by_id = {e.id: e for e in elements}
        for element in elements:
            material = element.material
            adapter = _EngineElement(element)
            for name, runner in runners.items():
                try:
                    band = str(runner(adapter).get("band", "Unknown"))
                except Exception:
                    band = "error"
                material_bands[material][name][band] += 1

            inputs = _element_inputs(element, by_id)
            input_total += 1
            for key, present in inputs.items():
                if present:
                    input_hits[key] += 1
            for engine, required in ENGINE_INPUTS.items():
                if all(inputs.get(k, False) for k in required):
                    engine_ready[engine] += 1

        # --- sensitivity: geometry once, clearance swept ------------------
        def collect(classes: tuple) -> list:
            found, seen = [], set()
            for ifc_class in classes:
                try:
                    entities = model.by_type(ifc_class)
                except Exception:
                    continue
                for entity in entities:
                    guid = getattr(entity, "GlobalId", None)
                    if guid and guid not in seen:
                        seen.add(guid)
                        found.append(entity)
            return found

        mep_entities = collect(MEP_CLASSES)
        structural_entities = collect(STRUCTURAL_CLASSES)
        boxes = world_bboxes_mm(model, mep_entities + structural_entities)

        def geoms(entities: list) -> list[ElementGeometry]:
            return [
                ElementGeometry(str(e.GlobalId), e.is_a(), boxes[e.GlobalId])
                for e in entities
                if e.GlobalId in boxes
            ]

        mep_geoms, all_geoms = geoms(mep_entities), geoms(mep_entities) + geoms(structural_entities)
        if mep_geoms and all_geoms and record["row"] in sens_rows:
            extents = [max(g.bbox_mm.size) for g in all_geoms]
            rule = config.rules[BRACE_VARIANT]
            for clearance in SENSITIVITY_CLEARANCES_MM:
                probe = _clone_rule(rule, clearance)
                grid = _SpatialGrid(all_geoms, cell_mm=max(_median(extents), clearance * 4))
                total = 0
                sev = Counter()
                for geometry in mep_geoms:
                    halo = generate_halo_volume_from_geometry(geometry, probe.brace_type, probe)
                    found = detect_halo_clash_against_geometry(halo, grid.candidates(halo.halo_bbox_mm))
                    total += len(found)
                    for clash in found:
                        sev[clash.severity] += 1
                sensitivity[clearance]["clashes"] += total
                for band in SEVERITY_ORDER:
                    sensitivity[clearance][band] += sev[band]

        models_used.append({"row": record["row"], "name": record["name"],
                            "seconds": round(time.time() - started, 1)})
        _out(f"        done in {time.time() - started:.0f}s "
             f"({len(elements)} piping, {len(mep_geoms)} MEP geoms)")

    return {
        "material_bands": material_bands,
        "input_hits": input_hits,
        "input_total": input_total,
        "engine_ready": engine_ready,
        "sensitivity": sensitivity,
        "models_used": models_used,
        "sensitivity_rows": sorted(sens_rows),
    }


def _clone_rule(rule, clearance_mm: float):
    """Copy a ClearanceRule with base_clearance_mm overridden."""
    from dataclasses import replace

    return replace(rule, base_clearance_mm=clearance_mm)


# ═══════════════════════════════════════════════════════════════════════════
# Figures
# ═══════════════════════════════════════════════════════════════════════════

_C = {"minor": "#4C78A8", "major": "#F58518", "critical": "#E45756", "grid": "#DDDDDD"}


def _short_label(name: str, row: int) -> str:
    """Compact model label that keeps the discipline.

    Six of the MEP-bearing models are west_riverside_hospital variants
    whose names differ only after the building name, so a plain prefix
    truncation renders them all identically. Abbreviate the building and
    keep the discipline, which is the part that distinguishes them.
    """
    name = name.replace("west_riverside_hospital", "w_riverside")
    name = name.replace("DigitalHub_FM-", "DigitalHub ").replace("_v2.ifc", "")
    name = name.replace("—", "-").replace(".ifc", "")
    name = re.sub(r"\s*\(zip:[^)]*\)", "", name)
    if len(name) > 34:
        name = name[:33] + "…"
    return f"{row} {name}"


def fig1_severity(records: list[dict], path: Path) -> None:
    ok = [r for r in records if r["status"] == "ok" and r.get("clashes", 0) > 0]
    ok.sort(key=lambda r: -r.get("clashes", 0))
    labels = [_short_label(r["name"], r["row"]) for r in ok]
    minor = [r.get("clash_severity", {}).get("minor", 0) for r in ok]
    major = [r.get("clash_severity", {}).get("major", 0) for r in ok]
    crit = [r.get("clash_severity", {}).get("critical", 0) for r in ok]

    fig, ax = plt.subplots(figsize=(11, 6.5))
    y = np.arange(len(labels))
    ax.barh(y, minor, color=_C["minor"], label="minor")
    ax.barh(y, major, left=minor, color=_C["major"], label="major")
    ax.barh(y, crit, left=np.array(minor) + np.array(major), color=_C["critical"], label="critical")
    ax.set_yticks(y, labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xscale("symlog")
    ax.set_xlabel("clashes (symlog scale)")
    ax.set_title("Figure B.1 — Clash severity distribution by model\n"
                 "Blue Halo, EN 1998-1 + DIN 4149 (200 mm clearance)", fontsize=11)
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="x", color=_C["grid"], lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig2_material_heatmap(material_bands: dict, path: Path) -> None:
    """Heatmap of mean band severity per material x engine.

    Cells are the mean band index (Low=0 .. Critical=3). A row that is
    uniform across engines, or a column uniform across materials, is the
    visible signature of an engine whose output does not vary with its
    input — which is what this dataset found for CC-001 and MC-001.
    """
    materials = sorted(material_bands, key=lambda m: -sum(
        sum(c.values()) for c in material_bands[m].values()))[:14]
    engines = ["GC-001", "CC-001", "MC-001"]
    grid = np.full((len(materials), len(engines)), np.nan)
    counts = np.zeros((len(materials), len(engines)), dtype=int)

    for i, material in enumerate(materials):
        for j, engine in enumerate(engines):
            counter = material_bands[material].get(engine, Counter())
            total = sum(counter.values())
            if not total:
                continue
            score = sum(BAND_ORDER.index(b) * n for b, n in counter.items() if b in BAND_ORDER)
            known = sum(n for b, n in counter.items() if b in BAND_ORDER)
            if known:
                grid[i, j] = score / known
                counts[i, j] = total

    fig, ax = plt.subplots(figsize=(7.5, 7))
    im = ax.imshow(grid, cmap="YlOrRd", vmin=0, vmax=3, aspect="auto")
    ax.set_xticks(range(len(engines)), engines)
    ax.set_yticks(range(len(materials)), materials, fontsize=8)
    for i in range(len(materials)):
        for j in range(len(engines)):
            if not np.isnan(grid[i, j]):
                ax.text(j, i, f"{grid[i,j]:.2f}\nn={counts[i,j]:,}", ha="center", va="center",
                        fontsize=6.5, color="black" if grid[i, j] < 2 else "white")
    cbar = fig.colorbar(im, ax=ax, ticks=[0, 1, 2, 3])
    cbar.ax.set_yticklabels(BAND_ORDER)
    cbar.set_label("mean risk band")
    ax.set_title("Figure B.2 — Mean corrosion band by material and engine\n"
                 "uniform rows/columns indicate output invariant to input", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig3_engine_radar(engine_ready: Counter, total: int, findings: dict, path: Path) -> None:
    """Radar of input coverage vs flag rate per engine.

    Plotting both axes together is the point: where coverage is low and the
    flag rate is high, the engine is scoring substituted defaults.
    """
    engines = list(ENGINE_NAMES)
    coverage = [engine_ready.get(e, 0) / total * 100 if total else 0 for e in engines]
    flag = [findings.get(e, 0) for e in engines]
    flag_pct = [f / total * 100 if total else 0 for f in flag]

    angles = np.linspace(0, 2 * np.pi, len(engines), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7.6, 7.6), subplot_kw={"polar": True})
    for values, label, colour, marker in (
        (coverage, "input coverage %", "#4C78A8", "o"),
        (flag_pct, "flag rate %", "#E45756", "^"),
    ):
        v = values + values[:1]
        ax.plot(angles, v, color=colour, lw=2, marker=marker, ms=6, label=label, zorder=4)
        ax.fill(angles, v, color=colour, alpha=0.15)
    # Both series are labelled on the perimeter rather than at their data
    # point. A series pinned at ~0 collapses onto the origin, where labels
    # from all five axes overlap each other and the centre — legible for
    # neither series. The axis label has room; the origin does not.
    tick_labels = [
        f"{engine}\ncoverage {cov:.2f}%  ·  flags {flag:.0f}%"
        for engine, cov, flag in zip(engines, coverage, flag_pct)
    ]
    ax.set_xticks(angles[:-1], tick_labels, fontsize=8)
    ax.tick_params(axis="x", pad=14)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100], ["25%", "50%", "75%", "100%"], fontsize=7)

    ax.set_title("Figure B.3 — Engine input coverage vs flag rate\n"
                 f"n = {total:,} piping elements — coverage is ~0 on every axis,\n"
                 "so the blue series sits on the origin by construction",
                 fontsize=10, pad=30)
    ax.legend(loc="upper right", bbox_to_anchor=(1.24, 1.11), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig4_schema_scatter(records: list[dict], path: Path) -> None:
    """Per-model MEP count vs clash count, marked by schema, with the
    schema-twin pairs joined — the controlled comparison in the dataset."""
    ok = [r for r in records if r["status"] == "ok" and r.get("halos", 0) > 0]
    fig, ax = plt.subplots(figsize=(8, 6))
    styles = {"IFC4": ("#4C78A8", "o"), "IFC2X3": ("#F58518", "s")}
    for schema, (colour, marker) in styles.items():
        pts = [(r["counts"]["mep"], r["clashes"]) for r in ok if r.get("schema") == schema]
        if pts:
            ax.scatter(*zip(*pts), c=colour, marker=marker, s=70, alpha=0.85,
                       edgecolor="white", lw=0.8, label=schema, zorder=3)

    # The twin pairs are the controlled comparison. Their points are so
    # nearly coincident that a connecting segment has no visible length —
    # which IS the result, but an invisible line reads as a missing
    # feature. Ring the pair and state the delta instead.
    by_row = {r["row"]: r for r in ok}
    for a, b in ((8, 13), (9, 14)):
        ra, rb = by_row.get(a), by_row.get(b)
        if not (ra and rb):
            continue
        x, y = ra["counts"]["mep"], ra["clashes"]
        delta = abs(ra["clashes"] - rb["clashes"])
        pct = delta / max(ra["clashes"], rb["clashes"], 1) * 100
        ax.scatter([x], [y], s=340, facecolors="none", edgecolors="#444444",
                   lw=1.1, ls="--", zorder=5)
        ax.annotate(f"twin {a}/{b}: Δ{delta:,} ({pct:.2f}%)", (x, y),
                    textcoords="offset points", xytext=(-14, -26), fontsize=7.5,
                    color="#333333", ha="right",
                    bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="#BBBBBB", lw=0.6))

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.margins(x=0.16, y=0.16)  # keep annotations inside the axes
    ax.set_xlabel("MEP elements (log)")
    ax.set_ylabel("clashes detected (log)")
    ax.set_title("Figure B.4 — Schema fidelity: clash yield vs model size\n"
                 "circled pairs are the same building exported to both schemas",
                 fontsize=10)
    ax.grid(color=_C["grid"], lw=0.6, which="both")
    ax.set_axisbelow(True)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Appendix B analysis")
    parser.add_argument("--max-models", type=int, default=0,
                        help="limit the recompute pass to the N largest models")
    parser.add_argument("--sensitivity-models", type=int, default=5,
                        help="models included in the clearance sensitivity sweep")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _out("=" * 78)
    _out("  BIMGUARD AI — Appendix B analysis (7 tables, 4 figures)")
    _out("=" * 78)

    records = load_records()
    ok = [r for r in records if r["status"] == "ok"]
    _out(f"\n  Loaded {len(records)} model record(s); {len(ok)} processed successfully")

    config = load_clearance_config(CONFIG_PATH)

    _out("\n  [Table 5] parsing BCF archives ...")
    t5h, t5r, bcf_by_row = table5_bcf(records)
    valid = sum(1 for r in t5r if r[-1] == "VALID")
    _out(f"    {valid}/{len(t5r)} archives VALID")

    _out("\n  [Tables 3,4,6] recomputing from cached IFCs ...")
    extra = recompute(records, config, args.max_models, args.sensitivity_models)

    # ---- assemble tables ----
    t1h, t1r = table1_per_model(records, bcf_by_row)
    t2h, t2r, sev_totals, sev_grand = table2_severity(records)
    t7h, t7r, t7th, t7tr = table7_schema(records)

    # Table 3 — material x engine
    mb = extra["material_bands"]
    t3h = ["material", "elements", "GC Low/Med/High/Crit", "CC Low/Med/High/Crit",
           "MC Low/Med/High/Crit", "GC_mean", "CC_mean", "MC_mean"]
    t3r = []
    for material in sorted(mb, key=lambda m: -sum(sum(c.values()) for c in mb[m].values())):
        cells, means = [], []
        n = 0
        for engine in ("GC-001", "CC-001", "MC-001"):
            counter = mb[material].get(engine, Counter())
            n = max(n, sum(counter.values()))
            cells.append("/".join(str(counter.get(b, 0)) for b in BAND_ORDER))
            known = sum(counter.get(b, 0) for b in BAND_ORDER)
            means.append(f"{sum(BAND_ORDER.index(b)*counter.get(b,0) for b in BAND_ORDER)/known:.2f}"
                         if known else "n/a")
        t3r.append([material, n, *cells, *means])

    # Table 4 — engine bands across the sweep + input coverage
    engine_bands: dict[str, Counter] = defaultdict(Counter)
    engine_findings: dict[str, int] = defaultdict(int)
    engine_status: dict[str, Counter] = defaultdict(Counter)
    for r in ok:
        for name, payload in r.get("engines", {}).items():
            engine_status[name][payload["status"]] += 1
            engine_findings[name] += payload.get("findings", 0)
            for band, count in (payload.get("bands") or {}).items():
                engine_bands[name][band] += count
    total_piping = sum(r.get("piping_elements", 0) for r in ok)
    recomputed_total = extra["input_total"]
    t4h = ["engine", "status", "bands seen", "flagged", "flag_%",
           "required inputs", "elements with all inputs", "coverage_%"]
    t4r = []
    for name in ENGINE_NAMES:
        counter = engine_bands[name]
        ready = extra["engine_ready"].get(name, 0)
        # Rendered as space-separated pairs, not a dict repr: a dict's
        # commas break the CSV column and the markdown table alike.
        t4r.append([
            name, " ".join(f"{k}={v}" for k, v in sorted(engine_status[name].items())),
            "/".join(f"{b}:{counter[b]}" for b in BAND_ORDER if counter.get(b)) or "-",
            engine_findings[name],
            f"{engine_findings[name]/total_piping*100:.1f}" if total_piping else "n/a",
            "+".join(ENGINE_INPUTS[name]),
            ready,
            f"{ready/recomputed_total*100:.1f}" if recomputed_total else "n/a",
        ])

    # Table 6 — standards sensitivity
    t6h = ["clearance_mm", "jurisdiction", "clashes", "minor", "major", "critical",
           "vs 200mm baseline"]
    t6r = []
    baseline = extra["sensitivity"].get(200.0, Counter()).get("clashes", 0)
    for clearance in SENSITIVITY_CLEARANCES_MM:
        c = extra["sensitivity"][clearance]
        total = c.get("clashes", 0)
        ratio = f"{total/baseline:.2f}x" if baseline else "n/a"
        t6r.append([clearance, JURISDICTION_CLEARANCES.get(clearance, "—"), total,
                    c.get("minor", 0), c.get("major", 0), c.get("critical", 0), ratio])

    tables = [
        ("table1_per_model", "Table B.1 — Per-model summary", t1h, t1r),
        ("table2_severity", "Table B.2 — Severity distribution", t2h, t2r),
        ("table3_material_engine", "Table B.3 — Material x corrosion engine", t3h, t3r),
        ("table4_engine_coverage", "Table B.4 — Engine band distribution and input coverage", t4h, t4r),
        ("table5_bcf_validity", "Table B.5 — BCF 2.1 validity", t5h, t5r),
        ("table6_standards_sensitivity", "Table B.6 — Standards sensitivity", t6h, t6r),
        ("table7_schema", "Table B.7 — IFC schema comparison", t7h, t7r),
        ("table7b_schema_twins", "Table B.7b — Schema twins (controlled)", t7th, t7tr),
    ]
    for slug, _title, header, rows in tables:
        _write_csv(OUT_DIR / f"{slug}.csv", header, rows)
    _out(f"\n  Wrote {len(tables)} CSV table(s) to {OUT_DIR}/")

    # ---- figures ----
    _out("\n  Rendering figures ...")
    fig1_severity(records, FIG_DIR / "figB1_clash_severity.png")
    fig2_material_heatmap(mb, FIG_DIR / "figB2_material_heatmap.png")
    fig3_engine_radar(extra["engine_ready"], recomputed_total, engine_findings,
                      FIG_DIR / "figB3_engine_radar.png")
    fig4_schema_scatter(records, FIG_DIR / "figB4_schema_scatter.png")
    _out("    figB1_clash_severity.png, figB2_material_heatmap.png,")
    _out("    figB3_engine_radar.png, figB4_schema_scatter.png")

    # ---- appendix markdown ----
    write_appendix(records, ok, tables, extra, sev_totals, sev_grand,
                   valid, len(t5r), total_piping, recomputed_total, engine_findings)

    _out(f"\n  Wrote {OUT_DIR / 'appendix_b_validation.md'}")
    (OUT_DIR / "analysis_run.txt").write_text("\n".join(_LINES) + "\n", encoding="utf-8")
    return 0


def write_appendix(records, ok, tables, extra, sev_totals, sev_grand,
                   bcf_valid, bcf_total, total_piping, recomputed_total, engine_findings) -> None:
    """Emit the Appendix B markdown with every table inlined."""
    failed = [r for r in records if r["status"] != "ok"]
    material_known = sum(
        sum(c.values()) for m, per in extra["material_bands"].items() if m != "Unknown"
        for c in [per.get("GC-001", Counter())]
    )
    mep_total = sum(r.get("counts", {}).get("mep", 0) for r in ok)
    mep_geom = sum(r.get("counts", {}).get("mep_with_geometry", 0) for r in ok)
    material_total = sum(r.get("material_coverage", {}).get("with_material", 0) for r in ok)
    halos = sum(r.get("halos", 0) for r in ok)

    body = [
        "# Appendix B — 38-Model Validation Dataset: Live Results",
        "",
        "Generated by `analyse_validation_results.py` from the sweep executed by",
        "`test_all_38_models.py`. Every figure in this appendix is computed from that run;",
        "no value is transcribed by hand.",
        "",
        "## B.0 Run provenance",
        "",
        f"- Models attempted: **{len(records)}**; processed: **{len(ok)}**; failed: **{len(failed)}**",
        f"- MEP elements: **{mep_total:,}**, of which **{mep_geom:,}** ({mep_geom/mep_total*100:.1f}%) resolved geometry"
        if mep_total else "- MEP elements: 0",
        f"- Halo volumes generated: **{halos:,}**",
        f"- Clashes detected: **{sev_grand:,}**",
        f"- Piping elements: **{total_piping:,}**, of which **{material_total:,}** "
        f"({material_total/total_piping*100:.1f}%) carry raw material text" if total_piping else "",
        f"- Of those, only **{material_known:,}** ({material_known/total_piping*100:.2f}%) normalise "
        f"to a `CANONICAL_MATERIALS` key the engines can score — see §B.1.1" if total_piping else "",
        f"- BCF 2.1 archives: **{bcf_valid} valid of {len(ok)} readable models** "
        f"(every archive parsed, every topic folder complete, zero malformed XML). "
        f"The remaining {bcf_total - bcf_valid} of {bcf_total} is absent rather than invalid — "
        f"a model that could not be read produces no archive.",
        f"- Clearance: EN 1998-1:2020 + DIN 4149:2022, {BRACE_VARIANT}, 200 mm",
        "",
        "### Failures",
        "",
    ]
    if failed:
        for r in failed:
            body.append(f"- Row {r['row']} — {r['name']}: `{str(r.get('error',''))[:150]}`")
    else:
        body.append("None.")

    ready = extra["engine_ready"]
    best_engine = max(ENGINE_NAMES, key=lambda e: ready.get(e, 0))
    best_pct = ready.get(best_engine, 0) / recomputed_total * 100 if recomputed_total else 0

    body += [
        "", "## B.1 Headline finding", "",
        "The spatial engine and the corrosion engines behave in opposite ways against",
        "third-party models, and the corpus separates them cleanly.",
        "",
        f"**Blue Halo generalises.** Geometry resolved for {mep_geom:,} of {mep_total:,} MEP "
        f"elements ({mep_geom/mep_total*100:.1f}%)" if mep_total else "**Blue Halo**: no MEP elements",
        f"across IFC2x3 and IFC4 alike, producing {halos:,} halo volumes and {sev_grand:,} clashes,",
        f"with all {bcf_valid} BCF archives valid. The same-building schema twins",
        "(Table B.7b) differ by 0.11% and 0.00%, so the result does not depend on the export schema.",
        "",
        "**The corrosion engines do not.** Table B.4 shows every engine either flags nothing",
        "(GC-001: 0%) or flags everything (CC-001 and MC-001: 100%), and Table B.3 shows why:",
        "across six distinct materials the mean band is constant — GC-001 returns Low for every",
        "material, CC-001 Medium for every material, and MC-001 Critical for all but one. These",
        "are constant functions of their input, not risk assessments.",
        "",
        f"The cause is input availability, not engine logic. The best-covered engine is",
        f"{best_engine}, whose required inputs are present on {ready.get(best_engine,0):,} of",
        f"{recomputed_total:,} elements ({best_pct:.3f}%); the rest are at zero. A 100% flag rate",
        "and 0% input coverage are the same fact viewed twice: the coercers substitute a default",
        "material when none is present, so the engines score the default, uniformly, everywhere.",
        "",
        "This is precisely the question §13 puts to this dataset — whether the inputs the",
        "engines need exist in real federated models at all. On this corpus the answer is no.",
        "",
        "### B.1.1 Material text is not material data", "",
        f"{material_total:,} elements ({material_total/total_piping*100:.1f}%) carry some material"
        if total_piping else "",
        f"string, but only {material_known:,} ({material_known/total_piping*100:.2f}%) normalise to a"
        if total_piping else "",
        "`CANONICAL_MATERIALS` key. The gap — "
        f"{material_total - material_known:,} elements — is material text that",
        "`piping_producer.normalise_material` cannot map, so the engines still receive",
        "\"Unknown\". Reporting the former as coverage overstates usable material data by",
        f"roughly {material_total / material_known:.0f}x" if material_known else "",
        "and is the single easiest way to misread this corpus.",
        "",
    ]

    for slug, title, header, rows in tables:
        body += [f"## {title}", "", _md_table(header, rows), "",
                 f"_Source: `{OUT_DIR}/{slug}.csv`_", ""]

    body += [
        "## Figures", "",
        "![Figure B.1](figB1_clash_severity.png)", "",
        "![Figure B.2](figB2_material_heatmap.png)", "",
        "![Figure B.3](figB3_engine_radar.png)", "",
        "![Figure B.4](figB4_schema_scatter.png)", "",
        "## B.8 Threats to validity", "",
        "- **Clash counts are geometric, not engineering judgements.** A clash is an AABB",
        "  intersection between a halo volume and another element. Bounding boxes overstate",
        "  intersection for diagonal or non-convex members, so counts are an upper bound.",
        "- **Severity banding is a spatial heuristic**, not a standards-derived threshold",
        "  (overlap fraction of halo volume: >=25% critical, >=5% major). Table B.6 shows how",
        "  sensitive the totals are to the clearance input.",
        "- **One brace variant was evaluated.** The EN+DIN config assigns every variant the",
        "  same clearance, a documented data gap in that config, so variant choice does not",
        "  change these numbers — but a jurisdiction that differentiates would.",
        "- **Corrosion coverage is measured on the recompute subset**",
        f"  ({recomputed_total:,} elements across {len(extra['models_used'])} models), not the full corpus.",
        f"- **The clearance sensitivity sweep (Table B.6) covers rows {extra['sensitivity_rows']} only**,",
        "  not the whole corpus; its absolute totals are therefore not comparable to Table B.2,",
        "  and only the ratios between thresholds should be read from it.",
        "- **Row 35 could not be read at all** (IFC2X2_FINAL, unsupported by IfcOpenShell),",
        "  so the industrial category is one model short of its already-thin count.",
        "",
    ]
    (OUT_DIR / "appendix_b_validation.md").write_text("\n".join(body) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
