"""
Audit API router — Tier 5 authenticated audit-trail access.

Exposes the field-level change history recorded in nss.field_change_log:
one row per field per DB operation (CREATE / UPDATE / DELETE), across every
audited table, with the actor and timestamp.

This is the authenticated counterpart to the deliberately-unexposed Tier 1
audit data: /api/v1/foundation/change-log does NOT exist (guarded by
tests/api/test_foundation.py::TestChangeLogNotExposed). Audit data is
reachable only here, and only with the AUDIT_VIEW permission (seeded to
NSS_ERP_ADMIN, NSS_ERP_KENDRA_ADMIN, NSS_ERP_AUDITOR).

Endpoints (all require authentication + AUDIT_VIEW):
  GET /api/v1/audit/change-log  — filterable, paginated field-change history
  GET /api/v1/audit/events      — system_event_log explorer: filtered, sorted, paged
  GET /api/v1/audit/events/facets — distinct tables / actions / modules (last 30 days)
  GET /api/v1/audit/events/{pk} — one event incl. its JSONB detail
  GET /api/v1/audit/live-change-markers — nss.live_change_marker diagnostics

nss_db_backend connects with SELECT privileges on field_change_log; this
router never writes — the change log is populated by the DB audit trigger.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from api.database import get_connection
from api.dependencies.rbac import require_permission
from api.helpers import DEFAULT_LIMIT, MAX_LIMIT, rows_to_models
from api.routers.live import LIVE_FEED_TABLES
from api.schemas.audit import (
    FieldChangeLogResponse,
    LiveChangeMarkerRow,
    LiveChangeMarkersResponse,
    SystemEventDetailResponse,
    SystemEventFacets,
    SystemEventPage,
    SystemEventResponse,
)
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/change-log", response_model=list[FieldChangeLogResponse])
def list_field_change_log(
    table_name: str | None = Query(None, description="Filter by source table name"),
    action: str | None = Query(
        None,
        pattern="^(CREATE|UPDATE|DELETE)$",
        description="Filter by DB operation: CREATE, UPDATE or DELETE",
    ),
    record_pk: UUID | None = Query(None, description="Filter by changed record PK"),
    field_name: str | None = Query(None, description="Filter by changed field name"),
    changed_by_sangha_sevi_pk: UUID | None = Query(
        None, description="Filter by the Sangha Sevi who made the change"
    ),
    changed_by_user_account_pk: UUID | None = Query(
        None, description="Filter by the user account that made the change"
    ),
    changed_from: datetime | None = Query(
        None, description="Only changes at/after this timestamp (inclusive)"
    ),
    changed_to: datetime | None = Query(
        None, description="Only changes at/before this timestamp (inclusive)"
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    user: UserContext = Depends(require_permission("AUDIT_VIEW")),
    conn=Depends(get_connection),
) -> list[FieldChangeLogResponse]:
    """
    List field-level change-log entries, most recent change first.

    Requires: AUDIT_VIEW permission.

    Covers every DB operation on every audited table — CREATE, UPDATE
    and DELETE — with the field name, its old and new value, when it
    happened (changed_at) and who did it (Sangha Sevi id and/or user
    account, with the person's name resolved).

    Filter by table_name, action, record_pk, field_name, the acting
    Sangha Sevi or user account, and/or a changed_at date range.
    Supports pagination via limit/offset (default 100, max 500).
    """
    sql = """
        SELECT fcl.field_change_log_pk,
               fcl.action,
               fcl.table_name,
               fcl.record_pk,
               fcl.field_name,
               fcl.old_value,
               fcl.new_value,
               fcl.change_reason,
               fcl.changed_at,
               fcl.changed_by_sangha_sevi_pk,
               ss.sangha_sevi_id AS changed_by_sangha_sevi_id,
               fcl.changed_by_user_account_pk,
               NULLIF(TRIM(CONCAT_WS(' ', p.first_name,
                                          p.middle_name,
                                          p.last_name)), '')
                   AS changed_by_name
        FROM   nss.field_change_log fcl
        LEFT JOIN nss.sangha_sevi ss
               ON ss.sangha_sevi_pk = fcl.changed_by_sangha_sevi_pk
        LEFT JOIN nss.user_account ua
               ON ua.user_account_pk = fcl.changed_by_user_account_pk
        LEFT JOIN nss.person p
               ON p.person_pk = ua.person_pk
    """
    conditions: list[str] = []
    params: list = []

    if table_name is not None:
        conditions.append("fcl.table_name = %s")
        params.append(table_name)
    if action is not None:
        conditions.append("fcl.action = %s")
        params.append(action)
    if record_pk is not None:
        conditions.append("fcl.record_pk = %s")
        params.append(str(record_pk))
    if field_name is not None:
        conditions.append("fcl.field_name = %s")
        params.append(field_name)
    if changed_by_sangha_sevi_pk is not None:
        conditions.append("fcl.changed_by_sangha_sevi_pk = %s")
        params.append(str(changed_by_sangha_sevi_pk))
    if changed_by_user_account_pk is not None:
        conditions.append("fcl.changed_by_user_account_pk = %s")
        params.append(str(changed_by_user_account_pk))
    if changed_from is not None:
        conditions.append("fcl.changed_at >= %s")
        params.append(changed_from)
    if changed_to is not None:
        conditions.append("fcl.changed_at <= %s")
        params.append(changed_to)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    # field_change_log_pk breaks ties among rows sharing a timestamp (one
    # statement logs one row per field in the same transaction), so
    # LIMIT/OFFSET paging is deterministic.
    sql += " ORDER BY fcl.changed_at DESC, fcl.field_change_log_pk DESC"
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        return rows_to_models(cur, FieldChangeLogResponse)


# ── system_event_log explorer ────────────────────────────────────────────

# Exact counting stops here: the explorer shows "10,000+" instead of scanning
# an unbounded range (the table is append-only with no retention policy).
EVENT_TOTAL_CAP = 10_000
# With neither event_from nor record_pk the explorer looks at the last day only.
EVENT_DEFAULT_WINDOW = timedelta(hours=24)
# Window used for the filter dropdowns (a bounded scan of idx_sel_event_at).
EVENT_FACET_WINDOW = timedelta(days=30)

_EVENT_SELECT = """
        SELECT sel.system_event_log_pk,
               sel.event_at,
               sel.action,
               sel.table_name,
               sel.record_pk,
               sel.module,
               sel.summary,
               sel.is_success,
               sel.actor_sangha_sevi_pk,
               ss.sangha_sevi_id AS actor_sangha_sevi_id,
               sel.actor_user_account_pk,
               NULLIF(TRIM(CONCAT_WS(' ', p.first_name,
                                          p.middle_name,
                                          p.last_name)), '')
                   AS actor_name
        {extra}
        FROM   nss.system_event_log sel
        LEFT JOIN nss.sangha_sevi ss
               ON ss.sangha_sevi_pk = sel.actor_sangha_sevi_pk
        LEFT JOIN nss.user_account ua
               ON ua.user_account_pk = sel.actor_user_account_pk
        LEFT JOIN nss.person p
               ON p.person_pk = COALESCE(ua.person_pk, ss.person_pk)
"""


def _like_escape(text: str) -> str:
    """Escape LIKE wildcards so free text is matched literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/events", response_model=SystemEventPage)
def list_system_events(
    table_name: str | None = Query(None, description="Exact table name"),
    action: str | None = Query(None, max_length=50, description="Exact action, e.g. CREATE, APPROVE, LOGIN"),
    module: str | None = Query(None, max_length=50, description="Exact module / functional area"),
    record_pk: UUID | None = Query(None, description="Events for this record PK"),
    actor_sangha_sevi_id: str | None = Query(
        None, max_length=50, description="Business Sangha Sevi id of the actor, e.g. SS12 (case-insensitive)"
    ),
    is_success: bool | None = Query(None, description="Only successful / only failed events"),
    event_from: datetime | None = Query(
        None, description="Events at/after this timestamp (default: last 24 h unless record_pk is given)"
    ),
    event_to: datetime | None = Query(None, description="Events at/before this timestamp"),
    q: str | None = Query(None, min_length=1, max_length=100, description="Free text over summary, module, table and action"),
    sort: str = Query("desc", pattern="^(asc|desc)$", description="event_at order"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Max rows"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    user: UserContext = Depends(require_permission("AUDIT_VIEW")),
    conn=Depends(get_connection),
) -> SystemEventPage:
    """
    Filtered, sorted, paged view of nss.system_event_log (read only).

    Requires: AUDIT_VIEW permission.

    Unless ``event_from`` or ``record_pk`` is given, only the last 24 hours are
    searched (the log is append-only and large); the applied lower bound is
    echoed as ``event_from``. ``total`` is exact up to 10,000 matches.
    """
    now = datetime.now(timezone.utc)
    applied_from = event_from
    if applied_from is None and record_pk is None:
        applied_from = now - EVENT_DEFAULT_WINDOW

    conditions: list[str] = []
    params: list = []
    if table_name is not None:
        conditions.append("sel.table_name = %s")
        params.append(table_name)
    if action is not None:
        conditions.append("sel.action = %s")
        params.append(action)
    if module is not None:
        conditions.append("sel.module = %s")
        params.append(module)
    if record_pk is not None:
        conditions.append("sel.record_pk = %s")
        params.append(str(record_pk))
    if actor_sangha_sevi_id is not None:
        conditions.append("UPPER(ss.sangha_sevi_id) = UPPER(%s)")
        params.append(actor_sangha_sevi_id.strip())
    if is_success is not None:
        conditions.append("sel.is_success = %s")
        params.append(is_success)
    if applied_from is not None:
        conditions.append("sel.event_at >= %s")
        params.append(applied_from)
    if event_to is not None:
        conditions.append("sel.event_at <= %s")
        params.append(event_to)
    if q is not None:
        like = f"%{_like_escape(q.strip())}%"
        conditions.append(
            "(sel.summary ILIKE %s OR sel.module ILIKE %s OR sel.table_name ILIKE %s OR sel.action ILIKE %s)"
        )
        params.extend([like, like, like, like])
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    direction = "ASC" if sort == "asc" else "DESC"
    # system_event_log_pk breaks ties among events of one transaction (they
    # share event_at), so LIMIT/OFFSET paging is deterministic.
    sql = (
        _EVENT_SELECT.format(extra="")
        + where
        + f" ORDER BY sel.event_at {direction}, sel.system_event_log_pk {direction}"
        + " LIMIT %s OFFSET %s"
    )
    count_sql = (
        "SELECT COUNT(*) FROM (SELECT 1 FROM nss.system_event_log sel "
        "LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = sel.actor_sangha_sevi_pk"
        + where
        + " LIMIT %s) c"
    )

    with conn.cursor() as cur:
        cur.execute(count_sql, tuple(params) + (EVENT_TOTAL_CAP + 1,))
        counted = cur.fetchone()[0]
        cur.execute(sql, tuple(params) + (limit, offset))
        items = rows_to_models(cur, SystemEventResponse)
    return SystemEventPage(
        items=items,
        total=min(counted, EVENT_TOTAL_CAP),
        total_capped=counted > EVENT_TOTAL_CAP,
        event_from=applied_from,
        limit=limit,
        offset=offset,
    )


@router.get("/events/facets", response_model=SystemEventFacets)
def system_event_facets(
    user: UserContext = Depends(require_permission("AUDIT_VIEW")),
    conn=Depends(get_connection),
) -> SystemEventFacets:
    """Distinct tables, actions and modules seen in the last 30 days (filter dropdowns)."""
    since = datetime.now(timezone.utc) - EVENT_FACET_WINDOW
    out: dict[str, list[str]] = {}
    with conn.cursor() as cur:
        for key, column in (("tables", "table_name"), ("actions", "action"), ("modules", "module")):
            cur.execute(
                f"SELECT DISTINCT {column} FROM nss.system_event_log "
                f"WHERE event_at >= %s AND {column} IS NOT NULL ORDER BY 1",
                (since,),
            )
            out[key] = [r[0] for r in cur.fetchall()]
    return SystemEventFacets(**out)


@router.get("/events/{system_event_log_pk}", response_model=SystemEventDetailResponse)
def get_system_event(
    system_event_log_pk: UUID,
    user: UserContext = Depends(require_permission("AUDIT_VIEW")),
    conn=Depends(get_connection),
) -> SystemEventDetailResponse:
    """
    One event with its JSONB ``detail``. The field-level changes recorded in the
    same transaction come from ``GET /audit/change-log`` (filter by this event's
    table_name + record_pk and changed_from = changed_to = event_at).
    """
    sql = _EVENT_SELECT.format(extra=", sel.detail") + " WHERE sel.system_event_log_pk = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (str(system_event_log_pk),))
        columns = [d[0] for d in cur.description]
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="System event not found.")
    return SystemEventDetailResponse(**dict(zip(columns, row)))


# ── live_change_marker diagnostics ───────────────────────────────────────

@router.get("/live-change-markers", response_model=LiveChangeMarkersResponse)
def list_live_change_markers(
    user: UserContext = Depends(require_permission("AUDIT_VIEW")),
    conn=Depends(get_connection),
) -> LiveChangeMarkersResponse:
    """
    Every row of nss.live_change_marker (about 27 tiny rows), most recently
    changed first, flagged with whether the table is on the live-feed whitelist
    (``api/routers/live.py::LIVE_FEED_TABLES``). Unlike GET /live/changes this
    shows the change timestamps and also non-whitelisted rows.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, change_seq, changed_at, clock_timestamp()
            FROM   nss.live_change_marker
            ORDER  BY change_seq DESC
            """
        )
        raw = cur.fetchall()
    markers = [
        LiveChangeMarkerRow(
            table_name=r[0], change_seq=r[1], changed_at=r[2],
            on_live_whitelist=r[0] in LIVE_FEED_TABLES,
        )
        for r in raw
    ]
    present = {m.table_name for m in markers}
    return LiveChangeMarkersResponse(
        server_time=raw[0][3] if raw else datetime.now(timezone.utc),
        markers=markers,
        latest_change_seq=markers[0].change_seq if markers else None,
        latest_table_name=markers[0].table_name if markers else None,
        whitelist_size=len(LIVE_FEED_TABLES),
        whitelist_without_marker=sorted(LIVE_FEED_TABLES - present),
    )
