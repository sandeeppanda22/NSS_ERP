# frontend/assets/css/

Stylesheets for the static frontend, served under `/assets/css/`. `api/main.py::_serve_page()` rewrites
each `<link href>` to `?v=<content hash>` per request, so never hand-maintain `?v=`.
Page-level detail: [`../../README.md`](../../README.md); deep doc: `docs/PROJECT_DOCUMENTATION.md`.

| File | Responsibility |
|---|---|
| `tailwind-input.css` | Tailwind entry file (`@tailwind` directives); source for the generated bundle. |
| `tailwind.min.css` | **Committed, generated** Tailwind + DaisyUI bundle. Rebuild with `npm run css:build` (repo root) after adding or changing any Tailwind/DaisyUI class in `frontend/**/*.html` or `frontend/assets/js/**/*.js` (scan paths: `tailwind.config.js`). Do not hand-edit. |
| `badges.css` | Single source of truth for all badge geometry and colours (`badge-status-*`, `badge-type-*`, `badge-aff-*`, `badge-account-*`, `badge-claim-*`, plus `badge-ap-*` Assets & Property, `badge-att-*`/`badge-attrev-*` attendance, `badge-audit-*`, `badge-changereq-*`, `badge-corr-*`, `badge-cred-*`, `badge-darshak-*`, `badge-gender-*`, `badge-position-*`, `badge-role-*`). Pages must not redefine badge classes inline. |
| `nss-layout.css` | Authenticated-page layout: sidebar, topbar, user info, shared page components, the `.pw-reveal-*` password-toggle styles (`../js/nss-password.js`) (largest file). |
| `nss-datepicker.css` | Styles for the shared DD/MM/YYYY picker (`../js/nss-datepicker.js`). |
| `nss-combobox.css` | Styles for the select-or-propose combobox (`../js/nss-combobox.js`). |
| `nss-theme.css` | The shared look (owner 2026-11-19): outlined cards with a tinted header, tidy tables, aligned filter panels, form controls, buttons and detail lists in the Finance pages' style. Loaded LAST on `admin.html` and `dashboard.html` and scoped under `body.nss-theme` so it out-ranks the older inline styles without `!important`; it restyles the shared components every page already uses, plus the small pieces the redone screens share: `count-chip` / `empty-note`, `kpi-tile`, `count-tile` (the Member Directory's total and per-status tiles, which are also filters), `nss-modal*` (dialogs; the older admin `modal-card` dialogs are restyled in place), the Member / Person Directory row (`md-head`, `md-facts`, `md-tabs`) and spaced `dir-list` rows, `att-tile` (member Attendance), `mbr-action`, `fam-panel`, `doc-row`, `card-grid--detail` (User Detail). Per-feature styles stay in `style.css`. Guarded by `tests/ui/test_ui_theme.py`. |
| `style.css` | Tier 0 leftovers: small project-specific overrides (e.g. `[x-cloak]`). |
