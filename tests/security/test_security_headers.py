"""
NSS ERP — Security middleware tests.

Verifies that security controls added across all tiers actually work:
  1. Security headers are present on every response
  2. Cache-Control is scoped to API routes (not static assets)
  3. Rate limiting returns 429 after threshold
  4. CORS responds correctly to preflight and same-origin requests
  5. DISABLE_DOCS toggle hides OpenAPI endpoints
  6. Content-Security-Policy is emitted with the verified directive set,
     and the frontend source stays free of the inline handlers/scripts that
     the policy blocks (Tier 5 advisory A2)
  7. DEBUG_MODE warns loudly at startup (Tier 5 advisory A5)
  8. DEV_LIVE_RELOAD is off by default — /__dev/frontend-version does not
     exist and no page references the dev-reload client script

These tests run against the FastAPI TestClient (no network).
"""

import logging
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


class TestSecurityHeaders:
    """Verify security headers on API and frontend responses."""

    def test_api_response_has_security_headers(self, client):
        """Every API response must include the four core security headers."""
        response = client.get("/api/v1/bootstrap/health")
        assert response.status_code == 200

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in response.headers["Permissions-Policy"]
        assert "microphone=()" in response.headers["Permissions-Policy"]
        assert "geolocation=()" in response.headers["Permissions-Policy"]

    def test_api_response_has_cache_control_no_store(self, client):
        """API responses under /api/ must have Cache-Control: no-store."""
        response = client.get("/api/v1/bootstrap/health")
        assert response.headers.get("Cache-Control") == "no-store"

    def test_static_asset_is_cacheable_not_no_store(self, client):
        """/assets/* responses are cached for a day, never no-store."""
        response = client.get("/assets/js/auth.js")
        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "public, max-age=86400, must-revalidate"

    def test_html_page_is_no_store(self, client):
        """HTML pages are served no-store so they always carry current ?v= asset hashes
        (api/main.py::_serve_page)."""
        response = client.get("/login")
        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "no-store"

    def test_x_xss_protection_not_present(self, client):
        """X-XSS-Protection is obsolete and must NOT be set."""
        response = client.get("/api/v1/bootstrap/health")
        assert "X-XSS-Protection" not in response.headers

    def test_security_headers_on_frontend_route(self, client):
        """Frontend routes also get the four core security headers."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


class TestRateLimiting:
    """Verify rate limiting produces 429 after threshold."""

    def test_rate_limit_returns_429(self, client):
        """
        Exceeding the rate limit must return 429 Too Many Requests.

        The limit is read from settings.RATE_LIMIT (default 300/minute, e.g.
        "300/minute"). We send limit+1 requests and verify the last one is
        rejected. TestClient is in-process (no network), so this completes
        quickly.
        """
        from api.config import settings
        from api.main import app, limiter

        limit = int(settings.RATE_LIMIT.split("/")[0])

        # NOTE: deliberately NOT using `with TestClient(app) as test_client:` here.
        # Entering/exiting TestClient as a context manager fires the app's
        # lifespan shutdown handler (api/main.py -> close_pool()), which closes
        # the shared psycopg2 pool that tests/conftest.py's session-scoped
        # `_db_conn` fixture draws its connection from. That poisoned every
        # test module that ran afterward in the same pytest session with
        # "psycopg2.InterfaceError: connection already closed". A plain
        # TestClient(app) serves requests without ever running startup/shutdown.
        test_client = TestClient(app)
        last_status = None
        for i in range(limit + 1):
            resp = test_client.get("/api/v1/bootstrap/health")
            last_status = resp.status_code
            if last_status == 429:
                break

        assert last_status == 429, (
            f"After {limit + 1} requests, rate limit ({settings.RATE_LIMIT}) should return 429"
        )


class TestCORS:
    """Verify CORS behaviour with and without configured origins."""

    def test_no_cors_headers_without_configured_origins(self, client):
        """
        When CORS_ORIGINS is empty (default), no CORS headers should
        appear even if the request includes an Origin header.
        """
        response = client.get(
            "/api/v1/bootstrap/health",
            headers={"Origin": "https://evil.example.com"},
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_cors_preflight_without_configured_origins(self, client):
        """
        OPTIONS preflight without configured origins should not
        return CORS allow headers.
        """
        response = client.options(
            "/api/v1/bootstrap/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "Access-Control-Allow-Origin" not in response.headers


# ── Content-Security-Policy (Tier 5 advisory A2) ─────────────────────────

def _csp_directives(header_value: str) -> dict[str, list[str]]:
    """Parse a CSP header value into {directive: [source, ...]}."""
    directives: dict[str, list[str]] = {}
    for raw in header_value.split(";"):
        parts = raw.split()
        if parts:
            directives[parts[0]] = parts[1:]
    return directives


class TestContentSecurityPolicy:
    """
    Verify the Content-Security-Policy header.

    The policy is asserted directive by directive rather than as one opaque
    string, so a future tightening (e.g. dropping 'unsafe-eval' after moving
    to the Alpine CSP build) fails only the assertion it actually changes.
    """

    def test_csp_present_on_frontend_response(self, client):
        """Frontend pages must carry the CSP header."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers

    def test_csp_present_on_api_response(self, client):
        """API responses must carry the CSP header too."""
        response = client.get("/api/v1/bootstrap/health")
        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers

    def test_csp_locks_down_default_and_dangerous_directives(self, client):
        """default-src is self-only; plugins, framing and base hijacking blocked."""
        d = _csp_directives(client.get("/").headers["Content-Security-Policy"])

        assert d["default-src"] == ["'self'"]
        assert d["object-src"] == ["'none'"]
        assert d["frame-ancestors"] == ["'none'"]
        assert d["base-uri"] == ["'self'"]
        assert d["form-action"] == ["'self'"]
        assert d["connect-src"] == ["'self'"]
        assert d["font-src"] == ["'self'"]

    def test_csp_script_src_forbids_unsafe_inline(self, client):
        """
        The whole point of removing every inline event handler: an injected
        on*= attribute or <script> block must not be executable.
        """
        d = _csp_directives(client.get("/").headers["Content-Security-Policy"])
        assert "'unsafe-inline'" not in d["script-src"]

    def test_csp_script_src_allows_alpine(self, client):
        """
        Alpine.js is CDN-hosted (SRI-pinned) and its default build compiles
        directive expressions with new Function() — both allowances are
        required for the frontend to work at all.
        """
        d = _csp_directives(client.get("/").headers["Content-Security-Policy"])
        assert "'self'" in d["script-src"]
        assert "https://cdn.jsdelivr.net" in d["script-src"]
        assert "'unsafe-eval'" in d["script-src"]

    def test_csp_style_src_allows_inline(self, client):
        """Inline style= attributes are used throughout; nonces cannot cover them."""
        d = _csp_directives(client.get("/").headers["Content-Security-Policy"])
        assert "'unsafe-inline'" in d["style-src"]

    def test_csp_img_src_allows_data_uris(self, client):
        """tailwind.min.css embeds form-control icons as data:image/svg+xml."""
        d = _csp_directives(client.get("/").headers["Content-Security-Policy"])
        assert "data:" in d["img-src"]

    def test_csp_absent_on_swagger_docs(self, client):
        """
        Swagger UI embeds an inline <script>, so /docs is exempt. (It is
        disabled outright in production via DISABLE_DOCS.)
        """
        response = client.get("/docs")
        if response.status_code == 404:
            pytest.skip("Docs disabled via DISABLE_DOCS.")
        assert "Content-Security-Policy" not in response.headers

    def test_csp_report_only_mode(self, client, monkeypatch):
        """CSP_REPORT_ONLY switches to the non-blocking report-only header."""
        from api.config import settings

        monkeypatch.setattr(settings, "CSP_REPORT_ONLY", True)
        response = client.get("/")
        assert "Content-Security-Policy-Report-Only" in response.headers
        assert "Content-Security-Policy" not in response.headers

    def test_csp_can_be_disabled(self, client, monkeypatch):
        """CSP_ENABLED=false suppresses the header entirely (escape hatch)."""
        from api.config import settings

        monkeypatch.setattr(settings, "CSP_ENABLED", False)
        response = client.get("/")
        assert "Content-Security-Policy" not in response.headers
        assert "Content-Security-Policy-Report-Only" not in response.headers

    def test_csp_extra_origins_are_appended(self, client, monkeypatch):
        """Adding a CDN is an env change, not a code change."""
        from api.config import settings

        monkeypatch.setattr(settings, "CSP_SCRIPT_SRC_EXTRA", ["https://cdn.example.com"])
        monkeypatch.setattr(settings, "CSP_STYLE_SRC_EXTRA", ["https://style.example.com"])
        d = _csp_directives(client.get("/").headers["Content-Security-Policy"])

        assert "https://cdn.example.com" in d["script-src"]
        assert "https://style.example.com" in d["style-src"]


class TestNoInlineEventHandlers:
    """
    Source guard for the CSP: script-src omits 'unsafe-inline', so any inline
    event handler or inline <script> block in the frontend would be silently
    dead in the browser. These tests fail the suite instead.
    """

    # on*=" not preceded by - a-z @ or : — excludes Alpine's @click / x-on:,
    # hyphenated attributes, and JS property access like this.onerror.
    _HANDLER_RE = re.compile(r'[^-a-zA-Z@:]on[a-z]+\s*=\s*"')

    @staticmethod
    def _frontend_dir() -> Path:
        return Path(__file__).resolve().parents[2] / "frontend"

    def test_no_inline_event_handlers_in_html(self):
        """No on*="..." attributes in any page."""
        offenders = []
        for path in sorted(self._frontend_dir().glob("*.html")):
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if self._HANDLER_RE.search(line):
                    offenders.append(f"{path.name}:{lineno}")

        assert not offenders, (
            "Inline event handlers found — CSP script-src omits 'unsafe-inline', "
            "so these will not fire. Use a CSS state selector or an Alpine "
            f"@event binding instead: {offenders}"
        )

    def test_no_inline_event_handlers_emitted_by_js(self):
        """
        No on*="..." in HTML-string templates built by JS either — those are
        injected via innerHTML and are equally blocked. Use the delegated
        data-nss-action hook in nss-layout.js.
        """
        offenders = []
        js_dir = self._frontend_dir() / "assets" / "js"
        for path in sorted(js_dir.glob("*.js")):
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if self._HANDLER_RE.search(line):
                    offenders.append(f"{path.name}:{lineno}")

        assert not offenders, f"Inline event handlers emitted by JS: {offenders}"

    def test_no_inline_script_blocks_in_html(self):
        """
        No <script> without a src=. All page logic lives in /assets/js/, which
        is what lets script-src stay free of 'unsafe-inline'.
        """
        offenders = []
        for path in sorted(self._frontend_dir().glob("*.html")):
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                for match in re.finditer(r"<script(\s[^>]*)?>", line):
                    if "src=" not in (match.group(1) or ""):
                        offenders.append(f"{path.name}:{lineno}")

        assert not offenders, f"Inline <script> blocks found: {offenders}"


class TestDebugModeWarning:
    """
    Tier 5 advisory A5: DEBUG_MODE makes /auth/forgot-password echo the
    plaintext reset OTP. It defaults to off; startup must make it loud if an
    environment ever turns it on.
    """

    def test_warns_when_debug_mode_enabled(self, monkeypatch, caplog):
        from api.config import settings
        from api.main import _warn_on_insecure_settings

        monkeypatch.setattr(settings, "DEBUG_MODE", True)
        with caplog.at_level(logging.WARNING):
            _warn_on_insecure_settings()

        assert any("DEBUG_MODE is enabled" in r.getMessage() for r in caplog.records), (
            "Enabling DEBUG_MODE must emit a startup security warning."
        )

    def test_silent_when_settings_are_secure(self, monkeypatch, caplog):
        from api.config import settings
        from api.main import _warn_on_insecure_settings

        monkeypatch.setattr(settings, "DEBUG_MODE", False)
        monkeypatch.setattr(settings, "CSP_ENABLED", True)
        monkeypatch.setattr(settings, "CSP_REPORT_ONLY", False)
        monkeypatch.setattr(settings, "DEV_LIVE_RELOAD", False)
        with caplog.at_level(logging.WARNING):
            _warn_on_insecure_settings()

        assert not caplog.records, (
            f"Secure defaults must not warn: {[r.getMessage() for r in caplog.records]}"
        )


class TestDevLiveReload:
    """
    DEV_LIVE_RELOAD is development-only browser auto-reload. The production
    guarantee is that with the flag at its default the dev endpoint does not
    exist at all and no page references the client script.

    Note on coverage: the route is registered inside an
    `if settings.DEV_LIVE_RELOAD:` block at api.main import time, so the
    flag-ON *route* cannot be exercised here — api.main (and the module-level
    `app` that tests/conftest.py attaches its dependency overrides to) is
    already imported with the flag off, and the only ways to flip it would be
    importlib.reload(api.main) or building a second app, both of which would
    detach the shared test connection overrides. The flag-on behaviour is
    therefore covered through its two pure helpers (fingerprint + injection),
    which read settings at call time, plus the live curl check documented in
    the Configuration section of docs/PROJECT_DOCUMENTATION.md.
    """

    def test_dev_version_endpoint_absent_by_default(self, client):
        """With DEV_LIVE_RELOAD unset the route is never registered."""
        from api.config import settings

        assert settings.DEV_LIVE_RELOAD is False, (
            "DEV_LIVE_RELOAD must default to off."
        )
        assert client.get("/__dev/frontend-version").status_code == 404

    def test_pages_do_not_reference_dev_reload_by_default(self, client):
        """No served page carries the dev-reload script when the flag is off."""
        for path in ("/login", "/register", "/dashboard", "/admin"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "dev-reload.js" not in response.text, path

    def test_dev_reload_script_is_not_referenced_in_html_source(self):
        """The tag is injected at serve time, never committed into a page."""
        frontend = Path(__file__).resolve().parents[2] / "frontend"
        for page in frontend.glob("*.html"):
            assert "dev-reload.js" not in page.read_text(encoding="utf-8"), page.name

    def test_injection_adds_versioned_tag_when_flag_on(self, monkeypatch):
        """Flag on: the tag lands before </body> and gets a ?v=<hash>."""
        from api.config import settings
        from api.main import _render_html_with_asset_versions, _FRONTEND_DIR

        monkeypatch.setattr(settings, "DEV_LIVE_RELOAD", True)
        html = _render_html_with_asset_versions(_FRONTEND_DIR / "login.html")

        match = re.search(r'<script src="/assets/js/dev-reload\.js\?v=([a-f0-9]+)">', html)
        assert match, "Injected dev-reload tag missing or not cache-busted."
        assert html.index(match.group(0)) < html.rindex("</body>")

    def test_injection_absent_when_flag_off(self, monkeypatch):
        from api.config import settings
        from api.main import _render_html_with_asset_versions, _FRONTEND_DIR

        monkeypatch.setattr(settings, "DEV_LIVE_RELOAD", False)
        html = _render_html_with_asset_versions(_FRONTEND_DIR / "login.html")
        assert "dev-reload.js" not in html

    def test_injection_handles_html_without_body_tag(self, monkeypatch):
        from api.main import _inject_dev_reload_script

        out = _inject_dev_reload_script("<div>fragment</div>")
        assert "dev-reload.js" in out
        assert out.startswith("<div>fragment</div>")

    def test_fingerprint_detects_add_modify_and_delete(self):
        """A bare max-mtime would miss deletions — the hash must not."""
        from api.main import _frontend_fingerprint, _FRONTEND_DIR

        probe = _FRONTEND_DIR / "_dev_reload_fingerprint_probe.txt"
        baseline = _frontend_fingerprint()
        try:
            probe.write_text("a", encoding="utf-8")
            after_add = _frontend_fingerprint()
            assert after_add != baseline, "Adding a file must change the fingerprint."

            os.utime(probe, (0, 0))
            after_modify = _frontend_fingerprint()
            assert after_modify != after_add, "An mtime change must be detected."
        finally:
            probe.unlink(missing_ok=True)

        assert _frontend_fingerprint() == baseline, (
            "Deleting the file must restore the original fingerprint."
        )

    def test_fingerprint_ignores_dotfiles(self):
        """.DS_Store churn must not trigger reloads."""
        from api.main import _frontend_fingerprint, _FRONTEND_DIR

        probe = _FRONTEND_DIR / "._dev_reload_dotfile_probe"
        baseline = _frontend_fingerprint()
        try:
            probe.write_text("a", encoding="utf-8")
            assert _frontend_fingerprint() == baseline, (
                "Dotfiles under frontend/ must be excluded from the fingerprint."
            )
        finally:
            probe.unlink(missing_ok=True)

    def test_warns_when_dev_live_reload_enabled(self, monkeypatch, caplog):
        from api.config import settings
        from api.main import _warn_on_insecure_settings

        monkeypatch.setattr(settings, "DEBUG_MODE", False)
        monkeypatch.setattr(settings, "CSP_ENABLED", True)
        monkeypatch.setattr(settings, "CSP_REPORT_ONLY", False)
        monkeypatch.setattr(settings, "DEV_LIVE_RELOAD", True)
        with caplog.at_level(logging.WARNING):
            _warn_on_insecure_settings()

        assert any(
            "DEV_LIVE_RELOAD is enabled" in r.getMessage() for r in caplog.records
        ), "Enabling DEV_LIVE_RELOAD must emit a startup security warning."
