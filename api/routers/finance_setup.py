"""
NSS ERP — Finance setup router (Tier 12): receiving accounts and finance heads.

Everything that makes the Finance module CUSTOMIZABLE per Sangha lives here
(owner decision 2026-11-10): each Sangha's own receiving account(s) and its own
catalogue of finance heads, seeded from Kendra-published templates.

  GET   /api/v1/finance/accounts | POST            list / create a receiving account
  GET   /api/v1/finance/accounts/{pk} | PATCH      detail / edit
  POST  /api/v1/finance/accounts/{pk}/transition   ACTIVE <-> INACTIVE
  GET   /api/v1/finance/heads | POST               list (incl. templates) / create a head
  POST  /api/v1/finance/heads/adopt-templates      copy Kendra templates into a Sangha's catalogue
  GET   /api/v1/finance/heads/{pk} | PATCH         detail / edit
  POST  /api/v1/finance/heads/{pk}/transition      ACTIVE <-> INACTIVE

Authorization: configuration is sensitive (a head decides what is restricted,
what a member sees as Pranami and where UPI money lands; an account decides
where it is paid), so WRITES need FINANCE_APPROVE; reads need any FINANCE_*
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
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.routers import finance as F
from api.schemas import finance as S
from api.services import upi_gateway
from api.services.rbac_service import UserContext, actor_scope_org_pks

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_VIEW, _MANAGE, _APPROVE = F._VIEW, F._MANAGE, F._APPROVE

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
        upi_gateway.credentials_for(account.get("gateway_credential_ref"))
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
        cur.execute(_ACCOUNT_SELECT + f" WHERE {where_sql} ORDER BY o.organization_name, a.is_default DESC, a.account_label LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        items = F._fetch_all(cur)
    for row in items:
        row["gateway_ready"] = account_ready(row)
    return F._paged(items, total, page, page_size)


@router.post("/accounts", response_model=S.AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(body: S.AccountCreate, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
    """Register a receiving account for a Sangha. FINANCE_APPROVE + admin scope on the Sangha."""
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
        return _account_response(cur, pk)


@router.get("/accounts/{account_pk}", response_model=S.AccountResponse)
def get_account(account_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        acct = _account_row(cur, account_pk)
        F._require_org_access(cur, user, acct["organization_pk"], "view this receiving account")
        return _account_response(cur, account_pk)


@router.patch("/accounts/{account_pk}", response_model=S.AccountResponse)
def update_account(account_pk: UUID, body: S.AccountUpdate, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
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
        return _account_response(cur, account_pk)


@router.post("/accounts/{account_pk}/transition", response_model=S.AccountResponse)
def transition_account(account_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
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
"""
_HEAD_SELECT = """
    SELECT h.finance_head_pk, h.organization_pk, o.organization_name, (h.organization_pk IS NULL) AS is_template,
           h.head_code, h.head_name, h.description, h.direction, h.is_restricted, h.restriction_purpose,
           h.required_fund_type, h.is_pranami, h.allow_upi, h.collection_scope_pk, cs.scope_code AS collection_scope_code,
           h.collection_fund_pk, cf.fund_code AS collection_fund_code, h.collection_account_pk,
           ca.account_label AS collection_account_label, h.template_head_pk, h.display_order, h.status,
           (SELECT COUNT(*) FROM nss.financial_transaction t WHERE t.finance_head_pk = h.finance_head_pk AND t.is_active = TRUE) AS transaction_count
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


@router.get("/heads", response_model=S.HeadListResponse)
def list_heads(
    q: str | None = Query(None, description="Matches code or name"),
    organization_pk: UUID | None = Query(None),
    templates_only: bool = Query(False, description="Only Kendra templates"),
    with_templates: bool = Query(True, description="False: leave the Kendra templates out (only Sangha-owned heads)"),
    for_scope_pk: UUID | None = Query(None, description="Only ACTIVE heads a transaction in this financial scope may use"),
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
        if allow_upi is not None:
            where.append("h.allow_upi = %s"); params.append(allow_upi)
        if q and q.strip():
            where.append("(h.head_code ILIKE %s OR h.head_name ILIKE %s)"); params += [f"%{q.strip()}%"] * 2
        where_sql = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) {_HEAD_FROM} WHERE {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(_HEAD_SELECT + f" WHERE {where_sql} ORDER BY h.display_order, h.head_name LIMIT %s OFFSET %s",
                    params + [page_size, (page - 1) * page_size])
        return F._paged(F._fetch_all(cur), total, page, page_size)


@router.post("/heads", response_model=S.HeadResponse, status_code=status.HTTP_201_CREATED)
def create_head(body: S.HeadCreate, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
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
    with conn.cursor() as cur:
        _head_access(cur, user, {"organization_pk": body.organization_pk}, "create a finance head for this organization", write=True)
        if body.organization_pk is not None:
            F._require_active_organization(cur, body.organization_pk, "Organization")
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
                 collection_account_pk, display_order, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_head_pk
            """,
            (str(body.organization_pk) if body.organization_pk else None, code, name, F._clean(body.description), body.direction,
             body.is_restricted, purpose, body.required_fund_type, body.is_pranami, body.allow_upi,
             str(body.collection_scope_pk) if body.collection_scope_pk else None,
             str(body.collection_fund_pk) if body.collection_fund_pk else None,
             str(body.collection_account_pk) if body.collection_account_pk else None, body.display_order, user.actor_pk),
        )
        pk = cur.fetchone()[0]
        F._audit(cur, user, "CREATE", "finance_head", pk, f"Created finance head {code}",
                 {"organization_pk": str(body.organization_pk) if body.organization_pk else None, "direction": body.direction})
        return _head_response(cur, pk)


@router.post("/heads/adopt-templates", response_model=S.AdoptTemplatesResult)
def adopt_templates(body: S.AdoptTemplates, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
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
                    f"required_fund_type, is_pranami, display_order FROM nss.finance_head WHERE {where} ORDER BY display_order, head_code", params)
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
                     required_fund_type, is_pranami, template_head_pk, display_order, created_by_sangha_sevi_pk)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING finance_head_pk
                """,
                (str(body.organization_pk), t["head_code"], t["head_name"], t["description"], t["direction"], t["is_restricted"],
                 t["restriction_purpose"], t["required_fund_type"], t["is_pranami"], str(t["finance_head_pk"]), t["display_order"], user.actor_pk),
            )
            new_pk = cur.fetchone()[0]
            created += 1
            items.append(_head_response(cur, new_pk))
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
def update_head(head_pk: UUID, body: S.HeadUpdate, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        head = F._head_row(cur, head_pk)
        _head_access(cur, user, head, "change this finance head", write=True)
        sent = {k: getattr(body, k) for k in body.model_fields_set}
        values: dict = {}
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
        if "display_order" in sent and sent["display_order"] is not None:
            values["display_order"] = sent["display_order"]
        if "is_pranami" in sent and sent["is_pranami"] is not None:
            if sent["is_pranami"] and head["direction"] != "INCOME":
                raise F._invalid("Only an INCOME head can be a Pranami head.")
            values["is_pranami"] = sent["is_pranami"]
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
        return _head_response(cur, head_pk)


@router.post("/heads/{head_pk}/transition", response_model=S.HeadResponse)
def transition_head(head_pk: UUID, body: S.TransitionRequest, user: UserContext = Depends(_APPROVE), conn=Depends(get_write_connection)):
    with conn.cursor() as cur:
        head = F._head_row(cur, head_pk)
        _head_access(cur, user, head, "change this finance head", write=True)
        F._guard_transition(user, "head", head["status"], body.status, body.remarks, None)
        F._update_row(cur, user, "finance_head", "finance_head_pk", head_pk, {"status": body.status})
        F._audit(cur, user, "STATUS_CHANGE", "finance_head", head_pk, f"Finance head {head['head_code']} {head['status']} -> {body.status}",
                 {"from": head["status"], "to": body.status, "remarks": F._clean(body.remarks)})
        return _head_response(cur, head_pk)
