"""
NSS ERP — Finance setup router (Tier 12): receiving accounts and finance heads.

Everything that makes the Finance module CUSTOMIZABLE per Sangha lives here
(owner decision 2026-11-10): each Sangha's own receiving account(s) and its own
catalogue of finance heads, seeded from Kendra-published templates.

  GET   /api/v1/finance/accounts | POST            list / create a receiving account
  GET   /api/v1/finance/accounts/{pk} | PATCH      detail / edit
  POST  /api/v1/finance/accounts/{pk}/transition   ACTIVE <-> INACTIVE
  GET   /api/v1/finance/heads | POST               list (incl. templates) / create a head
  POST  /api/v1/finance/contributions              the SIMPLE way to add a contribution (name, amount, how often)
  POST  /api/v1/finance/heads/adopt-templates      copy Kendra templates into a Sangha's catalogue
  GET   /api/v1/finance/heads/{pk} | PATCH         detail / edit
  POST  /api/v1/finance/heads/{pk}/transition      ACTIVE <-> INACTIVE
  POST  /api/v1/finance/heads/{pk}/sync-copies     Kendra all-Sakhas head: give every Sakha its copy / refresh them

Authorization: configuration is sensitive (a head decides what is restricted,
what a member sees as Pranami and where UPI money lands; an account decides
where it is paid), so WRITES need FINANCE_CONFIGURE (owner 2026-11-17; it approves nothing); reads need any FINANCE_*
permission. Both are bounded by admin scope on the OWNING organization
(``require_org_in_scope``). A Kendra TEMPLATE head (no organization) is
global-authority only for writes and readable by every finance user, because it
is a blueprint, not money.

Rules enforced here (DB CHECKs in database/ddl/14_finance/ are the backstop):
  - a head's code, organization, direction, restriction and required fund type
    never change after creation (create a new head and switch the old one off,
    so history keeps its meaning); name, description, order, Pranami flag and the
    UPI collection targets stay editable;
  - UPI collection needs an INCOME head owned by a Sangha, a collection scope of
    that Sangha, a receiving account of that Sangha with a gateway configured, and
    a fund consistent with the head's own rules (restricted / required type);
  - an account stores NO full account number and NO secret (last four digits and
    the NAME of a server-side credential set only);
  - an account in use by an active UPI head cannot be switched off or lose its
    gateway; nothing is ever deleted.
"""

import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.routers import finance as F
from api.schemas import finance as S
from api.services import finance_approval as FA
from api.services import finance_contribution as FC
from api.services import upi_gateway
from api.services.rbac_service import UserContext, actor_scope_org_pks

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE, _CONFIGURE = F._VIEW, F._MANAGE, F._CONFIGURE

_LAST4_RE = re.compile(r"^[0-9]{4}$")
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_VPA_RE = re.compile(r"^[A-Za-z0-9._-]{2,}@[A-Za-z]{2,}$")
_CRED_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,39}$")
_HEAD_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,49}$")


# ═══════════════════════════════════════════════════════════════════════
# Receiving accounts
# ═══════════════════════════════════════════════════════════════════════

_ACCOUNT_FROM = """
      FROM nss.financial_account a
      LEFT JOIN nss.organization o ON o.organization_pk = a.organization_pk
"""
_ACCOUNT_SELECT = """
    SELECT a.financial_account_pk, a.organization_pk, o.organization_name, a.account_label, a.account_type,
           a.bank_name, a.branch_name, a.account_holder_name, a.account_number_last4, a.ifsc_code, a.upi_vpa,
           a.gateway_provider, a.gateway_credential_ref, a.gateway_merchant_ref, a.is_default, a.status,
           (SELECT COUNT(*) FROM nss.finance_head h
             WHERE h.collection_account_pk = a.financial_account_pk AND h.is_active = TRUE
               AND h.allow_upi = TRUE AND h.status = 'ACTIVE') AS head_count
""" + _ACCOUNT_FROM


def account_ready(account: dict) -> bool:
    """True when the account's gateway is enabled on this server AND its credential set is fully configured."""
    provider = (account.get("gateway_provider") or "").upper()
    if not provider or provider not in upi_gateway.enabled_providers() or provider not in upi_gateway.PROVIDERS:
        return False
    try:
        upi_gateway.credentials_for(account.get("gateway_credential_ref"), provider)
    except upi_gateway.GatewayUnavailable:
        return False
    return True


def _account_response(cur, pk) -> dict:
    cur.execute(_ACCOUNT_SELECT + " WHERE a.financial_account_pk = %s", (str(pk),))
    row = F._fetch_one(cur)
    row["gateway_ready"] = account_ready(row)
    return row


def _account_row(cur, pk, *, lock: bool = False) -> dict:
    cur.execute(
        "SELECT financial_account_pk, organization_pk, account_label, gateway_provider, gateway_credential_ref, "
        "upi_vpa, is_default, status FROM nss.financial_account WHERE financial_account_pk = %s AND is_active = TRUE"
        + (" FOR UPDATE" if lock else ""),
        (str(pk),),
    )
    row = F._fetch_one(cur)
    if row is None:
        raise F._not_found("Receiving account")
    return row


def _clean_account_fields(values: dict) -> dict:
    """Normalise and validate the optional account fields that were supplied (same rules on create and edit)."""
    out = dict(values)
    for key in ("bank_name", "branch_name", "gateway_merchant_ref", "account_holder_name", "account_label"):
        if key in out and out[key] is not None:
            out[key] = F._clean(out[key])
    if out.get("account_type") is not None and out["account_type"] not in S.ACCOUNT_TYPES:
        raise F._invalid(f"account_type must be one of: {', '.join(S.ACCOUNT_TYPES)}.")
    if out.get("account_number_last4") is not None:
        v = out["account_number_last4"].strip()
        if not _LAST4_RE.match(v):
            raise F._invalid("account_number_last4 must be exactly four digits - the full account number is never stored.")
        out["account_number_last4"] = v
    if out.get("ifsc_code") is not None:
        v = out["ifsc_code"].strip().upper()
        if not _IFSC_RE.match(v):
            raise F._invalid("ifsc_code must look like SBIN0001234.")
        out["ifsc_code"] = v
    if out.get("upi_vpa") is not None:
        v = out["upi_vpa"].strip()
        if not _VPA_RE.match(v):
            raise F._invalid("upi_vpa must look like name@bank.")
        out["upi_vpa"] = v
    if out.get("gateway_provider") is not None:
        v = out["gateway_provider"].strip().upper()
        if v not in upi_gateway.PROVIDERS:
            raise F._invalid(f"gateway_provider must be one of: {', '.join(sorted(upi_gateway.PROVIDERS))}.")
        out["gateway_provider"] = v
    if out.get("gateway_credential_ref") is not None:
        v = out["gateway_credential_ref"].strip().upper()
        if not _CRED_RE.match(v):
            raise F._invalid("gateway_credential_ref is the NAME of a server-side credential set (letters, digits, underscore) - never a key or secret.")
        out["gateway_credential_ref"] = v
    return out


@router.get("/accounts", response_model=S.AccountListResponse)
def list_accounts(
    q: str | None = Query(None, description="Matches label, bank, holder or UPI id"),
    organization_pk: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        vis, params = F._visible(cur, user, "a.organization_pk")
        where = ["a.is_active = TRUE", vis]
        if organization_pk:
            where.append("a.organization_pk = %s"); params.append(str(organization_pk))
        if status_filter:
            where.append("a.status = %s"); params.append(status_filter)
        if q and q.strip():
            where.append("(a.account_label ILIKE %s OR a.bank_name ILIKE %s OR a.account_holder_name ILIKE %s OR a.upi_vpa ILIKE %s)")
            params += [f"%{q.strip()}%"] * 4
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_ACCOUNT_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_ACCOUNT_SELECT + f" WHERE {where_sql} ORDER BY LOWER(o.organization_name), a.is_default DESC, LOWER(a.account_label) LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        items = F._fetch_all(cur)
    for row in items:
        row["gateway_ready"] = account_ready(row)
    return F._paged(items, total, page, page_size)


@router.post("/accounts", response_model=S.AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(body: S.AccountCreate, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """Register a receiving account for a Sangha. FINANCE_CONFIGURE + admin scope on the Sangha."""
    with conn.cursor() as cur:
        F._require_org_access(cur, user, body.organization_pk, "add a receiving account for this organization")
        F._require_active_organization(cur, body.organization_pk, "Organization")
        v = _clean_account_fields(body.model_dump(exclude={"organization_pk", "is_default"}))
        if not v.get("account_label") or not v.get("account_holder_name"):
            raise F._invalid("account_label and account_holder_name cannot be blank.")
        if v.get("gateway_provider") and not v.get("gateway_credential_ref"):
            raise F._invalid("A gateway account needs the name of its credential set (gateway_credential_ref).")
        cur.execute("SELECT 1 FROM nss.financial_account WHERE organization_pk = %s AND account_label = %s",
                    (str(body.organization_pk), v["account_label"]))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This organization already has an account with that label.")
        if body.is_default:
            cur.execute("UPDATE nss.financial_account SET is_default = FALSE, updated_at = NOW(), updated_by_sangha_sevi_pk = %s "
                        "WHERE organization_pk = %s AND is_default = TRUE AND is_active = TRUE", (user.actor_pk, str(body.organization_pk)))
        cols = ["organization_pk", "is_default", "created_by_sangha_sevi_pk", *v]
        cur.execute(
            f"INSERT INTO nss.financial_account ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING financial_account_pk",
            [str(body.organization_pk), body.is_default, user.actor_pk, *v.values()],
        )
        pk = cur.fetchone()[0]
        F._audit(cur, user, "CREATE", "financial_account", pk, f"Added receiving account {v['account_label']}",
                 {"organization_pk": str(body.organization_pk), "gateway_provider": v.get("gateway_provider")})
        FC.link_account(cur, user, body.organization_pk)       # contributions waiting for an account start collecting into it
        return _account_response(cur, pk)


@router.get("/accounts/{account_pk}", response_model=S.AccountResponse)
def get_account(account_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        acct = _account_row(cur, account_pk)
        F._require_org_access(cur, user, acct["organization_pk"], "view this receiving account")
        return _account_response(cur, account_pk)


@router.patch("/accounts/{account_pk}", response_model=S.AccountResponse)
def update_account(account_pk: UUID, body: S.AccountUpdate, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        acct = _account_row(cur, account_pk, lock=True)
        F._require_org_access(cur, user, acct["organization_pk"], "change this receiving account")
        if acct["status"] != "ACTIVE":
            raise F._invalid("An INACTIVE account can no longer be edited; reactivate it first.")
        sent = {k: getattr(body, k) for k in body.model_fields_set}
        make_default = sent.pop("is_default", None)
        values = _clean_account_fields(sent)
        for required in ("account_label", "account_holder_name"):
            if required in values and not values[required]:
                raise F._invalid(f"{required} cannot be blank.")
        new_provider = values.get("gateway_provider", acct["gateway_provider"])
        new_ref = values.get("gateway_credential_ref", acct["gateway_credential_ref"])
        if new_provider and not new_ref:
            raise F._invalid("A gateway account needs the name of its credential set (gateway_credential_ref).")
        if not new_provider:
            cur.execute("SELECT COUNT(*) FROM nss.finance_head WHERE collection_account_pk = %s AND is_active = TRUE AND allow_upi = TRUE AND status = 'ACTIVE'", (str(account_pk),))
            if cur.fetchone()[0]:
                raise F._invalid("Active UPI heads collect into this account, so it must keep its payment gateway.")
        if "account_label" in values and values["account_label"] != acct["account_label"]:
            cur.execute("SELECT 1 FROM nss.financial_account WHERE organization_pk = %s AND account_label = %s",
                        (str(acct["organization_pk"]), values["account_label"]))
            if cur.fetchone():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This organization already has an account with that label.")
        if make_default:
            cur.execute("UPDATE nss.financial_account SET is_default = FALSE WHERE organization_pk = %s AND is_default = TRUE AND is_active = TRUE AND financial_account_pk <> %s",
                        (str(acct["organization_pk"]), str(account_pk)))
            values["is_default"] = True
        elif make_default is False:
            values["is_default"] = False
        if values:
            F._update_row(cur, user, "financial_account", "financial_account_pk", account_pk, values)
            F._audit(cur, user, "UPDATE", "financial_account", account_pk, f"Updated receiving account {acct['account_label']}", {"fields": sorted(values)})
            FC.link_account(cur, user, acct["organization_pk"])
        return _account_response(cur, account_pk)


@router.post("/accounts/{account_pk}/transition", response_model=S.AccountResponse)
def transition_account(account_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        acct = _account_row(cur, account_pk, lock=True)
        F._require_org_access(cur, user, acct["organization_pk"], "change this receiving account")
        F._guard_transition(user, "account", acct["status"], body.status, body.remarks, None)
        if body.status == "INACTIVE":
            cur.execute("SELECT COUNT(*) FROM nss.finance_head WHERE collection_account_pk = %s AND is_active = TRUE AND allow_upi = TRUE AND status = 'ACTIVE'", (str(account_pk),))
            n = cur.fetchone()[0]
            if n:
                raise F._invalid(f"{n} active UPI head(s) collect into this account; point them elsewhere or switch them off first.")
        values = {"status": body.status}
        if body.status == "INACTIVE":
            values["is_default"] = False
        F._update_row(cur, user, "financial_account", "financial_account_pk", account_pk, values)
        F._audit(cur, user, "STATUS_CHANGE", "financial_account", account_pk, f"Account {acct['account_label']} {acct['status']} -> {body.status}",
                 {"from": acct["status"], "to": body.status, "remarks": F._clean(body.remarks)})
        return _account_response(cur, account_pk)


# ═══════════════════════════════════════════════════════════════════════
# Finance heads
# ═══════════════════════════════════════════════════════════════════════

_HEAD_FROM = """
      FROM nss.finance_head h
      LEFT JOIN nss.organization o ON o.organization_pk = h.organization_pk
      LEFT JOIN nss.financial_scope cs ON cs.financial_scope_pk = h.collection_scope_pk
      LEFT JOIN nss.fund_master cf ON cf.fund_master_pk = h.collection_fund_pk
      LEFT JOIN nss.financial_account ca ON ca.financial_account_pk = h.collection_account_pk
      LEFT JOIN nss.finance_head src ON src.finance_head_pk = h.template_head_pk
"""
_HEAD_SELECT = """
    SELECT h.finance_head_pk, h.organization_pk, o.organization_name, (h.organization_pk IS NULL) AS is_template,
           h.head_code, h.head_name, h.description, h.direction, h.is_restricted, h.restriction_purpose,
           h.required_fund_type, h.is_pranami, h.allow_upi, h.collection_scope_pk, cs.scope_code AS collection_scope_code, cs.scope_name AS collection_scope_name,
           h.collection_fund_pk, cf.fund_code AS collection_fund_code, cf.fund_name AS collection_fund_name, h.collection_account_pk,
           ca.account_label AS collection_account_label, h.template_head_pk, h.status,
           (SELECT COUNT(*) FROM nss.financial_transaction t WHERE t.finance_head_pk = h.finance_head_pk AND t.is_active = TRUE) AS transaction_count,
           h.fixed_amount, h.due_period, h.due_date, h.allow_part_payment, h.applies_to_all_sakhas,
           h.skips_approval, h.treasurer_limit, h.requires_member,
           COALESCE(src.applies_to_all_sakhas, FALSE) AS is_kendra_copy,
           (COALESCE(src.applies_to_all_sakhas, FALSE) AND h.collection_account_pk IS NULL) AS needs_account,
           CASE WHEN h.applies_to_all_sakhas THEN
                (SELECT COUNT(*) FROM nss.finance_head c WHERE c.template_head_pk = h.finance_head_pk AND c.is_active = TRUE)
                ELSE 0 END AS copy_count
""" + _HEAD_FROM


def _head_response(cur, pk) -> dict:
    cur.execute(_HEAD_SELECT + " WHERE h.finance_head_pk = %s", (str(pk),))
    return F._fetch_one(cur)


def _head_access(cur, user: UserContext, head: dict, action: str, *, write: bool) -> None:
    """Templates are readable by every finance user; writing one (and any org head) follows admin scope."""
    if head["organization_pk"] is None:
        if write:
            F._require_global(cur, user, action)
        return
    F._require_org_access(cur, user, head["organization_pk"], action)


def _validate_collection(cur, *, org_pk, direction, is_restricted, required_fund_type, allow_upi, scope_pk, fund_pk, account_pk) -> None:
    """The collection targets of a head must be coherent with the head's own organization and rules."""
    if org_pk is None:
        if allow_upi or scope_pk or fund_pk or account_pk:
            raise F._invalid("A Kendra template is a blueprint: it cannot collect money (no UPI, scope, fund or account).")
        return
    if allow_upi and direction != "INCOME":
        raise F._invalid("Only an INCOME head can be collected by UPI.")
    if allow_upi and (not scope_pk or not account_pk):
        raise F._invalid("UPI collection needs a collection scope and a receiving account.")
    scope = fund = None
    if scope_pk:
        scope = F._scope_row(cur, scope_pk)
        if not F._same_org(scope["organization_pk"], org_pk):
            raise F._invalid("The collection scope belongs to a different organization.")
        if scope["status"] != "ACTIVE":
            raise F._invalid(f"The collection scope {scope['scope_code']} is {scope['status']}; it must be ACTIVE.")
    if fund_pk:
        if not scope:
            raise F._invalid("A collection fund needs a collection scope.")
        fund = F._fund_row(cur, fund_pk)
        if str(fund["financial_scope_pk"]) != str(scope_pk):
            raise F._invalid("The collection fund belongs to a different financial scope.")
        if fund["status"] != "ACTIVE":
            raise F._invalid(f"The collection fund {fund['fund_code']} is {fund['status']}; it must be ACTIVE.")
    if allow_upi and is_restricted and (fund is None or not fund["is_restricted"]):
        raise F._invalid("A restricted head must collect into a restricted fund (FIN-BR-019/022).")
    if allow_upi and required_fund_type and (fund is None or fund["fund_type"] != required_fund_type):
        raise F._invalid(f"This head must collect into a {required_fund_type} fund.")
    if account_pk:
        acct = _account_row(cur, account_pk)
        if not F._same_org(acct["organization_pk"], org_pk):
            raise F._invalid("The receiving account belongs to a different organization.")
        if acct["status"] != "ACTIVE":
            raise F._invalid(f"The receiving account {acct['account_label']} is {acct['status']}.")
        if allow_upi and (not acct["gateway_provider"] or not acct["gateway_credential_ref"]):
            raise F._invalid("UPI collection needs a receiving account that has a payment gateway configured.")


_WEBHOOK_EVENTS = {"RAZORPAY": ["payment_link.paid", "payment_link.expired", "payment_link.cancelled"], "MOCK": []}


@router.get("/gateway/readiness", response_model=S.GatewayReadiness)
def gateway_readiness(request: Request, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_connection)):
    """
    A checklist for going live with a payment gateway (Razorpay): is the provider enabled on this server, the exact webhook URL to register
    in the provider's dashboard, whether that URL can be reached from outside, the payment window, and which of the accounts in the
    caller's scope are ready. Names only - never a key or secret.
    """
    from api.config import settings

    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    base = f"{proto}://{host}"
    hostname = host.split(":")[0].strip("[]").lower()
    public = proto == "https" and hostname not in ("localhost", "127.0.0.1", "::1") and not hostname.endswith(".local")
    enabled = upi_gateway.enabled_providers()
    with conn.cursor() as cur:
        allowed = actor_scope_org_pks(cur, user)
        rows = []
        if allowed is None or allowed:                         # None = the global authority; an empty set = nothing in scope
            where, params = "a.is_active = TRUE AND a.gateway_provider IS NOT NULL", []
            if allowed is not None:
                where += " AND a.organization_pk = ANY(%s::uuid[])"
                params.append(list(allowed))
            cur.execute(f"SELECT a.gateway_provider, a.gateway_credential_ref, a.status FROM nss.financial_account a WHERE {where}", params)
            rows = cur.fetchall()
    providers = []
    for name in sorted(upi_gateway.PROVIDERS):
        mine = [r for r in rows if (r[0] or "").upper() == name]
        ready = sum(1 for r in mine if r[2] == "ACTIVE" and account_ready({"gateway_provider": name, "gateway_credential_ref": r[1]}))
        providers.append({
            "provider": name, "enabled": name in enabled, "webhook_url": f"{base}/api/v1/finance/gateway/webhook/{name.lower()}",
            "webhook_events": _WEBHOOK_EVENTS.get(name, []), "needs_credentials": name != "MOCK",
            "accounts_using_it": len(mine), "accounts_ready": ready,
        })
    windows = {name: int(getattr(p, "MIN_WINDOW").total_seconds() // 60) for name, p in upi_gateway.PROVIDERS.items() if hasattr(p, "MIN_WINDOW")}
    return {
        "providers": providers, "webhook_public": public, "request_expiry_minutes": settings.UPI_REQUEST_EXPIRY_MINUTES,
        "min_window_minutes": windows, "window_ok": all(settings.UPI_REQUEST_EXPIRY_MINUTES >= m for m in windows.values()),
        "credential_sets": sorted({r[1] for r in rows if r[1] and (r[0] or "").upper() != "MOCK"}), "dev_install": upi_gateway.is_dev_install(),
    }


@router.get("/heads", response_model=S.HeadListResponse)
def list_heads(
    q: str | None = Query(None, description="Matches code or name"),
    organization_pk: UUID | None = Query(None),
    templates_only: bool = Query(False, description="Only Kendra templates"),
    with_templates: bool = Query(True, description="False: leave the Kendra templates out (only Sangha-owned heads)"),
    for_scope_pk: UUID | None = Query(None, description="Only ACTIVE heads a transaction in this financial scope may use"),
    events_only: bool = Query(False, description="Only heads that collect for an event (an EVENT financial scope, e.g. Rasa)"),
    direction: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    is_pranami: bool | None = Query(None),
    allow_upi: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        where, params = ["h.is_active = TRUE"], []
        if for_scope_pk is not None:
            scope = F._scope_row(cur, for_scope_pk)
            F._require_org_access(cur, user, scope["organization_pk"], "view the heads of this financial scope")
            if scope["organization_pk"] is None:
                where.append("h.organization_pk IS NULL")
            else:
                where.append("h.organization_pk = %s"); params.append(str(scope["organization_pk"]))
            where.append("h.status = 'ACTIVE'")
        else:
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None:                       # templates are visible to every finance user
                where.append("(h.organization_pk IS NULL OR h.organization_pk = ANY(%s::uuid[]))"); params.append(sorted(allowed))
            if not with_templates and not templates_only:
                where.append("h.organization_pk IS NOT NULL")
        if templates_only:
            where.append("h.organization_pk IS NULL")
        if organization_pk:
            where.append("h.organization_pk = %s"); params.append(str(organization_pk))
        if direction:
            where.append("h.direction = %s"); params.append(direction)
        if status_filter:
            where.append("h.status = %s"); params.append(status_filter)
        if is_pranami is not None:
            where.append("h.is_pranami = %s"); params.append(is_pranami)
        if events_only:
            where.append("cs.scope_type = 'EVENT'")
        if allow_upi is not None:
            where.append("h.allow_upi = %s"); params.append(allow_upi)
        if q and q.strip():
            where.append("(h.head_code ILIKE %s OR h.head_name ILIKE %s)"); params += [f"%{q.strip()}%"] * 2
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_HEAD_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_HEAD_SELECT + f" WHERE {where_sql} ORDER BY LOWER(h.head_name), h.head_code LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return F._paged(F._fetch_all(cur), total, page, page_size)


@router.post("/heads", response_model=S.HeadResponse, status_code=status.HTTP_201_CREATED)
def create_head(body: S.HeadCreate, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """Create a finance head for a Sangha (or, for global authority only, a Kendra template)."""
    code = body.head_code.strip().upper()
    if not _HEAD_CODE_RE.match(code):
        raise F._invalid("head_code must be UPPER_SNAKE_CASE (letters, digits, underscore), 2-50 characters.")
    if body.direction not in S.HEAD_DIRECTIONS:
        raise F._invalid(f"direction must be one of: {', '.join(S.HEAD_DIRECTIONS)}.")
    name, purpose = F._clean(body.head_name), F._clean(body.restriction_purpose)
    if not name:
        raise F._invalid("head_name cannot be blank.")
    if body.is_restricted and not purpose:
        raise F._invalid("A restricted head must state its restriction_purpose (FIN-BR-020).")
    if body.required_fund_type is not None and body.required_fund_type not in S.FUND_TYPES:
        raise F._invalid(f"required_fund_type must be one of: {', '.join(S.FUND_TYPES)}.")
    if body.direction == "EXPENSE" and (body.is_pranami or body.allow_upi):
        raise F._invalid("Pranami and UPI collection apply to INCOME heads only.")
    if body.direction == "EXPENSE" and body.skips_approval:
        raise F._invalid("Only an INCOME head can skip approval.")
    if body.is_pranami and body.organization_pk is not None and not body.allow_upi:      # owner 2026-11-20: every Pranami is payable online
        raise F._invalid("A Pranami must be payable online (UPI or card): turn on online collection and choose a scope and a receiving account.")
    if body.direction == "INCOME" and (body.treasurer_limit is not None or body.requires_member):
        raise F._invalid("The Treasurer's limit and the reimbursement flag apply to EXPENSE heads only.")
    with conn.cursor() as cur:
        _head_access(cur, user, {"organization_pk": body.organization_pk}, "create a finance head for this organization", write=True)
        if body.organization_pk is not None:
            F._require_active_organization(cur, body.organization_pk, "Organization")
            if body.skips_approval or body.treasurer_limit is not None:                       # the Treasurer's own controls (owner 2026-11-20)
                FA.require_not_the_treasurer(cur, user, body.organization_pk, "the approval rules of a head (its Treasurer limit / 'needs no approval')")
        _validate_collection(cur, org_pk=body.organization_pk, direction=body.direction, is_restricted=body.is_restricted,
                             required_fund_type=body.required_fund_type, allow_upi=body.allow_upi,
                             scope_pk=body.collection_scope_pk, fund_pk=body.collection_fund_pk, account_pk=body.collection_account_pk)
        cur.execute("SELECT 1 FROM nss.finance_head WHERE head_code = %s AND organization_pk IS NOT DISTINCT FROM %s",
                    (code, str(body.organization_pk) if body.organization_pk else None))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A finance head with code {code} already exists here.")
        cur.execute(
            """
            INSERT INTO nss.finance_head
                (organization_pk, head_code, head_name, description, direction, is_restricted, restriction_purpose,
                 required_fund_type, is_pranami, allow_upi, collection_scope_pk, collection_fund_pk,
                 collection_account_pk, skips_approval, treasurer_limit, requires_member, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_head_pk
            """,
            (str(body.organization_pk) if body.organization_pk else None, code, name, F._clean(body.description), body.direction,
             body.is_restricted, purpose, body.required_fund_type, body.is_pranami, body.allow_upi,
             str(body.collection_scope_pk) if body.collection_scope_pk else None,
             str(body.collection_fund_pk) if body.collection_fund_pk else None,
             str(body.collection_account_pk) if body.collection_account_pk else None,
             body.skips_approval, body.treasurer_limit, body.requires_member, user.actor_pk),
        )
        pk = cur.fetchone()[0]
        F._audit(cur, user, "CREATE", "finance_head", pk, f"Created finance head {code}",
                 {"organization_pk": str(body.organization_pk) if body.organization_pk else None, "direction": body.direction})
        return _head_response(cur, pk)


def _check_due_date(due_date) -> None:
    """EVERY Pranami has a due date, a free-amount one too (owner 2026-11-19); it is set when the payment portal is opened."""
    if due_date is None:
        raise F._invalid("Choose the date this Pranami is due by.")


def _check_amount_fields(amount, period, part, *, direction="INCOME") -> None:
    """The fixed-amount fields of a head (same rules on create and edit)."""
    if period is not None and period not in S.DUE_PERIODS:
        raise F._invalid(f"due_period must be one of: {', '.join(S.DUE_PERIODS)}.")
    if amount is not None and period is None:
        raise F._invalid("A fixed amount needs a due period (yearly, monthly or one time).")
    if period is not None and amount is None:
        raise F._invalid("A due period needs a fixed amount.")
    if part and amount is None:
        raise F._invalid("Part payment only applies to a Pranami with a fixed amount.")
    if (amount is not None or part) and direction != "INCOME":
        raise F._invalid("A fixed amount applies to INCOME heads only.")


@router.post("/contributions", response_model=S.ContributionResult, status_code=status.HTTP_201_CREATED)
def create_contribution(body: S.ContributionCreate, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """
    The simple way to add a contribution (owner 2026-11-15): name, optional fixed amount, how often, part payment. The server
    sets the code, INCOME, member-visible, UPI collection, the Sangha's scope and its default receiving account. With
    ``applies_to = ALL_SAKHAS`` (the Kendra only) the head is the SOURCE and every active Sakha receives its OWN copy that
    collects into that Sakha's own account. FINANCE_CONFIGURE + admin scope on the Sangha. Every row written is audited.
    """
    if body.applies_to not in S.CONTRIBUTION_TARGETS:
        raise F._invalid(f"applies_to must be one of: {', '.join(S.CONTRIBUTION_TARGETS)}.")
    name = F._clean(body.head_name)
    if not name:
        raise F._invalid("head_name cannot be blank.")
    _check_amount_fields(body.fixed_amount, body.due_period, body.allow_part_payment)
    all_sakhas = body.applies_to == "ALL_SAKHAS"
    with conn.cursor() as cur:
        F._require_org_access(cur, user, body.organization_pk, "add a Pranami for this organization")
        F._require_active_organization(cur, body.organization_pk, "Organization")
        if all_sakhas:
            cur.execute("SELECT md.value_code FROM nss.organization o JOIN nss.master_data md "
                        "ON md.master_data_pk = o.organization_type_master_data_pk WHERE o.organization_pk = %s", (str(body.organization_pk),))
            if cur.fetchone()[0] != "KENDRA":
                raise F._invalid("Only the Kendra can add a Pranami that applies to all Sakhas.")
        chosen_scope = str(body.collection_scope_pk) if body.collection_scope_pk else None
        chosen_fund = str(body.collection_fund_pk) if body.collection_fund_pk else None
        if all_sakhas and (chosen_scope or chosen_fund):
            raise F._invalid("A Pranami for all Sakhas books into each Sakha's own scope: leave the scope and fund empty.")
        if chosen_scope or chosen_fund:        # the scope / fund the person picked must belong to this Sangha and be ACTIVE
            _validate_collection(cur, org_pk=body.organization_pk, direction="INCOME", is_restricted=False, required_fund_type=None,
                                 allow_upi=False, scope_pk=chosen_scope, fund_pk=chosen_fund, account_pk=None)
        account_pk = scope_pk = None
        if not all_sakhas and body.open_portal:
            if body.collection_account_pk is not None:
                account_pk = str(body.collection_account_pk)
            else:
                default = FC.default_account(cur, body.organization_pk) or FC.ensure_demo_account(cur, user, body.organization_pk)
                account_pk = default["financial_account_pk"] if default else None
            if account_pk:
                scope_pk = chosen_scope or FC.ensure_org_scope(cur, user, body.organization_pk)
                _validate_collection(cur, org_pk=body.organization_pk, direction="INCOME", is_restricted=False, required_fund_type=None,
                                     allow_upi=True, scope_pk=scope_pk, fund_pk=chosen_fund, account_pk=account_pk)
        code = f"CONTRIB_{uuid4().hex[:8].upper()}"
        cur.execute(
            """
            INSERT INTO nss.finance_head
                (organization_pk, head_code, head_name, description, direction, is_pranami, skips_approval, allow_upi,
                 collection_scope_pk, collection_fund_pk, collection_account_pk, fixed_amount, due_period, allow_part_payment, applies_to_all_sakhas,
                 created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, 'INCOME', %s, TRUE, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_head_pk
            """,
            (str(body.organization_pk), code, name, F._clean(body.description), body.open_portal, account_pk is not None, scope_pk or chosen_scope, chosen_fund, account_pk,
             body.fixed_amount, body.due_period, body.allow_part_payment, all_sakhas, user.actor_pk),
        )
        pk = cur.fetchone()[0]
        F._audit(cur, user, "CREATE", "finance_head", pk, f"Added contribution {name}",
                 {"organization_pk": str(body.organization_pk), "applies_to": body.applies_to,
                  "fixed_amount": str(body.fixed_amount) if body.fixed_amount is not None else None,
                  "due_period": body.due_period, "allow_part_payment": body.allow_part_payment})
        created = FC.sync_copies(cur, user, pk)["created"] if all_sakhas and body.open_portal else 0
        return {"head": _head_response(cur, pk), "copies_created": created,
                "needs_account": body.open_portal and (not all_sakhas) and account_pk is None}


@router.post("/heads/{head_pk}/portal", response_model=S.HeadResponse)
def set_head_portal(head_pk: UUID, body: S.PortalToggle, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """
    Open or close the payment portal of an INCOME head: while it is open, the members of the Sangha see the head in their Pranami
    tab and can pay it by UPI into the Sangha's default receiving account (the Sangha's own scope is used or created). Closing hides it
    from members again; nothing already paid changes. A head for EVERY Sakha is opened by giving each Sakha its copy (each collects into
    its own account); stopping it is switching the head off. FINANCE_CONFIGURE + admin scope on the Sangha; audited.
    """
    with conn.cursor() as cur:
        head = F._head_row(cur, head_pk)
        _head_access(cur, user, head, "open or close the payment portal of this head", write=True)
        if head["organization_pk"] is None:
            raise F._invalid("A Kendra template is a blueprint: it has no payment portal.")
        if head["direction"] != "INCOME":
            raise F._invalid("Only an income head can have a payment portal.")
        if head["status"] != "ACTIVE":
            raise F._invalid(f"The head is {head['status']}; switch it on first.")
        cur.execute("SELECT h.applies_to_all_sakhas, h.template_head_pk IS NOT NULL AND COALESCE(src.applies_to_all_sakhas, FALSE) "
                    "FROM nss.finance_head h LEFT JOIN nss.finance_head src ON src.finance_head_pk = h.template_head_pk "
                    "WHERE h.finance_head_pk = %s", (str(head_pk),))
        is_source, is_copy = cur.fetchone()
        sent = body.model_fields_set & {"fixed_amount", "due_period", "due_date", "allow_part_payment"}
        if sent and (is_copy or not body.open):
            raise F._invalid("The amount is set when a head's portal is opened, and a Sakha's copy takes it from the Kendra's head.")
        if body.open and not is_copy:                # a copy follows the Kendra's date; every other head needs one
            cur.execute("SELECT due_date FROM nss.finance_head WHERE finance_head_pk = %s", (str(head_pk),))
            _check_due_date(body.due_date if "due_date" in body.model_fields_set else cur.fetchone()[0])
        if is_source:
            if not body.open:
                raise F._invalid("A head for every Sakha is stopped by switching the head off.")
            values = {"is_pranami": True}
            if sent:
                _check_amount_fields(body.fixed_amount, body.due_period, body.allow_part_payment, direction="INCOME")
                values.update(fixed_amount=body.fixed_amount, due_period=body.due_period, allow_part_payment=body.allow_part_payment)
                if "due_date" in body.model_fields_set:
                    values["due_date"] = body.due_date
            F._update_row(cur, user, "finance_head", "finance_head_pk", head_pk, values)
            created = FC.sync_copies(cur, user, head_pk)["created"]
            F._audit(cur, user, "UPDATE", "finance_head", head_pk, f"Opened the payment portal of {head['head_code']} for every Sakha",
                     {"portal": True, "copies_created": created})
            return _head_response(cur, head_pk)
        if body.open:
            account = FC.default_account(cur, head["organization_pk"]) or FC.ensure_demo_account(cur, user, head["organization_pk"])
            if account is None:
                raise F._invalid("Add a receiving account with a payment gateway for this Sangha first; the portal collects into it.")
            # the scope chosen for the head (when it was created or edited) is kept; only a head with none gets the Sangha's general scope
            scope_pk = head["collection_scope_pk"] or FC.ensure_org_scope(cur, user, head["organization_pk"])
            _validate_collection(cur, org_pk=head["organization_pk"], direction="INCOME", is_restricted=head["is_restricted"],
                                 required_fund_type=head["required_fund_type"], allow_upi=True, scope_pk=scope_pk,
                                 fund_pk=head["collection_fund_pk"], account_pk=account["financial_account_pk"])
            # Members get a Pay button only when the gateway is enabled on THIS server and the account's credential set is complete
            # (account_ready - also for the MOCK provider). Opening a portal members cannot pay would look like it worked, so say why now.
            ready = _account_row(cur, account["financial_account_pk"])
            if not account_ready(ready):
                ref = ready.get("gateway_credential_ref") or "<REF>"
                raise F._invalid(
                    f"Members could not pay yet: the {ready.get('gateway_provider') or 'payment'} gateway of account '{account['account_label']}' is not "
                    f"set up on this server. Add the provider to UPI_GATEWAY_ENABLED_PROVIDERS and the credential set UPI_{ref}_KEY_ID, "
                    f"UPI_{ref}_KEY_SECRET and UPI_{ref}_WEBHOOK_SECRET to the server environment (api/.env), then restart it.")
            values = {"allow_upi": True, "collection_scope_pk": scope_pk, "collection_account_pk": account["financial_account_pk"]}
            if not is_copy:
                values["is_pranami"] = True
            if sent:                       # what members are asked to pay (same rules as creating / editing a head)
                _check_amount_fields(body.fixed_amount, body.due_period, body.allow_part_payment, direction="INCOME")
                values.update(fixed_amount=body.fixed_amount, due_period=body.due_period, allow_part_payment=body.allow_part_payment)
                if "due_date" in body.model_fields_set:
                    values["due_date"] = body.due_date
        else:
            # Closing only stops NEW payments. The head stays member-visible (is_pranami) so what members already paid on it stays in their
            # history, and nothing is re-hidden when it is opened again.
            values = {"allow_upi": False}
        F._update_row(cur, user, "finance_head", "finance_head_pk", head_pk, values)
        F._audit(cur, user, "UPDATE", "finance_head", head_pk, f"{'Opened' if body.open else 'Closed'} the payment portal of {head['head_code']}",
                 {"portal": body.open})
        return _head_response(cur, head_pk)


@router.post("/events", response_model=S.HeadResponse, status_code=status.HTTP_201_CREATED)
def create_event(body: S.EventCreate, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """
    Set up an event a Sangha collects for (e.g. Rasa) in one step, configured by the concerned Sangha: an ACTIVE financial
    scope of type EVENT owned by it (FIN-BR-062/063: events use the common Finance module through a scope) and a member-payable
    UPI head collecting into that scope. Returns the head. Same authority as any configuration (FINANCE_CONFIGURE + admin scope on
    the Sangha); the scope is created ACTIVE because the approver is the one switching it on.
    """
    name = F._clean(body.event_name)
    if not name:
        raise F._invalid("event_name cannot be blank.")
    with conn.cursor() as cur:
        F._require_org_access(cur, user, body.organization_pk, "set up an event for this organization")
        F._require_active_organization(cur, body.organization_pk, "Organization")
        suffix = uuid4().hex[:8].upper()
        scope_code, head_code = FC.scope_code_for(cur, body.organization_pk, "EVENT"), f"EVENT_{suffix}"
        # All or nothing: a refused setup (wrong account, no gateway...) must not leave a half-built event scope behind.
        cur.execute("SAVEPOINT event_setup")
        try:
            cur.execute(
                """
                INSERT INTO nss.financial_scope (scope_code, scope_name, scope_type, organization_pk, status, created_by_sangha_sevi_pk)
                VALUES (%s, %s, 'EVENT', %s, 'ACTIVE', %s) RETURNING financial_scope_pk
                """,
                (scope_code, name, str(body.organization_pk), user.actor_pk),
            )
            scope_pk = cur.fetchone()[0]
            F._audit(cur, user, "CREATE", "financial_scope", scope_pk, f"Created event scope {scope_code} ({name})",
                     {"organization_pk": str(body.organization_pk), "scope_type": "EVENT"})
            _validate_collection(cur, org_pk=body.organization_pk, direction="INCOME", is_restricted=False, required_fund_type=None,
                                 allow_upi=True, scope_pk=scope_pk, fund_pk=None, account_pk=body.collection_account_pk)
            cur.execute(
                """
                INSERT INTO nss.finance_head
                    (organization_pk, head_code, head_name, description, direction, is_restricted, is_pranami, skips_approval,
                     allow_upi, collection_scope_pk, collection_account_pk, created_by_sangha_sevi_pk)
                VALUES (%s, %s, %s, %s, 'INCOME', FALSE, TRUE, TRUE, TRUE, %s, %s, %s) RETURNING finance_head_pk
                """,
                (str(body.organization_pk), head_code, name, F._clean(body.description), str(scope_pk),
                 str(body.collection_account_pk), user.actor_pk),
            )
            pk = cur.fetchone()[0]
            F._audit(cur, user, "CREATE", "finance_head", pk, f"Created event head {head_code} ({name})",
                     {"organization_pk": str(body.organization_pk), "event_scope_code": scope_code})
        except HTTPException:
            cur.execute("ROLLBACK TO SAVEPOINT event_setup")
            raise
        return _head_response(cur, pk)


@router.post("/heads/adopt-templates", response_model=S.AdoptTemplatesResult)
def adopt_templates(body: S.AdoptTemplates, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """
    Copy Kendra templates into a Sangha's own catalogue (a copy, not a link: the Sangha may then rename or switch
    them off without touching anyone else). Templates the Sangha already has (same code) are skipped, so it is safe
    to run again when the Kendra publishes new ones. UPI settings are never copied - collection is set up per Sangha.
    """
    with conn.cursor() as cur:
        F._require_org_access(cur, user, body.organization_pk, "adopt finance heads for this organization")
        F._require_active_organization(cur, body.organization_pk, "Organization")
        where, params = "organization_pk IS NULL AND is_active = TRUE AND status = 'ACTIVE'", []
        if body.template_pks is not None:
            where += " AND finance_head_pk = ANY(%s::uuid[])"; params.append([str(t) for t in body.template_pks])
        cur.execute(f"SELECT finance_head_pk, head_code, head_name, description, direction, is_restricted, restriction_purpose, "
                    f"required_fund_type, is_pranami, skips_approval, requires_member, display_order FROM nss.finance_head WHERE {where} ORDER BY LOWER(head_name), head_code", params)
        templates = F._fetch_all(cur)
        if body.template_pks is not None and len(templates) != len(set(body.template_pks)):
            raise F._invalid("Some of the chosen templates do not exist or are not active templates.")
        created, skipped, items = 0, 0, []
        for t in templates:
            cur.execute("SELECT 1 FROM nss.finance_head WHERE organization_pk = %s AND head_code = %s", (str(body.organization_pk), t["head_code"]))
            if cur.fetchone():
                skipped += 1
                continue
            cur.execute(
                """
                INSERT INTO nss.finance_head
                    (organization_pk, head_code, head_name, description, direction, is_restricted, restriction_purpose,
                     required_fund_type, is_pranami, skips_approval, requires_member, template_head_pk, display_order,
                     created_by_sangha_sevi_pk)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_head_pk
                """,
                (str(body.organization_pk), t["head_code"], t["head_name"], t["description"], t["direction"], t["is_restricted"],
                 t["restriction_purpose"], t["required_fund_type"], t["is_pranami"], t["skips_approval"], t["requires_member"],
                 str(t["finance_head_pk"]), t["display_order"], user.actor_pk),
            )
            new_pk = cur.fetchone()[0]
            created += 1
            items.append(_head_response(cur, new_pk))
        if created:             # a repeat that copies nothing (the page calls this on first view of a Sangha) leaves no audit noise
            F._audit(cur, user, "CREATE", "finance_head", body.organization_pk, f"Adopted {created} finance head template(s)",
                     {"organization_pk": str(body.organization_pk), "created": created, "skipped": skipped})
        return {"created": created, "skipped": skipped, "items": items}


@router.get("/heads/{head_pk}", response_model=S.HeadResponse)
def get_head(head_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        head = F._head_row(cur, head_pk)
        _head_access(cur, user, head, "view this finance head", write=False)
        return _head_response(cur, head_pk)


@router.patch("/heads/{head_pk}", response_model=S.HeadResponse)
def update_head(head_pk: UUID, body: S.HeadUpdate, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        head = F._head_row(cur, head_pk)
        _head_access(cur, user, head, "change this finance head", write=True)
        sent = {k: getattr(body, k) for k in body.model_fields_set}
        cur.execute("SELECT h.template_head_pk, h.applies_to_all_sakhas, h.fixed_amount, h.due_period, h.allow_part_payment, "
                    "COALESCE(src.applies_to_all_sakhas, FALSE) FROM nss.finance_head h "
                    "LEFT JOIN nss.finance_head src ON src.finance_head_pk = h.template_head_pk WHERE h.finance_head_pk = %s", (str(head_pk),))
        _tpl, is_source, cur_amount, cur_period, cur_part, is_copy = cur.fetchone()
        values: dict = {}
        if is_copy:
            # A Sakha's copy of a Kendra head: name, amount, due period and part payment follow the Kendra; the Sakha only
            # chooses which of its own receiving accounts collects (and may switch the copy off by a transition).
            if set(sent) - {"collection_account_pk"}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="This Pranami comes from the Kendra: only its receiving account can be changed here.")
            account_pk = sent.get("collection_account_pk")
            if account_pk is not None:
                scope_pk = FC.ensure_org_scope(cur, user, head["organization_pk"])
                _validate_collection(cur, org_pk=head["organization_pk"], direction="INCOME", is_restricted=False, required_fund_type=None,
                                     allow_upi=True, scope_pk=scope_pk, fund_pk=None, account_pk=account_pk)
                values.update(collection_scope_pk=scope_pk, collection_account_pk=str(account_pk), allow_upi=True)
            elif "collection_account_pk" in sent:
                values.update(collection_account_pk=None, allow_upi=False)
            if values:
                F._update_row(cur, user, "finance_head", "finance_head_pk", head_pk, values)
                F._audit(cur, user, "UPDATE", "finance_head", head_pk, f"Changed the receiving account of {head['head_code']}", {"fields": sorted(values)})
            return _head_response(cur, head_pk)
        if is_source and {"allow_upi", "collection_scope_pk", "collection_fund_pk", "collection_account_pk"} & set(sent):
            raise F._invalid("A Pranami for all Sakhas collects through each Sakha's own copy, not itself.")
        if {"fixed_amount", "due_period", "allow_part_payment"} & set(sent):
            amount = sent["fixed_amount"] if "fixed_amount" in sent else cur_amount
            period = sent["due_period"] if "due_period" in sent else cur_period
            part = sent["allow_part_payment"] if sent.get("allow_part_payment") is not None else cur_part
            _check_amount_fields(amount, period, part, direction=head["direction"])
            values.update(fixed_amount=amount, due_period=period, allow_part_payment=part)
        if "head_name" in sent:
            if not F._clean(sent["head_name"]):
                raise F._invalid("head_name cannot be blank.")
            values["head_name"] = F._clean(sent["head_name"])
        if "description" in sent:
            values["description"] = F._clean(sent["description"])
        if "restriction_purpose" in sent:
            purpose = F._clean(sent["restriction_purpose"])
            if head["is_restricted"] and not purpose:
                raise F._invalid("A restricted head must keep its restriction_purpose (FIN-BR-020).")
            values["restriction_purpose"] = purpose
        # The Treasurer's own controls: a CHANGE of the head's "needs no approval" flag or Treasurer limit is refused for the seated Treasurer. The edit form
        # resends both on every save, so only a changed value counts (owner 2026-11-20).
        cur.execute("SELECT skips_approval, treasurer_limit FROM nss.finance_head WHERE finance_head_pk = %s", (str(head_pk),))
        cur_skips, cur_limit = cur.fetchone()
        if (sent.get("skips_approval") is not None and bool(sent["skips_approval"]) != bool(cur_skips)) or \
                ("treasurer_limit" in sent and sent["treasurer_limit"] != cur_limit):
            FA.require_not_the_treasurer(cur, user, head["organization_pk"], "the approval rules of a head (its Treasurer limit / 'needs no approval')")
        if sent.get("skips_approval") is not None:
            if sent["skips_approval"] and head["direction"] != "INCOME":
                raise F._invalid("Only an INCOME head can skip approval.")
            values["skips_approval"] = sent["skips_approval"]
        if "treasurer_limit" in sent:
            if sent["treasurer_limit"] is not None and head["direction"] != "EXPENSE":
                raise F._invalid("The Treasurer's limit applies to EXPENSE heads only.")
            values["treasurer_limit"] = sent["treasurer_limit"]
        if sent.get("requires_member") is not None:
            if sent["requires_member"] and head["direction"] != "EXPENSE":
                raise F._invalid("The reimbursement flag applies to EXPENSE heads only.")
            values["requires_member"] = sent["requires_member"]
        if "is_pranami" in sent and sent["is_pranami"] is not None:
            if sent["is_pranami"] and head["direction"] != "INCOME":
                raise F._invalid("Only an INCOME head can be a Pranami head.")
            values["is_pranami"] = sent["is_pranami"]
        # Owner 2026-11-20: every Pranami is payable online (UPI or card). Turning Pranami ON therefore turns online collection on too (which needs a
        # scope and a receiving account, and says so when it has none). A Pranami whose portal is CLOSED stays as it is: saving other changes never re-opens it.
        if sent.get("is_pranami") and not head["is_pranami"] and not is_source and head["organization_pk"] is not None:
            sent["allow_upi"] = True
        collection = {k: sent[k] for k in ("allow_upi", "collection_scope_pk", "collection_fund_pk", "collection_account_pk") if k in sent}
        if collection:
            merged = {"allow_upi": head["allow_upi"], "collection_scope_pk": head["collection_scope_pk"],
                      "collection_fund_pk": head["collection_fund_pk"], "collection_account_pk": head["collection_account_pk"], **collection}
            if merged["allow_upi"] is None:
                merged["allow_upi"] = False
            _validate_collection(cur, org_pk=head["organization_pk"], direction=head["direction"], is_restricted=head["is_restricted"],
                                 required_fund_type=head["required_fund_type"], allow_upi=merged["allow_upi"],
                                 scope_pk=merged["collection_scope_pk"], fund_pk=merged["collection_fund_pk"], account_pk=merged["collection_account_pk"])
            for k, v in merged.items():
                values[k] = str(v) if isinstance(v, UUID) else v
        if values:
            F._update_row(cur, user, "finance_head", "finance_head_pk", head_pk, values)
            F._audit(cur, user, "UPDATE", "finance_head", head_pk, f"Updated finance head {head['head_code']}", {"fields": sorted(values)})
            if is_source:
                FC.sync_copies(cur, user, head_pk)
        return _head_response(cur, head_pk)


@router.post("/heads/{head_pk}/sync-copies", response_model=S.SyncCopiesResult)
def sync_head_copies(head_pk: UUID, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """Bring every Sakha's copy of an all-Sakhas Kendra head up to date (new Sakhas get a copy). Idempotent; audited per copy."""
    with conn.cursor() as cur:
        head = F._head_row(cur, head_pk)
        _head_access(cur, user, head, "update the copies of this finance head", write=True)
        cur.execute("SELECT applies_to_all_sakhas FROM nss.finance_head WHERE finance_head_pk = %s", (str(head_pk),))
        if not cur.fetchone()[0]:
            raise F._invalid("Only a Pranami that applies to all Sakhas has copies to update.")
        result = FC.sync_copies(cur, user, head_pk)
        F._audit(cur, user, "UPDATE", "finance_head", head_pk, f"Updated the Sakha copies of {head['head_code']}", result)
        return result


def _head_money_count(cur, head_pks: list) -> int:
    """How many transactions, UPI payment requests and request lines name any of these heads (active or not: money history is never lost)."""
    if not head_pks:
        return 0
    arr = [str(p) for p in head_pks]
    cur.execute(
        "SELECT (SELECT COUNT(*) FROM nss.financial_transaction WHERE finance_head_pk = ANY(%s::uuid[]))"
        " + (SELECT COUNT(*) FROM nss.upi_payment_request WHERE finance_head_pk = ANY(%s::uuid[]))"
        " + (SELECT COUNT(*) FROM nss.upi_payment_request_line WHERE finance_head_pk = ANY(%s::uuid[]))", (arr, arr, arr))
    return cur.fetchone()[0]


@router.delete("/heads/{head_pk}", response_model=S.HeadDeleteResult)
def delete_head(head_pk: UUID, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    """
    Remove a finance head that was never used. A SOFT delete (``is_active = FALSE`` + deleted_at/by, audited; history is never erased).
    Refused while any transaction or UPI payment request names the head - money that came or went through a head keeps it; switch
    such a head OFF (``/transition``) instead. A Sakha's copy of a Kendra head cannot be deleted (switch it off); deleting a Kendra head
    for all Sakhas removes its copies too, and only when none of them has been used. FINANCE_CONFIGURE + admin scope on the Sangha.
    """
    with conn.cursor() as cur:
        head = F._head_row(cur, head_pk)
        _head_access(cur, user, head, "delete this finance head", write=True)
        cur.execute("SELECT h.template_head_pk, h.applies_to_all_sakhas, COALESCE(src.applies_to_all_sakhas, FALSE) "
                    "FROM nss.finance_head h LEFT JOIN nss.finance_head src ON src.finance_head_pk = h.template_head_pk "
                    "WHERE h.finance_head_pk = %s", (str(head_pk),))
        _tpl, is_source, is_copy = cur.fetchone()
        if is_copy:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="This Pranami comes from the Kendra: it cannot be deleted here. Switch it off instead.")
        copies: list = []
        if is_source:
            cur.execute("SELECT finance_head_pk FROM nss.finance_head WHERE template_head_pk = %s AND is_active = TRUE", (str(head_pk),))
            copies = [r[0] for r in cur.fetchall()]
        if _head_money_count(cur, [head_pk, *copies]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Money has already been recorded or requested on this head" + (" (or on a Sakha's copy of it)" if is_source else "")
                                       + ", so it cannot be deleted. Switch it off instead; its history stays.")
        for pk in [head_pk, *copies]:
            cur.execute("UPDATE nss.finance_head SET is_active = FALSE, status = 'INACTIVE', deleted_at = NOW(), deleted_by_sangha_sevi_pk = %s, "
                        "updated_at = NOW(), updated_by_sangha_sevi_pk = %s WHERE finance_head_pk = %s", (user.actor_pk, user.actor_pk, str(pk)))
        F._audit(cur, user, "DELETE", "finance_head", head_pk, f"Deleted finance head {head['head_code']}",
                 {"head_code": head["head_code"], "copies_deleted": len(copies)})
        for pk in copies:
            F._audit(cur, user, "DELETE", "finance_head", pk, f"Deleted with the Kendra head {head['head_code']}",
                     {"source_head_pk": str(head_pk), "automatic": True})
        return {"deleted": True, "head_code": head["head_code"], "copies_deleted": len(copies)}


@router.post("/heads/{head_pk}/transition", response_model=S.HeadResponse)
def transition_head(head_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_CONFIGURE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        head = F._head_row(cur, head_pk)
        _head_access(cur, user, head, "change this finance head", write=True)
        F._guard_transition(user, "head", head["status"], body.status, body.remarks, None)
        F._update_row(cur, user, "finance_head", "finance_head_pk", head_pk, {"status": body.status})
        F._audit(cur, user, "STATUS_CHANGE", "finance_head", head_pk, f"Finance head {head['head_code']} {head['status']} -> {body.status}",
                 {"from": head["status"], "to": body.status, "remarks": F._clean(body.remarks)})
        cur.execute("SELECT applies_to_all_sakhas FROM nss.finance_head WHERE finance_head_pk = %s", (str(head_pk),))
        if cur.fetchone()[0]:
            FC.set_copies_status(cur, user, head_pk, body.status)      # every Sakha copy follows the Kendra's on / off
        return _head_response(cur, head_pk)
