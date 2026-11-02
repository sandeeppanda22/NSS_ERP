# frontend/assets/css/

Stylesheets for the static frontend, served under `/assets/css/`. `api/main.py::_serve_page()` rewrites
each `<link href>` to `?v=<content hash>` per request, so never hand-maintain `?v=`.
Page-level detail: [`../../README.md`](../../README.md); deep doc: `docs/PROJECT_DOCUMENTATION.md`.

| File | Responsibility |
|---|---|
| `tailwind-input.css` | Tailwind entry file (`@tailwind` directives); source for the generated bundle. |
| `tailwind.min.css` | **Committed, generated** Tailwind + DaisyUI bundle. Rebuild with `npm run css:build` (repo root) after adding or changing any Tailwind/DaisyUI class in `frontend/**/*.html` or `frontend/assets/js/**/*.js` (scan paths: `tailwind.config.js`). Do not hand-edit. |
| `badges.css` | Single source of truth for all badge geometry and colours (`badge-status-*`, `badge-type-*`, `badge-aff-*`, `badge-account-*`, `badge-claim-*`). Pages must not redefine badge classes inline. |
| `nss-layout.css` | Authenticated-page layout: sidebar, topbar, user info, shared page components (largest file). |
| `nss-datepicker.css` | Styles for the shared DD/MM/YYYY picker (`../js/nss-datepicker.js`). |
| `nss-combobox.css` | Styles for the select-or-propose combobox (`../js/nss-combobox.js`). |
| `style.css` | Tier 0 leftovers: small project-specific overrides (e.g. `[x-cloak]`). |
