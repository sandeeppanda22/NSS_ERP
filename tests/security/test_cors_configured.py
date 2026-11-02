"""
NSS ERP — CORS with CONFIGURED origins (api/main.py, Settings.CORS_ORIGINS).

api/main.py registers CORSMiddleware at import time, and only when
`settings.CORS_ORIGINS` is non-empty, so the in-process `app` (built with the
test environment's empty value; see tests/security/test_security_headers.py::
TestCORS) can never exercise the configured branch. There is no app-factory to
call, and refactoring api/ is out of scope, so each case imports `api.main` in
a FRESH Python subprocess with `CORS_ORIGINS` set in its environment and drives
that app with a plain TestClient (no lifespan, so no DB pool is opened and no
shared test connection is touched). That runs the real wiring in api/main.py,
not a re-implementation of it.

Expected wiring (api/main.py): allow_origins=CORS_ORIGINS, allow_credentials=True,
allow_methods=GET/POST/PATCH/DELETE, allow_headers=*.

NOTE: not executed against a DB; the subprocess itself needs only api/.env to
import (config reads it) and no database connection.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]

ALLOWED = "https://app.allowed.example"
OTHER_ALLOWED = "https://second.allowed.example"
DISALLOWED = "https://evil.example.com"
HEALTH = "/api/v1/bootstrap/health"

# Runs inside the subprocess. Prints one JSON document describing the results.
_PROBE = textwrap.dedent(
    """
    import json, sys
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient
    from api.main import app

    origins = json.loads(sys.argv[1])
    path = sys.argv[2]
    client = TestClient(app)  # no `with`: lifespan (DB pool) never starts

    def hdrs(resp, *names):
        return {n: resp.headers.get(n) for n in names}

    out = {
        "registered": any(m.cls is CORSMiddleware for m in app.user_middleware),
    }
    cors_names = ("access-control-allow-origin", "access-control-allow-credentials",
                  "access-control-allow-methods", "access-control-allow-headers")
    out["simple"] = {}
    out["preflight"] = {}
    for origin in origins:
        # A non-existent route: CORS headers are added to any response and this
        # avoids touching the database.
        r = client.get("/api/v1/__no_such_route__", headers={"Origin": origin})
        out["simple"][origin] = hdrs(r, *cors_names)
        for method in ("GET", "POST", "PATCH", "DELETE", "PUT"):
            p = client.options(path, headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization,content-type",
            })
            out["preflight"][origin + "|" + method] = {
                "status": p.status_code, **hdrs(p, *cors_names),
            }
    print("PROBE_JSON=" + json.dumps(out))
    """
)


def _run_probe(cors_origins_env, origins_to_probe):
    env = dict(os.environ)
    env["CORS_ORIGINS"] = cors_origins_env
    # Keep the subprocess quiet and offline-safe.
    env.setdefault("DEV_LIVE_RELOAD", "")
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(origins_to_probe), HEALTH],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"probe failed:\n{proc.stdout}\n{proc.stderr}"
    line = next(
        (l for l in proc.stdout.splitlines() if l.startswith("PROBE_JSON=")), None
    )
    assert line is not None, f"no probe output:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(line[len("PROBE_JSON="):])


@pytest.fixture(scope="module")
def configured():
    """App imported with two allowed origins; probed with allowed and disallowed ones."""
    return _run_probe(
        f"{ALLOWED}, {OTHER_ALLOWED} ,",  # whitespace and trailing comma are tolerated
        [ALLOWED, OTHER_ALLOWED, DISALLOWED],
    )


@pytest.fixture(scope="module")
def unconfigured():
    return _run_probe("", [ALLOWED, DISALLOWED])


class TestCorsConfiguredOrigins:

    def test_middleware_is_registered(self, configured):
        assert configured["registered"] is True

    @pytest.mark.parametrize("origin", [ALLOWED, OTHER_ALLOWED])
    def test_allowed_origin_gets_acao_on_a_request(self, configured, origin):
        h = configured["simple"][origin]
        assert h["access-control-allow-origin"] == origin
        assert h["access-control-allow-credentials"] == "true"

    def test_disallowed_origin_gets_no_acao_on_a_request(self, configured):
        assert configured["simple"][DISALLOWED]["access-control-allow-origin"] is None

    def test_origin_is_echoed_not_wildcarded(self, configured):
        assert configured["simple"][ALLOWED]["access-control-allow-origin"] != "*"

    @pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
    def test_preflight_allowed_origin_and_method_is_accepted(self, configured, method):
        p = configured["preflight"][f"{ALLOWED}|{method}"]
        assert p["status"] == 200
        assert p["access-control-allow-origin"] == ALLOWED
        assert p["access-control-allow-credentials"] == "true"
        assert method in p["access-control-allow-methods"]

    def test_preflight_allow_methods_lists_exactly_the_four_verbs(self, configured):
        p = configured["preflight"][f"{ALLOWED}|GET"]
        listed = {m.strip() for m in p["access-control-allow-methods"].split(",")}
        assert listed == {"GET", "POST", "PATCH", "DELETE"}

    def test_preflight_disallowed_method_is_rejected(self, configured):
        """PUT is not an allowed method: Starlette answers the preflight with 400."""
        p = configured["preflight"][f"{ALLOWED}|PUT"]
        assert p["status"] == 400

    def test_preflight_disallowed_origin_is_rejected(self, configured):
        p = configured["preflight"][f"{DISALLOWED}|GET"]
        assert p["status"] == 400
        assert p["access-control-allow-origin"] is None

    def test_preflight_allows_requested_headers(self, configured):
        """allow_headers=['*'] reflects the requested Authorization/Content-Type."""
        p = configured["preflight"][f"{ALLOWED}|POST"]
        allowed_headers = (p["access-control-allow-headers"] or "").lower()
        assert "authorization" in allowed_headers
        assert "content-type" in allowed_headers


class TestCorsEmptyConfig:

    def test_empty_config_registers_no_cors_middleware(self, unconfigured):
        assert unconfigured["registered"] is False

    @pytest.mark.parametrize("origin", [ALLOWED, DISALLOWED])
    def test_empty_config_emits_no_cors_headers(self, unconfigured, origin):
        assert unconfigured["simple"][origin]["access-control-allow-origin"] is None
        p = unconfigured["preflight"][f"{origin}|GET"]
        assert p["access-control-allow-origin"] is None
