# Halo spatial reservation — performance characterisation and bottleneck analysis

**The question this answers.** At examination it was noted that the report "would benefit from
more detail on how the geometric engine will handle high-poly IFC geometry when generating
thousands of 'Halo' volumes simultaneously." That is a question about cost, and the only
defensible answer is a measured one. This document reports what `performance_benchmark.py`
measures, what it does not, and where the real constraint turns out to lie — which is not where
the claim implies.

**Statistics.** Every scenario was run **n = 7 times end to end**, re-parsing and re-triangulating
the source model on each repeat. Figures are reported as the **median with the inter-quartile
range** rather than the mean and standard deviation: a benchmark timing is bounded below by the
true cost of the work and unbounded above by scheduler interference on a shared virtual host, so
the distribution is right-skewed and a single stall drags the mean while leaving the median
untouched. Any metric whose IQR exceeds 20% of its median is flagged rather than quietly reported
(section 3.6). Quantities that must not vary between repeats — triangle counts, volumes,
interfering-pair counts — are checked for agreement across all seven runs instead of averaged.

> **These figures supersede the earlier single-run measurements entirely.** They were produced on
> a different interpreter (Python 3.11.15, after the project's `requires-python` was relaxed
> upstream, against 3.12.3 previously). The two sets must not be mixed or compared: where a number
> here differs from the earlier draft, this one is correct.

**Scope and honesty note.** The Halo generator benchmarked here is a **standalone prototype**. It
is not imported by any route or module in the live application, and generating clearance volumes
is not part of any user-facing workflow today. What follows characterises the cost of a capability
that has now been built and measured, not one that is in production. The generator reuses the
project's own `Point3D`/`BoundingBox` primitives from `piping_schema.py` and the same
`ifcopenshell.geom` ingestion path the live pipeline uses, so the ingestion figures transfer
directly to the platform as it stands; the Halo figures characterise the prototype.

**Reproduce with:**

```bash
uv sync
uv run python performance_benchmark.py --validate      # generator correctness
uv run python performance_benchmark.py --repeats 7     # full suite -> docs/benchmarks/
```

Re-rendering tables and figures from a completed run, without re-measuring:

```bash
uv run python performance_benchmark.py --from-json docs/benchmarks/halo_benchmark_results.json
```

---

## 1. What a Halo is, computationally

A Halo is the clearance volume that must remain unobstructed around an element — for BIMGuard's
purposes, the 500 mm seismic-bracing and maintenance access allowance of the kind clause 2.4.3 in
the SS316 case study demands. Geometrically it is a **Minkowski sum**: the element's solid, swollen
by a sphere of the buffer radius.

The prototype approximates that sum from the element's axis-aligned bounding box using one of
three primitives, selected by IFC class:

| Source class | Primitive | Rationale |
|---|---|---|
| `IfcPipeSegment`, `IfcDuctSegment`, cable segments/carriers | Cylinder about the dominant bbox axis | Clearance around a linear run is a sleeve |
| Fittings, valves, junctions, terminals, flanges, accessories | Sphere | Point-like components need omnidirectional access |
| Everything else (walls, slabs, columns, beams, proxies) | Rounded box (exact box ⊕ sphere) | Prismatic elements need an offset prism with filleted edges |

**The decisive design property is in that first column: the Halo is generated from the element's
bounding box, not from its triangulation.** Halo cost is therefore O(1) in the source element's
polygon count. A 40 000-triangle imported valve and a 12-triangle extruded pipe produce identically
priced Halos. This is what makes the high-poly concern tractable: the source model's polygon count
is paid exactly once, during ingestion, and never again per Halo.

### 1.1 Generator correctness

Performance figures are worthless if the geometry is wrong, so the generator is verified before it
is timed. `--validate` asserts two properties for every primitive at every LOD:

| Primitive | LOD | Faces | Vertices | Volume (m³) | vs. analytic | Watertight |
|---|---:|---:|---:|---:|---:|---|
| box | 200 | 12 | 8 | 13.4640 | **1.1180** | yes |
| box | 300 | 112 | 74 | 11.5776 | 0.9613 | yes |
| box | 400 | 336 | 202 | 11.9224 | 0.9900 | yes |
| cylinder | 200 / 300 / 400 | 32 / 64 / 128 | 18 / 34 / 66 | 11.64 / 12.59 / 12.84 | — | yes |
| sphere | 200 / 300 / 400 | 48 / 224 / 960 | 26 / 114 / 482 | 22.08 / 26.93 / 28.27 | — | yes |

*Test element: 1.2 × 0.8 × 2.4 m box, 0.5 m buffer. Analytic ground truth is the Steiner formula
for a box Minkowski-summed with a sphere, 12.0434 m³. Watertightness is tested by matching every
directed edge against its reverse by vertex position, not index, because the generator
deliberately duplicates vertices at seams. These values are exact and identical on every run.*

Two results in that table matter for clearance work:

* **LOD 200 overstates the reserved volume by 11.8%.** A naively enlarged box has square corners
  where the true offset surface is filleted. At LOD 200 that error is systematically
  *conservative* — the volume is too large, so a clash is reported where none exists. That is the
  right direction for a coarse first pass, but it is not free: on a dense MEP model an 11.8%
  over-reservation is a meaningful source of false positives.
* **LOD 300 and 400 converge upward towards the analytic volume from below** (0.9613, 0.9900), as
  inscribed polyhedral approximations must. LOD 400 is within 1% of exact.

---

## 2. Measured results

Host: 4-core x86-64 Linux VM, 15.7 GB RAM, Python 3.11.15, IfcOpenShell 0.8.5, NumPy 2.4.6. Source
models are the repository's own IFC fixtures; `BUILDING_R4.ifc` (IFC4, 2 602 products, 2 589 with
geometry) supplies the single-model scenarios. **All timings are medians of n = 7, IQR in
parentheses.**

### Table A — end-to-end scaling

| Scenario | Source | Elements | Parse (s) | Triangulate (s) | Halo gen (s) | Halos/s | µs/Halo | Halo arrays (MB) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| S-100 | IFC | 100 | 1.53 (0.14) | 1.84 (0.07) | 0.038 (0.001) | 2,660 | 376 | 0.21 |
| S-500 | IFC | 500 | 1.54 (0.10) | 14.43 (0.33) | 0.202 (0.032) | 2,479 | 403 | 1.06 |
| S-1000 | IFC | 1,000 | 1.55 (0.09) | 30.10 (1.54) | 0.386 (0.007) | 2,591 | 386 | 2.13 |
| S-federated | IFC ×4 | 1,999 | 6.29 (0.62) | 53.42 (2.29) | 0.755 (0.026) | 2,647 | 378 | 4.23 |
| S-lod200 | IFC | 1,000 | 1.52 (0.20) | 30.79 (0.87) | 0.020 (0.003) | 50,251 | 20 | 0.23 |
| S-lod300 | IFC | 1,000 | 1.52 (0.20) | 30.79 (0.87) | 0.386 (0.038) | 2,593 | 386 | 2.13 |
| S-lod400 | IFC | 1,000 | 1.52 (0.20) | 30.79 (0.87) | 0.490 (0.030) | 2,040 | 490 | 6.16 |
| S-scale2000 | synthetic | 2,000 | — | — | 0.468 (0.004) | 4,274 | 234 | 4.15 |
| S-scale5000 | synthetic | 5,000 | — | — | 1.206 (0.034) | 4,148 | 241 | 10.37 |
| S-scale10000 | synthetic | 10,000 | — | — | 2.460 (0.096) | 4,065 | 246 | 20.74 |
| S-scale20000 | synthetic | 20,000 | — | — | 5.116 (0.169) | 3,910 | 256 | 41.47 |

Resident-memory growth during generation was at or below 0.3 MB in every scenario and is omitted
from the table for that reason; it is in the results CSV. The federated scenario loads four
genuinely distinct IFC files (architectural, institutional, residential and
infrastructure-plumbing), allocating element quotas in proportion to what each model can supply,
and runs interference detection across model boundaries.

### Table B — geometric complexity (deterministic)

Every value in this table was **identical on all seven repeats of every scenario** — the
determinism check passed with no exceptions. Only wall-clock and resident memory vary between runs.

| Scenario | Source triangles | Halo triangles | Amplification | Mean Halo volume (m³) | Total reserved (m³) |
|---|---:|---:|---:|---:|---:|
| S-100 | 20,720 | 11,200 | 0.54× | 21.47 | 2,147 |
| S-500 | 248,504 | 56,000 | 0.23× | 15.03 | 7,516 |
| S-1000 | 533,320 | 112,000 | **0.21×** | 14.23 | 14,231 |
| S-federated | 737,661 | 222,672 | 0.30× | 49.45 | 98,857 |
| S-lod200 | 533,320 | 12,000 | 0.02× | 16.22 | 16,224 |
| S-lod400 | 533,320 | 336,000 | 0.63× | 14.60 | 14,597 |

**The amplification column is the direct answer to the examiner's question.** Generating a Halo
for every element in a 533 320-triangle model adds 112 000 triangles — the Halo layer is roughly
one fifth the size of the geometry it wraps, and at LOD 200 one fiftieth. Halos do not multiply
high-poly geometry; they *replace* it with a small, uniform-cost proxy. The amplification factor
falls as models get more detailed, because source triangle counts scale with authoring detail
while Halo triangle counts are fixed per element by LOD alone.

### Table C — interference detection

| Scenario | Halos | Grid: broad + mid (s) | Exhaustive O(n²) (s) | Speed-up | Candidate pairs | Interfering pairs | Cross-model |
|---|---:|---:|---:|---:|---:|---:|---:|
| S-100 | 100 | 0.002 | 0.002 | 0.9× | 544 | 259 | 0 |
| S-500 | 500 | 0.022 | 0.012 | 0.6× | 12,768 | 4,569 | 0 |
| S-1000 | 1,000 | 0.073 | 0.037 | 0.5× | 46,518 | 13,102 | 0 |
| S-federated | 1,999 | 0.154 | 0.117 | 0.8× | 81,609 | 27,434 | **3,916** |
| S-scale2000 | 2,000 | 0.036 | 0.114 | **3.2×** | 25,736 | 1,875 | 0 |
| S-scale5000 | 5,000 | 0.113 | 0.622 | 5.5× | 71,835 | 5,071 | 0 |
| S-scale10000 | 10,000 | 0.273 | 2.394 | 8.8× | 150,203 | 11,041 | 0 |
| S-scale20000 | 20,000 | 0.730 | 9.411 | **12.9×** | 304,805 | 22,869 | 0 |

---

## 3. Bottleneck analysis

### 3.1 Where the time actually goes

Shares are computed against the sum of the stage medians, because medians are not additive and
dividing by the median of the per-run totals would not sum to 100%.

| Scenario | IFC ingest (parse + triangulate) | Halo generation | Interference |
|---|---:|---:|---:|
| S-100 | **98.8%** | 1.10% | 0.06% |
| S-1000 | **98.6%** | 1.20% | 0.23% |
| S-federated | **98.5%** | 1.25% | 0.25% |
| S-scale20000 (no ingest) | — | 87.5% | 12.5% |

**Halo generation is not the bottleneck, and is not close to being the bottleneck.** On the
1 000-element scenario it accounts for 1.20% of wall-clock. IFC ingestion accounts for 98.6%, of
which triangulation alone is 93.7%. The 2 000-element federated coordination run completes in a
median 60.6 s end-to-end, of which 0.76 s is Halo generation and 53.4 s is triangulation.

This inverts the premise of the original concern. The risk in "generating thousands of Halo
volumes simultaneously" is not the Halos. It is that you must first read thousands of high-poly
elements out of IFC, and *that* is a cost the platform already pays today for every compliance
check, Halos or not.

### 3.2 The three regimes

1. **Ingestion-bound (any IFC-backed run).** `ifcopenshell.geom.iterator` triangulates a median
   33.2 elements/s on 4 cores against `BUILDING_R4.ifc`. This is the constraint on every figure in
   Table A that has a Triangulate column. The rate is stable across scenarios (32.5–37.4/s) once
   past the 100-element case, where a fixed ~1.5 s parse cost dominates.
2. **Generation-bound (cached ingestion).** Halo generation is close to linear, at 234 µs/element
   at 2 000 elements rising to 256 µs at 20 000 — **a 9% increase across a tenfold range.** It is
   not perfectly flat; the drift is consistent with allocator and cache pressure as the retained
   mesh population grows, and it is small enough that a linear model remains a good predictor.
3. **Interference-bound (very large populations).** Even at 20 000 volumes, pair-finding is 12.5%
   of the no-ingest total; it does not become the dominant cost within the measured range.

### 3.3 The broad-phase crossover — a negative result worth reporting

At the scales the real fixtures supply, **the uniform spatial hash grid is slower than exhaustive
pair testing** (0.5×–0.9× in Table C). This is not a defect in the grid; it is a consequence of
comparing a pure-Python O(n) algorithm against a NumPy-vectorised O(n²) one. Below roughly 1 500
volumes, the vectorised exhaustive test wins on constant factors alone.

The crossover sits between 1 000 and 2 000 volumes, after which the asymptotics assert themselves:
3.2× at 2 000, 5.5× at 5 000, 8.8× at 10 000, 12.9× at 20 000. The practical recommendation is
therefore a **hybrid**: exhaustive vectorised AABB testing below ~2 000 Halos, hash-grid
broad-phase above it. Choosing the grid unconditionally would make small coordination runs
measurably slower, and this is only visible because both were measured rather than one assumed.

### 3.4 Memory is not a constraint

Halo meshes are stored as float32 vertices and int32 faces, giving 2.13 MB per 1 000 Halos at
LOD 300 — 41.47 MB at 20 000. These are exact byte counts, not estimates, and are deterministic.
Process RSS growth during generation was at or below 0.3 MB in every scenario, because the source
triangulations are discarded as they are consumed: only the bounding box and centroid are retained
per element, roughly 100 bytes against the tens of kilobytes a high-poly mesh occupies. **Peak
memory tracks element count, not source polygon count** — the second half of the answer to the
high-poly question.

### 3.5 Level of detail is the main cost lever

| LOD | Triangles per box Halo | Median time per 1 000 Halos | Volume error vs. exact |
|---:|---:|---:|---:|
| 200 | 12 | 0.020 s (IQR 0.003) | +11.8% (over-reserves) |
| 300 | 112 | 0.386 s (IQR 0.038) | −3.9% |
| 400 | 336 | 0.490 s (IQR 0.030) | −1.0% |

LOD 200 is **19× faster** than LOD 300 and produces a ninth of the triangles, at the cost of
systematically over-reserving space. This maps cleanly onto a two-pass strategy: LOD 200 for a
whole-model first pass, LOD 400 only on the elements that first pass flags. On the 1 000-element
model that is 0.020 s plus a rounding error, instead of 0.490 s.

### 3.6 Measurement stability

Two metrics out of 88 measured (11 scenarios × 8 metrics) exceeded the 20%-of-median IQR
threshold:

| Scenario | Metric | Median | IQR | IQR as % of median | Verdict |
|---|---|---:|---:|---:|---|
| S-lod200 | broad-phase | 0.0487 s | 0.0102 s | 21% | **Material** — but it is an interference figure in a level-of-detail scenario, and no conclusion in this document rests on it. The equivalent figure at LOD 300 and 400 in the same scenario is stable, so this is host noise rather than a property of the coarse level. |
| S-scale20000 | resident memory | 0.29 MB | 0.31 MB | 107% | **Negligible** — a sub-megabyte delta measured against a 15.7 GB host. The relative spread is large only because the absolute value is near zero. |

Everything else — including every figure this document argues from — came in under the threshold.
The tightest are the ones that carry the most weight: Halo generation at 1 000 elements has an IQR
of 0.007 s on a 0.386 s median (1.8%), and at 20 000 elements 0.169 s on 5.116 s (3.3%).
Triangulation is looser at 1.54 s on 30.10 s (5.1%), which is expected for a multiprocess stage on
a 4-core host.

---

## 4. Extrapolation to "thousands of Halo volumes"

Taking the measured per-element costs and holding hardware constant:

| Halo volumes | Generation, LOD 300 | Generation, LOD 200 | Interference (grid) | Halo memory | Cold ingestion |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.39 s ᵐ | 0.020 s ᵐ | 0.07 s ᵐ | 2.13 MB ᵐ | ~30 s ᵐ |
| 5,000 | 1.21 s ᵐ | ~0.10 s | 0.11 s ᵐ | 10.37 MB ᵐ | ~151 s |
| 10,000 | 2.46 s ᵐ | ~0.20 s | 0.27 s ᵐ | 20.74 MB ᵐ | ~301 s |
| 20,000 | 5.12 s ᵐ | ~0.40 s | 0.73 s ᵐ | 41.47 MB ᵐ | ~602 s |
| 50,000 | ~12.8 s | ~1.0 s | ~2.0 s | ~104 MB | ~25 min |

*ᵐ = measured median of n = 7. Unmarked cells are extrapolated. The LOD 200 column scales the
20 µs per-element cost measured at 1 000 elements; the 50 000 LOD 300 row uses the 256 µs
per-element cost measured at 20 000 rather than the 234 µs measured at 2 000, since per-element
cost drifts upward with population (section 3.2) — so it over-estimates a strictly linear model
and under-estimates the outcome if that drift continues. Ingestion figures are extrapolated from
the measured 33.2 elements/s and are the least reliable column here, since triangulation cost
varies with per-element geometric complexity, not just element count.*

**Verdict on the claim.** Generating tens of thousands of Halo volumes is comfortably tractable:
20 000 volumes in a median 5.12 s and 41.5 MB, with interference detection in under a second. The
claim survives the scrutiny. What does *not* survive is the implicit assumption that generation is
the hard part — at 10 000 elements, a cold run spends ~301 s in IFC triangulation and 2.46 s making
Halos, a ratio of roughly **122:1**.

---

## 5. What to build, in priority order

1. **Cache the ingestion, not the meshes.** Halo generation needs only `(guid, centroid, bbox,
   ifc_type)` — about 100 bytes per element. Persisting that per model version turns every run
   after the first from ~301 s into ~2.5 s for 10 000 elements. This is the single highest-value
   optimisation available, it removes 98% of the wall-clock, and it needs no new geometry code.
2. **Re-triangulate only changed GUIDs between model drops.** In the weekly coordination cycle the
   inter-drop delta is a small fraction of the model, so incremental ingestion compounds with (1).
3. **Adopt the hybrid interference strategy** of section 3.3 with the crossover at ~2 000 volumes,
   rather than committing to either algorithm unconditionally.
4. **Default to LOD 200 for the first pass**, escalating to LOD 400 only on flagged elements, and
   document the +11.8% conservative bias so users understand why the coarse pass over-reports.
5. **Add exact narrow-phase testing.** The current mid-phase is an AABB overlap test, which is
   conservative: it reports overlapping bounding boxes, not overlapping volumes. Separating-axis
   or triangle-intersection testing on the pairs that survive the mid-phase would eliminate the
   remaining false positives, and would run on a small fraction of pairs.
6. **Only then consider a different geometry backend.** The main report listed evaluating
   `trimesh` for Halo work as a possible future addition. On this evidence that is premature: the
   current `ifcopenshell.geom` + NumPy stack generates ~4 000 watertight Halos/s and the bottleneck
   is elsewhere entirely. `trimesh` would earn its place for exact boolean narrow-phase work
   (item 5), not for generation.

---

## 6. Threats to validity

Stated plainly, because these bound how far the figures above can be pushed.

1. **Seven repeats is enough for a median, not for a tail.** n = 7 gives a stable central estimate
   and a usable IQR, but says little about worst-case latency, which is what a user actually feels
   on a bad run. The maximum observed is in the results JSON per metric; nothing here models a
   99th percentile.
2. **The first repeat is systematically the slowest** — cold file cache, cold allocator — and it
   was deliberately *not* discarded as a warm-up. A user's first run is also cold, so including it
   is the honest choice, but it inflates the IQR slightly relative to a steady-state benchmark.
3. **One host, four cores.** Triangulation is the parallel stage and uses `cpu_count()`, so the
   ingestion figures should improve close to linearly with core count — untested here. The
   interpreter also changed between this run and the earlier single-run draft (3.11.15 against
   3.12.3), which is why the two sets must not be mixed.
4. **The source models are architectural, not MEP-dense.** `BUILDING_R4.ifc` is walls, columns,
   windows and slabs, so most Halos took the rounded-box path. A real plant room dominated by pipe
   segments and fittings would be *faster* per element (cylinders and spheres are cheaper) but
   spatially far denser, which raises the candidate-pair count.
5. **Synthetic elements sit on a uniform lattice.** Real buildings are spatially clustered, which
   degrades uniform-grid performance relative to the S-scale figures. The crossover point of
   section 3.3 should be re-measured on a genuinely large real model before being treated as
   settled.
6. **AABB mid-phase, not exact intersection.** Interfering-pair counts in Table C are upper
   bounds.
7. **Bounding-box Halos are an approximation of the Minkowski sum of the true solid.** For a
   diagonal brace or a swept bend, the bbox-derived Halo over-reserves — correct in direction for
   a clearance check, but a source of false positives that a swept-solid Halo would avoid.
8. **The 2 000-element federated set is four architectural models, not a real multi-discipline
   federation.** It exercises the cross-model code path (3 916 cross-model interfering pairs) but
   is not a substitute for validating on a real coordinated data-centre or hospital model.

---

## 7. Figures and data

Figures are rendered at 300 DPI, sized to a 160 mm thesis column, with median ± IQR error bars and
one shared palette in which a colour always means the same stage or algorithm. They carry no
embedded titles: ready-to-paste captions are generated into `halo_benchmark_summary.md`.

| File | Content |
|---|---|
| `fig1_stage_cost.png` | Stage cost vs. element count (log) — the separation between triangulation and Halo generation |
| `fig2_throughput.png` | Halo generation throughput by element count |
| `fig3_memory.png` | Halo array footprint against process resident-memory growth |
| `fig4_collision.png` | Grid vs. exhaustive interference detection on the IFC-backed runs |
| `fig5_lod.png` | Level of detail: triangle count and generation cost, as two panels |
| `fig6_bottleneck.png` | Stage share of wall-clock across every scenario |
| `fig7_scaleout.png` | Scale-out to 20 000 volumes and the broad-phase crossover |

| Data file | Content |
|---|---|
| `halo_benchmark_results.json` | Host metadata, per-metric median/quartiles, and every raw sample |
| `halo_benchmark_results.csv` | One row per scenario: median, Q1, Q3, IQR and IQR% per metric |
| `halo_benchmark_raw_repeats.csv` | One row per (scenario, repeat), in run order |
| `halo_benchmark_summary.md` | Rendered tables plus the ready-to-paste figure captions |
