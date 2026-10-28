# frontend/

**In Tier 5 (v0.11.0), the six original Tier 0-4 verification pages this README used to document as
current — `index.html`, `foundation.html`, `organization.html`, `person.html`, `family.html`,
`membership.html`, and their per-page JS (`app.js`, `foundation.js`, `organization.js`,
`person.js`, `family.js`, `membership.js`) — were deleted outright**, not just retired at the
routing level (see the "Retired standalone verification pages" comment in `api/main.py`). Their
functionality was folded into two of the four pages below instead: `admin.html` (Reference
Data, Organization Hierarchy, Person Directory, Member Directory, Roles & System Settings) and
`dashboard.html` (a Family tab, including the family-tree visualization that used to live in
`family.html`). The first half of the **File Reference** section further down still documents those six deleted
pages in detail — it's kept as historical reference (useful if this branch is ever reverted, or
for understanding where a given piece of `admin.html`/`dashboard.html` logic originally came
from) but describes files that no longer exist on disk. The File Reference subsections from
`assets/css/badges.css` onward (shared CSS/JS helpers, the Tier 5 page scripts, `style.css`,
Tailwind build files, images) describe files that **do** exist. For the current frontend, see
**"Tier 5 pages"** further down and the **Directory Structure** immediately below, both of which
reflect what's actually on disk now.

What's actually on disk now: a Login page, self-Registration page, Member Dashboard, and
Administration Dashboard (`login.html`/`register.html`/`dashboard.html`/`admin.html`). The
backing `GET/PATCH /api/v1/admin/claims/*` registration-claim-approval API (see
`api/routers/claim_approval.py`) has a frontend — it shipped as a "Registration Approvals" tab
inside `admin.html`/`admin.js` rather than as a standalone `claim-approval.html`; no
`claim-approval.html` file exists, but that's not a gap.

**Purpose:** these four pages are Nilachala Saraswata Sangha's authenticated login, self-service
registration, member dashboard, and administration console. `admin.html` is a real operational
administration dashboard, not a verification UI.

**Tech stack:** Tailwind CSS + DaisyUI (pre-built via Tailwind CLI — no longer CDN, see
`../package.json`/`../tailwind.config.js`), Alpine.js (CDN), vanilla
`fetch()` for JSON API consumption. No React/Vue/Angular. No Django templates. Node.js/npm is
only needed to rebuild CSS after a Tailwind/DaisyUI class change — the built CSS
(`assets/css/tailwind.min.css`) is committed, so running the app itself needs no Node.js.

**Served by:** FastAPI mounts this directory as static files. No
separate frontend server, no CORS configuration needed.

---

## Directory Structure

```
frontend/
├── login.html               Login page (Tier 5)
├── register.html            Self-registration page (Tier 5)
├── dashboard.html           Member Dashboard (Tier 5) — includes a Family tab
├── admin.html                Administration Dashboard (Tier 5) — Users, Create User/Person/Sangha
│                             Sevi/Organization, Reference Data, Geography, Organization Hierarchy,
│                             Assign Sakhas, Person Directory, Member Directory, Roles & System
│                             Settings, Geo Approvals (member-proposed geography review), Registration Approvals (claims review),
│                             Change Requests (Sakha transfer / Apply for Darshak review), Member Credentials,
│                             a collapsible Governance nav group (Body Types & Positions, Governance Bodies,
│                             Assignments, Elections; Tier 6), and Org Dashboard tabs
├── assets/
│   ├── css/
│   │   ├── badges.css          Single source of truth for ALL badge CSS (status/account/claim/type/affiliation/gender/role/muted) + data-identity typography — mirrors docs/03_Solution/ui/mockups/status_badge_preview.html
│   │   ├── style.css           Minimal project-specific CSS overrides
│   │   ├── nss-layout.css      Shared authenticated-page shell (sidebar/topbar/content area), sortable-table styles, shared form controls, org-switcher — see its File Reference entry below
│   │   ├── nss-datepicker.css  Styles for the `nss-datepicker.js` date-picker component — see its File Reference entry below
│   │   ├── nss-combobox.css   Styles for the `nss-combobox.js` select-or-propose dropdown (`.nss-cb-*`)
│   │   ├── tailwind-input.css  Tailwind directives (`@tailwind base/components/utilities`) — build input, see ../package.json
│   │   └── tailwind.min.css    Generated, committed build output (~87 KB) — DO NOT hand-edit; regenerate via `npm run css:build`
│   ├── img/
│   │   ├── nss-logo.png          NSS logo, compressed for web (~100 KB, was 1.4 MB)
│   │   ├── nss-logo-original.png Uncompressed original, kept for reference/reprocessing
│   │   └── ssm-mandir.webp        Tier 5 — currently unreferenced by any page/CSS/JS (see "Dead asset" below)
│   └── js/
│       ├── login.js         `loginApp()` — Alpine.js data component + API fetch logic for login.html
│       ├── register.js      `registerApp()` — Alpine.js data component + API fetch logic for register.html
│       ├── dashboard.js     `dashboardApp()` — Alpine.js data component + API fetch logic for dashboard.html (incl. the personal-tab Active Sessions list/revoke via `/api/v1/auth/sessions`)
│       ├── admin.js         `adminApp()` — Alpine.js data component + API fetch logic for admin.html
│       ├── auth.js          `NSSAuth` — JWT storage/refresh + authenticated `fetch()` wrapper
│       ├── nss-layout.js    `NSSLayout` — sidebar/topbar mixin shared by admin.html/dashboard.html
│       ├── nss-datepicker.js  `nssDatePicker()` Alpine component + markup injector (shared DD/MM/YYYY date field)
│       ├── nss-combobox.js  `nssCombobox()` Alpine component + markup injector (select-existing-or-propose-new dropdown for geographic fields)
│       ├── nss-dialog.js    `NSSDialog` — styled replacement for native alert()/confirm()
│       ├── nss-location.js  `NSSLocation` — shared country/state/district/postal-code cascade helper
│       ├── attendance-register.js  Tier 6 shared attendance-marking mixin (roster, search, toggle, submit) installed into both `adminPanel()` (admin.js) and `orgDashboardTab()` (org-dashboard.js); loaded by admin.html and dashboard.html
│       ├── dev-reload.js    Dev-only 1s polling auto-reload client; injected by `api/main.py` only when `DEV_LIVE_RELOAD` is truthy (polls `GET /__dev/frontend-version`), never referenced from the HTML sources
│       ├── org-dashboard.js `orgDashboardTab()` — Org Dashboard tab component embedded in admin.html/dashboard.html
│       └── nss-config.js   Shared `NSS` config object — badge-class lookups, Bye-Law display-name
│                           overrides, document-visibility rules (all pages)
└── README.md               This file
```

`admin.html` and `dashboard.html` share a sidebar/topbar shell (via `nss-layout.js` +
`nss-layout.css`); `login.html`/`register.html` are standalone pages that load only `nss-layout.css`
for its base resets. Which shared assets each page loads (verified against each file's `<head>`):

| Page | CSS (in order) | Shared JS (in order, before the page's own JS) |
|---|---|---|
| `login.html` | `tailwind.min.css`, `style.css`, `nss-layout.css` | `nss-config.js`, `nss-dialog.js`, `auth.js` → `login.js` |
| `register.html` | `tailwind.min.css`, `style.css`, `nss-layout.css`, `nss-datepicker.css`, `nss-combobox.css` | `nss-config.js`, `nss-location.js`, `auth.js`, `nss-datepicker.js`, `nss-combobox.js` → `register.js` |
| `dashboard.html` | `tailwind.min.css`, `style.css`, `badges.css`, `nss-layout.css`, `nss-datepicker.css`, `nss-combobox.css` | `nss-config.js`, `nss-dialog.js`, `auth.js`, `nss-layout.js`, `nss-datepicker.js`, `nss-combobox.js`, `attendance-register.js`, `org-dashboard.js` → `dashboard.js` |
| `admin.html` | `tailwind.min.css`, `style.css`, `badges.css`, `nss-layout.css`, `nss-datepicker.css`, `nss-combobox.css` | `nss-config.js`, `nss-location.js`, `nss-dialog.js`, `auth.js`, `nss-layout.js`, `nss-datepicker.js`, `nss-combobox.js`, `attendance-register.js`, `org-dashboard.js` → `admin.js` |

All four pages load Alpine.js 3.14.8 from the jsDelivr CDN (`defer`). Only `admin.html` and
`dashboard.html` load `badges.css` — `login.html`/`register.html` don't render any status/type/
affiliation badges. `nss-config.js` is loaded on all four pages. **Convention for future page
authors:** individual pages must **not** redefine `badge-status-*`/`badge-type-*`/`badge-aff-*`
classes in a page-local inline `<style>` block — add any new status/type/affiliation value to
`badges.css` (and, if it needs a lookup helper, to `nss-config.js`'s `NSS` object) instead, so
every page that loads it picks it up automatically.

---

## File Reference

> **⚠ Partly retired.** `index.html`, `foundation.html`, `organization.html`, `person.html`,
> `family.html`, `membership.html`, and their per-page JS (`app.js`, `foundation.js`,
> `organization.js`, `person.js`, `family.js`, `membership.js`) — every subsection from
> `### index.html` down to `### assets/js/membership.js` — were **deleted from disk** on the Tier 5
> branch (v0.11.0); see the header note at the top of this file. Those
> subsections are kept for historical reference only. **Everything from `### assets/css/badges.css`
> onward describes files that still exist** (shared CSS/JS helpers, the four Tier 5 page scripts,
> Tailwind build files, images) and is kept current.

### index.html

The single-page application entry point. Uses a two-tier layout designed
to fit all sections on a single screen without scrolling:

1. **System Status** — centred card at the top (narrow, `max-w-md mx-auto`)
2. **Responsive grid** below:
   - Left: RBAC Roles (clickable rows)
   - Centre: Permissions (catalogue)
   - Right: Role Permissions (drill-down on role click)

The grid adapts to screen width:

| Screen | Breakpoint | Layout |
|--------|-----------|--------|
| Mobile (< 768px) | default | 1 column (stacked) |
| Tablet (768px–1279px) | `md` | 2 columns (Role Permissions wraps below) |
| Desktop (≥ 1280px) | `xl` | 3 columns (all side by side) |

Layout fills the full viewport width with progressive side padding
(`px-6` mobile, `lg:px-10` tablet, `2xl:px-16` large desktop). No
max-width cap — tables stretch dynamically with the screen.

Each section is rendered by Alpine.js directives bound to the
`bootstrapApp()` data component defined in `app.js`.

| Section | Position | API Endpoint Consumed | What It Shows |
|---------|----------|----------------------|---------------|
| **Header** | Top, full width | — | NSS logo, "Nilachala Saraswata Sangha", "Tier 0 — Bootstrap Verification" |
| **System Status** | Top, centred | `GET /api/v1/bootstrap/health` | Three-state indicator: "Checking..." (spinner), "Database Connected" (green badge), or "Database Unavailable" (red badge). Never exposes raw database errors. |
| **RBAC Roles** | Left column | `GET /api/v1/bootstrap/roles` | Table: Code, Name, Class (badge), Scope, Active (✓/✗). Counter badge. Rows are clickable — selecting a role triggers the Role Permissions column. SYSTEM-class roles show a primary badge; ORGANIZATIONAL-class roles show a secondary badge. |
| **Permissions** | Centre column | `GET /api/v1/bootstrap/permissions` | Table: Code, Name, Module (badge), Active (✓/✗). Counter badge. In Tier 0 this is intentionally empty — the UI displays an explanatory message. |
| **Role Permissions** | Right column | `GET /api/v1/bootstrap/roles/{role_pk}/permissions` | Table: Code, Name, Module (badge), Active (✓/✗). Before selection: prompt text. After: role detail header (code, class, scope) + permissions table. Toggle deselect on same role. |
| **Footer** | Bottom, full width | — | Copyright notice: "© 2026 Nilachala Saraswata Sangha. All rights reserved." |

**Table features:**
- `table-sm` density (DaisyUI) — readable without being cramped
- Hover tooltips via `:title` binding on Code and Name cells
- `overflow-x-auto` wrapper per table — horizontal scroll on very narrow screens
- Active column: ✓ (green) for active, ✗ (red) for inactive
- Card padding scales: `p-4` base, `xl:p-6` on desktop
- Grid gap scales: `gap-4` base, `xl:gap-6` on desktop

**CSS/JS dependencies (loaded in `<head>`, identical on `index.html`, `foundation.html`,
`organization.html`, `person.html`, `family.html`, and `membership.html`):**

| Library | Version | Purpose |
|---------|---------|---------|
| Tailwind CSS + DaisyUI | `3.4.17` / `4.12.14`, pre-built via Tailwind CLI into `assets/css/tailwind.min.css` (`<link rel="stylesheet" href="/assets/css/tailwind.min.css">`) — no longer CDN, no SRI (same-origin static file, not a third-party script) | Utility-first CSS framework + component library (cards, tables, badges, alerts, spinners) |
| Alpine.js | `3.14.8`, pinned with `integrity`/`crossorigin` (SRI), still CDN | Reactive UI state and DOM binding |

The old unpinned `tailwindcss@2` prebuilt CSS and an incompatible `@tailwindcss/browser` 4.x
build were both removed as part of the security-hardening pass — see
`docs/03_Solution/code_explanations/SECURITY_CODE_EXPLANATIONS.md` and
`UI_CODE_EXPLANATIONS.md` in the same folder.

**How Alpine.js is wired:**

The root `<div>` declares `x-data="bootstrapApp()"` and `x-init="init()"`.
On page load, Alpine calls `bootstrapApp()` (from `app.js`) to create the
reactive data store, then calls `init()` which fetches health, roles, and
permissions in parallel. The HTML uses Alpine directives (`x-if`, `x-for`,
`x-text`, `x-show`, `@click`, `:class`) to render data reactively.

---

### assets/js/app.js

Alpine.js data component that manages all UI state and API communication.
Defines one global function: `bootstrapApp()`.

**Constants:**

| Name | Value | Purpose |
|------|-------|---------|
| `API_BASE` | `"/api/v1/bootstrap"` | Base URL for all API calls. No hardcoded hostname — uses relative paths so it works regardless of host/port. |

**`bootstrapApp()` — Alpine.js data component:**

Returns an object with reactive state properties and async methods.

**State properties:**

| Property | Type | Initial Value | Purpose |
|----------|------|---------------|---------|
| `health.loading` | boolean | `true` | Whether the health check is in progress |
| `health.connected` | boolean | `false` | Whether the database is reachable |
| `roles` | array | `[]` | List of role objects from the API |
| `rolesLoading` | boolean | `true` | Loading state for roles fetch |
| `rolesError` | boolean | `false` | Error state for roles fetch |
| `permissions` | array | `[]` | List of permission objects from the API |
| `permissionsLoading` | boolean | `true` | Loading state for permissions fetch |
| `permissionsError` | boolean | `false` | Error state for permissions fetch |
| `selectedRole` | object/null | `null` | Currently selected role (clicked in the table) |
| `rolePermissions` | array | `[]` | Permissions for the selected role |
| `rolePermsLoading` | boolean | `false` | Loading state for role-permissions fetch |
| `rolePermsError` | boolean | `false` | Error state for role-permissions fetch |

**Methods:**

| Method | Trigger | API Call | Behaviour |
|--------|---------|----------|-----------|
| `init()` | `x-init` on page load | — | Calls `fetchHealth()`, `fetchRoles()`, and `fetchPermissions()` in parallel via `Promise.all`. |
| `fetchHealth()` | Called by `init()` | `GET /api/v1/bootstrap/health` | Sets `health.connected = true` if the response contains `database: "connected"`. On any error (network failure, non-200 response), sets `health.connected = false`. Never exposes error details to the UI. |
| `fetchRoles()` | Called by `init()` | `GET /api/v1/bootstrap/roles` | Populates `roles[]` with the JSON array. On error, sets `rolesError = true`. |
| `fetchPermissions()` | Called by `init()` | `GET /api/v1/bootstrap/permissions` | Populates `permissions[]` with the JSON array (empty in Tier 0). On error, sets `permissionsError = true`. |
| `selectRole(role)` | `@click` on a role table row | `GET /api/v1/bootstrap/roles/{role_pk}/permissions` | If the clicked role is already selected, deselects it (toggle). Otherwise, sets `selectedRole` and fetches that role's permissions. On error, sets `rolePermsError = true`. |

**Error handling pattern:**

Every fetch method follows the same structure:
1. Set loading state to `true`, error state to `false`
2. `try`: fetch → check `res.ok` → parse JSON → update data
3. `catch`: set error state to `true` (no error details exposed)
4. `finally`: set loading state to `false`

---

### foundation.html

The Tier 1 Foundation Verification UI entry point, structurally parallel to `index.html`: same
head boilerplate and System Status card (reusing `GET /api/v1/bootstrap/health`), but with
"Foundation" active in the nav bar and subtitle "Tier 1 — Foundation Verification". Below the
status card, a DaisyUI `tabs tabs-boxed` bar with 4 tabs, each lazily loaded on first visit
(driven by `activeTab` / `switchTab(tab)` in `foundation.js`):

| Tab | Contents |
|-----|----------|
| **Master Data** | "Master Categories" table (code/name/description/order/active) + "Master Data Values" table with a category-filter `<select>` (`selectedCategoryCode`, `filterByCategory()`) |
| **System Config** | "System Settings" table (key/value/type/description) + "ID Sequences" table (code/name/prefix/padding/`formatSample()`-generated sample) — deliberately excludes `current_value` |
| **Geographic** | Breadcrumb of selected country › state › district, then 4 columns: Countries → States → Districts → Cities/Villages (each a clickable list, `selectCountry()`/`selectState()`/`selectDistrict()`, toggle-deselect on repeat click), plus a Postal Codes section keyed to the selected country; handles "no districts seeded" and "no cities/villages seeded" empty states |
| **Runtime Tables** | "Document Master" table (type/name/number/MIME/version) with an explanatory empty state; notes that `field_change_log` exists in the DB but isn't exposed in Tier 1 (deferred to Tier 5, needs auth) |

Loads `<script src="/assets/js/foundation.js">` at the bottom.

---

### assets/js/foundation.js

Alpine.js data component for `foundation.html`. Defines one global function:
`foundationApp()`. Constant `FND_API = "/api/v1/foundation"`.

**State groups:** `activeTab`, `health{loading,connected}` (shared pattern with `app.js`),
master data (`categories`, `masterData`, `selectedCategoryCode`), config (`settings`,
`sequences`), geographic (`countries`, `states`+`selectedCountry`, `districts`+`selectedState`,
`cities`+`selectedDistrict`, `postalCodes`), runtime (`documents`).

**Lifecycle:** `init()` calls `fetchHealth()` then `loadMasterTab()` — only the active tab's
data loads eagerly; `switchTab()` lazily triggers `loadConfigTab()`/`loadGeoTab()`/
`loadRuntimeTab()` on first visit to each tab, guarded so repeat switches don't re-fetch.

**API calls** (all relative, all under `${FND_API}` except the shared health check):
`GET /api/v1/bootstrap/health`, `GET ${FND_API}/categories`,
`GET ${FND_API}/master-data` (optional `?category_code=`), `GET ${FND_API}/settings`,
`GET ${FND_API}/sequences`, `GET ${FND_API}/countries`,
`GET ${FND_API}/states?country_pk=...`, `GET ${FND_API}/postal-codes?country_pk=...` (fetched
alongside states in `selectCountry()`), `GET ${FND_API}/districts?state_pk=...`,
`GET ${FND_API}/cities?district_pk=...`, `GET ${FND_API}/documents`. The API also exposes
per-PK detail routes (`/categories/{pk}`, `/master-data/{pk}`, `/settings/{key}`,
`/countries/{pk}`, `/states/{pk}`, `/districts/{pk}`, `/postal-code-mappings`) that this UI
doesn't consume yet.

**Error-handling pattern:** identical to `app.js` — loading=true/error=false → try/fetch/check
`res.ok`/parse JSON → catch sets error flag only (never exposes raw error text) → finally
clears loading. `selectCountry()`/`selectState()`/`selectDistrict()` all toggle-deselect:
clicking the already-selected item clears it and every downstream selection/data.

---

### organization.html

The Tier 2 Organization Verification UI entry point, structurally parallel to `index.html` and
`foundation.html`: same head boilerplate and System Status card (reusing
`GET /api/v1/bootstrap/health`), but with "Organization" active in the nav bar and subtitle
"Tier 2 — Organization Verification". Below the status card, a DaisyUI `tabs tabs-boxed` bar
with 3 tabs, each lazily loaded on first visit (driven by `activeTab` / `switchTab(tab)` in
`organization.js`):

| Tab | Contents |
|-----|----------|
| **Reference Data** | Two side-by-side tables: "Organization Types" (code/name/description/sort order, 8 rows) and "Lifecycle Statuses" (code/name/description/sort order, 6 rows) |
| **Organizations** | Filterable list (2-column layout): left/wide panel is the organization table (code/name/type badge/status badge/parent/location) with `<select>` filters for type and status (`selectedTypeFilter`/`selectedStatusFilter`, `filterOrganizations()` — status filter auto-disables for the 3 singleton institutional types; auto-selects the sole result when a filter narrows to exactly one org); right panel is a detail view — key fields, Address, Contact (phone/mobile), Online Presence (NSS + org-specific email/website/YouTube links), Geographic (district/state/country), Coordinates, and a Children sub-table (hidden entirely for types that can't have children — the 2 institutional singletons plus `PATHA_CHAKRA`/`SAKHA_ASANA`) that lazy-loads on row click (`selectOrganization()`, toggle-deselect on repeat click). Status badges use 6 dedicated `.badge-status-*` CSS classes (one per lifecycle status) rather than DaisyUI's generic semantic badges |
| **Hierarchy** | Flat recursive-CTE result rendered client-side as an indented tree using a `depthIndent(node.depth)` inline-style helper, with type badge, name, code, and a status badge per node |

Loads `<script src="/assets/js/organization.js">` at the bottom.

---

### assets/js/organization.js

Alpine.js data component for `organization.html`. Defines one global function:
`organizationApp()`. Constant `ORG_API = "/api/v1/organization"`.

**State groups:** `activeTab`, `health{loading,connected}` (shared pattern with `app.js`),
reference data (`orgTypes`, `orgStatuses`), organizations (`organizations`,
`selectedTypeFilter`, `selectedStatusFilter`, `selectedOrg`, `orgChildren`), hierarchy
(`hierarchy`). Each collection has matching `*Loading`/`*Error` booleans following the same
convention as `app.js`/`foundation.js`.

**Lifecycle:** `init()` calls `fetchHealth()` then `loadReferenceTab()` — only the active tab's
data loads eagerly; `switchTab()` lazily triggers `loadOrganizationsTab()`/`loadHierarchyTab()`
on first visit to each tab, guarded so repeat switches don't re-fetch (each guard checks the
target array is still empty before fetching).

**API calls** (all relative, all under `${ORG_API}` except the shared health check):
`GET /api/v1/bootstrap/health`, `GET ${ORG_API}/types`, `GET ${ORG_API}/statuses`,
`GET ${ORG_API}/organizations` (optional `?type_code=`/`?status_code=`, rebuilt by
`filterOrganizations()` on filter change), `GET ${ORG_API}/organizations/{pk}/children`
(fetched on `selectOrganization()`), `GET ${ORG_API}/hierarchy`.

**Error-handling pattern:** identical to `app.js`/`foundation.js` — loading=true/error=false →
try/fetch/check `res.ok`/parse JSON → catch sets error flag only → finally clears loading.
`selectOrganization(org)` toggle-deselects: clicking the already-selected row clears
`selectedOrg` and `orgChildren`.

**Helper:** `depthIndent(depth)` returns an inline `padding-left` style string
(`${depth * 1.5}rem`) used by the Hierarchy tab to visually nest tree rows without any
client-side tree-building logic — the API already returns depth per flat row.

---

### person.html

The Tier 3 Person Verification UI entry point, structurally parallel to the earlier tier pages:
same head boilerplate and System Status card (reusing `GET /api/v1/bootstrap/health`), but with
"Person" active in the nav bar and subtitle "Tier 3 — Person Verification". Below the status
card, a DaisyUI `tabs tabs-boxed` bar with 2 tabs, each lazily loaded on first visit (driven by
`activeTab` / `switchTab(tab)` in `person.js`):

| Tab | Contents |
|-----|----------|
| **Persons** | Filterable list (2-column layout): left/wide panel is the person table (person_id/name/gender/DOB/mobile/email/marital status/blood group/status) with `<select>` filters for gender, marital status, and blood group (all sourced from Foundation master-data via `GET /api/v1/foundation/master-data?category_code=`); right panel is a detail view — identity, demographics, contact, masked Aadhaar ("XXXX XXXX 1234"), emergency contact section (name/phone/relationship), remarks, and an Addresses sub-section showing each address as a card with type badge, primary badge, address lines, landmark, and resolved location chain (city/village, postal code, district, state, country). Addresses auto-load on row click (`selectPerson()`, toggle-deselect on repeat click). Person lifecycle states (Active/Deceased/Inactive) are derived from `is_active` + `date_of_death` and shown via dedicated `.badge-status-*` CSS classes |
| **Search** | Trigram fuzzy search input (min 2 chars, 300ms debounce) querying `GET /api/v1/person/search?q=`; results table (person_id/name/gender/DOB/mobile/email/status) in a grid layout (`xl:col-span-2`) alongside its own inline "Person Detail" panel — clicking a result calls `selectPerson(p)` directly (no tab switch, same pattern as `membership.js`'s Search tab); if the search returns exactly one result it is auto-selected |

Loads `<script src="/assets/js/person.js?v=2.2">` at the bottom (cache-bust version — see the
note under `family.html` above; treat as a snapshot, not re-verified every doc pass).

---

### assets/js/person.js

Alpine.js data component for `person.html`. Defines one global function: `personApp()`.
Constants `PERSON_API = "/api/v1/person"` and `FOUNDATION_API = "/api/v1/foundation"`.

**State groups:** `activeTab`, `health{loading,connected}` (shared pattern with `app.js`),
filter options (`genderOptions`, `maritalStatusOptions`, `bloodGroupOptions` — loaded from
Foundation master-data), persons (`persons`, `selectedGenderFilter`, `selectedMaritalFilter`,
`selectedBloodGroupFilter`, `selectedPerson`, `personAddresses`), search (`searchQuery`,
`searchResults`, `searchExecuted`, `_searchDebounce`). Each collection has matching
`*Loading`/`*Error` booleans.

**Lifecycle:** `init()` calls `fetchHealth()` then `fetchFilterOptions()` and `fetchPersons()`
in parallel via `Promise.all`. Filter options are loaded once via 3 parallel
`GET /api/v1/foundation/master-data?category_code=` calls using `Promise.allSettled`.

**API calls** (all relative):
`GET /api/v1/bootstrap/health`,
`GET /api/v1/foundation/master-data?category_code=GENDER|MARITAL_STATUS|BLOOD_GROUP` (filter
options), `GET /api/v1/person/persons?gender_code=&marital_status_code=&blood_group_code=`,
`GET /api/v1/person/persons/{person_pk}` (full detail with resolved master-data names),
`GET /api/v1/person/persons/{person_pk}/addresses` (resolved location chain),
`GET /api/v1/person/search?q=` (trigram similarity search).

**Error-handling pattern:** identical to other tier JS files — loading=true/error=false →
try/fetch/check `res.ok`/parse JSON → catch sets error flag only → finally clears loading.
`selectPerson(p)` toggle-deselects; detail and addresses are fetched in parallel via
`Promise.all` on row click.

**Helpers:**
- `formatName(p)` — joins first/middle/last name parts, filtering nulls
- `formatPhone(p)` — prepends country_phone_code if present
- `statusLabel(p)` — derives lifecycle label: "Active" (is_active + no death), "Deceased"
  (is_active + date_of_death), "Inactive" (!is_active)
- `statusBadgeClass(p)` — maps lifecycle to `.badge-status-active`/`-deceased`/`-inactive`

---

### family.html

The Tier 4 Family Verification UI entry point, structurally parallel to the earlier tier pages
for header/status boilerplate (same head boilerplate and System Status card reusing
`GET /api/v1/bootstrap/health`, "Family" active in the nav bar, subtitle "Tier 4 — Family
Verification"), but the body departs from every other tier page's tab-bar pattern. It renders a
tab-less 3-panel layout — `grid-cols-1 lg:grid-cols-[220px_1fr] xl:grid-cols-[220px_1fr_360px]` —
driven by a `viewMode` toggle ("My Family" / "Org View"; state `viewMode`, default `"admin"`,
despite an in-code comment still calling `"member"` "the current default"):

| Panel | Contents |
|-------|----------|
| **Left (220px)** | The view-mode toggle buttons, then — in **Org View** (`viewMode === 'admin'`) — an org breadcrumb (`orgBreadcrumb`, clickable via `breadcrumbNav(i)`) and a drill-down list of org-children cards (`orgChildren`, one card per child org with name/code/type plus inline family/member/person count badges once `orgChildrenStats` loads); once a Sakha is drilled into (`selectedSakhaCode` set) the panel switches to a **Families** list scoped to that Sakha. In **My Family** view (`viewMode === 'member'`) the panel shows the same Families list, unfiltered. Clicking a family row calls `selectFamily(f)` |
| **Center (1fr)** | "Family Tree" — a "View As" `<select>` (`viewerPersonPk`) letting the user re-root the relationship computation on any family member, then a dynamic generation-based tree rendered via `x-html="renderTree()"` inside `.tree-canvas`: couples grouped in dashed boxes, connector lines between generations, avatar circles color-coded by relationship (`av-viewer`/`av-spouse`/`av-parent`/... classes), viewer/head corner-indicator badges. Clicking any tree node calls `handleTreeClick($event)` → `selectPerson()` |
| **Right (360px, `xl` only)** | Family Info (ID/status/name/Sakha/formed date), then — once a person is selected from the tree or member list — a detail card with demographics, a spouse mini-card (click to jump to the spouse), a "Sangha Membership" block (Sangha Sevi ID, type/status badges, Sakha + Sakha Sangha ID with an amber "Different" mismatch badge when `isMemberSakhaMismatch()` is true), Parichaya Patra / Anumati Patra snapshots, and emergency contact; below that, a Members list (each row clickable, YOU/HEAD badges, amber mismatch warning icon) and a Head History list (bordered rows, "Now" badge when `effective_to` is null) |

The org-admin drill-down (`fetchOrgRoot()` → `fetchOrgChildren(orgPk)` → `drillIntoOrg(org)`)
starts from the Kendra root and lets an admin walk Kendra → Anchalika → ... → Sakha; drilling
into a `SAKHA_SANGHA`-typed org stops the org-tree descent and loads that Sakha's families
instead. Per-child family/member/person count badges are populated by a **separate,
non-blocking** background fetch (`_fetchOrgChildrenStats()`), so the org-children cards render
immediately and the (heavier, uncapped-recursion) stats badges fill in a beat later. The tree/
graph visualization consumes `GET /api/v1/family/families/{pk}/graph?viewer_person_pk=`; the
Sakha-mismatch badges consume `GET /api/v1/family/families/{pk}/sakha-alignment`.

Loads `<script src="/assets/js/family.js?v=24">` at the bottom (cache-bust version — treat this
and the other pages' `?v=N` strings below as a snapshot taken during this doc pass, not
something to re-verify line-by-line every time).

---

### assets/js/family.js

Alpine.js data component for `family.html`. Defines one global function: `familyApp()`.
Constants `FAMILY_API = "/api/v1/family"` and `ORG_API = "/api/v1/organization"`. Also defines
module-level tree-rendering helpers: `avatarClass(gen, isHead, isSpouse)` (relationship →
`.av-*` CSS class) plus the `GEN_LABELS`/`SPOUSE_LABELS` lookup tables.

**State groups:** `health{loading,connected}` (shared pattern with `app.js`); view mode
(`viewMode` — `"member"`/`"admin"`, default `"admin"`); org navigation (`orgBreadcrumb`,
`orgChildren`, `orgChildrenLoading`, `orgChildrenStats`, `selectedSakhaCode`); families
(`families`, `familiesLoading`, `familiesError`, `selectedFamily`, `detailLoading`); members and
head history (`familyMembers`, `membersLoading`, `headHistory`, `headLoading`); graph
(`viewerPersonPk`, `graphMembers`, `graphLoading`, `graphError`); selected-person detail
(`selectedPerson`, `selectedPersonDetail`, `selectedPersonLoading`, `selectedPersonMembership`,
`selectedPersonMembershipLoading`); Sakha alignment (`sakhaAlignment`, `sakhaAlignmentLoading`);
and the recursive tree itself (`treeHead`, `treeSpouse`, `treeNodes`, `_allTreePersons`,
rebuilt by `buildTree()` every time `graphMembers` changes). No `activeTab` state — this is the
only tier page without a DaisyUI tab bar.

**Lifecycle:** `init()` fires `fetchHealth()` without awaiting it ("Fire health check in
parallel — don't block data loading" per the code comment), then branches on `viewMode`:
`await this.fetchOrgRoot()` for `"admin"`, `await this.fetchFamilies()` for `"member"`.
`switchViewMode(mode)` re-runs the same branch when the user toggles "My Family"/"Org View",
resetting family/detail/org state first.

**API calls:**
`GET /api/v1/bootstrap/health`;
`GET ${ORG_API}/organizations?type_code=KENDRA` (`fetchOrgRoot()` — finds the Kendra root and
seeds `orgBreadcrumb`);
`GET ${ORG_API}/organizations/{pk}/children` (`fetchOrgChildren(orgPk)` — awaited, renders cards
immediately);
`GET ${ORG_API}/organizations/{pk}/children-stats` (`_fetchOrgChildrenStats(orgPk)` — fired from
inside `fetchOrgChildren()` but **not awaited by it**, so it resolves in the background and
populates `orgChildrenStats` after the org-children cards are already on screen);
`GET ${FAMILY_API}/families` (optional `?sakha_code=`, used both for the unfiltered "My Family"
list and the Sakha-scoped list once `drillIntoOrg()` lands on a `SAKHA_SANGHA`);
`GET ${FAMILY_API}/families/{pk}/members` and `GET ${FAMILY_API}/families/{pk}/head-history`
(fetched together via `Promise.all` in `selectFamily()`);
`GET ${FAMILY_API}/families/{pk}/graph?viewer_person_pk=` (`fetchGraph()` — called after a
family loads, defaulting `viewerPersonPk` to the head or the first member if there's no head —
and again from `changeViewer()`);
`GET ${FAMILY_API}/families/{pk}/sakha-alignment` (`fetchSakhaAlignment()`, fired
fire-and-forget from `selectFamily()`);
`GET /api/v1/person/persons/{person_pk}` and
`GET ${FAMILY_API}/person/{person_pk}/membership-summary` (fetched together via `Promise.all`
in `selectPerson()`, populating `selectedPersonDetail` and `selectedPersonMembership`).

**Error-handling pattern:** the top-level `fetchHealth()`/`fetchOrgRoot()`/`fetchFamilies()`
calls follow the usual loading/error-flag/finally shape. Everything downstream of a family or
org selection is treated as non-fatal on failure — `selectFamily()`'s members/head-history
fetch, `_fetchOrgChildrenStats()`, and `fetchSakhaAlignment()` all swallow errors silently
(comments call stats and alignment "supplementary"/"informational"), so a partial failure never
blocks the family's core fields, the org cards, or the tree from rendering. `fetchGraph()` is
the one exception in this cluster — it does set `graphError = true` on failure, surfaced in the
UI as "Failed to compute family graph." `selectFamily(f)`/`selectPerson(member)` both
toggle-deselect on repeat click of the same row, same convention as
`selectOrganization()`/`selectPerson()` (person.js).

**Helpers:**
- `formatName(m)` — joins first/middle/last name parts, filtering nulls (same implementation as
  `person.js`'s `formatName()` and `membership.js`'s `formatName()`)
- `displayRelationship(m)` — resolves a display label for a member: viewer flag → direct
  `relationship_label` (from `/graph`) → lookup in `graphMembers` by `person_pk` → viewer-PK
  match → `is_head` fallback → static `relationship_type_name`/`relationship_type_code`
- `getInitials(m)`, `getAvatarClass(m)` — avatar-circle initials and `.av-*` CSS class, falling
  back to a `graphMembers` lookup when called for a plain member-table row that lacks
  `_avatarClass`
- `getSpouseName(personPk)` / `getSpousePersonPk(personPk)` / `getSpouseInitials(personPk)` /
  `selectSpouse(personPk)` — resolve and navigate to a person's spouse via `graphMembers`
  (falling back to the synthesized `treeSpouse` for the viewer)
- `isMemberSakhaMismatch(personPk)` / `getMemberSakhaName(personPk)` — read
  `sakhaAlignment.members` to flag/display a member whose affiliated Sakha differs from the
  family's FAM-036 majority Sakha
- `buildTree()` — rebuilds the recursive couple/children tree from `graphMembers` every time the
  graph loads (synthesizes the viewer node, groups spouses into couples, links couples to
  parent couples via `parent_person_pks`, finds root couples with no parent in the graph)
- `renderTree()` / `_renderSubtree()` / `_renderCouple()` / `_renderPerson()` / `_esc()` — build
  the tree's HTML string by hand (not Alpine templates) for `x-html`, since the tree's depth and
  branching are only known at runtime; `_esc()` does minimal HTML-escaping of user-visible
  name/label text before interpolation
- `handleTreeClick(event)` — event-delegation click handler on the tree container; resolves the
  clicked `data-person-pk` back to a member object and calls `selectPerson()`

---

### membership.html

The Tier 4 Membership Verification UI entry point, structurally parallel to `person.html`: same
head boilerplate and System Status card, but with "Membership" active in the nav bar and
subtitle "Tier 4 — Membership Verification". Below the status card, a compact "Three-Tier Member
Identity" legend card explains the module's central non-obvious concept before any data loads:

| Tier | Column | Example | Scope |
|------|--------|---------|-------|
| Sangha Sevi ID | `sangha_sevi_id` | `SS1` | NSS-wide, permanent, never reused |
| Sakha Sangha ID (Local Sakha ERP Number) | `local_sakha_erp_id` | `ESS1192` | Sakha-scoped, auto-generated, changes on transfer |
| Kendra Number | `parichaya_patra.document_number` | `345/2026/2027` | Kendra-wide, annual (financial year) |

Below the legend, a DaisyUI `tabs tabs-boxed` bar with 2 tabs (driven by `activeTab` /
`switchTab(tab)` in `membership.js`):

| Tab | Contents |
|-----|----------|
| **Members** | Filterable list (2-column layout): left/wide panel is the member table (Sangha Sevi ID/Person ID/Person/Mobile/Email/Type/Status/Sakha/Sakha Sangha ID/Joining Date/Renewal Due) with `<select>` filters for membership type and status (`selectedTypeFilter`/`selectedStatusFilter`); right panel is a detail view — identity block, then four sub-sections that lazy-load together on row click: Sakha Affiliations (effective-dated history), Parichaya Patra (Kendra Number + issuance snapshot), Anumati Patra (hidden entirely for Associate members, who don't receive one — `x-show="selectedMember.membership_type_code !== 'ASSOCIATE'"`), and a Journey Timeline rendered as DaisyUI vertical steps |
| **Search** | Trigram + prefix search input (min 2 chars, 300ms debounce) querying `GET /api/v1/membership/search?q=` across all three identity tiers plus name, mobile, and email; same inline-detail-panel pattern as the Members tab — clicking a result calls `selectMember()` directly without switching tabs |

**UI label convention:** the database column `local_sakha_erp_id` is always displayed as
**"Sakha Sangha ID"** in this UI (table headers, detail panel, Parichaya Patra snapshot) — the
UI-facing label differs from both the DB column name and the API-contract term "Local Sakha ERP
Number"/"ERP Number" used in `docs/03_Solution/api/API_CONTRACT.md`. `PROBATIONARY` membership
type likewise displays as **"Darshaka"** (`typeDisplayName()`, MBR-007) — the database stores
`PROBATIONARY`, the portal shows the Odia/NSS operational term.

Loads `<script src="/assets/js/membership.js?v=4.0">` at the bottom (cache-bust version — see
the note under `family.html` above; treat as a snapshot, not re-verified every doc pass).

---

### assets/js/membership.js

Alpine.js data component for `membership.html`. Defines one global function:
`membershipApp()`. Constant `MEMBERSHIP_API = "/api/v1/membership"`.

**State groups:** `activeTab`, `health{loading,connected}` (shared pattern with `app.js`),
members (`members`, `selectedTypeFilter`, `selectedStatusFilter`, `selectedMember`,
`detailLoading`), sub-data (`affiliations`, `parichayaPatras`, `anumatiPatras`,
`journeyEvents` — all four fetched together per selected member), search (`searchQuery`,
`searchResults`, `searchExecuted`, `_searchDebounce`). Each collection has matching
`*Loading`/`*Error` booleans following the same convention as the other tier JS files.

**Lifecycle:** `init()` fires `fetchHealth()` without awaiting it (doesn't block data loading),
then awaits `fetchMembers()`. `switchTab()` re-fetches members only if the list is still empty
(guard against redundant refetch on repeat tab visits).

**API calls** (all relative, all under `${MEMBERSHIP_API}` except the shared health check):
`GET /api/v1/bootstrap/health`, `GET ${MEMBERSHIP_API}/members` (optional
`?type_code=&status_code=`), `GET ${MEMBERSHIP_API}/members/{sangha_sevi_pk}/affiliations`,
`GET ${MEMBERSHIP_API}/members/{sangha_sevi_pk}/parichaya-patra`,
`GET ${MEMBERSHIP_API}/members/{sangha_sevi_pk}/anumati-patra`,
`GET ${MEMBERSHIP_API}/members/{sangha_sevi_pk}/journey` (last four fetched together via
`Promise.all` in `selectMember()`), `GET ${MEMBERSHIP_API}/search?q=`.

**Error-handling pattern:** identical to the other tier JS files — loading=true/error=false →
try/fetch/check `res.ok`/parse JSON → catch sets error flag only → finally clears loading.
`selectMember(member)` toggle-deselects on repeat click of the same row, same as
`selectPerson()`/`selectOrganization()`.

**Helpers:**
- `formatName(m)` — same implementation as `person.js`'s `formatName()`
- `typeDisplayName(m)` — delegates to shared `NSS.typeDisplayName()` (`assets/js/nss-config.js`);
  still returns `"Darshaka"` for `PROBATIONARY` (UI-label convention, see above)
- `typeBadgeClass(m)`, `statusBadgeClass(m)`, `affBadgeClass(a)`, `docBadgeClass(doc)` — thin
  wrappers delegating to shared `NSS.typeBadgeClass()`/`NSS.statusBadgeClass()`/
  `NSS.affBadgeClass()` (`assets/js/nss-config.js`), which map membership type, lifecycle
  status, affiliation status, and document (Parichaya/Anumati Patra) status to `.badge-type-*`/
  `.badge-status-*`/`.badge-aff-*` classes now centralized in `assets/css/badges.css` — no
  longer defined inline in `membership.html`'s own `<style>` block

---

### assets/css/badges.css

Single source of truth for every badge CSS class used across the pages, plus the three-tier
identity typographic classes. Loaded by `admin.html` and `dashboard.html` only (see the page/asset
matrix under Directory Structure), right after `style.css` and before `nss-layout.css`. The
prefix counts below were re-verified against the file (18 `badge-status-*`, 4 `badge-account-*`,
3 `badge-claim-*`, 4 `badge-type-*`, 3 `badge-aff-*`, 3 `badge-gender-*`, 3 `badge-role-*`, 4 `badge-changereq-*`,
4 `badge-cred-state-*`, 4 `badge-cred-status-*`, 6 `data-*`).

Its geometry and lifecycle palette are copied **verbatim** (px values included) from
`docs/03_Solution/ui/mockups/status_badge_preview.html`, which is the visual source of truth, so
the two can be diffed by eye. If a badge must change appearance, change the preview page and this
file together.

**Fill convention (load-bearing):** a SOLID fill with white text means a state the record actually
holds. An OUTLINE badge (`.badge-muted`) is metadata/annotation — record counts, "not implemented"
placeholders, data-type hints. This keeps real statuses visually dominant.

**Class families:**

| Prefix | Count | Purpose |
|--------|-------|---------|
| `.badge-status-*` | 18 | Unified lifecycle status — the full `master_data` `STATUS` category (16 values) plus the two credential-only values `cancelled`/`replaced` |
| `.badge-account-*` | 4 | `user_account.account_status` (`active`/`locked`/`inactive`/`pending-approval`) — a separate domain with its own CHECK constraint, so it does not borrow `badge-status-*` |
| `.badge-claim-*` | 3 | `registration_claim.claim_status` (`pending`/`approved`/`rejected`) |
| `.badge-muted` | 1 | Outline annotation badge. **Replaces DaisyUI's `.badge-ghost`**, which is unusable here because the shared `.badge` base forces white text |
| `.badge-type-*` | 4 | Membership type (`probationary`/`regular`/`associate`/`honorary`) |
| `.badge-aff-*` | 3 | Sakha affiliation status (`active`/`archived`/`reactivated`) |
| `.badge-gender-*` | 3 | Gender (`male`/`female`/`other`) |
| `.badge-changereq-*` | 4 | `membership_change_request.status` (`pending-release`/`pending-accept`/`completed`/`rejected`; both `REJECTED_BY_*` values share `rejected`) — Sakha Transfer / Apply for Darshak |
| `.badge-cred-state-*` | 4 | Per-member credential health (`ok`/`expiring`/`lapsed`/`missing`) — admin Credentials tab |
| `.badge-cred-status-*` | 4 | Individual Anumati/Parichaya Patra row status (`active`/`expired`/`lapsed`/`cancelled`) — credential timeline |
| `.badge-marital` | 1 | Marital status (single generic style, not per-value) |
| `.badge-role-*` | 3 | Role indicators (`viewer` = "YOU", `head` = "HEAD", `admin` = "ADMIN") |
| `.badge-identity` / `.badge-org` / `.badge-attention` | 3 | Context chips — Sangha Sevi ID, organization name, needs-action. They exist so pages stop hand-rolling `style="background:…"` on `.badge` elements |
| `.data-*` | 6 | Typographic classes for identity fields: `data-sevi-id`/`data-erp-no`/`data-kendra-no` (three-tier identity, theme-aware via DaisyUI CSS variables), `data-sakha-name`, `data-family-id`, `data-label` |

**Rules for future page authors:**

- Do **not** define `.badge`, `.badge-xs/sm/md/lg`, `badge-status-*`, `badge-type-*`, `badge-aff-*`,
  `badge-account-*`, or `badge-claim-*` in a page-local inline `<style>` block — this file is the
  only place they may live.
- Do **not** set badge colours via inline `style=` or Tailwind `bg-*`/`text-*` utilities. If you
  need a colour that doesn't exist, add a named class here.
- Do **not** use raw DaisyUI variants (`badge-ghost`, `badge-success`, `badge-info`, `badge-error`).
  They carry no domain meaning and `badge-ghost` renders invisible against the white-text base.
- Size by context: `badge-xs` in tables, `badge-sm` in cards, `badge-md`/`badge-lg` elsewhere.

The base rules use `!important` to override DaisyUI's compiled `.badge`/`.badge-xs` styles, which
would otherwise win on specificity/order.

There is deliberately **no** second badge system. Page chrome that merely looks badge-like —
`.count-badge`, `.version-badge`, `.step-badge`, `.nss-pill-btn`, `.tab-pill`, the topbar
`.role-badge` — lives in `nss-layout.css`/page styles and is **not** a status badge; styling a tab
control or a version label as a lifecycle pill would be wrong.

---

### assets/js/nss-config.js

Global `NSS` config object, loaded by all four pages' `<head>` (first of the shared scripts, before
`nss-location.js`/`nss-dialog.js`/`auth.js`/etc. and the page's own `*.js` file). Not an Alpine.js component (no `x-data` registration) — plain shared
state/logic that any page's inline bindings or `*.js` file calls directly as `NSS.methodName()`.

**What it provides:**

| Member | Purpose |
|--------|---------|
| `TYPE_DISPLAY_NAMES` / `typeDisplayName(code, dbName)` | Bye-Law display-name overrides (currently just `PROBATIONARY` → `"Darshaka"`, MBR-007); falls back to the API's `value_name`, then the raw code |
| `STATUS_BADGE_MAP` / `statusBadgeClass(code)` | Lifecycle status → `.badge-status-*` class |
| `TYPE_BADGE_MAP` / `typeBadgeClass(code)` | Membership type → `.badge-type-*` class |
| `AFF_BADGE_MAP` / `affBadgeClass(status)` | Affiliation status → `.badge-aff-*` class |
| `GENDER_BADGE_MAP` / `genderBadgeClass(code)` | Gender → `.badge-gender-*` class |
| `ACCOUNT_BADGE_MAP` / `accountBadgeClass(status)` | `user_account.account_status` → `.badge-account-*` class |
| `CLAIM_BADGE_MAP` / `claimBadgeClass(status)` | `registration_claim.claim_status` → `.badge-claim-*` class |
| `CREDENTIAL_STATE_BADGE_MAP` / `credentialStateBadgeClass(state)` | Per-member credential health (`OK`/`EXPIRING`/`LAPSED`/`MISSING`) → `.badge-cred-state-*` |
| `CREDENTIAL_STATUS_BADGE_MAP` / `credentialStatusBadgeClass(status)` | Credential row status (`ACTIVE`/`EXPIRED`/`LAPSED`/`CANCELLED`) → `.badge-cred-status-*` |
| `CHANGE_REQUEST_BADGE_MAP` / `changeRequestBadgeClass(status)` | `membership_change_request.status` (all five values) → `.badge-changereq-*` |
| `CHANGE_REQUEST_STATUS_LABELS` / `changeRequestStatusLabel(status)` | Human-readable label for the same statuses (e.g. `PENDING_SOURCE_RELEASE` → "Awaiting your current Sakha"); falls back to the raw code |
| `showParichayaPatra(typeCode)` | Always `true` — kept as a named method for one documented home, even though the rule doesn't currently vary |
| `showAnumatiPatra(typeCode)` | `true` for every membership type except `ASSOCIATE` (MBR-019A/B) — used by the Anumati Patra `x-show` bindings on `admin.html`/`dashboard.html` (originally `membership.html`/`family.html`) |
| `DEFAULT_COUNTRY_CODE` (`"+91"`), `MAX_PAGE_SIZE` (`500`), `PASSWORD_MIN_LENGTH` (`8`), `REDIRECT_DELAY_MS` (`1500`) | Shared constants used across `register.js`/`admin.js`/etc. instead of scattered magic numbers |
| `SORT_DIR_ASC`/`SORT_DIR_DESC`, `isBlankValue(v)`, `compareValues(a, b)`, `sortRows(rows, key, dir, accessor)`, `toggleSort(currentKey, currentDir, clickedKey)`, `sortIcon(...)`, `sortAria(...)` | Shared click-to-sort primitive for every data table. Blank/null always sorts last, natural numeric ordering (`SS2` before `SS10`), real dates compare chronologically. `sortRows` is client-side and only valid for tables holding the **complete** result set — server-paginated tables must send `sort_by`/`sort_dir` and re-fetch from page 1 instead (same `toggleSort`/`sortIcon` state helpers either way). Styled by the `.sortable`/`.sort-ind` rules in `nss-layout.css` |
| `formatName(m)`, `formatPhone(code, number)`, `formatDate(dateStr)`, `formatDateTime(dateStr)`, `escapeHtml(s)` | Shared display/escaping helpers (the old per-page-JS `formatName()` copies were folded into this one) |
| `statusMessage(status)`, `errorMessage(data, status)`, `extractError(res)` (async) | Turn an API error response into a readable sentence — handles a string `detail`, FastAPI/Pydantic's list-of-objects `detail` (see `api/error_handlers.py`), and bare HTTP statuses, so the UI never shows `[object Object]` or a raw status code alone |

All six badge-class helpers fall back to `badge-muted` (the outline annotation style) for unknown codes —
never to `badge-ghost`, which is invisible against the white-text `.badge` base.

Extracted from what used to be near-duplicate `if`/`else` chains inside `membership.js` (and an
inline `!== 'ASSOCIATE'` check repeated in both `membership.html` and `family.html`) — see
`docs/03_Solution/code_explanations/UI_CODE_EXPLANATIONS.md` §2.14 for the full walkthrough.

---

### assets/js/auth.js

Global `NSSAuth` object (217 lines) — the shared JWT/session layer. Loaded on all four pages; on
`login.html`/`register.html` it's used only for `redirectIfLoggedIn()`/token storage. Include it
**before** any page-specific JS.

| Member | Purpose |
|--------|---------|
| `TOKEN_KEY` / `REFRESH_KEY` / `USER_KEY` | `localStorage` keys: `nss_access_token`, `nss_refresh_token`, `nss_user` |
| `getAccessToken()`, `getRefreshToken()`, `setTokens(access, refresh)`, `clearTokens()`, `isLoggedIn()` | Token storage |
| `getCachedUser()` / `setCachedUser(user)` | Cached `/auth/me` profile |
| `decodePayload(token)` / `isTokenExpired(token)` | Client-side JWT payload peek (no signature validation); "expired" includes a 30-second buffer |
| `refreshAccessToken()` | `POST /api/v1/auth/refresh` with the stored refresh token; clears tokens on a non-OK response |
| `apiFetch(url, opts)` | `fetch()` wrapper: refreshes first if the access token is missing/expired, injects `Authorization: Bearer`, defaults JSON `Content-Type` for string bodies, defaults `cache: "no-store"` (authenticated per-user data must never be replayed from the browser cache), and on a 401 retries once after a refresh before calling `logout()` and throwing |
| `authHeaders()` | Raw `Authorization` header object for manual `fetch()` calls (no auto-refresh) |
| `requireAuth()` | Redirects to `/login` and returns `false` if not logged in |
| `redirectIfLoggedIn(target = "/dashboard")` | For the login/register pages — redirects away if a non-expired access token exists |
| `logout()` | Best-effort `POST /api/v1/auth/logout` (revokes the server-side `user_session`), clears tokens, redirects to `/login` |

---

### assets/js/nss-layout.js

Global `NSSLayout` object (326 lines) — the sidebar/topbar mixin for `admin.html` and
`dashboard.html` only. Backed by `assets/css/nss-layout.css`.

- `NSSLayout.mixin()` — returns state/methods to spread into a page's Alpine component
  (`...NSSLayout.mixin()`): `sidebarOpen`, `authLoading`, `currentUser`, `navGroupsCollapsed` +
  `isNavGroupCollapsed(key)`/`toggleNavGroup(key)` (collapsed sidebar groups persist in
  `localStorage` under `nss_nav_groups_collapsed`, shared across both pages), `topbarUserInfo()`
  (name, SS ID, local Sakha ERP ID, Sakha name, role badges — HTML string for `x-html`),
  `sidebarFooterInfo()` (avatar initials, name, SS ID, logout button), `_esc()`, `logout()`.
  These are **methods, not getters**, deliberately — object spread evaluates getters once and
  copies the value — so the HTML binds `x-html="topbarUserInfo()"` with parentheses.
- `NSSLayout.initAuth(component, opts)` — call from `init()`: `requireAuth()`, then
  `GET /api/v1/auth/me` into `component.currentUser` (cached via `NSSAuth.setCachedUser`);
  on failure clears tokens and redirects to `opts.redirectUrl` (default `/login`); optional
  `opts.requiredPermissions` (any-of) redirects to `/dashboard` if the user holds none. Returns
  `true`/`false`.
- A single document-level `click` listener keyed on `data-nss-action="logout"` handles the
  sidebar-footer logout button — the footer is injected as an HTML string via `x-html`, and the
  CSP's `script-src` omits `'unsafe-inline'`, so inline `onclick=` handlers aren't allowed
  (`docs/03_Solution/security/TIER5_SECURITY_AUDIT.md` A2). Add any new layout actions there
  rather than reintroducing inline handlers.

---

### assets/js/nss-datepicker.js

The shared DD/MM/YYYY date field (401 lines). Three globals:

- `nssDatePicker(modelPath, opts)` — Alpine component stored as `x-data="nssDatePicker('form.date_of_birth')"`;
  reads/writes an **ISO `YYYY-MM-DD`** value at `modelPath` (resolved against the parent `x-data`
  scope) and displays `DD/MM/YYYY`. Options: `maxToday` (reject future dates, e.g. DOB),
  `minYear`/`maxYear` (default 1900–2100). Exposes `open`, `display`, `invalid`/`errorMsg`
  (set only for a complete-but-unacceptable date, so a half-typed value never flashes an
  error), `onInput()`, `prevMonth()`/`nextMonth()`, `onMonthChange()`/`onYearInput()`,
  `selectDay()`, `goToday()`, `clearDate()`, `validate()`/`isValidDate()`.
- `nssDatePickerMarkup(cfg)` — builds the canonical input + calendar-popup HTML
  (`cfg.inputClass`, `cfg.disabledExpr`, `cfg.placeholder`).
- `nssDatePickerExpand(scope)` — injects that markup into every `[x-data^="nssDatePicker("]`
  root found in `scope`, recursing into `<template>` content (most date fields sit inside
  `x-if`/`x-for` blocks, which `querySelectorAll` doesn't descend into). Idempotent (skips roots
  carrying `data-nss-dp-built`), stamps `data-nss-dp="<modelPath>"` on each root as a stable test
  hook, and reads per-field overrides from `data-dp-input-class`/`data-dp-disabled`/
  `data-dp-placeholder`. Runs on `DOMContentLoaded`, i.e. before Alpine starts.

Pages therefore declare only the `x-data` + a `<label>`, **not** the input markup; see
`tests/README.md` → "Locating date fields in UI tests" for the resulting selector convention.
Loaded by `register.html`, `dashboard.html`, `admin.html`.

---

### assets/js/nss-combobox.js, assets/css/nss-combobox.css

`nssCombobox(modelPath, opts)` (405 lines JS, 152 CSS) — searchable "select an existing value OR
propose a new one" dropdown for the geographic address fields (Member-Assisted Geographic Entry,
SOL-ARCH-010 Amendment). Same design as the date picker: an Alpine factory bound to a model path,
with `nssComboboxMarkup(cfg)`/`nssComboboxExpand(scope)` injecting the popup markup on
`DOMContentLoaded`. Options: `optionsPath` (parent-scope array, e.g. the one `nss-location.js`
fills), `valueKey`/`labelKey`, `allowNew` (default true), `proposeUrl`/`proposeField`/
`proposeParams`, `minChars`, `placeholder`. A proposal `POST`s to a `.../propose` endpoint
(`POST /api/v1/foundation/districts|postal-codes|post-offices/propose` in `api/routers/foundation.py`),
which creates a PENDING row; the returned row is appended to the options and selected. Reviewed in
the **Geo Approvals** tab of `admin.html` (`geoApprovals`, `loadGeoEntries()`).
**Wiring note:** the script/stylesheet are loaded by `register.html`, `dashboard.html` and
`admin.html`, but no page currently instantiates `x-data="nssCombobox(...)"` (only the doc comment
in `nss-combobox.js` does) — it is loaded but not yet used.

---

### assets/js/nss-dialog.js

Global `NSSDialog` object (252 lines) — styled, promise-based replacements for native
`alert()`/`confirm()`, in the NSS palette, using inline styles (so it works regardless of
which CSS framework is loaded) and `x-ignore` on its overlay (Alpine never processes it).

- `await NSSDialog.alert(message, title = "")` — single OK button; also closes on overlay click.
- `await NSSDialog.confirm(message, { title, confirmText, cancelText, confirmClass })` →
  `true`/`false`; `confirmClass` accepts `"primary"`/`"danger"`/`"warning"` (legacy DaisyUI names
  `btn-primary`/`btn-error`/`btn-warning` are mapped for backwards compatibility); overlay click
  cancels.

Loaded as its own `<script>` by `login.html`, `dashboard.html`, `admin.html` — **not**
`register.html`. (The file's header comment says it is "included via nss-config.js" — that is
stale; there is no such include, each page loads it explicitly.)

---

### assets/js/nss-location.js

Global `NSSLocation` object (153 lines) — the shared country → state → district → postal-code
cascade, replacing three near-identical copies in `register.js` and `admin.js` (org edit + org
create). `NSSLocation.create({ fetchFn, basePath, arrays, form })` returns a stateless set of
methods that each take the Alpine component (`ctx`) as their first argument: `loadCountries`,
`loadStates`, `loadDistricts`, `loadPostalCodes` (keyed on state), `onCountryChange`,
`onStateChange`, `onDistrictChange`. `fetchFn` is plain `fetch` or `NSSAuth.apiFetch`;
`basePath` defaults to `/api/v1/foundation` (authenticated — `admin.js`) and `register.js` passes
`/api/v1/register` to hit the public reference-data endpoints instead. Form field names are fixed
(`country_pk`, `state_pk`, `district_pk`, `city_village_name`, `postal_code_pk`/
`postal_code_value`). Loaded by `register.html` and `admin.html`.

---

### assets/js/org-dashboard.js

Global `orgDashboardTab()` Alpine factory (799 lines) — the **Org Dashboard** tab, embedded in
both `admin.html` and `dashboard.html`'s own sidebar/topbar shell (not a standalone page; each
host instantiates it via a nested `x-data="orgDashboardTab()"` + `init(orgPk)` and wires its own
`openOrgDashboard(orgPk)`, `myOrgDashboardPk`, and `myOrgDashboardLabel`). It renders one of six
layouts by the viewed org's `organization_type_code` (`isSakha`/`isAnchalika`/`isZilla`/
`isKendra`/`isPathaChakra`/`isMahila`) — the six ORGANIZATIONAL roles in `role_master`
(SOL-ADMIN-004 §8.7). Sakha/Anchalika/Zilla/Kendra follow
`docs/03_Solution/ui/mockups/0{3,5,6,2}_*_dashboard.html`; Patha Chakra and Mahila Sangha have no
mockup and reuse the same card idiom.

Endpoints consumed (all via `NSSAuth.apiFetch`): `GET /api/v1/organization/organizations/{pk}`;
Sakha tier — `GET /api/v1/membership/members` (counts + 5 most recent by `joining_date`),
`GET /api/v1/family/families?sakha_organization_pk=`,
`GET /api/v1/membership/organizations/{pk}/darshak-summary`; Anchalika/Zilla/Kendra tiers —
`GET /api/v1/organization/organizations/{pk}/children-stats` and
`.../{pk}/stats`. Every figure shown is real; attendance % and renewal tracking (shown in the
mockups) have no backing DB tables and are rendered as honest "not tracked yet" placeholders.
Numbers that couldn't be determined render as "—" (`statNum()`), and a family count that hit the
page limit renders as a lower bound ("N+").

---

### assets/js/login.js, register.js, dashboard.js, admin.js

The four per-page Alpine components — each defines one primary global factory, used by the
page's root `x-data`:

| File | Factory | Notes |
|------|---------|-------|
| `login.js` (288 lines) | `loginApp()` | `login()` → `POST /api/v1/auth/login`; `changePassword()` (forced change / expiry); `openForgotPassword()`/`submitForgotPassword()`/`submitResetPassword()` drive the **in-page** forgot/reset-password panels via `POST /api/v1/auth/forgot-password` and `/reset-password` (there is no separate forgot-password page) |
| `register.js` (753 lines) | `registerApp()` | 3-step form — `step` 1 personal details, 2 optional membership claim (Sakha chosen first, then Local Sakha Number), 3 password — then a success screen (`step = 4`, shows the Person ID only, pending admin approval). A "Previously registered? Add membership" mode (`goLookupExisting()` → `step = 'lookup'`, `lookupExisting()` → `POST /api/v1/register/lookup-existing` with Person ID + DOB, then `submitExistingClaim()` → `POST /api/v1/register/claim`) is for people who registered without membership: they have no account yet, so the claim creates it. `submit()` dispatches to `submitNewRegistration()` or `submitExistingClaim()` by `mode`. A standalone "Apply for Darshak" entry (`goDarshakEntry()` → `step = 'darshak-entry'`, linked from step 1 as "New Darshak? Apply here") asks whether the applicant already has a Person ID (`startDarshakExisting()` reuses the lookup/claim path; `startDarshakNew()` reuses the step-1 wizard with `has_membership = true`), sets `darshakFlow`, pre-locks the membership type to Darshaka (`darshakaTypePk()`) and hides the Local Sakha Number field (system-generated at admin approval) Form state (minus password) is drafted to `sessionStorage` (`nss_register_draft`) and restored on reload; the Sakha dropdown lists all Sakhas with those near the chosen state/district first (`sakhasNearFirst`). Uses `NSSLocation` against `/api/v1/register/*` and `POST /api/v1/register/check-duplicate`; submits `POST /api/v1/register` |
| `dashboard.js` (5177 lines) | `dashboardApp()` (+ module-level `_avatarClass()`, `_buildCoupleTree()`; `_renderGenSubtree()` is a method) | Member dashboard: `personal`, `membership`, `family`, `documents`, `attendance`, `governance`, and `orgDashboard` tabs (the governance tab lists "Open Elections — Cast Your Vote" via `GET /api/v1/governance/elections/open-for-voting` + `POST /elections/{pk}/votes/self` (`castMySelfVote()`), and "Governance Bodies" via `GET /governance/public/national-bodies`; the Find-a-Sakha view loads President/Secretary via `GET /governance/public/sakha-office-bearers`; a `canViewGovernance` getter adds a sidebar link to `/admin#govCatalog`; the membership tab has a "My Change Requests" panel — Sakha Transfer / Apply for Darshak — over `/api/v1/membership/change-requests`, `openChangeRequestModal()`/`submitChangeRequest()`/`_loadMyChangeRequests()`); admin entries are added to the sidebar dynamically from the caller's role scopes (`ADMIN_TAB_MAP`, `DASHBOARD_LEVELS`, `ROLE_ORG_LABELS`, `FAMILY_BROWSER_ROLES`) |
| `admin.js` (8357 lines) | `adminApp()` (+ module-level `ROLE_ORG_LABELS`, `DASHBOARD_LEVELS`, a copy of `dashboard.js`'s — there is no cross-file include mechanism) | Admin console; tabs (from `admin.html`'s `activeTab` values): `users`, `detail`, `create`, `createSS`, `createOrg`, `organizations`, `orgHierarchy`, `assignSakha`, `refData`, `geography`, `geoApprovals`, `personDir`, `memberDir`, `claims`, `changeRequests`, `credentials`, `govCatalog`, `govBodies`, `govAssignments`, `govElections`, `sysSettings`, `password`, `orgDashboard`; a `tabLoaders` map in `init()` re-fires each lazy tab's loader on hash-restore. **Governance (Tier 6):** `canViewGovernance` (`GOVERNANCE_VIEW` or `GOVERNANCE_MANAGE`) shows the collapsible Governance nav group; `canManageGovernance` (`GOVERNANCE_MANAGE`) gates every create/edit/end/declare/apply control. ~38 `*Gov*` methods cover body types and positions (`loadGovCatalog`, `createGovBodyType`, `createGovPosition`, …), bodies (`loadGovBodies`, `createGovBody`, `saveGovBody`), assignments (`createGovAssignment`, `endGovAssignment`) and elections (`createGovElection`, `changeGovElectionStatus`, `createGovNomination`, `loadGovTally`, `declareGovResult`, `applyGovResult`, `resetGovBallots`, `castOfficerVote`). The user-detail view also shows a read-only "Auto-Granted Access (§63)" card from `selectedUser.auto_granted_scopes` (derived live from governance positions, not stored `user_role` rows, so no Revoke). The `changeRequests` tab (`loadChangeRequests`, release/accept/reject actions) and `credentials` tab (`loadCredentials`, `openCredentialTimeline`, `submitIssueCredential`, `submitPromote`) were also added |

(The header comments of `admin.js` — "Tabs: Users list, User detail, Create user, Change password"
— and `dashboard.js` — "same logic as family.html" — are stale.)

---

### assets/css/nss-layout.css

Shared authenticated-page styles (504 lines), used by `dashboard.html`/`admin.html` and also
loaded by `login.html`/`register.html` (base resets/body). Palette in the header comment:
Navy `#1B2A4A`, Teal `#0D7377`, Gold `#C8960C`, Saffron `#DC7831`, Lotus `#D64A6A`. Sections, in
file order: Sidebar (`.sidebar`, `.sidebar-brand`, `.sidebar-nav`, `.nav-section-label`, ...),
Main Content, Top bar, Topbar user info (`.user-name`/`.user-ss-id`/`.user-sakha-id`/
`.user-sakha-name`/`.role-badge`, rendered by `NSSLayout.topbarUserInfo()`), Content area, Common
components, **Sortable table headers** (`.sortable`, `.sort-ind`, `aria-sort` styling — pairs with
`NSS.toggleSort`/`sortIcon`/`sortAria`) and the card-directory **sort bar** (`.nss-dir-sortbar`,
`.nss-mini-th`, `.nss-search-th`), **Shared form controls**, Inactive row treatment, Detail grid,
Count badge, **Org switcher** (the `orgDashboard` tab), **CSP-safe hover/focus states** (classes such as
`.nss-search-input` that replace inline `onfocus`/`onblur`/`onmouseover`/`onmouseout` handlers,
which the CSP's `script-src` would block), and the mobile
Sidebar overlay. Page chrome that merely looks badge-like (`.count-badge`, `.role-badge`, ...)
lives here, **not** in `badges.css`. (Its header comment still lists `claim-approval.html` — a
page that was never built; stale.)

---

### assets/css/nss-datepicker.css

Styles for the `nssDatePicker` component (204 lines) — `.nss-dp-wrap` (input wrapper),
`.nss-dp-input`, `.nss-dp-icon` (calendar button), `.nss-dp-error` (validation message), and the
popup: `.nss-cal-popup`, `.nss-cal-header`/`-nav`/`-title`/`-selectors`/`-select`/`-year`,
`.nss-cal-weekdays`, `.nss-cal-days`/`-day` (+ `-today`/`-selected`), `.nss-cal-footer`/
`-today-btn`/`-clear`. The markup these classes style is injected by
`nssDatePickerExpand()` in `nss-datepicker.js`, not written in the HTML pages. Loaded by
`register.html`, `dashboard.html`, `admin.html`.

---

### assets/css/style.css

Minimal project-specific CSS (14 lines; loaded by all four pages). Tailwind and DaisyUI handle almost
all styling via the pre-built `tailwind.min.css` — this file exists only for overrides that cannot be
expressed as utility classes. (Its header comment still says "Tier 0 ... via CDN" and a trailing
comment still mentions the DaisyUI CDN — both stale wording, the file itself is correct.)

**Current rules:**

| Selector | Purpose |
|----------|---------|
| `[x-cloak]` | Hides elements with the `x-cloak` attribute until Alpine.js initialises, preventing a flash of unstyled/unrendered template syntax. Standard Alpine.js pattern. |

---

### assets/css/tailwind-input.css / tailwind.min.css

`tailwind-input.css` is the build input — just the three `@tailwind` directives
(`base`/`components`/`utilities`), processed by Tailwind CLI per `../tailwind.config.js`
(`content` globs cover `frontend/**/*.html` and `frontend/assets/js/**/*.js`; `daisyui` plugin
loaded). `tailwind.min.css` is the generated, minified, tree-shaken output (~87 KB) that all four
pages `<link>` — it's committed to the repo (not gitignored), so cloning the repo gives a
working build without installing Node.js. Regenerate via `npm run css:build` (one-shot) or
`npm run css:watch` (rebuild on change) from the repository root after editing any
Tailwind/DaisyUI class in the HTML or JS files — the old CDN Play compiler generated classes at
page-load time in the browser; this pre-built file does not, so a missed rebuild means the new
class silently has no styling.

---

### assets/img/nss-logo.png

NSS logo with transparent background, compressed for web (~100 KB, down from a 1.4 MB original).
Copied from `NSS LOGO/logooo.png`
in the repository root. Used as the favicon on `login.html`/`register.html`/`admin.html` and as
the brand image on `login.html`, `register.html`, and the `admin.html` sidebar. The uncompressed
original is kept alongside it as `assets/img/nss-logo-original.png` for future reprocessing.

---

## How FastAPI Serves This Directory

Defined in `api/main.py`. Registered only if the respective file/directory
exists on disk:

| URL Pattern | FastAPI Handler | Serves |
|-------------|----------------|--------|
| `GET /` | Explicit route → `RedirectResponse("/login")` | 302-redirects to the Login page (was `FileResponse(frontend/index.html)` before the six pages below were retired) |
| `GET /login` | Explicit route → `_serve_page(frontend/login.html)` | The Login page |
| `GET /register` | Explicit route → `_serve_page(frontend/register.html)` | The Registration page |
| `GET /dashboard` | Explicit route → `_serve_page(frontend/dashboard.html)` | The Member Dashboard |
| `GET /admin` | Explicit route → `_serve_page(frontend/admin.html)` | The Administration Dashboard |
| `GET /assets/*` | `StaticFiles` mount → `frontend/assets/` | CSS, JS, images (shared by every page) |

**Automatic asset cache-busting.** Every page route above now serves
through `_serve_page()`/`_render_html_with_asset_versions()` (`api/main.py`) instead of a bare
`FileResponse`: each response's `/assets/js/*.js`/`/assets/css/*.css` `src=`/`href=` references
are rewritten to `?v=<10-char sha256 prefix of that file's current contents>`, computed per
request but memoized by file mtime (an unchanged file is never re-hashed). This replaces the old
convention of a hand-maintained `?v=N` in each page's `<script>`/`<link>` tag — easy to forget to
bump, and the pages had already drifted (the same shared file carried different `?v=` numbers on
different pages); every manual `?v=` string was stripped from the four pages below. The served
HTML itself still carries `Cache-Control: no-store` (unchanged), so only `/assets/*`'s
long-lived cache (86400s, `middleware.py`) relies on this content-hash to invalidate correctly.

**Retired:** `GET /foundation`, `/organization`, `/person`, `/family`, `/membership`, and the
old `/` → `frontend/index.html` route are all gone — see the "Retired standalone verification
pages" comment in `api/main.py`.

**Why not mount at `/`?** A root-level `StaticFiles` mount would shadow
FastAPI's built-in `/docs` (Swagger UI) and `/openapi.json`. By mounting
only `/assets/*` and serving each page via an explicit route, all
FastAPI built-in routes remain accessible.

**Graceful degradation:** If `frontend/` does not exist on disk, the
mount and all page routes are skipped entirely. If any individual HTML file is
missing, `/api/v1/*`/`/docs` are unaffected — the API continues to work in API-only mode. Each
of `/login`, `/register`, `/dashboard`, `/admin` is only registered `if` its
respective HTML file exists on disk (see
`api/main.py`). There is no standalone `/forgot-password` page: that flow lives
inline on the Login page (see the "Forgot/reset password" note below).

---

## API Endpoints Consumed

> **⚠ Historical.** The per-page tables below document what the now-deleted `index.html`/
> `foundation.html`/`organization.html`/`person.html`/`family.html`/`membership.html` consumed.
> Two of the underlying facts have also since changed in Tier 5: `foundation.py`/
> `organization.py`/`person.py`/`membership.py` are now gated by `require_permission(...)`
> (were "no authentication" as stated below), and `/api/v1/bootstrap/permissions`/
> `/roles/{pk}/permissions` are no longer guaranteed-empty now that `permission_master`/
> `role_permission` are seeded. See `admin.js`/`dashboard.js` for what the current pages
> actually call.

All endpoints are read-only. No authentication. No CRUD.

**`index.html` (via `app.js`):**

| Method | URL | Response | Tier 0 State |
|--------|-----|----------|-------------|
| GET | `/api/v1/bootstrap/health` | `{ status, database }` | `{ "status": "ok", "database": "connected" }` |
| GET | `/api/v1/bootstrap/roles` | `RoleResponse[]` | 10 frozen roles |
| GET | `/api/v1/bootstrap/permissions` | `PermissionResponse[]` | Empty array (by design) |
| GET | `/api/v1/bootstrap/roles/{role_pk}/permissions` | `PermissionResponse[]` | Empty array (no mappings); 404 if role not found |

Response schemas are defined in `api/schemas/bootstrap.py`.

**`foundation.html` (via `foundation.js`):**

| Method | URL | Response | Tier 1 State |
|--------|-----|----------|-------------|
| GET | `/api/v1/bootstrap/health` | `{ status, database }` | Shared with index.html |
| GET | `/api/v1/foundation/categories` | `CategoryResponse[]` | 11 seeded categories |
| GET | `/api/v1/foundation/master-data?category_code=` | `MasterDataResponse[]` | 58 seeded values |
| GET | `/api/v1/foundation/settings` | `SettingResponse[]` | 4 seeded settings |
| GET | `/api/v1/foundation/sequences` | `SequenceResponse[]` | 9 seeded sequences (`current_value` excluded) |
| GET | `/api/v1/foundation/countries` | `CountryResponse[]` | 5 seeded countries |
| GET | `/api/v1/foundation/states?country_pk=` | `StateResponse[]` | 112 seeded states |
| GET | `/api/v1/foundation/districts?state_pk=` | `DistrictResponse[]` | ~770 seeded districts (India only) |
| GET | `/api/v1/foundation/cities?district_pk=` | `CityVillageResponse[]` | Empty (no seed data yet) |
| GET | `/api/v1/foundation/postal-codes?country_pk=` | `PostalCodeResponse[]` | 2 seeded postal codes |
| GET | `/api/v1/foundation/documents` | `DocumentResponse[]` | Empty (no seed data yet) |

Response schemas are defined in `api/schemas/foundation.py`. `nss.field_change_log` is
deliberately not exposed by any endpoint — deferred to Tier 5 (needs auth). Full contract:
`docs/03_Solution/api/FOUNDATION_API_CONTRACT.md`.

Audit columns (`created_at`, `*_by_sangha_sevi_pk`) are excluded from every response by design.

**`organization.html` (via `organization.js`):**

| Method | URL | Response | Tier 2 State |
|--------|-----|----------|-------------|
| GET | `/api/v1/bootstrap/health` | `{ status, database }` | Shared with index.html |
| GET | `/api/v1/organization/types` | `OrganizationTypeResponse[]` | 8 frozen types |
| GET | `/api/v1/organization/statuses` | `OrganizationStatusResponse[]` | 6 lifecycle statuses |
| GET | `/api/v1/organization/organizations?type_code=&status_code=` | `OrganizationResponse[]` | 3 seeded organizations (KEN, NKT, SMR), all roots |
| GET | `/api/v1/organization/organizations/{organization_pk}` | `OrganizationResponse` | Not called directly by the UI (list already carries full detail); available for future use |
| GET | `/api/v1/organization/organizations/{organization_pk}/children` | `OrganizationResponse[]` | Empty — all 3 seeded organizations are roots with no children |
| GET | `/api/v1/organization/hierarchy` | `OrganizationHierarchyNodeResponse[]` | 3 nodes, all at depth 0 |

Response schemas are defined in `api/schemas/organization.py`. `OrganizationResponse` also
resolves geography FK names (country/state/district/city_village/postal_code) via LEFT JOINs to
Foundation's tables. Full contract: `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md`.

**`person.html` (via `person.js`):**

| Method | URL | Response | Tier 3 State |
|--------|-----|----------|-------------|
| GET | `/api/v1/bootstrap/health` | `{ status, database }` | Shared with index.html |
| GET | `/api/v1/foundation/master-data?category_code=GENDER` | `MasterDataResponse[]` | Filter options for gender dropdown |
| GET | `/api/v1/foundation/master-data?category_code=MARITAL_STATUS` | `MasterDataResponse[]` | Filter options for marital status dropdown |
| GET | `/api/v1/foundation/master-data?category_code=BLOOD_GROUP` | `MasterDataResponse[]` | Filter options for blood group dropdown |
| GET | `/api/v1/person/persons?gender_code=&marital_status_code=&blood_group_code=` | `PersonSummaryResponse[]` | Compact list (no Aadhaar, emergency, photo) |
| GET | `/api/v1/person/persons/{person_pk}` | `PersonResponse` | Full detail with resolved master-data names; aadhaar_last4 only (never encrypted/hash) |
| GET | `/api/v1/person/persons/{person_pk}/addresses` | `PersonAddressResponse[]` | Resolved address type + location chain (city→district→state→country); primary first |
| GET | `/api/v1/person/search?q=` | `PersonSummaryResponse[]` | Trigram similarity on first_name/last_name + ILIKE prefix on person_id/mobile; max 50 results |

Response schemas are defined in `api/schemas/person.py`. Sensitive fields (`aadhaar_encrypted`,
`aadhaar_hash`) are never returned by the API — only `aadhaar_last4` for masked display.

**`family.html` (via `family.js`):**

| Method | URL | Response | Tier 4 State |
|--------|-----|----------|-------------|
| GET | `/api/v1/bootstrap/health` | `{ status, database }` | Shared with index.html |
| GET | `/api/v1/family/families` | `FamilyGroupResponse[]` | 1 seeded family (F1 Mishra Paribara) |
| GET | `/api/v1/family/families/{family_group_pk}` | `FamilyGroupResponse` | Not called directly by the UI (list already carries full detail); available for future use |
| GET | `/api/v1/family/families/{family_group_pk}/members` | `FamilyMemberResponse[]` | 3 current members (Ramesh/Sushma/Aniket Mishra) |
| GET | `/api/v1/family/families/{family_group_pk}/head-history` | `FamilyHeadHistoryResponse[]` | 1 head-history record (Ramesh Mishra, current) |
| GET | `/api/v1/family/families?sakha_code=` | `FamilyGroupResponse[]` | Used by the org-admin drill-down view (`family.js`'s `fetchFamilies()`) once a Sakha is selected |
| GET | `/api/v1/family/families/{family_group_pk}/graph?viewer_person_pk=` | graph-member array | Dynamic relationship-label computation via BFS traversal over `nss.family_link`, implemented in `api/services/family_graph.py`; drives the tree visualization. No test coverage yet |
| GET | `/api/v1/family/families/{family_group_pk}/sakha-alignment` | `FamilySakhaAlignmentResponse` | FAM-036 majority-rule "effective Sakha" computation; powers the amber mismatch badges |
| GET | `/api/v1/family/person/{person_pk}/membership-summary` | membership summary | Bridges family context to membership context for the right-panel detail card. No test coverage yet |
| GET | `/api/v1/person/persons/{person_pk}` | `PersonResponse` | Full person detail, fetched alongside `membership-summary` when a tree node/member row is selected |
| GET | `/api/v1/organization/organizations?type_code=KENDRA` | `OrganizationResponse[]` | Admin-view root lookup (`fetchOrgRoot()`) |
| GET | `/api/v1/organization/organizations/{organization_pk}/children` | `OrganizationResponse[]` | Admin-view drill-down cards |
| GET | `/api/v1/organization/organizations/{organization_pk}/children-stats` | aggregate counts | Background, non-blocking fetch; populates the family/member/person count badges on org-children cards |

Response schemas are defined in `api/schemas/family.py` (and `api/schemas/organization.py` for
the org-navigation calls above). `FamilyGroupResponse` resolves family status (Foundation's
unified `STATUS` category) and Sakha name/code via JOINs; member and head-history responses
resolve person name fields and (for members) relationship type via JOINs. Full contract:
`docs/03_Solution/api/API_CONTRACT.md` §7.

**`membership.html` (via `membership.js`):**

| Method | URL | Response | Tier 4 State |
|--------|-----|----------|-------------|
| GET | `/api/v1/bootstrap/health` | `{ status, database }` | Shared with index.html |
| GET | `/api/v1/membership/members?type_code=&status_code=` | `MemberResponse[]` | 5 seeded members (SS1–SS5) |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}` | `MemberResponse` | Not called directly by the UI (list already carries full detail); available for future use |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}/affiliations` | `SakhaAffiliationResponse[]` | 1 row per member, 2 for the transferred member (SS3) |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}/parichaya-patra` | `ParichayaPatraResponse[]` | Regular/Associate members only — Probationary members have none |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}/anumati-patra` | `AnumatiPatraResponse[]` | Probationary members (current) + Regular members who progressed from Probationary (historical, EXPIRED); Associate members have none |
| GET | `/api/v1/membership/members/{sangha_sevi_pk}/journey` | `JourneyEventResponse[]` | Chronological lifecycle events per member |
| GET | `/api/v1/membership/search?q=` | `MemberResponse[]` | Trigram + prefix search across all 3 identity tiers, name, mobile, and email; max 50 results |

Response schemas are defined in `api/schemas/membership.py`. `MemberResponse` resolves person
name/contact, membership type, status, organization (Sakha), and the current active
`local_sakha_erp_id` via JOINs. Full contract: `docs/03_Solution/api/API_CONTRACT.md` §8.

## Tier 5 pages (v0.11.0)

Four new pages. The shared helpers and per-page scripts now have their own File Reference
subsections above (`auth.js` through `nss-datepicker.css`); this section remains a summary
pointer for the pages themselves, not an exhaustive per-function walkthrough. All four consume the new `/api/v1/auth/*`/`/api/v1/admin/*`/
`/api/v1/register`/`/api/v1/admin/claims/*` endpoints (see `api/README.md` → "Endpoints (Tier 5)"
and `docs/PROJECT_DOCUMENTATION.md` → Key Workflow #9).

| Page | Route | JS | Purpose |
|---|---|---|---|
| `login.html` | `/login` (root `/` now redirects here) | `login.js`, `auth.js`, `nss-dialog.js`, `nss-config.js` | Login form (`POST /api/v1/auth/login`, stores the JWT pair, redirects to `/dashboard`), plus change-password/forgot-password/reset-password flows on the same page |
| `register.html` | `/register` | `register.js`, `auth.js`, `nss-location.js`, `nss-datepicker.js`, `nss-config.js` | Self-registration form — person details + optional membership claim (Sakha dropdown sourced from the new `05_sakha_branches.sql` seed) + Darshak-attendance toggle; duplicate-check via `POST /api/v1/register/check-duplicate`, submits `POST /api/v1/register` |
| `dashboard.html` | `/dashboard` | `dashboard.js`, `auth.js`, `nss-dialog.js`, `nss-layout.js`, `nss-datepicker.js`, `org-dashboard.js`, `nss-config.js` | Member dashboard (Personal/Membership/Family/Documents/Attendance/Governance tabs, plus an Org Dashboard tab and admin entries added from the caller's role scopes) — see `docs/03_Solution/architecture/MEMBER_DASHBOARD.md` |
| `admin.html` | `/admin` | `admin.js`, `auth.js`, `nss-layout.js`, `nss-location.js`, `nss-dialog.js`, `nss-datepicker.js`, `org-dashboard.js`, `nss-config.js` | The actual administration dashboard, now the sole home for the retired Tier 0-4 verification functionality too — Reference Data, Organization Hierarchy, Person Directory, Member Directory, Roles & System Settings, an **Assign Sakhas** tab (re-parent a Sakha Sangha to its real Anchalika/Zilla Sangha, see below), and a **Registration Approvals** tab (claims review, see below); `GET /api/v1/auth/me` for the current admin's own permissions/scopes |

**`claim-approval.html`/`claim-approval.js` were never built as standalone files, and this is
not a gap.** The review queue for `api/routers/claim_approval.py`'s `/api/v1/admin/claims/*`
endpoints (list/detail/edit/approve/reject `registration_claim` rows) shipped as a
**"Registration Approvals" tab inside `admin.html`/`admin.js`** instead (`admin.js` around the
`// ── Registration Claims (merged from claim-approval) ──` comment): status-filtered list +
pagination, a detail view, inline edit, a pending-count sidebar badge, a `canApproveClaims`
permission gate, and integration into the Person Directory tab (a pending claim blocks
Sangha-Sevi creation for that person and shows a "View Claim" jump-link).

**"Assign Sakhas" tab (`admin.js` `activeTab === 'assignSakha'`,
"Assign Sakhas to Anchalika/Zilla Sangha"):** lets an admin search/filter Sakha Sanghas
(`assignSakhaSearch`, `assignSakhaOnlyUnassigned` to show only Sakhas still on the wrong
parent) and re-parent one at a time (`assignSakhaToParent()`) via the new `PATCH
/api/v1/admin/organizations/{pk}` `parent_organization_pk` field.

**"Create Person" tab restructured into a real 3-step flow:** Step 1
Person (find-or-create, unchanged) → **Step 2 Sangha Sevi**, now its own step
(`createSanghaSeviForNewPerson()` against `POST /api/v1/admin/sangha-sevi`, with a
`skipCreateSanghaSevi()` "Skip for now" option) → Step 3 Account Credentials (no longer bundles
Sangha Sevi creation into the account-creation submit — previously Step 2). A
`sakhaShortCode(orgPk)`/`sakhaMissingShortCode(orgPk)` helper pair now backs both this flow's
Step 2 and the standalone Create Sangha Sevi tab, replacing a duplicated inline lookup
expression across the two form templates. `canEditOrg(org)` is now subtree-aware (walks the
org's parent chain via a new `isOrgOrDescendantOf()` helper) instead of matching only the
admin's exact own org row — a Zilla/Anchalika admin now sees Edit/Short-Code buttons on
descendant Sakhas too. A `tabLoaders` map in `init()` fixes a hash-restoration bug where
refreshing the page on a lazy-loaded tab (Organization Hierarchy, Assign Sakhas, Person
Directory, etc.) used to render permanently empty, since only the `claims` tab previously had
its loader wired to fire on hash-restore; `activeTab` is also now resolved synchronously from
the URL hash before Alpine's first render.

**Automatic asset cache-busting — see "How FastAPI Serves This
Directory" below** — replaced the old manual `?v=N` convention; all of it was stripped from
`login.html`/`register.html`/`dashboard.html`/`admin.html`.

**Shared helpers** (used across the four pages above; each now has its own File Reference
subsection earlier in this file): `auth.js` (`NSSAuth` — JWT storage/refresh, `apiFetch()`,
`requireAuth()`/`redirectIfLoggedIn()`, `logout()`), `nss-layout.js` (`NSSLayout` mixin —
`admin.html`/`dashboard.html` only), `nss-datepicker.js`, `nss-dialog.js`, `nss-location.js`
(`NSSLocation.create()`'s `basePath` option, default `/api/v1/foundation`; `register.js` passes
`/api/v1/register` so the same helper can hit the public registration reference-data endpoints),
and `org-dashboard.js` (the Org Dashboard tab component shared by `admin.html`/`dashboard.html`).
Shared constants, sort/format/error-message helpers also live in `nss-config.js`'s `NSS` object.

**Forgot/reset password (inline, by design):** there is no standalone
`frontend/forgot-password.html` and no `/forgot-password` page route. The
forgot-password + reset-password flow is implemented inline on the Login page
(`login.html` / `loginApp()`), toggled via `showForgotPassword` /
`showResetPassword` — the "Forgot Password?" link switches Alpine state instead
of navigating. The backing API (`POST /api/v1/auth/forgot-password` /
`reset-password`) is implemented and tested (`tests/api/test_forgot_password.py`),
and the inline UI is covered by `tests/ui/test_ui_forgot_password.py`.

**Dead asset:** `assets/img/ssm-mandir.webp` exists under `assets/img/` but is
not referenced by any `<img>`/CSS in `login.html`, `register.html`, `dashboard.html`, or
`admin.html` — currently unused.

## Future Growth

This shell is designed to evolve:

```
Tier 0   Bootstrap Verification (retired — deleted, folded into admin.html)
Tier 1   Foundation Verification (retired — deleted, folded into admin.html)
Tier 2   Organization Verification (retired — deleted, folded into admin.html)
Tier 3   Person Verification (retired — deleted, folded into admin.html)
Tier 4   Family + Membership Verification (retired — deleted, folded into admin.html/dashboard.html)
  ...
Tier 5   Authentication + Administration + login/session UI — released as v0.11.0 (see
         "Tier 5 pages" above)
  ...
         Full ERP interface
```


The page structure, CSS framework, and Alpine.js pattern established
by the original six Tiers 0-4 pages carried forward into the four Tier 5 pages, even though
those six pages themselves were deleted (see the header note at the top of this file).
Authentication + Administration UI is implemented and released in Tier 5 / v0.11.0 (see "Tier 5 pages" above).
