"""
NSS ERP — Member-Assisted Geographic Entry approval queue.

FOUNDATION_MANAGE admin endpoints for reviewing district / postal-code /
post-office / city-village values members proposed via the "propose"
endpoints in api/routers/foundation.py (SOL-ARCH-010 Amendment,
2026-10-03; SOL-FND-004 §16.8, FND-BR-085 .. FND-BR-090):

  GET  /api/v1/admin/geo-entries/{entity}            — List, filtered by status (scoped)
  GET  /api/v1/admin/geo-entries/{entity}/{entry_pk}  — Detail (scoped)
  POST /api/v1/admin/geo-entries/{entity}/{entry_pk}/approve — Approve a PENDING entry
  POST /api/v1/admin/geo-entries/{entity}/{entry_pk}/correct — Correct a PENDING entry
       into a canonical value (find-or-create), re-pointing dependent
       nss.person_address rows at the survivor.

*entity* is one of: district, postal-code, post-office, city-village.

Rather than four near-duplicate routers, every handler is generic over a
small ENTITY_REGISTRY that describes each table's shape (pk column, self-
correction FK column, entity-specific value columns, and — where
applicable — the nss.person_address FK column to re-point on /correct).
District has no person_address FK column (person_address carries
city_village_pk / postal_code_pk / post_office_pk, but no district_pk — a
district is reached only through city_village), so its registry entry
sets person_address_fk_col = None and /correct skips the re-point step
for it.

Scope: an admin's authority is the recursive organization subtree rooted
at their admin_scope (ADMIN-BR-076, via actor_scope_org_pks()), anchored
through the submitter's nss.sangha_sevi.organization_pk — the same anchor
claim_approval.py uses. A submission from a member outside the admin's
subtree is invisible to list and 403s on detail/approve/correct. The
global authority (NSS_ERP_ADMIN / NSS-WIDE scope) sees and manages
everything.
"""

import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

import psycopg2.errors

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.rbac import require_any_permission
from api.helpers import log_audit
from api.routers.foundation import _derive_provisional_code
from api.schemas.geo_approval import (
    ApproveGeoEntryRequest,
    CorrectGeoEntryRequest,
    CorrectGeoEntryResponse,
    GeoEntryListResponse,
    GeoEntryResponse,
)
from api.services.rbac_service import UserContext, actor_scope_org_pks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/geo-entries", tags=["geo-approval"])


# ── Entity registry ──────────────────────────────────────────────────────
#
# Single source of truth for how each of the four member-writable
# geographic tables maps onto the generic list/detail/approve/correct
# handlers below. Adding a fifth member-writable geo table in future would
# mean adding one entry here, not writing four more endpoints.

ENTITY_REGISTRY: dict[str, dict] = {
    "district": {
        "table": "district",
        "pk_col": "district_pk",
        "self_fk_col": "corrected_into_district_pk",
        "value_cols": ["state_pk", "district_code", "district_name", "display_order"],
        "person_address_fk_col": None,
        # District is never auto-created at registration (registration
        # picks district from a dropdown pk, not free text), so this
        # table has no submitted_by_person_pk column at all.
        "person_submitter": False,
    },
    "postal-code": {
        "table": "postal_code",
        "pk_col": "postal_code_pk",
        "self_fk_col": "corrected_into_postal_code_pk",
        "value_cols": ["state_pk", "postal_code"],
        "person_address_fk_col": "postal_code_pk",
        "person_submitter": True,
    },
    "post-office": {
        "table": "post_office",
        "pk_col": "post_office_pk",
        "self_fk_col": "corrected_into_post_office_pk",
        "value_cols": ["postal_code_pk", "post_office_name", "display_order"],
        "person_address_fk_col": "post_office_pk",
        "person_submitter": True,
    },
    "city-village": {
        "table": "city_village",
        "pk_col": "city_village_pk",
        "self_fk_col": "corrected_into_city_village_pk",
        "value_cols": [
            "district_pk", "postal_code_pk", "city_village_code",
            "city_village_name", "city_village_type", "display_order",
        ],
        "person_address_fk_col": "city_village_pk",
        "person_submitter": True,
    },
}

# The partial unique index(es) each table's APPROVED rows are protected
# by (FND-BR-090) — named explicitly so a UniqueViolation on /approve can
# be translated into a human 409 instead of a raw 500.
_APPROVED_UNIQUE_INDEXES: dict[str, list[str]] = {
    "district": ["uq_district_state_code_approved", "uq_district_state_name_approved"],
    "postal-code": ["uq_postal_code_code_approved"],
    "post-office": ["uq_post_office_pin_name_approved"],
    "city-village": [
        # 2026-10-21 (owner-confirmed): district+name uniqueness removed
        # and PIN+name widened to include district — village names repeat
        # within both a district and a PIN in real Indian geography. See
        # database/ddl/01_foundation/11_city_village.sql.
        "uq_city_village_district_code_approved",
        "uq_city_village_pin_name_district_approved",
    ],
}


def _get_entity_cfg(entity: str) -> dict:
    cfg = ENTITY_REGISTRY.get(entity)
    if cfg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown geo-entry entity '{entity}'. "
                   f"Expected one of: {', '.join(ENTITY_REGISTRY)}.",
        )
    return cfg


def _require_actor_sangha_sevi_pk(user: UserContext) -> str:
    if not user.sangha_sevi_pk:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has no active Sangha Sevi record, so it "
                   "cannot be recorded as the reviewer of this entry.",
        )
    return str(user.sangha_sevi_pk)


def _core_select_sql(cfg: dict, alias: str = "g") -> str:
    core_cols = [
        f"{alias}.{cfg['pk_col']} AS entry_pk",
        f"{alias}.entry_status AS entry_status",
        f"{alias}.submitted_by_sangha_sevi_pk AS submitted_by_sangha_sevi_pk",
        f"{alias}.reviewed_by_sangha_sevi_pk AS reviewed_by_sangha_sevi_pk",
        f"{alias}.reviewed_at AS reviewed_at",
        f"{alias}.admin_remarks AS admin_remarks",
        f"{alias}.{cfg['self_fk_col']} AS corrected_into_pk",
        f"{alias}.is_active AS is_active",
        f"{alias}.created_at AS created_at",
    ]
    value_cols = [f"{alias}.{c} AS val_{c}" for c in cfg["value_cols"]]
    submitter_cols = [
        "ss.sangha_sevi_id AS submitted_by_sangha_sevi_id",
        "ss.organization_pk AS submitted_by_organization_pk",
        "org.organization_name AS submitted_by_organization_name",
    ]
    if cfg.get("person_submitter"):
        person_cols = [
            f"{alias}.submitted_by_person_pk AS submitted_by_person_pk",
            "sp.person_id AS submitted_by_person_id",
            "(sp.first_name || ' ' || COALESCE(sp.last_name, '')) AS submitted_by_person_name",
        ]
    else:
        person_cols = [
            "NULL::uuid AS submitted_by_person_pk",
            "NULL::varchar AS submitted_by_person_id",
            "NULL::varchar AS submitted_by_person_name",
        ]
    return ", ".join(core_cols + value_cols + submitter_cols + person_cols)


def _person_join_sql(cfg: dict, alias: str = "g") -> str:
    """LEFT JOIN fragment for the registration-origin person submitter —
    only emitted for entities that actually carry submitted_by_person_pk
    (district does not; see ENTITY_REGISTRY)."""
    if not cfg.get("person_submitter"):
        return ""
    return f"LEFT JOIN nss.person sp ON sp.person_pk = {alias}.submitted_by_person_pk"


def _row_to_response(entity: str, cfg: dict, columns: list[str], row: tuple) -> GeoEntryResponse:
    d = dict(zip(columns, row))
    value = {c: d[f"val_{c}"] for c in cfg["value_cols"]}
    return GeoEntryResponse(
        entity=entity,
        entry_pk=d["entry_pk"],
        value=value,
        entry_status=d["entry_status"],
        submitted_by_sangha_sevi_pk=d["submitted_by_sangha_sevi_pk"],
        submitted_by_sangha_sevi_id=d["submitted_by_sangha_sevi_id"],
        submitted_by_organization_pk=d["submitted_by_organization_pk"],
        submitted_by_organization_name=d["submitted_by_organization_name"],
        submitted_by_person_pk=d["submitted_by_person_pk"],
        submitted_by_person_id=d["submitted_by_person_id"],
        submitted_by_person_name=d["submitted_by_person_name"],
        reviewed_by_sangha_sevi_pk=d["reviewed_by_sangha_sevi_pk"],
        reviewed_at=d["reviewed_at"],
        admin_remarks=d["admin_remarks"],
        corrected_into_pk=d["corrected_into_pk"],
        is_active=d["is_active"],
        created_at=d["created_at"],
    )


def _fetch_entry(cur, entity: str, cfg: dict, entry_pk) -> GeoEntryResponse | None:
    cur.execute(
        f"""
        SELECT {_core_select_sql(cfg)}
        FROM nss.{cfg['table']} g
        LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = g.submitted_by_sangha_sevi_pk
        LEFT JOIN nss.organization org ON org.organization_pk = ss.organization_pk
        {_person_join_sql(cfg)}
        WHERE g.{cfg['pk_col']} = %s
        """,
        (str(entry_pk),),
    )
    row = cur.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cur.description]
    return _row_to_response(entity, cfg, columns, row)


def _check_entry_scope(cur, user: UserContext, entry: GeoEntryResponse) -> None:
    """403 unless *entry*'s submitting organization is within the actor's scope subtree.

    Additive branch (Registration-Time Geography Creation, 2026-10-21):
    for a registration-origin row (submitted_by_person_pk set, no
    sangha_sevi yet), the submitting person's PENDING registration_claim
    or active sangha_sevi is used instead to anchor the org — see
    list_geo_entries' scope_filter for the equivalent SQL, applied here
    row-at-a-time for the single-entry endpoints (detail/approve/correct).
    """
    allowed = actor_scope_org_pks(cur, user)
    if allowed is None:
        return
    org_pk = entry.submitted_by_organization_pk
    if org_pk is not None and str(org_pk) in allowed:
        return
    person_pk = entry.submitted_by_person_pk
    if person_pk is not None:
        cur.execute(
            """
            SELECT 1 FROM nss.registration_claim rc
            WHERE rc.person_pk = %s
              AND rc.claim_status = 'PENDING' AND rc.is_active = TRUE
              AND rc.claimed_organization_pk = ANY(%s::uuid[])
            UNION ALL
            SELECT 1 FROM nss.sangha_sevi s2
            WHERE s2.person_pk = %s
              AND s2.is_active = TRUE
              AND s2.organization_pk = ANY(%s::uuid[])
            LIMIT 1
            """,
            (str(person_pk), list(allowed), str(person_pk), list(allowed)),
        )
        if cur.fetchone() is not None:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only review geographic entries submitted within your admin scope.",
    )


# ── GET /api/v1/admin/geo-entries/{entity} ──────────────────────────────

@router.get("/{entity}", response_model=GeoEntryListResponse)
def list_geo_entries(
    entity: str,
    entry_status: str = Query(
        "PENDING", alias="status", pattern="^(PENDING|APPROVED|CORRECTED)$"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(require_any_permission("FOUNDATION_MANAGE", "GEO_ENTRY_APPROVE")),
    conn=Depends(get_connection),
) -> GeoEntryListResponse:
    """
    List member-submitted geographic entries, filtered by entry_status.

    Scoped (ADMIN-BR-076): a scope-bounded admin sees only entries
    submitted by members whose sangha_sevi.organization_pk falls inside
    their admin scope subtree. The global authority sees everything.
    """
    cfg = _get_entity_cfg(entity)
    offset = (page - 1) * page_size

    with conn.cursor() as cur:
        allowed = actor_scope_org_pks(cur, user)

    if allowed is not None and not allowed:
        return GeoEntryListResponse(entries=[], total=0, page=page, page_size=page_size)

    scope_filter = ""
    scope_params: list = []
    if allowed is not None:
        if cfg.get("person_submitter"):
            # Additive OR branch (Registration-Time Geography Creation,
            # 2026-10-21): a registration-origin row has no sangha_sevi
            # yet, so it is surfaced via the submitting person's PENDING
            # registration_claim (claimed_organization_pk) OR active
            # sangha_sevi (organization_pk) instead.
            scope_filter = """
                AND (
                    ss.organization_pk = ANY(%s::uuid[])
                    OR EXISTS (
                        SELECT 1 FROM nss.registration_claim rc
                        WHERE rc.person_pk = g.submitted_by_person_pk
                          AND rc.claim_status = 'PENDING' AND rc.is_active = TRUE
                          AND rc.claimed_organization_pk = ANY(%s::uuid[])
                    )
                    OR EXISTS (
                        SELECT 1 FROM nss.sangha_sevi s2
                        WHERE s2.person_pk = g.submitted_by_person_pk
                          AND s2.is_active = TRUE
                          AND s2.organization_pk = ANY(%s::uuid[])
                    )
                )
            """
            scope_params = [list(allowed), list(allowed), list(allowed)]
        else:
            scope_filter = "AND ss.organization_pk = ANY(%s::uuid[])"
            scope_params = [list(allowed)]

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM nss.{cfg['table']} g
            LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = g.submitted_by_sangha_sevi_pk
            WHERE g.entry_status = %s
              {scope_filter}
            """,
            [entry_status] + scope_params,
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT {_core_select_sql(cfg)}
            FROM nss.{cfg['table']} g
            LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = g.submitted_by_sangha_sevi_pk
            LEFT JOIN nss.organization org ON org.organization_pk = ss.organization_pk
            {_person_join_sql(cfg)}
            WHERE g.entry_status = %s
              {scope_filter}
            ORDER BY g.created_at ASC
            LIMIT %s OFFSET %s
            """,
            [entry_status] + scope_params + [page_size, offset],
        )
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]

    entries = [_row_to_response(entity, cfg, columns, r) for r in rows]
    return GeoEntryListResponse(entries=entries, total=total, page=page, page_size=page_size)


# ── GET /api/v1/admin/geo-entries/{entity}/{entry_pk} ───────────────────

@router.get("/{entity}/{entry_pk}", response_model=GeoEntryResponse)
def get_geo_entry(
    entity: str,
    entry_pk: UUID,
    user: UserContext = Depends(require_any_permission("FOUNDATION_MANAGE", "GEO_ENTRY_APPROVE")),
    conn=Depends(get_connection),
) -> GeoEntryResponse:
    cfg = _get_entity_cfg(entity)
    with conn.cursor() as cur:
        entry = _fetch_entry(cur, entity, cfg, entry_pk)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"{entity} entry not found.")
        _check_entry_scope(cur, user, entry)
    return entry


# ── POST /api/v1/admin/geo-entries/{entity}/{entry_pk}/approve ──────────

@router.post("/{entity}/{entry_pk}/approve", response_model=GeoEntryResponse)
def approve_geo_entry(
    entity: str,
    entry_pk: UUID,
    body: ApproveGeoEntryRequest = ApproveGeoEntryRequest(),
    user: UserContext = Depends(require_any_permission("FOUNDATION_MANAGE", "GEO_ENTRY_APPROVE")),
    conn=Depends(get_write_connection),
) -> GeoEntryResponse:
    """
    Approve a PENDING entry as-is: entry_status -> APPROVED.

    If another, already-APPROVED row carries the identical value, the
    UPDATE collides with the approved-only partial unique index
    (FND-BR-090) and PostgreSQL raises UniqueViolation. That is translated
    into a clean 409 pointing the admin at POST .../correct instead, since
    approving a duplicate would otherwise either fail opaquely or (if the
    index weren't there) silently create a second canonical value.
    """
    cfg = _get_entity_cfg(entity)
    with conn.cursor() as cur:
        entry = _fetch_entry(cur, entity, cfg, entry_pk)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"{entity} entry not found.")
        if entry.entry_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Only a PENDING entry can be approved; this one is {entry.entry_status}.",
            )
        _check_entry_scope(cur, user, entry)
        reviewer_pk = _require_actor_sangha_sevi_pk(user)

        cur.execute("SAVEPOINT geo_entry_approve")
        try:
            cur.execute(
                f"""
                UPDATE nss.{cfg['table']}
                SET entry_status = 'APPROVED',
                    reviewed_by_sangha_sevi_pk = %s,
                    reviewed_at = NOW(),
                    admin_remarks = %s,
                    updated_at = NOW()
                WHERE {cfg['pk_col']} = %s
                """,
                (reviewer_pk, body.admin_remarks, str(entry_pk)),
            )
        except psycopg2.errors.UniqueViolation as exc:
            cur.execute("ROLLBACK TO SAVEPOINT geo_entry_approve")
            constraint = getattr(exc.diag, "constraint_name", None) or ""
            if constraint in _APPROVED_UNIQUE_INDEXES.get(entity, []):
                clash_desc = f" (violates {constraint})"
            else:
                clash_desc = ""
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot approve: another APPROVED {entity} entry already "
                    f"has this exact value{clash_desc}. Use POST .../correct "
                    "instead to point this submission at the existing canonical row."
                ),
            )
        cur.execute("RELEASE SAVEPOINT geo_entry_approve")

        log_audit(
            cur, action="APPROVE", table_name=cfg["table"], record_pk=str(entry_pk),
            actor_pk=reviewer_pk, actor_user_account_pk=str(user.user_account_pk),
            module="geo_approval", summary=f"Approved {entity} entry {entry_pk}",
        )

        updated = _fetch_entry(cur, entity, cfg, entry_pk)

    return updated


# ── POST /api/v1/admin/geo-entries/{entity}/{entry_pk}/correct ──────────

def _find_or_create_canonical(
    cur, entity: str, original: GeoEntryResponse, corrected_value: dict, reviewer_pk: str
) -> tuple[str, bool]:
    """
    Find an existing APPROVED, active row matching *corrected_value*, or
    create one. Returns (canonical_pk, newly_created).

    The anchor columns (state_pk / district_pk / postal_code_pk) are taken
    from the ORIGINAL submission, not from corrected_value — an admin is
    correcting the mistyped name/code, not re-anchoring the submission to
    a different parent. Each INSERT runs inside a SAVEPOINT so a race
    against a concurrent admin correction (two admins creating the "same"
    canonical row at once) surfaces as a clean 409 instead of a raw 500,
    mirroring helpers.insert_sakha_affiliation's pattern.
    """
    if entity == "district":
        district_name = (corrected_value.get("district_name") or "").strip()
        if not district_name:
            raise HTTPException(422, detail="corrected_value.district_name is required.")
        district_code = (corrected_value.get("district_code") or "").strip() \
            or _derive_provisional_code(district_name)
        state_pk = str(original.value["state_pk"])

        cur.execute(
            """
            SELECT district_pk FROM nss.district
            WHERE state_pk = %s AND LOWER(district_name) = LOWER(%s)
              AND entry_status = 'APPROVED' AND is_active = TRUE
            LIMIT 1
            """,
            (state_pk, district_name),
        )
        existing = cur.fetchone()
        if existing:
            return str(existing[0]), False

        cur.execute("SAVEPOINT geo_correct_create")
        try:
            cur.execute(
                """
                INSERT INTO nss.district
                    (state_pk, district_code, district_name,
                     entry_status, reviewed_by_sangha_sevi_pk, reviewed_at)
                VALUES (%s, %s, %s, 'APPROVED', %s, NOW())
                RETURNING district_pk
                """,
                (state_pk, district_code, district_name, reviewer_pk),
            )
            new_pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT geo_correct_create")
            raise HTTPException(
                409, detail="Another APPROVED district with this code or name "
                             "already exists. Retry — it will now be found."
            )
        cur.execute("RELEASE SAVEPOINT geo_correct_create")
        return str(new_pk), True

    if entity == "postal-code":
        pin = (corrected_value.get("postal_code") or "").strip()
        if not re.fullmatch(r"\d{6}", pin):
            raise HTTPException(422, detail="corrected_value.postal_code must be a 6-digit PIN.")
        state_pk = str(original.value["state_pk"])

        cur.execute(
            """
            SELECT postal_code_pk FROM nss.postal_code
            WHERE postal_code = %s AND entry_status = 'APPROVED' AND is_active = TRUE
            LIMIT 1
            """,
            (pin,),
        )
        existing = cur.fetchone()
        if existing:
            return str(existing[0]), False

        cur.execute("SAVEPOINT geo_correct_create")
        try:
            cur.execute(
                """
                INSERT INTO nss.postal_code
                    (state_pk, postal_code,
                     entry_status, reviewed_by_sangha_sevi_pk, reviewed_at)
                VALUES (%s, %s, 'APPROVED', %s, NOW())
                RETURNING postal_code_pk
                """,
                (state_pk, pin, reviewer_pk),
            )
            new_pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT geo_correct_create")
            raise HTTPException(
                409, detail="Another APPROVED PIN code with this value already "
                             "exists. Retry — it will now be found."
            )
        cur.execute("RELEASE SAVEPOINT geo_correct_create")
        return str(new_pk), True

    if entity == "post-office":
        name = (corrected_value.get("post_office_name") or "").strip()
        if not name:
            raise HTTPException(422, detail="corrected_value.post_office_name is required.")
        postal_code_pk = str(original.value["postal_code_pk"])

        cur.execute(
            """
            SELECT post_office_pk FROM nss.post_office
            WHERE postal_code_pk = %s AND LOWER(post_office_name) = LOWER(%s)
              AND entry_status = 'APPROVED' AND is_active = TRUE
            LIMIT 1
            """,
            (postal_code_pk, name),
        )
        existing = cur.fetchone()
        if existing:
            return str(existing[0]), False

        cur.execute("SAVEPOINT geo_correct_create")
        try:
            cur.execute(
                """
                INSERT INTO nss.post_office
                    (postal_code_pk, post_office_name,
                     entry_status, reviewed_by_sangha_sevi_pk, reviewed_at)
                VALUES (%s, %s, 'APPROVED', %s, NOW())
                RETURNING post_office_pk
                """,
                (postal_code_pk, name, reviewer_pk),
            )
            new_pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT geo_correct_create")
            raise HTTPException(
                409, detail="Another APPROVED post office with this name already "
                             "exists under this PIN. Retry — it will now be found."
            )
        cur.execute("RELEASE SAVEPOINT geo_correct_create")
        return str(new_pk), True

    if entity == "city-village":
        name = (corrected_value.get("city_village_name") or "").strip()
        cv_type = (corrected_value.get("city_village_type") or "").strip().upper()
        if not name:
            raise HTTPException(422, detail="corrected_value.city_village_name is required.")
        if cv_type not in ("CITY", "TOWN", "VILLAGE"):
            raise HTTPException(
                422, detail="corrected_value.city_village_type must be CITY, TOWN, or VILLAGE."
            )
        district_pk = original.value.get("district_pk")
        postal_code_pk = original.value.get("postal_code_pk")
        district_pk = str(district_pk) if district_pk else None
        postal_code_pk = str(postal_code_pk) if postal_code_pk else None

        existing = None
        if district_pk:
            cur.execute(
                """
                SELECT city_village_pk FROM nss.city_village
                WHERE district_pk = %s AND LOWER(city_village_name) = LOWER(%s)
                  AND entry_status = 'APPROVED' AND is_active = TRUE
                LIMIT 1
                """,
                (district_pk, name),
            )
            existing = cur.fetchone()
        if not existing and postal_code_pk:
            cur.execute(
                """
                SELECT city_village_pk FROM nss.city_village
                WHERE postal_code_pk = %s AND LOWER(city_village_name) = LOWER(%s)
                  AND entry_status = 'APPROVED' AND is_active = TRUE
                LIMIT 1
                """,
                (postal_code_pk, name),
            )
            existing = cur.fetchone()
        if existing:
            return str(existing[0]), False

        code = _derive_provisional_code(name)
        cur.execute("SAVEPOINT geo_correct_create")
        try:
            cur.execute(
                """
                INSERT INTO nss.city_village
                    (district_pk, postal_code_pk, city_village_code,
                     city_village_name, city_village_type,
                     entry_status, reviewed_by_sangha_sevi_pk, reviewed_at)
                VALUES (%s, %s, %s, %s, %s, 'APPROVED', %s, NOW())
                RETURNING city_village_pk
                """,
                (district_pk, postal_code_pk, code, name, cv_type, reviewer_pk),
            )
            new_pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT geo_correct_create")
            raise HTTPException(
                409, detail="Another APPROVED city/village with this value already "
                             "exists. Retry — it will now be found."
            )
        cur.execute("RELEASE SAVEPOINT geo_correct_create")
        return str(new_pk), True

    # Unreachable — _get_entity_cfg() already validated entity.
    raise HTTPException(500, detail="Unhandled entity in correction.")


@router.post("/{entity}/{entry_pk}/correct", response_model=CorrectGeoEntryResponse)
def correct_geo_entry(
    entity: str,
    entry_pk: UUID,
    body: CorrectGeoEntryRequest,
    user: UserContext = Depends(require_any_permission("FOUNDATION_MANAGE", "GEO_ENTRY_APPROVE")),
    conn=Depends(get_write_connection),
) -> CorrectGeoEntryResponse:
    """
    Correct a PENDING entry into a canonical value (FND-BR-087/088).

    1. Find-or-create the canonical APPROVED row matching corrected_value.
    2. Mark the original row CORRECTED, pointing corrected_into_<table>_pk
       at the canonical survivor.
    3. Re-point every nss.person_address row that referenced the original
       PK at the canonical one instead — except for district, since
       person_address has no district_pk column (a district is only
       reachable through city_village there).

    admin_remarks is mandatory here (unlike /approve) — this is the audit
    trail for why the member's typed value was not taken as-is.
    """
    cfg = _get_entity_cfg(entity)
    with conn.cursor() as cur:
        entry = _fetch_entry(cur, entity, cfg, entry_pk)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"{entity} entry not found.")
        if entry.entry_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Only a PENDING entry can be corrected; this one is {entry.entry_status}.",
            )
        _check_entry_scope(cur, user, entry)
        reviewer_pk = _require_actor_sangha_sevi_pk(user)

        canonical_pk, newly_created = _find_or_create_canonical(
            cur, entity, entry, body.corrected_value, reviewer_pk
        )

        cur.execute(
            f"""
            UPDATE nss.{cfg['table']}
            SET entry_status = 'CORRECTED',
                {cfg['self_fk_col']} = %s,
                reviewed_by_sangha_sevi_pk = %s,
                reviewed_at = NOW(),
                admin_remarks = %s,
                updated_at = NOW()
            WHERE {cfg['pk_col']} = %s
            """,
            (canonical_pk, reviewer_pk, body.admin_remarks, str(entry_pk)),
        )

        fk_col = cfg["person_address_fk_col"]
        if fk_col:
            cur.execute(
                f"""
                UPDATE nss.person_address
                SET {fk_col} = %s, updated_at = NOW()
                WHERE {fk_col} = %s
                """,
                (canonical_pk, str(entry_pk)),
            )

        log_audit(
            cur, action="CORRECT", table_name=cfg["table"], record_pk=str(entry_pk),
            actor_pk=reviewer_pk, actor_user_account_pk=str(user.user_account_pk),
            module="geo_approval",
            summary=f"Corrected {entity} entry {entry_pk} into canonical {canonical_pk}",
            detail={"corrected_value": body.corrected_value, "admin_remarks": body.admin_remarks},
        )

    return CorrectGeoEntryResponse(
        message="Entry corrected into canonical value.",
        original_pk=entry_pk,
        canonical_pk=UUID(canonical_pk),
        canonical_was_newly_created=newly_created,
    )
