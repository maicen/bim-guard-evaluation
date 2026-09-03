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


def compare_to_baseline(result: dict, baseline: dict, *, score_tolerance: float = 0.05) -> dict:
    """Compare a fresh result to a stored baseline. Returns
    {regressed: bool, score_delta: float, reason: str | None}."""
    score_delta = result["score"] - baseline["score"]
    regressed = score_delta < -score_tolerance
    reason = (
        f"score dropped {baseline['score']:.1%} -> {result['score']:.1%} "
        f"(delta {score_delta:+.1%}, tolerance {score_tolerance:.1%})"
        if regressed else None
    )
    return {"regressed": regressed, "score_delta": score_delta, "reason": reason}
