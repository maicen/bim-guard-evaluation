"""
eval/env_snapshot.py
---------------------------------------------
Cryptographic environment & hardware provenance capture for reproducible evaluation.
Records git revisions, lockfile hashes, operating system, and hardware telemetry.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_git_info(repo_dir: Path) -> dict[str, Any]:
    """Extracts git branch, commit hash, commit date, and dirty status."""
    if not (repo_dir / ".git").exists():
        return {"status": "not_a_git_repo"}

    def run_git(args: list[str]) -> str:
        try:
            return subprocess.check_output(
                ["git"] + args,
                cwd=str(repo_dir),
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            return "unknown"

    commit = run_git(["rev-parse", "HEAD"])
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    commit_date = run_git(["log", "-1", "--format=%cI"])
    dirty = bool(run_git(["status", "--porcelain"]))

    return {
        "commit": commit,
        "branch": branch,
        "commit_date": commit_date,
        "is_dirty": dirty,
    }


def _get_file_sha256(file_path: Path) -> str | None:
    """Computes SHA-256 hash of a file."""
    if not file_path.is_file():
        return None
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_environment_snapshot() -> dict[str, Any]:
    """
    Collects full cryptographic, environment, and hardware telemetry.
    """
    eval_root = Path(__file__).resolve().parent.parent
    bimguard_root = eval_root.parent / "bim-guard"

    eval_lock = eval_root / "uv.lock"
    bimguard_lock = bimguard_root / "uv.lock"

    # Hardware info
    cpu_count = os.cpu_count() or 1
    total_mem_gb = None
    try:
        if sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            total_mem_gb = round(int(out) / (1024 ** 3), 2)
        elif sys.platform.startswith("linux"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        total_mem_gb = round(kb / (1024 ** 2), 2)
                        break
    except Exception:
        total_mem_gb = None

    snapshot = {
        "schema_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "python_executable": sys.executable,
        },
        "system": {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "cpu_cores": cpu_count,
            "memory_gb": total_mem_gb,
        },
        "repositories": {
            "bim-guard-evaluation": {
                "path": str(eval_root),
                "git": _get_git_info(eval_root),
                "uv_lock_sha256": _get_file_sha256(eval_lock),
            },
            "bim-guard": {
                "path": str(bimguard_root),
                "git": _get_git_info(bimguard_root),
                "uv_lock_sha256": _get_file_sha256(bimguard_lock),
            },
        },
    }
    return snapshot


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Capture environment and cryptographic provenance")
    parser.add_argument("--output", "-o", type=str, help="Destination JSON path")
    args = parser.parse_args()

    snapshot = get_environment_snapshot()

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        print(f"Environment snapshot saved to: {out_path}")
    else:
        print(json.dumps(snapshot, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
