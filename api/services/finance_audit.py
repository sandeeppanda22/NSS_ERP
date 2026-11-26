"""
NSS ERP — the Kendra's annual audit (Bye-Law Section G, REF-003-G; owner request 2026-11-26).

ONE home for the rules, so the endpoints and the tests share a single implementation. The Bye-Law, in one sentence: the Accounts of the Kendra
Sangha are audited every year by a qualified Auditor appointed by the Governing Body; the Audit Report is placed first before the Governing Body,
then in the combined meeting of the Governing Body and the Advisory Board for their approval, and only after that does the Secretary place it
before the General Body.

  APPOINTED ──report──▶ REPORT_RECEIVED ──Governing Body──▶ PLACED_BEFORE_GB ──combined meeting approves──▶ APPROVED ──General Body──▶ PLACED_BEFORE_GENERAL_BODY

  * Every step is a recorded FACT (a date and a reference), none can be skipped, and the dates keep that order and are never in the future.
  * The Kendra only. Nothing is invented for any other level (FIN-BR-044); the central Mahila Sangha's audit (REF-MS-9, Section J) is a separate rule.
  * The financial year's status gates NOTHING (owner 2026-11-26): the audit may run while the year is open, closing or closed.
  * Placing the report before the Governing Body files a numbered OUTWARD letter Kendra -> Advisory Board in the Correspondence register (the
    router does this through the same code as POST /correspondence), so the Advisory Board has the report for the combined meeting.
  * The Auditor is recorded as free text (name, optional firm); the report as a reference + date + optional https link (the app has no file upload).
  * Bye-Law clause 17: the Parichalak's personal expenditure (discretionary grant) "will not be subject to any audit". It is kept OUT of the audit
    workflow and only SHOWN as not subject to audit (``EXEMPT_PURPOSES``, ``exempt_payments``); nothing here blocks or counts it.
  * A recorded text can be corrected with a reason (status unchanged, old and new text in the audit event); nothing else moves backwards.

Nothing here commits and nothing checks WHO may act: the router does that (permission + admin scope), like the other Finance routers.
"""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status

from api.services import finance_authority as FA

APPOINTED, REPORT_RECEIVED, PLACED_BEFORE_GB, APPROVED, PLACED_BEFORE_GENERAL_BODY = (
    "APPOINTED", "REPORT_RECEIVED", "PLACED_BEFORE_GB", "APPROVED", "PLACED_BEFORE_GENERAL_BODY")

# Statuses live in api/schemas/finance.py (AUDIT_STATUSES, parity-tested against the DDL CHECK); the order is the order of the steps.
STEP_ORDER = (APPOINTED, REPORT_RECEIVED, PLACED_BEFORE_GB, APPROVED, PLACED_BEFORE_GENERAL_BODY)

# Bye-Law clause 17: not subject to any audit. DISBURSEMENT_PURPOSE value codes.
EXEMPT_PURPOSES = ("KENDRA_PARICHALAK_EXPENDITURE",)
EXEMPT_NOTE = ("Bye-Law clause 17: the Parichalak's personal expenditure (the discretionary grant placed at his disposal) is not subject to any audit. "
               "It is shown here for information and is not part of the audit.")

# The text a correction may change (the dates and the order of the steps never change).
CORRECTABLE = ("auditor_name", "auditor_firm", "appointment_reference", "report_reference", "report_link", "gb_reference",
               "approval_reference", "general_body_reference")

_COLUMNS = """
    a.finance_year_audit_pk, a.financial_year_pk, y.year_code, y.status AS year_status, a.organization_pk, o.organization_name, a.status, a.notes,
    a.auditor_name, a.auditor_firm, a.appointed_on, a.appointment_reference,
    a.report_reference, a.report_date, a.report_link,
    a.gb_placed_on, a.gb_reference, a.advisory_correspondence_pk, ac.reference_number AS advisory_letter_reference,
    aic.reference_number AS advisory_letter_inward_reference,
    a.approved_on, a.approval_reference, a.general_body_on, a.general_body_reference, a.created_at, a.updated_at
"""
_FROM = """
      FROM nss.finance_year_audit a
      JOIN nss.financial_year y ON y.financial_year_pk = a.financial_year_pk
      JOIN nss.organization o ON o.organization_pk = a.organization_pk
      LEFT JOIN nss.correspondence ac ON ac.correspondence_pk = a.advisory_correspondence_pk
      LEFT JOIN nss.correspondence aic ON aic.correspondence_pk = ac.counterpart_correspondence_pk
"""


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.")


# ═══════════════════════════════════════════════════════════════════════
# Pure rules (no database)
# ═══════════════════════════════════════════════════════════════════════

def next_step(audit_status: str) -> str | None:
    """What has to happen next, in words (None once the report has been placed before the General Body)."""
    return {
        APPOINTED: "Record the Audit Report the Auditor has delivered.",
        REPORT_RECEIVED: "Place the Audit Report before the Governing Body.",
        PLACED_BEFORE_GB: "Record the combined meeting of the Governing Body and the Advisory Board approving the Audit Report.",
        APPROVED: "The Secretary places the approved Audit Report before the General Body.",
    }.get(audit_status)


def check_not_future(value: date, label: str, today: date | None = None) -> None:
    if value > (today or date.today()):
        raise _invalid(f"{label} cannot be in the future; record it when it has happened.")


def check_dates_in_order(*, appointed_on=None, report_date=None, gb_placed_on=None, approved_on=None, general_body_on=None) -> None:
    """Appointment, report, Governing Body, combined meeting, General Body - never the other way round."""
    chain = (("appointed", appointed_on), ("the report", report_date), ("placed before the Governing Body", gb_placed_on),
             ("approved by the combined meeting", approved_on), ("placed before the General Body", general_body_on))
    last_label, last = None, None
    for label, value in chain:
        if value is None:
            continue
        if last is not None and value < last:
            raise _invalid(f"The date it was {label} cannot be before the date it was {last_label}.")
        last_label, last = label, value


def require_status(audit: dict, allowed: tuple[str, ...], what: str) -> None:
    if audit["status"] not in allowed:
        raise _invalid(f"The audit is {audit['status']}; {what} is possible only while it is {' or '.join(allowed)}.")


def require_blank(value: str | None, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise _invalid(f"{label} cannot be blank.")
    return cleaned


def clean_link(value: str | None) -> str | None:
    """A report link must be an https address (the same rule as a bill's link); blank means none."""
    cleaned = (value or "").strip() or None
    if cleaned is not None and not cleaned.lower().startswith("https://"):
        raise _invalid("The report link must start with https://.")
    return cleaned


def advisory_letter_subject(year_code: str) -> str:
    return f"Audit Report of the Kendra's accounts {year_code} - for the combined meeting of the Governing Body and the Advisory Board"


def advisory_letter_remarks(audit: dict, report_reference: str, gb_reference: str) -> str:
    firm = f" ({audit['auditor_firm']})" if audit.get("auditor_firm") else ""
    text = (f"Audit Report {report_reference} of the Kendra's accounts for {audit['year_code']}, by Auditor {audit['auditor_name']}{firm}, "
            f"placed before the Governing Body ({gb_reference}); forwarded for approval in the combined meeting of the Governing Body and the Advisory Board.")
    return text if len(text) <= 2000 else text[:1999].rstrip() + "…"


# ═══════════════════════════════════════════════════════════════════════
# Which organization holds the audit
# ═══════════════════════════════════════════════════════════════════════

def require_kendra(cur, organization_pk) -> None:
    if FA.basis_for_org(cur, organization_pk) != FA.KENDRA:
        raise _invalid("Only the Kendra Sangha's accounts have this audit (Bye-Law Section G); no rule is invented for other levels (FIN-BR-044).")


# ═══════════════════════════════════════════════════════════════════════
# Reading
# ═══════════════════════════════════════════════════════════════════════

def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def present(audit: dict) -> dict:
    out = dict(audit)
    out["next_step"] = next_step(audit["status"])
    out["step_number"] = STEP_ORDER.index(audit["status"]) + 1
    out["steps_total"] = len(STEP_ORDER)
    return out


def load(cur, audit_pk, *, lock: bool = False) -> dict:
    cur.execute(f"SELECT {_COLUMNS} {_FROM} WHERE a.finance_year_audit_pk = %s AND a.is_active = TRUE" + (" FOR UPDATE OF a" if lock else ""),
                (str(audit_pk),))
    rows = _rows(cur)
    if not rows:
        raise _not_found()
    return rows[0]


def list_rows(cur, where_sql: str, params: list) -> list[dict]:
    """Audits matching a WHERE built by the caller from fixed predicates (never input text), newest year first."""
    cur.execute(f"SELECT {_COLUMNS} {_FROM} WHERE {where_sql} ORDER BY y.start_date DESC, o.organization_name", params)
    return [present(r) for r in _rows(cur)]


def exempt_payments(cur, audit: dict) -> dict:
    """The money clause 17 puts outside the audit, for information: payments (not cancelled) of the audit's year in the Kendra's scopes whose
    permitted purpose is in ``EXEMPT_PURPOSES``. Never part of any total or step."""
    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(p.amount), 0)
          FROM nss.finance_disbursement_authority a
          JOIN nss.master_data md ON md.master_data_pk = a.purpose_master_data_pk
          JOIN nss.financial_payment p ON p.financial_payment_pk = a.financial_payment_pk AND p.is_active = TRUE AND p.status <> 'CANCELLED'
          JOIN nss.financial_transaction t ON t.financial_transaction_pk = p.financial_transaction_pk AND t.is_active = TRUE
          JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
         WHERE md.value_code = ANY(%s) AND t.financial_year_pk = %s AND fs.organization_pk = %s
        """,
        (list(EXEMPT_PURPOSES), str(audit["financial_year_pk"]), str(audit["organization_pk"])),
    )
    count, total = cur.fetchone()
    return {"count": count, "total": Decimal(total), "note": EXEMPT_NOTE}


def detail(cur, audit_pk) -> dict:
    audit = load(cur, audit_pk)
    out = present(audit)
    out["not_subject_to_audit"] = exempt_payments(cur, audit)
    return out


# ═══════════════════════════════════════════════════════════════════════
# Writing (the caller has already checked permission + scope and holds the row lock)
# ═══════════════════════════════════════════════════════════════════════

def _set(cur, actor_pk, audit_pk, values: dict) -> None:
    sets = [f"{col} = %s" for col in values] + ["updated_at = NOW()", "updated_by_sangha_sevi_pk = %s"]
    cur.execute(f"UPDATE nss.finance_year_audit SET {', '.join(sets)} WHERE finance_year_audit_pk = %s", [*values.values(), actor_pk, str(audit_pk)])


def validate_appoint(*, auditor_name: str, appointed_on: date, appointment_reference: str) -> tuple[str, str]:
    """The rules of appointing, nothing written; returns the cleaned (name, reference)."""
    name = require_blank(auditor_name, "The Auditor's name")
    reference = require_blank(appointment_reference, "The Governing Body's resolution reference")
    check_not_future(appointed_on, "The appointment date")
    return name, reference


def create(cur, actor_pk, *, year_pk, organization_pk, auditor_name, auditor_firm, appointed_on, appointment_reference, notes) -> str:
    """Start the year's audit by recording the Governing Body's appointment of the Auditor. Any year (open, closing or closed) may be audited."""
    name, reference = validate_appoint(auditor_name=auditor_name, appointed_on=appointed_on, appointment_reference=appointment_reference)
    cur.execute("SELECT 1 FROM nss.financial_year WHERE financial_year_pk = %s AND is_active = TRUE", (str(year_pk),))
    if cur.fetchone() is None:
        raise _invalid("Financial year not found.")
    cur.execute("SELECT 1 FROM nss.finance_year_audit WHERE financial_year_pk = %s AND organization_pk = %s AND is_active = TRUE",
                (str(year_pk), str(organization_pk)))
    if cur.fetchone():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This financial year already has an audit for the Kendra.")
    cur.execute(
        "INSERT INTO nss.finance_year_audit (financial_year_pk, organization_pk, auditor_name, auditor_firm, appointed_on, appointment_reference, notes, "
        "created_by_sangha_sevi_pk) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_year_audit_pk",
        (str(year_pk), str(organization_pk), name, (auditor_firm or "").strip() or None, appointed_on, reference, notes, actor_pk),
    )
    return cur.fetchone()[0]


def validate_report(audit: dict, *, reference: str, report_date: date, link: str | None) -> tuple[str, str | None]:
    require_status(audit, (APPOINTED,), "recording the Audit Report")
    reference = require_blank(reference, "The Audit Report reference")
    check_not_future(report_date, "The report date")
    check_dates_in_order(appointed_on=audit["appointed_on"], report_date=report_date)
    return reference, clean_link(link)


def record_report(cur, actor_pk, audit: dict, *, reference: str, report_date: date, link: str | None) -> None:
    reference, link = validate_report(audit, reference=reference, report_date=report_date, link=link)
    _set(cur, actor_pk, audit["finance_year_audit_pk"], {"status": REPORT_RECEIVED, "report_reference": reference, "report_date": report_date, "report_link": link})


def validate_gb(audit: dict, *, placed_on: date, reference: str) -> str:
    """Every rule of placing the report before the Governing Body, nothing written - the caller runs it BEFORE filing the letter."""
    require_status(audit, (REPORT_RECEIVED,), "placing the report before the Governing Body")
    reference = require_blank(reference, "The Governing Body's resolution / minute reference")
    check_not_future(placed_on, "The date it was placed before the Governing Body")
    check_dates_in_order(appointed_on=audit["appointed_on"], report_date=audit["report_date"], gb_placed_on=placed_on)
    return reference


def place_before_gb(cur, actor_pk, audit: dict, *, placed_on: date, reference: str, letter_pk) -> None:
    reference = validate_gb(audit, placed_on=placed_on, reference=reference)
    _set(cur, actor_pk, audit["finance_year_audit_pk"], {"status": PLACED_BEFORE_GB, "gb_placed_on": placed_on, "gb_reference": reference,
                                                          "advisory_correspondence_pk": str(letter_pk)})


def approve(cur, actor_pk, audit: dict, *, approved_on: date, reference: str) -> None:
    require_status(audit, (PLACED_BEFORE_GB,), "recording the combined meeting's approval")
    reference = require_blank(reference, "The combined meeting's resolution reference")
    check_not_future(approved_on, "The approval date")
    check_dates_in_order(appointed_on=audit["appointed_on"], report_date=audit["report_date"], gb_placed_on=audit["gb_placed_on"], approved_on=approved_on)
    _set(cur, actor_pk, audit["finance_year_audit_pk"], {"status": APPROVED, "approved_on": approved_on, "approval_reference": reference})


def place_before_general_body(cur, actor_pk, audit: dict, *, placed_on: date, reference: str) -> None:
    require_status(audit, (APPROVED,), "placing the report before the General Body (it is placed only after the combined meeting has approved it)")
    reference = require_blank(reference, "The General Body's reference")
    check_not_future(placed_on, "The date it was placed before the General Body")
    check_dates_in_order(appointed_on=audit["appointed_on"], report_date=audit["report_date"], gb_placed_on=audit["gb_placed_on"],
                         approved_on=audit["approved_on"], general_body_on=placed_on)
    _set(cur, actor_pk, audit["finance_year_audit_pk"], {"status": PLACED_BEFORE_GENERAL_BODY, "general_body_on": placed_on, "general_body_reference": reference})


def validate_correction(audit: dict, changes: dict, reason: str | None) -> dict:
    """The text that really changes ({} is refused). Only recorded text can be corrected, only what has been recorded, and always with a reason."""
    why = require_blank(reason, "The reason for the correction")
    out: dict = {}
    for col, value in changes.items():
        if col not in CORRECTABLE:
            raise _invalid(f"{col} cannot be corrected.")
        if value is None:
            continue
        label = col.replace("_", " ").capitalize()
        new = clean_link(value) if col == "report_link" else (value or "").strip()
        optional = col in ("auditor_firm", "report_link")            # these may be blank (cleared) once the step they belong to exists
        if not new and not optional:
            raise _invalid(f"{label} cannot be blank.")
        if col == "report_link" and audit["report_reference"] is None:
            raise _invalid("The Audit Report has not been recorded yet; there is no link to correct.")
        if audit.get(col) is None and not optional:
            raise _invalid(f"{label} has not been recorded yet; there is nothing to correct.")
        if (new or None) != audit.get(col):
            out[col] = new or None
    if not out:
        raise _invalid("Nothing to correct: send a value that differs from what is recorded.")
    out["_reason"] = why
    return out


def correct(cur, actor_pk, audit: dict, changes: dict, reason: str | None) -> dict:
    """Apply a correction; returns {"reason", "changed": {column: (old, new)}} for the audit event. The status does not move."""
    done = validate_correction(audit, changes, reason)
    why = done.pop("_reason")
    _set(cur, actor_pk, audit["finance_year_audit_pk"], done)
    return {"reason": why, "changed": {col: (audit[col], new) for col, new in done.items()}}
