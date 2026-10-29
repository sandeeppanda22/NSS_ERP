"""
Family API router — Tier 4 read-only + Tier 5 write endpoints.

Read endpoints (GET): family listing, members, head history, graph,
sakha alignment, person families, membership summary, admins.

Write endpoints (POST/DELETE): add member, remove member,
assign/revoke admin, transfer head.

Security — OWNERSHIP-based, with a permission override:

  Family authority derives from a person's RELATIONSHIP to a family, not from
  a system-wide permission. FAMILY_VIEW / FAMILY_MANAGE are the organisational
  override that lets an administrator reach families they do not belong to
  (the org-level family browser in admin.html).

  - View one family (detail, members, head history, graph, admins,
    sakha alignment)         → current member of that family, or FAMILY_VIEW
  - View a person's family /
    membership summary       → self, a current relative, or FAMILY_VIEW
  - List/browse ALL families → FAMILY_VIEW only (admin surface)
  - Create a family          → any authenticated member (self-service: the
                               caller becomes founding member and head)
  - Add / remove member,
    create link              → that family's head or admin, or FAMILY_MANAGE
  - Assign / revoke admin,
    transfer headship        → that family's head only, or FAMILY_MANAGE
  - Audit actor columns populated via UserContext.sangha_sevi_pk

  An ordinary member holds no role and therefore no permissions; they reach
  their own family entirely through the ownership checks above. Gating these
  endpoints on FAMILY_VIEW/FAMILY_MANAGE alone would lock every ordinary
  member out of their own family tree.
"""

from datetime import date as date_type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.auth import get_current_user
from api.dependencies.rbac import require_permission
from api.helpers import DEFAULT_LIMIT, MAX_LIMIT, log_audit, next_id, row_to_model, rows_to_models, get_active_status_pk, require_entity
from api.schemas.auth import MessageResponse
from api.schemas.family import (
    AddFamilyMemberRequest,
    AssignFamilyAdminRequest,
    CreateFamilyLinkRequest,
    CreateFamilyRequest,
    FamilyAdminResponse,
    FamilyGraphMemberResponse,
    FamilyGroupResponse,
    FamilyHeadHistoryResponse,
    FamilyMemberResponse,
    FamilySakhaAlignmentResponse,
    MemberSakhaInfo,
    PersonMembershipSummaryResponse,
    RemoveFamilyMemberRequest,
    RevokeFamilyAdminRequest,
    SakhaAffiliationCount,
    TransferHeadRequest,
)
from api.services.family_graph import Step, build_family_graph
from api.services.family_majority import family_majority_cte, sakha_majority_sort_key
from api.services.family_membership import close_family_membership, next_family_id
from api.services.person_scope import person_in_admin_scope
from api.services.rbac_service import UserContext, actor_scope_org_pks

router = APIRouter(prefix="/api/v1/family", tags=["family"])


# ── Shared SQL fragments ──────────────────────────────────────────────────

def _family_select(restrict_sql: str = "") -> str:
    """
    The family SELECT with its FAM-036 effective-Sakha CTE.

    *restrict_sql* narrows the families the majority CTE evaluates (e.g.
    ``"AND fr.family_group_pk = %s"``) so single-family reads do not
    aggregate every family in the database; the caller then passes that
    bind parameter FIRST (the WITH clause precedes the rest). Without it
    the CTE covers all families (list endpoint).
    """
    return _FAMILY_SELECT_TEMPLATE.replace("__MAJORITY_CTE__", family_majority_cte(restrict_sql))


_FAMILY_SELECT_TEMPLATE = """
    WITH __MAJORITY_CTE__
    SELECT fg.family_group_pk,
           fg.family_id,
           fg.family_name,
           fg.family_status_master_data_pk,
           st.value_code  AS status_code,
           st.value_name  AS status_name,
           COALESCE(fmj.sakha_pk, fg.sakha_organization_pk)
               AS sakha_organization_pk,
           COALESCE(eo.organization_name, o.organization_name)
               AS sakha_name,
           COALESCE(eo.organization_code, o.organization_code)
               AS sakha_code,
           fg.formed_date,
           fg.remarks,
           fg.is_active
    FROM   nss.family_group fg
    JOIN   nss.master_data st
           ON st.master_data_pk = fg.family_status_master_data_pk
    JOIN   nss.organization o
           ON o.organization_pk = fg.sakha_organization_pk
    LEFT JOIN family_majority fmj
           ON fmj.family_group_pk = fg.family_group_pk AND fmj.rn = 1
    LEFT JOIN nss.organization eo
           ON eo.organization_pk = fmj.sakha_pk
"""

_FAMILY_ONE = "AND fr.family_group_pk = %s"

_MEMBER_SELECT = """
    SELECT fr.family_relationship_pk,
           fr.family_group_pk,
           fr.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           fr.relationship_type_master_data_pk,
           rt.value_code  AS relationship_type_code,
           rt.value_name  AS relationship_type_name,
           fr.effective_from,
           fr.effective_to,
           fr.is_current,
           CASE WHEN fhh.family_head_history_pk IS NOT NULL
                THEN TRUE ELSE FALSE
           END AS is_head,
           fr.remarks
    FROM   nss.family_relationship fr
    JOIN   nss.person p
           ON p.person_pk = fr.person_pk
    JOIN   nss.master_data rt
           ON rt.master_data_pk = fr.relationship_type_master_data_pk
    LEFT JOIN nss.family_head_history fhh
           ON fhh.family_group_pk = fr.family_group_pk
          AND fhh.person_pk = fr.person_pk
          AND fhh.effective_to IS NULL
"""

_HEAD_SELECT = """
    SELECT fh.family_head_history_pk,
           fh.family_group_pk,
           fh.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           fh.effective_from,
           fh.effective_to,
           fh.remarks
    FROM   nss.family_head_history fh
    JOIN   nss.person p
           ON p.person_pk = fh.person_pk
"""


# ═══════════════════════════════════════════════════════════════════════════
# 0. AUTHORIZATION HELPERS (FAM-046, FAM-048, FAM-050)
# ═══════════════════════════════════════════════════════════════════════════
#
# Family authority is OWNERSHIP-based, not permission-based. A person may act
# on a family because of their relationship to it, not because they hold a
# system-wide permission. FAMILY_VIEW / FAMILY_MANAGE are the ORGANISATIONAL
# OVERRIDE: they let an administrator reach families they do not belong to
# (the org-level family browser in admin.html).
#
#   View family      → any current member of that family, or FAMILY_VIEW
#   Change members   → that family's head or a family admin, or FAMILY_MANAGE
#   Appoint admins /
#   transfer headship → that family's head only, or FAMILY_MANAGE
#
# These helpers are defined before the endpoints deliberately: an authorization
# rule a reviewer cannot find next to the endpoint it guards is a rule that
# rots. Every family-scoped endpoint calls exactly one of them as its first act.


def _is_current_head(conn, family_group_pk: str, person_pk: str) -> bool:
    """Return True if person_pk is the current head of family_group_pk."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.family_head_history
            WHERE  family_group_pk = %s
              AND  person_pk = %s
              AND  effective_to IS NULL
        """, (family_group_pk, person_pk))
        return cur.fetchone() is not None


def _is_current_admin(conn, family_group_pk: str, person_pk: str) -> bool:
    """
    Return True if person_pk is a current admin of family_group_pk AND still
    a current member of it — an admin row that outlived the person's
    membership (legacy data) must never confer authority.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1
            FROM   nss.family_admin fa
            JOIN   nss.family_relationship fr
                   ON fr.family_group_pk = fa.family_group_pk
                  AND fr.person_pk = fa.person_pk
                  AND fr.is_current = TRUE
            WHERE  fa.family_group_pk = %s
              AND  fa.person_pk = %s
              AND  fa.effective_to IS NULL
        """, (family_group_pk, person_pk))
        return cur.fetchone() is not None


def _is_current_member(conn, family_group_pk: str, person_pk: str) -> bool:
    """Return True if person_pk is a current member of family_group_pk."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.family_relationship
            WHERE  family_group_pk = %s
              AND  person_pk = %s
              AND  is_current = TRUE
        """, (family_group_pk, person_pk))
        return cur.fetchone() is not None


def _shares_current_family(conn, person_a_pk: str, person_b_pk: str) -> bool:
    """
    Return True if both persons are current members of at least one family
    in common. Used so an ordinary member can read the membership summaries
    of their own relatives while viewing their family tree, without being
    able to read summaries of unrelated people.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1
            FROM   nss.family_relationship a
            JOIN   nss.family_relationship b
                   ON b.family_group_pk = a.family_group_pk
            WHERE  a.person_pk = %s AND a.is_current = TRUE
              AND  b.person_pk = %s AND b.is_current = TRUE
            LIMIT  1
        """, (person_a_pk, person_b_pk))
        return cur.fetchone() is not None


def _require_family_exists(conn, family_group_pk) -> None:
    """
    404 for an unknown/inactive family. Every family-scoped guard below runs
    this FIRST, so the order is uniformly existence (404) before
    authorization (403) on all family endpoints.
    """
    with conn.cursor() as cur:
        require_entity(cur, "family_group", str(family_group_pk), label="Family")


def _family_in_admin_scope(conn, family_group_pk, user: UserContext) -> bool:
    """
    ADMIN-BR-076: the FAMILY_VIEW / FAMILY_MANAGE override reaches only
    families whose EFFECTIVE Sakha (FAM-036) lies inside the admin's scope
    subtree — the same bound the /families list already applies. NSS_ERP_ADMIN
    / NSS-WIDE are unrestricted. (The ownership path — head/admin/member — is
    independent of scope.)
    """
    with conn.cursor() as cur:
        allowed = actor_scope_org_pks(cur, user)
        if allowed is None:
            return True
        cur.execute(
            _family_select(_FAMILY_ONE) + " WHERE fg.family_group_pk = %s",
            (str(family_group_pk), str(family_group_pk)),
        )
        row = cur.fetchone()
        if row is None:
            return False
        sakha_pk = row[[d[0] for d in cur.description].index("sakha_organization_pk")]
        return str(sakha_pk) in allowed


def _has_scoped_family_permission(conn, family_group_pk, user: UserContext, permission: str) -> bool:
    """The organisational override: *permission* held AND the family in scope."""
    return user.has_permission(permission) and _family_in_admin_scope(conn, family_group_pk, user)


def _require_family_view(conn, family_group_pk, user: UserContext) -> None:
    """
    Read access to one family: any current member of it, or an administrator
    holding FAMILY_VIEW.
    """
    _require_family_exists(conn, family_group_pk)
    if _has_scoped_family_permission(conn, family_group_pk, user, "FAMILY_VIEW"):
        return
    if _is_current_member(conn, str(family_group_pk), str(user.person_pk)):
        return
    raise HTTPException(
        status_code=403,
        detail="You do not have access to this family.",
    )


def _require_family_manage(
    conn, family_group_pk, user: UserContext, *, detail: str | None = None
) -> None:
    """
    Membership-changing access to one family: its current head or a current
    family admin, or an administrator holding FAMILY_MANAGE.
    """
    _require_family_exists(conn, family_group_pk)
    if _has_scoped_family_permission(conn, family_group_pk, user, "FAMILY_MANAGE"):
        return
    fg = str(family_group_pk)
    person = str(user.person_pk)
    if _is_current_head(conn, fg, person) or _is_current_admin(conn, fg, person):
        return
    raise HTTPException(
        status_code=403,
        detail=detail or (
            "Only the family head or a family admin can change this "
            "family's membership."
        ),
    )


def _resolve_relationship_type_pk(
    cur, relationship_type_code: str, *, missing_status: int = 400
) -> str:
    """
    RELATIONSHIP_TYPE value_code -> master_data_pk. *missing_status* is 400
    for a client-supplied code, 500 for a code the server itself relies on
    (a missing seed row).
    """
    cur.execute("""
        SELECT md.master_data_pk
        FROM   nss.master_data md
        JOIN   nss.master_category mc
               ON mc.master_category_pk = md.master_category_pk
        WHERE  mc.category_code = 'RELATIONSHIP_TYPE'
          AND  md.value_code = %s
    """, (relationship_type_code,))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=missing_status,
            detail=f"Invalid relationship type: {relationship_type_code}",
        )
    return str(row[0])


def _require_family_head(conn, family_group_pk, user: UserContext) -> None:
    """
    Head-only access: appointing/revoking family admins and transferring
    headship (FAM-046, FAM-050). An administrator holding FAMILY_MANAGE may
    also act, so a family whose head is lost is not permanently stuck.
    """
    _require_family_exists(conn, family_group_pk)
    if _has_scoped_family_permission(conn, family_group_pk, user, "FAMILY_MANAGE"):
        return
    if _is_current_head(conn, str(family_group_pk), str(user.person_pk)):
        return
    raise HTTPException(
        status_code=403,
        detail="Only the current family head can perform this action.",
    )


def _require_person_family_view(conn, person_pk, user: UserContext) -> None:
    """
    Read access to one person's family/membership context: themselves, a
    current relative, or an administrator holding FAMILY_VIEW.
    """
    if str(person_pk) == str(user.person_pk):
        return
    if user.has_permission("FAMILY_VIEW") and person_in_admin_scope(conn, person_pk, user):
        return
    if _shares_current_family(conn, str(user.person_pk), str(person_pk)):
        return
    raise HTTPException(
        status_code=403,
        detail="You do not have access to this person's family information.",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. FAMILIES (core read)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/families", response_model=list[FamilyGroupResponse])
def list_families(
    sakha_code: str | None = Query(
        None, description="Filter by Sakha organization_code (e.g. SKH1)"
    ),
    sakha_organization_pk: str | None = Query(
        None, description="Filter by Sakha organization PK (UUID)"
    ),
    status_code: str | None = Query(
        None, description="Filter by status value_code"
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FAMILY_VIEW")),
) -> list[FamilyGroupResponse]:
    """
    List all active families with resolved status and Sakha context.

    Optionally filter by sakha_code or status_code. Supports pagination
    via limit/offset (default 100, max 500).

    The result is bounded to the orgs the caller may act within
    (``actor_scope_org_pks``), so an admin holding the same organizational
    role over several sanghas sees families across ALL of them — not just
    the first — while a scope-bounded admin can never see families outside
    their subtree. NSS-WIDE / super admins are unrestricted. This mirrors
    the scope resolver already used by the Administration/claim write
    guards: what an admin can see now equals what an admin can manage.
    """
    sql = _family_select() + " WHERE fg.is_active = TRUE"
    params: list = []

    if sakha_code is not None:
        sql += " AND COALESCE(eo.organization_code, o.organization_code) = %s"
        params.append(sakha_code)
    elif sakha_organization_pk is not None:
        sql += " AND COALESCE(fmj.sakha_pk, fg.sakha_organization_pk) = %s"
        params.append(sakha_organization_pk)
    if status_code is not None:
        sql += " AND st.value_code = %s"
        params.append(status_code)

    with conn.cursor() as cur:
        # Restrict to the admin's scope subtree. None → NSS-WIDE / super
        # admin (no restriction). An empty set → a scope-bounded admin with
        # no org-anchored role: they manage no org, so they see no org-level
        # families (short-circuit avoids an empty-ARRAY cast in SQL).
        scoped = actor_scope_org_pks(cur, user)
        if scoped is not None:
            if not scoped:
                return []
            sql += (
                " AND COALESCE(fmj.sakha_pk, fg.sakha_organization_pk) = ANY(%s::uuid[])"
            )
            params.append(list(scoped))

        sql += " ORDER BY fg.family_name"
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(sql, tuple(params))
        return rows_to_models(cur, FamilyGroupResponse)


@router.get(
    "/families/{family_group_pk}",
    response_model=FamilyGroupResponse,
)
def get_family(
    family_group_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> FamilyGroupResponse:
    """
    Get a single family by PK with resolved context.

    Access: any current member of this family, or FAMILY_VIEW.
    """
    _require_family_view(conn, family_group_pk, user)

    sql = _family_select(_FAMILY_ONE) + " WHERE fg.family_group_pk = %s AND fg.is_active = TRUE"

    with conn.cursor() as cur:
        cur.execute(sql, (str(family_group_pk), str(family_group_pk)))
        result = row_to_model(cur, FamilyGroupResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Family not found")
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 1b. CREATE FAMILY (Tier 5 — authenticated write)
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/families",
    response_model=FamilyGroupResponse,
    status_code=201,
)
def create_family(
    body: CreateFamilyRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> FamilyGroupResponse:
    """
    Create a new family group with the authenticated user as
    the founding member and head.

    Access: any authenticated member. This is self-service by definition —
    the caller becomes the founding member and head, so there is no existing
    family for an ownership check to consult. No FAMILY_MANAGE required.

    Steps:
      1. Validate Sakha exists and is active
      2. Atomically allocate the next family_id (id_sequence_master FAMILY)
      3. Resolve ACTIVE status PK and SELF relationship type PK
      4. Create family_group
      5. Create family_relationship (SELF)
      6. Create family_head_history
      7. If user was in a previous family (close_family_membership):
         - Soft-delete old family_relationship, family_link edges, admin row
         - Head succession if they were its head; dissolve it if memberless
         - Record family_transition_history (NEW_FAMILY_FORMATION)
      8. Return the new family via the standard SELECT
    """
    today = date_type.today()
    formed = body.formed_date or today
    person_pk = str(user.person_pk)

    # 1. Validate Sakha
    with conn.cursor() as cur:
        cur.execute("""
            SELECT organization_pk
            FROM   nss.organization
            WHERE  organization_pk = %s
              AND  is_active = TRUE
              AND  organization_type_master_data_pk IN (
                       SELECT master_data_pk
                       FROM   nss.master_data md
                       JOIN   nss.master_category mc
                              ON mc.master_category_pk = md.master_category_pk
                       WHERE  mc.category_code = 'ORGANIZATION_TYPE'
                         AND  md.value_code = 'SAKHA_SANGHA'
                   )
        """, (str(body.sakha_organization_pk),))
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid Sakha: organization not found or not a SAKHA_SANGHA",
            )

    # 2. Allocate family_id atomically (id_sequence_master 'FAMILY')
    with conn.cursor() as cur:
        family_id = next_family_id(cur, actor_pk=user.actor_pk)

    # 3. Resolve ACTIVE status PK
    with conn.cursor() as cur:
        active_status_pk = get_active_status_pk(cur)

    # 3b. Resolve SELF relationship type PK
    with conn.cursor() as cur:
        self_rel_pk = _resolve_relationship_type_pk(cur, "SELF", missing_status=500)

    # 4. Create family_group
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nss.family_group
                (family_id, family_name, family_status_master_data_pk,
                 sakha_organization_pk, formed_date, remarks)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING family_group_pk
        """, (
            family_id,
            body.family_name,
            active_status_pk,
            str(body.sakha_organization_pk),
            str(formed),
            body.remarks,
        ))
        new_family_pk = str(cur.fetchone()[0])
        actor = user.actor_pk
        log_audit(cur, action="CREATE", table_name="family_group", record_pk=str(new_family_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="family", summary=f"Created family group for person {person_pk}")

    # 5. Check if user is in an existing family (before creating new relationship)
    old_family_pk = None
    with conn.cursor() as cur:
        cur.execute("""
            SELECT family_group_pk
            FROM   nss.family_relationship
            WHERE  person_pk = %s AND is_current = TRUE
        """, (person_pk,))
        row = cur.fetchone()
        if row is not None:
            old_family_pk = str(row[0])

    # 6. Create family_relationship (SELF) in new family
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nss.family_relationship
                (family_group_pk, person_pk,
                 relationship_type_master_data_pk,
                 effective_from, is_current)
            VALUES (%s, %s, %s, %s, TRUE)
        """, (new_family_pk, person_pk, self_rel_pk, str(formed)))

    # 7. Create family_head_history
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nss.family_head_history
                (family_group_pk, person_pk, effective_from, reason)
            VALUES (%s, %s, %s, %s)
        """, (
            new_family_pk,
            person_pk,
            str(formed),
            "Family founder — created own family",
        ))

    # 8. Leave the old family (relationship + links + admin row closed, head
    #    succession, dissolve if memberless) and record the transition.
    if old_family_pk:
        with conn.cursor() as cur:
            close_family_membership(
                cur, family_group_pk=old_family_pk, person_pk=person_pk,
                on_date=today, remark="Left to form a new family",
                head_reason="Auto-assigned: previous head left the family",
                actor_pk=user.actor_pk,
                actor_user_account_pk=str(user.user_account_pk),
            )
            cur.execute("""
                INSERT INTO nss.family_transition_history
                    (person_pk, old_family_group_pk, new_family_group_pk,
                     transition_type, transition_reason, effective_date)
                VALUES (%s, %s, %s, 'NEW_FAMILY_FORMATION', %s, %s)
            """, (
                person_pk,
                old_family_pk,
                new_family_pk,
                f"Created own family: {body.family_name}",
                str(today),
            ))

    # No explicit commit: get_write_connection commits once the handler
    # returns and rolls back on any exception. Committing here instead would
    # break atomicity — if the SELECT below failed, the family would already
    # be persisted while the caller received a 500 — and it would also
    # release any enclosing SAVEPOINT the caller established.

    # 9. Return the new family via standard SELECT
    sql = _family_select(_FAMILY_ONE) + " WHERE fg.family_group_pk = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (new_family_pk, new_family_pk))
        result = row_to_model(cur, FamilyGroupResponse)
        if result is None:
            raise HTTPException(status_code=500, detail="Family created but could not retrieve")
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 2. FAMILY MEMBERS (relationships)
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/families/{family_group_pk}/members",
    response_model=list[FamilyMemberResponse],
)
def list_family_members(
    family_group_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[FamilyMemberResponse]:
    """
    List all current members of a family with resolved person and
    relationship type context. Returns 404 if the family does not exist.

    Access: any current member of this family, or FAMILY_VIEW.
    """
    _require_family_view(conn, family_group_pk, user)

    sql = (
        _MEMBER_SELECT
        + " WHERE fr.family_group_pk = %s AND fr.is_current = TRUE"
        + " ORDER BY rt.display_order, p.first_name"
    )

    with conn.cursor() as cur:
        cur.execute(sql, (str(family_group_pk),))
        return rows_to_models(cur, FamilyMemberResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 3. FAMILY HEAD HISTORY
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/families/{family_group_pk}/head-history",
    response_model=list[FamilyHeadHistoryResponse],
)
def list_family_head_history(
    family_group_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[FamilyHeadHistoryResponse]:
    """
    List family head history (current and past). Returns 404 if
    the family does not exist.

    Access: any current member of this family, or FAMILY_VIEW.
    """
    _require_family_view(conn, family_group_pk, user)

    sql = (
        _HEAD_SELECT
        + " WHERE fh.family_group_pk = %s"
        + " ORDER BY fh.effective_from DESC"
    )

    with conn.cursor() as cur:
        cur.execute(sql, (str(family_group_pk),))
        return rows_to_models(cur, FamilyHeadHistoryResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 4. FAMILY GRAPH (dynamic relationship computation)
# ═══════════════════════════════════════════════════════════════════════════

_GRAPH_PERSONS_SQL = """
    SELECT DISTINCT p.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           g.value_code AS gender_code
    FROM   nss.family_link fl
    JOIN   nss.person p
           ON p.person_pk IN (fl.person_a_pk, fl.person_b_pk)
    LEFT JOIN nss.master_data g
           ON g.master_data_pk = p.gender_master_data_pk
    WHERE  fl.family_group_pk = %s
      AND  fl.is_current = TRUE
"""

_GRAPH_LINKS_SQL = """
    SELECT fl.person_a_pk,
           fl.person_b_pk,
           fl.link_type
    FROM   nss.family_link fl
    WHERE  fl.family_group_pk = %s
      AND  fl.is_current = TRUE
"""

# Departed members: persons who left this family (via NEW_FAMILY_FORMATION)
_DEPARTED_PERSONS_SQL = """
    SELECT fth.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           g.value_code AS gender_code,
           fth.new_family_group_pk,
           fg.family_id   AS departed_family_id,
           fg.family_name AS departed_family_name,
           o.organization_name AS departed_sakha_name
    FROM   nss.family_transition_history fth
    JOIN   nss.person p ON p.person_pk = fth.person_pk
    LEFT JOIN nss.master_data g ON g.master_data_pk = p.gender_master_data_pk
    LEFT JOIN nss.family_group fg ON fg.family_group_pk = fth.new_family_group_pk
    LEFT JOIN nss.organization o ON o.organization_pk = fg.sakha_organization_pk
    WHERE  fth.old_family_group_pk = %s
      AND  fth.transition_type IN (
               'NEW_FAMILY_FORMATION',
               'CHANGE_OF_FAMILY_UNIT',
               'MARRIAGE'
           )
"""

# Reverse direction: members who ARRIVED at this family from another one.
# Returns old-family persons connected to the arriving member as ghosts.
_ARRIVED_MEMBERS_SQL = """
    SELECT fth.person_pk   AS arrived_person_pk,
           fth.old_family_group_pk,
           fg.family_id    AS origin_family_id,
           fg.family_name  AS origin_family_name,
           o.organization_name AS origin_sakha_name
    FROM   nss.family_transition_history fth
    LEFT JOIN nss.family_group fg ON fg.family_group_pk = fth.old_family_group_pk
    LEFT JOIN nss.organization o ON o.organization_pk = fg.sakha_organization_pk
    WHERE  fth.new_family_group_pk = %s
      AND  fth.transition_type IN (
               'NEW_FAMILY_FORMATION',
               'CHANGE_OF_FAMILY_UNIT',
               'MARRIAGE'
           )
"""

# Ghost persons from the OLD family connected to an arrived member.
# Fetches ALL active members of the old family (not just direct links),
# so the entire origin tree appears as ghost nodes.
_ORIGIN_GHOST_PERSONS_SQL = """
    SELECT DISTINCT p.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           g.value_code AS gender_code
    FROM   nss.family_relationship fr
    JOIN   nss.person p ON p.person_pk = fr.person_pk
    LEFT JOIN nss.master_data g
           ON g.master_data_pk = p.gender_master_data_pk
    WHERE  fr.family_group_pk = %s
      AND  fr.is_current = TRUE
"""

# ALL active links from the OLD family — needed so the ghost tree
# is fully connected (not just the arrived person's direct links).
# Same "all current links for a family_group_pk" shape as _GRAPH_LINKS_SQL
# above — aliased, not redefined, so the two can't silently drift apart.
_ORIGIN_GHOST_LINKS_SQL = _GRAPH_LINKS_SQL

# Soft-deleted links between the arrived person and members
# of the old family (these reconnect the arrived person to the ghost tree).
# Includes links to BOTH active and departed members of the old family,
# since multiple persons may have departed the same family.
_ORIGIN_ARRIVED_LINKS_SQL = """
    SELECT DISTINCT ON (
               LEAST(fl.person_a_pk, fl.person_b_pk),
               GREATEST(fl.person_a_pk, fl.person_b_pk),
               fl.link_type
           )
           fl.person_a_pk,
           fl.person_b_pk,
           fl.link_type
    FROM   nss.family_link fl
    WHERE  fl.family_group_pk = %s
      AND  fl.is_current = FALSE
      AND  (fl.person_a_pk = %s OR fl.person_b_pk = %s)
"""

# Soft-deleted links for a departed person in a family (deduplicated).
# Prefer PARENT_OF over SPOUSE_OF when both exist between the same pair
# (guards against bad data from earlier testing).
# Only returns links where the OTHER person is a current active member
# of the family (still part of the graph).
_DEPARTED_LINKS_SQL = """
    SELECT DISTINCT ON (
               LEAST(fl.person_a_pk, fl.person_b_pk),
               GREATEST(fl.person_a_pk, fl.person_b_pk),
               fl.link_type
           )
           fl.person_a_pk,
           fl.person_b_pk,
           fl.link_type
    FROM   nss.family_link fl
    WHERE  fl.family_group_pk = %s
      AND  fl.is_current = FALSE
      AND  (fl.person_a_pk = %s OR fl.person_b_pk = %s)
      -- Other person must still be an active member of the family
      AND  EXISTS (
               SELECT 1 FROM nss.family_relationship fr
               WHERE  fr.family_group_pk = fl.family_group_pk
                 AND  fr.is_current = TRUE
                 AND  fr.person_pk = CASE
                          WHEN fl.person_a_pk = %s THEN fl.person_b_pk
                          ELSE fl.person_a_pk
                      END
           )
"""


@router.get(
    "/families/{family_group_pk}/graph",
    response_model=list[FamilyGraphMemberResponse],
)
def get_family_graph(
    family_group_pk: UUID,
    viewer_person_pk: UUID = Query(
        ..., description="Person PK of the logged-in viewer"
    ),
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[FamilyGraphMemberResponse]:
    """
    Compute family relationships dynamically relative to a viewer.

    Uses the ``family_link`` graph (direct PARENT_OF / SPOUSE_OF / SIBLING_OF edges)
    to derive all kinship labels via BFS traversal.  No static
    relationship codes are needed — labels adapt automatically when
    the viewer changes.

    Access: any current member of this family, or FAMILY_VIEW.
    """
    _require_family_view(conn, family_group_pk, user)

    # Fetch graph data (active members + links)
    with conn.cursor() as cur:
        cur.execute(_GRAPH_PERSONS_SQL, (str(family_group_pk),))
        cols = [desc[0] for desc in cur.description]
        person_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    with conn.cursor() as cur:
        cur.execute(_GRAPH_LINKS_SQL, (str(family_group_pk),))
        cols = [desc[0] for desc in cur.description]
        link_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Ensure the viewer (and all current members) are in the graph
    # even when the family has no links yet (e.g. SELF-only founder).
    existing_pks = {str(r["person_pk"]) for r in person_rows}
    if str(viewer_person_pk) not in existing_pks:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT p.person_pk, p.person_id,
                       p.first_name, p.middle_name, p.last_name,
                       g.value_code AS gender_code
                FROM   nss.family_relationship fr
                JOIN   nss.person p ON p.person_pk = fr.person_pk
                LEFT JOIN nss.master_data g
                       ON g.master_data_pk = p.gender_master_data_pk
                WHERE  fr.family_group_pk = %s
                  AND  fr.is_current = TRUE
            """, (str(family_group_pk),))
            cols = [desc[0] for desc in cur.description]
            for row in cur.fetchall():
                rd = dict(zip(cols, row))
                if str(rd["person_pk"]) not in existing_pks:
                    person_rows.append(rd)
                    existing_pks.add(str(rd["person_pk"]))

    # ── Departed members (ghost nodes) — DIRECTION A ────────────────
    # Persons who LEFT this family to form their own.
    # Include their soft-deleted links so BFS can still reach them.
    departed_info: dict[str, dict] = {}  # person_pk str → family info
    with conn.cursor() as cur:
        cur.execute(_DEPARTED_PERSONS_SQL, (str(family_group_pk),))
        cols = [desc[0] for desc in cur.description]
        departed_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    active_person_pks = {str(r["person_pk"]) for r in person_rows}

    for dep in departed_rows:
        dep_pk_str = str(dep["person_pk"])
        # Skip if the person is somehow still an active member
        if dep_pk_str in active_person_pks:
            continue

        # Store new-family info for later
        departed_info[dep_pk_str] = {
            "departed_family_group_pk": dep["new_family_group_pk"],
            "departed_family_id": dep.get("departed_family_id"),
            "departed_family_name": dep.get("departed_family_name"),
            "departed_sakha_name": dep.get("departed_sakha_name"),
        }

        # Add departed person to graph persons
        person_rows.append({
            "person_pk": dep["person_pk"],
            "person_id": dep["person_id"],
            "first_name": dep["first_name"],
            "middle_name": dep.get("middle_name"),
            "last_name": dep.get("last_name"),
            "gender_code": dep.get("gender_code"),
        })

        # Fetch their soft-deleted links (deduplicated)
        with conn.cursor() as cur2:
            dep_pk = str(dep["person_pk"])
            cur2.execute(_DEPARTED_LINKS_SQL, (
                str(family_group_pk),
                dep_pk, dep_pk, dep_pk,
            ))
            lcols = [desc[0] for desc in cur2.description]
            dep_links = [dict(zip(lcols, lrow)) for lrow in cur2.fetchall()]

        # If both PARENT_OF and SPOUSE_OF exist between the same pair,
        # keep only PARENT_OF (guards against corrupted test data).
        pair_types: dict[tuple, set] = {}
        for dl in dep_links:
            pair = (
                min(str(dl["person_a_pk"]), str(dl["person_b_pk"])),
                max(str(dl["person_a_pk"]), str(dl["person_b_pk"])),
            )
            pair_types.setdefault(pair, set()).add(dl["link_type"])

        for dl in dep_links:
            pair = (
                min(str(dl["person_a_pk"]), str(dl["person_b_pk"])),
                max(str(dl["person_a_pk"]), str(dl["person_b_pk"])),
            )
            # Skip SPOUSE_OF/SIBLING_OF if PARENT_OF exists for same pair
            # (PARENT_OF can't legitimately coexist with either on the
            # exact same pair; SIBLING_OF extension is a defensive
            # mirror of the pre-existing SPOUSE_OF guard, not a new rule)
            if dl["link_type"] in ("SPOUSE_OF", "SIBLING_OF") and "PARENT_OF" in pair_types[pair]:
                continue
            link_rows.append(dl)

    # ── Inter-departed links ─────────────────────────────────────────
    # When multiple persons departed the SAME family (e.g. Ramesh + Saraswati
    # both left F1), the per-departed query above only finds links where the
    # OTHER end is a current member.  Links between two departed persons
    # (e.g. Saraswati PARENT_OF Ramesh) are missed, causing wrong BFS labels
    # like "Step-Mother" instead of "Mother".  Fix: fetch soft-deleted links
    # where BOTH ends are departed.
    departed_pks = list(departed_info.keys())
    if len(departed_pks) >= 2:
        # Cast to UUID[] for psycopg2 — column is UUID, list is str
        from psycopg2.extras import execute_values  # noqa: already available
        departed_uuids = [UUID(pk) for pk in departed_pks]
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (
                           LEAST(fl.person_a_pk, fl.person_b_pk),
                           GREATEST(fl.person_a_pk, fl.person_b_pk),
                           fl.link_type
                       )
                       fl.person_a_pk,
                       fl.person_b_pk,
                       fl.link_type
                FROM   nss.family_link fl
                WHERE  fl.family_group_pk = %s
                  AND  fl.is_current = FALSE
                  AND  fl.person_a_pk = ANY(%s::uuid[])
                  AND  fl.person_b_pk = ANY(%s::uuid[])
            """, (str(family_group_pk), departed_pks, departed_pks))
            icols = [desc[0] for desc in cur.description]
            inter_links = [dict(zip(icols, row)) for row in cur.fetchall()]

        # Dedup: PARENT_OF wins over SPOUSE_OF for same pair
        ipair_types: dict[tuple, set] = {}
        for il in inter_links:
            ipair = (
                min(str(il["person_a_pk"]), str(il["person_b_pk"])),
                max(str(il["person_a_pk"]), str(il["person_b_pk"])),
            )
            ipair_types.setdefault(ipair, set()).add(il["link_type"])
        for il in inter_links:
            ipair = (
                min(str(il["person_a_pk"]), str(il["person_b_pk"])),
                max(str(il["person_a_pk"]), str(il["person_b_pk"])),
            )
            if il["link_type"] in ("SPOUSE_OF", "SIBLING_OF") and "PARENT_OF" in ipair_types[ipair]:
                continue
            link_rows.append(il)

    # ── Origin family ghosts — DIRECTION B ─────────────────────────
    # For members who ARRIVED at this family from another one,
    # include their old family's connected members as ghost nodes.
    # This makes the new family tree show the person's origin context.
    with conn.cursor() as cur:
        cur.execute(_ARRIVED_MEMBERS_SQL, (str(family_group_pk),))
        cols = [desc[0] for desc in cur.description]
        arrived_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    all_person_pks = {str(r["person_pk"]) for r in person_rows}

    for arr in arrived_rows:
        arrived_pk = str(arr["arrived_person_pk"])
        old_family_pk = str(arr["old_family_group_pk"])

        # Fetch ALL active members from the OLD family
        with conn.cursor() as cur2:
            cur2.execute(_ORIGIN_GHOST_PERSONS_SQL, (old_family_pk,))
            gcols = [desc[0] for desc in cur2.description]
            ghost_persons = [dict(zip(gcols, row)) for row in cur2.fetchall()]

        # Fetch ALL active links from the OLD family (internal edges)
        with conn.cursor() as cur2:
            cur2.execute(_ORIGIN_GHOST_LINKS_SQL, (old_family_pk,))
            lcols = [desc[0] for desc in cur2.description]
            ghost_links = [dict(zip(lcols, row)) for row in cur2.fetchall()]

        # Fetch soft-deleted links between arrived person and old family
        # (these reconnect the arrived person to the ghost tree)
        with conn.cursor() as cur2:
            cur2.execute(_ORIGIN_ARRIVED_LINKS_SQL, (
                old_family_pk, arrived_pk, arrived_pk,
            ))
            alcols = [desc[0] for desc in cur2.description]
            arrived_links = [dict(zip(alcols, row)) for row in cur2.fetchall()]

        # Add ghost persons (skip if already in graph)
        for gp in ghost_persons:
            gp_pk_str = str(gp["person_pk"])
            if gp_pk_str in all_person_pks:
                continue
            all_person_pks.add(gp_pk_str)
            person_rows.append(gp)
            # Mark as departed (pointing back to the old family)
            departed_info[gp_pk_str] = {
                "departed_family_group_pk": UUID(old_family_pk),
                "departed_family_id": arr.get("origin_family_id"),
                "departed_family_name": arr.get("origin_family_name"),
                "departed_sakha_name": arr.get("origin_sakha_name"),
            }

        # Add all active internal links from the old family
        for gl in ghost_links:
            link_rows.append(gl)

        # Add arrived person's soft-deleted links (with pair-type dedup)
        gpair_types: dict[tuple, set] = {}
        for gl in arrived_links:
            gpair = (
                min(str(gl["person_a_pk"]), str(gl["person_b_pk"])),
                max(str(gl["person_a_pk"]), str(gl["person_b_pk"])),
            )
            gpair_types.setdefault(gpair, set()).add(gl["link_type"])
        for gl in arrived_links:
            gpair = (
                min(str(gl["person_a_pk"]), str(gl["person_b_pk"])),
                max(str(gl["person_a_pk"]), str(gl["person_b_pk"])),
            )
            if gl["link_type"] in ("SPOUSE_OF", "SIBLING_OF") and "PARENT_OF" in gpair_types[gpair]:
                continue
            link_rows.append(gl)

    if not person_rows:
        return []

    # Build graph and compute
    graph = build_family_graph(person_rows, link_rows)
    computed = graph.compute_relationships(viewer_person_pk)

    # Look up current head
    with conn.cursor() as cur:
        cur.execute("""
            SELECT person_pk FROM nss.family_head_history
            WHERE  family_group_pk = %s AND effective_to IS NULL
        """, (str(family_group_pk),))
        head_row = cur.fetchone()
        head_pk = str(head_row[0]) if head_row else None

    # Build response — include spouse_person_pk, parent_person_pks,
    # and departed member info from graph adjacency
    results = []
    for member in computed:
        member_pk = UUID(member["person_pk"])
        member_pk_str = member["person_pk"]

        # Find spouse via SPOUSE edge in adjacency
        spouse_pk = None
        parent_pks = []
        for neighbor_pk, step in graph.adjacency.get(member_pk, []):
            if step == Step.SPOUSE:
                spouse_pk = neighbor_pk
            elif step == Step.UP:
                parent_pks.append(str(neighbor_pk))

        # Departed member info (ghost node)
        dep = departed_info.get(member_pk_str, {})

        results.append(FamilyGraphMemberResponse(
            person_pk=member_pk_str,
            person_id=member["person_id"],
            first_name=member["first_name"],
            middle_name=member["middle_name"],
            last_name=member["last_name"],
            gender_code=member["gender_code"],
            relationship_label=member["relationship_label"],
            generation=member["generation"],
            is_head=(member_pk_str == head_pk),
            spouse_person_pk=str(spouse_pk) if spouse_pk else None,
            parent_person_pks=parent_pks,
            is_departed=member_pk_str in departed_info,
            departed_family_group_pk=dep.get("departed_family_group_pk"),
            departed_family_id=dep.get("departed_family_id"),
            departed_family_name=dep.get("departed_family_name"),
            departed_sakha_name=dep.get("departed_sakha_name"),
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════
# 5. SAKHA ALIGNMENT (FAM-036 majority rule)
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/families/{family_group_pk}/sakha-alignment",
    response_model=FamilySakhaAlignmentResponse,
)
def get_family_sakha_alignment(
    family_group_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> FamilySakhaAlignmentResponse:
    """
    Compute Sakha alignment for a family.

    The family's effective Sakha is dynamically computed from the
    majority of its members' active affiliations (FAM-036).  When
    no members have affiliations the stored registration Sakha is
    used as fallback.

    Returns the effective Sakha, per-Sakha member counts, and
    per-member affiliation info with mismatch flags (member at a
    different Sakha than the family's effective Sakha).

    Access: any current member of this family, or FAMILY_VIEW.
    """
    _require_family_view(conn, family_group_pk, user)

    # 1. Fetch the family with its assigned Sakha
    sql = _family_select(_FAMILY_ONE) + " WHERE fg.family_group_pk = %s AND fg.is_active = TRUE"
    with conn.cursor() as cur:
        cur.execute(sql, (str(family_group_pk), str(family_group_pk)))
        family = row_to_model(cur, FamilyGroupResponse)
        if family is None:
            raise HTTPException(status_code=404, detail="Family not found")

    # 2. Get all current family members (persons)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fr.person_pk,
                   p.person_id,
                   p.first_name,
                   p.middle_name,
                   p.last_name
            FROM   nss.family_relationship fr
            JOIN   nss.person p ON p.person_pk = fr.person_pk
            WHERE  fr.family_group_pk = %s
              AND  fr.is_current = TRUE
            ORDER BY p.first_name
        """, (str(family_group_pk),))
        cols = [desc[0] for desc in cur.description]
        member_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    if not member_rows:
        return FamilySakhaAlignmentResponse(
            family_group_pk=family.family_group_pk,
            family_name=family.family_name,
            assigned_sakha_pk=family.sakha_organization_pk,
            assigned_sakha_name=family.sakha_name,
            assigned_sakha_code=family.sakha_code or "",
        )

    # 3. For each member, look up their active Sakha affiliation
    person_pks = [str(m["person_pk"]) for m in member_rows]
    placeholders = ",".join(["%s"] * len(person_pks))

    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT ss.person_pk,
                   aff.organization_pk  AS affiliated_sakha_pk,
                   o.organization_name  AS affiliated_sakha_name,
                   o.organization_code  AS affiliated_sakha_code
            FROM   nss.sangha_sevi ss
            JOIN   nss.membership_sakha_affiliation aff
                   ON aff.sangha_sevi_pk = ss.sangha_sevi_pk
                  AND aff.effective_to IS NULL
            JOIN   nss.organization o
                   ON o.organization_pk = aff.organization_pk
            WHERE  ss.person_pk IN ({placeholders})
              AND  ss.is_active = TRUE
        """, tuple(person_pks))
        cols = [desc[0] for desc in cur.description]
        aff_rows = {str(row[0]): dict(zip(cols, row)) for row in cur.fetchall()}

    # 4. Build per-member info
    members_info = []
    sakha_counts: dict[str, dict] = {}  # org_pk → {name, code, count}

    for m in member_rows:
        pk = str(m["person_pk"])
        aff = aff_rows.get(pk)
        has_membership = aff is not None

        affiliated_sakha_pk = None
        affiliated_sakha_name = None
        affiliated_sakha_code = None
        is_home = None

        if aff:
            affiliated_sakha_pk = aff["affiliated_sakha_pk"]
            affiliated_sakha_name = aff["affiliated_sakha_name"]
            affiliated_sakha_code = aff["affiliated_sakha_code"]
            is_home = (
                str(affiliated_sakha_pk) == str(family.sakha_organization_pk)
            )

            # Count per Sakha
            aff_pk_str = str(affiliated_sakha_pk)
            if aff_pk_str not in sakha_counts:
                sakha_counts[aff_pk_str] = {
                    "organization_pk": affiliated_sakha_pk,
                    "organization_name": affiliated_sakha_name,
                    "organization_code": affiliated_sakha_code,
                    "member_count": 0,
                }
            sakha_counts[aff_pk_str]["member_count"] += 1

        members_info.append(MemberSakhaInfo(
            person_pk=m["person_pk"],
            person_id=m["person_id"],
            first_name=m["first_name"],
            middle_name=m.get("middle_name"),
            last_name=m.get("last_name"),
            affiliated_sakha_pk=affiliated_sakha_pk,
            affiliated_sakha_name=affiliated_sakha_name,
            affiliated_sakha_code=affiliated_sakha_code,
            is_home_sakha=is_home,
            has_membership=has_membership,
        ))

    # 5. Compute majority Sakha
    # Same ordering as the SQL family_majority CTE (count desc, lowest
    # organization_pk on a tie) — see api/services/family_majority.py.
    affiliations = sorted(
        sakha_counts.values(),
        key=lambda x: sakha_majority_sort_key(x["member_count"], x["organization_pk"]),
    )

    majority_sakha_pk = None
    majority_sakha_name = None
    majority_sakha_code = None
    is_aligned = True

    if affiliations:
        top = affiliations[0]
        majority_sakha_pk = top["organization_pk"]
        majority_sakha_name = top["organization_name"]
        majority_sakha_code = top["organization_code"]
        is_aligned = (
            str(majority_sakha_pk) == str(family.sakha_organization_pk)
        )

    return FamilySakhaAlignmentResponse(
        family_group_pk=family.family_group_pk,
        family_name=family.family_name,
        assigned_sakha_pk=family.sakha_organization_pk,
        assigned_sakha_name=family.sakha_name,
        assigned_sakha_code=family.sakha_code or "",
        majority_sakha_pk=majority_sakha_pk,
        majority_sakha_name=majority_sakha_name,
        majority_sakha_code=majority_sakha_code,
        is_aligned=is_aligned,
        total_members=len(member_rows),
        members_with_affiliation=len(aff_rows),
        affiliations=[
            SakhaAffiliationCount(**a) for a in affiliations
        ],
        members=members_info,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 6. PERSON → FAMILIES (dashboard lookup)
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/person/{person_pk}/families",
    response_model=list[FamilyGroupResponse],
)
def get_person_families(
    person_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[FamilyGroupResponse]:
    """
    Get all families that contain this person as a current member.

    Used by the member dashboard to show the logged-in user's family.
    Returns an empty list (not 404) if the person has no family.

    Access: the person themselves, a current relative, or FAMILY_VIEW.
    """
    _require_person_family_view(conn, person_pk, user)

    person_families = """
        SELECT fr.family_group_pk
        FROM nss.family_relationship fr
        WHERE fr.person_pk = %s AND fr.is_current = TRUE
    """
    sql = _family_select(f"AND fr.family_group_pk IN ({person_families})") + f"""
    WHERE fg.family_group_pk IN ({person_families})
    AND fg.is_active = TRUE
    ORDER BY fg.family_name
    """
    with conn.cursor() as cur:
        cur.execute(sql, (str(person_pk), str(person_pk)))
        return rows_to_models(cur, FamilyGroupResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 7. PERSON MEMBERSHIP SUMMARY (for family tree Selected Person panel)
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/person/{person_pk}/membership-summary",
    response_model=PersonMembershipSummaryResponse,
)
def get_person_membership_summary(
    person_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> PersonMembershipSummaryResponse:
    """
    Lightweight membership snapshot for a person, used by the family
    tree's Selected Person panel.

    Bridges person_pk (family context) to sangha_sevi (membership context).
    Returns sangha_sevi_id, membership type/status, current sakha
    affiliation, and latest Parichaya Patra number.

    404 if the person does not exist (checked before the access gate, like
    every other endpoint); empty fields (not 404) if the person exists but
    has no membership record.

    Access: the person themselves, a current relative, or FAMILY_VIEW. The
    relative case is required — the dashboard fetches a summary for every
    member of the viewer's own family tree.
    """
    with conn.cursor() as cur:
        require_entity(cur, "person", str(person_pk), label="Person")

    _require_person_family_view(conn, person_pk, user)

    # Look up sangha_sevi by person_pk
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ss.sangha_sevi_pk,
                   ss.sangha_sevi_id,
                   mt.value_code  AS membership_type_code,
                   mt.value_name  AS membership_type_name,
                   ms.value_code  AS status_code,
                   ms.value_name  AS status_name,
                   o.organization_name,
                   aff.local_sakha_erp_id
            FROM   nss.sangha_sevi ss
            JOIN   nss.master_data mt
                   ON mt.master_data_pk = ss.membership_type_master_data_pk
            JOIN   nss.master_data ms
                   ON ms.master_data_pk = ss.membership_status_master_data_pk
            JOIN   nss.organization o
                   ON o.organization_pk = ss.organization_pk
            LEFT JOIN nss.membership_sakha_affiliation aff
                   ON aff.sangha_sevi_pk = ss.sangha_sevi_pk
                  AND aff.effective_to IS NULL
            WHERE  ss.person_pk = %s
              AND  ss.is_active = TRUE
            LIMIT  1
        """, (str(person_pk),))
        cols = [desc[0] for desc in cur.description]
        row = cur.fetchone()

    if not row:
        return PersonMembershipSummaryResponse()

    member = dict(zip(cols, row))
    sangha_sevi_pk = member["sangha_sevi_pk"]

    # Fetch latest Parichaya Patra
    pp_number = None
    pp_status = None
    pp_valid_to = None
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pp.document_number,
                   pp.status,
                   pp.valid_to
            FROM   nss.parichaya_patra pp
            WHERE  pp.sangha_sevi_pk = %s
            ORDER BY pp.valid_from DESC
            LIMIT  1
        """, (str(sangha_sevi_pk),))
        pp_row = cur.fetchone()
        if pp_row:
            pp_number, pp_status, pp_valid_to = pp_row

    # Fetch latest Anumati Patra (Darshaka / non-Associate only per MBR-019A/B)
    ap_number = None
    ap_status = None
    ap_valid_to = None
    if member["membership_type_code"] != "ASSOCIATE":
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ap.document_number,
                       ap.status,
                       ap.valid_to
                FROM   nss.anumati_patra ap
                WHERE  ap.sangha_sevi_pk = %s
                ORDER BY ap.valid_from DESC
                LIMIT  1
            """, (str(sangha_sevi_pk),))
            ap_row = cur.fetchone()
            if ap_row:
                ap_number, ap_status, ap_valid_to = ap_row

    return PersonMembershipSummaryResponse(
        sangha_sevi_id=member["sangha_sevi_id"],
        sangha_sevi_pk=sangha_sevi_pk,
        membership_type_code=member["membership_type_code"],
        membership_type_name=member["membership_type_name"],
        status_code=member["status_code"],
        status_name=member["status_name"],
        organization_name=member["organization_name"],
        local_sakha_erp_id=member["local_sakha_erp_id"],
        parichaya_patra_number=pp_number,
        parichaya_patra_status=pp_status,
        parichaya_patra_valid_to=pp_valid_to,
        anumati_patra_number=ap_number,
        anumati_patra_status=ap_status,
        anumati_patra_valid_to=ap_valid_to,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 7b. SHARED family_link HELPERS (SIBLING_OF — owner decision, 2026-10-22)
# ═══════════════════════════════════════════════════════════════════════════
#
# One shared INSERT path for family_link rows, used by add_family_member,
# create_family_link, AND scripts/backfill_sibling_links.py (a one-time
# live-data fix — see that script). Keeping the SQL in one place avoids a
# second parallel implementation drifting out of sync (standing rule,
# CLAUDE.md "Shared code — no duplicates").

_SYMMETRIC_LINK_TYPES = ("SPOUSE_OF", "SIBLING_OF")


def persons_share_parent(cur, family_group_pk: str, person_a_pk: str, person_b_pk: str) -> bool:
    """
    True if person_a and person_b already have a common parent via a
    current PARENT_OF edge in this family — i.e. the shared-parent-derived
    sibling relationship already works for this pair, so a direct
    SIBLING_OF edge between them would be redundant (see family_graph.py's
    SIBLING_OF handling note for why the redundant edge, once it DOES
    exist for another reason, is left in place rather than deleted).
    """
    cur.execute("""
        SELECT 1
        FROM   nss.family_link p1
        JOIN   nss.family_link p2
               ON  p2.family_group_pk = p1.family_group_pk
               AND p2.person_a_pk = p1.person_a_pk
               AND p2.link_type = 'PARENT_OF'
               AND p2.is_current = TRUE
        WHERE  p1.family_group_pk = %s
          AND  p1.link_type = 'PARENT_OF'
          AND  p1.is_current = TRUE
          AND  p1.person_b_pk = %s
          AND  p2.person_b_pk = %s
    """, (str(family_group_pk), str(person_a_pk), str(person_b_pk)))
    return cur.fetchone() is not None


def family_link_exists(cur, family_group_pk: str, person_a_pk: str, person_b_pk: str, link_type: str) -> bool:
    """Current family_link of this type already connects the pair (either
    direction for the symmetric types SPOUSE_OF/SIBLING_OF)."""
    if link_type in _SYMMETRIC_LINK_TYPES:
        cur.execute("""
            SELECT 1 FROM nss.family_link
            WHERE  family_group_pk = %s
              AND  link_type = %s
              AND  ((person_a_pk = %s AND person_b_pk = %s)
                OR  (person_a_pk = %s AND person_b_pk = %s))
              AND  is_current = TRUE
        """, (
            str(family_group_pk), link_type,
            str(person_a_pk), str(person_b_pk),
            str(person_b_pk), str(person_a_pk),
        ))
    else:
        cur.execute("""
            SELECT 1 FROM nss.family_link
            WHERE  family_group_pk = %s
              AND  person_a_pk = %s
              AND  person_b_pk = %s
              AND  link_type = %s
              AND  is_current = TRUE
        """, (str(family_group_pk), str(person_a_pk), str(person_b_pk), link_type))
    return cur.fetchone() is not None


def insert_family_link_edge(
    cur,
    *,
    family_group_pk: str,
    person_a_pk: str,
    person_b_pk: str,
    link_type: str,
    effective_from,
    actor_pk: str | None = None,
    actor_user_account_pk: str | None = None,
) -> str | None:
    """
    Insert one nss.family_link row, with the dedup/redundancy checks that
    both live endpoints need:

      - family_link_exists(): never create a second current edge of the
        same type for the same pair (checked bidirectionally for the
        symmetric types SPOUSE_OF/SIBLING_OF).
      - For SIBLING_OF specifically: skip the insert when
        persons_share_parent() already holds — the shared-parent-derived
        sibling relationship already works for this pair, so a direct
        edge would be redundant (owner decision; see family_graph.py).

    Returns the new family_link_pk, or None when the insert was skipped
    (either reason above). Does not raise on a skip — a skip is a normal,
    expected outcome, not an error.
    """
    if link_type == "SIBLING_OF" and persons_share_parent(cur, family_group_pk, person_a_pk, person_b_pk):
        return None

    if family_link_exists(cur, family_group_pk, person_a_pk, person_b_pk, link_type):
        return None

    cur.execute("""
        INSERT INTO nss.family_link
            (family_group_pk, person_a_pk, person_b_pk, link_type,
             effective_from, is_current)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        RETURNING family_link_pk
    """, (
        str(family_group_pk),
        str(person_a_pk),
        str(person_b_pk),
        link_type,
        effective_from,
    ))
    fl_pk = cur.fetchone()[0]
    log_audit(cur, action="CREATE", table_name="family_link", record_pk=str(fl_pk),
              actor_pk=actor_pk, actor_user_account_pk=actor_user_account_pk,
              module="family", summary=f"Created {link_type} family link in family {family_group_pk}")
    return str(fl_pk)


# ═══════════════════════════════════════════════════════════════════════════
# 8. ADD MEMBER TO FAMILY (Tier 5 — authenticated write)
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/families/{family_group_pk}/members",
    response_model=FamilyMemberResponse,
    status_code=201,
)
def add_family_member(
    family_group_pk: UUID,
    body: AddFamilyMemberRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> FamilyMemberResponse:
    """
    Add a person to an existing family group.

    Authorization: the family head or a family admin (or FAMILY_MANAGE).
    Being merely a member of the family is NOT sufficient.
    Validates:
      - Family exists and is active
      - Requester is the family head or a family admin
      - Target person exists
      - Target person is not already a current member
      - relationship_type_code / link_type / link target are valid (all
        checked BEFORE any write)
      - If the target currently belongs to another family, the requester is
        the target themselves or holds head/admin authority (or
        FAMILY_MANAGE) over that family; otherwise 403. The old family's
        relationship, links and admin row are closed, headship passes to a
        successor if the target was its head, and it is dissolved if
        nobody remains.
      - If link_type provided, creates a family_link edge
    """
    today = date_type.today()

    # 2. Verify requester may change this family's membership
    _require_family_manage(conn, family_group_pk, user)

    # 3. Verify target person exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.person
            WHERE  person_pk = %s AND is_active = TRUE
        """, (str(body.person_pk),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Person not found")

    # 4. Verify target not already a current member
    if _is_current_member(conn, str(family_group_pk), str(body.person_pk)):
        raise HTTPException(
            status_code=409,
            detail="This person is already a current member of the family",
        )

    # 5. Validate EVERYTHING in the request before the first write, so a bad
    #    relationship_type_code / link_type can never leave the target already
    #    pulled out of their previous family (the request is atomic per
    #    transaction, but later checks must not depend on rollback to undo a
    #    half-applied move).
    with conn.cursor() as cur:
        relationship_type_pk = _resolve_relationship_type_pk(cur, body.relationship_type_code)

    if body.link_type:
        if body.link_type not in ("PARENT_OF", "SPOUSE_OF", "SIBLING_OF"):
            raise HTTPException(
                status_code=400,
                detail="link_type must be PARENT_OF, SPOUSE_OF or SIBLING_OF",
            )
        if not body.link_target_person_pk:
            raise HTTPException(
                status_code=400,
                detail="link_target_person_pk is required when link_type is set",
            )
        if not _is_current_member(conn, str(family_group_pk), str(body.link_target_person_pk)):
            raise HTTPException(
                status_code=400,
                detail="link_target_person_pk must be a current family member",
            )

    # 6. Moving a person out of another family needs consent: the requester
    #    must be that person themselves, or hold authority over each family
    #    being left (its head/admin, or FAMILY_MANAGE). A head of THIS family
    #    alone can never pull someone out of a family they have no say in.
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fr.family_group_pk
            FROM   nss.family_relationship fr
            WHERE  fr.person_pk = %s
              AND  fr.is_current = TRUE
              AND  fr.family_group_pk <> %s
        """, (str(body.person_pk), str(family_group_pk)))
        old_families = [str(r[0]) for r in cur.fetchall()]

    if old_families and str(body.person_pk) != str(user.person_pk):
        for old_fam_str in old_families:
            _require_family_manage(
                conn, old_fam_str, user,
                detail=(
                    "This person already belongs to another family. Only that "
                    "family's head or admin (or the person themselves) can "
                    "move them into a new one."
                ),
            )

    # 7. Leave the old family(ies): relationship, links, admin row closed,
    #    head succession, dissolve if memberless — then the transition row so
    #    ghost nodes work bidirectionally.
    trans_type = (
        "MARRIAGE" if body.relationship_type_code == "SPOUSE" else "CHANGE_OF_FAMILY_UNIT"
    )
    for old_fam_str in old_families:
        with conn.cursor() as cur:
            close_family_membership(
                cur, family_group_pk=old_fam_str, person_pk=str(body.person_pk),
                on_date=today,
                remark=f"Transferred to {str(family_group_pk)[:8]}",
                head_reason="Auto-assigned: previous head left the family",
                actor_pk=user.actor_pk,
                actor_user_account_pk=str(user.user_account_pk),
            )
            cur.execute("""
                INSERT INTO nss.family_transition_history
                    (person_pk, old_family_group_pk, new_family_group_pk,
                     transition_type, transition_reason, effective_date)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                str(body.person_pk),
                old_fam_str,
                str(family_group_pk),
                trans_type,
                "Member added to new family via Add Member",
                today,
            ))

    # 8. Insert family_relationship
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nss.family_relationship
                (family_group_pk, person_pk, relationship_type_master_data_pk,
                 effective_from, is_current, remarks)
            VALUES (%s, %s, %s, %s, TRUE, %s)
            RETURNING family_relationship_pk
        """, (
            str(family_group_pk),
            str(body.person_pk),
            str(relationship_type_pk),
            today,
            body.remarks,
        ))
        new_pk = cur.fetchone()[0]
        actor = user.actor_pk
        log_audit(cur, action="CREATE", table_name="family_relationship", record_pk=str(new_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="family", summary=f"Added member {body.person_pk} to family {family_group_pk}")

    # 8b. Optionally insert the family_link edge (already validated above)
    if body.link_type:
        with conn.cursor() as cur:
            insert_family_link_edge(
                cur,
                family_group_pk=str(family_group_pk),
                person_a_pk=str(body.person_pk),
                person_b_pk=str(body.link_target_person_pk),
                link_type=body.link_type,
                effective_from=today,
                actor_pk=user.actor_pk,
                actor_user_account_pk=str(user.user_account_pk),
            )

    # 9. Return the newly created member row
    sql = (
        _MEMBER_SELECT
        + " WHERE fr.family_relationship_pk = %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (str(new_pk),))
        result = row_to_model(cur, FamilyMemberResponse)
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to fetch created member")
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 8b. CREATE FAMILY LINK (Tier 5 — authenticated write)
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/families/{family_group_pk}/links",
    response_model=MessageResponse,
    status_code=201,
)
def create_family_link(
    family_group_pk: UUID,
    body: CreateFamilyLinkRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Create an additional family_link edge in a family group.

    Used for auto-inferred links when adding family members:
    e.g., adding a Father also creates SPOUSE_OF with existing Mother,
    PARENT_OF links to siblings, or (owner decision, 2026-10-22) a direct
    SIBLING_OF edge when adding a Brother/Sister with no parent yet on
    file (see insert_family_link_edge / family_graph.py).

    Authorization: the family head or a family admin (or FAMILY_MANAGE) —
    this accompanies add_family_member and carries the same authority.
    Both person_a and person_b must be current members.
    """
    today = date_type.today()

    if body.link_type not in ("PARENT_OF", "SPOUSE_OF", "SIBLING_OF"):
        raise HTTPException(
            status_code=400,
            detail="link_type must be PARENT_OF, SPOUSE_OF or SIBLING_OF",
        )

    # 2. Verify requester may change this family's membership
    _require_family_manage(conn, family_group_pk, user)

    # 3. Verify both persons are current members
    for pk_label, pk_val in [("person_a", body.person_a_pk), ("person_b", body.person_b_pk)]:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM nss.family_relationship
                WHERE  family_group_pk = %s
                  AND  person_pk = %s
                  AND  is_current = TRUE
            """, (str(family_group_pk), str(pk_val)))
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"{pk_label}_pk must be a current family member",
                )

    # 4/5. Dedup + redundant-edge check + insert (shared with
    # add_family_member and scripts/backfill_sibling_links.py).
    with conn.cursor() as cur:
        fl_pk = insert_family_link_edge(
            cur,
            family_group_pk=str(family_group_pk),
            person_a_pk=str(body.person_a_pk),
            person_b_pk=str(body.person_b_pk),
            link_type=body.link_type,
            effective_from=today,
            actor_pk=user.actor_pk,
            actor_user_account_pk=str(user.user_account_pk),
        )
        if fl_pk is None:
            # Either an identical current edge already exists, or (for
            # SIBLING_OF) the pair already shares a parent — either way,
            # nothing to do, and this is not an error condition.
            return MessageResponse(message="Link already exists")

    return MessageResponse(message="Family link created successfully")


# ═══════════════════════════════════════════════════════════════════════════
# 9. REMOVE MEMBER FROM FAMILY (Tier 5 — authenticated write, head only)
# ═══════════════════════════════════════════════════════════════════════════


@router.delete(
    "/families/{family_group_pk}/members",
    response_model=MessageResponse,
)
def remove_family_member(
    family_group_pk: UUID,
    body: RemoveFamilyMemberRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Remove (soft-delete) a member from a family.

    Authorization: the current family head OR a family admin (or
    FAMILY_MANAGE) can remove members (FAM-048). Neither can remove
    themselves.

    Sets is_current=FALSE, effective_to=today on the family_relationship,
    all associated family_link rows and any current family_admin row. The
    head cannot be removed by a family admin (403); a FAMILY_MANAGE
    administrator may, in which case headship passes to a successor.
    """
    today = date_type.today()

    # 2. Verify requester may change this family's membership
    _require_family_manage(conn, family_group_pk, user)

    # 3. Cannot remove yourself (the head or admin)
    if str(body.person_pk) == str(user.person_pk):
        raise HTTPException(
            status_code=400,
            detail="You cannot remove yourself from the family",
        )

    # 4. Verify target is a current member
    if not _is_current_member(conn, str(family_group_pk), str(body.person_pk)):
        raise HTTPException(
            status_code=404,
            detail="Person is not a current member of this family",
        )

    # 5. Nobody but a FAMILY_MANAGE administrator may remove the current head
    #    (a family admin or the head's own authority chain cannot): the head
    #    must first hand over headship via transfer-head (FAM-050).
    if (
        _is_current_head(conn, str(family_group_pk), str(body.person_pk))
        and not _has_scoped_family_permission(conn, family_group_pk, user, "FAMILY_MANAGE")
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "The family head cannot be removed. Transfer headship to "
                "another member first."
            ),
        )

    # 6. Soft-delete: relationship + links + admin row closed, head succession
    #    if a FAMILY_MANAGE administrator removed the head, dissolve if the
    #    family is left memberless (shared with create/add-member moves).
    with conn.cursor() as cur:
        res = close_family_membership(
            cur, family_group_pk=str(family_group_pk),
            person_pk=str(body.person_pk), on_date=today,
            remark=body.remarks or "Removed by family head",
            head_reason="Auto-assigned: previous head was removed",
            actor_pk=user.actor_pk,
            actor_user_account_pk=str(user.user_account_pk),
        )
        log_audit(cur, action="DELETE", table_name="family_relationship",
                  record_pk=res["relationship_pk"],
                  actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
                  module="family", summary="Removed family member")

    return MessageResponse(message="Member removed from family successfully")


# ── Family Admin Endpoints (FAM-045–FAM-052) ─────────────────────────


_ADMIN_SELECT = """
    SELECT fa.family_admin_pk,
           fa.family_group_pk,
           fa.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           fa.effective_from,
           fa.effective_to,
           fa.appointed_by_person_pk,
           fa.remarks
    FROM   nss.family_admin fa
    JOIN   nss.person p
           ON p.person_pk = fa.person_pk
"""


@router.get(
    "/families/{family_group_pk}/admins",
    response_model=list[FamilyAdminResponse],
)
def list_family_admins(
    family_group_pk: UUID,
    current_only: bool = True,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[FamilyAdminResponse]:
    """
    List family admins (current by default, or all for history).

    Access: any current member of this family, or FAMILY_VIEW.
    """
    _require_family_view(conn, family_group_pk, user)

    with conn.cursor() as cur:
        if current_only:
            cur.execute(
                _ADMIN_SELECT + " WHERE fa.family_group_pk = %s AND fa.effective_to IS NULL"
                " ORDER BY fa.effective_from",
                (str(family_group_pk),),
            )
        else:
            cur.execute(
                _ADMIN_SELECT + " WHERE fa.family_group_pk = %s"
                " ORDER BY fa.effective_from DESC",
                (str(family_group_pk),),
            )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return [FamilyAdminResponse(**dict(zip(cols, r))) for r in rows]


@router.post(
    "/families/{family_group_pk}/admins",
    response_model=FamilyAdminResponse,
    status_code=201,
)
def assign_family_admin(
    family_group_pk: UUID,
    body: AssignFamilyAdminRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> FamilyAdminResponse:
    """
    Assign a family member as Family Admin.

    Authorization: only the current Family Head (FAM-046), or FAMILY_MANAGE.
    Head may assign themselves (FAM-047).
    """
    fg_str = str(family_group_pk)
    person_str = str(body.person_pk)

    # 2. Requester must be the current Head
    _require_family_head(conn, family_group_pk, user)

    # 3. Target must be a current member
    if not _is_current_member(conn, fg_str, person_str):
        raise HTTPException(
            status_code=400,
            detail="Person is not a current member of this family",
        )

    # 4. Check not already an active admin
    if _is_current_admin(conn, fg_str, person_str):
        raise HTTPException(
            status_code=409,
            detail="Person is already a current admin of this family",
        )

    # 5. Insert admin record
    today = date_type.today()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nss.family_admin
                (family_group_pk, person_pk, effective_from,
                 appointed_by_person_pk, remarks)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING family_admin_pk
        """, (
            fg_str, person_str, str(today),
            str(user.person_pk),
            body.remarks,
        ))
        admin_pk = cur.fetchone()[0]
        actor = user.actor_pk
        log_audit(cur, action="CREATE", table_name="family_admin", record_pk=str(admin_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="family", summary=f"Assigned family admin for family {family_group_pk}")

    # 6. Return the created record
    with conn.cursor() as cur:
        cur.execute(
            _ADMIN_SELECT + " WHERE fa.family_admin_pk = %s",
            (str(admin_pk),),
        )
        row = cur.fetchone()
        cols = [d[0] for d in cur.description]
    return FamilyAdminResponse(**dict(zip(cols, row)))


@router.delete(
    "/families/{family_group_pk}/admins",
    response_model=MessageResponse,
)
def revoke_family_admin(
    family_group_pk: UUID,
    body: RevokeFamilyAdminRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Revoke a Family Admin role.

    Authorization: only the current Family Head (FAM-046), or FAMILY_MANAGE.
    Closes the admin record (sets effective_to = today).
    """
    fg_str = str(family_group_pk)

    # 1. Requester must be the current Head
    _require_family_head(conn, family_group_pk, user)

    # 2. Find the active admin record
    with conn.cursor() as cur:
        cur.execute("""
            SELECT family_admin_pk
            FROM   nss.family_admin
            WHERE  family_group_pk = %s
              AND  person_pk = %s
              AND  effective_to IS NULL
        """, (fg_str, str(body.person_pk)))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Person is not a current admin of this family",
            )

    # 3. Close the record
    today = date_type.today()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE nss.family_admin
            SET    effective_to = %s,
                   remarks = CASE
                       WHEN remarks IS NOT NULL
                       THEN remarks || ' | Revoked: ' || %s
                       ELSE 'Revoked: ' || %s
                   END,
                   updated_at = CURRENT_TIMESTAMP
            WHERE  family_admin_pk = %s
        """, (
            str(today),
            body.remarks or "Revoked by head",
            body.remarks or "Revoked by head",
            str(row[0]),
        ))
        actor = user.actor_pk
        log_audit(cur, action="DELETE", table_name="family_admin", record_pk=str(row[0]),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="family", summary="Revoked family admin")

    return MessageResponse(message="Admin role revoked successfully")


@router.post(
    "/families/{family_group_pk}/transfer-head",
    response_model=MessageResponse,
)
def transfer_family_head(
    family_group_pk: UUID,
    body: TransferHeadRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """
    Transfer Family Head role to another family member.

    Authorization: only the current Head (FAM-049, FAM-050), or FAMILY_MANAGE.
    The previous head's admin role (if any) is preserved.
    """
    fg_str = str(family_group_pk)
    new_head_str = str(body.person_pk)
    today = date_type.today()

    # 2. Requester must be the current Head
    _require_family_head(conn, family_group_pk, user)

    # 3. Cannot transfer to the person who is already head
    if _is_current_head(conn, fg_str, new_head_str):
        raise HTTPException(
            status_code=400,
            detail="You are already the family head"
            if new_head_str == str(user.person_pk)
            else "Person is already the family head",
        )

    # 4. New head must be a current member
    if not _is_current_member(conn, fg_str, new_head_str):
        raise HTTPException(
            status_code=400,
            detail="Person is not a current member of this family",
        )

    # 5. Close the current head record — whoever holds it (a FAMILY_MANAGE
    #    administrator acts on a family they are not head of, so closing only
    #    the caller's own row would leave two current heads, FAM-051).
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE nss.family_head_history
            SET    effective_to = %s,
                   reason = COALESCE(reason, '') || ' — transferred to new head',
                   updated_at = CURRENT_TIMESTAMP
            WHERE  family_group_pk = %s
              AND  effective_to IS NULL
        """, (str(today), fg_str))

    # 6. Create new head record
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nss.family_head_history
                (family_group_pk, person_pk, effective_from, reason)
            VALUES (%s, %s, %s, %s)
            RETURNING family_head_history_pk
        """, (
            fg_str, new_head_str, str(today),
            body.remarks or "Headship transferred",
        ))
        new_fhh_pk = cur.fetchone()[0]
        actor = user.actor_pk
        log_audit(cur, action="UPDATE", table_name="family_head_history", record_pk=str(new_fhh_pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="family", summary=f"Transferred family head to person {body.person_pk}")

    return MessageResponse(message="Family head transferred successfully")
