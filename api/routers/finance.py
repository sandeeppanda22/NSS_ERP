"""
NSS ERP — Finance router (Tier 12).

Financial years, financial scopes, funds, the unified financial transaction,
receipt / payment evidence, inter-scope transfers, a summary and a reference
endpoint for the UI. Authority: docs/03_Solution/modules/finance/
(SOL-FIN-001..005, business rules FIN-BR-001..068).

  GET    /api/v1/finance/reference                       — pick-lists + the transition table (UI)
  GET    /api/v1/finance/summary                         — totals, per-fund balances, per-category totals
  GET    /api/v1/finance/my-pranami                      — the CALLER's own Pranami (login only, member tab)
  GET    /api/v1/finance/years                           — financial years
  POST   /api/v1/finance/years                           — create a year (01 Apr - 31 Mar)
  POST   /api/v1/finance/years/{pk}/transition           — PLANNED -> OPEN -> CLOSING -> CLOSED
  GET    /api/v1/finance/scopes | POST | GET {pk} | PATCH {pk} | POST {pk}/transition
  GET    /api/v1/finance/funds  | POST | GET {pk} | PATCH {pk} | POST {pk}/transition
  GET    /api/v1/finance/transactions | POST | GET {pk} | PATCH {pk} | POST {pk}/transition
  POST   /api/v1/finance/transactions/{pk}/receipts      — receipt evidence (income)
  POST   /api/v1/finance/transactions/{pk}/payments      — payment evidence (expense)
  GET    /api/v1/finance/receipts | POST {pk}/transition
  GET    /api/v1/finance/payments | POST {pk}/transition
  GET    /api/v1/finance/transfers | POST | GET {pk} | POST {pk}/transition

Authorization (lifecycle §28 — the common RBAC framework, no Finance roles):
FINANCE_VIEW (reads) / FINANCE_MANAGE (record, edit, submit) / FINANCE_APPROVE
(approve, post, reject, execute, cancel, open/close). Recording and approving
are separate grants (FIN-BR-040: no single generic approval). On top of the
permission, every record is bounded by admin scope on the owning Financial
Scope's organization (``actor_scope_org_pks`` / ``require_org_in_scope``); a
scope with no organization — and the financial years themselves — are
manageable only by the global authority (NSS_ERP_ADMIN / NSS-WIDE / Kendra).
Maker-checker: the APPROVE step of a transaction, payment or transfer refuses
the record's own creator, except the NSS_ERP_ADMIN super administrator (so a
single-administrator installation can still operate; the audit row says
``self_approved``). Approval of the scheme / the President's order (FIN-BR-040)
is a Governance matter and is only referenced through ``remarks``.

Rules enforced here (DB CHECKs in database/ddl/14_finance/ are the backstop):
  - a transaction needs an OPEN year and an ACTIVE scope, its date inside the
    year, and (when a fund is named) an ACTIVE fund of the SAME scope;
  - restricted money stays restricted (FIN-BR-019..022): specific-purpose
    donations and publication income must go to a restricted fund, a Sinking
    Fund entry to a SINKING_FUND fund carrying its Sakha (FIN-BR-023/024), an
    expense from a restricted fund must be EXPENSE_RESTRICTED, and a
    restricted expense can never exceed the fund's balance (checked at
    approval and again at posting, under a lock on the fund row);
  - receipts only for posted INCOME, payments only for approved EXPENSE, and
    the evidence can never add up to more than the transaction amount;
  - a transfer moves money between two DIFFERENT, ACTIVE scopes (the caller
    needs scope over both) and cannot take more than the source fund holds;
  - a year / scope cannot close while unfinished work remains in it;
  - nothing is deleted: cancellation and rejection are statuses (FIN-BR-051).
ADJUSTMENT transactions are recorded but excluded from balances and totals
until the sign / reversal mechanism is decided (lifecycle §40, PENDING).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.auth import get_current_user
from api.dependencies.rbac import require_any_permission
from api.helpers import SAKHA_LIKE_ORG_TYPES, get_master_data_pk, log_audit, next_id
from api.schemas import finance as S
from api.services import finance_authority as authority_service
from api.services import upi_gateway
from api.services.rbac_service import UserContext, actor_scope_org_pks, require_org_in_scope, require_person_in_scope

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW_PERMISSIONS = ("FINANCE_VIEW", "FINANCE_MANAGE", "FINANCE_APPROVE")
_VIEW = require_any_permission(*_VIEW_PERMISSIONS)
_MANAGE = require_any_permission("FINANCE_MANAGE", "FINANCE_APPROVE")
_APPROVE = require_any_permission("FINANCE_APPROVE")

_MAX_PARENT_WALK = 20  # same depth cap as helpers.MAX_RECURSION_DEPTH, walked in Python

_PERSON_NAME_SQL = "NULLIF(TRIM(CONCAT_WS(' ', {a}.first_name, {a}.middle_name, {a}.last_name)), '')"

_COUNTED_TXN_STATUSES = ("POSTED", "SETTLED")
_COUNTED_TRANSFER_STATUSES = ("EXECUTED", "COMPLETED")


def _in(values) -> str:
    """('A', 'B') for an SQL IN list built from CODE constants (never user input). repr() of a 1-tuple has a trailing comma, which is invalid SQL."""
    return "(" + ", ".join("'" + str(v).replace("'", "''") + "'" for v in values) + ")"


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle table — ONE definition for the API and (via /reference) the UI
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class _Step:
    permission: str                # FINANCE_MANAGE steps are also open to FINANCE_APPROVE holders
    remarks: bool = False          # remarks mandatory (reject / cancel)
    maker_checker: bool = False    # the record's creator may not take this step


_M, _A = "FINANCE_MANAGE", "FINANCE_APPROVE"

_STEPS: dict[str, dict[tuple[str, str], _Step]] = {
    "year": {
        ("PLANNED", "OPEN"): _Step(_A),
        ("OPEN", "CLOSING"): _Step(_A),
        ("CLOSING", "CLOSED"): _Step(_A),
    },
    "scope": {
        ("DRAFT", "ACTIVE"): _Step(_A),
        ("ACTIVE", "CLOSING"): _Step(_A),
        ("CLOSING", "CLOSED"): _Step(_A),
    },
    "fund": {
        ("DRAFT", "ACTIVE"): _Step(_A),
        ("ACTIVE", "INACTIVE"): _Step(_A),
    },
    "transaction": {
        ("DRAFT", "PENDING_APPROVAL"): _Step(_M),
        ("PENDING_APPROVAL", "APPROVED"): _Step(_A, maker_checker=True),
        ("PENDING_APPROVAL", "REJECTED"): _Step(_A, remarks=True),
        ("APPROVED", "POSTED"): _Step(_A),
        ("POSTED", "SETTLED"): _Step(_A),
        ("DRAFT", "CANCELLED"): _Step(_M, remarks=True),
        ("PENDING_APPROVAL", "CANCELLED"): _Step(_M, remarks=True),
        ("APPROVED", "CANCELLED"): _Step(_A, remarks=True),
    },
    "receipt": {
        ("DRAFT", "ISSUED"): _Step(_M),
        ("ISSUED", "CANCELLED"): _Step(_A, remarks=True),
    },
    "payment": {
        ("DRAFT", "APPROVED"): _Step(_A, maker_checker=True),
        ("APPROVED", "INITIATED"): _Step(_M),
        ("INITIATED", "COMPLETED"): _Step(_M),
        ("DRAFT", "CANCELLED"): _Step(_M, remarks=True),
        ("APPROVED", "CANCELLED"): _Step(_M, remarks=True),
        ("INITIATED", "CANCELLED"): _Step(_A, remarks=True),
    },
    # Configuration: a head / account is switched on and off, never deleted (history is kept).
    "account": {
        ("ACTIVE", "INACTIVE"): _Step(_A, remarks=True),
        ("INACTIVE", "ACTIVE"): _Step(_A),
    },
    "head": {
        ("ACTIVE", "INACTIVE"): _Step(_A),
        ("INACTIVE", "ACTIVE"): _Step(_A),
    },
    # A UPI request can be cancelled while it is still unpaid; PAID / FAILED / EXPIRED are set only by the gateway.
    "payment_request": {
        ("CREATED", "CANCELLED"): _Step(_M, remarks=True),
        ("PENDING", "CANCELLED"): _Step(_M, remarks=True),
    },
    "transfer": {
        ("DRAFT", "PENDING_APPROVAL"): _Step(_M),
        ("PENDING_APPROVAL", "APPROVED"): _Step(_A, maker_checker=True),
        ("PENDING_APPROVAL", "REJECTED"): _Step(_A, remarks=True),
        ("APPROVED", "EXECUTED"): _Step(_A),
        ("EXECUTED", "COMPLETED"): _Step(_A),
        ("DRAFT", "CANCELLED"): _Step(_M, remarks=True),
        ("PENDING_APPROVAL", "CANCELLED"): _Step(_M, remarks=True),
        ("APPROVED", "CANCELLED"): _Step(_A, remarks=True),
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════

def _fetch_all(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _fetch_one(cur) -> dict | None:
    rows = _fetch_all(cur)
    return rows[0] if rows else None


def _audit(cur, user: UserContext, action: str, table: str, pk, summary: str, detail: dict | None = None) -> None:
    log_audit(
        cur, action=action, table_name=table, record_pk=str(pk),
        actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
        module="finance", summary=summary, detail=detail,
    )


def _update_row(cur, user: UserContext, table: str, pk_col: str, pk, values: dict) -> None:
    """UPDATE the given columns (identifiers come from code, never input) + stamp the audit columns."""
    sets = [f"{col} = %s" for col in values] + ["updated_at = NOW()", "updated_by_sangha_sevi_pk = %s"]
    cur.execute(
        f"UPDATE nss.{table} SET {', '.join(sets)} WHERE {pk_col} = %s",
        [*values.values(), user.actor_pk, str(pk)],
    )


def _clean(value):
    if value is None:
        return None
    value = value.strip()
    return value or None


def _not_found(label: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found.")


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _require_global(cur, user: UserContext, action: str) -> None:
    """Financial years (and scopes with no organization) belong to the global authority only."""
    if actor_scope_org_pks(cur, user) is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Only NSS-wide administrators can {action}.")


def _require_org_access(cur, user: UserContext, organization_pk, action: str) -> None:
    """Admin scope on the owning organization; no organization -> global authority only."""
    if organization_pk is None:
        _require_global(cur, user, action)
    else:
        require_org_in_scope(cur, user, organization_pk, action)


def _visible(cur, user: UserContext, column: str) -> tuple[str, list]:
    """SQL predicate limiting *column* (a scope's organization_pk) to the caller's admin scope."""
    allowed = actor_scope_org_pks(cur, user)
    if allowed is None:
        return "TRUE", []
    return f"{column} = ANY(%s::uuid[])", [sorted(allowed)]


def _require_exists(cur, table: str, pk_col: str, pk, label: str) -> None:
    cur.execute(f"SELECT 1 FROM nss.{table} WHERE {pk_col} = %s AND is_active = TRUE", (str(pk),))
    if cur.fetchone() is None:
        raise _invalid(f"{label} not found.")


def _paged(items: list, total: int, page: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _guard_transition(user: UserContext, entity: str, current: str, target: str, remarks: str | None,
                      created_by) -> tuple[_Step, bool]:
    """Validate (current -> target) against the lifecycle table; returns the step and whether it was self-approved."""
    steps = _STEPS[entity]
    step = steps.get((current, target))
    if step is None:
        allowed = ", ".join(sorted(t for (f, t) in steps if f == current)) or "none"
        raise _invalid(f"Invalid {entity} transition {current} -> {target}. Allowed from {current}: {allowed}.")
    needed = (step.permission, "FINANCE_APPROVE") if step.permission == _M else (step.permission,)
    if not user.has_any_permission(*needed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{current} -> {target} needs the {step.permission} permission.")
    if step.remarks and not _clean(remarks):
        raise _invalid(f"Remarks are required for {current} -> {target}.")
    self_approved = False
    if step.maker_checker and created_by is not None and str(created_by) == user.actor_pk:
        if not user.is_super_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You created this record, so someone else must approve it.",
            )
        self_approved = True
    return step, self_approved


# ═══════════════════════════════════════════════════════════════════════
# Row loaders
# ═══════════════════════════════════════════════════════════════════════

def _year_row(cur, year_pk, *, lock: bool = False) -> dict:
    cur.execute(
        "SELECT financial_year_pk, year_code, start_date, end_date, status FROM nss.financial_year "
        "WHERE financial_year_pk = %s AND is_active = TRUE" + (" FOR UPDATE" if lock else ""),
        (str(year_pk),),
    )
    row = _fetch_one(cur)
    if row is None:
        raise _not_found("Financial year")
    return row


def _scope_row(cur, scope_pk, *, lock: bool = False) -> dict:
    cur.execute(
        """
        SELECT fs.financial_scope_pk, fs.scope_code, fs.scope_name, fs.scope_type, fs.organization_pk,
               fs.financial_year_pk, fs.parent_scope_pk, fs.status, fs.created_by_sangha_sevi_pk
          FROM nss.financial_scope fs
         WHERE fs.financial_scope_pk = %s AND fs.is_active = TRUE
        """ + (" FOR UPDATE" if lock else ""),
        (str(scope_pk),),
    )
    row = _fetch_one(cur)
    if row is None:
        raise _not_found("Financial scope")
    return row


def _fund_row(cur, fund_pk, *, lock: bool = False) -> dict:
    cur.execute(
        """
        SELECT fm.fund_master_pk, fm.fund_code, fm.fund_name, fm.fund_type, fm.financial_scope_pk,
               fm.is_restricted, fm.restriction_purpose, fm.organization_pk, fm.status
          FROM nss.fund_master fm
         WHERE fm.fund_master_pk = %s AND fm.is_active = TRUE
        """ + (" FOR UPDATE" if lock else ""),
        (str(fund_pk),),
    )
    row = _fetch_one(cur)
    if row is None:
        raise _not_found("Fund")
    return row


# Fund flows — the ONE definition of a fund's balance. ADJUSTMENT rows are not
# counted (sign convention PENDING); only posted/settled transactions and
# executed/completed transfers move money.
def _fund_flows_sql(fund_ref: str) -> dict[str, str]:
    def txn(kind: str) -> str:
        return (
            "COALESCE((SELECT SUM(ft.amount) FROM nss.financial_transaction ft "
            f"WHERE ft.fund_master_pk = {fund_ref} AND ft.is_active = TRUE "
            f"AND ft.transaction_type = '{kind}' AND ft.status IN {_in(_COUNTED_TXN_STATUSES)}), 0)"
        )

    def transfer(column: str) -> str:
        return (
            "COALESCE((SELECT SUM(tr.amount) FROM nss.financial_transfer tr "
            f"WHERE tr.{column} = {fund_ref} AND tr.is_active = TRUE "
            f"AND tr.status IN {_in(_COUNTED_TRANSFER_STATUSES)}), 0)"
        )

    return {"income": txn("INCOME"), "expense": txn("EXPENSE"),
            "transfers_in": transfer("destination_fund_pk"), "transfers_out": transfer("source_fund_pk")}


def _balance_sql(fund_ref: str) -> str:
    f = _fund_flows_sql(fund_ref)
    return f"({f['income']} - {f['expense']} + {f['transfers_in']} - {f['transfers_out']})"


def _lock_and_balance(cur, fund_pk) -> Decimal:
    """Serialise money leaving a fund: lock its row, then read the balance."""
    cur.execute("SELECT 1 FROM nss.fund_master WHERE fund_master_pk = %s FOR UPDATE", (str(fund_pk),))
    cur.execute(f"SELECT {_balance_sql('%s')}", (str(fund_pk),) * 4)
    return cur.fetchone()[0]


# ═══════════════════════════════════════════════════════════════════════
# Reference + summary
# ═══════════════════════════════════════════════════════════════════════

@router.get("/reference", response_model=S.FinanceReference)
def reference(user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    """Pick-lists (payment methods come from master_data) and the lifecycle table the UI renders buttons from."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT md.value_code, md.value_name
              FROM nss.master_data md
              JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk
             WHERE mc.category_code = 'PAYMENT_METHOD' AND md.is_active = TRUE
             ORDER BY md.display_order, md.value_name
            """
        )
        methods = [{"code": r[0], "name": r[1]} for r in cur.fetchall()]
        disbursement_purposes = authority_service.purposes(cur)
    return {
        "payment_methods": methods,
        "fund_types": list(S.FUND_TYPES),
        "scope_types": list(S.SCOPE_TYPES),
        "transaction_types": list(S.TRANSACTION_TYPES),
        "head_directions": list(S.HEAD_DIRECTIONS),
        "account_types": list(S.ACCOUNT_TYPES),
        "gateway_providers": sorted(upi_gateway.enabled_providers() & set(upi_gateway.PROVIDERS)),
        "disbursement_purposes": disbursement_purposes,
        "statuses": {
            "year": list(S.YEAR_STATUSES), "scope": list(S.SCOPE_STATUSES), "fund": list(S.FUND_STATUSES),
            "transaction": list(S.TRANSACTION_STATUSES), "receipt": list(S.RECEIPT_STATUSES),
            "payment": list(S.PAYMENT_STATUSES), "transfer": list(S.TRANSFER_STATUSES),
            "account": list(S.ACCOUNT_STATUSES), "head": list(S.HEAD_STATUSES),
            "payment_request": list(S.PAYMENT_REQUEST_STATUSES),
        },
        "transitions": {
            entity: [{"from": f, "to": t, "permission": s.permission, "remarks": s.remarks, "maker_checker": s.maker_checker}
                     for (f, t), s in steps.items()]
            for entity, steps in _STEPS.items()
        },
    }


@router.get("/summary", response_model=S.FinanceSummary)
def summary(
    financial_year_pk: UUID | None = Query(None, description="Default: the latest OPEN year, else the latest year"),
    financial_scope_pk: UUID | None = Query(None),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    """Posted/settled totals, pending work, per-fund balances and per-category totals for the caller's scopes."""
    with conn.cursor() as cur:
        if financial_year_pk is None:
            cur.execute(
                "SELECT financial_year_pk FROM nss.financial_year WHERE is_active = TRUE "
                "ORDER BY (status = 'OPEN') DESC, start_date DESC LIMIT 1"
            )
            row = cur.fetchone()
            year = _year_row(cur, row[0]) if row else None
        else:
            year = _year_row(cur, financial_year_pk)
        if financial_scope_pk is not None:
            scope = _scope_row(cur, financial_scope_pk)
            _require_org_access(cur, user, scope["organization_pk"], "view this financial scope")

        vis, vis_params = _visible(cur, user, "fs.organization_pk")
        txn_where = ["ft.is_active = TRUE", vis]
        txn_params: list = list(vis_params)
        if year:
            txn_where.append("ft.financial_year_pk = %s")
            txn_params.append(str(year["financial_year_pk"]))
        if financial_scope_pk is not None:
            txn_where.append("ft.financial_scope_pk = %s")
            txn_params.append(str(financial_scope_pk))
        where_sql = " AND ".join(txn_where)
        base = "FROM nss.financial_transaction ft JOIN nss.financial_scope fs ON fs.financial_scope_pk = ft.financial_scope_pk"

        cur.execute(
            f"""
            SELECT ft.transaction_type, ft.transaction_category, MIN(h.head_name), SUM(ft.amount), COUNT(*)
              {base}
              LEFT JOIN nss.finance_head h ON h.finance_head_pk = ft.finance_head_pk
             WHERE {where_sql} AND ft.status IN {_in(_COUNTED_TXN_STATUSES)} AND ft.transaction_type IN ('INCOME','EXPENSE')
             GROUP BY ft.transaction_type, ft.transaction_category
             ORDER BY ft.transaction_type, SUM(ft.amount) DESC
            """,
            txn_params,
        )
        by_category = [{"transaction_type": r[0], "transaction_category": r[1], "finance_head_name": r[2], "total": r[3], "count": r[4]}
                       for r in cur.fetchall()]
        income = sum((c["total"] for c in by_category if c["transaction_type"] == "INCOME"), Decimal("0.00"))
        expense = sum((c["total"] for c in by_category if c["transaction_type"] == "EXPENSE"), Decimal("0.00"))

        cur.execute(
            f"""
            SELECT COUNT(*) FILTER (WHERE ft.status = 'PENDING_APPROVAL'), COUNT(*) FILTER (WHERE ft.status = 'DRAFT')
              {base} WHERE {where_sql}
            """,
            txn_params,
        )
        pending_txn, draft_txn = cur.fetchone()

        tr_where = ["tr.is_active = TRUE", "tr.status = 'PENDING_APPROVAL'"]
        tr_params: list = []
        if year:
            tr_where.append("tr.financial_year_pk = %s")
            tr_params.append(str(year["financial_year_pk"]))
        sv, sp = _visible(cur, user, "sfs.organization_pk")
        dv, dp = _visible(cur, user, "dfs.organization_pk")
        tr_where.append(f"({sv} OR {dv})")
        tr_params += sp + dp
        if financial_scope_pk is not None:
            tr_where.append("(tr.source_scope_pk = %s OR tr.destination_scope_pk = %s)")
            tr_params += [str(financial_scope_pk)] * 2
        cur.execute(
            f"""
            SELECT COUNT(*) FROM nss.financial_transfer tr
              JOIN nss.financial_scope sfs ON sfs.financial_scope_pk = tr.source_scope_pk
              JOIN nss.financial_scope dfs ON dfs.financial_scope_pk = tr.destination_scope_pk
             WHERE {' AND '.join(tr_where)}
            """,
            tr_params,
        )
        pending_transfers = cur.fetchone()[0]

        flows = _fund_flows_sql("fm.fund_master_pk")
        fund_where = ["fm.is_active = TRUE", "fm.status <> 'DRAFT'", vis]
        fund_params: list = list(vis_params)
        if financial_scope_pk is not None:
            fund_where.append("fm.financial_scope_pk = %s")
            fund_params.append(str(financial_scope_pk))
        cur.execute(
            f"""
            SELECT fm.fund_master_pk, fm.fund_code, fm.fund_name, fs.scope_code, fm.is_restricted,
                   {flows['income']}, {flows['expense']}, {flows['transfers_in']}, {flows['transfers_out']}
              FROM nss.fund_master fm
              JOIN nss.financial_scope fs ON fs.financial_scope_pk = fm.financial_scope_pk
             WHERE {' AND '.join(fund_where)}
             ORDER BY fs.scope_code, fm.fund_code
            """,
            fund_params,
        )
        by_fund = [
            {"fund_master_pk": r[0], "fund_code": r[1], "fund_name": r[2], "scope_code": r[3], "is_restricted": r[4],
             "income": r[5], "expense": r[6], "transfers_in": r[7], "transfers_out": r[8],
             "balance": r[5] - r[6] + r[7] - r[8]}
            for r in cur.fetchall()
        ]
    return {
        "financial_year_pk": year["financial_year_pk"] if year else None,
        "year_code": year["year_code"] if year else None,
        "financial_scope_pk": financial_scope_pk,
        "income_total": income, "expense_total": expense, "net": income - expense,
        "pending_transactions": pending_txn, "pending_transfers": pending_transfers, "draft_transactions": draft_txn,
        "by_fund": by_fund, "by_category": by_category,
    }


# ═══════════════════════════════════════════════════════════════════════
# Member-facing: the caller's OWN Pranami
# ═══════════════════════════════════════════════════════════════════════

_MY_PRANAMI_LIMIT = 500


@router.get("/my-pranami", response_model=S.MyPranami)
def my_pranami(user: UserContext = Depends(get_current_user), conn=Depends(get_connection)):
    """
    The signed-in member's own Pranami: INCOME of a Pranami category that is already counted
    (POSTED / SETTLED) and linked to them by Sangha Sevi or person, newest first, each with its
    ISSUED receipts. Login only - there is deliberately NO id parameter, so a caller can only ever
    read their own rows (identity comes from the token). Nothing else of the books is returned.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT t.financial_transaction_pk, t.transaction_reference, t.transaction_date, fy.year_code,
                   t.transaction_category, h.head_name AS finance_head_name, t.amount, fs.scope_name,
                   o.organization_name, t.status
              FROM nss.financial_transaction t
              JOIN nss.finance_head h ON h.finance_head_pk = t.finance_head_pk AND h.is_pranami = TRUE
              JOIN nss.financial_year fy ON fy.financial_year_pk = t.financial_year_pk
              JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
              LEFT JOIN nss.organization o ON o.organization_pk = fs.organization_pk
             WHERE t.is_active = TRUE AND t.transaction_type = 'INCOME'
               AND t.status IN {_in(_COUNTED_TXN_STATUSES)}
               AND (t.person_pk = %s OR (%s::uuid IS NOT NULL AND t.sangha_sevi_pk = %s::uuid))
             ORDER BY t.transaction_date DESC, t.created_at DESC
             LIMIT {_MY_PRANAMI_LIMIT}
            """,
            (str(user.person_pk), user.actor_pk, user.actor_pk),
        )
        items = _fetch_all(cur)
        receipts: dict = {}
        if items:
            cur.execute(
                """
                SELECT r.financial_transaction_pk, r.receipt_number, r.receipt_date, r.amount,
                       md.value_name AS payment_method_name, r.instrument_reference
                  FROM nss.financial_receipt r
                  LEFT JOIN nss.master_data md ON md.master_data_pk = r.payment_method_master_data_pk
                 WHERE r.financial_transaction_pk = ANY(%s::uuid[]) AND r.is_active = TRUE AND r.status = 'ISSUED'
                 ORDER BY r.receipt_date, r.receipt_number
                """,
                ([str(i["financial_transaction_pk"]) for i in items],),
            )
            for r in _fetch_all(cur):
                receipts.setdefault(str(r.pop("financial_transaction_pk")), []).append(r)
        for i in items:
            i["receipts"] = receipts.get(str(i["financial_transaction_pk"]), [])
    return {"sangha_sevi_id": user.sangha_sevi_id or None, "items": items}


# ═══════════════════════════════════════════════════════════════════════
# Financial years
# ═══════════════════════════════════════════════════════════════════════

_YEAR_SELECT = """
    SELECT fy.financial_year_pk, fy.year_code, fy.start_date, fy.end_date, fy.status,
           (SELECT COUNT(*) FROM nss.financial_transaction ft
             WHERE ft.financial_year_pk = fy.financial_year_pk AND ft.is_active = TRUE) AS transaction_count
      FROM nss.financial_year fy
"""


@router.get("/years", response_model=S.YearListResponse)
def list_years(user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(_YEAR_SELECT + " WHERE fy.is_active = TRUE ORDER BY fy.start_date DESC")
        items = _fetch_all(cur)
    return {"items": items, "total": len(items)}


@router.post("/years", response_model=S.YearResponse, status_code=status.HTTP_201_CREATED)
def create_year(body: S.YearCreate, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
    """Create the Financial Year starting 01 April of ``start_year`` (status PLANNED). Global authority only."""
    with conn.cursor() as cur:
        _require_global(cur, user, "create a financial year")
        code = f"{body.start_year}-{(body.start_year + 1) % 100:02d}"
        cur.execute("SELECT 1 FROM nss.financial_year WHERE year_code = %s", (code,))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Financial year {code} already exists.")
        cur.execute(
            """
            INSERT INTO nss.financial_year (year_code, start_date, end_date, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s) RETURNING financial_year_pk
            """,
            (code, date(body.start_year, 4, 1), date(body.start_year + 1, 3, 31), user.actor_pk),
        )
        pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "financial_year", pk, f"Created financial year {code}")
        cur.execute(_YEAR_SELECT + " WHERE fy.financial_year_pk = %s", (str(pk),))
        return _fetch_one(cur)


def _open_work_blockers(cur, *, year_pk=None, scope_pk=None) -> list[str]:
    """What still has to be finished before a year / scope may close."""
    if year_pk is not None:
        txn_cond, tr_cond, params = "ft.financial_year_pk = %s", "tr.financial_year_pk = %s", [str(year_pk)] * 1
    else:
        txn_cond, tr_cond, params = "ft.financial_scope_pk = %s", "(tr.source_scope_pk = %s OR tr.destination_scope_pk = %s)", [str(scope_pk)]
    cur.execute(
        f"SELECT COUNT(*) FROM nss.financial_transaction ft WHERE {txn_cond} AND ft.is_active = TRUE "
        "AND ft.status IN ('DRAFT','PENDING_APPROVAL','APPROVED')", params,
    )
    open_txn = cur.fetchone()[0]
    cur.execute(
        f"SELECT COUNT(*) FROM nss.financial_transfer tr WHERE {tr_cond} AND tr.is_active = TRUE "
        "AND tr.status IN ('DRAFT','PENDING_APPROVAL','APPROVED','EXECUTED')",
        params if year_pk is not None else params * 2,
    )
    open_tr = cur.fetchone()[0]
    blockers = []
    if open_txn:
        blockers.append(f"{open_txn} transaction(s) still DRAFT / PENDING_APPROVAL / APPROVED")
    if open_tr:
        blockers.append(f"{open_tr} transfer(s) not yet COMPLETED, REJECTED or CANCELLED")
    return blockers


@router.post("/years/{year_pk}/transition", response_model=S.YearResponse)
def transition_year(year_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_APPROVE),
                    conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        _require_global(cur, user, "change a financial year")
        year = _year_row(cur, year_pk, lock=True)
        _guard_transition(user, "year", year["status"], body.status, body.remarks, None)
        if body.status == "CLOSED":
            blockers = _open_work_blockers(cur, year_pk=year_pk)
            if blockers:
                raise _invalid("Cannot close the financial year: " + "; ".join(blockers) + ".")
        _update_row(cur, user, "financial_year", "financial_year_pk", year_pk, {"status": body.status})
        _audit(cur, user, "STATUS_CHANGE", "financial_year", year_pk, f"Financial year {year['year_code']} {year['status']} -> {body.status}",
               {"from": year["status"], "to": body.status, "remarks": _clean(body.remarks)})
        cur.execute(_YEAR_SELECT + " WHERE fy.financial_year_pk = %s", (str(year_pk),))
        return _fetch_one(cur)


# ═══════════════════════════════════════════════════════════════════════
# Financial scopes
# ═══════════════════════════════════════════════════════════════════════

_SCOPE_FROM = """
      FROM nss.financial_scope fs
      LEFT JOIN nss.organization o ON o.organization_pk = fs.organization_pk
      LEFT JOIN nss.financial_year fy ON fy.financial_year_pk = fs.financial_year_pk
      LEFT JOIN nss.financial_scope ps ON ps.financial_scope_pk = fs.parent_scope_pk
"""
_SCOPE_SELECT = """
    SELECT fs.financial_scope_pk, fs.scope_code, fs.scope_name, fs.scope_type, fs.organization_pk,
           o.organization_name, fs.financial_year_pk, fy.year_code, fs.parent_scope_pk,
           ps.scope_code AS parent_scope_code, fs.status,
           (SELECT COUNT(*) FROM nss.fund_master fm WHERE fm.financial_scope_pk = fs.financial_scope_pk AND fm.is_active = TRUE) AS fund_count,
           (SELECT COUNT(*) FROM nss.financial_transaction ft WHERE ft.financial_scope_pk = fs.financial_scope_pk AND ft.is_active = TRUE) AS transaction_count
""" + _SCOPE_FROM


def _scope_response(cur, scope_pk) -> dict:
    cur.execute(_SCOPE_SELECT + " WHERE fs.financial_scope_pk = %s", (str(scope_pk),))
    return _fetch_one(cur)


def _require_active_organization(cur, organization_pk, label: str) -> None:
    cur.execute("SELECT 1 FROM nss.organization WHERE organization_pk = %s AND is_active = TRUE", (str(organization_pk),))
    if cur.fetchone() is None:
        raise _invalid(f"{label} not found or inactive.")


def _check_parent_scope(cur, user: UserContext, parent_pk, own_pk=None) -> None:
    parent = _scope_row(cur, parent_pk)
    _require_org_access(cur, user, parent["organization_pk"], "attach to this parent financial scope")
    if own_pk is not None:
        node, hops = parent, 0
        while node is not None and hops <= _MAX_PARENT_WALK:
            if str(node["financial_scope_pk"]) == str(own_pk):
                raise _invalid("A financial scope cannot be its own ancestor.")
            node = _scope_row(cur, node["parent_scope_pk"]) if node["parent_scope_pk"] else None
            hops += 1


@router.get("/scopes", response_model=S.ScopeListResponse)
def list_scopes(
    q: str | None = Query(None, description="Matches scope code or name"),
    scope_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    organization_pk: UUID | None = Query(None),
    financial_year_pk: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        vis, params = _visible(cur, user, "fs.organization_pk")
        where = ["fs.is_active = TRUE", vis]
        if scope_type:
            where.append("fs.scope_type = %s"); params.append(scope_type)
        if status_filter:
            where.append("fs.status = %s"); params.append(status_filter)
        if organization_pk:
            where.append("fs.organization_pk = %s"); params.append(str(organization_pk))
        if financial_year_pk:
            where.append("fs.financial_year_pk = %s"); params.append(str(financial_year_pk))
        if q and q.strip():
            where.append("(fs.scope_code ILIKE %s OR fs.scope_name ILIKE %s)"); params += [f"%{q.strip()}%"] * 2
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_SCOPE_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_SCOPE_SELECT + f" WHERE {where_sql} ORDER BY fs.scope_code LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return _paged(_fetch_all(cur), total, page, page_size)


@router.post("/scopes", response_model=S.ScopeResponse, status_code=status.HTTP_201_CREATED)
def create_scope(body: S.ScopeCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Create a Financial Scope (status DRAFT). Admin scope on its organization; none -> global authority only."""
    if body.scope_type not in S.SCOPE_TYPES:
        raise _invalid(f"scope_type must be one of: {', '.join(S.SCOPE_TYPES)}.")
    code, name = _clean(body.scope_code), _clean(body.scope_name)
    if not code or not name:
        raise _invalid("scope_code and scope_name cannot be blank.")
    if body.scope_type == "ORGANIZATION" and body.organization_pk is None:
        raise _invalid("An ORGANIZATION scope must name its organization.")
    with conn.cursor() as cur:
        _require_org_access(cur, user, body.organization_pk, "create a financial scope")
        if body.organization_pk is not None:
            _require_active_organization(cur, body.organization_pk, "Organization")
        if body.financial_year_pk is not None:
            _year_row(cur, body.financial_year_pk)
        if body.parent_scope_pk is not None:
            _check_parent_scope(cur, user, body.parent_scope_pk)
        cur.execute("SELECT 1 FROM nss.financial_scope WHERE scope_code = %s", (code,))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Scope code {code} already exists.")
        cur.execute(
            """
            INSERT INTO nss.financial_scope
                (scope_code, scope_name, scope_type, organization_pk, financial_year_pk, parent_scope_pk, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING financial_scope_pk
            """,
            (code, name, body.scope_type, str(body.organization_pk) if body.organization_pk else None,
             str(body.financial_year_pk) if body.financial_year_pk else None,
             str(body.parent_scope_pk) if body.parent_scope_pk else None, user.actor_pk),
        )
        pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "financial_scope", pk, f"Created financial scope {code}")
        return _scope_response(cur, pk)


@router.get("/scopes/{scope_pk}", response_model=S.ScopeResponse)
def get_scope(scope_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        scope = _scope_row(cur, scope_pk)
        _require_org_access(cur, user, scope["organization_pk"], "view this financial scope")
        return _scope_response(cur, scope_pk)


@router.patch("/scopes/{scope_pk}", response_model=S.ScopeResponse)
def update_scope(scope_pk: UUID, body: S.ScopeUpdate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        scope = _scope_row(cur, scope_pk, lock=True)
        _require_org_access(cur, user, scope["organization_pk"], "change this financial scope")
        if scope["status"] not in ("DRAFT", "ACTIVE"):
            raise _invalid(f"A {scope['status']} financial scope can no longer be edited.")
        values: dict = {}
        sent = body.model_fields_set
        if "scope_name" in sent and body.scope_name is not None:
            name = _clean(body.scope_name)
            if not name:
                raise _invalid("scope_name cannot be blank.")
            values["scope_name"] = name
        if "financial_year_pk" in sent:
            if body.financial_year_pk is not None:
                _year_row(cur, body.financial_year_pk)
            values["financial_year_pk"] = str(body.financial_year_pk) if body.financial_year_pk else None
        if "parent_scope_pk" in sent:
            if body.parent_scope_pk is not None:
                _check_parent_scope(cur, user, body.parent_scope_pk, own_pk=scope_pk)
            values["parent_scope_pk"] = str(body.parent_scope_pk) if body.parent_scope_pk else None
        if values:
            _update_row(cur, user, "financial_scope", "financial_scope_pk", scope_pk, values)
            _audit(cur, user, "UPDATE", "financial_scope", scope_pk, f"Updated financial scope {scope['scope_code']}", {"fields": sorted(values)})
        return _scope_response(cur, scope_pk)


@router.post("/scopes/{scope_pk}/transition", response_model=S.ScopeResponse)
def transition_scope(scope_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        scope = _scope_row(cur, scope_pk, lock=True)
        _require_org_access(cur, user, scope["organization_pk"], "change this financial scope")
        _guard_transition(user, "scope", scope["status"], body.status, body.remarks, None)
        if body.status == "CLOSED":
            blockers = _open_work_blockers(cur, scope_pk=scope_pk)
            if blockers:
                raise _invalid("Cannot close the financial scope: " + "; ".join(blockers) + ".")
        _update_row(cur, user, "financial_scope", "financial_scope_pk", scope_pk, {"status": body.status})
        _audit(cur, user, "STATUS_CHANGE", "financial_scope", scope_pk, f"Scope {scope['scope_code']} {scope['status']} -> {body.status}",
               {"from": scope["status"], "to": body.status, "remarks": _clean(body.remarks)})
        return _scope_response(cur, scope_pk)


# ═══════════════════════════════════════════════════════════════════════
# Funds
# ═══════════════════════════════════════════════════════════════════════

_FUND_FROM = """
      FROM nss.fund_master fm
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = fm.financial_scope_pk
      LEFT JOIN nss.organization o ON o.organization_pk = fm.organization_pk
"""
_FUND_SELECT = f"""
    SELECT fm.fund_master_pk, fm.fund_code, fm.fund_name, fm.fund_type, fm.financial_scope_pk,
           fs.scope_code, fs.scope_name, fm.is_restricted, fm.restriction_purpose, fm.organization_pk,
           o.organization_name, fm.status, {_balance_sql('fm.fund_master_pk')} AS balance
""" + _FUND_FROM


def _fund_response(cur, fund_pk) -> dict:
    cur.execute(_FUND_SELECT + " WHERE fm.fund_master_pk = %s", (str(fund_pk),))
    return _fetch_one(cur)


def _require_sakha(cur, organization_pk) -> None:
    cur.execute(
        """
        SELECT md.value_code FROM nss.organization o
          JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
         WHERE o.organization_pk = %s AND o.is_active = TRUE
        """,
        (str(organization_pk),),
    )
    row = cur.fetchone()
    if row is None or row[0] not in SAKHA_LIKE_ORG_TYPES:
        raise _invalid("A Sinking Fund must name the Sakha it belongs to (FIN-BR-023/024).")


@router.get("/funds", response_model=S.FundListResponse)
def list_funds(
    q: str | None = Query(None, description="Matches fund code or name"),
    financial_scope_pk: UUID | None = Query(None),
    fund_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    is_restricted: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        vis, params = _visible(cur, user, "fs.organization_pk")
        where = ["fm.is_active = TRUE", vis]
        if financial_scope_pk:
            where.append("fm.financial_scope_pk = %s"); params.append(str(financial_scope_pk))
        if fund_type:
            where.append("fm.fund_type = %s"); params.append(fund_type)
        if status_filter:
            where.append("fm.status = %s"); params.append(status_filter)
        if is_restricted is not None:
            where.append("fm.is_restricted = %s"); params.append(is_restricted)
        if q and q.strip():
            where.append("(fm.fund_code ILIKE %s OR fm.fund_name ILIKE %s)"); params += [f"%{q.strip()}%"] * 2
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_FUND_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_FUND_SELECT + f" WHERE {where_sql} ORDER BY fs.scope_code, fm.fund_code LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return _paged(_fetch_all(cur), total, page, page_size)


@router.post("/funds", response_model=S.FundResponse, status_code=status.HTTP_201_CREATED)
def create_fund(body: S.FundCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    if body.fund_type not in S.FUND_TYPES:
        raise _invalid(f"fund_type must be one of: {', '.join(S.FUND_TYPES)}.")
    code, name, purpose = _clean(body.fund_code), _clean(body.fund_name), _clean(body.restriction_purpose)
    if not code or not name:
        raise _invalid("fund_code and fund_name cannot be blank.")
    if body.is_restricted and not purpose:
        raise _invalid("A restricted fund must state its restriction_purpose (FIN-BR-020).")
    with conn.cursor() as cur:
        scope = _scope_row(cur, body.financial_scope_pk)
        _require_org_access(cur, user, scope["organization_pk"], "create a fund in this financial scope")
        if scope["status"] not in ("DRAFT", "ACTIVE"):
            raise _invalid(f"A {scope['status']} financial scope cannot take new funds.")
        if body.fund_type == "SINKING_FUND":
            if body.organization_pk is None:
                raise _invalid("A Sinking Fund must name the Sakha it belongs to (FIN-BR-023/024).")
            _require_sakha(cur, body.organization_pk)
        if body.organization_pk is not None:
            _require_active_organization(cur, body.organization_pk, "Organization")
            require_org_in_scope(cur, user, body.organization_pk, "create a fund for this organization")
        cur.execute("SELECT 1 FROM nss.fund_master WHERE financial_scope_pk = %s AND fund_code = %s", (str(body.financial_scope_pk), code))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Fund code {code} already exists in this scope.")
        cur.execute(
            """
            INSERT INTO nss.fund_master
                (fund_code, fund_name, fund_type, financial_scope_pk, is_restricted, restriction_purpose,
                 organization_pk, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING fund_master_pk
            """,
            (code, name, body.fund_type, str(body.financial_scope_pk), body.is_restricted, purpose,
             str(body.organization_pk) if body.organization_pk else None, user.actor_pk),
        )
        pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "fund_master", pk, f"Created fund {code} in scope {scope['scope_code']}")
        return _fund_response(cur, pk)


def _fund_access(cur, user: UserContext, fund: dict, action: str) -> dict:
    scope = _scope_row(cur, fund["financial_scope_pk"])
    _require_org_access(cur, user, scope["organization_pk"], action)
    return scope


@router.get("/funds/{fund_pk}", response_model=S.FundResponse)
def get_fund(fund_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        _fund_access(cur, user, _fund_row(cur, fund_pk), "view this fund")
        return _fund_response(cur, fund_pk)


@router.patch("/funds/{fund_pk}", response_model=S.FundResponse)
def update_fund(fund_pk: UUID, body: S.FundUpdate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        fund = _fund_row(cur, fund_pk, lock=True)
        _fund_access(cur, user, fund, "change this fund")
        if fund["status"] == "INACTIVE":
            raise _invalid("An INACTIVE fund can no longer be edited.")
        values: dict = {}
        if body.fund_name is not None:
            name = _clean(body.fund_name)
            if not name:
                raise _invalid("fund_name cannot be blank.")
            values["fund_name"] = name
        restricted = fund["is_restricted"]
        if body.is_restricted is not None and body.is_restricted != restricted:
            if fund["status"] != "DRAFT":
                raise _invalid("A fund's restriction can only be changed while it is DRAFT (FIN-BR-020).")
            values["is_restricted"] = restricted = body.is_restricted
        purpose = fund["restriction_purpose"]
        if "restriction_purpose" in body.model_fields_set:
            purpose = _clean(body.restriction_purpose)
            values["restriction_purpose"] = purpose
        if restricted and not purpose:
            raise _invalid("A restricted fund must state its restriction_purpose (FIN-BR-020).")
        if values:
            _update_row(cur, user, "fund_master", "fund_master_pk", fund_pk, values)
            _audit(cur, user, "UPDATE", "fund_master", fund_pk, f"Updated fund {fund['fund_code']}", {"fields": sorted(values)})
        return _fund_response(cur, fund_pk)


@router.post("/funds/{fund_pk}/transition", response_model=S.FundResponse)
def transition_fund(fund_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        fund = _fund_row(cur, fund_pk, lock=True)
        scope = _fund_access(cur, user, fund, "change this fund")
        _guard_transition(user, "fund", fund["status"], body.status, body.remarks, None)
        if body.status == "ACTIVE" and scope["status"] != "ACTIVE":
            raise _invalid("A fund can only be activated inside an ACTIVE financial scope.")
        _update_row(cur, user, "fund_master", "fund_master_pk", fund_pk, {"status": body.status})
        _audit(cur, user, "STATUS_CHANGE", "fund_master", fund_pk, f"Fund {fund['fund_code']} {fund['status']} -> {body.status}",
               {"from": fund["status"], "to": body.status, "remarks": _clean(body.remarks)})
        return _fund_response(cur, fund_pk)


# ═══════════════════════════════════════════════════════════════════════
# Transactions
# ═══════════════════════════════════════════════════════════════════════

_TXN_FROM = """
      FROM nss.financial_transaction t
      JOIN nss.financial_year fy ON fy.financial_year_pk = t.financial_year_pk
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
      LEFT JOIN nss.organization o ON o.organization_pk = fs.organization_pk
      LEFT JOIN nss.fund_master fm ON fm.fund_master_pk = t.fund_master_pk
      LEFT JOIN nss.finance_head fh ON fh.finance_head_pk = t.finance_head_pk
      LEFT JOIN nss.person p ON p.person_pk = t.person_pk
      LEFT JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = t.sangha_sevi_pk
"""
_TXN_SELECT = f"""
    SELECT t.financial_transaction_pk, t.transaction_reference, t.financial_year_pk, fy.year_code,
           t.financial_scope_pk, fs.scope_code, fs.scope_name, fs.organization_pk AS scope_organization_pk,
           o.organization_name AS scope_organization_name, t.fund_master_pk, fm.fund_code, fm.fund_name,
           t.transaction_type, t.finance_head_pk, fh.head_name AS finance_head_name, t.transaction_category,
           t.amount, t.transaction_date, t.description,
           t.person_pk, {_PERSON_NAME_SQL.format(a='p')} AS person_name, t.sangha_sevi_pk, ss.sangha_sevi_id,
           t.status, t.created_by_sangha_sevi_pk, t.created_at,
           COALESCE((SELECT SUM(r.amount) FROM nss.financial_receipt r
                      WHERE r.financial_transaction_pk = t.financial_transaction_pk AND r.is_active = TRUE
                        AND r.status = 'ISSUED'), 0) AS receipted_amount,
           COALESCE((SELECT SUM(py.amount) FROM nss.financial_payment py
                      WHERE py.financial_transaction_pk = t.financial_transaction_pk AND py.is_active = TRUE
                        AND py.status = 'COMPLETED'), 0) AS paid_amount
""" + _TXN_FROM


def _txn_response(cur, txn_pk) -> dict:
    cur.execute(_TXN_SELECT + " WHERE t.financial_transaction_pk = %s", (str(txn_pk),))
    return _fetch_one(cur)


def _txn_row(cur, user: UserContext, txn_pk, action: str, *, lock: bool = False) -> dict:
    """The stored transaction with its scope's organization, after the admin-scope check."""
    cur.execute(
        """
        SELECT t.financial_transaction_pk, t.transaction_reference, t.financial_year_pk, t.financial_scope_pk,
               t.fund_master_pk, t.transaction_type, t.finance_head_pk, t.transaction_category, t.amount, t.transaction_date,
               t.description, t.person_pk, t.sangha_sevi_pk, t.status, t.created_by_sangha_sevi_pk,
               fs.organization_pk AS scope_organization_pk
          FROM nss.financial_transaction t
          JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
         WHERE t.financial_transaction_pk = %s AND t.is_active = TRUE
        """ + (" FOR UPDATE OF t" if lock else ""),
        (str(txn_pk),),
    )
    row = _fetch_one(cur)
    if row is None:
        raise _not_found("Transaction")
    _require_org_access(cur, user, row["scope_organization_pk"], action)
    return row


def _head_row(cur, head_pk) -> dict:
    cur.execute(
        """
        SELECT finance_head_pk, organization_pk, head_code, head_name, direction, is_restricted, restriction_purpose,
               required_fund_type, is_pranami, allow_upi, collection_scope_pk, collection_fund_pk,
               collection_account_pk, status
          FROM nss.finance_head WHERE finance_head_pk = %s AND is_active = TRUE
        """,
        (str(head_pk),),
    )
    row = _fetch_one(cur)
    if row is None:
        raise _invalid("Finance head not found.")
    return row


def _same_org(a, b) -> bool:
    return (a is None and b is None) or (a is not None and b is not None and str(a) == str(b))


def _check_head(head: dict, *, scope: dict, txn_type: str, fund: dict | None) -> None:
    """
    The rules a finance head imposes on an entry (pure: no database). A head is DATA, so every rule here comes from
    its columns - there is no category list in the code:
      - ACTIVE, and owned by the scope's organization (a scope with no organization uses the global templates);
      - direction: INCOME needs an income head, EXPENSE an expense head (ADJUSTMENT may use either);
      - restricted money stays restricted (FIN-BR-019..022): an income head that is restricted needs a restricted fund,
        a restricted expense head must draw on a restricted fund and an expense from a restricted fund must use a
        restricted head;
      - required_fund_type (e.g. SINKING_FUND, which must also name its Sakha, FIN-BR-023/024).
    """
    code = head["head_code"]
    if head["status"] != "ACTIVE":
        raise _invalid(f"Finance head {code} is {head['status']}; only an ACTIVE head can take entries.")
    if not _same_org(head["organization_pk"], scope["organization_pk"]):
        raise _invalid(f"Finance head {code} belongs to a different organization than this financial scope.")
    if txn_type in ("INCOME", "EXPENSE") and head["direction"] != txn_type:
        raise _invalid(f"Finance head {code} is an {head['direction']} head; this entry is an {txn_type}.")
    if txn_type == "INCOME" and head["is_restricted"] and (fund is None or not fund["is_restricted"]):
        raise _invalid(f"{code} is a restricted head and must be recorded against a restricted fund (FIN-BR-019/022).")
    if txn_type == "EXPENSE":
        if fund is not None and fund["is_restricted"] and not head["is_restricted"]:
            raise _invalid("An expense from a restricted fund must use a restricted finance head (FIN-BR-021).")
        if head["is_restricted"] and (fund is None or not fund["is_restricted"]):
            raise _invalid(f"{code} is a restricted head and must name a restricted fund (FIN-BR-020).")
    wanted = head["required_fund_type"]
    if wanted:
        if fund is None or fund["fund_type"] != wanted:
            raise _invalid(f"{code} must be recorded against a {wanted} fund.")
        if wanted == "SINKING_FUND" and fund["organization_pk"] is None:
            raise _invalid(f"{code} must be recorded against a SINKING_FUND that names its Sakha (FIN-BR-023/024).")


def _check_transaction(cur, *, year_pk, scope_pk, fund_pk, txn_date, txn_type, head_pk, amount) -> tuple[dict | None, dict]:
    """
    Every rule a transaction must satisfy to be recorded, submitted, approved or posted: open year, active scope,
    date inside the year, fund of the same scope and ACTIVE, and the finance head's own rules (_check_head).
    Returns (fund row or None, head row).
    """
    if txn_type not in S.TRANSACTION_TYPES:
        raise _invalid(f"transaction_type must be one of: {', '.join(S.TRANSACTION_TYPES)}.")

    year = _year_row(cur, year_pk)
    if year["status"] != "OPEN":
        raise _invalid(f"Financial year {year['year_code']} is {year['status']}; transactions need an OPEN year (FIN-BR-003).")
    if not (year["start_date"] <= txn_date <= year["end_date"]):
        raise _invalid(f"transaction_date must fall inside financial year {year['year_code']} ({year['start_date']} to {year['end_date']}).")
    scope = _scope_row(cur, scope_pk)
    if scope["status"] != "ACTIVE":
        raise _invalid(f"Financial scope {scope['scope_code']} is {scope['status']}; transactions need an ACTIVE scope (FIN-BR-006).")
    if scope["financial_year_pk"] is not None and str(scope["financial_year_pk"]) != str(year_pk):
        raise _invalid(f"Financial scope {scope['scope_code']} belongs to a different financial year.")

    fund = None
    if fund_pk is not None:
        fund = _fund_row(cur, fund_pk)
        if str(fund["financial_scope_pk"]) != str(scope_pk):
            raise _invalid("The fund belongs to a different financial scope.")
        if fund["status"] != "ACTIVE":
            raise _invalid(f"Fund {fund['fund_code']} is {fund['status']}; only an ACTIVE fund can take transactions.")

    head = _head_row(cur, head_pk)
    _check_head(head, scope=scope, txn_type=txn_type, fund=fund)
    return fund, head


def _check_restricted_balance(cur, txn: dict, fund: dict | None) -> None:
    """A restricted expense can never exceed what the fund holds (FIN-BR-021)."""
    if txn["transaction_type"] == "EXPENSE" and fund is not None and fund["is_restricted"]:
        balance = _lock_and_balance(cur, fund["fund_master_pk"])
        if txn["amount"] > balance:
            raise _invalid(f"Fund {fund['fund_code']} holds only {balance}; the expense of {txn['amount']} exceeds it (FIN-BR-021).")


def _resolve_member(cur, user: UserContext, sangha_sevi_id: str) -> tuple[str, str]:
    """(sangha_sevi_pk, person_pk) of an ACTIVE member by business id; the member must be inside the caller's admin scope."""
    cur.execute(
        "SELECT sangha_sevi_pk, person_pk FROM nss.sangha_sevi WHERE sangha_sevi_id = %s AND is_active = TRUE",
        (sangha_sevi_id.strip(),),
    )
    row = cur.fetchone()
    if row is None:
        raise _invalid(f"No active member with Sangha Sevi ID {sangha_sevi_id.strip()}.")
    require_person_in_scope(cur, user, row[1], "record a transaction for this member")
    return str(row[0]), str(row[1])


def _check_links(cur, person_pk, sangha_sevi_pk) -> None:
    if person_pk is not None:
        _require_exists(cur, "person", "person_pk", person_pk, "Person")
    if sangha_sevi_pk is not None:
        _require_exists(cur, "sangha_sevi", "sangha_sevi_pk", sangha_sevi_pk, "Sangha Sevi")


@router.get("/transactions", response_model=S.TransactionListResponse)
def list_transactions(
    q: str | None = Query(None, description="Matches reference, description or donor name"),
    financial_year_pk: UUID | None = Query(None),
    financial_scope_pk: UUID | None = Query(None),
    fund_master_pk: UUID | None = Query(None),
    transaction_type: str | None = Query(None),
    transaction_category: str | None = Query(None, description="Head CODE (matches across Sanghas)"),
    finance_head_pk: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    person_pk: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        vis, params = _visible(cur, user, "fs.organization_pk")
        where = ["t.is_active = TRUE", vis]
        for column, value in (
            ("t.financial_year_pk", financial_year_pk), ("t.financial_scope_pk", financial_scope_pk),
            ("t.fund_master_pk", fund_master_pk), ("t.person_pk", person_pk), ("t.finance_head_pk", finance_head_pk),
        ):
            if value is not None:
                where.append(f"{column} = %s"); params.append(str(value))
        for column, value in (("t.transaction_type", transaction_type), ("t.transaction_category", transaction_category), ("t.status", status_filter)):
            if value:
                where.append(f"{column} = %s"); params.append(value)
        if date_from:
            where.append("t.transaction_date >= %s"); params.append(date_from)
        if date_to:
            where.append("t.transaction_date <= %s"); params.append(date_to)
        if q and q.strip():
            like = f"%{q.strip()}%"
            where.append(f"(t.transaction_reference ILIKE %s OR t.description ILIKE %s OR {_PERSON_NAME_SQL.format(a='p')} ILIKE %s)")
            params += [like] * 3
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_TXN_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_TXN_SELECT + f" WHERE {where_sql} ORDER BY t.transaction_date DESC, t.created_at DESC LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return _paged(_fetch_all(cur), total, page, page_size)


@router.post("/transactions", response_model=S.TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(body: S.TransactionCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Record a DRAFT transaction. Admin scope on the Financial Scope's organization."""
    with conn.cursor() as cur:
        scope = _scope_row(cur, body.financial_scope_pk)
        _require_org_access(cur, user, scope["organization_pk"], "record a transaction in this financial scope")
        _, head = _check_transaction(
            cur, year_pk=body.financial_year_pk, scope_pk=body.financial_scope_pk, fund_pk=body.fund_master_pk,
            txn_date=body.transaction_date, txn_type=body.transaction_type, head_pk=body.finance_head_pk,
            amount=body.amount,
        )
        person_pk, sevi_pk = body.person_pk, body.sangha_sevi_pk
        if _clean(body.sangha_sevi_id):
            sevi_pk, resolved_person = _resolve_member(cur, user, body.sangha_sevi_id)
            person_pk = person_pk or resolved_person
        _check_links(cur, person_pk, sevi_pk)
        reference = next_id(cur, "FINANCIAL_TRANSACTION")
        cur.execute(
            """
            INSERT INTO nss.financial_transaction
                (transaction_reference, financial_year_pk, financial_scope_pk, fund_master_pk, transaction_type,
                 finance_head_pk, transaction_category, amount, transaction_date, description, person_pk,
                 sangha_sevi_pk, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING financial_transaction_pk
            """,
            (reference, str(body.financial_year_pk), str(body.financial_scope_pk),
             str(body.fund_master_pk) if body.fund_master_pk else None, body.transaction_type,
             str(head["finance_head_pk"]), head["head_code"], body.amount, body.transaction_date, _clean(body.description),
             str(person_pk) if person_pk else None, str(sevi_pk) if sevi_pk else None,
             user.actor_pk),
        )
        pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "financial_transaction", pk, f"Recorded {body.transaction_type} {reference}",
               {"reference": reference, "amount": str(body.amount), "head": head["head_code"]})
        return _txn_response(cur, pk)


@router.get("/transactions/{txn_pk}", response_model=S.TransactionResponse)
def get_transaction(txn_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        _txn_row(cur, user, txn_pk, "view this transaction")
        return _txn_response(cur, txn_pk)


@router.patch("/transactions/{txn_pk}", response_model=S.TransactionResponse)
def update_transaction(txn_pk: UUID, body: S.TransactionUpdate, user: UserContext = Depends(_MANAGE),
                       conn=Depends(get_write_connection)):
    """Edit a DRAFT transaction (everything else is immutable; correct by cancelling and re-recording)."""
    with conn.cursor() as cur:
        txn = _txn_row(cur, user, txn_pk, "change this transaction", lock=True)
        if txn["status"] != "DRAFT":
            raise _invalid(f"Only a DRAFT transaction can be edited; this one is {txn['status']} (FIN-BR-051).")
        merged = {k: txn[k] for k in ("financial_year_pk", "financial_scope_pk", "fund_master_pk", "transaction_type",
                                      "finance_head_pk", "amount", "transaction_date", "description",
                                      "person_pk", "sangha_sevi_pk")}
        explicit = set(body.model_fields_set) - {"sangha_sevi_id"}          # real columns the caller sent
        for field in explicit:
            value = getattr(body, field)
            if value is None and field not in ("fund_master_pk", "description", "person_pk", "sangha_sevi_pk"):
                raise _invalid(f"{field} cannot be cleared.")
            merged[field] = value
        sent = set(explicit)
        if "sangha_sevi_id" in body.model_fields_set:       # a business id, not a column: becomes the two member FKs
            if _clean(body.sangha_sevi_id):
                merged["sangha_sevi_pk"], merged["person_pk"] = _resolve_member(cur, user, body.sangha_sevi_id)
            else:
                merged["sangha_sevi_pk"] = merged["person_pk"] = None
            sent |= {"sangha_sevi_pk", "person_pk"}
        if "financial_scope_pk" in sent and str(merged["financial_scope_pk"]) != str(txn["financial_scope_pk"]):
            new_scope = _scope_row(cur, merged["financial_scope_pk"])
            _require_org_access(cur, user, new_scope["organization_pk"], "move a transaction into this financial scope")
        _, head = _check_transaction(
            cur, year_pk=merged["financial_year_pk"], scope_pk=merged["financial_scope_pk"], fund_pk=merged["fund_master_pk"],
            txn_date=merged["transaction_date"], txn_type=merged["transaction_type"], head_pk=merged["finance_head_pk"],
            amount=merged["amount"],
        )
        _check_links(cur, merged["person_pk"], merged["sangha_sevi_pk"])
        values = {}
        if "finance_head_pk" in sent:
            values["transaction_category"] = head["head_code"]          # keep the immutable snapshot in step
        for field in sent:
            value = merged[field]
            if field == "description":
                value = _clean(value)
            elif isinstance(value, UUID):
                value = str(value)
            values[field] = value
        if values:
            _update_row(cur, user, "financial_transaction", "financial_transaction_pk", txn_pk, values)
            _audit(cur, user, "UPDATE", "financial_transaction", txn_pk, f"Updated transaction {txn['transaction_reference']}", {"fields": sorted(values)})
        return _txn_response(cur, txn_pk)


@router.post("/transactions/{txn_pk}/transition", response_model=S.TransactionResponse)
def transition_transaction(txn_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_MANAGE),
                           conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        txn = _txn_row(cur, user, txn_pk, "act on this transaction", lock=True)
        _, self_approved = _guard_transition(user, "transaction", txn["status"], body.status, body.remarks,
                                             txn["created_by_sangha_sevi_pk"])
        if body.status in ("PENDING_APPROVAL", "APPROVED", "POSTED"):
            fund, _ = _check_transaction(
                cur, year_pk=txn["financial_year_pk"], scope_pk=txn["financial_scope_pk"], fund_pk=txn["fund_master_pk"],
                txn_date=txn["transaction_date"], txn_type=txn["transaction_type"], head_pk=txn["finance_head_pk"],
                amount=txn["amount"],
            )
            if body.status in ("APPROVED", "POSTED"):
                _check_restricted_balance(cur, txn, fund)
        _update_row(cur, user, "financial_transaction", "financial_transaction_pk", txn_pk, {"status": body.status})
        _audit(cur, user, "STATUS_CHANGE", "financial_transaction", txn_pk,
               f"Transaction {txn['transaction_reference']} {txn['status']} -> {body.status}",
               {"from": txn["status"], "to": body.status, "remarks": _clean(body.remarks),
                **({"self_approved": True} if self_approved else {})})
        return _txn_response(cur, txn_pk)


# ═══════════════════════════════════════════════════════════════════════
# Receipt / payment evidence
# ═══════════════════════════════════════════════════════════════════════

def _method_pk(cur, code: str | None):
    return get_master_data_pk(cur, "PAYMENT_METHOD", code, client_supplied=True) if code else None


def _evidence_total(cur, table: str, txn_pk, live_statuses: tuple, exclude_pk=None, pk_col: str = "") -> Decimal:
    cond, params = "", [str(txn_pk), list(live_statuses)]
    if exclude_pk is not None:
        cond = f" AND {pk_col} <> %s"
        params.append(str(exclude_pk))
    cur.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM nss.{table} WHERE financial_transaction_pk = %s AND is_active = TRUE "
        f"AND status = ANY(%s){cond}",
        params,
    )
    return cur.fetchone()[0]


_RECEIPT_SELECT = f"""
    SELECT r.financial_receipt_pk, r.receipt_number, r.financial_transaction_pk, t.transaction_reference,
           r.receipt_date, r.amount, r.received_from, md.value_code AS payment_method_code,
           md.value_name AS payment_method_name, r.instrument_reference, r.person_pk,
           {_PERSON_NAME_SQL.format(a='p')} AS person_name, r.status, r.cancellation_reason, r.created_at
"""
_RECEIPT_FROM = """
      FROM nss.financial_receipt r
      JOIN nss.financial_transaction t ON t.financial_transaction_pk = r.financial_transaction_pk
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
      LEFT JOIN nss.master_data md ON md.master_data_pk = r.payment_method_master_data_pk
      LEFT JOIN nss.person p ON p.person_pk = r.person_pk
"""


def _receipt_response(cur, pk) -> dict:
    cur.execute(_RECEIPT_SELECT + _RECEIPT_FROM + " WHERE r.financial_receipt_pk = %s", (str(pk),))
    return _fetch_one(cur)


@router.post("/transactions/{txn_pk}/receipts", response_model=S.ReceiptResponse, status_code=status.HTTP_201_CREATED)
def create_receipt(txn_pk: UUID, body: S.ReceiptCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Draft a receipt for a POSTED / SETTLED INCOME transaction (issue it with /receipts/{pk}/transition)."""
    with conn.cursor() as cur:
        txn = _txn_row(cur, user, txn_pk, "record a receipt for this transaction", lock=True)
        if txn["transaction_type"] != "INCOME":
            raise _invalid("Receipts belong to INCOME transactions (FIN-BR-031).")
        if txn["status"] not in _COUNTED_TXN_STATUSES:
            raise _invalid(f"A receipt needs a POSTED or SETTLED transaction; this one is {txn['status']}.")
        already = _evidence_total(cur, "financial_receipt", txn_pk, ("DRAFT", "ISSUED"))
        if already + body.amount > txn["amount"]:
            raise _invalid(f"Receipts would total {already + body.amount}, more than the transaction amount {txn['amount']}.")
        if body.person_pk is not None:
            _require_exists(cur, "person", "person_pk", body.person_pk, "Person")
        number = next_id(cur, "FINANCIAL_RECEIPT")
        cur.execute(
            """
            INSERT INTO nss.financial_receipt
                (receipt_number, financial_transaction_pk, receipt_date, amount, received_from,
                 payment_method_master_data_pk, instrument_reference, person_pk, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING financial_receipt_pk
            """,
            (number, str(txn_pk), body.receipt_date, body.amount, _clean(body.received_from), _method_pk(cur, body.payment_method_code),
             _clean(body.instrument_reference), str(body.person_pk) if body.person_pk else None, user.actor_pk),
        )
        pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "financial_receipt", pk, f"Drafted receipt {number} for {txn['transaction_reference']}",
               {"amount": str(body.amount)})
        return _receipt_response(cur, pk)


@router.get("/receipts", response_model=S.ReceiptListResponse)
def list_receipts(
    financial_transaction_pk: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None, description="Matches receipt number, payer or instrument reference"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        vis, params = _visible(cur, user, "fs.organization_pk")
        where = ["r.is_active = TRUE", vis]
        if financial_transaction_pk:
            where.append("r.financial_transaction_pk = %s"); params.append(str(financial_transaction_pk))
        if status_filter:
            where.append("r.status = %s"); params.append(status_filter)
        if q and q.strip():
            where.append("(r.receipt_number ILIKE %s OR r.received_from ILIKE %s OR r.instrument_reference ILIKE %s)"); params += [f"%{q.strip()}%"] * 3
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_RECEIPT_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_RECEIPT_SELECT + _RECEIPT_FROM + f" WHERE {where_sql} ORDER BY r.created_at DESC LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return _paged(_fetch_all(cur), total, page, page_size)


@router.post("/receipts/{receipt_pk}/transition", response_model=S.ReceiptResponse)
def transition_receipt(receipt_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT financial_receipt_pk, receipt_number, financial_transaction_pk, amount, status "
            "FROM nss.financial_receipt WHERE financial_receipt_pk = %s AND is_active = TRUE FOR UPDATE",
            (str(receipt_pk),),
        )
        receipt = _fetch_one(cur)
        if receipt is None:
            raise _not_found("Receipt")
        txn = _txn_row(cur, user, receipt["financial_transaction_pk"], "act on this receipt", lock=True)
        _guard_transition(user, "receipt", receipt["status"], body.status, body.remarks, None)
        values: dict = {"status": body.status}
        if body.status == "ISSUED":
            if txn["status"] not in _COUNTED_TXN_STATUSES:
                raise _invalid(f"The transaction is {txn['status']}; a receipt can only be issued against a POSTED or SETTLED one.")
            others = _evidence_total(cur, "financial_receipt", txn["financial_transaction_pk"], ("ISSUED",), receipt_pk, "financial_receipt_pk")
            if others + receipt["amount"] > txn["amount"]:
                raise _invalid("Issued receipts would exceed the transaction amount.")
        if body.status == "CANCELLED":
            values["cancellation_reason"] = _clean(body.remarks)
        _update_row(cur, user, "financial_receipt", "financial_receipt_pk", receipt_pk, values)
        _audit(cur, user, "STATUS_CHANGE", "financial_receipt", receipt_pk, f"Receipt {receipt['receipt_number']} {receipt['status']} -> {body.status}",
               {"from": receipt["status"], "to": body.status, "remarks": _clean(body.remarks)})
        return _receipt_response(cur, receipt_pk)


_PAYMENT_SELECT = f"""
    SELECT py.financial_payment_pk, py.payment_reference, py.financial_transaction_pk, t.transaction_reference,
           py.payment_date, py.amount, py.paid_to, md.value_code AS payment_method_code,
           md.value_name AS payment_method_name, py.instrument_reference, py.person_pk,
           {_PERSON_NAME_SQL.format(a='p')} AS person_name, py.status, py.created_at
"""
_PAYMENT_FROM = """
      FROM nss.financial_payment py
      JOIN nss.financial_transaction t ON t.financial_transaction_pk = py.financial_transaction_pk
      JOIN nss.financial_scope fs ON fs.financial_scope_pk = t.financial_scope_pk
      LEFT JOIN nss.master_data md ON md.master_data_pk = py.payment_method_master_data_pk
      LEFT JOIN nss.person p ON p.person_pk = py.person_pk
"""


def _payment_response(cur, pk) -> dict:
    cur.execute(_PAYMENT_SELECT + _PAYMENT_FROM + " WHERE py.financial_payment_pk = %s", (str(pk),))
    return _fetch_one(cur)


@router.post("/transactions/{txn_pk}/payments", response_model=S.PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(txn_pk: UUID, body: S.PaymentCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Draft a payment for an APPROVED / POSTED / SETTLED EXPENSE transaction."""
    with conn.cursor() as cur:
        txn = _txn_row(cur, user, txn_pk, "record a payment for this transaction", lock=True)
        if txn["transaction_type"] != "EXPENSE":
            raise _invalid("Payments belong to EXPENSE transactions (FIN-BR-035).")
        if txn["status"] not in ("APPROVED", "POSTED", "SETTLED"):
            raise _invalid(f"A payment needs an APPROVED or POSTED transaction; this one is {txn['status']} (FIN-BR-021).")
        already = _evidence_total(cur, "financial_payment", txn_pk, ("DRAFT", "APPROVED", "INITIATED", "COMPLETED"))
        if already + body.amount > txn["amount"]:
            raise _invalid(f"Payments would total {already + body.amount}, more than the transaction amount {txn['amount']}.")
        if body.person_pk is not None:
            _require_exists(cur, "person", "person_pk", body.person_pk, "Person")
        reference = next_id(cur, "FINANCIAL_PAYMENT")
        cur.execute(
            """
            INSERT INTO nss.financial_payment
                (payment_reference, financial_transaction_pk, payment_date, amount, paid_to,
                 payment_method_master_data_pk, instrument_reference, person_pk, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING financial_payment_pk
            """,
            (reference, str(txn_pk), body.payment_date, body.amount, _clean(body.paid_to), _method_pk(cur, body.payment_method_code),
             _clean(body.instrument_reference), str(body.person_pk) if body.person_pk else None, user.actor_pk),
        )
        pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "financial_payment", pk, f"Drafted payment {reference} for {txn['transaction_reference']}",
               {"amount": str(body.amount)})
        return _payment_response(cur, pk)


@router.get("/payments", response_model=S.PaymentListResponse)
def list_payments(
    financial_transaction_pk: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None, description="Matches payment reference, payee or instrument reference"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        vis, params = _visible(cur, user, "fs.organization_pk")
        where = ["py.is_active = TRUE", vis]
        if financial_transaction_pk:
            where.append("py.financial_transaction_pk = %s"); params.append(str(financial_transaction_pk))
        if status_filter:
            where.append("py.status = %s"); params.append(status_filter)
        if q and q.strip():
            where.append("(py.payment_reference ILIKE %s OR py.paid_to ILIKE %s OR py.instrument_reference ILIKE %s)"); params += [f"%{q.strip()}%"] * 3
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_PAYMENT_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_PAYMENT_SELECT + _PAYMENT_FROM + f" WHERE {where_sql} ORDER BY py.created_at DESC LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return _paged(_fetch_all(cur), total, page, page_size)


@router.post("/payments/{payment_pk}/transition", response_model=S.PaymentResponse)
def transition_payment(payment_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT financial_payment_pk, payment_reference, financial_transaction_pk, amount, status, created_by_sangha_sevi_pk "
            "FROM nss.financial_payment WHERE financial_payment_pk = %s AND is_active = TRUE FOR UPDATE",
            (str(payment_pk),),
        )
        payment = _fetch_one(cur)
        if payment is None:
            raise _not_found("Payment")
        txn = _txn_row(cur, user, payment["financial_transaction_pk"], "act on this payment", lock=True)
        _, self_approved = _guard_transition(user, "payment", payment["status"], body.status, body.remarks,
                                             payment["created_by_sangha_sevi_pk"])
        if body.status in ("APPROVED", "INITIATED", "COMPLETED") and txn["status"] not in ("APPROVED", "POSTED", "SETTLED"):
            raise _invalid(f"The transaction is {txn['status']}; its payments cannot move forward.")
        # Kendra / central Mahila money: Governing Body resolution, President's order, Treasurer + Secretary (Bye-Law).
        authority_service.enforce_transition(cur, user.person_pk, "payment", payment_pk, txn["scope_organization_pk"],
                                             payment["status"], body.status)
        _update_row(cur, user, "financial_payment", "financial_payment_pk", payment_pk, {"status": body.status})
        _audit(cur, user, "STATUS_CHANGE", "financial_payment", payment_pk, f"Payment {payment['payment_reference']} {payment['status']} -> {body.status}",
               {"from": payment["status"], "to": body.status, "remarks": _clean(body.remarks),
                **({"self_approved": True} if self_approved else {})})
        return _payment_response(cur, payment_pk)


# ═══════════════════════════════════════════════════════════════════════
# Transfers
# ═══════════════════════════════════════════════════════════════════════

_TRANSFER_FROM = """
      FROM nss.financial_transfer tr
      JOIN nss.financial_year fy ON fy.financial_year_pk = tr.financial_year_pk
      JOIN nss.financial_scope sfs ON sfs.financial_scope_pk = tr.source_scope_pk
      JOIN nss.financial_scope dfs ON dfs.financial_scope_pk = tr.destination_scope_pk
      LEFT JOIN nss.fund_master sfm ON sfm.fund_master_pk = tr.source_fund_pk
      LEFT JOIN nss.fund_master dfm ON dfm.fund_master_pk = tr.destination_fund_pk
"""
_TRANSFER_SELECT = """
    SELECT tr.financial_transfer_pk, tr.transfer_reference, tr.financial_year_pk, fy.year_code,
           tr.source_scope_pk, sfs.scope_code AS source_scope_code, sfs.scope_name AS source_scope_name,
           tr.destination_scope_pk, dfs.scope_code AS destination_scope_code, dfs.scope_name AS destination_scope_name,
           tr.source_fund_pk, sfm.fund_code AS source_fund_code, tr.destination_fund_pk, dfm.fund_code AS destination_fund_code,
           tr.amount, tr.transfer_date, tr.purpose, tr.status, tr.created_by_sangha_sevi_pk, tr.created_at
""" + _TRANSFER_FROM


def _transfer_response(cur, pk) -> dict:
    cur.execute(_TRANSFER_SELECT + " WHERE tr.financial_transfer_pk = %s", (str(pk),))
    return _fetch_one(cur)


def _transfer_row(cur, user: UserContext, pk, action: str, *, lock: bool = False) -> dict:
    """The stored transfer, after checking the caller's scope over BOTH ends."""
    cur.execute(
        """
        SELECT tr.financial_transfer_pk, tr.transfer_reference, tr.financial_year_pk, tr.source_scope_pk,
               tr.destination_scope_pk, tr.source_fund_pk, tr.destination_fund_pk, tr.amount, tr.transfer_date,
               tr.status, tr.created_by_sangha_sevi_pk
          FROM nss.financial_transfer tr WHERE tr.financial_transfer_pk = %s AND tr.is_active = TRUE
        """ + (" FOR UPDATE" if lock else ""),
        (str(pk),),
    )
    row = _fetch_one(cur)
    if row is None:
        raise _not_found("Transfer")
    for scope_pk in (row["source_scope_pk"], row["destination_scope_pk"]):
        _require_org_access(cur, user, _scope_row(cur, scope_pk)["organization_pk"], action)
    return row


def _check_transfer(cur, *, year_pk, source_scope_pk, destination_scope_pk, source_fund_pk, destination_fund_pk, transfer_date) -> None:
    if str(source_scope_pk) == str(destination_scope_pk):
        raise _invalid("A transfer needs two different financial scopes (FIN-BR-027).")
    year = _year_row(cur, year_pk)
    if year["status"] != "OPEN":
        raise _invalid(f"Financial year {year['year_code']} is {year['status']}; transfers need an OPEN year.")
    if not (year["start_date"] <= transfer_date <= year["end_date"]):
        raise _invalid(f"transfer_date must fall inside financial year {year['year_code']}.")
    for label, scope_pk, fund_pk in (("source", source_scope_pk, source_fund_pk), ("destination", destination_scope_pk, destination_fund_pk)):
        scope = _scope_row(cur, scope_pk)
        if scope["status"] != "ACTIVE":
            raise _invalid(f"The {label} scope {scope['scope_code']} is {scope['status']}; transfers need ACTIVE scopes.")
        if fund_pk is not None:
            fund = _fund_row(cur, fund_pk)
            if str(fund["financial_scope_pk"]) != str(scope_pk):
                raise _invalid(f"The {label} fund belongs to a different financial scope.")
            if fund["status"] != "ACTIVE":
                raise _invalid(f"The {label} fund {fund['fund_code']} is {fund['status']}.")


def _check_transfer_funds(cur, transfer: dict) -> None:
    """A transfer can never take more out of a fund than it holds."""
    if transfer["source_fund_pk"] is not None:
        balance = _lock_and_balance(cur, transfer["source_fund_pk"])
        if transfer["amount"] > balance:
            raise _invalid(f"The source fund holds only {balance}; the transfer of {transfer['amount']} exceeds it.")


@router.get("/transfers", response_model=S.TransferListResponse)
def list_transfers(
    financial_year_pk: UUID | None = Query(None),
    financial_scope_pk: UUID | None = Query(None, description="Either end of the transfer"),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None, description="Matches reference or purpose"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        sv, sp = _visible(cur, user, "sfs.organization_pk")
        dv, dp = _visible(cur, user, "dfs.organization_pk")
        where, params = ["tr.is_active = TRUE", f"({sv} OR {dv})"], sp + dp
        if financial_year_pk:
            where.append("tr.financial_year_pk = %s"); params.append(str(financial_year_pk))
        if financial_scope_pk:
            where.append("(tr.source_scope_pk = %s OR tr.destination_scope_pk = %s)"); params += [str(financial_scope_pk)] * 2
        if status_filter:
            where.append("tr.status = %s"); params.append(status_filter)
        if q and q.strip():
            where.append("(tr.transfer_reference ILIKE %s OR tr.purpose ILIKE %s)"); params += [f"%{q.strip()}%"] * 2
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_TRANSFER_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_TRANSFER_SELECT + f" WHERE {where_sql} ORDER BY tr.transfer_date DESC, tr.created_at DESC LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return _paged(_fetch_all(cur), total, page, page_size)


@router.post("/transfers", response_model=S.TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(body: S.TransferCreate, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
    """Draft a transfer between two ACTIVE scopes; the caller needs admin scope over BOTH."""
    with conn.cursor() as cur:
        for scope_pk in (body.source_scope_pk, body.destination_scope_pk):
            _require_org_access(cur, user, _scope_row(cur, scope_pk)["organization_pk"], "transfer between these financial scopes")
        _check_transfer(
            cur, year_pk=body.financial_year_pk, source_scope_pk=body.source_scope_pk, destination_scope_pk=body.destination_scope_pk,
            source_fund_pk=body.source_fund_pk, destination_fund_pk=body.destination_fund_pk, transfer_date=body.transfer_date,
        )
        purpose = _clean(body.purpose)
        if not purpose:
            raise _invalid("purpose cannot be blank.")
        reference = next_id(cur, "FINANCIAL_TRANSFER")
        cur.execute(
            """
            INSERT INTO nss.financial_transfer
                (transfer_reference, financial_year_pk, source_scope_pk, destination_scope_pk, source_fund_pk,
                 destination_fund_pk, amount, transfer_date, purpose, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING financial_transfer_pk
            """,
            (reference, str(body.financial_year_pk), str(body.source_scope_pk), str(body.destination_scope_pk),
             str(body.source_fund_pk) if body.source_fund_pk else None,
             str(body.destination_fund_pk) if body.destination_fund_pk else None,
             body.amount, body.transfer_date, purpose, user.actor_pk),
        )
        pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "financial_transfer", pk, f"Drafted transfer {reference}", {"amount": str(body.amount)})
        return _transfer_response(cur, pk)


@router.get("/transfers/{transfer_pk}", response_model=S.TransferResponse)
def get_transfer(transfer_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        _transfer_row(cur, user, transfer_pk, "view this transfer")
        return _transfer_response(cur, transfer_pk)


@router.post("/transfers/{transfer_pk}/transition", response_model=S.TransferResponse)
def transition_transfer(transfer_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_MANAGE),
                        conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        transfer = _transfer_row(cur, user, transfer_pk, "act on this transfer", lock=True)
        _, self_approved = _guard_transition(user, "transfer", transfer["status"], body.status, body.remarks,
                                             transfer["created_by_sangha_sevi_pk"])
        if body.status in ("PENDING_APPROVAL", "APPROVED", "EXECUTED"):
            _check_transfer(
                cur, year_pk=transfer["financial_year_pk"], source_scope_pk=transfer["source_scope_pk"],
                destination_scope_pk=transfer["destination_scope_pk"], source_fund_pk=transfer["source_fund_pk"],
                destination_fund_pk=transfer["destination_fund_pk"], transfer_date=transfer["transfer_date"],
            )
        if body.status in ("APPROVED", "EXECUTED"):
            _check_transfer_funds(cur, transfer)
        # Money leaving the Kendra / central Mahila Sangha: same Bye-Law controls as a payment.
        authority_service.enforce_transition(cur, user.person_pk, "transfer", transfer_pk,
                                             _scope_row(cur, transfer["source_scope_pk"])["organization_pk"],
                                             transfer["status"], body.status)
        _update_row(cur, user, "financial_transfer", "financial_transfer_pk", transfer_pk, {"status": body.status})
        _audit(cur, user, "STATUS_CHANGE", "financial_transfer", transfer_pk,
               f"Transfer {transfer['transfer_reference']} {transfer['status']} -> {body.status}",
               {"from": transfer["status"], "to": body.status, "remarks": _clean(body.remarks),
                **({"self_approved": True} if self_approved else {})})
        return _transfer_response(cur, transfer_pk)
