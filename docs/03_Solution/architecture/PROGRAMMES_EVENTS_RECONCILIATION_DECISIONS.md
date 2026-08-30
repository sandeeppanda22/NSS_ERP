# NSS ERP — Programmes & Events Reconciliation Decisions

**Document ID:** SOL-EVT-007
**Version:** 1.0.0
**Status:** FROZEN
**Date:** 2026-08-28
**Parent Documents:**
- SOL-EVT-006 — Programmes & Events Cross-Module Review
- SOL-MOD21-005 — Programmes & Events Table Design
- SOL-ATT-004 — Attendance Table Design

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document records the formal reconciliation decisions for the
Programme & Events architecture against existing modules.

The reconciliation was required before physical Event tables could be
frozen (per SOL-EVT-006 §72 and SOL-MOD21-005 §49).

All 7 reconciliation gates are now CLOSED.

---

# 2. Reconciliation Gates — Final Decisions

| Gate | Question | Decision | Date |
|------|----------|----------|------|
| A | Programme & Events owns common Event entity? | YES | 2026-08-28 |
| B | `upbs_event` becomes extension of common Event? | YES | 2026-08-28 |
| C | Kishor event identity becomes common Event extension? | YES | 2026-08-28 |
| D | Sevak event types become common Event extensions? | YES | 2026-08-28 |
| E | Event Session — common table or domain-specific? | Optional, organiser-defined (P&E-ARCH-002) | 2026-08-28 |
| F | Weekly Sangha Puja — common Event or Attendance-owned? | Attendance-owned (no change) | 2026-08-28 |
| G | Registration — common infrastructure or domain-specific? | Common P&E infrastructure (P&E-ARCH-001) | 2026-08-28 |

---

# 3. Gate F — Weekly Sangha Puja

**CLOSED: Weekly Sangha Puja remains Attendance-owned.**

`weekly_sangha_puja` is an Attendance-domain date anchor, not a P&E
Event. No P&E dependency is introduced for the Attendance module.

### Rationale (source-verified from SOL-ATT-004 and SOL-ATT-006)

- `weekly_sangha_puja` lifecycle: SCHEDULED → CONDUCTED (two states)
- No registration, no sessions, no delegates, no financial transaction
- Its sole purpose: FK anchor for attendance records on a specific
  Sakha + date
- Consecutive-absence machinery is Attendance business logic
- Cross-Sakha attendance is Attendance business logic
- Attendance dependency chain: Foundation → Person → Organization →
  Membership → Attendance (no P&E in the chain)
- Forcing P&E lifecycle (DRAFT → PUBLISHED → ACTIVE → COMPLETED) onto
  a weekly Puja adds complexity without solving a real problem

### Architectural separation

```text
Programme & Events
├── programme_type
├── event (planned/discretionary events)
├── event_day (multi-day structure)
├── event_session (optional programme schedule)
├── event_registration (common registration)
└── event_history

Attendance (separate, no P&E dependency)
├── weekly_sangha_puja (date anchor)
├── weekly_sangha_puja_attendance
├── attendance_exception
└── attendance_review
```

These are not competing event systems. They serve different purposes:

- P&E = planned/organized programmes (UPBS, Janmotsaba, Rasautsab, etc.)
- Attendance = operational attendance recording with enforcement rules

---

# 4. P&E-ARCH-001 — Common Registration Capability

**Status:** FROZEN

Programme & Events shall provide a common registration capability
reusable across programme types.

### Scope

- Registration records are P&E-owned
- Registration type is configurable per event (PARTICIPANT, DELEGATE,
  GUEST, VOLUNTEER, etc.)
- Actual financial transactions remain exclusively Finance-owned
  (FIN-ARCH-001)
- Registration can exist without payment (free events)
- Paid registration links to Finance through optional cross-reference

### Architecture

```text
Event
  └── Registration
        ├── Person/Member reference
        ├── Registration type
        ├── Registration status
        └── Optional finance reference → Finance transaction
```

### Evidence

Registration + delegate + fee patterns recur across at least 3
confirmed programme types:

| Programme | Registration | Delegate | Fee/Pranami |
|-----------|:---:|:---:|:---:|
| UPBS | Yes | Yes | Yes |
| Janmotsaba | Yes | Yes | Yes (varies by organizer) |
| Rasautsab | Yes | — | Yes |

---

# 5. P&E-ARCH-002 — Optional Event Session

**Status:** FROZEN

An Event may optionally contain organiser-defined Event Sessions.

### Rules

- Sessions represent the programme/schedule within an Event Day
- Sessions are not mandatory
- Registration remains at the Event level unless a future requirement
  explicitly establishes session-level registration
- Attendance at events other than Weekly Sangha Puja may reference an
  Event or Event Day; session-level attendance is not required

### Hierarchy

```text
Event
  └── Event Day (for multi-day events)
        └── Event Session (optional programme schedule)
```

---

# 6. Confirmed Programme Types

The following are confirmed as valid Programme Types for the common
Event model:

| Programme | Organizer | Days | Registration | Delegate |
|-----------|-----------|:----:|:---:|:---:|
| UPBS (Bhakta Sammilani) | Kendra | 3 | Yes | Yes |
| Janmotsaba | Kendra (Puri) or local Sakha | 1 | Yes | Yes |
| Rasautsab | Sakha (e.g. Ekamra Sangha) | 5 | Yes | — |
| Kishor Puja | Kendra | TBD | Domain-specific | — |
| Saradiya Alochana Chakra | Kendra | TBD | TBD | — |

### Janmotsaba — key characteristics

- Can be organized centrally at Puri OR locally by a Sakha
- Delegate participation applies
- Pranami/fee varies by organizer/Sakha (not hard-coded per programme)

### Rasautsab — key characteristics

- Sakha-organized (e.g. Ekamra Saraswata Sangha)
- Registration with event-specific fee

### Saradiya Alochana Chakra

- Operational characterization PENDING source confirmation
- Does not block the common architecture (model works with or without
  registration)

---

# 7. Event Day — Multi-Day Structure

Multi-day events use day-wise structure:

```text
UPBS 2027 (3-day):
  ├── Day 1
  ├── Day 2
  └── Day 3

Rasautsab 2027 (5-day):
  ├── Day 1
  ├── Day 2
  ├── Day 3
  ├── Day 4
  └── Day 5

Janmotsaba 2027 (1-day):
  └── (no day breakdown needed — single day)
```

`event_day` is a CANDIDATE common table. Not yet frozen as physical DDL.

---

# 8. Updated Candidate Common Table Set

| # | Candidate Table | Purpose | Status |
|--:|-----------------|---------|--------|
| 1 | programme_type | Master of programme categories | CANDIDATE |
| 2 | event | Event definition (identity, dates, organizer) | CANDIDATE |
| 3 | event_day | Day-wise structure for multi-day events | CANDIDATE |
| 4 | event_session | Optional programme schedule within a day | CANDIDATE |
| 5 | event_registration | Common registration records | CANDIDATE |
| 6 | event_location | Physical/geographic event venue | CANDIDATE |
| 7 | event_history | Event lifecycle state changes | CANDIDATE |

All remain CANDIDATE until the physical DDL phase.

---

# 9. Correspondence Extension — CORR-EXT-001

**Status:** FROZEN (2026-08-30) — ORG-PENDING-001 resolved

The correspondence reference format is organization-scoped. Each
organization (Kendra, Sakha, Anchalika, etc.) maintains its own
inward and outward correspondence registers with independent
numbering sequences per financial year.

```text
<ORG_SHORT_CODE>/<DIR>/YYYY-YY/NNN
```

Examples:

```text
ESS/IN/2026-27/001    — Ekamra Sangha inward #1
ESS/OUT/2026-27/001   — Ekamra Sangha outward #1
KEN/IN/2026-27/001    — Kendra inward #1
KEN/OUT/2026-27/042   — Kendra outward #42
```

### Key Principles

- Inward and outward maintain **separate numbering sequences**
- Sequences are **per-organization, per-direction, per-financial-year**
- The reference identifies the **organization that owns the
  correspondence register** (not the sender or recipient)
- Works at **all organization levels**: Kendra, Anchalika, Zilla, Sakha
- The `<ORG_SHORT_CODE>` is the `organization_short_code` column
  (VARCHAR(5), UNIQUE) frozen in ORG-PENDING-001
- `id_sequence_master` usage becomes **per-organization** rather than
  global — each organization has its own inward and outward counters
- The exact textual format (`ESS/IN/2026-27/001` vs `ESSIN2026001`
  or other) is deferred to the application/DDL phase; the
  **organization-level prefix principle** is frozen

### Dependencies — Resolved

- `organization_short_code` (ORG-PENDING-001): **FROZEN** (2026-08-30)
- Compatible with existing frozen schema (additive extension)

### Not a new gate or module

CORR-EXT-001 is an implementation-phase refinement of the existing
CORR-DECISION-003 architecture. It does not change module ownership
or introduce new dependencies.

---

# 10. What This Document Does NOT Change

- Attendance module ownership (unchanged)
- Attendance dependency tier (unchanged)
- `weekly_sangha_puja` table ownership (Attendance)
- `weekly_sangha_puja_attendance` table ownership (Attendance)
- Finance module ownership (unchanged)
- Organization module ownership (unchanged)
- Existing UPBS/Kishor/Sevak table ownership (unchanged)
- No new P&E → Attendance FK dependency

---

# 11. Superseded Proposals

The following proposals from earlier discussion are explicitly
superseded by this document:

- "P&E-ARCH-004 — Weekly Sangha Puja = common recurring Event"
  → SUPERSEDED (Gate F closed: Attendance-owned)
- "event_instance replacing weekly_sangha_puja"
  → SUPERSEDED (no migration)
- "Attendance tier change due to P&E dependency"
  → SUPERSEDED (no dependency introduced)

---

# 12. Next Steps

With all 7 reconciliation gates closed, the following can proceed:

1. DB Standards document
2. Final FK dependency graph (includes P&E position)
3. DDL creation order
4. Freeze 12-tier implementation order
5. Begin Foundation vertical slice (Tier 1: DDL → API → UI)

The Programme & Events module's physical DDL remains deferred until its
implementation tier is reached in the vertical-slice sequence.

---

# 13. Status

```text
DOCUMENT STATUS:
FROZEN

VERSION:
1.0.0

RECONCILIATION GATES:
ALL CLOSED (7/7)

P&E-ARCH-001 (Common Registration):
FROZEN

P&E-ARCH-002 (Optional Event Session):
FROZEN

GATE F (Weekly Sangha Puja):
CLOSED — ATTENDANCE-OWNED

CANDIDATE COMMON TABLES:
7

PHYSICAL DDL:
NOT STARTED (deferred to implementation tier)

ATTENDANCE MODULE:
NO CHANGE

NEXT:
DB STANDARDS → FK GRAPH → DDL ORDER → FOUNDATION VERTICAL SLICE
```
