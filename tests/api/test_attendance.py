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
    BASE, FAKE_UUID, PUJA_DATES, WINDOW,
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
        assert r.json()["detail"] == "Only the Sakha's Secretary or President may approve an Excused Absence."

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
