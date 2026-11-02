# frontend/assets/js/

Alpine.js page logic and shared helpers for the static frontend. Served under `/assets/js/`;
`api/main.py::_serve_page()` rewrites each `<script src>` to `?v=<content hash>` per request, so never
hand-maintain `?v=`. CSP forbids inline handlers, so all behaviour lives in these files.
Page-level detail: [`../../README.md`](../../README.md); deep doc: `docs/PROJECT_DOCUMENTATION.md`.

| File | Loaded by | Responsibility |
|---|---|---|
| `auth.js` | all four pages | `NSSAuth`: JWT in localStorage, authed `apiFetch` with 401 refresh-retry, forced logout. Load before page JS. |
| `nss-config.js` | all four pages | Display-name overrides (e.g. `PROBATIONARY` -> "Darshaka"), badge-class maps, shared constants (`NSS.*`). |
| `login.js` | `login.html` | Login form, force-password-change, inline forgot/reset-password flow. |
| `register.js` | `register.html` | Multi-step self-registration (personal, membership claim, address). |
| `dashboard.js` | `dashboard.html` | Member dashboard (profile, own-address add/edit/remove, membership, family, governance, change requests, attendance tab). |
| `admin.js` | `admin.html` | `adminPanel()`: all admin tabs (users, roles, orgs, claims, geo approvals, governance, correspondence, attendance). Largest file. |
| `org-dashboard.js` | `dashboard.html`, `admin.html` | `orgDashboardTab()`: one component, six org-type layouts. |
| `attendance-register.js` | `dashboard.html`, `admin.html` | Tier 6 shared attendance-marking mixin installed into both `adminPanel()` and `dashboardApp()`; owns the register-screen percentage (`registerAttendancePercentage`) and the "ask before changing another marker's mark" taps (`attMarkTap`/`attMarkSetAll`); hosts override the `_afterAttendanceSaved` hook by defining it first. Live register: per-row `serverState`/`dirty`/`ackVersion`, `LIVE_POLL` (2 s active / 10 s after 60 s idle / 4-8-16-30 s back-off, paused when hidden or when the host tab is off screen via `_attRegisterShown`), Save sends only dirty rows with `expected_version` and resolves a 409 through `NSSDialog.confirm`; the panel stays open after Save. The markup is hand-copied in `admin.html` and `dashboard.html` and must stay in step. |
| `nss-layout.js` | `dashboard.html`, `admin.html` | Sidebar/topbar mixin, `currentUser` from `/auth/me`. |
| `nss-datepicker.js` | `dashboard.html`, `admin.html`, `register.html` | Shared DD/MM/YYYY picker; markup is injected, not written in HTML. |
| `nss-combobox.js` | `dashboard.html`, `admin.html`, `register.html` | Select-existing-or-propose-new combobox for geography fields. Instantiated by `dashboard.html`'s Address card (member self-service address form). |
| `nss-password.js` | `admin.html`, `login.html`, `register.html` | `x-pw-reveal` Alpine directive — the one show/hide eye toggle for every password input (styles: `.pw-reveal-*` in `nss-layout.css`). |
| `nss-location.js` | `admin.html`, `register.html`, `dashboard.html` | Country/state/district/PIN cascade helper. PIN list is narrowed by district (`loadPostalCodes(ctx, districtPk)`; sparse `city_village` seed => few PINs, new PINs stay enterable); every `load*` has a stale-response guard. |
| `nss-dialog.js` | `admin.html`, `dashboard.html`, `login.html` | Styled replacement for `alert()`/`confirm()`. |
| `dev-reload.js` | injected, never in HTML source | Dev-only auto-reload; injected by `api/main.py` only when `DEV_LIVE_RELOAD` is truthy. |
