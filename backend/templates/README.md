# backend/templates/

Project-level template root (`TEMPLATES[0]['DIRS']` in `backend/config/settings.py`, combined
with each app's own `APP_DIRS` templates).

| Folder | Contents |
|---|---|
| `base/` | Shared layout + partials (`base.html`, `login_base.html`, `navbar.html`, `sidebar.html`) |
| `auth/` | `login.html` — `authentication.login_view` |
| `dashboard/` | `kendra_dashboard.html` (used) + `sakha_dashboard.html` (orphan, empty) |
| `foundation/` | `person_list.html`, `person_detail.html` |
