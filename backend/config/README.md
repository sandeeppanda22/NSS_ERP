# backend/config/

Django project configuration package (not an app).

- `settings.py` — `INSTALLED_APPS` (`admin`, `auth`, `contenttypes`, `sessions`, `messages`,
  `staticfiles`, plus `heritage`, `foundation`, `membership`, `family`, `authentication`); `DATABASES`
  (PostgreSQL, credentials read via `django-environ` from `backend/.env` — `DB_NAME`, `DB_USER`,
  `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, no defaults); `TEMPLATES` (`DjangoTemplates`,
  project-level `templates/` dir + per-app dirs); `LOGIN_URL=/login/`,
  `LOGIN_REDIRECT_URL=/dashboard/`, `LOGOUT_REDIRECT_URL=/login/`. `DEBUG=True`,
  `ALLOWED_HOSTS=[]`, and `SECRET_KEY` are hardcoded dev-only values — not safe for deployment
  as-is.
- `urls.py` — root URL routing: `/` redirects to `login`, `/admin/` to Django admin, then
  includes `authentication.urls`, `dashboard.urls` (under `/dashboard/`), and `foundation.urls`.
  `family`, `membership`, `governance`, `attendance` are **not** included here.
- `asgi.py` / `wsgi.py` — standard Django entrypoints, unmodified from the Django default.

No custom `AUTH_USER_MODEL` — uses Django's built-in `django.contrib.auth.models.User`.

See `docs/PROJECT_DOCUMENTATION.md` → Configuration for the full environment-variable table.
