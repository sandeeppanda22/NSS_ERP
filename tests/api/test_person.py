"""
NSS ERP — Tier 3 Person API tests.

Integration tests for the 4 Person GET endpoints across 2 tables.
Runs against local PostgreSQL (not Neon). The database must be
bootstrapped with DDL + seed before running.

Person tables have no seed data — the test suite verifies endpoint
structure, response shapes, error handling, security, and UI rendering.
Data-dependent assertions (field values, counts) are guarded by
availability.

Endpoint groups tested:
  1. Person List:     /persons (with filters)
  2. Person Detail:   /persons/{person_pk}
  3. Addresses:       /persons/{person_pk}/addresses
  4. Search:          /search?q=
  5. Security:        aadhaar exclusion, security headers
  6. UI Route:        /person serves HTML

Pagination contract (both /persons and /search):
  Both endpoints return an envelope — `{persons: [...], total: N}` —
  rather than a bare array. `total` is the true row count matching
  the filters, independent of the MAX_LIMIT (or search-specific) cap
  on `persons`. This replaced a bare-array response on both endpoints
  because a capped array alone cannot tell a caller whether more rows
  exist beyond the page returned (silent truncation).
"""

import pytest


pytestmark = pytest.mark.integration

BASE = "/api/v1/person"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"


# The Person read endpoints are RBAC-gated (PERSON_VIEW) as of Tier 5.
# Override the shared anonymous `client` with an authenticated admin client
# for this whole module so the functional tests exercise real data instead
# of bouncing off 401. (The standalone /person page these once mirrored has
# been retired in favour of admin.html's authenticated Person Directory tab.)
@pytest.fixture(scope="module")
def client(authed_client):
    return authed_client


# ═══════════════════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════════════════


def _list_persons(client, **params):
    """GET /persons, returning the `persons` array from the envelope."""
    r = client.get(f"{BASE}/persons", params=params)
    return r.json()["persons"]


def _search_persons(client, **params):
    """GET /search, returning the `persons` array from the envelope."""
    r = client.get(f"{BASE}/search", params=params)
    return r.json()["persons"]


def _get_first_person_pk(client):
    """Return the PK of the first person, or None if no data."""
    data = _list_persons(client)
    return data[0]["person_pk"] if data else None


# ═══════════════════════════════════════════════════════════════════════════
# 1. PERSON LIST
# ═══════════════════════════════════════════════════════════════════════════


class TestPersonList:
    """GET /api/v1/person/persons"""

    def test_list_returns_200(self, client):
        """Person list endpoint returns 200."""
        r = client.get(f"{BASE}/persons")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["persons"], list)

    def test_list_returns_envelope_with_total(self, client):
        """Response is {persons, total}, not a bare array."""
        r = client.get(f"{BASE}/persons")
        assert r.status_code == 200
        data = r.json()
        assert "persons" in data
        assert "total" in data
        assert isinstance(data["total"], int)

    def test_list_total_is_never_less_than_returned_rows(self, client):
        """
        total must reflect the true row count, not len(persons) — a
        page can never be larger than the total it was drawn from.
        """
        data = client.get(f"{BASE}/persons").json()
        assert data["total"] >= len(data["persons"])

    def test_list_total_unaffected_by_limit(self, client):
        """
        total is the count of matching rows regardless of pagination —
        asking for a smaller page must not shrink the reported total.
        """
        full = client.get(f"{BASE}/persons").json()
        capped = client.get(f"{BASE}/persons", params={"limit": 1}).json()
        assert capped["total"] == full["total"]

    def test_list_has_required_fields_if_data(self, client):
        """Each person summary has the expected response fields."""
        required = {
            "person_pk", "person_id",
            "first_name", "middle_name", "last_name",
            "date_of_birth", "date_of_death",
            "gender_code", "gender_name",
            "marital_status_code", "marital_status_name",
            "blood_group_code", "blood_group_name",
            "country_phone_code", "mobile_number", "email",
            "is_active",
        }
        for p in _list_persons(client):
            assert required.issubset(p.keys()), (
                f"Missing fields in person {p.get('person_id', '?')}: "
                f"{required - p.keys()}"
            )

    def test_list_all_active(self, client):
        """All returned persons have is_active=True."""
        for p in _list_persons(client):
            assert p["is_active"] is True

    def test_list_excludes_audit_columns(self, client):
        """Audit columns must never appear in the response."""
        audit_cols = {
            "created_at", "updated_at", "deleted_at",
            "created_by_sangha_sevi_pk",
            "updated_by_sangha_sevi_pk",
            "deleted_by_sangha_sevi_pk",
        }
        for p in _list_persons(client):
            assert audit_cols.isdisjoint(p.keys()), (
                f"Audit columns leaked in person {p.get('person_id', '?')}: "
                f"{audit_cols & p.keys()}"
            )

    def test_list_excludes_sensitive_aadhaar(self, client):
        """Summary list must not contain aadhaar_encrypted or aadhaar_hash."""
        for p in _list_persons(client):
            assert "aadhaar_encrypted" not in p
            assert "aadhaar_hash" not in p
            # Summary also excludes aadhaar_last4
            assert "aadhaar_last4" not in p


class TestPersonListSorting:
    """
    GET /api/v1/person/persons?sort_by=…&sort_dir=…

    Sorting is done in SQL rather than in the browser because the response
    is capped at MAX_LIMIT: the Person Directory would otherwise be
    reordering whichever 500 rows happened to come back, and calling that
    the order of the directory.
    """

    COLUMNS = [
        "person_id", "person_name", "first_name", "last_name",
        "date_of_birth", "gender_name", "marital_status_name",
        "blood_group_name", "mobile_number", "email",
    ]

    @pytest.mark.parametrize("column", COLUMNS)
    @pytest.mark.parametrize("direction", ["asc", "desc"])
    def test_every_advertised_column_is_accepted(self, client, column, direction):
        r = client.get(
            f"{BASE}/persons", params={"sort_by": column, "sort_dir": direction}
        )
        assert r.status_code == 200, f"{column}/{direction} → {r.status_code}: {r.text}"

    def test_unknown_column_is_a_readable_422(self, client):
        r = client.get(f"{BASE}/persons", params={"sort_by": "nickname"})
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert "not a sortable column" in detail
        # The message must name the alternatives, or the user is stuck.
        assert "person_id" in detail

    def test_injection_via_sort_by_is_rejected(self, client):
        """
        The column cannot be a bound parameter, so it is interpolated —
        the whitelist is the only thing standing between this query string
        and arbitrary SQL.
        """
        r = client.get(
            f"{BASE}/persons",
            params={"sort_by": "p.person_id; DROP TABLE nss.person"},
        )
        assert r.status_code == 422
        # And the table is still there.
        assert client.get(f"{BASE}/persons").status_code == 200

    def test_asc_and_desc_are_actual_reverses(self, client):
        # Paginated list: compare the FIRST page of asc with the LAST page of
        # desc (offset = total - n); on a DB larger than a page the two first
        # pages are opposite ends, not reverses.
        n = 5
        first = client.get(f"{BASE}/persons", params={
            "sort_by": "person_id", "sort_dir": "asc", "limit": n}).json()
        total = first["total"]
        if total < 2:
            pytest.skip("needs at least two persons")
        n = min(n, total)
        tail = client.get(f"{BASE}/persons", params={
            "sort_by": "person_id", "sort_dir": "desc",
            "limit": n, "offset": total - n}).json()
        ids_asc = [p["person_id"] for p in first["persons"]][:n]
        ids_desc = [p["person_id"] for p in tail["persons"]]
        assert ids_asc == list(reversed(ids_desc))

    def test_person_id_sorts_numerically_not_as_text(self, client):
        """
        Every ID here is prefix + trailing digits, so plain text collation
        would place P100 before P9 and the column would read as noise.
        """
        data = _list_persons(client, sort_by="person_id", sort_dir="asc")
        if len(data) < 2:
            pytest.skip("needs at least two persons")

        def key(pid):
            digits = "".join(ch for ch in pid if ch.isdigit())
            return ("".join(ch for ch in pid if not ch.isdigit()),
                    int(digits) if digits else -1)

        ids = [p["person_id"] for p in data]
        assert ids == sorted(ids, key=key)

    def test_blank_values_sort_last_in_both_directions(self, client):
        """A missing value is not the smallest value."""
        for direction in ("asc", "desc"):
            data = _list_persons(client, sort_by="email", sort_dir=direction)
            filled = [i for i, p in enumerate(data) if p.get("email")]
            blank = [i for i, p in enumerate(data) if not p.get("email")]
            if not filled or not blank:
                continue
            assert max(filled) < min(blank), (
                f"blank emails must come last ({direction})"
            )

    def test_default_order_is_unchanged_when_no_sort_requested(self, client):
        """The directory's original order must survive the feature."""
        data = _list_persons(client)
        names = [(p["first_name"], p["last_name"]) for p in data]
        assert names == sorted(names)

    def test_filter_by_gender_code_returns_200(self, client):
        """Filtering by gender_code returns 200."""
        r = client.get(f"{BASE}/persons", params={"gender_code": "MALE"})
        assert r.status_code == 200
        for p in r.json()["persons"]:
            assert p["gender_code"] == "MALE"

    def test_filter_by_marital_status_code_returns_200(self, client):
        """Filtering by marital_status_code returns 200."""
        r = client.get(f"{BASE}/persons", params={"marital_status_code": "MARRIED"})
        assert r.status_code == 200
        assert isinstance(r.json()["persons"], list)

    def test_filter_by_blood_group_code_returns_200(self, client):
        """Filtering by blood_group_code returns 200."""
        r = client.get(f"{BASE}/persons", params={"blood_group_code": "O_POSITIVE"})
        assert r.status_code == 200
        assert isinstance(r.json()["persons"], list)

    def test_filter_nonexistent_gender_returns_empty(self, client):
        """Filtering by a nonexistent gender code returns empty list and zero total."""
        r = client.get(f"{BASE}/persons", params={"gender_code": "ZZZZZ_FAKE"})
        assert r.status_code == 200
        data = r.json()
        assert data["persons"] == []
        assert data["total"] == 0

    def test_multiple_filters_returns_200(self, client):
        """Combining multiple filters returns 200."""
        r = client.get(f"{BASE}/persons", params={
            "gender_code": "MALE",
            "marital_status_code": "MARRIED",
            "blood_group_code": "O_POSITIVE",
        })
        assert r.status_code == 200
        assert isinstance(r.json()["persons"], list)

    # ── Pagination ──────────────────────────────────────────────────────

    def test_pagination_default_returns_200(self, client):
        """Default limit/offset returns 200."""
        r = client.get(f"{BASE}/persons")
        assert r.status_code == 200

    def test_pagination_custom_limit(self, client):
        """limit=1 returns at most 1 person."""
        data = _list_persons(client, limit=1)
        assert len(data) <= 1

    def test_pagination_limit_zero_returns_422(self, client):
        """limit=0 violates ge=1 constraint — returns 422."""
        r = client.get(f"{BASE}/persons", params={"limit": 0})
        assert r.status_code == 422

    def test_pagination_limit_over_max_returns_422(self, client):
        """limit=501 exceeds MAX_LIMIT=500 — returns 422."""
        r = client.get(f"{BASE}/persons", params={"limit": 501})
        assert r.status_code == 422

    def test_pagination_negative_offset_returns_422(self, client):
        """offset=-1 violates ge=0 constraint — returns 422."""
        r = client.get(f"{BASE}/persons", params={"offset": -1})
        assert r.status_code == 422

    def test_pagination_large_offset_returns_empty(self, client):
        """offset beyond total count returns empty list, not error."""
        r = client.get(f"{BASE}/persons", params={"offset": 9999})
        assert r.status_code == 200
        assert r.json()["persons"] == []

    def test_pagination_max_limit_accepted(self, client):
        """limit=500 (MAX_LIMIT) is accepted."""
        r = client.get(f"{BASE}/persons", params={"limit": 500})
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 2. PERSON DETAIL
# ═══════════════════════════════════════════════════════════════════════════


class TestPersonDetail:
    """GET /api/v1/person/persons/{person_pk}"""

    def test_detail_fake_pk_returns_404(self, client):
        """Fetching a nonexistent person returns 404."""
        r = client.get(f"{BASE}/persons/{FAKE_UUID}")
        assert r.status_code == 404

    def test_detail_bad_uuid_returns_422(self, client):
        """Malformed UUID returns 422."""
        r = client.get(f"{BASE}/persons/not-a-uuid")
        assert r.status_code == 422

    def test_detail_valid_pk_returns_200(self, client):
        """Fetching a person by valid PK returns 200 with full fields."""
        pk = _get_first_person_pk(client)
        if pk is None:
            pytest.skip("No person data seeded")
        r = client.get(f"{BASE}/persons/{pk}")
        assert r.status_code == 200
        data = r.json()
        assert data["person_pk"] == pk

    def test_detail_has_required_fields(self, client):
        """Full detail response has all PersonResponse fields."""
        pk = _get_first_person_pk(client)
        if pk is None:
            pytest.skip("No person data seeded")
        required = {
            "person_pk", "person_id",
            "first_name", "middle_name", "last_name",
            "date_of_birth", "date_of_death",
            "gender_master_data_pk", "gender_code", "gender_name",
            "marital_status_master_data_pk", "marital_status_code",
            "marital_status_name",
            "blood_group_master_data_pk", "blood_group_code",
            "blood_group_name",
            "country_phone_code", "mobile_number", "email",
            "aadhaar_last4",
            "photo_document_master_pk",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_relationship_master_data_pk",
            "emergency_relationship_code", "emergency_relationship_name",
            "remarks", "is_active",
        }
        data = client.get(f"{BASE}/persons/{pk}").json()
        assert required.issubset(data.keys()), (
            f"Missing fields: {required - data.keys()}"
        )

    def test_detail_excludes_sensitive_aadhaar(self, client):
        """Detail response must never contain raw Aadhaar fields."""
        pk = _get_first_person_pk(client)
        if pk is None:
            pytest.skip("No person data seeded")
        data = client.get(f"{BASE}/persons/{pk}").json()
        assert "aadhaar_encrypted" not in data
        assert "aadhaar_hash" not in data

    def test_detail_excludes_audit_columns(self, client):
        """Audit columns must never appear in detail response."""
        pk = _get_first_person_pk(client)
        if pk is None:
            pytest.skip("No person data seeded")
        audit_cols = {
            "created_at", "updated_at", "deleted_at",
            "created_by_sangha_sevi_pk",
            "updated_by_sangha_sevi_pk",
            "deleted_by_sangha_sevi_pk",
        }
        data = client.get(f"{BASE}/persons/{pk}").json()
        assert audit_cols.isdisjoint(data.keys()), (
            f"Audit columns leaked: {audit_cols & data.keys()}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. ADDRESSES
# ═══════════════════════════════════════════════════════════════════════════


class TestPersonAddresses:
    """GET /api/v1/person/persons/{person_pk}/addresses"""

    def test_addresses_fake_pk_returns_404(self, client):
        """Addresses for a nonexistent person returns 404."""
        r = client.get(f"{BASE}/persons/{FAKE_UUID}/addresses")
        assert r.status_code == 404

    def test_addresses_bad_uuid_returns_422(self, client):
        """Malformed UUID in addresses route returns 422."""
        r = client.get(f"{BASE}/persons/not-a-uuid/addresses")
        assert r.status_code == 422

    def test_addresses_valid_pk_returns_200(self, client):
        """Addresses for a valid person returns 200 (possibly empty)."""
        pk = _get_first_person_pk(client)
        if pk is None:
            pytest.skip("No person data seeded")
        r = client.get(f"{BASE}/persons/{pk}/addresses")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_addresses_has_required_fields_if_data(self, client):
        """Each address has the expected response fields."""
        pk = _get_first_person_pk(client)
        if pk is None:
            pytest.skip("No person data seeded")
        required = {
            "person_address_pk", "person_pk",
            "address_type_master_data_pk", "address_type_code",
            "address_type_name",
            "address_line_1", "address_line_2", "landmark",
            "city_village_pk", "postal_code_pk",
            "city_village_name", "postal_code",
            "district_name", "state_name", "country_name",
            "is_primary", "remarks", "is_active",
        }
        data = client.get(f"{BASE}/persons/{pk}/addresses").json()
        for addr in data:
            assert required.issubset(addr.keys()), (
                f"Missing fields in address: {required - addr.keys()}"
            )

    def test_addresses_primary_first(self, client):
        """Primary addresses are ordered before non-primary."""
        pk = _get_first_person_pk(client)
        if pk is None:
            pytest.skip("No person data seeded")
        data = client.get(f"{BASE}/persons/{pk}/addresses").json()
        if len(data) >= 2:
            # Primary addresses come first in the ordering
            primaries = [a for a in data if a["is_primary"]]
            non_primaries = [a for a in data if not a["is_primary"]]
            if primaries and non_primaries:
                first_non_primary_idx = next(
                    i for i, a in enumerate(data) if not a["is_primary"]
                )
                last_primary_idx = max(
                    i for i, a in enumerate(data) if a["is_primary"]
                )
                assert last_primary_idx < first_non_primary_idx


# ═══════════════════════════════════════════════════════════════════════════
# 4. SEARCH
# ═══════════════════════════════════════════════════════════════════════════


class TestPersonSearch:
    """GET /api/v1/person/search?q="""

    def test_search_returns_200(self, client):
        """Search with a valid query returns 200."""
        r = client.get(f"{BASE}/search", params={"q": "test"})
        assert r.status_code == 200
        assert isinstance(r.json()["persons"], list)

    def test_search_returns_envelope_with_total(self, client):
        """Response is {persons, total}, not a bare array."""
        r = client.get(f"{BASE}/search", params={"q": "test"})
        data = r.json()
        assert "persons" in data
        assert "total" in data
        assert data["total"] >= len(data["persons"])

    def test_search_requires_query(self, client):
        """Search without q parameter returns 422."""
        r = client.get(f"{BASE}/search")
        assert r.status_code == 422

    def test_search_min_length_validation(self, client):
        """Search with single character returns 422 (min_length=2)."""
        r = client.get(f"{BASE}/search", params={"q": "a"})
        assert r.status_code == 422

    def test_search_two_chars_accepted(self, client):
        """Search with exactly 2 characters returns 200."""
        r = client.get(f"{BASE}/search", params={"q": "ab"})
        assert r.status_code == 200

    def test_search_returns_summary_fields(self, client):
        """Search results use PersonSummaryResponse shape."""
        for p in _search_persons(client, q="test"):
            assert "person_pk" in p
            assert "person_id" in p
            assert "first_name" in p
            assert "is_active" in p
            # Summary: no aadhaar, no emergency
            assert "aadhaar_encrypted" not in p
            assert "aadhaar_hash" not in p
            assert "aadhaar_last4" not in p

    def test_search_excludes_audit_columns(self, client):
        """Search results must not contain audit columns."""
        audit_cols = {
            "created_at", "updated_at", "deleted_at",
            "created_by_sangha_sevi_pk",
            "updated_by_sangha_sevi_pk",
            "deleted_by_sangha_sevi_pk",
        }
        for p in _search_persons(client, q="test"):
            assert audit_cols.isdisjoint(p.keys())

    def test_search_nonexistent_returns_empty(self, client):
        """Search for a name that cannot exist returns empty list and zero total."""
        r = client.get(f"{BASE}/search", params={"q": "zzzxxyynomatch"})
        assert r.status_code == 200
        data = r.json()
        assert data["persons"] == []
        assert data["total"] == 0

    def test_search_by_email(self, client):
        """Searching by email prefix finds a matching person."""
        persons = _list_persons(client)
        with_email = [p for p in persons if p.get("email")]
        if not with_email:
            pytest.skip("No persons with email seeded")
        person = with_email[0]
        email_prefix = person["email"].split("@")[0]
        data = _search_persons(client, q=email_prefix)
        ids = [p["person_id"] for p in data]
        assert person["person_id"] in ids, (
            f"Expected {person['person_id']} when searching by email prefix '{email_prefix}', got: {ids}"
        )

    def test_search_default_page_is_50_results(self, client):
        """Default page size (no limit passed) is still 50, matching prior behaviour."""
        r = client.get(f"{BASE}/search", params={"q": "aa"})
        assert r.status_code == 200
        assert len(r.json()["persons"]) <= 50

    def test_search_supports_limit_and_offset(self, client):
        """
        Unlike the old hardcoded LIMIT 50, /search now honours limit/offset
        like /persons — this is what makes total actionable instead of
        informational-only.
        """
        r = client.get(f"{BASE}/search", params={"q": "aa", "limit": 1})
        assert r.status_code == 200
        assert len(r.json()["persons"]) <= 1

    def test_search_limit_over_max_returns_422(self, client):
        """limit=501 exceeds MAX_LIMIT=500 — returns 422, same as /persons."""
        r = client.get(f"{BASE}/search", params={"q": "aa", "limit": 501})
        assert r.status_code == 422

    def test_search_negative_offset_returns_422(self, client):
        """offset=-1 violates ge=0 constraint — returns 422."""
        r = client.get(f"{BASE}/search", params={"q": "aa", "offset": -1})
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 5. SECURITY — Person endpoints
# ═══════════════════════════════════════════════════════════════════════════


class TestPersonSecurity:
    """Verify security middleware and data protection on Person endpoints."""

    def test_person_api_has_security_headers(self, client):
        """Person API responses include the four core security headers."""
        r = client.get(f"{BASE}/persons")
        assert r.status_code == 200
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in r.headers["Permissions-Policy"]

    def test_person_api_has_cache_control_no_store(self, client):
        """Person API responses have Cache-Control: no-store."""
        r = client.get(f"{BASE}/persons")
        assert r.headers.get("Cache-Control") == "no-store"

    def test_search_has_security_headers(self, client):
        """Search endpoint also gets security headers."""
        r = client.get(f"{BASE}/search", params={"q": "test"})
        assert r.headers["X-Content-Type-Options"] == "nosniff"

    def test_404_has_security_headers(self, client):
        """Even 404 responses get security headers."""
        r = client.get(f"{BASE}/persons/{FAKE_UUID}")
        assert r.status_code == 404
        assert r.headers["X-Content-Type-Options"] == "nosniff"
