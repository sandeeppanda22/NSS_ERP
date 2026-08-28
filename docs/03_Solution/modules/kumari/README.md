# NSS ERP Kumari Sangha Module

Status: DRAFT — full Solution design complete; there is still no `backend/kumari/` Django app.
Kumari Sangha is a permanent developmental institution for unmarried girls, distinct from NSS
Membership, reusing the existing Person/Family foundation.

---

## Documents

01_kumari_module_overview.md — Document ID `SOL-KUM-001`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: High-level Kumari Sangha module overview (KM Identity, Activities, Training, Membership
Transition).

02_kumari_erd.md — Document ID `SOL-KUM-002`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: Entity relationship design.

03_kumari_lifecycle.md — Document ID `SOL-KUM-003`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: Lifecycle — Enrollment → Active → exit via transition to NSS Membership, marriage
(`MARRIED_OUT`), withdrawal, or death (`ACTIVE, MARRIED_OUT, BECAME_NSS_MEMBER, WITHDRAWN,
DECEASED`). History is never physically deleted.

04_kumari_business_rules.md — Document ID `SOL-KUM-004`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: Business rules, including the Kumari ID format and transition-to-Membership rule.

05_kumari_table_design.md — Document ID `SOL-KUM-005`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: Physical table design — `kumari_sangha`, `kumari_membership`, `kumari_activity`,
`kumari_activity_participant`, `kumari_membership_transition`.

---

## Key facts

- **Kumari ID format: `KM000001`** (KM + 6 digits) — unique, permanent, never reused, distinct
  from Sangha Sevi ID (see `CLAUDE.md` §7).
- Transition to NSS Membership (Probationary/Regular) is an explicit recorded step
  (`KM000123 → SS000456`), never automatic.
- All docs self-label DRAFT even though individual sections are titled "Frozen Table
  Baseline"/"Frozen Decisions" — treat the document-level Status field as authoritative until
  a future pass reconciles that internal terminology inconsistency (same pattern already
  resolved for AUTH-001/GOV-001's Status vs. Rule Maturity fields).

---

## Current Status

Design Complete · ERD Complete · Lifecycle Documented · Business Rules Drafted · Table Design
Drafted · SQL Implementation Not Started · `backend/kumari/` Django app does not exist yet
