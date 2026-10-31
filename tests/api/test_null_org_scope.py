"""
NSS ERP — Scope resolution for NULL-organization scope levels (owner decision 2026-10-30).

Unit-level assertions against api/services/rbac_service.py (no HTTP):

  KENDRA_MAHILA_SANGHA  -> every MAHILA_SANGHA organization (central + Sakha-level)
                           plus its subtree, and NOTHING above or beside it.
  ADVISORY_BOARD        -> exactly the singleton ADVISORY_BOARD organization (its own
                           correspondence register; owner decision 2026-10-30), and
                           managed_null_org_body_types() == {"ADVISORY_BOARD"} for the
                           NULL-organization governance BODY.
  NSS-WIDE / KENDRA / SAKHA semantics are unchanged.

Plus the seeded role_permission footprint of the two roles (the live-DB patch
04_role_permission_mahila_advisory_board_patch.sql and the seed must agree).

Endpoint-level behaviour is in
tests/security/test_mahila_advisory_board_admin_security.py. Everything rolls
back with the module SAVEPOINT (tests/conftest.py).
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.services.rbac_service import (
    ScopeInfo,
    UserContext,
    actor_scope_org_pks,
    actor_scope_root_org_pks,
    org_in_scope,
    require_org_in_scope,
)
from tests.api.test_correspondence import _create_test_organization

pytestmark = pytest.mark.integration

MAHILA_ROLE = "NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN"
AB_ROLE = "NSS_ERP_ADVISORY_BOARD_ADMIN"


def _ctx(*scopes: ScopeInfo) -> UserContext:
    return UserContext(user_account_pk=uuid4(), person_pk=uuid4(), scopes=list(scopes))


def _mahila_scope() -> ScopeInfo:
    return ScopeInfo(None, MAHILA_ROLE, "KENDRA_MAHILA_SANGHA", None)


def _ab_scope() -> ScopeInfo:
    return ScopeInfo(None, AB_ROLE, "ADVISORY_BOARD", None)


@pytest.fixture(scope="module")
def tree(write_conn):
    """
    A small isolated org tree:

        sakha_parent (SAKHA_SANGHA)
          └─ mahila_sakha (MAHILA_SANGHA)         <- Sakha-level Mahila Sangha
        mahila_central (MAHILA_SANGHA, no parent)  <- stands in for the central one
          └─ mahila_child (SAKHA_ASANA)            <- a subtree member
        other_sakha (SAKHA_SANGHA)                 <- unrelated
    """
    def sc():
        return f"T{uuid4().hex[:3].upper()}"

    sakha_parent = _create_test_organization(
        write_conn, name_prefix="NullScope Sakha", type_code="SAKHA_SANGHA", parent_pk=None, short_code=sc())
    mahila_sakha = _create_test_organization(
        write_conn, name_prefix="NullScope Mahila (Sakha)", type_code="MAHILA_SANGHA",
        parent_pk=sakha_parent, short_code=sc())
    mahila_central = _create_test_organization(
        write_conn, name_prefix="NullScope Mahila (central)", type_code="MAHILA_SANGHA",
        parent_pk=None, short_code=sc())
    mahila_child = _create_test_organization(
        write_conn, name_prefix="NullScope Mahila child", type_code="SAKHA_ASANA",
        parent_pk=mahila_central, short_code=sc())
    other_sakha = _create_test_organization(
        write_conn, name_prefix="NullScope Other Sakha", type_code="SAKHA_SANGHA", parent_pk=None, short_code=sc())
    return {
        "sakha_parent": sakha_parent, "mahila_sakha": mahila_sakha,
        "mahila_central": mahila_central, "mahila_child": mahila_child,
        "other_sakha": other_sakha,
    }


class TestMahilaScopeResolution:

    def test_resolves_every_mahila_org_and_its_subtree(self, write_conn, tree):
        allowed = actor_scope_org_pks(write_conn.cursor(), _ctx(_mahila_scope()))
        assert allowed is not None, "a Mahila-scoped admin must never resolve to global reach"
        assert tree["mahila_central"] in allowed
        assert tree["mahila_sakha"] in allowed, "Sakha-level Mahila Sanghas are in reach"
        assert tree["mahila_child"] in allowed, "descendants of a Mahila Sangha are in reach"

    def test_excludes_everything_above_and_beside(self, write_conn, tree):
        allowed = actor_scope_org_pks(write_conn.cursor(), _ctx(_mahila_scope()))
        assert tree["sakha_parent"] not in allowed, "the parent Sakha is NOT in reach"
        assert tree["other_sakha"] not in allowed
        cur = write_conn.cursor()
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'KENDRA'
        """)
        for (kendra_pk,) in cur.fetchall():
            assert str(kendra_pk) not in allowed

    def test_org_in_scope_and_require_org_in_scope(self, write_conn, tree):
        cur = write_conn.cursor()
        user = _ctx(_mahila_scope())
        assert org_in_scope(cur, user, tree["mahila_sakha"]) is True
        assert org_in_scope(cur, user, tree["other_sakha"]) is False
        assert org_in_scope(cur, user, None) is False
        require_org_in_scope(cur, user, tree["mahila_central"], "edit organizations")
        with pytest.raises(HTTPException) as exc:
            require_org_in_scope(cur, user, tree["sakha_parent"], "edit organizations")
        assert exc.value.status_code == 403

    def test_union_with_an_org_anchored_scope(self, write_conn, tree):
        user = _ctx(
            _mahila_scope(),
            ScopeInfo(None, "NSS_ERP_SAKHA_ADMIN", "SAKHA", tree["other_sakha"]),
        )
        allowed = actor_scope_org_pks(write_conn.cursor(), user)
        assert tree["other_sakha"] in allowed and tree["mahila_central"] in allowed
        assert tree["sakha_parent"] not in allowed

    def test_roots_helper_matches_scope_resolution(self, write_conn, tree):
        cur = write_conn.cursor()
        roots = actor_scope_root_org_pks(cur, _ctx(_mahila_scope()))
        assert tree["mahila_central"] in roots and tree["mahila_sakha"] in roots
        assert tree["mahila_child"] not in roots, "roots are pre-subtree; the child is reached by descent"

    def test_does_not_become_nss_wide(self):
        user = _ctx(_mahila_scope())
        assert user.is_nss_wide() is False
        assert user.is_super_admin() is False
        # legacy exact-match probe cannot see type-resolved reach (documented)
        assert user.has_scope_for_org(uuid4()) is False


@pytest.fixture(scope="module")
def ab_org_pk(write_conn):
    """The seeded singleton ADVISORY_BOARD organization (07_advisory_board_organization_patch.sql)."""
    cur = write_conn.cursor()
    cur.execute("""
        SELECT o.organization_pk FROM nss.organization o
        JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE md.value_code = 'ADVISORY_BOARD' AND o.is_active = TRUE
    """)
    rows = cur.fetchall()
    if not rows:
        pytest.skip("Advisory Board organization not seeded (run the idempotent patch).")
    assert len(rows) == 1, "ADVISORY_BOARD is a singleton organization type"
    return str(rows[0][0])


class TestAdvisoryBoardScopeResolution:

    def test_reaches_exactly_the_advisory_board_organization(self, write_conn, tree, ab_org_pk):
        cur = write_conn.cursor()
        user = _ctx(_ab_scope())
        assert actor_scope_org_pks(cur, user) == {ab_org_pk}
        assert actor_scope_root_org_pks(cur, user) == {ab_org_pk}
        assert org_in_scope(cur, user, ab_org_pk) is True
        require_org_in_scope(cur, user, ab_org_pk, "register correspondence for this organization")

    def test_refused_everywhere_else(self, write_conn, tree, ab_org_pk):
        cur = write_conn.cursor()
        user = _ctx(_ab_scope())
        assert org_in_scope(cur, user, tree["mahila_central"]) is False
        assert org_in_scope(cur, user, tree["other_sakha"]) is False
        assert org_in_scope(cur, user, None) is False
        with pytest.raises(HTTPException) as exc:
            require_org_in_scope(cur, user, tree["other_sakha"], "view dashboard stats")
        assert exc.value.status_code == 403
        # the Kendra (the Advisory Board's PARENT) is not in reach either
        cur.execute("""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE md.value_code = 'KENDRA'
        """)
        for (kendra_pk,) in cur.fetchall():
            assert org_in_scope(cur, user, str(kendra_pk)) is False

    def test_organization_is_a_kendra_child_with_a_short_code(self, write_conn, ab_org_pk):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT pt.value_code, o.short_code, o.organization_code
            FROM nss.organization o
            LEFT JOIN nss.organization p ON p.organization_pk = o.parent_organization_pk
            LEFT JOIN nss.master_data pt ON pt.master_data_pk = p.organization_type_master_data_pk
            WHERE o.organization_pk = %s
        """, (ab_org_pk,))
        parent_type, short_code, org_code = cur.fetchone()
        assert parent_type == "KENDRA"
        assert short_code, "needs a short_code to mint correspondence reference numbers"
        assert org_code == "ADB"

    def test_governance_body_stays_null_org_and_unlinked(self, write_conn):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT bm.organization_pk FROM nss.body_master bm
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE bt.body_type_code = 'ADVISORY_BOARD' AND bm.is_active = TRUE
        """)
        rows = cur.fetchall()
        if not rows:
            pytest.skip("Advisory Board governance body not seeded.")
        assert all(r[0] is None for r in rows), "the body must NOT be linked to the organization"

    def test_may_manage_only_advisory_board_bodies(self):
        user = _ctx(_ab_scope())
        assert user.managed_null_org_body_types() == {"ADVISORY_BOARD"}
        assert user.is_nss_wide() is False and user.is_super_admin() is False

    def test_other_roles_manage_no_null_org_body_types(self):
        # The Mahila admin manages exactly the central Mandali (NULL_ORG_SCOPE_BODY_TYPES) ...
        assert _ctx(_mahila_scope()).managed_null_org_body_types() == {"MAHILA_PARICHALANA_MANDALI"}
        # ... and every OTHER role manages none.
        assert _ctx(ScopeInfo(None, "NSS_ERP_SAKHA_ADMIN", "SAKHA", uuid4())).managed_null_org_body_types() == set()
        assert _ctx(ScopeInfo(None, "NSS_ERP_KENDRA_ADMIN", "KENDRA", None)).managed_null_org_body_types() == set()

    def test_mahila_scope_does_not_reach_the_advisory_board_org(self, write_conn, ab_org_pk):
        allowed = actor_scope_org_pks(write_conn.cursor(), _ctx(_mahila_scope()))
        assert ab_org_pk not in allowed


class TestUnchangedGlobalSemantics:

    @pytest.mark.parametrize("role,level", [
        ("NSS_ERP_ADMIN", "NSS-WIDE"),
        ("NSS_ERP_KENDRA_ADMIN", "KENDRA"),
    ])
    def test_global_scopes_still_resolve_to_none(self, write_conn, role, level):
        cur = write_conn.cursor()
        user = _ctx(ScopeInfo(None, role, level, None))
        assert actor_scope_org_pks(cur, user) is None
        assert actor_scope_root_org_pks(cur, user) is None

    def test_sakha_scope_is_its_own_subtree_only(self, write_conn, tree):
        user = _ctx(ScopeInfo(None, "NSS_ERP_SAKHA_ADMIN", "SAKHA", tree["sakha_parent"]))
        allowed = actor_scope_org_pks(write_conn.cursor(), user)
        assert tree["sakha_parent"] in allowed
        assert tree["mahila_sakha"] in allowed, "a Sakha admin still reaches its own Mahila Sangha"
        assert tree["mahila_central"] not in allowed, "...but not the central one"
        assert tree["other_sakha"] not in allowed


class TestSeededPermissions:
    """The seed and the idempotent patch must leave exactly these footprints."""

    @staticmethod
    def _perms(write_conn, role_code):
        cur = write_conn.cursor()
        cur.execute("""
            SELECT pm.permission_code
            FROM nss.role_permission rp
            JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk
            JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk
            WHERE rm.role_code = %s AND rp.is_active = TRUE
        """, (role_code,))
        return {r[0] for r in cur.fetchall()}

    SYSTEM_ONLY = {
        "ADMIN_PERMISSION_VIEW", "ADMIN_ROLE_MANAGE", "ADMIN_SCOPE_MANAGE",
        "ADMIN_USER_MANAGE", "ADMIN_USER_VIEW", "AUDIT_VIEW",
        "FOUNDATION_MANAGE", "PERSON_VIEW_SENSITIVE",
    }

    def test_mahila_is_kendra_operational_set(self, write_conn):
        mahila = self._perms(write_conn, MAHILA_ROLE)
        kendra = self._perms(write_conn, "NSS_ERP_KENDRA_ADMIN")
        assert mahila == kendra - self.SYSTEM_ONLY
        assert len(mahila) == 18

    def test_ab_admin_footprint(self, write_conn):
        assert self._perms(write_conn, AB_ROLE) == {
            "GOVERNANCE_VIEW", "GOVERNANCE_MANAGE", "MEMBERSHIP_VIEW",
            "CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE", "ORGANIZATION_VIEW", "FOUNDATION_VIEW",
            "PERSON_VIEW",  # owner decision 2026-10-30 (03_role_permission.sql + 04_*_patch.sql)
        }

    @pytest.mark.parametrize("role", [MAHILA_ROLE, AB_ROLE])
    def test_neither_role_holds_any_admin_permission(self, write_conn, role):
        perms = self._perms(write_conn, role)
        assert not {p for p in perms if p.startswith("ADMIN_")}
        assert not perms & self.SYSTEM_ONLY
