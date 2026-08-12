# backend/templates/base/

Shared layout and partials.

- `base.html` — main authenticated-page layout (`{% load static %}`, Bootstrap 5.3.3 CDN +
  `static/css/app.css`), includes `navbar.html` and `sidebar.html`, defines
  `{% block content %}` in a two-column grid. Extended by `dashboard/kendra_dashboard.html`,
  `foundation/person_list.html`, `foundation/person_detail.html`.
- `login_base.html` — minimal standalone shell (no navbar/sidebar), extended only by
  `auth/login.html`.
- `navbar.html` — "NSS ERP" brand + `Welcome, {{ request.user.username }}` when authenticated.
- `sidebar.html` — 4 static nav links: Dashboard (`/dashboard/`), Persons (`/persons/`),
  Members and Families (both `href="#"` — dead links, no `membership`/`family` URLs exist yet).
