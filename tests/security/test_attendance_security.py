"""
NSS ERP — Security tests for the Attendance API (api/routers/attendance.py).

Focus: access control that the functional tests in tests/api/test_attendance.py
don't already exercise —
  - every endpoint rejects anonymous callers (401);
  - every endpoint rejects an authenticated user holding no ATTENDANCE_*
    permission (403) — a plain member has no role at all;
  - ATTENDANCE_VIEW alone (an auditor-style reader) cannot mark/create/correct;
  - admin-scope negatives with the exact router messages, for a Sakha admin
    scoped to a DIFFERENT Sakha;
  - review authority is a live Governing Body seat (ATT-042), not a permission:
    the marker role and an unseated Sakha admin are refused, and a President of
    another Sakha is refused here.

Exact messages are asserted verbatim against api/routers/attendance.py.
"""

import pytest

from tests.attendance_support import (  # noqa: F401  (fixtures)
    BASE, FAKE_UUID, PUJA_DATES, _create_admin_with_scope, _login_headers, _with_sevi_pk,
    admin_h, admin_user, make_puja, mark, marker_h, marker_user, new_member,
    other_admin, other_admin_h, other_org_pk, other_president, other_president_h,
    plain_member, plain_member_h, president_h, president_user, register_org_pk,
    register_pujas, sakha_admin, sakha_admin_h, sakha_pks, secretary_h, secretary_user,
)

pytestmark = pytest.mark.integration

PUJA = f"{BASE}/pujas/{FAKE_UUID}/attendance"

# (method, path, json body) — one row per route; ids are FAKE_UUID so a request
# that got past authentication could only ever 404/422, never succeed.
_BODY = {"remarks": "r"}
ENDPOINTS = [
    ("POST", f"{BASE}/pujas", {"sakha_pk": FAKE_UUID, "puja_date": "2001-01-07"}),
    ("GET", f"{BASE}/pujas", None),
    ("POST", PUJA, {"records": []}),
    ("PATCH", f"{BASE}/records/{FAKE_UUID}", {"attendance_status_code": "PRESENT"}),
    ("GET", f"{BASE}/records", None),
    ("POST", f"{BASE}/exceptions",
     {"sangha_sevi_pk": FAKE_UUID, "exception_type_code": "MEDICAL", "from_date": "2001-01-01"}),
    ("GET", f"{BASE}/exceptions", None),
    ("GET", f"{BASE}/reviews", None),
    ("GET", f"{BASE}/reviews/{FAKE_UUID}", None),
    ("POST", f"{BASE}/reviews/{FAKE_UUID}/close", _BODY),
    ("POST", f"{BASE}/reviews/{FAKE_UUID}/defer", _BODY),
    ("POST", f"{BASE}/reviews/{FAKE_UUID}/revisit", _BODY),
    ("POST", f"{BASE}/reviews/{FAKE_UUID}/escalate-to-president", _BODY),
    ("POST", f"{BASE}/reviews/{FAKE_UUID}/escalate-to-parichalak", _BODY),
    ("POST", f"{BASE}/reviews/{FAKE_UUID}/reopen", _BODY),
    ("POST", f"{BASE}/reviews/{FAKE_UUID}/override", {"new_status_code": "OPEN", "reason": "r"}),
    ("GET", f"{BASE}/watch-list", None),
    ("GET", f"{BASE}/stats/organizations/{FAKE_UUID}", None),
    ("GET", f"{BASE}/stats/organizations/{FAKE_UUID}/members", None),
    ("GET", f"{BASE}/stats/members/{FAKE_UUID}", None),
]
IDS = [f"{m} {p.removeprefix(BASE)}" for m, p, _ in ENDPOINTS]


def _call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


def test_endpoint_table_covers_every_route():
    """Guard: a new attendance route must be added to ENDPOINTS above."""
    import re

    from api.routers.attendance import router

    routes = {(m, re.sub(r"\{[^}]+\}", FAKE_UUID, r.path)) for r in router.routes for m in r.methods if m != "HEAD"}
    assert routes == {(m, p) for m, p, _ in ENDPOINTS}


class TestAuthentication:

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_anonymous_is_401(self, method, path, body, anon_client):
        assert _call(anon_client, method, path, body).status_code == 401

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_garbage_token_is_401(self, method, path, body, anon_client):
        r = _call(anon_client, method, path, body, {"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401


class TestPermissionGate:

    @pytest.mark.parametrize("method,path,body", ENDPOINTS, ids=IDS)
    def test_member_without_attendance_permission_is_403(self, method, path, body, client, plain_member_h):
        assert _call(client, method, path, body, plain_member_h).status_code == 403

    def test_view_only_role_cannot_write(self, client, write_conn, register_org_pk, register_pujas):
        """An ATTENDANCE_VIEW-only role (NSS_ERP_AUDITOR) reads but never marks/creates/corrects."""
        auditor = _with_sevi_pk(write_conn, _create_admin_with_scope(
            write_conn, role_code="NSS_ERP_AUDITOR", scope_level="SAKHA", organization_pk=register_org_pk))
        h = _login_headers(client, auditor["sangha_sevi_id"], auditor["password"])

        assert client.get(f"{BASE}/pujas", headers=h).status_code == 200
        assert client.get(f"{BASE}/watch-list", headers=h).status_code == 200

        pk = register_pujas[0]["weekly_sangha_puja_pk"]
        assert client.post(f"{BASE}/pujas", json={"sakha_pk": register_org_pk, "puja_date": "2001-06-03"},
                           headers=h).status_code == 403
        assert client.post(f"{BASE}/pujas/{pk}/attendance", json={"records": []}, headers=h).status_code == 403
        assert client.patch(f"{BASE}/records/{FAKE_UUID}", json={"attendance_status_code": "PRESENT"},
                            headers=h).status_code == 403


class TestAdminScope:
    """other_admin is a SAKHA_ADMIN scoped to a different Sakha than the data below."""

    def test_cannot_create_puja_for_foreign_sakha(self, client, other_admin_h, register_org_pk):
        r = client.post(f"{BASE}/pujas", json={"sakha_pk": register_org_pk, "puja_date": "2001-07-01"},
                        headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only create a Weekly Sangha Puja event within your admin scope."

    def test_cannot_mark_foreign_puja(self, client, write_conn, other_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "SecMark")
        r = client.post(
            f"{BASE}/pujas/{register_pujas[0]['weekly_sangha_puja_pk']}/attendance",
            json={"records": [{"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT"}]},
            headers=other_admin_h,
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only mark attendance for this Sakha within your admin scope."

    def test_cannot_correct_foreign_record(self, client, write_conn, sakha_admin_h, other_admin_h,
                                           register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "SecCorr")
        rec = mark(client, sakha_admin_h, register_pujas[0]["weekly_sangha_puja_pk"],
                   (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        r = client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                         json={"attendance_status_code": "ABSENT"}, headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only correct attendance for this Sakha within your admin scope."

    def test_cannot_list_foreign_sakha_filters(self, client, other_admin_h, register_org_pk):
        expected = {
            "pujas": "view this Sakha's puja events",
            "records": "view this Sakha's attendance",
            "reviews": "view this Sakha's reviews",
            "watch-list": "view this Sakha's watch list",
        }
        for path, action in expected.items():
            r = client.get(f"{BASE}/{path}", params={"organization_pk": register_org_pk}, headers=other_admin_h)
            assert r.status_code == 403, path
            assert r.json()["detail"] == f"You can only {action} within your admin scope.", path

    def test_cannot_read_foreign_member_data(self, client, write_conn, other_admin_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "SecRead")
        pk = m["sangha_sevi_pk"]
        for path, action in [
            (f"records?sangha_sevi_pk={pk}", "view this member's attendance"),
            (f"exceptions?sangha_sevi_pk={pk}", "view this member's exceptions"),
            (f"stats/members/{pk}", "view this member's attendance statistics"),
        ]:
            r = client.get(f"{BASE}/{path}", headers=other_admin_h)
            assert r.status_code == 403, path
            assert r.json()["detail"] == f"You can only {action} within your admin scope.", path

    def test_cannot_read_foreign_sakha_stats(self, client, other_admin_h, register_org_pk):
        r = client.get(f"{BASE}/stats/organizations/{register_org_pk}", headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only view this Sakha's attendance statistics within your admin scope."
        r = client.get(f"{BASE}/stats/organizations/{register_org_pk}/members", headers=other_admin_h)
        assert r.status_code == 403
        assert r.json()["detail"] == "You can only view this Sakha's member attendance within your admin scope."

    def test_unfiltered_lists_do_not_leak_foreign_rows(self, client, write_conn, sakha_admin_h, other_admin_h,
                                                       register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "SecLeak")
        rec = mark(client, sakha_admin_h, register_pujas[0]["weekly_sangha_puja_pk"],
                   (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        seen = client.get(f"{BASE}/records", params={"page_size": 200}, headers=other_admin_h).json()["records"]
        assert rec["attendance_pk"] not in {r["attendance_pk"] for r in seen}
        assert register_pujas[0]["weekly_sangha_puja_pk"] not in {
            p["weekly_sangha_puja_pk"]
            for p in client.get(f"{BASE}/pujas", params={"page_size": 200}, headers=other_admin_h).json()["pujas"]
        }


class TestReviewAuthorityIsASeatNotAPermission:
    """ATTENDANCE_VIEW/MANAGE alone must never grant review or exception approval (ATT-042)."""

    @pytest.fixture(scope="class")
    def review_pk(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "SecRev")
        for p in register_pujas[:3]:
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "ABSENT"))
        reviews = client.get(f"{BASE}/reviews", params={"page_size": 200, "review_status": "OPEN"},
                             headers=sakha_admin_h).json()["reviews"]
        return next(r["review_pk"] for r in reviews if r["sangha_sevi_pk"] == m["sangha_sevi_pk"])

    @pytest.mark.parametrize("who", ["sakha_admin_h", "marker_h"])
    @pytest.mark.parametrize("action", ["close", "defer", "escalate-to-president"])
    def test_unseated_manager_cannot_act(self, who, action, request, client, review_pk):
        r = client.post(f"{BASE}/reviews/{review_pk}/{action}", json={}, headers=request.getfixturevalue(who))
        assert r.status_code == 403
        assert r.json()["detail"].startswith("Only the Sakha's Secretary or President may ")

    @pytest.mark.parametrize("who", ["sakha_admin_h", "marker_h", "secretary_h"])
    def test_president_only_actions_refuse_everyone_else(self, who, request, client, review_pk):
        h = request.getfixturevalue(who)
        r = client.post(f"{BASE}/reviews/{review_pk}/override",
                        json={"new_status_code": "CLOSED", "reason": "x"}, headers=h)
        assert r.status_code == 403
        assert r.json()["detail"] == "Only the Sakha's President may override this review."

    def test_unseated_admin_cannot_approve_exception(self, client, write_conn, sakha_admin_h, marker_h,
                                                     register_org_pk):
        m = new_member(write_conn, register_org_pk, "SecExc")
        body = {"sangha_sevi_pk": m["sangha_sevi_pk"], "exception_type_code": "MEDICAL", "from_date": "2001-01-01"}
        for h in (sakha_admin_h, marker_h):
            assert client.post(f"{BASE}/exceptions", json=body, headers=h).status_code == 403

    def test_foreign_president_cannot_act_on_this_sakhas_review(self, client, other_president_h, review_pk):
        for action in ("close", "defer", "escalate-to-president"):
            r = client.post(f"{BASE}/reviews/{review_pk}/{action}", json={}, headers=other_president_h)
            assert r.status_code == 403, action
        assert client.get(f"{BASE}/reviews/{review_pk}", headers=other_president_h).status_code == 403

    def test_review_was_not_modified_by_any_denied_call(self, client, sakha_admin_h, review_pk):
        r = client.get(f"{BASE}/reviews/{review_pk}", headers=sakha_admin_h)
        assert r.json()["review_status_code"] == "OPEN"
        assert r.json()["closed_by_sangha_sevi_pk"] is None
