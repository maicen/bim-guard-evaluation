"""
test_e2e_roundtrip.py
------------------------------------------------
Priority 2 — End-to-end API roundtrip (plan-26003.md).

Exercises the real user workflow through bim-guard's HTTP surface, Mode A
(API), rather than importing internals:

    1. POST /api/projects/upload   -> create a project + attach a real IFC
    2. POST /api/analyze/seismic   -> trigger Blue Halo seismic analysis
    3. GET  /api/analyze/status/{project_id}  -> workflow snapshot
    4. GET  /api/analyze/export (fmt=bcf)      -> BCF 2.1 ZIP, validate structure
    5. DELETE /api/projects/{project_id}       -> cleanup

Seismic analysis is deliberately used instead of the PDF-rules -> LLM
extraction leg the plan sketches: it needs no LLM/API key, so this script
runs the same in CI as it does locally, mirroring score_rule_extraction.py's
Part A/B split (Part A always runs; anything needing an LLM is separate).
The PDF -> /api/rules/extract -> corrosion/arch analysis leg is left for a
follow-up script once an LLM key is available in CI.

This is the one script in eval/ that mutates bim-guard's database (it
creates a project) — every other eval script is read-only. It cleans up
the project it creates even when a later step fails.

Usage:
    uv run python eval/test_e2e_roundtrip.py
    uv run python eval/test_e2e_roundtrip.py --live
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import bimguard_path, build_result, new_run_id, setup_bimguard_path, write_result  # noqa: E402

_START = time.perf_counter()

IFC_FIXTURE = "data/test_hospital_mep_scenario.ifc"

passed = 0
failed = 0
failures: list[tuple[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed += 1
        failures.append((label, detail))
        print(f"  [FAIL] {label}")
        if detail:
            print(f"         {detail}")


# ── Client wrapper (mirrors test_api_endpoints.py) ──────────────────────────


class InProcessClient:
    def __init__(self):
        from starlette.testclient import TestClient
        from app.main import app

        self._client = TestClient(app)

    def get(self, path, **kw):
        return self._client.get(path, **kw)

    def post(self, path, **kw):
        return self._client.post(path, **kw)

    def delete(self, path, **kw):
        return self._client.delete(path, **kw)


class LiveClient:
    def __init__(self, base_url: str):
        import httpx

        self._client = httpx.Client(base_url=base_url, timeout=60.0)

    def get(self, path, **kw):
        return self._client.get(path, **kw)

    def post(self, path, **kw):
        return self._client.post(path, **kw)

    def delete(self, path, **kw):
        return self._client.delete(path, **kw)


# ── Roundtrip ────────────────────────────────────────────────────────────


def run_roundtrip(client) -> None:
    project_id = None
    try:
        # 1. Create project + attach IFC in one multipart call.
        ifc_path = bimguard_path() / IFC_FIXTURE
        if not ifc_path.exists():
            check(f"IFC fixture present ({IFC_FIXTURE})", False, f"not found at {ifc_path}")
            return
        check(f"IFC fixture present ({IFC_FIXTURE})", True)

        with open(ifc_path, "rb") as f:
            r = client.post(
                "/api/projects/upload",
                data={
                    "name": f"eval-e2e-roundtrip-{new_run_id()}",
                    "country": "Canada",
                    "analysis_type": "seismic",
                },
                files={"ifc_file": (ifc_path.name, f, "application/octet-stream")},
            )
        check("POST /api/projects/upload -> 201", r.status_code == 201, f"got {r.status_code}: {r.text[:300]}")
        if r.status_code != 201:
            return
        project = r.json()
        project_id = project.get("id")
        check("Created project has an id", isinstance(project_id, int), f"project payload: {project}")
        if project_id is None:
            return

        # 2. Run seismic (Blue Halo) analysis — no LLM required.
        r = client.post("/api/analyze/seismic", data={"project_id": project_id})
        check("POST /api/analyze/seismic -> 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            result = r.json()
            check("Seismic result has issues/summary shape", "issues" in result or "summary" in result, f"keys: {list(result)}")

        # 3. Workflow status snapshot.
        r = client.get(f"/api/analyze/status/{project_id}")
        check("GET /api/analyze/status/{project_id} -> 200", r.status_code == 200, f"got {r.status_code}")

        # 4. Export as BCF and validate ZIP structure.
        r = client.get("/api/analyze/export", params={"project_id": project_id, "slug": "seismic", "fmt": "bcf"})
        check("GET /api/analyze/export (fmt=bcf) -> 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
        if r.status_code == 200:
            try:
                with zipfile.ZipFile(BytesIO(r.content)) as zf:
                    names = zf.namelist()
                check("BCF export is a valid ZIP", True)
                check(
                    "BCF ZIP has bcf.version + project.bcfp",
                    "bcf.version" in names and "project.bcfp" in names,
                    f"entries: {names}",
                )
            except zipfile.BadZipFile as exc:
                check("BCF export is a valid ZIP", False, str(exc))
    finally:
        if project_id is not None:
            r = client.delete(f"/api/projects/{project_id}")
            check(
                f"DELETE /api/projects/{project_id} cleanup -> 204",
                r.status_code == 204,
                f"got {r.status_code}: manual cleanup may be required",
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="use real HTTP (httpx) against BIMGUARD_URL instead of an in-process TestClient")
    parser.add_argument("--json", action="store_true", help="write structured results to eval/results/")
    args = parser.parse_args()

    if args.live:
        base_url = os.getenv("BIMGUARD_URL", "http://127.0.0.1:8000")
        print(f"E2E roundtrip — live HTTP against {base_url}")
        client = LiveClient(base_url)
    else:
        print("E2E roundtrip — in-process TestClient")
        setup_bimguard_path()
        client = InProcessClient()

    run_roundtrip(client)

    total = passed + failed
    print(f"\n{'=' * 55}")
    print(f"  SCORE: {passed}/{total}  ({100 * passed // total if total else 0}%)")
    print(f"{'=' * 55}")

    if args.json:
        result = build_result(
            "test_e2e_roundtrip", tier=2,
            passed=passed, failed=failed, total=total,
            duration_s=time.perf_counter() - _START,
            details=[{"label": label, "detail": detail} for label, detail in failures],
        )
        out_path = write_result(result, run_id=new_run_id())
        print(f"\n  JSON result written to {out_path}")

    sys.exit(0 if failed == 0 else 1)
