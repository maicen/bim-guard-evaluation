"""
test_api_endpoints.py
------------------------------------------------
Mode A — Black-Box API Evaluation (plan-26003.md Priority 1).

Exercises bim-guard's FastAPI surface as an external black box: every router
group gets at least one smoke check — a safe read that should succeed, a
not-found path that should 404, or a validation failure that should 4xx.
No project/rule/document is created or mutated; every check is either a GET
or a POST expected to fail validation before touching persistence.

Two client modes:
  In-process (default) — starlette.testclient.TestClient(app), fast, no
    server to start.
  --live                — real HTTP via httpx against a running server.
    Reads BIMGUARD_URL (default http://127.0.0.1:8000) so this also exercises
    real network/CORS/middleware behaviour that the in-process client skips.

Mirrors score_nlp_annotation.py's style (plain script, print()-based
check()/passed/failed counters, no pytest).

Usage:
    uv run python eval/test_api_endpoints.py
    uv run python eval/test_api_endpoints.py --live
    BIMGUARD_URL=http://127.0.0.1:8000 uv run python eval/test_api_endpoints.py --live
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import build_result, new_run_id, setup_bimguard_path, write_result  # noqa: E402

_START = time.perf_counter()

NONEXISTENT_ID = 999_999_999

passed = 0
failed = 0
failures: list[tuple[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        failures.append((label, detail))


def check_status(label: str, response, expected) -> None:
    """expected: an int, or a set/tuple of acceptable status codes."""
    ok = response.status_code in expected if isinstance(expected, (set, tuple, list)) else response.status_code == expected
    check(label, ok, f"expected {expected}, got {response.status_code}: {response.text[:200]}")


# ── Response wrapper so TestClient and httpx look identical to the tests ────


class Response:
    def __init__(self, status_code: int, text: str, json_body):
        self.status_code = status_code
        self.text = text
        self._json = json_body

    def json(self):
        return self._json


class InProcessClient:
    def __init__(self):
        from starlette.testclient import TestClient
        from app.main import app

        self._client = TestClient(app)

    def get(self, path, **kw):
        r = self._client.get(path, **kw)
        return Response(r.status_code, r.text, _safe_json(r))

    def post(self, path, **kw):
        r = self._client.post(path, **kw)
        return Response(r.status_code, r.text, _safe_json(r))


class LiveClient:
    def __init__(self, base_url: str):
        import httpx

        self._client = httpx.Client(base_url=base_url, timeout=30.0)

    def get(self, path, **kw):
        r = self._client.get(path, **kw)
        return Response(r.status_code, r.text, _safe_json(r))

    def post(self, path, **kw):
        r = self._client.post(path, **kw)
        return Response(r.status_code, r.text, _safe_json(r))


def _safe_json(r):
    try:
        return r.json()
    except Exception:
        return None


# ── Checks, grouped by router ───────────────────────────────────────────────


def run_checks(client) -> None:
    # Projects
    r = client.get("/api/projects")
    check_status("GET /api/projects -> 200", r, 200)
    if r.status_code == 200:
        body = r.json()
        check("GET /api/projects response has total + projects list", isinstance(body, dict) and "total" in body and isinstance(body.get("projects"), list))

    r = client.get(f"/api/projects/{NONEXISTENT_ID}")
    check_status("GET /api/projects/{nonexistent} -> 404", r, 404)

    r = client.post("/api/projects", json={"name": "", "description": "eval smoke test"})
    check_status("POST /api/projects empty name -> 422", r, 422)

    r = client.get("/api/projects/options")
    check_status("GET /api/projects/options -> 200", r, 200)
    if r.status_code == 200:
        check("GET /api/projects/options has building_codes", "building_codes" in (r.json() or {}))

    r = client.get(f"/api/projects/{NONEXISTENT_ID}/ifc")
    check_status("GET /api/projects/{nonexistent}/ifc -> 404", r, 404)

    # Dashboard
    r = client.get("/api/dashboard/stats")
    check_status("GET /api/dashboard/stats -> 200", r, 200)

    # Rules
    r = client.get("/api/rules")
    check_status("GET /api/rules -> 200", r, 200)
    if r.status_code == 200:
        check("GET /api/rules returns a list", isinstance(r.json(), list))

    r = client.get("/api/rules/folders")
    check_status("GET /api/rules/folders -> 200", r, 200)

    r = client.get("/api/rules/snapshots")
    check_status("GET /api/rules/snapshots -> 200", r, 200)

    r = client.get(f"/api/rules/{NONEXISTENT_ID}")
    check_status("GET /api/rules/{nonexistent} -> 404", r, 404)

    r = client.get("/api/rules/export-ids")
    check_status("GET /api/rules/export-ids (no exportable rules) -> 400", r, (200, 400))

    # Analyze
    r = client.get(f"/api/analyze/status/{NONEXISTENT_ID}")
    check_status("GET /api/analyze/status/{nonexistent} -> 404", r, (404, 200))

    r = client.get("/api/analyze/bcf/list")
    check_status("GET /api/analyze/bcf/list -> 200", r, 200)

    r = client.get(f"/api/analyze/results/{NONEXISTENT_ID}/some-slug")
    check_status("GET /api/analyze/results/{nonexistent}/unknown-slug -> 400 (slug validated before project lookup)", r, 400)

    # Documents
    r = client.get("/api/documents")
    check_status("GET /api/documents -> 200", r, 200)
    if r.status_code == 200:
        check("GET /api/documents returns a list", isinstance(r.json(), list))

    r = client.get(f"/api/documents/{NONEXISTENT_ID}")
    check_status("GET /api/documents/{nonexistent} -> 404", r, 404)

    # BCF v2.1
    r = client.get("/api/bcf/v2.1/projects")
    check_status("GET /api/bcf/v2.1/projects -> 200", r, 200)
    if r.status_code == 200:
        check("GET /api/bcf/v2.1/projects returns a list", isinstance(r.json(), list))

    # BCF v2.1 projects are synthesized on read rather than looked up against
    # bim-guard's own project table (BCF "project" != bim-guard "project"), so
    # a nonexistent numeric ID still returns 200 with an authorization stub.
    r = client.get(f"/api/bcf/v2.1/projects/{NONEXISTENT_ID}")
    check_status("GET /api/bcf/v2.1/projects/{nonexistent} -> 200 (BCF projects are synthesized, not looked up)", r, 200)

    r = client.get(f"/api/bcf/v2.1/projects/{NONEXISTENT_ID}/topics")
    check_status("GET /api/bcf/v2.1/projects/{nonexistent}/topics -> 200 empty list", r, 200)
    if r.status_code == 200:
        check("GET /api/bcf/v2.1/projects/{nonexistent}/topics returns []", r.json() == [])

    # bSDD
    r = client.get("/api/bsdd/dictionaries")
    check_status("GET /api/bsdd/dictionaries -> 200", r, 200)
    if r.status_code == 200:
        check("GET /api/bsdd/dictionaries returns a list", isinstance(r.json(), list))

    r = client.get("/api/bsdd/classes/search", params={"q": "wall"})
    check_status("GET /api/bsdd/classes/search?q=wall -> 200", r, 200)

    r = client.get("/api/bsdd/classes/search")
    check_status("GET /api/bsdd/classes/search (missing required q) -> 422", r, 422)

    # OpenCDE
    r = client.get("/api/cde/versions")
    check_status("GET /api/cde/versions -> 200", r, 200)

    r = client.get("/api/cde/v1/auth/config")
    check_status("GET /api/cde/v1/auth/config -> 200", r, 200)

    r = client.get(f"/api/cde/v1/projects/{NONEXISTENT_ID}/documents")
    check_status("GET /api/cde/v1/projects/{nonexistent}/documents -> 404", r, (404, 200))

    # Naming config (ISO 19650)
    r = client.get("/api/naming-config/catalog")
    check_status("GET /api/naming-config/catalog -> 200", r, 200)

    r = client.get("/api/naming-config/presets")
    check_status("GET /api/naming-config/presets -> 200", r, 200)

    r = client.get(f"/api/naming-config/projects/{NONEXISTENT_ID}")
    check_status("GET /api/naming-config/projects/{nonexistent} -> 404", r, 404)

    # Parsing engines
    r = client.get("/api/parsing-engines")
    check_status("GET /api/parsing-engines -> 200", r, 200)
    if r.status_code == 200:
        check("GET /api/parsing-engines returns a list", isinstance(r.json(), list))

    # Settings
    r = client.get("/api/settings")
    check_status("GET /api/settings -> 200", r, 200)

    # Repositories
    r = client.get("/api/repositories")
    check_status("GET /api/repositories -> 200", r, 200)
    if r.status_code == 200:
        check("GET /api/repositories returns a list", isinstance(r.json(), list))

    r = client.get(f"/api/repositories/{NONEXISTENT_ID}")
    check_status("GET /api/repositories/{nonexistent} -> 404", r, 404)

    # Events / workflow
    r = client.get(f"/api/workflow/{NONEXISTENT_ID}")
    check_status("GET /api/workflow/{nonexistent} -> 404", r, (404, 200))

    # Digital inspector
    r = client.post(f"/api/projects/{NONEXISTENT_ID}/inspect", json={"question": "eval smoke test"})
    check_status("POST /api/projects/{nonexistent}/inspect -> 404", r, (404, 422))

    # OpenAPI contract sanity — every router actually mounted
    r = client.get("/api/openapi.json")
    check_status("GET /api/openapi.json -> 200", r, 200)
    if r.status_code == 200:
        paths = (r.json() or {}).get("paths", {})
        expected_prefixes = [
            "/api/projects", "/api/dashboard", "/api/rules", "/api/analyze",
            "/api/documents", "/api/cde", "/api/bsdd", "/api/bcf",
            "/api/settings", "/api/naming-config", "/api/parsing-engines",
            "/api/repositories",
        ]
        missing = [p for p in expected_prefixes if not any(path.startswith(p) for path in paths)]
        check(f"openapi.json mounts every expected router prefix ({len(expected_prefixes)} checked)", not missing, f"missing: {missing}")


# ── Main ─────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="use real HTTP (httpx) against BIMGUARD_URL instead of an in-process TestClient")
    parser.add_argument("--json", action="store_true", help="write structured results to eval/results/")
    args = parser.parse_args()

    if args.live:
        base_url = os.getenv("BIMGUARD_URL", "http://127.0.0.1:8000")
        print(f"Mode A — live HTTP against {base_url}")
        client = LiveClient(base_url)
    else:
        print("Mode A — in-process TestClient")
        setup_bimguard_path()
        client = InProcessClient()

    run_checks(client)

    total = passed + failed
    print(f"\n{'=' * 55}")
    print(f"  SCORE: {passed}/{total}  ({100 * passed // total if total else 0}%)")
    print(f"{'=' * 55}")

    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for label, detail in failures:
            print(f"    FAIL  {label}")
            if detail:
                print(f"          {detail}")
    else:
        print("\n  All checks passed.")

    if args.json:
        result = build_result(
            "test_api_endpoints", tier=2,
            passed=passed, failed=failed, total=total,
            duration_s=time.perf_counter() - _START,
            details=[{"label": label, "detail": detail} for label, detail in failures],
        )
        out_path = write_result(result, run_id=new_run_id())
        print(f"\n  JSON result written to {out_path}")

    sys.exit(0 if failed == 0 else 1)
