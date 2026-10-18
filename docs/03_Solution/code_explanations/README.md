# docs/03_Solution/code_explanations/

This folder holds **per-layer code explanations** — a "requirement + line-by-line" catalogue of
every source file in a given layer (API, Database, UI, Security, Testing). Each document exists
to answer "why does this file exist, and what exactly does its code do?" for every file it
covers.

Security audit reports (`TIER0_SECURITY_AUDIT.md` through `TIER4_SECURITY_AUDIT.md`, plus the
aggregate `SECURITY_AUDIT_TIER0_4.md`) are a different concern — findings and remediation status
from a security review, not code narration — and now live at `docs/03_Solution/security/` (see
that folder's own README).

This structure replaces an earlier, now-retired set of per-*tier* walkthroughs
(`TIER0_VERTICAL_SLICE.md`, `TIER1_FOUNDATION.md`, `SECURITY_HARDENING.md`) that interleaved the
same files' narration across multiple documents because each was written when a new tier or
cross-cutting concern landed. Organizing by layer instead means every source file has exactly one
home, and the same pattern extends cleanly as new layers are added in the future (e.g. a
`MOBILE_CODE_EXPLANATIONS.md` once a Flutter client exists).

## Files

- **`API_CODE_EXPLANATIONS.md`** (v1.7, Complete for Tier 0-4 only; Tier 5 routers/services/dependencies and `geo_approval.py` are not covered — updated: Tier 4 Family graph/sakha-alignment/
  membership-summary, first `api/services/` file) — every file under `api/` except
  `api/middleware.py` (which lives in the Security doc, since it's exclusively security code):
  `config.py`, `database.py`, `main.py`, `helpers.py`, `routers/bootstrap.py`,
  `routers/foundation.py`, `routers/organization.py`, `routers/person.py`, `routers/family.py`,
  `routers/membership.py`, `schemas/bootstrap.py`, `schemas/foundation.py`,
  `schemas/organization.py`, `schemas/person.py`, `schemas/family.py`, `schemas/membership.py`,
  `services/family_graph.py` (the first file in a new `api/services/` layer), and the three
  package `__init__.py` markers.
- **`DATABASE_CODE_EXPLANATIONS.md`** (v1.3, Complete for Tier 0-4 only; Tier 5 DDL/seed, festival/post_office tables and bulk geography seeds are not covered — updated: Tier 4 Family — `family_link`
  graph-edge table) —
  every hand-written SQL DDL/seed file and build/validate/grant script under `database/`
  (Bootstrap/Foundation/Organization/Person/Family/Membership — Person's
  `01_person_master_tables.sql` DDL/seed pair is the only remaining superseded file;
  `02_person.sql`/`03_person_address.sql` and all of `04_family/` (now 5 tables) and
  `05_membership/` are real, implemented DDL), full column-by-column detail for DDL,
  representative sampling (not verbatim row transcription) for large seed files.
- **`UI_CODE_EXPLANATIONS.md`** (v1.8, Superseded in part) — walks the six Tier 0-4 verification
  pages and their JS: `index.html`, `foundation.html`,
  `organization.html`, `person.html`, `family.html`, `membership.html`, `assets/js/app.js`,
  `assets/js/foundation.js`, `assets/js/organization.js`, `assets/js/person.js`,
  `assets/js/family.js`, `assets/js/membership.js`, plus `assets/css/style.css`. **All twelve
  HTML/JS files have since been deleted from `frontend/`** — their functionality was folded into
  `admin.html` and `dashboard.html` tabs (see the retirement table at the top of that document).
  The `style.css`/`badges.css`/`nss-config.js` sections remain current; the four current pages
  (`login.html`, `register.html`, `dashboard.html`, `admin.html`) and their JS are not yet
  covered there — see `frontend/README.md` for those.
- **`SECURITY_CODE_EXPLANATIONS.md`** (v1.2, Complete — updated: Tailwind CDN→CLI migration,
  `/assets/*` Cache-Control) —
  `api/middleware.py` in full, plus the security-relevant slices of `api/config.py`
  (`CORS_ORIGINS`/`RATE_LIMIT`/`DISABLE_DOCS`) and `api/main.py` (the middleware-registration
  block), plus the SRI-pinned CDN assets in `frontend/` — now just Alpine.js, since Tailwind/
  DaisyUI moved to a same-origin pre-built stylesheet. Note: the `frontend/` pages this
  describes were the six Tier 0-4 verification pages, since deleted — the identical Alpine.js
  SRI-pinned `<head>` block is now carried by `login.html`/`register.html`/`dashboard.html`/
  `admin.html`. Family's
  and Membership's router registration and their pages' dependency blocks follow the identical
  pattern already documented here — no Family/Membership-specific update needed in this file.
- **`TESTING_CODE_EXPLANATIONS.md`** (v1.8, Superseded in part) —
  every file under the flat Tier 4-era `tests/`: `conftest.py`, `test_bootstrap.py`,
  `test_foundation.py`,
  `test_organization.py`, `test_person.py`, `test_security.py`, `test_family.py`,
  `test_membership.py` (410 tests total at the time). **Its UI smoke-test sections assert against the six
  since-deleted Tier 0-4 verification pages, and `tests/` has been reorganized into
  `tests/api/`/`tests/ui/`/`tests/db/`/`tests/security/`** — see `tests/README.md` for the
  current breakdown.

**Tier 6 (Governance) coverage:** none of these five documents narrates Tier 6 yet — the
Governance router/schemas (`/api/v1/governance`), `admin/credentials` and `membership/change-requests`
endpoints, the Governance DDL/seed, the `admin.html` Governance nav group and `dashboard.html`
governance/"My Change Requests" panels, and `tests/api/test_governance.py` /
`tests/api/test_admin_credentials.py` are documented in `frontend/README.md`, `tests/README.md`,
`api/README.md`, `database/README.md` and `docs/03_Solution/modules/governance/` instead. In the test
suite, `tests/conftest.py` now overrides the auditing `get_write_connection` from
`api.dependencies.auth` (not `api.database`).

Security audit reports for Tiers 0–4 (`TIER0_SECURITY_AUDIT.md` … `TIER4_SECURITY_AUDIT.md`, plus
the cross-tier `SECURITY_AUDIT_TIER0_4.md`) live at `docs/03_Solution/security/`, not in this
folder — see that folder's own README for the current index.

See `docs/PROJECT_DOCUMENTATION.md` for the code-verified current state and
`docs/03_Solution/api/FOUNDATION_API_CONTRACT.md` for the Tier 1 API's formal contract. The same
`docs/03_Solution/api/` directory also holds `BOOTSTRAP_API_CONTRACT.md` (Tier 0),
`ORGANIZATION_API_CONTRACT.md` (Tier 2), `PERSON_API_CONTRACT.md` (Tier 3), and the new
cross-tier `API_CONTRACT.md` quick reference (Tiers 0–5, 137 endpoints; see that folder's README for detail).
