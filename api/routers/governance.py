"""
NSS ERP — Governance router (Tier 6).

Unified Body Governance Model (GOV-BR-004, SOL-GOV-002/004). Endpoints:

  Catalogs (frozen-shape, caller-supplied business codes — no next_id()):
    GET    /api/v1/governance/body-types
    POST   /api/v1/governance/body-types
    PATCH  /api/v1/governance/body-types/{pk}
    DELETE /api/v1/governance/body-types/{pk}
    GET    /api/v1/governance/positions
    POST   /api/v1/governance/positions
    PATCH  /api/v1/governance/positions/{pk}
    DELETE /api/v1/governance/positions/{pk}

  Bodies:
    GET    /api/v1/governance/bodies
    GET    /api/v1/governance/bodies/sakha-scope-options
    GET    /api/v1/governance/bodies/{pk}
    POST   /api/v1/governance/bodies
    PATCH  /api/v1/governance/bodies/{pk}
    DELETE /api/v1/governance/bodies/{pk}

  Member / acting assignments:
    GET    /api/v1/governance/bodies/{body_pk}/assignments
    POST   /api/v1/governance/bodies/{body_pk}/assignments
    POST   /api/v1/governance/assignments/{pk}/end
    POST   /api/v1/governance/assignments/{pk}/resign
    GET    /api/v1/governance/bodies/{body_pk}/acting-assignments
    POST   /api/v1/governance/bodies/{body_pk}/acting-assignments
    POST   /api/v1/governance/acting-assignments/{pk}/end
    GET    /api/v1/governance/advisory-board/missing-nominations

  Elections / nominations / votes / results:
    GET    /api/v1/governance/me/parichalak-status
    GET    /api/v1/governance/elections
    GET    /api/v1/governance/elections/{pk}
    POST   /api/v1/governance/elections
    PATCH  /api/v1/governance/elections/{pk}/status
    GET    /api/v1/governance/elections/{election_pk}/nominations
    POST   /api/v1/governance/elections/{election_pk}/nominations
    PATCH  /api/v1/governance/nominations/{pk}/status
    POST   /api/v1/governance/elections/{election_pk}/votes
    GET    /api/v1/governance/elections/{election_pk}/tally
    GET    /api/v1/governance/elections/{election_pk}/results
    POST   /api/v1/governance/elections/{election_pk}/results
    POST   /api/v1/governance/results/{pk}/apply

Authority: SOL-GOV-002, SOL-GOV-004, GOV-BR-003 through GOV-BR-087,
           DDL_CREATION_ORDER (SOL-ARCH-010), Tier 6 design (2026-10-06/07).

RBAC: GOVERNANCE_VIEW (read) / GOVERNANCE_MANAGE (write) — seeded 2026-10-06
in database/seed/00_bootstrap/01_permission_master.sql /
03_role_permission.sql. GOVERNANCE_MANAGE mirrors ORGANIZATION_MANAGE's
footprint (ADMIN + KENDRA_ADMIN only); GOVERNANCE_VIEW mirrors
ORGANIZATION_VIEW's broader footprint (all org-scoped admins + AUDITOR).

Scope (ADMIN-BR-076/077, GOV-BR-058/059): a body/election with
organization_pk IS NULL is NSS-wide/Kendra-level and may only be managed by
the global authority (is_super_admin() or is_nss_wide()); an org-scoped
body/election is managed through the normal require_org_in_scope() subtree
check. Visibility (GOVERNANCE_VIEW) is broader: an org-scoped admin sees
every NSS-wide record plus records anchored inside their own subtree.

Vote secrecy — OPEN ITEM (GOV-BR-045 / SOL-GOV-004 §12.6): election_vote
stores voter_person_pk, so a ballot is attributable, not secret. Pending
that resolution, vote casting here is modelled as an election-officer-
recorded action gated behind GOVERNANCE_MANAGE, not member self-service —
see POST /elections/{election_pk}/votes.

election_result -> body_member_assignment hand-off is a deliberate,
separate step (SOL-GOV-004 §13.5): declaring a result never auto-writes an
assignment; POST /results/{pk}/apply does that explicitly.
"""

from datetime import date, datetime
from uuid import UUID

import psycopg2.errors
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_current_user, get_write_connection
from api.dependencies.rbac import require_any_permission, require_permission
from api.helpers import (
    build_order_by,
    log_audit,
    natural_sort_key,
    parse_optional_date,
    require_entity,
)
from api.schemas.governance import (
    ActingAssignmentListResponse,
    ActingAssignmentResponse,
    ApplyResultRequest,
    ApplyResultResponse,
    AssignmentListResponse,
    AssignmentResponse,
    BodyListResponse,
    BodyResponse,
    BodyTypeResponse,
    CastVoteRequest,
    CreateActingAssignmentRequest,
    CreateAssignmentRequest,
    CreateBodyRequest,
    CreateBodyTypeRequest,
    CreateElectionRequest,
    CreateNominationRequest,
    CreatePositionRequest,
    DeclareResultRequest,
    DecideAssignmentRemovalRequest,
    ElectionListResponse,
    ElectionResponse,
    EndActingAssignmentRequest,
    EndAssignmentRequest,
    NominationListResponse,
    NominationResponse,
    ParichalakStatusResponse,
    PositionResponse,
    RequestAssignmentRemovalRequest,
    ResignAssignmentRequest,
    ResetBallotsRequest,
    ResetBallotsResponse,
    ResultListResponse,
    ResultResponse,
    SelfCastVoteRequest,
    TallyResponse,
    TallyRow,
    OpenElectionListResponse,
    OpenElectionRow,
    VotableNominationRow,
    UpdateBodyRequest,
    UpdateBodyTypeRequest,
    UpdateElectionStatusRequest,
    UpdateNominationStatusRequest,
    UpdatePositionRequest,
    VoteResponse,
)
from api.schemas.auth import MessageResponse
from api.services.rbac_service import (
    UserContext,
    actor_scope_org_pks,
    require_org_in_scope,
)

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


# ── Scope helper (GOV-BR-058/059) ───────────────────────────────────────

def _require_scope_for_org_or_nss_wide(
    cur, user: UserContext, organization_pk, action: str
) -> None:
    """
    Scope guard for a governance record that may be NSS-wide
    (organization_pk IS NULL) or org-scoped (GOV-BR-058/059).

    The global authority (NSS_ERP_ADMIN / NSS-WIDE scope) may act on both.
    An org-scoped admin may act only on an organization_pk within their own
    scope subtree, and may NEVER create/manage an NSS-wide record — that is
    reserved to the global authority, same as it would be for the Kendra
    itself.
    """
    if organization_pk is None:
        if not (user.is_super_admin() or user.is_nss_wide()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Only an NSS-wide admin may {action} for an NSS-wide "
                    "(no organization) governance record."
                ),
            )
        return
    require_org_in_scope(cur, user, organization_pk, action)


def _visible_org_filter(cur, user: UserContext, column: str, params: list) -> str:
    """
    WHERE fragment for GOVERNANCE_VIEW list endpoints: the global authority
    sees everything (no filter); an org-scoped admin sees NSS-wide records
    (column IS NULL) plus records anchored inside their own scope subtree.
    Appends to *params* and returns the SQL fragment, or "TRUE" when no
    filter is needed.
    """
    allowed = actor_scope_org_pks(cur, user)
    if allowed is None:
        return "TRUE"
    if not allowed:
        return f"{column} IS NULL"
    placeholders = ",".join(["%s"] * len(allowed))
    params.extend(allowed)
    return f"({column} IS NULL OR {column} IN ({placeholders}))"


def _person_name_sql(alias: str) -> str:
    return f"TRIM(CONCAT_WS(' ', {alias}.first_name, {alias}.middle_name, {alias}.last_name))"


# ═════════════════════════════════════════════════════════════════════
# Body Type Master (catalog)
# ═════════════════════════════════════════════════════════════════════

@router.get("/body-types", response_model=list[BodyTypeResponse])
def list_body_types(
    include_inactive: bool = Query(False),
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> list[BodyTypeResponse]:
    """List governance body types (catalog). Requires GOVERNANCE_VIEW/MANAGE."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT body_type_master_pk, body_type_code, body_type_name,
                   description, is_active
            FROM nss.body_type_master
            WHERE {"TRUE" if include_inactive else "is_active = TRUE"}
            ORDER BY body_type_name
            """
        )
        rows = cur.fetchall()
    return [
        BodyTypeResponse(
            body_type_master_pk=r[0], body_type_code=r[1], body_type_name=r[2],
            description=r[3], is_active=r[4],
        )
        for r in rows
    ]


@router.post("/body-types", response_model=BodyTypeResponse, status_code=201)
def create_body_type(
    body: CreateBodyTypeRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> BodyTypeResponse:
    """
    Create a governance body type (GOV-BR-006). body_type_code is a
    caller-supplied, human-meaningful business code (e.g.
    KENDRA_GOVERNING_BODY) — uniqueness is enforced by uq_body_type_master_code,
    guarded here with SAVEPOINT so a collision returns a clean 409.
    """
    with conn.cursor() as cur:
        _require_scope_for_org_or_nss_wide(cur, user, None, "create a governance body type")
        actor = user.actor_pk
        cur.execute("SAVEPOINT body_type_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.body_type_master (body_type_code, body_type_name, description)
                VALUES (%s, %s, %s)
                RETURNING body_type_master_pk
                """,
                (body.body_type_code.strip().upper(), body.body_type_name.strip(), body.description),
            )
            pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT body_type_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Body type code '{body.body_type_code}' already exists.",
            )
        cur.execute("RELEASE SAVEPOINT body_type_insert")
        log_audit(cur, action="CREATE", table_name="body_type_master", record_pk=str(pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary=f"Created body type {body.body_type_code}")
    return BodyTypeResponse(
        body_type_master_pk=pk, body_type_code=body.body_type_code.strip().upper(),
        body_type_name=body.body_type_name.strip(), description=body.description, is_active=True,
    )


@router.patch("/body-types/{body_type_master_pk}", response_model=BodyTypeResponse)
def update_body_type(
    body_type_master_pk: UUID,
    body: UpdateBodyTypeRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> BodyTypeResponse:
    """Edit a body type's name/description. body_type_code is immutable (identity)."""
    with conn.cursor() as cur:
        require_entity(cur, "body_type_master", str(body_type_master_pk), label="Body type")
        sets, params = [], []
        if body.body_type_name is not None:
            sets.append("body_type_name = %s")
            params.append(body.body_type_name.strip())
        if body.description is not None:
            sets.append("description = %s")
            params.append(body.description)
        if sets:
            sets.append("updated_at = NOW()")
            params.append(str(body_type_master_pk))
            cur.execute(
                f"UPDATE nss.body_type_master SET {', '.join(sets)} WHERE body_type_master_pk = %s",
                params,
            )
            log_audit(cur, action="UPDATE", table_name="body_type_master",
                      record_pk=str(body_type_master_pk), actor_pk=user.actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="governance", summary="Updated body type")
        cur.execute(
            """
            SELECT body_type_master_pk, body_type_code, body_type_name, description, is_active
            FROM nss.body_type_master WHERE body_type_master_pk = %s
            """,
            (str(body_type_master_pk),),
        )
        r = cur.fetchone()
    return BodyTypeResponse(
        body_type_master_pk=r[0], body_type_code=r[1], body_type_name=r[2],
        description=r[3], is_active=r[4],
    )


@router.delete("/body-types/{body_type_master_pk}", response_model=MessageResponse)
def deactivate_body_type(
    body_type_master_pk: UUID,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """Soft-delete a body type (GOV-BR-063 — historically-used types are never physically removed)."""
    with conn.cursor() as cur:
        _require_scope_for_org_or_nss_wide(cur, user, None, "deactivate a governance body type")
        require_entity(cur, "body_type_master", str(body_type_master_pk), label="Body type")
        cur.execute(
            """
            UPDATE nss.body_type_master
            SET is_active = FALSE, deleted_at = NOW(), updated_at = NOW()
            WHERE body_type_master_pk = %s
            """,
            (str(body_type_master_pk),),
        )
        log_audit(cur, action="DEACTIVATE", table_name="body_type_master",
                  record_pk=str(body_type_master_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Deactivated body type")
    return MessageResponse(message="Body type deactivated.")


# ═════════════════════════════════════════════════════════════════════
# Position Master (catalog)
# ═════════════════════════════════════════════════════════════════════

@router.get("/positions", response_model=list[PositionResponse])
def list_positions(
    include_inactive: bool = Query(False),
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> list[PositionResponse]:
    """List governance positions (catalog), ordered for display (GOV-BR-012)."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT position_master_pk, position_code, position_name,
                   description, display_order, is_active
            FROM nss.position_master
            WHERE {"TRUE" if include_inactive else "is_active = TRUE"}
            ORDER BY display_order, position_name
            """
        )
        rows = cur.fetchall()
    return [
        PositionResponse(
            position_master_pk=r[0], position_code=r[1], position_name=r[2],
            description=r[3], display_order=r[4], is_active=r[5],
        )
        for r in rows
    ]


@router.post("/positions", response_model=PositionResponse, status_code=201)
def create_position(
    body: CreatePositionRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> PositionResponse:
    """Create a governance position (GOV-BR-013/014). Not an RBAC role — no role_master FK."""
    with conn.cursor() as cur:
        _require_scope_for_org_or_nss_wide(cur, user, None, "create a governance position")
        actor = user.actor_pk
        cur.execute("SAVEPOINT position_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.position_master (position_code, position_name, description, display_order)
                VALUES (%s, %s, %s, %s)
                RETURNING position_master_pk
                """,
                (body.position_code.strip().upper(), body.position_name.strip(),
                 body.description, body.display_order),
            )
            pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT position_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Position code '{body.position_code}' already exists.",
            )
        cur.execute("RELEASE SAVEPOINT position_insert")
        log_audit(cur, action="CREATE", table_name="position_master", record_pk=str(pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary=f"Created position {body.position_code}")
    return PositionResponse(
        position_master_pk=pk, position_code=body.position_code.strip().upper(),
        position_name=body.position_name.strip(), description=body.description,
        display_order=body.display_order, is_active=True,
    )


@router.patch("/positions/{position_master_pk}", response_model=PositionResponse)
def update_position(
    position_master_pk: UUID,
    body: UpdatePositionRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> PositionResponse:
    """Edit a position's name/description/display_order. position_code is immutable."""
    with conn.cursor() as cur:
        require_entity(cur, "position_master", str(position_master_pk), label="Position")
        sets, params = [], []
        if body.position_name is not None:
            sets.append("position_name = %s")
            params.append(body.position_name.strip())
        if body.description is not None:
            sets.append("description = %s")
            params.append(body.description)
        if body.display_order is not None:
            sets.append("display_order = %s")
            params.append(body.display_order)
        if sets:
            sets.append("updated_at = NOW()")
            params.append(str(position_master_pk))
            cur.execute(
                f"UPDATE nss.position_master SET {', '.join(sets)} WHERE position_master_pk = %s",
                params,
            )
            log_audit(cur, action="UPDATE", table_name="position_master",
                      record_pk=str(position_master_pk), actor_pk=user.actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="governance", summary="Updated position")
        cur.execute(
            """
            SELECT position_master_pk, position_code, position_name, description,
                   display_order, is_active
            FROM nss.position_master WHERE position_master_pk = %s
            """,
            (str(position_master_pk),),
        )
        r = cur.fetchone()
    return PositionResponse(
        position_master_pk=r[0], position_code=r[1], position_name=r[2],
        description=r[3], display_order=r[4], is_active=r[5],
    )


@router.delete("/positions/{position_master_pk}", response_model=MessageResponse)
def deactivate_position(
    position_master_pk: UUID,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """Soft-delete a position (never physically removed, GOV-BR-063 parity)."""
    with conn.cursor() as cur:
        _require_scope_for_org_or_nss_wide(cur, user, None, "deactivate a governance position")
        require_entity(cur, "position_master", str(position_master_pk), label="Position")
        cur.execute(
            """
            UPDATE nss.position_master
            SET is_active = FALSE, deleted_at = NOW(), updated_at = NOW()
            WHERE position_master_pk = %s
            """,
            (str(position_master_pk),),
        )
        log_audit(cur, action="DEACTIVATE", table_name="position_master",
                  record_pk=str(position_master_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Deactivated position")
    return MessageResponse(message="Position deactivated.")


# ═════════════════════════════════════════════════════════════════════
# Body Master
# ═════════════════════════════════════════════════════════════════════

_BODY_SORT_COLUMNS: dict[str, str | list[str]] = {
    "body_code": natural_sort_key("bm.body_code"),
    "body_name": "bm.body_name",
    "body_type_name": "bt.body_type_name",
    "organization_name": "o.organization_name",
    "body_status": "bm.body_status",
    "effective_from": "bm.effective_from",
    "created_at": "bm.created_at",
}

_BODY_SELECT_SQL = """
    SELECT bm.body_master_pk, bm.body_type_master_pk, bt.body_type_name,
           bm.body_code, bm.body_name, bm.description,
           bm.organization_pk, o.organization_name,
           bm.body_status, bm.effective_from, bm.effective_to, bm.is_active,
           bt.body_type_code
    FROM nss.body_master bm
    JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
    LEFT JOIN nss.organization o ON o.organization_pk = bm.organization_pk
"""


def _row_to_body(r) -> BodyResponse:
    return BodyResponse(
        body_master_pk=r[0], body_type_master_pk=r[1], body_type_name=r[2],
        body_code=r[3], body_name=r[4], description=r[5],
        organization_pk=r[6], organization_name=r[7], body_status=r[8],
        effective_from=r[9], effective_to=r[10], is_active=r[11],
        body_type_code=r[12],
    )


@router.get("/bodies/sakha-scope-options")
def get_body_sakha_scope_options(
    body_type_master_pk: UUID = Query(
        ..., description="Sakha-anchored body type (e.g. Sakha Governing Body, "
                          "Mahila Parichalana Mandali, Sevak Sangha Executive)."
    ),
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_connection),
):
    """
    Parent-Sakha selection data for a Sakha-anchored governance body's
    org-picker. Mirrors admin.py's get_kumari_sevak_sakha_options
    (ORG-BR-101/102) auto-select/lock shape, but scoped by the actor's
    admin-scope subtree (ADMIN-BR-076/077) rather than org-creation rules,
    and dedups against Sakhas that already have an active body of this
    type rather than an organization of a given type.

    Registered before GET /bodies/{body_master_pk} so the literal
    "sakha-scope-options" segment isn't swallowed by that path param.

      - NSS-wide admin: every active Sakha, mode "choose" (no auto-select).
      - Admin scoped to exactly one Sakha: that Sakha only, mode "locked".
      - Admin scoped to more than one Sakha: if exactly one of their
        Sakhas lacks an active body of this type, mode "locked" with that
        Sakha auto-selected; otherwise mode "choose" over their own
        scoped Sakhas.
    """
    with conn.cursor() as cur:
        require_entity(cur, "body_type_master", str(body_type_master_pk), label="Body type")

        allowed = actor_scope_org_pks(cur, user)
        if allowed is None:
            cur.execute(
                """
                SELECT o.organization_pk, o.organization_name, o.organization_code
                FROM nss.organization o
                JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
                WHERE md.value_code = 'SAKHA_SANGHA' AND o.is_active = TRUE
                ORDER BY o.organization_name
                """
            )
            sakhas = [
                {"organization_pk": str(r[0]), "organization_name": r[1], "organization_code": r[2]}
                for r in cur.fetchall()
            ]
            return {"mode": "choose", "auto_select_pk": None, "sakhas": sakhas}

        scoped_sakha_pks = sorted(allowed) if allowed else []
        if not scoped_sakha_pks:
            return {"mode": "choose", "auto_select_pk": None, "sakhas": []}

        cur.execute(
            """
            SELECT o.organization_pk, o.organization_name, o.organization_code
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE o.organization_pk = ANY(%s::uuid[])
              AND md.value_code = 'SAKHA_SANGHA'
              AND o.is_active = TRUE
            ORDER BY o.organization_name
            """,
            (scoped_sakha_pks,),
        )
        sakhas = [
            {"organization_pk": str(r[0]), "organization_name": r[1], "organization_code": r[2]}
            for r in cur.fetchall()
        ]
        sakha_pks = [s["organization_pk"] for s in sakhas]

        if len(sakha_pks) == 1:
            return {"mode": "locked", "auto_select_pk": sakha_pks[0], "sakhas": sakhas}
        if not sakha_pks:
            return {"mode": "choose", "auto_select_pk": None, "sakhas": sakhas}

        cur.execute(
            """
            SELECT organization_pk FROM nss.body_master
            WHERE organization_pk = ANY(%s::uuid[])
              AND body_type_master_pk = %s
              AND is_active = TRUE
            """,
            (sakha_pks, str(body_type_master_pk)),
        )
        already_has = {str(r[0]) for r in cur.fetchall()}
        lacking = [pk for pk in sakha_pks if pk not in already_has]

        if len(lacking) == 1:
            return {"mode": "locked", "auto_select_pk": lacking[0], "sakhas": sakhas}

        return {"mode": "choose", "auto_select_pk": None, "sakhas": sakhas}


@router.get("/bodies", response_model=BodyListResponse)
def list_bodies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    body_status: str | None = Query(None),
    organization_pk: UUID | None = Query(None),
    include_inactive: bool = Query(False),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> BodyListResponse:
    """
    List governance bodies, paginated/sortable/searchable.

    Scope-aware (GOV-BR-058/059): NSS-wide/global admins see everything; an
    org-scoped admin sees every NSS-wide body plus bodies anchored inside
    their own scope subtree.
    """
    offset = (page - 1) * page_size
    order_by = build_order_by(sort_by, sort_dir, _BODY_SORT_COLUMNS, "bm.body_code")

    conditions = ["TRUE"] if include_inactive else ["bm.is_active = TRUE"]
    params: list = []

    if body_status:
        conditions.append("bm.body_status = %s")
        params.append(body_status)
    if organization_pk:
        conditions.append("bm.organization_pk = %s")
        params.append(str(organization_pk))
    if search:
        conditions.append("(bm.body_code ILIKE %s OR bm.body_name ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])

    with conn.cursor() as cur:
        conditions.append(_visible_org_filter(cur, user, "bm.organization_pk", params))
        where_clause = " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) FROM nss.body_master bm WHERE {where_clause}", params)
        total = cur.fetchone()[0]

        cur.execute(
            f"{_BODY_SELECT_SQL} WHERE {where_clause} ORDER BY {order_by} LIMIT %s OFFSET %s",
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    return BodyListResponse(
        items=[_row_to_body(r) for r in rows], total=total, page=page, page_size=page_size,
    )


@router.get("/bodies/{body_master_pk}", response_model=BodyResponse)
def get_body(
    body_master_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> BodyResponse:
    """Get one governance body's detail."""
    with conn.cursor() as cur:
        cur.execute(f"{_BODY_SELECT_SQL} WHERE bm.body_master_pk = %s", (str(body_master_pk),))
        r = cur.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Governance body not found.")
        if r[6] is not None:
            require_org_in_scope(cur, user, r[6], "view") if False else None
            # Visibility, not management: an NSS-wide/global admin always
            # passes; an org-scoped admin must have this org in their subtree.
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None and str(r[6]) not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This governance body is outside your admin scope.",
                )
    return _row_to_body(r)


@router.post("/bodies", response_model=BodyResponse, status_code=201)
def create_body(
    body: CreateBodyRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> BodyResponse:
    """
    Create a governance body (GOV-BR-007/008). body_code is a caller-supplied
    business code; organization_pk NULL = NSS-wide/Kendra-level (GOV-BR-058).
    """
    with conn.cursor() as cur:
        require_entity(cur, "body_type_master", str(body.body_type_master_pk), label="Body type")
        if body.organization_pk:
            require_entity(cur, "organization", str(body.organization_pk), label="Organization")
        _require_scope_for_org_or_nss_wide(cur, user, body.organization_pk, "create governance bodies")

        effective_from = parse_optional_date(body.effective_from, "Effective From")
        effective_to = parse_optional_date(body.effective_to, "Effective To")
        if effective_to and effective_from and effective_to < effective_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Effective To cannot be before Effective From.",
            )

        actor = user.actor_pk
        cur.execute("SAVEPOINT body_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.body_master (
                    body_type_master_pk, body_code, body_name, description,
                    organization_pk, effective_from, effective_to
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING body_master_pk
                """,
                (str(body.body_type_master_pk), body.body_code.strip().upper(),
                 body.body_name.strip(), body.description,
                 str(body.organization_pk) if body.organization_pk else None,
                 effective_from, effective_to),
            )
            pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT body_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Body code '{body.body_code}' already exists.",
            )
        cur.execute("RELEASE SAVEPOINT body_insert")
        log_audit(cur, action="CREATE", table_name="body_master", record_pk=str(pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary=f"Created governance body {body.body_code}")

        cur.execute(f"{_BODY_SELECT_SQL} WHERE bm.body_master_pk = %s", (str(pk),))
        r = cur.fetchone()
    return _row_to_body(r)


@router.patch("/bodies/{body_master_pk}", response_model=BodyResponse)
def update_body(
    body_master_pk: UUID,
    body: UpdateBodyRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> BodyResponse:
    """Edit a body's name/description/status/term. body_code and body_type are immutable here."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT organization_pk FROM nss.body_master WHERE body_master_pk = %s",
            (str(body_master_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Governance body not found.")
        _require_scope_for_org_or_nss_wide(cur, user, row[0], "update governance bodies")

        sets, params = [], []
        if body.body_name is not None:
            sets.append("body_name = %s")
            params.append(body.body_name.strip())
        if body.description is not None:
            sets.append("description = %s")
            params.append(body.description)
        if body.body_status is not None:
            sets.append("body_status = %s")
            params.append(body.body_status)
        if body.effective_from is not None:
            sets.append("effective_from = %s")
            params.append(parse_optional_date(body.effective_from, "Effective From"))
        if body.effective_to is not None:
            sets.append("effective_to = %s")
            params.append(parse_optional_date(body.effective_to, "Effective To"))
        if sets:
            sets.append("updated_at = NOW()")
            params.append(str(body_master_pk))
            cur.execute(
                f"UPDATE nss.body_master SET {', '.join(sets)} WHERE body_master_pk = %s", params,
            )
            log_audit(cur, action="UPDATE", table_name="body_master",
                      record_pk=str(body_master_pk), actor_pk=user.actor_pk,
                      actor_user_account_pk=str(user.user_account_pk),
                      module="governance", summary="Updated governance body")
        cur.execute(f"{_BODY_SELECT_SQL} WHERE bm.body_master_pk = %s", (str(body_master_pk),))
        r = cur.fetchone()
    return _row_to_body(r)


@router.delete("/bodies/{body_master_pk}", response_model=MessageResponse)
def deactivate_body(
    body_master_pk: UUID,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> MessageResponse:
    """Soft-delete a governance body (history preserved, GOV-BR-063/068)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT organization_pk FROM nss.body_master WHERE body_master_pk = %s",
            (str(body_master_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Governance body not found.")
        _require_scope_for_org_or_nss_wide(cur, user, row[0], "deactivate governance bodies")
        cur.execute(
            """
            UPDATE nss.body_master
            SET is_active = FALSE, deleted_at = NOW(), updated_at = NOW()
            WHERE body_master_pk = %s
            """,
            (str(body_master_pk),),
        )
        log_audit(cur, action="DEACTIVATE", table_name="body_master",
                  record_pk=str(body_master_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Deactivated governance body")
    return MessageResponse(message="Governance body deactivated.")


# ═════════════════════════════════════════════════════════════════════
# Public read endpoints (any logged-in user — no GOVERNANCE_VIEW)
# ═════════════════════════════════════════════════════════════════════
#
# These two endpoints are deliberately gated on get_current_user alone
# (a valid login) and NOT on GOVERNANCE_VIEW, so plain members — who do
# not hold GOVERNANCE_VIEW — can see the read-only governance panels on
# their dashboard. They expose a strictly narrower, fixed-shape slice than
# the admin endpoints above (never the full body list, no management
# fields), which is why widening GOVERNANCE_VIEW was rejected in favour of
# dedicated endpoints (owner-confirmed 2026-10-07).


def _mobile_display(country_phone_code, mobile_number) -> str | None:
    """'+91 9812345678' from the two person columns, or None when absent."""
    if not mobile_number:
        return None
    code = (country_phone_code or "").strip()
    num = mobile_number.strip()
    return f"{code} {num}".strip() if code else num


@router.get("/public/national-bodies")
def public_national_bodies(
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> dict:
    """
    Read-only governance panel for ANY logged-in user (dashboard Governance
    tab). Returns up to 4 bodies with their current composition:

      - the NSS-wide singleton bodies (body_master.organization_pk IS NULL):
        Kendra Governing Body, Advisory Board, central Mahila Parichalana
        Mandali; and
      - the viewer's OWN Sakha Governing Body, resolved from their active
        sangha_sevi.organization_pk.

    No scope filtering beyond that — these are the bodies every member is
    entitled to see. No management/term-edit fields are exposed.
    """
    with conn.cursor() as cur:
        # Viewer's base Sakha (if they are a Sangha Sevi at all).
        own_sakha_pk = None
        if user.person_pk is not None:
            cur.execute(
                """
                SELECT organization_pk
                FROM nss.sangha_sevi
                WHERE person_pk = %s AND is_active = TRUE
                """,
                (str(user.person_pk),),
            )
            r = cur.fetchone()
            if r is not None:
                own_sakha_pk = r[0]

        # The 4 bodies: all active NSS-wide singletons + the viewer's own
        # active Sakha Governing Body.
        cur.execute(
            f"""
            {_BODY_SELECT_SQL}
            WHERE bm.is_active = TRUE
              AND (
                    bm.organization_pk IS NULL
                 OR (bm.organization_pk = %s
                     AND bt.body_type_code = 'SAKHA_GOVERNING_BODY')
                  )
            ORDER BY (bm.organization_pk IS NOT NULL), bm.body_name
            """,
            (own_sakha_pk,),
        )
        body_rows = cur.fetchall()

        body_pks = [str(r[0]) for r in body_rows]
        members_by_body: dict[str, list] = {pk: [] for pk in body_pks}
        if body_pks:
            # Each member's home Sakha (via sangha_sevi.organization_pk) plus
            # that Sakha's Anchalika/Zilla parent — resolved by walking UP the
            # organization tree. No existing helper does this (every CTE
            # elsewhere in the codebase, e.g. actor_scope_org_pks, walks DOWN
            # from a root to its descendants) — this is a new upward walk,
            # mirrored on the same parent_organization_pk recursion/index
            # (idx_organization_parent_active) those downward CTEs already use.
            # Needed because bodies like the Advisory Board draw one
            # representative per Sakha — without the Sakha (and its
            # Anchalika/Zilla), the composition table can't tell them apart.
            cur.execute(
                f"""
                WITH RECURSIVE assignment_rows AS (
                    SELECT a.body_master_pk, pm.position_name, pm.display_order,
                           {_person_name_sql('p')} AS person_name, ss.sangha_sevi_id,
                           a.effective_from, a.effective_to,
                           ss.organization_pk AS sakha_org_pk
                    FROM nss.body_member_assignment a
                    JOIN nss.position_master pm
                      ON pm.position_master_pk = a.position_master_pk
                    JOIN nss.person p ON p.person_pk = a.person_pk
                    LEFT JOIN nss.sangha_sevi ss
                      ON ss.sangha_sevi_pk = a.sangha_sevi_pk
                    WHERE a.body_master_pk::text = ANY(%s)
                      AND a.is_active = TRUE
                      AND a.assignment_status IN ('ASSIGNED', 'ACTIVE')
                ),
                ancestors AS (
                    SELECT o.organization_pk AS start_pk, o.organization_pk,
                           o.parent_organization_pk, o.organization_name,
                           md.value_code AS organization_type_code
                    FROM nss.organization o
                    JOIN nss.master_data md
                      ON md.master_data_pk = o.organization_type_master_data_pk
                    WHERE o.organization_pk IN (
                        SELECT DISTINCT sakha_org_pk FROM assignment_rows
                        WHERE sakha_org_pk IS NOT NULL
                    )
                    UNION ALL
                    SELECT anc.start_pk, o.organization_pk,
                           o.parent_organization_pk, o.organization_name,
                           md.value_code
                    FROM nss.organization o
                    JOIN nss.master_data md
                      ON md.master_data_pk = o.organization_type_master_data_pk
                    JOIN ancestors anc ON anc.parent_organization_pk = o.organization_pk
                )
                SELECT ar.body_master_pk, ar.position_name, ar.display_order,
                       ar.person_name, ar.sangha_sevi_id,
                       ar.effective_from, ar.effective_to,
                       sakha.organization_name AS sakha_name,
                       az.organization_name AS anchalika_zilla_name
                FROM assignment_rows ar
                LEFT JOIN nss.organization sakha ON sakha.organization_pk = ar.sakha_org_pk
                LEFT JOIN ancestors az
                       ON az.start_pk = ar.sakha_org_pk
                      AND az.organization_type_code IN ('ANCHALIKA_SANGHA', 'ZILLA_SANGHA')
                ORDER BY ar.display_order, ar.position_name
                """,
                (body_pks,),
            )
            for m in cur.fetchall():
                members_by_body[str(m[0])].append({
                    "position_name": m[1],
                    "person_name": m[3].strip() if m[3] and m[3].strip() else None,
                    "sangha_sevi_id": m[4],
                    "effective_from": m[5],
                    "effective_to": m[6],
                    "sakha_name": m[7],
                    "anchalika_zilla_name": m[8],
                })

    bodies = []
    for r in body_rows:
        pk = str(r[0])
        members = members_by_body.get(pk, [])
        bodies.append({
            "body_master_pk": r[0],
            "body_type_name": r[2],
            "body_code": r[3],
            "body_name": r[4],
            "description": r[5],
            "organization_pk": r[6],
            "organization_name": r[7],
            "scope_label": "NSS-wide" if r[6] is None else "Your Sakha",
            "body_status": r[8],
            "effective_from": r[9],
            "effective_to": r[10],
            "member_count": len(members),
            "members": members,
        })
    return {"bodies": bodies}


@router.get("/public/sakha-office-bearers")
def public_sakha_office_bearers(
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> dict:
    """
    Per-Sakha President & Secretary (with mobile) for the "Find a Sakha"
    directory, for ANY logged-in user. One bulk query, keyed by the Sakha's
    organization_pk, so the directory merges it client-side with no N+1.

    Draws current office-bearers from each Sakha Governing Body
    (body_type_code = 'SAKHA_GOVERNING_BODY', org-scoped) via the active
    PRESIDENT / SECRETARY assignments.
    """
    office_bearers: dict[str, dict] = {}
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT bm.organization_pk, pm.position_code,
                   {_person_name_sql('p')},
                   p.country_phone_code, p.mobile_number
            FROM nss.body_master bm
            JOIN nss.body_type_master bt
              ON bt.body_type_master_pk = bm.body_type_master_pk
            JOIN nss.body_member_assignment a
              ON a.body_master_pk = bm.body_master_pk
             AND a.is_active = TRUE
             AND a.assignment_status IN ('ASSIGNED', 'ACTIVE')
            JOIN nss.position_master pm
              ON pm.position_master_pk = a.position_master_pk
            JOIN nss.person p ON p.person_pk = a.person_pk
            WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY'
              AND bm.is_active = TRUE
              AND bm.organization_pk IS NOT NULL
              AND pm.position_code IN ('PRESIDENT', 'SECRETARY')
            """
        )
        for org_pk, position_code, name, phone_code, mobile in cur.fetchall():
            key = str(org_pk)
            entry = office_bearers.setdefault(key, {"president": None, "secretary": None})
            role = "president" if position_code == "PRESIDENT" else "secretary"
            entry[role] = {
                "name": name.strip() if name and name.strip() else None,
                "mobile": _mobile_display(phone_code, mobile),
            }
    return {"office_bearers": office_bearers}


# ═════════════════════════════════════════════════════════════════════
# Body Member Assignment
# ═════════════════════════════════════════════════════════════════════

_ASSIGNMENT_SELECT_SQL = f"""
    SELECT a.body_member_assignment_pk, a.body_master_pk, a.position_master_pk,
           pm.position_name, a.person_pk, {_person_name_sql('p')}, a.sangha_sevi_pk,
           a.effective_from, a.effective_to, a.assignment_status,
           a.assignment_reference, a.remarks, a.is_active, a.resignation_reason
    FROM nss.body_member_assignment a
    JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
    JOIN nss.person p ON p.person_pk = a.person_pk
"""


def _row_to_assignment(r) -> AssignmentResponse:
    return AssignmentResponse(
        body_member_assignment_pk=r[0], body_master_pk=r[1], position_master_pk=r[2],
        position_name=r[3], person_pk=r[4], person_name=r[5] if r[5] and r[5].strip() else None,
        sangha_sevi_pk=r[6], effective_from=r[7], effective_to=r[8],
        assignment_status=r[9], assignment_reference=r[10], remarks=r[11], is_active=r[12],
        resignation_reason=r[13],
    )


def _get_body_org_or_404(cur, body_master_pk: UUID):
    cur.execute(
        "SELECT organization_pk FROM nss.body_master WHERE body_master_pk = %s",
        (str(body_master_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Governance body not found.")
    return row[0]


def _require_body_in_scope(cur, user: UserContext, body_master_pk: UUID):
    """
    Load a governance body's organization_pk (404 if it does not exist) and
    enforce the read-scope gate before any of the body's sub-resources are
    returned. Mirrors _visible_org_filter's visibility rule: the global
    authority (actor_scope_org_pks -> None) sees every body; an org-scoped
    admin may read a body anchored inside its own scope subtree, plus every
    NSS-wide body (organization_pk IS NULL, visible to all). Returns the
    body's organization_pk.
    """
    org_pk = _get_body_org_or_404(cur, body_master_pk)
    allowed = actor_scope_org_pks(cur, user)
    if allowed is not None and org_pk is not None and str(org_pk) not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This governance body is outside your admin scope.",
        )
    return org_pk


# ── Body composition rules (GOV-BR-011/024/032/033/034/035) ─────────────────
# Which positions each body type may hold, and how many distinct people may
# sit on it. Enforced here (API layer), same pattern as other occupancy
# limits — position_master stays a flat reusable catalogue (GOV-BR-013).
_COMPOSITION_RULES: dict[str, dict] = {
    "KENDRA_GOVERNING_BODY": {
        "positions": ("PRESIDENT", "VICE_PRESIDENT", "PARICHALAK", "SECRETARY",
                      "ASSISTANT_SECRETARY", "TREASURER", "MUKHYA_PUJAKA", "MEMBER"),
        "seat_limit": 9,
    },
    # Advisory Board: one representative nominated by each Sakha Sangha's own
    # general body (Bye-Law; owner-confirmed 2026-10-08). Hence
    # seat_limit = SAKHA_COUNT and one_seat_per_sakha — a second nominee from an
    # already-represented Sakha is rejected. The nominating/withdrawing authority
    # is the represented Sakha, NOT a Kendra/NSS-wide admin — see
    # _require_nominating_sakha_scope.
    "ADVISORY_BOARD": {
        "positions": ("PRESIDENT", "SECRETARY", "MEMBER"),
        "seat_limit": "SAKHA_COUNT",
        "officers_from_members": True,
        "one_seat_per_sakha": True,
    },
    # Mahila Parichalana Mandali: Kendra (organization_pk NULL) vs Sakha level.
    # PARICHALAK is deliberately NOT assignable here (owner-confirmed 2026-10-08):
    # the Parichalak is already seated on the Kendra Governing Body (an NSS-wide
    # singleton — see _NSS_WIDE_SINGLETON_CODES) and this body simply inherits
    # that same person rather than taking a second, independent assignment row.
    # The Bye-law's "nine-member" count (President, Vice-President, Parichalak,
    # Secretary, Joint Secretary, Treasurer, 3 Members) therefore maps to 8
    # directly-assignable seats here + 1 inherited (non-row) Parichalak seat.
    "MAHILA_PARICHALANA_MANDALI": {
        "positions": ("PRESIDENT", "VICE_PRESIDENT", "SECRETARY",
                      "JOINT_SECRETARY", "TREASURER", "MEMBER"),
        "seat_limit": 8,
    },
    "MAHILA_PARICHALANA_MANDALI@SAKHA": {
        "positions": ("PRESIDENT", "SECRETARY", "CASHIER"),
        "seat_limit": 3,
    },
    "SAKHA_GOVERNING_BODY": {
        "positions": ("PRESIDENT", "SECRETARY", "CASHIER", "MEMBER"),
        "seat_limit": 9,
    },
    "SEVAK_SANGHA_EXECUTIVE": {
        "positions": ("PRESIDENT", "SECRETARY", "CASHIER"),
        "seat_limit": 3,
    },
    # Anchalika/Zilla/Patha Chakra Governing Bodies (§63 composite auto-grant
    # rule, owner-confirmed 2026-10-09): previously-unmodeled org-scoped
    # bodies, added so their President/Secretary can auto-grant
    # NSS_ERP_ANCHALIKA_ADMIN / NSS_ERP_ZILLA_ADMIN / NSS_ERP_PATHA_CHAKRA_ADMIN
    # (scoped to that organization). Modeled directly on
    # SEVAK_SANGHA_EXECUTIVE — org-scoped, admin-created via "Add Body", no
    # NSS-wide singleton counterpart.
    "ANCHALIKA_GOVERNING_BODY": {
        "positions": ("PRESIDENT", "SECRETARY", "CASHIER"),
        "seat_limit": 3,
    },
    "ZILLA_GOVERNING_BODY": {
        "positions": ("PRESIDENT", "SECRETARY", "CASHIER"),
        "seat_limit": 3,
    },
    "PATHA_CHAKRA_GOVERNING_BODY": {
        "positions": ("PRESIDENT", "SECRETARY", "CASHIER"),
        "seat_limit": 3,
    },
}

# Positions that only one person may hold across ALL of NSS at a time.
_NSS_WIDE_SINGLETON_CODES = ("MUKHYA_PUJAKA", "PARICHALAK")

# Body types whose seats are mutually exclusive — a person active on one
# cannot also be assigned to the other (owner-confirmed 2026-10-08: the
# Advisory Board advises the Kendra Governing Body, so its membership must
# stay distinct from the body it advises).
_MUTUALLY_EXCLUSIVE_BODY_TYPES = (("KENDRA_GOVERNING_BODY", "ADVISORY_BOARD"),)

_BODY_TYPE_DISPLAY_NAMES = {
    "KENDRA_GOVERNING_BODY": "Kendra Governing Body",
    "ADVISORY_BOARD": "Advisory Board",
}

# A seat is "currently held" while ASSIGNED/ACTIVE and also while PENDING_REMOVAL:
# a forced-removal request does NOT vacate the seat — the holder keeps serving
# until the body's own President approves it (owner-confirmed 2026-10-08, GOV-BR
# item #18). Only approval (-> ENDED) actually frees the seat. RESIGNED is
# deliberately NOT listed: a voluntary self-resignation vacates the seat
# immediately, exactly like ENDED (owner-confirmed 2026-10-15).
_CURRENT_ASSIGNMENT_SQL = "a.is_active = TRUE AND a.assignment_status IN ('ASSIGNED','ACTIVE','PENDING_REMOVAL')"


def _composition_rule(body_type_code: str, org_pk) -> dict | None:
    if body_type_code == "MAHILA_PARICHALANA_MANDALI" and org_pk is not None:
        return _COMPOSITION_RULES["MAHILA_PARICHALANA_MANDALI@SAKHA"]
    return _COMPOSITION_RULES.get(body_type_code)


def _resolve_seat_limit(cur, rule: dict | None) -> int | None:
    if rule is None:
        return None
    limit = rule["seat_limit"]
    if limit == "SAKHA_COUNT":
        cur.execute(
            """
            SELECT COUNT(*) FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE o.is_active = TRUE AND md.value_code = 'SAKHA_SANGHA'
            """
        )
        return cur.fetchone()[0]
    return limit


def _body_type_code(cur, body_master_pk) -> str:
    cur.execute(
        """
        SELECT bt.body_type_code FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bm.body_master_pk = %s
        """,
        (str(body_master_pk),),
    )
    row = cur.fetchone()
    return row[0] if row else ""


def _home_sakha(cur, person_pk):
    """
    The person's home Sakha Sangha as (organization_pk, organization_name), via
    their active Sangha Sevi record — the same anchor the member directory uses
    (sangha_sevi.organization_pk). Returns (None, None) when the person has no
    active Sakha Sangha membership (e.g. a Kendra-level member).
    """
    cur.execute(
        """
        SELECT o.organization_pk, o.organization_name
        FROM nss.sangha_sevi ss
        JOIN nss.organization o ON o.organization_pk = ss.organization_pk
        JOIN nss.master_data md
             ON md.master_data_pk = o.organization_type_master_data_pk
        WHERE ss.person_pk = %s AND ss.is_active = TRUE
          AND md.value_code = 'SAKHA_SANGHA'
        LIMIT 1
        """,
        (str(person_pk),),
    )
    row = cur.fetchone()
    return (row[0], row[1]) if row else (None, None)


# Body types whose seats are filled AND vacated by the represented Sakha
# Sangha's general body rather than by the body's own (NSS-wide) admin.
_SAKHA_NOMINATED_BODY_TYPES = ("ADVISORY_BOARD",)

# Within a Sakha-nominated body type, only ONE position is actually the
# Sakha-nominated seat — the Advisory Board's PRESIDENT/SECRETARY are real
# office-bearer positions elected from among the MEMBER seats (see
# _COMPOSITION_RULES["ADVISORY_BOARD"]["officers_from_members"]) and are
# managed by the body's own (NSS-wide) governance admin like any other
# office-bearer, never by a Sakha's own admin. Only MEMBER — the seat a
# Sakha's general body appoints and withdraws — goes through
# _require_nominating_sakha_scope. Owner spec, 2026-10-14.
_SAKHA_NOMINATED_POSITION_CODES: dict[str, str] = {
    "ADVISORY_BOARD": "MEMBER",
}


def _require_nominating_sakha_scope(
    cur, user, body_type_code, position_code, person_pk, action, *,
    breakglass_endpoint: str | None = None,
) -> bool:
    """
    Authority guard for a Sakha-nominated seat (owner-confirmed 2026-10-08):

      - A Sakha Sangha's general body appoints its own Advisory Board
        representative, and ONLY that Sakha may withdraw the nomination.
      - A Kendra / NSS-wide governance admin may therefore NOT create or end
        these assignments, even though the Advisory Board itself is an NSS-wide
        body (body_master.organization_pk IS NULL) and would otherwise be
        NSS-wide-admin-only under _require_scope_for_org_or_nss_wide.

    So authority is checked against the member's HOME SAKHA, not the body's own
    organization. Returns True when this guard applied (caller must then skip
    the normal org/NSS-wide scope check), False when the body type is not
    Sakha-nominated OR this position is not the Sakha-nominated seat (e.g.
    Advisory Board PRESIDENT/SECRETARY — those stay under the normal
    NSS-wide/org-scope guard, 2026-10-14).

    The platform super-admin (NSS_ERP_ADMIN) is still allowed through as
    technical break-glass when breakglass_endpoint is None (e.g. for creating
    a new nomination — not itself approval-gated). When breakglass_endpoint IS
    given (the removal path, GOV-BR item #18, owner-confirmed 2026-10-08), the
    super-admin is instead blocked here and pointed at that endpoint — a
    forced removal of this seat must go through PENDING_REMOVAL for the body's
    own sitting President to approve, never an instant direct end.

    Deliberately NOT implemented with require_org_in_scope(): that helper is
    subtree-aware and treats an NSS-WIDE scope as covering everything, so both
    a Kendra-anchored admin (every Sakha is its descendant) and any NSS-wide
    admin would pass — exactly the people this rule excludes. Authority here
    must be anchored AT the Sakha, so we match the actor's own scope
    organizations directly.
    """
    if body_type_code not in _SAKHA_NOMINATED_BODY_TYPES:
        return False
    if position_code != _SAKHA_NOMINATED_POSITION_CODES.get(body_type_code):
        return False
    sakha_pk, sakha_name = _home_sakha(cur, person_pk)
    if sakha_pk is None:
        if user.is_super_admin():
            # No represented Sakha to defer to (e.g. it was dissolved) — there
            # is no nominating authority left, and for the removal path no
            # President of that Sakha to redirect to either. Break-glass
            # proceeds directly rather than leaving the seat permanently
            # unendable.
            return True
        raise HTTPException(
            status_code=422,
            detail=(
                "This Advisory Board seat has no represented Sakha Sangha, so its "
                f"nominating authority cannot be verified. Cannot {action}."
            ),
        )
    own_scope_orgs = {str(s.organization_pk) for s in user.scopes if s.organization_pk}
    if str(sakha_pk) in own_scope_orgs:
        return True
    if user.is_super_admin():
        if breakglass_endpoint:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A forced removal of this Advisory Board representative must go "
                    f"through {breakglass_endpoint} so the body's own President can "
                    "approve it — a direct end is not permitted (GOV-BR item #18)."
                ),
            )
        return True
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Only {sakha_name}'s own admin may {action} — its general body "
            "appoints and withdraws its Advisory Board representative. A Kendra "
            "or NSS-wide admin cannot."
        ),
    )


def _active_office_bearer(cur, body_master_pk, person_pk, *, position_code=None) -> bool:
    """True if person_pk currently holds an active, open-ended office-bearer
    seat (any position but MEMBER, or the specific position_code given) on
    body_master_pk."""
    if person_pk is None:
        return False
    cur.execute(
        """
        SELECT 1
        FROM nss.body_member_assignment a
        JOIN nss.position_master p ON p.position_master_pk = a.position_master_pk
        WHERE a.body_master_pk = %s
          AND (p.position_code = %s OR (%s IS NULL AND p.position_code != 'MEMBER'))
          AND a.person_pk = %s
          AND a.is_active = TRUE
          AND a.effective_to IS NULL
          AND a.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')
        LIMIT 1
        """,
        (str(body_master_pk), position_code, position_code, str(person_pk)),
    )
    return cur.fetchone() is not None


def _has_sitting_president(cur, body_master_pk) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM nss.body_member_assignment a
        JOIN nss.position_master p ON p.position_master_pk = a.position_master_pk
        WHERE a.body_master_pk = %s
          AND p.position_code = 'PRESIDENT'
          AND a.is_active = TRUE
          AND a.effective_to IS NULL
          AND a.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')
        LIMIT 1
        """,
        (str(body_master_pk),),
    )
    return cur.fetchone() is not None


def _removal_approver_body(cur, body_master_pk, body_type_code, org_pk):
    """
    Resolve which body's own office bearers must sign off on a forced
    removal. Normally the SAME body (its own GB/President). Sevak Sangha
    Executive is the one carve-out (owner-confirmed 2026-10-15): it has no
    independent GB of its own for this purpose — removal/assignment
    authority belongs to the concerned Sakha's own Governing Body office
    bearers instead.
    """
    if body_type_code != "SEVAK_SANGHA_EXECUTIVE":
        return body_master_pk
    cur.execute(
        """
        SELECT bm.body_master_pk
        FROM nss.body_master bm
        JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
        WHERE bt.body_type_code = 'SAKHA_GOVERNING_BODY'
          AND bm.organization_pk = %s AND bm.is_active = TRUE
        LIMIT 1
        """,
        (str(org_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=422,
            detail="This Sevak Sangha's own Sakha has no Governing Body on record to decide this.",
        )
    return row[0]


def _require_body_president(cur, user, approver_body_master_pk, action) -> None:
    """
    Authority guard for GOV-BR item #18 (generalized 2026-10-15 beyond the
    original Advisory-Board-only version): only an active office bearer of
    the body that owns this decision may approve or reject a forced-removal
    request — normally its sitting President, who is recording that the
    body's own General Body meeting has already resolved the matter (the
    President does not personally judge it, and does not approve their own
    filed request purely on their own say-so — the GB meeting is the real
    approval, owner-confirmed). If the Presidency is currently vacant, any
    other currently active office bearer of the SAME body may act instead
    (owner-confirmed: "they will decide among themselves" who steps in) — no
    fixed Vice-President/Secretary priority is hardcoded.

    Note: a position is deliberately not an RBAC role (GOV-BR-014), so this
    narrows "any governance admin" down to "this specific body's own
    President (or stand-in office bearer)" — it does not grant permission by
    itself; the endpoint's require_permission(GOVERNANCE_MANAGE) still applies.
    """
    if _active_office_bearer(cur, approver_body_master_pk, user.person_pk, position_code="PRESIDENT"):
        return
    if not _has_sitting_president(cur, approver_body_master_pk) and _active_office_bearer(
        cur, approver_body_master_pk, user.person_pk
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Only this body's sitting President may {action} — or, while that seat is "
            "vacant, another of its own currently sitting office bearers."
        ),
    )


def _require_removal_initiator(cur, user, org_pk, initiator_body_master_pk, action) -> None:
    """
    Who may FILE a forced-removal request (generalized 2026-10-15 beyond the
    original Advisory-Board-only, super-admin break-glass version): either
    this body's own scoped admin (the usual GOVERNANCE_MANAGE org/NSS-wide
    scope), or one of this body's own currently active office bearers
    (Secretary/Treasurer/etc. — not a plain MEMBER seat). The safety valve is
    the President's approval step, backed by the body's own GB meeting
    resolution — not who is allowed to raise the request.
    """
    try:
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, action)
        return
    except HTTPException:
        pass
    if _active_office_bearer(cur, initiator_body_master_pk, user.person_pk):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Only this body's own admin or one of its own office bearers may {action}.",
    )


def _require_valid_composition(cur, body_master_pk, org_pk, position_master_pk, person_pk) -> None:
    """
    Reject an assignment that would break the body's composition rules:
      1. the position must be allowed for this body type;
      2. office-bearer positions (anything but MEMBER) hold one person per body
         (the SAME person may still hold multiple DIFFERENT positions on one body);
      3. Mukhya Pujaka / Parichalak are single NSS-wide seats (one person).
         Parichalak is also not independently assignable on the Mahila
         Parichalana Mandali — see MAHILA_PARICHALANA_MANDALI's composition
         rule, it is inherited from the Kendra Governing Body seat instead;
      4. a person cannot sit on both the Kendra Governing Body and the
         Advisory Board at the same time;
      5. Advisory Board President/Secretary must already be a Member of it;
      6. the Advisory Board seats at most ONE representative per Sakha Sangha,
         and the nominee must belong to a Sakha Sangha (it is that Sakha's
         general body that nominates them);
      7. the body may not exceed its seat limit (distinct people).
    Body types with no rule (caller-created via POST /body-types) are not restricted.
    """
    body_type_code = _body_type_code(cur, body_master_pk)
    rule = _composition_rule(body_type_code, org_pk)

    cur.execute(
        "SELECT position_code, position_name FROM nss.position_master WHERE position_master_pk = %s",
        (str(position_master_pk),),
    )
    position_code, position_name = cur.fetchone()

    if rule is not None and position_code not in rule["positions"]:
        raise HTTPException(
            status_code=422,
            detail=f"'{position_name}' is not a position on this type of governing body.",
        )

    if position_code != "MEMBER":
        cur.execute(
            f"""
            SELECT 1 FROM nss.body_member_assignment a
            WHERE a.body_master_pk = %s AND a.position_master_pk = %s
              AND a.person_pk <> %s AND {_CURRENT_ASSIGNMENT_SQL}
            LIMIT 1
            """,
            (str(body_master_pk), str(position_master_pk), str(person_pk)),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=409,
                detail=f"This body already has a {position_name}. End that assignment first.",
            )

    if position_code in _NSS_WIDE_SINGLETON_CODES:
        cur.execute(
            f"""
            SELECT 1 FROM nss.body_member_assignment a
            WHERE a.position_master_pk = %s AND a.person_pk <> %s AND {_CURRENT_ASSIGNMENT_SQL}
            LIMIT 1
            """,
            (str(position_master_pk), str(person_pk)),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=409,
                detail=f"{position_name} is a single NSS-wide post and is already held "
                       "by another person. End that assignment first.",
            )

    for type_a, type_b in _MUTUALLY_EXCLUSIVE_BODY_TYPES:
        if body_type_code not in (type_a, type_b):
            continue
        other_type = type_b if body_type_code == type_a else type_a
        cur.execute(
            f"""
            SELECT 1 FROM nss.body_member_assignment m
            JOIN nss.body_master bm ON bm.body_master_pk = m.body_master_pk
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE m.person_pk = %s AND bt.body_type_code = %s
              AND {_CURRENT_ASSIGNMENT_SQL.replace('a.', 'm.')}
            LIMIT 1
            """,
            (str(person_pk), other_type),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=409,
                detail="This member already holds a position on the "
                       f"{_BODY_TYPE_DISPLAY_NAMES.get(other_type, other_type)}. "
                       "A person cannot sit on both the Kendra Governing Body and "
                       "the Advisory Board at the same time.",
            )

    if rule is None:
        return

    if rule.get("officers_from_members") and position_code in ("PRESIDENT", "SECRETARY"):
        cur.execute(
            f"""
            SELECT 1 FROM nss.body_member_assignment a
            JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
            WHERE a.body_master_pk = %s AND a.person_pk = %s
              AND pm.position_code = 'MEMBER' AND {_CURRENT_ASSIGNMENT_SQL}
            LIMIT 1
            """,
            (str(body_master_pk), str(person_pk)),
        )
        if not cur.fetchone():
            raise HTTPException(
                status_code=422,
                detail=f"The Advisory Board {position_name} is chosen from among its "
                       "members. Assign this person as a Member first.",
            )

    if rule.get("one_seat_per_sakha"):
        sakha_pk, sakha_name = _home_sakha(cur, person_pk)
        if sakha_pk is None:
            raise HTTPException(
                status_code=422,
                detail="The Advisory Board seats one representative nominated by each "
                       "Sakha Sangha's general body, so the nominee must belong to a "
                       "Sakha Sangha. This person has no active Sakha Sangha membership.",
            )
        # Another PERSON from the same Sakha already holding a seat is a conflict.
        # The same person taking a second position (Member -> President) is fine.
        cur.execute(
            f"""
            SELECT {_person_name_sql('p')}
            FROM nss.body_member_assignment a
            JOIN nss.person p ON p.person_pk = a.person_pk
            JOIN nss.sangha_sevi ss
                 ON ss.person_pk = a.person_pk AND ss.is_active = TRUE
            WHERE a.body_master_pk = %s AND a.person_pk <> %s
              AND ss.organization_pk = %s AND {_CURRENT_ASSIGNMENT_SQL}
            LIMIT 1
            """,
            (str(body_master_pk), str(person_pk), str(sakha_pk)),
        )
        row = cur.fetchone()
        if row:
            holder = row[0].strip() if row[0] and row[0].strip() else "another member"
            raise HTTPException(
                status_code=409,
                detail=f"{sakha_name} is already represented on the Advisory Board by "
                       f"{holder}. A Sakha Sangha may have only one representative — "
                       f"{sakha_name}'s general body must withdraw that nomination first.",
            )

    seat_limit = _resolve_seat_limit(cur, rule)
    cur.execute(
        f"""
        SELECT COUNT(DISTINCT a.person_pk),
               BOOL_OR(a.person_pk = %s)
        FROM nss.body_member_assignment a
        WHERE a.body_master_pk = %s AND {_CURRENT_ASSIGNMENT_SQL}
        """,
        (str(person_pk), str(body_master_pk)),
    )
    seated, already_seated = cur.fetchone()
    if not already_seated and seat_limit is not None and seated >= seat_limit:
        raise HTTPException(
            status_code=422,
            detail=f"This body is full ({seated} of {seat_limit} seats). "
                   "End an existing assignment before adding someone new.",
        )


def _get_membership_type(cur, person_pk: UUID) -> str | None:
    """
    Return the active Sangha Sevi's membership_type value_code
    (PROBATIONARY / REGULAR / ASSOCIATE / HONORARY) for person_pk, or None
    if the person has no active Sangha Sevi record (i.e. is not an NSS
    member at all).
    """
    cur.execute(
        """
        SELECT mt.value_code
        FROM nss.sangha_sevi ss
        JOIN nss.master_data mt ON mt.master_data_pk = ss.membership_type_master_data_pk
        WHERE ss.person_pk = %s AND ss.is_active = TRUE
        """,
        (str(person_pk),),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _has_valid_anumati_patra(cur, person_pk: UUID) -> bool:
    """
    GOV-BR-043-A: does person_pk's active Sangha Sevi hold a currently
    valid (not just existing) Anumati Patra right now?

    "Valid" means status = 'ACTIVE' and not yet past its valid_to date —
    an expired-but-not-yet-transitioned row, or a CANCELLED/REPLACED one,
    does not count. Mirrors the credential-state CASE logic in
    admin.py's credential dashboard, but as a reusable boolean check
    (no equivalent existed before this rule).
    """
    cur.execute(
        """
        SELECT 1
        FROM nss.anumati_patra ap
        JOIN nss.sangha_sevi ss ON ss.sangha_sevi_pk = ap.sangha_sevi_pk
        WHERE ss.person_pk = %s AND ss.is_active = TRUE
          AND ap.status = 'ACTIVE' AND ap.valid_to >= CURRENT_DATE
        """,
        (str(person_pk),),
    )
    return cur.fetchone() is not None


def _resolve_current_parichalak_sangha_sevi_pk(cur) -> UUID | None:
    """
    GOV-BR-043-A: the Parichalak is a single NSS-wide seat
    (position_master.position_code = 'PARICHALAK', see
    database/seed/08_governance/02_position_master.sql). Return the
    sangha_sevi_pk of whoever currently, actively holds it — or None if
    the seat is vacant.
    """
    cur.execute(
        """
        SELECT a.sangha_sevi_pk
        FROM nss.body_member_assignment a
        JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
        WHERE pm.position_code = 'PARICHALAK'
          AND a.is_active = TRUE AND a.assignment_status = 'ACTIVE'
        LIMIT 1
        """,
    )
    row = cur.fetchone()
    return row[0] if row else None


def _member_org_in_election_subtree(cur, person_pk: UUID, election_org_pk) -> tuple[bool, str]:
    """
    Subtree-aware home-organization test (GOV-BR-094, future-proof
    2026-10-09).

    Returns (is_in_subtree, member_org_name) where is_in_subtree is True iff
    the person's ACTIVE home organization (sangha_sevi.organization_pk) is the
    election's organization OR a descendant of it.

    Membership is always held at the Sakha (leaf) level; a member belongs to
    the parent Anchalika / Zilla / Kendra THROUGH that Sakha. Flat equality
    (home-org == election-org) is therefore correct only for Sakha-level
    elections and would reject every candidate/voter for a higher body, where
    no member's home org equals the body directly. Walking the subtree rooted
    at the election's org makes the check correct at every tier.

    If the person has no active Sangha Sevi row, returns (False, ...).
    """
    cur.execute(
        """
        WITH RECURSIVE subtree(organization_pk) AS (
            SELECT %s::uuid
            UNION ALL
            SELECT o.organization_pk
            FROM nss.organization o
            JOIN subtree s ON o.parent_organization_pk = s.organization_pk
        )
        SELECT o.organization_name,
               EXISTS (
                   SELECT 1 FROM subtree st
                   WHERE st.organization_pk = ss.organization_pk
               )
        FROM nss.sangha_sevi ss
        LEFT JOIN nss.organization o ON o.organization_pk = ss.organization_pk
        WHERE ss.person_pk = %s AND ss.is_active = TRUE
        """,
        (str(election_org_pk), str(person_pk)),
    )
    row = cur.fetchone()
    if row is None:
        return False, "no organization"
    return bool(row[1]), (row[0] or "no organization")


def _require_voter_eligible(cur, person_pk: UUID, election_pk: UUID) -> None:
    """
    GOV-BR-043: a vote may only be cast by an active NSS member who is not
    an ASSOCIATE member (and, pending a source ruling, not HONORARY either
    — treated as non-electoral like ASSOCIATE). No active Sangha Sevi at
    all means the person is not an NSS member and cannot vote.

    GOV-BR-094 (future-proof, subtree-aware 2026-10-09): the voter must also
    belong to the election body's OWN organization or one of its branches —
    the electorate for a body's election is the membership of its subtree. A
    member of a sibling Sakha may not vote in another Sakha's election. For an
    NSS-wide body (election.organization_pk IS NULL) no organization
    restriction applies; eligibility there is governed by the body's own
    composition rules.
    """
    membership_type = _get_membership_type(cur, person_pk)
    if membership_type is None:
        raise HTTPException(
            status_code=422,
            detail="This person is not an active NSS member (no active Sangha "
                   "Sevi record) and cannot cast a vote.",
        )
    if membership_type in ("ASSOCIATE", "HONORARY"):
        raise HTTPException(
            status_code=422,
            detail=f"{membership_type.title()} members may not vote or elect "
                   "a representative, per the Bye-Law (GOV-BR-043).",
        )

    cur.execute(
        """
        SELECT e.organization_pk, o.organization_name
        FROM nss.election e
        LEFT JOIN nss.organization o ON o.organization_pk = e.organization_pk
        WHERE e.election_pk = %s
        """,
        (str(election_pk),),
    )
    row = cur.fetchone()
    if row is None or row[0] is None:
        return  # NSS-wide body — no electorate-organization restriction.
    election_org_pk, election_org_name = row

    in_subtree, member_org_name = _member_org_in_election_subtree(
        cur, person_pk, election_org_pk
    )
    if not in_subtree:
        raise HTTPException(
            status_code=422,
            detail=f"This member belongs to {member_org_name} and is not part "
                   f"of the electorate for {election_org_name or 'this organization'}. "
                   "Only members of that organization or one of its branches "
                   "may vote in its election.",
        )


_SAKHA_RESTRICTED_POSITION_CODES = ("PRESIDENT", "SECRETARY")


def _require_candidate_in_own_organization(cur, person_pk: UUID, election_pk: UUID) -> None:
    """
    A candidate for an organization-scoped body may only be a member of THAT
    organization or one of its branches. A member of a sibling Sakha may never
    stand for another Sakha's post (GOV-BR-094, owner-confirmed 2026-10-09;
    made subtree-aware/future-proof the same day).

    The election's organization_pk mirrors its body's own org (GOV-BR-059):
      * organization_pk IS NOT NULL → an org-scoped body (Sakha Governing
        Body, Sevak Sangha Executive, per-Sakha Mahila Parichalana Mandali,
        ...). The candidate's home org (sangha_sevi.organization_pk) must be
        the election's org OR a descendant of it. Because membership is held
        at the Sakha (leaf) and a member belongs to the parent Anchalika /
        Zilla / Kendra THROUGH that Sakha, a higher-body election must accept
        every member in its subtree, not only those whose home org equals the
        body directly. Flat equality (correct only for Sakha-level elections)
        is replaced by a subtree walk here.
      * organization_pk IS NULL → an NSS-wide body (Kendra Governing Body,
        Advisory Board, central Mahila Parichalana Mandali). No org
        restriction applies here; eligibility for those seats is governed by
        the body's own composition rules, not by home Sakha.

    This is enforced server-side deliberately: the admin UI also filters the
    candidate typeahead to the election's org subtree, but that is only a
    convenience. A hand-crafted request must not be able to slip a
    sibling-Sakha candidate past it.
    """
    cur.execute(
        """
        SELECT e.organization_pk, o.organization_name
        FROM nss.election e
        LEFT JOIN nss.organization o ON o.organization_pk = e.organization_pk
        WHERE e.election_pk = %s
        """,
        (str(election_pk),),
    )
    row = cur.fetchone()
    if row is None or row[0] is None:
        return  # NSS-wide body — no home-organization restriction.
    election_org_pk, election_org_name = row

    in_subtree, member_org_name = _member_org_in_election_subtree(
        cur, person_pk, election_org_pk
    )
    if not in_subtree:
        raise HTTPException(
            status_code=422,
            detail=f"This member belongs to {member_org_name} and cannot be "
                   f"nominated for a post of {election_org_name or 'this organization'}. "
                   "Only members of that organization or one of its branches "
                   "may stand for its posts.",
        )


def _require_candidate_eligible(
    cur, person_pk: UUID, election_pk: UUID, position_master_pk: UUID,
    probationary_exception_approver_sangha_sevi_pk: UUID | None = None,
    probationary_exception_reason: str | None = None,
) -> None:
    """
    GOV-BR-043: a candidate must be an active NSS member who is not an
    ASSOCIATE/HONORARY member (they may not stand for any elected post).
    A PROBATIONARY member additionally may not stand for Sakha
    President/Secretary unless a Parichalak-approved exception is recorded
    (GOV-BR-043-A — the exception the base Bye-Law rule names but used to
    leave as a manual/organizational act only).

    The Sakha/President/Secretary check matches on the stable
    body_type_code ('SAKHA_GOVERNING_BODY') and position_code
    ('PRESIDENT'/'SECRETARY') from the seeded catalogues
    (database/seed/08_governance/), resolved from the election's body and
    the position actually being nominated for (not a name-substring
    heuristic — both catalogues are owner-confirmed, stable codes as of
    2026-10-07).

    GOV-BR-094 is also enforced here, via
    _require_candidate_in_own_organization: for an organization-scoped body
    the candidate's home Sakha must match the election's organization, so a
    sibling Sakha's member can never stand.
    """
    membership_type = _get_membership_type(cur, person_pk)
    if membership_type is None:
        raise HTTPException(
            status_code=422,
            detail="This person is not an active NSS member (no active Sangha "
                   "Sevi record) and cannot be nominated.",
        )
    _require_candidate_in_own_organization(cur, person_pk, election_pk)
    if membership_type in ("ASSOCIATE", "HONORARY"):
        raise HTTPException(
            status_code=422,
            detail=f"{membership_type.title()} members may not stand for any "
                   "elected post, per the Bye-Law (GOV-BR-043).",
        )
    if membership_type == "PROBATIONARY":
        cur.execute(
            """
            SELECT bt.body_type_code, pm.position_code
            FROM nss.election e
            JOIN nss.body_master bm ON bm.body_master_pk = e.body_master_pk
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            JOIN nss.position_master pm ON pm.position_master_pk = %s
            WHERE e.election_pk = %s
            """,
            (str(position_master_pk), str(election_pk)),
        )
        row = cur.fetchone()
        is_restricted = row is not None and (
            row[0] == "SAKHA_GOVERNING_BODY" and row[1] in _SAKHA_RESTRICTED_POSITION_CODES
        )
        if is_restricted:
            if not (probationary_exception_approver_sangha_sevi_pk
                     and probationary_exception_reason):
                raise HTTPException(
                    status_code=422,
                    detail="A Probationary member may not stand as President or "
                           "Secretary of a Sakha Sangha, per the Bye-Law "
                           "(GOV-BR-043), unless the currently-seated "
                           "Parichalak personally records this nomination "
                           "with a probationary_exception_reason "
                           "(GOV-BR-043-A).",
                )
            current_parichalak = _resolve_current_parichalak_sangha_sevi_pk(cur)
            if (current_parichalak is None
                    or str(current_parichalak) != str(probationary_exception_approver_sangha_sevi_pk)):
                raise HTTPException(
                    status_code=422,
                    detail="Only the person currently holding the Parichalak "
                           "seat may record this exception (GOV-BR-043-A).",
                )
            if not _has_valid_anumati_patra(cur, person_pk):
                raise HTTPException(
                    status_code=422,
                    detail="This Probationary candidate has no currently "
                           "valid Anumati Patra, so the Parichalak exception "
                           "cannot apply (GOV-BR-043-A).",
                )


def _require_active_membership(cur, person_pk: UUID, sangha_sevi_pk: UUID) -> None:
    """
    Enforce that a governance office-holder is an active NSS member.

    The supplied Sangha Sevi must exist, be active, and belong to person_pk.
    A person with no active Sangha Sevi record is not part of NSS and cannot
    hold a governance position (GOV-BR-056/074). Governance only validates
    membership here; it never creates or modifies it (GOV-BR-055).
    """
    cur.execute(
        "SELECT person_pk, is_active FROM nss.sangha_sevi WHERE sangha_sevi_pk = %s",
        (str(sangha_sevi_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Sangha Sevi not found.")
    sevi_person_pk, is_active = row
    if str(sevi_person_pk) != str(person_pk):
        raise HTTPException(
            status_code=422,
            detail="The Sangha Sevi membership does not belong to this person.",
        )
    if not is_active:
        raise HTTPException(
            status_code=422,
            detail="This person's Sangha Sevi membership is not active; "
                   "an inactive member cannot hold a governance position.",
        )


def _resolve_active_membership(cur, person_pk: UUID) -> UUID:
    """
    Return the person's single active Sangha Sevi (person_pk is UNIQUE on
    sangha_sevi). Raises 422 if the person is not an active NSS member, so a
    non-member can never be assigned via the election-result hand-off.
    """
    cur.execute(
        "SELECT sangha_sevi_pk FROM nss.sangha_sevi "
        "WHERE person_pk = %s AND is_active = TRUE",
        (str(person_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=422,
            detail="The winner is not an active NSS member (no active Sangha Sevi "
                   "record) and cannot be assigned to a governance position.",
        )
    return row[0]


@router.get("/bodies/{body_master_pk}/assignments", response_model=AssignmentListResponse)
def list_assignments(
    body_master_pk: UUID,
    include_inactive: bool = Query(False),
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> AssignmentListResponse:
    """List member assignments (office-holders) for one governance body."""
    with conn.cursor() as cur:
        _require_body_in_scope(cur, user, body_master_pk)
        clause = "a.body_master_pk = %s" + ("" if include_inactive else " AND a.is_active = TRUE")
        cur.execute(
            f"{_ASSIGNMENT_SELECT_SQL} WHERE {clause} ORDER BY a.effective_from DESC",
            (str(body_master_pk),),
        )
        rows = cur.fetchall()
    items = [_row_to_assignment(r) for r in rows]
    return AssignmentListResponse(items=items, total=len(items))


@router.get("/bodies/{body_master_pk}/allowed-positions")
def list_allowed_positions(
    body_master_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> dict:
    """Positions this body may hold, plus its seat limit and seats filled (drives the admin dropdown)."""
    with conn.cursor() as cur:
        org_pk = _require_body_in_scope(cur, user, body_master_pk)
        body_type_code = _body_type_code(cur, body_master_pk)
        rule = _composition_rule(body_type_code, org_pk)

        # The Sakha-nominated seat (e.g. Advisory Board MEMBER) is filled only
        # through the per-Sakha nominate flow, never through this generic
        # dropdown for an NSS-wide/global admin — exclude it for them so the
        # NSS-wide admin's "Add Assignment" form only ever offers the body's
        # own office-bearer positions (owner spec, 2026-10-14). A Sakha-scoped
        # admin (actor_scope_org_pks returns a concrete subtree, not None)
        # still sees it — that is exactly the nominate flow.
        exclude_position_code = None
        nominated_position_code = _SAKHA_NOMINATED_POSITION_CODES.get(body_type_code)
        if nominated_position_code and actor_scope_org_pks(cur, user) is None:
            exclude_position_code = nominated_position_code

        cur.execute(
            """
            SELECT position_master_pk, position_code, position_name, display_order
            FROM nss.position_master WHERE is_active = TRUE
            ORDER BY display_order, position_name
            """
        )
        positions = [
            {"position_master_pk": str(r[0]), "position_code": r[1],
             "position_name": r[2], "display_order": r[3]}
            for r in cur.fetchall()
            if (rule is None or r[1] in rule["positions"]) and r[1] != exclude_position_code
        ]
        seat_limit = _resolve_seat_limit(cur, rule)
        cur.execute(
            f"SELECT COUNT(DISTINCT a.person_pk) FROM nss.body_member_assignment a "
            f"WHERE a.body_master_pk = %s AND {_CURRENT_ASSIGNMENT_SQL}",
            (str(body_master_pk),),
        )
        seats_filled = cur.fetchone()[0]
    return {"positions": positions, "seat_limit": seat_limit, "seats_filled": seats_filled}


# Body types that display one or more INHERITED (non-assignable, read-only)
# office-holders drawn from another body. Owner-confirmed 2026-10-08: the
# Mahila Parichalana Mandali shows the Kendra Governing Body's current
# Parichalak as an inherited seat — it is not a row on the Mahila body
# (PARICHALAK is excluded from its assignable positions), the title holder
# is simply surfaced here so the nine-member body reads completely.
_INHERITED_POSITIONS: dict[str, tuple[tuple[str, str], ...]] = {
    # body_type_code -> ((inherited_position_code, source_body_type_code), ...)
    "MAHILA_PARICHALANA_MANDALI": (("PARICHALAK", "KENDRA_GOVERNING_BODY"),),
}


@router.get("/bodies/{body_master_pk}/inherited-positions")
def list_inherited_positions(
    body_master_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> dict:
    """Read-only office-holders this body inherits from another body (e.g. the
    Mahila Parichalana Mandali inherits the Kendra Governing Body's Parichalak).
    Returns an empty list for body types that inherit nothing."""
    with conn.cursor() as cur:
        _require_body_in_scope(cur, user, body_master_pk)
        body_type_code = _body_type_code(cur, body_master_pk)
        inherited = []
        for position_code, source_body_type in _INHERITED_POSITIONS.get(body_type_code, ()):  # noqa: E501
            cur.execute(
                f"""
                SELECT pm.position_name, {_person_name_sql('p')}, bm.body_name
                FROM nss.body_member_assignment a
                JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
                JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
                JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
                JOIN nss.person p ON p.person_pk = a.person_pk
                WHERE bt.body_type_code = %s AND pm.position_code = %s
                  AND bm.is_active = TRUE AND {_CURRENT_ASSIGNMENT_SQL}
                ORDER BY a.effective_from DESC
                LIMIT 1
                """,
                (source_body_type, position_code),
            )
            row = cur.fetchone()
            # Always surface the inherited seat; person_name is null when the
            # source post is currently vacant, so the UI can show "— vacant".
            cur.execute(
                "SELECT position_name FROM nss.position_master WHERE position_code = %s",
                (position_code,),
            )
            pos_row = cur.fetchone()
            inherited.append({
                "position_code": position_code,
                "position_name": (row[0] if row else (pos_row[0] if pos_row else position_code)),
                "person_name": (row[1] if row and row[1] and row[1].strip() else None),
                "source_body_name": row[2] if row else None,
                "source_body_type_code": source_body_type,
            })
    return {"inherited": inherited}


# ── Advisory Board: Sakhas not yet represented ──────────────────────────────
# Requirement (owner spec, 2026-10-14): an NSS-wide admin needs to see which
# Sakha Sanghas have NOT yet nominated their Advisory Board MEMBER
# representative. There is no direct "nominating Sakha" column on
# body_member_assignment — the nominating Sakha is derived the same way
# _home_sakha() does it everywhere else in this module: the holder's own
# active Sangha Sevi -> organization_pk. A Sakha counts as represented when
# some currently-active MEMBER assignment on the (single) Advisory Board
# resolves, via that path, back to it.
@router.get("/advisory-board/missing-nominations")
def list_advisory_board_missing_nominations(
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> dict:
    """
    Active Sakha Sanghas with no current Advisory Board MEMBER nomination.
    NSS-wide admins only — a Sakha-scoped admin only has standing over its
    own nomination (see _require_nominating_sakha_scope) and has no reason
    to see every other Sakha's status.
    """
    with conn.cursor() as cur:
        if actor_scope_org_pks(cur, user) is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an NSS-wide admin may view Advisory Board nomination status across all Sakhas.",
            )

        nominated_position_code = _SAKHA_NOMINATED_POSITION_CODES.get("ADVISORY_BOARD")
        cur.execute(
            """
            SELECT bm.body_master_pk FROM nss.body_master bm
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE bt.body_type_code = 'ADVISORY_BOARD' AND bm.is_active = TRUE
            ORDER BY bm.effective_from
            LIMIT 1
            """
        )
        body_row = cur.fetchone()
        if body_row is None:
            return {"items": [], "total": 0, "advisory_board_body_master_pk": None}
        body_master_pk = body_row[0]

        cur.execute(
            f"""
            SELECT o.organization_pk, o.organization_name, o.organization_code
            FROM nss.organization o
            JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
            WHERE o.is_active = TRUE AND md.value_code = 'SAKHA_SANGHA'
              AND o.organization_pk NOT IN (
                  SELECT ss.organization_pk
                  FROM nss.body_member_assignment a
                  JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
                  JOIN nss.sangha_sevi ss ON ss.person_pk = a.person_pk AND ss.is_active = TRUE
                  WHERE a.body_master_pk = %s AND pm.position_code = %s
                    AND {_CURRENT_ASSIGNMENT_SQL} AND ss.organization_pk IS NOT NULL
              )
            ORDER BY o.organization_name
            """,
            (str(body_master_pk), nominated_position_code),
        )
        rows = cur.fetchall()
    items = [
        {"organization_pk": r[0], "organization_name": r[1], "organization_code": r[2]}
        for r in rows
    ]
    return {
        "items": items, "total": len(items),
        "advisory_board_body_master_pk": body_master_pk,
    }


# ── Mukhya Pujaka (dedicated entry point) ───────────────────────────────────
# Owner-confirmed 2026-10-08:
#   - Mukhya Pujaka is a POSITION, not a body type. The post always exists,
#     whether or not its holder also sits on the Kendra Governing Body.
#   - When the holder IS seated on the Kendra Governing Body he counts as one
#     of its nine members (no seat exemption).
# So there is exactly ONE storage location — a MUKHYA_PUJAKA
# body_member_assignment on the Kendra Governing Body — and this endpoint just
# resolves it so a dedicated "Mukhya Pujaka" panel can read/write the SAME row
# the normal GB position-assignment flow writes. Both entry points therefore
# point at the same position via the DB; neither can create a duplicate (the
# post is in _NSS_WIDE_SINGLETON_CODES).

@router.get("/mukhya-pujaka")
def get_mukhya_pujaka(
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> dict:
    """
    The single NSS-wide Mukhya Pujaka post: its catalogue position, the Kendra
    Governing Body that hosts the seat, and the current holder (null if vacant).

    The returned position_master_pk + body_master_pk are exactly what the
    dedicated panel posts back to /bodies/{body_master_pk}/assignments, so the
    standalone entry point reuses the one validated write path (singleton,
    membership and seat-limit checks all still apply).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT position_master_pk, position_name FROM nss.position_master "
            "WHERE position_code = 'MUKHYA_PUJAKA'"
        )
        pos = cur.fetchone()
        if pos is None:
            raise HTTPException(
                status_code=404,
                detail="The Mukhya Pujaka position is missing from the position catalogue.",
            )
        position_master_pk, position_name = pos

        cur.execute(
            """
            SELECT bm.body_master_pk, bm.body_name
            FROM nss.body_master bm
            JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE bt.body_type_code = 'KENDRA_GOVERNING_BODY' AND bm.is_active = TRUE
            ORDER BY bm.effective_from
            LIMIT 1
            """
        )
        body = cur.fetchone()
        body_master_pk, body_name = body if body else (None, None)

        # Resolve the holder NSS-wide (not just on the Kendra GB) so a row
        # recorded against any body is still reported as the one current holder.
        cur.execute(
            f"""
            SELECT a.body_member_assignment_pk, a.person_pk, {_person_name_sql('p')},
                   a.effective_from, bm.body_master_pk, bm.body_name
            FROM nss.body_member_assignment a
            JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
            JOIN nss.person p ON p.person_pk = a.person_pk
            JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
            WHERE pm.position_code = 'MUKHYA_PUJAKA' AND {_CURRENT_ASSIGNMENT_SQL}
            ORDER BY a.effective_from DESC
            LIMIT 1
            """
        )
        h = cur.fetchone()
        holder = None
        if h:
            holder = {
                "body_member_assignment_pk": h[0],
                "person_pk": h[1],
                "person_name": h[2].strip() if h[2] and h[2].strip() else None,
                "effective_from": h[3],
                "body_master_pk": h[4],
                "body_name": h[5],
            }

    return {
        "position_master_pk": position_master_pk,
        "position_name": position_name,
        "body_master_pk": body_master_pk,
        "body_name": body_name,
        "holder": holder,
    }


@router.post(
    "/bodies/{body_master_pk}/assignments", response_model=AssignmentResponse, status_code=201,
)
def create_assignment(
    body_master_pk: UUID,
    body: CreateAssignmentRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> AssignmentResponse:
    """
    Assign a Person to a position within a governance body (GOV-BR-015/016).

    person_pk is the authoritative identity (GOV-BR-057/074). sangha_sevi_pk
    is MANDATORY: a governance position can only be held by an NSS member, and
    a person with no active Sangha Sevi record is not part of NSS. We validate
    the supplied Sangha Sevi is active and belongs to person_pk (GOV-BR-056)
    before accepting the assignment; Governance never creates or modifies the
    membership record itself (GOV-BR-055).
    """
    with conn.cursor() as cur:
        org_pk = _get_body_org_or_404(cur, body_master_pk)
        require_entity(cur, "position_master", str(body.position_master_pk), label="Position")
        require_entity(cur, "person", str(body.person_pk), label="Person")
        cur.execute(
            "SELECT position_code FROM nss.position_master WHERE position_master_pk = %s",
            (str(body.position_master_pk),),
        )
        position_code_row = cur.fetchone()
        position_code = position_code_row[0] if position_code_row else None
        # Advisory Board MEMBER seats are nominated by the represented Sakha's
        # general body, so authority is the nominee's own Sakha — not this
        # NSS-wide body. PRESIDENT/SECRETARY are real office-bearer seats
        # elected from among the members and stay under the normal NSS-wide/
        # org-scope guard below (2026-10-14).
        if not _require_nominating_sakha_scope(
            cur, user, _body_type_code(cur, body_master_pk), position_code, body.person_pk,
            "nominate an Advisory Board representative",
        ):
            _require_scope_for_org_or_nss_wide(cur, user, org_pk, "manage body member assignments")
        _require_active_membership(cur, body.person_pk, body.sangha_sevi_pk)
        _require_valid_composition(cur, body_master_pk, org_pk, body.position_master_pk, body.person_pk)

        effective_from = parse_optional_date(body.effective_from, "Effective From")
        effective_to = parse_optional_date(body.effective_to, "Effective To")
        if effective_to and effective_from and effective_to < effective_from:
            raise HTTPException(status_code=422, detail="Effective To cannot be before Effective From.")

        actor = user.actor_pk
        cur.execute("SAVEPOINT assignment_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.body_member_assignment (
                    body_master_pk, position_master_pk, person_pk, sangha_sevi_pk,
                    effective_from, effective_to, assignment_reference, remarks
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING body_member_assignment_pk
                """,
                (str(body_master_pk), str(body.position_master_pk), str(body.person_pk),
                 str(body.sangha_sevi_pk),
                 effective_from, effective_to, body.assignment_reference, body.remarks),
            )
            pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT assignment_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This person already holds this position in this body in an "
                    "active, open-ended assignment. End the existing one first."
                ),
            )
        cur.execute("RELEASE SAVEPOINT assignment_insert")
        log_audit(cur, action="CREATE", table_name="body_member_assignment", record_pk=str(pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Created body member assignment")

        cur.execute(f"{_ASSIGNMENT_SELECT_SQL} WHERE a.body_member_assignment_pk = %s", (str(pk),))
        r = cur.fetchone()
    return _row_to_assignment(r)


@router.post("/assignments/{body_member_assignment_pk}/end", response_model=AssignmentResponse)
def end_assignment(
    body_member_assignment_pk: UUID,
    body: EndAssignmentRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> AssignmentResponse:
    """
    End an open-ended member assignment (GOV-BR-017) — sets effective_to + status ENDED.

    Direct ending is reserved for the nominating Sakha withdrawing its own
    Advisory Board MEMBER nominee. Every other admin-initiated ending must go
    through POST /request-removal → GB-meeting-backed President approval
    (GOV-BR item #18, generalized 2026-10-15).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bm.organization_pk, a.effective_from, a.person_pk, bt.body_type_code,
                   pm.position_code
            FROM nss.body_member_assignment a
            JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
            JOIN nss.body_type_master bt
                 ON bt.body_type_master_pk = bm.body_type_master_pk
            JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
            WHERE a.body_member_assignment_pk = %s
            """,
            (str(body_member_assignment_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        org_pk, effective_from, holder_person_pk, body_type_code, position_code = row
        # Only the nominating Sakha may withdraw its Advisory Board MEMBER
        # representative directly — an NSS-wide admin may not (owner-confirmed
        # 2026-10-08). That is the one case left on this endpoint; it is the
        # nominating authority un-appointing its own nominee, not an "admin
        # removal", so it is deliberately NOT routed through GB-meeting +
        # President approval.
        #
        # Every other admin-initiated ending (generalized 2026-10-15, GOV-BR
        # item #18) is redirected to request-removal instead of ending here
        # directly: removing someone from any position in any governance body
        # must first be resolved in that body's own GB meeting (Sevak Sangha
        # Executive: the concerned Sakha's GB instead) and then recorded via
        # that body's own President sign-off.
        if _require_nominating_sakha_scope(
            cur, user, body_type_code, position_code, holder_person_pk,
            "withdraw this Advisory Board nomination",
            breakglass_endpoint="POST /governance/assignments/{id}/request-removal",
        ):
            pass
        else:
            _require_scope_for_org_or_nss_wide(cur, user, org_pk, "end body member assignments")
            raise HTTPException(
                status_code=409,
                detail=(
                    "Removing someone from a governance body position requires that "
                    "body's own GB meeting resolution and its President's approval — "
                    "use POST /governance/assignments/{id}/request-removal instead."
                ),
            )

        effective_to = parse_optional_date(body.effective_to, "Effective To")
        if effective_from and effective_to and effective_to < effective_from:
            raise HTTPException(status_code=422, detail="Effective To cannot be before Effective From.")

        cur.execute(
            """
            UPDATE nss.body_member_assignment
            SET effective_to = %s, assignment_status = 'ENDED',
                remarks = COALESCE(%s, remarks), updated_at = NOW()
            WHERE body_member_assignment_pk = %s
            """,
            (effective_to, body.remarks, str(body_member_assignment_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="body_member_assignment",
                  record_pk=str(body_member_assignment_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Ended body member assignment")

        cur.execute(
            f"{_ASSIGNMENT_SELECT_SQL} WHERE a.body_member_assignment_pk = %s",
            (str(body_member_assignment_pk),),
        )
        r = cur.fetchone()
    return _row_to_assignment(r)


@router.post("/assignments/{body_member_assignment_pk}/resign", response_model=AssignmentResponse)
def resign_assignment(
    body_member_assignment_pk: UUID,
    body: ResignAssignmentRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> AssignmentResponse:
    """
    Voluntary self-withdrawal from a governance seat (owner-confirmed 2026-10-15;
    Bye-Law REF-003-C(i)(1) clause (1)(d) names resignation as a vacancy cause
    with no acceptance step). Sets effective_to + assignment_status = RESIGNED.

    STRICTLY self-service: gated on get_current_user alone, and the authenticated
    user MUST be the person named on the assignment. There is deliberately no
    permission, admin-scope or NSS-wide override — not even GOVERNANCE_MANAGE or
    the super-admin may resign on someone's behalf (that is what distinguishes
    RESIGNED from an admin-driven ENDED, and resignation from forced removal,
    which routes through request-removal + President approval). A seat whose
    holder is deactivated or deceased is closed as ENDED by an admin, never
    RESIGNED.

    Resignation takes effect immediately: effective_to may not be in the future.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT person_pk, effective_from, assignment_status
            FROM nss.body_member_assignment
            WHERE body_member_assignment_pk = %s
            """,
            (str(body_member_assignment_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        holder_person_pk, effective_from, current_status = row

        # Self-only: no admin / scope / NSS-wide override of any kind.
        if user.person_pk is None or str(user.person_pk) != str(holder_person_pk):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the office holder may resign this assignment.",
            )
        if current_status not in ("ASSIGNED", "ACTIVE"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot resign — this assignment is already {current_status}.",
            )

        effective_to = parse_optional_date(body.effective_to, "Effective To")
        if effective_from and effective_to < effective_from:
            raise HTTPException(status_code=422, detail="Effective To cannot be before Effective From.")
        if effective_to > date.today():
            raise HTTPException(
                status_code=422,
                detail="Resignation takes effect immediately — the effective date cannot be in the future.",
            )

        cur.execute(
            """
            UPDATE nss.body_member_assignment
            SET effective_to = %s, assignment_status = 'RESIGNED',
                resignation_reason = %s, updated_at = NOW()
            WHERE body_member_assignment_pk = %s
            """,
            (effective_to, body.resignation_reason, str(body_member_assignment_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="body_member_assignment",
                  record_pk=str(body_member_assignment_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Member resigned from body")

        cur.execute(
            f"{_ASSIGNMENT_SELECT_SQL} WHERE a.body_member_assignment_pk = %s",
            (str(body_member_assignment_pk),),
        )
        r = cur.fetchone()
    return _row_to_assignment(r)


@router.post(
    "/assignments/{body_member_assignment_pk}/request-removal", response_model=AssignmentResponse,
)
def request_assignment_removal(
    body_member_assignment_pk: UUID,
    body: RequestAssignmentRemovalRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> AssignmentResponse:
    """
    Request a forced removal of a member from any position in any governance
    body (GOV-BR item #18, generalized 2026-10-15 beyond the original
    Advisory-Board-only, super-admin break-glass version).

    May be filed by that body's own scoped admin (NSS-wide/org-scope, as
    usual for GOVERNANCE_MANAGE) or by one of that body's own currently
    active office bearers. gb_resolution_reference is mandatory: the real
    approval is that body's own General Body meeting resolution (the
    concerned Sakha's GB, for a Sevak Sangha Executive seat) — this call only
    records that a removal has been proposed, and sets assignment_status to
    PENDING_REMOVAL. It only becomes ENDED once the body's own sitting
    President (or, while that seat is vacant, another of its own sitting
    office bearers) approves it.

    The nominating Sakha's own instant self-withdrawal of its Advisory Board
    MEMBER nominee stays on the direct /end endpoint — it is not an "admin
    removal" and never needs this approval gate.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.body_master_pk, bt.body_type_code, a.person_pk, a.assignment_status,
                   pm.position_code, bm.organization_pk
            FROM nss.body_member_assignment a
            JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
            JOIN nss.body_type_master bt
                 ON bt.body_type_master_pk = bm.body_type_master_pk
            JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
            WHERE a.body_member_assignment_pk = %s
            """,
            (str(body_member_assignment_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        body_master_pk, body_type_code, holder_person_pk, current_status, position_code, org_pk = row

        _require_removal_initiator(cur, user, org_pk, body_master_pk, "request a forced removal")
        if current_status not in ("ASSIGNED", "ACTIVE"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot request removal — this assignment is already {current_status}.",
            )

        cur.execute(
            """
            UPDATE nss.body_member_assignment
            SET assignment_status = 'PENDING_REMOVAL',
                remarks = %s, assignment_reference = %s, updated_at = NOW()
            WHERE body_member_assignment_pk = %s
            """,
            (body.reason, body.gb_resolution_reference, str(body_member_assignment_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="body_member_assignment",
                  record_pk=str(body_member_assignment_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Requested forced removal (pending President approval)")

        cur.execute(
            f"{_ASSIGNMENT_SELECT_SQL} WHERE a.body_member_assignment_pk = %s",
            (str(body_member_assignment_pk),),
        )
        r = cur.fetchone()
    return _row_to_assignment(r)


@router.post(
    "/assignments/{body_member_assignment_pk}/approve-removal", response_model=AssignmentResponse,
)
def approve_assignment_removal(
    body_member_assignment_pk: UUID,
    body: DecideAssignmentRemovalRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> AssignmentResponse:
    """
    Approve a pending forced removal — only the body's own sitting President,
    or (while that seat is vacant) another of its own sitting office bearers
    (GOV-BR item #18, generalized 2026-10-15). For a Sevak Sangha Executive
    seat, approval authority belongs to the concerned Sakha's own Governing
    Body office bearers instead.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.body_master_pk, a.assignment_status, a.effective_from,
                   bt.body_type_code, bm.organization_pk
            FROM nss.body_member_assignment a
            JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
            JOIN nss.body_type_master bt
                 ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE a.body_member_assignment_pk = %s
            """,
            (str(body_member_assignment_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        body_master_pk, current_status, effective_from, body_type_code, org_pk = row
        if current_status != "PENDING_REMOVAL":
            raise HTTPException(
                status_code=409, detail="This assignment has no pending removal request to approve.",
            )
        approver_body_master_pk = _removal_approver_body(cur, body_master_pk, body_type_code, org_pk)
        _require_body_president(cur, user, approver_body_master_pk, "approve this forced removal")

        effective_to = parse_optional_date(body.effective_to, "Effective To")
        if effective_to is None:
            raise HTTPException(status_code=422, detail="Effective To is required to approve a removal.")
        if effective_from and effective_to < effective_from:
            raise HTTPException(status_code=422, detail="Effective To cannot be before Effective From.")

        cur.execute(
            """
            UPDATE nss.body_member_assignment
            SET effective_to = %s, assignment_status = 'ENDED',
                remarks = COALESCE(%s, remarks), updated_at = NOW()
            WHERE body_member_assignment_pk = %s
            """,
            (effective_to, body.remarks, str(body_member_assignment_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="body_member_assignment",
                  record_pk=str(body_member_assignment_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="President approved forced removal")

        cur.execute(
            f"{_ASSIGNMENT_SELECT_SQL} WHERE a.body_member_assignment_pk = %s",
            (str(body_member_assignment_pk),),
        )
        r = cur.fetchone()
    return _row_to_assignment(r)


@router.post(
    "/assignments/{body_member_assignment_pk}/reject-removal", response_model=AssignmentResponse,
)
def reject_assignment_removal(
    body_member_assignment_pk: UUID,
    body: DecideAssignmentRemovalRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> AssignmentResponse:
    """
    Reject a pending forced removal — only the body's own sitting President,
    or (while that seat is vacant) another of its own sitting office bearers
    (GOV-BR item #18, generalized 2026-10-15). For a Sevak Sangha Executive
    seat, approval authority belongs to the concerned Sakha's own Governing
    Body office bearers instead.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.body_master_pk, a.assignment_status, bt.body_type_code, bm.organization_pk
            FROM nss.body_member_assignment a
            JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
            JOIN nss.body_type_master bt
                 ON bt.body_type_master_pk = bm.body_type_master_pk
            WHERE a.body_member_assignment_pk = %s
            """,
            (str(body_member_assignment_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Assignment not found.")
        body_master_pk, current_status, body_type_code, org_pk = row
        if current_status != "PENDING_REMOVAL":
            raise HTTPException(
                status_code=409, detail="This assignment has no pending removal request to reject.",
            )
        approver_body_master_pk = _removal_approver_body(cur, body_master_pk, body_type_code, org_pk)
        _require_body_president(cur, user, approver_body_master_pk, "reject this forced removal")

        cur.execute(
            """
            UPDATE nss.body_member_assignment
            SET assignment_status = 'ACTIVE',
                remarks = COALESCE(%s, remarks), updated_at = NOW()
            WHERE body_member_assignment_pk = %s
            """,
            (body.remarks, str(body_member_assignment_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="body_member_assignment",
                  record_pk=str(body_member_assignment_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="President rejected forced removal")

        cur.execute(
            f"{_ASSIGNMENT_SELECT_SQL} WHERE a.body_member_assignment_pk = %s",
            (str(body_member_assignment_pk),),
        )
        r = cur.fetchone()
    return _row_to_assignment(r)


# ═════════════════════════════════════════════════════════════════════
# Acting Position Assignment
# ═════════════════════════════════════════════════════════════════════

_ACTING_SELECT_SQL = f"""
    SELECT a.acting_position_assignment_pk, a.body_master_pk, a.position_master_pk,
           pm.position_name, a.person_pk, {_person_name_sql('p')},
           a.effective_from, a.effective_to, a.acting_status, a.reason, a.remarks, a.is_active
    FROM nss.acting_position_assignment a
    JOIN nss.position_master pm ON pm.position_master_pk = a.position_master_pk
    JOIN nss.person p ON p.person_pk = a.person_pk
"""


def _row_to_acting(r) -> ActingAssignmentResponse:
    return ActingAssignmentResponse(
        acting_position_assignment_pk=r[0], body_master_pk=r[1], position_master_pk=r[2],
        position_name=r[3], person_pk=r[4], person_name=r[5] if r[5] and r[5].strip() else None,
        effective_from=r[6], effective_to=r[7], acting_status=r[8], reason=r[9],
        remarks=r[10], is_active=r[11],
    )


@router.get(
    "/bodies/{body_master_pk}/acting-assignments", response_model=ActingAssignmentListResponse,
)
def list_acting_assignments(
    body_master_pk: UUID,
    include_inactive: bool = Query(False),
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> ActingAssignmentListResponse:
    """List acting/interim position cover for one governance body (GOV-BR-018)."""
    with conn.cursor() as cur:
        _require_body_in_scope(cur, user, body_master_pk)
        clause = "a.body_master_pk = %s" + ("" if include_inactive else " AND a.is_active = TRUE")
        cur.execute(
            f"{_ACTING_SELECT_SQL} WHERE {clause} ORDER BY a.effective_from DESC",
            (str(body_master_pk),),
        )
        rows = cur.fetchall()
    items = [_row_to_acting(r) for r in rows]
    return ActingAssignmentListResponse(items=items, total=len(items))


@router.post(
    "/bodies/{body_master_pk}/acting-assignments",
    response_model=ActingAssignmentResponse, status_code=201,
)
def create_acting_assignment(
    body_master_pk: UUID,
    body: CreateActingAssignmentRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> ActingAssignmentResponse:
    """Record a temporary/acting position holder (GOV-BR-018/019/020)."""
    with conn.cursor() as cur:
        org_pk = _get_body_org_or_404(cur, body_master_pk)
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, "manage acting position assignments")
        require_entity(cur, "position_master", str(body.position_master_pk), label="Position")
        require_entity(cur, "person", str(body.person_pk), label="Person")

        effective_from = parse_optional_date(body.effective_from, "Effective From")
        effective_to = parse_optional_date(body.effective_to, "Effective To")
        if effective_to and effective_from and effective_to < effective_from:
            raise HTTPException(status_code=422, detail="Effective To cannot be before Effective From.")

        actor = user.actor_pk
        cur.execute("SAVEPOINT acting_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.acting_position_assignment (
                    body_master_pk, position_master_pk, person_pk,
                    effective_from, effective_to, reason, remarks
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING acting_position_assignment_pk
                """,
                (str(body_master_pk), str(body.position_master_pk), str(body.person_pk),
                 effective_from, effective_to, body.reason, body.remarks),
            )
            pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT acting_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This person already has an active, open-ended acting "
                    "assignment for this position in this body."
                ),
            )
        cur.execute("RELEASE SAVEPOINT acting_insert")
        log_audit(cur, action="CREATE", table_name="acting_position_assignment", record_pk=str(pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Created acting position assignment")

        cur.execute(f"{_ACTING_SELECT_SQL} WHERE a.acting_position_assignment_pk = %s", (str(pk),))
        r = cur.fetchone()
    return _row_to_acting(r)


@router.post(
    "/acting-assignments/{acting_position_assignment_pk}/end",
    response_model=ActingAssignmentResponse,
)
def end_acting_assignment(
    acting_position_assignment_pk: UUID,
    body: EndActingAssignmentRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> ActingAssignmentResponse:
    """End an open-ended acting assignment — sets effective_to + status ENDED."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bm.organization_pk, a.effective_from
            FROM nss.acting_position_assignment a
            JOIN nss.body_master bm ON bm.body_master_pk = a.body_master_pk
            WHERE a.acting_position_assignment_pk = %s
            """,
            (str(acting_position_assignment_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Acting assignment not found.")
        org_pk, effective_from = row
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, "end acting position assignments")

        effective_to = parse_optional_date(body.effective_to, "Effective To")
        if effective_from and effective_to and effective_to < effective_from:
            raise HTTPException(status_code=422, detail="Effective To cannot be before Effective From.")

        cur.execute(
            """
            UPDATE nss.acting_position_assignment
            SET effective_to = %s, acting_status = 'ENDED',
                remarks = COALESCE(%s, remarks), updated_at = NOW()
            WHERE acting_position_assignment_pk = %s
            """,
            (effective_to, body.remarks, str(acting_position_assignment_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="acting_position_assignment",
                  record_pk=str(acting_position_assignment_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Ended acting position assignment")

        cur.execute(
            f"{_ACTING_SELECT_SQL} WHERE a.acting_position_assignment_pk = %s",
            (str(acting_position_assignment_pk),),
        )
        r = cur.fetchone()
    return _row_to_acting(r)


# ═════════════════════════════════════════════════════════════════════
# Election
# ═════════════════════════════════════════════════════════════════════

_ELECTION_SORT_COLUMNS: dict[str, str | list[str]] = {
    "election_code": natural_sort_key("e.election_code"),
    "election_name": "e.election_name",
    "election_date": "e.election_date",
    "election_status": "e.election_status",
    "body_name": "bm.body_name",
}

_ELECTION_SELECT_SQL = """
    SELECT e.election_pk, e.election_code, e.body_master_pk, bm.body_name,
           e.organization_pk, e.election_name, e.description, e.election_date,
           e.nomination_start_date, e.nomination_end_date,
           e.voting_start_date, e.voting_end_date,
           e.election_status, e.remarks, e.is_active, e.is_secret_ballot,
           e.election_type
    FROM nss.election e
    JOIN nss.body_master bm ON bm.body_master_pk = e.body_master_pk
"""


def _row_to_election(r) -> ElectionResponse:
    return ElectionResponse(
        election_pk=r[0], election_code=r[1], body_master_pk=r[2], body_name=r[3],
        organization_pk=r[4], election_name=r[5], description=r[6], election_date=r[7],
        nomination_start_date=r[8], nomination_end_date=r[9],
        voting_start_date=r[10], voting_end_date=r[11],
        election_status=r[12], remarks=r[13], is_active=r[14], is_secret_ballot=r[15],
        election_type=r[16],
    )


@router.get("/me/parichalak-status", response_model=ParichalakStatusResponse)
def get_my_parichalak_status(
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> ParichalakStatusResponse:
    """
    GOV-BR-043-A: self-check so the member dashboard can show the
    "probationary candidate exception" nomination action only to whoever
    currently, actively holds the single NSS-wide Parichalak seat — without
    the frontend having to infer it from /public/national-bodies. Any
    logged-in member may call this (it only ever reveals whether THEY are
    the Parichalak); no permission beyond a valid login is required, mirroring
    POST /elections/{election_pk}/votes/self.
    """
    if user.sangha_sevi_pk is None:
        return ParichalakStatusResponse(is_parichalak=False, sangha_sevi_pk=None)
    with conn.cursor() as cur:
        current_parichalak_pk = _resolve_current_parichalak_sangha_sevi_pk(cur)
    is_parichalak = (
        current_parichalak_pk is not None and current_parichalak_pk == user.sangha_sevi_pk
    )
    return ParichalakStatusResponse(
        is_parichalak=is_parichalak,
        sangha_sevi_pk=user.sangha_sevi_pk if is_parichalak else None,
    )


@router.get("/elections", response_model=ElectionListResponse)
def list_elections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    search: str | None = Query(None),
    election_status: str | None = Query(None),
    body_master_pk: UUID | None = Query(None),
    include_inactive: bool = Query(False),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> ElectionListResponse:
    """List elections, paginated/sortable/searchable, scope-aware (same rule as bodies)."""
    offset = (page - 1) * page_size
    order_by = build_order_by(sort_by, sort_dir, _ELECTION_SORT_COLUMNS, "e.election_date DESC")

    conditions = ["TRUE"] if include_inactive else ["e.is_active = TRUE"]
    params: list = []
    if election_status:
        conditions.append("e.election_status = %s")
        params.append(election_status)
    if body_master_pk:
        conditions.append("e.body_master_pk = %s")
        params.append(str(body_master_pk))
    if search:
        conditions.append("(e.election_code ILIKE %s OR e.election_name ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])

    with conn.cursor() as cur:
        conditions.append(_visible_org_filter(cur, user, "e.organization_pk", params))
        where_clause = " AND ".join(conditions)

        cur.execute(
            f"SELECT COUNT(*) FROM nss.election e JOIN nss.body_master bm ON bm.body_master_pk = e.body_master_pk WHERE {where_clause}",
            params,
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"{_ELECTION_SELECT_SQL} WHERE {where_clause} ORDER BY {order_by} LIMIT %s OFFSET %s",
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    return ElectionListResponse(
        items=[_row_to_election(r) for r in rows], total=total, page=page, page_size=page_size,
    )


@router.get("/elections/open-for-voting", response_model=OpenElectionListResponse)
def list_open_elections_for_voting(
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_connection),
) -> OpenElectionListResponse:
    """
    Member self-service (GOV-BR-045): elections currently in VOTING that THIS
    member may cast a ballot in — gated on a valid login alone, same as
    votes/self, so an ordinary member with no admin role can still see what
    they're entitled to vote on. Deliberately NOT behind GOVERNANCE_VIEW.

    Scope: NSS/Kendra-wide elections (body.organization_pk IS NULL) are
    visible to every member; an org-scoped election is visible only to
    members of that same org (currently: the member's home Sakha Sangha,
    via _home_sakha — mirrors the public/national-bodies visibility rule).
    Bylaw voter eligibility (GOV-BR-043) is enforced again at vote time by
    votes/self; this listing is read-only and does not re-check it, so an
    ineligible member can see the ballot but will still get a 4xx on cast.

    NOTE: this route MUST remain registered before GET /elections/{election_pk}
    below — Starlette matches routes by registration-order/syntactic pattern,
    not by the {election_pk} parameter's UUID type, so a later registration
    here would be shadowed and return a 422 instead of ever being reached.
    """
    if user.person_pk is None:
        return OpenElectionListResponse(items=[])

    with conn.cursor() as cur:
        home_org_pk, _ = _home_sakha(cur, user.person_pk)

        cur.execute(
            """
            SELECT e.election_pk, e.election_code, e.election_name,
                   e.body_master_pk, bm.body_name, e.is_secret_ballot,
                   e.voting_end_date
            FROM nss.election e
            JOIN nss.body_master bm ON bm.body_master_pk = e.body_master_pk
            WHERE e.is_active = TRUE
              AND e.election_status = 'VOTING'
              AND (e.organization_pk IS NULL OR e.organization_pk = %s)
            ORDER BY e.voting_end_date NULLS LAST, e.election_date
            """,
            (str(home_org_pk) if home_org_pk else None,),
        )
        election_rows = cur.fetchall()

        items: list[OpenElectionRow] = []
        for r in election_rows:
            election_pk = r[0]
            cur.execute(
                f"""
                SELECT n.election_nomination_pk, n.position_master_pk, pm.position_name,
                       n.candidate_person_pk, {_person_name_sql('cp')}
                FROM nss.election_nomination n
                JOIN nss.position_master pm ON pm.position_master_pk = n.position_master_pk
                JOIN nss.person cp ON cp.person_pk = n.candidate_person_pk
                WHERE n.election_pk = %s AND n.nomination_status = 'ACCEPTED' AND n.is_active = TRUE
                ORDER BY pm.position_name, {_person_name_sql('cp')}
                """,
                (str(election_pk),),
            )
            nominations = [
                VotableNominationRow(
                    election_nomination_pk=nr[0], position_master_pk=nr[1],
                    position_name=nr[2], candidate_person_pk=nr[3], candidate_name=nr[4],
                )
                for nr in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT DISTINCT position_master_pk
                FROM nss.election_vote_participation
                WHERE election_pk = %s AND voter_person_pk = %s
                """,
                (str(election_pk), str(user.person_pk)),
            )
            voted_position_pks = [vr[0] for vr in cur.fetchall()]

            items.append(OpenElectionRow(
                election_pk=election_pk, election_code=r[1], election_name=r[2],
                body_master_pk=r[3], body_name=r[4], is_secret_ballot=r[5],
                voting_end_date=str(r[6]) if r[6] else None,
                nominations=nominations, voted_position_pks=voted_position_pks,
            ))

    return OpenElectionListResponse(items=items)


@router.get("/elections/{election_pk}", response_model=ElectionResponse)
def get_election(
    election_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> ElectionResponse:
    """Get one election's detail."""
    with conn.cursor() as cur:
        cur.execute(f"{_ELECTION_SELECT_SQL} WHERE e.election_pk = %s", (str(election_pk),))
        r = cur.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Election not found.")
        if r[4] is not None:
            allowed = actor_scope_org_pks(cur, user)
            if allowed is not None and str(r[4]) not in allowed:
                raise HTTPException(status_code=403, detail="This election is outside your admin scope.")
    return _row_to_election(r)


def _get_election_org_or_404(cur, election_pk: UUID):
    cur.execute("SELECT organization_pk FROM nss.election WHERE election_pk = %s", (str(election_pk),))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Election not found.")
    return row[0]


@router.post("/elections", response_model=ElectionResponse, status_code=201)
def create_election(
    body: CreateElectionRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> ElectionResponse:
    """Schedule an election to reconstitute/fill a governance body (GOV-BR-030/031/032/033)."""
    with conn.cursor() as cur:
        require_entity(cur, "body_master", str(body.body_master_pk), label="Governance body")

        # organization_pk mirrors the body's own org (GOV-BR-059) — derived
        # server-side, never taken from the client. The admin UI never sent
        # this field at all, so trusting body.organization_pk meant every
        # election (Sakha or national) was created with organization_pk
        # NULL: a Sakha-scoped admin would 403 ("only NSS-wide admin may
        # create an NSS-wide record"), and anyone who did get it through
        # would have the election visible NSS-wide instead of Sakha-scoped.
        cur.execute(
            "SELECT organization_pk FROM nss.body_master WHERE body_master_pk = %s",
            (str(body.body_master_pk),),
        )
        body_organization_pk = cur.fetchone()[0]

        _require_scope_for_org_or_nss_wide(cur, user, body_organization_pk, "create elections")

        election_date = parse_optional_date(body.election_date, "Election Date")
        nomination_start = parse_optional_date(body.nomination_start_date, "Nomination Start Date")
        nomination_end = parse_optional_date(body.nomination_end_date, "Nomination End Date")
        voting_start = parse_optional_date(body.voting_start_date, "Voting Start Date")
        voting_end = parse_optional_date(body.voting_end_date, "Voting End Date")
        if nomination_start and nomination_end and nomination_end < nomination_start:
            raise HTTPException(status_code=422, detail="Nomination End Date cannot be before Nomination Start Date.")
        if voting_start and voting_end and voting_end < voting_start:
            raise HTTPException(status_code=422, detail="Voting End Date cannot be before Voting Start Date.")

        # A NOMINATION (consensus/selection) cycle holds no ballot at all, so a
        # voting window on it is meaningless — reject it here rather than let
        # chk_election_nomination_mode_no_voting surface as a 500 (GOV-BR-042).
        if body.election_type == "NOMINATION" and (voting_start or voting_end):
            raise HTTPException(
                status_code=422,
                detail="A Nomination (consensus/selection) cycle holds no ballot, "
                       "so it cannot have a voting window. Clear the voting dates, "
                       "or create this as an Election instead.",
            )

        actor = user.actor_pk
        cur.execute("SAVEPOINT election_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.election (
                    election_code, body_master_pk, organization_pk, election_name,
                    description, election_type, election_date,
                    nomination_start_date, nomination_end_date,
                    voting_start_date, voting_end_date, is_secret_ballot, remarks
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING election_pk
                """,
                (body.election_code.strip().upper(), str(body.body_master_pk),
                 str(body_organization_pk) if body_organization_pk else None,
                 body.election_name.strip(), body.description, body.election_type,
                 election_date, nomination_start, nomination_end, voting_start, voting_end,
                 body.is_secret_ballot, body.remarks),
            )
            pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT election_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Election code '{body.election_code}' already exists.",
            )
        cur.execute("RELEASE SAVEPOINT election_insert")
        log_audit(cur, action="CREATE", table_name="election", record_pk=str(pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary=f"Created election {body.election_code}")

        cur.execute(f"{_ELECTION_SELECT_SQL} WHERE e.election_pk = %s", (str(pk),))
        r = cur.fetchone()
    return _row_to_election(r)


# Valid election lifecycle transitions (GOV-BR-041), keyed by the CURRENT
# status. Previously this table lived only in the frontend (admin.js
# govNextStatuses), so the API would accept any status jump — including
# re-opening a COMPLETED election or skipping straight to COMPLETED without
# ever taking nominations. It is enforced here now; the frontend copy is a
# convenience for rendering the buttons, not the authority.
#
# NOMINATION -> VOTING is legal only for election_type = 'ELECTION', and
# NOMINATION -> COMPLETED only for election_type = 'NOMINATION' (the
# consensus/selection path, GOV-BR-042). _ELECTION_STATUS_TRANSITIONS lists
# the union; the mode check below narrows it.
_ELECTION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "SCHEDULED": {"NOMINATION", "CANCELLED"},
    "NOMINATION": {"VOTING", "COMPLETED", "CANCELLED"},
    "VOTING": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


@router.patch("/elections/{election_pk}/status", response_model=ElectionResponse)
def update_election_status(
    election_pk: UUID,
    body: UpdateElectionStatusRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> ElectionResponse:
    """
    Advance/change an election's lifecycle status (GOV-BR-041).

    An ELECTION cycle runs Scheduled -> Nomination -> Voting -> Completed.
    A NOMINATION cycle (consensus/selection, GOV-BR-042) runs
    Scheduled -> Nomination -> Completed, skipping Voting entirely.
    Either may be Cancelled from any open state; Completed and Cancelled are
    terminal.

    The transition itself is validated here. Which child steps
    (nomination/vote/result) are permitted at each status is gated in those
    endpoints.
    """
    with conn.cursor() as cur:
        org_pk = _get_election_org_or_404(cur, election_pk)
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, "change election status")

        cur.execute(
            "SELECT election_status, election_type FROM nss.election WHERE election_pk = %s",
            (str(election_pk),),
        )
        current_status, election_type = cur.fetchone()
        new_status = body.election_status

        if new_status != current_status:
            allowed = _ELECTION_STATUS_TRANSITIONS.get(current_status, set())
            if election_type == "NOMINATION":
                allowed = allowed - {"VOTING"}
            elif current_status == "NOMINATION":
                # A contested election must hold its ballot before completing.
                allowed = allowed - {"COMPLETED"}

            if new_status not in allowed:
                nice = ", ".join(sorted(allowed)) if allowed else "none"
                mode = "Nomination (consensus)" if election_type == "NOMINATION" else "Election"
                raise HTTPException(
                    status_code=422,
                    detail=f"Cannot move a {mode} cycle from {current_status} to "
                           f"{new_status}. Allowed next: {nice}.",
                )

        cur.execute(
            "UPDATE nss.election SET election_status = %s, updated_at = NOW() WHERE election_pk = %s",
            (new_status, str(election_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="election", record_pk=str(election_pk),
                  actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary=f"Set election status to {body.election_status}")
        cur.execute(f"{_ELECTION_SELECT_SQL} WHERE e.election_pk = %s", (str(election_pk),))
        r = cur.fetchone()
    return _row_to_election(r)


# ═════════════════════════════════════════════════════════════════════
# Election Nomination
# ═════════════════════════════════════════════════════════════════════

_NOMINATION_SELECT_SQL = f"""
    SELECT n.election_nomination_pk, n.election_pk, n.position_master_pk, pm.position_name,
           n.candidate_person_pk, {_person_name_sql('cp')},
           n.proposer_person_pk, {_person_name_sql('pp')},
           n.nomination_date, n.nomination_status, n.remarks,
           n.probationary_exception_approver_sangha_sevi_pk,
           n.probationary_exception_reason, n.is_active
    FROM nss.election_nomination n
    JOIN nss.position_master pm ON pm.position_master_pk = n.position_master_pk
    JOIN nss.person cp ON cp.person_pk = n.candidate_person_pk
    LEFT JOIN nss.person pp ON pp.person_pk = n.proposer_person_pk
"""


def _row_to_nomination(r) -> NominationResponse:
    return NominationResponse(
        election_nomination_pk=r[0], election_pk=r[1], position_master_pk=r[2],
        position_name=r[3], candidate_person_pk=r[4],
        candidate_name=r[5] if r[5] and r[5].strip() else None,
        proposer_person_pk=r[6], proposer_name=r[7] if r[7] and r[7].strip() else None,
        nomination_date=r[8], nomination_status=r[9], remarks=r[10],
        probationary_exception_approver_sangha_sevi_pk=r[11],
        probationary_exception_reason=r[12], is_active=r[13],
    )


@router.get("/elections/{election_pk}/nominations", response_model=NominationListResponse)
def list_nominations(
    election_pk: UUID,
    include_inactive: bool = Query(False),
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> NominationListResponse:
    """List candidate nominations for an election (GOV-BR-034)."""
    with conn.cursor() as cur:
        org_pk = _get_election_org_or_404(cur, election_pk)
        allowed = actor_scope_org_pks(cur, user)
        if allowed is not None and org_pk is not None and str(org_pk) not in allowed:
            raise HTTPException(status_code=403, detail="This election is outside your admin scope.")
        clause = "n.election_pk = %s" + ("" if include_inactive else " AND n.is_active = TRUE")
        cur.execute(f"{_NOMINATION_SELECT_SQL} WHERE {clause}", (str(election_pk),))
        rows = cur.fetchall()
    items = [_row_to_nomination(r) for r in rows]
    return NominationListResponse(items=items, total=len(items))


@router.post(
    "/elections/{election_pk}/nominations", response_model=NominationResponse, status_code=201,
)
def create_nomination(
    election_pk: UUID,
    body: CreateNominationRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> NominationResponse:
    """
    Nominate a candidate for a position in an election (GOV-BR-034/035/036).
    One active nomination per (election, position, candidate) — enforced by
    uq_election_nomination_active_candidate, guarded here with SAVEPOINT.

    Candidate eligibility (GOV-BR-043) is validated before insert: must be
    an active NSS member, not ASSOCIATE/HONORARY, and not a PROBATIONARY
    member standing for Sakha President/Secretary — unless a Parichalak-
    approved exception (GOV-BR-043-A) applies.

    GOV-BR-043-A is deliberately not a field any GOVERNANCE_MANAGE admin can
    fill in: only the person currently holding the Parichalak seat may
    record it, and they do so by nominating the candidate themselves while
    authenticated as that seat's holder. The approver identity is therefore
    always derived from the authenticated actor (user.sangha_sevi_pk), never
    taken from the request body — body.probationary_exception_reason is the
    only client-supplied input for this exception.
    """
    with conn.cursor() as cur:
        org_pk = _get_election_org_or_404(cur, election_pk)
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, "record nominations")
        require_entity(cur, "position_master", str(body.position_master_pk), label="Position")
        require_entity(cur, "person", str(body.candidate_person_pk), label="Candidate")
        probationary_exception_approver_sangha_sevi_pk = (
            user.sangha_sevi_pk if body.probationary_exception_reason else None
        )
        _require_candidate_eligible(
            cur, body.candidate_person_pk, election_pk, body.position_master_pk,
            probationary_exception_approver_sangha_sevi_pk,
            body.probationary_exception_reason,
        )
        if body.proposer_person_pk:
            require_entity(cur, "person", str(body.proposer_person_pk), label="Proposer")

        nomination_date = parse_optional_date(body.nomination_date, "Nomination Date")

        actor = user.actor_pk
        cur.execute("SAVEPOINT nomination_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.election_nomination (
                    election_pk, position_master_pk, candidate_person_pk,
                    proposer_person_pk, nomination_date, remarks,
                    probationary_exception_approver_sangha_sevi_pk,
                    probationary_exception_reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING election_nomination_pk
                """,
                (str(election_pk), str(body.position_master_pk), str(body.candidate_person_pk),
                 str(body.proposer_person_pk) if body.proposer_person_pk else None,
                 nomination_date, body.remarks,
                 str(probationary_exception_approver_sangha_sevi_pk)
                     if probationary_exception_approver_sangha_sevi_pk else None,
                 body.probationary_exception_reason),
            )
            pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT nomination_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This candidate already has an active nomination for this position in this election.",
            )
        cur.execute("RELEASE SAVEPOINT nomination_insert")
        log_audit(cur, action="CREATE", table_name="election_nomination", record_pk=str(pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Created election nomination")

        cur.execute(f"{_NOMINATION_SELECT_SQL} WHERE n.election_nomination_pk = %s", (str(pk),))
        r = cur.fetchone()
    return _row_to_nomination(r)


@router.patch("/nominations/{election_nomination_pk}/status", response_model=NominationResponse)
def update_nomination_status(
    election_nomination_pk: UUID,
    body: UpdateNominationStatusRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> NominationResponse:
    """Change a nomination's status (GOV-BR-043): Nominated/Accepted/Withdrawn/Rejected."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.organization_pk
            FROM nss.election_nomination n
            JOIN nss.election e ON e.election_pk = n.election_pk
            WHERE n.election_nomination_pk = %s
            """,
            (str(election_nomination_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Nomination not found.")
        _require_scope_for_org_or_nss_wide(cur, user, row[0], "change nomination status")

        cur.execute(
            "UPDATE nss.election_nomination SET nomination_status = %s, updated_at = NOW() "
            "WHERE election_nomination_pk = %s",
            (body.nomination_status, str(election_nomination_pk)),
        )
        log_audit(cur, action="UPDATE", table_name="election_nomination",
                  record_pk=str(election_nomination_pk), actor_pk=user.actor_pk,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary=f"Set nomination status to {body.nomination_status}")

        cur.execute(
            f"{_NOMINATION_SELECT_SQL} WHERE n.election_nomination_pk = %s",
            (str(election_nomination_pk),),
        )
        r = cur.fetchone()
    return _row_to_nomination(r)


# ═════════════════════════════════════════════════════════════════════
# Election Vote
# ═════════════════════════════════════════════════════════════════════
#
# Dual-mode ballots (GOV-BR-045, resolved 2026-10-09):
#   - The participation ledger (election_vote_participation) ALWAYS records
#     the voter and is the authoritative one-member-one-vote-PER-POSITION
#     gate (GOV-BR-038) in both modes.
#   - The choice row (election_vote) stores the voter only for an OPEN
#     ballot; for a SECRET ballot it stores NULL, so the choice can never be
#     traced to a member through this table.
#   - Ballots are IMMUTABLE (DB trigger blocks UPDATE); the only way to clear
#     them is reset_ballots (hard DELETE), below.
#
#   *** SECRET-BALLOT AUDIT CAVEAT (flagged for owner decision) ***
#   The global AFTER-write audit trigger (15_audit_trigger.sql) records the
#   election_vote row — including election_nomination_pk — into
#   field_change_log together with the session actor. In SELF-SERVICE secret
#   voting the session actor IS the voter, so a reader of field_change_log
#   could correlate member → chosen nomination, which weakens secrecy at the
#   audit layer (the election_vote table itself stays anonymous). Closing
#   this fully means either excluding election_vote from field-level audit or
#   suppressing the actor on secret-ballot inserts — a change to the audit
#   subsystem, deferred pending owner confirmation.


def _resolve_nomination_position(cur, election_pk: UUID, nomination_pk: UUID) -> UUID:
    """Validate a nomination belongs to this election; return its position_master_pk."""
    cur.execute(
        "SELECT election_pk, position_master_pk FROM nss.election_nomination "
        "WHERE election_nomination_pk = %s AND is_active = TRUE",
        (str(nomination_pk),),
    )
    nom = cur.fetchone()
    if nom is None:
        raise HTTPException(status_code=404, detail="Nomination not found or inactive.")
    if str(nom[0]) != str(election_pk):
        raise HTTPException(
            status_code=422,
            detail="This nomination does not belong to this election.",
        )
    return nom[1]


def _election_is_secret(cur, election_pk: UUID) -> bool:
    cur.execute(
        "SELECT is_secret_ballot FROM nss.election WHERE election_pk = %s",
        (str(election_pk),),
    )
    row = cur.fetchone()
    return bool(row[0]) if row else False


def _require_election_voting_open(cur, election_pk: UUID) -> None:
    """Self-service voting is permitted only while the election is in VOTING."""
    cur.execute(
        "SELECT election_status FROM nss.election WHERE election_pk = %s",
        (str(election_pk),),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Election not found.")
    if row[0] != "VOTING":
        raise HTTPException(
            status_code=422,
            detail="Voting is not open for this election (its status is "
                   f"'{row[0]}', not 'VOTING').",
        )


def _cast_ballot(cur, *, election_pk: UUID, nomination_pk: UUID, position_master_pk: UUID,
                 voter_person_pk: UUID, is_secret: bool, remarks: str | None,
                 actor, user_account_pk):
    """
    Write a ballot in both modes and return (vote_pk, cast_at).

    1) INSERT the participation row (voter always recorded) — the one-vote
       gate; a duplicate raises 409.
    2) INSERT the choice row with the voter NULLed when the ballot is secret.
    Both inserts are application-audited.
    """
    cur.execute("SAVEPOINT ballot_participation")
    try:
        cur.execute(
            """
            INSERT INTO nss.election_vote_participation (
                election_pk, position_master_pk, voter_person_pk, voted_at, remarks
            ) VALUES (%s, %s, %s, NOW(), %s)
            RETURNING election_vote_participation_pk
            """,
            (str(election_pk), str(position_master_pk), str(voter_person_pk), remarks),
        )
        participation_pk = cur.fetchone()[0]
    except psycopg2.errors.UniqueViolation:
        cur.execute("ROLLBACK TO SAVEPOINT ballot_participation")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This voter has already cast a vote for this position in this election.",
        )
    cur.execute("RELEASE SAVEPOINT ballot_participation")

    stored_voter = None if is_secret else str(voter_person_pk)
    cur.execute(
        """
        INSERT INTO nss.election_vote (
            election_pk, election_nomination_pk, position_master_pk,
            voter_person_pk, cast_at, remarks
        ) VALUES (%s, %s, %s, %s, NOW(), %s)
        RETURNING election_vote_pk, cast_at
        """,
        (str(election_pk), str(nomination_pk), str(position_master_pk),
         stored_voter, remarks),
    )
    vote_pk, cast_at = cur.fetchone()

    log_audit(cur, action="CREATE", table_name="election_vote", record_pk=str(vote_pk),
              actor_pk=actor, actor_user_account_pk=str(user_account_pk),
              module="governance",
              summary="Recorded secret ballot" if is_secret else "Recorded election vote")
    log_audit(cur, action="CREATE", table_name="election_vote_participation",
              record_pk=str(participation_pk), actor_pk=actor,
              actor_user_account_pk=str(user_account_pk), module="governance",
              summary="Recorded voter participation")
    return vote_pk, cast_at


@router.post("/elections/{election_pk}/votes", response_model=VoteResponse, status_code=201)
def cast_vote(
    election_pk: UUID,
    body: CastVoteRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> VoteResponse:
    """
    Officer-recorded ballot (GOVERNANCE_MANAGE): an election officer records a
    named member's ballot. For member self-service, see POST .../votes/self.

    Honours the election's ballot mode (GOV-BR-045): the voter is always
    recorded in the participation ledger (the one-vote gate, GOV-BR-038); the
    choice row stores the voter only for an OPEN election, NULL for a SECRET
    one. Voter eligibility (GOV-BR-043: active NSS member, not Associate/
    Honorary) is validated before insert.
    """
    with conn.cursor() as cur:
        org_pk = _get_election_org_or_404(cur, election_pk)
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, "record votes")

        position_master_pk = _resolve_nomination_position(cur, election_pk, body.election_nomination_pk)
        require_entity(cur, "person", str(body.voter_person_pk), label="Voter")
        _require_voter_eligible(cur, body.voter_person_pk, election_pk)
        is_secret = _election_is_secret(cur, election_pk)

        vote_pk, cast_at = _cast_ballot(
            cur, election_pk=election_pk, nomination_pk=body.election_nomination_pk,
            position_master_pk=position_master_pk, voter_person_pk=body.voter_person_pk,
            is_secret=is_secret, remarks=body.remarks, actor=user.actor_pk,
            user_account_pk=user.user_account_pk,
        )

    return VoteResponse(
        election_vote_pk=vote_pk, election_pk=election_pk,
        election_nomination_pk=body.election_nomination_pk,
        position_master_pk=position_master_pk,
        voter_person_pk=None if is_secret else body.voter_person_pk,
        is_secret_ballot=is_secret, cast_at=cast_at, remarks=body.remarks,
    )


@router.post("/elections/{election_pk}/votes/self", response_model=VoteResponse, status_code=201)
def self_cast_vote(
    election_pk: UUID,
    body: SelfCastVoteRequest,
    user: UserContext = Depends(get_current_user),
    conn=Depends(get_write_connection),
) -> VoteResponse:
    """
    Member self-service ballot (GOV-BR-045): the authenticated member casts
    their OWN vote. Gated on a valid login (NOT GOVERNANCE_MANAGE — ordinary
    members hold no admin role) plus bylaw eligibility (GOV-BR-043: active NSS
    member, not Associate/Honorary) and the election being in its VOTING
    window. The voter is taken from the session, never from the request body,
    so a member can only ever cast their own ballot.

    Secrecy follows the election's mode: for a SECRET election the choice row
    is anonymous (NULL voter); the voter is recorded only in the participation
    ledger, which also enforces one vote per position (GOV-BR-038).
    """
    if user.person_pk is None:
        raise HTTPException(
            status_code=403,
            detail="Your login is not linked to a member record, so you cannot vote.",
        )
    with conn.cursor() as cur:
        _get_election_org_or_404(cur, election_pk)
        _require_election_voting_open(cur, election_pk)
        position_master_pk = _resolve_nomination_position(cur, election_pk, body.election_nomination_pk)
        _require_voter_eligible(cur, user.person_pk, election_pk)
        is_secret = _election_is_secret(cur, election_pk)

        vote_pk, cast_at = _cast_ballot(
            cur, election_pk=election_pk, nomination_pk=body.election_nomination_pk,
            position_master_pk=position_master_pk, voter_person_pk=user.person_pk,
            is_secret=is_secret, remarks=body.remarks, actor=user.actor_pk,
            user_account_pk=user.user_account_pk,
        )

    return VoteResponse(
        election_vote_pk=vote_pk, election_pk=election_pk,
        election_nomination_pk=body.election_nomination_pk,
        position_master_pk=position_master_pk,
        voter_person_pk=None if is_secret else user.person_pk,
        is_secret_ballot=is_secret, cast_at=cast_at, remarks=body.remarks,
    )


@router.post("/elections/{election_pk}/votes/reset", response_model=ResetBallotsResponse)
def reset_ballots(
    election_pk: UUID,
    body: ResetBallotsRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> ResetBallotsResponse:
    """
    Clear cast ballots for an election (GOV-BR-045 reset flow). Ballots are
    immutable, so reset hard-DELETEs the choice rows and participation records
    — this is the only path that may remove them, and the delete is captured
    by the audit trigger.

    Two authorities (asserted by reset_mode and recorded for audit):
      - PRESIDENT_UNILATERAL — the President resets on their own authority.
      - ADMIN_WITH_PRESIDENT_APPROVAL — an administrator resets with the
        President's recorded approval (president_person_pk required).

    Scope: the whole election, or a single position when position_master_pk is
    supplied.
    """
    if body.reset_mode == "ADMIN_WITH_PRESIDENT_APPROVAL" and body.president_person_pk is None:
        raise HTTPException(
            status_code=422,
            detail="president_person_pk is required when reset_mode is "
                   "ADMIN_WITH_PRESIDENT_APPROVAL (the President's approval must "
                   "be recorded).",
        )

    with conn.cursor() as cur:
        org_pk = _get_election_org_or_404(cur, election_pk)
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, "reset ballots")
        if body.president_person_pk is not None:
            require_entity(cur, "person", str(body.president_person_pk), label="Approving President")

        params: list = [str(election_pk)]
        pos_clause = ""
        if body.position_master_pk is not None:
            pos_clause = " AND position_master_pk = %s"
            params.append(str(body.position_master_pk))

        cur.execute(
            f"DELETE FROM nss.election_vote WHERE election_pk = %s{pos_clause}",
            params,
        )
        votes_deleted = cur.rowcount
        cur.execute(
            f"DELETE FROM nss.election_vote_participation WHERE election_pk = %s{pos_clause}",
            params,
        )
        participation_deleted = cur.rowcount

        scope = (
            f"position {body.position_master_pk}" if body.position_master_pk
            else "all positions"
        )
        approver = (
            f"; president approval person_pk={body.president_person_pk}"
            if body.president_person_pk else ""
        )
        log_audit(
            cur, action="DELETE", table_name="election_vote", record_pk=str(election_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="governance",
            summary=(f"Reset ballots ({body.reset_mode}) for {scope}: "
                     f"{votes_deleted} vote(s), {participation_deleted} participation "
                     f"record(s). Reason: {body.reason}{approver}"),
        )

    return ResetBallotsResponse(
        election_pk=election_pk, position_master_pk=body.position_master_pk,
        votes_deleted=votes_deleted, participation_deleted=participation_deleted,
        message=(f"Reset complete ({body.reset_mode}): removed {votes_deleted} "
                 f"ballot(s) and {participation_deleted} participation record(s)."),
    )


@router.get("/elections/{election_pk}/tally", response_model=TallyResponse)
def get_tally(
    election_pk: UUID,
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> TallyResponse:
    """Per-nomination vote counts for an election, grouped by position."""
    with conn.cursor() as cur:
        org_pk = _get_election_org_or_404(cur, election_pk)
        allowed = actor_scope_org_pks(cur, user)
        if allowed is not None and org_pk is not None and str(org_pk) not in allowed:
            raise HTTPException(status_code=403, detail="This election is outside your admin scope.")
        cur.execute(
            f"""
            SELECT n.position_master_pk, pm.position_name, n.election_nomination_pk,
                   n.candidate_person_pk, {_person_name_sql('cp')},
                   COUNT(v.election_vote_pk) AS vote_count
            FROM nss.election_nomination n
            JOIN nss.position_master pm ON pm.position_master_pk = n.position_master_pk
            JOIN nss.person cp ON cp.person_pk = n.candidate_person_pk
            LEFT JOIN nss.election_vote v
                ON v.election_nomination_pk = n.election_nomination_pk AND v.is_active = TRUE
            WHERE n.election_pk = %s AND n.is_active = TRUE
            GROUP BY n.position_master_pk, pm.position_name, n.election_nomination_pk,
                     n.candidate_person_pk, cp.first_name, cp.middle_name, cp.last_name
            ORDER BY pm.position_name, vote_count DESC
            """,
            (str(election_pk),),
        )
        rows = cur.fetchall()
    items = [
        TallyRow(
            position_master_pk=r[0], position_name=r[1], election_nomination_pk=r[2],
            candidate_person_pk=r[3], candidate_name=r[4] if r[4] and r[4].strip() else None,
            vote_count=r[5],
        )
        for r in rows
    ]
    return TallyResponse(items=items)


# ═════════════════════════════════════════════════════════════════════
# Election Result
# ═════════════════════════════════════════════════════════════════════

_RESULT_SELECT_SQL = f"""
    SELECT res.election_result_pk, res.election_pk, res.position_master_pk, pm.position_name,
           res.winning_nomination_pk, res.winner_person_pk, {_person_name_sql('wp')},
           res.vote_count, res.result_status, res.declared_at, res.remarks, res.is_active
    FROM nss.election_result res
    JOIN nss.position_master pm ON pm.position_master_pk = res.position_master_pk
    LEFT JOIN nss.person wp ON wp.person_pk = res.winner_person_pk
"""


def _row_to_result(r) -> ResultResponse:
    return ResultResponse(
        election_result_pk=r[0], election_pk=r[1], position_master_pk=r[2], position_name=r[3],
        winning_nomination_pk=r[4], winner_person_pk=r[5],
        winner_name=r[6] if r[6] and r[6].strip() else None,
        vote_count=r[7], result_status=r[8], declared_at=r[9], remarks=r[10], is_active=r[11],
    )


@router.get("/elections/{election_pk}/results", response_model=ResultListResponse)
def list_results(
    election_pk: UUID,
    include_inactive: bool = Query(False),
    user: UserContext = Depends(
        require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")
    ),
    conn=Depends(get_connection),
) -> ResultListResponse:
    """List declared results (one per decided position) for an election."""
    with conn.cursor() as cur:
        org_pk = _get_election_org_or_404(cur, election_pk)
        allowed = actor_scope_org_pks(cur, user)
        if allowed is not None and org_pk is not None and str(org_pk) not in allowed:
            raise HTTPException(status_code=403, detail="This election is outside your admin scope.")
        clause = "res.election_pk = %s" + ("" if include_inactive else " AND res.is_active = TRUE")
        cur.execute(f"{_RESULT_SELECT_SQL} WHERE {clause}", (str(election_pk),))
        rows = cur.fetchall()
    items = [_row_to_result(r) for r in rows]
    return ResultListResponse(items=items, total=len(items))


@router.post("/elections/{election_pk}/results", response_model=ResultResponse, status_code=201)
def declare_result(
    election_pk: UUID,
    body: DeclareResultRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> ResultResponse:
    """
    Declare the outcome for one position in an election (GOV-BR-039/046/047/048).

    Valid in the VOTING or COMPLETED status for an ELECTION cycle (the ballot
    has been held, so there is a tally to declare from), and in the NOMINATION
    or COMPLETED status for a NOMINATION cycle (consensus/selection, no ballot
    — GOV-BR-042). A NOMINATION cycle may only produce UNCONTESTED or VACANT
    outcomes, and never carries a vote_count.

    Any named winner must hold an ACCEPTED nomination for that same position
    in this election (GOV-BR-046). A result with no winner is how a TIE or a
    VACANT seat is recorded.

    Deliberately does NOT write body_member_assignment — that hand-off is a
    separate, explicit step: POST /results/{pk}/apply (SOL-GOV-004 §13.5).
    One active result per (election, position) — enforced by
    uq_election_result_active_position, guarded here with SAVEPOINT.
    """
    with conn.cursor() as cur:
        org_pk = _get_election_org_or_404(cur, election_pk)
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, "declare election results")
        require_entity(cur, "position_master", str(body.position_master_pk), label="Position")
        if body.winning_nomination_pk:
            require_entity(cur, "election_nomination", str(body.winning_nomination_pk), label="Nomination")
        if body.winner_person_pk:
            require_entity(cur, "person", str(body.winner_person_pk), label="Winner")

        # ── Gate on the cycle's mode and status ─────────────────────────
        # Without this, a winner could be declared on a SCHEDULED election
        # with no nominations and no ballot ever held.
        cur.execute(
            "SELECT election_status, election_type FROM nss.election WHERE election_pk = %s",
            (str(election_pk),),
        )
        election_status, election_type = cur.fetchone()
        declarable_in = (
            {"NOMINATION", "COMPLETED"} if election_type == "NOMINATION"
            else {"VOTING", "COMPLETED"}
        )
        if election_status not in declarable_in:
            if election_type == "NOMINATION":
                hint = ("A Nomination cycle declares its outcomes once nominations "
                        "are in — advance it to Nomination first.")
            else:
                hint = ("An Election cycle declares its outcomes from the ballot — "
                        "advance it to Voting first.")
            raise HTTPException(
                status_code=422,
                detail=f"Results cannot be declared while this cycle is "
                       f"{election_status}. {hint}",
            )

        if election_type == "NOMINATION":
            if body.result_status not in ("UNCONTESTED", "VACANT"):
                raise HTTPException(
                    status_code=422,
                    detail="A Nomination (consensus/selection) cycle holds no ballot, "
                           "so its outcome must be Uncontested (the selected member) "
                           "or Vacant (no selection made). "
                           f"'{body.result_status}' requires a ballot.",
                )
            if body.vote_count is not None:
                raise HTTPException(
                    status_code=422,
                    detail="A Nomination (consensus/selection) cycle casts no ballots, "
                           "so it cannot carry a vote count.",
                )

        # ── GOV-BR-046: a winner must be a standing candidate ───────────
        if body.winner_person_pk:
            cur.execute(
                """
                SELECT 1
                FROM nss.election_nomination n
                WHERE n.election_pk = %s
                  AND n.position_master_pk = %s
                  AND n.candidate_person_pk = %s
                  AND n.nomination_status = 'ACCEPTED'
                  AND n.is_active = TRUE
                """,
                (str(election_pk), str(body.position_master_pk), str(body.winner_person_pk)),
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=422,
                    detail="The declared winner has no accepted nomination for this "
                           "position in this election (GOV-BR-046). Nominate the "
                           "candidate and set the nomination to Accepted first.",
                )

        declared_at = body.declared_at
        if declared_at:
            try:
                declared_at = datetime.fromisoformat(declared_at)
            except ValueError:
                raise HTTPException(status_code=422, detail="declared_at must be a valid ISO datetime.")

        actor = user.actor_pk
        cur.execute("SAVEPOINT result_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.election_result (
                    election_pk, position_master_pk, winning_nomination_pk, winner_person_pk,
                    vote_count, result_status, declared_at, remarks
                ) VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), %s)
                RETURNING election_result_pk
                """,
                (str(election_pk), str(body.position_master_pk),
                 str(body.winning_nomination_pk) if body.winning_nomination_pk else None,
                 str(body.winner_person_pk) if body.winner_person_pk else None,
                 body.vote_count, body.result_status, declared_at, body.remarks),
            )
            pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT result_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A result has already been declared for this position in this election.",
            )
        cur.execute("RELEASE SAVEPOINT result_insert")
        log_audit(cur, action="CREATE", table_name="election_result", record_pk=str(pk),
                  actor_pk=actor, actor_user_account_pk=str(user.user_account_pk),
                  module="governance", summary="Declared election result")

        cur.execute(f"{_RESULT_SELECT_SQL} WHERE res.election_result_pk = %s", (str(pk),))
        r = cur.fetchone()
    return _row_to_result(r)


@router.post("/results/{election_result_pk}/apply", response_model=ApplyResultResponse)
def apply_result(
    election_result_pk: UUID,
    body: ApplyResultRequest,
    user: UserContext = Depends(require_permission("GOVERNANCE_MANAGE")),
    conn=Depends(get_write_connection),
) -> ApplyResultResponse:
    """
    Hand off a declared result into a live body_member_assignment
    (SOL-GOV-004 §13.5, GOV-BR-039) — the explicit, separate step that
    turns an electoral fact into a governance fact. Only a result with a
    winner_person_pk (DECLARED/UNCONTESTED with a winner) can be applied;
    TIE/VACANT/CANCELLED results have nothing to assign.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT res.election_pk, res.position_master_pk, res.winner_person_pk,
                   res.result_status, e.body_master_pk, e.organization_pk
            FROM nss.election_result res
            JOIN nss.election e ON e.election_pk = res.election_pk
            WHERE res.election_result_pk = %s
            """,
            (str(election_result_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Election result not found.")
        election_pk, position_master_pk, winner_person_pk, result_status, body_master_pk, org_pk = row
        _require_scope_for_org_or_nss_wide(cur, user, org_pk, "apply election results")

        if not winner_person_pk:
            raise HTTPException(
                status_code=422,
                detail=f"This result (status {result_status}) has no winner to assign.",
            )
        # The assignment requires an active membership. If the caller named a
        # Sangha Sevi, validate it belongs to the winner and is active;
        # otherwise resolve the winner's single active Sangha Sevi record.
        if body.sangha_sevi_pk:
            _require_active_membership(cur, winner_person_pk, body.sangha_sevi_pk)
            sangha_sevi_pk = body.sangha_sevi_pk
        else:
            sangha_sevi_pk = _resolve_active_membership(cur, winner_person_pk)

        _require_valid_composition(
            cur, body_master_pk, _get_body_org_or_404(cur, body_master_pk),
            position_master_pk, winner_person_pk,
        )

        effective_from = parse_optional_date(body.effective_from, "Effective From") or date.today()

        actor = user.actor_pk
        cur.execute("SAVEPOINT apply_result_insert")
        try:
            cur.execute(
                """
                INSERT INTO nss.body_member_assignment (
                    body_master_pk, position_master_pk, person_pk, sangha_sevi_pk,
                    effective_from, assignment_reference, remarks
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING body_member_assignment_pk
                """,
                (str(body_master_pk), str(position_master_pk), str(winner_person_pk),
                 str(sangha_sevi_pk),
                 effective_from, body.assignment_reference or f"ELECTION_RESULT:{election_result_pk}",
                 f"Applied from election result {election_result_pk}."),
            )
            assignment_pk = cur.fetchone()[0]
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT apply_result_insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The winner already holds this position in this body in an "
                    "active, open-ended assignment. End the existing one first."
                ),
            )
        cur.execute("RELEASE SAVEPOINT apply_result_insert")
        log_audit(cur, action="CREATE", table_name="body_member_assignment",
                  record_pk=str(assignment_pk), actor_pk=actor,
                  actor_user_account_pk=str(user.user_account_pk),
                  module="governance",
                  summary=f"Applied election result {election_result_pk} to body member assignment")

    return ApplyResultResponse(
        body_member_assignment_pk=assignment_pk, election_result_pk=election_result_pk,
        message="Election result applied — body member assignment created.",
    )
