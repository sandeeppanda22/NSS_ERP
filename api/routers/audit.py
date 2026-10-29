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

nss_db_backend connects with SELECT privileges on field_change_log; this
router never writes — the change log is populated by the DB audit trigger.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from api.database import get_connection
from api.dependencies.rbac import require_permission
from api.helpers import DEFAULT_LIMIT, MAX_LIMIT, rows_to_models
from api.schemas.audit import FieldChangeLogResponse
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
