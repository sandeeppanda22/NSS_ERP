"""
NSS ERP — Correspondence Register router (Tier 6, SOL-ADMIN-009).

Inward/outward correspondence filed under an organization's register, plus
its document and finance-reference sub-resources.

  POST /api/v1/correspondence                               — register
  GET  /api/v1/correspondence                                — list (scoped)
  GET  /api/v1/correspondence/{pk}                            — detail
  POST /api/v1/correspondence/{pk}/transition                 — status transition
  POST /api/v1/correspondence/{pk}/responsible-party           — assign/clear
  POST /api/v1/correspondence/{pk}/documents                   — associate a document
  GET  /api/v1/correspondence/{pk}/documents                   — list associated documents
  POST /api/v1/correspondence/{pk}/finance-references           — reference a finance transaction
  GET  /api/v1/correspondence/{pk}/finance-references           — list finance references

Permissions: CORRESPONDENCE_VIEW (read), CORRESPONDENCE_MANAGE (write) —
bounded by admin scope on register_organization_pk (every org-scoped admin
role manages its own register; mirrors PERSON_MANAGE/MEMBERSHIP_MANAGE's
footprint, not GOVERNANCE_MANAGE's ADMIN/KENDRA-only one).

Authority: SOL-ADMIN-009, business rules
docs/03_Solution/modules/administration/08_correspondence_register_business_rules.md.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.rbac import require_any_permission, require_permission
from api.helpers import get_master_data_pk, log_audit, next_correspondence_reference_number
from api.schemas.correspondence import (
    CorrespondenceCreate,
    CorrespondenceListResponse,
    CorrespondenceResponse,
    DocumentAssociationCreate,
    DocumentAssociationListResponse,
    DocumentAssociationResponse,
    FinanceReferenceCreate,
    FinanceReferenceListResponse,
    FinanceReferenceResponse,
    ResponsiblePartyAssignRequest,
    StatusTransitionRequest,
)
from api.services.rbac_service import UserContext, actor_scope_org_pks, require_org_in_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/correspondence", tags=["correspondence"])

# §6.2 transition precondition table — the only transitions permitted.
# Preconditions beyond "record exists" are enforced in-line in transition()
# below (responsible-party populated for REGISTERED -> PENDING_ACTION;
# non-empty remarks for the two reopen transitions).
_VALID_TRANSITIONS = {
    ("REGISTERED", "PENDING_ACTION"),
    ("REGISTERED", "ACTIONED"),
    ("REGISTERED", "CLOSED"),
    ("PENDING_ACTION", "ACTIONED"),
    ("ACTIONED", "CLOSED"),
    ("ACTIONED", "PENDING_ACTION"),
    ("CLOSED", "PENDING_ACTION"),
}
_REOPEN_TRANSITIONS = {("ACTIONED", "PENDING_ACTION"), ("CLOSED", "PENDING_ACTION")}


_DETAIL_SELECT = """
    SELECT c.correspondence_pk,
           c.register_organization_pk,
           rorg.organization_name,
           c.reference_number,
           c.direction,
           c.correspondence_date,
           c.received_or_sent_date,
           c.follow_up_date,
           c.subject,
           c.remarks,
           c.sender_type,
           c.sender_person_pk,
           CONCAT_WS(' ', sp.first_name, sp.middle_name, sp.last_name),
           c.sender_organization_pk,
           sorg.organization_name,
           c.sender_external_name,
           c.sender_external_organization,
           c.sender_person_capacity,
           c.sender_person_organization_pk,
           c.sender_sakha_erp_id_snapshot,
           c.recipient_type,
           c.recipient_person_pk,
           CONCAT_WS(' ', rp.first_name, rp.middle_name, rp.last_name),
           c.recipient_organization_pk,
           recorg.organization_name,
           c.recipient_external_name,
           c.recipient_external_organization,
           c.responsible_person_pk,
           c.responsible_organization_pk,
           c.medium_master_data_pk,
           medium_md.value_code,
           c.status_master_data_pk,
           status_md.value_code,
           c.created_at,
           c.is_active
    FROM nss.correspondence c
    JOIN nss.organization rorg ON rorg.organization_pk = c.register_organization_pk
    LEFT JOIN nss.person sp ON sp.person_pk = c.sender_person_pk
    LEFT JOIN nss.organization sorg ON sorg.organization_pk = c.sender_organization_pk
    LEFT JOIN nss.person rp ON rp.person_pk = c.recipient_person_pk
    LEFT JOIN nss.organization recorg ON recorg.organization_pk = c.recipient_organization_pk
    JOIN nss.master_data medium_md ON medium_md.master_data_pk = c.medium_master_data_pk
    JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
"""


def _row_to_response(r) -> CorrespondenceResponse:
    return CorrespondenceResponse(
        correspondence_pk=r[0],
        register_organization_pk=r[1],
        register_organization_name=r[2],
        reference_number=r[3],
        direction=r[4],
        correspondence_date=r[5],
        received_or_sent_date=r[6],
        follow_up_date=r[7],
        subject=r[8],
        remarks=r[9],
        sender_type=r[10],
        sender_person_pk=r[11],
        sender_person_name=r[12] or None,
        sender_organization_pk=r[13],
        sender_organization_name=r[14],
        sender_external_name=r[15],
        sender_external_organization=r[16],
        sender_person_capacity=r[17],
        sender_person_organization_pk=r[18],
        sender_sakha_erp_id_snapshot=r[19],
        recipient_type=r[20],
        recipient_person_pk=r[21],
        recipient_person_name=r[22] or None,
        recipient_organization_pk=r[23],
        recipient_organization_name=r[24],
        recipient_external_name=r[25],
        recipient_external_organization=r[26],
        responsible_person_pk=r[27],
        responsible_organization_pk=r[28],
        medium_master_data_pk=r[29],
        medium_value_code=r[30],
        status_master_data_pk=r[31],
        status_value_code=r[32],
        created_at=r[33],
        is_active=r[34],
    )


def _fetch_sender_sakha_snapshot(cur, sender_type: str, sender_person_pk) -> str | None:
    """
    Point-in-time snapshot of the sender's active Local Sakha ID, if any
    (nss.correspondence.sender_sakha_erp_id_snapshot — see 01_correspondence.sql).
    Only applies to sender_type = PERSON.
    """
    if sender_type != "PERSON" or not sender_person_pk:
        return None
    cur.execute(
        """
        SELECT msa.local_sakha_erp_id
        FROM nss.sangha_sevi ss
        JOIN nss.membership_sakha_affiliation msa ON msa.sangha_sevi_pk = ss.sangha_sevi_pk
        WHERE ss.person_pk = %s AND ss.is_active = TRUE AND msa.effective_to IS NULL
        ORDER BY msa.effective_from DESC
        LIMIT 1
        """,
        (str(sender_person_pk),),
    )
    row = cur.fetchone()
    return row[0] if row else None


# ── POST /api/v1/correspondence ─────────────────────────────────────────

@router.post("", response_model=CorrespondenceResponse, status_code=status.HTTP_201_CREATED)
def create_correspondence(
    body: CorrespondenceCreate,
    user: UserContext = Depends(require_permission("CORRESPONDENCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> CorrespondenceResponse:
    """
    Register a new correspondence entry under register_organization_pk's
    register. New records always start at status REGISTERED (§6.1) — the
    caller cannot set an initial status; use the transition endpoint
    afterwards.
    """
    with conn.cursor() as cur:
        require_org_in_scope(cur, user, str(body.register_organization_pk), "register correspondence for this organization")

        reference_number = next_correspondence_reference_number(
            cur, str(body.register_organization_pk), body.direction,
        )
        medium_pk = get_master_data_pk(cur, "CORRESPONDENCE_MEDIUM", body.medium)
        status_pk = get_master_data_pk(cur, "CORRESPONDENCE_STATUS", "REGISTERED")
        sender_snapshot = _fetch_sender_sakha_snapshot(cur, body.sender_type, body.sender_person_pk)

        cur.execute(
            """
            INSERT INTO nss.correspondence (
                register_organization_pk, reference_number, direction,
                correspondence_date, received_or_sent_date, follow_up_date,
                subject, remarks,
                sender_type, sender_person_pk, sender_organization_pk,
                sender_external_name, sender_external_organization,
                sender_person_capacity, sender_person_organization_pk,
                sender_sakha_erp_id_snapshot,
                recipient_type, recipient_person_pk, recipient_organization_pk,
                recipient_external_name, recipient_external_organization,
                responsible_person_pk, responsible_organization_pk,
                medium_master_data_pk, status_master_data_pk,
                created_by_sangha_sevi_pk
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s
            )
            RETURNING correspondence_pk
            """,
            (
                str(body.register_organization_pk), reference_number, body.direction,
                body.correspondence_date, body.received_or_sent_date, body.follow_up_date,
                body.subject, body.remarks,
                body.sender_type,
                str(body.sender_person_pk) if body.sender_person_pk else None,
                str(body.sender_organization_pk) if body.sender_organization_pk else None,
                body.sender_external_name, body.sender_external_organization,
                body.sender_person_capacity,
                str(body.sender_person_organization_pk) if body.sender_person_organization_pk else None,
                sender_snapshot,
                body.recipient_type,
                str(body.recipient_person_pk) if body.recipient_person_pk else None,
                str(body.recipient_organization_pk) if body.recipient_organization_pk else None,
                body.recipient_external_name, body.recipient_external_organization,
                str(body.responsible_person_pk) if body.responsible_person_pk else None,
                str(body.responsible_organization_pk) if body.responsible_organization_pk else None,
                medium_pk, status_pk,
                user.actor_pk,
            ),
        )
        corr_pk = cur.fetchone()[0]

        log_audit(
            cur, action="CREATE", table_name="correspondence", record_pk=str(corr_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary=f"Registered {body.direction.lower()} correspondence {reference_number}",
        )

        cur.execute(_DETAIL_SELECT + " WHERE c.correspondence_pk = %s", (str(corr_pk),))
        row = cur.fetchone()

    return _row_to_response(row)


# ── GET /api/v1/correspondence ──────────────────────────────────────────

@router.get("", response_model=CorrespondenceListResponse)
def list_correspondence(
    register_organization_pk: UUID | None = Query(None),
    direction: str | None = Query(None, pattern="^(INWARD|OUTWARD)$"),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(require_any_permission("CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE")),
    conn=Depends(get_connection),
) -> CorrespondenceListResponse:
    """List correspondence, scoped to the caller's admin-scope register(s) (register_organization_pk)."""
    offset = (page - 1) * page_size
    filters = []
    params: list = []

    with conn.cursor() as cur:
        if not user.is_nss_wide() and not user.is_super_admin():
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None:
                if not allowed:
                    return CorrespondenceListResponse(items=[], total=0)
                placeholders = ",".join(["%s"] * len(allowed))
                filters.append(f"c.register_organization_pk IN ({placeholders})")
                params.extend(list(allowed))

        if register_organization_pk:
            filters.append("c.register_organization_pk = %s")
            params.append(str(register_organization_pk))
        if direction:
            filters.append("c.direction = %s")
            params.append(direction)
        if status_filter:
            filters.append("status_md.value_code = %s")
            params.append(status_filter)
        filters.append("c.is_active = TRUE")

        where_clause = f"WHERE {' AND '.join(filters)}"

        cur.execute(
            f"""
            SELECT COUNT(*) FROM nss.correspondence c
            JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
            {where_clause}
            """,
            params,
        )
        total = cur.fetchone()[0]

        cur.execute(
            _DETAIL_SELECT + f" {where_clause} ORDER BY c.correspondence_date DESC, c.created_at DESC LIMIT %s OFFSET %s",
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    return CorrespondenceListResponse(items=[_row_to_response(r) for r in rows], total=total)


# ── GET /api/v1/correspondence/{pk} ─────────────────────────────────────

@router.get("/{correspondence_pk}", response_model=CorrespondenceResponse)
def get_correspondence(
    correspondence_pk: UUID,
    user: UserContext = Depends(require_any_permission("CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE")),
    conn=Depends(get_connection),
) -> CorrespondenceResponse:
    with conn.cursor() as cur:
        cur.execute(_DETAIL_SELECT + " WHERE c.correspondence_pk = %s", (str(correspondence_pk),))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")

        if not user.is_nss_wide() and not user.is_super_admin():
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None and str(row[1]) not in allowed:
                raise HTTPException(status_code=403, detail="This correspondence record is outside your admin scope.")

    return _row_to_response(row)


# ── POST /api/v1/correspondence/{pk}/transition ─────────────────────────

@router.post("/{correspondence_pk}/transition", response_model=CorrespondenceResponse)
def transition_status(
    correspondence_pk: UUID,
    body: StatusTransitionRequest,
    user: UserContext = Depends(require_permission("CORRESPONDENCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> CorrespondenceResponse:
    """
    Move a correspondence record to a new status, per the §6.2 precondition
    table. §6.4: the transition is always timestamped with the current
    system time — there is no backdating parameter on this endpoint.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT register_organization_pk, status_md.value_code,
                   responsible_person_pk, responsible_organization_pk
            FROM nss.correspondence c
            JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
            WHERE c.correspondence_pk = %s
            """,
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")
        register_org_pk, current_status, responsible_person_pk, responsible_org_pk = row

        require_org_in_scope(cur, user, register_org_pk, "transition this correspondence record")

        if current_status == body.new_status:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"This record is already {current_status}.",
            )
        if (current_status, body.new_status) not in _VALID_TRANSITIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{current_status} -> {body.new_status} is not a valid transition.",
            )

        if current_status == "REGISTERED" and body.new_status == "PENDING_ACTION":
            if not responsible_person_pk and not responsible_org_pk:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Assign a responsible person or organization before moving to PENDING_ACTION.",
                )

        if (current_status, body.new_status) in _REOPEN_TRANSITIONS and not (body.remarks and body.remarks.strip()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Reopening requires remarks explaining why.",
            )

        new_status_pk = get_master_data_pk(cur, "CORRESPONDENCE_STATUS", body.new_status)
        cur.execute(
            """
            UPDATE nss.correspondence
            SET status_master_data_pk = %s,
                remarks = COALESCE(%s, remarks),
                updated_at = NOW(),
                updated_by_sangha_sevi_pk = %s
            WHERE correspondence_pk = %s
            """,
            (new_status_pk, body.remarks, user.actor_pk, str(correspondence_pk)),
        )
        log_audit(
            cur, action="UPDATE", table_name="correspondence", record_pk=str(correspondence_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary=f"Transitioned {current_status} -> {body.new_status}",
            detail={"remarks": body.remarks} if body.remarks else None,
        )

        cur.execute(_DETAIL_SELECT + " WHERE c.correspondence_pk = %s", (str(correspondence_pk),))
        result_row = cur.fetchone()

    return _row_to_response(result_row)


# ── POST /api/v1/correspondence/{pk}/responsible-party ──────────────────

@router.post("/{correspondence_pk}/responsible-party", response_model=CorrespondenceResponse)
def assign_responsible_party(
    correspondence_pk: UUID,
    body: ResponsiblePartyAssignRequest,
    user: UserContext = Depends(require_permission("CORRESPONDENCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> CorrespondenceResponse:
    """
    Reassign (or clear) who is responsible for acting on this correspondence
    (§5.4) — permitted at any state and does not itself trigger a status
    transition.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s",
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")

        require_org_in_scope(cur, user, row[0], "reassign responsibility for this correspondence record")

        cur.execute(
            """
            UPDATE nss.correspondence
            SET responsible_person_pk = %s,
                responsible_organization_pk = %s,
                updated_at = NOW(),
                updated_by_sangha_sevi_pk = %s
            WHERE correspondence_pk = %s
            """,
            (
                str(body.responsible_person_pk) if body.responsible_person_pk else None,
                str(body.responsible_organization_pk) if body.responsible_organization_pk else None,
                user.actor_pk,
                str(correspondence_pk),
            ),
        )
        log_audit(
            cur, action="UPDATE", table_name="correspondence", record_pk=str(correspondence_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary="Reassigned responsible party",
        )

        cur.execute(_DETAIL_SELECT + " WHERE c.correspondence_pk = %s", (str(correspondence_pk),))
        result_row = cur.fetchone()

    return _row_to_response(result_row)


# ── Document association sub-resource ───────────────────────────────────

@router.post(
    "/{correspondence_pk}/documents",
    response_model=DocumentAssociationResponse,
    status_code=status.HTTP_201_CREATED,
)
def associate_document(
    correspondence_pk: UUID,
    body: DocumentAssociationCreate,
    user: UserContext = Depends(require_permission("CORRESPONDENCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> DocumentAssociationResponse:
    """
    Associate a document_master row with this correspondence under a given
    purpose (§8). Documents may be attached at any state, including CLOSED,
    with no state-transition side effect.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s",
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")
        require_org_in_scope(cur, user, row[0], "attach a document to this correspondence record")

        cur.execute(
            """
            INSERT INTO nss.correspondence_document (
                correspondence_pk, document_master_pk, document_purpose, remarks,
                created_by_sangha_sevi_pk
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING correspondence_document_pk, correspondence_pk, document_master_pk,
                      document_purpose, remarks, created_at
            """,
            (str(correspondence_pk), str(body.document_master_pk), body.document_purpose, body.remarks, user.actor_pk),
        )
        result = cur.fetchone()

        log_audit(
            cur, action="CREATE", table_name="correspondence_document", record_pk=str(result[0]),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary=f"Associated document ({body.document_purpose})",
        )

    return DocumentAssociationResponse(
        correspondence_document_pk=result[0], correspondence_pk=result[1],
        document_master_pk=result[2], document_purpose=result[3],
        remarks=result[4], created_at=result[5],
    )


@router.get("/{correspondence_pk}/documents", response_model=DocumentAssociationListResponse)
def list_documents(
    correspondence_pk: UUID,
    user: UserContext = Depends(require_any_permission("CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE")),
    conn=Depends(get_connection),
) -> DocumentAssociationListResponse:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s",
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")

        if not user.is_nss_wide() and not user.is_super_admin():
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None and str(row[0]) not in allowed:
                raise HTTPException(status_code=403, detail="This correspondence record is outside your admin scope.")

        cur.execute(
            """
            SELECT correspondence_document_pk, correspondence_pk, document_master_pk,
                   document_purpose, remarks, created_at
            FROM nss.correspondence_document
            WHERE correspondence_pk = %s AND is_active = TRUE
            ORDER BY created_at DESC
            """,
            (str(correspondence_pk),),
        )
        rows = cur.fetchall()

    items = [
        DocumentAssociationResponse(
            correspondence_document_pk=r[0], correspondence_pk=r[1], document_master_pk=r[2],
            document_purpose=r[3], remarks=r[4], created_at=r[5],
        )
        for r in rows
    ]
    return DocumentAssociationListResponse(items=items, total=len(items))


# ── Finance reference sub-resource ──────────────────────────────────────

@router.post(
    "/{correspondence_pk}/finance-references",
    response_model=FinanceReferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def associate_finance_reference(
    correspondence_pk: UUID,
    body: FinanceReferenceCreate,
    user: UserContext = Depends(require_permission("CORRESPONDENCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> FinanceReferenceResponse:
    """
    Reference a Finance transaction from this correspondence (§9). §9.3:
    Administration does not create Finance transactions here — the
    financial_transaction_pk must already exist. Since
    nss.financial_transaction does not exist yet (Finance is Tier 12), that
    existence check cannot be enforced at the DB (no FK, see
    03_correspondence_finance_reference.sql Pass 2 note) or application
    layer yet — accepted as a documented, temporary gap. §9.5: the
    reference persists even if the transaction is later reversed/voided.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s",
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")
        require_org_in_scope(cur, user, row[0], "reference a finance transaction from this correspondence record")

        relationship_pk = get_master_data_pk(
            cur, "CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE", body.relationship_type,
        )

        cur.execute(
            """
            INSERT INTO nss.correspondence_finance_reference (
                correspondence_pk, financial_transaction_pk,
                relationship_type_master_data_pk, remarks,
                created_by_sangha_sevi_pk
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING correspondence_finance_reference_pk, correspondence_pk,
                      financial_transaction_pk, relationship_type_master_data_pk,
                      remarks, created_at
            """,
            (
                str(correspondence_pk), str(body.financial_transaction_pk),
                relationship_pk, body.remarks, user.actor_pk,
            ),
        )
        result = cur.fetchone()

        log_audit(
            cur, action="CREATE", table_name="correspondence_finance_reference", record_pk=str(result[0]),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary=f"Referenced finance transaction ({body.relationship_type})",
        )

    return FinanceReferenceResponse(
        correspondence_finance_reference_pk=result[0], correspondence_pk=result[1],
        financial_transaction_pk=result[2], relationship_type_master_data_pk=result[3],
        relationship_type_value_code=body.relationship_type,
        remarks=result[4], created_at=result[5],
    )


@router.get("/{correspondence_pk}/finance-references", response_model=FinanceReferenceListResponse)
def list_finance_references(
    correspondence_pk: UUID,
    user: UserContext = Depends(require_any_permission("CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE")),
    conn=Depends(get_connection),
) -> FinanceReferenceListResponse:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s",
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")

        if not user.is_nss_wide() and not user.is_super_admin():
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None and str(row[0]) not in allowed:
                raise HTTPException(status_code=403, detail="This correspondence record is outside your admin scope.")

        cur.execute(
            """
            SELECT cfr.correspondence_finance_reference_pk, cfr.correspondence_pk,
                   cfr.financial_transaction_pk, cfr.relationship_type_master_data_pk,
                   md.value_code, cfr.remarks, cfr.created_at
            FROM nss.correspondence_finance_reference cfr
            JOIN nss.master_data md ON md.master_data_pk = cfr.relationship_type_master_data_pk
            WHERE cfr.correspondence_pk = %s AND cfr.is_active = TRUE
            ORDER BY cfr.created_at DESC
            """,
            (str(correspondence_pk),),
        )
        rows = cur.fetchall()

    items = [
        FinanceReferenceResponse(
            correspondence_finance_reference_pk=r[0], correspondence_pk=r[1],
            financial_transaction_pk=r[2], relationship_type_master_data_pk=r[3],
            relationship_type_value_code=r[4], remarks=r[5], created_at=r[6],
        )
        for r in rows
    ]
    return FinanceReferenceListResponse(items=items, total=len(items))
