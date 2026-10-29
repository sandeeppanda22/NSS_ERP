"""
Foundation API router — Tier 1 Foundation endpoints.

17 GET (read) endpoints plus master-data / settings / sequences write
endpoints, across 11 Foundation tables. All routes require authentication
(FOUNDATION_VIEW to read, FOUNDATION_MANAGE to write). Reads use the
nss_db_backend pool (SELECT-only); writes use the nss_db_writer pool.

Endpoint groups:
  - Master Data:      categories, master-data
  - System Config:    settings, sequences
  - Geographic:       countries, states, districts, cities, postal-codes,
                      post-offices, postal-code-mappings
  - Member-Assisted:  districts/postal-codes/post-offices/city-villages
                      "propose" endpoints (SOL-ARCH-010 Amendment,
                      2026-10-03) — any authenticated member may submit a
                      value the system hasn't seen yet; it lands PENDING
                      and is invisible to the Geographic lookups above
                      until a FOUNDATION_MANAGE admin reviews it (see
                      api/routers/geo_approval.py).
  - Runtime:          documents

field_change_log is intentionally excluded from Tier 1 — audit data
requires authentication. Deferred to Tier 5.
"""

import re
from uuid import UUID

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.database import get_connection
from api.dependencies.auth import get_write_connection
from api.dependencies.auth import get_current_user
from api.dependencies.rbac import require_permission
from api.helpers import log_audit, require_entity, row_to_model, rows_to_models
from api.services.rbac_service import UserContext
from api.schemas.foundation import (
    CategoryResponse,
    CityVillageResponse,
    CountryResponse,
    CreateFestivalCalendarDateRequest,
    CreateMasterDataRequest,
    CreateSequenceRequest,
    CreateSettingRequest,
    DistrictResponse,
    DocumentResponse,
    FestivalCalendarDateResponse,
    FestivalMasterResponse,
    MasterDataResponse,
    PendingCityVillageResponse,
    PendingDistrictResponse,
    PendingPostalCodeResponse,
    PendingPostOfficeResponse,
    PostalCodeMappingResponse,
    PostalCodeResponse,
    PostOfficeResponse,
    ProposeCityVillageRequest,
    ProposeDistrictRequest,
    ProposePostalCodeRequest,
    ProposePostOfficeRequest,
    SakhaPostalCodeResponse,
    SequenceResponse,
    SettingResponse,
    StateResponse,
    UpdateFestivalCalendarDateRequest,
    UpdateMasterDataRequest,
    UpdateSequenceRequest,
    UpdateSettingRequest,
)

router = APIRouter(prefix="/api/v1/foundation", tags=["foundation"])


# ── Shared query helpers ─────────────────────────────────────────────────
# Factored out so a second, differently-authenticated caller (the public
# self-registration reference-data endpoint, api/routers/registration.py)
# can reuse the exact same SQL rather than a duplicated copy that could
# drift. Each authenticated route below is now a thin wrapper over one of
# these; behavior is unchanged.

def fetch_master_data(cur, category_code: str | None = None, category_pk=None):
    base_sql = """
        SELECT md.master_data_pk, md.master_category_pk,
               mc.category_code, mc.category_name,
               md.value_code, md.value_name,
               md.description, md.applicable_modules,
               md.display_order, md.is_active
        FROM   nss.master_data md
        JOIN   nss.master_category mc
               ON mc.master_category_pk = md.master_category_pk
        WHERE  md.is_active = TRUE
          AND  mc.is_active = TRUE
    """
    params: list = []
    if category_pk is not None:
        base_sql += " AND md.master_category_pk = %s"
        params.append(str(category_pk))
    elif category_code is not None:
        base_sql += " AND mc.category_code = %s"
        params.append(category_code)
    base_sql += """
        ORDER BY mc.display_order, mc.category_name,
                 md.display_order, md.value_name
    """
    cur.execute(base_sql, tuple(params))
    return rows_to_models(cur, MasterDataResponse)


def fetch_countries(cur):
    cur.execute("""
        SELECT country_pk, country_code, country_name,
               display_order, is_active
        FROM   nss.country
        WHERE  is_active = TRUE
        ORDER BY display_order, country_name
    """)
    return rows_to_models(cur, CountryResponse)


def fetch_states(cur, country_pk=None):
    base_sql = """
        SELECT s.state_pk, s.country_pk,
               c.country_code, c.country_name,
               s.state_code, s.state_name,
               s.display_order, s.is_active
        FROM   nss.state s
        JOIN   nss.country c ON c.country_pk = s.country_pk
        WHERE  s.is_active = TRUE
          AND  c.is_active = TRUE
    """
    params: list = []
    if country_pk is not None:
        base_sql += " AND s.country_pk = %s"
        params.append(str(country_pk))
    base_sql += " ORDER BY c.display_order, s.display_order, s.state_name"
    cur.execute(base_sql, tuple(params))
    return rows_to_models(cur, StateResponse)


def fetch_districts(cur, state_pk=None):
    base_sql = """
        SELECT d.district_pk, d.state_pk,
               s.state_name,
               d.district_code, d.district_name,
               d.display_order, d.is_active
        FROM   nss.district d
        JOIN   nss.state s ON s.state_pk = d.state_pk
        WHERE  d.is_active = TRUE
          AND  s.is_active = TRUE
          AND  d.entry_status = 'APPROVED'
    """
    params: list = []
    if state_pk is not None:
        base_sql += " AND d.state_pk = %s"
        params.append(str(state_pk))
    base_sql += " ORDER BY s.state_name, d.display_order, d.district_name"
    cur.execute(base_sql, tuple(params))
    return rows_to_models(cur, DistrictResponse)


def fetch_cities(cur, district_pk=None, postal_code_pk=None):
    """
    Shared Cities/Villages query — list_cities() (Foundation, authenticated)
    and get_register_cities() (public registration cascade) both route
    through here (SOL-ARCH-010 Amendment, 2026-10-01).
    """
    base_sql = """
        SELECT cv.city_village_pk, cv.district_pk,
               d.district_name,
               cv.city_village_code, cv.city_village_name,
               cv.city_village_type,
               cv.postal_code_pk, pc.postal_code,
               cv.display_order, cv.is_active
        FROM   nss.city_village cv
        LEFT JOIN nss.district d ON d.district_pk = cv.district_pk
        LEFT JOIN nss.postal_code pc ON pc.postal_code_pk = cv.postal_code_pk
        WHERE  cv.is_active = TRUE
          AND  cv.entry_status = 'APPROVED'
          AND  (d.district_pk IS NULL OR d.is_active = TRUE)
    """
    params: list = []
    if district_pk is not None:
        base_sql += " AND cv.district_pk = %s"
        params.append(str(district_pk))
    if postal_code_pk is not None:
        base_sql += " AND cv.postal_code_pk = %s"
        params.append(str(postal_code_pk))
    base_sql += " ORDER BY d.district_name, cv.display_order, cv.city_village_name"
    cur.execute(base_sql, tuple(params))
    return rows_to_models(cur, CityVillageResponse)


def fetch_postal_codes(cur, state_pk=None, country_pk=None, district_pk=None, q=None):
    """
    Simplified Geography Model (2026-10-02): nss.post_office is retired —
    postal_code is now a single state-scoped row per PIN (one row
    globally, unique on postal_code alone; no per-country/per-office
    duplicates to disambiguate, so there is no office_count or
    post_office_name any more).

    postal_code still has no direct district_pk column (a PIN is a
    state-scoped postal unit, not a revenue-district one), so "postal
    codes in district X" is answered through nss.city_village, which
    carries the direct district_pk anchor alongside postal_code_pk — the
    same join fetch_cities() uses in the other direction.

    country_pk is accepted for backward compatibility with callers (e.g.
    the public registration cascade) but postal_code itself has no
    country_pk column any more — it's resolved via state.country_pk.

    *q* now only matches the PIN digits — the office-name search is
    gone along with nss.post_office.
    """
    base_sql = """
        SELECT pc.postal_code_pk, pc.state_pk,
               s.state_name, s.country_pk,
               pc.postal_code, pc.is_active
        FROM   nss.postal_code pc
        JOIN   nss.state s ON s.state_pk = pc.state_pk
        WHERE  pc.is_active = TRUE
          AND  pc.entry_status = 'APPROVED'
    """
    params: list = []
    if district_pk is not None:
        base_sql += """
            AND EXISTS (
                SELECT 1 FROM nss.city_village cv
                WHERE  cv.postal_code_pk = pc.postal_code_pk
                  AND  cv.is_active = TRUE
                  AND  cv.entry_status = 'APPROVED'
                  AND  cv.district_pk = %s
            )
        """
        params.append(str(district_pk))
    if state_pk is not None:
        base_sql += " AND pc.state_pk = %s"
        params.append(str(state_pk))
    elif country_pk is not None:
        base_sql += " AND s.country_pk = %s"
        params.append(str(country_pk))
    if q:
        base_sql += " AND pc.postal_code LIKE %s"
        params.append(f"{q}%")
    base_sql += " ORDER BY pc.postal_code"
    cur.execute(base_sql, tuple(params))
    return rows_to_models(cur, PostalCodeResponse)


def fetch_post_offices(cur, postal_code_pk):
    """
    Post offices under a PIN (Member-Assisted Geographic Entry,
    SOL-ARCH-010 Amendment 2026-10-03): nss.post_office is reinstated — a
    single PIN can carry several post offices (one HO + several SO/BO).
    Only APPROVED, active rows are returned — PENDING/CORRECTED rows stay
    quarantined until an admin reviews them (api/routers/geo_approval.py).
    """
    cur.execute(
        """
        SELECT po.post_office_pk, po.postal_code_pk,
               pc.postal_code,
               po.post_office_name, po.display_order, po.is_active
        FROM   nss.post_office po
        JOIN   nss.postal_code pc ON pc.postal_code_pk = po.postal_code_pk
        WHERE  po.is_active = TRUE
          AND  po.entry_status = 'APPROVED'
          AND  pc.is_active = TRUE
          AND  pc.entry_status = 'APPROVED'
          AND  po.postal_code_pk = %s
        ORDER BY po.display_order, po.post_office_name
        """,
        (str(postal_code_pk),),
    )
    return rows_to_models(cur, PostOfficeResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 1. MASTER DATA SUBSYSTEM
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[CategoryResponse]:
    """List all active master categories."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT master_category_pk, category_code, category_name,
                   description, display_order, is_active
            FROM   nss.master_category
            WHERE  is_active = TRUE
            ORDER BY display_order, category_name
        """)
        return rows_to_models(cur, CategoryResponse)


@router.get("/categories/{master_category_pk}", response_model=CategoryResponse)
def get_category(
    master_category_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> CategoryResponse:
    """Get a single master category by PK."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT master_category_pk, category_code, category_name,
                   description, display_order, is_active
            FROM   nss.master_category
            WHERE  master_category_pk = %s AND is_active = TRUE
        """, (str(master_category_pk),))
        result = row_to_model(cur, CategoryResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Category not found")
        return result


@router.get("/master-data", response_model=list[MasterDataResponse])
def list_master_data(
    category_code: str | None = Query(None, description="Filter by category code"),
    category_pk: UUID | None = Query(None, description="Filter by category PK"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[MasterDataResponse]:
    """
    List all active master data values.

    Optionally filter by category_code or category_pk.
    If both are provided, category_pk takes precedence.
    """
    with conn.cursor() as cur:
        return fetch_master_data(cur, category_code, category_pk)


@router.get("/master-data/{master_data_pk}", response_model=MasterDataResponse)
def get_master_data(
    master_data_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> MasterDataResponse:
    """Get a single master data value by PK (with category context)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT md.master_data_pk, md.master_category_pk,
                   mc.category_code, mc.category_name,
                   md.value_code, md.value_name,
                   md.description, md.applicable_modules,
                   md.display_order, md.is_active
            FROM   nss.master_data md
            JOIN   nss.master_category mc
                   ON mc.master_category_pk = md.master_category_pk
            WHERE  md.master_data_pk = %s
              AND  md.is_active = TRUE
              AND  mc.is_active = TRUE
        """, (str(master_data_pk),))
        result = row_to_model(cur, MasterDataResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Master data value not found")
        return result


_MASTER_DATA_SELECT = """
    SELECT md.master_data_pk, md.master_category_pk,
           mc.category_code, mc.category_name,
           md.value_code, md.value_name,
           md.description, md.applicable_modules,
           md.display_order, md.is_active
    FROM   nss.master_data md
    JOIN   nss.master_category mc
           ON mc.master_category_pk = md.master_category_pk
    WHERE  md.master_data_pk = %s
"""


@router.post("/master-data", response_model=MasterDataResponse, status_code=status.HTTP_201_CREATED)
def create_master_data(
    body: CreateMasterDataRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_MANAGE")),
) -> MasterDataResponse:
    """
    Add a new value to an existing master-data category. Requires FOUNDATION_MANAGE.

    value_code must be unique within the category. applicable_modules NULL
    means the value applies to all modules.
    """
    category_code = body.category_code.strip().upper()
    value_code = body.value_code.strip().upper()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT master_category_pk FROM nss.master_category WHERE category_code = %s AND is_active = TRUE",
            (category_code,),
        )
        cat = cur.fetchone()
        if cat is None:
            raise HTTPException(status_code=404, detail=f"Category '{category_code}' not found.")
        category_pk = cat[0]

        cur.execute(
            "SELECT 1 FROM nss.master_data WHERE master_category_pk = %s AND value_code = %s",
            (str(category_pk), value_code),
        )
        if cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail=f"Value '{value_code}' already exists in category '{category_code}'.")

        cur.execute(
            """
            INSERT INTO nss.master_data
                (master_category_pk, value_code, value_name, description,
                 applicable_modules, display_order)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING master_data_pk
            """,
            (
                str(category_pk), value_code, body.value_name.strip(),
                (body.description.strip() if body.description else None) or None,
                body.applicable_modules if body.applicable_modules else None,
                body.display_order,
            ),
        )
        new_pk = cur.fetchone()[0]

        log_audit(
            cur, action="CREATE", table_name="master_data", record_pk=str(new_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Created master data {category_code}.{value_code}",
        )

        cur.execute(_MASTER_DATA_SELECT, (str(new_pk),))
        return row_to_model(cur, MasterDataResponse)


@router.patch("/master-data/{master_data_pk}", response_model=MasterDataResponse)
def update_master_data(
    master_data_pk: UUID,
    body: UpdateMasterDataRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_MANAGE")),
) -> MasterDataResponse:
    """
    Edit an existing master-data value. Requires FOUNDATION_MANAGE.

    value_code and category are immutable (value_code is referenced by other
    tables). Editable: value_name, description, display_order, applicable_modules.
    """
    updates: dict = {}
    if body.value_name is not None:
        updates["value_name"] = body.value_name.strip()
    if body.description is not None:
        updates["description"] = body.description.strip() or None
    if body.display_order is not None:
        updates["display_order"] = body.display_order
    if body.applicable_modules is not None:
        updates["applicable_modules"] = body.applicable_modules or None

    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update.")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM nss.master_data WHERE master_data_pk = %s AND is_active = TRUE",
            (str(master_data_pk),),
        )
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Master data value not found.")

        set_parts = ["updated_at = NOW()"]
        params: list = []
        for col, val in updates.items():
            set_parts.append(f"{col} = %s")
            params.append(val)
        params.append(str(master_data_pk))

        cur.execute(
            f"UPDATE nss.master_data SET {', '.join(set_parts)} WHERE master_data_pk = %s",
            params,
        )

        log_audit(
            cur, action="UPDATE", table_name="master_data", record_pk=str(master_data_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary="Updated master data value",
        )

        cur.execute(_MASTER_DATA_SELECT, (str(master_data_pk),))
        return row_to_model(cur, MasterDataResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 2. SYSTEM CONFIGURATION SUBSYSTEM
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/settings", response_model=list[SettingResponse])
def list_settings(
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[SettingResponse]:
    """List all active system settings."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT system_setting_pk, setting_key, setting_value,
                   description, data_type, is_active
            FROM   nss.system_setting
            WHERE  is_active = TRUE
            ORDER BY setting_key
        """)
        return rows_to_models(cur, SettingResponse)


@router.get("/settings/{setting_key}", response_model=SettingResponse)
def get_setting_by_key(
    setting_key: str,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> SettingResponse:
    """
    Get a single system setting by its business key.

    Settings are consumed by code using their key name
    (e.g., CURRENT_MEMBERSHIP_YEAR), not their UUID.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT system_setting_pk, setting_key, setting_value,
                   description, data_type, is_active
            FROM   nss.system_setting
            WHERE  setting_key = %s AND is_active = TRUE
        """, (setting_key,))
        result = row_to_model(cur, SettingResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Setting not found")
        return result


_VALID_DATA_TYPES = {"STRING", "INTEGER", "BOOLEAN", "DATE", "JSON"}


def _validate_setting_value(value: str, data_type: str) -> str:
    """
    Validate `value` against `data_type` and return a normalized string
    to persist. Raises HTTP 422 on invalid input.
    """
    dt = (data_type or "STRING").upper()
    v = value.strip()
    if dt == "INTEGER":
        try:
            return str(int(v))
        except ValueError:
            raise HTTPException(status_code=422, detail="Value must be a whole number for an INTEGER setting.")
    if dt == "BOOLEAN":
        low = v.lower()
        if low in ("true", "1", "yes"):
            return "true"
        if low in ("false", "0", "no"):
            return "false"
        raise HTTPException(status_code=422, detail="Value must be true or false for a BOOLEAN setting.")
    if dt == "DATE":
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                datetime.strptime(v, fmt)
                return v
            except ValueError:
                continue
        raise HTTPException(status_code=422, detail="Value must be a valid date (DD/MM/YYYY) for a DATE setting.")
    if dt == "JSON":
        try:
            json.loads(v)
            return v
        except ValueError:
            raise HTTPException(status_code=422, detail="Value must be valid JSON for a JSON setting.")
    return v  # STRING


@router.patch("/settings/{setting_key}", response_model=SettingResponse)
def update_setting(
    setting_key: str,
    body: UpdateSettingRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_MANAGE")),
) -> SettingResponse:
    """
    Update an existing system setting's value (and optionally its description).

    The setting_key and data_type are immutable — the value is validated
    against the stored data_type. Requires FOUNDATION_MANAGE.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT system_setting_pk, data_type
            FROM   nss.system_setting
            WHERE  setting_key = %s AND is_active = TRUE
            """,
            (setting_key,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Setting not found.")
        setting_pk, data_type = row[0], row[1]

        normalized = _validate_setting_value(body.setting_value, data_type)

        if body.description is not None:
            cur.execute(
                """
                UPDATE nss.system_setting
                SET    setting_value = %s, description = %s, updated_at = NOW()
                WHERE  system_setting_pk = %s
                """,
                (normalized, body.description.strip() or None, str(setting_pk)),
            )
        else:
            cur.execute(
                """
                UPDATE nss.system_setting
                SET    setting_value = %s, updated_at = NOW()
                WHERE  system_setting_pk = %s
                """,
                (normalized, str(setting_pk)),
            )

        log_audit(
            cur, action="UPDATE", table_name="system_setting", record_pk=str(setting_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Updated system setting {setting_key}",
        )

        cur.execute(
            """
            SELECT system_setting_pk, setting_key, setting_value,
                   description, data_type, is_active
            FROM   nss.system_setting
            WHERE  system_setting_pk = %s
            """,
            (str(setting_pk),),
        )
        return row_to_model(cur, SettingResponse)


@router.post("/settings", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
def create_setting(
    body: CreateSettingRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_MANAGE")),
) -> SettingResponse:
    """
    Add a new system setting. Requires FOUNDATION_MANAGE.

    setting_key must be unique; data_type must be one of
    STRING, INTEGER, BOOLEAN, DATE, JSON; the value is validated against it.
    """
    key = body.setting_key.strip().upper()
    dt = (body.data_type or "STRING").upper()
    if dt not in _VALID_DATA_TYPES:
        raise HTTPException(status_code=422, detail=f"data_type must be one of {', '.join(sorted(_VALID_DATA_TYPES))}.")
    normalized = _validate_setting_value(body.setting_value, dt)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM nss.system_setting WHERE setting_key = %s",
            (key,),
        )
        if cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail=f"A setting with key '{key}' already exists.")

        cur.execute(
            """
            INSERT INTO nss.system_setting (setting_key, setting_value, description, data_type)
            VALUES (%s, %s, %s, %s)
            RETURNING system_setting_pk
            """,
            (key, normalized, (body.description.strip() if body.description else None) or None, dt),
        )
        new_pk = cur.fetchone()[0]

        log_audit(
            cur, action="CREATE", table_name="system_setting", record_pk=str(new_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Created system setting {key}",
        )

        cur.execute(
            """
            SELECT system_setting_pk, setting_key, setting_value,
                   description, data_type, is_active
            FROM   nss.system_setting
            WHERE  system_setting_pk = %s
            """,
            (str(new_pk),),
        )
        return row_to_model(cur, SettingResponse)


@router.get("/sequences", response_model=list[SequenceResponse])
def list_sequences(
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[SequenceResponse]:
    """
    List all active ID sequence configurations.

    Infrastructure/verification endpoint. current_value is excluded —
    it's infrastructure state, not consumer data.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id_sequence_master_pk, sequence_code, sequence_name,
                   prefix, padding_length,
                   description, is_active
            FROM   nss.id_sequence_master
            WHERE  is_active = TRUE
            ORDER BY sequence_code
        """)
        return rows_to_models(cur, SequenceResponse)


_SEQUENCE_SELECT = """
    SELECT id_sequence_master_pk, sequence_code, sequence_name,
           prefix, padding_length, description, is_active
    FROM   nss.id_sequence_master
    WHERE  id_sequence_master_pk = %s
"""


@router.patch("/sequences/{sequence_code}", response_model=SequenceResponse)
def update_sequence(
    sequence_code: str,
    body: UpdateSequenceRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_MANAGE")),
) -> SequenceResponse:
    """
    Edit an ID sequence's configuration (name, prefix, padding, description).

    Requires FOUNDATION_MANAGE. current_value is never mutated here — it is
    infrastructure state advanced only by identifier generation, so prefix and
    padding changes affect only IDs minted from now on; already-issued IDs are
    unchanged. sequence_code is immutable (it is the lookup key used in code).
    """
    code = sequence_code.strip().upper()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id_sequence_master_pk FROM nss.id_sequence_master WHERE sequence_code = %s AND is_active = TRUE",
            (code,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Sequence not found.")
        seq_pk = row[0]

        sets: list[str] = []
        params: list = []
        if body.sequence_name is not None:
            sets.append("sequence_name = %s")
            params.append(body.sequence_name.strip())
        if body.prefix is not None:
            sets.append("prefix = %s")
            params.append(body.prefix.strip().upper())
        if body.padding_length is not None:
            sets.append("padding_length = %s")
            params.append(body.padding_length)
        if body.description is not None:
            sets.append("description = %s")
            params.append(body.description.strip() or None)

        if not sets:
            raise HTTPException(status_code=422, detail="No fields to update.")

        # Guard uniqueness of sequence_name if it is being changed.
        if body.sequence_name is not None:
            cur.execute(
                "SELECT 1 FROM nss.id_sequence_master WHERE sequence_name = %s AND id_sequence_master_pk <> %s",
                (body.sequence_name.strip(), str(seq_pk)),
            )
            if cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail="Another sequence already uses that name.")

        sets.append("updated_at = NOW()")
        params.append(str(seq_pk))
        cur.execute(
            f"UPDATE nss.id_sequence_master SET {', '.join(sets)} WHERE id_sequence_master_pk = %s",
            tuple(params),
        )

        log_audit(
            cur, action="UPDATE", table_name="id_sequence_master", record_pk=str(seq_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Updated ID sequence {code}",
        )

        cur.execute(_SEQUENCE_SELECT, (str(seq_pk),))
        return row_to_model(cur, SequenceResponse)


@router.post("/sequences", response_model=SequenceResponse, status_code=status.HTTP_201_CREATED)
def create_sequence(
    body: CreateSequenceRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_MANAGE")),
) -> SequenceResponse:
    """
    Add a new ID sequence. Requires FOUNDATION_MANAGE.

    sequence_code and sequence_name must both be unique. current_value starts
    at 0 (no identifiers issued yet).
    """
    code = body.sequence_code.strip().upper()
    name = body.sequence_name.strip()
    prefix = body.prefix.strip().upper()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM nss.id_sequence_master WHERE sequence_code = %s",
            (code,),
        )
        if cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail=f"A sequence with code '{code}' already exists.")
        cur.execute(
            "SELECT 1 FROM nss.id_sequence_master WHERE sequence_name = %s",
            (name,),
        )
        if cur.fetchone() is not None:
            raise HTTPException(status_code=409, detail=f"A sequence with name '{name}' already exists.")

        cur.execute(
            """
            INSERT INTO nss.id_sequence_master
                   (sequence_code, sequence_name, prefix, padding_length, description, current_value)
            VALUES (%s, %s, %s, %s, %s, 0)
            RETURNING id_sequence_master_pk
            """,
            (code, name, prefix, body.padding_length,
             (body.description.strip() if body.description else None) or None),
        )
        new_pk = cur.fetchone()[0]

        log_audit(
            cur, action="CREATE", table_name="id_sequence_master", record_pk=str(new_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Created ID sequence {code}",
        )

        cur.execute(_SEQUENCE_SELECT, (str(new_pk),))
        return row_to_model(cur, SequenceResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 3. GEOGRAPHIC SUBSYSTEM
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/countries", response_model=list[CountryResponse])
def list_countries(
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[CountryResponse]:
    """List all active countries."""
    with conn.cursor() as cur:
        return fetch_countries(cur)


@router.get("/countries/{country_pk}", response_model=CountryResponse)
def get_country(
    country_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> CountryResponse:
    """Get a single country by PK."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT country_pk, country_code, country_name,
                   display_order, is_active
            FROM   nss.country
            WHERE  country_pk = %s AND is_active = TRUE
        """, (str(country_pk),))
        result = row_to_model(cur, CountryResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="Country not found")
        return result


@router.get("/states", response_model=list[StateResponse])
def list_states(
    country_pk: UUID | None = Query(None, description="Filter by parent country"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[StateResponse]:
    """
    List all active states/provinces.

    Optionally filter by parent country PK.
    """
    with conn.cursor() as cur:
        return fetch_states(cur, country_pk)


@router.get("/states/{state_pk}", response_model=StateResponse)
def get_state(
    state_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> StateResponse:
    """Get a single state by PK (with country context)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.state_pk, s.country_pk,
                   c.country_code, c.country_name,
                   s.state_code, s.state_name,
                   s.display_order, s.is_active
            FROM   nss.state s
            JOIN   nss.country c ON c.country_pk = s.country_pk
            WHERE  s.state_pk = %s
              AND  s.is_active = TRUE
              AND  c.is_active = TRUE
        """, (str(state_pk),))
        result = row_to_model(cur, StateResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="State not found")
        return result


@router.get("/districts", response_model=list[DistrictResponse])
def list_districts(
    state_pk: UUID | None = Query(None, description="Filter by parent state"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[DistrictResponse]:
    """
    List all active districts.

    Optionally filter by parent state PK. Without filter, returns all
    active districts (~700+ for India alone).
    """
    with conn.cursor() as cur:
        return fetch_districts(cur, state_pk)


@router.get("/districts/{district_pk}", response_model=DistrictResponse)
def get_district(
    district_pk: UUID,
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> DistrictResponse:
    """Get a single district by PK (with state context)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.district_pk, d.state_pk,
                   s.state_name,
                   d.district_code, d.district_name,
                   d.display_order, d.is_active
            FROM   nss.district d
            JOIN   nss.state s ON s.state_pk = d.state_pk
            WHERE  d.district_pk = %s
              AND  d.is_active = TRUE
              AND  s.is_active = TRUE
              AND  d.entry_status = 'APPROVED'
        """, (str(district_pk),))
        result = row_to_model(cur, DistrictResponse)
        if result is None:
            raise HTTPException(status_code=404, detail="District not found")
        return result


@router.get("/cities", response_model=list[CityVillageResponse])
def list_cities(
    district_pk: UUID | None = Query(None, description="Filter by parent district"),
    postal_code_pk: UUID | None = Query(None, description="Filter by postal code"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[CityVillageResponse]:
    """
    List all active cities/villages.

    Optionally filter by parent district PK or by postal_code_pk
    (SOL-ARCH-010 Amendment, 2026-10-01): district is a best-effort name
    match and may be unresolved; postal_code is the primary location
    anchor, so filtering by it is the more reliable narrowing step —
    e.g. completing the Geography admin cascade (state → district →
    postal code → city/village) once a postal code is selected.
    """
    with conn.cursor() as cur:
        return fetch_cities(cur, district_pk, postal_code_pk)


@router.get("/postal-codes", response_model=list[PostalCodeResponse])
def list_postal_codes(
    state_pk: UUID | None = Query(None, description="Filter by state"),
    country_pk: UUID | None = Query(None, description="Filter by country"),
    district_pk: UUID | None = Query(None, description="Filter by district (via city_village — postal_code has no direct district FK)"),
    q: str | None = Query(None, min_length=2, max_length=100, description="Match the PIN digits"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[PostalCodeResponse]:
    """
    List all active postal codes.

    Optionally filter by state, country, or district, and search with *q*.

    Simplified Geography Model (2026-10-02): one row per PIN globally
    (unique on postal_code alone), no office-level detail any more.
    """
    with conn.cursor() as cur:
        return fetch_postal_codes(cur, state_pk, country_pk, district_pk, q)


@router.get("/post-offices", response_model=list[PostOfficeResponse])
def list_post_offices(
    postal_code_pk: UUID = Query(..., description="PIN to list post offices under"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[PostOfficeResponse]:
    """
    List active, APPROVED post offices under a PIN.

    Post offices were reinstated by the Member-Assisted Geographic Entry
    amendment (SOL-ARCH-010, 2026-10-03) — a PIN can carry several post
    offices (one HO + several SO/BO).
    """
    with conn.cursor() as cur:
        return fetch_post_offices(cur, postal_code_pk)


@router.get("/postal-code-mappings", response_model=list[PostalCodeMappingResponse])
def list_postal_code_mappings(
    city_village_pk: UUID | None = Query(None, description="Filter by city/village"),
    postal_code_pk: UUID | None = Query(None, description="Filter by postal code"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[PostalCodeMappingResponse]:
    """
    List city/village to postal code mappings.

    SOL-ARCH-010 Amendment (2026-10-01): the former M:N junction
    table is retired. This now reads the direct
    nss.city_village.postal_code_pk FK — a city/village is its own
    mapping row whenever its PIN has been resolved. No separate
    mapping PK exists any more.
    """
    base_sql = """
        SELECT cv.city_village_pk, cv.city_village_name,
               cv.postal_code_pk, pc.postal_code
        FROM   nss.city_village cv
        JOIN   nss.postal_code pc ON pc.postal_code_pk = cv.postal_code_pk
        WHERE  cv.is_active = TRUE
          AND  cv.entry_status = 'APPROVED'
          AND  pc.is_active = TRUE
          AND  pc.entry_status = 'APPROVED'
    """
    conditions: list[str] = []
    params: list = []

    if city_village_pk is not None:
        conditions.append("cv.city_village_pk = %s")
        params.append(str(city_village_pk))
    if postal_code_pk is not None:
        conditions.append("cv.postal_code_pk = %s")
        params.append(str(postal_code_pk))

    if conditions:
        base_sql += " AND " + " AND ".join(conditions)

    base_sql += " ORDER BY cv.city_village_name, pc.postal_code"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return rows_to_models(cur, PostalCodeMappingResponse)


@router.get("/sakha-postal-codes", response_model=list[SakhaPostalCodeResponse])
def list_sakha_postal_codes(
    state_pk: UUID | None = Query(None, description="Filter by state (via the linked postal code)"),
    district_pk: UUID | None = Query(None, description="Filter by district (via city_village — resolves which PINs belong to this district)"),
    postal_code_pk: UUID | None = Query(None, description="Filter by a specific postal code"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[SakhaPostalCodeResponse]:
    """
    List Sakha Sangha branches linked to a postal code.

    The link is `organization.postal_code_pk` (set from the branch's
    address PIN). Only active SAKHA_SANGHA organizations that have a
    resolved postal code are returned. Optionally filter by state,
    district (via city_village.district_pk — see fetch_postal_codes), or
    a specific postal code.
    """
    base_sql = """
        SELECT o.organization_pk, o.organization_name, o.organization_code,
               pc.postal_code_pk, pc.postal_code,
               pc.state_pk, s.state_name
        FROM   nss.organization o
        JOIN   nss.master_data md
               ON md.master_data_pk = o.organization_type_master_data_pk
        JOIN   nss.postal_code pc ON pc.postal_code_pk = o.postal_code_pk
        JOIN   nss.state s ON s.state_pk = pc.state_pk
        WHERE  md.value_code = 'SAKHA_SANGHA'
          AND  o.is_active = TRUE
          AND  o.postal_code_pk IS NOT NULL
    """
    params: list = []

    if district_pk is not None:
        base_sql += """
            AND EXISTS (
                SELECT 1 FROM nss.city_village cv
                WHERE  cv.postal_code_pk = pc.postal_code_pk
                  AND  cv.is_active = TRUE
                  AND  cv.entry_status = 'APPROVED'
                  AND  cv.district_pk = %s
            )
        """
        params.append(str(district_pk))
    if state_pk is not None:
        base_sql += " AND pc.state_pk = %s"
        params.append(str(state_pk))
    if postal_code_pk is not None:
        base_sql += " AND pc.postal_code_pk = %s"
        params.append(str(postal_code_pk))


    base_sql += " ORDER BY s.state_name, o.organization_name"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return rows_to_models(cur, SakhaPostalCodeResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 4. RUNTIME TABLES (Intentionally Empty at Tier 1 Launch)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    document_type_code: str | None = Query(None, description="Filter by document type code"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[DocumentResponse]:
    """
    List all active documents.

    Tier 1 exposes only currently useful fields. FK fields
    (person_pk, uploaded_by_sangha_sevi_pk) excluded — targets
    don't exist yet. Response shape revisited when consuming
    modules arrive.
    Currently returns empty — documents are runtime data.
    """
    base_sql = """
        SELECT document_master_pk, document_type_code,
               document_number, document_name, storage_path,
               file_size_bytes, mime_type, version, checksum,
               description, is_active
        FROM   nss.document_master
        WHERE  is_active = TRUE
    """
    params: list = []

    if document_type_code is not None:
        base_sql += " AND document_type_code = %s"
        params.append(document_type_code)

    base_sql += " ORDER BY document_type_code, document_name"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return rows_to_models(cur, DocumentResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 5. FESTIVAL REFERENCE CALENDAR (SOL-ARCH-013)
# ═══════════════════════════════════════════════════════════════════════════
#
# festival_master is seeded reference data (read-only here — no admin UI
# need to add new festivals yet, only DOLA_PURNIMA exists today).
# festival_calendar_date is the per-year observed-date record an
# administrator must enter/confirm before any credential-validity window
# or renewal-deadline calculation that depends on it (MBR-011A, MBR-029,
# SOL-ARCH-013 FC-DECISION-01) can resolve. Writes require
# FOUNDATION_CALENDAR_MANAGE (NSS_ERP_ADMIN only).

_FESTIVAL_CALENDAR_DATE_SELECT = """
    SELECT fcd.festival_calendar_date_pk, fcd.festival_master_pk,
           fm.festival_code, fm.festival_name,
           fcd.calendar_year, fcd.observed_date, fcd.is_confirmed,
           fcd.source_reference, fcd.remarks, fcd.is_active
    FROM   nss.festival_calendar_date fcd
    JOIN   nss.festival_master fm
           ON fm.festival_master_pk = fcd.festival_master_pk
    WHERE  fcd.festival_calendar_date_pk = %s
"""


@router.get("/festivals", response_model=list[FestivalMasterResponse])
def list_festivals(
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[FestivalMasterResponse]:
    """List all active festivals that can carry calendar dates."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT festival_master_pk, festival_code, festival_name,
                   festival_name_odia, lunar_basis, is_erp_reference_date,
                   description, display_order, is_active
            FROM   nss.festival_master
            WHERE  is_active = TRUE
            ORDER BY display_order, festival_name
        """)
        return rows_to_models(cur, FestivalMasterResponse)


@router.get("/festival-calendar-dates", response_model=list[FestivalCalendarDateResponse])
def list_festival_calendar_dates(
    festival_code: str | None = Query(None, description="Filter by festival code, e.g. DOLA_PURNIMA"),
    calendar_year: int | None = Query(None, description="Filter by calendar year"),
    conn=Depends(get_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_VIEW")),
) -> list[FestivalCalendarDateResponse]:
    """
    List observed festival dates on file, newest year first.

    Powers the Festival Calendar admin screen (SOL-ARCH-013): shows which
    years are confirmed vs. provisional vs. missing entirely, so an admin
    can see at a glance that (e.g.) 2016 has no Dola Purnima date on file.
    """
    base_sql = """
        SELECT fcd.festival_calendar_date_pk, fcd.festival_master_pk,
               fm.festival_code, fm.festival_name,
               fcd.calendar_year, fcd.observed_date, fcd.is_confirmed,
               fcd.source_reference, fcd.remarks, fcd.is_active
        FROM   nss.festival_calendar_date fcd
        JOIN   nss.festival_master fm
               ON fm.festival_master_pk = fcd.festival_master_pk
        WHERE  fcd.is_active = TRUE
    """
    params: list = []

    if festival_code is not None:
        base_sql += " AND fm.festival_code = %s"
        params.append(festival_code.strip().upper())

    if calendar_year is not None:
        base_sql += " AND fcd.calendar_year = %s"
        params.append(calendar_year)

    base_sql += " ORDER BY fcd.calendar_year DESC, fm.festival_name"

    with conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        return rows_to_models(cur, FestivalCalendarDateResponse)


@router.post(
    "/festival-calendar-dates",
    response_model=FestivalCalendarDateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_festival_calendar_date(
    body: CreateFestivalCalendarDateRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_CALENDAR_MANAGE")),
) -> FestivalCalendarDateResponse:
    """
    Record the observed date for a festival/year. Requires
    FOUNDATION_CALENDAR_MANAGE.

    One row per (festival, calendar_year) — a second POST for the same
    pair is a 409; use PATCH to correct or confirm an existing row.
    is_confirmed may be set TRUE immediately if the administrator already
    has a confirmed source (almanac/Kendra Sangha circular); otherwise
    leave it FALSE and confirm later via PATCH once verified.
    """
    festival_code = body.festival_code.strip().upper()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT festival_master_pk FROM nss.festival_master "
            "WHERE festival_code = %s AND is_active = TRUE",
            (festival_code,),
        )
        fm = cur.fetchone()
        if fm is None:
            raise HTTPException(status_code=404, detail=f"Festival '{festival_code}' not found.")
        festival_master_pk = fm[0]

        cur.execute(
            "SELECT 1 FROM nss.festival_calendar_date "
            "WHERE festival_master_pk = %s AND calendar_year = %s AND is_active = TRUE",
            (str(festival_master_pk), body.calendar_year),
        )
        if cur.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A {festival_code} date for {body.calendar_year} is already on "
                    "file — use PATCH to correct or confirm it instead."
                ),
            )

        if body.observed_date.year != body.calendar_year:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"observed_date ({body.observed_date.isoformat()}) must fall "
                    f"within calendar_year {body.calendar_year}."
                ),
            )

        cur.execute(
            """
            INSERT INTO nss.festival_calendar_date
                (festival_master_pk, calendar_year, observed_date,
                 is_confirmed, source_reference, remarks)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING festival_calendar_date_pk
            """,
            (
                str(festival_master_pk), body.calendar_year, body.observed_date,
                body.is_confirmed,
                (body.source_reference.strip() if body.source_reference else None) or None,
                (body.remarks.strip() if body.remarks else None) or None,
            ),
        )
        new_pk = cur.fetchone()[0]

        log_audit(
            cur, action="CREATE", table_name="festival_calendar_date", record_pk=str(new_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation",
            summary=f"Recorded {festival_code} {body.calendar_year} = {body.observed_date.isoformat()}",
        )

        cur.execute(_FESTIVAL_CALENDAR_DATE_SELECT, (str(new_pk),))
        return row_to_model(cur, FestivalCalendarDateResponse)


@router.patch(
    "/festival-calendar-dates/{festival_calendar_date_pk}",
    response_model=FestivalCalendarDateResponse,
)
def update_festival_calendar_date(
    festival_calendar_date_pk: UUID,
    body: UpdateFestivalCalendarDateRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(require_permission("FOUNDATION_CALENDAR_MANAGE")),
) -> FestivalCalendarDateResponse:
    """
    Correct or confirm an existing festival-calendar-date row. Requires
    FOUNDATION_CALENDAR_MANAGE.

    The common path is confirming a provisional date (is_confirmed:
    false → true) once the administrator has verified it against an
    almanac/Kendra Sangha circular — this is what unblocks any pending
    credential-validity window calculation for that year.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT fcd.calendar_year FROM nss.festival_calendar_date fcd "
            "WHERE fcd.festival_calendar_date_pk = %s AND fcd.is_active = TRUE",
            (str(festival_calendar_date_pk),),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Festival calendar date not found.")
        calendar_year = row[0]

        updates: dict = {}
        if body.observed_date is not None:
            if body.observed_date.year != calendar_year:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"observed_date ({body.observed_date.isoformat()}) must fall "
                        f"within calendar_year {calendar_year}."
                    ),
                )
            updates["observed_date"] = body.observed_date
        if body.is_confirmed is not None:
            updates["is_confirmed"] = body.is_confirmed
        if body.source_reference is not None:
            updates["source_reference"] = body.source_reference.strip() or None
        if body.remarks is not None:
            updates["remarks"] = body.remarks.strip() or None

        if not updates:
            raise HTTPException(status_code=422, detail="No fields provided to update.")

        set_parts = ["updated_at = NOW()"]
        params: list = []
        for col, val in updates.items():
            set_parts.append(f"{col} = %s")
            params.append(val)
        params.append(str(festival_calendar_date_pk))

        cur.execute(
            f"UPDATE nss.festival_calendar_date SET {', '.join(set_parts)} "
            "WHERE festival_calendar_date_pk = %s",
            params,
        )

        log_audit(
            cur, action="UPDATE", table_name="festival_calendar_date",
            record_pk=str(festival_calendar_date_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary="Updated festival calendar date",
        )

        cur.execute(_FESTIVAL_CALENDAR_DATE_SELECT, (str(festival_calendar_date_pk),))
        return row_to_model(cur, FestivalCalendarDateResponse)


# ═══════════════════════════════════════════════════════════════════════════
# 6. MEMBER-ASSISTED GEOGRAPHIC ENTRY — PROPOSE (SOL-ARCH-010 Amendment,
#    2026-10-03 — SOL-FND-004 §16.8, FND-BR-085 .. FND-BR-090)
# ═══════════════════════════════════════════════════════════════════════════
#
# Any authenticated member (not just FOUNDATION_MANAGE admins) may submit a
# district / postal-code / post-office / city-village value the system has
# not seen yet. The row lands as entry_status='PENDING', which the lookup
# endpoints above now filter out, so it is invisible to every other member
# until a FOUNDATION_MANAGE admin approves or corrects it (see
# api/routers/geo_approval.py, FND-BR-087/088).
#
# "Current member" resolution: UserContext.sangha_sevi_pk, exactly as
# auth.py / membership.py already use it — resolved once in
# rbac_service.load_user_context() from the active nss.sangha_sevi row for
# the logged-in person. A user with no active Sangha Sevi record (e.g. an
# account mid-registration) has nothing to anchor submitted_by to, so
# propose is refused with a clean 403 rather than inserting a NULL actor.
#
# Double-submit guard: rather than an ON CONFLICT against the
# approved-only partial unique index (which a PENDING insert can never
# hit), each handler does a cheap pre-check for an existing PENDING row
# with the same logical value and, if found, returns that one instead of
# inserting a duplicate. This is deliberately simple — it does not try to
# dedupe near-miss spellings, only an exact (case-insensitive) resubmission.


def _derive_provisional_code(name: str) -> str:
    """
    Provisional *_code for a member-submitted name (district / city-village).

    Uppercases, strips everything but letters/digits, and truncates to 20
    chars to fit the column. This is explicitly PROVISIONAL — it exists
    only so the NOT NULL *_code column has a value while the row sits
    PENDING. It is never shown to other members (PENDING rows are excluded
    from every lookup) and is fully superseded the moment an admin corrects
    the proposal into a canonical row via POST .../correct, which carries
    its own authoritative code.
    """
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()[:20]


def _require_submitter_sangha_sevi_pk(user: UserContext) -> str:
    """
    403 unless the current user has an active Sangha Sevi record to anchor
    submitted_by_sangha_sevi_pk to (every propose endpoint needs this).
    """
    if not user.sangha_sevi_pk:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an active Sangha Sevi may propose a new geographic value.",
        )
    return str(user.sangha_sevi_pk)


@router.post(
    "/districts/propose",
    response_model=PendingDistrictResponse,
    status_code=status.HTTP_201_CREATED,
)
def propose_district(
    body: ProposeDistrictRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(get_current_user),
) -> PendingDistrictResponse:
    """
    Submit a district name the system has not seen yet for *state_pk*.

    Lands as entry_status='PENDING' with a provisional district_code
    derived from the name (see _derive_provisional_code) — superseded on
    admin correction. A duplicate PENDING submission for the same
    (state, name) returns the existing PENDING row rather than creating a
    second one.
    """
    submitter_pk = _require_submitter_sangha_sevi_pk(user)
    district_name = body.district_name.strip()

    with conn.cursor() as cur:
        require_entity(cur, "state", str(body.state_pk), label="State")
        cur.execute(
            """
            SELECT district_pk, state_pk, district_code, district_name,
                   entry_status, submitted_by_sangha_sevi_pk, is_active
            FROM   nss.district
            WHERE  state_pk = %s
              AND  LOWER(district_name) = LOWER(%s)
              AND  entry_status = 'PENDING'
              AND  is_active = TRUE
            LIMIT 1
            """,
            (str(body.state_pk), district_name),
        )
        existing = row_to_model(cur, PendingDistrictResponse)
        if existing is not None:
            return existing

        provisional_code = _derive_provisional_code(district_name)
        cur.execute(
            """
            INSERT INTO nss.district (
                state_pk, district_code, district_name,
                entry_status, submitted_by_sangha_sevi_pk
            ) VALUES (%s, %s, %s, 'PENDING', %s)
            RETURNING district_pk, state_pk, district_code, district_name,
                      entry_status, submitted_by_sangha_sevi_pk, is_active
            """,
            (str(body.state_pk), provisional_code, district_name, submitter_pk),
        )
        new_row = row_to_model(cur, PendingDistrictResponse)

        log_audit(
            cur, action="CREATE", table_name="district", record_pk=str(new_row.district_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Member-proposed district '{district_name}' (PENDING)",
        )
        return new_row


@router.post(
    "/postal-codes/propose",
    response_model=PendingPostalCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
def propose_postal_code(
    body: ProposePostalCodeRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(get_current_user),
) -> PendingPostalCodeResponse:
    """
    Submit a 6-digit PIN the system has not seen yet, under *state_pk*.

    Lands as entry_status='PENDING'. No code-derivation needed — the PIN
    itself is the value. A duplicate PENDING submission for the same PIN
    returns the existing PENDING row.
    """
    submitter_pk = _require_submitter_sangha_sevi_pk(user)
    pin = body.postal_code.strip()
    if not re.fullmatch(r"\d{6}", pin):
        raise HTTPException(status_code=422, detail="postal_code must be exactly 6 digits.")

    with conn.cursor() as cur:
        require_entity(cur, "state", str(body.state_pk), label="State")
        # The PIN is already a canonical (APPROVED) row: nothing to propose.
        cur.execute(
            """
            SELECT 1 FROM nss.postal_code
            WHERE  postal_code = %s
              AND  entry_status = 'APPROVED'
              AND  is_active = TRUE
            """,
            (pin,),
        )
        if cur.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Postal code {pin} already exists.",
            )
        cur.execute(
            """
            SELECT postal_code_pk, state_pk, postal_code,
                   entry_status, submitted_by_sangha_sevi_pk, is_active
            FROM   nss.postal_code
            WHERE  postal_code = %s
              AND  entry_status = 'PENDING'
              AND  is_active = TRUE
            LIMIT 1
            """,
            (pin,),
        )
        existing = row_to_model(cur, PendingPostalCodeResponse)
        if existing is not None:
            return existing

        cur.execute(
            """
            INSERT INTO nss.postal_code (
                state_pk, postal_code, entry_status, submitted_by_sangha_sevi_pk
            ) VALUES (%s, %s, 'PENDING', %s)
            RETURNING postal_code_pk, state_pk, postal_code,
                      entry_status, submitted_by_sangha_sevi_pk, is_active
            """,
            (str(body.state_pk), pin, submitter_pk),
        )
        new_row = row_to_model(cur, PendingPostalCodeResponse)

        log_audit(
            cur, action="CREATE", table_name="postal_code", record_pk=str(new_row.postal_code_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Member-proposed postal code '{pin}' (PENDING)",
        )
        return new_row


@router.post(
    "/post-offices/propose",
    response_model=PendingPostOfficeResponse,
    status_code=status.HTTP_201_CREATED,
)
def propose_post_office(
    body: ProposePostOfficeRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(get_current_user),
) -> PendingPostOfficeResponse:
    """
    Submit a post office name the system has not seen yet, under
    *postal_code_pk*. Lands as entry_status='PENDING'. No code-derivation
    needed — post_office has no code column. A duplicate PENDING
    submission for the same (PIN, name) returns the existing PENDING row.
    """
    submitter_pk = _require_submitter_sangha_sevi_pk(user)
    post_office_name = body.post_office_name.strip()

    with conn.cursor() as cur:
        require_entity(cur, "postal_code", str(body.postal_code_pk), label="Postal code")

        cur.execute(
            """
            SELECT post_office_pk, postal_code_pk, post_office_name,
                   entry_status, submitted_by_sangha_sevi_pk, is_active
            FROM   nss.post_office
            WHERE  postal_code_pk = %s
              AND  LOWER(post_office_name) = LOWER(%s)
              AND  entry_status = 'PENDING'
              AND  is_active = TRUE
            LIMIT 1
            """,
            (str(body.postal_code_pk), post_office_name),
        )
        existing = row_to_model(cur, PendingPostOfficeResponse)
        if existing is not None:
            return existing

        cur.execute(
            """
            INSERT INTO nss.post_office (
                postal_code_pk, post_office_name,
                entry_status, submitted_by_sangha_sevi_pk
            ) VALUES (%s, %s, 'PENDING', %s)
            RETURNING post_office_pk, postal_code_pk, post_office_name,
                      entry_status, submitted_by_sangha_sevi_pk, is_active
            """,
            (str(body.postal_code_pk), post_office_name, submitter_pk),
        )
        new_row = row_to_model(cur, PendingPostOfficeResponse)

        log_audit(
            cur, action="CREATE", table_name="post_office", record_pk=str(new_row.post_office_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Member-proposed post office '{post_office_name}' (PENDING)",
        )
        return new_row


@router.post(
    "/city-villages/propose",
    response_model=PendingCityVillageResponse,
    status_code=status.HTTP_201_CREATED,
)
def propose_city_village(
    body: ProposeCityVillageRequest,
    conn=Depends(get_write_connection),
    user: UserContext = Depends(get_current_user),
) -> PendingCityVillageResponse:
    """
    Submit a city/village name the system has not seen yet, anchored to at
    least one of *district_pk* / *postal_code_pk* (city_village allows both
    to be NULL at the schema level, but a propose with neither anchor is
    not actionable for an admin to review, so it is rejected here).

    Lands as entry_status='PENDING' with a provisional city_village_code
    derived from the name — superseded on admin correction. A duplicate
    PENDING submission for the same (anchors, name) returns the existing
    PENDING row.
    """
    if body.district_pk is None and body.postal_code_pk is None:
        raise HTTPException(
            status_code=422,
            detail="At least one of district_pk or postal_code_pk is required.",
        )
    cv_type = body.city_village_type.strip().upper()
    if cv_type not in ("CITY", "TOWN", "VILLAGE"):
        raise HTTPException(status_code=422, detail="city_village_type must be CITY, TOWN, or VILLAGE.")

    submitter_pk = _require_submitter_sangha_sevi_pk(user)
    cv_name = body.city_village_name.strip()

    with conn.cursor() as cur:
        if body.district_pk is not None:
            require_entity(cur, "district", str(body.district_pk), label="District")
        if body.postal_code_pk is not None:
            require_entity(cur, "postal_code", str(body.postal_code_pk), label="Postal code")
        cur.execute(
            """
            SELECT city_village_pk, district_pk, postal_code_pk,
                   city_village_code, city_village_name, city_village_type,
                   entry_status, submitted_by_sangha_sevi_pk, is_active
            FROM   nss.city_village
            WHERE  entry_status = 'PENDING'
              AND  is_active = TRUE
              AND  LOWER(city_village_name) = LOWER(%s)
              AND  district_pk IS NOT DISTINCT FROM %s
              AND  postal_code_pk IS NOT DISTINCT FROM %s
            LIMIT 1
            """,
            (
                cv_name,
                str(body.district_pk) if body.district_pk else None,
                str(body.postal_code_pk) if body.postal_code_pk else None,
            ),
        )
        existing = row_to_model(cur, PendingCityVillageResponse)
        if existing is not None:
            return existing

        provisional_code = _derive_provisional_code(cv_name)
        cur.execute(
            """
            INSERT INTO nss.city_village (
                district_pk, postal_code_pk, city_village_code, city_village_name,
                city_village_type, entry_status, submitted_by_sangha_sevi_pk
            ) VALUES (%s, %s, %s, %s, %s, 'PENDING', %s)
            RETURNING city_village_pk, district_pk, postal_code_pk,
                      city_village_code, city_village_name, city_village_type,
                      entry_status, submitted_by_sangha_sevi_pk, is_active
            """,
            (
                str(body.district_pk) if body.district_pk else None,
                str(body.postal_code_pk) if body.postal_code_pk else None,
                provisional_code, cv_name, cv_type, submitter_pk,
            ),
        )
        new_row = row_to_model(cur, PendingCityVillageResponse)

        log_audit(
            cur, action="CREATE", table_name="city_village", record_pk=str(new_row.city_village_pk),
            actor_pk=user.actor_pk, actor_user_account_pk=str(user.user_account_pk),
            module="foundation", summary=f"Member-proposed city/village '{cv_name}' (PENDING)",
        )
        return new_row


