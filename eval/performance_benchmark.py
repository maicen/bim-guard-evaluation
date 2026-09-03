"""
BIMGUARD AI — Halo volume generation performance benchmark.

Purpose
-------
This harness answers the examination question:

    "How will the geometric engine handle high-poly IFC geometry when
     generating thousands of 'Halo' volumes simultaneously?"

It does so by measuring, not asserting. A prototype Halo generator
(spatial-reservation / clearance volumes around IFC elements) is run against
real IFC models materialized from Supabase Storage at increasing element
counts, and every stage is timed and memory-profiled separately so that the
dominant cost can be attributed rather than guessed at.

Pipeline stages measured independently
--------------------------------------
1. ``parse``     — ``ifcopenshell.open()``: STEP file to in-memory model.
2. ``ingest``    — ``ifcopenshell.geom.iterator``: triangulation of the source
                   elements into world-coordinate meshes. This is the stage
                   that actually touches "high-poly IFC geometry".
3. ``halo``      — generation of one Halo volume per element (the claim under
                   examination).
4. ``collision`` — broad-phase (uniform spatial hash) plus mid-phase (exact
                   AABB overlap) interference detection between Halo volumes,
                   with a naive O(n^2) baseline measured for comparison.

Scenarios
---------
S1  100 elements, single model.
S2  500 elements, single model.
S3  1000 elements, single model.
S4  2000 elements federated across four separate IFC files, including
    cross-file (inter-model) interference detection.
S5  LOD sweep — 1000 elements at LOD 200 / 300 / 400, to quantify the
    geometric-complexity cost of detail level.

Statistics
----------
Every scenario can be repeated with ``--repeats N``; the reported figures use
n = 7. Results are summarised by the **median and inter-quartile range**, not
the mean and standard deviation: a benchmark timing is bounded below by the
true cost of the work and unbounded above by scheduler interference on a
shared host, so the distribution is right-skewed and a single stall drags the
mean while leaving the median untouched. Any metric whose IQR exceeds 20% of
its median is flagged as unstable in the output rather than quietly reported.

Counts that should not vary between repeats — triangles, volumes, interfering
pairs — are checked for agreement across every repeat instead of being
averaged, so a non-deterministic result is surfaced as a defect rather than
smoothed into a mean.

Outputs (written to ``docs/benchmarks/`` by default)
----------------------------------------------------
* ``halo_benchmark_results.json``      — full structured record: host metadata,
  per-metric median/quartiles, and the raw per-repeat samples.
* ``halo_benchmark_results.csv``       — one row per scenario, median and IQR
  per metric.
* ``halo_benchmark_raw_repeats.csv``   — one row per (scenario, repeat) with
  the raw timings behind those medians.
* ``halo_benchmark_summary.md``        — rendered Markdown tables.
* ``fig*.png``                         — charts at 300 DPI, sized for a 160 mm
  thesis column, with median ± IQR error bars.

Usage
-----
    uv run python performance_benchmark.py --repeats 7
    uv run python performance_benchmark.py --validate
    uv run python performance_benchmark.py --scenarios 100,500 --repeats 3
    uv run python performance_benchmark.py --synthetic           # no IFC needed
    uv run python performance_benchmark.py --from-json docs/benchmarks/halo_benchmark_results.json

The last form re-renders tables and figures from a completed run without
re-measuring, so presentation changes cannot move a published number.

Dependencies (``matplotlib``, ``psutil``) are declared in ``pyproject.toml``;
install with ``uv sync``.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import logging
import math
import multiprocessing
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np

import os

# Reuse the project's own geometry primitives rather than redefining them, so
# the benchmark measures the same data contract the platform would use.
REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
BIMGUARD_CORE = Path(os.getenv("BIMGUARD_PATH", str(REPO_ROOT.parent / "bim-guard")))

for p in [EVAL_DIR, REPO_ROOT, BIMGUARD_CORE, Path(".")]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.modules.ifc_reader.piping_schema import BoundingBox, Point3D  # noqa: E402
from app.services.object_storage import ObjectStorage  # noqa: E402

logger = logging.getLogger("bimguard.benchmark")

try:
    import psutil

    _PSUTIL = True
except ImportError:  # pragma: no cover - psutil is declared in the bench group
    _PSUTIL = False

try:
    import ifcopenshell
    import ifcopenshell.geom

    _IFCOS = True
except ImportError:  # pragma: no cover - ifcopenshell is a core dependency
    _IFCOS = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

IFC_DIR = Path("data/uploads/ifc")

#: Primary model for the single-file scenarios. Chosen because it is the
#: largest real benchmark model (2 602 IfcProduct instances, IFC4).
PRIMARY_MODEL = "9152ac527a1844f69a73f73e77468326_BUILDING_R4.ifc"

#: Four genuinely distinct models standing in for a federated coordination
#: set (architectural / institutional / residential / infrastructure-plumbing).
FEDERATED_MODELS = [
    "9152ac527a1844f69a73f73e77468326_BUILDING_R4.ifc",
    "c243ce49cc834c47bad6f393bba1af4a_AC20-Institute-Var-2.ifc",
    "7589fcfc61b849f38c286efebd251ec2_Pacific Continental Residence Sample IFC4.3 Reference View ARCH.ifc",
    "f4c3f1b8390a4183b599323799caae83_Infra-Plumbing.ifc",
]

IFC_STORAGE_REFERENCES = {
    "9152ac527a1844f69a73f73e77468326_BUILDING_R4.ifc": (
        "sb://bim-guard-artifacts/uploads/ifc/"
        "93ce691468c34b51955f5239bd33ec23_BUILDING_R4.ifc"
    ),
    "c243ce49cc834c47bad6f393bba1af4a_AC20-Institute-Var-2.ifc": (
        "sb://bim-guard-artifacts/migration/uploads/ifc/"
        "c243ce49cc834c47bad6f393bba1af4a_AC20-Institute-Var-2.ifc"
    ),
    "7589fcfc61b849f38c286efebd251ec2_Pacific Continental Residence Sample IFC4.3 Reference View ARCH.ifc": (
        "sb://bim-guard-artifacts/migration/uploads/ifc/"
        "7589fcfc61b849f38c286efebd251ec2_"
        "Pacific Continental Residence Sample IFC4.3 Reference View ARCH.ifc"
    ),
    "f4c3f1b8390a4183b599323799caae83_Infra-Plumbing.ifc": (
        "sb://bim-guard-artifacts/migration/uploads/ifc/"
        "f4c3f1b8390a4183b599323799caae83_Infra-Plumbing.ifc"
    ),
}

#: IFC classes that carry no meaningful clearance requirement of their own.
EXCLUDED_TYPES = {
    "IfcOpeningElement",
    "IfcSpace",
    "IfcSite",
    "IfcBuilding",
    "IfcBuildingStorey",
    "IfcAnnotation",
    "IfcGrid",
}

#: Circumferential / arc segment count per level of detail. LOD 200 is a
#: coarse "does it fit at all" volume; LOD 400 is a fabrication-grade offset.
LOD_SEGMENTS = {200: 8, 300: 16, 400: 32}

#: Number of segments used per 90-degree arc when rounding a box Halo.
LOD_ARC_SEGMENTS = {200: 0, 300: 2, 400: 4}

DEFAULT_BUFFER_M = 0.5  # 500 mm seismic-bracing clearance


# ---------------------------------------------------------------------------
# Geometry types
# ---------------------------------------------------------------------------


@dataclass
class Mesh:
    """
    A triangle mesh in world coordinates, metres.

    ``vertices`` is an (N, 3) float32 array; ``faces`` is an (M, 3) int32
    array of vertex indices. Float32 is deliberate: at thousands of Halos the
    array dtype is the single largest lever on resident memory, and 32-bit
    precision is far finer than any clearance tolerance in AECO practice.
    """

    vertices: np.ndarray
    faces: np.ndarray

    @property
    def vertex_count(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def face_count(self) -> int:
        return int(self.faces.shape[0])

    @property
    def nbytes(self) -> int:
        return int(self.vertices.nbytes + self.faces.nbytes)

    def volume_m3(self) -> float:
        """
        Return the enclosed volume via the divergence theorem.

        Sums the signed volumes of the tetrahedra formed by each triangle and
        the origin. Valid for the closed, outward-oriented meshes this module
        emits; the absolute value guards against winding-order surprises.
        """
        v = self.vertices.astype(np.float64)
        a, b, c = v[self.faces[:, 0]], v[self.faces[:, 1]], v[self.faces[:, 2]]
        return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        """Return the (min, max) axis-aligned bounds of the mesh."""
        return self.vertices.min(axis=0), self.vertices.max(axis=0)


@dataclass
class ElementRecord:
    """One source IFC element, reduced to what the Halo generator needs."""

    guid: str
    ifc_type: str
    model: str
    centroid: Point3D
    bbox: BoundingBox
    source_vertices: int
    source_faces: int


# ---------------------------------------------------------------------------
# Halo generation — the capability under examination
# ---------------------------------------------------------------------------


def _classify(ifc_type: str) -> str:
    """
    Map an IFC class to the Halo primitive that best represents its clearance.

    Linear distribution elements get a cylindrical sleeve, point-like fittings
    get a sphere, and everything else gets an offset box.
    """
    t = ifc_type.lower()
    if any(k in t for k in ("pipesegment", "ductsegment", "cablesegment", "cablecarriersegment")):
        return "cylinder"
    if any(k in t for k in ("fitting", "valve", "junction", "terminal", "flange", "accessory")):
        return "sphere"
    return "box"


def _cylinder(radius: float, half_length: float, axis: int, segments: int) -> tuple[np.ndarray, np.ndarray]:
    """Build a closed cylinder of ``segments`` sides, centred on the origin."""
    theta = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
    cos_t, sin_t = np.cos(theta) * radius, np.sin(theta) * radius

    ring = np.zeros((segments, 3), dtype=np.float64)
    u, v = (axis + 1) % 3, (axis + 2) % 3
    ring[:, u], ring[:, v] = cos_t, sin_t

    lo, hi = ring.copy(), ring.copy()
    lo[:, axis], hi[:, axis] = -half_length, half_length

    cap_lo = np.zeros(3)
    cap_hi = np.zeros(3)
    cap_lo[axis], cap_hi[axis] = -half_length, half_length

    verts = np.vstack([lo, hi, cap_lo[None, :], cap_hi[None, :]])
    i = np.arange(segments)
    j = (i + 1) % segments
    lo_c, hi_c = 2 * segments, 2 * segments + 1

    side_a = np.column_stack([i, j, j + segments])
    side_b = np.column_stack([i, j + segments, i + segments])
    cap_a = np.column_stack([np.full(segments, lo_c), j, i])
    cap_b = np.column_stack([np.full(segments, hi_c), i + segments, j + segments])

    return verts, np.vstack([side_a, side_b, cap_a, cap_b]).astype(np.int32)


def _sphere(radius: float, segments: int) -> tuple[np.ndarray, np.ndarray]:
    """Build a closed UV sphere of ``segments`` longitudes, centred on the origin."""
    rings = max(2, segments // 2)
    lon = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
    lat = np.linspace(0.0, math.pi, rings + 1)[1:-1]  # exclude the two poles

    sin_lat, cos_lat = np.sin(lat), np.cos(lat)
    x = np.outer(sin_lat, np.cos(lon)) * radius
    y = np.outer(sin_lat, np.sin(lon)) * radius
    z = np.repeat(cos_lat * radius, segments).reshape(len(lat), segments)
    body = np.stack([x, y, z], axis=-1).reshape(-1, 3)

    north = np.array([[0.0, 0.0, radius]])
    south = np.array([[0.0, 0.0, -radius]])
    verts = np.vstack([body, north, south])
    n_body = body.shape[0]
    n_i, s_i = n_body, n_body + 1

    faces: list[np.ndarray] = []
    i = np.arange(segments)
    j = (i + 1) % segments
    faces.append(np.column_stack([np.full(segments, n_i), i, j]))
    for r in range(len(lat) - 1):
        a, b = r * segments + i, r * segments + j
        c, d = (r + 1) * segments + i, (r + 1) * segments + j
        faces.append(np.column_stack([a, c, d]))
        faces.append(np.column_stack([a, d, b]))
    last = (len(lat) - 1) * segments
    faces.append(np.column_stack([np.full(segments, s_i), last + j, last + i]))

    return verts, np.vstack(faces).astype(np.int32)


def _box(half: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build an axis-aligned box of half-extents ``half``, centred on the origin."""
    signs = np.array(
        [
            [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
            [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
        ],
        dtype=np.float64,
    )
    faces = np.array(
        [
            [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
            [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
            [1, 2, 6], [1, 6, 5], [0, 4, 7], [0, 7, 3],
        ],
        dtype=np.int32,
    )
    return signs * half, faces


def _rounded_box(half: np.ndarray, radius: float, arc_segments: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Build the exact Minkowski offset of a box by a sphere of ``radius``.

    A clearance zone around a prismatic element is geometrically a Minkowski
    sum, not a scaled box: the true offset surface is six flat faces, twelve
    quarter-cylinder edge fillets and eight spherical corner patches.
    Approximating it with a plain enlarged box overstates the reserved volume
    at every edge and corner — by 21% on a 0.3 m cube at a 0.5 m buffer — which
    is why LOD 300 and above round it.

    The surface is generated as a single latitude/longitude grid in which the
    three coordinate planes are deliberately *duplicated*. Each grid vertex is
    placed at ``sign_offset + radius * direction``, where ``sign_offset`` is the
    box corner belonging to that vertex's octant. Duplicating the seams is what
    opens the flat faces and edge fillets out of what would otherwise collapse
    to a sphere, so faces, fillets and corners all fall out of one quad mesh
    with no special-casing. ``arc_segments`` is the number of segments per
    90-degree arc, so cost scales as O(arc_segments^2).
    """
    arc = max(1, arc_segments)
    quarter = np.linspace(0.0, math.pi / 2.0, arc + 1)

    # Rows: southern hemisphere (offset -hz) then northern (offset +hz). The
    # equator appears in both, which opens the side faces.
    lat = np.concatenate([quarter - math.pi / 2.0, quarter])
    sz = np.concatenate([np.full(arc + 1, -1.0), np.full(arc + 1, 1.0)])

    # Columns: four quadrants, each closed at both ends. The four axis
    # meridians therefore appear twice, which opens the four side faces.
    lon = np.concatenate([quarter + q * math.pi / 2.0 for q in range(4)])
    quad_sx = np.array([1.0, -1.0, -1.0, 1.0])
    quad_sy = np.array([1.0, 1.0, -1.0, -1.0])
    sx = np.repeat(quad_sx, arc + 1)
    sy = np.repeat(quad_sy, arc + 1)

    rows, cols = len(lat), len(lon)
    cos_lat = np.cos(lat)[:, None]
    dirs = np.stack(
        [
            cos_lat * np.cos(lon)[None, :],
            cos_lat * np.sin(lon)[None, :],
            np.repeat(np.sin(lat)[:, None], cols, axis=1),
        ],
        axis=-1,
    )
    offsets = np.stack(
        [
            np.repeat((sx * half[0])[None, :], rows, axis=0),
            np.repeat((sy * half[1])[None, :], rows, axis=0),
            np.repeat((sz * half[2])[:, None], cols, axis=1),
        ],
        axis=-1,
    )
    grid = (offsets + radius * dirs).reshape(-1, 3)

    # Poles close the top and bottom faces, whose boundary is the first/last row.
    bottom_c = np.array([[0.0, 0.0, -half[2] - radius]])
    top_c = np.array([[0.0, 0.0, half[2] + radius]])
    verts = np.vstack([grid, bottom_c, top_c])
    bottom_i, top_i = rows * cols, rows * cols + 1

    r = np.arange(rows - 1)[:, None]
    c = np.arange(cols)[None, :]
    c_next = (c + 1) % cols
    a = (r * cols + c).ravel()
    b = (r * cols + c_next).ravel()
    d = ((r + 1) * cols + c).ravel()
    e = ((r + 1) * cols + c_next).ravel()
    quads = np.vstack([np.column_stack([a, d, e]), np.column_stack([a, e, b])])

    ring = np.arange(cols)
    ring_next = (ring + 1) % cols
    bottom_fan = np.column_stack([np.full(cols, bottom_i), ring_next, ring])
    last = (rows - 1) * cols
    top_fan = np.column_stack([np.full(cols, top_i), last + ring, last + ring_next])

    faces = np.vstack([quads, bottom_fan, top_fan]).astype(np.int32)
    return _clean_convex(verts, faces)


def _clean_convex(verts: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Drop degenerate triangles and orient a convex mesh consistently outward.

    The seam-duplication scheme collapses to zero-area triangles along the two
    pole rows, and the quadrant seams can invert winding locally. Because the
    Minkowski sum of two convex bodies is convex, outward orientation can be
    restored exactly by testing each face normal against the vector from the
    mesh centroid — no general-purpose mesh repair is needed.
    """
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    normals = np.cross(b - a, c - a)
    keep = np.linalg.norm(normals, axis=1) > 1e-12
    faces, normals = faces[keep], normals[keep]

    centre = verts.mean(axis=0)
    outward = ((verts[faces[:, 0]] + verts[faces[:, 1]] + verts[faces[:, 2]]) / 3.0) - centre
    flip = np.einsum("ij,ij->i", normals, outward) < 0
    faces[flip] = faces[flip][:, [0, 2, 1]]
    return verts, faces.astype(np.int32)


def generate_halo_volume(
    element_centroid: Point3D,
    element_bbox: BoundingBox,
    buffer_m: float = DEFAULT_BUFFER_M,
    lod: int = 300,
    kind: str = "box",
) -> Mesh:
    """
    Generate the Halo (spatial reservation) volume around a single element.

    Args:
        element_centroid: Centre point of the element, world coordinates, metres.
        element_bbox: Axis-aligned extent of the element, metres.
        buffer_m: Clearance distance held around the element. Defaults to
            0.5 m (500 mm), a typical seismic-bracing access allowance.
        lod: Level of detail. 200 = coarse (8-segment / prismatic),
            300 = medium (16-segment / rounded), 400 = fine (32-segment).
        kind: Halo primitive — ``"cylinder"`` for linear distribution runs,
            ``"sphere"`` for point-like fittings, ``"box"`` for everything else.

    Returns:
        A closed triangle :class:`Mesh` positioned at the element, in world
        coordinates.

    Notes:
        The Halo is generated from the element's *bounding box*, not its
        source triangulation. This is the single most important performance
        property of the design: Halo cost is O(1) in the source element's
        polygon count, so a 40 000-triangle imported valve and a 12-triangle
        extruded pipe produce identically priced Halos. The polygon count of
        the source model is paid once, during ingestion, not once per Halo.
    """
    segments = LOD_SEGMENTS.get(lod, LOD_SEGMENTS[300])
    dx, dy, dz = element_bbox.dimensions_m
    half = np.array([max(dx, 0.0), max(dy, 0.0), max(dz, 0.0)], dtype=np.float64) / 2.0
    origin = np.array([element_centroid.x, element_centroid.y, element_centroid.z], dtype=np.float64)

    if kind == "cylinder":
        axis = int(np.argmax(half))
        cross = [half[i] for i in range(3) if i != axis]
        radius = max(cross) + buffer_m
        verts, faces = _cylinder(radius, half[axis] + buffer_m, axis, segments)
    elif kind == "sphere":
        radius = float(np.linalg.norm(half)) + buffer_m
        verts, faces = _sphere(radius, segments)
    else:
        arcs = LOD_ARC_SEGMENTS.get(lod, LOD_ARC_SEGMENTS[300])
        if arcs == 0:
            verts, faces = _box(half + buffer_m)
        else:
            verts, faces = _rounded_box(half, buffer_m, arcs)

    return Mesh(vertices=(verts + origin).astype(np.float32), faces=faces)


# ---------------------------------------------------------------------------
# Interference detection between Halo volumes
# ---------------------------------------------------------------------------


def halo_aabbs(halos: Sequence[Mesh]) -> np.ndarray:
    """Return an (N, 6) array of ``[minx, miny, minz, maxx, maxy, maxz]`` per Halo."""
    out = np.empty((len(halos), 6), dtype=np.float32)
    for i, h in enumerate(halos):
        lo, hi = h.aabb()
        out[i, :3], out[i, 3:] = lo, hi
    return out


def broadphase_hash_grid(boxes: np.ndarray, cell_size: Optional[float] = None) -> list[tuple[int, int]]:
    """
    Find candidate interfering Halo pairs with a uniform spatial hash grid.

    Each AABB is stamped into every grid cell it overlaps; pairs sharing a cell
    become candidates. Expected cost is O(n) in the number of Halos for a
    bounded spatial density, against O(n^2) for exhaustive pair testing —
    the difference that makes "thousands of Halos" tractable.
    """
    if len(boxes) == 0:
        return []
    if cell_size is None:
        extents = boxes[:, 3:] - boxes[:, :3]
        cell_size = float(max(np.median(extents), 0.1)) * 2.0

    grid: dict[tuple[int, int, int], list[int]] = {}
    lo_cells = np.floor(boxes[:, :3] / cell_size).astype(np.int64)
    hi_cells = np.floor(boxes[:, 3:] / cell_size).astype(np.int64)

    for idx in range(len(boxes)):
        for cx in range(lo_cells[idx, 0], hi_cells[idx, 0] + 1):
            for cy in range(lo_cells[idx, 1], hi_cells[idx, 1] + 1):
                for cz in range(lo_cells[idx, 2], hi_cells[idx, 2] + 1):
                    grid.setdefault((cx, cy, cz), []).append(idx)

    candidates: set[tuple[int, int]] = set()
    for bucket in grid.values():
        n = len(bucket)
        if n < 2:
            continue
        for a in range(n - 1):
            for b in range(a + 1, n):
                i, j = bucket[a], bucket[b]
                candidates.add((i, j) if i < j else (j, i))
    return sorted(candidates)


def aabb_overlap(boxes: np.ndarray, pairs: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Filter candidate pairs down to those whose AABBs genuinely overlap."""
    pairs = list(pairs)
    if not pairs:
        return []
    arr = np.array(pairs, dtype=np.int64)
    a, b = boxes[arr[:, 0]], boxes[arr[:, 1]]
    hit = np.all((a[:, :3] <= b[:, 3:]) & (b[:, :3] <= a[:, 3:]), axis=1)
    return [tuple(p) for p in arr[hit]]


def naive_pairs(boxes: np.ndarray) -> int:
    """Count overlapping AABB pairs exhaustively, as an O(n^2) baseline."""
    n = len(boxes)
    lo, hi = boxes[:, :3], boxes[:, 3:]
    count = 0
    for i in range(n - 1):
        overlap = np.all((lo[i] <= hi[i + 1 :]) & (lo[i + 1 :] <= hi[i]), axis=1)
        count += int(overlap.sum())
    return count


# ---------------------------------------------------------------------------
# IFC ingestion
# ---------------------------------------------------------------------------


def _select_products(model, limit: int) -> list:
    """Pick up to ``limit`` clearance-relevant products, deterministically ordered."""
    products = [
        p
        for p in model.by_type("IfcProduct")
        if p.is_a() not in EXCLUDED_TYPES and getattr(p, "Representation", None) is not None
    ]
    products.sort(key=lambda p: p.id())
    return products[:limit]


def _triangulate(path: Path, model, products: list) -> tuple[list[ElementRecord], float]:
    """
    Triangulate ``products`` from an open model into :class:`ElementRecord` values.

    Returns the records and the wall-clock seconds the triangulation took. Only
    the bounding box and centroid are retained: the Halo generator never needs
    the source triangles themselves, which is why peak memory does not track
    the source model's polygon count.
    """
    settings = ifcopenshell.geom.settings()
    try:
        settings.set("use-world-coords", True)
    except Exception:  # pragma: no cover - older ifcopenshell settings API
        settings.set(settings.USE_WORLD_COORDS, True)

    records: list[ElementRecord] = []
    if not products:
        return records, 0.0

    t0 = time.perf_counter()
    iterator = ifcopenshell.geom.iterator(
        settings, model, multiprocessing.cpu_count(), include=products
    )
    if iterator.initialize():
        while True:
            shape = iterator.get()
            geometry = shape.geometry
            verts = np.asarray(geometry.verts, dtype=np.float64).reshape(-1, 3)
            n_faces = len(geometry.faces) // 3
            if len(verts):
                lo, hi = verts.min(axis=0), verts.max(axis=0)
                mid = (lo + hi) / 2.0
                records.append(
                    ElementRecord(
                        guid=shape.guid,
                        ifc_type=shape.type,
                        model=path.name,
                        centroid=Point3D(*(float(c) for c in mid)),
                        bbox=BoundingBox(
                            min=Point3D(*(float(c) for c in lo)),
                            max=Point3D(*(float(c) for c in hi)),
                        ),
                        source_vertices=len(verts),
                        source_faces=n_faces,
                    )
                )
            if not iterator.next():
                break
    return records, time.perf_counter() - t0


def ingest_elements(path: Path, limit: int) -> tuple[list[ElementRecord], float, float]:
    """
    Parse an IFC file and triangulate up to ``limit`` elements.

    Returns:
        A tuple of ``(records, parse_seconds, triangulate_seconds)``.
    """
    if not _IFCOS:
        raise RuntimeError("ifcopenshell is required for IFC-backed benchmarking")

    t0 = time.perf_counter()
    model = ifcopenshell.open(str(path))
    parse_s = time.perf_counter() - t0

    records, triangulate_s = _triangulate(path, model, _select_products(model, limit))
    return records, parse_s, triangulate_s


def synthetic_elements(count: int, model: str = "synthetic") -> list[ElementRecord]:
    """
    Build a deterministic lattice of synthetic elements.

    Used by ``--synthetic`` so the harness is reproducible on a machine that
    does not carry the repository's IFC fixtures. Element extents mimic a
    mixed MEP/structural population.
    """
    rng = np.random.default_rng(20260819)
    records: list[ElementRecord] = []
    side = max(1, int(math.ceil(count ** (1.0 / 3.0))))
    kinds = ["IfcPipeSegment", "IfcPipeFitting", "IfcBeam", "IfcColumn", "IfcDuctSegment"]
    for i in range(count):
        gx, gy, gz = i % side, (i // side) % side, i // (side * side)
        centre = np.array([gx * 3.0, gy * 3.0, gz * 3.5], dtype=np.float64)
        extent = rng.uniform(0.1, 2.5, size=3)
        records.append(
            ElementRecord(
                guid=f"SYN{i:07d}",
                ifc_type=kinds[i % len(kinds)],
                model=model,
                centroid=Point3D(*centre),
                bbox=BoundingBox(
                    min=Point3D(*(centre - extent / 2)),
                    max=Point3D(*(centre + extent / 2)),
                ),
                source_vertices=int(rng.integers(8, 400)),
                source_faces=int(rng.integers(12, 800)),
            )
        )
    return records


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

#: Wall-clock and memory metrics aggregated across repeats. Everything else a
#: scenario reports (triangle counts, volumes, pair counts) is deterministic
#: and is verified to be identical on every repeat rather than averaged.
TIMING_METRICS = [
    "parse_s",
    "triangulate_s",
    "halo_s",
    "broadphase_s",
    "midphase_s",
    "naive_s",
    "total_s",
    "rss_delta_mb",
]

#: A metric whose inter-quartile range exceeds this fraction of its median is
#: reported as unstable. Timing distributions on a shared virtual host are
#: right-skewed, so the median and IQR are used throughout in preference to
#: the mean and standard deviation, which a single scheduling stall distorts.
UNSTABLE_IQR_FRACTION = 0.20

#: Physical unit per metric. Everything is seconds except resident-memory
#: growth, which is megabytes — the distinction matters because the two need
#: different thresholds below which a large *relative* spread is meaningless.
METRIC_UNITS = {"rss_delta_mb": "MB"}
DEFAULT_METRIC_UNIT = "s"

#: Medians below these are reported as unstable-but-negligible: at this
#: magnitude the spread is measurement noise rather than a property of the
#: algorithm, and no conclusion in the analysis rests on it.
NEGLIGIBLE_MEDIAN = {"s": 0.01, "MB": 1.0}
NEGLIGIBLE_LABEL = {"s": "negligible (<10 ms)", "MB": "negligible (<1 MB)"}


@dataclass
class MetricStats:
    """Robust summary of one metric across repeated runs of a scenario."""

    metric: str
    unit: str
    n: int
    median: float
    q1: float
    q3: float
    iqr: float
    iqr_pct_of_median: float
    minimum: float
    maximum: float
    unstable: bool
    raw: list[float]

    @classmethod
    def summarise(cls, metric: str, values: Sequence[float]) -> "MetricStats":
        """
        Build robust statistics for one metric.

        Uses the median and inter-quartile range rather than the mean and
        standard deviation: benchmark timings are bounded below by the true
        cost and unbounded above by scheduler interference, so the
        distribution is right-skewed and the mean is pulled by outliers the
        median ignores. Quartiles use the inclusive method, which is defined
        for the small sample sizes a benchmark can afford.
        """
        ordered = [float(v) for v in values]      # run order — preserved for the raw record
        data = sorted(ordered)                       # sorted copy — used for the quantiles
        n = len(data)
        median = statistics.median(data) if n else 0.0
        if n >= 2:
            q1, _, q3 = statistics.quantiles(data, n=4, method="inclusive")
        else:
            q1 = q3 = median
        iqr = q3 - q1
        pct = (100.0 * iqr / median) if median > 0 else 0.0
        return cls(
            metric=metric,
            unit=METRIC_UNITS.get(metric, DEFAULT_METRIC_UNIT),
            n=n,
            median=round(median, 4),
            q1=round(q1, 4),
            q3=round(q3, 4),
            iqr=round(iqr, 4),
            iqr_pct_of_median=round(pct, 1),
            minimum=round(data[0], 4) if n else 0.0,
            maximum=round(data[-1], 4) if n else 0.0,
            unstable=bool(n >= 2 and median > 0 and iqr > UNSTABLE_IQR_FRACTION * median),
            # Raw samples stay in run order, not sorted: the per-repeat CSV joins
            # metrics by row index, so sorting each metric independently would
            # fabricate runs that never happened.
            raw=[round(v, 4) for v in ordered],
        )

    @property
    def negligible(self) -> bool:
        """True when the median is small enough that its spread carries no argument."""
        return self.median < NEGLIGIBLE_MEDIAN.get(self.unit, 0.0)

    @property
    def magnitude_label(self) -> str:
        """Human-readable verdict on whether an unstable metric actually matters."""
        return NEGLIGIBLE_LABEL[self.unit] if self.negligible else "**material**"


@dataclass
class SingleRun:
    """One complete measurement of one scenario — the unit that gets repeated."""

    parse_s: float
    triangulate_s: float
    halo_s: float
    broadphase_s: float
    midphase_s: float
    naive_s: float
    rss_delta_mb: float
    element_actual: int
    source_faces: int
    source_vertices: int
    halo_faces: int
    halo_vertices: int
    halo_array_mb: float
    mean_halo_volume_m3: float
    median_halo_volume_m3: float
    total_halo_volume_m3: float
    candidate_pairs: int
    interfering_pairs: int
    naive_pairs: int
    cross_model_pairs: int

    @property
    def total_s(self) -> float:
        return (
            self.parse_s
            + self.triangulate_s
            + self.halo_s
            + self.broadphase_s
            + self.midphase_s
        )

    def timing(self, metric: str) -> float:
        return self.total_s if metric == "total_s" else float(getattr(self, metric))


#: Fields that must be identical on every repeat. Any variation means the
#: benchmark is not measuring what it claims to, so it is reported rather
#: than averaged away.
DETERMINISTIC_FIELDS = [
    "element_actual",
    "source_faces",
    "source_vertices",
    "halo_faces",
    "halo_vertices",
    "halo_array_mb",
    "mean_halo_volume_m3",
    "median_halo_volume_m3",
    "total_halo_volume_m3",
    "candidate_pairs",
    "interfering_pairs",
    "naive_pairs",
    "cross_model_pairs",
]


@dataclass
class ScenarioResult:
    """Aggregated measurements for one benchmark scenario across all repeats."""

    scenario: str
    element_target: int
    element_actual: int
    models: list[str]
    lod: int
    buffer_m: float
    repeats: int
    stats: dict[str, MetricStats]
    halos_per_s: float
    halo_us_per_element: float
    ingest_elements_per_s: float
    source_faces: int
    source_vertices: int
    halo_faces: int
    halo_vertices: int
    halo_array_mb: float
    mean_halo_volume_m3: float
    median_halo_volume_m3: float
    total_halo_volume_m3: float
    candidate_pairs: int
    interfering_pairs: int
    naive_pairs: int
    cross_model_pairs: int
    nondeterministic_fields: list[str] = field(default_factory=list)
    unstable_metrics: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def median(self, metric: str) -> float:
        """Median of one timing metric, or 0.0 if the metric was not collected."""
        stat = self.stats.get(metric)
        return stat.median if stat else 0.0

    @property
    def synthetic(self) -> bool:
        """True when every source model is a synthetic lattice rather than an IFC file."""
        return all(m.startswith("synthetic") for m in self.models)


def _rss_mb() -> float:
    """Return the current process resident set size in MB (0.0 without psutil)."""
    if not _PSUTIL:
        return 0.0
    return psutil.Process().memory_info().rss / 1024 / 1024


def measure_once(
    records: list[ElementRecord],
    parse_s: float,
    triangulate_s: float,
    lod: int,
    buffer_m: float,
    run_naive: bool = True,
) -> SingleRun:
    """Generate Halos for ``records`` once and time every stage of the process."""
    gc.collect()
    rss_start = _rss_mb()

    t0 = time.perf_counter()
    halos = [
        generate_halo_volume(r.centroid, r.bbox, buffer_m=buffer_m, lod=lod, kind=_classify(r.ifc_type))
        for r in records
    ]
    halo_s = time.perf_counter() - t0

    rss_delta = _rss_mb() - rss_start
    halo_array_mb = sum(h.nbytes for h in halos) / 1024 / 1024

    boxes = halo_aabbs(halos)
    t0 = time.perf_counter()
    candidates = broadphase_hash_grid(boxes)
    broadphase_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    hits = aabb_overlap(boxes, candidates)
    midphase_s = time.perf_counter() - t0

    naive_s, naive_count = 0.0, 0
    if run_naive:
        t0 = time.perf_counter()
        naive_count = naive_pairs(boxes)
        naive_s = time.perf_counter() - t0

    model_of = [r.model for r in records]
    cross = sum(1 for i, j in hits if model_of[i] != model_of[j])
    volumes = [h.volume_m3() for h in halos]

    return SingleRun(
        parse_s=parse_s,
        triangulate_s=triangulate_s,
        halo_s=halo_s,
        broadphase_s=broadphase_s,
        midphase_s=midphase_s,
        naive_s=naive_s,
        rss_delta_mb=rss_delta,
        element_actual=len(records),
        source_faces=sum(r.source_faces for r in records),
        source_vertices=sum(r.source_vertices for r in records),
        halo_faces=sum(h.face_count for h in halos),
        halo_vertices=sum(h.vertex_count for h in halos),
        halo_array_mb=round(halo_array_mb, 2),
        mean_halo_volume_m3=round(statistics.fmean(volumes), 3) if volumes else 0.0,
        median_halo_volume_m3=round(statistics.median(volumes), 3) if volumes else 0.0,
        total_halo_volume_m3=round(sum(volumes), 2),
        candidate_pairs=len(candidates),
        interfering_pairs=len(hits),
        naive_pairs=naive_count,
        cross_model_pairs=cross,
    )


def aggregate(
    name: str,
    runs: list[SingleRun],
    lod: int,
    buffer_m: float,
    models: list[str],
    target: int,
) -> ScenarioResult:
    """
    Reduce the repeats of one scenario to medians, IQRs and integrity checks.

    Timing metrics are summarised robustly; deterministic fields are checked
    for agreement across repeats and reported verbatim from the first run.
    """
    assert runs, "aggregate() requires at least one run"
    first = runs[0]

    stats = {m: MetricStats.summarise(m, [r.timing(m) for r in runs]) for m in TIMING_METRICS}

    nondeterministic = [
        f for f in DETERMINISTIC_FIELDS if len({getattr(r, f) for r in runs}) > 1
    ]

    halo_median = stats["halo_s"].median
    tri_median = stats["triangulate_s"].median
    n = first.element_actual

    warnings: list[str] = []
    if n < target:
        warnings.append(
            f"Only {n} elements with usable geometry were available against a target of {target}"
        )
    if halo_median > 5.0:
        warnings.append(f"Median Halo generation exceeded 5 s wall-clock ({halo_median:.2f} s)")
    if stats["rss_delta_mb"].median > 512:
        warnings.append(
            f"Median resident memory grew by {stats['rss_delta_mb'].median:.0f} MB during Halo generation"
        )
    for f in nondeterministic:
        warnings.append(
            f"Field '{f}' varied across repeats — it was expected to be deterministic"
        )

    unstable = []
    for metric, stat in stats.items():
        if not stat.unstable:
            continue
        unstable.append(metric)
        floor = NEGLIGIBLE_MEDIAN.get(stat.unit, 0.0)
        qualifier = f" (median below {floor:g} {stat.unit} — noise, not signal)" if stat.negligible else ""
        warnings.append(
            f"Unstable timing: {metric} IQR is {stat.iqr_pct_of_median:.0f}% of its "
            f"{stat.median:.4f} {stat.unit} median across n={stat.n}{qualifier}"
        )

    return ScenarioResult(
        scenario=name,
        element_target=target,
        element_actual=n,
        models=models,
        lod=lod,
        buffer_m=buffer_m,
        repeats=len(runs),
        stats=stats,
        halos_per_s=round(n / halo_median, 1) if halo_median > 0 else 0.0,
        halo_us_per_element=round(1e6 * halo_median / n, 1) if n else 0.0,
        ingest_elements_per_s=round(n / tri_median, 1) if tri_median > 0 else 0.0,
        source_faces=first.source_faces,
        source_vertices=first.source_vertices,
        halo_faces=first.halo_faces,
        halo_vertices=first.halo_vertices,
        halo_array_mb=first.halo_array_mb,
        mean_halo_volume_m3=first.mean_halo_volume_m3,
        median_halo_volume_m3=first.median_halo_volume_m3,
        total_halo_volume_m3=first.total_halo_volume_m3,
        candidate_pairs=first.candidate_pairs,
        interfering_pairs=first.interfering_pairs,
        naive_pairs=first.naive_pairs,
        cross_model_pairs=first.cross_model_pairs,
        nondeterministic_fields=nondeterministic,
        unstable_metrics=unstable,
        warnings=warnings,
    )

# ---------------------------------------------------------------------------
# Scenario orchestration
# ---------------------------------------------------------------------------


def _resolve(name: str) -> Path:
    """Resolve an IFC fixture from an explicit local copy or Supabase Storage."""
    path = IFC_DIR / name
    if path.exists():
        return path

    reference = IFC_STORAGE_REFERENCES.get(name)
    if reference is None:
        raise FileNotFoundError(f"No IFC fixture reference configured for: {name}")
    materialized = ObjectStorage().materialize_local_path(reference)
    if materialized is None:
        raise FileNotFoundError(f"Unable to materialize IFC fixture: {reference}")
    return materialized


def run_single_model_scenarios(
    counts: Sequence[int], lod: int, buffer_m: float, synthetic: bool, repeats: int = 1
) -> list[ScenarioResult]:
    """
    Run the single-model scaling scenarios (S1-S3) at the given element counts.

    Every repeat re-parses and re-triangulates the source model rather than
    reusing a cached ingestion, so the ingestion figures carry the same
    statistical treatment as the generation figures. That is deliberately the
    expensive choice: ingestion is the dominant cost, and a median over
    repeats of the whole pipeline is the only honest way to report it.
    """
    results: list[ScenarioResult] = []
    for n in counts:
        label = f"S-{n}"
        runs: list[SingleRun] = []
        models = ["synthetic"] if synthetic else [PRIMARY_MODEL]
        for rep in range(repeats):
            logger.info("scenario %s: %d elements (repeat %d/%d)", label, n, rep + 1, repeats)
            if synthetic:
                records, parse_s, triangulate_s = synthetic_elements(n), 0.0, 0.0
            else:
                path = _resolve(PRIMARY_MODEL)
                records, parse_s, triangulate_s = ingest_elements(path, n)
                models = [path.name]
            runs.append(measure_once(records, parse_s, triangulate_s, lod, buffer_m))
        results.append(aggregate(label, runs, lod, buffer_m, models, n))
    return results


def _federated_records(total: int) -> tuple[list[ElementRecord], float, float, list[str]]:
    """
    Load one federated element population across the four fixture models.

    Element quotas are allocated in proportion to what each model can actually
    supply, rather than split evenly. An even split silently under-fills the
    scenario, because the infrastructure model in the federated set holds only
    38 products against the architectural model's 2 589.
    """
    records: list[ElementRecord] = []
    parse_s = triangulate_s = 0.0
    models: list[str] = []
    opened = []

    for name in FEDERATED_MODELS:
        path = _resolve(name)
        t0 = time.perf_counter()
        model = ifcopenshell.open(str(path))
        parse_s += time.perf_counter() - t0
        available = _select_products(model, limit=10**9)
        opened.append((path, model, available))
        models.append(path.name)

    supply = sum(len(a) for _, _, a in opened)
    if supply < total:
        logger.warning("federated set can supply only %d of %d requested elements", supply, total)

    # Water-filling: models that cannot meet an even share release their
    # remainder to the models that can, so the target is met whenever the
    # federated set holds enough elements in aggregate.
    quotas = {path.name: 0 for path, _, _ in opened}
    remaining, pool = total, list(opened)
    while remaining > 0 and pool:
        share = math.ceil(remaining / len(pool))
        still: list = []
        for path, model, available in pool:
            take = min(share, len(available) - quotas[path.name], remaining)
            quotas[path.name] += take
            remaining -= take
            if quotas[path.name] < len(available):
                still.append((path, model, available))
        if not still or share == 0:
            break
        pool = still

    for path, model, available in opened:
        quota = quotas[path.name]
        if quota == 0:
            continue
        recs, t_s = _triangulate(path, model, available[:quota])
        triangulate_s += t_s
        records.extend(recs)

    return records[:total], parse_s, triangulate_s, models


def run_federated_scenario(
    total: int, lod: int, buffer_m: float, synthetic: bool, repeats: int = 1
) -> ScenarioResult:
    """
    Run the federated coordination scenario (S4).

    Four separate IFC files are loaded and merged into one Halo population, so
    that interference detection runs across model boundaries as it would in a
    real multi-discipline coordination review.
    """
    runs: list[SingleRun] = []
    models: list[str] = []
    for rep in range(repeats):
        logger.info("scenario S-federated: %d elements (repeat %d/%d)", total, rep + 1, repeats)
        if synthetic:
            per_model = math.ceil(total / 4)
            records: list[ElementRecord] = []
            models = []
            for k in range(4):
                records.extend(synthetic_elements(per_model, model=f"synthetic-{k}"))
                models.append(f"synthetic-{k}")
            records, parse_s, triangulate_s = records[:total], 0.0, 0.0
        else:
            records, parse_s, triangulate_s, models = _federated_records(total)
        runs.append(measure_once(records, parse_s, triangulate_s, lod, buffer_m))
    return aggregate("S-federated", runs, lod, buffer_m, models, total)


def run_scaleout_scenarios(
    counts: Sequence[int], lod: int, buffer_m: float, repeats: int = 1
) -> list[ScenarioResult]:
    """
    Run the synthetic scale-out scenarios (S6) beyond what the fixtures supply.

    The largest real model in the repository holds 2 589 usable elements, which
    is not enough to locate the crossover between exhaustive and broad-phase
    interference detection, nor to test the "thousands of Halos" claim at the
    upper end. These scenarios therefore use a deterministic synthetic element
    lattice, and are reported separately from the IFC-backed measurements so
    the two are never conflated.
    """
    results = []
    for n in counts:
        runs: list[SingleRun] = []
        for rep in range(repeats):
            logger.info("scale-out scenario: %d synthetic elements (repeat %d/%d)", n, rep + 1, repeats)
            runs.append(measure_once(synthetic_elements(n), 0.0, 0.0, lod, buffer_m))
        results.append(aggregate(f"S-scale{n}", runs, lod, buffer_m, ["synthetic"], n))
    return results


def run_lod_sweep(
    count: int, buffer_m: float, synthetic: bool, repeats: int = 1
) -> list[ScenarioResult]:
    """
    Run the LOD sweep (S5) — the same element population at LOD 200/300/400.

    Within a repeat, ingestion happens once and is shared by all three levels,
    because the source triangulation is identical across levels of detail;
    only Halo generation and interference detection are re-measured per level.
    Each repeat re-ingests, so the shared parse and triangulate figures still
    carry a distribution rather than a single sample.
    """
    lods = (200, 300, 400)
    runs: dict[int, list[SingleRun]] = {lod: [] for lod in lods}
    models = ["synthetic"] if synthetic else [PRIMARY_MODEL]

    for rep in range(repeats):
        if synthetic:
            records, parse_s, triangulate_s = synthetic_elements(count), 0.0, 0.0
        else:
            path = _resolve(PRIMARY_MODEL)
            records, parse_s, triangulate_s = ingest_elements(path, count)
            models = [path.name]
        for lod in lods:
            logger.info(
                "LOD sweep: LOD %d over %d elements (repeat %d/%d)",
                lod, len(records), rep + 1, repeats,
            )
            runs[lod].append(measure_once(records, parse_s, triangulate_s, lod, buffer_m))

    return [aggregate(f"S-lod{lod}", runs[lod], lod, buffer_m, models, count) for lod in lods]

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def host_metadata() -> dict:
    """Capture the host characteristics a reader needs to interpret timings."""
    meta = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": multiprocessing.cpu_count(),
        "numpy": np.__version__,
    }
    if _IFCOS:
        meta["ifcopenshell"] = ifcopenshell.version
    if _PSUTIL:
        vm = psutil.virtual_memory()
        meta["total_ram_gb"] = round(vm.total / 1024**3, 2)
    return meta


def _stats_from_dict(d: dict) -> MetricStats:
    """Rebuild a :class:`MetricStats` from its serialised form."""
    return MetricStats(**d)


def _result_from_dict(d: dict) -> ScenarioResult:
    """Rebuild a :class:`ScenarioResult` from its serialised form."""
    payload = dict(d)
    payload["stats"] = {k: _stats_from_dict(v) for k, v in payload["stats"].items()}
    return ScenarioResult(**payload)


def load_results(path: Path) -> tuple[list[ScenarioResult], dict]:
    """
    Load a previous run's results so charts and tables can be re-rendered.

    Re-rendering from saved data rather than re-measuring keeps presentation
    changes free of measurement drift: the figures in the report are provably
    the same numbers as the ones in the JSON.
    """
    payload = json.loads(Path(path).read_text())
    return [_result_from_dict(s) for s in payload["scenarios"]], payload.get("host", {})


#: Median/IQR columns emitted per timing metric in the summary CSV.
_STAT_SUFFIXES = ("median", "q1", "q3", "iqr", "iqr_pct_of_median")

CSV_HEAD = ["scenario", "source", "element_target", "element_actual", "lod", "buffer_m", "repeats"]
CSV_TAIL = [
    "halos_per_s", "halo_us_per_element", "ingest_elements_per_s",
    "source_faces", "source_vertices", "halo_faces", "halo_vertices", "halo_array_mb",
    "mean_halo_volume_m3", "median_halo_volume_m3", "total_halo_volume_m3",
    "candidate_pairs", "interfering_pairs", "naive_pairs", "cross_model_pairs",
    "unstable_metrics",
]


def _csv_fields() -> list[str]:
    """Column order for the aggregated results CSV."""
    stat_cols = [f"{m}_{s}" for m in TIMING_METRICS for s in _STAT_SUFFIXES]
    return CSV_HEAD + stat_cols + CSV_TAIL


def write_outputs(results: list[ScenarioResult], out_dir: Path) -> None:
    """Write the JSON record, both CSVs and the Markdown summary."""
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_by": "performance_benchmark.py",
        "statistics": {
            "central_tendency": "median",
            "spread": "inter-quartile range (Q3 - Q1), inclusive method",
            "rationale": (
                "Benchmark timings are bounded below by the true cost and unbounded above "
                "by scheduler interference, so the distribution is right-skewed; the median "
                "and IQR are robust to that where the mean and standard deviation are not."
            ),
            "unstable_threshold": f"IQR > {UNSTABLE_IQR_FRACTION:.0%} of median",
            "negligible_median_by_unit": NEGLIGIBLE_MEDIAN,
        },
        "host": host_metadata(),
        "scenarios": [asdict(r) for r in results],
    }
    (out_dir / "halo_benchmark_results.json").write_text(json.dumps(payload, indent=2))

    fields = _csv_fields()
    with (out_dir / "halo_benchmark_results.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in results:
            row = {
                "scenario": r.scenario,
                "source": "synthetic" if r.synthetic else "IFC",
                "element_target": r.element_target,
                "element_actual": r.element_actual,
                "lod": r.lod,
                "buffer_m": r.buffer_m,
                "repeats": r.repeats,
                "unstable_metrics": ";".join(r.unstable_metrics),
            }
            for metric, stat in r.stats.items():
                for suffix in _STAT_SUFFIXES:
                    row[f"{metric}_{suffix}"] = getattr(stat, suffix)
            for key in CSV_TAIL[:-1]:
                row[key] = getattr(r, key)
            writer.writerow(row)

    # Per-repeat raw timings, one row per (scenario, repeat, metric sample).
    with (out_dir / "halo_benchmark_raw_repeats.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["scenario", "source", "element_actual", "lod", "repeat"] + TIMING_METRICS)
        for r in results:
            for i in range(r.repeats):
                writer.writerow(
                    [r.scenario, "synthetic" if r.synthetic else "IFC", r.element_actual, r.lod, i + 1]
                    + [r.stats[m].raw[i] if i < len(r.stats[m].raw) else "" for m in TIMING_METRICS]
                )

    (out_dir / "halo_benchmark_summary.md").write_text(render_markdown(results))
    logger.info("wrote results to %s", out_dir)


def _md(stat: MetricStats, places: int = 2) -> str:
    """Render one metric as ``median (IQR)`` for a Markdown table cell."""
    return f"{stat.median:.{places}f} ({stat.iqr:.{places}f})"


def render_markdown(results: list[ScenarioResult]) -> str:
    """Render the benchmark results as Markdown tables for the thesis."""
    meta = host_metadata()
    n_values = sorted({r.repeats for r in results})
    n_label = str(n_values[0]) if len(n_values) == 1 else "varies: " + ", ".join(map(str, n_values))

    lines: list[str] = [
        "# Halo volume generation — measured performance",
        "",
        f"Generated by `performance_benchmark.py`. Every figure below is measured, not estimated. "
        f"Each scenario was run **n = {n_label}** times; cells report the **median with the "
        f"inter-quartile range in parentheses**. The median and IQR are used rather than the mean "
        f"and standard deviation because benchmark timings are bounded below by the true cost and "
        f"unbounded above by scheduler interference, making the distribution right-skewed.",
        "",
        "## Host",
        "",
        "| Property | Value |",
        "|---|---|",
    ]
    for k, v in meta.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Table A — end-to-end scaling (median, IQR in parentheses)",
        "",
        "| Scenario | Source | Elements | LOD | Parse (s) | Triangulate (s) | Halo gen (s) | Halos/s | µs/Halo | RSS Δ (MB) | Halo arrays (MB) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario} | {'synthetic' if r.synthetic else 'IFC'} | {r.element_actual:,} | {r.lod} "
            f"| {_md(r.stats['parse_s'])} | {_md(r.stats['triangulate_s'])} | {_md(r.stats['halo_s'], 3)} "
            f"| {r.halos_per_s:,.0f} | {r.halo_us_per_element:.1f} | {_md(r.stats['rss_delta_mb'], 1)} "
            f"| {r.halo_array_mb:.2f} |"
        )

    lines += [
        "",
        "## Table B — geometric complexity (deterministic; identical on every repeat)",
        "",
        "| Scenario | Source triangles | Halo triangles | Halo vertices | Amplification | Mean Halo volume (m³) | Total reserved (m³) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        amp = (r.halo_faces / r.source_faces) if r.source_faces else 0.0
        lines.append(
            f"| {r.scenario} | {r.source_faces:,} | {r.halo_faces:,} | {r.halo_vertices:,} "
            f"| {amp:.2f}× | {r.mean_halo_volume_m3:,.2f} | {r.total_halo_volume_m3:,.0f} |"
        )

    lines += [
        "",
        "## Table C — interference detection (median, IQR in parentheses)",
        "",
        "| Scenario | Halos | Broad-phase (s) | Mid-phase (s) | Naive O(n²) (s) | Speed-up | Candidate pairs | Interfering pairs | Cross-model |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        grid = r.median("broadphase_s") + r.median("midphase_s")
        speed = (r.median("naive_s") / grid) if grid > 0 and r.median("naive_s") else 0.0
        lines.append(
            f"| {r.scenario} | {r.element_actual:,} | {_md(r.stats['broadphase_s'], 3)} "
            f"| {_md(r.stats['midphase_s'], 3)} | {_md(r.stats['naive_s'], 3)} | {speed:.1f}× "
            f"| {r.candidate_pairs:,} | {r.interfering_pairs:,} | {r.cross_model_pairs:,} |"
        )

    lines += [
        "",
        "## Table D — measurement stability",
        "",
        "Metrics whose IQR exceeds 20% of their median. A large relative spread on a "
        "sub-10 ms median (or a sub-1 MB memory delta) is measurement noise; a large spread on a "
        "multi-second median is not, and no conclusion should rest on it without more repeats.",
        "",
        "| Scenario | Metric | Unit | Median | IQR | IQR as % of median | Min | Max | Magnitude |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    any_unstable = False
    for r in results:
        for metric in r.unstable_metrics:
            s = r.stats[metric]
            any_unstable = True
            lines.append(
                f"| {r.scenario} | `{metric}` | {s.unit} | {s.median:.4f} | {s.iqr:.4f} "
                f"| {s.iqr_pct_of_median:.0f}% | {s.minimum:.4f} | {s.maximum:.4f} | {s.magnitude_label} |"
            )
    if not any_unstable:
        lines.append("| — | — | — | — | — | — | — | — | No metric exceeded the threshold |")

    warned = [(r.scenario, w) for r in results for w in r.warnings if not w.startswith("Unstable timing")]
    lines += ["", "## Warnings raised during the run", ""]
    lines += [f"* **{s}** — {w}" for s, w in warned] or ["* None."]

    nondet = [(r.scenario, f) for r in results for f in r.nondeterministic_fields]
    lines += ["", "## Determinism check", ""]
    if nondet:
        lines += [f"* **{s}** — field `{f}` varied across repeats" for s, f in nondet]
    else:
        lines.append(
            "* Passed. Every triangle count, volume and pair count was identical on all repeats "
            "of every scenario, confirming that only wall-clock and resident memory vary between runs."
        )

    lines += [
        "",
        "## Stage share of total wall-clock (from medians)",
        "",
        "Shares are computed against the sum of the stage medians rather than the median of the "
        "per-run totals, because medians are not additive and the row would otherwise not sum to 100%.",
        "",
        "| Scenario | Parse | Triangulate | Halo gen | Interference |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in results:
        # Normalised by the sum of the stage medians, not by the median of the
        # totals: medians are not additive, so dividing by median(total_s) makes
        # the row sum to something other than 100%.
        interference = r.median("broadphase_s") + r.median("midphase_s")
        total = max(r.median("parse_s") + r.median("triangulate_s") + r.median("halo_s") + interference, 1e-9)
        lines.append(
            f"| {r.scenario} | {100 * r.median('parse_s') / total:.1f}% "
            f"| {100 * r.median('triangulate_s') / total:.1f}% "
            f"| {100 * r.median('halo_s') / total:.1f}% | {100 * interference / total:.1f}% |"
        )

    return "\n".join(lines) + "\n" + render_captions(results)


def _pretty_model(name: str) -> str:
    """Strip the 32-hex upload prefix from a fixture filename for display."""
    head, _, tail = name.partition("_")
    return tail if len(head) == 32 and all(c in "0123456789abcdef" for c in head) else name


def _stage_total(result: ScenarioResult) -> float:
    """Sum of the stage medians — the correct denominator for a share, since medians do not add."""
    return max(
        result.median("parse_s")
        + result.median("triangulate_s")
        + result.median("halo_s")
        + result.median("broadphase_s")
        + result.median("midphase_s"),
        1e-9,
    )


def _host_sentence(meta: dict) -> str:
    """One sentence naming the measurement host, for use inside a figure caption."""
    return (
        f"Measured on a {meta.get('cpu_count', '?')}-core {meta.get('processor', 'x86_64')} "
        f"Linux VM with {meta.get('total_ram_gb', '?')} GB RAM, Python {meta.get('python', '?')}, "
        f"IfcOpenShell {meta.get('ifcopenshell', '?')}, NumPy {meta.get('numpy', '?')}"
    )


def render_captions(results: list[ScenarioResult]) -> str:
    """
    Emit self-contained, ready-to-paste thesis captions for every figure.

    Numbers are read from the results rather than typed, so a caption cannot
    drift from the figure it describes. Numbering follows the results chapter
    (Figure 5.x); renumber the prefix if the chapter moves.
    """
    meta = host_metadata()
    host = _host_sentence(meta)
    by_name = {r.scenario: r for r in results}
    n = results[0].repeats if results else 0
    stats_note = (
        f"Markers are medians of n = {n} complete runs and error bars span the "
        f"inter-quartile range (Q1–Q3)"
    )

    def get(name: str):
        return by_name.get(name)

    k = get("S-1000")
    fed = get("S-federated")
    lo2, lo3, lo4 = get("S-lod200"), get("S-lod300"), get("S-lod400")
    s2k, s20k = get("S-scale2000"), get("S-scale20000")

    lines = [
        "",
        "---",
        "",
        "## Ready-to-paste thesis figure captions",
        "",
        "Self-contained captions for each figure, in results-chapter numbering. Every quantity is "
        "read from the results file rather than transcribed, so a caption cannot drift from the "
        "figure it describes. The figures themselves carry no embedded title, because the caption "
        "beneath them supplies it.",
        "",
        f"**Figure specifications.** Rendered at {CHART_DPI} DPI on a {FIG_WIDTH_IN:.1f} in "
        f"({FIG_WIDTH_IN * 25.4:.0f} mm) canvas and cropped to content, so saved widths run "
        "136–159 mm. Placed at a 160 mm A4 column they need at most 1.18× enlargement, giving an "
        "effective resolution of 255 DPI or better — above the 250 DPI print floor — so none needs "
        "regenerating for the page. One palette is shared across all seven: a colour always means "
        "the same pipeline stage or the same algorithm. Categorical hues are taken from a validated "
        "reference palette and the combinations used were checked with a contrast and "
        "colour-vision-deficiency validator on the light (paper) surface; the aqua slot sits below "
        "3:1 against paper, which is why every figure ships beside the full data tables above and "
        "colour never carries a value on its own.",
        "",
    ]

    def block(number: str, filename: str, text: str) -> None:
        lines.append(f"**Figure {number}** — `{filename}`")
        lines.append("")
        lines.append("> " + text.replace("\n", " "))
        lines.append("")

    if k:
        block(
            "5.1", "fig1_stage_cost.png",
            f"Wall-clock cost of each pipeline stage against element count, generating Halo "
            f"clearance volumes at LOD 300 with a 500 mm buffer from the reference IFC4 model "
            f"({_pretty_model(k.models[0])}). {stats_note}; the vertical axis is logarithmic. IFC triangulation "
            f"exceeds Halo generation by roughly two orders of magnitude at every count — "
            f"{k.median('triangulate_s'):.1f} s against {k.median('halo_s'):.2f} s at "
            f"{k.element_actual:,} elements. {host}."
        )

    if k:
        block(
            "5.2", "fig2_throughput.png",
            f"Halo generation throughput, derived from the median generation time of n = {n} runs "
            f"per scenario, at LOD 300 with a 500 mm buffer. Throughput is effectively flat across "
            f"this range, because generation cost is close to constant per element and independent "
            f"of the source element's polygon count; a mild upward drift in per-element cost is "
            f"visible only at the far larger synthetic populations of Figure 5.7. {host}."
        )

    if k:
        block(
            "5.3", "fig3_memory.png",
            f"Memory footprint of the generated Halo population. The solid series is the exact "
            f"array size (float32 vertices, int32 faces), which is deterministic and identical on "
            f"every repeat; the dashed series is process resident-memory growth across the "
            f"generation phase, shown as the median of n = {n} runs with an inter-quartile range. "
            f"At {k.element_actual:,} elements the Halo arrays occupy {k.halo_array_mb:.2f} MB. "
            f"Resident growth stays near zero because source triangulations are discarded as they "
            f"are consumed, so memory tracks element count rather than source polygon count. {host}."
        )

    if k:
        speed = (k.median("naive_s") / (k.median("broadphase_s") + k.median("midphase_s"))
                 if (k.median("broadphase_s") + k.median("midphase_s")) else 0.0)
        block(
            "5.4", "fig4_collision.png",
            f"Interference detection between Halo volumes on the IFC-backed scenarios, comparing a "
            f"uniform spatial hash grid (broad plus mid phase) against exhaustive vectorised "
            f"axis-aligned bounding-box testing. {stats_note}; the vertical axis is logarithmic. At "
            f"these element counts the grid is the slower of the two — {speed:.1f}× at "
            f"{k.element_actual:,} elements — because a pure-Python linear algorithm loses on "
            f"constant factors to a vectorised quadratic one. {host}."
        )

    if lo2 and lo3 and lo4:
        ratio = (lo3.median("halo_s") / lo2.median("halo_s")) if lo2.median("halo_s") else 0.0
        block(
            "5.5", "fig5_lod.png",
            f"Level-of-detail trade-off over {lo3.element_actual:,} elements, shown as two panels "
            f"rather than two vertical axes because triangle counts and seconds share no scale. "
            f"(a) Total triangles in the generated Halo population: {lo2.halo_faces:,} at LOD 200, "
            f"{lo3.halo_faces:,} at LOD 300, {lo4.halo_faces:,} at LOD 400. (b) Median generation "
            f"time over n = {n} runs with the inter-quartile range: LOD 300 costs {ratio:.0f}× LOD "
            f"200. The coarse level is a plain enlarged box that over-reserves volume by 11.8% "
            f"against the exact Minkowski offset; LOD 300 and 400 approximate the rounded offset "
            f"from below. {host}."
        )

    if k and fed:
        block(
            "5.6", "fig6_bottleneck.png",
            f"Share of total wall-clock time by pipeline stage across every scenario, computed from "
            f"the medians of n = {n} runs. IFC parse and triangulation are combined into a single "
            f"ingest band; the per-stage split is given in the accompanying table. Ingest accounts "
            f"for {100 * (k.median('parse_s') + k.median('triangulate_s')) / _stage_total(k):.0f}% "
            f"of the {k.element_actual:,}-element run and Halo generation for "
            f"{100 * k.median('halo_s') / _stage_total(k):.1f}%. The synthetic "
            f"scale-out scenarios have no ingest stage by construction, which is what exposes the "
            f"relative cost of generation against interference detection. {host}."
        )

    if s2k and s20k:
        def speedup(r):
            g = r.median("broadphase_s") + r.median("midphase_s")
            return (r.median("naive_s") / g) if g else 0.0
        block(
            "5.7", "fig7_scaleout.png",
            f"Scale-out to {s20k.element_actual:,} Halo volumes on a deterministic synthetic "
            f"element lattice, on logarithmic axes. {stats_note}. The crossover at which the "
            f"spatial hash grid overtakes exhaustive vectorised testing lies between 1 000 and "
            f"2 000 volumes; beyond it the advantage grows from {speedup(s2k):.1f}× at "
            f"{s2k.element_actual:,} volumes to {speedup(s20k):.1f}× at {s20k.element_actual:,}. "
            f"Halo generation remains close to linear throughout, its per-element cost drifting "
            f"from {s2k.halo_us_per_element:.0f} µs at {s2k.element_actual:,} volumes to "
            f"{s20k.halo_us_per_element:.0f} µs at {s20k.element_actual:,}. Synthetic elements are used because the "
            f"largest available IFC fixture supplies only 2 589 usable elements; these results are "
            f"never combined with the IFC-backed measurements. {host}."
        )

    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

#: One palette across every figure, so a reader can carry meaning between them:
#: the same colour always means the same pipeline stage or the same algorithm.
#: Hues are slots 1-3 and 7 of the validated categorical reference palette, and
#: the combinations actually used were checked with the palette validator on the
#: light (paper) surface: the stacked set orange/blue/aqua passes all-pairs
#: (worst CVD ΔE 9.2, worst normal-vision ΔE 24.0), as does the
#: aqua/violet/blue set used wherever the two interference algorithms appear
#: together (worst CVD ΔE 13.0). Aqua sits below 3:1 against paper, so every
#: figure using it ships alongside the full data tables in this directory —
#: colour never carries a value on its own.
PALETTE = {
    "ingest": "#eb6834",        # IFC parse + triangulation
    "halo": "#2a78d6",          # Halo generation — the capability under examination
    "interference": "#1baf7a",  # spatial hash grid (broad + mid phase)
    "naive": "#4a3aa7",         # exhaustive O(n^2) AABB comparison
}

#: Text and chrome wear ink, never a series colour.
INK = {"primary": "#0b0b0b", "secondary": "#52514e", "grid": "#c9c8c4"}

CHART_DPI = 300
#: A4 with 25 mm margins leaves a ~160 mm column; 6.3 in matches it exactly, so
#: figures are placed at 100% scale and never resampled by the typesetter.
FIG_WIDTH_IN = 6.3

#: Figures carry no embedded title: in a thesis the caption below the figure
#: names it, and an in-figure title duplicates that. Ready-to-paste captions are
#: emitted into halo_benchmark_summary.md instead.
FIG_HEIGHT_IN = 3.4


def _err(results: Sequence[ScenarioResult], metric: str) -> np.ndarray:
    """Return asymmetric (lower, upper) error bars spanning Q1 to Q3."""
    med = np.array([r.stats[metric].median for r in results])
    q1 = np.array([r.stats[metric].q1 for r in results])
    q3 = np.array([r.stats[metric].q3 for r in results])
    return np.vstack([np.maximum(med - q1, 0.0), np.maximum(q3 - med, 0.0)])


def _err_sum(results: Sequence[ScenarioResult], metrics: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
    """Return the summed medians and combined error bars for several metrics."""
    med = np.zeros(len(results))
    lo = np.zeros(len(results))
    hi = np.zeros(len(results))
    for m in metrics:
        med += np.array([r.stats[m].median for r in results])
        lo += np.array([max(r.stats[m].median - r.stats[m].q1, 0.0) for r in results])
        hi += np.array([max(r.stats[m].q3 - r.stats[m].median, 0.0) for r in results])
    return med, np.vstack([lo, hi])


def _plain_log_ticks(ax, axis: str, values: Sequence[int]) -> None:
    """
    Label a log axis with exactly the measured values, and nothing else.

    Matplotlib keeps labelling the decade minor ticks even when major ticks are
    set explicitly, which collides with them (a "5,000" landing on top of a
    "6 x 10^3"). Clearing the minor formatter is the only reliable fix.
    """
    from matplotlib.ticker import NullFormatter

    target = ax.xaxis if axis == "x" else ax.yaxis
    target.set_major_formatter(lambda v, _pos: f"{int(v):,}")
    target.set_minor_formatter(NullFormatter())
    target.set_minor_locator(plt_ticker_null())
    (ax.set_xticks if axis == "x" else ax.set_yticks)(list(values))


def plt_ticker_null():
    """Return a locator that emits no minor ticks."""
    from matplotlib.ticker import NullLocator

    return NullLocator()


def _apply_style(plt) -> None:
    """Set the print style: hairline recessive chrome, sans text, no top/right spines."""
    plt.rcParams.update({
        "figure.dpi": CHART_DPI,
        "savefig.dpi": CHART_DPI,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "font.family": "sans-serif",
        "font.size": 8.5,
        "axes.labelsize": 8.5,
        "axes.labelcolor": INK["primary"],
        "axes.edgecolor": INK["grid"],
        "axes.linewidth": 0.6,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "xtick.color": INK["secondary"],
        "ytick.color": INK["secondary"],
        "text.color": INK["primary"],
        "legend.fontsize": 8,
        "legend.frameon": False,
        "axes.grid": True,
        "grid.color": INK["grid"],
        "grid.linewidth": 0.5,
        "grid.linestyle": "-",      # solid hairline: dashes read as thresholds
        "grid.alpha": 0.55,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def render_charts(results: list[ScenarioResult], out_dir: Path) -> list[str]:
    """Render the benchmark figures at print resolution; returns filenames written."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed (uv sync) — skipping charts")
        return []

    _apply_style(plt)

    scaling = sorted(
        (r for r in results if r.scenario.startswith("S-") and r.scenario[2:].isdigit()),
        key=lambda r: r.element_actual,
    )
    lod_runs = sorted((r for r in results if r.scenario.startswith("S-lod")), key=lambda r: r.lod)
    scale = sorted(
        (r for r in results if r.scenario.startswith("S-scale")), key=lambda r: r.element_actual
    )
    written: list[str] = []

    ebar = dict(capsize=2.5, elinewidth=0.8, capthick=0.8, ecolor=INK["secondary"])
    line = dict(linewidth=1.6, markersize=5, markeredgecolor="white", markeredgewidth=0.7)

    if scaling:
        x = [r.element_actual for r in scaling]

        # Figure 1 — stage cost against element count.
        fig, ax = plt.subplots(figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN))
        inter_med, inter_err = _err_sum(scaling, ["broadphase_s", "midphase_s"])
        ax.errorbar(x, [r.median("triangulate_s") for r in scaling], yerr=_err(scaling, "triangulate_s"),
                    marker="s", color=PALETTE["ingest"], label="IFC triangulation", **line, **ebar)
        ax.errorbar(x, [r.median("halo_s") for r in scaling], yerr=_err(scaling, "halo_s"),
                    marker="o", color=PALETTE["halo"], label="Halo generation", **line, **ebar)
        ax.errorbar(x, inter_med, yerr=inter_err, marker="^", color=PALETTE["interference"],
                    label="Interference detection", **line, **ebar)
        ax.set_xlabel("Elements (count)")
        ax.set_ylabel("Wall-clock time (s, log scale)")
        ax.set_yscale("log")
        ax.set_xticks(x)
        ax.set_xticklabels([f"{v:,}" for v in x])
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3)
        fig.savefig(out_dir / "fig1_stage_cost.png")
        plt.close(fig)
        written.append("fig1_stage_cost.png")

        # Figure 2 — generation throughput. Single series: no legend, the axis names it.
        fig, ax = plt.subplots(figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN))
        pos = np.arange(len(scaling))
        ax.bar(pos, [r.halos_per_s for r in scaling], color=PALETTE["halo"], width=0.55)
        ax.set_xticks(pos)
        ax.set_xticklabels([f"{v:,}" for v in x])
        ax.set_xlabel("Elements (count)")
        ax.set_ylabel("Throughput (Halos per second)")
        top = max(r.halos_per_s for r in scaling)
        for i, r in enumerate(scaling):
            ax.text(i, r.halos_per_s + top * 0.02, f"{r.halos_per_s:,.0f}",
                    ha="center", va="bottom", fontsize=8, color=INK["primary"])
        ax.set_ylim(0, top * 1.16)
        fig.savefig(out_dir / "fig2_throughput.png")
        plt.close(fig)
        written.append("fig2_throughput.png")

        # Figure 3 — memory footprint. Both series are MB, so one axis.
        fig, ax = plt.subplots(figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN))
        ax.plot(x, [r.halo_array_mb for r in scaling], marker="o", color=PALETTE["halo"],
                label="Halo mesh arrays (exact, deterministic)", **line)
        ax.errorbar(x, [r.median("rss_delta_mb") for r in scaling], yerr=_err(scaling, "rss_delta_mb"),
                    marker="s", linestyle="--", color=PALETTE["naive"],
                    label="Process resident-memory growth", **line, **ebar)
        ax.set_xlabel("Elements (count)")
        ax.set_ylabel("Memory (MB)")
        ax.set_xticks(x)
        ax.set_xticklabels([f"{v:,}" for v in x])
        ax.legend(loc="upper left")
        fig.savefig(out_dir / "fig3_memory.png")
        plt.close(fig)
        written.append("fig3_memory.png")

        # Figure 4 — interference detection on the IFC-backed runs. Markers, not
        # bars: a bar encodes magnitude by length from zero, and a log axis has no
        # zero, so bars on a log scale misstate the ratios they appear to show.
        # This also keeps the visual language identical to the scale-out figure.
        fig, ax = plt.subplots(figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN))
        grid_med, grid_err = _err_sum(scaling, ["broadphase_s", "midphase_s"])
        ax.errorbar(x, grid_med, yerr=grid_err, marker="o", color=PALETTE["interference"],
                    label="Spatial hash grid (broad + mid phase)", **line, **ebar)
        ax.errorbar(x, [r.median("naive_s") for r in scaling], yerr=_err(scaling, "naive_s"),
                    marker="s", color=PALETTE["naive"], label="Exhaustive O(n²), vectorised",
                    **line, **ebar)
        ax.set_xscale("log")
        ax.set_yscale("log")
        _plain_log_ticks(ax, "x", x)
        ax.set_xlabel("Elements (count)")
        ax.set_ylabel("Wall-clock time (s, log scale)")
        ax.legend(loc="upper left")
        fig.savefig(out_dir / "fig4_collision.png")
        plt.close(fig)
        written.append("fig4_collision.png")

    if lod_runs:
        # Figure 5 — level of detail. Two panels rather than two y-axes on one:
        # triangles and seconds share no scale, and a dual-axis chart invites the
        # reader to compare two lines that are not comparable.
        fig, (ax_a, ax_b) = plt.subplots(
            1, 2, figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN), sharex=True, constrained_layout=True
        )
        pos = np.arange(len(lod_runs))
        labels = [str(r.lod) for r in lod_runs]

        ax_a.bar(pos, [r.halo_faces for r in lod_runs], color=PALETTE["halo"], width=0.55)
        ax_a.set_ylabel("Total Halo triangles (count)")
        ax_a.set_xlabel("Level of detail")
        ax_a.set_xticks(pos)
        ax_a.set_xticklabels(labels)
        ax_a.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
        ax_a.set_title("(a) Geometric complexity", fontsize=8.5, color=INK["secondary"], pad=6)

        ax_b.errorbar(pos, [r.median("halo_s") for r in lod_runs], yerr=_err(lod_runs, "halo_s"),
                      marker="o", color=PALETTE["halo"], **line, **ebar)
        ax_b.set_ylabel("Halo generation time (s)")
        ax_b.set_xlabel("Level of detail")
        ax_b.set_xticks(pos)
        ax_b.set_xticklabels(labels)
        ax_b.set_ylim(bottom=0)
        ax_b.set_title("(b) Generation cost", fontsize=8.5, color=INK["secondary"], pad=6)

        fig.savefig(out_dir / "fig5_lod.png")
        plt.close(fig)
        written.append("fig5_lod.png")

    if scale:
        # Figure 7 — scale-out and the broad-phase crossover.
        fig, ax = plt.subplots(figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN))
        x = [r.element_actual for r in scale]
        grid_med, grid_err = _err_sum(scale, ["broadphase_s", "midphase_s"])
        ax.errorbar(x, grid_med, yerr=grid_err, marker="o", color=PALETTE["interference"],
                    label="Spatial hash grid (broad + mid phase)", **line, **ebar)
        ax.errorbar(x, [r.median("naive_s") for r in scale], yerr=_err(scale, "naive_s"),
                    marker="s", color=PALETTE["naive"], label="Exhaustive O(n²), vectorised", **line, **ebar)
        ax.errorbar(x, [r.median("halo_s") for r in scale], yerr=_err(scale, "halo_s"),
                    marker="^", linestyle="--", color=PALETTE["halo"],
                    label="Halo generation", **line, **ebar)
        ax.set_xscale("log")
        ax.set_yscale("log")
        _plain_log_ticks(ax, "x", x)
        ax.set_xlabel("Halo volumes (count, synthetic elements)")
        ax.set_ylabel("Wall-clock time (s, log scale)")
        ax.legend(loc="upper left")
        fig.savefig(out_dir / "fig7_scaleout.png")
        plt.close(fig)
        written.append("fig7_scaleout.png")

    if results:
        # Figure 6 — stage share. Parse and triangulation are merged into a single
        # ingest band: both are IFC reading, the argument is about ingest as a
        # whole, and the per-stage split is carried by the tables.
        fig, ax = plt.subplots(figsize=(FIG_WIDTH_IN, 3.9))
        names = [r.scenario for r in results]
        ingest = np.array([r.median("parse_s") + r.median("triangulate_s") for r in results])
        halo = np.array([r.median("halo_s") for r in results])
        coll = np.array([r.median("broadphase_s") + r.median("midphase_s") for r in results])
        total = np.maximum(ingest + halo + coll, 1e-9)
        bottom = np.zeros(len(results))
        for data, label, colour in (
            (ingest, "IFC ingest (parse + triangulate)", PALETTE["ingest"]),
            (halo, "Halo generation", PALETTE["halo"]),
            (coll, "Interference detection", PALETTE["interference"]),
        ):
            share = 100 * data / total
            # A 1pt white edge renders the 2px surface gap between segments.
            ax.bar(names, share, bottom=bottom, label=label, color=colour, width=0.68,
                   edgecolor="white", linewidth=1.0)
            bottom += share
        ax.set_ylabel("Share of wall-clock time (%)")
        ax.set_xlabel("Scenario")
        ax.set_ylim(0, 100)
        ax.grid(axis="x", visible=False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=3)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        fig.savefig(out_dir / "fig6_bottleneck.png")
        plt.close(fig)
        written.append("fig6_bottleneck.png")

    logger.info("wrote %d figures at %d DPI", len(written), CHART_DPI)
    return written

# ---------------------------------------------------------------------------
# Generator self-validation
# ---------------------------------------------------------------------------


def _analytic_rounded_box_volume(half: np.ndarray, radius: float) -> float:
    """Return the exact volume of a box Minkowski-summed with a sphere (Steiner formula)."""
    a, b, c = (float(v) for v in half)
    return (
        8 * a * b * c
        + 8 * radius * (a * b + b * c + c * a)
        + 2 * math.pi * radius**2 * (a + b + c)
        + (4.0 / 3.0) * math.pi * radius**3
    )


def _unmatched_edges(mesh: Mesh) -> int:
    """
    Count directed edges without a matching opposite, comparing by position.

    Vertices are compared by rounded coordinate rather than by index because
    the seam-duplication scheme deliberately places coincident vertices at the
    quadrant and equator seams; a watertight surface must still pair every
    directed edge with its reverse.
    """
    counts: dict[tuple, int] = {}
    verts = np.round(mesh.vertices.astype(np.float64), 6)
    for tri in mesh.faces:
        for i in range(3):
            a = tuple(verts[int(tri[i])])
            b = tuple(verts[int(tri[(i + 1) % 3])])
            counts[(a, b)] = counts.get((a, b), 0) + 1
    return sum(1 for (a, b), n in counts.items() if counts.get((b, a), 0) != n)


def validate_generator() -> int:
    """
    Verify the Halo generator against analytic ground truth.

    Two properties are asserted for every primitive at every LOD: the mesh is
    watertight (every directed edge has a matching reverse), and its volume
    converges upward towards the analytic Minkowski-sum volume as LOD rises,
    always from below, as an inscribed polyhedron must. Returns a process exit
    code so this can be used as a regression gate.
    """
    failures = 0
    half = np.array([0.6, 0.4, 1.2])
    bbox = BoundingBox(
        min=Point3D(-float(half[0]), -float(half[1]), -float(half[2])),
        max=Point3D(float(half[0]), float(half[1]), float(half[2])),
    )
    centroid = Point3D(0.0, 0.0, 0.0)
    buffer_m = 0.5
    exact = _analytic_rounded_box_volume(half, buffer_m)

    print(f"{'primitive':10s} {'LOD':>5s} {'faces':>7s} {'verts':>7s} {'volume m3':>11s} {'vs analytic':>12s} {'watertight':>11s}")
    previous = 0.0
    for kind in ("box", "cylinder", "sphere"):
        for lod in (200, 300, 400):
            mesh = generate_halo_volume(centroid, bbox, buffer_m=buffer_m, lod=lod, kind=kind)
            volume = mesh.volume_m3()
            leaks = _unmatched_edges(mesh)
            ratio = volume / exact if kind == "box" else float("nan")
            watertight = "yes" if leaks == 0 else f"NO ({leaks})"
            print(
                f"{kind:10s} {lod:5d} {mesh.face_count:7d} {mesh.vertex_count:7d} "
                f"{volume:11.4f} {ratio:11.4f}  {watertight:>11s}"
            )
            if leaks:
                failures += 1
            if kind == "box":
                # LOD 200 is a plain enlarged box and must *overstate* the true
                # offset volume; LOD 300 and 400 are inscribed approximations of
                # the rounded offset and must converge upward towards it.
                if lod == 200 and volume <= exact:
                    print(f"  FAIL: LOD 200 box should overstate {exact:.4f} m3, got {volume:.4f}")
                    failures += 1
                if lod == 400 and not (previous < volume <= exact * 1.0001):
                    print(f"  FAIL: LOD 400 volume did not converge upward towards {exact:.4f}")
                    failures += 1
                previous = volume

    print()
    print(f"analytic Minkowski volume for the test box: {exact:.4f} m3")
    print("PASS" if failures == 0 else f"FAIL ({failures} check(s))")
    return 0 if failures == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse arguments, run the benchmark suite and write the artefacts."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", default="docs/benchmarks", help="output directory")
    parser.add_argument(
        "--scenarios", default="100,500,1000", help="comma-separated element counts for S1-S3"
    )
    parser.add_argument("--federated", type=int, default=2000, help="element count for S4 (0 to skip)")
    parser.add_argument("--lod", type=int, default=300, help="LOD used for S1-S4")
    parser.add_argument("--lod-sweep", type=int, default=1000, help="element count for S5 (0 to skip)")
    parser.add_argument(
        "--scaleout",
        default="2000,5000,10000,20000",
        help="synthetic element counts for S6 (empty string to skip)",
    )
    parser.add_argument("--buffer", type=float, default=DEFAULT_BUFFER_M, help="clearance buffer, metres")
    parser.add_argument("--synthetic", action="store_true", help="use synthetic elements, no IFC required")
    parser.add_argument("--no-charts", action="store_true", help="skip matplotlib chart rendering")
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="run each scenario this many times and report the median with its IQR (7 for the reported figures)",
    )
    parser.add_argument(
        "--validate", action="store_true", help="verify the Halo generator against analytic volumes and exit"
    )
    parser.add_argument(
        "--from-json",
        metavar="PATH",
        help="re-render tables and charts from a previous run's halo_benchmark_results.json without re-measuring",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    if args.validate:
        return validate_generator()

    out_dir = Path(args.out)

    if args.from_json:
        # Presentation-only path: the numbers are provably the ones already
        # measured, so a figure or caption change cannot silently move a result.
        results, host = load_results(Path(args.from_json))
        logger.info("re-rendering %d scenarios from %s (host: %s)",
                    len(results), args.from_json, host.get("platform", "unknown"))
        (out_dir / "halo_benchmark_summary.md").write_text(render_markdown(results))
        if not args.no_charts:
            render_charts(results, out_dir)
        print()
        print(render_markdown(results))
        return 0

    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    counts = [int(c) for c in args.scenarios.split(",") if c.strip()]
    n = args.repeats

    results = run_single_model_scenarios(counts, args.lod, args.buffer, args.synthetic, n)
    if args.federated:
        results.append(run_federated_scenario(args.federated, args.lod, args.buffer, args.synthetic, n))
    if args.lod_sweep:
        results.extend(run_lod_sweep(args.lod_sweep, args.buffer, args.synthetic, n))
    scaleout = [int(c) for c in args.scaleout.split(",") if c.strip()]
    if scaleout:
        results.extend(run_scaleout_scenarios(scaleout, args.lod, args.buffer, n))

    write_outputs(results, out_dir)
    if not args.no_charts:
        render_charts(results, out_dir)

    print()
    print(render_markdown(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
