"""
NSS ERP — RBAC service.

Loads and evaluates role-based access control:
  - Load user roles, permissions, and scopes from the database
  - Check if a user has a specific permission
  - Check if a user's scope covers a given organization

Authority: SOL-ADMIN-004, SOL-AUTH-004,
           Tier 5 design decisions (2026-09-15)

RBAC Model (FROZEN):
  - 9 parallel roles (no hierarchy/inheritance)
  - Multi-role per user (user_role junction table)
  - Scope-on-assignment (admin_scope per user_role)
  - Composite permissions = union of all active role permissions
"""

from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException, status


@dataclass
class ScopeInfo:
    """
    A single scope assignment.

    Normally sourced from admin_scope (user_role_pk set). §63 composite
    auto-grant scopes (see _load_composite_grants) are synthetic — derived
    live from a governance position, not from any user_role row — and carry
    user_role_pk = None. Every scope consumer in this module only reads
    role_code / scope_level / organization_pk, so synthetic entries behave
    identically to real ones.
    """
    user_role_pk: UUID | None
    role_code: str
    scope_level: str           # NSS-WIDE, KENDRA, ANCHALIKA, ZILLA, SAKHA,
                               # PATHA_CHAKRA, KENDRA_MAHILA_SANGHA
    organization_pk: UUID | None  # NULL for NSS-WIDE


@dataclass
class UserContext:
    """
    Complete auth + RBAC context for the current user.

    Built once per request from the JWT + database lookups.
    Passed to endpoint handlers and RBAC checks.
    """
    user_account_pk: UUID
    person_pk: UUID
    sangha_sevi_pk: UUID | None = None
    sangha_sevi_id: str = ""
    permissions: set[str] = field(default_factory=set)
    scopes: list[ScopeInfo] = field(default_factory=list)
    force_password_change: bool = False
    session_pk: UUID | None = None  # nss.user_session row for this access token (Tier 5 A4)

    def has_permission(self, permission_code: str) -> bool:
        """Check if the user has a specific permission (union across all roles)."""
        return permission_code in self.permissions

    def has_any_permission(self, *permission_codes: str) -> bool:
        """Check if the user has any of the given permissions."""
        return bool(self.permissions & set(permission_codes))

    def has_scope_for_org(self, organization_pk: UUID | None) -> bool:
        """
        Check if any of the user's scopes cover a given organization.

        NSS-WIDE scope covers everything. KENDRA scope is treated as
        equivalent to NSS-WIDE (owner-confirmed 2026-10-22: "NSS = KENDRA =
        NSS_WIDE" — NSS_ERP_KENDRA_ADMIN is capability-equivalent to
        NSS_ERP_ADMIN, reserved for governing-body members; the role_master
        seed's `scope_level='KENDRA'`/`role_class='ORGANIZATIONAL'` predates
        that decision and was never updated — see backlog #12).
        Otherwise, the organization_pk must match one of the user's scopes.

        Compares as strings deliberately: psycopg2 returns admin_scope.
        organization_pk as a plain str (no register_uuid() call in this
        codebase — see api/database.py), while callers commonly pass a
        uuid.UUID (e.g. UUID(body.organization_pk)). A direct `==` between
        str and UUID is always False, which silently denied every
        in-scope request. Normalizing both sides to str avoids relying on
        the caller's type.
        """
        if organization_pk is None:
            return any(scope.scope_level in ("NSS-WIDE", "KENDRA") for scope in self.scopes)

        target = str(organization_pk)
        for scope in self.scopes:
            if scope.scope_level in ("NSS-WIDE", "KENDRA"):
                return True
            if scope.organization_pk and str(scope.organization_pk) == target:
                return True
        return False

    def is_nss_wide(self) -> bool:
        """
        Check if the user has any NSS-WIDE (or KENDRA-equivalent) scope.

        KENDRA is treated as NSS-WIDE-equivalent (owner-confirmed
        2026-10-22) — see has_scope_for_org's docstring for the full
        rationale. This is the single source of truth every other "is this
        admin global" check routes through (actor_scope_org_pks,
        organization.py's hierarchy anchor, governance.py, correspondence.py,
        family.py, membership_change_request.py, admin.py) — fixing it here
        propagates everywhere without a duplicate check anywhere else.
        """
        return any(s.scope_level in ("NSS-WIDE", "KENDRA") for s in self.scopes)

    def is_super_admin(self) -> bool:
        """
        The sole blanket, all-scope authority (ADMIN-BR-043/077).

        Only the NSS_ERP_ADMIN role carries unrestricted, organization-wide
        reach. Every other role — including the other ``*_ADMIN`` roles — is
        scope-bounded even when it holds the same permission (ADMIN-BR-076).
        Callers gate any "manage anything" branch on this, never on a
        permission alone.
        """
        return any(s.role_code == "NSS_ERP_ADMIN" for s in self.scopes)

    @property
    def actor_pk(self) -> str | None:
        """Sangha Sevi PK as string for audit columns, or None."""
        return str(self.sangha_sevi_pk) if self.sangha_sevi_pk else None


def load_user_context(conn, user_account_pk: UUID) -> UserContext | None:
    """
    Load the full RBAC context for a user from the database.

    Performs two queries:
      1. user_account → basic info + force_password_change
      2. user_role + role_permission + admin_scope → permissions + scopes

    Returns None if user_account is not found or inactive.
    """
    with conn.cursor() as cur:
        # 1. Get user account basics
        cur.execute(
            """
            SELECT ua.user_account_pk,
                   ua.person_pk,
                   ua.force_password_change,
                   ss.sangha_sevi_id,
                   ss.sangha_sevi_pk
            FROM nss.user_account ua
            JOIN nss.person p ON p.person_pk = ua.person_pk
            LEFT JOIN nss.sangha_sevi ss ON ss.person_pk = ua.person_pk
                  AND ss.is_active = TRUE
            WHERE ua.user_account_pk = %s
              AND ua.is_active = TRUE
              AND ua.account_status = 'ACTIVE'
            """,
            (str(user_account_pk),),
        )
        row = cur.fetchone()
        if row is None:
            return None

        ua_pk, person_pk, force_pw, sevi_id, sevi_pk = row

        # 2. Get permissions (union across all active roles)
        cur.execute(
            """
            SELECT DISTINCT pm.permission_code
            FROM nss.user_role ur
            JOIN nss.role_permission rp
              ON rp.role_master_pk = ur.role_master_pk
             AND rp.is_active = TRUE
            JOIN nss.permission_master pm
              ON pm.permission_master_pk = rp.permission_master_pk
             AND pm.is_active = TRUE
            WHERE ur.user_account_pk = %s
              AND ur.is_active = TRUE
            """,
            (str(user_account_pk),),
        )
        permissions = {r[0] for r in cur.fetchall()}

        # 3. Get scopes (one per active user_role assignment)
        cur.execute(
            """
            SELECT ur.user_role_pk,
                   rm.role_code,
                   asc2.scope_level,
                   asc2.organization_pk
            FROM nss.user_role ur
            JOIN nss.role_master rm
              ON rm.role_master_pk = ur.role_master_pk
            LEFT JOIN nss.admin_scope asc2
              ON asc2.user_role_pk = ur.user_role_pk
             AND asc2.is_active = TRUE
            WHERE ur.user_account_pk = %s
              AND ur.is_active = TRUE
            """,
            (str(user_account_pk),),
        )
        scopes = []
        for s_row in cur.fetchall():
            ur_pk, role_code, scope_level, org_pk = s_row
            if scope_level:  # admin_scope exists for this role assignment
                scopes.append(ScopeInfo(
                    user_role_pk=ur_pk,
                    role_code=role_code,
                    scope_level=scope_level,
                    organization_pk=org_pk,
                ))

        # 4. §63 composite auto-grant — governance positions that carry
        #    automatic RBAC authority (Tier 6 governance, owner-confirmed
        #    2026-10-09). Deliberately overrides GOV-BR-014's general rule
        #    ("a position is not an RBAC role") for exactly these bodies.
        composite_scopes, composite_permissions = load_composite_grants(cur, person_pk)
        existing_tuples = {(s.role_code, str(s.organization_pk) if s.organization_pk else None)
                            for s in scopes}
        for cs in composite_scopes:
            key = (cs.role_code, str(cs.organization_pk) if cs.organization_pk else None)
            if key not in existing_tuples:
                scopes.append(cs)
                existing_tuples.add(key)
        permissions |= composite_permissions

    return UserContext(
        user_account_pk=ua_pk,
        person_pk=person_pk,
        sangha_sevi_pk=sevi_pk,
        sangha_sevi_id=sevi_id or "",
        permissions=permissions,
        scopes=scopes,
        force_password_change=force_pw,
    )


# ── §63 composite auto-grant (Tier 6 governance) ─────────────────────────
# Certain governance body positions carry automatic RBAC authority — this is
# the deferred §63 composite rule: "every admin role will get auto assigned
# to its concerned body's President, Secretary — except Kendra GB, where all
# members get the access." Owner-confirmed 2026-10-09. This deliberately
# narrows/overrides GOV-BR-014 ("a position is NOT an RBAC role") for exactly
# the nine body/role pairs below; it is a live, computed view (Option A) —
# no stored rows, nothing to keep in sync, re-derived on every login/request.
#
# requires_org_null:
#   TRUE  -> rule applies only when body_master.organization_pk IS NULL
#   FALSE -> rule applies only when body_master.organization_pk IS NOT NULL
#   NULL  -> rule applies regardless (the body type only ever appears one way)
#
# position_codes: NULL means "any/all current holders" (Kendra GB's "all
# members" branch); otherwise an array of position_master.position_code
# values that trigger the grant.
#
# org_source: 'NULL' -> synthetic scope's organization_pk is NULL (NSS-wide
# footprint, e.g. Advisory Board, Kendra GB, central Mahila Parichalana
# Mandali); 'BODY_ORG' -> synthetic scope's organization_pk is the body's
# own organization_pk (Sakha/Anchalika/Zilla/Patha Chakra and per-Sakha
# Mahila Parichalana Mandali / Sevak Sangha Executive).
_COMPOSITE_GRANT_RULES_SQL = """
    (body_type_code, requires_org_null, position_codes, role_code, org_source) AS (
        VALUES
            ('KENDRA_GOVERNING_BODY',      NULL,  NULL::text[],
                'NSS_ERP_KENDRA_ADMIN',               'NULL'),
            ('ADVISORY_BOARD',              NULL,  ARRAY['PRESIDENT','SECRETARY'],
                'NSS_ERP_ADVISORY_BOARD_ADMIN',       'NULL'),
            ('MAHILA_PARICHALANA_MANDALI',  TRUE,  ARRAY['PRESIDENT','JOINT_SECRETARY'],
                'NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN', 'NULL'),
            ('MAHILA_PARICHALANA_MANDALI',  FALSE, ARRAY['PRESIDENT','JOINT_SECRETARY'],
                'NSS_ERP_SAKHA_ADMIN',                'BODY_ORG'),
            ('SAKHA_GOVERNING_BODY',        NULL,  ARRAY['PRESIDENT','SECRETARY'],
                'NSS_ERP_SAKHA_ADMIN',                'BODY_ORG'),
            ('SEVAK_SANGHA_EXECUTIVE',      NULL,  ARRAY['PRESIDENT','SECRETARY'],
                'NSS_ERP_SAKHA_ADMIN',                'BODY_ORG'),
            ('ANCHALIKA_GOVERNING_BODY',    NULL,  ARRAY['PRESIDENT','SECRETARY'],
                'NSS_ERP_ANCHALIKA_ADMIN',            'BODY_ORG'),
            ('ZILLA_GOVERNING_BODY',        NULL,  ARRAY['PRESIDENT','SECRETARY'],
                'NSS_ERP_ZILLA_ADMIN',                'BODY_ORG'),
            ('PATHA_CHAKRA_GOVERNING_BODY', NULL,  ARRAY['PRESIDENT','SECRETARY'],
                'NSS_ERP_PATHA_CHAKRA_ADMIN',          'BODY_ORG')
    )
"""


def load_composite_grants(cur, person_pk) -> tuple[list["ScopeInfo"], set[str]]:
    """
    Compute §63 auto-granted scopes + permissions for a person, live.

    Public (no leading underscore): also called directly by admin.py's
    user-detail endpoint to surface these as read-only "Auto-Admin (§63)"
    rows, separate from real user_role assignments.

    Two sources, merged with the acting-officeholder rule:
      1. Substantive holders (body_member_assignment) — the baseline grant.
      2. Acting holders (acting_position_assignment) — added ONLY when the
         resulting (role_code, organization_pk) isn't already covered by a
         substantive grant. This single dedupe rule is sufficient to encode
         "an acting officeholder who is already a GB member in their own
         right needs nothing extra" without a Kendra-specific special case:
         Kendra's substantive query already yields NSS_ERP_KENDRA_ADMIN /
         NULL for every current member, so an acting President/Secretary
         who is also a plain member is naturally deduped against that row.

    Returns (scopes, permission_codes) — permission_codes still needs to be
    resolved against role_permission by the caller's role_code lookup, so we
    resolve it here directly to keep load_user_context's merge simple.
    """
    substantive_sql = f"""
        WITH grant_rules {_COMPOSITE_GRANT_RULES_SQL}
        SELECT DISTINCT rm.role_master_pk, rm.role_code, rm.scope_level,
               CASE gr.org_source WHEN 'NULL' THEN NULL ELSE bm.organization_pk END
        FROM nss.body_member_assignment bma
        JOIN nss.body_master bm ON bm.body_master_pk = bma.body_master_pk
        JOIN nss.body_type_master btm ON btm.body_type_master_pk = bm.body_type_master_pk
        JOIN nss.position_master pom ON pom.position_master_pk = bma.position_master_pk
        JOIN grant_rules gr
          ON gr.body_type_code = btm.body_type_code
         AND (gr.requires_org_null IS NULL
              OR (gr.requires_org_null = TRUE AND bm.organization_pk IS NULL)
              OR (gr.requires_org_null = FALSE AND bm.organization_pk IS NOT NULL))
         AND (gr.position_codes IS NULL OR pom.position_code = ANY(gr.position_codes))
        JOIN nss.role_master rm ON rm.role_code = gr.role_code
        WHERE bma.person_pk = %s
          AND bma.assignment_status = 'ACTIVE'
          AND bma.is_active = TRUE
          AND bma.effective_from <= CURRENT_DATE
          AND (bma.effective_to IS NULL OR bma.effective_to >= CURRENT_DATE)
    """
    cur.execute(substantive_sql, (str(person_pk),))
    substantive = [
        ScopeInfo(user_role_pk=None, role_code=role_code, scope_level=scope_level,
                  organization_pk=org_pk)
        for (_rm_pk, role_code, scope_level, org_pk) in cur.fetchall()
    ]
    substantive_keys = {
        (s.role_code, str(s.organization_pk) if s.organization_pk else None)
        for s in substantive
    }

    acting_sql = f"""
        WITH grant_rules {_COMPOSITE_GRANT_RULES_SQL}
        SELECT DISTINCT rm.role_master_pk, rm.role_code, rm.scope_level,
               CASE gr.org_source WHEN 'NULL' THEN NULL ELSE bm.organization_pk END
        FROM nss.acting_position_assignment apa
        JOIN nss.body_master bm ON bm.body_master_pk = apa.body_master_pk
        JOIN nss.body_type_master btm ON btm.body_type_master_pk = bm.body_type_master_pk
        JOIN nss.position_master pom ON pom.position_master_pk = apa.position_master_pk
        JOIN grant_rules gr
          ON gr.body_type_code = btm.body_type_code
         AND (gr.requires_org_null IS NULL
              OR (gr.requires_org_null = TRUE AND bm.organization_pk IS NULL)
              OR (gr.requires_org_null = FALSE AND bm.organization_pk IS NOT NULL))
         AND (gr.position_codes IS NULL OR pom.position_code = ANY(gr.position_codes))
        JOIN nss.role_master rm ON rm.role_code = gr.role_code
        WHERE apa.person_pk = %s
          AND apa.acting_status = 'ACTIVE'
          AND apa.is_active = TRUE
          AND apa.effective_from <= CURRENT_DATE
          AND (apa.effective_to IS NULL OR apa.effective_to >= CURRENT_DATE)
    """
    cur.execute(acting_sql, (str(person_pk),))
    acting = [
        ScopeInfo(user_role_pk=None, role_code=role_code, scope_level=scope_level,
                  organization_pk=org_pk)
        for (_rm_pk, role_code, scope_level, org_pk) in cur.fetchall()
    ]

    composite_scopes = list(substantive)
    for a in acting:
        key = (a.role_code, str(a.organization_pk) if a.organization_pk else None)
        if key not in substantive_keys:
            composite_scopes.append(a)
            substantive_keys.add(key)

    if not composite_scopes:
        return [], set()

    role_codes = sorted({s.role_code for s in composite_scopes})
    cur.execute(
        """
        SELECT DISTINCT pm.permission_code
        FROM nss.role_master rm
        JOIN nss.role_permission rp
          ON rp.role_master_pk = rm.role_master_pk
         AND rp.is_active = TRUE
        JOIN nss.permission_master pm
          ON pm.permission_master_pk = rp.permission_master_pk
         AND pm.is_active = TRUE
        WHERE rm.role_code = ANY(%s)
        """,
        (role_codes,),
    )
    composite_permissions = {r[0] for r in cur.fetchall()}

    return composite_scopes, composite_permissions


# ── Scope-authority enforcement (ADMIN-BR-076/077/078) ──────────────────
# Every administrator is bounded to their own organizational scope. The sole
# blanket authority is the NSS_ERP_ADMIN role (equivalently, an NSS-WIDE
# scope). "Scope" is the recursive subtree of each organization the actor
# holds scope over — their org plus every descendant — so a Kendra-scoped
# admin reaches the whole tree through scope, not through a blanket bypass.
#
# These live here (not in a single router) because both the Administration
# and Claim-Approval routers must define "in scope" identically: what an
# admin can see (list filters) must equal what an admin can manage (write
# guards). Direct-org-pk matching (has_scope_for_org) is the old model and
# is retained only for the NSS-WIDE short-circuit inside these helpers.


def actor_scope_org_pks(cur, user: UserContext) -> set[str] | None:
    """
    Set of organization_pks the actor may act within (ADMIN-BR-076).

    Returns ``None`` to mean "all organizations", reserved for the sole
    global authority — the NSS_ERP_ADMIN role or an NSS-WIDE scope
    (ADMIN-BR-077). For a scope-bounded admin the set is the recursive
    subtree (each scoped organization + all its descendants). An admin with
    no organization-anchored scope resolves to the empty set.
    """
    if user.is_super_admin() or user.is_nss_wide():
        return None
    roots = [str(s.organization_pk) for s in user.scopes if s.organization_pk]
    if not roots:
        return set()
    placeholders = ",".join(["%s"] * len(roots))
    cur.execute(
        f"""
        WITH RECURSIVE subtree AS (
            SELECT organization_pk
            FROM nss.organization
            WHERE organization_pk IN ({placeholders})
            UNION ALL
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN subtree s ON o.parent_organization_pk = s.organization_pk
        )
        SELECT organization_pk FROM subtree
        """,
        roots,
    )
    return {str(r[0]) for r in cur.fetchall()}


def org_subtree_pks(cur, organization_pk) -> set[str]:
    """
    *organization_pk* plus every descendant organization, no actor
    involved — the single-root counterpart to ``actor_scope_org_pks``'s
    multi-root union.

    Added for per-tab dashboard stats (GET /admin/dashboard-stats?org_pk=):
    a dual-role admin (e.g. NSS-WIDE Kendra admin + Sakha-scoped admin) was
    seeing byte-identical member/family counts on every admin tab because
    the endpoint only ever computed one actor-wide union via
    ``actor_scope_org_pks`` and stamped it onto every tab. Scoping a single
    call to one specific org (the tab's own scope organization) instead of
    the actor's combined scope is what lets each tab show its own numbers.
    Callers must still check ``org_in_scope``/``require_org_in_scope`` first
    — this function trusts its input and applies no authorization.
    """
    cur.execute(
        """
        WITH RECURSIVE subtree AS (
            SELECT organization_pk
            FROM nss.organization
            WHERE organization_pk = %s
            UNION ALL
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN subtree s ON o.parent_organization_pk = s.organization_pk
        )
        SELECT organization_pk FROM subtree
        """,
        (str(organization_pk),),
    )
    return {str(r[0]) for r in cur.fetchall()}


def org_in_scope(cur, user: UserContext, organization_pk) -> bool:
    """
    Subtree-aware replacement for ``UserContext.has_scope_for_org``.

    True when *organization_pk* falls within the actor's scope subtree, or
    the actor is the global authority. Unlike ``has_scope_for_org`` this
    walks the org hierarchy, so a Kendra admin covers every descendant Sakha.
    """
    allowed = actor_scope_org_pks(cur, user)
    if allowed is None:
        return True
    return organization_pk is not None and str(organization_pk) in allowed


def require_org_in_scope(cur, user: UserContext, organization_pk, action: str) -> None:
    """403 unless *organization_pk* falls within the actor's scope subtree."""
    if org_in_scope(cur, user, organization_pk):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You can only {action} within your admin scope.",
    )


def require_person_in_scope(cur, user: UserContext, person_pk: str, action: str) -> None:
    """
    403 unless the person is reachable within the actor's scope (ADMIN-BR-076).

    A person is in scope when any of their active Sangha-Sevi organizations
    falls inside the actor's scope subtree. A person with no active Sangha
    Sevi has no organizational anchor and is therefore only reachable by the
    global authority (ADMIN-BR-077).
    """
    allowed = actor_scope_org_pks(cur, user)
    if allowed is None:
        return
    cur.execute(
        "SELECT organization_pk FROM nss.sangha_sevi "
        "WHERE person_pk = %s AND is_active = TRUE",
        (str(person_pk),),
    )
    person_orgs = {str(r[0]) for r in cur.fetchall() if r[0]}
    if person_orgs & allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You can only {action} within your admin scope.",
    )


def require_account_in_scope(cur, user: UserContext, user_account_pk, action: str) -> None:
    """
    403 unless the account's person is within the actor's scope (ADMIN-BR-076).

    Account-lifecycle operations (reset password, status change, delete) stay
    bounded to the actor's scope even for the global-authority exemption path,
    which ``require_person_in_scope`` short-circuits.
    """
    allowed = actor_scope_org_pks(cur, user)
    if allowed is None:
        return
    cur.execute(
        "SELECT person_pk FROM nss.user_account WHERE user_account_pk = %s",
        (str(user_account_pk),),
    )
    row = cur.fetchone()
    if row is None:
        # Non-existent account: leave the 404 to the caller's require_entity.
        return
    require_person_in_scope(cur, user, str(row[0]), action)
