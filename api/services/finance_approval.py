"""
NSS ERP — Sakha approval chain for Finance transactions (owner decision 2026-11-17).

ONE home for the rules that decide who may approve a Sakha's (or Sakha Asana's) income / expense entry, so the endpoints, the
member dashboard list and the tests share a single implementation.

The rules (Sakha / Sakha Asana only; Kendra and central Mahila money keep the Bye-Law controls in finance_authority.py and every
other level has no rule here, FIN-BR-044):

  1. Every entry is booked under a FINANCE HEAD.
  2. INCOME on a head flagged ``skips_approval`` (Pranami, Parichaya Patra, Anumati Patra, subscription ...) needs NO approval:
     it posts when it is submitted.
  3. Every other entry is approved by the office-bearers SEATED on the Sakha Governing Body, in order:
       step 1  the TREASURER (always first);
       step 2  the PRESIDENT - or, when no President is seated and no acting President covers, the SECRETARY.
  4. The Treasurer approves ALONE (step 1 only) an EXPENSE up to the head's ``treasurer_limit``, else the Sakha's default limit
     (finance_approval_policy). A head with no limit and no default always needs step 2 as well. Income that needs approval
     (a head not flagged) always needs both steps.
  5. Every EXPENSE is supported by bills (finance_transaction_bill) that add up to its amount; a reimbursement head
     (``requires_member``) must also name the member who paid.
  6. The authority is the SEAT held at the moment of deciding (acting cover counts), never a permission and never the super
     administrator, so there is no override; a vacant Treasurer seat blocks the entry until it is filled. The Treasurer may
     approve an entry they recorded themselves (it is their office's spending authority); the President / Secretary may not, and
     the step-2 approver must be a different person from the step-1 approver.

Every decision is a ``finance_approval_step`` row (who, in which office, when, why a Secretary stood in) AND an audit event.
Nothing here commits.
"""

from decimal import Decimal

from fastapi import HTTPException, status

from api.helpers import SAKHA_LIKE_ORG_TYPES_SQL, log_audit
from api.services import seat_service

BODY_TYPE = "SAKHA_GOVERNING_BODY"
TREASURER, PRESIDENT, SECRETARY = "TREASURER", "PRESIDENT", "SECRETARY"
STAGE_LABEL = {1: "Treasurer", 2: "President"}

REQUIRES_NONE = "NONE"
REQUIRES_TREASURER = "TREASURER"
REQUIRES_BOTH = "TREASURER_THEN_PRESIDENT"


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# ═══════════════════════════════════════════════════════════════════════
# Pure rules (no database)
# ═══════════════════════════════════════════════════════════════════════

def requirement(txn_type: str, amount: Decimal, skips_approval: bool, limit: Decimal | None) -> str:
    """Which approvals an entry needs: NONE, TREASURER (alone) or TREASURER_THEN_PRESIDENT."""
    if txn_type == "INCOME" and skips_approval:
        return REQUIRES_NONE
    if txn_type == "EXPENSE" and limit is not None and amount <= limit:
        return REQUIRES_TREASURER
    return REQUIRES_BOTH


def stages_for(required: str) -> list[int]:
    return {REQUIRES_NONE: [], REQUIRES_TREASURER: [1], REQUIRES_BOTH: [1, 2]}[required]


def bills_problem(txn_type: str, amount: Decimal, bills_total: Decimal, bill_count: int) -> str | None:
    """Why the bills do not support this entry (None = fine). Only an EXPENSE needs bills."""
    if txn_type != "EXPENSE":
        return None
    if bill_count == 0:
        return "Every spend needs at least one bill: add the bill details before submitting."
    if bills_total != amount:
        return f"The bills add up to {bills_total:,.2f} but the spend is {amount:,.2f}; they must be equal."
    return None


# ═══════════════════════════════════════════════════════════════════════
# Which entries does the chain govern?
# ═══════════════════════════════════════════════════════════════════════

def is_chain_org(cur, organization_pk) -> bool:
    """True for a Sakha Sangha / Sakha Asana: the only organizations this chain governs."""
    if organization_pk is None:
        return False
    cur.execute(
        "SELECT 1 FROM nss.organization o JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk "
        f"WHERE o.organization_pk = %s AND md.value_code IN {SAKHA_LIKE_ORG_TYPES_SQL}",
        (str(organization_pk),),
    )
    return cur.fetchone() is not None


def default_limit(cur, organization_pk) -> Decimal | None:
    cur.execute(
        "SELECT default_treasurer_limit FROM nss.finance_approval_policy WHERE organization_pk = %s AND is_active = TRUE",
        (str(organization_pk),),
    )
    row = cur.fetchone()
    return row[0] if row else None


def effective_limit(cur, head: dict, organization_pk) -> Decimal | None:
    """The amount the Treasurer may approve alone for this head: its own limit, else the Sakha default, else None."""
    if head.get("treasurer_limit") is not None:
        return head["treasurer_limit"]
    return default_limit(cur, organization_pk)


def _head(cur, head_pk) -> dict:
    cur.execute(
        "SELECT finance_head_pk, head_code, head_name, direction, skips_approval, treasurer_limit, requires_member "
        "FROM nss.finance_head WHERE finance_head_pk = %s",
        (str(head_pk),),
    )
    row = cur.fetchone()
    return dict(zip(("finance_head_pk", "head_code", "head_name", "direction", "skips_approval", "treasurer_limit", "requires_member"), row))


def bills_summary(cur, txn_pk) -> tuple[Decimal, int]:
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM nss.finance_transaction_bill WHERE financial_transaction_pk = %s AND is_active = TRUE",
        (str(txn_pk),),
    )
    total, count = cur.fetchone()
    return total, count


def submit_problems(cur, txn: dict, organization_pk) -> str | None:
    """What stops a Sakha entry from being SUBMITTED for approval (None = nothing): bills and, for a reimbursement, the member."""
    head = _head(cur, txn["finance_head_pk"])
    total, count = bills_summary(cur, txn["financial_transaction_pk"])
    problem = bills_problem(txn["transaction_type"], txn["amount"], total, count)
    if problem:
        return problem
    if head["requires_member"] and txn.get("person_pk") is None and txn.get("sangha_sevi_pk") is None:
        return f"{head['head_name']} repays a member: name the member who paid before submitting."
    return None


# ═══════════════════════════════════════════════════════════════════════
# Seats
# ═══════════════════════════════════════════════════════════════════════

def _body_pk(cur, organization_pk) -> str | None:
    return seat_service.find_body_master_pk(cur, BODY_TYPE, organization_pk)


def require_not_the_treasurer(cur, user, organization_pk, what: str) -> None:
    """
    Owner 2026-11-20: the seated (or acting) Treasurer of a Sakha may configure its finance (heads, contributions, events, accounts) but never the
    controls that bind THEMSELVES - their approval limit and a head's "needs no approval" flag - so they cannot loosen their own check. 403 when the
    caller holds the Treasurer seat of *organization_pk* (a Sakha); a no-op for any other caller or organization. By SEAT, like the approval chain
    itself: a Sakha admin who is not the Treasurer (the President / Secretary) sets these.
    """
    if organization_pk is None or getattr(user, "person_pk", None) is None:
        return
    body = _body_pk(cur, organization_pk)
    if body is None:
        return
    holder = seat_service.live_seat_holder(cur, body, TREASURER)
    if holder and str(holder[0]) == str(user.person_pk):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"The Treasurer cannot change {what}; the Sakha's President or Secretary sets it.")


FINANCE_OFFICES = (TREASURER, PRESIDENT, SECRETARY)


def office_sakhas(cur, person_pk) -> set[str]:
    """
    The Sakhas (organization_pks) whose Governing Body seats this person holds as TREASURER, PRESIDENT or SECRETARY right now - substantively
    or as acting cover (owner 2026-11-22: they are the finance administrators of their own Sakha, "they head the finance department", by seat).
    """
    if person_pk is None:
        return set()
    held: set[str] = set()
    for position in FINANCE_OFFICES:
        held |= seat_service.seat_body_pks_held(cur, person_pk, position)
    if not held:
        return set()
    cur.execute(
        """
        SELECT bm.organization_pk
          FROM nss.body_master bm
          JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
         WHERE bm.body_master_pk = ANY(%s::uuid[]) AND bt.body_type_code = %s AND bm.organization_pk IS NOT NULL AND bm.is_active = TRUE
        """,
        (sorted(held), BODY_TYPE),
    )
    return {str(r[0]) for r in cur.fetchall()}


def approver_for_stage(cur, organization_pk, stage: int) -> dict | None:
    """
    Who may take *stage* right now: {person_pk, position_code, cover_reason} or None when nobody sits there.
    Stage 2 is the President (an acting President counts, flagged ACTING_COVER); with no President at all the Secretary.
    """
    body = _body_pk(cur, organization_pk)
    if body is None:
        return None
    if stage == 1:
        holder = seat_service.live_seat_holder(cur, body, TREASURER)
        return {"person_pk": holder[0], "position_code": TREASURER, "cover_reason": "ACTING_COVER" if holder[2] else None} if holder else None
    holder = seat_service.live_seat_holder(cur, body, PRESIDENT)
    if holder:
        return {"person_pk": holder[0], "position_code": PRESIDENT, "cover_reason": "ACTING_COVER" if holder[2] else None}
    holder = seat_service.live_seat_holder(cur, body, SECRETARY)
    if holder:
        return {"person_pk": holder[0], "position_code": SECRETARY, "cover_reason": "PRESIDENT_SEAT_VACANT"}
    return None


# ═══════════════════════════════════════════════════════════════════════
# State of one entry
# ═══════════════════════════════════════════════════════════════════════

def _steps(cur, txn_pk) -> list[dict]:
    cur.execute(
        """
        SELECT s.step_no, s.position_code, s.decision, s.decided_at, s.remarks, s.cover_reason,
               s.decided_by_person_pk, NULLIF(TRIM(CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)), '') AS decided_by_name
          FROM nss.finance_approval_step s
          JOIN nss.person p ON p.person_pk = s.decided_by_person_pk
         WHERE s.financial_transaction_pk = %s AND s.is_active = TRUE
         ORDER BY s.step_no
        """,
        (str(txn_pk),),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def creator_person(cur, created_by_sangha_sevi_pk) -> str | None:
    if created_by_sangha_sevi_pk is None:
        return None
    cur.execute("SELECT person_pk FROM nss.sangha_sevi WHERE sangha_sevi_pk = %s", (str(created_by_sangha_sevi_pk),))
    row = cur.fetchone()
    return str(row[0]) if row else None


def state(cur, txn: dict, organization_pk) -> dict:
    """
    Where an entry stands in the chain: what it needs, what is done, and who must act next. ``txn`` needs transaction_type,
    amount, status, finance_head_pk, financial_transaction_pk. Always safe to call; a non-Sakha entry reports applies=False.
    """
    out = {"applies": False, "requires": None, "limit": None, "steps": [], "next_stage": None, "next_position": None,
           "next_person_pk": None, "next_cover_reason": None, "complete": False, "blocked_reason": None}
    if not is_chain_org(cur, organization_pk):
        return out
    head = _head(cur, txn["finance_head_pk"])
    limit = effective_limit(cur, head, organization_pk) if txn["transaction_type"] == "EXPENSE" else None
    required = requirement(txn["transaction_type"], txn["amount"], head["skips_approval"], limit)
    steps = _steps(cur, txn["financial_transaction_pk"])
    out.update(applies=True, requires=required, limit=limit, steps=steps)
    needed = stages_for(required)
    done = {s["step_no"] for s in steps if s["decision"] == "APPROVED"}
    pending = [n for n in needed if n not in done]
    if not pending:
        out["complete"] = True
        return out
    stage = pending[0]
    who = approver_for_stage(cur, organization_pk, stage)
    out.update(next_stage=stage)
    if who is None:
        out["blocked_reason"] = (f"The Treasurer seat of this Sakha is vacant, so nobody can approve yet." if stage == 1
                                 else "Neither the President nor the Secretary seat of this Sakha is filled, so nobody can give the second approval yet.")
    else:
        out.update(next_position=who["position_code"], next_person_pk=who["person_pk"], next_cover_reason=who["cover_reason"])
    return out


# ═══════════════════════════════════════════════════════════════════════
# Deciding
# ═══════════════════════════════════════════════════════════════════════

def _audit(cur, user, action: str, txn: dict, summary: str, detail: dict) -> None:
    log_audit(
        cur, action=action, table_name="financial_transaction", record_pk=str(txn["financial_transaction_pk"]),
        actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk), module="finance", summary=summary, detail=detail,
    )


def decide(cur, user, txn: dict, organization_pk, decision: str, remarks: str | None) -> dict:
    """
    Record the caller's APPROVE / REJECT of the next step. Returns {"final": "APPROVED" | "REJECTED" | None, "step": {...}}:
    "APPROVED" means that was the last required step (the caller then posts the entry), None that one more step is due.
    Raises 403 when the caller is not the person who may act now, 422 when the entry is not waiting for this.
    """
    if txn["status"] != "PENDING_APPROVAL":
        raise _invalid(f"The entry is {txn['status']}; only an entry waiting for approval can be decided.")
    st = state(cur, txn, organization_pk)
    if not st["applies"]:
        raise _invalid("This entry is not governed by the Sakha approval chain.")
    if st["requires"] == REQUIRES_NONE:
        raise _invalid("This entry needs no approval.")
    if st["complete"]:
        raise _invalid("This entry has already been approved.")
    problem = submit_problems(cur, txn, organization_pk)
    if problem and decision == "APPROVED":
        raise _invalid(problem)
    stage = st["next_stage"]
    if st["next_person_pk"] is None:
        raise _invalid(st["blocked_reason"])
    if str(user.person_pk) != str(st["next_person_pk"]):
        raise _forbidden(f"Only the {STAGE_LABEL[stage]} of this Sakha (the person now holding that seat) can take this step.")
    maker = creator_person(cur, txn.get("created_by_sangha_sevi_pk"))
    done = [s for s in st["steps"] if s["decision"] == "APPROVED"]
    if stage == 2:
        if maker is not None and maker == str(user.person_pk):
            raise _forbidden("You recorded this entry, so another office-bearer must give this approval.")
        if any(str(s["decided_by_person_pk"]) == str(user.person_pk) for s in done):
            raise _forbidden("The second approval must come from a different person than the first.")
    if decision == "REJECTED" and not (remarks and remarks.strip()):
        raise _invalid("A rejection needs a reason.")
    position = st["next_position"]
    cur.execute(
        """
        INSERT INTO nss.finance_approval_step
            (financial_transaction_pk, step_no, position_code, decision, decided_by_person_pk, remarks, cover_reason,
             created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_approval_step_pk
        """,
        (str(txn["financial_transaction_pk"]), stage, position, decision, str(user.person_pk), (remarks or "").strip() or None,
         st["next_cover_reason"], user.actor_pk),
    )
    step_pk = cur.fetchone()[0]
    detail = {"step_no": stage, "position": position, "decision": decision, "cover_reason": st["next_cover_reason"],
              "remarks": (remarks or "").strip() or None, "requires": st["requires"],
              "treasurer_recorded_it": bool(maker and maker == str(user.person_pk) and stage == 1)}
    _audit(cur, user, "APPROVE" if decision == "APPROVED" else "REJECT", txn,
           f"{position.title()} {decision.lower()} {txn['transaction_reference']} (step {stage})", detail)
    last = stages_for(st["requires"])[-1]
    final = None
    if decision == "REJECTED":
        final = "REJECTED"
    elif stage == last:
        final = "APPROVED"
    return {"final": final, "step_pk": str(step_pk), "stage": stage, "position": position}
