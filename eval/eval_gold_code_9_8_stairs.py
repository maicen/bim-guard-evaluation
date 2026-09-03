"""
eval_gold_code_9_8_stairs.py
------------------------------------------------
Hand-annotated ground truth for CODE Part 9, Sections 9.8.2-9.8.4.7 (stairs),
sourced verbatim from data/uploads/..._pdf_stairs_mock.pdf — the same document
code_seed_rules.py's stair entries were originally derived from, extended here
to cover the WHOLE section (table rows, relative-bound tread rules, tolerances,
winders, spiral stairs) rather than just the ~10 clauses seeded so far.

Used by score_rule_extraction.py to measure rule-extraction accuracy
against a known-correct answer key instead of eyeballing output.

Field names match the LiteLLMRuleExtractor / RuleConverter schema
(app/services/rule_extractor.py, app/modules/rule_builder/rule_converter.py).

GOLD_RULES: clauses that ARE discrete, checkable requirements — every one of
these should show up in extracted output with the right target/property/value.

EXCLUDED_CLAUSES: clauses that are NOT expressible as a single discrete
checkable rule (definitional, occupant-load-dependent table lookups, or no
clean IFC property mapping). A good pipeline should skip these, not
hallucinate a fabricated numeric rule for them — used to check precision,
not just recall.
"""

SOURCE_TEXT = """\
9.8.2. Stair Dimensions

9.8.2.1. Stair Width

(1) Except as provided in Sentence (2) and Article 9.8.4.5A., required exit stairs and public stairs serving buildings
of residential occupancy shall have a width, measured between wall faces or guards, of not less than 900 mm.

(2) Required exit stairs serving a house or an individual dwelling unit shall have a width of not less than 860 mm.

(3) Except as provided in Article 9.8.4.5A., required exit stairs and public stairs serving buildings of other than
residential occupancy shall have a width of not less than the greater of,
(a) 900 mm, or
(b) 8 mm per person based on the occupant load limits specified in Table 3.1.17.1.

(4) Except as provided in Article 9.8.4.5A., at least one stair between each floor level within a dwelling unit and
exterior stairs serving a house or an individual dwelling unit shall have a width of not less than 860 mm.

9.8.2.2. Height over Stairs

(1) The clear height over stairs shall be measured vertically, over the clear width of the stair, from a straight line
tangent to the tread and landing nosings to the lowest point above.

(2) Except as provided in Sentence (3) and Article 9.8.4.5A., the clear height over stairs shall not be less than 2 050 mm.

(3) Except as provided in Article 9.8.4.5A., the clear height over stairs serving a house or an individual dwelling
unit shall not be less than 1 950 mm.

9.8.3. Stair Configurations

9.8.3.1. Straight and Curved Runs in Stairs

(1) Except as permitted in Sentence (2), stairs shall consist of,
(a) straight flights,
(b) curved flights, or
(c) spiral stairs.

(2) Stairs within houses and individual dwelling units may consist of,
(a) flights with rectangular treads and winders provided winders as described in Article 9.8.4.5. are installed
between floor levels, or
(b) flights with a mix of rectangular and tapered treads provided all tapered treads within a flight turn in the same
direction.

(3) Curved flights in exits shall comply with Sentence 3.4.6.9.(2).

(4) Spiral stairs shall comply with Article 9.8.4.5A.

9.8.3.2. Minimum Number of Risers

(1) Except for stairs within a dwelling unit, at least three risers shall be provided in interior flights.

9.8.3.3. Maximum Height of Flights

(1) The vertical height of a flight shall not exceed 3.7 m.

9.8.4. Step Dimensions

9.8.4.1. Dimensions for Risers

(1) Except as provided in Article 9.8.4.5A., the rise, which is measured as the vertical nosing-to-nosing distance,
shall conform to Table 9.8.4.1.

Table 9.8.4.1.
Rise for Rectangular Treads, Tapered Treads and Winders and Run for Rectangular Treads
Forming Part of Sentences 9.8.4.1.(1) and 9.8.4.2.(1)

Item | Column 1 Stair Type | Column 2 Max. Rise, mm, for All Steps | Column 3 Min. Rise, mm, for All Steps | Column 4 Max. Run, mm, for Rectangular Treads | Column 5 Min. Run, mm, for Rectangular Treads
1. Private stairs(1) | 200 | 125 | 355 | 255
2. Public stairs(2) | 180 | 125 | no limit | 280
3. Service stairs(3) | no limit | 125 | 355 | no limit
4. Stairs to unoccupied attic space(4) | no limit | 125 | 355 | no limit
5. Stairs to crawl spaces | no limit | 125 | 355 | no limit
6. Stairs that serve mezzanines not exceeding 20 m2 within live/work units | no limit | 125 | 355 | no limit

Notes to Table 9.8.4.1.:
(1) Private stairs are: (a) interior stairs within a house or an individual dwelling unit, (b) exterior stairs serving
a house or an individual dwelling unit, and (c) exterior stairs serving a garage that serves a house or an individual
dwelling unit.
(2) Public stairs are all stairs not described as service stairs or private stairs.
(3) Service stairs are stairs that serve areas used only as service rooms or service spaces.
(4) Stairs to unoccupied attic space are stairs that serve attics containing no storage or living space.

9.8.4.2. Dimensions for Runs and Rectangular Treads

(1) The run for rectangular treads shall conform to Table 9.8.4.1.

(2) The depth of a rectangular tread shall be not less than its run and not more than its run plus 25 mm.

9.8.4.3. Dimensions for Tapered Treads

(1) Except as provided in Sentence (2) and Articles 9.8.4.5. and 9.8.4.5A., tapered treads shall have a run that,
(a) is not less than 150 mm at the narrow end of the tread, and
(b) complies with the dimensions for rectangular treads specified in Table 9.8.4.1. when measured at a point 300
mm from the centre line of the inside handrail.

(2) Tapered treads in required exit stairs shall conform to the requirements in Article 3.4.6.9.

(3) The depth of a tapered tread shall be not less than its run at any point and not more than its run at any point
plus 25 mm.

9.8.4.4. Uniformity and Tolerances for Risers, Runs and Treads

(1) Except as provided in Sentence (2), risers shall be of uniform height in any one flight with a maximum tolerance of,
(a) 5 mm between adjacent treads or landings, and
(b) 10 mm between the tallest and shortest risers in a flight.

(2) Except for required exit stairs, where the top or bottom riser in a stair adjoins a sloping finished walking surface
such as a garage floor, driveway or sidewalk, the height of the riser across the stair shall vary by not more than 1 in 12.

(3) Rectangular treads shall have uniform run with a maximum tolerance of,
(a) 5 mm between adjacent treads, and
(b) 10 mm between the deepest and shallowest treads in a flight.

(4) Tapered treads in a flight shall have a uniform run in accordance with the tolerances described in Sentence (3)
when measured at a point 300 mm from the centre line of the inside handrail.

(5) The slope of treads shall not exceed 1 in 50.

9.8.4.4A. Uniformity of Runs in Flights with Mixed Treads within a House or Dwelling Unit

(1) Except as provided in Sentence (2) and Article 9.8.4.5., where a flight within a house or individual dwelling
unit consists of both tapered treads and rectangular treads, all the treads shall have a uniform run when measured at
a point 300 mm from the centre line of the inside handrail.

(2) Where tapered treads are located at the bottom of a mixed-tread flight described in Sentence (1), the run of the
tapered treads when measured at a point 300 mm from the centre line of the inside handrail is permitted to exceed the
run of the rectangular treads.

9.8.4.5. Winders

(1) Stairs within dwelling units are permitted to contain winders that converge to a centre point provided,
(a) the winders turn through an angle of not more than 90 degrees,
(b) individual treads turn through an angle of not less than 30 degrees or not more than 45 degrees, and
(c) adjacent winders turn through the same angle.

(2) Where more than one set of winders described in Sentence (1) is provided in a single stairway between adjacent
floor levels, such winders shall be separated in plan by at least 1 200 mm.

9.8.4.5A. Spiral Stairs

(1) Spiral stairs shall have,
(a) handrails on both sides, the outer handrail being not less than 1 070 mm high,
(b) a clear width not less than 660 mm between handrails,
(c) risers that are not more than 240 mm high,
(d) treads that,
(i) are a minimum of 190 mm deep at a point 300 mm from the centre line of the inside handrail,
(ii) have a consistent angle and uniform dimension, and
(iii) turn in the same direction, and
(e) a clear height not less than 1 980 mm.

(2) Spiral stairs conforming to Sentence (1) are permitted to be used as the only means of egress where they serve
not more than 3 persons.

(3) Except as permitted by Sentence (2), spiral stairs shall not serve as an exit.

9.8.4.6. Leading Edges of Treads

(1) Leading edges of treads that are bevelled or rounded shall,
(a) not reduce the required tread depth by more than 15 mm, and
(b) not, in any case, exceed 25 mm horizontally.

9.8.4.7. Interior Stairs Extending through the Roof

(1) Interior stairways extending through the roof of a building shall be protected from ice and snow.
"""

# ── GOLD RULES ──────────────────────────────────────────────────────────────
# Every entry here is a requirement the pipeline SHOULD extract. `ref` is the
# match key the scorer uses to pair extracted rules back to gold.

GOLD_RULES = [
    # ── STAIR WIDTH (9.8.2.1) ────────────────────────────────────────────────
    {"ref": "9.8.2.1.(1)", "target": "IfcStairFlight", "property_name": "Width",
     "operator": ">=", "value": 900, "unit": "mm",
     "applies_when": {"building_use": "residential"},
     "desc": "Exit/public stairs, residential occupancy — min width 900 mm"},
    {"ref": "9.8.2.1.(2)", "target": "IfcStairFlight", "property_name": "Width",
     "operator": ">=", "value": 860, "unit": "mm",
     "desc": "Exit stair serving house/dwelling unit — min width 860 mm"},
    {"ref": "9.8.2.1.(4)", "target": "IfcStairFlight", "property_name": "Width",
     "operator": ">=", "value": 860, "unit": "mm",
     "desc": "At least one stair between floor levels within a dwelling unit — min width 860 mm"},

    # ── HEIGHT OVER STAIRS (9.8.2.2) ─────────────────────────────────────────
    {"ref": "9.8.2.2.(2)", "target": "IfcStairFlight", "property_name": "RequiredHeadroom",
     "operator": ">=", "value": 2050, "unit": "mm",
     "desc": "Clear height over stairs (general case) — min 2050 mm"},
    {"ref": "9.8.2.2.(3)", "target": "IfcStairFlight", "property_name": "RequiredHeadroom",
     "operator": ">=", "value": 1950, "unit": "mm",
     "desc": "Clear height over stairs serving house/dwelling unit — min 1950 mm"},

    # ── STAIR CONFIGURATIONS (9.8.3) ─────────────────────────────────────────
    {"ref": "9.8.3.2.(1)", "target": "IfcStairFlight", "property_name": "NumberOfRiser",
     "operator": ">=", "value": 3, "unit": None,
     "desc": "Minimum risers in interior flights (except dwelling-unit stairs) — at least 3"},
    {"ref": "9.8.3.3.(1)", "target": "IfcStairFlight", "property_name": "FlightHeight",
     "operator": "<=", "value": 3700, "unit": "mm",
     "desc": "Maximum vertical height per stair flight — 3700 mm"},

    # ── TABLE 9.8.4.1 — RISE & RUN BY STAIR TYPE ─────────────────────────────
    {"ref": "Table 9.8.4.1 (private, rise)", "target": "IfcStairFlight", "property_name": "RiserHeight",
     "operator": "between", "value_min": 125, "value_max": 200, "unit": "mm",
     "desc": "Private stairs — riser height between 125 and 200 mm"},
    {"ref": "Table 9.8.4.1 (private, run)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": "between", "value_min": 255, "value_max": 355, "unit": "mm",
     "desc": "Private stairs — tread run/depth between 255 and 355 mm"},
    {"ref": "Table 9.8.4.1 (public, rise)", "target": "IfcStairFlight", "property_name": "RiserHeight",
     "operator": "between", "value_min": 125, "value_max": 180, "unit": "mm",
     "desc": "Public stairs — riser height between 125 and 180 mm"},
    {"ref": "Table 9.8.4.1 (public, run)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": ">=", "value": 280, "unit": "mm",
     "desc": "Public stairs — tread run/depth at least 280 mm (no upper limit)"},
    {"ref": "Table 9.8.4.1 (service, rise)", "target": "IfcStairFlight", "property_name": "RiserHeight",
     "operator": ">=", "value": 125, "unit": "mm",
     "desc": "Service stairs — riser height at least 125 mm (no upper limit)"},
    {"ref": "Table 9.8.4.1 (service, run)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": "<=", "value": 355, "unit": "mm",
     "desc": "Service stairs — tread run/depth at most 355 mm (no lower limit)"},

    # ── RELATIVE-BOUND TREAD RULES (9.8.4.2 / 9.8.4.3) ───────────────────────
    # The exact pattern the value_min/max_property feature was built for.
    {"ref": "9.8.4.2.(2)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": "between",
     "value_min_property": "Run", "value_min_offset": 0,
     "value_max_property": "Run", "value_max_offset": 25, "unit": "mm",
     "desc": "Rectangular tread depth must be between its own run and run + 25 mm"},
    {"ref": "9.8.4.3.(1)(a)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": ">=", "value": 150, "unit": "mm",
     "desc": "Tapered tread run — not less than 150 mm at the narrow end"},
    {"ref": "9.8.4.3.(3)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": "between",
     "value_min_property": "Run", "value_min_offset": 0,
     "value_max_property": "Run", "value_max_offset": 25, "unit": "mm",
     "desc": "Tapered tread depth must be between its own run and run + 25 mm"},

    # ── TOLERANCES (9.8.4.4) ──────────────────────────────────────────────────
    {"ref": "9.8.4.4.(1)(a)", "target": "IfcStairFlight", "property_name": "RiserHeight",
     "operator": "<=", "value": 5, "unit": "mm",
     "desc": "Riser height tolerance between adjacent treads/landings — max 5 mm"},
    {"ref": "9.8.4.4.(1)(b)", "target": "IfcStairFlight", "property_name": "RiserHeight",
     "operator": "<=", "value": 10, "unit": "mm",
     "desc": "Riser height tolerance between tallest/shortest riser in a flight — max 10 mm"},
    {"ref": "9.8.4.4.(3)(a)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": "<=", "value": 5, "unit": "mm",
     "desc": "Tread run tolerance between adjacent treads — max 5 mm"},
    {"ref": "9.8.4.4.(3)(b)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": "<=", "value": 10, "unit": "mm",
     "desc": "Tread run tolerance between deepest/shallowest tread in a flight — max 10 mm"},
    {"ref": "9.8.4.4.(5)", "target": "IfcStairFlight", "property_name": "PitchAngle",
     "operator": "<=", "value": 0.02, "unit": "ratio",
     "desc": "Slope of treads shall not exceed 1 in 50 (0.02)"},

    # ── WINDERS (9.8.4.5) ─────────────────────────────────────────────────────
    {"ref": "9.8.4.5.(1)(a)", "target": "IfcStairFlight", "property_name": "WinderTurnAngle",
     "operator": "<=", "value": 90, "unit": "deg",
     "desc": "Maximum total winder set turn angle — 90 degrees"},
    {"ref": "9.8.4.5.(1)(b)", "target": "IfcStairFlight", "property_name": "IndividualWinderAngle",
     "operator": "between", "value_min": 30, "value_max": 45, "unit": "deg",
     "desc": "Each winder tread angle must be between 30 and 45 degrees"},
    {"ref": "9.8.4.5.(2)", "target": "IfcStairFlight", "property_name": "WinderSetSeparation",
     "operator": ">=", "value": 1200, "unit": "mm",
     "desc": "Minimum plan separation between winder sets — 1200 mm"},

    # ── SPIRAL STAIRS (9.8.4.5A) ─────────────────────────────────────────────
    {"ref": "9.8.4.5A.(1)(a)", "target": "IfcStairFlight", "property_name": "HandrailHeight",
     "operator": ">=", "value": 1070, "unit": "mm",
     "desc": "Spiral stair outer handrail height — min 1070 mm"},
    {"ref": "9.8.4.5A.(1)(b)", "target": "IfcStairFlight", "property_name": "Width",
     "operator": ">=", "value": 660, "unit": "mm",
     "desc": "Spiral stair clear width between handrails — min 660 mm"},
    {"ref": "9.8.4.5A.(1)(c)", "target": "IfcStairFlight", "property_name": "RiserHeight",
     "operator": "<=", "value": 240, "unit": "mm",
     "desc": "Spiral stair riser height — max 240 mm"},
    {"ref": "9.8.4.5A.(1)(d)(i)", "target": "IfcStairFlight", "property_name": "TreadLength",
     "operator": ">=", "value": 190, "unit": "mm",
     "desc": "Spiral stair tread depth at 300 mm from centreline — min 190 mm"},
    {"ref": "9.8.4.5A.(1)(e)", "target": "IfcStairFlight", "property_name": "RequiredHeadroom",
     "operator": ">=", "value": 1980, "unit": "mm",
     "desc": "Spiral stair clear height — min 1980 mm"},
]

# ── CLAUSES DELIBERATELY EXCLUDED FROM GOLD_RULES ────────────────────────────
# Not discrete/checkable as a single numeric IFC-property rule. A pipeline
# that fabricates a confident numeric rule for one of these is a precision
# bug, not a good catch — track separately from recall against GOLD_RULES.
EXCLUDED_CLAUSES = [
    ("9.8.2.1.(3)", "Width = greater of 900mm or 8mm/person by occupant load — "
                     "table lookup depending on Table 3.1.17.1, not a fixed threshold"),
    ("9.8.2.2.(1)", "Defines HOW to measure clear height, not a requirement itself"),
    ("9.8.3.1", "Enumerates permitted stair shapes (straight/curved/spiral) — classification, not a numeric bound"),
    ("9.8.4.6.(1)(a)/(b)", "Tread leading-edge reduction limits — no canonical IFC property "
                            "for 'leading edge reduction' exists in ifc_reader's alias table"),
    ("9.8.4.7.(1)", "Requires weatherproofing 'protected from ice and snow' — not numeric/checkable via IFC properties"),
]

if __name__ == "__main__":
    print(f"SOURCE_TEXT: {len(SOURCE_TEXT)} chars")
    print(f"GOLD_RULES: {len(GOLD_RULES)} rules")
    print(f"EXCLUDED_CLAUSES: {len(EXCLUDED_CLAUSES)} clauses")
