"""
NSS ERP — Assets & Property router (Module #22, Tier 6).

Properties (immovable), assets (movable), custodianship history, property
statutory records, maintenance records and document links. Authority:
docs/03_Solution/modules/assets_property/ (SOL-AP-001..005, business rules
AP-001..AP-074), GDR-010 (implementation decisions on the PENDING items).

  POST   /api/v1/assets-property/properties                          — register a property
  GET    /api/v1/assets-property/properties                          — list/search (paged)
  GET    /api/v1/assets-property/properties/{pk}                     — detail
  PATCH  /api/v1/assets-property/properties/{pk}                     — edit descriptive fields
  POST   /api/v1/assets-property/properties/{pk}/transition          — lifecycle event
  DELETE /api/v1/assets-property/properties/{pk}                     — archive (soft delete)
  (the same six for /assets, with asset-specific fields)

  GET    /api/v1/assets-property/{kind}/{pk}/custodianships          — custody history
  POST   /api/v1/assets-property/{kind}/{pk}/custodianships          — assign the first custodian
  POST   /api/v1/assets-property/{kind}/{pk}/custodianships/transfer — close current + open new
  GET    /api/v1/assets-property/{kind}/{pk}/maintenance-records     — list
  POST   /api/v1/assets-property/{kind}/{pk}/maintenance-records     — record maintenance
  PATCH  /api/v1/assets-property/maintenance-records/{record_pk}     — correct
  DELETE /api/v1/assets-property/maintenance-records/{record_pk}     — soft delete
  GET    /api/v1/assets-property/{kind}/{pk}/documents               — attached documents
  POST   /api/v1/assets-property/{kind}/{pk}/documents               — attach a document_master row
  DELETE /api/v1/assets-property/{kind}/{pk}/documents/{link_pk}     — detach (soft delete)
  GET    /api/v1/assets-property/properties/{pk}/statutory-records   — property ONLY (AP-040)
  POST   /api/v1/assets-property/properties/{pk}/statutory-records
  PATCH  /api/v1/assets-property/statutory-records/{record_pk}
  DELETE /api/v1/assets-property/statutory-records/{record_pk}
  ({kind} is "properties" or "assets")

Authorization (AP-074, centralized RBAC — no module authorization tables):
ASSET_VIEW (reads) / ASSET_MANAGE (writes) PLUS admin scope on the EFFECTIVE
CUSTODIAN organization of the record (``require_org_in_scope`` /
``actor_scope_org_pks``). Effective custodian (GDR-010 §2F) = the ACTIVE
custodianship's organization or, for a terminal record (DISPOSED property /
RETIRED asset, whose custody the terminal transition ENDed), the organization
of its most recently ENDED custodianship — one SQL definition,
``_effective_custodian_join()``, used by detail, list, filters and every scope
check, so a disposed record stays visible to (and only to) the admins who could
see it before and never degrades to 'custodian-less'. A record with no
effective custodian is visible and manageable
only to the global authority (NSS_ERP_ADMIN / NSS-wide / Kendra scope). A
custody transfer needs scope over BOTH the releasing and the receiving
organization, so a scope-bounded admin can neither hand a record to an
unrelated unit nor take one from another. Nothing here is exposed to
members/public.

Rules enforced here (API first, DB triggers in
database/ddl/11_assets_property/08_assets_property_guards.sql as backstop):
  - identifiers (property_id / asset_id) are minted by next_id() and immutable
    (AP-004..008); status is never writable through PATCH;
  - lifecycle transitions follow SOL-AP-003 §3.2/§4.2; DISPOSED / RETIRED are
    terminal (AP-046/047) and, in the SAME transaction, END the active
    custodianship (end reason DISPOSED / RETIRED, effective_to = transition
    date; owner decision 2026-11-03, GDR-010 §2F) — the last custodian is still
    reported, flagged ``custodian_is_last``; leaving REGISTERED needs a custodian (AP-LIF-001);
    assigning the first custodian advances REGISTERED -> ACTIVE / IN_CUSTODY
    (SOL-AP-003 §3.3); a transfer never changes the lifecycle status (AP-041);
  - one ACTIVE custodian per record (AP-017); a transfer ENDs the current
    custodianship (with an end reason, AP-058) and opens a new one — history is
    never overwritten or deleted (AP-018/042/072); the custodian is always an
    organization (AP-015) and a PHYSICAL one — Sakha (incl. Sakha Asana),
    Patha Chakra, Kendra, Nilachala Kutira or Smruti Mandira (owner rule
    2026-11-02, GDR-010 §2C; ``ASSET_CUSTODIAN_ORG_TYPES`` in api/helpers.py).
    Conceptual groupings (Anchalika / Zilla Sangha), wing organizations and the
    Advisory Board never hold property/assets: 422 on create-with-custodian,
    assign and transfer (admins of a grouping manage the physical organizations
    beneath them through the ordinary admin-scope subtree rule, and the list
    endpoints accept ``include_sub_organizations`` to filter a whole subtree);
  - 'belongs to' (GDR-010 item 4): property/asset carry an OPTIONAL
    ``belongs_to_organization_pk`` (any ACTIVE organization, nullable, null
    clears) distinct from the physical custodian — e.g. custodian = Kendra
    Sangha, belongs to = Mahila Sangha. Informational only: no effect on
    authorization, admin scope, the custodian rule or lifecycle, and the list
    filter of the same name never widens visibility beyond the custodian scope;
  - acquisition method (GDR-010 §2E, open question 4): OPTIONAL
    ``acquisition_method_code`` (master_data ACQUISITION_METHOD, unknown -> 422,
    null clears) records HOW it was acquired (AP-023); informational only and
    filterable, never an authorization input;
  - statutory records are property-only (AP-040): there is no asset route;
  - disposal / retirement / acquisition are RECORDED, not approved, here
    (AP-025/045/073): ``remarks`` carries the Governance decision reference
    into the audit trail;
  - no financial fields exist (AP-031/039/048/060..063).
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.rbac import require_any_permission, require_permission
from api.helpers import get_master_data_pk, is_asset_custodian_org_type, log_audit, next_id
from api.schemas.assets_property import (
    AssetCreate,
    AssetListResponse,
    AssetResponse,
    AssetUpdate,
    CustodianshipAssign,
    CustodianshipListResponse,
    CustodianshipResponse,
    CustodianshipTransfer,
    CustodianshipTransferResponse,
    DocumentLinkCreate,
    DocumentLinkListResponse,
    DocumentLinkResponse,
    MaintenanceCreate,
    MaintenanceListResponse,
    MaintenanceResponse,
    MaintenanceUpdate,
    PropertyCreate,
    PropertyListResponse,
    PropertyResponse,
    PropertyUpdate,
    StatutoryRecordCreate,
    StatutoryRecordListResponse,
    StatutoryRecordResponse,
    StatutoryRecordUpdate,
    TransitionRequest,
)
from api.schemas.auth import MessageResponse
from api.services.rbac_service import UserContext, actor_scope_org_pks, org_subtree_pks, require_org_in_scope

router = APIRouter(prefix="/api/v1/assets-property", tags=["assets-property"])

_VIEW = require_any_permission("ASSET_VIEW", "ASSET_MANAGE")
_MANAGE = require_permission("ASSET_MANAGE")


# ═══════════════════════════════════════════════════════════════════════
# Property / asset descriptors — one set of handlers serves both entities
# ═══════════════════════════════════════════════════════════════════════

class EntityKind(str, Enum):
    properties = "properties"
    assets = "assets"


@dataclass(frozen=True)
class _Kind:
    label: str            # "property" / "asset" — also the response-key prefix
    route_prefix: str     # "/properties" / "/assets"
    table: str
    pk_col: str
    id_col: str
    name_col: str
    type_col: str         # master_data FK column
    type_category: str    # master_category.category_code of the type
    extra_col: str        # holding_arrangement / condition
    seq_code: str         # id_sequence_master code
    entered_status: str   # what REGISTERED advances to once custody exists
    terminal_status: str
    transitions: dict     # SOL-AP-003 §3.2 / §4.2 — keep in step with fn_ap_entity_guard()
    doc_table: str
    doc_pk_col: str
    response_model: type
    list_model: type


_PROPERTY = _Kind(
    label="property", route_prefix="/properties", table="property", pk_col="property_pk", id_col="property_id",
    name_col="property_name", type_col="property_type_master_data_pk", type_category="PROPERTY_TYPE",
    extra_col="holding_arrangement", seq_code="PROPERTY",
    entered_status="ACTIVE", terminal_status="DISPOSED",
    transitions={
        "REGISTERED": {"ACTIVE"},
        "ACTIVE": {"UNDER_MAINTENANCE", "DISPOSED"},
        "UNDER_MAINTENANCE": {"ACTIVE", "DISPOSED"},
        "DISPOSED": set(),
    },
    doc_table="property_document", doc_pk_col="property_document_pk",
    response_model=PropertyResponse, list_model=PropertyListResponse,
)
_ASSET = _Kind(
    label="asset", route_prefix="/assets", table="asset", pk_col="asset_pk", id_col="asset_id",
    name_col="asset_name", type_col="asset_type_master_data_pk", type_category="ASSET_TYPE",
    extra_col="condition", seq_code="ASSET",
    entered_status="IN_CUSTODY", terminal_status="RETIRED",
    transitions={
        "REGISTERED": {"IN_CUSTODY"},
        "IN_CUSTODY": {"UNDER_MAINTENANCE", "RETIRED"},
        "UNDER_MAINTENANCE": {"IN_CUSTODY", "RETIRED"},
        "RETIRED": set(),
    },
    doc_table="asset_document", doc_pk_col="asset_document_pk",
    response_model=AssetResponse, list_model=AssetListResponse,
)
_KINDS = {EntityKind.properties: _PROPERTY, EntityKind.assets: _ASSET}

# Entities are archived (soft-deleted) only while they have no live lifecycle:
# never-activated (REGISTERED, e.g. registered in error) or already terminal.
_ARCHIVABLE_STATUSES = {"REGISTERED", "DISPOSED", "RETIRED"}

_ACQUISITION_METHOD_CATEGORY = "ACQUISITION_METHOD"

# CUSTODIANSHIP_END_REASON values reserved for the terminal transition (the
# value_code equals the terminal status). A routine custody transfer must not
# claim them.
_LIFECYCLE_END_REASONS = frozenset({_PROPERTY.terminal_status, _ASSET.terminal_status})


# ═══════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════

def _audit(cur, user: UserContext, action: str, table: str, pk, summary: str, detail: dict | None = None) -> None:
    log_audit(
        cur, action=action, table_name=table, record_pk=str(pk),
        actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
        module="assets_property", summary=summary, detail=detail,
    )


def _update_row(cur, user: UserContext, table: str, pk_col: str, pk, values: dict[str, Any]) -> None:
    """UPDATE the given columns (identifiers come from code, never from input) + stamp the audit columns."""
    sets = [f"{col} = %s" for col in values] + ["updated_at = NOW()", "updated_by_sangha_sevi_pk = %s"]
    cur.execute(
        f"UPDATE nss.{table} SET {', '.join(sets)} WHERE {pk_col} = %s",
        [*values.values(), user.actor_pk, str(pk)],
    )


def _soft_delete(cur, user: UserContext, table: str, pk_col: str, pk) -> None:
    cur.execute(
        f"""
        UPDATE nss.{table}
           SET is_active = FALSE, deleted_at = NOW(), deleted_by_sangha_sevi_pk = %s,
               updated_at = NOW(), updated_by_sangha_sevi_pk = %s
         WHERE {pk_col} = %s
        """,
        (user.actor_pk, user.actor_pk, str(pk)),
    )


def _require_custodian_scope(cur, user: UserContext, custodian_pk, action: str) -> None:
    """
    Admin scope on the CURRENT custodian. A record with no custodian has no
    organizational anchor, so only the global authority (actor scope = None)
    may touch it — same convention as require_person_in_scope for a person
    with no Sangha Sevi.
    """
    if custodian_pk is None:
        if actor_scope_org_pks(cur, user) is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This record has no custodian, so only NSS-wide administrators can {action}.",
            )
        return
    require_org_in_scope(cur, user, custodian_pk, action)


def _effective_custodian_join(k: _Kind, entity_alias: str = "e") -> str:
    """
    THE single definition of the effective custodian (GDR-010 §2F), joined as
    ``cu`` (nss.custodianship columns) onto the entity aliased ``entity_alias``:
    the ACTIVE custodianship; else, only for a TERMINAL record (DISPOSED
    property / RETIRED asset - its custody was ENDed by the terminal
    transition), the most recently ENDED one (latest effective_to, then
    effective_from, then created_at). Non-terminal records never fall back to
    ENDED history, so a mid-life record with no active custodian stays
    'custodian-less' exactly as before. Used by detail, list, filters and every
    scope check - never re-derive it.
    """
    return f"""
        LEFT JOIN LATERAL (
            SELECT c.*
            FROM nss.custodianship c
            WHERE c.{k.pk_col} = {entity_alias}.{k.pk_col}
              AND c.is_active = TRUE
              AND (c.status = 'ACTIVE'
                   OR (c.status = 'ENDED' AND {entity_alias}.status = '{k.terminal_status}'))
            ORDER BY (c.status = 'ACTIVE') DESC, c.effective_to DESC NULLS FIRST,
                     c.effective_from DESC, c.created_at DESC
            LIMIT 1
        ) cu ON TRUE
    """


def _entity_head(cur, user: UserContext, k: _Kind, entity_pk, verb: str, *, lock: bool = False):
    """
    404 unless an active record exists; 403 unless its EFFECTIVE custodian
    (active, or last for a terminal record) is in the caller's scope. Returns
    (status, effective_custodian_organization_pk).
    """
    cur.execute(
        f"""
        SELECT e.status, cu.custodian_organization_pk
        FROM nss.{k.table} e
        {_effective_custodian_join(k)}
        WHERE e.{k.pk_col} = %s AND e.is_active = TRUE
        {"FOR UPDATE OF e" if lock else ""}
        """,
        (str(entity_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{k.label.capitalize()} not found.")
    _require_custodian_scope(cur, user, row[1], f"{verb} this {k.label}")
    return row[0], row[1]


def _active_organization(cur, organization_pk, label: str):
    """(name, type_code, type_name) of an ACTIVE organization; 422 '<label> organization not found.' otherwise."""
    cur.execute(
        """
        SELECT o.organization_name, md.value_code, md.value_name
        FROM   nss.organization o
        JOIN   nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE  o.organization_pk = %s AND o.is_active = TRUE
        """,
        (str(organization_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail=f"{label} organization not found.")
    return row


def _require_belongs_to_org(cur, organization_pk) -> None:
    """
    Optional 'belongs to' attribution (GDR-010 item 4): ANY organization type
    is acceptable (Mahila Sangha, Kumari, Sevak, Paribarik, Zilla, Anchalika,
    ...) as long as it is an ACTIVE organization. Deliberately no scope check
    and no custodian-type check: it is informational and never affects
    authorization, visibility or the custodian rule.
    """
    _active_organization(cur, organization_pk, "Belongs-to")


def _require_custodian_org(cur, organization_pk, label: str) -> None:
    """
    The custodian must be an ACTIVE *physical* organization (owner rule
    2026-11-02, GDR-010 §2C): property and assets are held only by Sakha
    (incl. Sakha Asana), Patha Chakra, Kendra, Nilachala Kutira or Smruti
    Mandira — never by a conceptual grouping (Anchalika / Zilla Sangha), a
    wing organization or the Advisory Board. 422 otherwise. The DB trigger
    nss.fn_custodianship_custodian_guard() is the backstop.
    """
    name, type_code, type_name = _active_organization(cur, organization_pk, label)
    if not is_asset_custodian_org_type(type_code):
        raise HTTPException(
            status_code=422,
            detail=(
                f"{label} organization '{name}' is a {type_name or type_code} ({type_code}); property and assets are "
                "held by physical organizations (Sakha, Patha Chakra, Kendra, Nilachala Kutira, Smruti Mandira). "
                "Assign it to the Sakha or other physical organization instead."
            ),
        )


def _require_not_terminal(k: _Kind, entity_status: str) -> None:
    if entity_status == k.terminal_status:
        rule = "AP-046" if k.label == "property" else "AP-047"
        raise HTTPException(
            status_code=422,
            detail=f"This {k.label} is {k.terminal_status} (terminal, {rule}); its custodianship can no longer change.",
        )


def _clean_text(value):
    """Blank/whitespace-only optional text is stored as NULL."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# ── Entity SELECT ───────────────────────────────────────────────────────

def _entity_from(k: _Kind) -> str:
    return f"""
        FROM nss.{k.table} e
        JOIN nss.master_data t ON t.master_data_pk = e.{k.type_col}
        {_effective_custodian_join(k)}
        LEFT JOIN nss.organization co ON co.organization_pk = cu.custodian_organization_pk
        LEFT JOIN nss.organization bo ON bo.organization_pk = e.belongs_to_organization_pk
        LEFT JOIN nss.master_data am ON am.master_data_pk = e.acquisition_method_master_data_pk
    """


def _entity_select(k: _Kind) -> str:
    return f"""
        SELECT e.{k.pk_col}, e.{k.id_col}, e.{k.name_col}, t.value_code, t.value_name, e.status,
               e.location_description, e.{k.extra_col}, e.notes, e.acquired_at,
               cu.custodianship_pk, cu.custodian_organization_pk, co.organization_name, cu.effective_from,
               e.created_at, e.updated_at, e.belongs_to_organization_pk, bo.organization_name,
               am.value_code, am.value_name, cu.status, cu.effective_to
        {_entity_from(k)}
    """


def _entity_response(k: _Kind, r):
    return k.response_model(**{
        k.pk_col: r[0], k.id_col: r[1], k.name_col: r[2],
        f"{k.label}_type_code": r[3], f"{k.label}_type_name": r[4],
        "status": r[5], "location_description": r[6], k.extra_col: r[7],
        "notes": r[8], "acquired_at": r[9],
        "current_custodianship_pk": r[10], "current_custodian_organization_pk": r[11],
        "current_custodian_organization_name": r[12], "current_custodian_since": r[13],
        "created_at": r[14], "updated_at": r[15],
        "belongs_to_organization_pk": r[16], "belongs_to_organization_name": r[17],
        "acquisition_method_code": r[18], "acquisition_method_name": r[19],
        "custodian_is_last": r[20] == "ENDED", "custodian_ended_at": r[21] if r[20] == "ENDED" else None,
    })


def _fetch_entity(cur, k: _Kind, entity_pk):
    cur.execute(_entity_select(k) + f" WHERE e.{k.pk_col} = %s AND e.is_active = TRUE", (str(entity_pk),))
    return _entity_response(k, cur.fetchone())


# ── Custodianship primitives ────────────────────────────────────────────

_CUSTODIANSHIP_SELECT = """
    SELECT c.custodianship_pk, c.property_pk, c.asset_pk, c.custodian_organization_pk, o.organization_name,
           c.status, c.effective_from, c.effective_to, er.value_code, er.value_name, c.notes, c.created_at
    FROM nss.custodianship c
    JOIN nss.organization o ON o.organization_pk = c.custodian_organization_pk
    LEFT JOIN nss.master_data er ON er.master_data_pk = c.end_reason_master_data_pk
"""


def _custodianship_response(r) -> CustodianshipResponse:
    return CustodianshipResponse(
        custodianship_pk=r[0], property_pk=r[1], asset_pk=r[2],
        custodian_organization_pk=r[3], custodian_organization_name=r[4],
        status=r[5], effective_from=r[6], effective_to=r[7],
        end_reason_code=r[8], end_reason_name=r[9], notes=r[10], created_at=r[11],
    )


def _fetch_custodianship(cur, custodianship_pk) -> CustodianshipResponse:
    cur.execute(_CUSTODIANSHIP_SELECT + " WHERE c.custodianship_pk = %s", (str(custodianship_pk),))
    return _custodianship_response(cur.fetchone())


def _set_entity_status(cur, user: UserContext, k: _Kind, entity_pk, new_status: str) -> None:
    _update_row(cur, user, k.table, k.pk_col, entity_pk, {"status": new_status})


def _open_custodianship(
    cur, user: UserContext, k: _Kind, entity_pk, entity_status: str,
    organization_pk, effective_from: date | None, notes: str | None,
) -> str:
    """
    New custodianship: ASSIGNED -> ACTIVE (AP-042, SOL-AP-003 §5.4), both steps
    in the caller's transaction. When the record is still REGISTERED, the first
    custody advances it to ACTIVE / IN_CUSTODY (SOL-AP-003 §3.3 / §4.3: "enters
    active state when custody is assigned"). Returns the custodianship_pk.
    """
    cur.execute(
        f"""
        INSERT INTO nss.custodianship
            ({k.pk_col}, custodian_organization_pk, status, effective_from, notes, created_by_sangha_sevi_pk)
        VALUES (%s, %s, 'ASSIGNED', %s, %s, %s)
        RETURNING custodianship_pk
        """,
        (str(entity_pk), str(organization_pk), effective_from or date.today(), _clean_text(notes), user.actor_pk),
    )
    custodianship_pk = cur.fetchone()[0]
    _update_row(cur, user, "custodianship", "custodianship_pk", custodianship_pk, {"status": "ACTIVE"})
    if entity_status == "REGISTERED":
        _set_entity_status(cur, user, k, entity_pk, k.entered_status)
        _audit(cur, user, "STATUS_CHANGE", k.table, entity_pk,
               f"{k.label.capitalize()} advanced REGISTERED -> {k.entered_status} on first custodian assignment",
               {"from": "REGISTERED", "to": k.entered_status, "trigger": "first_custodianship"})
    return str(custodianship_pk)


# ═══════════════════════════════════════════════════════════════════════
# Property / asset CRUD + lifecycle (registered per kind by a factory)
# ═══════════════════════════════════════════════════════════════════════

def _create_entity(
    cur, user: UserContext, k: _Kind, *, name: str, type_code: str, location, extra, notes,
    acquired_at, custodian_pk, custodian_from, belongs_to_pk=None, acquisition_method_code=None,
):
    if not name or not name.strip():
        raise HTTPException(status_code=422, detail=f"{k.name_col} cannot be blank.")
    type_pk = get_master_data_pk(cur, k.type_category, type_code, client_supplied=True)
    if custodian_pk is None:
        if actor_scope_org_pks(cur, user) is not None:
            raise HTTPException(
                status_code=422,
                detail=f"custodian_organization_pk is required: only NSS-wide administrators may register a {k.label} without a custodian.",
            )
    else:
        _require_custodian_org(cur, custodian_pk, "Custodian")
        require_org_in_scope(cur, user, custodian_pk, f"register {k.label} records for this organization")

    if belongs_to_pk is not None:
        _require_belongs_to_org(cur, belongs_to_pk)

    acquisition_pk = (
        get_master_data_pk(cur, _ACQUISITION_METHOD_CATEGORY, acquisition_method_code, client_supplied=True)
        if acquisition_method_code else None
    )

    business_id = next_id(cur, k.seq_code)
    cur.execute(
        f"""
        INSERT INTO nss.{k.table}
            ({k.id_col}, {k.name_col}, {k.type_col}, location_description, {k.extra_col}, notes,
             acquired_at, belongs_to_organization_pk, acquisition_method_master_data_pk, created_by_sangha_sevi_pk)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {k.pk_col}
        """,
        (business_id, name.strip(), type_pk, _clean_text(location), _clean_text(extra), _clean_text(notes),
         acquired_at, str(belongs_to_pk) if belongs_to_pk is not None else None, acquisition_pk, user.actor_pk),
    )
    entity_pk = cur.fetchone()[0]
    _audit(cur, user, "CREATE", k.table, entity_pk, f"Registered {k.label} {business_id}", {"id": business_id})
    if custodian_pk is not None:
        cust_pk = _open_custodianship(cur, user, k, entity_pk, "REGISTERED", custodian_pk, custodian_from, None)
        _audit(cur, user, "CREATE", "custodianship", cust_pk, f"Assigned initial custodian to {business_id}")
    return entity_pk


def _list_entities(
    cur, user: UserContext, k: _Kind, *, q, type_code, status_filter, custodian_pk, include_sub_organizations=False,
    belongs_to_pk=None, acquisition_method_code=None, page, page_size,
):
    where = ["e.is_active = TRUE"]
    params: list = []

    allowed = actor_scope_org_pks(cur, user)
    if allowed is not None:
        if not allowed:
            return k.list_model(items=[], total=0, page=page, page_size=page_size)
        where.append("cu.custodian_organization_pk = ANY(%s::uuid[])")
        params.append(sorted(allowed))
    if custodian_pk is not None:
        require_org_in_scope(cur, user, custodian_pk, f"view this organization's {k.label} records")
        if include_sub_organizations:
            # The filtered organization AND its whole subtree (e.g. everything
            # held by the Sakhas under an Anchalika/Zilla). Still intersected
            # with the caller's scope by the ``allowed`` clause above.
            where.append("cu.custodian_organization_pk = ANY(%s::uuid[])")
            params.append(sorted(org_subtree_pks(cur, custodian_pk)))
        else:
            where.append("cu.custodian_organization_pk = %s")
            params.append(str(custodian_pk))
    if belongs_to_pk is not None:
        # Pure attribute filter, ANDed with the custodian-scope clause above:
        # 'belongs to' never widens what the caller may see.
        where.append("e.belongs_to_organization_pk = %s")
        params.append(str(belongs_to_pk))
    if acquisition_method_code:
        where.append("am.value_code = %s")
        params.append(acquisition_method_code)
    if type_code:
        where.append("t.value_code = %s")
        params.append(type_code)
    if status_filter:
        where.append("e.status = %s")
        params.append(status_filter)
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append(f"(e.{k.name_col} ILIKE %s OR e.{k.id_col} ILIKE %s OR e.location_description ILIKE %s)")
        params.extend([like, like, like])

    where_sql = " AND ".join(where)
    cur.execute(f"SELECT COUNT(*) {_entity_from(k)} WHERE {where_sql}", params)
    total = cur.fetchone()[0]
    cur.execute(
        _entity_select(k) + f" WHERE {where_sql} ORDER BY e.created_at DESC, e.{k.id_col} LIMIT %s OFFSET %s",
        params + [page_size, (page - 1) * page_size],
    )
    return k.list_model(
        items=[_entity_response(k, r) for r in cur.fetchall()], total=total, page=page, page_size=page_size,
    )


def _update_entity(cur, user: UserContext, k: _Kind, entity_pk, fields: dict[str, Any]) -> None:
    status_now, _ = _entity_head(cur, user, k, entity_pk, "edit", lock=True)
    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update.")
    values: dict[str, Any] = {}
    for col, value in fields.items():
        if col == f"{k.label}_type_code":
            if value is None:
                raise HTTPException(status_code=422, detail=f"{col} cannot be cleared.")
            values[k.type_col] = get_master_data_pk(cur, k.type_category, value, client_supplied=True)
        elif col == "acquisition_method_code":
            values["acquisition_method_master_data_pk"] = (
                get_master_data_pk(cur, _ACQUISITION_METHOD_CATEGORY, value, client_supplied=True)
                if value else None
            )
        elif col == "belongs_to_organization_pk":
            if value is not None:
                _require_belongs_to_org(cur, value)
            values[col] = str(value) if value is not None else None
        elif col == k.name_col:
            if value is None or not value.strip():
                raise HTTPException(status_code=422, detail=f"{col} cannot be blank.")
            values[col] = value.strip()
        else:
            values[col] = _clean_text(value)
    _update_row(cur, user, k.table, k.pk_col, entity_pk, values)
    _audit(cur, user, "UPDATE", k.table, entity_pk, f"Updated {k.label} fields: {', '.join(sorted(fields))}",
           {"fields": sorted(fields)})


def _transition_entity(cur, user: UserContext, k: _Kind, entity_pk, target: str, remarks: str | None) -> None:
    current, custodian = _entity_head(cur, user, k, entity_pk, "record a lifecycle event for", lock=True)
    known = set(k.transitions)
    if target not in known:
        raise HTTPException(status_code=422, detail=f"Unknown {k.label} status '{target}'. Valid: {', '.join(sorted(known))}.")
    if current == k.terminal_status:
        rule = "AP-046" if k.label == "property" else "AP-047"
        raise HTTPException(status_code=422, detail=f"A {current} {k.label} is terminal and cannot change status ({rule}).")
    if target == current:
        raise HTTPException(status_code=422, detail=f"The {k.label} is already {current}.")
    if target not in k.transitions[current]:
        allowed = ", ".join(sorted(k.transitions[current])) or "none"
        raise HTTPException(status_code=422, detail=f"Invalid transition {current} -> {target}. Allowed from {current}: {allowed}.")
    if current == "REGISTERED" and custodian is None:
        raise HTTPException(
            status_code=422,
            detail=f"A {k.label} needs a custodian before leaving REGISTERED (AP-LIF-001). Assign a custodian first.",
        )
    ended_custodianship = None
    if target == k.terminal_status:
        # Owner decision 2026-11-03 (GDR-010 §2F): the terminal event ENDs the
        # active custodianship in the same transaction. The custodian stays on
        # the record as the LAST custodian (effective custodian definition).
        ended_custodianship = _end_custody_on_terminal(cur, user, k, entity_pk)
    _set_entity_status(cur, user, k, entity_pk, target)
    _audit(cur, user, "STATUS_CHANGE", k.table, entity_pk, f"{k.label.capitalize()} {current} -> {target}",
           {"from": current, "to": target, "remarks": _clean_text(remarks),
            **({"ended_custodianship_pk": ended_custodianship} if ended_custodianship else {})})


def _end_custody_on_terminal(cur, user: UserContext, k: _Kind, entity_pk) -> str | None:
    """
    END the ACTIVE custodianship of a record going DISPOSED / RETIRED: status
    ENDED, effective_to = today (never before effective_from), end reason =
    the master_data CUSTODIANSHIP_END_REASON value named like the terminal
    status. Returns the ended custodianship_pk (None when no active custody
    exists, e.g. a legacy row). The caller owns the transaction.
    """
    cur.execute(
        f"""
        SELECT custodianship_pk, effective_from FROM nss.custodianship
        WHERE {k.pk_col} = %s AND status = 'ACTIVE' AND is_active = TRUE FOR UPDATE
        """,
        (str(entity_pk),),
    )
    row = cur.fetchone()
    if row is None:
        return None
    custodianship_pk, effective_from = row
    end_reason_pk = get_master_data_pk(cur, "CUSTODIANSHIP_END_REASON", k.terminal_status)
    _update_row(cur, user, "custodianship", "custodianship_pk", custodianship_pk, {
        "status": "ENDED", "effective_to": max(date.today(), effective_from),
        "end_reason_master_data_pk": end_reason_pk,
    })
    _audit(cur, user, "UPDATE", "custodianship", custodianship_pk,
           f"Custodianship ended by {k.terminal_status} of the {k.label}",
           {k.pk_col: str(entity_pk), "end_reason": k.terminal_status})
    return str(custodianship_pk)


def _archive_entity(cur, user: UserContext, k: _Kind, entity_pk) -> None:
    current, _ = _entity_head(cur, user, k, entity_pk, "archive", lock=True)
    if current not in _ARCHIVABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"This {k.label} is {current} (in live use); record its {k.terminal_status} first, then archive it.",
        )
    _soft_delete(cur, user, k.table, k.pk_col, entity_pk)
    _audit(cur, user, "DELETE", k.table, entity_pk, f"Archived {k.label} (status {current})", {"status": current})


def _register_entity_routes(k: _Kind, create_model: type, update_model: type) -> None:
    """Register the six CRUD/lifecycle routes of one entity kind (same handlers, kind-specific models)."""
    prefix = k.route_prefix
    response_model, list_model = k.response_model, k.list_model

    def create(body: create_model, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
        with conn.cursor() as cur:
            entity_pk = _create_entity(
                cur, user, k,
                name=getattr(body, k.name_col), type_code=getattr(body, f"{k.label}_type_code"),
                location=body.location_description, extra=getattr(body, k.extra_col), notes=body.notes,
                acquired_at=body.acquired_at, custodian_pk=body.custodian_organization_pk,
                custodian_from=body.custodian_effective_from, belongs_to_pk=body.belongs_to_organization_pk,
                acquisition_method_code=body.acquisition_method_code,
            )
            return _fetch_entity(cur, k, entity_pk)

    create.__doc__ = (
        f"Register a {k.label} (its {k.id_col} is minted by the server; status REGISTERED, or "
        f"{k.entered_status} when a custodian is given). ASSET_MANAGE + admin scope on the named custodian."
    )

    def list_(
        q: str | None = Query(None, description=f"Matches {k.label} name, id or location"),
        type_code: str | None = Query(None, description=f"{k.type_category} value_code"),
        status_filter: str | None = Query(None, alias="status"),
        custodian_organization_pk: UUID | None = Query(None),
        include_sub_organizations: bool = Query(
            False,
            description="With custodian_organization_pk: match that organization AND every organization beneath it "
                        "(still limited to the caller's admin scope). Ignored without a custodian filter.",
        ),
        belongs_to_organization_pk: UUID | None = Query(
            None,
            description="Only records attributed ('belongs to') to this organization. Informational: still limited "
                        "to records whose EFFECTIVE custodian is within the caller's admin scope.",
        ),
        acquisition_method_code: str | None = Query(None, description="ACQUISITION_METHOD value_code"),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        user: UserContext = Depends(_VIEW),
        conn=Depends(get_connection),
    ):
        with conn.cursor() as cur:
            return _list_entities(
                cur, user, k, q=q, type_code=type_code, status_filter=status_filter,
                custodian_pk=custodian_organization_pk, include_sub_organizations=include_sub_organizations,
                belongs_to_pk=belongs_to_organization_pk, acquisition_method_code=acquisition_method_code,
                page=page, page_size=page_size,
            )

    list_.__doc__ = f"Search/list {k.label} records whose EFFECTIVE custodian (active, or last for a {k.terminal_status} record) is within the caller's admin scope (NSS-wide admins also see custodian-less records). include_sub_organizations widens a custodian filter to the organization's whole subtree (still scope-limited)."

    def detail(entity_pk: UUID, user: UserContext = Depends(_VIEW), conn=Depends(get_connection)):
        with conn.cursor() as cur:
            _entity_head(cur, user, k, entity_pk, "view")
            return _fetch_entity(cur, k, entity_pk)

    def update(entity_pk: UUID, body: update_model, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
        with conn.cursor() as cur:
            _update_entity(cur, user, k, entity_pk, body.model_dump(exclude_unset=True))
            return _fetch_entity(cur, k, entity_pk)

    update.__doc__ = f"Edit descriptive fields only; {k.id_col} and status are immutable here (status moves via /transition)."

    def transition(entity_pk: UUID, body: TransitionRequest, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
        with conn.cursor() as cur:
            _transition_entity(cur, user, k, entity_pk, body.status, body.remarks)
            return _fetch_entity(cur, k, entity_pk)

    transition.__doc__ = (
        f"Record a {k.label} lifecycle event per SOL-AP-003. {k.terminal_status} is terminal; the Governance "
        "approval is outside this module (AP-045) — put its reference in remarks. Moving to "
        f"{k.terminal_status} also ENDs the active custodianship (end reason {k.terminal_status}) in the same "
        "transaction; the last custodian stays on the record (custodian_is_last)."
    )

    def archive(entity_pk: UUID, user: UserContext = Depends(_MANAGE), conn=Depends(get_write_connection)):
        with conn.cursor() as cur:
            _archive_entity(cur, user, k, entity_pk)
        return MessageResponse(message=f"{k.label.capitalize()} archived.")

    archive.__doc__ = f"Soft-delete (archive) a {k.label} that is REGISTERED (registered in error) or {k.terminal_status}; history is retained."

    router.add_api_route(prefix, create, methods=["POST"], response_model=response_model,
                         status_code=status.HTTP_201_CREATED, name=f"create_{k.label}")
    router.add_api_route(prefix, list_, methods=["GET"], response_model=list_model, name=f"list_{k.label}s")
    router.add_api_route(prefix + "/{entity_pk}", detail, methods=["GET"], response_model=response_model, name=f"get_{k.label}")
    router.add_api_route(prefix + "/{entity_pk}", update, methods=["PATCH"], response_model=response_model, name=f"update_{k.label}")
    router.add_api_route(prefix + "/{entity_pk}/transition", transition, methods=["POST"],
                         response_model=response_model, name=f"transition_{k.label}")
    router.add_api_route(prefix + "/{entity_pk}", archive, methods=["DELETE"],
                         response_model=MessageResponse, name=f"archive_{k.label}")


_register_entity_routes(_PROPERTY, PropertyCreate, PropertyUpdate)
_register_entity_routes(_ASSET, AssetCreate, AssetUpdate)


# ═══════════════════════════════════════════════════════════════════════
# Custodianship (property or asset)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/{kind}/{entity_pk}/custodianships", response_model=CustodianshipListResponse)
def list_custodianships(
    kind: EntityKind,
    entity_pk: UUID,
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
) -> CustodianshipListResponse:
    """Full custody history, newest first (AP-018/072). The ACTIVE row is the current custodian."""
    k = _KINDS[kind]
    with conn.cursor() as cur:
        _entity_head(cur, user, k, entity_pk, "view")
        cur.execute(
            _CUSTODIANSHIP_SELECT
            + f" WHERE c.{k.pk_col} = %s AND c.is_active = TRUE ORDER BY c.effective_from DESC, c.created_at DESC",
            (str(entity_pk),),
        )
        items = [_custodianship_response(r) for r in cur.fetchall()]
    return CustodianshipListResponse(items=items, total=len(items))


@router.post("/{kind}/{entity_pk}/custodianships", response_model=CustodianshipResponse,
             status_code=status.HTTP_201_CREATED)
def assign_custodian(
    kind: EntityKind,
    entity_pk: UUID,
    body: CustodianshipAssign,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> CustodianshipResponse:
    """
    Assign the FIRST custodian of a record that has none (a record with no
    custodian is the global authority's to manage, so only an NSS-wide admin
    can reach this; scope-bounded admins name the custodian at registration).
    409 when an ACTIVE custodian already exists — use /transfer. Advances a
    REGISTERED record to ACTIVE / IN_CUSTODY.
    """
    k = _KINDS[kind]
    with conn.cursor() as cur:
        current_status, custodian = _entity_head(cur, user, k, entity_pk, "assign a custodian to", lock=True)
        _require_not_terminal(k, current_status)
        if custodian is not None:
            raise HTTPException(
                status_code=409,
                detail=f"This {k.label} already has an active custodian (AP-017); use the transfer endpoint to change it.",
            )
        _require_custodian_org(cur, body.custodian_organization_pk, "Custodian")
        require_org_in_scope(cur, user, body.custodian_organization_pk, f"assign this {k.label} to this organization")
        cust_pk = _open_custodianship(
            cur, user, k, entity_pk, current_status, body.custodian_organization_pk, body.effective_from, body.notes,
        )
        _audit(cur, user, "CREATE", "custodianship", cust_pk, f"Assigned custodian to {k.label}",
               {k.pk_col: str(entity_pk), "custodian_organization_pk": str(body.custodian_organization_pk)})
        return _fetch_custodianship(cur, cust_pk)


@router.post("/{kind}/{entity_pk}/custodianships/transfer", response_model=CustodianshipTransferResponse,
             status_code=status.HTTP_201_CREATED)
def transfer_custodian(
    kind: EntityKind,
    entity_pk: UUID,
    body: CustodianshipTransfer,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> CustodianshipTransferResponse:
    """
    Transfer custody (AP-018/041/042): the current custodianship becomes ENDED
    (effective_to = transfer date, end reason recorded) and a new one is opened;
    both rows are kept. The lifecycle status does not change. Needs admin scope
    over BOTH the releasing and the receiving organization.
    """
    k = _KINDS[kind]
    with conn.cursor() as cur:
        current_status, custodian = _entity_head(cur, user, k, entity_pk, "transfer custody of", lock=True)
        _require_not_terminal(k, current_status)
        if custodian is None:
            raise HTTPException(
                status_code=409,
                detail=f"This {k.label} has no active custodian to transfer from; use the assign endpoint.",
            )
        if str(custodian) == str(body.new_custodian_organization_pk):
            raise HTTPException(status_code=422, detail="That organization is already the current custodian.")
        _require_custodian_org(cur, body.new_custodian_organization_pk, "New custodian")
        require_org_in_scope(cur, user, body.new_custodian_organization_pk,
                             f"transfer this {k.label} to this organization")
        if body.end_reason_code in _LIFECYCLE_END_REASONS:
            raise HTTPException(
                status_code=422,
                detail=f"End reason {body.end_reason_code} is reserved for recording a disposal / retirement "
                       f"(use the lifecycle transition); a custody transfer needs a transfer-type reason.",
            )
        end_reason_pk = get_master_data_pk(cur, "CUSTODIANSHIP_END_REASON", body.end_reason_code, client_supplied=True)

        cur.execute(
            f"""
            SELECT custodianship_pk, effective_from FROM nss.custodianship
            WHERE {k.pk_col} = %s AND status = 'ACTIVE' AND is_active = TRUE FOR UPDATE
            """,
            (str(entity_pk),),
        )
        old_pk, old_from = cur.fetchone()
        effective = body.effective_from or date.today()
        if effective < old_from:
            raise HTTPException(
                status_code=422,
                detail=f"effective_from must not be before the current custodianship began ({old_from.isoformat()}).",
            )

        _update_row(cur, user, "custodianship", "custodianship_pk", old_pk, {
            "status": "ENDED", "effective_to": effective, "end_reason_master_data_pk": end_reason_pk,
        })
        new_pk = _open_custodianship(
            cur, user, k, entity_pk, current_status, body.new_custodian_organization_pk, effective, body.notes,
        )
        if "location_description" in body.model_fields_set:
            _update_row(cur, user, k.table, k.pk_col, entity_pk,
                        {"location_description": _clean_text(body.location_description)})
        _audit(cur, user, "TRANSFER", "custodianship", new_pk, f"Transferred custody of {k.label}",
               {k.pk_col: str(entity_pk), "from_custodianship_pk": str(old_pk),
                "from_organization_pk": str(custodian),
                "to_organization_pk": str(body.new_custodian_organization_pk),
                "end_reason": body.end_reason_code})
        return CustodianshipTransferResponse(
            previous=_fetch_custodianship(cur, old_pk), current=_fetch_custodianship(cur, new_pk),
        )


# ═══════════════════════════════════════════════════════════════════════
# Maintenance records (property or asset)
# ═══════════════════════════════════════════════════════════════════════

_MAINTENANCE_SELECT = """
    SELECT m.maintenance_record_pk, m.property_pk, m.asset_pk, mt.value_code, mt.value_name,
           m.description, m.performed_at, m.notes, m.created_at
    FROM nss.maintenance_record m
    JOIN nss.master_data mt ON mt.master_data_pk = m.maintenance_type_master_data_pk
"""


def _maintenance_response(r) -> MaintenanceResponse:
    return MaintenanceResponse(
        maintenance_record_pk=r[0], property_pk=r[1], asset_pk=r[2],
        maintenance_type_code=r[3], maintenance_type_name=r[4],
        description=r[5], performed_at=r[6], notes=r[7], created_at=r[8],
    )


@router.get("/{kind}/{entity_pk}/maintenance-records", response_model=MaintenanceListResponse)
def list_maintenance_records(
    kind: EntityKind,
    entity_pk: UUID,
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
) -> MaintenanceListResponse:
    k = _KINDS[kind]
    with conn.cursor() as cur:
        _entity_head(cur, user, k, entity_pk, "view")
        cur.execute(
            _MAINTENANCE_SELECT
            + f" WHERE m.{k.pk_col} = %s AND m.is_active = TRUE ORDER BY m.performed_at DESC NULLS LAST, m.created_at DESC",
            (str(entity_pk),),
        )
        items = [_maintenance_response(r) for r in cur.fetchall()]
    return MaintenanceListResponse(items=items, total=len(items))


@router.post("/{kind}/{entity_pk}/maintenance-records", response_model=MaintenanceResponse,
             status_code=status.HTTP_201_CREATED)
def create_maintenance_record(
    kind: EntityKind,
    entity_pk: UUID,
    body: MaintenanceCreate,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> MaintenanceResponse:
    """Record maintenance that WAS performed (AP-029). Does not change the lifecycle status or create any Finance record (AP-031)."""
    k = _KINDS[kind]
    with conn.cursor() as cur:
        _entity_head(cur, user, k, entity_pk, "record maintenance for", lock=True)
        type_pk = get_master_data_pk(cur, "MAINTENANCE_TYPE", body.maintenance_type_code, client_supplied=True)
        cur.execute(
            f"""
            INSERT INTO nss.maintenance_record
                ({k.pk_col}, maintenance_type_master_data_pk, description, performed_at, notes, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING maintenance_record_pk
            """,
            (str(entity_pk), type_pk, _clean_text(body.description), body.performed_at,
             _clean_text(body.notes), user.actor_pk),
        )
        record_pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "maintenance_record", record_pk,
               f"Recorded {body.maintenance_type_code} maintenance on {k.label}", {k.pk_col: str(entity_pk)})
        cur.execute(_MAINTENANCE_SELECT + " WHERE m.maintenance_record_pk = %s", (str(record_pk),))
        return _maintenance_response(cur.fetchone())


def _maintenance_target(cur, user: UserContext, record_pk, verb: str) -> _Kind:
    """Authorize through the record's parent property/asset (404 if the record or parent is gone)."""
    cur.execute(
        "SELECT property_pk, asset_pk FROM nss.maintenance_record WHERE maintenance_record_pk = %s AND is_active = TRUE",
        (str(record_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found.")
    k, parent_pk = (_PROPERTY, row[0]) if row[0] is not None else (_ASSET, row[1])
    _entity_head(cur, user, k, parent_pk, verb, lock=True)
    return k


@router.patch("/maintenance-records/{record_pk}", response_model=MaintenanceResponse)
def update_maintenance_record(
    record_pk: UUID,
    body: MaintenanceUpdate,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> MaintenanceResponse:
    """Correct a maintenance record. The property/asset it belongs to cannot change."""
    fields = body.model_dump(exclude_unset=True)
    with conn.cursor() as cur:
        _maintenance_target(cur, user, record_pk, "edit a maintenance record of")
        if not fields:
            raise HTTPException(status_code=422, detail="No fields to update.")
        values: dict[str, Any] = {}
        for col, value in fields.items():
            if col == "maintenance_type_code":
                if value is None:
                    raise HTTPException(status_code=422, detail="maintenance_type_code cannot be cleared.")
                values["maintenance_type_master_data_pk"] = get_master_data_pk(
                    cur, "MAINTENANCE_TYPE", value, client_supplied=True)
            else:
                values[col] = _clean_text(value)
        _update_row(cur, user, "maintenance_record", "maintenance_record_pk", record_pk, values)
        _audit(cur, user, "UPDATE", "maintenance_record", record_pk,
               f"Updated maintenance record fields: {', '.join(sorted(fields))}", {"fields": sorted(fields)})
        cur.execute(_MAINTENANCE_SELECT + " WHERE m.maintenance_record_pk = %s", (str(record_pk),))
        return _maintenance_response(cur.fetchone())


@router.delete("/maintenance-records/{record_pk}", response_model=MessageResponse)
def delete_maintenance_record(
    record_pk: UUID,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """Soft-delete (retract an entry made in error). The row is retained for the audit trail."""
    with conn.cursor() as cur:
        _maintenance_target(cur, user, record_pk, "delete a maintenance record of")
        _soft_delete(cur, user, "maintenance_record", "maintenance_record_pk", record_pk)
        _audit(cur, user, "DELETE", "maintenance_record", record_pk, "Soft-deleted maintenance record")
    return MessageResponse(message="Maintenance record deleted.")


# ═══════════════════════════════════════════════════════════════════════
# Statutory records (PROPERTY ONLY — AP-040: deliberately no asset route)
# ═══════════════════════════════════════════════════════════════════════

_STATUTORY_SELECT = """
    SELECT r.property_statutory_record_pk, r.property_pk, ot.value_code, ot.value_name,
           r.description, r.reference_number, r.notes, r.created_at
    FROM nss.property_statutory_record r
    JOIN nss.master_data ot ON ot.master_data_pk = r.obligation_type_master_data_pk
"""


def _statutory_response(r) -> StatutoryRecordResponse:
    return StatutoryRecordResponse(
        property_statutory_record_pk=r[0], property_pk=r[1], obligation_type_code=r[2],
        obligation_type_name=r[3], description=r[4], reference_number=r[5], notes=r[6], created_at=r[7],
    )


@router.get("/properties/{entity_pk}/statutory-records", response_model=StatutoryRecordListResponse)
def list_statutory_records(
    entity_pk: UUID,
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
) -> StatutoryRecordListResponse:
    with conn.cursor() as cur:
        _entity_head(cur, user, _PROPERTY, entity_pk, "view")
        cur.execute(
            _STATUTORY_SELECT + " WHERE r.property_pk = %s AND r.is_active = TRUE ORDER BY r.created_at DESC",
            (str(entity_pk),),
        )
        items = [_statutory_response(r) for r in cur.fetchall()]
    return StatutoryRecordListResponse(items=items, total=len(items))


@router.post("/properties/{entity_pk}/statutory-records", response_model=StatutoryRecordResponse,
             status_code=status.HTTP_201_CREATED)
def create_statutory_record(
    entity_pk: UUID,
    body: StatutoryRecordCreate,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> StatutoryRecordResponse:
    """Identify a statutory obligation of the property (AP-034). Payment is Finance's (AP-039): no amount/date fields."""
    with conn.cursor() as cur:
        _entity_head(cur, user, _PROPERTY, entity_pk, "record a statutory obligation for", lock=True)
        type_pk = get_master_data_pk(cur, "STATUTORY_OBLIGATION_TYPE", body.obligation_type_code, client_supplied=True)
        cur.execute(
            """
            INSERT INTO nss.property_statutory_record
                (property_pk, obligation_type_master_data_pk, description, reference_number, notes,
                 created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING property_statutory_record_pk
            """,
            (str(entity_pk), type_pk, _clean_text(body.description), _clean_text(body.reference_number),
             _clean_text(body.notes), user.actor_pk),
        )
        record_pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", "property_statutory_record", record_pk,
               f"Recorded {body.obligation_type_code} obligation", {"property_pk": str(entity_pk)})
        cur.execute(_STATUTORY_SELECT + " WHERE r.property_statutory_record_pk = %s", (str(record_pk),))
        return _statutory_response(cur.fetchone())


def _statutory_property(cur, user: UserContext, record_pk, verb: str) -> None:
    cur.execute(
        "SELECT property_pk FROM nss.property_statutory_record WHERE property_statutory_record_pk = %s AND is_active = TRUE",
        (str(record_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Statutory record not found.")
    _entity_head(cur, user, _PROPERTY, row[0], verb, lock=True)


@router.patch("/statutory-records/{record_pk}", response_model=StatutoryRecordResponse)
def update_statutory_record(
    record_pk: UUID,
    body: StatutoryRecordUpdate,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> StatutoryRecordResponse:
    fields = body.model_dump(exclude_unset=True)
    with conn.cursor() as cur:
        _statutory_property(cur, user, record_pk, "edit a statutory record of")
        if not fields:
            raise HTTPException(status_code=422, detail="No fields to update.")
        values: dict[str, Any] = {}
        for col, value in fields.items():
            if col == "obligation_type_code":
                if value is None:
                    raise HTTPException(status_code=422, detail="obligation_type_code cannot be cleared.")
                values["obligation_type_master_data_pk"] = get_master_data_pk(
                    cur, "STATUTORY_OBLIGATION_TYPE", value, client_supplied=True)
            else:
                values[col] = _clean_text(value)
        _update_row(cur, user, "property_statutory_record", "property_statutory_record_pk", record_pk, values)
        _audit(cur, user, "UPDATE", "property_statutory_record", record_pk,
               f"Updated statutory record fields: {', '.join(sorted(fields))}", {"fields": sorted(fields)})
        cur.execute(_STATUTORY_SELECT + " WHERE r.property_statutory_record_pk = %s", (str(record_pk),))
        return _statutory_response(cur.fetchone())


@router.delete("/statutory-records/{record_pk}", response_model=MessageResponse)
def delete_statutory_record(
    record_pk: UUID,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """Soft-delete; the row is retained (obligation history is never physically removed)."""
    with conn.cursor() as cur:
        _statutory_property(cur, user, record_pk, "delete a statutory record of")
        _soft_delete(cur, user, "property_statutory_record", "property_statutory_record_pk", record_pk)
        _audit(cur, user, "DELETE", "property_statutory_record", record_pk, "Soft-deleted statutory record")
    return MessageResponse(message="Statutory record deleted.")


# ═══════════════════════════════════════════════════════════════════════
# Document links (Foundation document_master — AP-067..069)
# ═══════════════════════════════════════════════════════════════════════

def _document_select(k: _Kind) -> str:
    return f"""
        SELECT l.{k.doc_pk_col}, {"l.property_pk, NULL::uuid" if k.label == "property" else "NULL::uuid, l.asset_pk"},
               d.document_master_pk, d.document_type_code, d.document_name, d.document_number,
               rt.value_code, rt.value_name, l.notes, l.created_at
        FROM nss.{k.doc_table} l
        JOIN nss.document_master d ON d.document_master_pk = l.document_master_pk
        LEFT JOIN nss.master_data rt ON rt.master_data_pk = l.relationship_type_master_data_pk
    """


def _document_response(r) -> DocumentLinkResponse:
    return DocumentLinkResponse(
        link_pk=r[0], property_pk=r[1], asset_pk=r[2], document_master_pk=r[3],
        document_type_code=r[4], document_name=r[5], document_number=r[6],
        relationship_type_code=r[7], relationship_type_name=r[8], notes=r[9], created_at=r[10],
    )


@router.get("/{kind}/{entity_pk}/documents", response_model=DocumentLinkListResponse)
def list_document_links(
    kind: EntityKind,
    entity_pk: UUID,
    user: UserContext = Depends(_VIEW),
    conn=Depends(get_connection),
) -> DocumentLinkListResponse:
    k = _KINDS[kind]
    with conn.cursor() as cur:
        _entity_head(cur, user, k, entity_pk, "view")
        cur.execute(
            _document_select(k) + f" WHERE l.{k.pk_col} = %s AND l.is_active = TRUE AND d.is_active = TRUE ORDER BY l.created_at DESC",
            (str(entity_pk),),
        )
        items = [_document_response(r) for r in cur.fetchall()]
    return DocumentLinkListResponse(items=items, total=len(items))


@router.post("/{kind}/{entity_pk}/documents", response_model=DocumentLinkResponse,
             status_code=status.HTTP_201_CREATED)
def attach_document(
    kind: EntityKind,
    entity_pk: UUID,
    body: DocumentLinkCreate,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> DocumentLinkResponse:
    """Link an existing Foundation document_master row (no local document table, AP-068). One live link per document."""
    k = _KINDS[kind]
    with conn.cursor() as cur:
        _entity_head(cur, user, k, entity_pk, "attach a document to", lock=True)
        cur.execute(
            "SELECT 1 FROM nss.document_master WHERE document_master_pk = %s AND is_active = TRUE",
            (str(body.document_master_pk),),
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=422, detail="Document not found in the document registry.")
        relationship_pk = None
        if body.relationship_type_code:
            relationship_pk = get_master_data_pk(
                cur, "ASSET_PROPERTY_DOCUMENT_RELATIONSHIP", body.relationship_type_code, client_supplied=True)
        cur.execute(
            f"SELECT 1 FROM nss.{k.doc_table} WHERE {k.pk_col} = %s AND document_master_pk = %s AND is_active = TRUE",
            (str(entity_pk), str(body.document_master_pk)),
        )
        if cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail=f"That document is already attached to this {k.label}.")
        cur.execute(
            f"""
            INSERT INTO nss.{k.doc_table}
                ({k.pk_col}, document_master_pk, relationship_type_master_data_pk, notes, created_by_sangha_sevi_pk)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING {k.doc_pk_col}
            """,
            (str(entity_pk), str(body.document_master_pk), relationship_pk, _clean_text(body.notes), user.actor_pk),
        )
        link_pk = cur.fetchone()[0]
        _audit(cur, user, "CREATE", k.doc_table, link_pk, f"Attached document to {k.label}",
               {k.pk_col: str(entity_pk), "document_master_pk": str(body.document_master_pk)})
        cur.execute(_document_select(k) + f" WHERE l.{k.doc_pk_col} = %s", (str(link_pk),))
        return _document_response(cur.fetchone())


@router.delete("/{kind}/{entity_pk}/documents/{link_pk}", response_model=MessageResponse)
def detach_document(
    kind: EntityKind,
    entity_pk: UUID,
    link_pk: UUID,
    user: UserContext = Depends(_MANAGE),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """Detach (soft-delete the link). The document_master row itself is untouched."""
    k = _KINDS[kind]
    with conn.cursor() as cur:
        _entity_head(cur, user, k, entity_pk, "detach a document from", lock=True)
        cur.execute(
            f"SELECT 1 FROM nss.{k.doc_table} WHERE {k.doc_pk_col} = %s AND {k.pk_col} = %s AND is_active = TRUE",
            (str(link_pk), str(entity_pk)),
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Document link not found.")
        _soft_delete(cur, user, k.doc_table, k.doc_pk_col, link_pk)
        _audit(cur, user, "DELETE", k.doc_table, link_pk, f"Detached document from {k.label}",
               {k.pk_col: str(entity_pk)})
    return MessageResponse(message="Document detached.")
