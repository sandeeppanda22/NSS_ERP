# backend/authentication/

Login and role/audit models. In `INSTALLED_APPS` and wired into the root URLconf.

## Models (`models.py`)

- `Role` — `code` (unique), `name`, `description`, `is_active`. `db_table="role"`.
- `UserRole` — links `auth.User` ↔ `Role` (`unique_together`), `is_primary` flag,
  `assigned_at`. `db_table="user_role"`.
- `LoginAudit` — `user` (nullable FK), `login_time`, `ip_address`, `user_agent`, `success`.
  `db_table="login_audit"`. **Not currently written to** — see Gotchas below.

## Views / URLs

- `login_view` (`views.py`) — function-based. GET renders `templates/auth/login.html`; POST
  authenticates against `auth.User` via `authenticate()`/`login()`, redirects to `/dashboard/`
  on success (hardcoded string, not `reverse()`) or re-renders with an inline error on failure.
- `urls.py` — `path("login/", login_view, name="login")`.

## Gotchas

- `LoginAudit` exists but nothing in `login_view` creates a row on login attempts — it's an
  unused model today.
- No RBAC enforcement uses `Role`/`UserRole` yet; they're defined but not checked anywhere in
  views. Full target RBAC/RLS model is in `docs/00_Project_Governance/STD/05_security_standards.md`.
