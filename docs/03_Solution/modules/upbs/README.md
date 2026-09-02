# NSS ERP UPBS Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0. Full Solution design complete (4 files); there is no
`backend/upbs/` Django app.

---

## Documents

01_upbs_module_overview.md (`SOL-UPBS-001`) — Version 1.0.0
Purpose: Digital operational foundation for the Utkala Pradeshika Bhakta Sammilani (UPBS) —
event management, registration, delegate management, accommodation, camp allocation, guest/
reference management, event-day operations, meal tracking, committee/volunteer operations,
UPBS reporting.

02_upbs_erd.md — Version 1.0.0
Purpose: Entity relationship design for the seven frozen foundation tables.

03_upbs_business_rules.md — Version 1.0.0, UPBS-BR-001–UPBS-BR-069
Purpose: Business rules for event sessions, registration timing, delegate packages, and
mandatory reference requirements.

04_upbs_table_design.md — Version 1.0.0
Purpose: Physical table design — seven tables.

---

## Key facts

- Seven tables: `upbs_event`, `upbs_registration`, `delegate_card`, `prasad_patra`,
  `accommodation_allocation`, `camp_master`, `guest_reference`.
- Event sessions: `ADHIBASA` / `DAY_1` / `DAY_2` / `DAY_3`; registration may happen before or
  during UPBS.
- Delegate Package = Delegate Card + Prasad Patra. "Prasad Only" is allowed; "Delegate Only" is
  prohibited (a delegate always gets Prasad Patra too).
- QR-based meal tracking; a Reference Sangha Sevi is mandatory for registration.
- Day 1/2/3 operational detail and volunteer structure are explicitly marked PENDING — still
  open work (UPBS Volunteer structure + Day 1/2/3 operations).

---

## Current Status

Design Complete · ERD Complete · Business Rules Drafted (SOURCE ALIGNED) · Table Design
Drafted (SOURCE ALIGNED) · SQL Implementation Not Started · `backend/upbs/` Django app does
not exist yet
