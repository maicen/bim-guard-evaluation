# GC-001 Galvanic Series — MIL-STD-889B Validation

Independent validation of the seeded `BIMGUARD-GC-001` galvanic potentials
against an authoritative external reference, and the vocabulary expansion
derived from the same source.

| | |
| --- | --- |
| Reference standard | MIL-STD-889B (USAF), Notices 1–3 |
| Reference table | Table II, *Galvanic series of selected metals in seawater* |
| Attribution | Army Missile Command Report RS-TR-67-11, *Practical Galvanic Series* |
| Acquisition | Firecrawl scrape → `docs/scraped_standards/corrosion_mil_std_889_galvanic.md` |
| Structured extract | `data/reference/mil_std_889b_table_ii.json` (93 entries) |

> **Citation note.** The scraped copy is a third-party PDF mirror, and
> MIL-STD-889B is superseded by 889D. The final citation should reference an
> ASSIST/EverySpec original. This does not affect the validation result, which
> depends only on Table II's ordering.

## 1. Why the series could not simply be imported

MIL-STD-889B Table II is **ordinal**. It ranks 93 alloys from most active to
most noble and publishes no electrode potentials. GC-001 is **interval**: it
scores a couple on `abs(anode_potential - cathode_potential)` against a
per-environment voltage threshold of 0.10–0.50 V.

Converting rank to voltage would mean inventing the interval data — attributing
fabricated numbers to a military standard. The standard forecloses the shortcut
itself, at §30.4:

> Standard electrode potentials of metals are of little value in establishing
> galvanic corrosion relationships in actual environments.

Its Table IA does publish volts (Mg²⁺ −2.37 … Au⁺ +1.69), but those are
pure-element equilibrium potentials: no alloys, no active/passive states, and
disclaimed for this purpose by the passage above.

Table II was therefore used as an **ordinal check on the existing seeded
potentials**, not as a replacement for them.

## 2. Validation result

Harness: `scripts/validate_galvanic_potentials.py` (exit 1 when inversions
are found).

17 of the 20 seeded materials map to a Table II counterpart, giving 136 ordered
pairs. **132 pairs concordant — 97%.**

| Catalog key | Potential (V) | Table II rank |
| --- | --- | --- |
| magnesium | 0.95 | 2 |
| galv_steel | 0.82 | 4 |
| zinc | 0.80 | 4 |
| cadmium | 0.75 | 10 |
| aluminium | 0.70 | 17 |
| carbon_steel | 0.55 | 31 |
| cast_iron | 0.52 | 32 |
| ss304_active | 0.38 | 41 |
| bronze | 0.34 | 63 |
| brass | 0.32 | 51 |
| copper | 0.28 | 45 |
| ss316_active | 0.22 | 68 |
| silver_solder | 0.18 | — |
| hastelloy_c | 0.14 | — |
| ss304_passive | 0.12 | 72 |
| ss316_passive | 0.08 | 77 |
| titanium | 0.05 | 86 |
| graphite | 0.03 | 93 |
| gold | 0.02 | 92 |
| platinum | 0.00 | — |

### The four inversions

| Pair | Potential order | Table II order |
| --- | --- | --- |
| bronze / brass | bronze more active (0.34 vs 0.32) | brass more active (63 vs 51) |
| bronze / copper | bronze more active (0.34 vs 0.28) | copper more active (63 vs 45) |
| brass / copper | brass more active (0.32 vs 0.28) | copper more active (51 vs 45) |
| graphite / gold | graphite more active (0.03 vs 0.02) | gold more active (93 vs 92) |

All four fall inside two tight clusters — the copper family spans 0.06 V and
gold/graphite 0.01 V. Both are below the most sensitive environment threshold
(0.10 V, `E5_EXPOSED`), so a couple drawn from within either cluster scores a
gap well under threshold and lands in the Low band regardless of which member
is nominally the anode. The disagreement is about anode designation within a
cluster, not about any verdict the engine issues.

**No recalibration is indicated.**

### Method caveats

- Mapping 20 generic families onto 93 specific alloys is engineering judgement,
  recorded explicitly in `TABLE_II_MAPPING` so it can be audited rather than
  inferred from string matching.
- Generic families take the **median** rank of their matched entries;
  `aluminium` spans 19 Table II entries (ranks 6–27) and `brass` spans 7.
- `silver_solder`, `hastelloy_c` and `platinum` have no Table II counterpart
  and are excluded rather than forced onto an approximate neighbour.
- Rank distance is not proportional to potential difference. Ordinal adjacency
  was used only to corroborate ordering, never to derive a magnitude.

## 3. Vocabulary expansion

Script: `scripts/map_mil_std_synonyms.py`. 79 of 93 designations mapped to 143
`material_alias` rule rows (`BIMGUARD-GC-001`), consumed via
`corrosion_rule_catalog.load_gc_catalog()` and merged into the engine's
`MATERIAL_ALIASES` with `setdefault`, so the built-in table stays authoritative.

Recognition of Table II designations rose from **66/93 to 81/93**.

### Defect found during expansion

Every *active* stainless grade previously resolved to **passive** SS316:

```
Stainless steel 304 (active)   ss316_passive (0.08 V) -> ss304_active (0.38 V)
Stainless steel 410 (active)   ss316_passive (0.08 V) -> ss304_active (0.38 V)
```

A 0.30 V error, exceeding all four environment thresholds. The active/passive
distinction was present in the seeded series but unreachable through material
resolution.

### Greedy substring defect

`resolve_material()` falls back to substring containment, which short chemical
symbols hijack:

| Input | Resolved (before) | Cause |
| --- | --- | --- |
| `Tantalum` | `aluminium` | contains "al" |
| `Tin (plated)` | `titanium` | contains "ti" |
| `AM350 (active)` | `titanium` | "active" contains "ti" |

Aliases of three characters or fewer now require a word boundary
(`_alias_matches`). Longer aliases retain plain containment.

### Noble metals added to the built-in table

Unrecognised metals default to `carbon_steel` (0.55 V). For a noble metal that
is not conservative — it reads as strongly anodic and can invert the couple's
anode/cathode assignment.

| Alias | Mapped to | Basis |
| --- | --- | --- |
| nickel, monel, monel 400, cupronickel | `hastelloy_c` (0.14 V) | Only nickel-base alloy in the catalog; Table II ranks Nickel (35) and Monel 400 (64) nobler than copper |
| tantalum | `titanium` (0.05 V) | Valve metal with a stable passive oxide film. **Approximate** — Table II ranks tantalum at 37, mid-series, against wider literature placing it among the most noble metals; this mapping follows the literature |
| tungsten | `copper` (0.28 V) | Table II rank 45 coincides with the median rank of the catalog's copper entries |

Beryllium, uranium, indium, tin, lead, chromium, niobium, molybdenum and pure
silver remain deliberately unmapped — no defensible counterpart exists among
the 20 catalog materials, and forcing one would be worse than the default.

## 4. Reproduction

```bash
python scripts/parse_mil_std_889_series.py        # scrape -> structured JSON
python scripts/validate_galvanic_potentials.py    # exit 1 while inversions stand
python scripts/map_mil_std_synonyms.py --dry-run  # inspect before writing
python scripts/map_mil_std_synonyms.py            # write material_alias rows
```
