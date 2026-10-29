"""
NSS ERP — Membership Change Request router (Tier 6, MBR-048/MBR-049).

Sakha Transfer / Apply for Darshak: a two-step request/release/accept
workflow on nss.membership_change_request.

  POST /api/v1/membership/change-requests                        — create
  GET  /api/v1/membership/change-requests                         — list (scoped)
  GET  /api/v1/membership/change-requests/{pk}                    — detail
  POST /api/v1/membership/change-requests/{pk}/source-decision     — release/reject
  POST /api/v1/membership/change-requests/{pk}/destination-decision — accept/reject

Workflow:
  PENDING_SOURCE_RELEASE
    -> source Sakha releases   -> PENDING_DESTINATION_ACCEPT
    -> source Sakha rejects    -> REJECTED_BY_SOURCE          [terminal]
  PENDING_DESTINATION_ACCEPT
    -> destination Sakha accepts  -> COMPLETED                [terminal]
    -> destination Sakha rejects  -> REJECTED_BY_DESTINATION   [terminal]

A separate router (not api/routers/membership.py) because membership.py is
documented and built as a read-only, nss_db_backend-only router (8 GET
endpoints) — these are write endpoints and need the auditing write
connection (api.dependencies.auth.get_write_connection), never
api.database's non-auditing primitive.

Authority: MBR-048 (Sakha Transfer), MBR-049 (Apply for Darshak).
"""

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_current_user, get_write_connection
from api.dependencies.rbac import require_permission
from api.helpers import (
    close_sakha_affiliation,
    insert_sakha_affiliation,
    is_probationary_membership_type,
    log_audit,
    next_festival_date_on_or_after,
    require_sakha_organization,
)
from api.schemas.membership_change_request import (
    ChangeRequestCreate,
    ChangeRequestListResponse,
    ChangeRequestResponse,
    DestinationDecisionRequest,
    SourceDecisionRequest,
)
from api.services.rbac_service import UserContext, org_in_scope, require_org_in_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/membership/change-requests", tags=["membership-change-request"])

_OPEN_STATUSES = ("PENDING_SOURCE_RELEASE", "PENDING_DESTINATION_ACCEPT")

# Darshak attendance has no single obvious journey_event code in the
# existing catalogue (07_membership_journey_event.sql's example list is
# ENROLMENT/TRANSFER/STATUS_CHANGE-shaped, not attendance-shaped). event_type
# is a plain, non-FK VARCHAR by design (the catalogue is application-layer,
# extensible) — this is a new, documented addition to it.
_DARSHAK_JOURNEY_EVENT_TYPE = "DARSHAK_ATTENDANCE_STARTED"


_DETAIL_SELECT = """
    SELECT mcr.membership_change_request_pk,
           mcr.sangha_sevi_pk,
           ss.sangha_sevi_id,
           CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name) AS member_name,
           mcr.request_type,
           mcr.old_organization_pk,
           oorg.organization_name,
           mcr.new_organization_pk,
           norg.organization_name,
           mcr.transfer_reason,
           mcr.requested_by_sangha_sevi_pk,
           mcr.requested_date,
           mcr.status,
           mcr.source_decided_by_sangha_sevi_pk,
           mcr.source_decided_at,
           mcr.source_remarks,
           mcr.destination_decided_by_sangha_sevi_pk,
           mcr.destination_decided_at,
           mcr.destination_remarks,
           mcr.new_local_number,
           mcr.effective_date,
           mcr.remarks,
           mcr.created_at
    FROM nss.membership_change_request mcr
    JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = mcr.sangha_sevi_pk
    JOIN nss.person p ON p.person_pk = ss.person_pk
    JOIN nss.organization oorg ON oorg.organization_pk = mcr.old_organization_pk
    JOIN nss.organization norg ON norg.organization_pk = mcr.new_organization_pk
"""


def _row_to_response(r) -> ChangeRequestResponse:
    return ChangeRequestResponse(
        membership_change_request_pk=r[0],
        sangha_sevi_pk=r[1],
        sangha_sevi_id=r[2],
        member_name=r[3] or "",
        request_type=r[4],
        old_organization_pk=r[5],
        old_organization_name=r[6],
        new_organization_pk=r[7],
        new_organization_name=r[8],
        transfer_reason=r[9],
        requested_by_sangha_sevi_pk=r[10],
        requested_date=r[11],
        status=r[12],
        source_decided_by_sangha_sevi_pk=r[13],
        source_decided_at=r[14],
        source_remarks=r[15],
        destination_decided_by_sangha_sevi_pk=r[16],
        destination_decided_at=r[17],
        destination_remarks=r[18],
        new_local_number=r[19],
        effective_date=r[20],
        remarks=r[21],
        created_at=r[22],
    )


# ── POST /api/v1/membership/change-requests ────────────────────────────

@router.post("", response_model=ChangeRequestResponse, status_code=status.HTTP_201_CREATED)
def create_change_request(
    body: ChangeRequestCreate,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> ChangeRequestResponse:
    """
    File a TRANSFER or DARSHAK change request.

    Self-service: a member may file for themself (body.sangha_sevi_pk ==
    user.sangha_sevi_pk). Admin-on-behalf-of: MEMBERSHIP_MANAGE is the
    permission used here (not MEMBERSHIP_APPROVE, which is reserved for the
    source/destination decision steps below — filing a request is a distinct
    action from approving one, and MEMBERSHIP_MANAGE is this project's
    general "administer a member's record" permission).
    """
    is_self = user.sangha_sevi_pk is not None and str(body.sangha_sevi_pk) == str(user.sangha_sevi_pk)
    if not is_self and not user.has_permission("MEMBERSHIP_MANAGE"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only file a change request for yourself unless you hold MEMBERSHIP_MANAGE.",
        )

    with conn.cursor() as cur:
        # The member's current home Sakha (ACTIVE/REACTIVATED, open-ended
        # affiliation) is old_organization_pk for both request types — for
        # DARSHAK this is informational only (MBR-049), never closed.
        cur.execute(
            """
            SELECT organization_pk
            FROM nss.membership_sakha_affiliation
            WHERE sangha_sevi_pk = %s AND effective_to IS NULL
            ORDER BY effective_from DESC
            LIMIT 1
            """,
            (str(body.sangha_sevi_pk),),
        )
        home_row = cur.fetchone()
        if home_row is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="This member has no active Sakha affiliation to transfer or attend from.",
            )
        old_organization_pk = str(home_row[0])

        # Filing on a member's behalf is an admin action on that member's
        # home Sakha: the filer must hold admin scope over it (ADMIN-BR-076).
        if not is_self:
            require_org_in_scope(cur, user, old_organization_pk, "file a change request for this member")

        if str(body.new_organization_pk) == old_organization_pk:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The destination Sakha must be different from the current Sakha.",
            )

        require_sakha_organization(cur, str(body.new_organization_pk))

        # One open request per member at a time (also enforced by the partial
        # unique index uq_mem_change_req_one_open) — a clear 409 instead of a
        # generic integrity-violation message.
        cur.execute(
            """
            SELECT 1 FROM nss.membership_change_request
            WHERE sangha_sevi_pk = %s AND status = ANY(%s)
            """,
            (str(body.sangha_sevi_pk), list(_OPEN_STATUSES)),
        )
        if cur.fetchone() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This member already has an open change request; it must be decided before another is filed.",
            )

        cur.execute(
            """
            INSERT INTO nss.membership_change_request (
                sangha_sevi_pk, request_type,
                old_organization_pk, new_organization_pk,
                transfer_reason, requested_by_sangha_sevi_pk
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING membership_change_request_pk
            """,
            (
                str(body.sangha_sevi_pk),
                body.request_type,
                old_organization_pk,
                str(body.new_organization_pk),
                body.transfer_reason,
                str(user.sangha_sevi_pk) if user.sangha_sevi_pk else str(body.sangha_sevi_pk),
            ),
        )
        req_pk = cur.fetchone()[0]

        log_audit(
            cur, action="CREATE", table_name="membership_change_request", record_pk=str(req_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="membership_change_request",
            summary=f"Filed {body.request_type} change request",
        )

        cur.execute(_DETAIL_SELECT + " WHERE mcr.membership_change_request_pk = %s", (str(req_pk),))
        row = cur.fetchone()

    return _row_to_response(row)


# ── GET /api/v1/membership/change-requests ──────────────────────────────

@router.get("", response_model=ChangeRequestListResponse)
def list_change_requests(
    status_filter: str | None = Query(None, alias="status"),
    organization_pk: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> ChangeRequestListResponse:
    """
    List change requests, optionally filtered by status and/or an org
    (matches either old_organization_pk or new_organization_pk).

    Two access paths, mirroring the self-or-permission pattern used by
    Person/Membership detail endpoints:
      - MEMBERSHIP_VIEW or MEMBERSHIP_APPROVE: admin view, scoped to the
        caller's admin scope (NSS-wide sees everything).
      - Neither permission, but the caller has a sangha_sevi_pk: self
        view — forced to only their own rows (requested_by filter/org
        filter above are ignored; a plain member has no admin scope to
        filter by anyway, and this is the only way they can ever see
        their own request's status, since the create response is their
        only other source of it).
      - Neither permission and no sangha_sevi_pk: nothing to see, 403.
    """
    is_admin_view = user.has_permission("MEMBERSHIP_VIEW") or user.has_permission("MEMBERSHIP_APPROVE")
    if not is_admin_view and not user.sangha_sevi_pk:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view change requests.",
        )

    offset = (page - 1) * page_size
    filters = []
    params: list = []

    if is_admin_view and status_filter:
        filters.append("mcr.status = %s")
        params.append(status_filter)
    if is_admin_view and organization_pk:
        filters.append("(mcr.old_organization_pk = %s OR mcr.new_organization_pk = %s)")
        params.extend([str(organization_pk), str(organization_pk)])

    with conn.cursor() as cur:
        if not is_admin_view:
            # Self view: own requests only, regardless of any status/org
            # filter passed in.
            filters.append("mcr.sangha_sevi_pk = %s")
            params.append(str(user.sangha_sevi_pk))
        elif not user.is_nss_wide():
            # Admin view, scoped: visible only if either side of the
            # request is within the caller's admin scope.
            from api.services.rbac_service import actor_scope_org_pks
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None:
                if not allowed:
                    return ChangeRequestListResponse(requests=[], total=0)
                placeholders = ",".join(["%s"] * len(allowed))
                filters.append(
                    f"(mcr.old_organization_pk IN ({placeholders}) OR mcr.new_organization_pk IN ({placeholders}))"
                )
                params.extend(list(allowed))
                params.extend(list(allowed))

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        cur.execute(
            f"SELECT COUNT(*) FROM nss.membership_change_request mcr {where_clause}",
            params,
        )
        total = cur.fetchone()[0]

        cur.execute(
            _DETAIL_SELECT + f" {where_clause} ORDER BY mcr.created_at DESC LIMIT %s OFFSET %s",
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    return ChangeRequestListResponse(requests=[_row_to_response(r) for r in rows], total=total)


# ── GET /api/v1/membership/change-requests/{pk} ─────────────────────────

@router.get("/{change_request_pk}", response_model=ChangeRequestResponse)
def get_change_request(
    change_request_pk: UUID,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> ChangeRequestResponse:
    """
    Detail access: the member themself, or an admin holding MEMBERSHIP_VIEW/
    MEMBERSHIP_APPROVE whose admin scope covers either side (old or new
    Sakha) of the request — the same visibility rule list_change_requests()
    applies.
    """
    with conn.cursor() as cur:
        cur.execute(_DETAIL_SELECT + " WHERE mcr.membership_change_request_pk = %s", (str(change_request_pk),))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Change request not found.")

        is_self = user.sangha_sevi_pk is not None and str(row[1]) == str(user.sangha_sevi_pk)
        if not is_self and not user.has_any_permission("MEMBERSHIP_VIEW", "MEMBERSHIP_APPROVE"):
            raise HTTPException(status_code=403, detail="You do not have access to this change request.")
        if not is_self and not (org_in_scope(cur, user, row[5]) or org_in_scope(cur, user, row[7])):
            raise HTTPException(status_code=403, detail="You do not have access to this change request.")

    return _row_to_response(row)


# ── POST /api/v1/membership/change-requests/{pk}/source-decision ───────

@router.post("/{change_request_pk}/source-decision", response_model=ChangeRequestResponse)
def source_decision(
    change_request_pk: UUID,
    body: SourceDecisionRequest,
    user: UserContext = Depends(require_permission("MEMBERSHIP_APPROVE")),
    conn=Depends(get_write_connection),
) -> ChangeRequestResponse:
    """Source (old_organization_pk) Sakha releases or rejects a PENDING_SOURCE_RELEASE request."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, old_organization_pk FROM nss.membership_change_request WHERE membership_change_request_pk = %s",
            (str(change_request_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Change request not found.")
        current_status, old_org_pk = row

        # Authorization before state: an out-of-scope admin gets 403 whatever
        # the request's status, never a 422 that discloses it.
        require_org_in_scope(cur, user, old_org_pk, "release this member's affiliation")

        if current_status != "PENDING_SOURCE_RELEASE":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"This request is {current_status}; a source decision is no longer applicable.",
            )

        new_status = "PENDING_DESTINATION_ACCEPT" if body.decision == "RELEASE" else "REJECTED_BY_SOURCE"
        cur.execute(
            """
            UPDATE nss.membership_change_request
            SET status = %s,
                source_decided_by_sangha_sevi_pk = %s,
                source_decided_at = NOW(),
                source_remarks = %s
            WHERE membership_change_request_pk = %s
            """,
            (new_status, user.actor_pk, body.remarks, str(change_request_pk)),
        )
        log_audit(
            cur, action="APPROVE" if body.decision == "RELEASE" else "REJECT",
            table_name="membership_change_request", record_pk=str(change_request_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="membership_change_request",
            summary=f"Source Sakha {body.decision.lower()}d change request",
            detail={"remarks": body.remarks},
        )

        cur.execute(_DETAIL_SELECT + " WHERE mcr.membership_change_request_pk = %s", (str(change_request_pk),))
        result_row = cur.fetchone()

    return _row_to_response(result_row)


# ── POST /api/v1/membership/change-requests/{pk}/destination-decision ──

@router.post("/{change_request_pk}/destination-decision", response_model=ChangeRequestResponse)
def destination_decision(
    change_request_pk: UUID,
    body: DestinationDecisionRequest,
    user: UserContext = Depends(require_permission("MEMBERSHIP_APPROVE")),
    conn=Depends(get_write_connection),
) -> ChangeRequestResponse:
    """
    Destination (new_organization_pk) Sakha accepts or rejects a
    PENDING_DESTINATION_ACCEPT request.

    On ACCEPT: resolves effective_date to the next Dola Purnima, opens the
    new affiliation (auto-numbered unless is_legacy_import + new_local_number
    are both given), and — for TRANSFER only — closes the old affiliation and
    writes membership_transfer_history. Both request types write a
    membership_journey_event.
    """
    if body.new_local_number and not body.is_legacy_import:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="new_local_number may only be set together with is_legacy_import=true.",
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, sangha_sevi_pk, request_type,
                   old_organization_pk, new_organization_pk
            FROM nss.membership_change_request
            WHERE membership_change_request_pk = %s
            """,
            (str(change_request_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Change request not found.")
        current_status, sangha_sevi_pk, request_type, old_org_pk, new_org_pk = row

        require_org_in_scope(cur, user, new_org_pk, "accept this member into this Sakha")

        if current_status != "PENDING_DESTINATION_ACCEPT":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"This request is {current_status}; a destination decision is no longer applicable.",
            )

        if body.decision == "REJECT":
            cur.execute(
                """
                UPDATE nss.membership_change_request
                SET status = 'REJECTED_BY_DESTINATION',
                    destination_decided_by_sangha_sevi_pk = %s,
                    destination_decided_at = NOW(),
                    destination_remarks = %s
                WHERE membership_change_request_pk = %s
                """,
                (user.actor_pk, body.remarks, str(change_request_pk)),
            )
            log_audit(
                cur, action="REJECT", table_name="membership_change_request",
                record_pk=str(change_request_pk), actor_pk=user.actor_pk,
                actor_user_account_pk=str(user.user_account_pk),
                module="membership_change_request",
                summary="Destination Sakha rejected change request",
                detail={"remarks": body.remarks},
            )
            cur.execute(_DETAIL_SELECT + " WHERE mcr.membership_change_request_pk = %s", (str(change_request_pk),))
            return _row_to_response(cur.fetchone())

        # ── ACCEPT ────────────────────────────────────────────────
        # effective_date: the next confirmed Dola Purnima on/after today —
        # the same festival-calendar lookup issue_membership_credential()
        # already uses, never reimplemented.
        effective_date: date = next_festival_date_on_or_after(cur, "DOLA_PURNIMA", date.today())
        if effective_date is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "No confirmed Dola Purnima date is on file on or after today. "
                    "An administrator must enter/confirm it in the festival reference calendar first."
                ),
            )

        # Darshak attendance is namespaced (MBR-030C): only a PROBATIONARY
        # member's attendance affiliation uses the Darshak namespace marker;
        # a Regular member attending as a visiting Darshak elsewhere still
        # composes under the Darshak namespace at the ATTENDING org (MBR-049
        # "Visiting Regular Members"). Either way, DARSHAK requests always
        # use the Darshak namespace at the destination.
        cur.execute("SELECT membership_type_master_data_pk FROM nss.sangha_sevi WHERE sangha_sevi_pk = %s",
                    (str(sangha_sevi_pk),))
        membership_type_pk = (cur.fetchone() or (None,))[0]
        is_darshak_namespace = (
            request_type == "DARSHAK" or is_probationary_membership_type(cur, membership_type_pk)
        )

        new_local_number = body.new_local_number if body.is_legacy_import else None
        # TRANSFER: this new affiliation IS the transfer (the old one is
        # closed below) — tag it 'TRANSFER' so the row is distinguishable
        # from a fresh enrollment. DARSHAK: this is a second, concurrently
        # -active affiliation at another Sakha while the home affiliation
        # stays open — a genuine new enrollment in that Sakha's namespace,
        # so the 'ENROLLMENT' default is correct and left unset here.
        new_aff_pk = insert_sakha_affiliation(
            cur,
            sangha_sevi_pk=str(sangha_sevi_pk),
            organization_pk=str(new_org_pk),
            local_number=new_local_number,
            effective_from=effective_date,
            is_darshak=is_darshak_namespace,
            source_event_type="TRANSFER" if request_type == "TRANSFER" else "ENROLLMENT",
        )
        cur.execute(
            "SELECT local_sakha_erp_id FROM nss.membership_sakha_affiliation WHERE membership_sakha_affiliation_pk = %s",
            (new_aff_pk,),
        )
        new_local_sakha_erp_id = cur.fetchone()[0]

        log_audit(
            cur, action="CREATE", table_name="membership_sakha_affiliation", record_pk=str(new_aff_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="membership_change_request",
            summary=f"Opened {request_type.lower()} affiliation at destination Sakha",
        )

        if request_type == "TRANSFER":
            # Close the old (home) affiliation — MBR-048. Darshak (MBR-049)
            # deliberately does NOT reach this branch: the home affiliation
            # stays open, which is the entire point of the two coexisting.
            cur.execute(
                """
                SELECT membership_sakha_affiliation_pk, local_sakha_erp_id
                FROM nss.membership_sakha_affiliation
                WHERE sangha_sevi_pk = %s AND organization_pk = %s AND effective_to IS NULL
                """,
                (str(sangha_sevi_pk), str(old_org_pk)),
            )
            old_aff_row = cur.fetchone()
            old_local_sakha_erp_id = old_aff_row[1] if old_aff_row else None
            if old_aff_row:
                close_sakha_affiliation(
                    cur, membership_sakha_affiliation_pk=str(old_aff_row[0]), effective_to=effective_date,
                )
                log_audit(
                    cur, action="UPDATE", table_name="membership_sakha_affiliation",
                    record_pk=str(old_aff_row[0]), actor_pk=user.actor_pk,
                    actor_user_account_pk=str(user.user_account_pk),
                    module="membership_change_request",
                    summary="Closed old-Sakha affiliation on transfer",
                )

            cur.execute(
                """
                INSERT INTO nss.membership_transfer_history (
                    sangha_sevi_pk, old_organization_pk, new_organization_pk,
                    transfer_type, transfer_reason, requested_date, approved_date,
                    effective_date, old_local_sakha_erp_id, new_local_sakha_erp_id,
                    approved_by_sangha_sevi_pk, remarks
                ) VALUES (%s, %s, %s, 'SAKHA_TRANSFER', NULL, NULL, CURRENT_DATE,
                          %s, %s, %s, %s, %s)
                RETURNING membership_transfer_history_pk
                """,
                (
                    str(sangha_sevi_pk), str(old_org_pk), str(new_org_pk),
                    effective_date, old_local_sakha_erp_id, new_local_sakha_erp_id,
                    user.actor_pk, body.remarks,
                ),
            )
            transfer_history_pk = cur.fetchone()[0]
            log_audit(
                cur, action="CREATE", table_name="membership_transfer_history",
                record_pk=str(transfer_history_pk), actor_pk=user.actor_pk,
                actor_user_account_pk=str(user.user_account_pk),
                module="membership_change_request",
                summary="Recorded Sakha transfer history",
            )

            # The member's HOME Sakha moves with the transfer: attendance,
            # correspondence and the directory all resolve "home" through
            # sangha_sevi.organization_pk, so leaving it on the old Sakha
            # would strand the member there. (DARSHAK deliberately skips
            # this — the home Sakha stays.)
            cur.execute(
                """
                UPDATE nss.sangha_sevi
                SET organization_pk = %s, updated_at = NOW(), updated_by_sangha_sevi_pk = %s
                WHERE sangha_sevi_pk = %s
                """,
                (str(new_org_pk), user.actor_pk, str(sangha_sevi_pk)),
            )
            log_audit(
                cur, action="UPDATE", table_name="sangha_sevi", record_pk=str(sangha_sevi_pk),
                actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
                module="membership_change_request",
                summary="Moved member's home Sakha on transfer",
            )

            journey_event_type = "TRANSFER"
        else:
            journey_event_type = _DARSHAK_JOURNEY_EVENT_TYPE

        cur.execute(
            """
            INSERT INTO nss.membership_journey_event (
                sangha_sevi_pk, event_type, event_date, event_reference,
                remarks, created_by_sangha_sevi_pk
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING membership_journey_event_pk
            """,
            (
                str(sangha_sevi_pk), journey_event_type, effective_date,
                str(change_request_pk), body.remarks, user.actor_pk,
            ),
        )
        journey_event_pk = cur.fetchone()[0]
        log_audit(
            cur, action="CREATE", table_name="membership_journey_event",
            record_pk=str(journey_event_pk), actor_pk=user.actor_pk,
            actor_user_account_pk=str(user.user_account_pk),
            module="membership_change_request",
            summary=f"Recorded {journey_event_type} journey event",
        )

        cur.execute(
            """
            UPDATE nss.membership_change_request
            SET status = 'COMPLETED',
                destination_decided_by_sangha_sevi_pk = %s,
                destination_decided_at = NOW(),
                destination_remarks = %s,
                new_local_number = %s,
                effective_date = %s
            WHERE membership_change_request_pk = %s
            """,
            (user.actor_pk, body.remarks, new_local_sakha_erp_id, effective_date, str(change_request_pk)),
        )
        log_audit(
            cur, action="APPROVE", table_name="membership_change_request",
            record_pk=str(change_request_pk), actor_pk=user.actor_pk,
            actor_user_account_pk=str(user.user_account_pk),
            module="membership_change_request",
            summary=f"Destination Sakha accepted {request_type} change request",
        )

        cur.execute(_DETAIL_SELECT + " WHERE mcr.membership_change_request_pk = %s", (str(change_request_pk),))
        result_row = cur.fetchone()

    return _row_to_response(result_row)
