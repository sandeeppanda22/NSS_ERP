"""
NSS ERP — Sakha Branch tests.

Integration tests for the 175 Sakha Sangha branches, the short_code
column, PIN-to-postal_code_pk mapping, and the registration page
dropdown that loads Sakha branches.

Runs against local PostgreSQL (not Neon). The database must be
bootstrapped with DDL + seed (02_build.sh) before running.

Test groups:
  1. Sakha Branch Seed Verification — count, codes, naming, parent
  2. Short Code Column — constraint, uniqueness, nullable
  3. PIN/Postal Code Mapping — FK resolution
  4. Organization API — Sakha filter, limit, short_code field
  5. Registration Page — HTML loads, dropdown data present
  6. Admin Short Code API — PATCH endpoint (requires admin auth)
"""

import pytest
import re


pytestmark = pytest.mark.integration

BASE = "/api/v1/organization"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"


# Organization read endpoints are RBAC-gated (ORGANIZATION_VIEW) as of Tier 5.
# Authenticate this whole module as an admin. The negative auth tests below
# use the `anon_client` fixture explicitly so they still exercise the 401 path.
@pytest.fixture(scope="module")
def client(authed_client):
    return authed_client


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _get_sakhas(client, limit=500):
    """Fetch all SAKHA_SANGHA organizations."""
    r = client.get(f"{BASE}/organizations", params={
        "type_code": "SAKHA_SANGHA", "limit": limit
    })
    assert r.status_code == 200
    return r.json()


def _get_kendra_pk(client):
    """Find the Kendra organization PK."""
    r = client.get(f"{BASE}/organizations", params={"type_code": "KENDRA"})
    data = r.json()
    return data[0]["organization_pk"] if data else None


# ═══════════════════════════════════════════════════════════════════════════
# 1. SAKHA BRANCH SEED VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════


class TestSakhaBranchSeed:
    """Verify 175 Sakha branches are correctly seeded."""

    def test_sakha_count_is_175(self, client):
        """Exactly 175 Sakha branches should be seeded."""
        sakhas = _get_sakhas(client)
        assert len(sakhas) == 175, f"Expected 175 Sakha branches, got {len(sakhas)}"

    def test_sakha_codes_sequential_unpadded(self, client):
        """Sakha codes should be SKH1–SKH175, unpadded."""
        sakhas = _get_sakhas(client)
        codes = sorted(
            [s["organization_code"] for s in sakhas],
            key=lambda c: int(c.replace("SKH", ""))
        )
        expected = [f"SKH{i}" for i in range(1, 176)]
        assert codes == expected, f"Sakha codes mismatch. First diff: {set(codes) ^ set(expected)}"

    def test_ekamra_is_skh1(self, client):
        """Ekamra Saraswata Sangha must be SKH1."""
        sakhas = _get_sakhas(client)
        skh1 = [s for s in sakhas if s["organization_code"] == "SKH1"]
        assert len(skh1) == 1, "SKH1 not found"
        assert "Ekamra" in skh1[0]["organization_name"], (
            f"SKH1 is '{skh1[0]['organization_name']}', expected Ekamra"
        )

    def test_all_sakhas_parented_to_kendra(self, client):
        """Every Sakha branch must have Kendra as parent."""
        kendra_pk = _get_kendra_pk(client)
        if kendra_pk is None:
            pytest.skip("No Kendra organization seeded")
        sakhas = _get_sakhas(client)
        bad = [s for s in sakhas if s["parent_organization_pk"] != kendra_pk]
        assert len(bad) == 0, (
            f"{len(bad)} Sakhas not parented to Kendra: "
            f"{[s['organization_code'] for s in bad[:5]]}"
        )

    def test_all_sakhas_active(self, client):
        """All Sakha branches should be active."""
        sakhas = _get_sakhas(client)
        inactive = [s for s in sakhas if not s["is_active"]]
        assert len(inactive) == 0

    def test_all_sakhas_have_organization_type(self, client):
        """Every Sakha has type_code = SAKHA_SANGHA."""
        sakhas = _get_sakhas(client)
        for s in sakhas:
            assert s["organization_type_code"] == "SAKHA_SANGHA"

    def test_all_sakhas_have_country(self, client):
        """Every Sakha should have a country_pk resolved."""
        sakhas = _get_sakhas(client)
        no_country = [s for s in sakhas if s["country_pk"] is None]
        assert len(no_country) == 0, (
            f"{len(no_country)} Sakhas missing country: "
            f"{[s['organization_code'] for s in no_country[:5]]}"
        )

    def test_sakha_names_are_unique(self, client):
        """All Sakha names should be unique."""
        sakhas = _get_sakhas(client)
        names = [s["organization_name"] for s in sakhas]
        assert len(names) == len(set(names)), "Duplicate Sakha names found"

    def test_sakha_codes_are_unique(self, client):
        """All Sakha codes should be unique."""
        sakhas = _get_sakhas(client)
        codes = [s["organization_code"] for s in sakhas]
        assert len(codes) == len(set(codes)), "Duplicate Sakha codes found"


# ═══════════════════════════════════════════════════════════════════════════
# 2. SHORT CODE COLUMN
# ═══════════════════════════════════════════════════════════════════════════


class TestShortCodeColumn:
    """Verify short_code field behavior in the API response."""

    def test_short_code_field_present(self, client):
        """Organization response includes short_code field."""
        sakhas = _get_sakhas(client)
        for s in sakhas[:5]:  # spot check first 5
            assert "short_code" in s, (
                f"{s['organization_code']} missing short_code field"
            )

    def test_short_code_nullable(self, write_conn):
        """short_code is a nullable column (schema), not a data assertion --
        the dev DB may already have codes assigned to every Sakha."""
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'nss' AND table_name = 'organization' "
                "AND column_name = 'short_code'"
            )
            row = cur.fetchone()
        assert row is not None, "organization.short_code column missing"
        assert row[0] == "YES"

    def test_short_code_in_all_org_types(self, client):
        """short_code field is present on non-Sakha orgs too."""
        r = client.get(f"{BASE}/organizations", params={"type_code": "KENDRA"})
        assert r.status_code == 200
        for org in r.json():
            assert "short_code" in org


# ═══════════════════════════════════════════════════════════════════════════
# 3. PIN / POSTAL CODE MAPPING
# ═══════════════════════════════════════════════════════════════════════════


class TestPostalCodeMapping:
    """Verify PIN code → postal_code_pk FK resolution."""

    def test_some_sakhas_have_postal_code(self, client):
        """At least 60 Sakhas should have postal_code_pk resolved."""
        sakhas = _get_sakhas(client)
        with_pin = [s for s in sakhas if s["postal_code_pk"] is not None]
        assert len(with_pin) >= 60, (
            f"Expected >= 60 Sakhas with postal_code_pk, got {len(with_pin)}"
        )

    def test_postal_code_format(self, client):
        """Resolved postal codes should be 5-6 digit Indian PIN or US ZIP format."""
        sakhas = _get_sakhas(client)
        with_code = [s for s in sakhas if s.get("postal_code")]
        for s in with_code:
            code = s["postal_code"]
            # Indian PIN: 6 digits, US ZIP: 5 digits
            assert re.match(r'^\d{5,6}$', code), (
                f"{s['organization_code']} has unexpected postal_code: {code}"
            )

    def test_sakhas_without_pin_have_null_postal(self, client):
        """Sakhas without PINs should have NULL postal_code_pk."""
        sakhas = _get_sakhas(client)
        # We know at least some don't have PINs
        without_pin = [s for s in sakhas if s["postal_code_pk"] is None]
        assert len(without_pin) > 0, (
            "Expected some Sakhas without postal_code_pk"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. ORGANIZATION API — SAKHA FILTER
# ═══════════════════════════════════════════════════════════════════════════


class TestSakhaAPIFilter:
    """Verify SAKHA_SANGHA filter on the organizations endpoint."""

    def test_type_filter_returns_only_sakhas(self, client):
        """Filtering by SAKHA_SANGHA returns only Sakha-type orgs."""
        sakhas = _get_sakhas(client)
        for s in sakhas:
            assert s["organization_type_code"] == "SAKHA_SANGHA"

    def test_default_limit_caps_at_100(self, client):
        """Default limit=100 returns at most 100 Sakhas."""
        r = client.get(f"{BASE}/organizations", params={
            "type_code": "SAKHA_SANGHA"
        })
        assert r.status_code == 200
        assert len(r.json()) <= 100

    def test_limit_500_returns_all_175(self, client):
        """limit=500 returns all 175 Sakha branches."""
        sakhas = _get_sakhas(client, limit=500)
        assert len(sakhas) == 175

    def test_pagination_offset_works(self, client):
        """offset=170 returns the last 5 Sakhas."""
        r = client.get(f"{BASE}/organizations", params={
            "type_code": "SAKHA_SANGHA", "limit": 500, "offset": 170
        })
        assert r.status_code == 200
        assert len(r.json()) == 5

    def test_sakhas_ordered_by_name(self, client):
        """Sakhas should be ordered alphabetically by name."""
        sakhas = _get_sakhas(client)
        names = [s["organization_name"] for s in sakhas]
        assert names == sorted(names), "Sakhas not sorted alphabetically"


# ═══════════════════════════════════════════════════════════════════════════
# 5. REGISTRATION PAGE
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistrationPage:
    """Verify registration page loads and references Sakha data."""

    def test_register_page_returns_200(self, client):
        """Registration page returns 200."""
        r = client.get("/register")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_register_page_contains_register_js(self, client):
        """Page loads register.js."""
        html = client.get("/register").text
        assert "register.js" in html

    def test_register_page_contains_auth_js(self, client):
        """Page loads auth.js."""
        html = client.get("/register").text
        assert "auth.js" in html

    def test_register_page_has_sakha_dropdown(self, client):
        """Page HTML has a Sakha selection dropdown."""
        html = client.get("/register").text
        assert "Select Sakha..." in html

    def test_register_page_has_alpine_binding(self, client):
        """Page has x-data binding to registerApp()."""
        html = client.get("/register").text
        assert 'x-data="registerApp()"' in html

    def test_register_page_has_membership_toggle(self, client):
        """Page has the membership credentials toggle."""
        html = client.get("/register").text
        assert "I have membership credentials" in html

    def test_register_page_has_darshak_section(self, client):
        """Page has the Darshak attendance section."""
        html = client.get("/register").text
        assert "Darshak" in html

    def test_register_js_correct_api_url(self, client):
        """register.js loads its Sakha dropdown from the public reference-data
        endpoint (bundled with countries/master-data into one round trip),
        not a direct call to the authenticated /organization router."""
        r = client.get("/assets/js/register.js")
        assert r.status_code == 200
        js = r.text
        assert "/api/v1/register/reference-data" in js
        # Should NOT call organization.py's endpoint directly — that's
        # FOUNDATION_VIEW/ORGANIZATION_VIEW-gated and 403s for this page's
        # anonymous visitors (the exact regression reference-data fixed).
        assert "/api/v1/organization/organizations" not in js

    def test_register_js_requests_sufficient_limit(self, client):
        """The reference-data endpoint register.js calls requests enough
        rows to cover all 175 Sakhas — the limit lives server-side
        (api/routers/registration.py), not as a query param in register.js
        itself since /reference-data takes no limit argument from the caller."""
        from pathlib import Path
        src = Path("api/routers/registration.py").read_text()
        assert 'type_code="SAKHA_SANGHA"' in src
        assert "limit=500" in src, (
            "GET /api/v1/register/reference-data should request enough rows "
            "(limit=500) to cover all 175 Sakha branches"
        )

    def test_register_page_cache_buster_updated(self, client):
        """register.js cache buster should be > v0.1.0."""
        html = client.get("/register").text
        # Old broken version was v0.1.0
        assert "register.js?v=0.1.0" not in html, (
            "register.js still uses old cache buster v0.1.0 — browser may serve stale JS"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 6. ADMIN SHORT CODE API
# ═══════════════════════════════════════════════════════════════════════════


class TestAdminOrganizations:
    """GET /api/v1/admin/organizations (requires auth)."""

    def test_admin_org_list_requires_auth(self, anon_client):
        """Organization list without auth returns 401."""
        r = anon_client.get("/api/v1/admin/organizations")
        assert r.status_code == 401

    def test_admin_short_code_patch_requires_auth(self, anon_client, client):
        """Short code PATCH without auth returns 401."""
        sakhas = _get_sakhas(client)
        if not sakhas:
            pytest.skip("No Sakhas seeded")
        pk = sakhas[0]["organization_pk"]
        r = anon_client.patch(
            f"/api/v1/admin/organizations/{pk}/short-code",
            json={"short_code": "TEST"}
        )
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 7. ID SEQUENCE MASTER — SAKHA PADDING
# ═══════════════════════════════════════════════════════════════════════════


class TestIdSequencePadding:
    """Verify SAKHA sequence uses unpadded codes."""

    def test_sakha_codes_are_unpadded(self, client):
        """Sakha codes should not have zero-padding (SKH1 not SKH001)."""
        sakhas = _get_sakhas(client)
        for s in sakhas:
            code = s["organization_code"]
            num_part = code.replace("SKH", "")
            # Should not start with 0 (except SKH0 which doesn't exist)
            if int(num_part) > 0:
                assert not num_part.startswith("0"), (
                    f"{code} appears to be zero-padded"
                )
