"""
Family authorization — the OWNERSHIP path.

Why this file exists separately from test_family.py
---------------------------------------------------
Every test in test_family.py authenticates through `authed_client`, an admin
token carrying FAMILY_VIEW/FAMILY_MANAGE. Those requests short-circuit on the
permission override in the very first line of each `_require_family_*` helper
and never touch an ownership check. A green test_family.py therefore proves
nothing about the rule the project actually depends on:

    an ordinary member holds NO role and therefore NO permissions, and reaches
    their own family purely through their RELATIONSHIP to it.

This file builds real role-less members — person + sangha_sevi + ACTIVE
user_account with no row in nss.user_role — mints genuine JWTs for them via
POST /api/v1/auth/login, and asserts the four properties that matter:

  1. A role-less member CAN read their own family.            (the regression)
  2. A role-less non-member CANNOT read that family.          (privacy)
  3. The head CAN add a member.                               (ownership write)
  4. A plain member (not head, not admin) CANNOT add a member. (the tightening)

Property 4 is the behaviour change the user asked for: add/remove used to
accept any current member of the family; it now requires head or family admin.

Authorization model under test (api/routers/family.py, section 0):

  | Action                              | Who                                |
  |-------------------------------------|------------------------------------|
  | View one family                     | current member, or FAMILY_VIEW     |
  | Add / remove member, create link    | head or family admin, or FAMILY_MANAGE |
  | Assign admin, transfer headship     | head only, or FAMILY_MANAGE        |
  | Browse ALL families                 | FAMILY_VIEW only                   |
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.main import app

# Password forced onto every throwaway account in this module. The rows are
# created inside the module savepoint and rolled back, so this never persists.
_MEMBER_PASSWORD = "FamilyOwner1x"

FAKE_PK = "00000000-0000-0000-0000-000000000000"


# ── Infrastructure ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sakha_pk(write_conn):
    """PK of any active Sakha Sangha — families must be registered under one."""
    with write_conn.cursor() as cur:
        cur.execute("""
            SELECT o.organization_pk
            FROM   nss.organization o
            JOIN   nss.master_data md
                   ON md.master_data_pk = o.organization_type_master_data_pk
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  mc.category_code = 'ORGANIZATION_TYPE'
              AND  md.value_code = 'SAKHA_SANGHA'
              AND  o.is_active = TRUE
            LIMIT  1
        """)
        row = cur.fetchone()
    if row is None:
        pytest.skip("No active Sakha Sangha in the database.")
    return str(row[0])


@pytest.fixture(scope="module")
def make_roleless_member(write_conn, _override_deps):
    """
    Factory producing a genuinely role-less member: nss.person +
    nss.sangha_sevi + ACTIVE nss.user_account, and deliberately NO
    nss.user_role row.

    Returns a dict with `person_pk`, `sangha_sevi_id` and `client` — a
    TestClient carrying that member's own Bearer token.

    The token is real, minted through the login endpoint, so it carries
    exactly the permission set the RBAC service computes for someone with no
    role: the empty set. That is the whole point — a hand-built UserContext
    would let a bug in role resolution hide.

    Plain TestClient(app), not a `with` block: the `with` form fires the
    app's lifespan shutdown (close_pool()) on exit and would close the
    connection the whole session shares.
    """
    # Resolve the master data every sangha_sevi row needs, once. The
    # membership STATUS column points at the shared STATUS category (see
    # api.helpers.get_active_status_pk), not at a membership-specific one.
    with write_conn.cursor() as cur:
        cur.execute("""
            SELECT md.value_code, md.master_data_pk
            FROM   nss.master_data md
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  md.is_active = TRUE
              AND ((mc.category_code = 'MEMBERSHIP_TYPE' AND md.value_code = 'REGULAR')
                OR (mc.category_code = 'STATUS'          AND md.value_code = 'ACTIVE'))
        """)
        md = {code: str(pk) for code, pk in cur.fetchall()}
    for key in ("REGULAR", "ACTIVE"):
        if key not in md:
            pytest.skip(f"Master data {key} missing; cannot build a member.")

    from api.services.auth_service import hash_password

    password_hash = hash_password(_MEMBER_PASSWORD)
    created = []

    def _make(org_pk):
        suffix = uuid4().hex[:10].upper()
        with write_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nss.person (person_id, first_name, last_name, email)
                VALUES (%s, %s, %s, %s)
                RETURNING person_pk
            """, (
                f"TFO{suffix}",
                "TestFamilyOwner",
                suffix,
                f"tfo.{suffix.lower()}@example.test",
            ))
            person_pk = str(cur.fetchone()[0])

            sevi_id = f"TFO{suffix}"
            cur.execute("""
                INSERT INTO nss.sangha_sevi
                    (sangha_sevi_id, person_pk,
                     membership_type_master_data_pk,
                     membership_status_master_data_pk,
                     organization_pk, joining_date)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                sevi_id, person_pk, md["REGULAR"], md["ACTIVE"],
                org_pk, "2024-04-01",
            ))

            # ACTIVE account, no role. This is exactly what the claim-approval
            # flow produces for an ordinary member.
            cur.execute("""
                INSERT INTO nss.user_account
                    (person_pk, password_hash, account_status,
                     force_password_change, password_changed_at,
                     password_expires_at)
                VALUES (%s, %s, 'ACTIVE', FALSE,
                        NOW(), NOW() + INTERVAL '365 days')
            """, (person_pk, password_hash))

        login = TestClient(app)
        resp = login.post(
            "/api/v1/auth/login",
            json={"login_id": sevi_id, "password": _MEMBER_PASSWORD},
        )
        if resp.status_code != 200:
            pytest.skip(
                f"Role-less member login failed: {resp.status_code} {resp.text}"
            )
        token = resp.json()["access_token"]

        c = TestClient(app)
        c.headers.update({"Authorization": f"Bearer {token}"})

        member = {
            "person_pk": person_pk,
            "sangha_sevi_id": sevi_id,
            "client": c,
        }
        created.append(member)
        return member

    return _make


@pytest.fixture(scope="module")
def family_of_head(make_roleless_member, sakha_pk):
    """
    A family created by a role-less member via the public endpoint.

    Creating it through POST /families rather than raw SQL is deliberate: it
    proves self-service family creation works without FAMILY_MANAGE, and it
    lets the endpoint establish the SELF relationship and head_history rows
    the ownership helpers read.
    """
    head = make_roleless_member(sakha_pk)
    resp = head["client"].post(
        "/api/v1/family/families",
        json={
            "family_name": f"Ownership Test Paribara {uuid4().hex[:6]}",
            "sakha_organization_pk": sakha_pk,
        },
    )
    assert resp.status_code == 201, (
        "A role-less member must be able to create their own family "
        f"(self-service, no FAMILY_MANAGE). Got {resp.status_code}: {resp.text}"
    )
    return {"head": head, "family_pk": resp.json()["family_group_pk"]}


# ── 1. A role-less member can read their own family ────────────────────────

class TestRolelessMemberReadsOwnFamily:
    """
    The regression this whole change exists to prevent: gating the family
    reads on FAMILY_VIEW alone would 403 every ordinary member out of their
    own family tree, because no seeded role is a plain 'member' role and
    nothing in the registration or claim-approval flow grants one.
    """

    def test_member_holds_no_permissions(self, family_of_head):
        """
        Guard on the premise. If this member somehow acquired permissions,
        every other assertion in this file would pass through the override
        and prove nothing.
        """
        resp = family_of_head["head"]["client"].get("/api/v1/auth/me")
        assert resp.status_code == 200, resp.text
        perms = resp.json().get("permissions") or []
        assert perms == [], (
            "The test member must hold zero permissions for the ownership "
            f"path to be under test; got {perms}"
        )

    def test_head_can_read_own_family_detail(self, family_of_head):
        resp = family_of_head["head"]["client"].get(
            f"/api/v1/family/families/{family_of_head['family_pk']}"
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["family_group_pk"] == family_of_head["family_pk"]

    def test_head_can_read_own_family_members(self, family_of_head):
        resp = family_of_head["head"]["client"].get(
            f"/api/v1/family/families/{family_of_head['family_pk']}/members"
        )
        assert resp.status_code == 200, resp.text
        pks = [m["person_pk"] for m in resp.json()]
        assert family_of_head["head"]["person_pk"] in pks

    def test_head_can_read_own_family_graph(self, family_of_head):
        """
        The graph endpoint takes viewer_person_pk as a query parameter — it
        derives kinship labels relative to a viewer. That parameter is NOT
        the authorization subject: authorization still comes from the token.
        """
        resp = family_of_head["head"]["client"].get(
            f"/api/v1/family/families/{family_of_head['family_pk']}/graph",
            params={"viewer_person_pk": family_of_head["head"]["person_pk"]},
        )
        assert resp.status_code == 200, resp.text

    def test_head_can_read_own_head_history(self, family_of_head):
        resp = family_of_head["head"]["client"].get(
            f"/api/v1/family/families/{family_of_head['family_pk']}/head-history"
        )
        assert resp.status_code == 200, resp.text
        current = [h for h in resp.json() if h.get("effective_to") is None]
        assert len(current) == 1
        assert current[0]["person_pk"] == family_of_head["head"]["person_pk"]

    def test_member_can_read_own_person_families(self, family_of_head):
        """The dashboard's entry point: 'which family am I in?'"""
        person_pk = family_of_head["head"]["person_pk"]
        resp = family_of_head["head"]["client"].get(
            f"/api/v1/family/person/{person_pk}/families"
        )
        assert resp.status_code == 200, resp.text
        assert any(
            f["family_group_pk"] == family_of_head["family_pk"]
            for f in resp.json()
        )


# ── 2. A role-less non-member cannot read that family ──────────────────────

class TestRolelessOutsiderIsRefused:
    """
    Ownership must cut both ways. The reads had NO ownership check before
    this change — they relied entirely on FAMILY_VIEW. Simply dropping that
    gate so members could get in would have let any authenticated member
    read EVERY family in the organisation.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def outsider(make_roleless_member, sakha_pk):
        return make_roleless_member(sakha_pk)

    def test_outsider_cannot_read_family_detail(self, outsider, family_of_head):
        resp = outsider["client"].get(
            f"/api/v1/family/families/{family_of_head['family_pk']}"
        )
        assert resp.status_code == 403, resp.text

    def test_outsider_cannot_read_family_members(self, outsider, family_of_head):
        resp = outsider["client"].get(
            f"/api/v1/family/families/{family_of_head['family_pk']}/members"
        )
        assert resp.status_code == 403, resp.text

    def test_outsider_cannot_read_another_persons_families(
        self, outsider, family_of_head
    ):
        resp = outsider["client"].get(
            "/api/v1/family/person/"
            f"{family_of_head['head']['person_pk']}/families"
        )
        assert resp.status_code == 403, resp.text

    def test_outsider_cannot_browse_all_families(self, outsider):
        """
        The org-level family browser stays permission-gated (FAMILY_VIEW).
        It is the one family endpoint with no ownership interpretation —
        'all families' is not anybody's own family.
        """
        resp = outsider["client"].get("/api/v1/family/families")
        assert resp.status_code == 403, resp.text

    def test_viewer_person_pk_does_not_bypass_the_gate(
        self, outsider, family_of_head
    ):
        """
        The graph endpoint takes viewer_person_pk as a query parameter. A
        caller-supplied parameter must never become the authorization subject:
        passing a genuine member's PK must not let an outsider in. The gate
        reads the token, not the query string.
        """
        resp = outsider["client"].get(
            f"/api/v1/family/families/{family_of_head['family_pk']}/graph",
            params={"viewer_person_pk": family_of_head["head"]["person_pk"]},
        )
        assert resp.status_code == 403, resp.text

    def test_nonexistent_family_still_404s_for_a_member(self, family_of_head):
        """
        404-before-403 ordering is preserved where require_entity already ran
        first, so a missing family does not leak its absence as a 403.
        """
        resp = family_of_head["head"]["client"].get(
            f"/api/v1/family/families/{FAKE_PK}/members"
        )
        assert resp.status_code == 404, resp.text


# ── 3 & 4. Writes: head/admin yes, plain member no ─────────────────────────

class TestMembershipWritesRequireHeadOrAdmin:
    """
    The tightening. Before this change add_family_member and
    create_family_link accepted ANY current member of the family, via an
    inlined raw-SQL check. The rule is now head or family admin.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def added_member(family_of_head, make_roleless_member, sakha_pk):
        """
        A plain member: added to the family by the head, so genuinely a
        current member — but neither head nor family admin.
        """
        plain = make_roleless_member(sakha_pk)
        resp = family_of_head["head"]["client"].post(
            f"/api/v1/family/families/{family_of_head['family_pk']}/members",
            json={
                "person_pk": plain["person_pk"],
                "relationship_type_code": "SON",
            },
        )
        # Property 3: the head — holding no permission at all — can write.
        assert resp.status_code == 201, (
            "The family head must be able to add a member without "
            f"FAMILY_MANAGE. Got {resp.status_code}: {resp.text}"
        )
        return plain

    def test_added_member_can_now_read_the_family(
        self, added_member, family_of_head
    ):
        """Ownership is live, not cached: membership grants read immediately."""
        resp = added_member["client"].get(
            f"/api/v1/family/families/{family_of_head['family_pk']}/members"
        )
        assert resp.status_code == 200, resp.text

    def test_plain_member_cannot_add_a_member(
        self, added_member, family_of_head, make_roleless_member, sakha_pk
    ):
        """
        THE tightening. A current member who is not head and not a family
        admin must be refused — this is exactly what used to be allowed.
        """
        outsider = make_roleless_member(sakha_pk)
        resp = added_member["client"].post(
            f"/api/v1/family/families/{family_of_head['family_pk']}/members",
            json={
                "person_pk": outsider["person_pk"],
                "relationship_type_code": "SON",
            },
        )
        assert resp.status_code == 403, (
            "A plain family member must NOT be able to add members. "
            f"Got {resp.status_code}: {resp.text}"
        )

    def test_plain_member_cannot_remove_a_member(
        self, added_member, family_of_head
    ):
        resp = added_member["client"].request(
            "DELETE",
            f"/api/v1/family/families/{family_of_head['family_pk']}/members",
            json={"person_pk": family_of_head["head"]["person_pk"]},
        )
        assert resp.status_code == 403, resp.text

    def test_outsider_cannot_add_a_member(
        self, family_of_head, make_roleless_member, sakha_pk
    ):
        stranger = make_roleless_member(sakha_pk)
        resp = stranger["client"].post(
            f"/api/v1/family/families/{family_of_head['family_pk']}/members",
            json={
                "person_pk": stranger["person_pk"],
                "relationship_type_code": "SON",
            },
        )
        assert resp.status_code == 403, resp.text


# ── 5. Head-only actions ───────────────────────────────────────────────────

class TestHeadOnlyActions:
    """
    Appointing family admins and transferring headship are head-only
    (FAM-046, FAM-050). A family admin — who CAN change membership — must
    not be able to appoint further admins or hand over the headship.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def family_with_admin(family_of_head, make_roleless_member, sakha_pk):
        """A second member, added then appointed family admin by the head."""
        admin = make_roleless_member(sakha_pk)
        fam = family_of_head["family_pk"]
        head_client = family_of_head["head"]["client"]

        add = head_client.post(
            f"/api/v1/family/families/{fam}/members",
            json={
                "person_pk": admin["person_pk"],
                "relationship_type_code": "SON",
            },
        )
        assert add.status_code == 201, add.text

        # Property: the head can appoint an admin with no permissions at all.
        appoint = head_client.post(
            f"/api/v1/family/families/{fam}/admins",
            json={"person_pk": admin["person_pk"]},
        )
        assert appoint.status_code in (200, 201), (
            "The family head must be able to appoint a family admin without "
            f"FAMILY_MANAGE. Got {appoint.status_code}: {appoint.text}"
        )
        return {"admin": admin, "family_pk": fam}

    def test_family_admin_can_add_a_member(
        self, family_with_admin, make_roleless_member, sakha_pk
    ):
        """A family admin holds the membership-changing authority."""
        newcomer = make_roleless_member(sakha_pk)
        resp = family_with_admin["admin"]["client"].post(
            f"/api/v1/family/families/{family_with_admin['family_pk']}/members",
            json={
                "person_pk": newcomer["person_pk"],
                "relationship_type_code": "DAUGHTER",
            },
        )
        assert resp.status_code == 201, (
            "A family admin must be able to add members. "
            f"Got {resp.status_code}: {resp.text}"
        )

    def test_family_admin_cannot_appoint_another_admin(
        self, family_with_admin, family_of_head
    ):
        resp = family_with_admin["admin"]["client"].post(
            f"/api/v1/family/families/{family_with_admin['family_pk']}/admins",
            json={"person_pk": family_of_head["head"]["person_pk"]},
        )
        assert resp.status_code == 403, (
            "Appointing family admins is head-only. "
            f"Got {resp.status_code}: {resp.text}"
        )

    def test_family_admin_cannot_transfer_headship(self, family_with_admin):
        resp = family_with_admin["admin"]["client"].post(
            f"/api/v1/family/families/{family_with_admin['family_pk']}"
            "/transfer-head",
            json={
                "person_pk": family_with_admin["admin"]["person_pk"],
                "remarks": "Attempted self-promotion",
            },
        )
        assert resp.status_code == 403, (
            "Transferring headship is head-only. "
            f"Got {resp.status_code}: {resp.text}"
        )

    def test_family_admin_can_still_read_the_family(self, family_with_admin):
        resp = family_with_admin["admin"]["client"].get(
            f"/api/v1/family/families/{family_with_admin['family_pk']}/admins"
        )
        assert resp.status_code == 200, resp.text


# ═══════════════════════════════════════════════════════════════════════════
# Coverage additions (endpoint x test matrix audit)
#
# Everything below reuses make_roleless_member / sakha_pk / family_of_head.
# Each write-heavy class builds its OWN family through `new_family` so that
# mutating the head (transfer-head, remove, move-between-families) can never
# change the premise of the read-only classes above.
# ═══════════════════════════════════════════════════════════════════════════

FAMILY = "/api/v1/family"


@pytest.fixture(scope="module")
def new_family(make_roleless_member, sakha_pk):
    """Factory: a brand-new family created by a brand-new role-less head."""

    def _make():
        head = make_roleless_member(sakha_pk)
        resp = head["client"].post(
            f"{FAMILY}/families",
            json={
                "family_name": f"Matrix Paribara {uuid4().hex[:6]}",
                "sakha_organization_pk": sakha_pk,
            },
        )
        assert resp.status_code == 201, resp.text
        return {"head": head, "family_pk": resp.json()["family_group_pk"]}

    return _make


def _add_member(family, person, relationship="SON", **extra):
    """Head adds `person` (a make_roleless_member dict); returns the response."""
    return family["head"]["client"].post(
        f"{FAMILY}/families/{family['family_pk']}/members",
        json={
            "person_pk": person["person_pk"],
            "relationship_type_code": relationship,
            **extra,
        },
    )


def _authed_has(authed_client, permission):
    me = authed_client.get("/api/v1/auth/me")
    return me.status_code == 200 and permission in (me.json().get("permissions") or [])


# ── GET /person/{pk}/membership-summary (previously had NO coverage) ───────

class TestPersonMembershipSummary:
    """
    GET /api/v1/family/person/{person_pk}/membership-summary

    Gate: get_current_user + _require_person_family_view — self, a current
    relative (shares a current family), or FAMILY_VIEW.
    """

    _EMPTY_FIELDS = (
        "sangha_sevi_id", "sangha_sevi_pk", "membership_type_code",
        "membership_type_name", "status_code", "status_name",
        "organization_name", "local_sakha_erp_id",
        "parichaya_patra_number", "parichaya_patra_status",
        "parichaya_patra_valid_to", "anumati_patra_number",
        "anumati_patra_status", "anumati_patra_valid_to",
    )

    @staticmethod
    @pytest.fixture(scope="class")
    def fam(new_family, make_roleless_member, sakha_pk):
        """A family with a head and one added relative."""
        family = new_family()
        relative = make_roleless_member(sakha_pk)
        assert _add_member(family, relative).status_code == 201
        return {**family, "relative": relative}

    @staticmethod
    def _url(person_pk):
        return f"{FAMILY}/person/{person_pk}/membership-summary"

    def _sevi_pk(self, write_conn, person_pk):
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT sangha_sevi_pk FROM nss.sangha_sevi "
                "WHERE person_pk = %s AND is_active = TRUE",
                (person_pk,),
            )
            return str(cur.fetchone()[0])

    # -- 401 / 422 ---------------------------------------------------------

    def test_requires_authentication(self, anon_client):
        assert anon_client.get(self._url(FAKE_PK)).status_code == 401

    def test_bad_uuid_returns_422(self, fam):
        resp = fam["head"]["client"].get(self._url("not-a-uuid"))
        assert resp.status_code == 422, resp.text

    # -- self --------------------------------------------------------------

    def test_self_gets_own_membership_snapshot(self, fam):
        head = fam["head"]
        resp = head["client"].get(self._url(head["person_pk"]))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body) == set(self._EMPTY_FIELDS)
        assert body["sangha_sevi_id"] == head["sangha_sevi_id"]
        assert body["membership_type_code"] == "REGULAR"
        assert body["status_code"] == "ACTIVE"
        assert body["organization_name"]
        # No credential issued yet -> None, never a missing key / error.
        assert body["parichaya_patra_number"] is None
        assert body["anumati_patra_number"] is None

    # -- relatives (ownership model) ---------------------------------------

    def test_relative_can_read_heads_summary(self, fam):
        resp = fam["relative"]["client"].get(self._url(fam["head"]["person_pk"]))
        assert resp.status_code == 200, resp.text
        assert resp.json()["sangha_sevi_id"] == fam["head"]["sangha_sevi_id"]

    def test_head_can_read_relatives_summary(self, fam):
        resp = fam["head"]["client"].get(self._url(fam["relative"]["person_pk"]))
        assert resp.status_code == 200, resp.text
        assert resp.json()["sangha_sevi_id"] == fam["relative"]["sangha_sevi_id"]

    def test_unrelated_member_is_refused(self, fam, make_roleless_member, sakha_pk):
        stranger = make_roleless_member(sakha_pk)
        resp = stranger["client"].get(self._url(fam["head"]["person_pk"]))
        assert resp.status_code == 403, resp.text

    def test_unknown_person_is_404_for_role_less_caller(self, fam):
        """Existence is checked before authorization (as on every family
        endpoint): an unknown person is 404 for any authenticated caller."""
        resp = fam["head"]["client"].get(self._url(FAKE_PK))
        assert resp.status_code == 404, resp.text

    def test_removed_relative_loses_access(
        self, new_family, make_roleless_member, sakha_pk
    ):
        family = new_family()
        relative = make_roleless_member(sakha_pk)
        assert _add_member(family, relative).status_code == 201
        url = self._url(family["head"]["person_pk"])
        assert relative["client"].get(url).status_code == 200
        removal = family["head"]["client"].request(
            "DELETE",
            f"{FAMILY}/families/{family['family_pk']}/members",
            json={"person_pk": relative["person_pk"]},
        )
        assert removal.status_code == 200, removal.text
        assert relative["client"].get(url).status_code == 403

    # -- FAMILY_VIEW override: empty (not 404) shapes ----------------------

    def test_admin_gets_empty_summary_for_person_without_membership(
        self, authed_client, write_conn
    ):
        if not _authed_has(authed_client, "FAMILY_VIEW"):
            pytest.skip("authed_client does not hold FAMILY_VIEW.")
        suffix = uuid4().hex[:10].upper()
        with write_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO nss.person (person_id, first_name, last_name, email) "
                "VALUES (%s, 'NoMembership', %s, %s) RETURNING person_pk",
                (f"TNM{suffix}", suffix, f"tnm.{suffix.lower()}@example.test"),
            )
            person_pk = str(cur.fetchone()[0])
        resp = authed_client.get(self._url(person_pk))
        assert resp.status_code == 200, resp.text
        assert all(resp.json()[f] is None for f in self._EMPTY_FIELDS)

    def test_unknown_person_is_404_even_with_family_view(self, authed_client):
        """'Empty, not 404' applies only to an EXISTING person without a
        membership record; an unknown person_pk is a 404."""
        if not _authed_has(authed_client, "FAMILY_VIEW"):
            pytest.skip("authed_client does not hold FAMILY_VIEW.")
        resp = authed_client.get(self._url(FAKE_PK))
        assert resp.status_code == 404, resp.text

    def test_inactive_membership_is_reported_as_empty(
        self, authed_client, write_conn, make_roleless_member, sakha_pk
    ):
        if not _authed_has(authed_client, "FAMILY_VIEW"):
            pytest.skip("authed_client does not hold FAMILY_VIEW.")
        member = make_roleless_member(sakha_pk)
        with write_conn.cursor() as cur:
            cur.execute(
                "UPDATE nss.sangha_sevi SET is_active = FALSE, deleted_at = CURRENT_TIMESTAMP WHERE person_pk = %s",
                (member["person_pk"],),
            )
        resp = authed_client.get(self._url(member["person_pk"]))
        assert resp.status_code == 200, resp.text
        assert resp.json()["sangha_sevi_id"] is None

    # -- credentials -------------------------------------------------------

    def test_latest_credentials_are_reported(self, fam, write_conn, sakha_pk):
        head = fam["head"]
        sevi_pk = self._sevi_pk(write_conn, head["person_pk"])
        suffix = uuid4().hex[:8].upper()
        with write_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nss.parichaya_patra
                    (sangha_sevi_pk, document_number, issue_date,
                     valid_from, valid_to, status)
                VALUES (%s, %s, CURRENT_DATE, CURRENT_DATE,
                        CURRENT_DATE + INTERVAL '1 year', 'ACTIVE')
                """,
                (sevi_pk, f"TPP-{suffix}"),
            )
            cur.execute(
                """
                INSERT INTO nss.anumati_patra
                    (sangha_sevi_pk, issuing_organization_pk, document_number,
                     issue_date, valid_from, valid_to, status)
                VALUES (%s, %s, %s, CURRENT_DATE, CURRENT_DATE,
                        CURRENT_DATE + INTERVAL '1 year', 'ACTIVE')
                """,
                (sevi_pk, sakha_pk, f"TAP-{suffix}"),
            )
        body = head["client"].get(self._url(head["person_pk"])).json()
        assert body["parichaya_patra_number"] == f"TPP-{suffix}"
        assert body["parichaya_patra_status"] == "ACTIVE"
        assert body["parichaya_patra_valid_to"]
        assert body["anumati_patra_number"] == f"TAP-{suffix}"
        assert body["anumati_patra_status"] == "ACTIVE"

    def test_associate_never_reports_an_anumati_patra(
        self, new_family, write_conn, sakha_pk
    ):
        """MBR-019A/B: Associate members hold a Parichaya Patra but no
        Anumati Patra — even if a stray anumati_patra row exists."""
        family = new_family()
        head = family["head"]
        with write_conn.cursor() as cur:
            cur.execute(
                """
                SELECT md.master_data_pk FROM nss.master_data md
                JOIN nss.master_category mc
                  ON mc.master_category_pk = md.master_category_pk
                WHERE mc.category_code = 'MEMBERSHIP_TYPE'
                  AND md.value_code = 'ASSOCIATE' AND md.is_active = TRUE
                """
            )
            row = cur.fetchone()
        if row is None:
            pytest.skip("ASSOCIATE membership type not seeded.")
        sevi_pk = self._sevi_pk(write_conn, head["person_pk"])
        suffix = uuid4().hex[:8].upper()
        with write_conn.cursor() as cur:
            cur.execute(
                "UPDATE nss.sangha_sevi SET membership_type_master_data_pk = %s "
                "WHERE sangha_sevi_pk = %s",
                (str(row[0]), sevi_pk),
            )
            cur.execute(
                """
                INSERT INTO nss.parichaya_patra
                    (sangha_sevi_pk, document_number, issue_date,
                     valid_from, valid_to, status)
                VALUES (%s, %s, CURRENT_DATE, CURRENT_DATE,
                        CURRENT_DATE + INTERVAL '1 year', 'ACTIVE')
                """,
                (sevi_pk, f"TPA-{suffix}"),
            )
            cur.execute(
                """
                INSERT INTO nss.anumati_patra
                    (sangha_sevi_pk, issuing_organization_pk, document_number,
                     issue_date, valid_from, valid_to, status)
                VALUES (%s, %s, %s, CURRENT_DATE, CURRENT_DATE,
                        CURRENT_DATE + INTERVAL '1 year', 'ACTIVE')
                """,
                (sevi_pk, sakha_pk, f"TAA-{suffix}"),
            )
        body = head["client"].get(self._url(head["person_pk"])).json()
        assert body["membership_type_code"] == "ASSOCIATE"
        assert body["parichaya_patra_number"] == f"TPA-{suffix}"
        assert body["anumati_patra_number"] is None


# ── Outsider (403) coverage for the family endpoints not covered above ─────

class TestOutsiderRefusedOnRemainingFamilyEndpoints:
    """
    The first outsider class covers detail/members/graph/person-families/list.
    These are the remaining family-scoped endpoints. Request bodies are VALID
    on purpose: the ownership check runs inside the handler, after FastAPI's
    body validation, so an invalid body would 422 and hide a missing gate.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def outsider(make_roleless_member, sakha_pk):
        return make_roleless_member(sakha_pk)

    def _fam(self, family_of_head):
        return f"{FAMILY}/families/{family_of_head['family_pk']}"

    def test_outsider_cannot_read_head_history(self, outsider, family_of_head):
        r = outsider["client"].get(self._fam(family_of_head) + "/head-history")
        assert r.status_code == 403, r.text

    def test_outsider_cannot_read_sakha_alignment(self, outsider, family_of_head):
        r = outsider["client"].get(self._fam(family_of_head) + "/sakha-alignment")
        assert r.status_code == 403, r.text

    def test_outsider_cannot_list_admins(self, outsider, family_of_head):
        r = outsider["client"].get(self._fam(family_of_head) + "/admins")
        assert r.status_code == 403, r.text

    def test_outsider_cannot_create_link(self, outsider, family_of_head):
        head = family_of_head["head"]["person_pk"]
        r = outsider["client"].post(
            self._fam(family_of_head) + "/links",
            json={"person_a_pk": head, "person_b_pk": outsider["person_pk"],
                  "link_type": "SPOUSE_OF"},
        )
        assert r.status_code == 403, r.text

    def test_outsider_cannot_assign_admin(self, outsider, family_of_head):
        r = outsider["client"].post(
            self._fam(family_of_head) + "/admins",
            json={"person_pk": outsider["person_pk"]},
        )
        assert r.status_code == 403, r.text

    def test_outsider_cannot_revoke_admin(self, outsider, family_of_head):
        r = outsider["client"].request(
            "DELETE", self._fam(family_of_head) + "/admins",
            json={"person_pk": family_of_head["head"]["person_pk"]},
        )
        assert r.status_code == 403, r.text

    def test_outsider_cannot_transfer_head(self, outsider, family_of_head):
        r = outsider["client"].post(
            self._fam(family_of_head) + "/transfer-head",
            json={"person_pk": outsider["person_pk"]},
        )
        assert r.status_code == 403, r.text

    def test_anonymous_is_rejected_everywhere(self, anon_client, family_of_head):
        base = self._fam(family_of_head)
        body = {"person_pk": FAKE_PK}
        calls = [
            ("GET", base, None), ("GET", base + "/members", None),
            ("GET", base + "/head-history", None), ("GET", base + "/graph", None),
            ("GET", base + "/sakha-alignment", None), ("GET", base + "/admins", None),
            ("GET", f"{FAMILY}/families", None),
            ("GET", f"{FAMILY}/person/{FAKE_PK}/families", None),
            ("POST", f"{FAMILY}/families", {"family_name": "x", "sakha_organization_pk": FAKE_PK}),
            ("POST", base + "/members", {**body, "relationship_type_code": "SON"}),
            ("DELETE", base + "/members", body),
            ("POST", base + "/links", {"person_a_pk": FAKE_PK, "person_b_pk": FAKE_PK, "link_type": "SPOUSE_OF"}),
            ("POST", base + "/admins", body), ("DELETE", base + "/admins", body),
            ("POST", base + "/transfer-head", body),
        ]
        for method, url, json_body in calls:
            r = anon_client.request(method, url, json=json_body)
            assert r.status_code == 401, f"{method} {url} -> {r.status_code}"


# ── POST /families ─────────────────────────────────────────────────────────

class TestCreateFamily:
    """POST /api/v1/family/families — self-service creation."""

    def test_missing_fields_returns_422(self, make_roleless_member, sakha_pk):
        member = make_roleless_member(sakha_pk)
        r = member["client"].post(f"{FAMILY}/families", json={})
        assert r.status_code == 422, r.text

    def test_blank_family_name_returns_422(self, make_roleless_member, sakha_pk):
        member = make_roleless_member(sakha_pk)
        r = member["client"].post(
            f"{FAMILY}/families",
            json={"family_name": "", "sakha_organization_pk": sakha_pk},
        )
        assert r.status_code == 422, r.text

    def test_unknown_sakha_returns_400(self, make_roleless_member, sakha_pk):
        member = make_roleless_member(sakha_pk)
        r = member["client"].post(
            f"{FAMILY}/families",
            json={"family_name": "Ghost", "sakha_organization_pk": FAKE_PK},
        )
        assert r.status_code == 400, r.text

    def test_non_sakha_organization_returns_400(
        self, make_roleless_member, sakha_pk, write_conn
    ):
        """A family can only be registered under a SAKHA_SANGHA."""
        with write_conn.cursor() as cur:
            cur.execute(
                """
                SELECT o.organization_pk FROM nss.organization o
                JOIN nss.master_data md
                  ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE md.value_code <> 'SAKHA_SANGHA' AND o.is_active = TRUE
                LIMIT 1
                """
            )
            row = cur.fetchone()
        if row is None:
            pytest.skip("No non-Sakha organization available.")
        member = make_roleless_member(sakha_pk)
        r = member["client"].post(
            f"{FAMILY}/families",
            json={"family_name": "Wrong Level", "sakha_organization_pk": str(row[0])},
        )
        assert r.status_code == 400, r.text

    def test_creator_becomes_active_self_member_and_head(self, new_family):
        family = new_family()
        client, pk = family["head"]["client"], family["family_pk"]
        detail = client.get(f"{FAMILY}/families/{pk}").json()
        assert detail["status_code"] == "ACTIVE"
        assert detail["family_id"].startswith("F")
        assert detail["family_id"][1:].isdigit()
        members = client.get(f"{FAMILY}/families/{pk}/members").json()
        assert [m["person_pk"] for m in members] == [family["head"]["person_pk"]]
        assert members[0]["relationship_type_code"] == "SELF"
        assert members[0]["is_head"] is True

    def test_family_ids_are_unique_across_creations(self, new_family):
        def family_id(f):
            return f["head"]["client"].get(
                f"{FAMILY}/families/{f['family_pk']}"
            ).json()["family_id"]

        assert family_id(new_family()) != family_id(new_family())

    def test_creating_a_second_family_leaves_the_first(
        self, new_family, make_roleless_member, sakha_pk, write_conn
    ):
        """A person is in one current family at a time: creating a new one
        closes the old relationship and records NEW_FAMILY_FORMATION."""
        first = new_family()
        head = first["head"]
        second = head["client"].post(
            f"{FAMILY}/families",
            json={"family_name": f"Second {uuid4().hex[:5]}", "sakha_organization_pk": sakha_pk},
        )
        assert second.status_code == 201, second.text
        # The founder was the first family's only member: it is dissolved
        # (soft-deleted, never left memberless-but-active), so it is gone
        # from the API but kept for history.
        r = head["client"].get(f"{FAMILY}/families/{first['family_pk']}/members")
        assert r.status_code == 404, r.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT is_active, deleted_at IS NOT NULL FROM nss.family_group "
                "WHERE family_group_pk = %s", (first["family_pk"],),
            )
            assert cur.fetchone() == (False, True)
            cur.execute(
                """
                SELECT transition_type FROM nss.family_transition_history
                WHERE person_pk = %s AND old_family_group_pk = %s
                  AND new_family_group_pk = %s
                """,
                (head["person_pk"], first["family_pk"],
                 second.json()["family_group_pk"]),
            )
            assert cur.fetchone() == ("NEW_FAMILY_FORMATION",)

    def test_family_ids_come_from_the_atomic_counter(self, new_family, write_conn):
        """family_id is allocated from id_sequence_master 'FAMILY' (never
        MAX+1): the counter advances and tracks the highest id issued."""
        fam = new_family()
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT family_id FROM nss.family_group WHERE family_group_pk = %s",
                (fam["family_pk"],),
            )
            fid = int(cur.fetchone()[0][1:])
            cur.execute(
                "SELECT current_value FROM nss.id_sequence_master WHERE sequence_code = 'FAMILY'"
            )
            assert cur.fetchone()[0] >= fid

    def test_founder_leaving_a_shared_family_promotes_a_successor(
        self, new_family, make_roleless_member, sakha_pk, write_conn
    ):
        """Head creates a new family: the old one keeps its other members,
        gets a new head (spouse preferred), and the founder's admin row is
        closed. Exactly one current head remains."""
        first = new_family()
        head = first["head"]
        other = make_roleless_member(sakha_pk)
        spouse = make_roleless_member(sakha_pk)
        assert _add_member(first, other).status_code == 201
        assert _add_member(
            first, spouse, relationship="SPOUSE", link_type="SPOUSE_OF",
            link_target_person_pk=head["person_pk"],
        ).status_code == 201
        assert head["client"].post(
            f"{FAMILY}/families/{first['family_pk']}/admins",
            json={"person_pk": head["person_pk"]},
        ).status_code == 201
        second = head["client"].post(
            f"{FAMILY}/families",
            json={"family_name": f"Split {uuid4().hex[:5]}", "sakha_organization_pk": sakha_pk},
        )
        assert second.status_code == 201, second.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT person_pk FROM nss.family_head_history "
                "WHERE family_group_pk = %s AND effective_to IS NULL",
                (first["family_pk"],),
            )
            assert [str(r[0]) for r in cur.fetchall()] == [spouse["person_pk"]]
            cur.execute(
                "SELECT COUNT(*) FROM nss.family_admin "
                "WHERE family_group_pk = %s AND person_pk = %s AND effective_to IS NULL",
                (first["family_pk"], head["person_pk"]),
            )
            assert cur.fetchone()[0] == 0
            cur.execute(
                "SELECT is_active FROM nss.family_group WHERE family_group_pk = %s",
                (first["family_pk"],),
            )
            assert cur.fetchone() == (True,)


# ── POST/DELETE /families/{pk}/members business rules ──────────────────────

class TestAddRemoveMemberRules:

    def test_add_to_unknown_family_returns_404(self, family_of_head):
        r = family_of_head["head"]["client"].post(
            f"{FAMILY}/families/{FAKE_PK}/members",
            json={"person_pk": FAKE_PK, "relationship_type_code": "SON"},
        )
        assert r.status_code == 404, r.text

    def test_add_unknown_person_returns_404(self, new_family):
        family = new_family()
        r = family["head"]["client"].post(
            f"{FAMILY}/families/{family['family_pk']}/members",
            json={"person_pk": FAKE_PK, "relationship_type_code": "SON"},
        )
        assert r.status_code == 404, r.text

    def test_add_body_validation_returns_422(self, new_family):
        family = new_family()
        r = family["head"]["client"].post(
            f"{FAMILY}/families/{family['family_pk']}/members", json={},
        )
        assert r.status_code == 422, r.text

    def test_add_already_member_returns_409(self, new_family, make_roleless_member, sakha_pk):
        family = new_family()
        person = make_roleless_member(sakha_pk)
        assert _add_member(family, person).status_code == 201
        assert _add_member(family, person).status_code == 409

    def test_add_invalid_relationship_type_returns_400(
        self, new_family, make_roleless_member, sakha_pk
    ):
        family = new_family()
        person = make_roleless_member(sakha_pk)
        r = _add_member(family, person, relationship="NOT_A_REAL_RELATION")
        assert r.status_code == 400, r.text

    def test_add_link_type_without_target_returns_400(
        self, new_family, make_roleless_member, sakha_pk
    ):
        family = new_family()
        person = make_roleless_member(sakha_pk)
        r = _add_member(family, person, link_type="PARENT_OF")
        assert r.status_code == 400, r.text

    def test_add_with_spouse_link_creates_edge(
        self, new_family, make_roleless_member, sakha_pk, write_conn
    ):
        family = new_family()
        spouse = make_roleless_member(sakha_pk)
        r = _add_member(
            family, spouse, relationship="SPOUSE",
            link_type="SPOUSE_OF",
            link_target_person_pk=family["head"]["person_pk"],
        )
        assert r.status_code == 201, r.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM nss.family_link "
                "WHERE family_group_pk = %s AND link_type = 'SPOUSE_OF' "
                "AND is_current = TRUE",
                (family["family_pk"],),
            )
            assert cur.fetchone()[0] == 1

    def test_adding_a_person_from_another_family_moves_them(
        self, new_family, write_conn, authed_client
    ):
        """Adding a person who is currently in family A to family B closes
        their A relationship and records the transition (SPOUSE -> MARRIAGE,
        anything else -> CHANGE_OF_FAMILY_UNIT). Moving someone out of a
        family needs authority over that family: here a FAMILY_MANAGE admin."""
        if not _authed_has(authed_client, "FAMILY_MANAGE"):
            pytest.skip("authed_client does not hold FAMILY_MANAGE.")
        fam_a, fam_b = new_family(), new_family()
        mover = fam_a["head"]
        r = authed_client.post(
            f"{FAMILY}/families/{fam_b['family_pk']}/members",
            json={"person_pk": mover["person_pk"], "relationship_type_code": "SPOUSE"},
        )
        assert r.status_code == 201, r.text
        with write_conn.cursor() as cur:
            cur.execute(
                """
                SELECT transition_type FROM nss.family_transition_history
                WHERE person_pk = %s AND old_family_group_pk = %s
                  AND new_family_group_pk = %s
                """,
                (mover["person_pk"], fam_a["family_pk"], fam_b["family_pk"]),
            )
            assert cur.fetchone() == ("MARRIAGE",)
            cur.execute(
                "SELECT is_current FROM nss.family_relationship "
                "WHERE family_group_pk = %s AND person_pk = %s",
                (fam_a["family_pk"], mover["person_pk"]),
            )
            assert cur.fetchone() == (False,)

    def test_head_cannot_pull_a_person_out_of_another_family(
        self, new_family, write_conn
    ):
        """No consent, no move: the head of family B holds no authority over
        family A, so adding A's member to B is refused and changes nothing."""
        fam_a, fam_b = new_family(), new_family()
        victim = fam_a["head"]
        r = fam_b["head"]["client"].post(
            f"{FAMILY}/families/{fam_b['family_pk']}/members",
            json={"person_pk": victim["person_pk"], "relationship_type_code": "SON"},
        )
        assert r.status_code == 403, r.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT is_current FROM nss.family_relationship "
                "WHERE family_group_pk = %s AND person_pk = %s",
                (fam_a["family_pk"], victim["person_pk"]),
            )
            assert cur.fetchone() == (True,)
            cur.execute(
                "SELECT COUNT(*) FROM nss.family_relationship "
                "WHERE family_group_pk = %s AND person_pk = %s",
                (fam_b["family_pk"], victim["person_pk"]),
            )
            assert cur.fetchone()[0] == 0

    @pytest.mark.parametrize("extra", [
        {"relationship_type_code": "NOT_A_REAL_RELATION"},
        {"link_type": "BOGUS", "link_target_person_pk": "HEAD"},
        {"link_type": "PARENT_OF"},
        {"link_type": "PARENT_OF", "link_target_person_pk": FAKE_PK},
    ])
    def test_invalid_request_never_moves_the_target(
        self, extra, new_family, authed_client, write_conn
    ):
        """Validation happens BEFORE the first write: a rejected request must
        leave the target in their original family (even for FAMILY_MANAGE)."""
        if not _authed_has(authed_client, "FAMILY_MANAGE"):
            pytest.skip("authed_client does not hold FAMILY_MANAGE.")
        fam_a, fam_b = new_family(), new_family()
        mover = fam_a["head"]
        body = {"person_pk": mover["person_pk"], "relationship_type_code": "SON", **extra}
        if body.get("link_target_person_pk") == "HEAD":
            body["link_target_person_pk"] = fam_b["head"]["person_pk"]
        r = authed_client.post(f"{FAMILY}/families/{fam_b['family_pk']}/members", json=body)
        assert r.status_code == 400, r.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT is_current FROM nss.family_relationship "
                "WHERE family_group_pk = %s AND person_pk = %s",
                (fam_a["family_pk"], mover["person_pk"]),
            )
            assert cur.fetchone() == (True,)

    def test_moving_the_head_out_promotes_a_successor(
        self, new_family, make_roleless_member, sakha_pk, authed_client, write_conn
    ):
        if not _authed_has(authed_client, "FAMILY_MANAGE"):
            pytest.skip("authed_client does not hold FAMILY_MANAGE.")
        fam_a, fam_b = new_family(), new_family()
        other = make_roleless_member(sakha_pk)
        assert _add_member(fam_a, other).status_code == 201
        r = authed_client.post(
            f"{FAMILY}/families/{fam_b['family_pk']}/members",
            json={"person_pk": fam_a["head"]["person_pk"], "relationship_type_code": "SON"},
        )
        assert r.status_code == 201, r.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT person_pk FROM nss.family_head_history "
                "WHERE family_group_pk = %s AND effective_to IS NULL",
                (fam_a["family_pk"],),
            )
            assert [str(x[0]) for x in cur.fetchall()] == [other["person_pk"]]

    def test_remove_from_unknown_family_returns_404(self, family_of_head):
        r = family_of_head["head"]["client"].request(
            "DELETE", f"{FAMILY}/families/{FAKE_PK}/members",
            json={"person_pk": FAKE_PK},
        )
        assert r.status_code == 404, r.text

    def test_head_cannot_remove_self(self, new_family):
        family = new_family()
        r = family["head"]["client"].request(
            "DELETE", f"{FAMILY}/families/{family['family_pk']}/members",
            json={"person_pk": family["head"]["person_pk"]},
        )
        assert r.status_code == 400, r.text

    def test_remove_non_member_returns_404(self, new_family, make_roleless_member, sakha_pk):
        family = new_family()
        stranger = make_roleless_member(sakha_pk)
        r = family["head"]["client"].request(
            "DELETE", f"{FAMILY}/families/{family['family_pk']}/members",
            json={"person_pk": stranger["person_pk"]},
        )
        assert r.status_code == 404, r.text

    def test_remove_is_a_soft_delete_and_closes_links(
        self, new_family, make_roleless_member, sakha_pk, write_conn
    ):
        family = new_family()
        spouse = make_roleless_member(sakha_pk)
        assert _add_member(
            family, spouse, relationship="SPOUSE", link_type="SPOUSE_OF",
            link_target_person_pk=family["head"]["person_pk"],
        ).status_code == 201
        r = family["head"]["client"].request(
            "DELETE", f"{FAMILY}/families/{family['family_pk']}/members",
            json={"person_pk": spouse["person_pk"], "remarks": "matrix test"},
        )
        assert r.status_code == 200, r.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT is_current, effective_to FROM nss.family_relationship "
                "WHERE family_group_pk = %s AND person_pk = %s",
                (family["family_pk"], spouse["person_pk"]),
            )
            is_current, effective_to = cur.fetchone()   # row kept: history is never deleted
            assert is_current is False and effective_to is not None
            cur.execute(
                "SELECT COUNT(*) FROM nss.family_link "
                "WHERE family_group_pk = %s AND is_current = TRUE",
                (family["family_pk"],),
            )
            assert cur.fetchone()[0] == 0
        members = family["head"]["client"].get(
            f"{FAMILY}/families/{family['family_pk']}/members"
        ).json()
        assert spouse["person_pk"] not in [m["person_pk"] for m in members]


# ── POST /families/{pk}/links ──────────────────────────────────────────────

class TestCreateFamilyLink:

    @staticmethod
    @pytest.fixture(scope="class")
    def fam(new_family, make_roleless_member, sakha_pk):
        family = new_family()
        other = make_roleless_member(sakha_pk)
        assert _add_member(family, other, relationship="BROTHER").status_code == 201
        return {**family, "other": other}

    def _post(self, fam, **body):
        return fam["head"]["client"].post(
            f"{FAMILY}/families/{fam['family_pk']}/links",
            json={
                "person_a_pk": fam["head"]["person_pk"],
                "person_b_pk": fam["other"]["person_pk"],
                "link_type": "SIBLING_OF",
                **body,
            },
        )

    def test_invalid_link_type_returns_400(self, fam):
        assert self._post(fam, link_type="FRIEND_OF").status_code == 400

    def test_missing_body_returns_422(self, fam):
        r = fam["head"]["client"].post(
            f"{FAMILY}/families/{fam['family_pk']}/links", json={}
        )
        assert r.status_code == 422, r.text

    def test_unknown_family_returns_404(self, fam):
        r = fam["head"]["client"].post(
            f"{FAMILY}/families/{FAKE_PK}/links",
            json={"person_a_pk": FAKE_PK, "person_b_pk": FAKE_PK, "link_type": "SPOUSE_OF"},
        )
        assert r.status_code == 404, r.text

    def test_non_member_endpoint_returns_400(self, fam, make_roleless_member, sakha_pk):
        stranger = make_roleless_member(sakha_pk)
        r = self._post(fam, person_b_pk=stranger["person_pk"])
        assert r.status_code == 400, r.text

    def test_plain_member_cannot_create_link(self, fam):
        r = fam["other"]["client"].post(
            f"{FAMILY}/families/{fam['family_pk']}/links",
            json={"person_a_pk": fam["head"]["person_pk"],
                  "person_b_pk": fam["other"]["person_pk"],
                  "link_type": "SIBLING_OF"},
        )
        assert r.status_code == 403, r.text

    def test_create_then_duplicate_is_idempotent(self, fam):
        first = self._post(fam)
        assert first.status_code == 201, first.text
        assert "created" in first.json()["message"].lower()
        again = self._post(fam)
        assert again.status_code == 201, again.text
        assert again.json()["message"] == "Link already exists"
        # Symmetric type: the reversed pair is the same edge.
        reversed_pair = self._post(
            fam,
            person_a_pk=fam["other"]["person_pk"],
            person_b_pk=fam["head"]["person_pk"],
        )
        assert reversed_pair.json()["message"] == "Link already exists"


# ── Head-only actions: business rules and happy paths ──────────────────────

class TestHeadActionRules:

    @staticmethod
    @pytest.fixture
    def fam(new_family, make_roleless_member, sakha_pk):
        family = new_family()
        member = make_roleless_member(sakha_pk)
        assert _add_member(family, member).status_code == 201
        return {**family, "member": member}

    def _url(self, fam, suffix):
        return f"{FAMILY}/families/{fam['family_pk']}/{suffix}"

    # -- transfer-head -----------------------------------------------------

    def test_transfer_to_self_returns_400(self, fam):
        r = fam["head"]["client"].post(
            self._url(fam, "transfer-head"),
            json={"person_pk": fam["head"]["person_pk"]},
        )
        assert r.status_code == 400, r.text

    def test_transfer_to_non_member_returns_400(self, fam, make_roleless_member, sakha_pk):
        stranger = make_roleless_member(sakha_pk)
        r = fam["head"]["client"].post(
            self._url(fam, "transfer-head"),
            json={"person_pk": stranger["person_pk"]},
        )
        assert r.status_code == 400, r.text

    def test_transfer_unknown_family_returns_404(self, fam):
        r = fam["head"]["client"].post(
            f"{FAMILY}/families/{FAKE_PK}/transfer-head",
            json={"person_pk": fam["member"]["person_pk"]},
        )
        assert r.status_code == 404, r.text

    def test_transfer_moves_headship_and_authority(self, fam):
        old, new = fam["head"], fam["member"]
        r = old["client"].post(
            self._url(fam, "transfer-head"),
            json={"person_pk": new["person_pk"], "remarks": "matrix test"},
        )
        assert r.status_code == 200, r.text

        history = new["client"].get(self._url(fam, "head-history")).json()
        current = [h for h in history if h["effective_to"] is None]
        assert [h["person_pk"] for h in current] == [new["person_pk"]]
        assert len(history) == 2

        # The new head holds the head-only power ...
        appoint = new["client"].post(
            self._url(fam, "admins"), json={"person_pk": new["person_pk"]}
        )
        assert appoint.status_code == 201, appoint.text
        # ... and the old head, now a plain member, no longer does.
        denied = old["client"].post(
            self._url(fam, "transfer-head"), json={"person_pk": new["person_pk"]}
        )
        assert denied.status_code == 403, denied.text
        denied_add = old["client"].post(
            self._url(fam, "members"),
            json={"person_pk": FAKE_PK, "relationship_type_code": "SON"},
        )
        assert denied_add.status_code == 403, denied_add.text

    # -- admins ------------------------------------------------------------

    def test_assign_admin_unknown_family_returns_404(self, fam):
        r = fam["head"]["client"].post(
            f"{FAMILY}/families/{FAKE_PK}/admins",
            json={"person_pk": fam["member"]["person_pk"]},
        )
        assert r.status_code == 404, r.text

    def test_assign_admin_body_validation_returns_422(self, fam):
        r = fam["head"]["client"].post(self._url(fam, "admins"), json={})
        assert r.status_code == 422, r.text

    def test_assign_admin_non_member_returns_400(self, fam, make_roleless_member, sakha_pk):
        stranger = make_roleless_member(sakha_pk)
        r = fam["head"]["client"].post(
            self._url(fam, "admins"), json={"person_pk": stranger["person_pk"]}
        )
        assert r.status_code == 400, r.text

    def test_head_may_appoint_self_and_duplicate_is_409(self, fam):
        head = fam["head"]
        first = head["client"].post(
            self._url(fam, "admins"), json={"person_pk": head["person_pk"]}
        )
        assert first.status_code == 201, first.text      # FAM-047
        again = head["client"].post(
            self._url(fam, "admins"), json={"person_pk": head["person_pk"]}
        )
        assert again.status_code == 409, again.text

    def test_assign_list_revoke_lifecycle(self, fam):
        head, member = fam["head"], fam["member"]
        assigned = head["client"].post(
            self._url(fam, "admins"),
            json={"person_pk": member["person_pk"], "remarks": "helper"},
        )
        assert assigned.status_code == 201, assigned.text
        body = assigned.json()
        assert body["person_pk"] == member["person_pk"]
        assert body["effective_to"] is None
        assert body["appointed_by_person_pk"] == head["person_pk"]

        listed = head["client"].get(self._url(fam, "admins")).json()
        assert [a["person_pk"] for a in listed] == [member["person_pk"]]

        revoked = head["client"].request(
            "DELETE", self._url(fam, "admins"),
            json={"person_pk": member["person_pk"], "remarks": "done"},
        )
        assert revoked.status_code == 200, revoked.text
        assert head["client"].get(self._url(fam, "admins")).json() == []
        # Revoked admin lost the membership-changing power.
        denied = member["client"].post(
            self._url(fam, "members"),
            json={"person_pk": FAKE_PK, "relationship_type_code": "SON"},
        )
        assert denied.status_code == 403, denied.text

    def test_revoke_non_admin_returns_404(self, fam):
        r = fam["head"]["client"].request(
            "DELETE", self._url(fam, "admins"),
            json={"person_pk": fam["member"]["person_pk"]},
        )
        assert r.status_code == 404, r.text

    def test_plain_member_cannot_revoke_admin(self, fam):
        r = fam["member"]["client"].request(
            "DELETE", self._url(fam, "admins"),
            json={"person_pk": fam["head"]["person_pk"]},
        )
        assert r.status_code == 403, r.text

    def test_removed_admin_loses_authority(self, fam):
        head, member = fam["head"], fam["member"]
        assert head["client"].post(
            self._url(fam, "admins"), json={"person_pk": member["person_pk"]}
        ).status_code == 201
        assert head["client"].request(
            "DELETE", self._url(fam, "members"),
            json={"person_pk": member["person_pk"]},
        ).status_code == 200
        r = member["client"].post(
            self._url(fam, "members"),
            json={"person_pk": FAKE_PK, "relationship_type_code": "SON"},
        )
        assert r.status_code == 403, r.text

    def test_removing_a_member_closes_their_admin_row(self, fam, write_conn):
        head, member = fam["head"], fam["member"]
        assert head["client"].post(
            self._url(fam, "admins"), json={"person_pk": member["person_pk"]}
        ).status_code == 201
        assert head["client"].request(
            "DELETE", self._url(fam, "members"),
            json={"person_pk": member["person_pk"]},
        ).status_code == 200
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT effective_to FROM nss.family_admin "
                "WHERE family_group_pk = %s AND person_pk = %s",
                (fam["family_pk"], member["person_pk"]),
            )
            rows = cur.fetchall()
        assert len(rows) == 1 and rows[0][0] is not None   # kept as history, closed
        assert head["client"].get(self._url(fam, "admins")).json() == []

    def test_admin_row_of_a_non_member_confers_no_authority(self, fam, write_conn):
        """Legacy data: an OPEN family_admin row whose holder is no longer a
        member must not grant membership-changing authority."""
        member = fam["member"]
        with write_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO nss.family_admin "
                "(family_group_pk, person_pk, appointed_by_person_pk, effective_from) "
                "VALUES (%s, %s, %s, CURRENT_DATE)",
                (fam["family_pk"], member["person_pk"], member["person_pk"]),
            )
            cur.execute(
                "UPDATE nss.family_relationship SET is_current = FALSE, "
                "effective_to = CURRENT_DATE WHERE family_group_pk = %s AND person_pk = %s",
                (fam["family_pk"], member["person_pk"]),
            )
        r = member["client"].post(
            self._url(fam, "members"),
            json={"person_pk": FAKE_PK, "relationship_type_code": "SON"},
        )
        assert r.status_code == 403, r.text

    def test_revoke_admin_unknown_family_is_404_before_403(self, fam, make_roleless_member, sakha_pk):
        """Existence precedes authorization: a non-head gets 404, not 403,
        for a family that does not exist (same order as every other endpoint)."""
        stranger = make_roleless_member(sakha_pk)
        r = stranger["client"].request(
            "DELETE", f"{FAMILY}/families/{FAKE_PK}/admins",
            json={"person_pk": FAKE_PK},
        )
        assert r.status_code == 404, r.text

    def test_list_admins_unknown_family_is_404_before_403(self, make_roleless_member, sakha_pk):
        stranger = make_roleless_member(sakha_pk)
        r = stranger["client"].get(f"{FAMILY}/families/{FAKE_PK}/admins")
        assert r.status_code == 404, r.text

    def test_get_family_unknown_is_404_before_403(self, make_roleless_member, sakha_pk):
        stranger = make_roleless_member(sakha_pk)
        assert stranger["client"].get(f"{FAMILY}/families/{FAKE_PK}").status_code == 404
        assert stranger["client"].get(
            f"{FAMILY}/families/{FAKE_PK}/sakha-alignment").status_code == 404

    def test_admin_cannot_remove_the_head(self, fam, write_conn):
        head, member = fam["head"], fam["member"]
        assert head["client"].post(
            self._url(fam, "admins"), json={"person_pk": member["person_pk"]}
        ).status_code == 201
        r = member["client"].request(
            "DELETE", self._url(fam, "members"),
            json={"person_pk": head["person_pk"]},
        )
        assert r.status_code == 403, r.text
        with write_conn.cursor() as cur:
            cur.execute(
                "SELECT is_current FROM nss.family_relationship "
                "WHERE family_group_pk = %s AND person_pk = %s",
                (fam["family_pk"], head["person_pk"]),
            )
            assert cur.fetchone() == (True,)

    def test_manage_admin_removing_head_closes_history_and_promotes_successor(
        self, fam, authed_client, write_conn
    ):
        if not _authed_has(authed_client, "FAMILY_MANAGE"):
            pytest.skip("authed_client does not hold FAMILY_MANAGE.")
        head, member = fam["head"], fam["member"]
        r = authed_client.request(
            "DELETE", self._url(fam, "members"),
            json={"person_pk": head["person_pk"]},
        )
        assert r.status_code == 200, r.text
        history = member["client"].get(self._url(fam, "head-history")).json()
        current = [h for h in history if h["effective_to"] is None]
        assert [h["person_pk"] for h in current] == [member["person_pk"]]
        old = [h for h in history if h["person_pk"] == head["person_pk"]]
        assert len(old) == 1 and old[0]["effective_to"] is not None

    def test_manage_admin_transfer_head_leaves_exactly_one_head(
        self, fam, authed_client
    ):
        """Transfer by a FAMILY_MANAGE admin (not the head) must close the
        real head's record — previously it closed the caller's own (nonexistent)
        row and tripped the one-current-head unique index."""
        if not _authed_has(authed_client, "FAMILY_MANAGE"):
            pytest.skip("authed_client does not hold FAMILY_MANAGE.")
        member = fam["member"]
        r = authed_client.post(
            self._url(fam, "transfer-head"), json={"person_pk": member["person_pk"]}
        )
        assert r.status_code == 200, r.text
        history = member["client"].get(self._url(fam, "head-history")).json()
        current = [h for h in history if h["effective_to"] is None]
        assert [h["person_pk"] for h in current] == [member["person_pk"]]

    def test_transfer_to_current_head_returns_400(self, fam, authed_client):
        if not _authed_has(authed_client, "FAMILY_MANAGE"):
            pytest.skip("authed_client does not hold FAMILY_MANAGE.")
        r = authed_client.post(
            self._url(fam, "transfer-head"),
            json={"person_pk": fam["head"]["person_pk"]},
        )
        assert r.status_code == 400, r.text


# ── FAM-036: a family's effective Sakha is the MAJORITY of its members' ────
#    current Sakha affiliations (registration Sakha is only the fallback)

class TestFamilyEffectiveSakhaMajority:
    """
    Controlled-data tests for the majority rule shared by every family read
    (api/services/family_majority.py) and by the organization stats.
    test_family.py::TestSakhaAlignment only asserts shape against whatever
    families happen to exist; here the affiliations are built explicitly.

    A person's Sakha for this rule is their OPEN membership_sakha_affiliation
    (effective_to IS NULL) on an active sangha_sevi — not sangha_sevi
    .organization_pk and not a closed (archived) affiliation.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def two_sakhas(write_conn):
        with write_conn.cursor() as cur:
            cur.execute(
                """
                SELECT o.organization_pk FROM nss.organization o
                JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
                ORDER BY o.organization_name LIMIT 2
                """
            )
            rows = [str(r[0]) for r in cur.fetchall()]
        if len(rows) < 2:
            pytest.skip("Need two active Sakhas.")
        return rows

    @staticmethod
    def _affiliate(write_conn, person_pk, sakha_pk, *, closed=False):
        """Give person_pk an affiliation at sakha_pk; returns its pk."""
        suffix = uuid4().hex[:8].upper()
        with write_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nss.membership_sakha_affiliation
                    (sangha_sevi_pk, organization_pk, local_sakha_erp_id,
                     effective_from, effective_to, affiliation_status,
                     source_event_type)
                SELECT ss.sangha_sevi_pk, %s, %s, DATE '2024-04-01', %s, %s, 'ENROLLMENT'
                FROM   nss.sangha_sevi ss WHERE ss.person_pk = %s AND ss.is_active = TRUE
                RETURNING membership_sakha_affiliation_pk
                """,
                (sakha_pk, f"TF{suffix}", "2025-01-01" if closed else None,
                 "ARCHIVED" if closed else "ACTIVE", person_pk),
            )
            return str(cur.fetchone()[0])

    def _family(self, new_family, make_roleless_member, registered_sakha):
        """A family registered under `registered_sakha`, created by a head
        whose own sangha_sevi lives there too. Returns the family dict."""
        head = make_roleless_member(registered_sakha)
        resp = head["client"].post(
            f"{FAMILY}/families",
            json={"family_name": f"Majority {uuid4().hex[:6]}",
                  "sakha_organization_pk": registered_sakha},
        )
        assert resp.status_code == 201, resp.text
        return {"head": head, "family_pk": resp.json()["family_group_pk"]}

    @staticmethod
    def _effective(family):
        return family["head"]["client"].get(
            f"{FAMILY}/families/{family['family_pk']}"
        ).json()["sakha_organization_pk"]

    @staticmethod
    def _alignment(family):
        r = family["head"]["client"].get(
            f"{FAMILY}/families/{family['family_pk']}/sakha-alignment"
        )
        assert r.status_code == 200, r.text
        return r.json()

    def test_no_affiliations_falls_back_to_registration_sakha(
        self, new_family, make_roleless_member, two_sakhas
    ):
        a, _ = two_sakhas
        fam = self._family(new_family, make_roleless_member, a)
        assert self._effective(fam) == a
        al = self._alignment(fam)
        assert al["assigned_sakha_pk"] == a
        assert al["majority_sakha_pk"] is None
        assert al["members_with_affiliation"] == 0
        assert al["is_aligned"] is True

    def test_single_affiliation_decides_the_effective_sakha(
        self, new_family, make_roleless_member, write_conn, two_sakhas
    ):
        a, b = two_sakhas
        fam = self._family(new_family, make_roleless_member, a)
        self._affiliate(write_conn, fam["head"]["person_pk"], b)
        assert self._effective(fam) == b           # beats the registration Sakha
        al = self._alignment(fam)
        assert al["assigned_sakha_pk"] == b == al["majority_sakha_pk"]
        assert al["members"][0]["is_home_sakha"] is True

    def test_majority_wins_over_head_and_registration(
        self, new_family, make_roleless_member, write_conn, two_sakhas
    ):
        a, b = two_sakhas
        fam = self._family(new_family, make_roleless_member, a)
        members = []
        for _ in range(2):
            m = make_roleless_member(b)
            assert _add_member(fam, m).status_code == 201
            members.append(m)
        self._affiliate(write_conn, fam["head"]["person_pk"], a)
        for m in members:
            self._affiliate(write_conn, m["person_pk"], b)

        assert self._effective(fam) == b           # 2 x B beats 1 x A
        al = self._alignment(fam)
        assert al["total_members"] == 3 and al["members_with_affiliation"] == 3
        counts = {x["organization_pk"]: x["member_count"] for x in al["affiliations"]}
        assert counts == {a: 1, b: 2}
        assert al["affiliations"][0]["organization_pk"] == b       # sorted by count
        by_person = {m["person_pk"]: m for m in al["members"]}
        assert by_person[fam["head"]["person_pk"]]["is_home_sakha"] is False
        assert all(by_person[m["person_pk"]]["is_home_sakha"] is True for m in members)

    @pytest.mark.parametrize("registered_first", [True, False])
    def test_tie_is_broken_by_lowest_organization_pk_everywhere(
        self, registered_first, new_family, make_roleless_member, write_conn,
        two_sakhas, authed_client
    ):
        """1 x A vs 1 x B is a tie. The winner is the LOWEST organization_pk
        — independent of registration Sakha, join order and member names — and
        the SQL CTE (family read) and the Python sakha-alignment path agree."""
        low, high = sorted(two_sakhas)
        reg = low if registered_first else high
        fam = self._family(new_family, make_roleless_member, reg)
        other = make_roleless_member(reg)
        assert _add_member(fam, other).status_code == 201
        # head votes `high`, the second member votes `low` (or vice versa by
        # parametrisation of `reg`): always a 1-1 tie.
        self._affiliate(write_conn, fam["head"]["person_pk"], high)
        self._affiliate(write_conn, other["person_pk"], low)

        assert self._effective(fam) == low
        al = self._alignment(fam)
        assert al["majority_sakha_pk"] == low == al["affiliations"][0]["organization_pk"]
        assert al["assigned_sakha_pk"] == low      # SQL effective == Python majority
        assert al["is_aligned"] is True
        if _authed_has(authed_client, "FAMILY_VIEW"):
            listed = authed_client.get(
                f"{FAMILY}/families", params={"sakha_organization_pk": low, "limit": 500})
            assert fam["family_pk"] in [f["family_group_pk"] for f in listed.json()]

    def test_closed_affiliation_does_not_vote(
        self, new_family, make_roleless_member, write_conn, two_sakhas
    ):
        a, b = two_sakhas
        fam = self._family(new_family, make_roleless_member, a)
        m1, m2 = make_roleless_member(b), make_roleless_member(b)
        for m in (m1, m2):
            assert _add_member(fam, m).status_code == 201
        self._affiliate(write_conn, fam["head"]["person_pk"], a)
        self._affiliate(write_conn, m1["person_pk"], b, closed=True)   # archived
        self._affiliate(write_conn, m2["person_pk"], b, closed=True)   # archived
        assert self._effective(fam) == a
        assert self._alignment(fam)["members_with_affiliation"] == 1

    def test_departed_member_stops_voting(
        self, new_family, make_roleless_member, write_conn, two_sakhas
    ):
        a, b = two_sakhas
        fam = self._family(new_family, make_roleless_member, a)
        m1, m2 = make_roleless_member(b), make_roleless_member(b)
        for m in (m1, m2):
            assert _add_member(fam, m).status_code == 201
            self._affiliate(write_conn, m["person_pk"], b)
        self._affiliate(write_conn, fam["head"]["person_pk"], a)
        assert self._effective(fam) == b
        removal = fam["head"]["client"].request(
            "DELETE", f"{FAMILY}/families/{fam['family_pk']}/members",
            json={"person_pk": m2["person_pk"]},
        )
        assert removal.status_code == 200, removal.text
        # 1 x A vs 1 x B is now a TIE — only assert the departed vote is gone.
        al = self._alignment(fam)
        assert al["total_members"] == 2
        assert sum(x["member_count"] for x in al["affiliations"]) == 2

    def test_inactive_sangha_sevi_does_not_vote(
        self, new_family, make_roleless_member, write_conn, two_sakhas
    ):
        a, b = two_sakhas
        fam = self._family(new_family, make_roleless_member, a)
        m = make_roleless_member(b)
        assert _add_member(fam, m).status_code == 201
        self._affiliate(write_conn, m["person_pk"], b)
        assert self._effective(fam) == b
        with write_conn.cursor() as cur:
            cur.execute("UPDATE nss.sangha_sevi SET is_active = FALSE, deleted_at = CURRENT_TIMESTAMP WHERE person_pk = %s",
                        (m["person_pk"],))
        assert self._effective(fam) == a

    def test_family_list_and_stats_use_the_effective_sakha(
        self, authed_client, new_family, make_roleless_member, write_conn, two_sakhas
    ):
        """The same rule feeds the admin family list (?sakha_organization_pk)
        and the organization stats' family_count."""
        if not _authed_has(authed_client, "FAMILY_VIEW"):
            pytest.skip("authed_client does not hold FAMILY_VIEW.")
        a, b = two_sakhas

        def count(org):
            r = authed_client.get(f"/api/v1/organization/organizations/{org}/stats")
            assert r.status_code == 200, r.text
            return r.json()["family_count"]

        a0, b0 = count(a), count(b)
        fam = self._family(new_family, make_roleless_member, a)
        assert (count(a), count(b)) == (a0 + 1, b0)           # fallback: registration Sakha
        self._affiliate(write_conn, fam["head"]["person_pk"], b)
        assert (count(a), count(b)) == (a0, b0 + 1)           # moved by majority
        listed = authed_client.get(
            f"{FAMILY}/families",
            params={"sakha_organization_pk": b, "limit": 500},
        )
        assert listed.status_code == 200, listed.text
        assert fam["family_pk"] in [f["family_group_pk"] for f in listed.json()]
