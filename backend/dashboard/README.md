# backend/dashboard/

Single dashboard view. **Not in `INSTALLED_APPS`** (`backend/config/settings.py`) — it still
works because it has no models to register, and `config/urls.py` includes its urlconf directly
under `/dashboard/`.

## Views / URLs

- `kendra_dashboard` (`views.py`) — function-based, renders `templates/dashboard/
  kendra_dashboard.html` with no context.
- `urls.py` — `path("", kendra_dashboard, name="kendra_dashboard")`, mounted at `/dashboard/`.

## Gotchas

- `templates/dashboard/sakha_dashboard.html` exists but is a 0-byte orphan — no view or URL
  renders it. If you're implementing the Sakha dashboard, this is the placeholder to fill in
  (and you'll need a new view + URL, and likely to add `dashboard` to `INSTALLED_APPS` if it
  ever gets its own models).
- `models.py` is an empty stub.
