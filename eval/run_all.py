"""
run_all.py
------------------------------------------------
Single entry point that runs the eval/ scripts in tier order, as
subprocesses (each script keeps its own module-level singletons isolated,
consistent with bim-guard's own test pattern).

Tiers (see CLAUDE.md / plan-26003.md section 2):
  0 - Unit          - no bim-guard imports, sub-second
  1 - Component     - imports bim-guard modules, no IFC/LLM
  2 - Integration   - requires IFC files or PDF fixtures
  3 - System        - requires LLM keys or large downloads

Usage:
    uv run python eval/run_all.py --tier 2
    uv run python eval/run_all.py --tier 2 --json
    uv run python eval/run_all.py --update-baseline
    uv run python eval/run_all.py --compare-baseline
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import (
    RESULTS_DIR,
    bimguard_path,
    compare_to_baseline,
    load_baseline,
    new_run_id,
    update_baseline,
)

# (eval_id, script, tier, supports_json, needs_bimguard_cwd)
# needs_bimguard_cwd: True for scripts that read bim-guard resources via a
# path relative to cwd (e.g. data/rulesets/*.json) rather than package-
# relative — they must run with cwd=bim-guard's checkout, not this repo's.
SCRIPTS: list[tuple[str, str, int, bool, bool]] = [
    ("score_nlp_annotation", "score_nlp_annotation.py", 0, True, False),
    ("validate_blue_halo", "validate_blue_halo.py", 1, True, False),
    ("eval_gold_code_9_8_stairs", "eval_gold_code_9_8_stairs.py", 1, False, False),
    ("score_rule_extraction", "score_rule_extraction.py", 2, True, False),
    ("test_real_ifc_pipeline", "test_real_ifc_pipeline.py", 2, True, False),
    ("test_api_endpoints", "test_api_endpoints.py", 2, True, True),
    ("test_e2e_roundtrip", "test_e2e_roundtrip.py", 2, True, True),
    ("performance_benchmark", "performance_benchmark.py", 2, False, False),
    ("eval_harness", "eval_harness.py", 3, False, False),
    ("test_all_38_models", "test_all_38_models.py", 3, False, False),
]


def run_script(eval_id: str, script: str, tier: int, supports_json: bool, run_id: str, *, smoke: bool, needs_bimguard_cwd: bool = False) -> dict:
    cmd = [sys.executable, str(EVAL_DIR / script)]
    if supports_json:
        cmd.append("--json")
    if smoke and script == "test_all_38_models.py":
        cmd.append("--smoke")

    cwd = str(bimguard_path()) if needs_bimguard_cwd else str(EVAL_DIR)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    duration_s = time.perf_counter() - t0

    manifest_entry = {
        "eval_id": eval_id,
        "tier": tier,
        "returncode": proc.returncode,
        "duration_s": round(duration_s, 3),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }

    if supports_json:
        result_files = sorted(RESULTS_DIR.glob(f"{eval_id}_*.json"))
        if result_files:
            with open(result_files[-1], encoding="utf-8") as f:
                manifest_entry["result"] = json.load(f)

    return manifest_entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", type=int, default=2, help="run up to this tier (default: 2)")
    parser.add_argument("--smoke", action="store_true", help="fast subsets per script, where supported")
    parser.add_argument("--json", action="store_true", help="request --json on scripts that support it")
    parser.add_argument("--compare-baseline", action="store_true", help="compare results to stored baselines, exit 1 on regression")
    parser.add_argument("--update-baseline", action="store_true", help="promote current results to baselines")
    args = parser.parse_args()

    run_id = new_run_id()
    to_run = [s for s in SCRIPTS if s[2] <= args.tier]

    print(f"run_all.py — run_id={run_id}  tier<={args.tier}  {len(to_run)} script(s)")
    manifest = []
    any_failed = False
    any_regressed = False

    for eval_id, script, tier, supports_json, needs_bimguard_cwd in to_run:
        print(f"\n{'=' * 70}\n  [tier {tier}] {script}\n{'=' * 70}")
        entry = run_script(eval_id, script, tier, supports_json and args.json, run_id, smoke=args.smoke, needs_bimguard_cwd=needs_bimguard_cwd)
        manifest.append(entry)

        if entry["returncode"] != 0:
            any_failed = True
            print(f"  FAIL (exit {entry['returncode']}, {entry['duration_s']}s)")
            if entry["stderr_tail"]:
                print(entry["stderr_tail"][-500:])
        else:
            print(f"  PASS ({entry['duration_s']}s)")

        if "result" in entry:
            if args.update_baseline:
                path = update_baseline(eval_id, entry["result"])
                print(f"  baseline updated -> {path}")
            if args.compare_baseline:
                baseline = load_baseline(eval_id)
                if baseline is None:
                    print(f"  no baseline for {eval_id} — skipping comparison")
                else:
                    cmp = compare_to_baseline(entry["result"], baseline)
                    entry["baseline_comparison"] = cmp
                    if cmp["regressed"]:
                        any_regressed = True
                        print(f"  REGRESSION: {cmp['reason']}")
                    else:
                        print(f"  STABLE (score delta {cmp['score_delta']:+.1%})")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = RESULTS_DIR / f"manifest_{run_id}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "tier": args.tier, "scripts": manifest}, f, indent=2)
    print(f"\nManifest written to {manifest_path}")

    if any_regressed:
        return 1
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
