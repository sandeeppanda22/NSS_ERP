"""
NSS ERP — Finance contributions (Tier 12): simple fixed-amount heads and the Kendra -> every-Sakha copies.

Owner decision 2026-11-15: a Sangha adds a contribution ("Annual Pranami, ₹500, yearly") in one short form; the server
fills in everything else. A Kendra head can be flagged ``applies_to_all_sakhas``: the Kendra row is then only the SOURCE
(it never collects itself) and every active Sakha / Sakha Asana receives its OWN copy, collecting into that Sakha's own
receiving account and scope. Money therefore always lands with the Sangha that owns the head the member pays.

Rules kept in this ONE module (routers import it; nothing here is duplicated elsewhere):
  - the copy fields that follow the source (name, description, amount, due period, part payment, order) and the ones the
    Sakha keeps (its receiving account, switching its copy off);
  - which account / scope a copy collects into (``link_account``);
  - the due window of a head (``period_window``) and the paid / due arithmetic (``card_state``);
  - the audit rows: EVERY row this module writes is logged (``log_audit``), by the acting admin or - for the automatic
    creation of copies for a new Sakha or a newly added account - by the system (``actor_pk`` NULL, ``system`` = true).

Nothing here commits, and nothing is ever deleted (soft status only).
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg2
from fastapi import HTTPException

from api.helpers import SAKHA_LIKE_ORG_TYPES_SQL, log_audit
from api.schemas.finance import DUE_PERIODS  # noqa: F401  (re-exported: the one list of due periods lives in the schemas)

logger = logging.getLogger(__name__)

# The head columns a Sakha copy takes from its source (everything else stays the Sakha's own).
FOLLOWED_FIELDS = ("head_name", "description", "fixed_amount", "due_period", "due_date", "allow_part_payment", "display_order", "skips_approval")


# ───────────────────────── pure helpers (no database) ─────────────────────────

def period_window(due_period: str | None, today: date) -> tuple[date, date] | None:
    """The dates a payment must fall in to count against a head's amount now; None = no window (one-time / free amount)."""
    if due_period == "YEARLY":                                   # Financial year 01 Apr - 31 Mar (SOL-FIN-001)
        start_year = today.year if today.month >= 4 else today.year - 1
        return date(start_year, 4, 1), date(start_year + 1, 3, 31)
    if due_period == "MONTHLY":
        start = today.replace(day=1)
        nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, nxt - timedelta(days=1)
    return None


def period_label(due_period: str | None, today: date) -> str | None:
    """What the card calls the period: "2026-27", "Nov 2026" or "one time"."""
    if due_period == "YEARLY":
        start = period_window(due_period, today)[0].year
        return f"{start}-{(start + 1) % 100:02d}"
    if due_period == "MONTHLY":
        return today.strftime("%b %Y")
    return "one time" if due_period == "ONE_TIME" else None


def card_state(fixed_amount: Decimal | None, paid: Decimal, pending: Decimal = Decimal("0")) -> dict:
    """
    Paid / due for one head card. ``state`` is PAID (green), PART (amber), DUE (red) or OPEN (no fixed amount: nothing is
    "due", the member may give any amount). ``pending`` is money in an unexpired UPI request that is not booked yet - it is
    never counted as paid, only reported. Money comes back with exactly two places ("0.00", never "0").
    """
    cents = Decimal("0.01")
    paid, pending = paid.quantize(cents), pending.quantize(cents)
    if fixed_amount is None:
        return {"state": "OPEN", "paid_amount": paid, "due_amount": None, "pending_amount": pending}
    due = max(fixed_amount.quantize(cents) - paid, Decimal("0.00"))
    state = "PAID" if due == 0 else ("PART" if paid > 0 else "DUE")
    return {"state": state, "paid_amount": paid, "due_amount": due, "pending_amount": pending}


def amount_problem(head: dict, amount: Decimal, due: Decimal | None) -> str | None:
    """Why ``amount`` is not acceptable for this head right now (None = fine). ``due`` is the remaining due (None = free head)."""
    if head.get("fixed_amount") is None:
        return None
    if due is None or due <= 0:
        return "This Pranami is already fully paid."
    if head.get("allow_part_payment"):
        return None if amount <= due else f"The amount is more than what is due ({due:,.2f})."
    return None if amount == due else f"This Pranami must be paid in full: {due:,.2f}."


# ───────────────────────── audit ─────────────────────────

def _audit(cur, user, action: str, table: str, pk, summary: str, detail: dict | None = None) -> None:
    detail = dict(detail or {})
    if user is None:
        detail["system"] = True
    log_audit(
        cur, action=action, table_name=table, record_pk=str(pk),
        actor_pk=user.actor_pk if user else None,
        actor_user_account_pk=str(user.user_account_pk) if user else None,
        module="finance", summary=summary, detail=detail,
    )


# ───────────────────────── scope / account for a Sangha ─────────────────────────

SCOPE_CODE_MAX = 50      # nss.financial_scope.scope_code
FUND_CODE_MAX = 50       # nss.fund_master.fund_code


def code_part(text) -> str:
    """UPPER-CASE letters and digits only, words joined by one hyphen: "Annual festival (Rasa)" -> "ANNUAL-FESTIVAL-RASA"."""
    return "-".join(re.findall(r"[A-Z0-9]+", (text or "").upper()))


def first_free_scope_code(cur, base: str, tries: int) -> str | None:
    """*base*, else *base*-2 .. *base*-<tries>; None when every one is taken. scope_code is unique across the whole system."""
    for n in range(1, tries + 1):
        suffix = "" if n == 1 else f"-{n}"
        candidate = base[: SCOPE_CODE_MAX - len(suffix)].rstrip("-") + suffix
        cur.execute("SELECT 1 FROM nss.financial_scope WHERE scope_code = %s", (candidate,))
        if cur.fetchone() is None:
            return candidate
    return None


def readable_scope_code(cur, short_code) -> str | None:
    """
    A readable code for a Sangha's general scope: its organization short code + "-GENERAL" (``EKM-GENERAL``; owner 2026-11-21 - the random
    ``ORG6B1BD5B8`` told nobody which Sangha it was). ``-2`` .. ``-9`` when taken; None when the Sangha has no short code or every one is taken,
    and the caller falls back to the random form.
    """
    base = code_part(short_code)
    return first_free_scope_code(cur, f"{base}-GENERAL", 9) if base else None


def org_code_prefix(cur, organization_pk) -> str:
    """A Sangha's code as the front of a generated code: its short code, its organization code when it has none, "" for no Sangha."""
    if organization_pk is None:
        return ""
    cur.execute("SELECT short_code, organization_code FROM nss.organization WHERE organization_pk = %s", (str(organization_pk),))
    row = cur.fetchone()
    return code_part((row[0] or row[1]) if row else "")


def scope_code_for(cur, organization_pk, scope_name: str) -> str:
    """
    The code of a new scope, made for the user (owner 2026-11-22: "scope code should come automatic (Sakha code + name)"): the owning
    Sangha's short code - its organization code when it has none - then the scope's name, e.g. ``EKM-ANNUAL-FESTIVAL``; ``-2``.. when
    taken. A scope with no organization takes the name alone; the random form is the last resort.
    """
    parts = [p for p in (org_code_prefix(cur, organization_pk), code_part(scope_name)) if p]
    base = "-".join(parts)
    return (first_free_scope_code(cur, base, 99) if base else None) or f"SCOPE{uuid4().hex[:8].upper()}"


FUND_TYPE_CODE_CATEGORY = "FUND_TYPE_CODE"


def fund_type_codes(cur) -> dict[str, str]:
    """
    The short code of each fund type, from MASTER DATA (category FUND_TYPE_CODE; owner 2026-11-23: "add these codes with other master data"):
    {fund type -> code}. value_code is the code, description the fund type it stands for. Only active rows.
    """
    cur.execute(
        """
        SELECT md.description, md.value_code
          FROM nss.master_data md
          JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
         WHERE mc.category_code = %s AND md.is_active = TRUE AND md.description IS NOT NULL
         ORDER BY md.display_order, md.value_code
        """,
        (FUND_TYPE_CODE_CATEGORY,),
    )
    return {fund_type: code for fund_type, code in cur.fetchall()}


def fund_type_code(cur, fund_type: str) -> str:
    code = fund_type_codes(cur).get(fund_type)
    if not code:
        raise HTTPException(status_code=422, detail=f"The fund type {fund_type} has no short code: add one under Reference data, category Fund Type Code "
                                                    "(or give the fund its own code).")
    return code


def fund_code_for(cur, scope_pk, organization_pk, fund_type: str) -> str:
    """
    The code of a new fund, made for the user (owner 2026-11-22: "fund code automatic: Org code + Fund Type Code"): the Sangha's code + the fund
    type's short code (api/schemas/finance.py::FUND_TYPE_CODES), e.g. ``EKM-GEN``, ``EKM-SINK``. A fund code is unique within its scope, so a second
    fund of the same type there is ``EKM-GEN-2`` and so on. *organization_pk* is the Sangha the fund belongs to - the Sakha of a Sinking Fund, else
    the scope's own. With no Sangha the type code stands alone.
    """
    base = "-".join(p for p in (org_code_prefix(cur, organization_pk), fund_type_code(cur, fund_type)) if p)
    for n in range(1, 100):
        suffix = "" if n == 1 else f"-{n}"
        candidate = base[: FUND_CODE_MAX - len(suffix)].rstrip("-") + suffix
        cur.execute("SELECT 1 FROM nss.fund_master WHERE financial_scope_pk = %s AND fund_code = %s", (str(scope_pk), candidate))
        if cur.fetchone() is None:
            return candidate
    return f"FUND{uuid4().hex[:8].upper()}"


def ensure_org_scope(cur, user, org_pk) -> str:
    """The Sangha's ACTIVE ORGANIZATION financial scope; one is created ACTIVE (audited) when it has none."""
    cur.execute(
        "SELECT financial_scope_pk FROM nss.financial_scope WHERE organization_pk = %s AND scope_type = 'ORGANIZATION' "
        "AND is_active = TRUE AND status = 'ACTIVE' ORDER BY created_at LIMIT 1", (str(org_pk),))
    row = cur.fetchone()
    if row:
        return str(row[0])
    cur.execute("SELECT organization_name, short_code FROM nss.organization WHERE organization_pk = %s", (str(org_pk),))
    name, short_code = cur.fetchone()
    code = readable_scope_code(cur, short_code) or f"ORG{uuid4().hex[:8].upper()}"
    cur.execute(
        "INSERT INTO nss.financial_scope (scope_code, scope_name, scope_type, organization_pk, status, created_by_sangha_sevi_pk) "
        "VALUES (%s, %s, 'ORGANIZATION', %s, 'ACTIVE', %s) RETURNING financial_scope_pk",
        (code, f"{name} - general"[:150], str(org_pk), user.actor_pk if user else None))
    pk = cur.fetchone()[0]
    _audit(cur, user, "CREATE", "financial_scope", pk, f"Created financial scope {code} for contributions",
           {"organization_pk": str(org_pk), "scope_type": "ORGANIZATION"})
    return str(pk)


def default_account(cur, org_pk) -> dict | None:
    """The Sangha's receiving account contributions go to: its default ACTIVE account that has a gateway named, else any such."""
    cur.execute(
        "SELECT financial_account_pk, account_label FROM nss.financial_account WHERE organization_pk = %s AND is_active = TRUE "
        "AND status = 'ACTIVE' AND gateway_provider IS NOT NULL AND gateway_credential_ref IS NOT NULL "
        "ORDER BY is_default DESC, created_at LIMIT 1", (str(org_pk),))
    row = cur.fetchone()
    return {"financial_account_pk": str(row[0]), "account_label": row[1]} if row else None


DEMO_ACCOUNT_LABEL = "Demo UPI account"


def ensure_demo_account(cur, user, org_pk) -> dict | None:
    """
    DEMO ONLY. On a development / demo install (the database is on this machine) where the MOCK gateway is enabled, when the Sangha has no
    usable receiving account create its default "Demo UPI account" on the MOCK gateway, so a head's payment portal works end to end with no
    manual setup - even while RAZORPAY is also enabled: a Sangha that HAS a Razorpay account keeps using it. Returns the account like
    default_account(), or None on any other server (production never gets a fake account) or when the Sangha already has an account with that
    label. No money ever moves through it. Audited.
    """
    from api.services import upi_gateway          # local: this module is imported by code that must not need the gateway

    if "MOCK" not in upi_gateway.enabled_providers() or not upi_gateway.is_dev_install():
        return None
    cur.execute("SELECT 1 FROM nss.financial_account WHERE organization_pk = %s AND account_label = %s", (str(org_pk), DEMO_ACCOUNT_LABEL))
    if cur.fetchone():
        return None
    cur.execute("SELECT organization_name FROM nss.organization WHERE organization_pk = %s", (str(org_pk),))
    name = cur.fetchone()[0]
    cur.execute("UPDATE nss.financial_account SET is_default = FALSE, updated_at = NOW() WHERE organization_pk = %s AND is_default = TRUE AND is_active = TRUE",
                (str(org_pk),))
    cur.execute(
        "INSERT INTO nss.financial_account (organization_pk, account_label, account_type, account_holder_name, upi_vpa, gateway_provider, "
        "gateway_credential_ref, is_default, created_by_sangha_sevi_pk) VALUES (%s, %s, 'BANK', %s, 'nss.demo@mockbank', 'MOCK', 'MOCK_DEMO', TRUE, %s) "
        "RETURNING financial_account_pk",
        (str(org_pk), DEMO_ACCOUNT_LABEL, name[:200], user.actor_pk if user else None))
    pk = cur.fetchone()[0]
    _audit(cur, user, "CREATE", "financial_account", pk, f"Created the demo receiving account for {name} (MOCK gateway, no real money)",
           {"organization_pk": str(org_pk), "gateway_provider": "MOCK", "automatic": True})
    return {"financial_account_pk": str(pk), "account_label": DEMO_ACCOUNT_LABEL}


# ───────────────────────── the Kendra -> Sakha copies ─────────────────────────

def _source_row(cur, source_pk) -> dict:
    cur.execute(
        "SELECT finance_head_pk, head_code, head_name, description, fixed_amount, due_period, due_date, allow_part_payment, display_order, "
        "skips_approval, status FROM nss.finance_head WHERE finance_head_pk = %s AND is_active = TRUE AND applies_to_all_sakhas = TRUE",
        (str(source_pk),))
    row = cur.fetchone()
    if row is None:
        raise LookupError("not an all-Sakhas source head")
    return dict(zip(("finance_head_pk", "head_code", "head_name", "description", "fixed_amount", "due_period", "due_date",
                     "allow_part_payment", "display_order", "skips_approval", "status"), row))


def _active_sakhas(cur) -> list[str]:
    cur.execute(
        "SELECT o.organization_pk FROM nss.organization o JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk "
        f"WHERE o.is_active = TRUE AND md.value_code IN {SAKHA_LIKE_ORG_TYPES_SQL} ORDER BY o.organization_name")
    return [str(r[0]) for r in cur.fetchall()]


def _make_copy(cur, user, source: dict, org_pk: str) -> str | None:
    """Create the Sakha's copy of one source head unless it already has one. Returns the new head pk, else None."""
    cur.execute("SELECT 1 FROM nss.finance_head WHERE organization_pk = %s AND template_head_pk = %s", (org_pk, str(source["finance_head_pk"])))
    if cur.fetchone():
        return None
    cur.execute("SELECT 1 FROM nss.finance_head WHERE organization_pk = %s AND head_code = %s", (org_pk, source["head_code"]))
    if cur.fetchone():
        return None                                              # the code is taken by something else: never overwrite it
    cur.execute(
        """
        INSERT INTO nss.finance_head
            (organization_pk, head_code, head_name, description, direction, is_pranami, skips_approval, template_head_pk,
             fixed_amount, due_period, due_date, allow_part_payment, display_order, status, created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, 'INCOME', TRUE, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_head_pk
        """,
        (org_pk, source["head_code"], source["head_name"], source["description"], source["skips_approval"],
         str(source["finance_head_pk"]), source["fixed_amount"], source["due_period"], source["due_date"], source["allow_part_payment"],
         source["display_order"], source["status"], user.actor_pk if user else None))
    pk = cur.fetchone()[0]
    _audit(cur, user, "CREATE", "finance_head", pk, f"Created {source['head_code']} for a Sakha from the Kendra's head",
           {"organization_pk": org_pk, "source_head_pk": str(source["finance_head_pk"]), "automatic": True})
    link_account(cur, user, org_pk, only_head_pk=pk)
    return str(pk)


def sync_copies(cur, user, source_pk) -> dict:
    """
    Make every active Sakha hold a copy of the all-Sakhas head ``source_pk``, and bring existing copies in line with it.
    Idempotent. Returns counts. A copy the Sakha switched off is left alone (only a source deactivation propagates).
    """
    source = _source_row(cur, source_pk)
    created = updated = 0
    for org_pk in _active_sakhas(cur):
        if _make_copy(cur, user, source, org_pk):
            created += 1
    cur.execute(
        "SELECT finance_head_pk, head_name, description, fixed_amount, due_period, due_date, allow_part_payment, display_order, "
        "skips_approval FROM nss.finance_head WHERE template_head_pk = %s AND is_active = TRUE", (str(source_pk),))
    for pk, name, desc, amt, per, due, part, order, skip in cur.fetchall():
        if (name, desc, amt, per, due, part, order, skip) == tuple(source[f] for f in FOLLOWED_FIELDS):
            continue
        cur.execute(
            "UPDATE nss.finance_head SET head_name = %s, description = %s, fixed_amount = %s, due_period = %s, due_date = %s, "
            "allow_part_payment = %s, display_order = %s, skips_approval = %s, updated_at = NOW(), "
            "updated_by_sangha_sevi_pk = %s WHERE finance_head_pk = %s",
            (source["head_name"], source["description"], source["fixed_amount"], source["due_period"], source["due_date"],
             source["allow_part_payment"], source["display_order"], source["skips_approval"],
             user.actor_pk if user else None, str(pk)))
        _audit(cur, user, "UPDATE", "finance_head", pk, f"Copy of {source['head_code']} brought in line with the Kendra's head",
               {"source_head_pk": str(source_pk), "automatic": True, "fields": list(FOLLOWED_FIELDS)})
        updated += 1
    return {"created": created, "updated": updated}


def set_copies_status(cur, user, source_pk, new_status: str) -> int:
    """
    The Kendra switched the source ``new_status`` (ACTIVE / INACTIVE): every copy follows (history stays; a Sakha may still
    switch its own copy off afterwards, but a later Kendra change applies to all copies again). Returns how many changed.
    """
    old = "ACTIVE" if new_status == "INACTIVE" else "INACTIVE"
    cur.execute("SELECT finance_head_pk FROM nss.finance_head WHERE template_head_pk = %s AND is_active = TRUE AND status = %s",
                (str(source_pk), old))
    pks = [r[0] for r in cur.fetchall()]
    for pk in pks:
        cur.execute("UPDATE nss.finance_head SET status = %s, updated_at = NOW(), updated_by_sangha_sevi_pk = %s "
                    "WHERE finance_head_pk = %s", (new_status, user.actor_pk if user else None, str(pk)))
        _audit(cur, user, "STATUS_CHANGE", "finance_head", pk, f"Copy switched {new_status} because the Kendra's head was",
               {"source_head_pk": str(source_pk), "from": old, "to": new_status, "automatic": True})
    return len(pks)


def sync_sakha(cur, user, org_pk) -> int:
    """A Sakha is new (or newly active): give it a copy of every ACTIVE all-Sakhas head. Returns how many were created."""
    cur.execute("SELECT finance_head_pk FROM nss.finance_head WHERE applies_to_all_sakhas = TRUE AND is_active = TRUE AND status = 'ACTIVE'")
    made = 0
    for (pk,) in cur.fetchall():
        if _make_copy(cur, user, _source_row(cur, pk), str(org_pk)):
            made += 1
    return made


def sync_new_sakha(cur, user, org_pk) -> int:
    """
    The hook that runs when a Sakha is created. A failure here (for example a database that has not had the finance patch
    applied yet) must never block creating the Sakha: it is rolled back to a savepoint, logged, and the Kendra can bring the
    copies up to date later with ``sync_copies`` (POST /finance/heads/{pk}/sync-copies).
    """
    cur.execute("SAVEPOINT finance_new_sakha")
    try:
        made = sync_sakha(cur, user, org_pk)
    except psycopg2.Error:
        cur.execute("ROLLBACK TO SAVEPOINT finance_new_sakha")
        logger.exception("Could not give the new Sakha %s its Kendra contribution copies", org_pk)
        return 0
    cur.execute("RELEASE SAVEPOINT finance_new_sakha")
    return made


def link_account(cur, user, org_pk, *, only_head_pk=None) -> int:
    """
    Point the Sangha's UPI-less copies at its receiving account (and its scope) and switch UPI collection on. Called when a
    copy is created, when the Sangha adds / changes an account. A copy that already has an account is left alone.
    """
    account = default_account(cur, org_pk)
    if account is None:
        return 0
    # ONLY copies of a Kendra all-Sakhas head: other heads that carry a template_head_pk (the Kendra templates a Sangha adopted,
    # many of them EXPENSE heads) are never switched onto UPI collection from here.
    where, params = ("h.organization_pk = %s AND h.is_active = TRUE AND h.collection_account_pk IS NULL "
                     "AND s.applies_to_all_sakhas = TRUE AND s.is_active = TRUE"), [str(org_pk)]
    if only_head_pk is not None:
        where += " AND h.finance_head_pk = %s"; params.append(str(only_head_pk))
    cur.execute("SELECT h.finance_head_pk FROM nss.finance_head h JOIN nss.finance_head s ON s.finance_head_pk = h.template_head_pk "
                f"WHERE {where}", params)
    pks = [r[0] for r in cur.fetchall()]
    if not pks:
        return 0
    scope_pk = ensure_org_scope(cur, user, org_pk)
    for pk in pks:
        cur.execute(
            "UPDATE nss.finance_head SET collection_scope_pk = %s, collection_account_pk = %s, allow_upi = TRUE, "
            "updated_at = NOW(), updated_by_sangha_sevi_pk = %s WHERE finance_head_pk = %s",
            (scope_pk, account["financial_account_pk"], user.actor_pk if user else None, str(pk)))
        _audit(cur, user, "UPDATE", "finance_head", pk, f"Contribution now collects into {account['account_label']}",
               {"organization_pk": str(org_pk), "financial_account_pk": account["financial_account_pk"], "automatic": True})
    return len(pks)
