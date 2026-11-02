"""
NSS ERP — Correspondence Register router (Tier 6, SOL-ADMIN-009).

Inward/outward correspondence filed under an organization's register, plus
its document and finance-reference sub-resources.

  POST /api/v1/correspondence                               — register
  GET  /api/v1/correspondence                                — list (scoped)
  GET  /api/v1/correspondence/{pk}                            — detail
  GET  /api/v1/correspondence/{pk}/history                     — activity log + reply-thread path tracker
  POST /api/v1/correspondence/{pk}/dispatch                    — mint the recipient org's own INWARD counterpart row
  POST /api/v1/correspondence/{pk}/transition                 — status transition
  POST /api/v1/correspondence/{pk}/responsible-party           — assign/clear
  POST /api/v1/correspondence/{pk}/documents                   — associate a document
  GET  /api/v1/correspondence/{pk}/documents                   — list associated documents
  POST /api/v1/correspondence/{pk}/finance-references           — reference a finance transaction
  GET  /api/v1/correspondence/{pk}/finance-references           — list finance references

  POST /api/v1/correspondence/my-applications                   — member "Send Application"
  GET  /api/v1/correspondence/my-applications                   — the caller's own sent applications
  GET  /api/v1/correspondence/my-applications/{pk}               — one of the caller's own applications
  GET  /api/v1/correspondence/addressed-to-me                    — applications currently addressed to the caller
  GET  /api/v1/correspondence/approval-steps/pending-for-me       — approval-chain steps awaiting the caller's decision
  POST /api/v1/correspondence/approval-steps/{pk}/decision        — decide a pending approval-chain step
  GET  /api/v1/correspondence/my-involvements                    — every correspondence the caller is attached to, any role

Permissions: CORRESPONDENCE_VIEW (read, unchanged); CORRESPONDENCE_MANAGE +
admin scope on register_organization_pk governs register/create and the
document/finance-reference sub-resources (mirrors PERSON_MANAGE/
MEMBERSHIP_MANAGE's footprint, not GOVERNANCE_MANAGE's ADMIN/KENDRA-only
one).

/transition and /responsible-party are the exception (owner-confirmed
2026-10-22): a correspondence's status/responsible-party may only be
changed by the authority it is actually DIRECTED AT — the current
responsible_person_pk, the recipient_person_pk (recipient_type=PERSON), or
a currently-seated office-bearer of the recipient organization
(recipient_type=ORGANIZATION) — see _require_directed_authority() below.
CORRESPONDENCE_MANAGE/admin-scope alone no longer suffices there, not even
for NSS_ERP_ADMIN/KENDRA_ADMIN; it only remains the fallback authority for
the one row shape with no directed human authority at all
(recipient_type=EXTERNAL, or an ORGANIZATION recipient of a type this app
has no governing-body model for) — otherwise such a record could never be
acted on by anyone.

Authority: SOL-ADMIN-009, business rules
docs/03_Solution/modules/administration/08_correspondence_register_business_rules.md.
"""

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_current_user, get_write_connection
from api.dependencies.rbac import require_any_permission, require_permission
from api.helpers import get_master_data_pk, log_audit, next_correspondence_reference_number
from api.routers.governance import _active_office_bearer, _home_sakha
from api.schemas.correspondence import (
    ApprovalStepDecisionRequest,
    ApprovalStepResponse,
    CorrespondenceBroadcastCreate,
    CorrespondenceBroadcastResponse,
    CorrespondenceCreate,
    CorrespondenceHistoryEventResponse,
    CorrespondenceHistoryResponse,
    CorrespondenceListResponse,
    CorrespondenceResponse,
    CorrespondenceThreadNodeResponse,
    DocumentAssociationCreate,
    DocumentAssociationListResponse,
    DocumentAssociationResponse,
    FinanceReferenceCreate,
    FinanceReferenceListResponse,
    FinanceReferenceResponse,
    MemberApplicationCreate,
    MemberApplicationListResponse,
    MemberApplicationResponse,
    ResponsiblePartyAssignRequest,
    StatusTransitionRequest,
)
from api.services.rbac_service import UserContext, actor_scope_org_pks, org_subtree_pks, require_org_in_scope
from api.services.seat_service import (
    assignment_person_for_position as _assignment_person_for_position,
    assignment_position_for_person as _assignment_position_for_person,
    find_body_master_pk as _find_body_master_pk,
)

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
           c.is_active,
           c.counterpart_correspondence_pk,
           counterpart.reference_number,
           c.in_reply_to_correspondence_pk,
           reply_to.reference_number
    FROM nss.correspondence c
    JOIN nss.organization rorg ON rorg.organization_pk = c.register_organization_pk
    LEFT JOIN nss.person sp ON sp.person_pk = c.sender_person_pk
    LEFT JOIN nss.organization sorg ON sorg.organization_pk = c.sender_organization_pk
    LEFT JOIN nss.person rp ON rp.person_pk = c.recipient_person_pk
    LEFT JOIN nss.organization recorg ON recorg.organization_pk = c.recipient_organization_pk
    JOIN nss.master_data medium_md ON medium_md.master_data_pk = c.medium_master_data_pk
    JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
    LEFT JOIN nss.correspondence counterpart ON counterpart.correspondence_pk = c.counterpart_correspondence_pk
    LEFT JOIN nss.correspondence reply_to ON reply_to.correspondence_pk = c.in_reply_to_correspondence_pk
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
        counterpart_correspondence_pk=r[35],
        counterpart_reference_number=r[36],
        in_reply_to_correspondence_pk=r[37],
        in_reply_to_reference_number=r[38],
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

def _insert_correspondence_row(
    cur, *,
    register_organization_pk: str, reference_number: str, direction: str,
    correspondence_date, received_or_sent_date, follow_up_date,
    subject: str, remarks: str | None,
    sender_type: str, sender_person_pk: str | None, sender_organization_pk: str | None,
    sender_external_name: str | None, sender_external_organization: str | None,
    sender_person_capacity: str | None, sender_person_organization_pk: str | None,
    sender_sakha_erp_id_snapshot: str | None,
    recipient_type: str, recipient_person_pk: str | None, recipient_organization_pk: str | None,
    recipient_external_name: str | None, recipient_external_organization: str | None,
    responsible_person_pk: str | None, responsible_organization_pk: str | None,
    medium_pk: str, status_pk: str, actor_pk: str | None,
    in_reply_to_correspondence_pk: str | None = None,
) -> str:
    """
    Shared INSERT for nss.correspondence — used by both the admin-facing
    create_correspondence() below and the member-facing
    create_member_application() ("Send Application"), so the column list
    and chk_correspondence_* consistency rules are expressed exactly once.
    """
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
            in_reply_to_correspondence_pk,
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
            %s,
            %s
        )
        RETURNING correspondence_pk
        """,
        (
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
            medium_pk, status_pk,
            in_reply_to_correspondence_pk,
            actor_pk,
        ),
    )
    return str(cur.fetchone()[0])


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

    Owner-confirmed 2026-10-26: "when the letter is sent intra org (within
    nss), i dont think there is any need to register it through receive
    application, it should auto register." So whenever this creates an
    OUTWARD row addressed to a DIFFERENT NSS organization
    (recipient_type=ORGANIZATION), it immediately mints that organization's
    own INWARD counterpart too — via the same _mint_inward_counterpart()
    helper POST /{pk}/dispatch and POST /broadcast use — collapsing the
    previous two-step "create, then separately click Dispatch" flow into
    one. This is a best-effort step, not a hard requirement of the create:
    if it fails (most likely cause: the recipient organization has no
    short_code yet, so next_correspondence_reference_number 422s) the
    OUTWARD row is still created and simply stays un-dispatched — exactly
    as every row did before this change — recoverable later via the
    existing POST /{pk}/dispatch endpoint once the blocker is fixed. Only
    HTTPException is caught here (a known, pre-write validation failure);
    anything else propagates and rolls back the whole request as normal.

    Event-driven lifecycle, option 3 (owner-confirmed 2026-10-26 — amends
    §5.4/§6.2, see that doc for the full rationale): if this create is a
    reply (in_reply_to_correspondence_pk set), and the original is still
    REGISTERED/PENDING_ACTION, and the reply is filed under the SAME
    register the original belongs to, the original is auto-transitioned to
    ACTIONED right here — sending a reply IS the action it was pending.
    Unlike auto-dispatch above, this is NOT best-effort/swallowed: there is
    no realistic failure mode for a plain status UPDATE, so no try/except.
    """
    with conn.cursor() as cur:
        require_org_in_scope(cur, user, str(body.register_organization_pk), "register correspondence for this organization")

        # Resolved here (not just existence-checked) because the
        # event-driven lifecycle amendment below needs both the original's
        # current status and its own register — see that block for why.
        original_status = None
        original_register_pk = None
        if body.in_reply_to_correspondence_pk:
            cur.execute(
                """
                SELECT status_md.value_code, c.register_organization_pk
                FROM nss.correspondence c
                JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
                WHERE c.correspondence_pk = %s AND c.is_active = TRUE
                """,
                (str(body.in_reply_to_correspondence_pk),),
            )
            original_row = cur.fetchone()
            if original_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The correspondence being replied to was not found.",
                )
            original_status, original_register_pk = original_row
            # Naming a record is a read of it (the response echoes its
            # reference number): the caller must have scope over the
            # ORIGINAL's register too, not just over the reply's own.
            require_org_in_scope(
                cur, user, str(original_register_pk), "reply to correspondence in this organization's register",
            )

        reference_number = next_correspondence_reference_number(
            cur, str(body.register_organization_pk), body.direction, as_of=body.correspondence_date,
        )
        medium_pk = get_master_data_pk(cur, "CORRESPONDENCE_MEDIUM", body.medium, client_supplied=True)
        status_pk = get_master_data_pk(cur, "CORRESPONDENCE_STATUS", "REGISTERED")
        sender_snapshot = _fetch_sender_sakha_snapshot(cur, body.sender_type, body.sender_person_pk)

        corr_pk = _insert_correspondence_row(
            cur,
            register_organization_pk=str(body.register_organization_pk),
            reference_number=reference_number,
            direction=body.direction,
            correspondence_date=body.correspondence_date,
            received_or_sent_date=body.received_or_sent_date,
            follow_up_date=body.follow_up_date,
            subject=body.subject,
            remarks=body.remarks,
            sender_type=body.sender_type,
            sender_person_pk=str(body.sender_person_pk) if body.sender_person_pk else None,
            sender_organization_pk=str(body.sender_organization_pk) if body.sender_organization_pk else None,
            sender_external_name=body.sender_external_name,
            sender_external_organization=body.sender_external_organization,
            sender_person_capacity=body.sender_person_capacity,
            sender_person_organization_pk=str(body.sender_person_organization_pk) if body.sender_person_organization_pk else None,
            sender_sakha_erp_id_snapshot=sender_snapshot,
            recipient_type=body.recipient_type,
            recipient_person_pk=str(body.recipient_person_pk) if body.recipient_person_pk else None,
            recipient_organization_pk=str(body.recipient_organization_pk) if body.recipient_organization_pk else None,
            recipient_external_name=body.recipient_external_name,
            recipient_external_organization=body.recipient_external_organization,
            responsible_person_pk=str(body.responsible_person_pk) if body.responsible_person_pk else None,
            responsible_organization_pk=str(body.responsible_organization_pk) if body.responsible_organization_pk else None,
            medium_pk=medium_pk,
            status_pk=status_pk,
            actor_pk=user.actor_pk,
            in_reply_to_correspondence_pk=(
                str(body.in_reply_to_correspondence_pk) if body.in_reply_to_correspondence_pk else None
            ),
        )

        log_audit(
            cur, action="CREATE", table_name="correspondence", record_pk=str(corr_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary=f"Registered {body.direction.lower()} correspondence {reference_number}",
        )

        # Event-driven lifecycle (§5.4/§6.2 amendment, owner-confirmed
        # 2026-10-26, option 3): sending a reply IS the action the original
        # was pending, so it auto-advances the ORIGINAL to ACTIONED — once,
        # right here, rather than needing a separate manual /transition
        # call. Guarded narrowly (see the §6.2 doc amendment for the full
        # rationale): only from REGISTERED/PENDING_ACTION (already-ACTIONED
        # is a silent no-op; CLOSED is never auto-reopened — that transition
        # was never valid even manually); and only when the reply's own
        # register matches the original's — require_org_in_scope above only
        # ever checked THIS reply's register_organization_pk, so without
        # this match a reply could otherwise be used to mutate an
        # out-of-scope record's status just by naming its pk.
        if (
            body.in_reply_to_correspondence_pk
            and original_status in ("REGISTERED", "PENDING_ACTION")
            and str(original_register_pk) == str(body.register_organization_pk)
        ):
            _set_correspondence_status(
                cur, str(body.in_reply_to_correspondence_pk), "ACTIONED",
                remarks=None, actor_pk=user.actor_pk,
            )
            log_audit(
                cur, action="UPDATE", table_name="correspondence",
                record_pk=str(body.in_reply_to_correspondence_pk),
                actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
                module="correspondence",
                summary=f"Auto-transitioned {original_status} -> ACTIONED (replied via {reference_number})",
            )

        # Auto-dispatch (owner 2026-10-26) — see docstring. Same eligibility
        # guard dispatch_correspondence() itself checks (minus the "already
        # dispatched" check, which can't apply to a row just created).
        if (
            body.direction == "OUTWARD"
            and body.recipient_type == "ORGANIZATION"
            and str(body.recipient_organization_pk) != str(body.register_organization_pk)
        ):
            try:
                counterpart_pk, inward_reference_number = _mint_inward_counterpart(
                    cur, user,
                    outward_correspondence_pk=corr_pk,
                    recipient_organization_pk=body.recipient_organization_pk,
                    correspondence_date=body.correspondence_date,
                    received_or_sent_date=body.received_or_sent_date,
                    subject=body.subject,
                    remarks=body.remarks,
                    sender_type=body.sender_type,
                    sender_person_pk=body.sender_person_pk,
                    sender_organization_pk=body.sender_organization_pk,
                    sender_external_name=body.sender_external_name,
                    sender_external_organization=body.sender_external_organization,
                    sender_person_capacity=body.sender_person_capacity,
                    sender_person_organization_pk=body.sender_person_organization_pk,
                    sender_sakha_erp_id_snapshot=sender_snapshot,
                    medium_pk=medium_pk,
                )
                cur.execute(
                    "UPDATE nss.correspondence SET counterpart_correspondence_pk = %s, updated_at = NOW() "
                    "WHERE correspondence_pk = %s",
                    (str(counterpart_pk), str(corr_pk)),
                )
                _log_dispatch(
                    cur, user, outward_pk=corr_pk, counterpart_pk=counterpart_pk,
                    reference_number=reference_number, inward_reference_number=inward_reference_number,
                    verb="Auto-dispatched",
                )
            except HTTPException as exc:
                logger.warning(
                    "create_correspondence: auto-dispatch of %s skipped (%s) — "
                    "left un-dispatched, recoverable via POST /dispatch.",
                    reference_number, exc.detail,
                )

        cur.execute(_DETAIL_SELECT + " WHERE c.correspondence_pk = %s", (str(corr_pk),))
        row = cur.fetchone()

    return _row_to_response(row)


# ── Shared by create_correspondence (auto-dispatch), /dispatch and /broadcast ──

def _mint_inward_counterpart(
    cur, user, *,
    outward_correspondence_pk: UUID, recipient_organization_pk,
    correspondence_date, received_or_sent_date, subject: str, remarks: str | None,
    sender_type: str, sender_person_pk, sender_organization_pk,
    sender_external_name: str | None, sender_external_organization: str | None,
    sender_person_capacity: str | None, sender_person_organization_pk,
    sender_sakha_erp_id_snapshot: str | None, medium_pk,
) -> tuple[str, str]:
    """
    Mints the recipient organization's own INWARD row for one OUTWARD
    record addressed to it, and links the NEW row back to
    *outward_correspondence_pk* (the reverse link — OUTWARD -> INWARD —
    is the caller's job, since only the caller knows whether it's linking
    one row (create_correspondence's auto-dispatch, dispatch_correspondence)
    or updating it inside a loop (broadcast_correspondence)).

    Shared by create_correspondence() (auto-dispatch on creation, owner
    2026-10-26), dispatch_correspondence() (manual single-letter retry) and
    broadcast_correspondence() (one circular, many recipients) so the
    actual INSERT/link shape is expressed exactly once — extracted
    2026-10-26 when the broadcast feature needed the identical logic a
    second time.

    Returns (counterpart_pk, inward_reference_number).
    """
    status_pk = get_master_data_pk(cur, "CORRESPONDENCE_STATUS", "REGISTERED")
    inward_reference_number = next_correspondence_reference_number(
        cur, str(recipient_organization_pk), "INWARD", as_of=received_or_sent_date,
    )

    counterpart_pk = _insert_correspondence_row(
        cur,
        register_organization_pk=str(recipient_organization_pk),
        reference_number=inward_reference_number,
        direction="INWARD",
        correspondence_date=correspondence_date,
        received_or_sent_date=received_or_sent_date,
        follow_up_date=None,
        subject=subject,
        remarks=remarks,
        sender_type=sender_type,
        sender_person_pk=str(sender_person_pk) if sender_person_pk else None,
        sender_organization_pk=str(sender_organization_pk) if sender_organization_pk else None,
        sender_external_name=sender_external_name,
        sender_external_organization=sender_external_organization,
        sender_person_capacity=sender_person_capacity,
        sender_person_organization_pk=(
            str(sender_person_organization_pk) if sender_person_organization_pk else None
        ),
        sender_sakha_erp_id_snapshot=sender_sakha_erp_id_snapshot,
        # The recipient of the INWARD copy is the recipient org itself
        # (§4.6: "recipient = which NSS person/organization received
        # it") — no specific office-bearer was named, the letter was
        # addressed to the organization generally.
        recipient_type="ORGANIZATION",
        recipient_person_pk=None,
        recipient_organization_pk=str(recipient_organization_pk),
        recipient_external_name=None,
        recipient_external_organization=None,
        responsible_person_pk=None,
        responsible_organization_pk=None,
        medium_pk=str(medium_pk),
        status_pk=status_pk,
        actor_pk=user.actor_pk,
    )

    cur.execute(
        "UPDATE nss.correspondence SET counterpart_correspondence_pk = %s, updated_at = NOW() "
        "WHERE correspondence_pk = %s",
        (str(outward_correspondence_pk), str(counterpart_pk)),
    )

    return counterpart_pk, inward_reference_number


def _log_dispatch(cur, user, *, outward_pk, counterpart_pk, reference_number: str,
                  inward_reference_number: str, verb: str) -> None:
    """
    Audit a dispatch on BOTH rows of the pair: CREATE on the new INWARD
    counterpart, and UPDATE on the OUTWARD row (which gained its
    counterpart link) so the sender's GET /{pk}/history shows the dispatch
    too. Shared by create_correspondence()'s auto-dispatch and
    dispatch_correspondence() ("Auto-dispatched" / "Dispatched").
    """
    summary = f"{verb} {reference_number} to inward {inward_reference_number}"
    for action, record_pk in (("CREATE", counterpart_pk), ("UPDATE", outward_pk)):
        log_audit(
            cur, action=action, table_name="correspondence", record_pk=str(record_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence", summary=summary,
        )


# ── POST /api/v1/correspondence/{pk}/dispatch ───────────────────────────

@router.post("/{correspondence_pk:uuid}/dispatch", response_model=CorrespondenceResponse)
def dispatch_correspondence(
    correspondence_pk: UUID,
    user: UserContext = Depends(require_permission("CORRESPONDENCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> CorrespondenceResponse:
    """
    Two-sided org-to-org register (v1.1, owner-confirmed 2026-10-25): mints
    the RECIPIENT organization's own INWARD counterpart row — with its own
    reference_number under its own per-org counter (§4.1/CORR-EXT-001) —
    for an OUTWARD record addressed to an NSS organization, and links the
    two rows via counterpart_correspondence_pk (reciprocally, on both
    sides).

    Owner-confirmed 2026-10-26 ("...it should auto register"):
    create_correspondence() now attempts this same mint automatically right
    after creating an eligible OUTWARD/ORGANIZATION row, so this endpoint is
    no longer the only path to a dispatched pair — it is now primarily the
    MANUAL RECOVERY path for the one case auto-dispatch can't cover: the
    recipient organization had no short_code yet at creation time (so the
    automatic attempt 422'd internally and left the row un-dispatched,
    exactly as any row did before auto-dispatch existed). Once an admin
    assigns that short_code, this endpoint retries the exact same mint.
    Also still the only path for correspondence created before 2026-10-26
    (no auto-dispatch attempt ever ran for those rows).

    Scope/authority: the caller is checked against the SENDER row's own
    register_organization_pk only (require_org_in_scope, same gate
    create_correspondence() uses). Writing the recipient org's inward row
    is deliberately NOT re-checked against that org's own admin scope —
    it is the system fulfilling what the sender's admin already had
    authority to send, not an independent write the recipient's org chose
    to make.

    Only reachable for recipient_type = 'ORGANIZATION' (422 otherwise) —
    PERSON and EXTERNAL recipients have no register of their own to write
    an inward copy into, and are untouched by this endpoint; they stay
    single-row, exactly as before this feature existed. Only an OUTWARD
    row may be dispatched (422) — an INWARD row is either hand-entered
    (a letter that arrived by post, not through this system) or is
    itself already a dispatched counterpart. 409 if already dispatched
    (idempotent: calling dispatch twice never mints a second counterpart —
    including the now-common case where auto-dispatch at creation already
    succeeded, so a later manual call here simply 409s).
    422 (via next_correspondence_reference_number, same guard
    create_correspondence() already relies on) if the recipient
    organization has no short_code assigned yet.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT register_organization_pk, direction, recipient_type, recipient_organization_pk,
                   reference_number, counterpart_correspondence_pk,
                   correspondence_date, subject, remarks,
                   sender_type, sender_person_pk, sender_organization_pk,
                   sender_external_name, sender_external_organization,
                   sender_person_capacity, sender_person_organization_pk,
                   sender_sakha_erp_id_snapshot, medium_master_data_pk
            FROM nss.correspondence
            WHERE correspondence_pk = %s AND is_active = TRUE
            """,
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")
        (register_organization_pk, direction, recipient_type, recipient_organization_pk,
         reference_number, existing_counterpart_pk, correspondence_date, subject, remarks,
         sender_type, sender_person_pk, sender_organization_pk, sender_external_name,
         sender_external_organization, sender_person_capacity, sender_person_organization_pk,
         sender_sakha_erp_id_snapshot, medium_pk) = row

        require_org_in_scope(
            cur, user, str(register_organization_pk), "dispatch correspondence from this organization",
        )

        if direction != "OUTWARD":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only an OUTWARD record can be dispatched.",
            )
        if recipient_type != "ORGANIZATION":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Only correspondence addressed to an NSS organization "
                    "(recipient_type=ORGANIZATION) can be dispatched."
                ),
            )
        if existing_counterpart_pk is not None:
            raise HTTPException(status_code=409, detail="This record has already been dispatched.")
        if str(recipient_organization_pk) == str(register_organization_pk):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cannot dispatch a letter to its own sending organization.",
            )

        today = date.today()
        counterpart_pk, inward_reference_number = _mint_inward_counterpart(
            cur, user,
            outward_correspondence_pk=correspondence_pk,
            recipient_organization_pk=recipient_organization_pk,
            correspondence_date=correspondence_date,
            received_or_sent_date=today,
            subject=subject,
            remarks=remarks,
            sender_type=sender_type,
            sender_person_pk=sender_person_pk,
            sender_organization_pk=sender_organization_pk,
            sender_external_name=sender_external_name,
            sender_external_organization=sender_external_organization,
            sender_person_capacity=sender_person_capacity,
            sender_person_organization_pk=sender_person_organization_pk,
            sender_sakha_erp_id_snapshot=sender_sakha_erp_id_snapshot,
            medium_pk=medium_pk,
        )

        # Reciprocal link — both rows end up pointing at each other.
        cur.execute(
            "UPDATE nss.correspondence SET counterpart_correspondence_pk = %s, updated_at = NOW() "
            "WHERE correspondence_pk = %s",
            (str(counterpart_pk), str(correspondence_pk)),
        )

        _log_dispatch(
            cur, user, outward_pk=correspondence_pk, counterpart_pk=counterpart_pk,
            reference_number=reference_number, inward_reference_number=inward_reference_number,
            verb="Dispatched",
        )

        cur.execute(_DETAIL_SELECT + " WHERE c.correspondence_pk = %s", (str(correspondence_pk),))
        row = cur.fetchone()

    return _row_to_response(row)


# ── POST /api/v1/correspondence/broadcast ───────────────────────────────

@router.post("/broadcast", response_model=CorrespondenceBroadcastResponse, status_code=status.HTTP_201_CREATED)
def broadcast_correspondence(
    body: CorrespondenceBroadcastCreate,
    user: UserContext = Depends(require_permission("CORRESPONDENCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> CorrespondenceBroadcastResponse:
    """
    Owner-confirmed 2026-10-26: "sometimes, kendra/anchalika/zilla send
    letter to all sakhas under it. we should have some option" —
    generalizes §4.7 ERP-FROZEN's own example ("Kendra circular to all
    Sakhas") to any sender organization + any descendant organization
    type.

    Creates one real OUTWARD row per recipient (CorrespondenceBroadcastCreate's
    own docstring explains why it can't be a single row — §4.6's
    one-recipient-per-row CHECK is unconditional), then immediately mints
    and links each recipient's own INWARD counterpart via the same
    _mint_inward_counterpart() helper dispatch_correspondence() uses — so
    a circular lands pre-dispatched in every recipient's register, not
    sitting as N un-dispatched drafts the admin would then have to
    dispatch one by one anyway.

    Scope: checked against register_organization_pk only (same gate
    create_correspondence()/dispatch_correspondence() use) — the
    recipient-side writes are the system fulfilling what the sender's
    admin already had authority to send, exactly like a single dispatch.

    422 if the organization has no descendants at all, or none of the
    requested type (an empty circular is never created) — this
    distinction is in the detail message, not the status code, since
    it's the same user mistake either way (nothing to send to).
    """
    with conn.cursor() as cur:
        require_org_in_scope(
            cur, user, str(body.register_organization_pk), "send a circular from this organization",
        )

        subtree = org_subtree_pks(cur, str(body.register_organization_pk))
        subtree.discard(str(body.register_organization_pk))
        if not subtree:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="This organization has no descendant organizations to send a circular to.",
            )

        placeholders = ",".join(["%s"] * len(subtree))
        cur.execute(
            f"""
            SELECT o.organization_pk FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE o.organization_pk IN ({placeholders})
              AND md.value_code = %s AND o.is_active = TRUE
            ORDER BY o.organization_name
            """,
            list(subtree) + [body.recipient_organization_type_code],
        )
        target_pks = [str(r[0]) for r in cur.fetchall()]
        if not target_pks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"No active {body.recipient_organization_type_code} organizations "
                    "found under this organization."
                ),
            )

        medium_pk = get_master_data_pk(cur, "CORRESPONDENCE_MEDIUM", body.medium, client_supplied=True)
        status_pk = get_master_data_pk(cur, "CORRESPONDENCE_STATUS", "REGISTERED")
        created_pks: list[str] = []

        for target_pk in target_pks:
            reference_number = next_correspondence_reference_number(
                cur, str(body.register_organization_pk), "OUTWARD", as_of=body.correspondence_date,
            )
            outward_pk = _insert_correspondence_row(
                cur,
                register_organization_pk=str(body.register_organization_pk),
                reference_number=reference_number,
                direction="OUTWARD",
                correspondence_date=body.correspondence_date,
                received_or_sent_date=body.received_or_sent_date,
                follow_up_date=body.follow_up_date,
                subject=body.subject,
                remarks=body.remarks,
                sender_type="ORGANIZATION",
                sender_person_pk=None,
                sender_organization_pk=str(body.register_organization_pk),
                sender_external_name=None,
                sender_external_organization=None,
                sender_person_capacity=None,
                sender_person_organization_pk=None,
                sender_sakha_erp_id_snapshot=None,
                recipient_type="ORGANIZATION",
                recipient_person_pk=None,
                recipient_organization_pk=target_pk,
                recipient_external_name=None,
                recipient_external_organization=None,
                responsible_person_pk=None,
                responsible_organization_pk=None,
                medium_pk=medium_pk,
                status_pk=status_pk,
                actor_pk=user.actor_pk,
            )

            counterpart_pk, inward_reference_number = _mint_inward_counterpart(
                cur, user,
                outward_correspondence_pk=outward_pk,
                recipient_organization_pk=target_pk,
                correspondence_date=body.correspondence_date,
                received_or_sent_date=body.received_or_sent_date,
                subject=body.subject,
                remarks=body.remarks,
                sender_type="ORGANIZATION",
                sender_person_pk=None,
                sender_organization_pk=str(body.register_organization_pk),
                sender_external_name=None,
                sender_external_organization=None,
                sender_person_capacity=None,
                sender_person_organization_pk=None,
                sender_sakha_erp_id_snapshot=None,
                medium_pk=medium_pk,
            )
            cur.execute(
                "UPDATE nss.correspondence SET counterpart_correspondence_pk = %s, updated_at = NOW() "
                "WHERE correspondence_pk = %s",
                (str(counterpart_pk), str(outward_pk)),
            )

            log_audit(
                cur, action="CREATE", table_name="correspondence", record_pk=str(outward_pk),
                actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
                module="correspondence",
                summary=f"Circular {reference_number} (to {len(target_pks)} recipients) dispatched to inward {inward_reference_number}",
            )
            created_pks.append(outward_pk)

        placeholders = ",".join(["%s"] * len(created_pks))
        cur.execute(
            _DETAIL_SELECT + f" WHERE c.correspondence_pk IN ({placeholders}) ORDER BY c.reference_number",
            [str(pk) for pk in created_pks],
        )
        items = [_row_to_response(r) for r in cur.fetchall()]

    return CorrespondenceBroadcastResponse(recipient_count=len(items), items=items)


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

@router.get("/{correspondence_pk:uuid}", response_model=CorrespondenceResponse)
def get_correspondence(
    correspondence_pk: UUID,
    user: UserContext = Depends(require_any_permission("CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE")),
    conn=Depends(get_connection),
) -> CorrespondenceResponse:
    with conn.cursor() as cur:
        cur.execute(
            _DETAIL_SELECT + " WHERE c.correspondence_pk = %s AND c.is_active = TRUE", (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")

        if not user.is_nss_wide() and not user.is_super_admin():
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None and str(row[1]) not in allowed:
                raise HTTPException(status_code=403, detail="This correspondence record is outside your admin scope.")

    return _row_to_response(row)


# ── GET /api/v1/correspondence/{pk}/history ─────────────────────────────

_THREAD_NODE_SELECT_COLUMNS = """
    c.correspondence_pk, c.reference_number, c.subject, c.direction, status_md.value_code
"""

_HISTORY_EVENTS_SELECT = """
    SELECT sel.event_at, sel.action, sel.summary,
           CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)
    FROM nss.system_event_log sel
    LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = sel.actor_sangha_sevi_pk
    LEFT JOIN nss.person p ON p.person_pk = ss.person_pk
    WHERE sel.table_name = 'correspondence' AND sel.record_pk = %s
    ORDER BY sel.event_at ASC
"""

# Depth cap mirrors the project's existing convention for unbounded
# recursive CTEs (e.g. /organization/hierarchy caps at 10) — a reply
# thread 20 deep is already pathological, not a real use case being cut off.
_THREAD_DEPTH_CAP = 20

_THREAD_ANCESTORS_SELECT = f"""
    WITH RECURSIVE ancestors AS (
        SELECT c.correspondence_pk, c.in_reply_to_correspondence_pk, 0 AS depth
        FROM nss.correspondence c
        WHERE c.correspondence_pk = %s
        UNION ALL
        SELECT c.correspondence_pk, c.in_reply_to_correspondence_pk, a.depth + 1
        FROM nss.correspondence c
        JOIN ancestors a ON c.correspondence_pk = a.in_reply_to_correspondence_pk
        WHERE a.depth < {_THREAD_DEPTH_CAP}
    )
    SELECT {_THREAD_NODE_SELECT_COLUMNS}, a.depth
    FROM ancestors a
    JOIN nss.correspondence c ON c.correspondence_pk = a.correspondence_pk
    JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
    WHERE a.depth > 0 AND c.is_active = TRUE
    ORDER BY a.depth DESC
"""

_THREAD_DESCENDANTS_SELECT = f"""
    WITH RECURSIVE descendants AS (
        SELECT c.correspondence_pk, 0 AS depth
        FROM nss.correspondence c
        WHERE c.correspondence_pk = %s
        UNION ALL
        SELECT c.correspondence_pk, d.depth + 1
        FROM nss.correspondence c
        JOIN descendants d ON c.in_reply_to_correspondence_pk = d.correspondence_pk
        WHERE d.depth < {_THREAD_DEPTH_CAP}
    )
    SELECT {_THREAD_NODE_SELECT_COLUMNS}, d.depth
    FROM descendants d
    JOIN nss.correspondence c ON c.correspondence_pk = d.correspondence_pk
    JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
    WHERE d.depth > 0 AND c.is_active = TRUE
    ORDER BY d.depth ASC, c.created_at ASC
"""


@router.get("/{correspondence_pk:uuid}/history", response_model=CorrespondenceHistoryResponse)
def get_correspondence_history(
    correspondence_pk: UUID,
    user: UserContext = Depends(require_any_permission("CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE")),
    conn=Depends(get_connection),
) -> CorrespondenceHistoryResponse:
    """
    Owner-confirmed 2026-10-26: "can we add history with path tracker for
    correspondance?" Two parts, one response:

      - events: the full activity log for this ONE record — every status
        transition (manual via /transition, or the 2026-10-26 event-driven
        auto-advances), responsible-party reassignment, creation, and
        dispatch/auto-dispatch — reusing the EXISTING generic audit write
        path (log_audit() -> nss.system_event_log) rather than a new
        per-module history table (owner's own standing "shared Change
        History framework" decision). Nothing new is written for this —
        every correspondence mutation already calls log_audit() with a
        human-readable summary; this just filters those rows to one
        record_pk.
      - thread_ancestors / thread_descendants: the reply "path" —
        in_reply_to_correspondence_pk walked both directions. Ancestors are
        oldest-first (what this ultimately replies to); descendants are
        depth-then-chronological (every reply this drew, recursively).

    Same permission + scope gate as GET /{pk} itself (get_correspondence) —
    history is an extension of viewing the record, not a separately
    privileged capability.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s AND is_active = TRUE",
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")

        if not user.is_nss_wide() and not user.is_super_admin():
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None and str(row[0]) not in allowed:
                raise HTTPException(status_code=403, detail="This correspondence record is outside your admin scope.")

        cur.execute(_HISTORY_EVENTS_SELECT, (str(correspondence_pk),))
        events = [
            CorrespondenceHistoryEventResponse(
                event_at=r[0], action=r[1], summary=r[2], actor_name=r[3] or None,
            )
            for r in cur.fetchall()
        ]

        cur.execute(_THREAD_ANCESTORS_SELECT, (str(correspondence_pk),))
        ancestors = [
            CorrespondenceThreadNodeResponse(
                correspondence_pk=r[0], reference_number=r[1], subject=r[2],
                direction=r[3], status_value_code=r[4], depth=r[5],
            )
            for r in cur.fetchall()
        ]

        cur.execute(_THREAD_DESCENDANTS_SELECT, (str(correspondence_pk),))
        descendants = [
            CorrespondenceThreadNodeResponse(
                correspondence_pk=r[0], reference_number=r[1], subject=r[2],
                direction=r[3], status_value_code=r[4], depth=r[5],
            )
            for r in cur.fetchall()
        ]

    return CorrespondenceHistoryResponse(
        events=events, thread_ancestors=ancestors, thread_descendants=descendants,
    )


# ── §6.2/§5.4 write authority — "directed-at" check (PART 2, owner-confirmed
#    2026-10-22) ────────────────────────────────────────────────────────
#
# Previously /transition and /responsible-party were gated by
# CORRESPONDENCE_MANAGE + admin scope alone — meaning any admin whose scope
# covered register_organization_pk could change status/responsibility on
# ANY correspondence in that register, including ones addressed to someone
# else entirely. The owner wants this tightened: only the authority the
# record is actually directed at may act — never a blanket admin-scope
# grant, not even NSS_ERP_ADMIN/KENDRA_ADMIN.
#
# "Directed at" resolves, in order:
#   1. The current responsible_person_pk (whoever §5.4 has most recently
#      pointed this record at).
#   2. recipient_person_pk, if recipient_type = PERSON.
#   3. A currently-seated, non-MEMBER office-bearer of recipient_organization_pk's
#      governing body, if recipient_type = ORGANIZATION (reuses
#      _find_body_master_pk/_active_office_bearer — the same lookup this
#      router already uses for the approval chain below; no new authority
#      primitive).
#
# Un-actionable-row edge case (owner-flagged, see report): a record with
# recipient_type = EXTERNAL has no in-app person to delegate to at all — the
# addressee isn't a system user. The same is true for an ORGANIZATION
# recipient of a type this app has no governing-body concept for (no
# body_master row resolves). Treating "directed-at" as absolute for these
# would make such records permanently un-actionable by anyone, so they fall
# back to the pre-existing CORRESPONDENCE_MANAGE + admin-scope gate — the
# ONLY case where that blanket permission still suffices.

_ORG_SCOPED_GOVERNING_BODY_TYPES = (
    "SAKHA_GOVERNING_BODY", "ANCHALIKA_GOVERNING_BODY", "ZILLA_GOVERNING_BODY",
    "PATHA_CHAKRA_GOVERNING_BODY", "SEVAK_SANGHA_EXECUTIVE", "MAHILA_PARICHALANA_MANDALI",
)


def _org_has_governing_body(cur, organization_pk: str) -> bool:
    """True if *organization_pk* has an active body_master row of any
    org-scoped governing-body type this app models (see
    _ORG_SCOPED_GOVERNING_BODY_TYPES) — i.e. the "directed-at" concept is
    even applicable to this organization."""
    return any(
        _find_body_master_pk(cur, body_type_code, organization_pk) is not None
        for body_type_code in _ORG_SCOPED_GOVERNING_BODY_TYPES
    )


def _org_office_bearer_match(cur, organization_pk: str, person_pk: str) -> bool:
    """True if person_pk currently holds an active, non-MEMBER office-bearer
    seat on any of organization_pk's org-scoped governing bodies."""
    for body_type_code in _ORG_SCOPED_GOVERNING_BODY_TYPES:
        body_master_pk = _find_body_master_pk(cur, body_type_code, organization_pk)
        if body_master_pk and _active_office_bearer(cur, body_master_pk, person_pk):
            return True
    return False


def _require_directed_authority(cur, user: UserContext, correspondence_pk: str, action: str) -> dict:
    """
    Gate for transition_status()/assign_responsible_party() — see module
    comment above. Raises 404/403 on failure; on success returns the fields
    those two callers need, so neither re-selects the row.
    """
    cur.execute(
        """
        SELECT register_organization_pk, status_md.value_code,
               recipient_type, recipient_person_pk, recipient_organization_pk,
               responsible_person_pk, responsible_organization_pk
        FROM nss.correspondence c
        JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
        WHERE c.correspondence_pk = %s AND c.is_active = TRUE
        """,
        (str(correspondence_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Correspondence record not found.")
    (register_org_pk, current_status, recipient_type, recipient_person_pk,
     recipient_org_pk, responsible_person_pk, responsible_org_pk) = row

    person_pk = str(user.person_pk) if user.person_pk else None
    directed = False
    concept_applies = recipient_type != "EXTERNAL"

    if person_pk:
        if responsible_person_pk and str(responsible_person_pk) == person_pk:
            directed = True
        elif recipient_type == "PERSON" and recipient_person_pk and str(recipient_person_pk) == person_pk:
            directed = True
        elif recipient_type == "ORGANIZATION" and recipient_org_pk:
            if _org_has_governing_body(cur, str(recipient_org_pk)):
                if _org_office_bearer_match(cur, str(recipient_org_pk), person_pk):
                    directed = True
            else:
                concept_applies = False  # unmodeled org type -> fall back below

    result = {
        "register_organization_pk": register_org_pk,
        "status": current_status,
        "responsible_person_pk": responsible_person_pk,
        "responsible_organization_pk": responsible_org_pk,
    }

    if directed:
        return result

    if not concept_applies:
        # No directed human authority exists for this row at all — the
        # pre-existing blanket gate is the only path left (see edge-case
        # note above), so it still applies here, unchanged.
        if not user.has_permission("CORRESPONDENCE_MANAGE"):
            raise HTTPException(status_code=403, detail=f"Permission required to {action}.")
        require_org_in_scope(cur, user, register_org_pk, action)
        return result

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"This correspondence record is not directed at you, so you cannot {action}.",
    )


def _set_correspondence_status(cur, correspondence_pk: str, new_status: str, *, remarks: str | None, actor_pk) -> None:
    """
    Shared UPDATE for nss.correspondence.status_master_data_pk — used by
    both transition_status() (§6.2, user-initiated) and
    decide_approval_step()'s step-2-APPROVE terminal transition below, so
    the column list/semantics are expressed exactly once.
    """
    new_status_pk = get_master_data_pk(cur, "CORRESPONDENCE_STATUS", new_status)
    cur.execute(
        """
        UPDATE nss.correspondence
        SET status_master_data_pk = %s,
            remarks = COALESCE(%s, remarks),
            updated_at = NOW(),
            updated_by_sangha_sevi_pk = %s
        WHERE correspondence_pk = %s
        """,
        (new_status_pk, remarks, actor_pk, str(correspondence_pk)),
    )


# ── POST /api/v1/correspondence/{pk}/transition ─────────────────────────

@router.post("/{correspondence_pk:uuid}/transition", response_model=CorrespondenceResponse)
def transition_status(
    correspondence_pk: UUID,
    body: StatusTransitionRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> CorrespondenceResponse:
    """
    Move a correspondence record to a new status, per the §6.2 precondition
    table. §6.4: the transition is always timestamped with the current
    system time — there is no backdating parameter on this endpoint.

    Authority: the record's directed-at authority only (see
    _require_directed_authority above) — CORRESPONDENCE_MANAGE/admin-scope
    is no longer sufficient on its own, except for the one row shape with
    no directed human authority at all (EXTERNAL recipient / unmodeled org
    type).
    """
    with conn.cursor() as cur:
        info = _require_directed_authority(cur, user, str(correspondence_pk), "transition this correspondence record")
        current_status = info["status"]
        responsible_person_pk = info["responsible_person_pk"]
        responsible_org_pk = info["responsible_organization_pk"]

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

        _set_correspondence_status(cur, str(correspondence_pk), body.new_status, remarks=body.remarks, actor_pk=user.actor_pk)
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

@router.post("/{correspondence_pk:uuid}/responsible-party", response_model=CorrespondenceResponse)
def assign_responsible_party(
    correspondence_pk: UUID,
    body: ResponsiblePartyAssignRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> CorrespondenceResponse:
    """
    Reassign (or clear) who is responsible for acting on this correspondence
    (§5.4) — permitted at any state.

    Event-driven lifecycle amendment (§5.4/§6.2, owner-confirmed 2026-10-26,
    option 3): assigning (not clearing) a responsible party to a REGISTERED
    record now auto-advances it to PENDING_ACTION — populating either field
    is §6.2's entire precondition for that transition, so this is the one
    case "reassignment does not automatically trigger a state transition"
    no longer holds. Every other state is unaffected: reassigning at
    PENDING_ACTION/ACTIONED/CLOSED still has no status side effect, exactly
    as before.

    Authority: the record's directed-at authority only (see
    _require_directed_authority above) — same gate as transition_status().
    """
    with conn.cursor() as cur:
        info = _require_directed_authority(cur, user, str(correspondence_pk), "reassign responsibility for this correspondence record")
        current_status = info["status"]

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

        auto_transitioned = (
            current_status == "REGISTERED"
            and bool(body.responsible_person_pk or body.responsible_organization_pk)
        )
        if auto_transitioned:
            _set_correspondence_status(cur, str(correspondence_pk), "PENDING_ACTION", remarks=None, actor_pk=user.actor_pk)

        log_audit(
            cur, action="UPDATE", table_name="correspondence", record_pk=str(correspondence_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary=(
                "Reassigned responsible party; auto-transitioned REGISTERED -> PENDING_ACTION"
                if auto_transitioned else "Reassigned responsible party"
            ),
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
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s AND is_active = TRUE",
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


@router.get("/{correspondence_pk:uuid}/documents", response_model=DocumentAssociationListResponse)
def list_documents(
    correspondence_pk: UUID,
    user: UserContext = Depends(require_any_permission("CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE")),
    conn=Depends(get_connection),
) -> DocumentAssociationListResponse:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s AND is_active = TRUE",
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
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s AND is_active = TRUE",
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Correspondence record not found.")
        require_org_in_scope(cur, user, row[0], "reference a finance transaction from this correspondence record")

        relationship_pk = get_master_data_pk(
            cur, "CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE", body.relationship_type, client_supplied=True,
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


@router.get("/{correspondence_pk:uuid}/finance-references", response_model=FinanceReferenceListResponse)
def list_finance_references(
    correspondence_pk: UUID,
    user: UserContext = Depends(require_any_permission("CORRESPONDENCE_VIEW", "CORRESPONDENCE_MANAGE")),
    conn=Depends(get_connection),
) -> FinanceReferenceListResponse:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT register_organization_pk FROM nss.correspondence WHERE correspondence_pk = %s AND is_active = TRUE",
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


# ═════════════════════════════════════════════════════════════════════
# Member "Send Application" — additive approval-chain extension
# (owner-confirmed 2026-10-21; nss.correspondence_approval_step,
# database/ddl/09_correspondence/05_correspondence_approval_step.sql)
#
# A member files a plain nss.correspondence row (direction=OUTWARD,
# sender_type=PERSON) addressed one of six ways (a/b/c owner-confirmed
# 2026-10-21; d/e/f owner-confirmed 2026-10-25, gender-gated — "mahila
# sangha also (local and kendra) - only for female members, sevaka sangha
# (local) - only for male members"):
#   SAKHA_ORG                      -> their own Sakha, as an organization.
#   SAKHA_OFFICE_BEARER             -> a named, currently-seated office-bearer
#                                      of their own Sakha Governing Body /
#                                      Mahila Parichalana Mandali.
#   KENDRA_VIA_SAKHA_PRESIDENT      -> a named, currently-seated Kendra-level
#                                      office-bearer, routed through the
#                                      member's own Sakha President first (a
#                                      real 2-step approval chain — step 2,
#                                      the Kendra office-bearer's OWN
#                                      decision, is not actionable/visible
#                                      until step 1 is approved).
#   MAHILA_OFFICE_BEARER            -> a named, currently-seated office-bearer
#                                      of their own (Sakha-level) Mahila
#                                      Parichalana Mandali. FEMALE only.
#   KENDRA_MAHILA_VIA_SAKHA_PRESIDENT -> a named, currently-seated office-
#                                      bearer of the CENTRAL (Kendra-level,
#                                      NSS-wide) Mahila Parichalana Mandali,
#                                      routed through the member's own Sakha
#                                      President first — same 2-step chain
#                                      mechanism as KENDRA_VIA_SAKHA_PRESIDENT.
#                                      FEMALE only.
#   SEVAK_OFFICE_BEARER             -> a named, currently-seated office-bearer
#                                      of their own (Sakha-level) Sevak Sangha
#                                      Executive. MALE only.
#
# Fixed 2026-10-22 (owner-confirmed root-cause fix): step 2 used to be
# auto-flipped to APPROVED by the API the moment step 1 was approved,
# deciding on the Kendra office-bearer's behalf with no real decision
# mechanism for step 2 at all. The real bug was conflating two different
# things — "step 2 is now visible to the Kendra office-bearer" and "step 2
# has been decided" — by mutating step 2's own stored status to fake the
# former. The fix: visibility is now a pure read-time join against step 1's
# status in list_addressed_to_me()/list_pending_approvals_for_me() below
# (step 2 simply stays PENDING, meaning "not yet decided", exactly like
# step 1), and step 2 gets its own genuine decision path through
# decide_approval_step() — gated on the caller being the actual seated
# Kendra-level office-bearer at decision time (re-verified the same way
# step 1 re-verifies the Sakha President), and only reachable once step 1
# is APPROVED.
#
# None of this touches the 9 existing endpoints above, CorrespondenceCreate,
# or the §6.2 status-transition table in the general case — correspondence
# status stays REGISTERED on creation regardless of addressing mode.
# responsible_person_pk is kept pointed at whoever must act next (the
# Sakha President while step 1 is pending, then the Kendra office-bearer
# once step 1 is approved), using the same "assign without transitioning
# status" semantics as the existing /responsible-party endpoint (§5.4) —
# EXCEPT at step 2's own terminal APPROVE, which is the chain's actual
# conclusion: see decide_approval_step() for exactly which existing §6.2
# transition that maps to (REGISTERED -> PENDING_ACTION, via the shared
# _set_correspondence_status() helper — not a new/duplicated transition
# path).
#
# Office-bearer lookups for the frontend's addressing dropdowns are NOT
# duplicated here — the UI calls the existing, already-public governance
# endpoints directly:
#   GET /api/v1/governance/public/my-sakha-bodies   (mode b candidates)
#   GET /api/v1/governance/public/national-bodies   (mode c candidates,
#                                                      Kendra Governing Body)
# This router only re-validates the selected recipient server-side (never
# trusts the client), via small single-purpose queries below that are not
# duplicates of governance.py's bulk/display queries (those return
# all-orgs dicts shaped for a directory UI; these answer one yes/no
# question about one specific body+person).
# ═════════════════════════════════════════════════════════════════════


def _find_sakha_office_bearer_position(
    cur,
    own_sakha_pk: str,
    person_pk,
    body_type_codes: tuple[str, ...] = ("SAKHA_GOVERNING_BODY", "MAHILA_PARICHALANA_MANDALI"),
) -> str | None:
    """Checks each of the given Sakha-scoped body types (default: a Sakha's
    two member-facing bodies, its Sakha Governing Body and its own Mahila
    Parichalana Mandali — unchanged for the SAKHA_OFFICE_BEARER caller) for
    an active office-bearer seat held by person_pk, org-scoped to
    own_sakha_pk. Callers needing a single specific local body type (the
    MAHILA_OFFICE_BEARER / SEVAK_OFFICE_BEARER addressing modes, added
    2026-10-25) pass a single-element body_type_codes tuple instead —
    added here rather than duplicating this loop, since the only thing
    that differs is which body type(s) are tried."""
    for body_type_code in body_type_codes:
        body_master_pk = _find_body_master_pk(cur, body_type_code, own_sakha_pk)
        if body_master_pk:
            position_pk = _assignment_position_for_person(cur, body_master_pk, person_pk)
            if position_pk:
                return position_pk
    return None


def _require_gender(cur, person_pk, expected_value_code: str, mode_label: str) -> None:
    """Fail-closed gender gate for the gendered addressing modes
    (MAHILA_OFFICE_BEARER / KENDRA_MAHILA_VIA_SAKHA_PRESIDENT / SEVAK_
    OFFICE_BEARER; owner-confirmed 2026-10-25). A member whose gender is
    NULL/unset, or any value other than expected_value_code (including
    the seeded 'OTHER' value), is always rejected — this never defaults
    to "allowed" for a missing/unresolved gender. Mirrors this file's
    existing small single-purpose validation queries (e.g.
    _assignment_position_for_person) rather than UserContext, which does
    not carry gender."""
    cur.execute(
        """
        SELECT md.value_code
        FROM nss.person p
        LEFT JOIN nss.master_data md ON md.master_data_pk = p.gender_master_data_pk
        WHERE p.person_pk = %s
        """,
        (str(person_pk),),
    )
    row = cur.fetchone()
    value_code = row[0] if row else None
    if value_code != expected_value_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your account's gender does not permit addressing_mode {mode_label}.",
        )


_APPROVAL_STEP_SELECT = """
    SELECT s.correspondence_approval_step_pk, s.correspondence_pk, s.step_number,
           s.approver_person_pk, CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name),
           s.approver_position_master_pk, pm.position_name, pm.position_code,
           s.approver_organization_pk, o.organization_name,
           s.step_status, s.decided_at, s.remarks, s.created_at,
           CONCAT_WS(' ', ap.first_name, ap.middle_name, ap.last_name)
    FROM nss.correspondence_approval_step s
    JOIN nss.person p ON p.person_pk = s.approver_person_pk
    JOIN nss.position_master pm ON pm.position_master_pk = s.approver_position_master_pk
    LEFT JOIN nss.organization o ON o.organization_pk = s.approver_organization_pk
    -- Display-only "Absent — Acting" lookup (owner ask #3, 2026-10-24):
    -- the seat this step's approver currently holds (bma), then any LIVE
    -- acting delegate covering that exact (body, position) pair (apa).
    -- Never touches step_status/approver_person_pk — authority/routing
    -- are untouched; this only tells the UI who is actually standing in.
    --
    -- LATERAL + LIMIT 1 (bug found 2026-10-26, surfaced by a test failure
    -- after a hard rebuild): approver_position_master_pk is a GENERIC
    -- catalog code (PRESIDENT/SECRETARY/...) shared across every body
    -- type, not body-specific — a plain JOIN on (person_pk,
    -- position_master_pk) fans out one row per body_member_assignment row
    -- that happens to match, for any approver who holds that same position
    -- code in more than one body (e.g. Sakha President who is ALSO a
    -- Kendra GB member — Kendra GB grants every member a composite role,
    -- not a position match here, but the same structural risk applies to
    -- any dual seat). Silently duplicated the whole step in the response —
    -- observed as the same correspondence_approval_step_pk returned 3
    -- times. LATERAL + LIMIT 1 picks at most one such body deterministically
    -- for this display-only lookup; it never affects step_status/
    -- approver_person_pk/routing.
    --
    -- "Live" means today falls inside [effective_from, effective_to], not
    -- "effective_to IS NULL" (bug found 2026-10-25 — a bounded-date
    -- delegation, e.g. "acting while I'm on leave this week", was wrongly
    -- excluded even on a day it was genuinely in effect; same fix as
    -- governance.py::_assemble_bodies_with_members).
    LEFT JOIN LATERAL (
        SELECT bma.body_master_pk
        FROM nss.body_member_assignment bma
        WHERE bma.person_pk = s.approver_person_pk
          AND bma.position_master_pk = s.approver_position_master_pk
          AND bma.is_active = TRUE AND bma.effective_to IS NULL
          AND bma.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')
        ORDER BY bma.effective_from DESC
        LIMIT 1
    ) bma ON TRUE
    LEFT JOIN LATERAL (
        SELECT apa.person_pk
        FROM nss.acting_position_assignment apa
        WHERE apa.body_master_pk = bma.body_master_pk
          AND apa.position_master_pk = s.approver_position_master_pk
          AND apa.is_active = TRUE AND apa.acting_status = 'ACTIVE'
          AND apa.effective_from <= CURRENT_DATE
          AND (apa.effective_to IS NULL OR apa.effective_to >= CURRENT_DATE)
        ORDER BY apa.effective_from DESC
        LIMIT 1
    ) apa ON TRUE
    LEFT JOIN nss.person ap ON ap.person_pk = apa.person_pk
    WHERE s.correspondence_pk = %s AND s.is_active = TRUE
    ORDER BY s.step_number
"""


def _fetch_approval_steps(cur, correspondence_pk: str) -> list[ApprovalStepResponse]:
    cur.execute(_APPROVAL_STEP_SELECT, (str(correspondence_pk),))
    return [
        ApprovalStepResponse(
            correspondence_approval_step_pk=r[0], correspondence_pk=r[1], step_number=r[2],
            approver_person_pk=r[3], approver_person_name=r[4].strip() if r[4] and r[4].strip() else None,
            approver_position_master_pk=r[5], approver_position_name=r[6], approver_position_code=r[7],
            approver_organization_pk=r[8], approver_organization_name=r[9],
            step_status=r[10], decided_at=r[11], remarks=r[12], created_at=r[13],
            acting_person_name=r[14].strip() if r[14] and r[14].strip() else None,
        )
        for r in cur.fetchall()
    ]



def _member_application_response(cur, correspondence_pk: str) -> MemberApplicationResponse:
    cur.execute(_DETAIL_SELECT + " WHERE c.correspondence_pk = %s", (str(correspondence_pk),))
    row = cur.fetchone()
    base = _row_to_response(row)
    return MemberApplicationResponse(**base.model_dump(), approval_steps=_fetch_approval_steps(cur, correspondence_pk))


def _require_active_member(user: UserContext) -> None:
    """Mirrors geo_approval.py's _require_actor_sangha_sevi_pk guard — a
    member must hold an active Sangha Sevi record to file a "Send
    Application" (only an active member's Sakha membership resolves to a
    register_organization_pk and a sender capacity to file from)."""
    if not user.sangha_sevi_pk or not user.person_pk:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has no active Sangha Sevi record, so it cannot send an application.",
        )


# ── POST /api/v1/correspondence/my-applications ─────────────────────────

@router.post("/my-applications", response_model=MemberApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_member_application(
    body: MemberApplicationCreate,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MemberApplicationResponse:
    """
    Member-initiated "Send Application" — self-service, login + active
    Sangha Sevi only (no CORRESPONDENCE_MANAGE check: a member files their
    own application, exactly like membership_change_request.py's
    create_change_request() self-service path). Always files OUTWARD,
    sender_type=PERSON/PERSONAL, under the member's own Sakha's register,
    medium=HAND_DELIVERY (filed through the member portal — the closest
    existing CORRESPONDENCE_MEDIUM value to an in-app submission; the
    medium catalogue itself is ERP-FROZEN per 01_correspondence.sql and is
    not extended here), status always starts REGISTERED (§6.1, unchanged).
    """
    _require_active_member(user)

    with conn.cursor() as cur:
        own_sakha_pk, _own_sakha_name = _home_sakha(cur, user.person_pk)
        if own_sakha_pk is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="You have no active Sakha affiliation to send an application from.",
            )

        recipient_type: str
        recipient_person_pk: str | None = None
        recipient_organization_pk: str | None = None
        routing_president_person_pk: str | None = None
        routing_president_position_pk: str | None = None
        routing_kendra_position_pk: str | None = None

        if body.addressing_mode == "SAKHA_ORG":
            recipient_type = "ORGANIZATION"
            recipient_organization_pk = own_sakha_pk

        elif body.addressing_mode == "SAKHA_OFFICE_BEARER":
            position_pk = _find_sakha_office_bearer_position(cur, own_sakha_pk, body.recipient_person_pk)
            if position_pk is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The selected person is not a current office-bearer of your Sakha.",
                )
            recipient_type = "PERSON"
            recipient_person_pk = str(body.recipient_person_pk)

        elif body.addressing_mode == "MAHILA_OFFICE_BEARER":
            # Gender-gated (owner-confirmed 2026-10-25) — checked here, at
            # the top of the branch, before any body/position lookup.
            _require_gender(cur, user.person_pk, "FEMALE", "MAHILA_OFFICE_BEARER")
            position_pk = _find_sakha_office_bearer_position(
                cur, own_sakha_pk, body.recipient_person_pk,
                body_type_codes=("MAHILA_PARICHALANA_MANDALI",),
            )
            if position_pk is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The selected person is not a current office-bearer of your Sakha's Mahila Parichalana Mandali.",
                )
            recipient_type = "PERSON"
            recipient_person_pk = str(body.recipient_person_pk)

        elif body.addressing_mode == "SEVAK_OFFICE_BEARER":
            _require_gender(cur, user.person_pk, "MALE", "SEVAK_OFFICE_BEARER")
            position_pk = _find_sakha_office_bearer_position(
                cur, own_sakha_pk, body.recipient_person_pk,
                body_type_codes=("SEVAK_SANGHA_EXECUTIVE",),
            )
            if position_pk is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The selected person is not a current office-bearer of your Sakha's Sevak Sangha Executive.",
                )
            recipient_type = "PERSON"
            recipient_person_pk = str(body.recipient_person_pk)

        elif body.addressing_mode == "KENDRA_MAHILA_VIA_SAKHA_PRESIDENT":
            _require_gender(cur, user.person_pk, "FEMALE", "KENDRA_MAHILA_VIA_SAKHA_PRESIDENT")
            kendra_body_pk = _find_body_master_pk(cur, "MAHILA_PARICHALANA_MANDALI", None)
            routing_kendra_position_pk = (
                _assignment_position_for_person(cur, kendra_body_pk, body.recipient_person_pk)
                if kendra_body_pk else None
            )
            if routing_kendra_position_pk is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The selected person is not a current office-bearer of the central Mahila Parichalana Mandali.",
                )

            sakha_gb_pk = _find_body_master_pk(cur, "SAKHA_GOVERNING_BODY", own_sakha_pk)
            president = _assignment_person_for_position(cur, sakha_gb_pk, "PRESIDENT") if sakha_gb_pk else None
            if president is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Your Sakha currently has no sitting President to route this application through.",
                )
            routing_president_person_pk, routing_president_position_pk = president

            recipient_type = "PERSON"
            recipient_person_pk = str(body.recipient_person_pk)

        else:  # KENDRA_VIA_SAKHA_PRESIDENT
            kendra_body_pk = _find_body_master_pk(cur, "KENDRA_GOVERNING_BODY", None)
            routing_kendra_position_pk = (
                _assignment_position_for_person(cur, kendra_body_pk, body.recipient_person_pk)
                if kendra_body_pk else None
            )
            if routing_kendra_position_pk is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The selected person is not a current Kendra-level office-bearer.",
                )

            sakha_gb_pk = _find_body_master_pk(cur, "SAKHA_GOVERNING_BODY", own_sakha_pk)
            president = _assignment_person_for_position(cur, sakha_gb_pk, "PRESIDENT") if sakha_gb_pk else None
            if president is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Your Sakha currently has no sitting President to route this application through.",
                )
            routing_president_person_pk, routing_president_position_pk = president

            recipient_type = "PERSON"
            recipient_person_pk = str(body.recipient_person_pk)

        today = date.today()
        reference_number = next_correspondence_reference_number(cur, own_sakha_pk, "OUTWARD", today)
        medium_pk = get_master_data_pk(cur, "CORRESPONDENCE_MEDIUM", "HAND_DELIVERY")
        status_pk = get_master_data_pk(cur, "CORRESPONDENCE_STATUS", "REGISTERED")
        sender_snapshot = _fetch_sender_sakha_snapshot(cur, "PERSON", user.person_pk)

        corr_pk = _insert_correspondence_row(
            cur,
            register_organization_pk=own_sakha_pk,
            reference_number=reference_number,
            direction="OUTWARD",
            correspondence_date=today,
            received_or_sent_date=today,
            follow_up_date=body.follow_up_date,
            subject=body.subject,
            remarks=body.remarks,
            sender_type="PERSON",
            sender_person_pk=str(user.person_pk),
            sender_organization_pk=None,
            sender_external_name=None,
            sender_external_organization=None,
            sender_person_capacity="PERSONAL",
            sender_person_organization_pk=None,
            sender_sakha_erp_id_snapshot=sender_snapshot,
            recipient_type=recipient_type,
            recipient_person_pk=recipient_person_pk,
            recipient_organization_pk=recipient_organization_pk,
            recipient_external_name=None,
            recipient_external_organization=None,
            # While a chain is pending, the Sakha President is who must act
            # next; otherwise there is no particular responsible party yet
            # (an admin assigns one later via the existing endpoint, §5.4).
            responsible_person_pk=routing_president_person_pk,
            responsible_organization_pk=None,
            medium_pk=medium_pk,
            status_pk=status_pk,
            actor_pk=user.actor_pk,
        )

        log_audit(
            cur, action="CREATE", table_name="correspondence", record_pk=corr_pk,
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary=f"Member application ({body.addressing_mode}) {reference_number}",
        )

        if body.addressing_mode in ("KENDRA_VIA_SAKHA_PRESIDENT", "KENDRA_MAHILA_VIA_SAKHA_PRESIDENT"):
            # Owner request, 2026-10-25: "if the two consecutive steps
            # approver is the same person... no need of one extra step".
            # routing_president_person_pk (step 1) is the SUBSTANTIVE Sakha
            # President; recipient_person_pk (step 2) is whoever the
            # applicant picked in the office-bearer picker — which, per
            # _assignment_position_for_person's contract, is already the
            # delegate's own person_pk when the real holder is absent and
            # covered. So this one equality check also correctly collapses
            # the "Sakha President is themselves currently acting for the
            # Kendra seat" case, not just the identical-person case.
            same_person_both_steps = (
                routing_president_person_pk is not None
                and recipient_person_pk is not None
                and str(routing_president_person_pk) == str(recipient_person_pk)
            )

            cur.execute(
                """
                INSERT INTO nss.correspondence_approval_step (
                    correspondence_pk, step_number, approver_person_pk,
                    approver_position_master_pk, approver_organization_pk,
                    step_status, created_by_sangha_sevi_pk
                ) VALUES (%s, 1, %s, %s, %s, 'PENDING', %s)
                RETURNING correspondence_approval_step_pk
                """,
                (corr_pk, routing_president_person_pk, routing_president_position_pk, own_sakha_pk, user.actor_pk),
            )
            step1_pk = cur.fetchone()[0]
            log_audit(
                cur, action="CREATE", table_name="correspondence_approval_step", record_pk=str(step1_pk),
                actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
                module="correspondence",
                summary=(
                    "Step 1: awaiting Sakha President decision (sole step — "
                    "step 1 approver is also the step-2 addressee)"
                    if same_person_both_steps else
                    "Step 1: awaiting Sakha President decision"
                ),
            )

            if not same_person_both_steps:
                cur.execute(
                    """
                    INSERT INTO nss.correspondence_approval_step (
                        correspondence_pk, step_number, approver_person_pk,
                        approver_position_master_pk, approver_organization_pk,
                        step_status, created_by_sangha_sevi_pk
                    ) VALUES (%s, 2, %s, %s, NULL, 'PENDING', %s)
                    RETURNING correspondence_approval_step_pk
                    """,
                    (corr_pk, recipient_person_pk, routing_kendra_position_pk, user.actor_pk),
                )
                step2_pk = cur.fetchone()[0]
                log_audit(
                    cur, action="CREATE", table_name="correspondence_approval_step", record_pk=str(step2_pk),
                    actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
                    module="correspondence",
                    summary="Step 2: not yet visible to the Kendra office-bearer (pending step 1)",
                )

        response = _member_application_response(cur, corr_pk)

    return response


# ── GET /api/v1/correspondence/my-applications ──────────────────────────

@router.get("/my-applications", response_model=MemberApplicationListResponse)
def list_my_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> MemberApplicationListResponse:
    """The calling member's own submitted "Send Application" history — self
    view only, mirroring membership_change_request.py's self-scoped list."""
    if not user.person_pk:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No person record for this account.")

    offset = (page - 1) * page_size
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM nss.correspondence WHERE sender_person_pk = %s AND is_active = TRUE",
            (str(user.person_pk),),
        )
        total = cur.fetchone()[0]

        cur.execute(
            """
            SELECT correspondence_pk FROM nss.correspondence
            WHERE sender_person_pk = %s AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (str(user.person_pk), page_size, offset),
        )
        pks = [r[0] for r in cur.fetchall()]
        items = [_member_application_response(cur, pk) for pk in pks]

    return MemberApplicationListResponse(items=items, total=total)


# ── GET /api/v1/correspondence/my-applications/{pk} ─────────────────────

@router.get("/my-applications/{correspondence_pk:uuid}", response_model=MemberApplicationResponse)
def get_my_application(
    correspondence_pk: UUID,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> MemberApplicationResponse:
    """Full detail of one of the caller's own applications — 404 (not 403) if
    it exists but belongs to someone else, so existence is never leaked."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sender_person_pk FROM nss.correspondence WHERE correspondence_pk = %s AND is_active = TRUE",
            (str(correspondence_pk),),
        )
        row = cur.fetchone()
        if row is None or user.person_pk is None or str(row[0]) != str(user.person_pk):
            raise HTTPException(status_code=404, detail="Application not found.")

        return _member_application_response(cur, str(correspondence_pk))


# ── GET /api/v1/correspondence/addressed-to-me ───────────────────────────

@router.get("/addressed-to-me", response_model=MemberApplicationListResponse)
def list_addressed_to_me(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> MemberApplicationListResponse:
    """
    Applications currently addressed to the caller as recipient_person_pk —
    this IS the approval-chain visibility gate, implemented as a pure
    read-time filter (fixed 2026-10-22; see the root-cause note above the
    "Member Send Application" section): a directly-addressed application
    (mode a/b has no chain, or mode c has no step-1 row) is always
    included; a KENDRA_VIA_SAKHA_PRESIDENT application is only included
    once its OWN step 1 — the Sakha President's decision — is APPROVED.
    Step 2's own step_status is never consulted here and is never mutated
    to fake this gate; it reflects step 2's real, independent decision
    (see decide_approval_step()). Login-only, like the governance
    /public/* endpoints.
    """
    if not user.person_pk:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No person record for this account.")

    visibility_clause = """
        NOT EXISTS (
            SELECT 1 FROM nss.correspondence_approval_step s1
            WHERE s1.correspondence_pk = c.correspondence_pk AND s1.step_number = 1 AND s1.is_active = TRUE
        )
        OR EXISTS (
            SELECT 1 FROM nss.correspondence_approval_step s1
            WHERE s1.correspondence_pk = c.correspondence_pk AND s1.step_number = 1
              AND s1.is_active = TRUE AND s1.step_status = 'APPROVED'
        )
    """

    offset = (page - 1) * page_size
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*) FROM nss.correspondence c
            WHERE c.recipient_person_pk = %s AND c.is_active = TRUE AND ({visibility_clause})
            """,
            (str(user.person_pk),),
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT c.correspondence_pk FROM nss.correspondence c
            WHERE c.recipient_person_pk = %s AND c.is_active = TRUE AND ({visibility_clause})
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (str(user.person_pk), page_size, offset),
        )
        pks = [r[0] for r in cur.fetchall()]
        items = [_member_application_response(cur, pk) for pk in pks]

    return MemberApplicationListResponse(items=items, total=total)


# ── GET /api/v1/correspondence/approval-steps/pending-for-me ────────────

_PENDING_FOR_ME_JOIN = """
    JOIN nss.correspondence_approval_step s ON s.correspondence_pk = c.correspondence_pk
    WHERE s.step_status = 'PENDING' AND s.is_active = TRUE
      AND s.approver_person_pk = %s AND c.is_active = TRUE
      AND (
          s.step_number = 1
          OR (
              s.step_number = 2
              AND EXISTS (
                  SELECT 1 FROM nss.correspondence_approval_step s1
                  WHERE s1.correspondence_pk = s.correspondence_pk AND s1.step_number = 1
                    AND s1.is_active = TRUE AND s1.step_status = 'APPROVED'
              )
          )
      )
"""


@router.get("/approval-steps/pending-for-me", response_model=MemberApplicationListResponse)
def list_pending_approvals_for_me(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> MemberApplicationListResponse:
    """
    Applications awaiting the caller's own decision — step 1 (the Sakha
    President's decision, always eligible once PENDING) or step 2 (the
    Kendra office-bearer's decision, eligible only once step 1 is already
    APPROVED — same precondition decide_approval_step() enforces for a real
    decision, so a step 2 row never appears here before it is actually
    actionable). Login-only — gated by approver_person_pk = caller, not a
    permission; the decision endpoint below re-verifies the caller is
    still the seated authority before allowing the actual decision.
    """
    if not user.person_pk:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No person record for this account.")

    offset = (page - 1) * page_size
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(DISTINCT c.correspondence_pk) FROM nss.correspondence c {_PENDING_FOR_ME_JOIN}",
            (str(user.person_pk),),
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT DISTINCT c.correspondence_pk, c.created_at FROM nss.correspondence c
            {_PENDING_FOR_ME_JOIN}
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (str(user.person_pk), page_size, offset),
        )
        pks = [r[0] for r in cur.fetchall()]
        items = [_member_application_response(cur, pk) for pk in pks]

    return MemberApplicationListResponse(items=items, total=total)


# ── POST /api/v1/correspondence/approval-steps/{pk}/decision ────────────

def _require_captured_identity(user: UserContext, approver_person_pk) -> None:
    """Both steps' decision identity must match who was actually asked at
    creation time — a necessary but not sufficient check, see the live
    seat re-verification that follows it for each step."""
    if user.person_pk is None or str(approver_person_pk) != str(user.person_pk):
        raise HTTPException(status_code=403, detail="This application is not awaiting your decision.")


def _require_seated_sakha_president(cur, user: UserContext, approver_org_pk) -> None:
    sakha_gb_pk = _find_body_master_pk(cur, "SAKHA_GOVERNING_BODY", approver_org_pk)
    if sakha_gb_pk is None or not _active_office_bearer(cur, sakha_gb_pk, user.person_pk, position_code="PRESIDENT"):
        raise HTTPException(
            status_code=403,
            detail="You are no longer the seated President of this Sakha, so you cannot act on this application.",
        )


_CENTRAL_BODY_TYPES_FOR_STEP2 = ("KENDRA_GOVERNING_BODY", "MAHILA_PARICHALANA_MANDALI")


def _require_seated_central_office_bearer(cur, user: UserContext) -> None:
    """Step 2's own authority check (PART 1) — the caller must currently
    hold SOME active, non-MEMBER office-bearer seat on one of the central
    (NSS-wide, organization_pk IS NULL) bodies that route through this
    2-step chain, mirroring how step 1 re-verifies the Sakha President
    rather than trusting the approver_person_pk captured at creation time
    alone.

    Generalized 2026-10-25 from a Kendra-Governing-Body-only check (the
    original KENDRA_VIA_SAKHA_PRESIDENT mode's only step-2 target) to also
    cover the central Mahila Parichalana Mandali (KENDRA_MAHILA_VIA_
    SAKHA_PRESIDENT's step-2 target) — found while wiring up the new mode:
    correspondence_approval_step does not itself record which body a given
    step 2 targets (no DDL change was made for this, per task scope), so
    re-verification tries each candidate central body type in turn rather
    than assuming Kendra Governing Body specifically. Step-2 CREATION
    (create_member_application) already resolved the right body directly
    from the addressing_mode and needed no change; only this decision-time
    re-verification had the hardcoded assumption."""
    for body_type_code in _CENTRAL_BODY_TYPES_FOR_STEP2:
        body_pk = _find_body_master_pk(cur, body_type_code, None)
        if body_pk and _active_office_bearer(cur, body_pk, user.person_pk):
            return
    raise HTTPException(
        status_code=403,
        detail="You are no longer a seated central-level office-bearer, so you cannot act on this application.",
    )


@router.post("/approval-steps/{step_pk:uuid}/decision", response_model=MemberApplicationResponse)
def decide_approval_step(
    step_pk: UUID,
    body: ApprovalStepDecisionRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> MemberApplicationResponse:
    """
    Decide a pending approval-chain step — step 1 (the Sakha President) or,
    fixed 2026-10-22 (PART 1 root-cause fix), step 2 (the Kendra
    office-bearer) now has a genuine decision of its own too, instead of
    being auto-approved by the API the moment step 1 was approved.

    Both steps require: the caller matches the approver_person_pk captured
    at creation time (_require_captured_identity), AND the caller is still
    the actual seated authority at decision time — step 1 via the Sakha
    Governing Body/PRESIDENT, step 2 via one of the central (NSS-wide)
    governance bodies/any office-bearer seat (_require_seated_sakha_president /
    _require_seated_central_office_bearer) — never a stored PK trusted
    blindly. Step 2 additionally requires step 1 to already be APPROVED;
    it can never be decided before that (422 otherwise).

    On step 1 APPROVE: no status change (§6.2 untouched) — only
    responsible_person_pk is reassigned to the step-2 approver, who is now
    the one who must act (§5.4 semantics). step 2 itself stays PENDING —
    it is now visible/actionable (see list_addressed_to_me/
    list_pending_approvals_for_me), not pre-decided.
    On step 1 REJECT: the chain stops; responsible_person_pk is cleared.

    On step 2 APPROVE: this is the chain's actual terminal approval. If the
    correspondence is still at its initial REGISTERED status, this moves it
    to PENDING_ACTION (§6.2's own REGISTERED -> PENDING_ACTION transition —
    its precondition, a populated responsible_person_pk, is already
    satisfied by step 1's approval) via the same _set_correspondence_status()
    helper transition_status() uses, so the §6.2 table is never duplicated
    or bypassed. If the record's status has since moved on some other way,
    status is left untouched here — this endpoint only ever applies that
    one specific, already-valid transition, never an arbitrary one.
    responsible_person_pk is (re)confirmed to the step-2 approver.
    On step 2 REJECT: mirrors step 1's reject — responsible_person_pk is
    cleared, no status change.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT correspondence_pk, step_number, approver_person_pk,
                   approver_organization_pk, step_status
            FROM nss.correspondence_approval_step
            WHERE correspondence_approval_step_pk = %s AND is_active = TRUE
            """,
            (str(step_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Approval step not found.")
        corr_pk, step_number, approver_person_pk, approver_org_pk, step_status_current = row

        if step_number not in (1, 2):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown step number.")
        if step_status_current != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"This step is already {step_status_current}.",
            )

        _require_captured_identity(user, approver_person_pk)

        if step_number == 1:
            _require_seated_sakha_president(cur, user, approver_org_pk)
        else:
            cur.execute(
                """
                SELECT step_status FROM nss.correspondence_approval_step
                WHERE correspondence_pk = %s AND step_number = 1 AND is_active = TRUE
                """,
                (corr_pk,),
            )
            step1_row = cur.fetchone()
            if step1_row is None or step1_row[0] != "APPROVED":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Step 2 cannot be decided before step 1 has been approved.",
                )
            _require_seated_central_office_bearer(cur, user)

        new_status = "APPROVED" if body.decision == "APPROVE" else "REJECTED"
        cur.execute(
            """
            UPDATE nss.correspondence_approval_step
            SET step_status = %s, decided_at = NOW(), remarks = %s,
                updated_at = NOW(), updated_by_sangha_sevi_pk = %s
            WHERE correspondence_approval_step_pk = %s
            """,
            (new_status, body.remarks, user.actor_pk, str(step_pk)),
        )
        log_audit(
            cur, action="APPROVE" if body.decision == "APPROVE" else "REJECT",
            table_name="correspondence_approval_step", record_pk=str(step_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="correspondence",
            summary=f"Step {step_number} {body.decision.lower()}d",
            detail={"remarks": body.remarks} if body.remarks else None,
        )

        if step_number == 1:
            if body.decision == "APPROVE":
                cur.execute(
                    """
                    SELECT approver_person_pk FROM nss.correspondence_approval_step
                    WHERE correspondence_pk = %s AND step_number = 2 AND is_active = TRUE
                    """,
                    (corr_pk,),
                )
                step2 = cur.fetchone()
                if step2:
                    cur.execute(
                        """
                        UPDATE nss.correspondence
                        SET responsible_person_pk = %s, updated_at = NOW(), updated_by_sangha_sevi_pk = %s
                        WHERE correspondence_pk = %s
                        """,
                        (str(step2[0]), user.actor_pk, corr_pk),
                    )
                else:
                    # No step 2 exists — a collapsed single-step chain
                    # (owner request, 2026-10-25: the step-2 addressee was
                    # the same person as this step-1 approver, so creation
                    # never inserted a redundant second step). Step 1's own
                    # approval is therefore this chain's terminal decision —
                    # mirrors step_number == 2's APPROVE branch exactly.
                    # responsible_person_pk is already this approver (set at
                    # creation and never changed since), so no UPDATE is
                    # needed for it here.
                    cur.execute(
                        """
                        SELECT status_md.value_code FROM nss.correspondence c
                        JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
                        WHERE c.correspondence_pk = %s
                        """,
                        (corr_pk,),
                    )
                    current_status = cur.fetchone()[0]
                    if current_status == "REGISTERED":
                        _set_correspondence_status(cur, corr_pk, "PENDING_ACTION", remarks=None, actor_pk=user.actor_pk)
            else:
                cur.execute(
                    """
                    UPDATE nss.correspondence
                    SET responsible_person_pk = NULL, updated_at = NOW(), updated_by_sangha_sevi_pk = %s
                    WHERE correspondence_pk = %s
                    """,
                    (user.actor_pk, corr_pk),
                )
        else:  # step_number == 2 — the chain's terminal decision
            if body.decision == "APPROVE":
                cur.execute(
                    """
                    SELECT status_md.value_code FROM nss.correspondence c
                    JOIN nss.master_data status_md ON status_md.master_data_pk = c.status_master_data_pk
                    WHERE c.correspondence_pk = %s
                    """,
                    (corr_pk,),
                )
                current_status = cur.fetchone()[0]
                cur.execute(
                    """
                    UPDATE nss.correspondence
                    SET responsible_person_pk = %s, updated_at = NOW(), updated_by_sangha_sevi_pk = %s
                    WHERE correspondence_pk = %s
                    """,
                    (str(approver_person_pk), user.actor_pk, corr_pk),
                )
                if current_status == "REGISTERED":
                    _set_correspondence_status(cur, corr_pk, "PENDING_ACTION", remarks=None, actor_pk=user.actor_pk)
            else:
                cur.execute(
                    """
                    UPDATE nss.correspondence
                    SET responsible_person_pk = NULL, updated_at = NOW(), updated_by_sangha_sevi_pk = %s
                    WHERE correspondence_pk = %s
                    """,
                    (user.actor_pk, corr_pk),
                )

        response = _member_application_response(cur, corr_pk)

    return response


# ═════════════════════════════════════════════════════════════════════
# "Involved-in" history (PART 3, owner item 2, 2026-10-22)
# ═════════════════════════════════════════════════════════════════════

@router.get("/my-involvements", response_model=MemberApplicationListResponse)
def list_my_involvements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> MemberApplicationListResponse:
    """
    Every correspondence row the calling person is attached to in ANY
    capacity — sender, recipient, current responsible party, or an
    approver at any step (1 or 2) of the approval chain — so a person never
    loses sight of something they were involved in, even after their role
    in it (e.g. "responsible party") has moved on to someone else. A new,
    dedicated endpoint rather than a param on list_my_applications():
    list_my_applications() is specifically "things I sent" (sender_person_pk
    only); this is strictly broader and follows the same one-purpose-per-
    path convention as /addressed-to-me and /approval-steps/pending-for-me
    below. Login-only, self-view (get_current_user, no permission
    dependency) — same pattern as list_my_applications().

    Reuses _member_application_response() (hence CorrespondenceResponse's
    full field set plus approval_steps) for every row — no duplicated
    response-shaping SQL.

    Unlike /addressed-to-me, this is a historical "was/am I involved" view,
    not an actionability view — it does NOT apply the step-2 visibility
    gate; a Kendra office-bearer named on a still-pending step 2 sees that
    application here immediately, even before step 1 is approved.
    """
    if not user.person_pk:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No person record for this account.")

    involvement_clause = """
        WHERE c.is_active = TRUE AND (
            c.sender_person_pk = %s
            OR c.recipient_person_pk = %s
            OR c.responsible_person_pk = %s
            OR EXISTS (
                SELECT 1 FROM nss.correspondence_approval_step s
                WHERE s.correspondence_pk = c.correspondence_pk
                  AND s.is_active = TRUE AND s.approver_person_pk = %s
            )
        )
    """

    offset = (page - 1) * page_size
    person_pk = str(user.person_pk)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM nss.correspondence c {involvement_clause}",
            (person_pk, person_pk, person_pk, person_pk),
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT c.correspondence_pk FROM nss.correspondence c
            {involvement_clause}
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (person_pk, person_pk, person_pk, person_pk, page_size, offset),
        )
        pks = [r[0] for r in cur.fetchall()]
        items = [_member_application_response(cur, pk) for pk in pks]

    return MemberApplicationListResponse(items=items, total=total)

