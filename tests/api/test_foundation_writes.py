"""
NSS ERP — Foundation WRITE endpoints and the remaining read gaps.

tests/api/test_foundation.py covers the GET endpoints only. This module adds
the endpoints it never touched:

  Writes (FOUNDATION_MANAGE):
    POST/PATCH /master-data
    POST/PATCH /settings            (per-data_type validation)
    POST/PATCH /sequences
  Writes (FOUNDATION_CALENDAR_MANAGE):
    POST/PATCH /festival-calendar-dates
  Member-assisted geography (authentication only, active Sangha Sevi):
    POST /districts/propose, /postal-codes/propose,
         /post-offices/propose, /city-villages/propose
  Reads:
    GET /post-offices, /sakha-postal-codes, /festivals,
        /festival-calendar-dates (list + filters)

401/403 gating for all of them lives in
tests/security/test_core_modules_security.py.

The admin writer is the shared `authed_client`; tests skip (rather than
fail) if that admin lacks the needed MANAGE permission. Everything runs
inside the module SAVEPOINT and is rolled back.
"""

import itertools
import random
from uuid import uuid4

import pytest

from tests.api.test_family_ownership import (  # noqa: F401  (fixtures)
    make_roleless_member,
    sakha_pk,
)


pytestmark = pytest.mark.integration

BASE = "/api/v1/foundation"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"


_YEARS = itertools.count(2100)


def _tag(n=8):
    return uuid4().hex[:n].upper()


def _require_permission(client, code):
    me = client.get("/api/v1/auth/me")
    if me.status_code != 200 or code not in (me.json().get("permissions") or []):
        pytest.skip(f"authed_client does not hold {code}.")


@pytest.fixture(scope="module")
def admin(authed_client):
    """Admin client; individual classes assert the permission they need."""
    return authed_client


@pytest.fixture(scope="module")
def manager(admin):
    _require_permission(admin, "FOUNDATION_MANAGE")
    return admin


@pytest.fixture(scope="module")
def calendar_manager(admin):
    _require_permission(admin, "FOUNDATION_CALENDAR_MANAGE")
    return admin


# ═══════════════════════════════════════════════════════════════════════════
# MASTER DATA WRITES
# ═══════════════════════════════════════════════════════════════════════════


class TestMasterDataWrites:

    @staticmethod
    @pytest.fixture(scope="class")
    def category_code(manager):
        cats = manager.get(f"{BASE}/categories").json()
        if not cats:
            pytest.skip("No master-data categories.")
        return cats[0]["category_code"]

    def _create(self, manager, category_code, **over):
        body = {
            "category_code": category_code,
            "value_code": f"tst_{_tag()}",
            "value_name": "Matrix Test Value",
            **over,
        }
        return manager.post(f"{BASE}/master-data", json=body), body

    def test_create_returns_201_and_normalises_codes(self, manager, category_code):
        r, body = self._create(manager, category_code.lower())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["value_code"] == body["value_code"].upper()
        assert data["category_code"] == category_code
        assert data["is_active"] is True
        # Visible through the normal read endpoint.
        assert manager.get(f"{BASE}/master-data/{data['master_data_pk']}").status_code == 200

    def test_duplicate_value_code_returns_409(self, manager, category_code):
        r, body = self._create(manager, category_code)
        assert r.status_code == 201
        again = manager.post(f"{BASE}/master-data", json=body)
        assert again.status_code == 409, again.text

    def test_unknown_category_returns_404(self, manager):
        r, _ = self._create(manager, "NO_SUCH_CATEGORY_" + _tag())
        assert r.status_code == 404, r.text

    @pytest.mark.parametrize("body", [
        {},
        {"category_code": "X", "value_code": "", "value_name": "n"},
        {"category_code": "X", "value_code": "V", "value_name": ""},
        {"category_code": "X", "value_code": "V", "value_name": "n", "display_order": -1},
    ])
    def test_invalid_body_returns_422(self, manager, body):
        assert manager.post(f"{BASE}/master-data", json=body).status_code == 422

    def test_patch_updates_editable_fields_only(self, manager, category_code):
        created = self._create(manager, category_code)[0].json()
        pk = created["master_data_pk"]
        r = manager.patch(
            f"{BASE}/master-data/{pk}",
            json={"value_name": "Renamed", "description": "d", "display_order": 7},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert (data["value_name"], data["description"], data["display_order"]) == ("Renamed", "d", 7)
        assert data["value_code"] == created["value_code"]   # immutable

    def test_patch_cannot_change_value_code(self, manager, category_code):
        pk = self._create(manager, category_code)[0].json()["master_data_pk"]
        r = manager.patch(f"{BASE}/master-data/{pk}", json={"value_code": "HACKED"})
        assert r.status_code == 422, r.text      # no editable field supplied

    def test_patch_empty_body_returns_422(self, manager, category_code):
        pk = self._create(manager, category_code)[0].json()["master_data_pk"]
        assert manager.patch(f"{BASE}/master-data/{pk}", json={}).status_code == 422

    def test_patch_unknown_pk_returns_404(self, manager):
        r = manager.patch(f"{BASE}/master-data/{FAKE_UUID}", json={"value_name": "x"})
        assert r.status_code == 404, r.text

    def test_patch_bad_uuid_returns_422(self, manager):
        r = manager.patch(f"{BASE}/master-data/not-a-uuid", json={"value_name": "x"})
        assert r.status_code == 422, r.text


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS WRITES
# ═══════════════════════════════════════════════════════════════════════════


class TestSettingsWrites:

    def _create(self, manager, value, data_type="STRING", **over):
        key = f"TST_{_tag()}"
        r = manager.post(
            f"{BASE}/settings",
            json={"setting_key": key.lower(), "setting_value": value,
                  "data_type": data_type, **over},
        )
        return r, key

    def test_create_uppercases_key_and_is_readable(self, manager):
        r, key = self._create(manager, "hello", description="  d  ")
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["setting_key"] == key
        assert data["data_type"] == "STRING"
        assert data["description"] == "d"
        assert manager.get(f"{BASE}/settings/{key}").json()["setting_value"] == "hello"

    def test_duplicate_key_returns_409(self, manager):
        r, key = self._create(manager, "1")
        assert r.status_code == 201
        again = manager.post(
            f"{BASE}/settings", json={"setting_key": key, "setting_value": "2"}
        )
        assert again.status_code == 409, again.text

    def test_unknown_data_type_returns_422(self, manager):
        r, _ = self._create(manager, "1", data_type="FLOAT")
        assert r.status_code == 422, r.text

    @pytest.mark.parametrize("data_type,value", [
        ("INTEGER", "12.5"),
        ("INTEGER", "abc"),
        ("BOOLEAN", "maybe"),
        ("DATE", "31-31-2020"),
        ("JSON", "{not json"),
    ])
    def test_value_not_matching_data_type_returns_422(self, manager, data_type, value):
        r, _ = self._create(manager, value, data_type=data_type)
        assert r.status_code == 422, r.text

    @pytest.mark.parametrize("data_type,raw,stored", [
        ("INTEGER", " 007 ", "7"),
        ("BOOLEAN", "YES", "true"),
        ("BOOLEAN", "0", "false"),
        ("DATE", "28/10/2026", "28/10/2026"),
        ("DATE", "2026-10-28", "2026-10-28"),
        ("JSON", '{"a": 1}', '{"a": 1}'),
    ])
    def test_value_is_normalised_per_data_type(self, manager, data_type, raw, stored):
        r, _ = self._create(manager, raw, data_type=data_type)
        assert r.status_code == 201, r.text
        assert r.json()["setting_value"] == stored

    def test_create_missing_fields_returns_422(self, manager):
        assert manager.post(f"{BASE}/settings", json={}).status_code == 422

    def test_patch_validates_against_stored_type(self, manager):
        _, key = self._create(manager, "5", data_type="INTEGER")
        bad = manager.patch(f"{BASE}/settings/{key}", json={"setting_value": "five"})
        assert bad.status_code == 422, bad.text
        ok = manager.patch(
            f"{BASE}/settings/{key}",
            json={"setting_value": "042", "description": "new desc"},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["setting_value"] == "42"
        assert ok.json()["description"] == "new desc"
        assert ok.json()["data_type"] == "INTEGER"       # immutable

    def test_patch_without_description_keeps_it(self, manager):
        r, key = self._create(manager, "a", description="keep me")
        assert r.status_code == 201
        out = manager.patch(f"{BASE}/settings/{key}", json={"setting_value": "b"}).json()
        assert out["description"] == "keep me"

    def test_patch_unknown_key_returns_404(self, manager):
        r = manager.patch(f"{BASE}/settings/NO_SUCH_{_tag()}", json={"setting_value": "1"})
        assert r.status_code == 404, r.text

    def test_patch_empty_value_returns_422(self, manager):
        _, key = self._create(manager, "a")
        assert manager.patch(f"{BASE}/settings/{key}", json={"setting_value": ""}).status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# SEQUENCE WRITES
# ═══════════════════════════════════════════════════════════════════════════


class TestSequenceWrites:

    def _create(self, manager, **over):
        tag = _tag()
        body = {
            "sequence_code": f"tst_{tag}", "sequence_name": f"Matrix Seq {tag}",
            "prefix": "tst", "padding_length": 4, **over,
        }
        return manager.post(f"{BASE}/sequences", json=body), body

    def test_create_normalises_and_hides_current_value(self, manager):
        r, body = self._create(manager)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["sequence_code"] == body["sequence_code"].upper()
        assert data["prefix"] == "TST"
        assert "current_value" not in data
        listed = {s["sequence_code"] for s in manager.get(f"{BASE}/sequences").json()}
        assert data["sequence_code"] in listed

    def test_duplicate_code_returns_409(self, manager):
        r, body = self._create(manager)
        assert r.status_code == 201
        other = {**body, "sequence_name": f"Other {_tag()}"}
        assert manager.post(f"{BASE}/sequences", json=other).status_code == 409

    def test_duplicate_name_returns_409(self, manager):
        r, body = self._create(manager)
        assert r.status_code == 201
        other = {**body, "sequence_code": f"tst_{_tag()}"}
        assert manager.post(f"{BASE}/sequences", json=other).status_code == 409

    @pytest.mark.parametrize("over", [
        {"padding_length": 13}, {"padding_length": -1},
        {"prefix": ""}, {"sequence_code": ""},
    ])
    def test_invalid_body_returns_422(self, manager, over):
        assert self._create(manager, **over)[0].status_code == 422

    def test_patch_edits_config(self, manager):
        _, body = self._create(manager)
        code = body["sequence_code"].upper()
        r = manager.patch(
            f"{BASE}/sequences/{code.lower()}",      # lookup is case-insensitive
            json={"sequence_name": f"Renamed {_tag()}", "prefix": "zz",
                  "padding_length": 6, "description": "d"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert (data["prefix"], data["padding_length"], data["description"]) == ("ZZ", 6, "d")
        assert data["sequence_code"] == code             # immutable

    def test_patch_empty_body_returns_422(self, manager):
        _, body = self._create(manager)
        assert manager.patch(f"{BASE}/sequences/{body['sequence_code'].upper()}", json={}).status_code == 422

    def test_patch_unknown_code_returns_404(self, manager):
        r = manager.patch(f"{BASE}/sequences/NO_SUCH_{_tag()}", json={"prefix": "A"})
        assert r.status_code == 404, r.text

    def test_patch_name_collision_returns_409(self, manager):
        _, a = self._create(manager)
        _, b = self._create(manager)
        r = manager.patch(
            f"{BASE}/sequences/{b['sequence_code'].upper()}",
            json={"sequence_name": a["sequence_name"]},
        )
        assert r.status_code == 409, r.text

    def test_patch_keeping_own_name_is_not_a_collision(self, manager):
        _, a = self._create(manager)
        r = manager.patch(
            f"{BASE}/sequences/{a['sequence_code'].upper()}",
            json={"sequence_name": a["sequence_name"], "prefix": "KK"},
        )
        assert r.status_code == 200, r.text


# ═══════════════════════════════════════════════════════════════════════════
# FESTIVAL CALENDAR (reads + FOUNDATION_CALENDAR_MANAGE writes)
# ═══════════════════════════════════════════════════════════════════════════


class TestFestivalReads:

    def test_festivals_list_shape(self, admin):
        r = admin.get(f"{BASE}/festivals")
        assert r.status_code == 200, r.text
        for row in r.json():
            for field in ("festival_master_pk", "festival_code", "festival_name",
                          "is_erp_reference_date", "display_order", "is_active"):
                assert field in row
            assert row["is_active"] is True

    def test_calendar_dates_list_and_filters(self, admin):
        r = admin.get(f"{BASE}/festival-calendar-dates")
        assert r.status_code == 200, r.text
        rows = r.json()
        years = [x["calendar_year"] for x in rows]
        assert years == sorted(years, reverse=True)       # newest year first
        if rows:
            code, year = rows[0]["festival_code"], rows[0]["calendar_year"]
            by_code = admin.get(f"{BASE}/festival-calendar-dates", params={"festival_code": code.lower()}).json()
            assert by_code and all(x["festival_code"] == code for x in by_code)
            by_year = admin.get(f"{BASE}/festival-calendar-dates", params={"calendar_year": year}).json()
            assert by_year and all(x["calendar_year"] == year for x in by_year)

    def test_calendar_dates_bad_year_returns_422(self, admin):
        assert admin.get(f"{BASE}/festival-calendar-dates", params={"calendar_year": "abc"}).status_code == 422

    def test_calendar_dates_unknown_festival_is_empty(self, admin):
        r = admin.get(f"{BASE}/festival-calendar-dates", params={"festival_code": "NO_SUCH"})
        assert r.status_code == 200 and r.json() == []


class TestFestivalCalendarWrites:

    @staticmethod
    @pytest.fixture(scope="class")
    def festival_code(calendar_manager):
        festivals = calendar_manager.get(f"{BASE}/festivals").json()
        if not festivals:
            pytest.skip("No festival_master rows seeded.")
        return festivals[0]["festival_code"]

    @staticmethod
    @pytest.fixture
    def year():
        # Far-future years the seed data never reaches; a module-level
        # counter hands out a distinct one per test (no random collisions).
        return next(_YEARS)

    def _create(self, client, code, year, **over):
        return client.post(
            f"{BASE}/festival-calendar-dates",
            json={"festival_code": code, "calendar_year": year,
                  "observed_date": f"{year}-03-14", **over},
        )

    def test_create_then_duplicate_year_returns_409(self, calendar_manager, festival_code, year):
        r = self._create(calendar_manager, festival_code.lower(), year,
                         source_reference=" almanac ", remarks="")
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["festival_code"] == festival_code
        assert data["is_confirmed"] is False             # provisional by default
        assert data["source_reference"] == "almanac"
        assert data["remarks"] is None
        again = self._create(calendar_manager, festival_code, year)
        assert again.status_code == 409, again.text

    def test_unknown_festival_returns_404(self, calendar_manager, year):
        assert self._create(calendar_manager, "NO_SUCH_FESTIVAL", year).status_code == 404

    def test_observed_date_outside_calendar_year_returns_422(self, calendar_manager, festival_code, year):
        r = self._create(calendar_manager, festival_code, year, observed_date=f"{year + 1}-01-01")
        assert r.status_code == 422, r.text

    @pytest.mark.parametrize("over", [{"calendar_year": 1800}, {"calendar_year": 2300},
                                      {"observed_date": "not-a-date"}])
    def test_invalid_body_returns_422(self, calendar_manager, festival_code, over):
        body = {"festival_code": festival_code, "calendar_year": 2150,
                "observed_date": "2150-03-14", **over}
        assert calendar_manager.post(f"{BASE}/festival-calendar-dates", json=body).status_code == 422

    def test_patch_confirms_and_corrects(self, calendar_manager, festival_code, year):
        pk = self._create(calendar_manager, festival_code, year).json()["festival_calendar_date_pk"]
        r = calendar_manager.patch(
            f"{BASE}/festival-calendar-dates/{pk}",
            json={"is_confirmed": True, "observed_date": f"{year}-03-15",
                  "source_reference": "Kendra circular"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_confirmed"] is True
        assert data["observed_date"] == f"{year}-03-15"
        assert data["calendar_year"] == year             # year never changes

    def test_patch_date_in_other_year_returns_422(self, calendar_manager, festival_code, year):
        pk = self._create(calendar_manager, festival_code, year).json()["festival_calendar_date_pk"]
        r = calendar_manager.patch(
            f"{BASE}/festival-calendar-dates/{pk}", json={"observed_date": f"{year + 1}-03-15"}
        )
        assert r.status_code == 422, r.text

    def test_patch_empty_body_returns_422(self, calendar_manager, festival_code, year):
        pk = self._create(calendar_manager, festival_code, year).json()["festival_calendar_date_pk"]
        assert calendar_manager.patch(f"{BASE}/festival-calendar-dates/{pk}", json={}).status_code == 422

    def test_patch_unknown_pk_returns_404(self, calendar_manager):
        r = calendar_manager.patch(f"{BASE}/festival-calendar-dates/{FAKE_UUID}", json={"is_confirmed": True})
        assert r.status_code == 404, r.text


# ═══════════════════════════════════════════════════════════════════════════
# POST-OFFICES / SAKHA-POSTAL-CODES READS
# ═══════════════════════════════════════════════════════════════════════════


class TestPostOfficeAndSakhaPostalReads:

    def test_post_offices_requires_postal_code_pk(self, admin):
        assert admin.get(f"{BASE}/post-offices").status_code == 422

    def test_post_offices_bad_uuid_returns_422(self, admin):
        assert admin.get(f"{BASE}/post-offices", params={"postal_code_pk": "x"}).status_code == 422

    def test_post_offices_unknown_pin_is_empty_list(self, admin):
        r = admin.get(f"{BASE}/post-offices", params={"postal_code_pk": FAKE_UUID})
        assert r.status_code == 200 and r.json() == []

    def test_post_offices_only_approved_rows(self, admin, write_conn):
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT postal_code_pk FROM nss.post_office "
                "WHERE entry_status = 'APPROVED' AND is_active = TRUE LIMIT 1"
            )
            row = cur.fetchone()
        if row is None:
            pytest.skip("No approved post offices seeded.")
        r = admin.get(f"{BASE}/post-offices", params={"postal_code_pk": str(row[0])})
        assert r.status_code == 200 and r.json()
        for po in r.json():
            assert po.get("entry_status", "APPROVED") == "APPROVED"

    def test_sakha_postal_codes_shape_and_filters(self, admin):
        r = admin.get(f"{BASE}/sakha-postal-codes")
        assert r.status_code == 200, r.text
        rows = r.json()
        for row in rows:
            for field in ("organization_pk", "organization_name", "organization_code",
                          "postal_code_pk", "postal_code", "state_pk", "state_name"):
                assert field in row
        if rows:
            pc = rows[0]["postal_code_pk"]
            filtered = admin.get(f"{BASE}/sakha-postal-codes", params={"postal_code_pk": pc}).json()
            assert filtered and all(x["postal_code_pk"] == pc for x in filtered)
            st = rows[0]["state_pk"]
            by_state = admin.get(f"{BASE}/sakha-postal-codes", params={"state_pk": st}).json()
            assert by_state and all(x["state_pk"] == st for x in by_state)

    def test_sakha_postal_codes_unknown_state_is_empty(self, admin):
        r = admin.get(f"{BASE}/sakha-postal-codes", params={"state_pk": FAKE_UUID})
        assert r.status_code == 200 and r.json() == []

    def test_sakha_postal_codes_bad_uuid_returns_422(self, admin):
        assert admin.get(f"{BASE}/sakha-postal-codes", params={"state_pk": "x"}).status_code == 422


# ═══════════════════════��══════���════════════════════════════════════════════
# MEMBER-ASSISTED GEOGRAPHIC ENTRY — PROPOSE (FND-BR-085 .. FND-BR-090)
# ═══════════════════════════════════════════════════════════════════════════


class TestProposeGeography:
    """
    Any active Sangha Sevi may propose; the row lands PENDING and is invisible
    to the lookup endpoints until an admin approves it (geo_approval.py,
    tested in tests/api/test_geo_approval.py).
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def member(make_roleless_member, sakha_pk):
        return make_roleless_member(sakha_pk)

    @staticmethod
    @pytest.fixture(scope="class")
    def state_pk(write_conn):
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT state_pk FROM nss.state WHERE is_active = TRUE LIMIT 1"
            )
            row = cur.fetchone()
        if row is None:
            pytest.skip("No state seeded.")
        return str(row[0])

    @staticmethod
    def _fresh_pin(write_conn):
        while True:
            pin = str(random.randint(100000, 999999))
            with write_conn.cursor() as cur:
                cur.execute("SELECT 1 FROM nss.postal_code WHERE postal_code = %s", (pin,))
                if cur.fetchone() is None:
                    return pin

    # -- districts ---------------------------------------------------------

    def test_propose_district_lands_pending_with_provisional_code(self, member, state_pk):
        name = f"Matrix Dist {_tag(5)}"
        r = member["client"].post(f"{BASE}/districts/propose", json={"state_pk": state_pk, "district_name": f"  {name}  "})
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["entry_status"] == "PENDING"
        assert data["district_name"] == name
        assert data["district_code"] == "".join(c for c in name if c.isalnum()).upper()[:20]
        assert data["submitted_by_sangha_sevi_pk"]
        assert data["state_pk"] == state_pk

    def test_propose_district_duplicate_returns_existing_row(self, member, state_pk):
        name = f"Matrix Dup {_tag(5)}"
        first = member["client"].post(f"{BASE}/districts/propose", json={"state_pk": state_pk, "district_name": name}).json()
        again = member["client"].post(f"{BASE}/districts/propose", json={"state_pk": state_pk, "district_name": name.upper()}).json()
        assert again["district_pk"] == first["district_pk"]

    def test_pending_district_is_hidden_from_lookups(self, member, admin, state_pk):
        name = f"Matrix Hidden {_tag(5)}"
        pk = member["client"].post(f"{BASE}/districts/propose", json={"state_pk": state_pk, "district_name": name}).json()["district_pk"]
        listed = admin.get(f"{BASE}/districts", params={"state_pk": state_pk}).json()
        assert pk not in [d["district_pk"] for d in listed]
        assert admin.get(f"{BASE}/districts/{pk}").status_code == 404

    @pytest.mark.parametrize("body", [{}, {"district_name": "x"}, {"state_pk": "bad", "district_name": "x"}])
    def test_propose_district_invalid_body_returns_422(self, member, body):
        assert member["client"].post(f"{BASE}/districts/propose", json=body).status_code == 422

    def test_propose_district_blank_name_returns_422(self, member, state_pk):
        r = member["client"].post(f"{BASE}/districts/propose", json={"state_pk": state_pk, "district_name": ""})
        assert r.status_code == 422, r.text

    # -- postal codes ------------------------------------------------------

    @pytest.mark.parametrize("pin", ["12345", "1234567", "12345a", "abcdef", "12 456"])
    def test_propose_postal_code_must_be_six_digits(self, member, state_pk, pin):
        r = member["client"].post(f"{BASE}/postal-codes/propose", json={"state_pk": state_pk, "postal_code": pin})
        assert r.status_code == 422, r.text

    def test_propose_postal_code_pending_and_deduplicated(self, member, admin, state_pk, write_conn):
        pin = self._fresh_pin(write_conn)
        first = member["client"].post(f"{BASE}/postal-codes/propose", json={"state_pk": state_pk, "postal_code": pin})
        assert first.status_code == 201, first.text
        assert first.json()["entry_status"] == "PENDING"
        again = member["client"].post(f"{BASE}/postal-codes/propose", json={"state_pk": state_pk, "postal_code": pin})
        assert again.json()["postal_code_pk"] == first.json()["postal_code_pk"]
        hidden = admin.get(f"{BASE}/postal-codes", params={"q": pin}).json()
        assert pin not in [p["postal_code"] for p in hidden]

    # -- post offices ------------------------------------------------------

    def test_propose_post_office_unknown_pin_returns_404(self, member):
        r = member["client"].post(f"{BASE}/post-offices/propose", json={"postal_code_pk": FAKE_UUID, "post_office_name": "Nowhere SO"})
        assert r.status_code == 404, r.text

    def test_propose_post_office_pending_and_deduplicated(self, member, state_pk, write_conn):
        pin = member["client"].post(
            f"{BASE}/postal-codes/propose",
            json={"state_pk": state_pk, "postal_code": self._fresh_pin(write_conn)},
        ).json()["postal_code_pk"]
        name = f"Matrix PO {_tag(5)}"
        first = member["client"].post(f"{BASE}/post-offices/propose", json={"postal_code_pk": pin, "post_office_name": name})
        assert first.status_code == 201, first.text
        assert first.json()["entry_status"] == "PENDING"
        again = member["client"].post(f"{BASE}/post-offices/propose", json={"postal_code_pk": pin, "post_office_name": name.lower()})
        assert again.json()["post_office_pk"] == first.json()["post_office_pk"]

    # -- referenced rows must exist / canonical PIN is a conflict ---------

    def test_propose_district_unknown_state_returns_404(self, member):
        r = member["client"].post(f"{BASE}/districts/propose", json={"state_pk": FAKE_UUID, "district_name": f"Ghost {_tag(5)}"})
        assert r.status_code == 404, r.text

    def test_propose_postal_code_unknown_state_returns_404(self, member, write_conn):
        r = member["client"].post(f"{BASE}/postal-codes/propose", json={"state_pk": FAKE_UUID, "postal_code": self._fresh_pin(write_conn)})
        assert r.status_code == 404, r.text

    def test_propose_postal_code_already_approved_returns_409(self, member, state_pk, write_conn):
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT postal_code FROM nss.postal_code "
                "WHERE entry_status = 'APPROVED' AND is_active = TRUE LIMIT 1"
            )
            row = cur.fetchone()
        if row is None:
            pytest.skip("No approved postal code seeded.")
        r = member["client"].post(f"{BASE}/postal-codes/propose", json={"state_pk": state_pk, "postal_code": row[0]})
        assert r.status_code == 409, r.text

    def test_propose_city_village_unknown_district_returns_404(self, member):
        r = member["client"].post(
            f"{BASE}/city-villages/propose",
            json={"district_pk": FAKE_UUID, "city_village_name": f"Ghost {_tag(5)}", "city_village_type": "VILLAGE"},
        )
        assert r.status_code == 404, r.text

    def test_propose_city_village_unknown_postal_code_returns_404(self, member):
        r = member["client"].post(
            f"{BASE}/city-villages/propose",
            json={"postal_code_pk": FAKE_UUID, "city_village_name": f"Ghost {_tag(5)}", "city_village_type": "VILLAGE"},
        )
        assert r.status_code == 404, r.text

    # -- city / village ----------------------------------------------------

    def test_propose_city_village_needs_an_anchor(self, member):
        r = member["client"].post(f"{BASE}/city-villages/propose", json={"city_village_name": "Nowhere", "city_village_type": "VILLAGE"})
        assert r.status_code == 422, r.text

    def test_propose_city_village_rejects_unknown_type(self, member):
        # The type check runs before any DB access, so a dummy anchor is fine.
        r = member["client"].post(
            f"{BASE}/city-villages/propose",
            json={"district_pk": FAKE_UUID, "city_village_name": "Nowhere",
                  "city_village_type": "HAMLET"},
        )
        assert r.status_code == 422, r.text

    def test_propose_city_village_normalises_type_and_deduplicates(self, member, state_pk, write_conn):
        pin = member["client"].post(
            f"{BASE}/postal-codes/propose",
            json={"state_pk": state_pk, "postal_code": self._fresh_pin(write_conn)},
        ).json()["postal_code_pk"]
        name = f"Matrix Vill {_tag(5)}"
        body = {"postal_code_pk": pin, "city_village_name": name, "city_village_type": "village"}
        first = member["client"].post(f"{BASE}/city-villages/propose", json=body)
        assert first.status_code == 201, first.text
        data = first.json()
        assert data["entry_status"] == "PENDING"
        assert data["city_village_type"] == "VILLAGE"
        assert data["city_village_code"] == "".join(c for c in name if c.isalnum()).upper()[:20]
        again = member["client"].post(f"{BASE}/city-villages/propose", json={**body, "city_village_name": name.upper()})
        assert again.json()["city_village_pk"] == data["city_village_pk"]
