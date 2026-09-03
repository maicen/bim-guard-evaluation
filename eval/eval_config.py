"""
eval_config.py
------------------------------------------------
Shared foundation for all eval/ scripts: path setup for importing bim-guard,
result storage, the standard JSON result schema, baseline load/compare
helpers, and run-ID generation.

Import this before any bim-guard (`app.*`) import:

    from eval_config import setup_bimguard_path, write_result, new_run_id
    setup_bimguard_path()
    from app.modules.blue_halo... import ...
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
RESULTS_DIR = EVAL_DIR / "results"
BASELINES_DIR = EVAL_DIR / "baselines"


def bimguard_path() -> Path:
    """Resolve the bim-guard checkout: $BIMGUARD_PATH, else a sibling directory."""
    return Path(os.getenv("BIMGUARD_PATH", str(REPO_ROOT.parent / "bim-guard")))


def setup_bimguard_path() -> Path:
    """Insert this repo and bim-guard onto sys.path so `app.*` imports resolve.
    Idempotent — safe to call multiple times or from multiple scripts."""
    core = bimguard_path()
    for p in (EVAL_DIR, REPO_ROOT, core):
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return core


def _git_commit(repo_path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_path), capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:
        return None


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_result(
    eval_id: str,
    tier: int,
    *,
    passed: int,
    failed: int,
    total: int,
    duration_s: float,
    details: Any = None,
) -> dict:
    """Assemble a result dict matching the standard schema:
    {eval_id, tier, status, passed, failed, total, score, duration_s,
     bimguard_commit, eval_commit, details}
    """
    score = (passed / total) if total else 0.0
    return {
        "eval_id": eval_id,
        "tier": tier,
        "status": "PASS" if failed == 0 else "FAIL",
        "passed": passed,
        "failed": failed,
        "total": total,
        "score": score,
        "duration_s": duration_s,
        "bimguard_commit": _git_commit(bimguard_path()),
        "eval_commit": _git_commit(REPO_ROOT),
        "details": details,
    }


def write_result(result: dict, run_id: str | None = None) -> Path:
    """Write a result dict to eval/results/<eval_id>_<run_id>.json."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = run_id or new_run_id()
    out_path = RESULTS_DIR / f"{result['eval_id']}_{run_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return out_path


def load_baseline(eval_id: str) -> dict | None:
    path = BASELINES_DIR / f"{eval_id}.baseline.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def update_baseline(eval_id: str, result: dict) -> Path:
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    baseline = dict(result)
    baseline["baseline_created"] = datetime.now(timezone.utc).isoformat()
    path = BASELINES_DIR / f"{eval_id}.baseline.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)
    return path


#: eval_ids whose duration_s is a measured metric worth comparing (not just
#: a score) get a wider tolerance — timing varies with the host, accuracy
#: shouldn't. 1.5x mirrors performance_benchmark.py's own IQR-based stance.
PERFORMANCE_EVAL_IDS = {"performance_benchmark"}


def _failing_labels(details: Any) -> set[str]:
    """Extract the set of check labels a result's `details` marks as failing.

    Handles both shapes eval scripts use: a full per-check list (each entry
    carries `passed`), and a failures-only list (entries with no `passed`
    key are implicitly failures). Anything else (a plain metrics dict, None)
    yields an empty set — individual-check diffing just doesn't apply.
    """
    if not isinstance(details, list):
        return set()
    out = set()
    for d in details:
        if isinstance(d, dict) and "label" in d and d.get("passed", False) is False:
            out.add(d["label"])
    return out


def compare_to_baseline(
    result: dict,
    baseline: dict,
    *,
    score_tolerance: float = 0.05,
    duration_tolerance: float = 0.5,
) -> dict:
    """Compare a fresh result to a stored baseline.

    Returns:
        {regressed, score_delta, duration_ratio, regressed_checks,
         improved_checks, reasons: list[str]}
    """
    reasons: list[str] = []

    score_delta = result["score"] - baseline["score"]
    score_regressed = score_delta < -score_tolerance
    if score_regressed:
        reasons.append(
            f"score dropped {baseline['score']:.1%} -> {result['score']:.1%} "
            f"(delta {score_delta:+.1%}, tolerance {score_tolerance:.1%})"
        )

    base_dur, cur_dur = baseline.get("duration_s") or 0.0, result.get("duration_s") or 0.0
    duration_ratio = (cur_dur / base_dur) if base_dur > 0 else 1.0
    perf_tolerance = 1.5 if result["eval_id"] in PERFORMANCE_EVAL_IDS else (1.0 + duration_tolerance)
    duration_regressed = base_dur > 0.05 and duration_ratio > perf_tolerance
    if duration_regressed:
        reasons.append(
            f"duration grew {base_dur:.2f}s -> {cur_dur:.2f}s "
            f"({duration_ratio:.2f}x, tolerance {perf_tolerance:.2f}x)"
        )

    base_failing = _failing_labels(baseline.get("details"))
    cur_failing = _failing_labels(result.get("details"))
    regressed_checks = sorted(cur_failing - base_failing)
    improved_checks = sorted(base_failing - cur_failing)
    if regressed_checks:
        reasons.append(f"{len(regressed_checks)} check(s) newly failing: {regressed_checks}")

    regressed = score_regressed or duration_regressed or bool(regressed_checks)
    return {
        "regressed": regressed,
        "score_delta": score_delta,
        "duration_ratio": duration_ratio,
        "regressed_checks": regressed_checks,
        "improved_checks": improved_checks,
        "reasons": reasons,
        "reason": "; ".join(reasons) if reasons else None,
    }
