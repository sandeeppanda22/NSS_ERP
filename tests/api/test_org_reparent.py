"""
Sakha re-parent approval workflow (owner rule 2026-10-30) — api/routers/
org_reparent.py, api/services/org_reparent_service.py and the deferred-parent
branch of PATCH /admin/organizations/{pk}.

Real-DB integration tests like the rest of tests/api (nothing mocked); written
but NOT yet run against a database — do not claim they pass. Everything rolls
back with the module SAVEPOINT. Fresh Sakhas/Anchalikas are created per test
through the admin API (see tests/reparent_support.py).

Covers (chain = Sakha Pres -> leaving Anchalika/Zilla Pres -> destination Pres -> Kendra Pres, owner 2026-10-31): rule matrix (Kendra GB member and NSS_ERP_ADMIN direct; non-GB Kendra
admin / scoped admin / Sakha admin -> request; Sakha Asana treated like a Sakha), chain construction incl. fallback + collapse,
step authority by live seat only, reject/cancel, single open request, parent
unchanged while pending, atomic apply + re-validation, supersede, visibility,
non-Sakha re-parenting unchanged.
"""

from uuid import uuid4

import pytest

from api.services.org_reparent_service import collapse_consecutive_kendra_steps
from tests.reparent_support import (
    BASE,
    FAKE_UUID,
    _create_admin_with_scope,
    _create_person_with_login,
    _login_headers,
    _scoped_user,
    _with_sevi_pk,
    create_org,
    create_test_organization,
    decide,
    ensure_gb_body,
    get_request,
    kendra_pks,
    location_pks,
    parent_of,
    patch_parent,
    seat,
)

pytestmark = pytest.mark.integration


# ═══════════════════════════════════════════════════════════════════════
# Pure chain-collapse rule (no DB)
# ═══════════════════════════════════════════════════════════════════════

def _s(is_kendra, reason=None):
    return {"is_kendra": is_kendra, "fallback_reason": reason, "role": "X"}


class TestCollapseRule:
    def test_three_kendra_steps_collapse_to_one(self):
        out = collapse_consecutive_kendra_steps([_s(True, "a"), _s(True, "b"), _s(True)])
        assert len(out) == 1
        assert "a" in out[0]["fallback_reason"] and "b" in out[0]["fallback_reason"]

    def test_trailing_pair_collapses_leading_non_kendra_kept(self):
        assert len(collapse_consecutive_kendra_steps([_s(False), _s(True, "b"), _s(True)])) == 2

    def test_non_consecutive_kendra_steps_are_kept(self):
        assert len(collapse_consecutive_kendra_steps([_s(True, "a"), _s(False), _s(True)])) == 3

    def test_four_step_chain_with_missing_leaving_and_destination_presidents(self):
        """[Sakha ok, leaving K, dest K, final K] -> the three trailing Kendra steps collapse."""
        out = collapse_consecutive_kendra_steps([_s(False), _s(True, "leaving"), _s(True, "dest"), _s(True)])
        assert len(out) == 2 and "leaving" in out[1]["fallback_reason"] and "dest" in out[1]["fallback_reason"]

    def test_leaving_kendra_between_two_real_presidents_is_kept(self):
        out = collapse_consecutive_kendra_steps([_s(False), _s(True, "leaving"), _s(False), _s(True)])
        assert [x["is_kendra"] for x in out] == [False, True, False, True]

    def test_no_fallback_chain_untouched(self):
        assert len(collapse_consecutive_kendra_steps([_s(False), _s(False), _s(True)])) == 3


# ═══════════════════════════════════════════════════════════════════════
# World
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def world(client, write_conn):
    kendra_pk, kendra_body = kendra_pks(write_conn)
    admin = _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_ADMIN", scope_level="NSS-WIDE", organization_pk=None))
    admin_h = _login_headers(client, admin["sangha_sevi_id"], admin["password"])

    # A Kendra admin holding the role through a REAL user_role: global reach
    # but NOT a Governing Body member -> must get no direct re-parent.
    kendra_admin = _with_sevi_pk(write_conn, _create_admin_with_scope(
        write_conn, role_code="NSS_ERP_KENDRA_ADMIN", scope_level="KENDRA", organization_pk=None))

    loc = location_pks(write_conn)
    src = create_org(client, admin_h, loc, "ANCHALIKA_SANGHA", kendra_pk, "RptSrc")
    # A second source Anchalika that never gets a governing body / President:
    # exercises the leaving-parent fallback + Kendra-step collapse.
    src2 = create_org(client, admin_h, loc, "ANCHALIKA_SANGHA", kendra_pk, "RptSrcNoPres")
    # Members must belong to a Sakha (MBR-038A): persons below live in this one.
    home = create_org(client, admin_h, loc, "SAKHA_SANGHA", src, "RptHome")
    dest = create_org(client, admin_h, loc, "ANCHALIKA_SANGHA", kendra_pk, "RptDest")
    other_dest = create_org(client, admin_h, loc, "ZILLA_SANGHA", kendra_pk, "RptZilla")

    # Kendra Governing Body: a President and a (non-President) GB member.
    k_president = _create_person_with_login(write_conn, "KPres", organization_pk=home)
    gb_member = _create_person_with_login(write_conn, "KGbMember", organization_pk=home)
    seat(write_conn, kendra_body, "PRESIDENT", k_president)
    seat(write_conn, kendra_body, "SECRETARY", gb_member)

    # A President seated on the destination Anchalika's governing body.
    dest_body = ensure_gb_body(write_conn, dest, "ANCHALIKA_GOVERNING_BODY")
    dest_president = _create_person_with_login(write_conn, "DestPres", organization_pk=home)
    seat(write_conn, dest_body, "PRESIDENT", dest_president)

    # A President seated on the SOURCE (leaving) Anchalika's governing body.
    src_body = ensure_gb_body(write_conn, src, "ANCHALIKA_GOVERNING_BODY")
    src_president = _create_person_with_login(write_conn, "SrcPres", organization_pk=home)
    seat(write_conn, src_body, "PRESIDENT", src_president)

    def login(u):
        return _login_headers(client, u["sangha_sevi_id"], u["password"])

    return {
        "loc": loc, "kendra_pk": kendra_pk, "kendra_body": kendra_body,
        "src": src, "src2": src2, "home": home, "src_body": src_body, "dest": dest, "other_dest": other_dest, "dest_body": dest_body,
        "admin_h": admin_h,
        "kendra_admin_h": login(kendra_admin),
        # The default REQUESTER in these tests: a global admin that is neither a
        # Kendra GB member nor NSS_ERP_ADMIN, so it always goes through the chain.
        "req_h": login(kendra_admin),
        "gb_h": login(gb_member), "gb_person": gb_member,
        "kpres_h": login(k_president), "kpres_person": k_president,
        "dpres_h": login(dest_president), "dpres_person": dest_president,
        "spres_h": login(src_president), "spres_person": src_president,
    }


def _new_sakha(client, w, write_conn, *, president=None, parent=None):
    """Fresh Sakha under *parent* (default w['src'], the Anchalika WITH a seated
    President; w['src2'] has none) with its auto-created Sakha Governing Body shell;
    optionally seat a fresh Sakha President (returns (sakha_pk, president, headers))."""
    sakha = create_org(client, w["admin_h"], w["loc"], "SAKHA_SANGHA", parent or w["src"], "RptSakha")
    if president is False or president is None:
        return sakha, None, None
    p = _create_person_with_login(write_conn, "SakhaPres", organization_pk=sakha)
    cur = write_conn.cursor()
    cur.execute("""
        SELECT bm.body_master_pk FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY' AND bm.organization_pk = %s
    """, (sakha,))
    seat(write_conn, str(cur.fetchone()[0]), "PRESIDENT", p)
    return sakha, p, _login_headers(client, p["sangha_sevi_id"], p["password"])


FULL_CHAIN = [
    (1, "SAKHA_PRESIDENT"), (2, "SOURCE_PARENT_PRESIDENT"),
    (3, "DEST_PARENT_PRESIDENT"), (4, "KENDRA_PRESIDENT"),
]


def _chain_roles(req):
    return [(s["step_order"], s["step_role"]) for s in req["steps"]]


# ═══════════════════════════════════════════════════════════════════════
# Rule matrix
# ═══════════════════════════════════════════════════════════════════════

class TestRuleMatrix:
    def test_kendra_gb_member_changes_parent_directly(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        r = patch_parent(client, world["gb_h"], sakha, world["dest"])
        assert r.status_code == 200, r.text
        assert r.json()["parent_change_applied"] is True
        assert parent_of(write_conn, sakha) == world["dest"]

    def test_nss_erp_admin_changes_parent_directly(self, client, write_conn, world):
        """The NSS_ERP_ADMIN super administrator is exempt (owner 2026-10-30,
        decided by role) — and supersedes any open request, like a GB member."""
        sakha, _, _ = _new_sakha(client, world, write_conn)
        pending = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        r = patch_parent(client, world["admin_h"], sakha, world["other_dest"])
        assert r.status_code == 200, r.text
        assert r.json()["parent_change_applied"] is True
        assert parent_of(write_conn, sakha) == world["other_dest"]
        after = get_request(client, world["req_h"], pending["organization_reparent_request_pk"])
        assert after["request_status"] == "CANCELLED"

    def test_non_gb_kendra_admin_needs_approval(self, client, write_conn, world):
        """A role-assigned (non-GB) Kendra Administrator gets no exemption."""
        sakha, _, _ = _new_sakha(client, world, write_conn)
        r = patch_parent(client, world["kendra_admin_h"], sakha, world["dest"])
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["parent_change_applied"] is False
        assert body["parent_change_pending_approval"] is True
        assert body["reparent_request"]["request_status"] == "PENDING"
        assert parent_of(write_conn, sakha) == world["src"], "parent must not change while pending"

    def test_scoped_anchalika_admin_needs_approval(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        sa = _with_sevi_pk(write_conn, _create_admin_with_scope(
            write_conn, role_code="NSS_ERP_ANCHALIKA_ADMIN", scope_level="ANCHALIKA",
            organization_pk=world["src"]))
        h = _login_headers(client, sa["sangha_sevi_id"], sa["password"])
        r = patch_parent(client, h, sakha, world["dest"])
        assert r.status_code == 202, r.text
        assert parent_of(write_conn, sakha) == world["src"]

    def test_sakha_admin_needs_approval(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        sa = _scoped_user(write_conn, role_code="NSS_ERP_SAKHA_ADMIN", organization_pk=sakha)
        h = _login_headers(client, sa["sangha_sevi_id"], sa["password"])
        r = patch_parent(client, h, sakha, world["dest"])
        assert r.status_code == 202, r.text
        assert parent_of(write_conn, sakha) == world["src"]

    def test_other_fields_apply_immediately_only_parent_is_deferred(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        r = patch_parent(client, world["req_h"], sakha, world["dest"], organization_name="Renamed By Rule Test")
        assert r.status_code == 202, r.text
        assert r.json()["updated_fields"] == ["organization_name"]
        cur = write_conn.cursor()
        cur.execute("SELECT organization_name FROM nss.organization WHERE organization_pk = %s", (sakha,))
        assert cur.fetchone()[0] == "Renamed By Rule Test"
        assert parent_of(write_conn, sakha) == world["src"]

    def test_non_sakha_reparenting_is_unchanged(self, client, write_conn, world):
        """A SEVAK_SANGHA wing moved between Sakhas by NSS_ERP_ADMIN stays direct (200)."""
        s1, _, _ = _new_sakha(client, world, write_conn)
        s2, _, _ = _new_sakha(client, world, write_conn)
        w = client.post("/api/v1/admin/organizations", headers=world["admin_h"], json={
            "organization_name": "Rpt Sevak", "organization_type_code": "SEVAK_SANGHA",
            "parent_organization_pk": s1,
        })
        assert w.status_code == 201, w.text
        r = patch_parent(client, world["admin_h"], w.json()["organization_pk"], s2)
        assert r.status_code == 200, r.text
        assert parent_of(write_conn, w.json()["organization_pk"]) == s2

    def test_invalid_parent_type_still_422_before_any_request(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        r = patch_parent(client, world["req_h"], sakha, world["kendra_pk"])
        assert r.status_code == 422, r.text

    def test_unknown_parent_404(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        assert patch_parent(client, world["req_h"], sakha, FAKE_UUID).status_code == 404

    def test_second_open_request_is_409_and_rolls_back_other_fields(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        assert patch_parent(client, world["req_h"], sakha, world["dest"]).status_code == 202
        r = patch_parent(client, world["req_h"], sakha, world["other_dest"], organization_name="Should Roll Back")
        assert r.status_code == 409, r.text
        cur = write_conn.cursor()
        cur.execute("SELECT organization_name FROM nss.organization WHERE organization_pk = %s", (sakha,))
        assert cur.fetchone()[0] != "Should Roll Back"


# ═══════════════════════════════════════════════════════════════════════
# Sakha Asana — a Sakha Sangha without its own building: same rule, own GB
# ═══════════════════════════════════════════════════════════════════════

def _new_asana(write_conn, w, *, president=False, parent=None):
    """Fresh SAKHA_ASANA under w['src'] (or *parent*) with its own SAKHA_GOVERNING_BODY shell
    (what seed/08_governance/04_sakha_asana_governing_body_patch.sql gives a
    real one); optionally seat an Asana President."""
    asana = create_test_organization(
        write_conn, name_prefix="RptAsana", type_code="SAKHA_ASANA", parent_pk=parent or w["src"],
        short_code="AS" + uuid4().hex[:6].upper(),
    )
    body = ensure_gb_body(write_conn, asana, "SAKHA_GOVERNING_BODY")
    if not president:
        return asana, None
    p = _create_person_with_login(write_conn, "AsanaPres", organization_pk=asana)
    seat(write_conn, body, "PRESIDENT", p)
    return asana, p


class TestSakhaAsana:
    def test_asana_reparent_needs_approval_for_non_exempt_requester(self, client, write_conn, world):
        asana, _ = _new_asana(write_conn, world)
        r = patch_parent(client, world["req_h"], asana, world["dest"])
        assert r.status_code == 202, r.text
        assert parent_of(write_conn, asana) == world["src"]

    def test_asana_reparent_is_direct_for_gb_member_and_nss_erp_admin(self, client, write_conn, world):
        for who, dest in (("gb_h", world["dest"]), ("admin_h", world["other_dest"])):
            asana, _ = _new_asana(write_conn, world)
            r = patch_parent(client, world[who], asana, dest)
            assert r.status_code == 200, (who, r.text)
            assert parent_of(write_conn, asana) == dest

    def test_asana_step_one_is_its_own_president(self, client, write_conn, world):
        asana, pres = _new_asana(write_conn, world, president=True)
        req = patch_parent(client, world["req_h"], asana, world["dest"]).json()["reparent_request"]
        assert _chain_roles(req) == FULL_CHAIN
        assert req["steps"][0]["assigned_person_pk"] == pres["person_pk"]
        assert req["steps"][0]["fallback_reason"] is None

    def test_asana_vacant_president_falls_back_to_kendra(self, client, write_conn, world):
        asana, _ = _new_asana(write_conn, world)  # GB shell, nobody seated
        req = patch_parent(client, world["req_h"], asana, world["dest"]).json()["reparent_request"]
        first = req["steps"][0]
        assert first["assigned_person_pk"] == world["kpres_person"]["person_pk"]
        assert "no seated President" in first["fallback_reason"]
        assert first["step_status"] == "PENDING", "never auto-approved"

    def test_asana_without_any_governing_body_shell_still_falls_back(self, client, write_conn, world):
        """Defensive: an Asana row the idempotent patch has not reached yet."""
        asana = create_test_organization(
            write_conn, name_prefix="RptAsanaNoGb", type_code="SAKHA_ASANA", parent_pk=world["src"],
            short_code="AN" + uuid4().hex[:6].upper(),
        )
        req = patch_parent(client, world["req_h"], asana, world["dest"]).json()["reparent_request"]
        assert req["steps"][0]["assigned_person_pk"] == world["kpres_person"]["person_pk"]
        assert "no governing body" in req["steps"][0]["fallback_reason"]

    def test_admin_org_list_accepts_repeated_type_code_for_the_assign_tab(self, client, write_conn, world):
        asana, _ = _new_asana(write_conn, world)
        sakha, _, _ = _new_sakha(client, world, write_conn)
        r = client.get(
            "/api/v1/admin/organizations?type_code=SAKHA_SANGHA&type_code=SAKHA_ASANA&page_size=200",
            headers=world["admin_h"],
        )
        assert r.status_code == 200, r.text
        got = {o["organization_pk"]: o["type_code"] for o in r.json()["organizations"]}
        assert got.get(asana) == "SAKHA_ASANA" and got.get(sakha) == "SAKHA_SANGHA"
        assert set(got.values()) <= {"SAKHA_SANGHA", "SAKHA_ASANA"}

    def test_asana_full_approval_applies_parent(self, client, write_conn, world):
        asana, pres = _new_asana(write_conn, world, president=True)
        req = patch_parent(client, world["req_h"], asana, world["dest"]).json()["reparent_request"]
        pres_h = _login_headers(client, pres["sangha_sevi_id"], pres["password"])
        assert decide(client, pres_h, req, 1).status_code == 200
        assert decide(client, world["spres_h"], req, 2).status_code == 200
        assert decide(client, world["dpres_h"], req, 3).status_code == 200
        assert parent_of(write_conn, asana) == world["src"]
        done = decide(client, world["kpres_h"], req, 4)
        assert done.status_code == 200, done.text
        assert done.json()["request_status"] == "APPROVED"
        assert parent_of(write_conn, asana) == world["dest"]


# ═══════════════════════════════════════════════════════════════════════
# Chain construction + fallback
# ═══════════════════════════════════════════════════════════════════════

class TestChain:
    def test_full_four_step_chain(self, client, write_conn, world):
        """Sakha President -> leaving Anchalika/Zilla President -> destination
        Anchalika/Zilla President -> Kendra President (owner 2026-10-31)."""
        sakha, pres, _ = _new_sakha(client, world, write_conn, president=True)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        assert _chain_roles(req) == FULL_CHAIN
        assert [s["assigned_person_pk"] for s in req["steps"]] == [
            pres["person_pk"], world["spres_person"]["person_pk"],
            world["dpres_person"]["person_pk"], world["kpres_person"]["person_pk"],
        ]
        assert req["steps"][1]["assigned_organization_pk"] == world["src"]
        assert req["steps"][2]["assigned_organization_pk"] == world["dest"]
        assert all(s["fallback_reason"] is None for s in req["steps"])

    def test_no_seated_sakha_president_falls_back_to_kendra(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)  # GB shell, nobody seated
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        first = req["steps"][0]
        assert first["step_role"] == "SAKHA_PRESIDENT"
        assert first["assigned_person_pk"] == world["kpres_person"]["person_pk"]
        assert "no seated President" in first["fallback_reason"]
        assert first["step_status"] == "PENDING", "never auto-approved"
        assert [s["step_role"] for s in req["steps"]] == [r for _, r in FULL_CHAIN]

    def test_requester_is_the_sakha_president_falls_back(self, client, write_conn, world):
        sakha, _, pres_h = _new_sakha(client, world, write_conn, president=True)
        req = patch_parent(client, pres_h, sakha, world["dest"]).json()["reparent_request"]
        first = req["steps"][0]
        assert first["assigned_person_pk"] == world["kpres_person"]["person_pk"]
        assert "requester holds the seat" in first["fallback_reason"]

    def test_destination_without_president_and_sakha_without_president_collapse(self, client, write_conn, world):
        """Leaving parent has no governing body -> Kendra; dest has none -> Kendra;
        Sakha has no president -> Kendra; final is Kendra: every consecutive
        Kendra step collapses into ONE."""
        sakha, _, _ = _new_sakha(client, world, write_conn, parent=world["src2"])
        req = patch_parent(client, world["req_h"], sakha, world["other_dest"]).json()["reparent_request"]
        assert _chain_roles(req) == [(1, "KENDRA_PRESIDENT")]
        assert req["steps"][0]["assigned_person_pk"] == world["kpres_person"]["person_pk"]
        assert req["steps"][0]["fallback_reason"]

    def test_sakha_president_then_collapsed_kendra_run(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn, president=True, parent=world["src2"])
        req = patch_parent(client, world["req_h"], sakha, world["other_dest"]).json()["reparent_request"]
        assert _chain_roles(req) == [(1, "SAKHA_PRESIDENT"), (2, "KENDRA_PRESIDENT")]

    def test_source_parent_without_president_falls_back_to_kendra(self, client, write_conn, world):
        """Leaving Anchalika has no governing body: step 2 keeps its role but is
        assigned to the Kendra President with a fallback reason (never skipped)."""
        sakha, pres, _ = _new_sakha(client, world, write_conn, president=True, parent=world["src2"])
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        assert _chain_roles(req) == FULL_CHAIN
        step2 = req["steps"][1]
        assert step2["assigned_person_pk"] == world["kpres_person"]["person_pk"]
        assert "no governing body" in step2["fallback_reason"]
        assert step2["step_status"] == "PENDING", "never auto-approved"

    def test_source_parent_vacant_president_falls_back_to_kendra(self, client, write_conn, world):
        src3 = create_org(client, world["admin_h"], world["loc"], "ANCHALIKA_SANGHA", world["kendra_pk"], "RptSrcVacant")
        ensure_gb_body(write_conn, src3, "ANCHALIKA_GOVERNING_BODY")  # shell, nobody seated
        sakha, _, _ = _new_sakha(client, world, write_conn, president=True, parent=src3)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        step2 = req["steps"][1]
        assert step2["step_role"] == "SOURCE_PARENT_PRESIDENT"
        assert step2["assigned_person_pk"] == world["kpres_person"]["person_pk"]
        assert "no seated President" in step2["fallback_reason"]

    def test_requester_is_the_leaving_parent_president_falls_back(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn, president=True)
        req = patch_parent(client, world["spres_h"], sakha, world["dest"]).json()["reparent_request"]
        step2 = req["steps"][1]
        assert step2["step_role"] == "SOURCE_PARENT_PRESIDENT"
        assert step2["assigned_person_pk"] == world["kpres_person"]["person_pk"]
        assert "requester holds the seat" in step2["fallback_reason"]

    def test_kendra_source_has_no_leaving_parent_step(self, client, write_conn, world):
        """A Sakha still under Kendra (the unassigned flat state) has no leaving
        Anchalika/Zilla: step 2 does not exist (not a fallback)."""
        sakha = create_test_organization(
            write_conn, name_prefix="RptFlat", type_code="SAKHA_SANGHA", parent_pk=world["kendra_pk"],
            short_code="FL" + uuid4().hex[:6].upper(),
        )
        body = ensure_gb_body(write_conn, sakha, "SAKHA_GOVERNING_BODY")
        pres = _create_person_with_login(write_conn, "FlatPres", organization_pk=sakha)
        seat(write_conn, body, "PRESIDENT", pres)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        assert _chain_roles(req) == [
            (1, "SAKHA_PRESIDENT"), (2, "DEST_PARENT_PRESIDENT"), (3, "KENDRA_PRESIDENT"),
        ]
        assert all(s["step_role"] != "SOURCE_PARENT_PRESIDENT" for s in req["steps"])

    def test_zilla_source_uses_zilla_governing_body(self, client, write_conn, world):
        zilla = create_org(client, world["admin_h"], world["loc"], "ZILLA_SANGHA", world["kendra_pk"], "RptSrcZilla")
        zbody = ensure_gb_body(write_conn, zilla, "ZILLA_GOVERNING_BODY")
        zpres = _create_person_with_login(write_conn, "ZillaPres", organization_pk=world["home"])
        seat(write_conn, zbody, "PRESIDENT", zpres)
        sakha, _, _ = _new_sakha(client, world, write_conn, president=True, parent=zilla)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        assert _chain_roles(req) == FULL_CHAIN
        assert req["steps"][1]["assigned_person_pk"] == zpres["person_pk"]
        assert req["steps"][1]["fallback_reason"] is None

    def test_asana_with_vacant_leaving_parent_collapses_like_a_sakha(self, client, write_conn, world):
        asana, _ = _new_asana(write_conn, world, parent=world["src2"])
        req = patch_parent(client, world["req_h"], asana, world["other_dest"]).json()["reparent_request"]
        assert _chain_roles(req) == [(1, "KENDRA_PRESIDENT")]

    def test_naming_the_current_parent_files_no_request(self, client, write_conn, world):
        """Source == destination: not a change, so no chain is built."""
        sakha, _, _ = _new_sakha(client, world, write_conn)
        patch_parent(client, world["req_h"], sakha, world["src"])
        assert client.get(f"{BASE}?sakha_pk={sakha}", headers=world["admin_h"]).json()["total"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Decisions: authority by live seat only; sequencing; apply; reject
# ═══════════════════════════════════════════════════════════════════════

class TestDecisions:
    def _filed(self, client, write_conn, world):
        sakha, pres, pres_h = _new_sakha(client, world, write_conn, president=True)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        return sakha, pres_h, req

    def test_full_approval_applies_parent_only_at_the_end(self, client, write_conn, world):
        sakha, pres_h, req = self._filed(client, write_conn, world)

        r1 = decide(client, pres_h, req, 1)
        assert r1.status_code == 200, r1.text
        assert parent_of(write_conn, sakha) == world["src"]
        rs = decide(client, world["spres_h"], req, 2)
        assert rs.status_code == 200, rs.text
        r2 = decide(client, world["dpres_h"], req, 3)
        assert r2.status_code == 200, r2.text
        assert r2.json()["request_status"] == "PENDING"
        assert parent_of(write_conn, sakha) == world["src"], "still unchanged before the final step"

        r3 = decide(client, world["kpres_h"], req, 4)
        assert r3.status_code == 200, r3.text
        assert r3.json()["request_status"] == "APPROVED"
        assert parent_of(write_conn, sakha) == world["dest"]

    def test_steps_must_be_decided_in_order(self, client, write_conn, world):
        _, _, req = self._filed(client, write_conn, world)
        r = decide(client, world["spres_h"], req, 2)
        assert r.status_code == 422, r.text
        r = decide(client, world["dpres_h"], req, 3)
        assert r.status_code == 422, r.text

    def test_wrong_person_cannot_decide(self, client, write_conn, world):
        _, _, req = self._filed(client, write_conn, world)
        assert decide(client, world["dpres_h"], req, 1).status_code == 403

    def test_admin_and_gb_member_have_no_override(self, client, write_conn, world):
        """No NSS_ERP_ADMIN override, no Kendra-GB-member override: only the
        seat holder decides."""
        _, _, req = self._filed(client, write_conn, world)
        assert decide(client, world["admin_h"], req, 1).status_code == 403
        assert decide(client, world["gb_h"], req, 1).status_code == 403
        assert decide(client, world["kendra_admin_h"], req, 1).status_code == 403

    def test_kendra_president_cannot_skip_ahead(self, client, write_conn, world):
        _, _, req = self._filed(client, write_conn, world)
        assert decide(client, world["kpres_h"], req, 4).status_code == 422

    def test_leaving_and_destination_presidents_cannot_decide_each_others_step(self, client, write_conn, world):
        sakha, pres_h, req = self._filed(client, write_conn, world)
        assert decide(client, pres_h, req, 1).status_code == 200
        assert decide(client, world["dpres_h"], req, 2).status_code == 403
        assert decide(client, world["spres_h"], req, 2).status_code == 200
        assert decide(client, world["spres_h"], req, 3).status_code == 403
        assert decide(client, world["dpres_h"], req, 3).status_code == 200

    def test_leaving_parent_president_can_reject(self, client, write_conn, world):
        sakha, pres_h, req = self._filed(client, write_conn, world)
        assert decide(client, pres_h, req, 1).status_code == 200
        r = decide(client, world["spres_h"], req, 2, "REJECT", "Sakha stays with us")
        assert r.status_code == 200, r.text
        assert r.json()["request_status"] == "REJECTED"
        assert parent_of(write_conn, sakha) == world["src"]

    def test_authority_follows_the_live_seat_not_the_captured_person(self, client, write_conn, world):
        """The Sakha's President is replaced after the request was filed: the
        NEW seat holder decides, the old one no longer can."""
        sakha, old_pres_h, req = self._filed(client, write_conn, world)
        cur = write_conn.cursor()
        cur.execute("""
            SELECT bm.body_master_pk FROM nss.body_master bm
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY' AND bm.organization_pk = %s
        """, (sakha,))
        body = str(cur.fetchone()[0])
        new_pres = _create_person_with_login(write_conn, "NewSakhaPres", organization_pk=sakha)
        seat(write_conn, body, "PRESIDENT", new_pres)
        new_h = _login_headers(client, new_pres["sangha_sevi_id"], new_pres["password"])
        assert decide(client, old_pres_h, req, 1).status_code == 403
        assert decide(client, new_h, req, 1).status_code == 200

    def test_acting_delegate_covering_the_seat_may_decide(self, client, write_conn, world):
        sakha, _, req = self._filed(client, write_conn, world)
        cur = write_conn.cursor()
        cur.execute("""
            SELECT bm.body_master_pk FROM nss.body_master bm
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY' AND bm.organization_pk = %s
        """, (sakha,))
        body = str(cur.fetchone()[0])
        delegate = _create_person_with_login(write_conn, "ActingPres", organization_pk=sakha)
        cur.execute("SELECT position_master_pk FROM nss.position_master WHERE position_code = 'PRESIDENT'")
        pos = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO nss.acting_position_assignment
                (body_master_pk, position_master_pk, person_pk, effective_from, acting_status)
            VALUES (%s, %s, %s, CURRENT_DATE - 1, 'ACTIVE')
        """, (body, str(pos), delegate["person_pk"]))
        h = _login_headers(client, delegate["sangha_sevi_id"], delegate["password"])
        assert decide(client, h, req, 1).status_code == 200

    def test_requester_cannot_decide_own_request(self, client, write_conn, world):
        sakha, _, pres_h = _new_sakha(client, world, write_conn, president=True)
        req = patch_parent(client, pres_h, sakha, world["dest"]).json()["reparent_request"]
        # The Sakha President's own step was re-routed to the Kendra President,
        # but even holding some other seat the requester may never decide.
        assert decide(client, pres_h, req, 1).status_code == 403

    def test_reject_requires_remarks(self, client, write_conn, world):
        _, pres_h, req = self._filed(client, write_conn, world)
        r = decide(client, pres_h, req, 1, "REJECT", None)
        assert r.status_code == 422, r.text

    def test_reject_closes_request_and_parent_is_unchanged(self, client, write_conn, world):
        sakha, pres_h, req = self._filed(client, write_conn, world)
        r = decide(client, pres_h, req, 1, "REJECT", "Not agreed by the Sakha")
        assert r.status_code == 200, r.text
        assert r.json()["request_status"] == "REJECTED"
        assert r.json()["decision_remarks"] == "Not agreed by the Sakha"
        assert parent_of(write_conn, sakha) == world["src"]
        # A closed request admits no further decisions...
        assert decide(client, world["spres_h"], req, 2).status_code == 422
        # ...and frees the Sakha for a new request.
        assert patch_parent(client, world["req_h"], sakha, world["dest"]).status_code == 202

    def test_final_approval_revalidates_target_and_cancels_instead_of_applying(self, client, write_conn, world):
        sakha, pres_h, req = self._filed(client, write_conn, world)
        assert decide(client, pres_h, req, 1).status_code == 200
        assert decide(client, world["spres_h"], req, 2).status_code == 200
        assert decide(client, world["dpres_h"], req, 3).status_code == 200
        cur = write_conn.cursor()
        cur.execute(
            "UPDATE nss.organization SET is_active = FALSE, deleted_at = NOW() WHERE organization_pk = %s",
            (world["dest"],),
        )
        r = decide(client, world["kpres_h"], req, 4)
        assert r.status_code == 200, r.text
        assert r.json()["request_status"] == "CANCELLED"
        assert "could not be applied" in r.json()["decision_remarks"]
        assert parent_of(write_conn, sakha) == world["src"]
        cur.execute(
            "UPDATE nss.organization SET is_active = TRUE, deleted_at = NULL WHERE organization_pk = %s",
            (world["dest"],),
        )


# ═══════════════════════════════════════════════════════════════════════
# Cancel + supersede
# ═══════════════════════════════════════════════════════════════════════

class TestCancel:
    def test_requester_can_cancel_while_pending(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        r = client.post(f"{BASE}/{req['organization_reparent_request_pk']}/cancel", json={}, headers=world["req_h"])
        assert r.status_code == 200, r.text
        assert r.json()["request_status"] == "CANCELLED"
        assert parent_of(write_conn, sakha) == world["src"]
        # cancelled -> cannot be cancelled again
        again = client.post(f"{BASE}/{req['organization_reparent_request_pk']}/cancel", json={}, headers=world["req_h"])
        assert again.status_code == 422

    def test_kendra_gb_member_can_cancel_anyones_request(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        r = client.post(f"{BASE}/{req['organization_reparent_request_pk']}/cancel", json={}, headers=world["gb_h"])
        assert r.status_code == 200, r.text

    def test_unrelated_person_cannot_cancel(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        r = client.post(f"{BASE}/{req['organization_reparent_request_pk']}/cancel", json={}, headers=world["dpres_h"])
        assert r.status_code in (403, 404), r.text

    def test_cancel_unknown_request_404(self, client, world):
        assert client.post(f"{BASE}/{FAKE_UUID}/cancel", json={}, headers=world["admin_h"]).status_code == 404

    def test_direct_gb_change_supersedes_open_request(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        assert patch_parent(client, world["gb_h"], sakha, world["other_dest"]).status_code == 200
        after = get_request(client, world["req_h"], req["organization_reparent_request_pk"])
        assert after["request_status"] == "CANCELLED"
        assert parent_of(write_conn, sakha) == world["other_dest"]


# ═══════════════════════════════════════════════════════════════════════
# Reads: list filters, visibility, auth model
# ═══════════════════════════════════════════════════════════════════════

class TestReads:
    def test_requires_login(self, client):
        assert client.get(BASE).status_code in (401, 403)
        assert client.get(f"{BASE}/{FAKE_UUID}").status_code in (401, 403)
        assert client.post(f"{BASE}/{FAKE_UUID}/cancel", json={}).status_code in (401, 403)
        assert client.post(
            f"{BASE}/{FAKE_UUID}/steps/{FAKE_UUID}/decide", json={"decision": "APPROVE"}
        ).status_code in (401, 403)

    def test_list_filters_by_sakha_status_and_mine(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        r = client.get(f"{BASE}?sakha_pk={sakha}&request_status=PENDING", headers=world["req_h"])
        assert r.status_code == 200, r.text
        assert [i["organization_reparent_request_pk"] for i in r.json()["items"]] == [
            req["organization_reparent_request_pk"]
        ]
        mine = client.get(f"{BASE}?mine=true&sakha_pk={sakha}", headers=world["req_h"]).json()
        assert mine["total"] == 1
        not_mine = client.get(f"{BASE}?mine=true&sakha_pk={sakha}", headers=world["dpres_h"]).json()
        assert not_mine["total"] == 0

    def test_bad_status_filter_422(self, client, world):
        assert client.get(f"{BASE}?request_status=NOPE", headers=world["admin_h"]).status_code == 422

    def test_awaiting_my_decision_lists_only_the_actionable_step_holder(self, client, write_conn, world):
        sakha, _, pres_h = _new_sakha(client, world, write_conn, president=True)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        pk = req["organization_reparent_request_pk"]

        def awaiting(h):
            data = client.get(f"{BASE}?awaiting_my_decision=true&sakha_pk={sakha}", headers=h).json()
            return [i["organization_reparent_request_pk"] for i in data["items"]]

        assert awaiting(pres_h) == [pk]
        assert awaiting(world["spres_h"]) == [], "step 2 is not actionable until step 1 is approved"
        assert awaiting(world["dpres_h"]) == []
        assert awaiting(world["admin_h"]) == [], "no NSS_ERP_ADMIN override when deciding"
        assert decide(client, pres_h, req, 1).status_code == 200
        assert awaiting(world["spres_h"]) == [pk]
        assert awaiting(world["dpres_h"]) == [], "destination President waits for the leaving President"
        assert awaiting(pres_h) == []

    def test_viewer_flags(self, client, write_conn, world):
        sakha, _, pres_h = _new_sakha(client, world, write_conn, president=True)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        pk = req["organization_reparent_request_pk"]
        as_pres = get_request(client, pres_h, pk)
        assert as_pres["steps"][0]["viewer_can_decide"] is True
        assert as_pres["viewer_can_cancel"] is False
        as_requester = get_request(client, world["req_h"], pk)
        assert all(s["viewer_can_decide"] is False for s in as_requester["steps"])
        assert as_requester["viewer_can_cancel"] is True
        # NSS_ERP_ADMIN is exempt from approval: it may cancel, but never decide.
        as_admin = get_request(client, world["admin_h"], pk)
        assert all(s["viewer_can_decide"] is False for s in as_admin["steps"])
        assert as_admin["viewer_can_cancel"] is True

    def test_unrelated_member_cannot_see_request(self, client, write_conn, world):
        sakha, _, _ = _new_sakha(client, world, write_conn)
        req = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"]
        stranger = _create_person_with_login(write_conn, "Stranger", organization_pk=world["home"])
        h = _login_headers(client, stranger["sangha_sevi_id"], stranger["password"])
        pk = req["organization_reparent_request_pk"]
        assert client.get(f"{BASE}/{pk}", headers=h).status_code == 404
        assert client.get(f"{BASE}?sakha_pk={sakha}", headers=h).json()["total"] == 0

    def test_approver_and_gb_member_can_see_request(self, client, write_conn, world):
        sakha, _, pres_h = _new_sakha(client, world, write_conn, president=True)
        pk = patch_parent(client, world["req_h"], sakha, world["dest"]).json()["reparent_request"][
            "organization_reparent_request_pk"]
        for h in (pres_h, world["spres_h"], world["dpres_h"], world["kpres_h"], world["gb_h"]):
            assert client.get(f"{BASE}/{pk}", headers=h).status_code == 200
