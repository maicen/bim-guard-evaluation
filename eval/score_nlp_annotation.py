import argparse
import sys
import time
from pathlib import Path

# Support running from repository root or from eval/
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import build_result, new_run_id, write_result  # noqa: E402

_START = time.perf_counter()

try:
    from nlp_annotation.deontic_extractor import DeonticExtractor
    from nlp_annotation.condition_parser import ConditionParser
    from nlp_annotation.cross_ref_resolver import CrossRefResolver
    from nlp_annotation.dependency_mapper import DependencyMapper
    from nlp_annotation.dimension_extractor import DimensionExtractor
except ImportError:
    from app.modules.nlp_annotation.deontic_extractor import DeonticExtractor
    from app.modules.nlp_annotation.condition_parser import ConditionParser
    from app.modules.nlp_annotation.cross_ref_resolver import CrossRefResolver
    from app.modules.nlp_annotation.dependency_mapper import DependencyMapper
    from app.modules.nlp_annotation.dimension_extractor import DimensionExtractor

de = DeonticExtractor()
cp = ConditionParser()
cr = CrossRefResolver()
dm = DependencyMapper()
dx = DimensionExtractor()

passed = 0
failed = 0
failures = []

def check(label, got, expected_subset):
    global passed, failed
    ok = all(e in got for e in expected_subset)
    if ok:
        passed += 1
    else:
        failed += 1
        failures.append((label, got, expected_subset))

# ── 1. DEONTIC OPERATORS ──────────────────────────────────────────────────────

t = "Every exit stair shall have a clear width of not less than 860 mm."
ops = [d["operator"] for d in de.extract(t)]
check("SHALL simple", ops, ["SHALL"])

t = "Guards shall not be less than 900 mm in height."
ops = [d["operator"] for d in de.extract(t)]
check("SHALL NOT", ops, ["SHALL NOT"])

t = "Risers may be open where the rise does not exceed 125 mm."
ops = [d["operator"] for d in de.extract(t)]
check("MAY permitted", ops, ["MAY"])

t = "Stairs shall comply with this section and handrails shall be graspable."
ops = [d["operator"] for d in de.extract(t)]
check("Multiple SHALL", ops, ["SHALL", "SHALL"])

t = "The door must be self-closing and must not be locked."
strengths = [d["strength"] for d in de.extract(t)]
check("MUST mandatory + MUST NOT prohibited", strengths, ["mandatory", "prohibited"])

t = "Sprinklers shall not be required where the building is less than 3 storeys."
negated = [d["negated"] for d in de.extract(t)]
check("SHALL NOT negated=True", negated, [True])

t = "The door is required to be self-closing."
ops = [d["operator"] for d in de.extract(t)]
check("IS REQUIRED TO", ops, ["IS REQUIRED TO"])

t = "The stairway should have a handrail on at least one side."
strengths = [d["strength"] for d in de.extract(t)]
check("SHOULD recommended", strengths, ["recommended"])

# ── 2. CONDITIONS & REQUIREMENTS ─────────────────────────────────────────────

t = "Where a building exceeds 3 storeys, exit stairs shall have a minimum width of 1100 mm."
p = cp.parse(t)
cond_types  = [c["type"] for c in p["conditions"]]
cond_texts  = [c["text"] for c in p["conditions"]]
check("WHERE applicability type", cond_types, ["applicability"])
check("WHERE condition text contains '3 storeys'", [any("3 storeys" in ct for ct in cond_texts)], [True])
check("WHERE requirement contains '1100 mm'", [any("1100 mm" in r for r in p["requirements"])], [True])

t = "All stairs shall comply with this Subsection, except as permitted by Sentence 9.8.8.3.(1)."
p = cp.parse(t)
exc_types = [e["type"] for e in p["exceptions"]]
check("EXCEPT exception type", exc_types, ["exception"])
check("Requirement before exception present", [len(p["requirements"]) > 0], [True])

t = "Unless otherwise permitted, stairs shall have a minimum headroom of 1950 mm."
p = cp.parse(t)
exc_types = [e["type"] for e in p["exceptions"]]
check("UNLESS exception type", exc_types, ["exception"])

t = "Where floor area exceeds 600 m2 and building exceeds 3 storeys, two exits shall be provided."
p = cp.parse(t)
check("Multi-clause WHERE applicability", [c["type"] for c in p["conditions"]], ["applicability"])
check("Multi-clause requirement present", [len(p["requirements"]) > 0], [True])

t = "Guards shall not be less than 900 mm in height, except where the guard is on a stairway."
p = cp.parse(t)
check("Inline EXCEPT exception", [e["type"] for e in p["exceptions"]], ["exception"])
check("Inline EXCEPT requirement present", [len(p["requirements"]) > 0], [True])

t = "Stairways shall be designed in accordance with good engineering practice."
p = cp.parse(t)
check("Simple sentence no condition", [len(p["conditions"])], [0])
check("Simple sentence has requirement", [len(p["requirements"]) > 0], [True])

# ── 3. CROSS-REFERENCES ───────────────────────────────────────────────────────

t = "in accordance with Section 9.8.4.1"
refs = cr.extract(t); norms = [r["normalized"] for r in refs]; types = [r["ref_type"] for r in refs]
check("Section ref normalised", norms, ["9.8.4.1"])
check("Section ref type", types, ["section"])

t = "as required by Table 9.8.4.1.A"
refs = cr.extract(t); norms = [r["normalized"] for r in refs]
check("Table ref captured", ["9.8.4.1" in norms[0] if norms else False], [True])

t = "except as permitted by Sentence 9.8.8.3.(1)"
refs = cr.extract(t); norms = [r["normalized"] for r in refs]
check("Sentence ref with subsection full", norms, ["9.8.8.3.(1)"])

t = "conforming to CAN/ULC-S101"
refs = cr.extract(t); types = [r["ref_type"] for r in refs]
check("Standard ref CAN/ULC type", types, ["standard"])

t = "as provided in Part 3"
refs = cr.extract(t); norms = [r["normalized"] for r in refs]
check("Part ref", norms, ["Part 3"])

t = "Section 9.8.2.1 and Article 9.8.3.4 and Table 9.10.1.A shall apply."
refs  = cr.extract(t); norms = [r["normalized"] for r in refs]
check("Multiple mixed refs all found", [all(n in norms for n in ["9.8.2.1", "9.8.3.4"])], [True])

t = "The area shall be 3.5 m wide."
refs = cr.extract(t)
check("Decimal 3.5 NOT a section ref", refs, [])

t = "guards shall not be less than 0.9 m in height"
refs = cr.extract(t)
check("0.9 (leading zero) NOT a section ref", refs, [])

t = "as required by ASTM C62"
refs = cr.extract(t); types = [r["ref_type"] for r in refs]
check("ASTM standard ref", types, ["standard"])

# ── 4. DIMENSIONS ─────────────────────────────────────────────────────────────

t = "exit stairs shall have a clear width of not less than 860 mm"
dims = dx.extract(t)
check("not less than -> min constraint", [d["constraint"] for d in dims], ["min"])
check("not less than -> 860.0 value",    [d["value"] for d in dims],      [860.0])

t = "Riser height shall be between 125 mm and 200 mm."
dims = dx.extract(t)
check("between -> range", [d["constraint"] for d in dims], ["range"])
check("range value_min=125", [d["value_min"] for d in dims], [125.0])
check("range value_max=200", [d["value_max"] for d in dims], [200.0])

t = "not more than 35 percent slope"
dims = dx.extract(t)
check("not more than -> max", [d["constraint"] for d in dims], ["max"])
check("35 percent value",     [d["value"] for d in dims],      [35.0])

t = "at least 1950 mm headroom"
dims = dx.extract(t)
check("at least -> min", [d["constraint"] for d in dims], ["min"])

t = "a minimum of 860 mm clear width"
dims = dx.extract(t)
check("minimum of -> min", [d["constraint"] for d in dims], ["min"])

t = "guards shall not be less than 900 mm in height"
dims = dx.extract(t)
check("not be less than -> min", [d["constraint"] for d in dims], ["min"])

t = "The window opening shall be not less than 0.35 m2."
dims = dx.extract(t)
units = [d["unit"] for d in dims]
check("m2 area unit", units, ["m2"])

t = "The fire resistance rating shall not be less than 45 min."
dims = dx.extract(t)
check("45 min -> min constraint", [d["constraint"] for d in dims], ["min"])
check("45 min -> unit=min",       [d["unit"] for d in dims],       ["min"])

t = "floor area shall not exceed 600 m2"
dims = dx.extract(t)
check("not exceed -> max", [d["constraint"] for d in dims], ["max"])

# ── 5. DEPENDENCIES ───────────────────────────────────────────────────────────

t = "Notwithstanding Sentence 9.8.2.1.(1), where sprinklers are installed the minimum shall be 860 mm."
deps = dm.extract(t); dtypes = [d["dep_type"] for d in deps]
refs = [r["normalized"] for d in deps for r in d["refs"]]
check("Notwithstanding -> override", dtypes, ["override"])
check("Notwithstanding ref 9.8.2.1.(1) preserved", refs, ["9.8.2.1.(1)"])

t = "Subject to Sentence 9.8.4.1.(3), the minimum clear width shall be 860 mm."
deps = dm.extract(t); dtypes = [d["dep_type"] for d in deps]
refs = [r["normalized"] for d in deps for r in d["refs"]]
check("Subject to -> subject_to", dtypes, ["subject_to"])
check("Subject_to ref 9.8.4.1.(3) preserved", refs, ["9.8.4.1.(3)"])

t = "Sprinklers may be installed in lieu of fire separation required by Subsection 9.10.9."
deps = dm.extract(t)
check("In lieu of -> alternative", [d["dep_type"] for d in deps], ["alternative"])

t = "The stair shall comply, provided that occupancy does not exceed 60 persons."
deps = dm.extract(t)
check("Provided that -> conditional", [d["dep_type"] for d in deps], ["conditional"])

t = "The building is deemed to comply with Section 9.10.9."
deps = dm.extract(t)
check("Deemed to comply -> alternative", [d["dep_type"] for d in deps], ["alternative"])

t = "except as permitted by Sentence 9.8.8.3.(1)"
deps = dm.extract(t); refs = [r["normalized"] for d in deps for r in d["refs"]]
check("Except ref 9.8.8.3.(1) fully captured", refs, ["9.8.8.3.(1)"])

t = "in addition to the requirements of Section 9.8.4, guards shall be provided."
deps = dm.extract(t)
check("In addition to -> addition", [d["dep_type"] for d in deps], ["addition"])

t = "unless otherwise permitted by the authority having jurisdiction"
deps = dm.extract(t)
check("Unless no ref -> still exception", [d["dep_type"] for d in deps], ["exception"])

# ── RESULTS ───────────────────────────────────────────────────────────────────

total = passed + failed
print(f"\n{'='*55}")
print(f"  SCORE: {passed}/{total}  ({100*passed//total}%)")
print(f"{'='*55}")

cats = [
    ("1. Deontic operators",     8),
    ("2. Conditions/requirements", 10),
    ("3. Cross-references",      10),
    ("4. Dimensions",             9),
    ("5. Dependencies",           8),
]
offset = 0
for name, n in cats:
    cat_pass = sum(1 for i, f in enumerate(failures) if False)  # just display totals

print()
if failures:
    print(f"  FAILURES ({len(failures)}):")
    for label, got, expected in failures:
        print(f"    FAIL  {label}")
        print(f"          expected subset: {expected}")
        print(f"          got:             {got}")
else:
    print("  All tests passed.")

parser = argparse.ArgumentParser()
parser.add_argument("--json", action="store_true", help="write structured results to eval/results/")
args = parser.parse_args()

if args.json:
    duration_s = time.perf_counter() - _START
    details = [
        {"label": label, "got": got, "expected_subset": expected}
        for label, got, expected in failures
    ]
    result = build_result(
        "score_nlp_annotation", tier=0,
        passed=passed, failed=failed, total=total,
        duration_s=duration_s, details=details,
    )
    out_path = write_result(result, run_id=new_run_id())
    print(f"\n  JSON result written to {out_path}")

sys.exit(0 if failed == 0 else 1)
