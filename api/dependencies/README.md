# api/dependencies/

FastAPI `Depends()` factories (Tier 5). Distinct from `api/services/`, which holds
the logic these call. `__init__.py` exports nothing — import from the submodules.

| File | Provides |
|------|----------|
| `auth.py` | `get_current_user()` — HTTP Bearer JWT → `UserContext`. 401 on missing/invalid/expired token, a refresh token presented as an access token, or an unknown/inactive account. Also sets the `nss.actor_user_account_pk`/`nss.actor_sangha_sevi_pk` session variables (`set_config(..., TRUE)`) that the DB `fn_audit_trigger()` reads. `get_optional_user()` — same but returns `None` instead of 401 (also sets the actor variables); used only by `get_write_connection()`. `get_write_connection()` — the write-pool (`nss_db_writer`) dependency every write router imports; resolves the caller via `get_optional_user()`, sets the actor variables on the write connection (NULL actor for public endpoints), commits on success / rolls back on exception. |
| `rbac.py` | `require_permission(code)` and `require_any_permission(*codes)` — dependency factories wrapping `get_current_user()`; 403 (`Permission required: ...` / `One of these permissions required: ...`) otherwise. Permissions are the union across all of a user's active roles. |

`get_current_user()` depends on `get_connection` (the read pool), so the actor variables it sets live on
a read-pool connection and do not reach writes; the trigger-visible actor comes from
`get_write_connection()` in this same module. Routers must import the write-connection dependency from
`api.dependencies.auth`, not `api.database` (the latter is the non-auditing primitive, NULL actor).
`rbac.py` wraps `get_current_user()`.

Tier 6 uses the same factories unchanged: `governance.py` gates with `require_any_permission("GOVERNANCE_VIEW", "GOVERNANCE_MANAGE")` for reads and `require_permission("GOVERNANCE_MANAGE")` for writes, and `get_current_user` for its member self-service endpoints.

Usage: `user: UserContext = Depends(require_permission("ADMIN_USER_MANAGE"))`. Scope-based checks
(`require_org_in_scope()` and friends) are not dependencies — they live in
`api/services/rbac_service.py` and are called inside handlers.
