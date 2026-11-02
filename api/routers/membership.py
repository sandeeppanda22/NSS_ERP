"""
Membership API router — Tier 4 read endpoints.

8 GET endpoints across 5 Membership tables. Requires authentication
(require_permission("MEMBERSHIP_VIEW"), or self-access via
require_self_or_permission).
nss_db_backend connects with SELECT-only privileges.

Endpoint groups:
  - Core:          members (list with filters, detail)
  - Search:        trigram + prefix across all 3 identity tiers + name
  - Affiliations:  sakha affiliation history (per member)
  - Credentials:   parichaya patra, anumati patra (per member)
  - Timeline:      journey events (per member)
  - Org summary:   darshak affiliation summary (per organization)

Three-tier identity model:
  - Sangha Sevi ID (SS1) — permanent NSS-wide (sangha_sevi)
  - ERP Number / Local Sakha Number (ESS1192) — Sakha-scoped,
    auto-generated (membership_sakha_affiliation)
  - Kendra Number (345/2026/2027) — annual per FY
    (parichaya_patra.document_number)

Security:
  - Audit actor FKs excluded per API convention
"""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.database import get_connection
from api.dependencies.auth import get_current_user
from api.dependencies.rbac import require_permission
from api.helpers import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    build_order_by,
    natural_sort_key,
    row_to_model,
    rows_to_models,
    require_entity,
    MEMBER_JOINS_SQL,
    require_self_or_permission,
)
from api.services.rbac_service import UserContext, actor_scope_org_pks, org_in_scope, require_org_in_scope
from api.routers.governance import _CURRENT_ASSIGNMENT_SQL
from api.schemas.membership import (
    AnumatiPatraResponse,
    JourneyEventResponse,
    MemberDirectoryListResponse,
    MemberDirectoryResponse,
    MemberListResponse,
    MemberResponse,
    OrgDarshakSummaryResponse,
    ParichayaPatraResponse,
    SakhaAffiliationResponse,
)

router = APIRouter(prefix="/api/v1/membership", tags=["membership"])


def _require_member_view(conn, sangha_sevi_pk, user: UserContext) -> None:
    """
    Read access to one member record: the member themself (e.g. their own
    Member Dashboard), or an administrator holding MEMBERSHIP_VIEW whose
    admin scope covers the member's home organization (ADMIN-BR-076 — the
    same rule /members (list) applies). NSS_ERP_ADMIN / NSS-WIDE are
    unrestricted. An unknown member is passed through so the endpoint's own
    404 is reported (existence before authorization).
    """
    if user.sangha_sevi_pk is not None and str(sangha_sevi_pk) == str(user.sangha_sevi_pk):
        return
    require_self_or_permission(
        sangha_sevi_pk, user.sangha_sevi_pk, "MEMBERSHIP_VIEW", user,
        detail="You do not have access to this member record.",
    )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT organization_pk FROM nss.sangha_sevi "
            "WHERE sangha_sevi_pk = %s AND is_active = TRUE",
            (str(sangha_sevi_pk),),
        )
        row = cur.fetchone()
        if row is not None and not org_in_scope(cur, user, row[0]):
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this member record.",
            )


# ── Shared SQL fragments ──────────────────────────────────────────────────

# Member list/detail with resolved person, type, status, org, and
# current active local_sakha_erp_id (LEFT JOIN on active affiliation).
_MEMBER_SELECT = f"""
    SELECT ss.sangha_sevi_pk,
           ss.sangha_sevi_id,
           ss.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           p.country_phone_code,
           p.mobile_number,
           p.email,
           ss.membership_type_master_data_pk,
           mt.value_code  AS membership_type_code,
           mt.value_name  AS membership_type_name,
           ss.membership_status_master_data_pk,
           ms.value_code  AS status_code,
           ms.value_name  AS status_name,
           ss.organization_pk,
           o.organization_name,
           o.organization_code,
           aff.local_sakha_erp_id,
           daff.organization_pk  AS darshak_organization_pk,
           dorg.organization_name AS darshak_organization_name,
           daff.local_sakha_erp_id AS darshak_local_sakha_number,
           ss.joining_date,
           ss.renewal_due_date,
           ss.remarks,
           ss.is_active
    FROM   nss.sangha_sevi ss
    {MEMBER_JOINS_SQL}
"""

# Count variant of _MEMBER_SELECT's FROM/JOIN — shares the same
# MEMBER_JOINS_SQL fragment so total counts match the member rows
# one-for-one; previously a byte-identical standalone copy.
_MEMBER_COUNT_SELECT = f"""
    SELECT count(*)
    FROM   nss.sangha_sevi ss
    {MEMBER_JOINS_SQL}
"""

# Shared member-search predicate (trigram name match + exact prefix on the
# three identity tiers / mobile / email / Kendra Number, plus a substring
# match on the member's own Sakha name — owner ask 2026-10-27: "search
# should... also include sakha too") — used by both /search (admin,
# MEMBERSHIP_VIEW, org/body-scoped) and /directory (any logged-in member,
# NSS-wide self-service lookup, 2026-10-27) so the two don't carry two
# independently-maintained copies of the same matching logic. Takes
# exactly the 9 placeholders _member_search_params() below builds, in the
# same order.
_MEMBER_SEARCH_PREDICATE_SQL = """
    (
        ss.sangha_sevi_id ILIKE %s
        OR p.person_id ILIKE %s
        OR aff.local_sakha_erp_id ILIKE %s
        OR similarity(p.first_name, %s) > 0.45
        OR similarity(p.last_name, %s) > 0.45
        OR p.mobile_number ILIKE %s
        OR p.email ILIKE %s
        OR o.organization_name ILIKE %s
        OR EXISTS (
            SELECT 1 FROM nss.parichaya_patra pp
            WHERE  pp.sangha_sevi_pk = ss.sangha_sevi_pk
              AND  pp.document_number ILIKE %s
        )
    )
"""


def _member_search_params(q: str) -> tuple[str, tuple]:
    """
    Build (name_q, params) for _MEMBER_SEARCH_PREDICATE_SQL's 9 placeholders.

    If q contains '.' or '@' (email-like), trigram runs on the portion
    before the first separator to avoid false positives (e.g.
    "aniket.mishra" uses "aniket" for name matching, full string for
    email prefix). name_q is also returned standalone for callers that
    ORDER BY similarity(p.first_name, name_q) DESC.

    The Sakha-name match is a substring (%q%), not a prefix like the
    identity-tier/mobile/email checks — a Sakha name is typically
    searched by a word inside it (e.g. "Puri"), not necessarily its
    first word, unlike an ID or a Kendra Number.
    """
    name_q = re.split(r'[.@]', q)[0] if ('.' in q or '@' in q) else q
    prefix_pattern = f"{q}%"
    substring_pattern = f"%{q}%"
    return name_q, (
        prefix_pattern, prefix_pattern, prefix_pattern,
        name_q, name_q,
        prefix_pattern, prefix_pattern,
        substring_pattern,
        prefix_pattern,
    )



# ═══════════════════════════════════════════════════════════════════════════
# 1. MEMBERS (core read)
# ═══════════════════════════════════════════════════════════════════════════


# Sortable columns for the Member Directory.
#
# Whitelist, not convenience: the expression is interpolated into the
# ORDER BY (a column name cannot be a bound parameter), so only values
# written here ever reach the statement. Aliases come from
# _MEMBER_SELECT — ss (sangha_sevi), p (person), mt (type),
# ms (status), o (organization), aff (active sakha affiliation).
_MEMBER_SORT_COLUMNS: dict[str, str | list[str]] = {
    # All three identity tiers are "prefix + trailing digits"
    # (SS10, P7, ESS1192), so text collation would put SS100 before SS9.
    "sangha_sevi_id": natural_sort_key("ss.sangha_sevi_id"),
    "person_id": natural_sort_key("p.person_id"),
    "local_sakha_erp_id": natural_sort_key("aff.local_sakha_erp_id"),
    "person_name": "CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)",
    "mobile_number": natural_sort_key("p.mobile_number"),
    "email": "p.email",
    "membership_type_name": "mt.value_name",
    "status_name": "ms.value_name",
    "organization_name": "o.organization_name",
    "organization_code": natural_sort_key("o.organization_code"),
    "joining_date": "ss.joining_date",
    "renewal_due_date": "ss.renewal_due_date",
}


@router.get("/members", response_model=MemberListResponse)
def list_members(
    type_code: str | None = Query(
        None, description="Filter by membership type (REGULAR, PROBATIONARY, etc.)"
    ),
    status_code: str | None = Query(
        None, description="Filter by status value_code"
    ),
    org_code: str | None = Query(
        None, description="Filter by organization_code (e.g. SKH1)"
    ),
    org_type_code: str | None = Query(
        None,
        description=(
            "Filter by the member organization's type value_code "
            "(e.g. SAKHA_SANGHA, KENDRA). Narrows the list to members "
            "whose primary organization is of that type."
        ),
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_dir: str | None = Query(None, description="Sort direction: asc or desc"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("MEMBERSHIP_VIEW")),
) -> MemberListResponse:
    """
    List all active members with resolved person, type, status,
    organization, and current local_sakha_erp_id.

    Optionally filter by type_code, status_code, org_code, or
    org_type_code.
    Supports pagination via limit/offset (default 100, max 500).

    Sorted in SQL. The response is capped at MAX_LIMIT, so ordering in
    the browser would only reorder whichever arbitrary 500 rows came
    back; ordering here returns the top 500 *of the requested order*.

    Returns an envelope — `{members, total}` — rather than a bare
    array. `total` is the true row count matching the filters,
    independent of the MAX_LIMIT cap on `members`; callers must
    compare the two to detect truncation instead of assuming the
    array is complete.
    """
    where = " WHERE ss.is_active = TRUE"
    params: list = []

    if type_code is not None:
        where += " AND mt.value_code = %s"
        params.append(type_code)
    if status_code is not None:
        where += " AND ms.value_code = %s"
        params.append(status_code)
    if org_code is not None:
        where += " AND o.organization_code = %s"
        params.append(org_code)
    if org_type_code is not None:
        where += " AND ot.value_code = %s"
        params.append(org_type_code)

    order_by = build_order_by(
        sort_by, sort_dir, _MEMBER_SORT_COLUMNS, "p.first_name, p.last_name"
    )

    with conn.cursor() as cur:
        # ── Scope filter (ADMIN-BR-076, subtree-aware) ──
        # A member's home organization is ss.organization_pk directly, so
        # the same actor_scope_org_pks() subtree used elsewhere (admin
        # user list, geo-entry approval queue) applies with no extra join.
        # Global authority (NSS-WIDE / NSS_ERP_ADMIN) is unfiltered.
        allowed = actor_scope_org_pks(cur, user)
        if allowed is not None:
            if not allowed:
                return MemberListResponse(members=[], total=0)
            where += " AND ss.organization_pk = ANY(%s::uuid[])"
            params.append(list(allowed))

        sql = _MEMBER_SELECT + where + f" ORDER BY {order_by} LIMIT %s OFFSET %s"

        cur.execute(_MEMBER_COUNT_SELECT + where, tuple(params))
        total = cur.fetchone()[0]

        cur.execute(sql, tuple(params + [limit, offset]))
        members = rows_to_models(cur, MemberResponse)

    return MemberListResponse(members=members, total=total)


@router.get(
    "/members/{sangha_sevi_pk}",
    response_model=MemberResponse,
)
def get_member(
    sangha_sevi_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> MemberResponse:
    """
    Get a single member by PK with full resolved context.

    Access: an administrator holding MEMBERSHIP_VIEW whose admin scope
    covers the member's home organization (ADMIN-BR-076), or the member
    themself (e.g. their own Member Dashboard).
    """
    _require_member_view(conn, sangha_sevi_pk, user)
    sql = _MEMBER_SELECT + " WHERE ss.sangha_sevi_pk = %s AND ss.is_active = TRUE"

    with conn.cursor() as cur:
        cur.execute(sql, (str(sangha_sevi_pk),))
        result = row_to_model(cur, MemberResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Member not found")
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 2. SEARCH
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/search", response_model=MemberListResponse)
def search_members(
    q: str = Query(
        ...,
        min_length=2,
        max_length=100,
        description="Search term — matches against Sangha Sevi ID (prefix), "
        "Person ID (prefix), ERP Number (prefix), name (trigram), "
        "mobile number (prefix), email (prefix), "
        "or Kendra Number (prefix)",
    ),
    organization_pk: UUID | None = Query(
        None,
        description="Restrict results to members whose home organization "
                    "(sangha_sevi.organization_pk) is this org OR any branch "
                    "beneath it in the hierarchy (subtree-aware). Because "
                    "membership is held at the Sakha leaf and a member belongs "
                    "to the parent Anchalika / Zilla / Kendra THROUGH that "
                    "Sakha, passing a higher body's org returns every member in "
                    "its subtree; passing a single Sakha returns just that "
                    "Sakha's members. Used by governance nomination / vote / "
                    "reset candidate / voter search so an org-scoped body (Sakha "
                    "Governing Body, Sevak Sangha Executive, per-Sakha Mahila "
                    "Parichalana Mandali, ...) only offers members from its own "
                    "subtree. Omit for an NSS-wide body (organization_pk IS "
                    "NULL), where any active member is eligible.",
    ),
    member_of_body_pk: UUID | None = Query(
        None,
        description="Restrict results to members who currently hold an active "
                    "seat (any position) on this governance body — used by the "
                    "Governance Assignments panel when the position being "
                    "filled must be chosen from the body's own existing "
                    "members (e.g. Advisory Board President/Secretary, which "
                    "GOV-BR-033/034 requires be chosen from among the body's "
                    "MEMBER seat-holders). Composable with organization_pk.",
    ),
    limit: int = Query(50, ge=1, le=MAX_LIMIT, description="Max rows to return (default 50)"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("MEMBERSHIP_VIEW")),
) -> MemberListResponse:
    """
    Search active members across all three identity tiers plus name,
    mobile number, and email.

    Uses PostgreSQL trigram similarity (pg_trgm) on first_name and
    last_name for fuzzy matching. If the query contains '.' or '@'
    (email-like), trigram runs on the portion before the first
    separator to avoid false positives (e.g. "aniket.mishra" uses
    "aniket" for name matching, full string for email prefix).
    Also matches exact prefix on sangha_sevi_id, person_id,
    local_sakha_erp_id, mobile_number, email, and parichaya_patra
    document_number (Kendra Number). Results ordered by trigram
    similarity (best match first).

    Supports pagination via limit/offset (default 50, max 500) — the
    same convention as /members, replacing the previous hardcoded
    LIMIT 50 with no way to see or page past it. Returns an envelope
    — `{members, total}` — so callers can tell when a match set is
    larger than the page returned.
    """
    name_q, predicate_params = _member_search_params(q)

    where = f"""
        WHERE ss.is_active = TRUE
          AND (%s::uuid IS NULL OR EXISTS (
              WITH RECURSIVE subtree(organization_pk) AS (
                  SELECT %s::uuid
                  UNION ALL
                  SELECT o.organization_pk
                  FROM nss.organization o
                  JOIN subtree s ON o.parent_organization_pk = s.organization_pk
              )
              SELECT 1 FROM subtree st
              WHERE st.organization_pk = ss.organization_pk
          ))
          AND (%s::uuid IS NULL OR EXISTS (
              SELECT 1 FROM nss.body_member_assignment a
              WHERE a.body_master_pk = %s AND a.person_pk = p.person_pk
                AND {_CURRENT_ASSIGNMENT_SQL}
          ))
          AND {_MEMBER_SEARCH_PREDICATE_SQL}
    """
    sql = (
        _MEMBER_SELECT
        + where
        + """
        ORDER BY similarity(p.first_name, %s) DESC,
                 p.first_name, p.last_name
        LIMIT %s OFFSET %s
    """
    )

    org_val = str(organization_pk) if organization_pk else None
    body_val = str(member_of_body_pk) if member_of_body_pk else None
    match_params = (org_val, org_val, body_val, body_val) + predicate_params

    with conn.cursor() as cur:
        cur.execute(_MEMBER_COUNT_SELECT + where, match_params)
        total = cur.fetchone()[0]

        cur.execute(sql, match_params + (name_q, limit, offset))
        members = rows_to_models(cur, MemberResponse)

    return MemberListResponse(members=members, total=total)


# ═══════════════════════════════════════════════════════════════════════════
# 2B. MEMBER DIRECTORY (general member self-service, NSS-wide)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/directory", response_model=MemberDirectoryListResponse)
def member_directory(
    q: str | None = Query(
        None,
        min_length=2,
        max_length=100,
        description="Optional search term — same matching as /search "
        "(Sangha Sevi ID, Person ID, name, mobile, email, Kendra Number "
        "prefix/trigram). Omit to browse the full directory.",
    ),
    organization_pk: UUID | None = Query(
        None,
        description="Restrict to one Sakha (and, if a higher body is "
                    "passed, its subtree) — see /search's organization_pk "
                    "for the exact subtree semantics.",
    ),
    district_pk: UUID | None = Query(
        None, description="Restrict to members whose person.district_pk matches.",
    ),
    limit: int = Query(50, ge=1, le=MAX_LIMIT, description="Max rows to return (default 50)"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> MemberDirectoryListResponse:
    """
    Member Directory (owner-confirmed 2026-10-27): any logged-in member can
    browse or search every active member NSS-wide — deliberately NOT scoped
    to the caller's own Sakha (unlike /search's admin-scoped callers), so
    get_current_user is the only gate, not require_permission("MEMBERSHIP_VIEW")
    or an admin_scope filter. Field set is MemberDirectoryResponse, a
    narrower projection than MemberResponse — see that model's docstring
    for exactly what is/isn't exposed to this audience.

    Shares the trigram/prefix matching logic with /search via
    _MEMBER_SEARCH_PREDICATE_SQL / _member_search_params rather than a
    second copy. q is optional here (unlike /search) so the directory is
    browsable with no search term, per the owner's "both a browsable
    directory and a search box" ask — mirrors the admin Person Directory's
    own browsable+search pattern (dashboard.js).
    """
    conditions = ["ss.is_active = TRUE"]
    params: list = []

    if organization_pk:
        conditions.append("""
            EXISTS (
                WITH RECURSIVE subtree(organization_pk) AS (
                    SELECT %s::uuid
                    UNION ALL
                    SELECT o.organization_pk
                    FROM nss.organization o
                    JOIN subtree s ON o.parent_organization_pk = s.organization_pk
                )
                SELECT 1 FROM subtree st WHERE st.organization_pk = ss.organization_pk
            )
        """)
        params.append(str(organization_pk))

    if district_pk:
        conditions.append("p.district_pk = %s")
        params.append(str(district_pk))

    name_q = None
    if q:
        name_q, predicate_params = _member_search_params(q)
        conditions.append(_MEMBER_SEARCH_PREDICATE_SQL)
        params.extend(predicate_params)

    where = "WHERE " + " AND ".join(conditions)
    joins = f"""
        {MEMBER_JOINS_SQL}
        LEFT JOIN nss.district d ON d.district_pk = p.district_pk
        LEFT JOIN nss.city_village cv ON cv.city_village_pk = p.city_village_pk
    """
    # Sakha Governing Body President/Secretary badge (owner ask 2026-10-27:
    # "show only sakha sangha president and secretary") — restricted to
    # body_type_code = 'SAKHA_GOVERNING_BODY', so a President/Secretary of
    # any OTHER body (Advisory Board, Mahila Parichalana Mandali, Sevak
    # Sangha Executive, ...) is deliberately NOT badged here. One row per
    # person via LATERAL; a person holding both seats somehow shows
    # PRESIDENT first (position_master.display_order: PRESIDENT=1,
    # SECRETARY=4). Reuses _CURRENT_ASSIGNMENT_SQL (governance.py) — the
    # same "currently seated" definition /search already uses. Not needed
    # in count_select (doesn't affect which rows match).
    position_join = f"""
        LEFT JOIN LATERAL (
            SELECT pm2.position_code, pm2.position_name
            FROM   nss.body_member_assignment a
            JOIN   nss.position_master pm2 ON pm2.position_master_pk = a.position_master_pk
            JOIN   nss.body_master bm2 ON bm2.body_master_pk = a.body_master_pk
            JOIN   nss.body_type_master bt2 ON bt2.body_type_master_pk = bm2.body_type_master_pk
            WHERE  a.person_pk = p.person_pk
              AND  bt2.body_type_code = 'SAKHA_GOVERNING_BODY'
              AND  pm2.position_code IN ('PRESIDENT', 'SECRETARY')
              AND  {_CURRENT_ASSIGNMENT_SQL}
            ORDER BY pm2.display_order
            LIMIT 1
        ) pos ON TRUE
    """
    select = f"""
        SELECT ss.sangha_sevi_pk, ss.sangha_sevi_id, p.person_id, p.first_name, p.middle_name,
               p.last_name, p.photo_document_master_pk,
               pos.position_code, pos.position_name,
               o.organization_pk, o.organization_name, aff.local_sakha_erp_id,
               mt.value_code AS membership_type_code, mt.value_name AS membership_type_name,
               ms.value_code AS status_code, ms.value_name AS status_name,
               d.district_name, cv.city_village_name,
               p.country_phone_code, p.mobile_number, p.email
        FROM   nss.sangha_sevi ss
        {joins}
        {position_join}
    """
    count_select = f"""
        SELECT count(*)
        FROM   nss.sangha_sevi ss
        {joins}
    """
    order_by = (
        "ORDER BY similarity(p.first_name, %s) DESC, p.first_name, p.last_name"
        if name_q else
        "ORDER BY p.first_name, p.last_name"
    )
    order_params = (name_q,) if name_q else ()

    with conn.cursor() as cur:
        cur.execute(count_select + where, params)
        total = cur.fetchone()[0]

        cur.execute(
            f"{select} {where} {order_by} LIMIT %s OFFSET %s",
            params + list(order_params) + [limit, offset],
        )
        members = rows_to_models(cur, MemberDirectoryResponse)

    return MemberDirectoryListResponse(members=members, total=total)





@router.get(
    "/members/{sangha_sevi_pk}/affiliations",
    response_model=list[SakhaAffiliationResponse],
)
def list_member_affiliations(
    sangha_sevi_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[SakhaAffiliationResponse]:
    """
    List all sakha affiliations for a member (current and historical).
    Returns 404 if the member does not exist.

    Access: an administrator holding MEMBERSHIP_VIEW whose admin scope
    covers the member's home organization (ADMIN-BR-076), or the member
    themself (e.g. their own Member Dashboard).
    """
    _require_member_view(conn, sangha_sevi_pk, user)
    with conn.cursor() as cur:
        require_entity(cur, "sangha_sevi", str(sangha_sevi_pk), label="Member")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT msa.membership_sakha_affiliation_pk,
                   msa.sangha_sevi_pk,
                   msa.organization_pk,
                   o.organization_name,
                   o.organization_code,
                   msa.local_sakha_erp_id,
                   msa.effective_from,
                   msa.effective_to,
                   msa.affiliation_status,
                   msa.source_event_type,
                   msa.legacy_sakha_number
            FROM   nss.membership_sakha_affiliation msa
            JOIN   nss.organization o
                   ON o.organization_pk = msa.organization_pk
            WHERE  msa.sangha_sevi_pk = %s
            ORDER BY msa.effective_from DESC
        """, (str(sangha_sevi_pk),))
        return rows_to_models(cur, SakhaAffiliationResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 4. PARICHAYA PATRA (Identity Cards)
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/members/{sangha_sevi_pk}/parichaya-patra",
    response_model=list[ParichayaPatraResponse],
)
def list_member_parichaya_patra(
    sangha_sevi_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[ParichayaPatraResponse]:
    """
    List all Parichaya Patra records for a member (current and historical).
    Includes point-in-time snapshot of affiliated Sakha and local number.
    Returns 404 if the member does not exist.

    Access: an administrator holding MEMBERSHIP_VIEW whose admin scope
    covers the member's home organization (ADMIN-BR-076), or the member
    themself (e.g. their own Member Dashboard).
    """
    _require_member_view(conn, sangha_sevi_pk, user)
    with conn.cursor() as cur:
        require_entity(cur, "sangha_sevi", str(sangha_sevi_pk), label="Member")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT pp.parichaya_patra_pk,
                   pp.sangha_sevi_pk,
                   pp.document_number,
                   pp.issue_date,
                   pp.valid_from,
                   pp.valid_to,
                   pp.status,
                   pp.affiliated_organization_pk,
                   o.organization_name  AS affiliated_organization_name,
                   o.organization_code  AS affiliated_organization_code,
                   pp.local_sakha_erp_id,
                   pp.document_reference,
                   pp.remarks
            FROM   nss.parichaya_patra pp
            LEFT JOIN nss.organization o
                   ON o.organization_pk = pp.affiliated_organization_pk
            WHERE  pp.sangha_sevi_pk = %s
            ORDER BY pp.valid_from DESC
        """, (str(sangha_sevi_pk),))
        return rows_to_models(cur, ParichayaPatraResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 5. ANUMATI PATRA (Probationary Credentials)
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/members/{sangha_sevi_pk}/anumati-patra",
    response_model=list[AnumatiPatraResponse],
)
def list_member_anumati_patra(
    sangha_sevi_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[AnumatiPatraResponse]:
    """
    List all Anumati Patra records for a member.
    Returns 404 if the member does not exist.

    Access: an administrator holding MEMBERSHIP_VIEW whose admin scope
    covers the member's home organization (ADMIN-BR-076), or the member
    themself (e.g. their own Member Dashboard).
    """
    _require_member_view(conn, sangha_sevi_pk, user)
    with conn.cursor() as cur:
        require_entity(cur, "sangha_sevi", str(sangha_sevi_pk), label="Member")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT ap.anumati_patra_pk,
                   ap.sangha_sevi_pk,
                   ap.document_number,
                   ap.issue_date,
                   ap.valid_from,
                   ap.valid_to,
                   ap.status,
                   ap.document_reference,
                   ap.remarks
            FROM   nss.anumati_patra ap
            WHERE  ap.sangha_sevi_pk = %s
            ORDER BY ap.valid_from DESC
        """, (str(sangha_sevi_pk),))
        return rows_to_models(cur, AnumatiPatraResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 6. JOURNEY EVENTS (lifecycle timeline)
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/members/{sangha_sevi_pk}/journey",
    response_model=list[JourneyEventResponse],
)
def list_member_journey(
    sangha_sevi_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[JourneyEventResponse]:
    """
    List all journey events for a member in chronological order.
    Returns 404 if the member does not exist.

    Access: an administrator holding MEMBERSHIP_VIEW whose admin scope
    covers the member's home organization (ADMIN-BR-076), or the member
    themself (e.g. their own Member Dashboard).
    """
    _require_member_view(conn, sangha_sevi_pk, user)
    with conn.cursor() as cur:
        require_entity(cur, "sangha_sevi", str(sangha_sevi_pk), label="Member")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT mje.membership_journey_event_pk,
                   mje.sangha_sevi_pk,
                   mje.event_type,
                   mje.event_date,
                   mje.event_reference,
                   mje.remarks
            FROM   nss.membership_journey_event mje
            WHERE  mje.sangha_sevi_pk = %s
            ORDER BY mje.event_date ASC
        """, (str(sangha_sevi_pk),))
        return rows_to_models(cur, JourneyEventResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 7. ORG-LEVEL DARSHAK SUMMARY (Sakha/Kendra dashboard card)
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/organizations/{organization_pk}/darshak-summary",
    response_model=OrgDarshakSummaryResponse,
)
def get_org_darshak_summary(
    organization_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("MEMBERSHIP_VIEW")),
) -> OrgDarshakSummaryResponse:
    """
    Darshak counts for one organization's own "Darshak" dashboard card
    (docs/03_Solution/ui/mockups/03_sakha_dashboard.html §Darshak Summary,
    02_kendra_dashboard.html §Membership and Renewal):

      - home_probationary_count: active members whose HOME sangha_sevi
        record at this org has membership_type PROBATIONARY (Darshaka).
      - attending_from_other_sakha_count: members whose home Sakha is a
        DIFFERENT org, currently holding an active membership_sakha_affiliation
        at this org (cross-Sakha darshak attendance, SOL-MEM-006).

    Not scoped to a Sakha specifically — a Kendra/Anchalika/Zilla org_pk
    aggregates across nothing on its own (both counts are 0 for non-leaf
    orgs); callers wanting a Kendra-wide total should sum this across
    every Sakha themselves.
    """
    with conn.cursor() as cur:
        require_entity(cur, "organization", str(organization_pk), label="Organization")
        require_org_in_scope(cur, user, organization_pk, "view Darshak counts for")

        cur.execute(
            """
            SELECT COUNT(*)
            FROM   nss.sangha_sevi ss
            JOIN   nss.master_data mt ON mt.master_data_pk = ss.membership_type_master_data_pk
            WHERE  ss.organization_pk = %s
              AND  ss.is_active = TRUE
              AND  mt.value_code = 'PROBATIONARY'
            """,
            (str(organization_pk),),
        )
        home_probationary_count = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(DISTINCT msa.sangha_sevi_pk)
            FROM   nss.membership_sakha_affiliation msa
            JOIN   nss.sangha_sevi ss ON ss.sangha_sevi_pk = msa.sangha_sevi_pk
            WHERE  msa.organization_pk = %s
              AND  msa.effective_to IS NULL
              AND  ss.organization_pk != %s
              AND  ss.is_active = TRUE
            """,
            (str(organization_pk), str(organization_pk)),
        )
        attending_from_other_sakha_count = cur.fetchone()[0]

    return OrgDarshakSummaryResponse(
        home_probationary_count=home_probationary_count,
        attending_from_other_sakha_count=attending_from_other_sakha_count,
    )
