"""
Organization API router — Tier 2 endpoints.

8 GET endpoints across the organization table plus Foundation
master_data (for type/status), plus 2 wing-body endpoints. Gated by
require_permission("ORGANIZATION_VIEW") on the Tier 5 branch.
nss_db_backend connects with SELECT-only privileges.

Endpoint groups:
  - Reference:   types, statuses (from master_data)
  - Core:        organizations (list, detail, children)
  - Aggregation: children-stats (recursive family/member/person counts per
                 direct child), stats (same recursive counts collapsed to
                 one row of totals for the requested org's whole subtree)
  - Wings:       wings (Mahila/Kumari/Sevak org + member counts over the
                 subtree), wings/{type}/members (the derived roster).
                 Tier-independent: the same subtree walk serves Sakha,
                 Anchalika, Zilla and Kendra.
  - Navigation:  hierarchy (recursive CTE tree)

Organization type values are stored in Foundation master_data
under category ORGANIZATION_TYPE. Status values use the unified
ERP-wide STATUS category (shared across all modules).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.database import get_connection
from api.dependencies.auth import get_current_user
from api.dependencies.rbac import require_permission
from api.helpers import DEFAULT_LIMIT, MAX_LIMIT, row_to_model, rows_to_models, FAMILY_MAJORITY_CTE_SQL, ORGANIZATION_ADDRESS_JOINS_SQL
from api.services.rbac_service import UserContext, require_org_in_scope, actor_scope_org_pks
from api.schemas.organization import (
    OrgChildStatsResponse,
    OrgStatsResponse,
    OrgWingResponse,
    OrgWingSummaryResponse,
    OrganizationHierarchyNodeResponse,
    OrganizationResponse,
    OrganizationTypeResponse,
    StatusResponse,
    WingMemberListResponse,
    WingMemberResponse,
)

router = APIRouter(prefix="/api/v1/organization", tags=["organization"])


# ── Shared SQL fragment for the organization SELECT ──────────────────────

_ORG_SELECT = f"""
    SELECT o.organization_pk,
           o.organization_id,
           o.organization_name,
           o.organization_code,
           o.short_code,
           ot.master_data_pk   AS organization_type_pk,
           ot.value_code       AS organization_type_code,
           ot.value_name       AS organization_type_name,
           os.master_data_pk   AS status_pk,
           os.value_code       AS status_code,
           os.value_name       AS status_name,
           o.parent_organization_pk,
           p.organization_name AS parent_organization_name,
           pt.value_code       AS parent_organization_type_code,
           o.address_line_1,
           o.address_line_2,
           o.phone_number,
           o.country_phone_code,
           o.mobile_number,
           o.email,
           o.org_email,
           o.website_url,
           o.org_website_url,
           o.youtube_channel_url,
           o.org_youtube_channel_url,
           o.district_pk,
           d.district_name,
           o.state_pk,
           s.state_name,
           o.country_pk,
           c.country_name,
           o.city_village_pk,
           cv.city_village_name,
           o.postal_code_pk,
           pc.postal_code,
           o.latitude,
           o.longitude,
           o.is_active
    FROM   nss.organization o
    JOIN   nss.master_data ot
           ON ot.master_data_pk = o.organization_type_master_data_pk
    JOIN   nss.master_data os
           ON os.master_data_pk = o.status_master_data_pk
    LEFT JOIN nss.organization p
           ON p.organization_pk = o.parent_organization_pk
    LEFT JOIN nss.master_data pt
           ON pt.master_data_pk = p.organization_type_master_data_pk
    {ORGANIZATION_ADDRESS_JOINS_SQL}
"""


# ═══════════════════════════════════════════════════════════════════════════
# 1. REFERENCE DATA
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/types", response_model=list[OrganizationTypeResponse])
def list_organization_types(
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> list[OrganizationTypeResponse]:
    """List all active organization types (10 frozen types from master_data)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT md.master_data_pk  AS organization_type_pk,
                   md.value_code      AS organization_type_code,
                   md.value_name      AS organization_type_name,
                   md.description,
                   md.display_order   AS sort_order,
                   md.is_active
            FROM   nss.master_data md
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  mc.category_code = 'ORGANIZATION_TYPE'
              AND  md.is_active = TRUE
            ORDER BY md.display_order
        """)
        return rows_to_models(cur, OrganizationTypeResponse)


@router.get("/statuses", response_model=list[StatusResponse])
def list_statuses(
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> list[StatusResponse]:
    """List active lifecycle statuses applicable to the Organization module."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT md.master_data_pk  AS status_pk,
                   md.value_code      AS status_code,
                   md.value_name      AS status_name,
                   md.description,
                   md.display_order   AS sort_order,
                   md.is_active
            FROM   nss.master_data md
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  mc.category_code = 'STATUS'
              AND  md.is_active = TRUE
              AND  ('ORGANIZATION' = ANY(md.applicable_modules)
                    OR md.applicable_modules IS NULL)
            ORDER BY md.display_order
        """)
        return rows_to_models(cur, StatusResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 2. ORGANIZATIONS (core CRUD-read)
# ═══════════════════════════════════════════════════════════════════════════


def fetch_organizations(cur, type_code: str | None = None, status_code: str | None = None,
                         country_pk: UUID | None = None,
                         state_pk: UUID | None = None, district_pk: UUID | None = None,
                         postal_code_pk: UUID | None = None,
                         limit: int = DEFAULT_LIMIT, offset: int = 0,
                         *, type_codes: list[str] | None = None):
    """
    Shared query behind list_organizations() — factored out so the public
    self-registration Sakha-list endpoint (api/routers/registration.py) can
    reuse the exact same SQL/response shape rather than a duplicated copy.

    country_pk/state_pk/district_pk/postal_code_pk (SOL-ARCH-010 Amendment,
    2026-10-01) let callers narrow the list to a geographic area — e.g.
    "find a Sakha Sangha near me" — using the same direct FKs already on
    nss.organization (o.country_pk, o.state_pk, o.district_pk,
    o.postal_code_pk). NOTE: state_pk/district_pk are only populated for
    branches whose PIN resolved to a city_village district during seed
    (05_sakha_branches.sql backfill); country_pk is always set, so country
    is the most reliable geographic narrower.

    type_codes (keyword-only, 2026-10-02) is an OR-matched alternative to
    type_code for "find a Sakha OR Patha Chakra near me" — passing both
    SAKHA_SANGHA and PATHA_CHAKRA in one call instead of two round trips.
    Takes precedence over type_code when given.
    """
    sql = _ORG_SELECT + " WHERE o.is_active = TRUE"
    params: list = []

    if type_codes:
        sql += " AND ot.value_code = ANY(%s)"
        params.append(list(type_codes))
    elif type_code is not None:
        sql += " AND ot.value_code = %s"
        params.append(type_code)
    if status_code is not None:
        sql += " AND os.value_code = %s"
        params.append(status_code)
    if country_pk is not None:
        sql += " AND o.country_pk = %s"
        params.append(str(country_pk))
    if state_pk is not None:
        sql += " AND o.state_pk = %s"
        params.append(str(state_pk))
    if district_pk is not None:
        sql += " AND o.district_pk = %s"
        params.append(str(district_pk))
    if postal_code_pk is not None:
        sql += " AND o.postal_code_pk = %s"
        params.append(str(postal_code_pk))

    sql += " ORDER BY ot.display_order, o.organization_name"
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cur.execute(sql, tuple(params))
    return rows_to_models(cur, OrganizationResponse)


@router.get("/organizations", response_model=list[OrganizationResponse])
def list_organizations(
    type_code: str | None = Query(None, description="Filter by organization type code"),
    status_code: str | None = Query(None, description="Filter by status code"),
    country_pk: UUID | None = Query(None, description="Filter by country"),
    state_pk: UUID | None = Query(None, description="Filter by state"),
    district_pk: UUID | None = Query(None, description="Filter by district"),
    postal_code_pk: UUID | None = Query(None, description="Filter by postal code"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> list[OrganizationResponse]:
    """
    List all active organizations with resolved type, status, and parent.

    Optionally filter by type_code, status_code, or geography
    (country_pk/state_pk/district_pk/postal_code_pk). Supports pagination
    via limit/offset (default 100, max 500).
    """
    with conn.cursor() as cur:
        return fetch_organizations(cur, type_code, status_code, country_pk, state_pk,
                                    district_pk, postal_code_pk, limit, offset)


@router.get("/organizations/selectable", response_model=list[OrganizationResponse])
def list_selectable_organizations(
    type_code: list[str] | None = Query(None, description="Filter by organization type code — repeat the param for an OR match across types (e.g. ?type_code=SAKHA_SANGHA&type_code=PATHA_CHAKRA)"),
    country_pk: UUID | None = Query(None, description="Filter by country — e.g. 'find a Sakha near me'"),
    state_pk: UUID | None = Query(None, description="Filter by state — e.g. 'find a Sakha near me'"),
    district_pk: UUID | None = Query(None, description="Filter by district"),
    postal_code_pk: UUID | None = Query(None, description="Filter by postal code"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[OrganizationResponse]:
    """
    Member-facing organization lookup for selection dropdowns.

    Gated on authentication only (NOT ORGANIZATION_VIEW): a regular member
    creating their own family needs to pick their Sakha Sangha, but does not
    hold the administrative ORGANIZATION_VIEW permission. The public
    self-registration page already exposes the same Sakha list unauthenticated
    (register.py), so surfacing active organizations to a logged-in member is
    strictly less sensitive. Only active organizations are returned.

    country_pk/state_pk/district_pk/postal_code_pk (SOL-ARCH-010 Amendment,
    2026-10-01) support a "find a Sakha/Patha Chakra near me" search by
    narrowing the list to a geographic area before the member picks from it.

    type_code accepts repeats (2026-10-02) so the member-dashboard
    find-a-Sakha-or-Patha-Chakra directory can fetch both types in one call.
    """
    with conn.cursor() as cur:
        return fetch_organizations(cur, status_code=None, country_pk=country_pk,
                                    state_pk=state_pk, district_pk=district_pk,
                                    postal_code_pk=postal_code_pk,
                                    limit=limit, offset=offset,
                                    type_codes=type_code)


@router.get(
    "/organizations/{organization_pk}",
    response_model=OrganizationResponse,
)
def get_organization(
    organization_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> OrganizationResponse:
    """Get a single organization by PK with full resolved context."""
    sql = _ORG_SELECT + " WHERE o.organization_pk = %s AND o.is_active = TRUE"

    with conn.cursor() as cur:
        cur.execute(sql, (str(organization_pk),))
        result = row_to_model(cur, OrganizationResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        return result


@router.get(
    "/organizations/{organization_pk}/children",
    response_model=list[OrganizationResponse],
)
def list_organization_children(
    organization_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> list[OrganizationResponse]:
    """
    List direct children of a given organization.

    Returns 404 if the parent organization_pk does not exist.
    Useful for navigating the organizational hierarchy one level at a time.
    """
    # Verify the parent exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.organization
            WHERE  organization_pk = %s AND is_active = TRUE
        """, (str(organization_pk),))
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=404, detail="Parent organization not found"
            )

    sql = (
        _ORG_SELECT
        + " WHERE o.parent_organization_pk = %s AND o.is_active = TRUE"
        + " ORDER BY ot.display_order, o.organization_name"
    )

    with conn.cursor() as cur:
        cur.execute(sql, (str(organization_pk),))
        return rows_to_models(cur, OrganizationResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 3. CHILDREN STATS (aggregate counts per child org)
# ═══════════════════════════════════════════════════════════════════════════


_CHILDREN_STATS_SQL = f"""
    WITH RECURSIVE org_tree AS (
        -- Anchor: direct children of the requested parent
        SELECT o.organization_pk,
               o.organization_pk   AS root_child_pk,
               o.organization_name,
               o.organization_code,
               ot.value_code       AS organization_type_code
        FROM   nss.organization o
        JOIN   nss.master_data ot
               ON ot.master_data_pk = o.organization_type_master_data_pk
        WHERE  o.parent_organization_pk = %s
          AND  o.is_active = TRUE

        UNION ALL

        -- Recursive: descendants (capped at depth 10)
        SELECT o.organization_pk,
               t.root_child_pk,
               o.organization_name,
               o.organization_code,
               ot.value_code
        FROM   nss.organization o
        JOIN   nss.master_data ot
               ON ot.master_data_pk = o.organization_type_master_data_pk
        JOIN   org_tree t
               ON t.organization_pk = o.parent_organization_pk
        WHERE  o.is_active = TRUE
    ),
    -- Sakha PKs grouped by which direct child they belong to
    sakha_pks AS (
        SELECT root_child_pk, organization_pk AS sakha_pk
        FROM   org_tree
        WHERE  organization_type_code = 'SAKHA_SANGHA'
    ),
    -- Family majority CTE (dynamic Sakha — FAM-036), shared with
    -- family.py's _FAMILY_SELECT — see api/helpers.py::FAMILY_MAJORITY_CTE_SQL
    {FAMILY_MAJORITY_CTE_SQL},
    -- Each family's effective Sakha
    family_effective AS (
        SELECT fg.family_group_pk,
               COALESCE(fm.sakha_pk, fg.sakha_organization_pk)
                   AS effective_sakha_pk
        FROM   nss.family_group fg
        LEFT JOIN family_majority fm
               ON fm.family_group_pk = fg.family_group_pk AND fm.rn = 1
        WHERE  fg.is_active = TRUE
    ),
    -- Family count per root_child
    family_counts AS (
        SELECT sp.root_child_pk,
               COUNT(DISTINCT fe.family_group_pk) AS family_count
        FROM   sakha_pks sp
        JOIN   family_effective fe
               ON fe.effective_sakha_pk = sp.sakha_pk
        GROUP BY sp.root_child_pk
    ),
    -- Member count per root_child — HOME membership only: active sangha_sevi
    -- whose home org is the Sakha (Parichay Patra holders + this Sakha's own
    -- PROBATIONARY "Darshak" entrants). Deliberately NOT affiliation-based.
    -- An affiliation join also pulls in Parichay Patra holders whose HOME is a
    -- different Sakha but who attend here as Darshaks (SOL-MEM-006), so on any
    -- multi-Sakha rollup (Anchalika/Zilla/Kendra) the same person was counted
    -- once at their home Sakha AND again at every Sakha they visit, inflating
    -- the total. Home scoping counts each member exactly once. Cross-Sakha
    -- visitor attendance is surfaced separately, on the Sakha's own dashboard
    -- only, via /darshak-summary.attending_from_other_sakha_count.
    member_counts AS (
        SELECT sp.root_child_pk,
               COUNT(DISTINCT ss.sangha_sevi_pk) AS member_count
        FROM   sakha_pks sp
        JOIN   nss.sangha_sevi ss
               ON ss.organization_pk = sp.sakha_pk
              AND ss.is_active = TRUE
        GROUP BY sp.root_child_pk
    ),
    -- Person count per root_child (persons in families under effective Sakha)
    person_counts AS (
        SELECT sp.root_child_pk,
               COUNT(DISTINCT fr.person_pk) AS person_count
        FROM   sakha_pks sp
        JOIN   family_effective fe
               ON fe.effective_sakha_pk = sp.sakha_pk
        JOIN   nss.family_relationship fr
               ON fr.family_group_pk = fe.family_group_pk
              AND fr.is_current = TRUE
        GROUP BY sp.root_child_pk
    ),
    -- Attendance per root_child (Tier 6, 2026-10-27) — present/absent
    -- across every Weekly Sangha Puja event at any Sakha under this
    -- child, mirroring attendance.py::organization_stats' own
    -- computation (EXCUSED_ABSENCE excluded from the denominator,
    -- ATT-008) and admin.py::dashboard_stats' NSS-wide rollup.
    attendance_counts AS (
        SELECT sp.root_child_pk,
               COUNT(DISTINCT w.weekly_sangha_puja_pk) AS total_puja_events,
               COUNT(*) FILTER (WHERE md.value_code = 'PRESENT') AS present_c,
               COUNT(*) FILTER (WHERE md.value_code = 'ABSENT') AS absent_c
        FROM   sakha_pks sp
        JOIN   nss.weekly_sangha_puja w ON w.sakha_pk = sp.sakha_pk AND w.is_active = TRUE
        LEFT JOIN nss.weekly_sangha_puja_attendance a
               ON a.weekly_sangha_puja_pk = w.weekly_sangha_puja_pk AND a.is_active = TRUE
        LEFT JOIN nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
        GROUP BY sp.root_child_pk
    )
    SELECT ot.root_child_pk        AS organization_pk,
           ot.organization_name,
           ot.organization_code,
           ot.organization_type_code,
           COALESCE(fc.family_count, 0)  AS family_count,
           COALESCE(mc.member_count, 0)  AS member_count,
           COALESCE(pc.person_count, 0)  AS person_count,
           COALESCE(ac.total_puja_events, 0) > 0 AS attendance_tracked,
           CASE WHEN COALESCE(ac.present_c, 0) + COALESCE(ac.absent_c, 0) > 0
                THEN ROUND(100.0 * ac.present_c / (ac.present_c + ac.absent_c), 1)
                ELSE NULL END AS attendance_pct
    FROM   org_tree ot
    LEFT JOIN family_counts fc   ON fc.root_child_pk = ot.root_child_pk
    LEFT JOIN member_counts mc   ON mc.root_child_pk = ot.root_child_pk
    LEFT JOIN person_counts pc   ON pc.root_child_pk = ot.root_child_pk
    LEFT JOIN attendance_counts ac ON ac.root_child_pk = ot.root_child_pk
    WHERE  ot.organization_pk = ot.root_child_pk
    ORDER BY ot.organization_name
"""


@router.get(
    "/organizations/{organization_pk}/children-stats",
    response_model=list[OrgChildStatsResponse],
)
def list_children_stats(
    organization_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> list[OrgChildStatsResponse]:
    """
    Aggregate statistics for each direct child of an organization.

    For each child org, recursively finds all descendant Sakhas and
    counts families (dynamic majority rule), members (active
    affiliations), and persons (family members).

    Used by the org admin sidebar to display inline counts on each
    drill-down card.
    """
    # Verify parent exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.organization
            WHERE  organization_pk = %s AND is_active = TRUE
        """, (str(organization_pk),))
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=404, detail="Parent organization not found"
            )

    with conn.cursor() as cur:
        cur.execute(_CHILDREN_STATS_SQL, (str(organization_pk),))
        return rows_to_models(cur, OrgChildStatsResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 3b. ORG STATS (whole-subtree totals for the requested org itself)
# ═══════════════════════════════════════════════════════════════════════════

# Same recursive-subtree + FAM-036 majority-rule pattern as
# _CHILDREN_STATS_SQL, but rooted AT the requested org (not its children)
# and collapsed to one row of totals rather than one row per child. See
# OrgStatsResponse's docstring for why this exists as a separate,
# org-scoped endpoint instead of reusing /admin/dashboard-stats.
_ORG_STATS_SQL = f"""
    WITH RECURSIVE org_tree AS (
        -- Anchor: the requested org itself
        SELECT o.organization_pk,
               ot.value_code AS organization_type_code
        FROM   nss.organization o
        JOIN   nss.master_data ot
               ON ot.master_data_pk = o.organization_type_master_data_pk
        WHERE  o.organization_pk = %s
          AND  o.is_active = TRUE

        UNION ALL

        -- Recursive: descendants (capped at depth 10, matches
        -- children-stats/hierarchy's own guard against circular parents)
        SELECT o.organization_pk,
               ot.value_code
        FROM   nss.organization o
        JOIN   nss.master_data ot
               ON ot.master_data_pk = o.organization_type_master_data_pk
        JOIN   org_tree t
               ON t.organization_pk = o.parent_organization_pk
        WHERE  o.is_active = TRUE
    ),
    sakha_pks AS (
        SELECT organization_pk AS sakha_pk
        FROM   org_tree
        WHERE  organization_type_code = 'SAKHA_SANGHA'
    ),
    -- Family majority CTE (dynamic Sakha — FAM-036), shared with
    -- family.py's _FAMILY_SELECT and this file's _CHILDREN_STATS_SQL —
    -- see api/helpers.py::FAMILY_MAJORITY_CTE_SQL
    {FAMILY_MAJORITY_CTE_SQL},
    family_effective AS (
        SELECT fg.family_group_pk,
               COALESCE(fm.sakha_pk, fg.sakha_organization_pk)
                   AS effective_sakha_pk
        FROM   nss.family_group fg
        LEFT JOIN family_majority fm
               ON fm.family_group_pk = fg.family_group_pk AND fm.rn = 1
        WHERE  fg.is_active = TRUE
    )
    SELECT
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'SAKHA_SANGHA')  AS sakha_sanghas,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'MAHILA_SANGHA') AS mahila_sanghas,
        -- Remaining ORGANIZATION_TYPE tiers present in this subtree, so a
        -- Kendra dashboard can break its constituent bodies out by type
        -- instead of showing one meaningless "total organizations" figure.
        -- All are counted inside org_tree (the requested org + every active
        -- descendant), which for a Kendra is exactly "whose parent is Kendra"
        -- for the tiers that attach directly to it.
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'ANCHALIKA_SANGHA') AS anchalika_sanghas,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'ZILLA_SANGHA')     AS zilla_sanghas,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'PATHA_CHAKRA')     AS patha_chakras,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'PARIBARIK_SANGHA') AS paribarik_sanghas,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'KUMARI_SANGHA')    AS kumari_sanghas,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'SEVAK_SANGHA')     AS sevak_sanghas,
        (SELECT COUNT(DISTINCT ss.sangha_sevi_pk)
         FROM   sakha_pks sp
         JOIN   nss.sangha_sevi ss
                ON ss.organization_pk = sp.sakha_pk
               AND ss.is_active = TRUE
        ) AS member_count,
        -- member_count split by Parichay Patra eligibility. A Parichay Patra
        -- is issued to every MEMBERSHIP_TYPE except PROBATIONARY (value_name
        -- "Darshaka"), and sangha_sevi.membership_type_master_data_pk is
        -- NOT NULL, so these two are a complete, non-overlapping partition of
        -- member_count above: parichay_patra_holders + darshaks = member_count.
        --
        -- darshaks here is HOME probationary members only. Parichay Patra
        -- holders whose home is another Sakha but who attend one in this
        -- subtree as Darshaks are deliberately excluded: they are already
        -- counted once at their home Sakha, and adding their visits would
        -- count the same person several times in a multi-Sakha rollup. That
        -- cross-Sakha figure stays on the individual Sakha's own dashboard
        -- (/darshak-summary.attending_from_other_sakha_count), where
        -- "how many attend this Sangha" is the actual question.
        (SELECT COUNT(DISTINCT ss.sangha_sevi_pk)
         FROM   sakha_pks sp
         JOIN   nss.sangha_sevi ss
                ON ss.organization_pk = sp.sakha_pk
               AND ss.is_active = TRUE
         JOIN   nss.master_data mt
                ON mt.master_data_pk = ss.membership_type_master_data_pk
         WHERE  mt.value_code <> 'PROBATIONARY'
        ) AS parichay_patra_holders,
        (SELECT COUNT(DISTINCT ss.sangha_sevi_pk)
         FROM   sakha_pks sp
         JOIN   nss.sangha_sevi ss
                ON ss.organization_pk = sp.sakha_pk
               AND ss.is_active = TRUE
         JOIN   nss.master_data mt
                ON mt.master_data_pk = ss.membership_type_master_data_pk
         WHERE  mt.value_code = 'PROBATIONARY'
        ) AS darshaks,
        (SELECT COUNT(DISTINCT fe.family_group_pk)
         FROM   sakha_pks sp
         JOIN   family_effective fe
                ON fe.effective_sakha_pk = sp.sakha_pk
        ) AS family_count,
        (SELECT COUNT(*)
         FROM   nss.membership_renewal_request rr
         JOIN   nss.sangha_sevi ss
                ON ss.sangha_sevi_pk = rr.sangha_sevi_pk
         WHERE  rr.status = 'PENDING'
           AND  ss.is_active = TRUE
           AND  ss.organization_pk IN (SELECT sakha_pk FROM sakha_pks)
        ) AS renewals_due,
        -- Attendance percentage (Tier 6, 2026-10-27) — same present/(present+absent)
        -- computation as attendance.py::organization_stats, rolled up
        -- across every Sakha in this org's subtree.
        (SELECT COUNT(*) > 0
         FROM   nss.weekly_sangha_puja w
         WHERE  w.sakha_pk IN (SELECT sakha_pk FROM sakha_pks) AND w.is_active = TRUE
        ) AS attendance_tracked,
        (SELECT CASE WHEN COUNT(*) FILTER (WHERE md.value_code IN ('PRESENT', 'ABSENT')) > 0
                THEN ROUND(100.0 * COUNT(*) FILTER (WHERE md.value_code = 'PRESENT')
                           / COUNT(*) FILTER (WHERE md.value_code IN ('PRESENT', 'ABSENT')), 1)
                ELSE NULL END
         FROM   nss.weekly_sangha_puja w
         JOIN   nss.weekly_sangha_puja_attendance a
                ON a.weekly_sangha_puja_pk = w.weekly_sangha_puja_pk AND a.is_active = TRUE
         JOIN   nss.master_data md ON md.master_data_pk = a.attendance_status_master_data_pk
         WHERE  w.sakha_pk IN (SELECT sakha_pk FROM sakha_pks) AND w.is_active = TRUE
        ) AS attendance_pct
"""


@router.get(
    "/organizations/{organization_pk}/stats",
    response_model=OrgStatsResponse,
)
def get_organization_stats(
    organization_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> OrgStatsResponse:
    """
    Whole-subtree totals for one organization (itself + every descendant).

    Unlike /admin/dashboard-stats (which scopes to the *viewer's* admin
    scope), this scopes to the *requested org's* subtree, and 403s if that
    org falls outside the viewer's own scope (ADMIN-BR-076) — so it can be
    used to render the Org Dashboard correctly no matter which org the
    viewer drilled into.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM nss.organization "
            "WHERE organization_pk = %s AND is_active = TRUE",
            (str(organization_pk),),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=404, detail="Organization not found"
            )

        require_org_in_scope(cur, user, organization_pk, "view stats for")

        cur.execute(_ORG_STATS_SQL, (str(organization_pk),))
        # Mapped by column name rather than positional unpack: this row is now
        # 13 columns wide, and a positional tuple silently mis-assigns every
        # value if a column is ever inserted mid-SELECT.
        row = dict(zip([d[0] for d in cur.description], cur.fetchone()))

    return OrgStatsResponse(
        organization_pk=organization_pk,
        member_count=row["member_count"] or 0,
        parichay_patra_holders=row["parichay_patra_holders"] or 0,
        darshaks=row["darshaks"] or 0,
        family_count=row["family_count"] or 0,
        sakha_sanghas=row["sakha_sanghas"] or 0,
        mahila_sanghas=row["mahila_sanghas"] or 0,
        anchalika_sanghas=row["anchalika_sanghas"] or 0,
        zilla_sanghas=row["zilla_sanghas"] or 0,
        patha_chakras=row["patha_chakras"] or 0,
        paribarik_sanghas=row["paribarik_sanghas"] or 0,
        kumari_sanghas=row["kumari_sanghas"] or 0,
        sevak_sanghas=row["sevak_sanghas"] or 0,
        renewals_due=row["renewals_due"] or 0,
        attendance_pct=row["attendance_pct"],
        attendance_tracked=bool(row["attendance_tracked"]),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3c. WING BODIES (Mahila / Kumari / Sevak Sangha)
# ═══════════════════════════════════════════════════════════════════════════
#
# The three wings look symmetric in the ORGANIZATION_TYPE master data and
# are NOT symmetric in how membership works. Getting this wrong would mean
# reporting a confident zero for two wings whose rosters are not knowable
# from the database at all, so the asymmetry is encoded explicitly here
# rather than smoothed over:
#
#   MAHILA_SANGHA  — DERIVED from person attributes. "all female members"
#     (MBR-046); affiliation is automatic the moment a female member's
#     Sakha affiliation is recorded (ORG-BR-096). Deliberately has no
#     membership table — mahila/05_mahila_table_design.md §5.2 declines
#     `mahila_membership` outright ("Mahila Participation != Separate
#     Global Membership"). So a query over person.gender IS the roster,
#     and it is correct today.
#
#   KUMARI_SANGHA  — ENROLLMENT-based. A Kumari holds a kumari_membership
#     row with its own kumari_id. KUM-007 leaves the age boundary
#     explicitly UNFROZEN ("the ERP shall not hard-code an unsupported
#     age limit"), and KUM-004 even allows a Kumari with no NSS
#     membership at all. So "unmarried female members of this Sakha" is
#     NOT the Kumari roster — it is a different, larger set.
#
#   SEVAK_SANGHA   — ENROLLMENT-based. SEV-015: "An authorized user
#     performs the enrollment action." SEV-013 names no gender predicate;
#     the male-only rule is scoped to *event participation*
#     (sevak/04_sevak_participation_rules.md), not enrollment. SEV-014
#     adds no age rule. So no attribute predicate exists to derive from.
#
# Neither kumari_membership nor sevak_participation exists in the schema:
# there is no CREATE TABLE for either anywhere under database/ddl/ (the
# DDL tiers stop at 07_administration). Both are design-only documents.
# Their member_count is therefore None with a note, never 0.
#
# A person is never attached to a wing org row in any case: MBR-038A's
# trigger (05_membership/14_sakha_only_membership_trigger.sql) rejects any
# sangha_sevi.organization_pk or membership_sakha_affiliation.organization_pk
# that is not a SAKHA_SANGHA. That is why wing rosters must be computed
# from the member's Sakha outward, and why no wing-affiliation column is
# added here.

_WING_TYPE_CODES = ("MAHILA_SANGHA", "KUMARI_SANGHA", "SEVAK_SANGHA")

# Wings whose roster is a function of person attributes, and the predicate
# for each. Keep this table the single source of truth: both the summary
# counts and the roster endpoint read it, so they cannot drift apart and
# report a count that the list does not reproduce.
#
# The MAHILA predicate is gender only. No age or marital-status term is
# included because none is documented — MBR-046 says "all female members"
# full stop, and neither the Mahila bye-law (REF-MS-2, which qualifies on
# character and faith, not demographics) nor GOV-BR-033 adds one. Inventing
# an age cutoff here would be exactly the unsupported hard-coding KUM-007
# forbids for Kumari.
_DERIVED_WING_PREDICATES = {
    "MAHILA_SANGHA": "g.value_code = 'FEMALE'",
}

_WING_NOT_DERIVABLE_NOTE = {
    "KUMARI_SANGHA": (
        "Kumari Sangha membership is an enrollment record (kumari_membership, "
        "with its own kumari_id), not a person attribute — KUM-012 governs who "
        "stays active and KUM-007 leaves the age boundary unfrozen, so it cannot "
        "be derived from gender and marital status. That table does not exist in "
        "the schema yet, so no roster can be reported."
    ),
    "SEVAK_SANGHA": (
        "Sevak Sangha membership is an enrollment action performed by an "
        "authorized user (SEV-015) with no documented attribute predicate — "
        "SEV-013 names no gender rule, and male-only applies to event "
        "participation, not enrollment. The sevak_participation table does not "
        "exist in the schema yet, so no roster can be reported."
    ),
}

# Subtree walk shared by both wing endpoints — identical anchor/recursion to
# _ORG_STATS_SQL so wing figures reconcile with /stats rather than being a
# second, subtly different definition of "this org's Sakhas".
_ORG_SUBTREE_CTE = """
    WITH RECURSIVE org_tree AS (
        SELECT o.organization_pk,
               o.parent_organization_pk,
               ot.value_code AS organization_type_code
        FROM   nss.organization o
        JOIN   nss.master_data ot
               ON ot.master_data_pk = o.organization_type_master_data_pk
        WHERE  o.organization_pk = %s
          AND  o.is_active = TRUE

        UNION ALL

        SELECT o.organization_pk,
               o.parent_organization_pk,
               ot.value_code
        FROM   nss.organization o
        JOIN   nss.master_data ot
               ON ot.master_data_pk = o.organization_type_master_data_pk
        JOIN   org_tree t
               ON t.organization_pk = o.parent_organization_pk
        WHERE  o.is_active = TRUE
    ),
    sakha_pks AS (
        SELECT organization_pk AS sakha_pk
        FROM   org_tree
        WHERE  organization_type_code = 'SAKHA_SANGHA'
    )
"""

# Per-wing ORG counts + the derived Mahila head-count, in one round trip.
#
# gender_not_recorded is counted over the same member population as
# mahila_members so the two are directly comparable: it is the number of
# members who would qualify or not purely depending on a gender value
# nobody has filled in. person.gender_master_data_pk is NULLable, so
# without this figure the Mahila count silently under-reports and looks
# authoritative.
_WING_STATS_SQL = f"""
    {_ORG_SUBTREE_CTE},
    subtree_members AS (
        SELECT DISTINCT ss.sangha_sevi_pk,
               ss.person_pk
        FROM   sakha_pks sp
        JOIN   nss.sangha_sevi ss
               ON ss.organization_pk = sp.sakha_pk
              AND ss.is_active = TRUE
    )
    SELECT
        (SELECT organization_type_code FROM org_tree
          WHERE organization_pk = %s)                      AS requested_type_code,
        (SELECT COUNT(*) FROM sakha_pks)                   AS sakha_sangha_count,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'MAHILA_SANGHA')  AS mahila_orgs,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'KUMARI_SANGHA')  AS kumari_orgs,
        (SELECT COUNT(*) FROM org_tree
          WHERE organization_type_code = 'SEVAK_SANGHA')   AS sevak_orgs,
        (SELECT COUNT(*)
         FROM   subtree_members sm
         JOIN   nss.person p ON p.person_pk = sm.person_pk
         JOIN   nss.master_data g
                ON g.master_data_pk = p.gender_master_data_pk
         WHERE  g.value_code = 'FEMALE'
        ) AS mahila_members,
        (SELECT COUNT(*)
         FROM   subtree_members sm
         JOIN   nss.person p ON p.person_pk = sm.person_pk
         WHERE  p.gender_master_data_pk IS NULL
        ) AS gender_not_recorded
"""


@router.get(
    "/organizations/{organization_pk}/wings",
    response_model=OrgWingSummaryResponse,
)
def get_organization_wings(
    organization_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> OrgWingSummaryResponse:
    """
    Wing-body summary for one organization's subtree: how many wing
    organizations exist, and how many people are in each.

    Works at every tier without special-casing, because the subtree walk
    is the same one /stats uses:

      Sakha            -> its own wings
      Anchalika/Zilla  -> roll-up of its descendant Sakhas' wings
      Kendra           -> roll-up of every Sakha, which per ORG-BR-096 is
                          also the central Mahila Sangha's roster

    Only MAHILA_SANGHA reports a member_count today. Kumari and Sevak
    report None plus a note explaining why — their rosters are enrollment
    records, not attribute-derived, and those tables are not in the schema
    yet. See this section's header comment for the full reasoning.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM nss.organization "
            "WHERE organization_pk = %s AND is_active = TRUE",
            (str(organization_pk),),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=404, detail="Organization not found"
            )

        require_org_in_scope(cur, user, organization_pk, "view wings for")

        # organization_pk twice: once for the recursive anchor, once for the
        # requested_type_code lookup inside the CTE.
        cur.execute(_WING_STATS_SQL, (str(organization_pk), str(organization_pk)))
        row = dict(zip([d[0] for d in cur.description], cur.fetchone()))

        # value_name comes from master_data rather than being hardcoded, so a
        # renamed ORGANIZATION_TYPE label propagates without a code change.
        cur.execute(
            """
            SELECT md.value_code, md.value_name
            FROM   nss.master_data md
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  mc.category_code = 'ORGANIZATION_TYPE'
              AND  md.value_code = ANY(%s)
            """,
            (list(_WING_TYPE_CODES),),
        )
        names = {r[0]: r[1] for r in cur.fetchall()}

    org_counts = {
        "MAHILA_SANGHA": row["mahila_orgs"] or 0,
        "KUMARI_SANGHA": row["kumari_orgs"] or 0,
        "SEVAK_SANGHA": row["sevak_orgs"] or 0,
    }

    wings: list[OrgWingResponse] = []
    for code in _WING_TYPE_CODES:
        is_derived = code in _DERIVED_WING_PREDICATES
        wings.append(
            OrgWingResponse(
                wing_type_code=code,
                # Fall back to a humanised code rather than failing if the
                # master_data row is absent (e.g. a partially seeded DB).
                wing_type_name=names.get(code, code.replace("_", " ").title()),
                organization_count=org_counts[code],
                member_count=(row["mahila_members"] or 0) if is_derived else None,
                member_count_note=(
                    None if is_derived else _WING_NOT_DERIVABLE_NOTE[code]
                ),
                is_derived=is_derived,
                gender_not_recorded_count=(
                    (row["gender_not_recorded"] or 0) if is_derived else None
                ),
            )
        )

    return OrgWingSummaryResponse(
        organization_pk=organization_pk,
        organization_type_code=row["requested_type_code"],
        sakha_sangha_count=row["sakha_sangha_count"] or 0,
        wings=wings,
    )


# Roster SELECT. Mirrors membership.py's _MEMBER_SELECT shape but joins
# gender/marital_status (which that query does not expose) and reports the
# member's SAKHA as the place label, since the wing org row carries neither
# organization_code nor short_code (ORG-BR-104).
#
# Note this cannot reuse /membership/members: that endpoint filters on
# o.organization_code, and a wing's code is NULL by rule, so a wing is
# literally unaddressable through it. It also has no subtree filter, which
# the Anchalika/Zilla/Kendra tiers require.
_WING_MEMBER_SELECT = """
    SELECT ss.sangha_sevi_pk,
           ss.sangha_sevi_id,
           ss.person_pk,
           TRIM(CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name))
               AS full_name,
           g.value_code  AS gender_code,
           mar.value_code AS marital_status_code,
           mt.value_code AS membership_type_code,
           mst.value_code AS status_code,
           ss.organization_pk AS sakha_organization_pk,
           o.organization_name AS sakha_organization_name,
           o.organization_code AS sakha_organization_code,
           aff.local_sakha_erp_id,
           ss.joining_date
    FROM   sakha_pks sp
    JOIN   nss.sangha_sevi ss
           ON ss.organization_pk = sp.sakha_pk
          AND ss.is_active = TRUE
    JOIN   nss.person p
           ON p.person_pk = ss.person_pk
    JOIN   nss.organization o
           ON o.organization_pk = ss.organization_pk
    JOIN   nss.master_data mt
           ON mt.master_data_pk = ss.membership_type_master_data_pk
    JOIN   nss.master_data mst
           ON mst.master_data_pk = ss.membership_status_master_data_pk
    LEFT JOIN nss.master_data g
           ON g.master_data_pk = p.gender_master_data_pk
    LEFT JOIN nss.master_data mar
           ON mar.master_data_pk = p.marital_status_master_data_pk
    LEFT JOIN nss.membership_sakha_affiliation aff
           ON aff.sangha_sevi_pk = ss.sangha_sevi_pk
          AND aff.organization_pk = ss.organization_pk
          AND aff.effective_to IS NULL
"""


@router.get(
    "/organizations/{organization_pk}/wings/{wing_type_code}/members",
    response_model=WingMemberListResponse,
)
def list_organization_wing_members(
    organization_pk: UUID,
    wing_type_code: str,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> WingMemberListResponse:
    """
    Who the members of one wing are, across this organization's subtree.

    Each row names the member's Sakha, because a wing has no code of its
    own (ORG-BR-104) — at Kendra or Zilla level the Sakha is the only
    thing that makes the roster readable.

    422 for KUMARI_SANGHA/SEVAK_SANGHA: those rosters are enrollment
    records rather than a function of person attributes, and the tables do
    not exist yet. The error says so explicitly instead of returning an
    empty list, which would read as "this wing has no members".
    """
    code = wing_type_code.upper()

    if code not in _WING_TYPE_CODES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown wing type '{wing_type_code}'. Expected one of: "
                f"{', '.join(_WING_TYPE_CODES)}."
            ),
        )

    if code not in _DERIVED_WING_PREDICATES:
        # 422, not 404/200-empty: the request is well-formed and the wing is
        # real, but no roster is obtainable. An empty 200 would be read as a
        # factual "nobody is in this wing".
        raise HTTPException(
            status_code=422, detail=_WING_NOT_DERIVABLE_NOTE[code]
        )

    predicate = _DERIVED_WING_PREDICATES[code]

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM nss.organization "
            "WHERE organization_pk = %s AND is_active = TRUE",
            (str(organization_pk),),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=404, detail="Organization not found"
            )

        require_org_in_scope(cur, user, organization_pk, "view wing members for")

        # COUNT first so `total` is a real total rather than a page length —
        # the roster is paginated and a Kendra-level call will exceed one page.
        cur.execute(
            f"""
            {_ORG_SUBTREE_CTE}
            SELECT COUNT(*)
            FROM   sakha_pks sp
            JOIN   nss.sangha_sevi ss
                   ON ss.organization_pk = sp.sakha_pk
                  AND ss.is_active = TRUE
            JOIN   nss.person p
                   ON p.person_pk = ss.person_pk
            LEFT JOIN nss.master_data g
                   ON g.master_data_pk = p.gender_master_data_pk
            WHERE  {predicate}
            """,
            (str(organization_pk),),
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            {_ORG_SUBTREE_CTE}
            {_WING_MEMBER_SELECT}
            WHERE  {predicate}
            ORDER BY o.organization_name, p.first_name, p.last_name
            LIMIT %s OFFSET %s
            """,
            (str(organization_pk), limit, offset),
        )
        members = rows_to_models(cur, WingMemberResponse)

    return WingMemberListResponse(
        wing_type_code=code,
        organization_pk=organization_pk,
        total=total,
        limit=limit,
        offset=offset,
        members=members,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. HIERARCHY (recursive CTE)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/hierarchy", response_model=list[OrganizationHierarchyNodeResponse])
def get_organization_hierarchy(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("ORGANIZATION_VIEW")),
) -> list[OrganizationHierarchyNodeResponse]:
    """
    Return the organizational hierarchy as a flat list with depth.

    Uses a recursive CTE. For the NSS-wide/global authority (NSS_ERP_ADMIN
    or an NSS-WIDE scope) the anchor is the true root nodes (parent =
    NULL), returning the whole tree as before. For a scope-bounded admin
    (ADMIN-BR-076) the anchor is instead their own admin_scope
    organization(s) — the tree is *rooted* at their own scope rather than
    filtered after the fact, which would otherwise break parent-chain
    integrity (orphaned nodes whose parent got filtered out). A scoped
    admin therefore sees exactly their own org subtree, depth 0 at their
    own org.

    Depth is capped at 10 levels as a defence-in-depth guard against
    circular parent references. Supports pagination via limit/offset.
    The UI reconstructs the tree using depth for indentation.
    """
    # Scope-rooted anchor (ADMIN-BR-076): resolved without a DB round
    # trip, same scopes actor_scope_org_pks() itself reads to build the
    # subtree — here we only need the admin's own org(s), not the full
    # subtree, since the recursive step below expands descendants itself.
    root_pks: list[str] | None = None
    if not (user.is_super_admin() or user.is_nss_wide()):
        root_pks = [str(s.organization_pk) for s in user.scopes if s.organization_pk]
        if not root_pks:
            return []

    anchor_filter = (
        "o.organization_pk = ANY(%s::uuid[])" if root_pks is not None
        else "o.parent_organization_pk IS NULL"
    )
    anchor_params: list = [root_pks] if root_pks is not None else []

    with conn.cursor() as cur:
        cur.execute(f"""
            WITH RECURSIVE org_tree AS (
                -- Anchor: root nodes (no parent) for the global authority,
                -- or the scoped admin's own org(s) for a scope-bounded
                -- admin (ADMIN-BR-076).
                SELECT o.organization_pk,
                       o.organization_name,
                       o.organization_code,
                       ot.value_code  AS organization_type_code,
                       ot.value_name  AS organization_type_name,
                       os.value_code  AS status_code,
                       os.value_name  AS status_name,
                       o.parent_organization_pk,
                       0 AS depth,
                       o.is_active
                FROM   nss.organization o
                JOIN   nss.master_data ot
                       ON ot.master_data_pk = o.organization_type_master_data_pk
                JOIN   nss.master_data os
                       ON os.master_data_pk = o.status_master_data_pk
                WHERE  {anchor_filter}
                  AND  o.is_active = TRUE

                UNION ALL

                -- Recursive: children (depth capped at 10)
                SELECT o.organization_pk,
                       o.organization_name,
                       o.organization_code,
                       ot.value_code  AS organization_type_code,
                       ot.value_name  AS organization_type_name,
                       os.value_code  AS status_code,
                       os.value_name  AS status_name,
                       o.parent_organization_pk,
                       t.depth + 1,
                       o.is_active
                FROM   nss.organization o
                JOIN   nss.master_data ot
                       ON ot.master_data_pk = o.organization_type_master_data_pk
                JOIN   nss.master_data os
                       ON os.master_data_pk = o.status_master_data_pk
                JOIN   org_tree t
                       ON t.organization_pk = o.parent_organization_pk
                WHERE  o.is_active = TRUE
                  AND  t.depth < 10
            )
            SELECT * FROM org_tree
            ORDER BY depth, organization_name
            LIMIT %s OFFSET %s
        """, tuple(anchor_params + [limit, offset]))
        return rows_to_models(cur, OrganizationHierarchyNodeResponse)
