# UI Code Explanations — `frontend/`

| Field       | Value                                                                  |
|-------------|-------------------------------------------------------------------------|
| Document    | UI_CODE_EXPLANATIONS                                                   |
| Version     | 1.8                                                                     |
| Scope       | The six retired Tier 0-4 verification pages and their JS/CSS under `frontend/` (historical); the four current pages (`login.html`, `register.html`, `dashboard.html`, `admin.html`) are not yet covered |
| Status      | Superseded in part — the six Tier 0-4 verification pages this document walks through have been deleted from `frontend/`; retained as a historical walkthrough pending a rewrite against the current four pages |

---

> **⚠ Files no longer on disk.** Every HTML/JS file walked through in §2 below —
> `index.html`/`app.js`, `foundation.html`/`foundation.js`,
> `organization.html`/`organization.js`, `person.html`/`person.js`,
> `family.html`/`family.js`, `membership.html`/`membership.js` — has been **deleted** from
> `frontend/`. `frontend/` now contains exactly four pages: `login.html`, `register.html`,
> `dashboard.html` and `admin.html` (plus `assets/js/login.js`, `register.js`, `dashboard.js`,
> `admin.js`, `auth.js`, `nss-config.js`, `nss-layout.js`, `nss-datepicker.js`,
> `nss-dialog.js`, `nss-location.js`, `nss-combobox.js`, `org-dashboard.js`). Each retired page's functionality moved into a tab of
> one of the two authenticated pages:
>
> | Retired page | Current home |
> |---|---|
> | `index.html` (Bootstrap RBAC) | `admin.html` → System Settings tab |
> | `foundation.html` | `admin.html` → Reference Data + Geography tabs |
> | `organization.html` | `admin.html` → Organizations + Organization Hierarchy tabs |
> | `person.html` | `admin.html` → Person Directory tab |
> | `family.html` | `dashboard.html` → Family tab |
> | `membership.html` | `dashboard.html` → Membership tab; `admin.html` → Member Directory tab |
>
> The `assets/css/style.css`, `assets/css/badges.css` and `assets/js/nss-config.js` sections
> below remain current — those files survived the retirement and are loaded by all four current
> pages. Everything else in §2 is a historical record of where a given piece of
> `admin.html`/`dashboard.html` logic originally came from. See `frontend/README.md` for the
> current per-page reference.

---

## 1. Purpose of this document

This document was the current, authoritative line-by-line (HTML: section-by-section /
directive-by-directive; JS: state-property-by-property / method-by-method; CSS:
rule-by-rule) reference for every source file in the frontend/UI layer, as of the six Tier 0-4
verification pages. It has not yet been rewritten against the four pages that replaced them.

It replaces the UI-relevant portions of three retired documents:

- `TIER0_VERTICAL_SLICE.md` (§5 — `frontend/index.html`, `assets/js/app.js`, `assets/css/style.css`)
- `TIER1_FOUNDATION.md` (§6 — `frontend/foundation.html`, `assets/js/foundation.js`)
- `SECURITY_HARDENING.md` (§7 — CDN pinning / Subresource Integrity changes to both HTML files)

Those three documents also covered the database, API, and test layers, and the
cross-tier security-middleware stack — none of that is repeated here; consult
`FOUNDATION_API_CONTRACT.md` and the (now-deleted) tier docs' git history for that
material. This document is organized **file-by-file**, in the order the files are
listed in §2 (nine: `index.html`/`app.js`, `foundation.html`/`foundation.js`,
`organization.html`/`organization.js`, `person.html`/`person.js`, plus the shared
`style.css`), rather than tier-by-tier, because a UI file (e.g. `style.css`) is shared
across tiers and a per-tier split would fragment its explanation.

`frontend/README.md` remains the primary human-facing reference for this folder — it
carries the state/method summary tables, the API-endpoints-consumed tables, and the
"how FastAPI serves this directory" reference. This document does not duplicate those
tables verbatim; it adds the missing line-by-line depth that `frontend/README.md`
intentionally leaves out (README.md is a reference card, this is a walkthrough). Where a
README table already gives the complete picture (e.g. the state-property table for
`app.js`), this document restates it briefly for context and then walks the actual code.

All code shown below was read directly from the working tree at the time of writing; version
numbers, SRI hashes, and attribute values are transcribed exactly as they were then.

---

## 2. Files

### 2.1 `frontend/index.html`

**Requirement.** This is the Tier 0 "Bootstrap Verification UI" — the human-facing proof
that the full stack (PostgreSQL `nss.role_master`/`permission_master`/`role_permission` →
FastAPI `/api/v1/bootstrap/*` → browser) actually works end to end, without requiring
Swagger UI or `curl`. It is explicitly **not** an administration dashboard: there is no
login (Tier 0 has no authentication by design — deferred to Tier 5), no forms, and no
CRUD. It is a single static HTML file served by FastAPI's explicit `GET /` route
(`api/main.py`), which mounts `bootstrapApp()` (defined in `assets/js/app.js`) as an
Alpine.js component.

**Section-by-section walkthrough** (file has 278 lines):

**`<head>` (lines 1–17):**
```html
<html lang="en" data-theme="light">
```
- `data-theme="light"` selects DaisyUI's built-in "light" theme for every DaisyUI
  component on the page (cards, badges, buttons, tables).

```html
<link rel="icon" type="image/png" href="/assets/img/nss-logo.png">
<title>Nilachala Saraswata Sangha — Bootstrap Verification</title>
```
- Favicon and tab title both reuse the NSS logo asset served from the static mount.

CDN/asset dependency block (identical on `foundation.html`, exact strings from the current
file):
```html
<!-- Tailwind CSS 3.x + DaisyUI 4 (pre-built, tree-shaken — see tailwind.config.js) -->
<link rel="stylesheet" href="/assets/css/tailwind.min.css">
<!-- Alpine.js 3.14.8 -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.8/dist/cdn.min.js" integrity="sha384-X9kJyAubVxnP0hcA+AMMs21U445qsnqhnUF8EBlEpP3a42Kh/JwWjlv2ZcvGfphb" crossorigin="anonymous"></script>

<link rel="stylesheet" href="/assets/css/style.css">
```
- **Tailwind CSS + DaisyUI** — as of the current working tree, both are a single
  same-origin, pre-built stylesheet: `/assets/css/tailwind.min.css` (~72 KB, minified,
  tree-shaken), served by the existing `/assets/*` `StaticFiles` mount in `api/main.py`.
  It is generated at build time by the Tailwind CLI (root `package.json`
  devDependencies `tailwindcss` + `daisyui`; root `tailwind.config.js` sets `content`
  globs to `frontend/**/*.html` + `frontend/assets/js/**/*.js` and loads the `daisyui`
  plugin; input file `frontend/assets/css/tailwind-input.css` holds only the three
  `@tailwind base/components/utilities` directives). The compiled file is committed to
  git (not gitignored), so cloning the repo yields a working build without Node.js
  installed; `render_build.sh` runs `npm install` plus the Tailwind CLI build as its
  first step, before Python deps. This replaces the earlier Tailwind Play CDN
  `<script>` tag and the DaisyUI CDN `<link>` (pinned to `4.12.14` with a `sha384-`
  Subresource Integrity hash) that older revisions of this document described — no SRI
  `integrity`/`crossorigin` attributes are needed on a same-origin file, since an
  attacker able to tamper with it could tamper with any file this server serves.
- **Alpine.js** — unchanged by the Tailwind/DaisyUI switch. Still pinned to `3.14.8` on
  jsdelivr, with its own SRI hash
  (`sha384-X9kJyAubVxnP0hcA+AMMs21U445qsnqhnUF8EBlEpP3a42Kh/JwWjlv2ZcvGfphb`) and
  `crossorigin="anonymous"`. The `defer` attribute delays script execution until the
  HTML document has been fully parsed, so Alpine's `x-data`/`x-init` scan finds a
  complete DOM.
- The local stylesheet `/assets/css/style.css` (§2.5) is loaded last, after
  `tailwind.min.css`, so any override rules in it win on specificity ties.
- **(v1.5, Tier 4 shared-config extraction.)** The page-local `<style>` block described in
  earlier revisions of this document — a `.badge`/`.badge-xs`/`.badge-sm` padding override plus
  6 `.badge-status-*` classes, duplicated near-identically across `index.html`,
  `foundation.html`, and `organization.html` — has been **removed**. In its place, two shared
  files are now linked/scripted immediately after `style.css`:
```html
<link rel="stylesheet" href="/assets/css/badges.css">
<script src="/assets/js/nss-config.js"></script>
```
  `/assets/css/badges.css` (§2.14) is now the single source of truth for every
  `.badge-status-*`/`.badge-type-*`/`.badge-aff-*`/`.badge-gender-*` class across all six pages —
  it centralizes what used to be several slightly-diverging per-page copies (6 classes here, 13
  on `organization.html`, 3 on `person.html`, etc.) into one 18-status superset, so every page
  gets every status color regardless of whether that particular page currently renders that
  status. `/assets/js/nss-config.js` (§2.15) defines the global `NSS` object — badge-class
  lookup helpers (`NSS.statusBadgeClass()`, `NSS.typeBadgeClass()`, etc.) and the `PROBATIONARY`
  → "Darshaka" display-name override — that page-specific JS (e.g. `membership.js`, §2.11) now
  delegates to instead of hardcoding its own `if`/`else` chains. This page renders no
  lifecycle-status badge itself, so it calls no `NSS.*` helper, but still loads both files for
  consistency with the other five pages, and because `badges.css`'s `.badge`/`.badge-xs` padding
  overrides still apply to its health-status dot and roles-count badge.

---

### 2.6 `frontend/organization.html`

> **v2.0 (2026-09-12):** Type/status field references renamed `organization_status_*` →
> `status_*` throughout (fetch URLs unchanged); type count 8→10 and status count 6→13 following
> the org-to-master-data migration; badge CSS grew from 6 `.badge-status-*` classes to 13; the
> children-hidden-for-types list grew to include `PARIBARIK_ASANA`/`PARIBARIK_SANGHA`.

**Requirement.** This is the Tier 2 "Organization Verification UI" — the visual proof that
the 6 read-only `/api/v1/organization/*` endpoints correctly expose `organization` plus
Foundation's shared `master_data`/`master_category` tables (for type/status, categories
`ORGANIZATION_TYPE` and `STATUS`). It is
structurally parallel to `foundation.html` (same head boilerplate, same System Status card
reusing the Tier 0 health endpoint, same nav bar with three tier links) and organizes its
surface area into three tabs: Reference Data, Organizations, and Hierarchy. Mobile-
responsive from initial implementation (unlike Tiers 0/1, which were retrofitted), using
the same Tailwind breakpoint patterns (`px-3 sm:px-6`, `text-lg sm:text-2xl`, etc.).
Served by FastAPI's `GET /organization` route, conditional on the file existing on disk.

**Section-by-section walkthrough:**

**`<head>`:**
- Same asset dependency block as `index.html` and `foundation.html`: the pre-built,
  same-origin `/assets/css/tailwind.min.css` (Tailwind 3.x + DaisyUI 4, tree-shaken —
  see §2.1 for the build-pipeline detail; no SRI, since same-origin files need none),
  Alpine.js 3.14.8 with SRI (`sha384-X9kJyAubVxnP0hcA+...`, unchanged), local
  `style.css`. Only the `<title>` differs ("— Organization Verification").
- A page-local `<style>` block (also duplicated in `index.html`/`foundation.html` — see below)
  overrides DaisyUI's default `.badge`/`.badge-xs`/`.badge-sm` padding (`!important`, since
  `tailwind.min.css` loads after any plain CSS in `style.css` and would otherwise win)
  and defines 13 `.badge-status-*` classes (`active`/`proposed`/`approved`/`suspended`/
  `inactive`/`lapsed`/`transferred`/`resigned`/`expelled`/`deceased`/`dissolved`/`archived`/
  `expired`), each a solid background color with white text — replacing DaisyUI's
  generic semantic badges (`badge-success`/`badge-warning`/`badge-ghost`) so all 13 lifecycle
  statuses (from Foundation's unified `STATUS` category — see §2.7) get their own distinct,
  readable color instead of sharing a handful of generic badges. The 7 classes added in the
  v2.0 migration (`lapsed`/`transferred`/`resigned`/`expelled`/`deceased`/`dissolved`/
  `expired`) cover status values that `STATUS` absorbed from the wider, ERP-unified lifecycle
  vocabulary — values the old 6-status, Organization-only set never needed.

> **Cross-reference (Tier 4 shared-config extraction):** the page-local `<style>` block
> described above has since been removed from `organization.html`; the file now loads
> `/assets/css/badges.css` and `/assets/js/nss-config.js` in `<head>` instead (see §2.14–§2.15
> for the shared files these classes now live in).

**Root component:**
```html
<div x-data="organizationApp()" x-init="init()" class="mx-auto px-3 py-4 sm:px-6 sm:py-6 lg:px-10 2xl:px-16">
```
- Mobile-first padding: `px-3 py-4` below 640px, `sm:px-6 sm:py-6` from 640px, `lg:px-10`
  from 1024px, `2xl:px-16` at 1536px+. Calls `organizationApp()` (§2.7).

**Header:** Same layout as `index.html`/`foundation.html` but with mobile-responsive sizing
(`h-10 w-10 sm:h-14 sm:w-14` for the logo, `text-lg sm:text-2xl` for the title). The nav
bar has three links: Bootstrap, Foundation, Organization — with Organization styled
`btn-active`.

**System Status card:** Identical `x-if` triad to the other pages, bound to
`organizationApp().health`, calling the Tier 0 `/api/v1/bootstrap/health` endpoint.

**Tab bar:**
```html
<div class="tabs tabs-boxed bg-base-100 shadow-sm mb-4 inline-flex overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
    <button class="tab" :class="{ 'tab-active': activeTab === 'reference' }" @click="switchTab('reference')">Reference Data</button>
    <button class="tab" :class="{ 'tab-active': activeTab === 'organizations' }" @click="switchTab('organizations')">Organizations</button>
    <button class="tab" :class="{ 'tab-active': activeTab === 'hierarchy' }" @click="switchTab('hierarchy')">Hierarchy</button>
</div>
```
- `overflow-x-auto` with `-mx-3 px-3 sm:mx-0 sm:px-0` makes the tab bar horizontally
  scrollable on mobile (tab labels don't wrap), while restoring normal margins on larger
  screens. Same DaisyUI `tabs tabs-boxed` pattern as `foundation.html`.

**Tab 1 — Reference Data:** Two-column grid (`grid-cols-1 xl:grid-cols-2`) with
Organization Types (10 frozen types, sourced from Foundation `master_data` category
`ORGANIZATION_TYPE`) on the left and Lifecycle Statuses (7 statuses — as of Tier 4, `/statuses`
filters the 16-value unified `STATUS` category down to only those with `ORGANIZATION` in
`applicable_modules`, category
`STATUS`) on the right. Each card follows the standard loading/error/data `x-if` triad.
Type and status badges use `whitespace-nowrap` on both the `<td>` and `<span>` to prevent
text spill for long names like "Anchalika Sangha". Every status `<tr>`/badge binding reads
`s.status_pk`/`s.status_code`/`s.status_name` (renamed from `organization_status_*` in the
pre-migration schema) — the `status_pk + '-row'` key expression on the `<template x-for>` is
a leftover disambiguation pattern from when multiple tables shared row keys, kept for
uniqueness safety.

**Tab 2 — Organizations:** Filter controls at the top (type and status dropdowns, both
`x-model`-bound to `selectedTypeFilter`/`selectedStatusFilter`, triggering
`filterOrganizations()` on change — see §2.7 for the full current body, including the
auto-select-on-single-result behavior). The status `<select>` is `:disabled` (and dimmed via
`:class="{ 'opacity-40 cursor-not-allowed': ... }"`) whenever the type filter is `KENDRA`,
`NILACHALA_KUTIRA`, or `SMRUTI_MANDIRA` — each is a unique singleton type with no meaningful
status dimension. Below, a responsive table of organizations with
clickable rows (`@click="selectOrganization(org)"`); each row's status badge uses the
`badge-status-*` classes (one `:class` binding per status code, now 13 — see the `<head>`
notes above) rather than DaisyUI's generic semantic badges, reading `org.status_code`/
`org.status_name` (renamed from `organization_status_code`/`organization_status_name`).
When an organization is selected, a detail panel appears below the table showing:
- Full organization metadata (name, code, ID, type, status) — the Status field reads
  `selectedOrg.status_name` (renamed from `organization_status_name`).
- Address information (address lines, city/village, district, state, country, postal code).
- Coordinates (latitude, longitude) if present.
- A Children section — wrapped in `<template x-if="!['NILACHALA_KUTIRA', 'SMRUTI_MANDIRA',
  'PATHA_CHAKRA', 'SAKHA_ASANA', 'PARIBARIK_ASANA', 'PARIBARIK_SANGHA'].includes(selectedOrg.organization_type_code)">`
  — entirely hidden for org types that structurally cannot have children (the two unique
  institutional types, plus `PATHA_CHAKRA`, `SAKHA_ASANA`, and — new in the v2.0 migration —
  the two family-level types `PARIBARIK_ASANA` and `PARIBARIK_SANGHA`, all leaf types in the
  hierarchy). When shown, the children list (fetched via `/organizations/{pk}/children`) has
  its own loading/empty state handling and the same `badge-status-*` classes as the parent
  table, reading `child.status_code`/`child.status_name` (renamed from
  `organization_status_code`/`organization_status_name`).

**Tab 3 — Hierarchy:** Flat tree rendering of the recursive CTE result. Each node is
rendered as a row with indentation controlled by:
```html
<div :style="depthIndent(node.depth)" class="flex items-center gap-2">
```
- `depthIndent(depth)` returns `padding-left: ${depth * 1.5}rem` — depth 0 (roots) has no
  indent, depth 1 gets 1.5rem, depth 2 gets 3rem, etc. Each node shows its name,
  type badge, and status badge (also using the now-13 `badge-status-*` classes, reading
  `node.status_code`/`node.status_name` — renamed from `organization_status_code`/
  `organization_status_name` — replacing an earlier 3-way `active`/`proposed`/"everything
  else" `badge-ghost` mapping that collapsed the rest into one indistinguishable grey badge),
  and code.

**Footer and script include:** Same copyright footer as the other pages. Loads
`<script src="/assets/js/organization.js"></script>` at the bottom.

---

### 2.7 `frontend/assets/js/organization.js`

> **v2.0 (2026-09-12):** State/fetch logic unchanged (fetch URLs are still
> `/api/v1/organization/types` and `/statuses` — Organization does **not** call Foundation's
> `master-data` endpoint directly). Comment banners updated to say "10 frozen types" and "13
> unified lifecycle statuses." All downstream field consumption (in `organization.html`) reads
> `status_*` instead of `organization_status_*` — see §2.6.

**Requirement.** The client-side state/behaviour layer for `organization.html`, mirroring
the role `foundation.js` plays for `foundation.html` but scoped to the Organization
module's 6 API endpoints across 3 tabs. Defines one global factory function,
`organizationApp()`.

**Full file, 214 lines. Walkthrough:**

```javascript
const ORG_API = "/api/v1/organization";
```
- Same relative-path pattern as `app.js`'s `API_BASE` and `foundation.js`'s `FND_API`. Points
  at the Organization router's own `/types`/`/statuses` endpoints — those endpoints internally
  query Foundation's `master_data` (see `API_CODE_EXPLANATIONS.md` §2.9), but this file never
  calls `/api/v1/foundation/master-data` itself; the indirection is entirely server-side.

**State properties** (grouped by the file's own comment banners):

```javascript
activeTab: "reference",
health: { loading: true, connected: false },
```
- Default tab is `"reference"` (vs Foundation's `"master"`).
- Same health object shape, reusing the Tier 0 health endpoint.

**Reference Data group:**
```javascript
orgTypes: [],
orgTypesLoading: true,
orgTypesError: false,

orgStatuses: [],
orgStatusesLoading: true,
orgStatusesError: false,
```
- Both start `loading: true` because they're fetched eagerly by `init()`. The file's module
  docstring documents these as "1. Organization Types (10 frozen types)" and "2. Statuses (13
  unified lifecycle statuses)" — both counts bumped by the org-to-master-data migration (from
  8 and 6 respectively).

**Organizations group:**
```javascript
organizations: [],
orgsLoading: true,
orgsError: false,
selectedTypeFilter: "",
selectedStatusFilter: "",

selectedOrg: null,
orgChildren: [],
childrenLoading: false,
childrenError: false,
```
- `selectedTypeFilter` and `selectedStatusFilter` are bound via `x-model` to the filter
  dropdowns. `selectedOrg` drives the detail panel; `orgChildren` holds the children list
  for the selected organization.

**Hierarchy group:**
```javascript
hierarchy: [],
hierarchyLoading: true,
hierarchyError: false,
```

**Init:**
```javascript
async init() {
    await this.fetchHealth();
    await this.loadReferenceTab();
},
```
- Sequential: health check first, then the default tab's data. Same pattern as
  `foundation.js`'s `init()`.

**Tab switching and lazy loading:**
```javascript
async switchTab(tab) {
    this.activeTab = tab;
    if (tab === "reference") await this.loadReferenceTab();
    else if (tab === "organizations") await this.loadOrganizationsTab();
    else if (tab === "hierarchy") await this.loadHierarchyTab();
},

async loadReferenceTab() {
    if (this.orgTypes.length === 0) await this.fetchOrgTypes();
    if (this.orgStatuses.length === 0) await this.fetchOrgStatuses();
},

async loadOrganizationsTab() {
    if (this.organizations.length === 0) await this.fetchOrganizations();
},

async loadHierarchyTab() {
    if (this.hierarchy.length === 0) await this.fetchHierarchy();
},
```
- Same lazy-load-once pattern as `foundation.js`: `array.length === 0` guards prevent
  re-fetching on tab revisits. This works because all three data sets (types, statuses,
  organizations, hierarchy) are seeded and never legitimately empty.

**Reference Data fetchers:**
```javascript
async fetchOrgTypes() { ... }
async fetchOrgStatuses() { ... }
```
- Standard four-step pattern against `GET ${ORG_API}/types` and `GET ${ORG_API}/statuses`.

**Organization fetchers:**
```javascript
async fetchOrganizations() {
    this.orgsLoading = true;
    this.orgsError = false;
    try {
        let url = `${ORG_API}/organizations`;
        const params = [];
        if (this.selectedTypeFilter)
            params.push(`type_code=${encodeURIComponent(this.selectedTypeFilter)}`);
        if (this.selectedStatusFilter)
            params.push(`status_code=${encodeURIComponent(this.selectedStatusFilter)}`);
        if (params.length) url += `?${params.join("&")}`;

        const res = await fetch(url);
        if (!res.ok) throw new Error(res.statusText);
        this.organizations = await res.json();
    } catch {
        this.orgsError = true;
    } finally {
        this.orgsLoading = false;
    }
},
```
- Builds the URL with optional `type_code` and `status_code` query parameters, both
  `encodeURIComponent`-encoded. Unlike Foundation's `filterByCategory()` which converts
  empty string to `null`, here empty strings are simply not appended to the params array.

```javascript
async filterOrganizations() {
    // Clear detail panel — previous selection may not exist in new filter results
    this.selectedOrg = null;
    this.orgChildren = [];

    // Status filter is not applicable for unique institutional types
    const noStatusTypes = ['KENDRA', 'NILACHALA_KUTIRA', 'SMRUTI_MANDIRA'];
    if (noStatusTypes.includes(this.selectedTypeFilter)) {
        this.selectedStatusFilter = '';
    }

    this.organizations = [];
    await this.fetchOrganizations();

    // Auto-select if filter yields exactly one result
    if (this.organizations.length === 1) {
        await this.selectOrganization(this.organizations[0]);
    }
},
```
- Bound to both filter dropdowns' `@change`. Clears `selectedOrg`/`orgChildren` first, since
  the previously-selected organization may not be in the new filtered result set. `KENDRA`,
  `NILACHALA_KUTIRA`, and `SMRUTI_MANDIRA` are each a unique, singleton institutional type with
  no meaningful status filter (there's only ever one row) — selecting one of them as the type
  filter forces `selectedStatusFilter` back to `""` (the corresponding `<select>` is also
  `:disabled` and dimmed in `organization.html`, see §2.6). Blanks the array (so the loading
  spinner shows), re-fetches, then auto-selects the single result if the filter narrowed the
  list to exactly one organization — sparing the user an extra click for the common
  "look up one org by type" case.

```javascript
async selectOrganization(org) {
    if (this.selectedOrg?.organization_pk === org.organization_pk) {
        this.selectedOrg = null;
        this.orgChildren = [];
        return;
    }
    this.selectedOrg = org;
    this.childrenLoading = true;
    this.childrenError = false;
    this.orgChildren = [];

    try {
        const res = await fetch(
            `${ORG_API}/organizations/${org.organization_pk}/children`
        );
        if (!res.ok) throw new Error(res.statusText);
        this.orgChildren = await res.json();
    } catch {
        this.childrenError = true;
    } finally {
        this.childrenLoading = false;
    }
},
```
- Same toggle-off guard pattern as `app.js`'s `selectRole()` and `foundation.js`'s
  geographic drill-down. Clicking the same org again deselects and clears children.
  Selecting a new org immediately blanks `orgChildren` (preventing stale data flash) and
  fetches `GET /organizations/{pk}/children`.

**Hierarchy fetcher:**
```javascript
async fetchHierarchy() { ... }
```
- Standard four-step pattern against `GET ${ORG_API}/hierarchy`.

**Helper:**
```javascript
depthIndent(depth) {
    return `padding-left: ${depth * 1.5}rem`;
},
```
- Returns an inline CSS `padding-left` value proportional to `depth`. Called from the
  hierarchy tab's `x-for` loop via `:style="depthIndent(node.depth)"`. At depth 0 (roots),
  returns `padding-left: 0rem`; at depth 1, `1.5rem`; at depth 2, `3rem`; etc.

**Root component (line 20):**
```html
<div x-data="bootstrapApp()" x-init="init()" class="mx-auto px-6 py-6 lg:px-10 2xl:px-16">
```
- `x-data="bootstrapApp()"` — calls the factory function defined in `app.js` to create
  this component's reactive data store; every directive inside this `<div>` can read
  and write that store's properties.
- `x-init="init()"` — runs once, immediately after the store is created, calling the
  `init()` method (§2.2) which kicks off the three parallel API fetches.
- The padding classes (`px-6` mobile → `lg:px-10` tablet → `2xl:px-16` large desktop)
  give the page progressive side margins with no `max-width` cap, so the layout fills
  the viewport rather than centering in a fixed column.

**Header (lines 23–35):**
```html
<header class="mb-6 flex items-center justify-between flex-wrap gap-4">
    <div class="flex items-center gap-4">
        <img src="/assets/img/nss-logo.png" alt="NSS Logo" class="h-14 w-14 object-contain">
        <div>
            <h1 ...>Nilachala Saraswata Sangha</h1>
            <p ...>Tier 0 — Bootstrap Verification</p>
        </div>
    </div>
    <nav class="flex gap-2">
        <a href="/" class="btn btn-sm btn-active">Bootstrap</a>
        <a href="/foundation" class="btn btn-sm btn-ghost">Foundation</a>
    </nav>
</header>
```
- Static logo (56×56px via `h-14 w-14`), title, and tier subtitle — no Alpine bindings.
- Two-link nav: `Bootstrap` is styled `btn-active` (the current page) and `Foundation`
  is `btn-ghost` (the other page, one click away). These are plain anchor tags, not
  Alpine-driven — the "active" styling is hardcoded per file rather than computed,
  since each HTML file only ever represents one nav state.

**System Status card (lines 38–62)** — a centred, narrow card (`max-w-md mx-auto`)
showing database connectivity as a three-way `x-if` chain:
```html
<template x-if="health.loading">
    <span ...><span class="loading loading-spinner loading-xs"></span> Checking...</span>
</template>
<template x-if="!health.loading && health.connected">
    <span ...><span class="badge badge-success badge-xs"></span> <span>Database Connected</span></span>
</template>
<template x-if="!health.loading && !health.connected">
    <span ...><span class="badge badge-error badge-xs"></span> <span>Database Unavailable</span></span>
</template>
```
- `x-if` (not `x-show`) is used for all three branches — Alpine physically adds/removes
  the `<template>`'s content from the DOM rather than toggling `display`, since exactly
  one of the three states is ever true and there is no need to keep the other two
  mounted.
- The three conditions are mutually exclusive and jointly exhaustive over
  `{loading: bool, connected: bool}`, so exactly one renders at a time.
- DaisyUI `loading loading-spinner loading-xs` renders an animated spinner;
  `badge-success`/`badge-error` render green/red dot badges. No raw error text is ever
  shown — the UI only ever displays one of these three fixed strings.

**Three-column responsive grid (line 65):**
```html
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 xl:gap-6">
```
- 1 column below `md` (mobile, stacked), 2 columns from `md` to below `xl` (tablet — the
  third card wraps below), 3 columns from `xl` up (desktop — all three side by side).

**Card 1 — RBAC Roles (lines 68–124):**
```html
<span class="badge badge-ghost badge-sm" x-text="roles.length + ' roles'"></span>
```
- `x-text` sets the badge's text content reactively to e.g. `"8 roles"`.

Three mutually exclusive `x-if` blocks gate the card body:
```html
<template x-if="rolesLoading">
    <div class="flex justify-center py-6">
        <span class="loading loading-spinner loading-md"></span>
    </div>
</template>

<template x-if="!rolesLoading && rolesError">
    <div class="alert alert-error mt-2">
        <span class="text-sm">Failed to load roles.</span>
    </div>
</template>

<template x-if="!rolesLoading && !rolesError && roles.length > 0">
    <div class="overflow-x-auto mt-2">
        <table class="table table-sm">
            <!-- header row + x-for body, shown separately below -->
        </table>
    </div>
</template>
```
- `rolesLoading` (spinner), `!rolesLoading && rolesError` (DaisyUI `alert alert-error`),
  and `!rolesLoading && !rolesError && roles.length > 0` (the data table) are mutually
  exclusive. There is no explicit "0 roles, no error" branch — Tier 0 always seeds 8
  roles, so this state is not designed for, but if the array were empty and non-error, no
  table would render (silently blank card body).

```html
<template x-for="role in roles" :key="role.role_master_pk">
    <tr class="cursor-pointer hover"
        :class="{ 'bg-base-200': selectedRole?.role_master_pk === role.role_master_pk }"
        @click="selectRole(role)">
```
- `x-for="role in roles"` — repeats the `<tr>` once per element of the `roles` array
  (§2.2 state).
- `:key="role.role_master_pk"` — gives Alpine a stable identity per row for efficient
  DOM diffing across re-renders (analogous to React's `key`).
- `:class="{ 'bg-base-200': ... }"` — conditionally applies the highlight class only to
  the row matching `selectedRole` (optional-chained since `selectedRole` starts `null`).
- `@click="selectRole(role)"` — calls the method (§2.2) that drives the third card.

The remaining cells in the row:
```html
<td class="font-mono text-xs whitespace-nowrap" x-text="role.role_code" :title="role.role_code"></td>
<td class="text-xs" x-text="role.role_name" :title="role.role_name"></td>
<td>
    <span class="badge badge-xs"
          :class="role.role_class === 'SYSTEM' ? 'badge-primary' : 'badge-secondary'"
          x-text="role.role_class">
    </span>
</td>
<td class="text-xs" x-text="role.scope_level || '—'"></td>
<td class="text-center">
    <span x-show="role.is_active" class="text-success">&#10003;</span>
    <span x-show="!role.is_active" class="text-error">&#10007;</span>
</td>
```
- `role.role_code` and `role.role_name` are bound via `x-text` and mirrored into a
  `:title` attribute (native browser hover tooltip) — useful since the code cell is
  `font-mono text-xs whitespace-nowrap` and can visually truncate on narrow layouts.
- Ternary `:class` on the class badge — `SYSTEM` roles get the primary (blue) badge
  colour, anything else (`ORGANIZATIONAL`) gets secondary.
- `scope_level` renders as `role.scope_level || '—'` (em dash fallback for null scope).
- The Active column uses two `x-show` spans (not `x-if`) — both `✓` (`&#10003;`,
  `text-success`) and `✗` (`&#10007;`, `text-error`) are always in the DOM; `x-show`
  merely toggles `display:none` on whichever doesn't match `role.is_active`.

**Card 2 — Permissions (lines 127–185):** structurally identical loading/error pattern,
plus a fourth `x-if` branch specific to this card:
```html
<template x-if="!permissionsLoading && !permissionsError && permissions.length === 0">
    <div class="py-4">
        <p ...>No permissions configured yet.</p>
        <p ...>Permission catalogue is populated progressively as functional modules are implemented.</p>
    </div>
</template>
```
- Unlike the Roles card, Permissions is expected to be empty in Tier 0 (no
  `permission_master` seed data), so this branch explicitly explains why, rather than
  silently rendering nothing. The data-table branch (`permissions.length > 0`) uses the
  same code/name cell pattern as Roles, but the class badge is replaced by a module badge:
```html
<span class="badge badge-outline badge-xs" x-text="perm.module_code"></span>
```
  and there is no `@click` handler on the `<tr>` — this table is not interactive.

**Card 3 — Role Permissions (lines 188–264)** — the only interactive/drill-down card:
```html
<template x-if="!selectedRole">
    <p ...>Select a role from the left to view its permissions.</p>
</template>
<template x-if="selectedRole">
    ...
</template>
```
- Before any row is clicked, shows a prompt. After selection, shows a detail strip:
```html
<div class="flex flex-wrap gap-x-4 gap-y-1 text-xs mb-3">
    <div>
        <span class="text-base-content/50">Role:</span>
        <span class="font-mono font-semibold" x-text="selectedRole.role_code"></span>
    </div>
    <div>
        <span class="text-base-content/50">Class:</span>
        <span x-text="selectedRole.role_class"></span>
    </div>
    <div>
        <span class="text-base-content/50">Scope:</span>
        <span x-text="selectedRole.scope_level || '—'"></span>
    </div>
</div>
```
  showing `selectedRole.role_code`, `role_class`, and `scope_level || '—'`, followed by
  its own independent loading/error/empty `x-if` chain:
```html
<template x-if="rolePermsLoading">
    <div class="flex items-center gap-2 py-2">
        <span class="loading loading-spinner loading-xs"></span>
        <span class="text-sm text-base-content/60">Loading permissions...</span>
    </div>
</template>

<template x-if="!rolePermsLoading && rolePermsError">
    <div class="alert alert-error">
        <span class="text-sm">Failed to load role permissions.</span>
    </div>
</template>

<template x-if="!rolePermsLoading && !rolePermsError && rolePermissions.length === 0">
    <p class="text-sm text-base-content/60">No permissions assigned.</p>
</template>
```
  driven by `rolePermsLoading` / `rolePermsError` / `rolePermissions`. The fourth branch
  (`rolePermissions.length > 0`) repeats the same code/name/module-badge/active-checkmark
  row shape used in Card 2.

**Footer (lines 269–271):**
```html
<footer class="text-center text-xs text-base-content/30 mt-6">
    <p>&copy; 2026 Nilachala Saraswata Sangha. All rights reserved.</p>
</footer>
```
- Static, no bindings.

**Script include (line 275):**
```html
<script src="/assets/js/app.js"></script>
```
- Loaded last, after the root `<div>` markup, without `defer` — by this point Alpine.js
  (deferred, loaded in `<head>`) has already executed and is waiting; `app.js` merely
  needs to define the global `bootstrapApp()` function before Alpine's initial scan
  reaches this `<div>`, which it does since script tags execute in document order and
  Alpine's own `defer`red execution runs after all synchronous scripts including this
  one.

---

### 2.8 `frontend/person.html`

**Requirement.** This is the Tier 3 "Person Verification UI" — the visual proof that the
4 read-only `/api/v1/person/*` endpoints correctly expose `person` and `person_address`
joined against Foundation's shared `master_data` (for gender, marital status, blood group,
emergency relationship, and address type lookups). It is structurally parallel to
`organization.html` (same head boilerplate, same System Status card reusing the Tier 0
health endpoint, same responsive tab bar) and organizes its surface area into two tabs:
Persons (list + filters + detail + addresses) and Search (trigram fuzzy search). Mobile-
responsive from initial implementation, using the same Tailwind breakpoint patterns as
`organization.html` (`px-3 sm:px-6`, `text-lg sm:text-2xl`, etc.). Served by FastAPI's
`GET /person` route, conditional on the file existing on disk. Sensitive fields
(`aadhaar_encrypted`, `aadhaar_hash`) are never sent by the API, so this page never has
the opportunity to render them — only the masked `aadhaar_last4` is displayed.

**Section-by-section walkthrough:**

**`<head>`:**
```html
<link rel="stylesheet" href="/assets/css/style.css">
<link rel="stylesheet" href="/assets/css/badges.css">
<script src="/assets/js/nss-config.js"></script>
```
- Same asset dependency block as the other three pages: same-origin, pre-built
  `/assets/css/tailwind.min.css` (Tailwind 3.x + DaisyUI 4, no SRI needed), Alpine.js
  3.14.8 with SRI, local `style.css`. Only the `<title>` differs ("— Person
  Verification").
- **(v1.5, Tier 4 shared-config extraction.)** The page-local `<style>` block quoted in
  earlier revisions of this document — a `.badge`/`.badge-xs`/`.badge-sm` padding override
  plus 3 `.badge-status-*` classes (`active`/`inactive`/`deceased`) — has been **removed**
  and replaced with the two shared includes shown above. `badges.css` (§2.14) now supplies
  all 18 `.badge-status-*` classes (a superset covering every page's needs, not just
  Person's 3); this page's `statusLabel()`/`statusBadgeClass()` helpers in `person.js`
  (§2.9) are unchanged — they still derive exactly three possible states (Active / Deceased
  / Inactive) client-side from `is_active` and `date_of_death`, since Person's lifecycle
  status is not sourced from Foundation's unified `STATUS` category at all — they simply now
  resolve to class names defined in the shared file instead of a page-local one.

**Root component:**
```html
<div x-data="personApp()" x-init="init()" class="mx-auto px-3 py-4 sm:px-6 sm:py-6 lg:px-10 2xl:px-16">
```
- Identical mobile-first padding scale to `organization.html`. Calls `personApp()` (§2.9).

**Header:** Same layout as the other three pages. The nav bar now has **four** links —
Bootstrap, Foundation, Organization, Person — with Person styled `btn-active`:
```html
<nav class="flex gap-2">
    <a href="/" class="btn btn-sm btn-ghost">Bootstrap</a>
    <a href="/foundation" class="btn btn-sm btn-ghost">Foundation</a>
    <a href="/organization" class="btn btn-sm btn-ghost">Organization</a>
    <a href="/person" class="btn btn-sm btn-active">Person</a>
</nav>
```
- Plain anchor tags, not Alpine-driven, same as the other pages — each file hardcodes
  which nav link is `btn-active` for itself.

**System Status card:** Identical `x-if` triad to the other three pages, bound to
`personApp().health`, calling the Tier 0 `/api/v1/bootstrap/health` endpoint.

**Tab bar:**
```html
<div class="tabs tabs-boxed bg-base-100 shadow-sm inline-flex min-w-max">
    <button class="tab tab-sm sm:tab-md" :class="{ 'tab-active': activeTab === 'persons' }" @click="switchTab('persons')">Persons</button>
    <button class="tab tab-sm sm:tab-md" :class="{ 'tab-active': activeTab === 'search' }" @click="switchTab('search')">Search</button>
</div>
```
- Only two tabs (vs Organization's three) — Person has no separate "Reference Data" tab
  because its filter dropdowns (gender/marital status/blood group) are populated inline
  from Foundation's `master-data` endpoint rather than surfaced as their own browsable
  tab. `tab-sm sm:tab-md` sizes the tab buttons down on mobile, matching the smaller
  `select-xs sm:select-sm` filter controls used throughout this page.

**Tab 1 — Persons:** A `grid-cols-1 xl:grid-cols-3` layout — the person list occupies
`xl:col-span-2` (left, wider) and the detail panel occupies the remaining column (right).

*Person list (left):*
```html
<select class="select select-bordered select-xs sm:select-sm"
        x-model="selectedGenderFilter" @change="filterPersons()">
    <option value="">All Genders</option>
    <template x-for="g in genderOptions" :key="g.value_code">
        <option :value="g.value_code" x-text="g.value_name"></option>
    </template>
</select>
```
- Three filter `<select>`s (gender, marital status, blood group), each `x-model`-bound to
  its own `selectedXFilter` property and triggering `filterPersons()` on `@change`. The
  options come from `genderOptions`/`maritalStatusOptions`/`bloodGroupOptions` (§2.9),
  populated from Foundation's `master-data` endpoint — not from a Person-specific
  reference-data endpoint, since Person has none. Unlike Organization's type filter, none
  of these three dropdowns is ever `:disabled` — every gender/marital-status/blood-group
  value is a valid, always-applicable filter.
- Standard loading/error/empty/data `x-if` quadruple (spinner → `alert alert-error` →
  "No persons match the current filters." → data table), the same four-state pattern used
  throughout Foundation and Organization.
- The table header row lists nine columns: Person ID, Name, Gender, DOB, Mobile, Email,
  Marital Status, Blood Group, Status. Each row:
```html
<tr class="cursor-pointer hover"
    :class="{ 'bg-base-200': selectedPerson?.person_pk === p.person_pk }"
    @click="selectPerson(p)">
    <td class="font-mono text-xs whitespace-nowrap" x-text="p.person_id"></td>
    <td class="text-xs font-medium whitespace-nowrap" x-text="formatName(p)"></td>
    ...
    <td class="whitespace-nowrap">
        <span class="badge badge-xs whitespace-nowrap"
              :class="statusBadgeClass(p)"
              x-text="statusLabel(p)"></span>
    </td>
</tr>
```
  — the same clickable-row/highlight-on-select pattern as Organization's organizations
  table, calling `selectPerson(p)` (§2.9). `formatName(p)` joins first/middle/last name
  parts; the Status cell uses `statusBadgeClass(p)`/`statusLabel(p)` rather than a
  Foundation- or Organization-style `status_code` lookup, per the `<head>` note above.

*Person Detail + Addresses (right):* Four mutually exclusive top-level `x-if` states —
"select a person" prompt (`!selectedPerson && !detailLoading`), spinner (`detailLoading`),
error (`detailError`), and the populated detail body (`selectedPerson && !detailLoading &&
!detailError`). The populated body is a sequence of labeled `<div>` grids, each wrapped in
its own `x-show` so a group with no data (e.g. no emergency contact) collapses entirely
rather than rendering empty labels:
- **Identity** — Person ID (`font-mono`) and the lifecycle Status badge.
- **Demographics** — Name (via `formatName()`), Gender, Date of Birth, Date of Death
  (only shown `x-show="selectedPerson.date_of_death"`), Marital Status, Blood Group.
- **Contact** — Mobile (via `formatPhone()`, only shown if `mobile_number` is present) and
  Email (rendered as a `mailto:` link, only shown if `email` is present).
- **Aadhaar (masked)** — the one field in this document that exists specifically to prove
  a security property:
```html
<div class="text-xs" x-show="selectedPerson.aadhaar_last4">
    <span class="text-base-content/50">Aadhaar:</span>
    <span class="font-mono" x-text="'XXXX XXXX ' + selectedPerson.aadhaar_last4"></span>
</div>
```
  The API's `PersonDetail` schema never includes `aadhaar_encrypted` or `aadhaar_hash` —
  only `aadhaar_last4` (a 4-digit string) is present on the wire. This markup renders it
  as `XXXX XXXX 1234`-style masked display; there is no code path in this file (or in
  `person.js`) that could render the full Aadhaar number, because the full number never
  reaches the browser in the first place.
- **Emergency Contact** — name, phone, and relationship (`emergency_relationship_name`,
  resolved server-side via a JOIN against `master_data`), wrapped in an outer `x-show` so
  the whole block (including its `divider`) disappears if none of the three fields exist.
- **Remarks** — free-text, `x-show="selectedPerson.remarks"`.
- **Addresses** — a sub-section with its own independent loading/error/empty/data `x-if`
  quadruple bound to `addressesLoading`/`addressesError`/`personAddresses`, fetched in
  parallel with the person detail itself (see `selectPerson()`, §2.9). Each address card:
```html
<div class="border border-base-300 rounded-lg p-2 text-xs">
    <div class="flex items-center gap-2 mb-1">
        <span class="badge badge-xs badge-primary" x-text="addr.address_type_name"></span>
        <template x-if="addr.is_primary">
            <span class="badge badge-xs badge-accent">Primary</span>
        </template>
        <template x-if="!addr.is_active">
            <span class="badge badge-xs badge-status-inactive">Inactive</span>
        </template>
    </div>
    <p x-text="addr.address_line_1"></p>
    <p x-show="addr.address_line_2" x-text="addr.address_line_2"></p>
    <p x-show="addr.landmark" class="text-base-content/60" x-text="'Landmark: ' + addr.landmark"></p>
    <p class="text-base-content/60"
       x-text="[addr.city_village_name, addr.postal_code, addr.district_name, addr.state_name, addr.country_name].filter(Boolean).join(', ')">
    </p>
    <p x-show="addr.remarks" class="text-base-content/40 italic" x-text="addr.remarks"></p>
</div>
```
  — an `address_type_name` badge (primary color), a conditional `Primary` badge
  (`badge-accent`, `x-if`) if `is_primary` is set, and a conditional `Inactive` badge
  (reusing the same `.badge-status-inactive` class defined for persons) if the address is
  soft-deleted. The geography line joins city/village, postal code, district, state, and
  country names — all resolved server-side via JOINs against Foundation's geography
  tables — filtering out any that are `null`/falsy before joining with `", "`.

**Tab 2 — Search:** Uses the same grid layout as the Persons tab
(`xl:grid-cols-3`) — search results on the left (2/3 width), detail panel on the right
(1/3 width). The search input is wired to the trigram `/search` endpoint:
```html
<input type="text" placeholder="Name, Person ID, Mobile, or Email (min 2 chars)"
       class="input input-bordered input-sm w-full"
       x-model="searchQuery"
       @keydown.enter="executeSearch()"
       @input="searchQuery.length >= 2 ? executeSearch() : (searchResults = [])">
```
- `x-model="searchQuery"` two-way-binds the input to state. `@keydown.enter` lets the user
  force an immediate search. `@input` fires on every keystroke: once the trimmed-in-place
  query reaches 2+ characters it calls `executeSearch()` (which internally debounces —
  see §2.9); below 2 characters it synchronously clears `searchResults` rather than
  calling the API, since the backend's trigram search has a documented 2-character
  minimum. A `label-text-alt` hint below the input reads "Uses trigram similarity for
  fuzzy name matching."
- Standard loading/error/empty/data `x-if` quadruple — the empty-state branch is gated by
  `searchExecuted` (`searchExecuted && searchResults.length === 0`) so "No results found."
  never flashes before the user has typed anything.
- The results table has seven columns (Person ID, Name, Gender, DOB, Mobile, Email,
  Status) — one fewer than the Persons tab's table (no Marital Status/Blood Group
  columns, since `PersonSummary`/search-result rows don't carry those fields). Clicking a
  result row calls `selectPerson(p)` directly — the detail loads **inline** in the
  right-hand panel without switching tabs:
```html
<tr class="cursor-pointer hover"
    @click="selectPerson(p)">
```
  — the search tab has its own detail panel (identical to the Persons tab's) so the user
  never loses the search context. This replaced the earlier `switchTab('persons');
  selectPersonByPk(p.person_pk)` pattern.

**Footer and script include:** Same copyright footer as the other three pages. Loads
`<script src="/assets/js/person.js"></script>` at the bottom.

---

### 2.9 `frontend/assets/js/person.js`

**Requirement.** The client-side state/behaviour layer for `person.html`, mirroring the
role `organization.js` plays for `organization.html` but scoped to the Person module's 4
API endpoints across 2 tabs, plus 3 Foundation `master-data` lookups for filter options.
Defines one global factory function, `personApp()`.

**Full file, 270 lines. Walkthrough:**

```javascript
const PERSON_API = "/api/v1/person";
const FOUNDATION_API = "/api/v1/foundation";
```
- Two module-scope constants, not one — unlike `organization.js` (which only ever calls
  its own router, with Foundation lookups happening server-side), `person.js` calls
  Foundation's `/master-data` endpoint **directly from the browser** to populate its
  gender/marital-status/blood-group filter dropdowns. Both are relative paths, same
  origin-agnostic pattern as the other three JS files.

**State properties** (grouped by the file's own comment banners):

```javascript
activeTab: "persons",
health: { loading: true, connected: false },
```
- Default tab is `"persons"`. Same health object shape, reusing the Tier 0 health
  endpoint.

**Filter options group (from Foundation master-data):**
```javascript
genderOptions: [],
maritalStatusOptions: [],
bloodGroupOptions: [],
```
- Backing arrays for the three filter `<select>`s, populated by `fetchFilterOptions()`
  from Foundation's `master-data` endpoint, not from any Person-specific endpoint.

**Persons group:**
```javascript
persons: [],
personsLoading: true,
personsError: false,
selectedGenderFilter: "",
selectedMaritalFilter: "",
selectedBloodGroupFilter: "",
```
- `persons` starts `loading: true` because `init()` fetches it eagerly. The three
  `selectedXFilter` strings are `x-model`-bound to the filter dropdowns and default to
  `""` (no filter applied).

**Detail group:**
```javascript
selectedPerson: null,
detailLoading: false,
detailError: false,
```
- `detailLoading`/`detailError` start `false` (unlike the list's loading flags) because
  the detail panel only loads in response to a user clicking a row — the same
  loads-on-demand pattern as `app.js`'s `rolePermsLoading`/`rolePermsError`.

**Addresses group:**
```javascript
personAddresses: [],
addressesLoading: false,
addressesError: false,
```
- Independent loading/error pair from the detail group's, even though both are fetched
  together in `selectPerson()` — addresses are allowed to fail without invalidating the
  already-loaded person detail (see `selectPerson()` below).

**Search group:**
```javascript
searchQuery: "",
searchResults: [],
searchLoading: false,
searchError: false,
searchExecuted: false,
_searchDebounce: null,
```
- `searchExecuted` distinguishes "never searched" from "searched, zero results" so the
  empty-state message in `person.html` doesn't show prematurely. `_searchDebounce` (a
  leading-underscore convention signaling "private, not for template use") holds the
  pending `setTimeout` handle for `executeSearch()`'s debounce.

**Init:**
```javascript
async init() {
    await this.fetchHealth();
    await Promise.all([
        this.fetchFilterOptions(),
        this.fetchPersons(),
    ]);
},
```
- Health check first (sequential), then filter options and the person list fetched
  **concurrently** via `Promise.all` — a hybrid of `app.js`'s all-parallel `init()` and
  `organization.js`'s all-sequential `init()`: the health probe still gates everything
  else, but the two independent data sources that follow don't wait on each other.

```javascript
async fetchHealth() { ... }
```
- Identical implementation to `organizationApp()`'s `fetchHealth()` — same `res.ok` /
  `data.database === "connected"` / bare-`catch` / `finally` pattern (see §2.2 for the
  full explanation of this pattern, reused verbatim here).

**Filter option loader:**
```javascript
async fetchFilterOptions() {
    const categories = ["GENDER", "MARITAL_STATUS", "BLOOD_GROUP"];
    const results = await Promise.allSettled(
        categories.map(cat =>
            fetch(`${FOUNDATION_API}/master-data?category_code=${cat}`)
                .then(r => r.ok ? r.json() : [])
        )
    );
    this.genderOptions = results[0].status === "fulfilled" ? results[0].value : [];
    this.maritalStatusOptions = results[1].status === "fulfilled" ? results[1].value : [];
    this.bloodGroupOptions = results[2].status === "fulfilled" ? results[2].value : [];
},
```
- Unlike every other multi-fetch in this codebase (which uses `Promise.all` and lets one
  failure reject the whole batch), this uses `Promise.allSettled` — each of the three
  `master-data?category_code=...` calls is allowed to fail independently, falling back to
  an empty array (`[]`) for just that one filter's options rather than blanking all three
  or throwing. This is the only `allSettled` usage across the four JS files; the filter
  dropdowns are a secondary, non-blocking feature of this page (the person list itself
  doesn't depend on them), so a partial failure degrading one dropdown to "no options" is
  preferable to failing the whole page.

**Tab switching:**
```javascript
async switchTab(tab) {
    this.activeTab = tab;
    if (tab === "persons" && this.persons.length === 0) {
        await this.fetchPersons();
    }
},
```
- Simpler than `organization.js`'s `switchTab()` (which dispatches to a `loadXTab()`
  helper per tab) because Person only has one tab (`persons`) that needs a lazy-load
  guard — `search` has no data to preload; its results only ever come from user input.

**Person list:**
```javascript
async fetchPersons() {
    this.personsLoading = true;
    this.personsError = false;
    try {
        let url = `${PERSON_API}/persons`;
        const params = [];
        if (this.selectedGenderFilter)
            params.push(`gender_code=${encodeURIComponent(this.selectedGenderFilter)}`);
        if (this.selectedMaritalFilter)
            params.push(`marital_status_code=${encodeURIComponent(this.selectedMaritalFilter)}`);
        if (this.selectedBloodGroupFilter)
            params.push(`blood_group_code=${encodeURIComponent(this.selectedBloodGroupFilter)}`);
        if (params.length) url += `?${params.join("&")}`;

        const res = await fetch(url);
        if (!res.ok) throw new Error(res.statusText);
        this.persons = await res.json();
    } catch {
        this.personsError = true;
    } finally {
        this.personsLoading = false;
    }
},
```
- Same optional-query-param-array-join pattern as `organization.js`'s
  `fetchOrganizations()`, generalized to three filters (`gender_code`,
  `marital_status_code`, `blood_group_code`) instead of two. Note this call does not send
  `limit`/`offset` — pagination controls are not wired up on this page; the endpoint's
  defaults apply server-side (see `docs/03_Solution/api/PERSON_API_CONTRACT.md` for the
  `/persons` endpoint's pagination defaults).

```javascript
async filterPersons() {
    this.selectedPerson = null;
    this.personAddresses = [];
    this.persons = [];
    await this.fetchPersons();

    if (this.persons.length === 1) {
        await this.selectPerson(this.persons[0]);
    }
},
```
- Bound to all three filter dropdowns' `@change`. Same clear-detail /
  blank-then-refetch / auto-select-single-result pattern as `organization.js`'s
  `filterOrganizations()` — clears `selectedPerson` and `personAddresses` first (the
  previous selection may not exist in the new filtered result set), blanks `persons` (so
  the spinner shows during refetch), then auto-selects if exactly one person matches the
  combined filters.

**Person detail:**
```javascript
async selectPerson(personSummary) {
    if (this.selectedPerson?.person_pk === personSummary.person_pk) {
        this.selectedPerson = null;
        this.personAddresses = [];
        return;
    }

    this.detailLoading = true;
    this.detailError = false;
    this.selectedPerson = null;
    this.personAddresses = [];

    try {
        const [detailRes, addrRes] = await Promise.all([
            fetch(`${PERSON_API}/persons/${personSummary.person_pk}`),
            fetch(`${PERSON_API}/persons/${personSummary.person_pk}/addresses`),
        ]);

        if (!detailRes.ok) throw new Error(detailRes.statusText);
        this.selectedPerson = await detailRes.json();

        if (addrRes.ok) {
            this.personAddresses = await addrRes.json();
        }
        // Addresses may legitimately be empty — don't fail detail for it
    } catch {
        this.detailError = true;
    } finally {
        this.detailLoading = false;
    }
},
```
- Same toggle-off guard as `organization.js`'s `selectOrganization()` — clicking the
  already-selected row deselects. On a new selection, fetches `GET /persons/{pk}` and
  `GET /persons/{pk}/addresses` **concurrently** via `Promise.all`, but only the detail
  response's failure is fatal (`detailRes.ok` check throws into the `catch`, setting
  `detailError`); the addresses response is checked independently (`if (addrRes.ok)`)
  with no `throw` on failure, so a broken/slow addresses call degrades to an empty address
  list rather than blocking the whole detail panel from rendering — the comment in the
  source (`// Addresses may legitimately be empty — don't fail detail for it`) documents
  this intentional asymmetry.

**Search:**
```javascript
async executeSearch() {
    const q = this.searchQuery.trim();
    if (q.length < 2) {
        this.searchResults = [];
        this.searchExecuted = false;
        return;
    }

    if (this._searchDebounce) clearTimeout(this._searchDebounce);
    this._searchDebounce = setTimeout(async () => {
        this.searchLoading = true;
        this.searchError = false;
        this.searchExecuted = true;
        try {
            const res = await fetch(
                `${PERSON_API}/search?q=${encodeURIComponent(q)}`
            );
            if (!res.ok) throw new Error(res.statusText);
            this.searchResults = await res.json();
            if (this.searchResults.length === 1) {
                await this.selectPerson(this.searchResults[0]);
            }
        } catch {
            this.searchError = true;
        } finally {
            this.searchLoading = false;
        }
    }, 300);
},
```
- The only debounced fetch across all four JS files. Called on every keystroke once the
  input reaches 2+ characters (see `person.html`'s `@input` handler, §2.8). Trims the
  query first; below 2 trimmed characters, it clears results and resets `searchExecuted`
  synchronously without touching the network — matching the backend's trigram-search
  minimum-length requirement. Otherwise it clears any previously pending timer
  (`clearTimeout`) and schedules a new one 300ms out; only the last keystroke within any
  300ms window actually reaches `GET /search?q=...`, preventing a request-per-keystroke
  flood while typing. `q` is `encodeURIComponent`-encoded in the URL.
  After results are loaded, the **auto-select single result** pattern fires: if exactly
  one person matches, `selectPerson()` is called immediately — the user sees the detail
  panel populate without needing to click. This matches the same auto-select behavior
  used by `filterPersons()` and `membership.js`'s `executeSearch()`.

**Helpers:**
```javascript
formatName(p) {
    return [p.first_name, p.middle_name, p.last_name]
        .filter(Boolean)
        .join(" ");
},
```
- Joins the three name parts with a space, dropping any that are falsy (`null`/`""`) —
  e.g. a person with no middle name renders as `"First Last"`, not `"First  Last"` with a
  double space.

```javascript
formatPhone(p) {
    if (!p.mobile_number) return "—";
    if (p.country_phone_code) return `${p.country_phone_code} ${p.mobile_number}`;
    return p.mobile_number;
},
```
- Em-dash fallback for no mobile number; prefixes the country calling code
  (`country_phone_code`, e.g. `+91`) when present.

```javascript
statusLabel(p) {
    if (!p.is_active) return "Inactive";
    if (p.date_of_death) return "Deceased";
    return "Active";
},

statusBadgeClass(p) {
    if (!p.is_active) return "badge-status-inactive";
    if (p.date_of_death) return "badge-status-deceased";
    return "badge-status-active";
},
```
- The pair driving every Status badge on this page (list rows, search results, and the
  detail panel). Both check `is_active` first (soft-delete takes precedence over deceased
  status — an inactive-and-deceased person still shows "Inactive," not "Deceased") then
  `date_of_death` (a person can be `is_active = true` and still have a recorded date of
  death — e.g. before an admin formally deactivates the record — which is why "Deceased"
  is a distinct label from "Inactive" rather than folded into it). This is Person's
  entire lifecycle-status model — three states derived from two raw columns — in contrast
  to Organization's 13-value `STATUS` master-data category (§2.6/§2.7); Person's `person`
  table carries no separate status/lifecycle master-data FK.

---

### 2.2 `frontend/assets/js/app.js`

**Requirement.** This file is the entire client-side "brain" for `index.html`: it owns
all reactive state (loading flags, fetched arrays, selection state) and all
communication with the four Tier 0 Bootstrap API endpoints. It exists so `index.html`
stays pure markup — every dynamic behaviour lives here, in one factory function,
`bootstrapApp()`, that Alpine.js instantiates via `x-data="bootstrapApp()"`.

**Full file, 108 lines. Walkthrough:**

```javascript
const API_BASE = "/api/v1/bootstrap";
```
- Module-scope constant, not part of the returned Alpine store. A **relative** path —
  no scheme/host/port — so requests always target whatever origin served this page
  (works identically on `localhost:8001`, a Render deployment, etc., with zero
  configuration).

```javascript
function bootstrapApp() {
    return {
```
- A plain factory function returning a plain object literal. Alpine calls this once per
  `x-data` mount and uses the returned object as the reactive store (Alpine wraps every
  property in a reactivity proxy).

**State properties** (in declaration order):

```javascript
health: { loading: true, connected: false },
```
- Nested object backing the System Status card; starts "checking" and "not connected"
  until the first fetch resolves.

```javascript
roles: [],
rolesLoading: true,
rolesError: false,
```
- `roles` is the backing array for the RBAC Roles table, empty until `fetchRoles()`
  populates it. `rolesLoading` gates the Roles card's spinner branch — `true` from the
  start because `init()` fetches immediately on mount. `rolesError` gates the Roles
  card's error `alert`.

```javascript
permissions: [],
permissionsLoading: true,
permissionsError: false,
```
- Backing array for the Permissions table, plus the same loading/error pair pattern as
  `roles`/`rolesLoading`/`rolesError`.

```javascript
selectedRole: null,
rolePermissions: [],
rolePermsLoading: false,
rolePermsError: false,
```
- `selectedRole` is the clicked role object, or `null` if none selected — read by the
  `:class` highlight binding and the Role Permissions card's `x-if`. `rolePermissions`
  holds the permissions for `selectedRole`, populated on click. `rolePermsLoading` starts
  `false` (unlike `rolesLoading`/`permissionsLoading`) because this panel only loads in
  response to a user click, not on initial mount; `rolePermsError` follows the same
  toggle-on-demand pattern.

**Methods:**

```javascript
async init() {
    await Promise.all([
        this.fetchHealth(),
        this.fetchRoles(),
        this.fetchPermissions(),
    ]);
},
```
- Called once by `x-init="init()"`. `Promise.all` fires all three fetches **concurrently**
  rather than sequentially — each card populates independently as soon as its own fetch
  resolves, instead of waiting for the slowest of the three before showing any data.

```javascript
async fetchHealth() {
    this.health.loading = true;
    try {
        const res = await fetch(`${API_BASE}/health`);
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        this.health.connected = data.database === "connected";
    } catch {
        this.health.connected = false;
    } finally {
        this.health.loading = false;
    }
},
```
- Calls `GET /api/v1/bootstrap/health`. `res.ok` is `true` only for HTTP 200–299; a
  non-2xx status is deliberately converted into a thrown `Error` so it falls into the
  same `catch` as a network failure or JSON-parse failure — the UI treats "reachable but
  errored" and "unreachable" identically as "disconnected."
- `data.database === "connected"` reads the specific field from the API's
  `HealthResponse` shape (`{status, database}`) — it does not merely check `res.ok`,
  since the health endpoint can return HTTP 200 with `database: "unreachable"` (a
  "degraded" but still-responding API).
- The bare `catch { ... }` (no bound error variable) intentionally discards the error
  object — no error detail is ever surfaced to `connected`, satisfying the "never expose
  raw database errors" design constraint.
- `finally` unconditionally clears `loading`, regardless of which branch ran.

```javascript
async fetchRoles() {
    this.rolesLoading = true;
    this.rolesError = false;
    try {
        const res = await fetch(`${API_BASE}/roles`);
        if (!res.ok) throw new Error(res.statusText);
        this.roles = await res.json();
    } catch {
        this.rolesError = true;
    } finally {
        this.rolesLoading = false;
    }
},
```
- Identical four-step shape to every other fetch method in this file (and in
  `foundation.js`): (1) set `loading=true, error=false`; (2) `try` fetch → check
  `res.ok` → parse JSON → assign to state; (3) `catch` sets only the error flag; (4)
  `finally` clears loading. `GET /api/v1/bootstrap/roles` returns the 10 frozen roles as
  a JSON array which is assigned wholesale to `this.roles`, triggering the `x-for` in
  `index.html` to re-render.

```javascript
async fetchPermissions() {
    this.permissionsLoading = true;
    this.permissionsError = false;
    try {
        const res = await fetch(`${API_BASE}/permissions`);
        if (!res.ok) throw new Error(res.statusText);
        this.permissions = await res.json();
    } catch {
        this.permissionsError = true;
    } finally {
        this.permissionsLoading = false;
    }
},
```
- Same four-step pattern against `GET /api/v1/bootstrap/permissions`. In Tier 0 this
  endpoint always returns `[]` (no `permission_master` seed data) — the method has no
  special-case handling for that; an empty array is a perfectly normal successful
  response, and the "No permissions configured yet" messaging lives entirely in the
  HTML's `x-if permissions.length === 0` branch, not here.

```javascript
async selectRole(role) {
    // Toggle off if clicking the same role
    if (this.selectedRole?.role_master_pk === role.role_master_pk) {
        this.selectedRole = null;
        this.rolePermissions = [];
        return;
    }

    this.selectedRole = role;
    this.rolePermsLoading = true;
    this.rolePermsError = false;
    this.rolePermissions = [];

    try {
        const res = await fetch(
            `${API_BASE}/roles/${role.role_master_pk}/permissions`
        );
        if (!res.ok) throw new Error(res.statusText);
        this.rolePermissions = await res.json();
    } catch {
        this.rolePermsError = true;
    } finally {
        this.rolePermsLoading = false;
    }
},
```
- Triggered by `@click="selectRole(role)"` on each role row.
- **Toggle guard first**: `this.selectedRole?.role_master_pk === role.role_master_pk` —
  the optional-chain (`?.`) is required because `selectedRole` may be `null` on the
  first call; comparing `null?.role_master_pk` yields `undefined`, which never equals a
  real UUID, so the guard is false and execution falls through on first click. Clicking
  the *same* already-selected role a second time clears both `selectedRole` and
  `rolePermissions` and returns early — no fetch is issued.
- Selecting a *different* (or first) role sets `selectedRole`, immediately blanks
  `rolePermissions` (so stale data from a previous selection never flashes under the new
  role's header while the new fetch is in flight), then fetches
  `GET /api/v1/bootstrap/roles/{role_pk}/permissions`. In Tier 0 this always resolves to
  `[]` (no `role_permission` seed rows), but the fetch/loading/error machinery is fully
  exercised regardless.

---

### 2.3 `frontend/foundation.html`

**Requirement.** This is the Tier 1 "Foundation Verification UI" — the visual proof that
the 17 read-only `/api/v1/foundation/*` endpoints correctly expose 11 of the 12
Foundation tables (the 12th, `field_change_log`, is intentionally never exposed — audit
data needs authentication, deferred to Tier 5). It is structurally parallel to
`index.html` (same head boilerplate, same System Status card reusing the Tier 0 health
endpoint, same nav bar) but organizes its much larger surface area — master data,
system config, a 4-level geographic hierarchy, and runtime tables — into four tabs
instead of index.html's fixed three-column layout, since all of that could not
reasonably fit on one screen at once. Served by FastAPI's explicit `GET /foundation`
route, conditional on the file existing on disk.

**Section-by-section walkthrough** (597 lines):

**`<head>` (lines 1–17):**
```html
<title>Nilachala Saraswata Sangha — Foundation Verification</title>

<!-- Tailwind CSS 3.x + DaisyUI 4 (pre-built, tree-shaken — see tailwind.config.js) -->
<link rel="stylesheet" href="/assets/css/tailwind.min.css">
<!-- Alpine.js 3.14.8 -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.8/dist/cdn.min.js" integrity="sha384-X9kJyAubVxnP0hcA+AMMs21U445qsnqhnUF8EBlEpP3a42Kh/JwWjlv2ZcvGfphb" crossorigin="anonymous"></script>

<link rel="stylesheet" href="/assets/css/style.css">
```
- Byte-for-byte the same asset block as `index.html` (§2.1) — same same-origin,
  pre-built `/assets/css/tailwind.min.css` `<link>` (no SRI, since it is served by this
  app itself), same Alpine.js 3.14.8 `<script defer>` with the identical
  `integrity="sha384-X9kJyAubVxnP0hcA+AMMs21U445qsnqhnUF8EBlEpP3a42Kh/JwWjlv2ZcvGfphb"`
  hash, same local `/assets/css/style.css` link, and — as of the Tier 4 shared-config
  extraction (see §2.1) — the same `/assets/css/badges.css` + `/assets/js/nss-config.js`
  `<head>` includes (§2.14–§2.15) in place of the old per-page `.badge-status-*` `<style>`
  block. Only the `<title>` differs ("— Foundation Verification").

**Root component and header (lines 20–35):**
```html
<div x-data="foundationApp()" x-init="init()" class="mx-auto px-6 py-6 lg:px-10 2xl:px-16">
```
- Same wrapper pattern as `index.html`, calling `foundationApp()` (§2.4) instead of
  `bootstrapApp()`. Header is identical except the subtitle reads "Tier 1 — Foundation
  Verification" and the nav swaps which link is `btn-active`:
```html
<a href="/" class="btn btn-sm btn-ghost">Bootstrap</a>
<a href="/foundation" class="btn btn-sm btn-active">Foundation</a>
```

**System Status card (lines 38–62):** byte-for-byte identical `x-if` triad to
`index.html` (`health.loading` / `!loading && connected` / `!loading && !connected`),
bound to the same-shaped `health` object — but here it is populated by
`foundationApp().fetchHealth()` calling the *Tier 0* endpoint
`/api/v1/bootstrap/health` directly (§2.4), not a Foundation-specific health check.
Foundation has no `/api/v1/foundation/health` of its own; it deliberately reuses Tier 0's.

**Tab bar (lines 65–70):**
```html
<div class="tabs tabs-boxed bg-base-100 shadow-sm mb-4 inline-flex">
    <button class="tab" :class="{ 'tab-active': activeTab === 'master' }" @click="switchTab('master')">Master Data</button>
    <button class="tab" :class="{ 'tab-active': activeTab === 'config' }" @click="switchTab('config')">System Config</button>
    <button class="tab" :class="{ 'tab-active': activeTab === 'geo' }" @click="switchTab('geo')">Geographic</button>
    <button class="tab" :class="{ 'tab-active': activeTab === 'runtime' }" @click="switchTab('runtime')">Runtime Tables</button>
</div>
```
- DaisyUI `tabs tabs-boxed` component. Each `<button>`'s `:class` object-syntax binding
  adds `tab-active` only when `activeTab` (state, default `"master"`) equals that tab's
  key. `@click="switchTab('config')"` (etc.) is the only way `activeTab` changes — see
  §2.4 for the lazy-load side effects triggered inside `switchTab()`.

**Tab panel wrapper pattern** — all four tab bodies share:
```html
<div x-show="activeTab === 'master'" x-cloak>
```
- `x-show` (not `x-if`) — all four tab `<div>`s stay mounted in the DOM at all times;
  only `display` is toggled. This is a deliberate contrast with `index.html`'s use of
  `x-if` for its mutually-exclusive states: here, once a tab's data has been fetched
  (e.g. drilled several levels into Geographic), switching away and back must not lose
  that DOM/selection state, which `x-if` (destroy-and-recreate) would do but `x-show`
  (hide-and-keep) does not.
- `x-cloak` — combined with the CSS rule in `style.css` (§2.5), this hides the panel
  markup (including raw `{{ }}`/directive text) until Alpine has finished its initial
  render pass, preventing a flash of unstyled/unbound content on first page load. It is
  used here (and not in `index.html`) because `index.html`'s equivalent branching is all
  done via `<template x-if>`, which Alpine never renders to the live DOM until the
  condition is true — so there is nothing to cloak. `foundation.html`'s tab panels are
  live, always-present DOM nodes that only start correctly hidden once Alpine attaches,
  hence the extra `x-cloak` guard.

**Tab 1 — Master Data (lines 72–191):** a 2-column grid of two cards:
```html
<div class="grid grid-cols-1 xl:grid-cols-2 gap-4 xl:gap-6">
```
- 1 column on mobile, 2 columns from `xl` up — Master Categories on the left, Master
  Data Values on the right.

**Master Categories card:**
```html
<h2 class="card-title text-sm uppercase tracking-wide text-base-content/50">Master Categories</h2>
<span class="badge badge-ghost badge-sm" x-text="categories.length + ' categories'"></span>
```
- Badge counter, same pattern as `index.html`'s cards. The body is gated by a
  loading/error/data `x-if` triad — with no explicit "empty" branch, since categories
  are seeded:
```html
<template x-if="categoriesLoading"> ... spinner ... </template>
<template x-if="!categoriesLoading && categoriesError"> ... alert ... </template>
<template x-if="!categoriesLoading && !categoriesError"> ... table ... </template>
```
- The data-table row:
```html
<template x-for="cat in categories" :key="cat.master_category_pk">
    <tr class="hover">
        <td class="font-mono text-xs whitespace-nowrap" x-text="cat.category_code"></td>
        <td class="text-xs" x-text="cat.category_name"></td>
        <td class="text-xs text-base-content/60 max-w-xs truncate" x-text="cat.description || '—'" :title="cat.description"></td>
        <td class="text-xs text-center" x-text="cat.display_order"></td>
        <td class="text-center">
            <span x-show="cat.is_active" class="text-success">&#10003;</span>
            <span x-show="!cat.is_active" class="text-error">&#10007;</span>
        </td>
    </tr>
</template>
```
- Renders `category_code`, `category_name`, a truncated `description || '—'` with
  `:title` carrying the full text for a hover tooltip, `display_order`, and the same
  `x-show` ✓/✗ active-indicator pattern seen in `index.html`.

**Master Data Values card:**
```html
<span class="badge badge-ghost badge-sm" x-text="filteredMasterData.length + ' values'"></span>
```
- Badge counter bound to a **computed getter**, `filteredMasterData.length + ' values'`
  (not the raw `masterData.length`), because this card is filterable. The filter control:
```html
<select class="select select-bordered select-sm w-full max-w-xs"
        x-model="selectedCategoryCode"
        @change="filterByCategory()">
    <option value="">All Categories</option>
    <template x-for="cat in categories" :key="cat.category_code">
        <option :value="cat.category_code" x-text="cat.category_name"></option>
    </template>
</select>
```
  - `x-model="selectedCategoryCode"` — two-way binds the `<select>`'s value to state;
    Alpine keeps them in sync in both directions.
  - `@change="filterByCategory()"` — re-fetches master data scoped to the newly chosen
    category (or all, if `"All Categories"` — empty string — is chosen); see §2.4.
  - The `<option>` list is itself an `x-for` over `categories`, so the dropdown's
    choices are populated from the same API data as the left card, never hardcoded.
- The data-table row:
```html
<template x-for="md in filteredMasterData" :key="md.master_data_pk">
    <tr class="hover">
        <td><span class="badge badge-outline badge-xs" x-text="md.category_code"></span></td>
        <td class="font-mono text-xs whitespace-nowrap" x-text="md.value_code"></td>
        <td class="text-xs" x-text="md.value_name"></td>
        <td class="text-xs text-center" x-text="md.display_order"></td>
        <td class="text-center">
            <span x-show="md.is_active" class="text-success">&#10003;</span>
            <span x-show="!md.is_active" class="text-error">&#10007;</span>
        </td>
    </tr>
</template>
```
- Iterates `x-for="md in filteredMasterData"` — the **computed getter**, not `masterData`
  directly — showing a `category_code` badge, `value_code`, `value_name`,
  `display_order`, and the same ✓/✗ pattern.

**Tab 2 — System Config (lines 193–292):** same 2-column grid shape.

**System Settings card** — a flat table, no filter, no interactivity:
```html
<template x-for="s in settings" :key="s.system_setting_pk">
    <tr class="hover">
        <td class="font-mono text-xs whitespace-nowrap" x-text="s.setting_key"></td>
        <td class="text-xs font-semibold" x-text="s.setting_value"></td>
        <td><span class="badge badge-outline badge-xs" x-text="s.data_type"></span></td>
        <td class="text-xs text-base-content/60 max-w-xs truncate" x-text="s.description || '—'" :title="s.description"></td>
    </tr>
</template>
```
- `setting_key` (mono), `setting_value` in `font-semibold`, a `data_type` outline badge,
  and a truncated `description` with the full text in `:title`.

**ID Sequences card** — table with "Max Digits" and "Range" columns (renamed from "Padding"
and "Format Sample" in the v2.0 migration — see the note at §2.4):
```html
<td class="text-xs text-center" x-text="seq.padding_length"></td>
<td class="font-mono text-xs text-primary" x-text="formatSample(seq)"></td>
```
- The "Max Digits" column displays the raw `seq.padding_length` value directly — the
  maximum number of digits the numeric portion of an ID can grow to (e.g. 8 means up to
  8 digits, so up to 99,999,999).
- The "Range" column calls the `formatSample(seq)` helper (§2.4) per row to synthesize a
  `min → max` range string from `prefix` + `padding_length` (e.g. `SS1 → SS99999999` for
  `padding_length: 8`) — the column deliberately
  does **not** display `current_value`, because the API response (`SequenceResponse`) never
  includes that field at all (it is infrastructure state, excluded by design at the
  Pydantic-schema layer).

**Tab 3 — Geographic (lines 294–518):** the most complex tab — an interactive
drill-down through Country → State → District → City/Village, plus a Postal Codes panel
keyed off the selected country.

Breadcrumb (rendered only once a country is selected):
```html
<template x-if="selectedCountry">
    <div class="flex items-center gap-1 text-sm mb-4">
        <span x-text="selectedCountry.country_name"></span>
        <template x-if="selectedState">
            <span><span>&#x203A;</span><span x-text="selectedState.state_name"></span></span>
        </template>
        <template x-if="selectedDistrict">
            <span><span>&#x203A;</span><span x-text="selectedDistrict.district_name"></span></span>
        </template>
    </div>
</template>
```
- Three nested `x-if` templates build a progressively longer breadcrumb
  (`India`, then `India › Odisha`, then `India › Odisha › Khordha`) as deeper
  selections are made. The separator is the literal entity `&#x203A;` (›) rather than a
  DaisyUI/CSS pseudo-element, chosen because pseudo-element separators did not render
  consistently in all configurations tested.

Four-column grid of drill-down list cards:
```html
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
```
- 1 column on mobile, 2 from `md`, 4 (Countries/States/Districts/Cities side by side)
  from `xl` up. Each level follows the same shape (shown here for Countries → States;
  Districts → Cities/Villages repeat it one level deeper):
```html
<template x-for="c in countries" :key="c.country_pk">
    <button class="btn btn-sm btn-block justify-start gap-2"
            :class="selectedCountry?.country_pk === c.country_pk ? 'btn-primary' : 'btn-ghost'"
            @click="selectCountry(c)">
        <span class="font-mono text-xs" x-text="c.country_code"></span>
        <span class="text-xs" x-text="c.country_name"></span>
    </button>
</template>
```
- Full-width (`btn-block`) buttons, not table rows, for the list-of-buttons drill-down
  affordance. Selected item gets `btn-primary` (Countries), `btn-secondary` (States), or
  `btn-accent` (Districts) — a different DaisyUI accent colour per depth level, purely
  visual, so the currently active path through the hierarchy is scannable at a glance.
- The States/Districts/Cities cards additionally gate on the parent selection:
```html
<template x-if="!selectedCountry">
    <p ...>Select a country to view states.</p>
</template>
<template x-if="selectedCountry && statesLoading"> ... </template>
<template x-if="selectedCountry && !statesLoading && !statesError"> ... list ... </template>
```
  and Districts/Cities add a fourth branch for the empty-but-loaded case:
```html
<template x-if="selectedState && !districtsLoading && !districtsError && districts.length === 0">
    <p ...>No districts seeded for this state.</p>
</template>
```
  distinguishing "nothing selected yet," "loading," "error," and "loaded but genuinely
  empty" as four separate, explicit UI states (Cities/Villages' empty state adds an
  extra explanatory line: "This is expected — city/village data is deferred reference
  data.").

Postal Codes panel (lines 468–517), rendered only when a country is selected, keyed to
`selectedCountry` rather than to any deeper selection:
```html
<h2 ...>Postal Codes — <span x-text="selectedCountry.country_name"></span></h2>
```
- The data-table row:
```html
<template x-for="pc in postalCodes" :key="pc.postal_code_pk">
    <tr class="hover">
        <td class="font-mono text-xs" x-text="pc.postal_code"></td>
        <td class="text-xs" x-text="pc.state_name"></td>
        <td class="text-center">
            <span x-show="pc.is_active" class="text-success">&#10003;</span>
            <span x-show="!pc.is_active" class="text-error">&#10007;</span>
        </td>
    </tr>
</template>
```
- `postal_code`, `state_name`, and the ✓/✗ active indicator; own independent
  `postalCodesLoading` gate and an "empty for this country" message. Under the Simplified
  Geography Model (2026-10-02) each PIN is a single row carrying its pre-resolved dominant
  state, so there is no office-name column to render and no multi-office fan-out to collapse.

**Tab 4 — Runtime Tables (lines 520–585):** a single, narrower Document Master card:
```html
<section class="card bg-base-100 shadow-sm max-w-2xl">
```
- `max-w-2xl` caps the card's width — unlike the other tabs' full-width grids, this tab
  has only one card, so it is intentionally not stretched. Badge counter, and a
  loading/empty/data `x-if` triad (loading spinner; `documents.length === 0`; `documents.length > 0`) gate the body.
- The data-table row:
```html
<template x-for="doc in documents" :key="doc.document_master_pk">
    <tr class="hover">
        <td><span class="badge badge-outline badge-xs" x-text="doc.document_type_code"></span></td>
        <td class="text-xs" x-text="doc.document_name"></td>
        <td class="font-mono text-xs" x-text="doc.document_number || '—'"></td>
        <td class="text-xs" x-text="doc.mime_type || '—'"></td>
        <td class="text-xs text-center" x-text="doc.version"></td>
    </tr>
</template>
```
- `document_type_code` (badge), `document_name`, `document_number || '—'`,
  `mime_type || '—'`, `version`. Closes with a static explanatory footnote, not
data-bound:
```html
<p class="text-xs text-base-content/40">
    field_change_log exists in the database but is not exposed in Tier 1.
    Audit data requires authentication — deferred to Tier 5.
</p>
```
- This line exists purely to document, in the running UI itself, why a 12th Foundation
  table has no corresponding tab/section anywhere on the page.

**Footer and script include (lines 587–594):** identical copyright footer to
`index.html`; loads `<script src="/assets/js/foundation.js"></script>` at the bottom.

---

### 2.4 `frontend/assets/js/foundation.js`

**Requirement.** The client-side state/behaviour layer for `foundation.html`, mirroring
the role `app.js` plays for `index.html` but scaled to cover 6 API resource groups
(categories, master-data, settings, sequences, 5 geographic levels, documents) across 4
lazily-loaded tabs, plus a filter dropdown and a multi-level toggleable drill-down.
Defines one global factory function, `foundationApp()`.

**Full file, 332 lines. Walkthrough:**

```javascript
const FND_API = "/api/v1/foundation";
```
- Same relative-path pattern as `app.js`'s `API_BASE`, scoped to the Foundation router
  prefix. The Tier 0 health check is called via its own separate literal path
  (`/api/v1/bootstrap/health`) inside `fetchHealth()` rather than through this constant,
  since it belongs to a different router.

**State properties**, in the order declared, grouped by the file's own comment banners:

```javascript
activeTab: "master",
```
- Controls which of the four tab panels is visible; read by every
  `x-show="activeTab === '...'"` binding and every tab button's `:class`.

```javascript
health: { loading: true, connected: false },
```
- Identical shape to `app.js`, reused for the shared System Status card.

**Master Data group:**
```javascript
categories: [],
categoriesLoading: true,
categoriesError: false,

masterData: [],
masterDataLoading: false,
masterDataError: false,
selectedCategoryCode: "",  // filter dropdown
```
- `selectedCategoryCode` is bound via `x-model` to the filter `<select>`. Note the
  asymmetry: `categoriesLoading` starts `true` (fetched eagerly by `init()`) but
  `masterDataLoading` starts `false` — both are actually fetched together in
  `loadMasterTab()` (below), so this initial `false` is momentarily inaccurate but is
  overwritten to `true` within `fetchMasterData()` before any render depending on it
  would matter in practice.

**System Settings group:**
```javascript
settings: [],
settingsLoading: true,
settingsError: false,
```

**ID Sequences group:**
```javascript
sequences: [],
sequencesLoading: true,
sequencesError: false,
```

**Geographic group:**
```javascript
countries: [],
countriesLoading: true,
countriesError: false,

states: [],
statesLoading: false,
statesError: false,
selectedCountry: null,

districts: [],
districtsLoading: false,
districtsError: false,
selectedState: null,

cities: [],
citiesLoading: false,
citiesError: false,
selectedDistrict: null,

postalCodes: [],
postalCodesLoading: false,
postalCodesError: false,
```
- Only `countries*` starts in the "loading" state (fetched eagerly when the Geographic
  tab is first opened); every deeper level (`states`/`districts`/`cities`/`postalCodes`)
  starts `loading: false` because it is fetched only in reaction to a parent-level click.

**Runtime group:**
```javascript
documents: [],
documentsLoading: true,
documentsError: false,
```
- There is also an implicit, undeclared `_runtimeLoaded` flag — see `loadRuntimeTab()`
  below — set as a property the first time it's assigned rather than declared upfront in
  the returned object literal.

**Init:**
```javascript
async init() {
    await this.fetchHealth();
    // Load data for the default tab
    await this.loadMasterTab();
},
```
- Unlike `app.js`'s `init()` (which fires 3 fetches in `Promise.all` concurrently),
  this `init()` awaits sequentially: health check first, then the default tab's data.
  Only the default (`"master"`) tab's data is loaded eagerly — the other three tabs'
  data is deferred until first visited.

```javascript
async fetchHealth() {
    this.health.loading = true;
    try {
        const res = await fetch("/api/v1/bootstrap/health");
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        this.health.connected = data.database === "connected";
    } catch {
        this.health.connected = false;
    } finally {
        this.health.loading = false;
    }
},
```
- Byte-for-byte the same try/catch/finally shape as `app.js`'s `fetchHealth()`, against
  the Tier 0 endpoint by its literal path (not `FND_API`, since it isn't a Foundation
  route).

**Tab switching and lazy loading:**
```javascript
async switchTab(tab) {
    this.activeTab = tab;
    if (tab === "master") await this.loadMasterTab();
    else if (tab === "config") await this.loadConfigTab();
    else if (tab === "geo") await this.loadGeoTab();
    else if (tab === "runtime") await this.loadRuntimeTab();
},
```
- Bound to every tab button's `@click`. Sets `activeTab` (driving the `x-show`
  bindings) and then delegates to the tab-specific loader.

```javascript
async loadMasterTab() {
    if (this.categories.length === 0) await this.fetchCategories();
    if (this.masterData.length === 0) await this.fetchMasterData();
},

async loadConfigTab() {
    if (this.settings.length === 0) await this.fetchSettings();
    if (this.sequences.length === 0) await this.fetchSequences();
},

async loadGeoTab() {
    if (this.countries.length === 0) await this.fetchCountries();
},

async loadRuntimeTab() {
    if (!this._runtimeLoaded) {
        await this.fetchDocuments();
        this._runtimeLoaded = true;
    }
},
```
- **Lazy-load-once guards.** `loadMasterTab`/`loadConfigTab`/`loadGeoTab` all use
  `if (array.length === 0)` as the "not yet loaded" test — cheap and works because none
  of those endpoints are expected to legitimately return an empty array in a healthy
  system (categories/master-data/settings/sequences/countries are all seeded).
  `loadRuntimeTab` cannot use that same test, because `documents` is *expected* to be
  legitimately empty (no seed data, runtime-populated table) — an empty-array check
  would re-fetch on every single tab visit. Instead it introduces a one-shot boolean
  flag, `this._runtimeLoaded`, assigned dynamically (not present in the initial state
  object literal) the first time this method runs, and checked thereafter.

**Master Data fetchers:**
```javascript
async fetchCategories() {
    this.categoriesLoading = true;
    this.categoriesError = false;
    try {
        const res = await fetch(`${FND_API}/categories`);
        if (!res.ok) throw new Error(res.statusText);
        this.categories = await res.json();
    } catch {
        this.categoriesError = true;
    } finally {
        this.categoriesLoading = false;
    }
},
```
- Standard four-step pattern against `GET /api/v1/foundation/categories`.

```javascript
async fetchMasterData(categoryCode) {
    this.masterDataLoading = true;
    this.masterDataError = false;
    try {
        let url = `${FND_API}/master-data`;
        if (categoryCode) url += `?category_code=${encodeURIComponent(categoryCode)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(res.statusText);
        this.masterData = await res.json();
    } catch {
        this.masterDataError = true;
    } finally {
        this.masterDataLoading = false;
    }
},
```
- Takes an optional `categoryCode` parameter. When falsy (undefined/null/empty string),
  the base URL with no query string is used, fetching **all** master data values across
  every category. When truthy, `encodeURIComponent(categoryCode)` URL-encodes it into a
  `?category_code=` query parameter, matching the FastAPI endpoint's optional
  `category_code` filter (`api/routers/foundation.py`).

```javascript
async filterByCategory() {
    await this.fetchMasterData(this.selectedCategoryCode || null);
},
```
- Bound to the filter `<select>`'s `@change`. Converts an empty-string selection (the
  "All Categories" option's `value=""`) to `null` before delegating to
  `fetchMasterData()`, so choosing "All Categories" re-fetches the unfiltered set rather
  than filtering on the literal empty string.

**System Config fetchers:**
```javascript
async fetchSettings() {
    this.settingsLoading = true;
    this.settingsError = false;
    try {
        const res = await fetch(`${FND_API}/settings`);
        if (!res.ok) throw new Error(res.statusText);
        this.settings = await res.json();
    } catch {
        this.settingsError = true;
    } finally {
        this.settingsLoading = false;
    }
},

async fetchSequences() {
    this.sequencesLoading = true;
    this.sequencesError = false;
    try {
        const res = await fetch(`${FND_API}/sequences`);
        if (!res.ok) throw new Error(res.statusText);
        this.sequences = await res.json();
    } catch {
        this.sequencesError = true;
    } finally {
        this.sequencesLoading = false;
    }
},
```
- `fetchSettings()` and `fetchSequences()` are both the same four-step pattern against
  `GET ${FND_API}/settings` and `GET ${FND_API}/sequences` respectively, no parameters,
  populating `this.settings` / `this.sequences`.

**Geographic fetchers and drill-down:**
```javascript
async fetchCountries() {
    this.countriesLoading = true;
    this.countriesError = false;
    try {
        const res = await fetch(`${FND_API}/countries`);
        if (!res.ok) throw new Error(res.statusText);
        this.countries = await res.json();
    } catch {
        this.countriesError = true;
    } finally {
        this.countriesLoading = false;
    }
},
```
- Standard pattern, no parameters — Countries is the top of the hierarchy.

```javascript
async selectCountry(country) {
    if (this.selectedCountry?.country_pk === country.country_pk) {
        this.selectedCountry = null;
        this.states = [];
        this.selectedState = null;
        this.districts = [];
        this.selectedDistrict = null;
        this.cities = [];
        this.postalCodes = [];
        return;
    }
    this.selectedCountry = country;
    this.selectedState = null;
    this.districts = [];
    this.selectedDistrict = null;
    this.cities = [];

    this.statesLoading = true;
    this.statesError = false;
    try {
        const res = await fetch(`${FND_API}/states?country_pk=${country.country_pk}`);
        if (!res.ok) throw new Error(res.statusText);
        this.states = await res.json();
    } catch {
        this.statesError = true;
    } finally {
        this.statesLoading = false;
    }

    // Also load postal codes for this country
    this.postalCodesLoading = true;
    this.postalCodesError = false;
    try {
        const res = await fetch(`${FND_API}/postal-codes?country_pk=${country.country_pk}`);
        if (!res.ok) throw new Error(res.statusText);
        this.postalCodes = await res.json();
    } catch {
        this.postalCodesError = true;
    } finally {
        this.postalCodesLoading = false;
    }
},
```
- **Toggle-off guard** (`?.` optional chaining, same reasoning as `app.js`'s
  `selectRole`): clicking the already-selected country deselects it and cascades a full
  clear of every downstream level (states, selectedState, districts, selectedDistrict,
  cities, postalCodes) — this is the "clear entire drill-down" branch.
- **Selecting a new country**: first clears everything below the country level (in case
  a deeper selection was active from a previous country), then issues **two sequential
  fetches**, one after the other (each fully awaited before the next starts, not run in
  parallel): `states?country_pk=...` and `postal-codes?country_pk=...`. Both use their
  own independent loading/error flag pairs, so the States card and the Postal Codes
  panel can show independent loading spinners even though they're triggered from the
  same click.

```javascript
async selectState(state) {
    if (this.selectedState?.state_pk === state.state_pk) {
        this.selectedState = null;
        this.districts = [];
        this.selectedDistrict = null;
        this.cities = [];
        return;
    }
    this.selectedState = state;
    this.selectedDistrict = null;
    this.cities = [];

    this.districtsLoading = true;
    this.districtsError = false;
    try {
        const res = await fetch(`${FND_API}/districts?state_pk=${state.state_pk}`);
        if (!res.ok) throw new Error(res.statusText);
        this.districts = await res.json();
    } catch {
        this.districtsError = true;
    } finally {
        this.districtsLoading = false;
    }
},
```
- Same toggle-off-and-cascade-clear / select-and-fetch-children shape one level down:
  toggling off clears districts/selectedDistrict/cities; selecting fetches
  `districts?state_pk=...`. Notably, `selectState` does **not** re-fetch postal codes —
  the Postal Codes panel stays scoped to the country level throughout the whole
  drill-down (confirmed by `foundation.html`'s panel header,
  `Postal Codes — {{selectedCountry.country_name}}`, and by the DDL/API design in which
  `PostalCodeResponse` carries state context but the UI only ever filters by country).

```javascript
async selectDistrict(district) {
    if (this.selectedDistrict?.district_pk === district.district_pk) {
        this.selectedDistrict = null;
        this.cities = [];
        return;
    }
    this.selectedDistrict = district;

    this.citiesLoading = true;
    this.citiesError = false;
    try {
        const res = await fetch(`${FND_API}/cities?district_pk=${district.district_pk}`);
        if (!res.ok) throw new Error(res.statusText);
        this.cities = await res.json();
    } catch {
        this.citiesError = true;
    } finally {
        this.citiesLoading = false;
    }
},
```
- Bottom of the drill-down chain: toggle-off clears only `cities` (nothing deeper
  exists); selecting fetches `cities?district_pk=...`. In practice this always resolves
  to `[]` at Tier 1 (no city/village seed data), which `foundation.html`'s
  `districts.length === 0` / empty-state branches account for.

**Runtime fetcher:**
```javascript
async fetchDocuments() {
    this.documentsLoading = true;
    this.documentsError = false;
    try {
        const res = await fetch(`${FND_API}/documents`);
        if (!res.ok) throw new Error(res.statusText);
        this.documents = await res.json();
    } catch {
        this.documentsError = true;
    } finally {
        this.documentsLoading = false;
    }
},
```
- Standard pattern, no parameters, against `GET ${FND_API}/documents`; called exactly
  once per page load by `loadRuntimeTab()`'s `_runtimeLoaded` guard.

**Helpers:**
```javascript
get filteredMasterData() {
    if (!this.selectedCategoryCode) return this.masterData;
    return this.masterData.filter(
        d => d.category_code === this.selectedCategoryCode
    );
},
```
- An Alpine/JS **computed getter** (accessed as a property, `filteredMasterData`, not
  called as a function) — recomputed reactively whenever `masterData` or
  `selectedCategoryCode` changes. When no category filter is set, returns the raw
  `masterData` array unmodified; otherwise returns only rows whose `category_code`
  matches. In practice this client-side filter is redundant with the server-side
  `?category_code=` filter already applied by `fetchMasterData()`/`filterByCategory()`,
  but it also protects the badge counter (`filteredMasterData.length`) and table body
  from ever transiently showing unfiltered data while a filtered fetch is in flight.

> **v2.0 (2026-09-12):** `formatSample(seq)` changed from returning a single zero-padded
> sample to a `min → max` range string, because `padding_length` now represents the maximum
> number of digits the numeric portion of an ID can grow to ("Max Digits"), not the
> zero-padding width. `id_sequence_master`'s CHECK was loosened to `BETWEEN 0 AND 12`
> (see `DATABASE_CODE_EXPLANATIONS.md`'s `04_id_sequence_master.sql` section); the default
> is 8. A single fixed-width sample like `SS1` is far less informative than seeing
> the full `SS1 → SS99999999` span. The ID Sequences table's "Padding"/"Format Sample"
> column headers became "Max Digits"/"Range" to match (see §2.3).

```javascript
formatSample(seq) {
    const max = "9".repeat(seq.padding_length);
    return `${seq.prefix}1 → ${seq.prefix}${max}`;
},
```
- Plain (non-getter, non-async) helper method, called per-row from the ID Sequences
  table's "Range" column (`x-text="formatSample(seq)"`). Builds a `min → max` range string
  by repeating the literal character `"9"` `seq.padding_length` times to get the widest
  possible value for that many digits, then formatting `${prefix}1 → ${prefix}${max}`.
  For example, `prefix: "SS"`, `padding_length: 8` → `"SS1 → SS99999999"`;
  `prefix: "PS"`, `padding_length: 3` → `"PS1 → PS999"`. It deliberately uses the
  constant `"9"` (for the max) and `"1"` (for the min), never `seq.current_value` — the
  API's `SequenceResponse` never includes `current_value` in the first place (excluded at
  the schema layer as infrastructure state), so this helper has no such field available
  even if it wanted to use it; it exists purely to preview the *range*, not to predict or
  display the next real ID that will be issued.

---

### 2.5 `frontend/assets/css/style.css`

**Requirement.** Tailwind and DaisyUI (now a single same-origin, pre-built stylesheet —
`/assets/css/tailwind.min.css`, see §2.1 — rather than CDN-delivered) supply essentially
all visual styling via utility classes and components; this file exists only to hold the
one rule that **cannot** be expressed as a Tailwind utility class because it targets a
framework-specific attribute (`x-cloak`) that Tailwind doesn't know about. It is the
smallest file in the frontend layer, shared unmodified by both `index.html` and
`foundation.html`.

**Full file, 10 lines:**
```css
/*
 * NSS ERP — Tier 0 minimal custom styles.
 * Tailwind/DaisyUI handle the heavy lifting via CDN.
 * This file is for project-specific overrides only.
 */

/* Keep the body from showing unstyled content before Alpine initialises */
[x-cloak] {
    display: none !important;
}
```
- The header comment states the file's scope and intent directly. **Note:** as of the
  Tailwind Play CDN → pre-built `tailwind.min.css` switch (see §2.1), this comment's
  wording ("via CDN") is stale in the actual file — it was not updated when the build
  pipeline changed — but is transcribed here verbatim per this document's byte-for-byte
  quoting convention (line 41–42 above).
- **The one rule** — an attribute selector, `[x-cloak]`, matching any element carrying
  the `x-cloak` attribute (used in `foundation.html`'s four tab panels; see §2.3) — sets
  `display: none !important;`.
- **Why this is needed at all:** Alpine.js only removes the `x-cloak` attribute from an
  element *after* it has finished evaluating that element's directives on initial page
  load. Until that removal happens, the browser would otherwise render the element in
  its default (visible) state — which, for an element whose visibility is meant to be
  controlled by `x-show="activeTab === '...'"`, would mean every tab panel flashing
  visible simultaneously for one rendering frame before Alpine hides the non-active
  three. This CSS rule pre-emptively hides any `[x-cloak]` element via a plain
  browser-native CSS selector (no JavaScript required, so it applies even before
  Alpine's script has finished downloading/parsing/executing), and Alpine's own runtime
  then strips the `x-cloak` attribute once it has taken over, letting the rule stop
  applying and `x-show`'s own inline-style toggling take over cleanly.
- `!important` ensures this rule outranks any Tailwind utility class (e.g. a stray
  `block` or `grid` class) that might otherwise force the element visible before Alpine
  attaches.
- `index.html` loads this same stylesheet but has no `x-cloak` attributes anywhere in
  its markup (its conditional sections all use `<template x-if>`, which Alpine never
  inserts into the live DOM until true, so there is nothing to flash) — the rule is
  simply inert, harmless dead weight on that page.

---

## 2.10 `frontend/membership.html`

**Requirement.** The Membership Verification page — Tier 4 — displaying all NSS
members with their three-tier identity (Sangha Sevi ID, Sakha Sangha ID, Kendra
Number), credentials (Parichaya Patra, Anumati Patra), Sakha affiliations, and
journey timeline. Two tabs: Members (list + detail) and Search (trigram + prefix).

**Layout:** Same responsive grid pattern as `person.html` — `xl:grid-cols-3` with
list/results taking 2 columns, detail panel taking 1.

**`<head>` note:** loads `/assets/css/badges.css` and `/assets/js/nss-config.js` (shared
across all six tier pages — see §2.14–§2.15) in place of the page-local `.badge-status-*`/
`.badge-type-*`/`.badge-aff-*` `<style>` block described in earlier revisions of this
document; `typeDisplayName()`/`typeBadgeClass()`/`statusBadgeClass()`/`affBadgeClass()`/
`docBadgeClass()` in `membership.js` (§2.11) now delegate to `NSS.*` helpers instead of
hardcoding their own class maps.

**Three-Tier Identity Legend:** A compact card between the system status and tabs
displays the three identity tiers with examples (SS1, ESS1192, 345/2026/2027).

**UI Label Convention:** The Tier 2 identity (stored as `local_sakha_erp_id` in the
database) is labeled **"Sakha Sangha ID"** in all UI contexts — table headers,
detail panels, and Parichaya Patra snapshots. Documentation may refer to the
concept as "Local Sakha ERP Number" or "ERP Number"; the UI consistently uses
"Sakha Sangha ID".

**Tab 1 — Members:** Member list table with 11 columns: Sangha Sevi ID, Person ID,
Person, Mobile, Email, Type, Status, Sakha, Sakha Sangha ID, Joining Date, Renewal
Due. Filters for membership type (Regular / Darshaka / Associate / Honorary) and
status. Detail panel shows:

- **Identity section:** Sangha Sevi ID, Sakha Sangha ID, Person ID, Name, Mobile,
  Email, Type (badge with `typeDisplayName()` — PROBATIONARY displays as
  "Darshaka"), Status, Sakha, Joining Date, Renewal Due.
- **Sakha Affiliations:** Effective-dated history with Local Sakha ERP ID, Sakha
  name, affiliation status badge, and source event type.
- **Parichaya Patra:** Kendra Number, issue date, validity period, affiliated Sakha
  snapshot, Sakha Sangha ID snapshot at time of issuance.
- **Anumati Patra:** Conditionally hidden for Associate members:
  ```html
  <div x-show="selectedMember.membership_type_code !== 'ASSOCIATE'">
  ```
  Associate members do not receive an Anumati Patra (Probationary-only credential).
  Regular members may have EXPIRED historical AP records from their probationary
  period.
- **Journey Timeline:** Chronological events (MEMBERSHIP_CREATED,
  PROBATIONARY_STARTED, REGULAR_ENROLMENT, etc.) rendered as DaisyUI vertical steps.

**Tab 2 — Search:** Same inline-detail grid pattern as Person's search tab.
Search input placeholder: `"ID, Name, Mobile, Email, or Kendra # (min 2 chars)"`.
Searches across all 3 identity tiers plus name, contact, and Kendra Number (7
search fields — see `API_CONTRACT.md` search fields table). Clicking a result
calls `selectMember(m)` directly — detail loads inline without tab switch.

**Auto-select single result:** Both `executeSearch()` (search tab) and
`filterMembers()` (members tab) auto-call `selectMember()` when exactly one result
is returned, same pattern as person.js.

---

## 2.11 `frontend/assets/js/membership.js`

**Requirement.** Client-side state/behaviour for `membership.html`. Defines one
global factory function `membershipApp()`. Consumes 7 membership API endpoints.

**Key behavioral patterns:**

- **`selectMember()`:** Fetches member detail plus all sub-resources (affiliations,
  Parichaya Patra, Anumati Patra, journey events) via `Promise.all`. Toggle-off on
  re-click (same as person.js/organization.js).
- **`typeDisplayName()`:** Returns `"Darshaka"` for `PROBATIONARY` membership type
  (MBR-007); all other types display their `membership_type_name` as-is.
- **`typeBadgeClass()`:** Color-coded badges per type: Regular (blue), Probationary
  (amber), Associate (purple), Honorary (green).
- **Debounced search:** 300ms debounce on `executeSearch()`, same pattern as person.js.
- **`formatName()`:** Same implementation as person.js (joins first/middle/last,
  drops falsy parts).

---

## 2.12 `frontend/family.html`

**Requirement.** The Tier 4 "Family Verification UI" — visual proof that the now-7 read-only
`/api/v1/family/*` endpoints correctly expose `family_group`, `family_relationship`, and
`family_head_history` (joined against Foundation's `master_data` and Organization/Person), plus
three newer endpoints layered on top: `/graph` (dynamic per-viewer relationship computation),
`/sakha-alignment` (FAM-036 majority-rule effective Sakha), and `/person/{pk}/membership-summary`
(family-to-membership bridge). Structurally still parallel to `person.html` in its head
boilerplate and mobile-first padding scale, but the body has been rebuilt from the original
two-column list+detail grid into a **3-panel layout** (left sidebar / center tree / right detail)
plus a second top-level view mode. Served by FastAPI's `GET /family` route, conditional on the
file existing on disk.

**Section-by-section walkthrough:**

**`<head>`:** Same asset dependency block as the other tier pages (same-origin, pre-built
`/assets/css/tailwind.min.css` — Tailwind 3.x + DaisyUI 4, no SRI needed — plus Alpine.js
3.14.8 with SRI, local `style.css`), plus `/assets/css/badges.css` and
`/assets/js/nss-config.js` (see §2.14–§2.15) — the old two-class page-local
`.badge-status-active`/`.badge-status-inactive` block has been fully replaced by shared classes.
The page-local `<style>` block is now much larger than before: alongside CSS custom properties for
text colors (`--nss-text-primary`/`-secondary`/`-muted`/`-accent`) and the tree's connector color
(`--conn-color`), it defines every class the new center-panel tree and right-panel detail card
need — `.tree-canvas`/`.tree-container`/`.tree-node`/`.node-avatar`/`.node-name`/`.node-role`
(the tree infographic), `.conn-v`/`.conn-h`/`.bracket-wrap`/`.bracket-row`/`.couple-group`/
`.couple-join-line` (the connector-line geometry), `.av-viewer`/`.av-spouse`/`.av-parent`/
`.av-grandparent`/`.av-child`/`.av-grandchild`/`.av-sibling`/`.av-other` (per-generation avatar
gradients), `.node-indicator`/`.indicator-viewer`/`.indicator-head` (the eye/star corner badges),
`.gen-divider`/`.gen-divider-line`/`.gen-divider-text` (generation-band labels), and
`.detail-card`/`.detail-section`/`.detail-label`/`.spouse-card` (right-panel Selected Person
layout). `NSS.genderBadgeClass()`/`NSS.typeBadgeClass()`/`NSS.statusBadgeClass()`/
`NSS.showAnumatiPatra()` from `nss-config.js` are used inside the Selected Person panel's
membership snapshot, alongside the shared `.data-label`/`.data-sevi-id`/`.data-erp-no`/
`.data-kendra-no`/`.data-sakha-name`/`.data-family-id`/`.badge-role-viewer`/`.badge-role-head`/
`.badge-marital` classes from `badges.css`.

**Root component and header:** `<div x-data="familyApp()" x-init="init()" ...>` calls
`familyApp()` (§2.13). The nav bar still carries the same six links — Bootstrap, Foundation,
Organization, Person, Family, Membership — with Family styled `btn-active`, unchanged from the
prior version of this page.

**System Status:** Same connected/checking/unavailable `x-if` triad as every other tier page,
bound to `familyApp().health`, now rendered as a small pill rather than a full status card.

**Main content — 3-panel grid** (`grid-cols-1 lg:grid-cols-[220px_1fr] xl:grid-cols-[220px_1fr_360px]`
— sidebar / tree / detail, the detail panel collapsing off-screen below `xl`):

**LEFT — Navigation & Family List panel.** New in this revision: a **view-mode toggle** (`My
Family` / `Org View`) drives `viewMode`, switched via `switchViewMode('member'|'admin')` (§2.13).
In `admin` mode the panel shows an org-hierarchy breadcrumb (`orgBreadcrumb`, navigated via
`breadcrumbNav(i)`) and a drill-down list of child organizations (`orgChildren`, entered via
`drillIntoOrg(org)`) sourced from `/api/v1/organization/organizations/{pk}/children` plus
per-child family/member/person counts from `/api/v1/organization/organizations/{pk}/children-stats`
(rendered via `getOrgStats(orgPk)`); drilling into a `SAKHA_SANGHA`-type org switches to a
sakha-filtered family list (`fetchFamilies(sakhaCode)`) instead of drilling further. This
Kendra→Anchalika/Zilla→Sakha→Families navigation path is a genuinely separate feature from the
three items below and is only summarized here — it consumes Organization's `/children` and
`/children-stats` endpoints, not any of the three new Family endpoints this pass is documenting.
In `member` mode (the default-equivalent path used by every test in this file) the panel simply
lists families as before, each row now a card (`.family-item`) rather than a table row, still
calling `selectFamily(f)` on click.

**CENTER — Family Tree panel (new).** Replaces the old "select a family to see detail" text with
an always-visible tree canvas once a family is selected. Immediately below the panel header, a
**"View as" selector** lets the user pick any current family member as the traversal viewer:

```html
<select class="select select-xs select-bordered flex-1 bg-white"
        :value="viewerPersonPk"
        @change="changeViewer($event.target.value)">
    <template x-for="m in familyMembers" :key="m.person_pk">
        <option :value="m.person_pk"
                :selected="m.person_pk === viewerPersonPk"
                x-text="formatName(m) + (m.is_head ? ' ★ HEAD' : '')">
        </option>
    </template>
</select>
```

Changing the selector calls `changeViewer(personPk)` (§2.13), which re-fetches
`GET /api/v1/family/families/{pk}/graph?viewer_person_pk=...` and rebuilds the tree — this is the
UI's direct exercise of the new `/graph` endpoint's whole reason for existing: relabeling every
member relative to whoever is picked, with zero server-side data re-entry. Below the selector, one
of four mutually exclusive states renders: the pre-selection empty state, a loading spinner
(`detailLoading`), a `graphError` message ("Failed to compute family graph"), or the tree itself —
`<div class="tree-container" @click="handleTreeClick($event)" x-html="renderTree()"></div>`. The
tree is rendered via `x-html` from a string built entirely in JS (`renderTree()`/
`_renderSubtree()`/`_renderCouple()`/`_renderPerson()`, §2.13) rather than native Alpine
`x-for`/`x-if` directives — the only place in the whole frontend that builds markup as a string
instead of declaratively, because the tree's shape (arbitrary depth, sibling brackets, couple
grouping) isn't expressible as a fixed template. Clicks are handled by a single delegated listener
(`handleTreeClick`) on the container rather than one handler per rendered node, since the nodes
themselves are raw HTML strings with no Alpine bindings. Each person renders as a `.tree-node` with
a colored `.node-avatar` (color keyed to generation via `avatarClass()`), two-letter initials, a
viewer/head corner indicator (👁 / ★), a name, and the computed `relationship_label`. Couples
(spouse pairs) render inside a shared `.couple-group` box joined by `.couple-join-line`; sibling
couples at the same generation render inside a `.bracket-row` with a horizontal `.conn-h` bar and
per-item `::before` drop connectors; each generation band is preceded by a `.gen-divider` label
(`Parents`/`Self & Siblings`/`Children`/etc., from the `GEN_LABELS` map, falling back to
"Ancestors (N)"/"Descendants (N)" for anything beyond ±3 generations).

**RIGHT — Detail panel.** Three top-level sections, all still gated on `selectedFamily`:

- **Family Info** — the same Identity fields as before (ID, Status, Name, Sakha, Formed date),
  now styled with the shared `.data-label`/`.data-family-id`/`.data-sakha-name` classes instead of
  inline `text-base-content/50` utility classes.
- **Selected Person** (new) — appears only `x-if="selectedPerson"`, populated by clicking any tree
  node (via `handleTreeClick`) or any row in the Members list below. Header: avatar + name +
  `person_id` + a badge row (`YOU`/`HEAD`/`Active`/`Inactive`, the first two via the shared
  `.badge-role-viewer`/`.badge-role-head` classes), then a relationship pill showing
  `displayRelationship(selectedPerson)`. Below that, once `GET /api/v1/person/persons/{pk}` and
  `GET /api/v1/family/person/{pk}/membership-summary` both resolve (fired in parallel by
  `selectPerson()`, §2.13):
  - Person fields (DOB, gender badge via `NSS.genderBadgeClass()`, marital-status badge via the
    shared `.badge-marital` class, blood group, mobile, email, masked Aadhaar last-4) — the same
    fields `person.html`'s detail panel shows, now reused here rather than duplicated markup.
  - A clickable **Spouse mini-card** (`.spouse-card`), shown only if `getSpouseName()` resolves one
    from the graph — clicking it calls `selectSpouse()` to jump the panel to the spouse.
  - A **Sangha Membership** block — this is the UI's direct consumption of
    `/person/{pk}/membership-summary`: Sangha Sevi ID (`.data-sevi-id`), membership type/status
    badges (`NSS.typeBadgeClass()`/`NSS.statusBadgeClass()`), the person's current Sakha
    (`.data-sakha-name`) with an amber "⚠ Different" badge when
    `isMemberSakhaMismatch(selectedPerson.person_pk)` is true (cross-referencing the
    `/sakha-alignment` response — see below), and the local Sakha Sangha ERP ID
    (`.data-erp-no`). Falls back to "No record found" when `membership_summary.sangha_sevi_id` is
    empty (the endpoint's own no-membership shape).
  - **Parichaya Patra** (`.data-kendra-no`) and, gated on `NSS.showAnumatiPatra(membership_type_code)`
    (MBR-019A/B — Associate members are excluded), **Anumati Patra** blocks, each with a
    status badge and a "Valid to" date when present.
  - An Emergency Contact block when the person detail carries one.
  - If the person-detail fetch is still pending or the person has no graph/membership data yet, a
    fallback shows just `effective_from`/`is_current` from the raw member row.
- **Members** — now a compact clickable list (`selectPerson(m)` per row) rather than a table, each
  row showing the member's name, `YOU`/`HEAD` badges, an amber Sakha-mismatch warning icon (again
  via `isMemberSakhaMismatch()`), and a relationship label resolved with a graph-first fallback
  chain (`graphMembers.find(...)?.relationship_label || displayRelationship(m)`).
- **Head History** — the same bordered-card-per-row presentation as before (`Now` badge when
  `effective_to` is falsy), just restyled to match the new panel's flat-list look.

**Footer and script include:** Same copyright footer, cache-busted script tag
(`<script src="/assets/js/family.js?v=23"></script>`) — the `?v=23` query string is a manual
cache-buster incremented as the file has grown across revisions, not present on any other tier
page's script tag.

---

## 2.13 `frontend/assets/js/family.js`

**Requirement.** The client-side state/behaviour layer for `family.html`. Originally mirrored
`person.js`'s role scoped to Family's 4 original read-only endpoints with no tab state; now much
larger (~740 lines added), adding: dynamic-relationship graph fetching + a recursive tree builder,
a Sakha-alignment mismatch lookup, a Selected-Person detail fetch (bridging into Person and the
new membership-summary endpoint), and a separate org-hierarchy browsing mode. Still one global
factory function, `familyApp()`.

**State — new groups added on top of the original four (families/detail/members/headHistory,
unchanged from before):**

```js
viewMode: "admin",
orgBreadcrumb: [], orgChildren: [], orgChildrenLoading: false,
orgChildrenStats: {}, selectedSakhaCode: null,

viewerPersonPk: null, graphMembers: [], graphLoading: false, graphError: false,

selectedPerson: null, selectedPersonDetail: null, selectedPersonLoading: false,
selectedPersonMembership: null, selectedPersonMembershipLoading: false,

sakhaAlignment: null, sakhaAlignmentLoading: false,

treeHead: null, treeSpouse: null, treeNodes: [], _allTreePersons: [],
```

Five new state groups: org-hierarchy navigation (admin view — out of scope for this pass, see
`ORGANIZATION_API_CONTRACT.md`), the graph/viewer state, the selected-person detail state, the
Sakha-alignment state, and the rebuilt-tree state. Notably `viewMode` defaults to `"admin"`, not
`"member"` — the org-drill-down view is the page's landing state, not the direct family view.

```js
async init() {
    // Fire health check in parallel — don't block data loading
    this.fetchHealth();
    if (this.viewMode === "admin") {
        await this.fetchOrgRoot();
    } else {
        await this.fetchFamilies();
    }
},
```

`init()` now branches on `viewMode` — since it defaults to `"admin"`, a fresh page load fetches
the Kendra root org and its children (`fetchOrgRoot()`) rather than the flat family list.
`fetchHealth()` is fire-and-forget here (no `await`) — it only updates a status indicator, so it
no longer blocks the org/family fetch from starting (v0.10.4; see `PERFORMANCE_TUNING.md`).

**`selectFamily()` — extended, not replaced:**

```js
async selectFamily(family) {
    ...
    try {
        const [membersRes, headRes] = await Promise.all([
            fetch(`${FAMILY_API}/families/${family.family_group_pk}/members`),
            fetch(`${FAMILY_API}/families/${family.family_group_pk}/head-history`),
        ]);

        // Sakha alignment — fire-and-forget (non-blocking)
        this.fetchSakhaAlignment(family.family_group_pk);

        if (membersRes.ok) this.familyMembers = await membersRes.json();
        if (headRes.ok) this.headHistory = await headRes.json();

        // Auto-select the HEAD as default viewer
        const head = this.familyMembers.find(m => m.is_head);
        if (head) {
            this.viewerPersonPk = head.person_pk;
            await this.fetchGraph();
        } else if (this.familyMembers.length > 0) {
            this.viewerPersonPk = this.familyMembers[0].person_pk;
            await this.fetchGraph();
        }
    } catch { /* Non-fatal */ } finally { this.detailLoading = false; }
},
```

Same toggle-deselect-on-re-click / members+head-history-in-parallel / swallow-fetch-errors
structure as the original version (see prior revisions of this section for that base
behaviour — unchanged), plus two new side effects on a genuine selection: `fetchSakhaAlignment()`
is fired without being awaited (a deliberate "fire-and-forget" — alignment is informational and
must not block the members/head-history render), and the family's current **head** (or, absent a
head, its first member) is auto-picked as the default graph viewer, immediately triggering
`fetchGraph()`.

```js
async fetchGraph() {
    if (!this.selectedFamily || !this.viewerPersonPk) return;
    this.graphLoading = true;
    this.graphError = false;
    try {
        const url = `${FAMILY_API}/families/${this.selectedFamily.family_group_pk}/graph?viewer_person_pk=${this.viewerPersonPk}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(res.statusText);
        this.graphMembers = await res.json();
        this.buildTree();
    } catch {
        this.graphError = true;
    } finally {
        this.graphLoading = false;
    }
},

async changeViewer(personPk) {
    this.viewerPersonPk = personPk;
    this.selectedPerson = null;
    this.selectedPersonDetail = null;
    this.selectedPersonMembership = null;
    await this.fetchGraph();
},
```

`fetchGraph()` is the UI's direct call into the new `GET /families/{pk}/graph?viewer_person_pk=`
endpoint — standard loading/error try-fetch-catch-finally shape, but on success it immediately
calls `buildTree()` (below) rather than just storing the raw response, since the raw
`FamilyGraphMemberResponse[]` list has no parent/child nesting of its own. `changeViewer()` is the
"View as" `<select>`'s `@change` handler (§2.12) — clearing any previously selected person (their
relationship label would be stale relative to the new viewer) before re-fetching.

```js
buildTree() {
    const members = this.graphMembers;
    ...
    // 1. Synthesize the viewer node (not in graph response)
    // 2. Infer viewer's parent PKs from graph labels (Father/Mother/Step-Father/Step-Mother)
    // 3. Combine viewer + graph members into allPersons
    // 4. Group into couples via spouse_person_pk (falls back to a reverse scan
    //    when the API's spouse_person_pk points the "wrong" direction)
    // 5. Build a parent-couple → [child couples] map via parent_person_pks
    // 6. Couples with no parent couple found become rootCouples
    // 7. attach(node) recursively assigns each couple's children array
    this.treeNodes = rootCouples;
},
```

The most substantial new method. The `/graph` endpoint's response never includes the viewer
themself (the whole point of the endpoint is to compute labels *relative to* the viewer, so the
viewer has no label relative to themself) — `buildTree()` first synthesizes a `treeHead` node for
the viewer (label hardcoded to `"You (Viewer)"`), inferring their parent PKs by scanning the graph
response for anyone labeled Father/Mother/Step-Father/Step-Mother (there is no `parent_person_pks`
field for the viewer since they're not a row in the response). It then groups every person (viewer
included) into couples by matching `spouse_person_pk` pairs, and links couples into a tree by
matching each couple's `parent_person_pks` against a `person_pk → couple` map built during the
grouping pass — a couple with no resolvable parent couple becomes a tree root (this correctly
places a "married-in" spouse, who has no `parent_person_pks` of their own, under their spouse's
parents rather than as an orphan root). `attach()` is a local recursive closure, not a method on
`this`, since it only needs the `childCouplesOf` map from its enclosing closure.

```js
renderTree() {
    if (!this.treeNodes?.length) return "";
    return this._renderSubtree(this.treeNodes, true);
},
_renderSubtree(nodes, isRoot) { ... },
_renderCouple(node) { ... },
_renderPerson(m) { ... },
_esc(s) {
    if (!s) return "";
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;")
            .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
},
handleTreeClick(event) {
    const el = event.target.closest("[data-person-pk]");
    if (!el) return;
    const pk = el.dataset.personPk;
    const member = this._allTreePersons?.find(m => m.person_pk === pk);
    if (member) this.selectPerson(member);
},
```

`renderTree()`/`_renderSubtree()`/`_renderCouple()`/`_renderPerson()` recursively build the tree's
HTML as a plain string, consumed by `family.html`'s `x-html="renderTree()"` (§2.12) — the one place
in the frontend that hand-assembles markup rather than using Alpine directives, because a tree of
arbitrary, data-driven depth isn't expressible as a fixed `x-for` template.
`_renderSubtree()` recurses per generation band (emitting a `.gen-divider` label first, then either
a single `.gen-row` or a bracketed `.bracket-row` for multiple sibling couples, then recursing into
each node's `.children`); `_renderCouple()` wraps two `_renderPerson()` calls in a `.couple-group`
when the node has a spouse, otherwise renders the single person directly; `_renderPerson()` emits
one `.tree-node data-person-pk="..."` div per person, with `_esc()` HTML-escaping every
user-supplied string (name, relationship label) before interpolation — the only manual XSS
escaping anywhere in the frontend, required specifically because this content bypasses Alpine's
normally-auto-escaping `x-text` bindings. `handleTreeClick()` is the single delegated listener
bound once on the tree container (§2.12): it walks up from the click target to the nearest
`[data-person-pk]` ancestor, looks the PK up in the flat `_allTreePersons` array (built in
`buildTree()`), and forwards to `selectPerson()`.

```js
async fetchSakhaAlignment(familyGroupPk) {
    this.sakhaAlignmentLoading = true;
    try {
        const res = await fetch(`${FAMILY_API}/families/${familyGroupPk}/sakha-alignment`);
        if (res.ok) this.sakhaAlignment = await res.json();
    } catch {
        // Non-fatal — alignment is informational
    } finally {
        this.sakhaAlignmentLoading = false;
    }
},

isMemberSakhaMismatch(personPk) {
    if (!this.sakhaAlignment?.members) return false;
    const m = this.sakhaAlignment.members.find(x => x.person_pk === personPk);
    return m?.has_membership && m?.is_home_sakha === false;
},

getMemberSakhaName(personPk) {
    if (!this.sakhaAlignment?.members) return null;
    const m = this.sakhaAlignment.members.find(x => x.person_pk === personPk);
    return m?.affiliated_sakha_name || null;
},
```

The UI's entire consumption of the new `/sakha-alignment` endpoint: `fetchSakhaAlignment()` (fired
non-blocking from `selectFamily()`, above) stores the full `FamilySakhaAlignmentResponse`, and
`isMemberSakhaMismatch()`/`getMemberSakhaName()` are pure lookup helpers over its `members[]`
array, called from both the Members list and the Selected Person panel (§2.12) to render the amber
"⚠ Different" warning. `isMemberSakhaMismatch()` deliberately checks `has_membership` first —
a member with no active `sangha_sevi` affiliation at all has `is_home_sakha: null`, which must
read as "not a mismatch" (no data to be mismatched), not as a false "aligned".

```js
async selectPerson(member) {
    if (this.selectedPerson?.person_pk === member.person_pk) {
        this.selectedPerson = null; // toggle off
        this.selectedPersonDetail = null;
        this.selectedPersonMembership = null;
        return;
    }
    this.selectedPerson = member;
    this.selectedPersonDetail = null;
    this.selectedPersonLoading = true;
    this.selectedPersonMembership = null;
    this.selectedPersonMembershipLoading = true;

    const personFetch = fetch(`/api/v1/person/persons/${member.person_pk}`)
        .then(r => r.ok ? r.json() : null).catch(() => null);
    const membershipFetch = fetch(`${FAMILY_API}/person/${member.person_pk}/membership-summary`)
        .then(r => r.ok ? r.json() : null).catch(() => null);

    const [personData, membershipData] = await Promise.all([personFetch, membershipFetch]);
    this.selectedPersonDetail = personData;
    this.selectedPersonLoading = false;
    this.selectedPersonMembership = membershipData;
    this.selectedPersonMembershipLoading = false;
},
```

The Selected Person panel's data loader — toggle-deselect on re-click of the same person (same
pattern as `selectFamily()`), then two independent fetches issued in parallel via `Promise.all`:
`GET /api/v1/person/persons/{pk}` (an existing Tier 3 endpoint, reused here rather than
duplicated) and `GET /api/v1/family/person/{pk}/membership-summary` (the third new endpoint this
pass documents). Both fetches use an inline `.then(r => r.ok ? r.json() : null).catch(() => null)`
chain instead of the file's usual try/catch-around-await style — a non-fatal-by-construction
shape where either request failing simply leaves its half of the panel showing "no data" rather
than blocking the other half or the person's own header fields.

**Helpers — new/changed:**

```js
formatName(m) {
    return [m.first_name, m.middle_name, m.last_name].filter(Boolean).join(" ");
},
```

Renamed from the original `formatMemberName()` to `formatName()` (matching `person.js`'s
convention) — same first/middle/last, drop-falsy, join-with-space implementation as before.

```js
displayRelationship(m) {
    if (m._isViewer) return "You (Viewer)";
    if (m.relationship_label) return m.relationship_label;
    if (m.person_pk === this.viewerPersonPk) return "You (Viewer)";
    const graphMember = this.graphMembers.find(g => g.person_pk === m.person_pk);
    if (graphMember?.relationship_label) return graphMember.relationship_label;
    if (m.is_head) return "Head of Family";
    return m.relationship_type_name || m.relationship_type_code || "—";
},
```

A five-way fallback chain, needed because the same person can be displayed from three different
data sources with different shapes (a raw tree node already carrying `relationship_label`, a
`familyMembers` row that only has the old static `relationship_type_name`/`_code`, or the viewer
who has neither) — it prefers the dynamic graph-computed label wherever available and only falls
back to the static `RELATIONSHIP_TYPE` master-data name as a last resort.

`getInitials()`, `getAvatarClass()`, `getViewerName()`, `getSpouseName()`, `getSpousePersonPk()`,
`getSpouseInitials()`, and `selectSpouse()` are small, single-purpose lookup/formatting helpers
supporting the tree and Selected Person panel — respectively: two-letter initials for an avatar
circle; resolving a `._avatarClass` (falling back to a graph lookup, then `"av-other"`); the
current viewer's display name; a person's spouse's name/PK/initials (checked first via the graph
response, then via the synthesized `treeSpouse` for the viewer themself); and jumping the Selected
Person panel to a person's spouse when their mini-card is clicked.

```js
_resetDetail() {
    this.familyMembers = []; this.headHistory = [];
    this.graphMembers = []; this.viewerPersonPk = null;
    this.selectedPerson = null; this.selectedPersonDetail = null;
    this.selectedPersonLoading = false;
    this.selectedPersonMembership = null; this.selectedPersonMembershipLoading = false;
    this.sakhaAlignment = null; this.sakhaAlignmentLoading = false;
    this.graphError = false;
    this.treeHead = null; this.treeSpouse = null;
    this.treeNodes = []; this._allTreePersons = [];
},
```

A new centralizing reset helper — every place that used to hand-clear `familyMembers`/
`headHistory` inline (toggle-deselect in `selectFamily()`, switching families, switching view
mode) now calls this one method, so the much larger set of graph/person/alignment/tree state
introduced in this revision can't be forgotten in any one of those call sites.

**Org-hierarchy navigation** (`fetchOrgRoot()`, `fetchOrgChildren()`, `getOrgStats()`,
`drillIntoOrg()`, `breadcrumbNav()`, `switchViewMode()`) is a separate feature added alongside the
three Family endpoints above — it consumes Organization's `/organizations?type_code=`,
`/organizations/{pk}/children`, and `/organizations/{pk}/children-stats` endpoints, not any new
Family endpoint, and is out of scope for this pass; see `ORGANIZATION_API_CONTRACT.md` for that
endpoint's contract.

**Update (v0.10.4, performance-hardening release):** `fetchOrgChildren(orgPk)` no
longer awaits both the children list and the stats query together. It now fetches and renders
`orgChildren` immediately, then kicks off a new `_fetchOrgChildrenStats(orgPk)` method
separately (not awaited) to populate `orgChildrenStats` once the heavier recursive
`/children-stats` CTE resolves. A failure in `_fetchOrgChildrenStats()` is treated as non-fatal
("stats are supplementary") and no longer clears `orgChildren`. See
`docs/03_Solution/architecture/PERFORMANCE_TUNING.md` §2.2.

---

## 2.14 `frontend/assets/js/nss-config.js`

**Requirement.** As the tier pages multiplied (six by Tier 4), each page's own JS file had grown
its own copy of the same three things: a `PROBATIONARY` → "Darshaka" display-name override
(MBR-007), a `value_code` → CSS-class lookup per badge family (lifecycle status, membership
type, affiliation status, gender), and the MBR-019A/B rule for which membership types receive an
Anumati Patra. `membership.js`'s `typeBadgeClass()`/`statusBadgeClass()`/`affBadgeClass()`/
`docBadgeClass()`/`typeDisplayName()` (§2.11) and `family.js`'s Anumati-Patra visibility check in
`family.html` (§2.12) were the two clearest duplicate-logic offenders. This file factors all of
it into one global object, `NSS`, loaded by every one of the six tier pages immediately before
their own page-specific script, so page JS calls `NSS.typeBadgeClass(code)` etc. instead of
re-deriving the mapping.

**Full file, 150 lines. Walkthrough:**

```javascript
const NSS = {
    TYPE_DISPLAY_NAMES: {
        PROBATIONARY: "Darshaka",
    },
```
- A single global `const NSS = { ... }` object literal — no factory function, no Alpine
  `x-data` registration; this is plain shared state/logic, not a reactive component. Every
  property and method below is accessed as `NSS.propertyName`/`NSS.methodName()` from any
  page's inline `x-text`/`:class` bindings or from its `*.js` file.
- `TYPE_DISPLAY_NAMES` holds only the one Bye-Law display-name override the codebase currently
  needs: `PROBATIONARY` → `"Darshaka"`. The design rule (stated in the file's header comment) is
  that `value_code` is the stable DB key and `master_data.value_name` is the default display
  name — this map is consulted only as an override, not a full replacement lookup table, so
  `REGULAR`/`ASSOCIATE`/`HONORARY` are deliberately absent (their DB `value_name` is used as-is).

```javascript
typeDisplayName(code, dbName) {
    return this.TYPE_DISPLAY_NAMES[code] || dbName || code;
},
```
- Three-way fallback: the Bye-Law override first, then whatever `value_name` the API already
  resolved server-side, then the raw `value_code` itself as a last-resort non-blank string (so a
  brand-new membership type added to the DB before this map is updated still renders *something*
  readable rather than `undefined`).

```javascript
STATUS_BADGE_MAP: { ACTIVE: "badge-status-active", /* ...18 entries... */ },
TYPE_BADGE_MAP: { PROBATIONARY: "badge-type-probationary", /* ...4 entries... */ },
AFF_BADGE_MAP: { ACTIVE: "badge-aff-active", /* ...3 entries... */ },
GENDER_BADGE_MAP: { MALE: "badge-gender-male", /* ...3 entries... */ },
```
- Four `value_code`/`status`/`affiliation_status` → CSS-class lookup tables, one per badge
  family. `STATUS_BADGE_MAP`'s 18 entries are the full unified `STATUS` category superset (every
  status value seen across Organization/Membership/Family, not just the subset any one page
  currently renders) — every class it maps to is defined in `badges.css` (§2.15).

```javascript
statusBadgeClass(code) {
    return this.STATUS_BADGE_MAP[code] || "badge-ghost";
},
typeBadgeClass(code) {
    return this.TYPE_BADGE_MAP[code] || "badge-ghost";
},
affBadgeClass(status) {
    return this.AFF_BADGE_MAP[status] || "badge-ghost";
},
genderBadgeClass(code) {
    return this.GENDER_BADGE_MAP[code] || "badge-ghost";
},
```
- Four near-identical lookup methods, each falling back to DaisyUI's neutral `badge-ghost` class
  for any code not present in its map — the same "unknown code degrades to a generic grey badge
  rather than throwing" convention every tier page's inline JS used before extraction (e.g. the
  pre-extraction `membership.js` versions of these methods, quoted in §2.11's git history, ended
  every `if`/`else` chain with `return "badge-ghost"`).

```javascript
showParichayaPatra(typeCode) {
    return true; // All membership types receive Parichaya Patra
},
showAnumatiPatra(typeCode) {
    return typeCode !== "ASSOCIATE";
},
```
- Document-visibility rules, authority NSS Bye-Law §B, MBR-019A/B. `showParichayaPatra()` always
  returns `true` (kept as a named method — not just a hardcoded `x-show="true"` in markup — so
  the rule has one documented, greppable home even though it doesn't currently vary by type).
  `showAnumatiPatra()` is the one rule that does vary: every membership type except `ASSOCIATE`
  receives an Anumati Patra. `membership.html` and `family.html` both call
  `NSS.showAnumatiPatra(selectedMember.membership_type_code)` in an `x-show` directly, replacing
  each page's previous local `x-show="selectedMember.membership_type_code !== 'ASSOCIATE'"`
  inline expression — the same boolean, now expressed once instead of copy-pasted per page.

---

## 2.15 `frontend/assets/css/badges.css`

**Requirement.** Companion file to `nss-config.js` (§2.14): every CSS class its lookup maps
resolve to (`badge-status-*`, `badge-type-*`, `badge-aff-*`, `badge-gender-*`) needs to actually
exist somewhere, exactly once. Before this file existed, each of the six tier pages defined its
own inline `<style>` block with its own subset of these classes — `index.html`/`foundation.html`
had 6 `.badge-status-*` classes, `organization.html` had 13, `person.html` had 3, `family.html`
had 2, `membership.html` had the full status set plus type/affiliation classes — meaning the same
`.badge-status-active` rule (green background, white text) was hand-copied into five separate
`<style>` blocks with no guarantee they'd stay byte-identical. This file is now the single
definition of every one of those classes, loaded by all six pages, with an explicit
header-comment rule: "Individual pages MUST NOT define badge-status-*, badge-type-*, or
badge-aff-* classes in inline `<style>` blocks" anymore. It also introduces a new set of
`.data-*` typographic classes for the three-tier identity display (Sangha Sevi ID / Sakha Sangha
ID / Kendra Number) that did not exist as shared classes before.

**Full file, 97 lines. Walkthrough:**

```css
.badge         { padding: 0.25rem 0.75rem !important; }
.badge-xs      { padding: 0.125rem 0.4rem !important; height: auto !important; min-height: 1.125rem; font-size: 0.6rem; }
```
- The same DaisyUI-padding-override purpose every page's old inline block served
  (`tailwind.min.css` — Tailwind 3.x + DaisyUI 4, same-origin pre-built stylesheet, see
  §2.1 — loads after this file and would otherwise win on the base `.badge`/`.badge-xs`
  rules without `!important`), now defined once. The `badge-xs` values here (`0.125rem 0.4rem`,
  `font-size: 0.6rem`) are a new, slightly more compact spec than several of the removed
  per-page overrides (e.g. `index.html`'s old copy used `0.15rem 0.5rem` with no explicit
  `font-size`) — a minor, intentional visual normalization that comes for free from
  deduplication.

```css
.badge-status-active              { background-color: #16a34a !important; color: #fff !important; }  /* green-600  */
/* ...18 total, through: */
.badge-status-disciplinary-review { background-color: #be123c !important; color: #fff !important; }  /* rose-700   */
```
- 18 lifecycle-status classes — the full unified `STATUS` category superset (Bye-Law authority
  noted in the section comment: §D(d), §12, §I, §C), covering every status value any page might
  need to render, not just the subset that page's own status column ever takes. Each class pins
  a Tailwind 600-level (or, for a few, 700/900-level) hex color with `!important` and white text,
  matching the exact hex values previously duplicated per-page (e.g. `#16a34a` for `active`,
  `#dc2626` for `suspended`/`cancelled`) — this file preserves those colors byte-for-byte rather
  than re-choosing a new palette, so no page's badge color changes as a visible side effect of
  the refactor.

```css
.badge-type-probationary  { background-color: #d97706 !important; color: #fff !important; }  /* amber-600   — Darshaka   */
.badge-type-regular       { background-color: #2563eb !important; color: #fff !important; }  /* blue-600    — Regular    */
.badge-type-associate     { background-color: #7c3aed !important; color: #fff !important; }  /* violet-600  — Associate  */
.badge-type-honorary      { background-color: #059669 !important; color: #fff !important; }  /* emerald-600 — Honorary   */
```
- The 4 membership-type classes, previously defined only in `membership.html`'s inline block —
  now available to any page (e.g. `family.html`'s per-person membership snapshot in its detail
  panel also renders a type badge via `NSS.typeBadgeClass()`).

```css
.badge-aff-active         { background-color: #16a34a !important; color: #fff !important; }  /* green-600 */
.badge-aff-archived       { background-color: #6b7280 !important; color: #fff !important; }  /* gray-500  */
.badge-aff-reactivated    { background-color: #2563eb !important; color: #fff !important; }  /* blue-600  */

.badge-gender-male        { background-color: #2563eb !important; color: #fff !important; }  /* blue-600   */
.badge-gender-female      { background-color: #ec4899 !important; color: #fff !important; }  /* pink-500   */
.badge-gender-other       { background-color: #8b5cf6 !important; color: #fff !important; }  /* violet-500 */
.badge-marital            { background-color: #7c3aed !important; color: #fff !important; }  /* violet-600 */
```
- Affiliation-status classes (previously `membership.html`-only) and gender/marital classes
  (previously not centralized at all — `person.html` rendered gender as plain text before this
  extraction). `badge-gender-*` is a genuinely new capability this file adds, not just a
  deduplication of pre-existing per-page rules.

```css
.badge-role-viewer        { background-color: #6366f1 !important; color: #fff !important; }  /* indigo-500 — YOU    */
.badge-role-head          { background-color: #f59e0b !important; color: #fff !important; }  /* amber-500  — HEAD   */
```
- Two role-indicator classes used by `family.html`'s family-tree/detail panel to mark "the
  person currently being viewed as" (`YOU`) and "the family head" (`HEAD`).

```css
.data-sevi-id             { font-family: ui-monospace, SFMono-Regular, monospace; font-weight: 600; color: oklch(var(--p)); }
.data-erp-no              { font-family: ui-monospace, SFMono-Regular, monospace; font-weight: 600; color: oklch(var(--s)); }
.data-kendra-no           { font-family: ui-monospace, SFMono-Regular, monospace; font-weight: 600; color: oklch(var(--a)); }
```
- The three-tier identity typographic classes (Sangha Sevi ID / Sakha Sangha ID / Kendra Number —
  see `membership.html`'s Three-Tier Identity Legend, §2.10). Each uses a DaisyUI CSS theme
  variable (`--p`/`--s`/`--a`, primary/secondary/accent) via `oklch(var(--x))` rather than a fixed
  hex, so the three colors stay visually distinct from each other and theme-aware (they'd repaint
  automatically if `data-theme` on `<html>` ever changed) — unlike every badge class above, which
  hardcodes a fixed hex regardless of theme. These replace what used to be ad hoc
  `font-mono text-primary`/`text-secondary`/`text-accent` utility-class combinations scattered
  inline across `membership.html` and `family.html` (see those files' diffs: `<span
  class="font-mono font-semibold text-primary">` became `<span class="data-sevi-id">`).

```css
.data-sakha-name          { font-weight: 500; color: #374151; }
.data-family-id           { font-family: ui-monospace, SFMono-Regular, monospace; font-weight: 600; color: #374151; }
.data-label               { font-size: 0.65rem; color: #9ca3af; letter-spacing: 0.02em; }
```
- Three more contextual identifier/label classes: `data-sakha-name` for organization names shown
  alongside identity fields, `data-family-id` for the family's own business ID, and `data-label`
  — a small, muted, letter-spaced caption style used above a value in detail-panel grids (e.g.
  `family.html`'s "Sangha Sevi ID" / "Status" / "Name" field labels).

---



- `frontend/README.md` — primary human-facing reference for this folder: directory
  structure, per-file summary tables (state properties, methods, API endpoints
  consumed), the FastAPI static-serving/routing setup (`api/main.py`), and the
  Tier-by-tier growth plan. Read that first for the "what" and "where"; this document
  supplies the "how, exactly" for each file's actual code.
- `docs/03_Solution/api/FOUNDATION_API_CONTRACT.md` — the authoritative API
  contract for the 17 `/api/v1/foundation/*` endpoints consumed by `foundation.html` /
  `foundation.js` (request/response shapes, filter query parameters, the deliberate
  exclusion of `current_value` and `field_change_log`).
- `docs/03_Solution/api/ORGANIZATION_API_CONTRACT.md` — the authoritative API
  contract for the 6 `/api/v1/organization/*` endpoints consumed by `organization.html` /
  `organization.js`.
- `docs/03_Solution/api/PERSON_API_CONTRACT.md` — the authoritative API contract for
  the 4 `/api/v1/person/*` endpoints consumed by `person.html` / `person.js` (request/
  response shapes, filter query parameters, the trigram `/search` endpoint, and the
  deliberate exclusion of `aadhaar_encrypted`/`aadhaar_hash`).
- `docs/03_Solution/api/API_CONTRACT.md` — the authoritative API contract for
  the 7 `/api/v1/membership/*` endpoints consumed by `membership.html` / `membership.js`
  (three-tier identity, search fields, sub-resource endpoints).
