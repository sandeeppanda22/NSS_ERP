# backend/

Django project for NSS ERP. See `docs/PROJECT_DOCUMENTATION.md` for full architecture, setup,
and configuration detail — this file is a short map of what's here.

## Apps

| App | Real models? | In `INSTALLED_APPS`? | URLs wired? |
|---|---|---|---|
| `authentication/` | Yes (`Role`, `UserRole`, `LoginAudit`) | Yes | Yes (`/login/`) |
| `foundation/` | Yes (`OrganizationType`, `Organization`, `Address`, `Person`) | Yes | Yes (`/persons/`) |
| `dashboard/` | No (stub) | **No** | Yes (`/dashboard/`, via `config/urls.py`) |
| `family/` | Yes (`FamilyGroup`, `FamilyMembership`) | Yes | **No** — admin-only |
| `membership/` | Yes (`MembershipType`, `MembershipStatus`, `SanghaSevi`) | Yes | **No** — admin-only |
| `governance/` | No (stub) | No | No |
| `attendance/` | No (stub) | No | No |
| `config/` | — Django project settings/urls/asgi/wsgi, not an app | — | — |

`mahila`, `kumari`, `kishore`, `sevak`, `heritage`, `publications`, `upbs`, `reports`,
`administration` don't exist as apps yet — planned only.

## Other folders

- `static/` — `css/app.css` (NSS color theme), `js/app.js` (empty placeholder).
- `templates/` — `base/` (layout + navbar/sidebar partials), `auth/`, `dashboard/`,
  `foundation/`. `templates/dashboard/sakha_dashboard.html` is an orphan (0 bytes, no view
  renders it).
- `manage.py` — standard Django entrypoint.

## Running

```
pip install -r requirements.txt      # from repo root
```
Create `backend/.env` with `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (no
`.env.example` exists yet — see `config/README.md`), then:
```
python manage.py migrate
python manage.py runserver
```
