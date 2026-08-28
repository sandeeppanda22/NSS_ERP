# NSS ERP Membership Module

Status: DRAFT — full Solution design complete, **not yet implemented in SQL or reconciled with
Django code**. The `backend/membership/` Django app already has real models (`MembershipType`,
`MembershipStatus`, `SanghaSevi` — plain integer PKs, no audit/soft-delete columns); see
`backend/membership/README.md`. The design below describes a much richer intended schema — see
Note below.

---

## Documents

01_membership_module_overview.md — Version 1.0, DRAFT
Purpose: High-level Membership module overview (Member Registration, Membership Types,
Approval, Renewal, Transfer, Membership Journey, Sangha Sevi ID Management).

02_membership_erd.md — Version 1.0.0, DRAFT
Purpose: Entity relationship design across the membership lifecycle.

03_membership_lifecycle.md — Version 1.0.0, DRAFT
Purpose: Membership state machine — Probationary → Regular → Associate, renewal (Dola Purnima
deadline, no grace period), transfer, reinstatement touchpoints.

04_membership_business_rules.md — Version 1.0.0, DRAFT
Purpose: Business rules governing membership approval, renewal, transfer, and journey tracking.

05_membership_table_design.md — Version 1.0.0, DRAFT, Document ID `SOL-MEM-005`
Purpose: Physical table design — `sangha_sevi`, `anumati_patra` (+ history), `parichaya_patra`
(+ history), `membership_status_history`, `membership_renewal_request`/`history`,
`membership_transfer_history`, `membership_journey_event`, `probationary_member_review` — UUID
`_pk` internal keys, full audit columns.

---

## Current Status

Design Complete

ERD Complete

Lifecycle Documented

Business Rules Drafted (not yet Frozen)

Table Design Drafted (not yet Frozen)

SQL Implementation Not Started

---

## Note

`backend/membership/models.py` (`MembershipType`, `MembershipStatus`, `SanghaSevi`) is a much
simpler placeholder that predates this design — plain auto-increment PKs, no UUID, no
`created_by_sangha_sevi_pk`-style audit trail, and none of the ~10 supporting history/journey
tables in `05_membership_table_design.md`. Same two-track gap already tracked for
`organization`/`person` in `docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas — don't
assume the Django model and this design describe the same schema.
