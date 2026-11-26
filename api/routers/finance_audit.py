"""
NSS ERP — Finance: the Kendra's annual audit (Bye-Law Section G, REF-003-G).

``/api/v1/finance`` (8 endpoints). The rules live in ``api/services/finance_audit.py`` (one place); this router checks permission +
admin scope, calls them and audits every change.

  GET    /audits                            list (filters: financial_year_pk, organization_pk, status)         FINANCE_VIEW + scope
  POST   /audits                            record the Governing Body's appointment of the Auditor (starts it)  FINANCE_MANAGE + scope
  GET    /audits/{pk}                       the audit, its next step and the clause-17 note                    FINANCE_VIEW + scope
  POST   /audits/{pk}/report                record the Audit Report (reference, date, optional https link)     FINANCE_MANAGE + scope
  POST   /audits/{pk}/governing-body        place the report before the Governing Body (files a numbered letter to the Advisory Board)
  POST   /audits/{pk}/approval              record the combined meeting's approval (Governing Body + Advisory Board)
  POST   /audits/{pk}/general-body          record the Secretary placing it before the General Body (final)
  POST   /audits/{pk}/correct               correct recorded text, with a reason                               FINANCE_MANAGE + scope

The Kendra only (no rule is invented for other levels, FIN-BR-044). The financial year's status gates nothing (owner 2026-11-26). No seat check on
a step itself - the recorded facts (date + reference) are the evidence and every write is audited - but who can reach it is the Kendra finance
roles, the same as the annual budget. Everything written is audited.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.routers import correspondence as C
from api.routers import finance as F
from api.routers.finance_budget import _LETTER_MEDIUM
from api.schemas import finance as S
from api.schemas.correspondence import CorrespondenceCreate
from api.services import finance_audit as A
from api.services import finance_budget as B
from api.services.rbac_service import UserContext

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE = F._VIEW, F._MANAGE


def _locked(cur, user: UserContext, audit_pk, action: str) -> dict:
    """The audit row (locked), after the caller's admin scope on the Kendra is checked."""
    audit = A.load(cur, audit_pk, lock=True)
    F._require_org_access(cur, user, audit["organization_pk"], action)
    return audit


@router.get("/audits", response_model=S.AuditListResponse)
def list_audits(
    financial_year_pk: UUID | None = Query(None),
    organization_pk: UUID | None = Query(None),
    status_code: str | None = Query(None, alias="status"),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    if status_code is not None and status_code not in S.AUDIT_STATUSES:
        raise F._invalid(f"status must be one of {', '.join(S.AUDIT_STATUSES)}.")
    with conn.cursor() as cur:
        visible, params = F._visible(cur, user, "a.organization_pk")
        where = ["a.is_active = TRUE", visible]
        for column, value in (("a.financial_year_pk", financial_year_pk), ("a.organization_pk", organization_pk), ("a.status", status_code)):
            if value is not None:
                where.append(f"{column} = %s")
                params.append(str(value))
        items = A.list_rows(cur, " AND ".join(where), params)
    return {"items": items, "total": len(items)}


@router.post("/audits", response_model=S.AuditDetailResponse, status_code=status.HTTP_201_CREATED)
def create_audit(body: S.AuditCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        org_pk = body.organization_pk or B.kendra_organization_pk(cur)
        if org_pk is None:
            raise F._invalid("There is no active Kendra organization to hold an audit.")
        A.require_kendra(cur, org_pk)
        F._require_org_access(cur, user, org_pk, "start the audit of the Kendra's accounts")
        pk = A.create(cur, user.actor_pk, year_pk=body.financial_year_pk, organization_pk=org_pk, auditor_name=body.auditor_name,
                      auditor_firm=body.auditor_firm, appointed_on=body.appointed_on, appointment_reference=body.appointment_reference,
                      notes=F._clean(body.notes))
        F._audit(cur, user, "CREATE", "finance_year_audit", pk, "The Governing Body appointed the Auditor",
                 {"financial_year_pk": str(body.financial_year_pk), "organization_pk": str(org_pk), "auditor_name": body.auditor_name.strip(),
                  "auditor_firm": F._clean(body.auditor_firm), "appointed_on": str(body.appointed_on), "appointment_reference": body.appointment_reference.strip()})
        return A.detail(cur, pk)


@router.get("/audits/{audit_pk}", response_model=S.AuditDetailResponse)
def get_audit(audit_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        audit = A.load(cur, audit_pk)
        F._require_org_access(cur, user, audit["organization_pk"], "see this audit")
        return A.detail(cur, audit_pk)


@router.post("/audits/{audit_pk}/report", response_model=S.AuditDetailResponse)
def record_report(audit_pk: UUID, body: S.AuditReportWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        audit = _locked(cur, user, audit_pk, "record the Audit Report")
        A.record_report(cur, user.actor_pk, audit, reference=body.report_reference, report_date=body.report_date, link=body.report_link)
        F._audit(cur, user, "UPDATE", "finance_year_audit", audit_pk, "Recorded the Audit Report",
                 {"report_reference": body.report_reference.strip(), "report_date": str(body.report_date), "from": audit["status"], "to": A.REPORT_RECEIVED})
        return A.detail(cur, audit_pk)


@router.post("/audits/{audit_pk}/governing-body", response_model=S.AuditDetailResponse)
def place_before_governing_body(audit_pk: UUID, body: S.AuditGoverningBodyWrite, user: UserContext = Depends(_MANAGE),
                                conn=Depends(get_write_connection)):
    """Place the report before the Governing Body: a numbered letter Kendra -> Advisory Board is filed in Correspondence automatically, so the Board has the report for the combined meeting."""
    with conn.cursor() as cur:
        audit = _locked(cur, user, audit_pk, "place the Audit Report before the Governing Body")
        placed_on = body.gb_placed_on or date.today()
        reference = A.validate_gb(audit, placed_on=placed_on, reference=body.gb_reference)       # refuse BEFORE anything is filed
        letter = C.register_correspondence(
            cur, user,
            CorrespondenceCreate(
                register_organization_pk=audit["organization_pk"], direction="OUTWARD", correspondence_date=placed_on, received_or_sent_date=placed_on,
                subject=A.advisory_letter_subject(audit["year_code"]), remarks=A.advisory_letter_remarks(audit, audit["report_reference"], reference),
                sender_type="ORGANIZATION", sender_organization_pk=audit["organization_pk"],
                recipient_type="ORGANIZATION", recipient_organization_pk=B.advisory_board_organization_pk(cur), medium=_LETTER_MEDIUM,
            ),
            check_scope=False,
        )
        A.place_before_gb(cur, user.actor_pk, audit, placed_on=placed_on, reference=reference, letter_pk=letter["correspondence_pk"])
        F._audit(cur, user, "UPDATE", "finance_year_audit", audit_pk, "Placed the Audit Report before the Governing Body",
                 {"gb_placed_on": str(placed_on), "gb_reference": reference, "from": audit["status"], "to": A.PLACED_BEFORE_GB,
                  "letter": letter["reference_number"], "advisory_board_copy": letter["inward_reference_number"]})
        return A.detail(cur, audit_pk)


@router.post("/audits/{audit_pk}/approval", response_model=S.AuditDetailResponse)
def record_approval(audit_pk: UUID, body: S.AuditApprovalWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        audit = _locked(cur, user, audit_pk, "record the approval of the Audit Report")
        A.approve(cur, user.actor_pk, audit, approved_on=body.approved_on, reference=body.approval_reference)
        F._audit(cur, user, "APPROVE", "finance_year_audit", audit_pk, "The combined meeting of the Governing Body and the Advisory Board approved the Audit Report",
                 {"approved_on": str(body.approved_on), "approval_reference": body.approval_reference.strip(), "from": audit["status"], "to": A.APPROVED})
        return A.detail(cur, audit_pk)


@router.post("/audits/{audit_pk}/general-body", response_model=S.AuditDetailResponse)
def place_before_general_body(audit_pk: UUID, body: S.AuditGeneralBodyWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        audit = _locked(cur, user, audit_pk, "place the Audit Report before the General Body")
        A.place_before_general_body(cur, user.actor_pk, audit, placed_on=body.general_body_on, reference=body.general_body_reference)
        F._audit(cur, user, "UPDATE", "finance_year_audit", audit_pk, "The Secretary placed the Audit Report before the General Body",
                 {"general_body_on": str(body.general_body_on), "general_body_reference": body.general_body_reference.strip(),
                  "from": audit["status"], "to": A.PLACED_BEFORE_GENERAL_BODY})
        return A.detail(cur, audit_pk)


@router.post("/audits/{audit_pk}/correct", response_model=S.AuditDetailResponse)
def correct_audit(audit_pk: UUID, body: S.AuditCorrectWrite, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Correct recorded text with a reason. The status does not move; the audit event keeps the old and new text and the reason."""
    with conn.cursor() as cur:
        audit = _locked(cur, user, audit_pk, "correct this audit")
        changes = {col: getattr(body, col) for col in A.CORRECTABLE}
        done = A.correct(cur, user.actor_pk, audit, changes, body.reason)
        F._audit(cur, user, "UPDATE", "finance_year_audit", audit_pk, "Corrected what was recorded on the Kendra audit",
                 {"reason": done["reason"], "status": audit["status"], "changed": {col: {"from": old, "to": new} for col, (old, new) in done["changed"].items()}})
        return A.detail(cur, audit_pk)
