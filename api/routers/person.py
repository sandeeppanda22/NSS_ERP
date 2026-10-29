"""
Person API router — Tier 3 read endpoints.

4 GET endpoints across 2 Person tables. Requires authentication
(require_permission("PERSON_VIEW")).
nss_db_backend connects with SELECT-only privileges.

Endpoint groups:
  - Core:       persons (list with filters, detail)
  - Addresses:  person addresses (per person)
  - Search:     trigram-based name/ID search

Security:
  - aadhaar_encrypted and aadhaar_hash are NEVER returned (PER-BR-081)
  - Only aadhaar_last4 is exposed for masked display
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
    PERSON_MASTER_DATA_JOINS_SQL,
)
from api.services.person_scope import person_in_admin_scope
from api.services.rbac_service import UserContext, actor_scope_org_pks
from api.routers.family import _shares_current_family
from api.schemas.person import (
    PersonAddressResponse,
    PersonListResponse,
    PersonResponse,
    PersonSummaryResponse,
)

router = APIRouter(prefix="/api/v1/person", tags=["person"])


def _require_person_view(conn, person_pk, user: UserContext) -> None:
    """
    Read access to one person: an administrator holding PERSON_VIEW, the
    person themself (e.g. their own Member Dashboard), or a current relative
    who shares a family with them (e.g. clicking a relative in the family
    tree). The relative path mirrors _require_person_family_view() in
    api/routers/family.py so person detail and family/membership context stay
    consistent — a member who may read a relative's membership summary may
    also open that relative's person card.
    """
    if str(person_pk) == str(user.person_pk):
        return
    if user.has_permission("PERSON_VIEW") and person_in_admin_scope(conn, person_pk, user):
        return
    if _shares_current_family(conn, str(user.person_pk), str(person_pk)):
        return
    raise HTTPException(
        status_code=403,
        detail="You do not have access to this person.",
    )


# ── Shared SQL fragments ──────────────────────────────────────────────────

# Full person SELECT with resolved master-data names.
# LEFT JOINs on master_data: gender, marital_status, blood_group,
# emergency_relationship — all nullable FKs.
_PERSON_DETAIL_SELECT = f"""
    SELECT p.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           p.date_of_birth,
           p.date_of_death,
           p.gender_master_data_pk,
           g.value_code   AS gender_code,
           g.value_name   AS gender_name,
           p.marital_status_master_data_pk,
           ms.value_code  AS marital_status_code,
           ms.value_name  AS marital_status_name,
           p.blood_group_master_data_pk,
           bg.value_code  AS blood_group_code,
           bg.value_name  AS blood_group_name,
           p.country_phone_code,
           p.mobile_number,
           p.email,
           p.aadhaar_last4,
           p.photo_document_master_pk,
           p.emergency_contact_name,
           p.emergency_contact_phone,
           p.emergency_relationship_master_data_pk,
           er.value_code  AS emergency_relationship_code,
           er.value_name  AS emergency_relationship_name,
           p.remarks,
           p.is_active
    FROM   nss.person p
    {PERSON_MASTER_DATA_JOINS_SQL}
    LEFT JOIN nss.master_data er
           ON er.master_data_pk = p.emergency_relationship_master_data_pk
"""

# Compact person SELECT for list/search results (no Aadhaar, emergency, photo).
_PERSON_SUMMARY_SELECT = f"""
    SELECT p.person_pk,
           p.person_id,
           p.first_name,
           p.middle_name,
           p.last_name,
           p.date_of_birth,
           p.date_of_death,
           g.value_code   AS gender_code,
           g.value_name   AS gender_name,
           ms.value_code  AS marital_status_code,
           ms.value_name  AS marital_status_name,
           bg.value_code  AS blood_group_code,
           bg.value_name  AS blood_group_name,
           p.country_phone_code,
           p.mobile_number,
           p.email,
           p.is_active
    FROM   nss.person p
    {PERSON_MASTER_DATA_JOINS_SQL}
"""

# Count variant of _PERSON_SUMMARY_SELECT's FROM/JOIN — shares the same
# PERSON_MASTER_DATA_JOINS_SQL fragment so total counts match the summary
# rows one-for-one; previously a byte-identical standalone copy.
_PERSON_COUNT_SELECT = f"""
    SELECT count(*)
    FROM   nss.person p
    {PERSON_MASTER_DATA_JOINS_SQL}
"""

# Address SELECT with resolved location context via direct, nullable
# FKs on person_address (city_village_pk, postal_code_pk) → district
# + state + country geographic chain. SOL-ARCH-010 Amendment
# (2026-10-01): the former city_village_postal_code_map junction is
# retired; both FKs are independently optional, so both joins are LEFT.
_ADDRESS_SELECT = """
    SELECT pa.person_address_pk,
           pa.person_pk,
           pa.address_type_master_data_pk,
           at.value_code  AS address_type_code,
           at.value_name  AS address_type_name,
           pa.address_line_1,
           pa.address_line_2,
           pa.landmark,
           pa.city_village_pk,
           pa.postal_code_pk,
           cv.city_village_name,
           pc.postal_code,
           d.district_name,
           s.state_name,
           c.country_name,
           pa.is_primary,
           pa.remarks,
           pa.is_active
    FROM   nss.person_address pa
    JOIN   nss.master_data at
           ON at.master_data_pk = pa.address_type_master_data_pk
    LEFT JOIN nss.city_village cv
           ON cv.city_village_pk = pa.city_village_pk
    LEFT JOIN nss.postal_code pc
           ON pc.postal_code_pk = pa.postal_code_pk
    LEFT JOIN nss.district d
           ON d.district_pk = cv.district_pk
    LEFT JOIN nss.state s
           ON s.state_pk = d.state_pk
    LEFT JOIN nss.country c
           ON c.country_pk = s.country_pk
"""


# ═══════════════════════════════════════════════════════════════════════════
# 1. PERSONS (core read)
# ═══════════════════════════════════════════════════════════════════════════


# Sortable columns for the Person Directory.
#
# This is a whitelist, not a convenience: the chosen expression is
# interpolated into the ORDER BY (a column name cannot be a bound
# parameter), so nothing outside this dict may ever reach the statement.
# Keys are the names the frontend sends; values are SQL over the aliases
# established by _PERSON_SUMMARY_SELECT (p person, g gender, ms marital
# status, bg blood group).
_PERSON_SORT_COLUMNS: dict[str, str | list[str]] = {
    # person_id is "prefix + trailing digits" (P7, P100), so plain text
    # collation would order P100 before P7. Sort on the split key instead.
    "person_id": natural_sort_key("p.person_id"),
    "person_name": "CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)",
    "first_name": "p.first_name",
    "last_name": "p.last_name",
    "date_of_birth": "p.date_of_birth",
    "gender_name": "g.value_name",
    "marital_status_name": "ms.value_name",
    "blood_group_name": "bg.value_name",
    "mobile_number": natural_sort_key("p.mobile_number"),
    "email": "p.email",
}


@router.get("/persons", response_model=PersonListResponse)
def list_persons(
    gender_code: str | None = Query(
        None, description="Filter by gender value_code (e.g. MALE, FEMALE)"
    ),
    marital_status_code: str | None = Query(
        None, description="Filter by marital status value_code"
    ),
    blood_group_code: str | None = Query(
        None, description="Filter by blood group value_code"
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_dir: str | None = Query(None, description="Sort direction: asc or desc"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("PERSON_VIEW")),
) -> PersonListResponse:
    """
    List all active persons with resolved master-data context.

    Optionally filter by gender_code, marital_status_code, or
    blood_group_code. Returns a compact summary (no Aadhaar,
    emergency, or photo fields). Supports pagination via limit/offset
    (default 100, max 500).

    Sorted in SQL. This matters even though the Person Directory loads
    one large page: the response is capped at MAX_LIMIT, so ordering in
    the browser would sort whichever arbitrary 500 rows came back, while
    ordering here returns the top 500 *of the requested order*.

    Returns an envelope — `{persons, total}` — rather than a bare array.
    `total` is the true row count matching the filters, independent of
    the MAX_LIMIT cap on `persons`; callers must compare the two to
    detect truncation instead of assuming the array is complete.
    """
    where = " WHERE p.is_active = TRUE"
    params: list = []

    if gender_code is not None:
        where += " AND g.value_code = %s"
        params.append(gender_code)
    if marital_status_code is not None:
        where += " AND ms.value_code = %s"
        params.append(marital_status_code)
    if blood_group_code is not None:
        where += " AND bg.value_code = %s"
        params.append(blood_group_code)

    order_by = build_order_by(
        sort_by, sort_dir, _PERSON_SORT_COLUMNS, "p.first_name, p.last_name"
    )

    with conn.cursor() as cur:
        # ── Scope filter (ADMIN-BR-076, subtree-aware) ──
        # nss.person carries no organization_pk of its own, so a person's
        # scope is resolved through their own active sangha_sevi
        # (nss.sangha_sevi.organization_pk) — a scoped admin sees only
        # persons whose active membership falls inside their org subtree,
        # the same subtree actor_scope_org_pks() already resolves for
        # every other admin-scoped list. A person with no active
        # sangha_sevi (e.g. a pending registrant not yet approved) is
        # conservatively excluded from a scoped admin's view; only the
        # NSS-wide/global authority (allowed is None) still sees everyone.
        allowed = actor_scope_org_pks(cur, user)
        if allowed is not None:
            if not allowed:
                return PersonListResponse(persons=[], total=0)
            where += """
                AND EXISTS (
                    SELECT 1 FROM nss.sangha_sevi ss2
                    WHERE ss2.person_pk = p.person_pk
                      AND ss2.is_active = TRUE
                      AND ss2.organization_pk = ANY(%s::uuid[])
                )
            """
            params.append(list(allowed))

        sql = _PERSON_SUMMARY_SELECT + where + f" ORDER BY {order_by} LIMIT %s OFFSET %s"

        cur.execute(_PERSON_COUNT_SELECT + where, tuple(params))
        total = cur.fetchone()[0]

        cur.execute(sql, tuple(params + [limit, offset]))
        persons = rows_to_models(cur, PersonSummaryResponse)

    return PersonListResponse(persons=persons, total=total)


@router.get(
    "/persons/{person_pk}",
    response_model=PersonResponse,
)
def get_person(
    person_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> PersonResponse:
    """
    Get a single person by PK with full resolved context.

    Includes Aadhaar last-4 (masked), emergency contact, and photo
    FK. Never returns aadhaar_encrypted or aadhaar_hash.

    Access: an administrator holding PERSON_VIEW whose admin scope covers
    the person (ADMIN-BR-076), the person themself (e.g. their own Member
    Dashboard), or a current relative.
    """
    _require_person_view(conn, person_pk, user)
    sql = _PERSON_DETAIL_SELECT + " WHERE p.person_pk = %s AND p.is_active = TRUE"

    with conn.cursor() as cur:
        cur.execute(sql, (str(person_pk),))
        result = row_to_model(cur, PersonResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Person not found")
        return result


# ═══════════════════════════════════════════════════════════════════════════
# 2. ADDRESSES
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/persons/{person_pk}/addresses",
    response_model=list[PersonAddressResponse],
)
def list_person_addresses(
    person_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> list[PersonAddressResponse]:
    """
    List all active addresses for a given person.

    Resolves address type, city/village, postal code, district,
    state, and country names via JOINs. Returns 404 if the person
    does not exist.

    Access: an administrator holding PERSON_VIEW, or the person themself.
    """
    _require_person_view(conn, person_pk, user)
    # Verify the person exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM nss.person
            WHERE  person_pk = %s AND is_active = TRUE
        """, (str(person_pk),))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Person not found")

    sql = (
        _ADDRESS_SELECT
        + " WHERE pa.person_pk = %s AND pa.is_active = TRUE"
        + " ORDER BY pa.is_primary DESC, at.value_name"
    )

    with conn.cursor() as cur:
        cur.execute(sql, (str(person_pk),))
        return rows_to_models(cur, PersonAddressResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 3. SEARCH
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/search", response_model=PersonListResponse)
def search_persons(
    q: str = Query(
        ...,
        min_length=2,
        max_length=100,
        description="Search term — matches against first_name (trigram), "
        "last_name (trigram), person_id, mobile_number, or email",
    ),
    limit: int = Query(50, ge=1, le=MAX_LIMIT, description="Max rows to return (default 50)"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("PERSON_VIEW")),
) -> PersonListResponse:
    """
    Search active persons by name, person_id, mobile number, or email.

    Uses PostgreSQL trigram similarity (pg_trgm) on first_name and
    last_name for fuzzy matching. If the query contains '.' or '@'
    (email-like), trigram runs on the portion before the first
    separator to avoid false positives (e.g. "aniket.mishra" uses
    "aniket" for name matching, full string for email prefix).
    Also matches exact prefix on person_id, mobile_number, and email.
    Results ordered by trigram similarity (best match first).

    Supports pagination via limit/offset (default 50, max 500) — the
    same convention as /persons, replacing the previous hardcoded
    LIMIT 50 with no way to see or page past it. Returns an envelope
    — `{persons, total}` — so callers can tell when a match set is
    larger than the page returned.
    """
    return _run_person_search(conn, q, limit, offset)


@router.get("/search-selectable", response_model=PersonListResponse)
def search_persons_selectable(
    q: str = Query(..., min_length=2, max_length=100, description="Search term"),
    limit: int = Query(50, ge=1, le=MAX_LIMIT, description="Max rows to return (default 50)"),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    conn=Depends(get_connection),
    user: UserContext = Depends(get_current_user),
) -> PersonListResponse:
    """
    Member-facing person lookup for selection flows (e.g. a family head
    adding an existing person to their family via POST
    /families/{pk}/members, which is itself gated only on family-head /
    family-admin ownership — NOT the administrative PERSON_VIEW).

    Gated on authentication only, so a family head without PERSON_VIEW can
    still find the person to add. Returns the same PersonSummaryResponse
    (name/id/gender/DOB/mobile/status) the add-member picker displays.
    """
    return _run_person_search(conn, q, limit, offset)


def _run_person_search(conn, q: str, limit: int, offset: int) -> PersonListResponse:
    """Shared trigram person-search behind /search and /search-selectable."""
    # For trigram: strip email-like suffix so "aniket.mishra" → "aniket"
    name_q = re.split(r'[.@]', q)[0] if ('.' in q or '@' in q) else q

    where = """
        WHERE p.is_active = TRUE
          AND (
              similarity(p.first_name, %s) > 0.45
              OR similarity(p.last_name, %s) > 0.45
              OR p.person_id ILIKE %s
              OR p.mobile_number ILIKE %s
              OR p.email ILIKE %s
          )
    """
    sql = (
        _PERSON_SUMMARY_SELECT
        + where
        + """
        ORDER BY similarity(p.first_name, %s) DESC,
                 p.first_name, p.last_name
        LIMIT %s OFFSET %s
    """
    )

    prefix_pattern = f"{q}%"
    match_params = (name_q, name_q, prefix_pattern, prefix_pattern, prefix_pattern)

    with conn.cursor() as cur:
        cur.execute(_PERSON_COUNT_SELECT + where, match_params)
        total = cur.fetchone()[0]

        cur.execute(sql, match_params + (name_q, limit, offset))
        persons = rows_to_models(cur, PersonSummaryResponse)

    return PersonListResponse(persons=persons, total=total)
