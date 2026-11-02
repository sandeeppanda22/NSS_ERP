"""
NSS ERP — Tier 6 Attendance API tests.

Integration tests for every endpoint of api/routers/attendance.py:

  1. Pujas        — POST/GET /pujas
  2. Marking      — POST /pujas/{pk}/attendance (bulk upsert), PATCH /records/{pk}
  3. Records      — GET /records
  4. Exceptions   — POST/GET /exceptions          (Secretary/President seat, ATT-042)
  5. Reviews      — 3-consecutive-ABSENT trigger + GET/POST /reviews/* workflow
  6. Watch list   — GET /watch-list
  7. Stats        — /stats/organizations/{pk}, .../members, /stats/members/{pk}

Authorization negatives (anonymous, no-permission, cross-scope) live in
tests/security/test_attendance_security.py. Shared identities and builders:
tests/attendance_support.py.

Runs against local PostgreSQL bootstrapped through Phase 11e
(database/ddl/10_attendance/*) with the ATTENDANCE_* master data and RBAC seeds.
"""

from datetime import date, timedelta

import pytest

from api.helpers import MAX_LIMIT
from tests.attendance_support import (  # noqa: F401  (fixtures)
    BASE, FAKE_UUID, PUJA_DATES, WINDOW, _login_headers, plain_member, plain_member_h,
    admin_h, admin_user, make_puja, mark, marker_h, marker_user, new_member,
    other_admin, other_admin_h, other_org_pk, other_president, other_president_h,
    president_h, president_user, register_org_pk, register_pujas,
    sakha_admin, sakha_admin_h, sakha_pks, secretary_h, secretary_user,
)

pytestmark = pytest.mark.integration


def _status_by_member(marked: dict) -> dict:
    return {r["sangha_sevi_pk"]: r["attendance_status_code"] for r in marked["records"]}


def _list_reviews(client, headers, **params) -> list:
    """page_size=200 so a dev DB with many real reviews can't push ours off page 1."""
    r = client.get(f"{BASE}/reviews", params={"page_size": 200, **params}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["reviews"]


def _open_review(client, headers, pujas, member) -> str:
    """Drive a fresh member to 3 consecutive ABSENTs and return the opened review's pk."""
    for p in pujas[:3]:
        mark(client, headers, p["weekly_sangha_puja_pk"], (member["sangha_sevi_pk"], "ABSENT"))
    mine = [x for x in _list_reviews(client, headers, review_status="OPEN")
            if x["sangha_sevi_pk"] == member["sangha_sevi_pk"]]
    assert len(mine) == 1, "expected exactly one OPEN review for the member"
    return mine[0]["review_pk"]


# ═══════════════════════════════════════════════════════════════════════
# 1. Weekly Sangha Puja
# ═══════════════════════════════════════════════════════════════════════

class TestPujas:

    def test_create_past_puja_is_conducted(self, register_pujas):
        p = register_pujas[0]
        assert p["puja_status"] == "CONDUCTED"
        assert p["puja_date"] == PUJA_DATES[0].isoformat()
        assert (p["marked_count"], p["present_count"], p["absent_count"], p["excused_count"]) == (0, 0, 0, 0)

    def test_create_future_puja_is_scheduled(self, client, sakha_admin_h, register_org_pk):
        p = make_puja(client, sakha_admin_h, register_org_pk, date.today() + timedelta(days=400), "future")
        assert p["puja_status"] == "SCHEDULED"
        assert p["remarks"] == "future"

    def test_duplicate_puja_is_409(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        # The unique violation aborts the shared test transaction, so isolate it
        # in its own SAVEPOINT (the app's per-request rollback doesn't run here).
        cur = write_conn.cursor()
        cur.execute("SAVEPOINT dup_puja")
        r = client.post(
            f"{BASE}/pujas",
            json={"sakha_pk": register_org_pk, "puja_date": PUJA_DATES[0].isoformat()},
            headers=sakha_admin_h,
        )
        cur.execute("ROLLBACK TO SAVEPOINT dup_puja")
        assert r.status_code == 409, r.text
        assert "already exists" in r.json()["detail"]

    def test_unknown_sakha_is_404_for_global_admin(self, client, admin_h):
        r = client.post(f"{BASE}/pujas", json={"sakha_pk": FAKE_UUID, "puja_date": "2001-01-07"}, headers=admin_h)
        assert r.status_code == 404, r.text

    def test_list_filters_by_org_and_dates(self, client, sakha_admin_h, register_org_pk, register_pujas):
        r = client.get(
            f"{BASE}/pujas",
            params={"organization_pk": register_org_pk, **WINDOW},
            headers=sakha_admin_h,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 5
        dates = [p["puja_date"] for p in body["pujas"]]
        assert dates == sorted(dates, reverse=True), "newest puja first"
        assert {p["sakha_pk"] for p in body["pujas"]} == {register_org_pk}

    def test_list_to_date_excludes_later_pujas(self, client, sakha_admin_h, register_org_pk, register_pujas):
        r = client.get(
            f"{BASE}/pujas",
            params={"organization_pk": register_org_pk, "from_date": "2001-01-01", "to_date": PUJA_DATES[1].isoformat()},
            headers=sakha_admin_h,
        )
        assert r.json()["total"] == 2

    def test_list_pagination(self, client, sakha_admin_h, register_org_pk, register_pujas):
        r = client.get(
            f"{BASE}/pujas",
            params={"organization_pk": register_org_pk, **WINDOW, "page": 2, "page_size": 2},
            headers=sakha_admin_h,
        )
        body = r.json()
        assert body["total"] == 5 and len(body["pujas"]) == 2

    def test_scoped_admin_list_never_leaks_other_sakha(
        self, client, admin_h, sakha_admin_h, register_org_pk, other_org_pk,
    ):
        other = make_puja(client, admin_h, other_org_pk, PUJA_DATES[0])
        r = client.get(f"{BASE}/pujas", params=WINDOW, headers=sakha_admin_h)
        assert r.status_code == 200
        assert other["weekly_sangha_puja_pk"] not in {p["weekly_sangha_puja_pk"] for p in r.json()["pujas"]}


# ═══════════════════════════════════════════════════════════════════════
# 2. Marking and correction
# ═══════════════════════════════════════════════════════════════════════

class TestMarking:

    def test_bulk_mark_all_three_statuses(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        a, b, c = (new_member(write_conn, register_org_pk, n) for n in ("MkA", "MkB", "MkC"))
        out = mark(
            client, sakha_admin_h, register_pujas[0]["weekly_sangha_puja_pk"],
            (a["sangha_sevi_pk"], "PRESENT", "on time"),
            (b["sangha_sevi_pk"], "ABSENT"),
            (c["sangha_sevi_pk"], "EXCUSED_ABSENCE"),
        )
        assert out["total"] == 3
        assert _status_by_member(out) == {
            a["sangha_sevi_pk"]: "PRESENT", b["sangha_sevi_pk"]: "ABSENT",
            c["sangha_sevi_pk"]: "EXCUSED_ABSENCE",
        }
        rec_a = next(r for r in out["records"] if r["sangha_sevi_pk"] == a["sangha_sevi_pk"])
        assert rec_a["remarks"] == "on time"
        assert rec_a["is_darshak"] is False
        assert rec_a["home_organization_pk"] == register_org_pk
        assert rec_a["attendance_sakha_pk"] == register_org_pk

        # The puja listing's per-status counters follow the marks.
        listed = client.get(
            f"{BASE}/pujas",
            params={"organization_pk": register_org_pk, "from_date": PUJA_DATES[0].isoformat(),
                    "to_date": PUJA_DATES[0].isoformat()},
            headers=sakha_admin_h,
        ).json()["pujas"][0]
        assert (listed["marked_count"], listed["present_count"], listed["absent_count"],
                listed["excused_count"]) == (3, 1, 1, 1)

    def test_remarking_upserts_not_duplicates(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "Upsert")
        pk = register_pujas[1]["weekly_sangha_puja_pk"]
        first = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "ABSENT"))["records"][0]
        second = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        assert second["attendance_pk"] == first["attendance_pk"]
        assert second["attendance_status_code"] == "PRESENT"
        listed = client.get(f"{BASE}/records", params={"sangha_sevi_pk": m["sangha_sevi_pk"]}, headers=sakha_admin_h)
        assert listed.json()["total"] == 1

    def test_unknown_status_is_422(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "BadStatus")
        r = client.post(
            f"{BASE}/pujas/{register_pujas[0]['weekly_sangha_puja_pk']}/attendance",
            json={"records": [{"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "LATE"}]},
            headers=sakha_admin_h,
        )
        assert r.status_code == 422, r.text
        assert "Unknown attendance status" in r.json()["detail"]

    def test_unknown_member_is_404(self, client, sakha_admin_h, register_pujas):
        r = client.post(
            f"{BASE}/pujas/{register_pujas[0]['weekly_sangha_puja_pk']}/attendance",
            json={"records": [{"sangha_sevi_pk": FAKE_UUID, "attendance_status_code": "PRESENT"}]},
            headers=sakha_admin_h,
        )
        assert r.status_code == 404, r.text

    def test_unknown_puja_is_404(self, client, write_conn, sakha_admin_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "NoPuja")
        r = client.post(
            f"{BASE}/pujas/{FAKE_UUID}/attendance",
            json={"records": [{"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT"}]},
            headers=sakha_admin_h,
        )
        assert r.status_code == 404, r.text

    def test_attendance_marker_role_can_mark(self, client, write_conn, marker_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "ByMarker")
        out = mark(client, marker_h, register_pujas[2]["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "PRESENT"))
        assert out["total"] == 1

    def test_cross_sakha_attendee_is_darshak(
        self, client, write_conn, sakha_admin_h, register_org_pk, other_org_pk, register_pujas,
    ):
        visitor = new_member(write_conn, other_org_pk, "Visitor")
        rec = mark(
            client, sakha_admin_h, register_pujas[2]["weekly_sangha_puja_pk"],
            (visitor["sangha_sevi_pk"], "PRESENT"),
        )["records"][0]
        assert rec["is_darshak"] is True
        assert rec["home_organization_pk"] == other_org_pk
        assert rec["sakha_pk"] == register_org_pk
        assert rec["has_approved_darshak_registration"] is False


class TestCorrection:

    def _marked(self, client, write_conn, headers, org, puja, status):
        m = new_member(write_conn, org, "Corr")
        rec = mark(client, headers, puja["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], status))["records"][0]
        return m, rec

    def test_present_absent_correction_needs_only_manage(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        _, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[3], "ABSENT")
        r = client.patch(
            f"{BASE}/records/{rec['attendance_pk']}",
            json={"attendance_status_code": "PRESENT", "remarks": "was late"}, headers=sakha_admin_h,
        )
        assert r.status_code == 200, r.text
        assert r.json()["attendance_status_code"] == "PRESENT"
        assert r.json()["remarks"] == "was late"

    def test_correction_without_remarks_keeps_existing_remarks(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "KeepRemark")
        rec = mark(client, sakha_admin_h, register_pujas[3]["weekly_sangha_puja_pk"],
                   (m["sangha_sevi_pk"], "ABSENT", "kept"))["records"][0]
        r = client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                         json={"attendance_status_code": "PRESENT"}, headers=sakha_admin_h)
        assert r.json()["remarks"] == "kept"

    def test_excused_correction_by_unseated_admin_is_403(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        _, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[3], "ABSENT")
        r = client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                         json={"attendance_status_code": "EXCUSED_ABSENCE"}, headers=sakha_admin_h)
        assert r.status_code == 403, r.text
        detail = r.json()["detail"]
        assert detail.startswith("Only the Sakha's Secretary or President may ")
        assert detail.endswith("an Excused Absence.")

    @pytest.mark.parametrize("who", ["secretary_h", "president_h", "admin_h"])
    def test_excused_correction_by_seated_officer_or_global_admin(
        self, who, request, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        headers = request.getfixturevalue(who)
        _, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[3], "ABSENT")
        r = client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                         json={"attendance_status_code": "EXCUSED_ABSENCE"}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["attendance_status_code"] == "EXCUSED_ABSENCE"

    def test_other_sakhas_president_cannot_excuse_here(
        self, client, write_conn, sakha_admin_h, other_president_h, register_org_pk, register_pujas,
    ):
        _, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[3], "ABSENT")
        r = client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                         json={"attendance_status_code": "EXCUSED_ABSENCE"}, headers=other_president_h)
        assert r.status_code == 403, r.text
        assert "within your admin scope" in r.json()["detail"]

    def test_unknown_record_is_404(self, client, sakha_admin_h):
        r = client.patch(f"{BASE}/records/{FAKE_UUID}",
                         json={"attendance_status_code": "PRESENT"}, headers=sakha_admin_h)
        assert r.status_code == 404, r.text

    def test_correcting_to_absent_runs_review_detection(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "CorrectTrigger")
        recs = [
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
            for p in register_pujas[:3]
        ]
        for rec in recs:
            r = client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                             json={"attendance_status_code": "ABSENT"}, headers=sakha_admin_h)
            assert r.status_code == 200, r.text
        reviews = _list_reviews(client, sakha_admin_h, review_status="OPEN")
        assert [x["sangha_sevi_pk"] for x in reviews].count(m["sangha_sevi_pk"]) == 1


# ═══════════════════════════════════════════════════════════════════════
# 3. Records
# ═══════════════════════════════════════════════════════════════════════

class TestRecords:

    def test_list_by_member_newest_first(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "Hist")
        for p in register_pujas[:3]:
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "PRESENT"))
        r = client.get(f"{BASE}/records", params={"sangha_sevi_pk": m["sangha_sevi_pk"]}, headers=sakha_admin_h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 3
        dates = [x["puja_date"] for x in body["records"]]
        assert dates == sorted(dates, reverse=True)

    def test_list_pagination(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "Page")
        for p in register_pujas[:3]:
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "PRESENT"))
        r = client.get(f"{BASE}/records",
                       params={"sangha_sevi_pk": m["sangha_sevi_pk"], "page": 2, "page_size": 2}, headers=sakha_admin_h)
        assert r.json()["total"] == 3 and len(r.json()["records"]) == 1

    def test_list_by_organization_filters_attendance_sakha(
        self, client, sakha_admin_h, register_org_pk, register_pujas,
    ):
        r = client.get(f"{BASE}/records", params={"organization_pk": register_org_pk}, headers=sakha_admin_h)
        assert r.status_code == 200
        assert r.json()["records"], "marks from earlier tests should be present"
        assert {x["attendance_sakha_pk"] for x in r.json()["records"]} == {register_org_pk}

    def test_unknown_member_is_404(self, client, admin_h):
        r = client.get(f"{BASE}/records", params={"sangha_sevi_pk": FAKE_UUID}, headers=admin_h)
        assert r.status_code == 404, r.text


# ═══════════════════════════════════════════════════════════════════════
# 4. Exceptions
# ═══════════════════════════════════════════════════════════════════════

class TestExceptions:

    def _body(self, member, **kw):
        return {"sangha_sevi_pk": member["sangha_sevi_pk"], "exception_type_code": "MEDICAL",
                "from_date": "2001-03-01", "to_date": "2001-03-31", "remarks": "surgery", **kw}

    @pytest.mark.parametrize("who", ["secretary_h", "president_h", "admin_h"])
    def test_seated_officer_or_global_admin_creates(self, who, request, client, write_conn, register_org_pk):
        headers = request.getfixturevalue(who)
        m = new_member(write_conn, register_org_pk, "ExcOk")
        r = client.post(f"{BASE}/exceptions", json=self._body(m), headers=headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["exception_type_code"] == "MEDICAL"
        assert body["sangha_sevi_pk"] == m["sangha_sevi_pk"]
        assert body["from_date"] == "2001-03-01" and body["to_date"] == "2001-03-31"
        assert body["approved_date"] == date.today().isoformat()
        assert body["approved_by_name"]

    def test_open_ended_exception(self, client, write_conn, secretary_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "ExcOpen")
        r = client.post(f"{BASE}/exceptions", json=self._body(m, to_date=None), headers=secretary_h)
        assert r.status_code == 201, r.text
        assert r.json()["to_date"] is None

    def test_unseated_admin_is_403(self, client, write_conn, sakha_admin_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "ExcNo")
        r = client.post(f"{BASE}/exceptions", json=self._body(m), headers=sakha_admin_h)
        assert r.status_code == 403, r.text
        assert r.json()["detail"] == "Only the Sakha's Secretary or President may approve an attendance exception."

    def test_other_sakhas_president_is_403(self, client, write_conn, other_president_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "ExcOther")
        r = client.post(f"{BASE}/exceptions", json=self._body(m), headers=other_president_h)
        assert r.status_code == 403, r.text

    def test_unknown_member_is_404(self, client, secretary_h):
        r = client.post(f"{BASE}/exceptions",
                        json={"sangha_sevi_pk": FAKE_UUID, "exception_type_code": "MEDICAL", "from_date": "2001-03-01"},
                        headers=secretary_h)
        assert r.status_code == 404, r.text

    def test_list_by_member_and_scope(self, client, write_conn, secretary_h, sakha_admin_h, other_admin_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "ExcList")
        created = client.post(f"{BASE}/exceptions", json=self._body(m), headers=secretary_h).json()

        r = client.get(f"{BASE}/exceptions", params={"sangha_sevi_pk": m["sangha_sevi_pk"]}, headers=sakha_admin_h)
        assert r.status_code == 200, r.text
        assert [e["exception_pk"] for e in r.json()["exceptions"]] == [created["exception_pk"]]

        # Unfiltered list: in-scope admin sees it, the other Sakha's admin does not.
        mine = client.get(f"{BASE}/exceptions", headers=sakha_admin_h).json()["exceptions"]
        theirs = client.get(f"{BASE}/exceptions", headers=other_admin_h).json()["exceptions"]
        assert created["exception_pk"] in {e["exception_pk"] for e in mine}
        assert created["exception_pk"] not in {e["exception_pk"] for e in theirs}


# ═══════════════════════════════════════════════════════════════════════
# 5. Review trigger (ATT-009/010/014) and watch list
# ═══════════════════════════════════════════════════════════════════════

class TestReviewTrigger:

    def test_three_consecutive_absences_open_one_review(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "Trig")
        pk = lambda i: register_pujas[i]["weekly_sangha_puja_pk"]  # noqa: E731
        mark(client, sakha_admin_h, pk(0), (m["sangha_sevi_pk"], "ABSENT"))
        mark(client, sakha_admin_h, pk(1), (m["sangha_sevi_pk"], "ABSENT"))
        reviews = lambda: [  # noqa: E731
            x for x in _list_reviews(client, sakha_admin_h) if x["sangha_sevi_pk"] == m["sangha_sevi_pk"]
        ]
        assert reviews() == [], "two absences are only a watch-list entry"

        mark(client, sakha_admin_h, pk(2), (m["sangha_sevi_pk"], "ABSENT"))
        [review] = reviews()
        assert review["review_status_code"] == "OPEN"
        assert review["consecutive_absences"] == 3
        assert review["assigned_to_role"] == "SECRETARY"
        assert review["organization_pk"] == register_org_pk
        assert review["trigger_date"] == PUJA_DATES[2].isoformat()

        # A 4th absence while a review is already non-terminal must not open a second.
        mark(client, sakha_admin_h, pk(3), (m["sangha_sevi_pk"], "ABSENT"))
        assert len(reviews()) == 1

    def test_excused_absence_breaks_the_chain(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "Chain")
        for p, s in zip(register_pujas[:3], ("ABSENT", "EXCUSED_ABSENCE", "ABSENT")):
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], s))
        reviews = _list_reviews(client, sakha_admin_h)
        assert m["sangha_sevi_pk"] not in {x["sangha_sevi_pk"] for x in reviews}
        wl = client.get(f"{BASE}/watch-list", params={"organization_pk": register_org_pk}, headers=sakha_admin_h)
        assert m["sangha_sevi_pk"] not in {i["sangha_sevi_pk"] for i in wl.json()["items"]}

    def test_present_in_the_run_prevents_review(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "Present")
        for p, s in zip(register_pujas[:3], ("ABSENT", "PRESENT", "ABSENT")):
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], s))
        reviews = _list_reviews(client, sakha_admin_h)
        assert m["sangha_sevi_pk"] not in {x["sangha_sevi_pk"] for x in reviews}


class TestWatchList:

    def test_two_consecutive_absences_appear(
        self, client, write_conn, sakha_admin_h, register_org_pk, other_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "Watch")
        for p in register_pujas[:2]:
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "ABSENT"))
        r = client.get(f"{BASE}/watch-list", params={"organization_pk": register_org_pk}, headers=sakha_admin_h)
        assert r.status_code == 200, r.text
        item = next(i for i in r.json()["items"] if i["sangha_sevi_pk"] == m["sangha_sevi_pk"])
        assert item["current_consecutive_absences"] == 2
        assert item["last_puja_date"] == PUJA_DATES[1].isoformat()
        assert item["organization_pk"] == register_org_pk

    def test_unfiltered_list_is_scoped(self, client, write_conn, other_admin_h, register_org_pk):
        r = client.get(f"{BASE}/watch-list", headers=other_admin_h)
        assert r.status_code == 200
        assert register_org_pk not in {i["organization_pk"] for i in r.json()["items"]}

    @pytest.mark.parametrize("threshold", [0, 3])
    def test_threshold_is_bounded(self, client, sakha_admin_h, threshold):
        r = client.get(f"{BASE}/watch-list", params={"threshold": threshold}, headers=sakha_admin_h)
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# 6. Review workflow (Review Workflow doc §§ 8-13)
# ═══════════════════════════════════════════════════════════════════════

class TestReviewWorkflow:

    def _new_review(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "Rev")
        return _open_review(client, sakha_admin_h, register_pujas, m), m

    def _act(self, client, headers, review_pk, action, **body):
        return client.post(f"{BASE}/reviews/{review_pk}/{action}", json=body, headers=headers)

    def test_secretary_closes_open_review(
        self, client, write_conn, sakha_admin_h, secretary_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        r = self._act(client, secretary_h, pk, "close", remarks="spoke to family")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["review_status_code"] == "CLOSED"
        assert body["remarks"] == "spoke to family"
        assert body["closed_by_name"]

    def test_defer_then_revisit(self, client, write_conn, sakha_admin_h, secretary_h, register_org_pk, register_pujas):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        assert self._act(client, secretary_h, pk, "defer", remarks="festival").json()["review_status_code"] == "DEFERRED"
        assert self._act(client, secretary_h, pk, "defer").status_code == 422, "only OPEN can be deferred"
        assert self._act(client, secretary_h, pk, "revisit").json()["review_status_code"] == "OPEN"
        assert self._act(client, secretary_h, pk, "revisit").status_code == 422, "only DEFERRED can be revisited"

    def test_escalation_chain_and_president_only_steps(
        self, client, write_conn, sakha_admin_h, secretary_h, president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)

        r = self._act(client, secretary_h, pk, "escalate-to-president")
        assert r.status_code == 200 and r.json()["review_status_code"] == "ESCALATED_TO_PRESIDENT"
        assert r.json()["escalated_by_name"]

        # Once escalated, the Secretary no longer has the authority to close it.
        denied = self._act(client, secretary_h, pk, "close")
        assert denied.status_code == 403
        assert denied.json()["detail"] == "Only the Sakha's President may close this review."
        assert self._act(client, secretary_h, pk, "escalate-to-parichalak").status_code == 403

        r = self._act(client, president_h, pk, "escalate-to-parichalak", remarks="needs Parichalak")
        assert r.status_code == 200 and r.json()["review_status_code"] == "ESCALATED_TO_PARICHALAK"

    def test_president_closes_escalated_review_and_only_president_reopens(
        self, client, write_conn, sakha_admin_h, secretary_h, president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        self._act(client, secretary_h, pk, "escalate-to-president")
        assert self._act(client, president_h, pk, "close").json()["review_status_code"] == "CLOSED"

        assert self._act(client, secretary_h, pk, "reopen").status_code == 403, "Secretary cannot reopen"
        r = self._act(client, president_h, pk, "reopen", remarks="new facts")
        assert r.status_code == 200 and r.json()["review_status_code"] == "OPEN"
        assert self._act(client, president_h, pk, "reopen").status_code == 422, "only CLOSED can be reopened"

    def test_state_preconditions_are_422(
        self, client, write_conn, sakha_admin_h, secretary_h, president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        # OPEN cannot jump straight to the Parichalak, nor be reopened.
        assert self._act(client, president_h, pk, "escalate-to-parichalak").status_code == 422
        assert self._act(client, president_h, pk, "reopen").status_code == 422
        self._act(client, secretary_h, pk, "close")
        # CLOSED cannot be closed/deferred/escalated again.
        for action in ("close", "defer", "escalate-to-president"):
            assert self._act(client, secretary_h, pk, action).status_code == 422, action

    def test_president_override(
        self, client, write_conn, sakha_admin_h, secretary_h, president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        self._act(client, secretary_h, pk, "close")

        denied = self._act(client, secretary_h, pk, "override", new_status_code="OPEN", reason="x")
        assert denied.status_code == 403

        r = self._act(client, president_h, pk, "override", new_status_code="OPEN", reason="Secretary closed too early")
        assert r.status_code == 200, r.text
        assert r.json()["review_status_code"] == "OPEN"
        assert r.json()["remarks"] == "Secretary closed too early"

    def test_global_admin_may_act(self, client, write_conn, sakha_admin_h, admin_h, register_org_pk, register_pujas):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        r = self._act(client, admin_h, pk, "close", remarks="oversight")
        assert r.status_code == 200 and r.json()["review_status_code"] == "CLOSED"

    def test_other_sakhas_president_cannot_act(
        self, client, write_conn, sakha_admin_h, other_president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        r = self._act(client, other_president_h, pk, "close")
        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("action", ["close", "defer", "revisit", "escalate-to-president",
                                        "escalate-to-parichalak", "reopen"])
    def test_unknown_review_is_404(self, action, client, secretary_h):
        assert self._act(client, secretary_h, FAKE_UUID, action).status_code == 404

    def test_unknown_review_override_is_404(self, client, president_h):
        r = self._act(client, president_h, FAKE_UUID, "override", new_status_code="OPEN", reason="r")
        assert r.status_code == 404

    def test_get_and_list_filters(
        self, client, write_conn, sakha_admin_h, other_admin_h, secretary_h, register_org_pk, register_pujas,
    ):
        pk, m = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)

        r = client.get(f"{BASE}/reviews/{pk}", headers=sakha_admin_h)
        assert r.status_code == 200, r.text
        assert r.json()["sangha_sevi_id"] == m["sangha_sevi_id"]
        assert r.json()["review_status_code"] == "OPEN"

        assert client.get(f"{BASE}/reviews/{FAKE_UUID}", headers=sakha_admin_h).status_code == 404
        assert client.get(f"{BASE}/reviews/{pk}", headers=other_admin_h).status_code == 403

        open_ = _list_reviews(client, sakha_admin_h, review_status="OPEN", organization_pk=register_org_pk)
        assert pk in {x["review_pk"] for x in open_}

        self._act(client, secretary_h, pk, "close")
        closed = _list_reviews(client, sakha_admin_h, review_status="CLOSED")
        still_open = _list_reviews(client, sakha_admin_h, review_status="OPEN")
        assert pk in {x["review_pk"] for x in closed}
        assert pk not in {x["review_pk"] for x in still_open}


# ═══════════════════════════════════════════════════════════════════════
# 7. Statistics
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def stats_members(client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
    """
    Four members with known histories on the 2001 pujas:
      star   P P P          -> 3/3 = 100.0, streak 0, latest remark on P3
      half   P A            -> 1/2 =  50.0, streak 1
      zero   A A A A        -> 0/4 =   0.0, streak 4
      excuse A E A          -> 0/2 =   0.0, streak 1 (EXCUSED breaks the run, excluded from %)
      none   (no records)   -> percentage None
    """
    pk = lambda i: register_pujas[i]["weekly_sangha_puja_pk"]  # noqa: E731
    m = {n: new_member(write_conn, register_org_pk, n) for n in ("Star", "Half", "Zero", "Excuse", "None")}
    sp = lambda n: m[n]["sangha_sevi_pk"]  # noqa: E731

    mark(client, sakha_admin_h, pk(0), (sp("Star"), "PRESENT"), (sp("Half"), "PRESENT"), (sp("Zero"), "ABSENT"),
         (sp("Excuse"), "ABSENT"))
    mark(client, sakha_admin_h, pk(1), (sp("Star"), "PRESENT"), (sp("Half"), "ABSENT"), (sp("Zero"), "ABSENT"),
         (sp("Excuse"), "EXCUSED_ABSENCE"))
    mark(client, sakha_admin_h, pk(2), (sp("Star"), "PRESENT", "latest-remark"), (sp("Zero"), "ABSENT"),
         (sp("Excuse"), "ABSENT"))
    mark(client, sakha_admin_h, pk(3), (sp("Zero"), "ABSENT"))
    # Someone on the 5th puja too, so all five count as puja events with records.
    mark(client, sakha_admin_h, pk(4), (new_member(write_conn, register_org_pk, "Fifth")["sangha_sevi_pk"], "PRESENT"))
    return m


class TestMemberStats:

    @pytest.mark.parametrize("name,total,present,absent,excused,pct,streak", [
        ("Star", 3, 3, 0, 0, 100.0, 0),
        ("Half", 2, 1, 1, 0, 50.0, 1),
        ("Zero", 4, 0, 4, 0, 0.0, 4),
        ("Excuse", 3, 0, 2, 1, 0.0, 1),
        ("None", 0, 0, 0, 0, None, 0),
    ])
    def test_figures(self, name, total, present, absent, excused, pct, streak,
                     client, sakha_admin_h, stats_members):
        m = stats_members[name]
        r = client.get(f"{BASE}/stats/members/{m['sangha_sevi_pk']}", params=WINDOW, headers=sakha_admin_h)
        assert r.status_code == 200, r.text
        b = r.json()
        assert (b["total_records"], b["present_count"], b["absent_count"], b["excused_count"]) == (
            total, present, absent, excused)
        assert b["attendance_percentage"] == pct
        assert b["current_consecutive_absences"] == streak
        assert b["sangha_sevi_id"] == m["sangha_sevi_id"]

    def test_date_window_narrows_counts(self, client, sakha_admin_h, stats_members):
        m = stats_members["Star"]
        r = client.get(f"{BASE}/stats/members/{m['sangha_sevi_pk']}",
                       params={"from_date": "2001-01-01", "to_date": PUJA_DATES[0].isoformat()}, headers=sakha_admin_h)
        assert r.json()["total_records"] == 1

    def test_unknown_member_is_404(self, client, admin_h):
        assert client.get(f"{BASE}/stats/members/{FAKE_UUID}", headers=admin_h).status_code == 404


class TestOrganizationStats:

    def test_totals_are_internally_consistent(self, client, sakha_admin_h, register_org_pk, stats_members):
        r = client.get(f"{BASE}/stats/organizations/{register_org_pk}", params=WINDOW, headers=sakha_admin_h)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["organization_pk"] == register_org_pk
        assert b["total_puja_events"] == 5
        assert b["total_records"] == b["present_count"] + b["absent_count"] + b["excused_count"]
        denom = b["present_count"] + b["absent_count"]
        assert b["attendance_percentage"] == round(b["present_count"] / denom * 100, 1)

    def test_empty_window_has_null_percentage(self, client, sakha_admin_h, register_org_pk):
        r = client.get(f"{BASE}/stats/organizations/{register_org_pk}",
                       params={"from_date": "1990-01-01", "to_date": "1990-12-31"}, headers=sakha_admin_h)
        b = r.json()
        assert b["total_records"] == 0 and b["attendance_percentage"] is None

    def test_unknown_org_is_404(self, client, admin_h):
        assert client.get(f"{BASE}/stats/organizations/{FAKE_UUID}", headers=admin_h).status_code == 404


class TestMemberLeaderboard:

    def _board(self, client, headers, org, **params):
        r = client.get(f"{BASE}/stats/organizations/{org}/members", params={"limit": MAX_LIMIT, **params},
                       headers=headers)
        assert r.status_code == 200, r.text
        return r.json()

    def test_member_rows(self, client, sakha_admin_h, register_org_pk, stats_members):
        body = self._board(client, sakha_admin_h, register_org_pk)
        by_pk = {m["sangha_sevi_pk"]: m for m in body["members"]}
        star = by_pk[stats_members["Star"]["sangha_sevi_pk"]]
        assert star["attendance_percentage"] == 100.0
        assert star["latest_remarks"] == "latest-remark"
        assert [s["attendance_status_code"] for s in star["recent_statuses"]] == ["PRESENT"] * 3
        assert by_pk[stats_members["None"]["sangha_sevi_pk"]]["attendance_percentage"] is None
        assert by_pk[stats_members["None"]["sangha_sevi_pk"]]["recent_statuses"] == []

    def test_recent_statuses_capped_at_three_newest_first(self, client, sakha_admin_h, register_org_pk, stats_members):
        zero = next(m for m in self._board(client, sakha_admin_h, register_org_pk)["members"]
                    if m["sangha_sevi_pk"] == stats_members["Zero"]["sangha_sevi_pk"])
        assert len(zero["recent_statuses"]) == 3
        dates = [s["puja_date"] for s in zero["recent_statuses"]]
        assert dates == sorted(dates, reverse=True)
        assert dates[0] == PUJA_DATES[3].isoformat()

    @pytest.mark.parametrize("sort", ["desc", "asc"])
    def test_sort_order_with_nulls_last(self, sort, client, sakha_admin_h, register_org_pk, stats_members):
        pcts = [m["attendance_percentage"] for m in self._board(client, sakha_admin_h, register_org_pk, sort=sort)["members"]]
        known = [p for p in pcts if p is not None]
        assert known == sorted(known, reverse=(sort == "desc"))
        assert pcts[len(known):] == [None] * (len(pcts) - len(known)), "members with no history sort last"

    def test_limit_and_offset(self, client, sakha_admin_h, register_org_pk, stats_members):
        full = self._board(client, sakha_admin_h, register_org_pk)
        top = client.get(f"{BASE}/stats/organizations/{register_org_pk}/members", params={"limit": 2},
                         headers=sakha_admin_h).json()
        assert len(top["members"]) == 2 and top["total"] == full["total"]
        nxt = client.get(f"{BASE}/stats/organizations/{register_org_pk}/members", params={"limit": 2, "offset": 2},
                         headers=sakha_admin_h).json()
        assert [m["sangha_sevi_pk"] for m in nxt["members"]] == [m["sangha_sevi_pk"] for m in full["members"][2:4]]

    def test_unknown_org_is_404(self, client, admin_h):
        assert client.get(f"{BASE}/stats/organizations/{FAKE_UUID}/members", headers=admin_h).status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# 8. Request validation and pagination bounds (422 coverage, every route)
# ═══════════════════════════════════════════════════════════════════════

class TestRequestValidation:
    """Pydantic/Query validation fires before any DB work, so these never touch data."""

    @pytest.mark.parametrize("body", [
        {},
        {"sakha_pk": FAKE_UUID},
        {"puja_date": "2001-03-04"},
        {"sakha_pk": "not-a-uuid", "puja_date": "2001-03-04"},
        {"sakha_pk": FAKE_UUID, "puja_date": "04/03/2001"},
    ], ids=["empty", "no-date", "no-sakha", "bad-uuid", "bad-date"])
    def test_create_puja_invalid_body_is_422(self, body, client, admin_h):
        assert client.post(f"{BASE}/pujas", json=body, headers=admin_h).status_code == 422

    @pytest.mark.parametrize("body", [
        {},
        {"records": [{"sangha_sevi_pk": "not-a-uuid", "attendance_status_code": "PRESENT"}]},
        {"records": [{"sangha_sevi_pk": FAKE_UUID}]},
        {"records": [{"attendance_status_code": "PRESENT"}]},
        {"records": "PRESENT"},
    ], ids=["empty", "bad-member-uuid", "no-status", "no-member", "records-not-a-list"])
    def test_mark_attendance_invalid_body_is_422(self, body, client, admin_h):
        assert client.post(f"{BASE}/pujas/{FAKE_UUID}/attendance", json=body, headers=admin_h).status_code == 422

    def test_non_uuid_path_ids_are_422(self, client, admin_h):
        assert client.post(f"{BASE}/pujas/not-a-uuid/attendance", json={"records": []}, headers=admin_h).status_code == 422
        assert client.patch(f"{BASE}/records/not-a-uuid", json={"attendance_status_code": "PRESENT"},
                            headers=admin_h).status_code == 422
        assert client.get(f"{BASE}/reviews/not-a-uuid", headers=admin_h).status_code == 422
        assert client.post(f"{BASE}/reviews/not-a-uuid/close", json={}, headers=admin_h).status_code == 422
        assert client.get(f"{BASE}/stats/members/not-a-uuid", headers=admin_h).status_code == 422
        assert client.get(f"{BASE}/stats/organizations/not-a-uuid", headers=admin_h).status_code == 422

    def test_correct_attendance_requires_a_status(self, client, admin_h):
        r = client.patch(f"{BASE}/records/{FAKE_UUID}", json={"remarks": "only remarks"}, headers=admin_h)
        assert r.status_code == 422

    @pytest.mark.parametrize("body", [
        {},
        {"sangha_sevi_pk": FAKE_UUID, "exception_type_code": "MEDICAL"},
        {"sangha_sevi_pk": FAKE_UUID, "from_date": "2001-01-01"},
        {"exception_type_code": "MEDICAL", "from_date": "2001-01-01"},
        {"sangha_sevi_pk": FAKE_UUID, "exception_type_code": "MEDICAL", "from_date": "yesterday"},
    ], ids=["empty", "no-from-date", "no-type", "no-member", "bad-date"])
    def test_create_exception_invalid_body_is_422(self, body, client, admin_h):
        assert client.post(f"{BASE}/exceptions", json=body, headers=admin_h).status_code == 422

    @pytest.mark.parametrize("body", [{}, {"new_status_code": "OPEN"}, {"reason": "r"}])
    def test_override_requires_status_and_reason(self, body, client, president_h):
        assert client.post(f"{BASE}/reviews/{FAKE_UUID}/override", json=body, headers=president_h).status_code == 422

    @pytest.mark.parametrize("path", ["pujas", "records", "exceptions", "reviews"])
    @pytest.mark.parametrize("params", [{"page_size": 201}, {"page_size": 0}, {"page": 0}],
                             ids=["page-size-too-big", "page-size-zero", "page-zero"])
    def test_list_pagination_bounds_are_422(self, path, params, client, sakha_admin_h):
        assert client.get(f"{BASE}/{path}", params=params, headers=sakha_admin_h).status_code == 422

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": MAX_LIMIT + 1}, {"offset": -1}],
                             ids=["limit-zero", "limit-too-big", "negative-offset"])
    def test_leaderboard_bounds_are_422(self, params, client, sakha_admin_h, register_org_pk):
        r = client.get(f"{BASE}/stats/organizations/{register_org_pk}/members", params=params, headers=sakha_admin_h)
        assert r.status_code == 422

    @pytest.mark.parametrize("path", ["pujas", "stats/members/" + FAKE_UUID, "stats/organizations/" + FAKE_UUID])
    def test_malformed_date_filters_are_422(self, path, client, admin_h):
        assert client.get(f"{BASE}/{path}", params={"from_date": "31-12-2001"}, headers=admin_h).status_code == 422
        assert client.get(f"{BASE}/{path}", params={"to_date": "nope"}, headers=admin_h).status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# 9. Marking, correction and exception edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestMarkingEdgeCases:

    def test_empty_records_list_marks_nothing(self, client, sakha_admin_h, register_pujas):
        r = client.post(f"{BASE}/pujas/{register_pujas[0]['weekly_sangha_puja_pk']}/attendance",
                        json={"records": []}, headers=sakha_admin_h)
        assert r.status_code == 201, r.text
        assert r.json() == {"records": [], "total": 0}

    def test_same_member_twice_in_one_request_keeps_one_row_last_status_wins(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "MkTwice")
        out = mark(client, sakha_admin_h, register_pujas[4]["weekly_sangha_puja_pk"],
                   (m["sangha_sevi_pk"], "ABSENT"), (m["sangha_sevi_pk"], "PRESENT"))
        assert _status_by_member(out) == {m["sangha_sevi_pk"]: "PRESENT"}
        listed = client.get(f"{BASE}/records", params={"sangha_sevi_pk": m["sangha_sevi_pk"]}, headers=sakha_admin_h)
        assert listed.json()["total"] == 1

    def test_remarking_overwrites_remarks(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "MkRemark")
        pk = register_pujas[4]["weekly_sangha_puja_pk"]
        mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT", "first"))
        again = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        assert again["remarks"] is None, "bulk upsert replaces remarks (unlike PATCH, which keeps them)"

    def test_unknown_attendance_sakha_is_422_not_500(
        self, client, write_conn, isolated_savepoint, sakha_admin_h, register_org_pk, register_pujas,
    ):
        """fk_wspa_attendance_sakha: a bogus attendance_sakha_pk is a clean 422 from the integrity handler."""
        m = new_member(write_conn, register_org_pk, "MkBadSakha")
        with isolated_savepoint():
            r = client.post(
                f"{BASE}/pujas/{register_pujas[4]['weekly_sangha_puja_pk']}/attendance",
                json={"records": [{"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT",
                                   "attendance_sakha_pk": FAKE_UUID}]},
                headers=sakha_admin_h,
            )
        assert r.status_code == 422, r.text

    def test_attendance_marker_role_can_create_a_puja(self, client, marker_h, register_org_pk):
        p = make_puja(client, marker_h, register_org_pk, date(2002, 1, 6))
        assert p["sakha_pk"] == register_org_pk and p["puja_status"] == "CONDUCTED"

    def test_marking_a_future_puja_is_rejected(self, client, write_conn, sakha_admin_h, register_org_pk):
        """Lifecycle §4: attendance records may be created once the puja date is reached (SCHEDULED -> CONDUCTED)."""
        future = make_puja(client, sakha_admin_h, register_org_pk, date.today() + timedelta(days=600))
        assert future["puja_status"] == "SCHEDULED"
        m = new_member(write_conn, register_org_pk, "MkFuture")
        r = client.post(
            f"{BASE}/pujas/{future['weekly_sangha_puja_pk']}/attendance",
            json={"records": [{"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT"}]},
            headers=sakha_admin_h,
        )
        assert r.status_code == 422 and "before the puja date" in r.json()["detail"], r.text

    def test_puja_for_a_non_sakha_organization_is_rejected(self, client, write_conn, admin_h):
        """ATT-004: the event identifies the *Sakha* at which the puja was conducted."""
        cur = write_conn.cursor()
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code NOT IN ('SAKHA_SANGHA', 'SAKHA_ASANA') AND o.is_active = TRUE LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("No non-Sakha organization available.")
        r = client.post(f"{BASE}/pujas", json={"sakha_pk": str(row[0]), "puja_date": "2002-02-03"}, headers=admin_h)
        assert r.status_code == 422 and "Sakha Asana" in r.json()["detail"], r.text


class TestCorrectionEdgeCases:

    def _marked(self, client, write_conn, headers, org, puja, status):
        m = new_member(write_conn, org, "CorrEdge")
        return m, mark(client, headers, puja["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], status))["records"][0]

    def test_correcting_to_the_same_status_is_idempotent(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        _, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[4], "PRESENT")
        r = client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                         json={"attendance_status_code": "PRESENT"}, headers=sakha_admin_h)
        assert r.status_code == 200, r.text
        assert r.json()["attendance_pk"] == rec["attendance_pk"]

    def test_correction_keeps_the_same_row_and_member(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[4], "ABSENT")
        client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                     json={"attendance_status_code": "PRESENT"}, headers=sakha_admin_h)
        listed = client.get(f"{BASE}/records", params={"sangha_sevi_pk": m["sangha_sevi_pk"]}, headers=sakha_admin_h)
        assert listed.json()["total"] == 1, "ATT-039: corrected in place, original never duplicated or deleted"

    def test_correcting_to_an_unknown_status_is_a_client_error(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        _, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[4], "ABSENT")
        r = client.patch(f"{BASE}/records/{rec['attendance_pk']}",
                         json={"attendance_status_code": "LATE"}, headers=sakha_admin_h)
        assert r.status_code == 422 and "LATE" in r.json()["detail"], r.text

    def test_changing_away_from_excused_needs_the_secretary_or_president_seat(
        self, client, write_conn, sakha_admin_h, secretary_h, register_org_pk, register_pujas,
    ):
        """Un-excusing revokes an approval, so it needs the same seat as granting one."""
        m, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[4], "EXCUSED_ABSENCE")
        body = {"attendance_status_code": "ABSENT"}
        denied = client.patch(f"{BASE}/records/{rec['attendance_pk']}", json=body, headers=sakha_admin_h)
        assert denied.status_code == 403, denied.text
        # The bulk-mark upsert is the same revocation by another route.
        remark = client.post(f"{BASE}/pujas/{register_pujas[4]['weekly_sangha_puja_pk']}/attendance",
                             json={"records": [{"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT"}]},
                             headers=sakha_admin_h)
        assert remark.status_code == 403, remark.text
        allowed = client.patch(f"{BASE}/records/{rec['attendance_pk']}", json=body, headers=secretary_h)
        assert allowed.status_code == 200 and allowed.json()["attendance_status_code"] == "ABSENT"

    def test_remarking_a_soft_deleted_record_reactivates_it(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        """uq_wspa_puja_sevi is a plain UNIQUE, so a re-record upserts onto the soft-deleted row and revives it."""
        m, rec = self._marked(client, write_conn, sakha_admin_h, register_org_pk, register_pujas[4], "PRESENT")
        cur = write_conn.cursor()
        cur.execute("UPDATE nss.weekly_sangha_puja_attendance SET is_active = FALSE, deleted_at = NOW() "
                    "WHERE attendance_pk = %s", (rec["attendance_pk"],))
        again = mark(client, sakha_admin_h, register_pujas[4]["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "ABSENT"))
        assert again["records"][0]["attendance_pk"] == rec["attendance_pk"]
        listed = client.get(f"{BASE}/records", params={"sangha_sevi_pk": m["sangha_sevi_pk"]}, headers=sakha_admin_h).json()
        assert listed["total"] == 1 and listed["records"][0]["attendance_status_code"] == "ABSENT"


class TestExceptionEdgeCases:

    def test_to_date_before_from_date_is_422(
        self, client, write_conn, isolated_savepoint, secretary_h, register_org_pk,
    ):
        """chk_attexc_date_range surfaces as a clean 422 via the integrity handler."""
        m = new_member(write_conn, register_org_pk, "ExcRange")
        with isolated_savepoint():
            r = client.post(
                f"{BASE}/exceptions",
                json={"sangha_sevi_pk": m["sangha_sevi_pk"], "exception_type_code": "MEDICAL",
                      "from_date": "2001-03-31", "to_date": "2001-03-01"},
                headers=secretary_h,
            )
        assert r.status_code == 422, r.text

    def test_single_day_exception_is_allowed(self, client, write_conn, secretary_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "ExcOneDay")
        r = client.post(
            f"{BASE}/exceptions",
            json={"sangha_sevi_pk": m["sangha_sevi_pk"], "exception_type_code": "MEDICAL",
                  "from_date": "2001-03-04", "to_date": "2001-03-04"},
            headers=secretary_h,
        )
        assert r.status_code == 201, r.text

    def test_unknown_exception_type_is_a_client_error(self, client, write_conn, secretary_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "ExcBadType")
        r = client.post(
            f"{BASE}/exceptions",
            json={"sangha_sevi_pk": m["sangha_sevi_pk"], "exception_type_code": "NOT_A_TYPE", "from_date": "2001-03-01"},
            headers=secretary_h,
        )
        assert r.status_code == 422 and "NOT_A_TYPE" in r.json()["detail"], r.text

    def test_list_pagination_and_newest_first(self, client, write_conn, secretary_h, sakha_admin_h, register_org_pk):
        m = new_member(write_conn, register_org_pk, "ExcPage")
        for frm in ("2001-01-01", "2001-02-01", "2001-03-01"):
            r = client.post(f"{BASE}/exceptions",
                            json={"sangha_sevi_pk": m["sangha_sevi_pk"], "exception_type_code": "MEDICAL",
                                  "from_date": frm}, headers=secretary_h)
            assert r.status_code == 201, r.text
        r = client.get(f"{BASE}/exceptions", params={"sangha_sevi_pk": m["sangha_sevi_pk"], "page": 1, "page_size": 2},
                       headers=sakha_admin_h)
        body = r.json()
        assert body["total"] == 3 and len(body["exceptions"]) == 2
        assert [e["from_date"] for e in body["exceptions"]] == ["2001-03-01", "2001-02-01"]

    def test_an_approved_exception_prevents_the_review_trigger(
        self, client, write_conn, sakha_admin_h, secretary_h, register_org_pk, register_pujas,
    ):
        """ATT-025: an absence inside an approved exception period is not an ordinary ABSENT."""
        m = new_member(write_conn, register_org_pk, "ExcNoReview")
        r = client.post(
            f"{BASE}/exceptions",
            json={"sangha_sevi_pk": m["sangha_sevi_pk"], "exception_type_code": "MEDICAL",
                  "from_date": "2001-01-01", "to_date": "2001-12-31"},
            headers=secretary_h,
        )
        assert r.status_code == 201, r.text
        for p in register_pujas[:3]:
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "ABSENT"))
        assert m["sangha_sevi_pk"] not in {x["sangha_sevi_pk"] for x in _list_reviews(client, sakha_admin_h)}


# ══════════════════════════════════════════════════���════════════════════
# 10. Review workflow edge cases and the watch list
# ═══════════════════════════════════════════════════════════════════════

class TestReviewEdgeCases:

    def _act(self, client, headers, review_pk, action, **body):
        return client.post(f"{BASE}/reviews/{review_pk}/{action}", json=body, headers=headers)

    def _new_review(self, client, write_conn, headers, org, pujas, label="RevEdge"):
        m = new_member(write_conn, org, label)
        return _open_review(client, headers, pujas, m), m

    def test_parichalak_escalated_review_accepts_no_further_workflow_action(
        self, client, write_conn, sakha_admin_h, secretary_h, president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        self._act(client, secretary_h, pk, "escalate-to-president")
        assert self._act(client, president_h, pk, "escalate-to-parichalak").status_code == 200
        for action in ("close", "defer", "revisit", "escalate-to-president", "escalate-to-parichalak", "reopen"):
            assert self._act(client, president_h, pk, action).status_code == 422, action

    def test_escalated_to_president_cannot_be_deferred_or_revisited(
        self, client, write_conn, sakha_admin_h, secretary_h, president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        self._act(client, secretary_h, pk, "escalate-to-president")
        for action in ("defer", "revisit", "escalate-to-president", "reopen"):
            assert self._act(client, president_h, pk, action).status_code == 422, action

    def test_deferred_review_can_only_be_revisited_or_overridden(
        self, client, write_conn, sakha_admin_h, secretary_h, president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        self._act(client, secretary_h, pk, "defer", remarks="festival")
        for action in ("close", "escalate-to-president", "escalate-to-parichalak", "reopen"):
            assert self._act(client, secretary_h, pk, action).status_code == 422, action
        r = self._act(client, president_h, pk, "override", new_status_code="CLOSED", reason="resolved offline")
        assert r.status_code == 200 and r.json()["review_status_code"] == "CLOSED"

    def test_action_remarks_and_actor_names_are_recorded(
        self, client, write_conn, sakha_admin_h, secretary_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        body = self._act(client, secretary_h, pk, "defer", remarks="after Holi").json()
        assert body["remarks"] == "after Holi"
        assert body["deferred_by_name"] and body["closed_by_name"] is None and body["escalated_by_name"] is None
        # Revisit without remarks leaves the previous remarks untouched (remarks are only SET when supplied).
        assert self._act(client, secretary_h, pk, "revisit").json()["remarks"] == "after Holi"

    def test_fourth_absence_after_close_opens_a_fresh_review(
        self, client, write_conn, sakha_admin_h, secretary_h, register_org_pk, register_pujas,
    ):
        """ATT-014: only a *non-terminal* review suppresses a new one; a CLOSED review does not."""
        pk, m = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        assert self._act(client, secretary_h, pk, "close").status_code == 200
        mark(client, sakha_admin_h, register_pujas[3]["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "ABSENT"))
        mine = [x for x in _list_reviews(client, sakha_admin_h) if x["sangha_sevi_pk"] == m["sangha_sevi_pk"]]
        assert sorted(x["review_status_code"] for x in mine) == ["CLOSED", "OPEN"]

    def test_override_to_an_unknown_status_is_a_client_error(
        self, client, write_conn, sakha_admin_h, president_h, register_org_pk, register_pujas,
    ):
        pk, _ = self._new_review(client, write_conn, sakha_admin_h, register_org_pk, register_pujas)
        r = self._act(client, president_h, pk, "override", new_status_code="NOT_A_STATUS", reason="x")
        assert r.status_code == 422 and "NOT_A_STATUS" in r.json()["detail"], r.text

    def test_review_list_pagination(self, client, sakha_admin_h):
        r = client.get(f"{BASE}/reviews", params={"page": 1, "page_size": 1}, headers=sakha_admin_h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["reviews"]) <= 1 and body["total"] >= len(body["reviews"])

    def test_review_status_filter_with_unknown_code_is_empty(self, client, sakha_admin_h):
        r = client.get(f"{BASE}/reviews", params={"review_status": "NOT_A_STATUS"}, headers=sakha_admin_h)
        assert r.status_code == 200 and r.json() == {"reviews": [], "total": 0}


class TestWatchListEdgeCases:

    def test_threshold_one_lists_a_single_trailing_absence(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "WatchOne")
        mark(client, sakha_admin_h, register_pujas[0]["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "ABSENT"))
        r = client.get(f"{BASE}/watch-list", params={"organization_pk": register_org_pk, "threshold": 1},
                       headers=sakha_admin_h)
        item = next(i for i in r.json()["items"] if i["sangha_sevi_pk"] == m["sangha_sevi_pk"])
        assert item["current_consecutive_absences"] == 1

    def test_default_threshold_excludes_a_single_absence(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "WatchSingle")
        mark(client, sakha_admin_h, register_pujas[0]["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "ABSENT"))
        r = client.get(f"{BASE}/watch-list", params={"organization_pk": register_org_pk}, headers=sakha_admin_h)
        assert m["sangha_sevi_pk"] not in {i["sangha_sevi_pk"] for i in r.json()["items"]}

    def test_a_latest_present_removes_the_member(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "WatchPresent")
        for p, s in zip(register_pujas[:3], ("ABSENT", "ABSENT", "PRESENT")):
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], s))
        r = client.get(f"{BASE}/watch-list", params={"organization_pk": register_org_pk}, headers=sakha_admin_h)
        assert m["sangha_sevi_pk"] not in {i["sangha_sevi_pk"] for i in r.json()["items"]}

    def test_member_already_at_the_review_trigger_is_not_on_the_watch_list(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        """watch_list's docstring: 'not yet at the 3-absence trigger'."""
        m = new_member(write_conn, register_org_pk, "WatchTrigger")
        _open_review(client, sakha_admin_h, register_pujas, m)
        r = client.get(f"{BASE}/watch-list", params={"organization_pk": register_org_pk}, headers=sakha_admin_h)
        assert m["sangha_sevi_pk"] not in {i["sangha_sevi_pk"] for i in r.json()["items"]}

    def test_absences_covered_by_an_approved_exception_do_not_count(
        self, client, write_conn, sakha_admin_h, secretary_h, register_org_pk, register_pujas,
    ):
        """ATT-025 applies to the watch list exactly as it does to the review trigger."""
        m = new_member(write_conn, register_org_pk, "WatchExcepted")
        assert client.post(f"{BASE}/exceptions", headers=secretary_h, json={
            "sangha_sevi_pk": m["sangha_sevi_pk"], "exception_type_code": "MEDICAL",
            "from_date": "2001-01-01", "to_date": "2001-12-31"}).status_code == 201
        for p in register_pujas[:2]:
            mark(client, sakha_admin_h, p["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "ABSENT"))
        r = client.get(f"{BASE}/watch-list", params={"organization_pk": register_org_pk}, headers=sakha_admin_h)
        assert m["sangha_sevi_pk"] not in {i["sangha_sevi_pk"] for i in r.json()["items"]}


class TestSelfAccessAndValidation:

    def test_a_member_can_read_their_own_records_exceptions_and_stats_without_attendance_view(
        self, client, write_conn, sakha_admin_h, register_org_pk,
    ):
        member = new_member(write_conn, register_org_pk, "SelfRead")
        me = member["sangha_sevi_pk"]
        # Own puja date outside 2001 so register-wide 2001 stats assertions are unaffected.
        puja = make_puja(client, sakha_admin_h, register_org_pk, date(2002, 6, 2))
        mark(client, sakha_admin_h, puja["weekly_sangha_puja_pk"], (me, "PRESENT"))
        h = _login_headers(client, member["sangha_sevi_id"], member["password"])
        recs = client.get(f"{BASE}/records", params={"sangha_sevi_pk": me}, headers=h)
        assert recs.status_code == 200 and recs.json()["total"] == 1
        assert client.get(f"{BASE}/exceptions", params={"sangha_sevi_pk": me}, headers=h).status_code == 200
        assert client.get(f"{BASE}/stats/members/{me}", headers=h).status_code == 200

    def test_a_member_cannot_read_someone_elses_without_attendance_view(
        self, client, write_conn, plain_member_h, register_org_pk,
    ):
        other = new_member(write_conn, register_org_pk, "NotMe")["sangha_sevi_pk"]
        for path in (f"{BASE}/records", f"{BASE}/exceptions"):
            assert client.get(path, params={"sangha_sevi_pk": other}, headers=plain_member_h).status_code == 403
        assert client.get(f"{BASE}/stats/members/{other}", headers=plain_member_h).status_code == 403

    def test_records_can_be_narrowed_to_one_puja(self, client, sakha_admin_h, register_org_pk, register_pujas):
        r = client.get(f"{BASE}/records", headers=sakha_admin_h, params={
            "organization_pk": register_org_pk, "weekly_sangha_puja_pk": register_pujas[0]["weekly_sangha_puja_pk"],
            "page_size": 200})
        assert r.status_code == 200
        assert {x["weekly_sangha_puja_pk"] for x in r.json()["records"]} <= {register_pujas[0]["weekly_sangha_puja_pk"]}

    def test_records_page_size_is_capped_at_200(self, client, sakha_admin_h):
        assert client.get(f"{BASE}/records", params={"page_size": 201}, headers=sakha_admin_h).status_code == 422

    def test_attendance_sakha_must_be_a_sakha(self, client, write_conn, admin_h, sakha_admin_h,
                                              register_org_pk, register_pujas):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code NOT IN ('SAKHA_SANGHA', 'SAKHA_ASANA') AND o.is_active = TRUE LIMIT 1
        """)
        row = cur.fetchone()
        if row is None:
            pytest.skip("No non-Sakha organization available.")
        m = new_member(write_conn, register_org_pk, "MkNonSakha")
        r = client.post(
            f"{BASE}/pujas/{register_pujas[4]['weekly_sangha_puja_pk']}/attendance",
            json={"records": [{"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT",
                               "attendance_sakha_pk": str(row[0])}]},
            headers=sakha_admin_h)
        assert r.status_code == 422 and "Sakha Asana" in r.json()["detail"], r.text

    @pytest.mark.parametrize("sort", ["sideways", "DESC", ""])
    def test_leaderboard_sort_must_be_asc_or_desc(self, sort, client, sakha_admin_h, register_org_pk):
        r = client.get(f"{BASE}/stats/organizations/{register_org_pk}/members", params={"sort": sort}, headers=sakha_admin_h)
        assert r.status_code == 422


class TestStatsEdgeCases:

    def test_inverted_window_yields_zero_counts(self, client, sakha_admin_h, register_org_pk, stats_members):
        params = {"from_date": "2001-12-31", "to_date": "2001-01-01"}
        org = client.get(f"{BASE}/stats/organizations/{register_org_pk}", params=params, headers=sakha_admin_h).json()
        assert org["total_records"] == 0 and org["attendance_percentage"] is None
        mem = client.get(f"{BASE}/stats/members/{stats_members['Star']['sangha_sevi_pk']}",
                         params=params, headers=sakha_admin_h).json()
        assert mem["total_records"] == 0 and mem["attendance_percentage"] is None

    def test_leaderboard_total_counts_every_active_home_member(
        self, client, sakha_admin_h, register_org_pk, stats_members,
    ):
        r = client.get(f"{BASE}/stats/organizations/{register_org_pk}/members",
                       params={"limit": MAX_LIMIT}, headers=sakha_admin_h).json()
        assert r["total"] == len(r["members"]) and r["total"] >= len(stats_members)

    def test_member_stats_echo_the_requested_window(self, client, sakha_admin_h, stats_members):
        b = client.get(f"{BASE}/stats/members/{stats_members['Half']['sangha_sevi_pk']}",
                       params=WINDOW, headers=sakha_admin_h).json()
        assert b["period_from"] == WINDOW["from_date"] and b["period_to"] == WINDOW["to_date"]

    def test_excused_only_history_has_null_percentage(self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas):
        m = new_member(write_conn, register_org_pk, "OnlyExcused")
        mark(client, sakha_admin_h, register_pujas[4]["weekly_sangha_puja_pk"], (m["sangha_sevi_pk"], "EXCUSED_ABSENCE"))
        b = client.get(f"{BASE}/stats/members/{m['sangha_sevi_pk']}", params=WINDOW, headers=sakha_admin_h).json()
        assert (b["total_records"], b["excused_count"], b["attendance_percentage"]) == (1, 1, None)


# ═══════════════════════════════════════════════════════════════════════
# Live register — GET /pujas/{pk}/live and optimistic-concurrency marking
# (collected only: written but NOT yet run against a DB)
#
# The suite runs every test of a module inside ONE transaction, so NOW() (and
# therefore created_at/updated_at) is identical for every write. Another
# marker's later change is therefore simulated by moving the row's timestamp
# with _shift_version(), which is exactly what a later commit looks like.
# ═══════════════════════════════════════════════════════════════════════

def _shift_version(write_conn, attendance_pk: str, minutes: int) -> None:
    with write_conn.cursor() as cur:
        cur.execute(
            "UPDATE nss.weekly_sangha_puja_attendance "
            "SET updated_at = COALESCE(updated_at, created_at) + %s * INTERVAL '1 minute' "
            "WHERE attendance_pk = %s",
            (minutes, attendance_pk),
        )


def _live(client, headers, puja_pk, params=None):
    return client.get(f"{BASE}/pujas/{puja_pk}/live", params=params, headers=headers)


def _post_mark(client, headers, puja_pk, records, overwrite=None):
    body = {"records": records}
    if overwrite is not None:
        body["overwrite_sangha_sevi_pks"] = overwrite
    return client.post(f"{BASE}/pujas/{puja_pk}/attendance", json=body, headers=headers)


class TestLiveEndpoint:

    def test_without_since_returns_every_row_with_attribution(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[0]["weekly_sangha_puja_pk"]
        a, b = (new_member(write_conn, register_org_pk, n) for n in ("LvA", "LvB"))
        marked = mark(client, sakha_admin_h, pk, (a["sangha_sevi_pk"], "PRESENT"), (b["sangha_sevi_pk"], "ABSENT"))
        r = _live(client, sakha_admin_h, pk)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) == {"server_time", "marked_count", "changed"}
        by_member = {c["sangha_sevi_pk"]: c for c in body["changed"]}
        assert by_member[a["sangha_sevi_pk"]]["attendance_status_code"] == "PRESENT"
        assert by_member[b["sangha_sevi_pk"]]["attendance_status_code"] == "ABSENT"
        row = by_member[a["sangha_sevi_pk"]]
        assert set(row) == {"sangha_sevi_pk", "attendance_pk", "attendance_status_code", "version",
                            "marked_by_name", "marked_by_sangha_sevi_id", "marked_at", "is_active"}
        assert row["is_active"] is True and row["marked_by_sangha_sevi_id"]
        assert row["version"] == row["marked_at"]
        assert body["marked_count"] >= 2
        assert r.headers["ETag"]
        # The marked-by data matches what the mark response / GET /records carry.
        rec = next(x for x in marked["records"] if x["sangha_sevi_pk"] == a["sangha_sevi_pk"])
        assert rec["version"] == row["version"] and rec["marked_by_sangha_sevi_id"] == row["marked_by_sangha_sevi_id"]

    def test_since_returns_only_rows_changed_after_the_cursor(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[1]["weekly_sangha_puja_pk"]
        a, b = (new_member(write_conn, register_org_pk, n) for n in ("LvSinceA", "LvSinceB"))
        out = mark(client, sakha_admin_h, pk, (a["sangha_sevi_pk"], "PRESENT"), (b["sangha_sevi_pk"], "PRESENT"))
        rec_a = next(x for x in out["records"] if x["sangha_sevi_pk"] == a["sangha_sevi_pk"])
        _shift_version(write_conn, rec_a["attendance_pk"], 10)     # a changed 10 minutes "later"
        full = {c["sangha_sevi_pk"]: c for c in _live(client, sakha_admin_h, pk).json()["changed"]}
        cursor = full[b["sangha_sevi_pk"]]["version"]
        # A cursor 5 minutes after b's version: only a (shifted +10 min) is newer.
        from datetime import datetime, timedelta
        since = (datetime.fromisoformat(cursor) + timedelta(minutes=5)).isoformat()
        changed = _live(client, sakha_admin_h, pk, params={"since": since}).json()["changed"]
        assert {c["sangha_sevi_pk"] for c in changed} == {a["sangha_sevi_pk"]}
        # (b is excluded: it is older than the cursor minus the 1 s overlap.)
        # A cursor after everything: nothing changed.
        later = (datetime.fromisoformat(cursor) + timedelta(hours=1)).isoformat()
        assert _live(client, sakha_admin_h, pk, params={"since": later}).json()["changed"] == []

    def test_rows_within_the_one_second_overlap_are_resent(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        from datetime import datetime, timedelta
        pk = register_pujas[1]["weekly_sangha_puja_pk"]
        m = new_member(write_conn, register_org_pk, "LvOverlap")
        rec = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        v = datetime.fromisoformat(rec["version"])
        inside = (v + timedelta(milliseconds=500)).isoformat()    # cursor just after the row: still inside the overlap
        outside = (v + timedelta(seconds=5)).isoformat()
        assert m["sangha_sevi_pk"] in {c["sangha_sevi_pk"] for c in
                                       _live(client, sakha_admin_h, pk, params={"since": inside}).json()["changed"]}
        assert m["sangha_sevi_pk"] not in {c["sangha_sevi_pk"] for c in
                                           _live(client, sakha_admin_h, pk, params={"since": outside}).json()["changed"]}

    def test_etag_gives_304_until_something_changes(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[2]["weekly_sangha_puja_pk"]
        m = new_member(write_conn, register_org_pk, "LvEtag")
        mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))
        first = _live(client, sakha_admin_h, pk)
        etag = first.headers["ETag"]
        again = _live(client, {**sakha_admin_h, "If-None-Match": etag}, pk)
        assert again.status_code == 304 and again.content == b""
        mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "ABSENT"))
        changed = _live(client, {**sakha_admin_h, "If-None-Match": etag}, pk)
        assert changed.status_code == 200 and changed.headers["ETag"] != etag

    def test_a_removed_row_is_reported_inactive_and_leaves_the_marked_count(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[3]["weekly_sangha_puja_pk"]
        m = new_member(write_conn, register_org_pk, "LvRemoved")
        rec = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        before = _live(client, sakha_admin_h, pk).json()["marked_count"]
        with write_conn.cursor() as cur:
            cur.execute(
                "UPDATE nss.weekly_sangha_puja_attendance SET is_active = FALSE, deleted_at = NOW(), "
                "updated_at = NOW() + INTERVAL '1 minute' WHERE attendance_pk = %s", (rec["attendance_pk"],))
        body = _live(client, sakha_admin_h, pk).json()
        row = next(c for c in body["changed"] if c["sangha_sevi_pk"] == m["sangha_sevi_pk"])
        assert row["is_active"] is False
        assert body["marked_count"] == before - 1

    def test_marker_role_can_poll_its_own_sakha(self, client, marker_h, register_pujas):
        r = _live(client, marker_h, register_pujas[0]["weekly_sangha_puja_pk"])
        assert r.status_code == 200, r.text

    def test_unknown_puja_is_404(self, client, sakha_admin_h):
        assert _live(client, sakha_admin_h, FAKE_UUID).status_code == 404

    def test_bad_since_is_422(self, client, sakha_admin_h, register_pujas):
        r = _live(client, sakha_admin_h, register_pujas[0]["weekly_sangha_puja_pk"], params={"since": "yesterday"})
        assert r.status_code == 422


class TestRecordAttribution:

    def test_records_and_mark_response_say_who_marked_and_when(
        self, client, write_conn, sakha_admin_h, sakha_admin, register_org_pk, register_pujas,
    ):
        pk = register_pujas[0]["weekly_sangha_puja_pk"]
        m = new_member(write_conn, register_org_pk, "AttrWho")
        rec = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        assert rec["marked_by_sangha_sevi_id"] == sakha_admin["sangha_sevi_id"]
        assert rec["marked_by_name"] and rec["marked_at"] and rec["version"] == rec["marked_at"]
        listed = client.get(f"{BASE}/records", params={"sangha_sevi_pk": m["sangha_sevi_pk"]}, headers=sakha_admin_h).json()
        assert listed["records"][0]["version"] == rec["version"]

    def test_a_remark_by_someone_else_changes_the_marker_and_version(
        self, client, write_conn, sakha_admin_h, marker_h, marker_user, register_org_pk, register_pujas,
    ):
        pk = register_pujas[0]["weekly_sangha_puja_pk"]
        m = new_member(write_conn, register_org_pk, "AttrRemark")
        first = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "ABSENT"))["records"][0]
        second = mark(client, marker_h, pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        assert second["marked_by_sangha_sevi_id"] == marker_user["sangha_sevi_id"]
        assert second["attendance_pk"] == first["attendance_pk"]


class TestConcurrentMarking:

    def _setup(self, client, write_conn, sakha_admin_h, marker_h, register_org_pk, puja_pk, label):
        """Member marked PRESENT by marker A (version v1); then marker B flips it to ABSENT a minute later."""
        m = new_member(write_conn, register_org_pk, label)
        v1 = mark(client, sakha_admin_h, puja_pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        theirs = mark(client, marker_h, puja_pk, (m["sangha_sevi_pk"], "ABSENT"))["records"][0]
        _shift_version(write_conn, theirs["attendance_pk"], 1)
        return m, v1, theirs

    def test_stale_expected_version_with_a_different_status_is_a_409_and_saves_nothing(
        self, client, write_conn, sakha_admin_h, marker_h, marker_user, register_org_pk, register_pujas,
    ):
        pk = register_pujas[0]["weekly_sangha_puja_pk"]
        m, v1, theirs = self._setup(client, write_conn, sakha_admin_h, marker_h, register_org_pk, pk, "CcStale")
        other = new_member(write_conn, register_org_pk, "CcInnocent")
        r = _post_mark(client, sakha_admin_h, pk, [
            {"sangha_sevi_pk": other["sangha_sevi_pk"], "attendance_status_code": "PRESENT", "expected_version": None},
            {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT", "expected_version": v1["version"]},
        ])
        assert r.status_code == 409, r.text
        detail = r.json()["detail"]
        assert set(detail) == {"message", "conflicts"} and len(detail["conflicts"]) == 1
        c = detail["conflicts"][0]
        assert set(c) == {"sangha_sevi_pk", "current_status_code", "changed_by_name", "changed_by_sangha_sevi_id",
                          "changed_at", "requested_status_code"}
        assert c["sangha_sevi_pk"] == m["sangha_sevi_pk"]
        assert (c["current_status_code"], c["requested_status_code"]) == ("ABSENT", "PRESENT")
        assert c["changed_by_sangha_sevi_id"] == marker_user["sangha_sevi_id"]
        # All-or-nothing: neither the conflicting nor the innocent member was written.
        now = {x["sangha_sevi_pk"]: x["attendance_status_code"] for x in
               client.get(f"{BASE}/records", params={"weekly_sangha_puja_pk": pk, "organization_pk": register_org_pk,
                                                     "page_size": 200}, headers=sakha_admin_h).json()["records"]}
        assert now[m["sangha_sevi_pk"]] == "ABSENT" and other["sangha_sevi_pk"] not in now

    def test_identical_requested_status_is_not_a_conflict(
        self, client, write_conn, sakha_admin_h, marker_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[1]["weekly_sangha_puja_pk"]
        m, v1, theirs = self._setup(client, write_conn, sakha_admin_h, marker_h, register_org_pk, pk, "CcSame")
        r = _post_mark(client, sakha_admin_h, pk, [
            {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "ABSENT", "expected_version": v1["version"]}])
        assert r.status_code == 201, r.text

    def test_confirmed_overwrite_saves(
        self, client, write_conn, sakha_admin_h, marker_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[2]["weekly_sangha_puja_pk"]
        m, v1, theirs = self._setup(client, write_conn, sakha_admin_h, marker_h, register_org_pk, pk, "CcOverwrite")
        item = {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT", "expected_version": v1["version"]}
        assert _post_mark(client, sakha_admin_h, pk, [item]).status_code == 409
        r = _post_mark(client, sakha_admin_h, pk, [item], overwrite=[m["sangha_sevi_pk"]])
        assert r.status_code == 201, r.text
        assert r.json()["records"][0]["attendance_status_code"] == "PRESENT"

    def test_matching_expected_version_saves(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[3]["weekly_sangha_puja_pk"]
        m = new_member(write_conn, register_org_pk, "CcMatch")
        v1 = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        r = _post_mark(client, sakha_admin_h, pk, [
            {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "ABSENT", "expected_version": v1["version"]}])
        assert r.status_code == 201, r.text

    def test_null_expected_version_conflicts_only_if_someone_marked_it_meanwhile(
        self, client, write_conn, sakha_admin_h, marker_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[4]["weekly_sangha_puja_pk"]
        fresh = new_member(write_conn, register_org_pk, "CcNullFresh")
        taken = new_member(write_conn, register_org_pk, "CcNullTaken")
        mark(client, marker_h, pk, (taken["sangha_sevi_pk"], "ABSENT"))
        ok = _post_mark(client, sakha_admin_h, pk, [
            {"sangha_sevi_pk": fresh["sangha_sevi_pk"], "attendance_status_code": "PRESENT", "expected_version": None}])
        assert ok.status_code == 201, ok.text
        bad = _post_mark(client, sakha_admin_h, pk, [
            {"sangha_sevi_pk": taken["sangha_sevi_pk"], "attendance_status_code": "PRESENT", "expected_version": None}])
        assert bad.status_code == 409
        assert bad.json()["detail"]["conflicts"][0]["current_status_code"] == "ABSENT"

    # ── Someone else's mark, version MATCHES (owner 2026-11-01: "ask, naming who changed it") ──

    def _marked_by_other(self, client, write_conn, marker_h, register_org_pk, pk, label, status="ABSENT"):
        m = new_member(write_conn, register_org_pk, label)
        rec = mark(client, marker_h, pk, (m["sangha_sevi_pk"], status))["records"][0]
        return m, rec

    def test_matching_version_but_marked_by_someone_else_with_a_different_status_is_a_409(
        self, client, write_conn, sakha_admin_h, marker_h, marker_user, register_org_pk, register_pujas,
    ):
        pk = register_pujas[0]["weekly_sangha_puja_pk"]
        m, rec = self._marked_by_other(client, write_conn, marker_h, register_org_pk, pk, "CcOtherMatch")
        item = {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT",
                "expected_version": rec["version"]}
        r = _post_mark(client, sakha_admin_h, pk, [item])
        assert r.status_code == 409, r.text
        [c] = r.json()["detail"]["conflicts"]
        assert c["changed_by_sangha_sevi_id"] == marker_user["sangha_sevi_id"] and c["changed_by_name"]
        assert (c["current_status_code"], c["requested_status_code"]) == ("ABSENT", "PRESENT")
        # nothing was written; an explicit overwrite then saves
        assert _post_mark(client, sakha_admin_h, pk, [item], overwrite=[m["sangha_sevi_pk"]]).status_code == 201

    def test_matching_version_same_status_as_someone_else_is_not_a_conflict(
        self, client, write_conn, sakha_admin_h, marker_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[1]["weekly_sangha_puja_pk"]
        m, rec = self._marked_by_other(client, write_conn, marker_h, register_org_pk, pk, "CcOtherSame")
        r = _post_mark(client, sakha_admin_h, pk, [
            {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "ABSENT", "expected_version": rec["version"]}])
        assert r.status_code == 201, r.text

    def test_editing_your_own_mark_never_conflicts_even_after_the_row_was_touched_by_you_twice(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[2]["weekly_sangha_puja_pk"]
        m = new_member(write_conn, register_org_pk, "CcOwnTwice")
        v1 = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))["records"][0]
        v2 = _post_mark(client, sakha_admin_h, pk, [
            {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "ABSENT", "expected_version": v1["version"]}])
        assert v2.status_code == 201, v2.text
        r = _post_mark(client, sakha_admin_h, pk, [
            {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "PRESENT",
             "expected_version": v2.json()["records"][0]["version"]}])
        assert r.status_code == 201, r.text

    def test_legacy_request_without_expected_version_may_still_overwrite_someone_elses_mark(
        self, client, write_conn, sakha_admin_h, marker_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[3]["weekly_sangha_puja_pk"]
        m, _ = self._marked_by_other(client, write_conn, marker_h, register_org_pk, pk, "CcOtherLegacy")
        out = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))
        assert out["records"][0]["attendance_status_code"] == "PRESENT"

    def test_request_without_any_expected_version_is_last_write_wins_as_before(
        self, client, write_conn, sakha_admin_h, marker_h, register_org_pk, register_pujas,
    ):
        pk = register_pujas[0]["weekly_sangha_puja_pk"]
        m, v1, theirs = self._setup(client, write_conn, sakha_admin_h, marker_h, register_org_pk, pk, "CcLegacy")
        out = mark(client, sakha_admin_h, pk, (m["sangha_sevi_pk"], "PRESENT"))
        assert out["records"][0]["attendance_status_code"] == "PRESENT"

    def test_unknown_status_is_still_422_before_any_conflict_check(
        self, client, write_conn, sakha_admin_h, register_org_pk, register_pujas,
    ):
        m = new_member(write_conn, register_org_pk, "CcBadStatus")
        r = _post_mark(client, sakha_admin_h, register_pujas[0]["weekly_sangha_puja_pk"], [
            {"sangha_sevi_pk": m["sangha_sevi_pk"], "attendance_status_code": "LATE", "expected_version": None}])
        assert r.status_code == 422
