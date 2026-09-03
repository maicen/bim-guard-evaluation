"""
test_all_38_models.py
------------------------------------------------
BIMGUARD AI — full validation sweep across the 38-model verified IFC dataset.

Drives every stage of the pipeline over each model in
"BIMGUARD AI Validation Dataset — Verified Downloadable IFC Models.md":

    download (cached)  ->  ifcopenshell.open
      ->  extract pipes / ducts / structural elements
      ->  Phase 1  generate_halo_volume + clash detection
      ->  Module 4 corrosion engines (GC-001, CC-001, MC-001, MM-001, XM-001)
      ->  Phase 4  BCF 2.1 export
      ->  aggregate

Mirrors score_rule_extraction.py / test_real_ifc_pipeline.py in style
(plain script, print()-based, no pytest).

DESIGN NOTES

    Resumability
        Downloads are cached under data/validation_models/ and per-model
        results under data/validation_results/. Re-running skips work that
        already succeeded, so a sweep interrupted at model 25 resumes there
        rather than re-downloading ~1 GB. --refresh forces re-computation.

    Geometry comes from ifcopenshell.geom, not the fast vertex path
        halo_volume_generator.element_bbox_mm reads vertices straight off
        the shape representation, handling only tessellated face sets,
        polylines, and swept-solid extrusion axes. Real models overwhelm-
        ingly use IfcMappedItem (Revit/ArchiCAD) and IfcFacetedBrep, for
        which that function returns None — measured on this dataset, it
        resolves 0 of 87 elements in the AISC steel models. Zero geometry
        means zero halos, which would make the whole sweep vacuous.

        This harness therefore evaluates real geometry through
        ifcopenshell.geom's multithreaded iterator, which handles every
        representation type. Two settings matter and are easy to get wrong:
        `use-world-coords` MUST be set, or every element is returned in
        local coordinates centred near the origin and every element appears
        to clash with every other; and the iterator emits SI metres
        regardless of the file's declared unit, so results are scaled by
        1000 to reach this codebase's millimetre convention (verified
        against data/test_hospital_mep_scenario.ifc, whose true extents are
        known exactly).

    Clash detection is spatially pre-filtered
        halo_volume_generator.detect_halo_clash does no broad-phase
        filtering — its docstring states candidates are expected to be
        pre-filtered upstream. Naively pairing every element against every
        other is O(n^2): the West Riverside mechanical model alone carries
        ~8,700 duct/pipe segments, i.e. ~76M pair tests, which does not
        finish in reasonable time. _SpatialGrid below buckets candidate
        bounding boxes into a uniform grid so each halo only tests the
        elements sharing its cells. Results are identical to the brute-force
        pairing; only the wasted comparisons are removed.

        It also calls detect_halo_clash_against_geometry (the pure core)
        rather than detect_halo_clash (the IFC wrapper), because the wrapper
        re-extracts every candidate's geometry on every call — O(n^2)
        geometry extraction on top of the O(n^2) pairing. Geometry is
        extracted once per element here and reused.

    Corrosion findings are reported against material coverage
        The Module 4 coercers substitute a default material when an element
        carries none (_coerce_cc_element defaults to "stainless_steel"),
        so a model with no material data yields a Medium crevice band for
        every element — 861 of 861 on the fire-alarm model, all spurious.
        Each engine result therefore carries `elements_with_material`
        alongside its findings so a flagged count is never read as
        evidence without the data quality that produced it.

    Caps are reported, never silent
        Very large models are capped by --max-elements. Whenever a cap
        truncates a model, the count dropped is recorded in that model's
        result JSON and printed, so a partial sweep is never mistaken for
        full coverage.

    Engine availability is measured, not assumed
        Only GC-001, CC-001 and MC-001 are wired into
        engine_registry.register_default_engines(). MM-001 and XM-001 exist
        in comparator but their load_rule_pack() validators expect a
        top-level pack shape that the shipped, APPROVED-v1.0 packs in
        data/rulesets/ do not have (those nest everything under
        "parameters"), and their compare() reads element.get_property(),
        which PipingElement does not implement. This harness calls each
        engine's real entry point and records precisely why an engine did
        not produce findings rather than reporting a silent zero. See
        ENGINE STATUS in the final summary.

Usage:
    uv run python test_all_38_models.py                 # full sweep (~1 GB)
    uv run python test_all_38_models.py --smoke         # 3 smallest models
    uv run python test_all_38_models.py --limit 5
    uv run python test_all_38_models.py --only 5,8,12
    uv run python test_all_38_models.py --refresh       # recompute cached
    uv run python test_all_38_models.py --no-download   # only cached files
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import re
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional
import os

# Resolve evaluation dir and core bim-guard repo path
REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
BIMGUARD_CORE = Path(os.getenv("BIMGUARD_PATH", str(REPO_ROOT.parent / "bim-guard")))

for p in [EVAL_DIR, REPO_ROOT, BIMGUARD_CORE, Path(".")]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

import ifcopenshell  # noqa: E402
import ifcopenshell.geom  # noqa: E402

from app.modules.ifc_reader.piping_producer import (  # noqa: E402
    media_for_system,
    produce_piping_elements_from_model,
)
from app.modules.blue_halo.halo_volume_generator import (  # noqa: E402
    BoundingBox,
    ClashReport,
    ClearanceConfig,
    ElementGeometry,
    HaloVolume,
    Point3D,
    detect_halo_clash_against_geometry,
    generate_halo_volume_from_geometry,
    load_clearance_config,
    unit_scale_to_mm,
)
from app.modules.comparator.compliance_runner import (  # noqa: E402
    run_crevice_compliance_check,
    run_galvanic_compliance_check,
    run_mic_compliance_check,
)
from app.modules.comparator.issue_adapter import IssueIdAllocator  # noqa: E402
from app.modules.reporter.blue_halo_bcf_exporter import (  # noqa: E402
    generate_bcf_zip_from_halo_clashes,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATASET_DOC = Path("BIMGUARD AI Validation Dataset — Verified Downloadable IFC Models.md")
CONFIG_PATH = Path("hermes_case_study_and_config.json")
DOWNLOAD_DIR = Path("data/validation_models")
RESULT_DIR = Path("data/validation_results")
BCF_DIR = Path("data/validation_bcf")
SUMMARY_JSON = Path("validation_sweep_summary.json")
SUMMARY_TXT = Path("validation_sweep_summary.txt")

EXPECTED_MODEL_COUNT = 38
BRACE_VARIANT = "angle_fire"

MEP_CLASSES = ("IfcPipeSegment", "IfcDuctSegment", "IfcFlowSegment")
STRUCTURAL_CLASSES = ("IfcColumn", "IfcBeam", "IfcSlab", "IfcWall", "IfcMember", "IfcFooting")

DOWNLOAD_TIMEOUT_S = 300
_USER_AGENT = "BIMGUARD-AI-validation/1.0 (+academic research; IFC compliance testing)"

_LINES: list[str] = []


def _out(line: str = "") -> None:
    print(line, flush=True)
    _LINES.append(line)


# ═══════════════════════════════════════════════════════════════════════════
# Dataset catalogue — parsed from the markdown doc (single source of truth)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ModelSpec:
    row: int
    name: str
    building_type: str
    url: str
    size_mb: float
    ifc_version: str
    material_data: str
    category: str

    @property
    def is_zip(self) -> bool:
        return self.url.lower().split("?")[0].endswith(".zip")

    @property
    def slug(self) -> str:
        base = re.sub(r"[^A-Za-z0-9]+", "_", self.name).strip("_")[:60]
        return f"{self.row:02d}_{base}"


_CATEGORY_BY_HEADING = {
    "Hospital": "hospital",
    "Office": "office",
    "Industrial": "industrial",
}

# Matches the first markdown link whose target looks like a URL, e.g.
# "[Download](https://...)" — the Source column also holds links, so the
# Download column is located positionally rather than by regex over the row.
_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")


def parse_dataset(path: Path = DATASET_DOC) -> list[ModelSpec]:
    """Parse the validation-dataset markdown into ModelSpecs.

    The markdown table is the canonical dataset definition, so it is parsed
    rather than duplicated into a Python literal that could drift from it.
    Rows whose leading cell is not an integer (header/separator rows) are
    skipped.

    Raises:
        FileNotFoundError: If the dataset doc is missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"validation dataset doc not found: {path}")

    specs: list[ModelSpec] = []
    category = "unknown"

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped.startswith("## Part"):
            for key, value in _CATEGORY_BY_HEADING.items():
                if key.lower() in stripped.lower():
                    category = value
                    break
            continue

        if not stripped.startswith("|"):
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 9 or not cells[0].isdigit():
            continue

        # Column order per the doc's table header:
        # # | Model Name | Building Type | Systems | Size (MB) | Source
        #   | Download Link | IFC Ver. | Material Data | Notes
        download_links = _LINK_RE.findall(cells[6])
        if not download_links:
            continue

        size_match = re.search(r"[\d.]+", cells[4])
        specs.append(
            ModelSpec(
                row=int(cells[0]),
                name=cells[1],
                building_type=cells[2],
                url=download_links[0][1],
                size_mb=float(size_match.group()) if size_match else 0.0,
                ifc_version=cells[7],
                material_data=cells[8],
                category=category,
            )
        )

    return specs


# ═══════════════════════════════════════════════════════════════════════════
# Download layer
# ═══════════════════════════════════════════════════════════════════════════


def _ssl_context() -> Optional[Any]:
    """Return an SSL context backed by certifi's CA bundle, or None.

    Several dataset hosts (tib.eu, habitatge.gva.es) chain to roots absent
    from this machine's system trust store, so the stdlib default rejects
    them with CERTIFICATE_VERIFY_FAILED even though the certificates are
    valid — measured as 6 of 38 models lost. certifi ships a complete,
    current bundle and verifies them cleanly.

    This strengthens verification rather than weakening it: certificates
    are still fully validated, just against a better root set. Verification
    is never disabled.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None  # fall back to the stdlib default


def _download(url: str, dest: Path) -> None:
    """Fetch `url` to `dest` atomically (via a .part file)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(
        request, timeout=DOWNLOAD_TIMEOUT_S, context=_ssl_context()
    ) as response:
        with open(part, "wb") as handle:
            while chunk := response.read(1 << 20):
                handle.write(chunk)
    part.replace(dest)


def _first_ifc_in_zip(archive: Path, extract_root: Path) -> Optional[Path]:
    """Extract the largest .ifc member of `archive` and return its path.

    The dataset's zip rows bundle several discipline files; the largest is
    taken as the most content-rich, and the choice is reported by the
    caller so it is never a silent pick.
    """
    extract_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        members = [m for m in zf.infolist() if m.filename.lower().endswith(".ifc")]
        if not members:
            return None
        member = max(members, key=lambda m: m.file_size)
        target = extract_root / Path(member.filename).name
        if not target.exists():
            with zf.open(member) as src, open(target, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
        return target


def ensure_local_ifc(spec: ModelSpec, *, allow_download: bool) -> tuple[Optional[Path], str]:
    """Return (path_to_ifc, note), downloading and unzipping as needed."""
    raw_name = spec.slug + (".zip" if spec.is_zip else ".ifc")
    raw_path = DOWNLOAD_DIR / raw_name

    if not raw_path.exists():
        if not allow_download:
            return None, "not cached and --no-download set"
        try:
            _download(spec.url, raw_path)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as exc:
            return None, f"download failed: {type(exc).__name__}: {exc}"

    if not spec.is_zip:
        return raw_path, f"cached {raw_path.stat().st_size / 1e6:.1f} MB"

    extracted = _first_ifc_in_zip(raw_path, DOWNLOAD_DIR / spec.slug)
    if extracted is None:
        return None, "zip contains no .ifc member"
    return extracted, f"extracted largest .ifc from zip: {extracted.name}"


# ═══════════════════════════════════════════════════════════════════════════
# Geometry — real evaluation via ifcopenshell.geom
# ═══════════════════════════════════════════════════════════════════════════

# ifcopenshell.geom emits SI metres irrespective of the file's declared
# length unit; this codebase works in millimetres throughout.
_GEOM_METRES_TO_MM = 1000.0


def world_bboxes_mm(
    model: Any,
    entities: list,
    *,
    threads: int = 0,
) -> dict[str, BoundingBox]:
    """Compute world-space bounding boxes in mm for `entities`.

    Uses ifcopenshell.geom's multithreaded iterator so every representation
    type resolves (IfcMappedItem, IfcFacetedBrep, swept solids, tessella-
    tions), not just the subset halo_volume_generator's fast vertex reader
    handles. See the module docstring for why that distinction is load-
    bearing rather than an optimisation.

    Args:
        model: The open ifcopenshell model.
        entities: Entities to evaluate; an empty list short-circuits.
        threads: Worker threads; defaults to the machine's CPU count.

    Returns:
        {GlobalId: BoundingBox} for every entity whose geometry resolved.
        Entities with no usable shape are simply absent from the mapping.
    """
    if not entities:
        return {}

    settings = ifcopenshell.geom.settings()
    # Without this every shape comes back in local coordinates near the
    # origin, and all elements appear mutually coincident.
    settings.set("use-world-coords", True)

    boxes: dict[str, BoundingBox] = {}
    try:
        iterator = ifcopenshell.geom.iterator(
            settings, model, threads or multiprocessing.cpu_count(), include=entities
        )
        if not iterator.initialize():
            return boxes
        while True:
            shape = iterator.get()
            verts = shape.geometry.verts
            if verts:
                xs, ys, zs = verts[0::3], verts[1::3], verts[2::3]
                s = _GEOM_METRES_TO_MM
                boxes[shape.guid] = BoundingBox(
                    min=Point3D(min(xs) * s, min(ys) * s, min(zs) * s),
                    max=Point3D(max(xs) * s, max(ys) * s, max(zs) * s),
                )
            if not iterator.next():
                break
    except Exception:
        # A model whose geometry engine fails entirely still yields element
        # counts and corrosion results; the caller reports the empty map as
        # zero geometry rather than aborting the sweep.
        return boxes

    return boxes


# ═══════════════════════════════════════════════════════════════════════════
# Broad-phase spatial index
# ═══════════════════════════════════════════════════════════════════════════


class _SpatialGrid:
    """Uniform-grid broad phase over element bounding boxes.

    Exists purely to make clash detection tractable on large models — see
    the module docstring. Cell size is derived from the median element
    extent so it adapts to the model's scale instead of assuming one.
    """

    def __init__(self, geometries: list[ElementGeometry], cell_mm: float) -> None:
        self.cell_mm = max(cell_mm, 1.0)
        self._cells: dict[tuple[int, int, int], list[ElementGeometry]] = {}
        for geometry in geometries:
            for key in self._keys(geometry.bbox_mm):
                self._cells.setdefault(key, []).append(geometry)

    def _keys(self, bbox: BoundingBox) -> Iterable[tuple[int, int, int]]:
        c = self.cell_mm
        for i in range(int(bbox.min.x // c), int(bbox.max.x // c) + 1):
            for j in range(int(bbox.min.y // c), int(bbox.max.y // c) + 1):
                for k in range(int(bbox.min.z // c), int(bbox.max.z // c) + 1):
                    yield (i, j, k)

    def candidates(self, bbox: BoundingBox) -> list[ElementGeometry]:
        """Return the distinct elements sharing any cell with `bbox`."""
        seen: dict[str, ElementGeometry] = {}
        for key in self._keys(bbox):
            for geometry in self._cells.get(key, ()):
                seen.setdefault(geometry.element_id, geometry)
        return list(seen.values())


def _median(values: list[float]) -> float:
    if not values:
        return 1000.0
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


# ═══════════════════════════════════════════════════════════════════════════
# Corrosion engines
# ═══════════════════════════════════════════════════════════════════════════


class _EngineElement:
    """Duck-typed adapter feeding a PipingElement to the Module 4 engines.

    compliance_runner's coercers read `.GlobalId`, `.is_a()` and
    `.get_info()`. They also expect FREE-TEXT material (their own
    MATERIAL_ALIASES tables normalise "copper", "ss316", "galvanised" etc.),
    which is why material_raw is preferred over PipingElement.material:
    the latter is the CANONICAL_MATERIALS vocabulary, a deliberately
    different namespace that piping_schema warns must not be interchanged.
    """

    def __init__(self, element: Any) -> None:
        self._element = element
        self.GlobalId = element.id

    def is_a(self) -> str:
        return self._element.ifc_class

    def get_info(self) -> dict:
        e = self._element
        return {
            "material": e.material_raw or e.material,
            "paired_material": e.material_raw or e.material,
            "system_type": getattr(e.system, "value", str(e.system)),
            "zone_category": getattr(e.environment_class, "value", str(e.environment_class)),
            "floor": e.level_name or "Unknown",
            "zone": e.space_name or "Unknown",
            "operating_temp_c": e.operating_temperature_c,
            "nominal_diameter_m": (e.nominal_diameter_mm / 1000.0) if e.nominal_diameter_mm else None,
            "joint_description": getattr(e.joint_type, "value", "") if e.joint_type else "",
            "insulation_condition": e.insulation_material or "unknown",
        }


@dataclass
class EngineOutcome:
    """Per-engine result for one model.

    `elements_with_material` is carried on every outcome because a findings
    count is uninterpretable without it — see the module docstring's note on
    the coercers substituting a default material.
    """

    status: str  # "ok" | "unavailable" | "error"
    findings: int = 0
    bands: dict = field(default_factory=dict)
    reason: str = ""
    elements_scored: int = 0
    elements_with_material: int = 0       # normalises to a CANONICAL_MATERIALS key
    elements_with_material_text: int = 0  # carries any raw material text


def _run_band_engine(name: str, runner, elements: list) -> EngineOutcome:
    """Run one of the GC/CC/MC band engines across a model's elements."""
    bands: dict[str, int] = {}
    errors = 0
    for element in elements:
        try:
            result = runner(_EngineElement(element))
        except Exception:
            errors += 1
            continue
        band = str(result.get("band", "Unknown"))
        bands[band] = bands.get(band, 0) + 1

    if not bands and errors:
        return EngineOutcome(status="error", reason=f"all {errors} element(s) raised", bands={})
    flagged = sum(count for band, count in bands.items() if band.upper() not in ("LOW", "UNKNOWN"))
    return EngineOutcome(
        status="ok",
        findings=flagged,
        bands=bands,
        reason=f"{errors} element(s) raised" if errors else "",
    )


def _run_path_b_engine(name: str, module, elements: list, allocator: IssueIdAllocator) -> EngineOutcome:
    """Run MM-001 / XM-001 via their real compare() entry points.

    These are expected to report unavailable against the shipped rule packs
    (see the module docstring). The real entry point is still called rather
    than assumed broken, so the day the packs or the engines are fixed this
    harness reports findings with no change here.
    """
    try:
        pack = module.load_rule_pack()
    except Exception as exc:
        return EngineOutcome(status="unavailable", reason=f"load_rule_pack(): {type(exc).__name__}: {exc}")

    issues: list = []
    for element in elements:
        try:
            issues.extend(module.compare(element, rule_pack=pack, id_allocator=allocator))
        except Exception as exc:
            return EngineOutcome(
                status="unavailable",
                reason=f"compare(): {type(exc).__name__}: {exc}",
            )
    return EngineOutcome(status="ok", findings=len(issues))


ENGINE_NAMES = ("GC-001", "CC-001", "MC-001", "MM-001", "XM-001")


def run_corrosion_engines(piping_elements: list, run_id: str) -> dict[str, EngineOutcome]:
    """Run all five corrosion engines over a model's piping elements."""
    from app.modules.comparator import cross_material, material_media

    allocator = IssueIdAllocator(run_id)

    if not piping_elements:
        # A fresh instance per engine: one shared object would alias five
        # entries onto the same mutable record.
        return {
            name: EngineOutcome(status="ok", reason="model carries no piping elements")
            for name in ENGINE_NAMES
        }

    # Two distinct measures, deliberately kept apart. An element can carry
    # material TEXT that normalise_material cannot map to a
    # CANONICAL_MATERIALS key, in which case the engines still see
    # "Unknown" and the text is of no use to them. Measured on this
    # corpus: 38,012 elements carry text but only 2,403 normalise, so
    # conflating the two overstates usable coverage by ~16x.
    with_material_text = sum(1 for e in piping_elements if (e.material_raw or "").strip())
    with_material = sum(1 for e in piping_elements if e.material != "Unknown")

    outcomes: dict[str, EngineOutcome] = {
        "GC-001": _run_band_engine("GC-001", run_galvanic_compliance_check, piping_elements),
        "CC-001": _run_band_engine("CC-001", run_crevice_compliance_check, piping_elements),
        "MC-001": _run_band_engine("MC-001", run_mic_compliance_check, piping_elements),
        "MM-001": _run_path_b_engine("MM-001", material_media, piping_elements, allocator),
        "XM-001": _run_path_b_engine("XM-001", cross_material, piping_elements, allocator),
    }
    for outcome in outcomes.values():
        outcome.elements_scored = len(piping_elements)
        outcome.elements_with_material = with_material
        outcome.elements_with_material_text = with_material_text
    return outcomes


# ═══════════════════════════════════════════════════════════════════════════
# Per-model pipeline
# ═══════════════════════════════════════════════════════════════════════════


def process_model(
    spec: ModelSpec,
    config: ClearanceConfig,
    *,
    allow_download: bool,
    max_elements: int,
) -> dict:
    """Run the full pipeline for one model, returning a result record."""
    started = time.time()
    record: dict[str, Any] = {
        "row": spec.row,
        "name": spec.name,
        "category": spec.category,
        "building_type": spec.building_type,
        "declared_size_mb": spec.size_mb,
        "url": spec.url,
        "status": "pending",
    }

    ifc_path, note = ensure_local_ifc(spec, allow_download=allow_download)
    record["acquisition"] = note
    if ifc_path is None:
        record.update(status="download_failed", error=note, seconds=round(time.time() - started, 1))
        return record

    record["local_file"] = str(ifc_path)
    record["actual_size_mb"] = round(ifc_path.stat().st_size / 1e6, 2)

    model = ifcopenshell.open(str(ifc_path))
    record["schema"] = model.schema
    scale = unit_scale_to_mm(model)
    record["unit_scale_to_mm"] = scale

    # --- extract -----------------------------------------------------------
    def collect(classes: tuple) -> list:
        found, seen = [], set()
        for ifc_class in classes:
            try:
                entities = model.by_type(ifc_class)
            except Exception:
                continue  # class absent from this schema version
            for entity in entities:
                guid = getattr(entity, "GlobalId", None)
                if guid and guid not in seen:
                    seen.add(guid)
                    found.append(entity)
        return found

    mep_entities = collect(MEP_CLASSES)
    structural_entities = collect(STRUCTURAL_CLASSES)

    record["counts"] = {
        "mep": len(mep_entities),
        "structural": len(structural_entities),
        "total_products": len(model.by_type("IfcProduct")),
    }

    truncated = {}
    if len(mep_entities) > max_elements:
        truncated["mep_dropped"] = len(mep_entities) - max_elements
        mep_entities = mep_entities[:max_elements]
    if len(structural_entities) > max_elements:
        truncated["structural_dropped"] = len(structural_entities) - max_elements
        structural_entities = structural_entities[:max_elements]
    record["truncated"] = truncated

    # --- geometry (evaluated once, reused by every halo) -------------------
    geom_started = time.time()
    boxes = world_bboxes_mm(model, mep_entities + structural_entities)
    record["geometry_seconds"] = round(time.time() - geom_started, 1)

    def geometries_for(entities: list) -> list[ElementGeometry]:
        out = []
        for entity in entities:
            bbox = boxes.get(entity.GlobalId)
            if bbox is None:
                continue
            out.append(
                ElementGeometry(
                    element_id=str(entity.GlobalId),
                    ifc_class=entity.is_a(),
                    bbox_mm=bbox,
                )
            )
        return out

    mep_geoms = geometries_for(mep_entities)
    structural_geoms = geometries_for(structural_entities)
    all_geoms = mep_geoms + structural_geoms
    record["counts"]["mep_with_geometry"] = len(mep_geoms)
    record["counts"]["structural_with_geometry"] = len(structural_geoms)

    # --- Phase 1: halos + clashes ------------------------------------------
    rule = config.rules[BRACE_VARIANT]
    halos: list[HaloVolume] = []
    clashes: list[ClashReport] = []

    if all_geoms:
        extents = [max(g.bbox_mm.size) for g in all_geoms]
        grid = _SpatialGrid(all_geoms, cell_mm=max(_median(extents), rule.base_clearance_mm * 4))

        for geometry in mep_geoms:
            halo = generate_halo_volume_from_geometry(geometry, rule.brace_type, rule)
            halos.append(halo)
            nearby = grid.candidates(halo.halo_bbox_mm)
            clashes.extend(detect_halo_clash_against_geometry(halo, nearby))

    severity_counts: dict[str, int] = {}
    for clash in clashes:
        severity_counts[clash.severity] = severity_counts.get(clash.severity, 0) + 1

    record["halos"] = len(halos)
    record["clashes"] = len(clashes)
    record["clash_severity"] = severity_counts

    # --- corrosion engines --------------------------------------------------
    try:
        piping_elements = produce_piping_elements_from_model(model, source_path=str(ifc_path))
    except Exception as exc:
        piping_elements = []
        record["piping_producer_error"] = f"{type(exc).__name__}: {exc}"

    if len(piping_elements) > max_elements:
        record.setdefault("truncated", {})["piping_dropped"] = len(piping_elements) - max_elements
        piping_elements = piping_elements[:max_elements]

    record["piping_elements"] = len(piping_elements)
    record["media_seen"] = sorted({media_for_system(e.system) for e in piping_elements})

    outcomes = run_corrosion_engines(piping_elements, run_id=f"row{spec.row}")
    record["engines"] = {
        name: {
            "status": o.status,
            "findings": o.findings,
            "bands": o.bands,
            "reason": o.reason,
            "elements_scored": o.elements_scored,
            "elements_with_material": o.elements_with_material,
            "elements_with_material_text": o.elements_with_material_text,
        }
        for name, o in outcomes.items()
    }
    record["material_coverage"] = {
        "piping_elements": len(piping_elements),
        "with_material": next(iter(outcomes.values())).elements_with_material,
        "with_material_text": next(iter(outcomes.values())).elements_with_material_text,
    }

    # --- Phase 4: BCF export ------------------------------------------------
    BCF_DIR.mkdir(parents=True, exist_ok=True)
    bcf_path = BCF_DIR / f"{spec.slug}.bcf"
    try:
        zip_bytes = generate_bcf_zip_from_halo_clashes(
            clashes,
            project_id=f"BIMGUARD-VALIDATION-{spec.row:02d}",
            halos={h.id: h for h in halos},
            project_name=f"BIMGUARD AI validation — {spec.name}",
        )
        bcf_path.write_bytes(zip_bytes)
        with zipfile.ZipFile(bcf_path) as zf:
            entries = len(zf.namelist())
        record["bcf"] = {"path": str(bcf_path), "bytes": len(zip_bytes), "entries": entries}
    except Exception as exc:
        record["bcf"] = {"error": f"{type(exc).__name__}: {exc}"}

    record["status"] = "ok"
    record["seconds"] = round(time.time() - started, 1)
    return record


# ═══════════════════════════════════════════════════════════════════════════
# Aggregation
# ═══════════════════════════════════════════════════════════════════════════


def aggregate(records: list[dict]) -> dict:
    ok = [r for r in records if r["status"] == "ok"]
    engine_status: dict[str, dict[str, int]] = {}
    for record in ok:
        for name, payload in record.get("engines", {}).items():
            bucket = engine_status.setdefault(name, {})
            bucket[payload["status"]] = bucket.get(payload["status"], 0) + 1

    severities: dict[str, int] = {}
    for record in ok:
        for band, count in record.get("clash_severity", {}).items():
            severities[band] = severities.get(band, 0) + count

    return {
        "models_total": len(records),
        "models_ok": len(ok),
        "models_failed": len(records) - len(ok),
        "mep_elements": sum(r.get("counts", {}).get("mep", 0) for r in ok),
        "mep_with_geometry": sum(r.get("counts", {}).get("mep_with_geometry", 0) for r in ok),
        "structural_elements": sum(r.get("counts", {}).get("structural", 0) for r in ok),
        "structural_with_geometry": sum(
            r.get("counts", {}).get("structural_with_geometry", 0) for r in ok
        ),
        "piping_elements": sum(r.get("piping_elements", 0) for r in ok),
        "piping_with_material": sum(
            r.get("material_coverage", {}).get("with_material", 0) for r in ok
        ),
        "piping_with_material_text": sum(
            r.get("material_coverage", {}).get("with_material_text", 0) for r in ok
        ),
        # Records cached before the material metric was split carry only
        # "with_material", and under the OLD semantics that value counted
        # raw material TEXT, not successful normalisation. Printing it
        # under the new label silently overstates usable coverage ~16x, so
        # legacy records are counted and the summary says so rather than
        # relabelling them.
        "legacy_material_records": sum(
            1 for r in ok if "with_material_text" not in r.get("material_coverage", {})
        ),
        "halos": sum(r.get("halos", 0) for r in ok),
        "clashes": sum(r.get("clashes", 0) for r in ok),
        "clash_severity": severities,
        "engine_status": engine_status,
        "engine_findings": {
            name: sum(r.get("engines", {}).get(name, {}).get("findings", 0) for r in ok)
            for name in ENGINE_NAMES
        },
        "truncated_models": [r["row"] for r in ok if r.get("truncated")],
        "models_with_zero_geometry": [
            r["row"]
            for r in ok
            if (r.get("counts", {}).get("mep", 0) + r.get("counts", {}).get("structural", 0)) > 0
            and (r.get("counts", {}).get("mep_with_geometry", 0)
                 + r.get("counts", {}).get("structural_with_geometry", 0)) == 0
        ],
        "seconds": round(sum(r.get("seconds", 0) for r in records), 1),
    }


def print_summary(records: list[dict], totals: dict) -> None:
    _out("\n" + "=" * 78)
    _out("  PER-MODEL RESULTS")
    _out("=" * 78)
    _out(f"  {'#':>3} {'category':10s} {'model':30s} {'MEP':>6} {'geom':>6} {'halos':>6} "
         f"{'clash':>6} {'pipe':>6} {'mat':>6}  status")
    for record in records:
        counts = record.get("counts", {})
        geom = counts.get("mep_with_geometry", 0) + counts.get("structural_with_geometry", 0)
        _out(
            f"  {record['row']:>3} {record.get('category','?'):10s} {record['name'][:30]:30s} "
            f"{counts.get('mep',0):>6} {geom:>6} {record.get('halos',0):>6} "
            f"{record.get('clashes',0):>6} {record.get('piping_elements',0):>6} "
            f"{record.get('material_coverage',{}).get('with_material',0):>6}  {record['status']}"
        )
        if record["status"] != "ok":
            _out(f"      -> {record.get('error','')[:100]}")
        if record.get("truncated"):
            _out(f"      -> CAPPED: {record['truncated']}")

    _out("\n" + "=" * 78)
    _out("  AGGREGATE")
    _out("=" * 78)
    _out(f"  models:            {totals['models_ok']}/{totals['models_total']} processed "
         f"({totals['models_failed']} failed)")
    _out(f"  MEP elements:      {totals['mep_elements']:,} "
         f"({totals['mep_with_geometry']:,} with resolved geometry)")
    _out(f"  structural:        {totals['structural_elements']:,} "
         f"({totals['structural_with_geometry']:,} with resolved geometry)")
    _out(f"  piping elements:   {totals['piping_elements']:,} "
         + (f"({totals['piping_with_material']:,} normalise to a known material; "
            f"{totals.get('piping_with_material_text', 0):,} carry raw material text)"
            if not totals.get("legacy_material_records")
            else f"({totals['piping_with_material']:,} carry raw material text — "
                 f"{totals['legacy_material_records']} model record(s) predate the "
                 "material-metric split, so the normalised count is unavailable; "
                 "re-run with --refresh, or see Table A.3)"))
    _out(f"  halo volumes:      {totals['halos']:,}")
    _out(f"  clashes:           {totals['clashes']:,}  {totals['clash_severity']}")
    _out(f"  wall clock:        {totals['seconds']:,.0f}s")
    if totals["truncated_models"]:
        _out(f"  CAPPED models:     rows {totals['truncated_models']} (see per-model 'truncated')")
    if totals["models_with_zero_geometry"]:
        _out(f"  ZERO GEOMETRY:     rows {totals['models_with_zero_geometry']} had elements but "
             "no resolvable shapes")

    _out("\n" + "=" * 78)
    _out("  ENGINE STATUS")
    _out("=" * 78)
    _out("  (flagged counts are only interpretable against material coverage above —"
         " see the module docstring)")
    for name in ENGINE_NAMES:
        status = totals["engine_status"].get(name, {})
        findings = totals["engine_findings"].get(name, 0)
        _out(f"  {name}: {status}  flagged={findings:,}")
        reasons = {
            r["engines"][name]["reason"]
            for r in records
            if r.get("engines", {}).get(name, {}).get("reason")
        }
        for reason in sorted(reasons)[:2]:
            _out(f"      reason: {reason[:110]}")


# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="BIMGUARD AI 38-model validation sweep")
    parser.add_argument("--smoke", action="store_true", help="run the 3 smallest models only")
    parser.add_argument("--limit", type=int, default=0, help="process at most N models")
    parser.add_argument("--only", type=str, default="", help="comma-separated row numbers")
    parser.add_argument("--refresh", action="store_true", help="recompute cached results")
    parser.add_argument("--no-download", action="store_true", help="use cached files only")
    parser.add_argument("--max-elements", type=int, default=20000,
                        help="per-class element cap (reported when it truncates)")
    args = parser.parse_args()

    _out("=" * 78)
    _out("  BIMGUARD AI — validation sweep across the verified IFC dataset")
    _out("=" * 78)

    specs = parse_dataset()
    _out(f"\n  Parsed {len(specs)} model(s) from {DATASET_DOC}")
    if len(specs) != EXPECTED_MODEL_COUNT:
        _out(f"  WARNING: expected {EXPECTED_MODEL_COUNT} models, parsed {len(specs)} — "
             "the markdown table may have changed shape")

    if args.only:
        wanted = {int(x) for x in args.only.split(",") if x.strip().isdigit()}
        specs = [s for s in specs if s.row in wanted]
    elif args.smoke:
        specs = sorted(specs, key=lambda s: s.size_mb)[:3]
    if args.limit:
        specs = specs[: args.limit]

    total_mb = sum(s.size_mb for s in specs)
    _out(f"  Selected {len(specs)} model(s), ~{total_mb:,.0f} MB to acquire (cached files reused)")

    config = load_clearance_config(CONFIG_PATH)
    _out(f"  Config: {config.jurisdiction} (variant {BRACE_VARIANT}, "
         f"clearance {config.rules[BRACE_VARIANT].base_clearance_mm:.0f}mm)")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    for index, spec in enumerate(specs, start=1):
        cache = RESULT_DIR / f"{spec.slug}.json"
        if cache.exists() and not args.refresh:
            records.append(json.loads(cache.read_text(encoding="utf-8")))
            _out(f"\n[{index}/{len(specs)}] row {spec.row}: {spec.name} — cached, skipping")
            continue

        _out(f"\n[{index}/{len(specs)}] row {spec.row}: {spec.name} "
             f"({spec.category}, ~{spec.size_mb:.1f} MB)")
        try:
            record = process_model(
                spec, config,
                allow_download=not args.no_download,
                max_elements=args.max_elements,
            )
        except Exception as exc:
            record = {
                "row": spec.row, "name": spec.name, "category": spec.category,
                "status": "error", "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc()[-1500:],
            }

        cache.write_text(json.dumps(record, indent=2), encoding="utf-8")
        records.append(record)

        if record["status"] == "ok":
            _out(f"    OK  {record['counts']['mep']} MEP / {record['counts']['structural']} struct"
                 f" -> {record['halos']} halos, {record['clashes']} clashes,"
                 f" {record['piping_elements']} piping  [{record['seconds']}s]")
        else:
            _out(f"    {record['status'].upper()}: {str(record.get('error',''))[:120]}")

    totals = aggregate(records)
    print_summary(records, totals)

    SUMMARY_JSON.write_text(
        json.dumps({"totals": totals, "models": records}, indent=2), encoding="utf-8"
    )
    SUMMARY_TXT.write_text("\n".join(_LINES) + "\n", encoding="utf-8")
    _out(f"\n  Wrote {SUMMARY_JSON} and {SUMMARY_TXT}")
    _out(f"  BCF files: {BCF_DIR}/  |  per-model JSON: {RESULT_DIR}/")

    return 0 if totals["models_failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
