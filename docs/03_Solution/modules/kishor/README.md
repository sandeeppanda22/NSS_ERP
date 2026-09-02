# NSS ERP Kishor Puja Module

Status: DRAFT — full Solution design complete; there is still no `backend/kishor/` Django app.
Kishor Puja is modeled as an annual event/activity for boys (not a permanent org unit like
Kumari Sangha), reusing the existing Person/Family foundation.

---

## Documents

01_kishor_module_overview.md — Document ID `SOL-KISH-001`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: High-level Kishor Puja module overview (KH Identity, Registration, Guardian
Assignment).

02_kishor_erd.md — Document ID `SOL-KISH-002`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: Entity relationship design.

03_kishor_lifecycle.md — Document ID `SOL-KISH-003`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: Lifecycle — one permanent Kishor ID retained across multiple years' registrations,
with optional transition to NSS Membership.

04_kishor_business_rules.md — Document ID `SOL-KISH-004`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: Business rules, including the Kishor ID format, registration sources, and the Guardian
Model (frozen v2.1 — Guardian must independently qualify as an NSS Member via `sangha_sevi`
identity; being the legal guardian/parent does not itself satisfy the requirement, KISH-023).

05_kishor_table_design.md — Document ID `SOL-KISH-005`, Version 1.0.0, DRAFT — SOURCE ALIGNED
Purpose: Physical table design — `kishor_participant`, `kishor_event`,
`kishor_event_registration`, `kishor_membership_transition`.

---

## Key facts

- **Kishor ID format: `KH000001`** (KH + 6 digits) — unique, permanent, distinct from Sangha
  Sevi ID; one ID spans many yearly `kishor_event_registration` rows.
- **Guardian Model (Frozen):** every participant must have an assigned Guardian who is an NSS
  Member of the participant's Sakha, assigned by the Sakha — not necessarily the parent.
- Registration sources: Parent Nomination or Sakha Nomination.
- Transition to NSS Membership follows the same non-automatic, history-preserving pattern as
  Kumari Sangha (`KH000123 → SS000456`).

---

## Current Status

Design Complete · ERD Complete · Lifecycle Documented · Business Rules Drafted (Guardian Model
Frozen) · Table Design Drafted · SQL Implementation Not Started · `backend/kishor/` Django app
does not exist yet
