# NSS ERP — Technology Stack and Decision Matrix

**Document Type:** Solution Architecture Decision Record
**Version:** 1.1
**Date:** 2026-08-16
**Status:** Approved
**Branch:** feature/ref-documentation

**Revision History:**

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-08-16 | Initial approved decision record |
| 1.1 | 2026-08-20 | §6 Deployment and Git reconciled to live remote state: removed `pie` (Apple-internal remote, removed from the repo 2026-08-15); `org` — github.com/NilachalaSaraswataSangha/NSS_ERP is now an actual configured git remote (added 2026-08-18), not just a description — the Production remote row and Flow row now use the `org` alias consistently. No other section changed. |

---

## 1. Database

| Parameter | Decision | Rationale |
|-----------|----------|-----------|
| Engine | PostgreSQL | Best constraint/integrity tooling for governance-driven schema; UUID support, CHECK constraints, partial indexes, RLS, self-referencing FKs |
| Hosting (Production) | Neon.dev (free tier) | 512MB, no inactivity pause, branching, scales to zero without data loss |
| Hosting (Development) | Local PostgreSQL | `.env` configured per machine |
| Schema authority | Hand-written DDL (`database/ddl/`) | Governance-aligned, traceable to REF/GOV/REQ/SOLUTION |
| PK strategy | UUID (`gen_random_uuid()`, suffix `_pk`) | Security, no sequential enumeration |
| Business identifiers | `_code` suffix (e.g. `person_code`, `sangha_sevi_code`) | Permanent, human-readable, never reused |
| Audit columns | `created_at`, `updated_at`, `deleted_at`, `is_active` | Full lifecycle tracking |
| Soft delete | `deleted_at` pattern | History never deleted (frozen principle) |
| Naming | `snake_case` tables and columns | Existing DDL convention |

---

## 2. Backend

| Parameter | Decision | Rationale |
|-----------|----------|-----------|
| Language | Python | Existing expertise, mature ecosystem |
| Web framework | Django 6.0.6 | ORM, admin, auth, templates, migrations — built for multi-model ERP |
| API framework | FastAPI 0.136.3 | JSON APIs, sync endpoints, future mobile/offline support |
| Server | Uvicorn (ASGI) | Async-capable, serves both Django and FastAPI |
| ORM | Django ORM | Single source of truth for model-to-DB mapping |
| Hosting | Render.com (free tier) | 750 hours/month, native Django support, auto-deploy from GitHub |
| Environment | `django-environ` (`.env` file) | Secrets never in git |
| Testing | pytest | Standard Python testing |

---

## 3. Frontend

| Parameter | Decision | Rationale |
|-----------|----------|-----------|
| Rendering | Django Templates (server-side) | Single codebase, no separate frontend build |
| CSS framework | Tailwind CSS + DaisyUI | Modern SaaS look, color-coded domains, theme system, dark mode built-in |
| Interactivity | HTMX | Partial page updates without full reload, no JS framework needed |
| Micro-interactions | Alpine.js | Dropdowns, modals, toggles — tiny, no build step |
| Design language | Saffron (#DC7831) accent, institutional/spiritual, accessible to elderly | NSS identity, not corporate ERP |
| Previous (replaced) | Bootstrap 5 | Functional but visually flat — Tailwind + DaisyUI achieves modern feel with same effort |

---

## 4. Mobile Strategy

| Parameter | Decision | Rationale |
|-----------|----------|-----------|
| Primary delivery | PWA (Progressive Web App) | Installable on iOS/Android home screen, no app store needed |
| Manifest + Service Worker | Yes | Full-screen, splash screen, cached pages |
| App Store (future) | Capacitor wrapper (only if needed) | Same web app in a native shell |
| Native app (future) | Flutter consuming FastAPI (only if needed) | Only if PWA limits are hit — unlikely for this user base |

---

## 5. Offline Capability

| Parameter | Decision | Rationale |
|-----------|----------|-----------|
| Scope | Generic Event Engine (not UPBS-specific) | Any NSS event at a venue with poor connectivity |
| Storage | IndexedDB (browser) | Local data persistence, event-scoped |
| Sync mechanism | Service Worker + Background Sync | Queue writes offline, replay when connected |
| Conflict resolution | Server-authoritative + audit trail | Server assigns final IDs; conflicts flagged for manual review |
| Offline-capable modules | On-site registration, delegate/participant cards, venue attendance, receipt collection |
| Online-only modules | Membership, Governance, Family, Admin, Finance |

---

## 6. Deployment and Git

| Parameter | Decision | Rationale |
|-----------|----------|-----------|
| Development remote | `personal` — github.com/sandeeppanda22/NSS_ERP | Daily pushes |
| Production remote | `org` — github.com/NilachalaSaraswataSangha/NSS_ERP | Org account, deployment source |
| Deployment platform | Render.com | Connected to `org` repo main branch, auto-deploy on merge |
| Flow | feature/* to develop (`personal`) to PR to `org` to main (`org`) to Render deploys |
| Branch policy | Complete current branch, merge to develop, then create next |

---

## 7. Architecture Diagram

```
CLIENTS
  Browser (Desktop)
  PWA (Mobile, home screen)
  Offline Event Engine (IndexedDB + Service Worker)
       |                         | (Background Sync)
       v                         v
RENDER.COM (Free Tier)
  Uvicorn (ASGI)
    Django 6.0.6
      Templates + Tailwind CSS + DaisyUI
      HTMX + Alpine.js
      Django ORM
      Django Admin
    FastAPI 0.136.3
      JSON APIs (CRUD, search, reports)
      Sync endpoints (offline upload/download)
       |
       v
NEON.DEV (Free Tier)
  PostgreSQL
    UUID PKs + Business Codes
    CHECK constraints
    Row-Level Security (RLS)
    Soft delete + Audit trail
    ~100-130 tables (estimated final)
```

---

## 8. Implementation Order

### Phase 1 — Database (DDL)

```
02_organization (implement 0-byte placeholders from design doc)
04_membership
05_family
06_governance
07_attendance
08_authentication
Seed data for all masters
```

### Phase 2 — Django Models (rewrite to match DDL)

```
foundation (align with existing DDL)
membership
family
governance
attendance
authentication
```

### Phase 3 — API (FastAPI)

```
Person CRUD
Membership lifecycle
Organization hierarchy
Sync endpoints (for offline)
```

### Phase 4 — UI (Django Templates + Tailwind + DaisyUI + HTMX)

```
UI-001 Login
UI-002 Kendra Dashboard
UI-003 Sakha Dashboard
UI-004 Member Search
UI-005 Member Profile
UI-006 Family Dashboard
```

### Phase 5 — PWA + Offline (later phase)

```
PWA Manifest + Service Worker
Generic Event Engine (IndexedDB + Background Sync)
Capacitor wrapper (only if App Store needed)
```

---

## 9. Color Language (UI Design System)

| Color | Hex | Domain |
|-------|-----|--------|
| Saffron | #DC7831 | NSS brand accent, primary buttons, login |
| Indigo | #6366F1 | People/Members |
| Green | #22C55E | Families/Success/Active |
| Amber | #F97316 | Renewals/Warnings/Sakha |
| Blue | #0284C7 | Attendance/Information |
| Pink | #EC4899 | Mahila Sangha |
| Purple | #7C3AED | Governance/Transfer |
| Red | #DC2626 | Errors/Admin/Critical |

---

## 10. Alternatives Considered and Rejected

| Alternative | Rejected Because |
|-------------|-----------------|
| Next.js frontend | Wrong paradigm for ERP; doubles codebase; requires React/TypeScript learning; Django admin becomes useless |
| Vercel hosting | Serverless model fights Django (cold starts, timeout limits, no persistent process) |
| MongoDB | Data is highly relational (person to membership to organization to hierarchy); document DBs fight this shape |
| Supabase (database) | Free tier pauses after 7 days inactivity; Neon does not |
| React SPA | Doubles development time; requires separate build tooling; no benefit for the user base (elderly office bearers) |
| Bootstrap 5 (alone) | Functional but visually flat; Tailwind + DaisyUI achieves modern look without extra complexity |
| SQLite | No concurrent writes, no RLS, no UUID type — too limited for multi-user ERP |

---

## 11. Governance Traceability

This document is a SOLUTION-layer artifact per the frozen governance lifecycle:

```
REF (Statutory source)
  AUTH (Reference management)
    GOV (Governance interpretation)
      REQ (Business requirements)
        SOLUTION (This document) <--
          CODE (Implementation)
            TEST (Validation)
              RELEASE (Publication)
```

Technology decisions recorded here must not contradict frozen governance principles (GOV-ORG-001 through GOV-LIFE-002) or frozen module architectures (Person, Membership, Organization, Family, Governance).

---

# End of Document
