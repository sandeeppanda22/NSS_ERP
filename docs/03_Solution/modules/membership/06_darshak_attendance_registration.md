# NSS ERP — Darshak Attendance Registration Business Rules & Table Design

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Darshak Attendance Registration |
| Document ID | SOL-MEM-006 |
| Domain | Membership |
| Repository Path | docs/03_Solution/modules/membership/06_darshak_attendance_registration.md |
| Version | 1.1.0 |
| Status | Approved |
| Authority | Project Owner clarification (2026-09-20; request-initiation source added 2026-10-12) |
| Parent Document | 01_membership_module_overview.md |
| Related Documents | 04_membership_business_rules.md (MBR-007), 05_membership_table_design.md (§27.1), CROSS_MODULE_PRINCIPLES.md (§20.2, §20.3), DARSHAK_BUSINESS_RULE.md |

---

# 1. Purpose

This document defines the business rules and physical table design for
Darshak attendance registration — the process by which an existing
NSS member attends a Sakha other than their home Sakha with formal
approval and receives a local tracking number from the receiving Sakha.

This is **separate from** `membership_sakha_affiliation`, which
records the member's authoritative home-Sakha affiliation and Local
Sakha ERP ID. Darshak attendance registration does not constitute
a membership transfer. The member's Parichaya Patra remains at their
home Sakha.

---

# 2. Terminology

| Term | Meaning |
|------|---------|
| Home Sakha | The Sakha where the member's Parichaya Patra resides and their active `membership_sakha_affiliation` points |
| Attending Sakha | The Sakha the member attends as Darshak (approved cross-Sakha attendance) |
| Darshak Local Number | A local tracking number assigned by the attending Sakha to the Darshak attendee; operationally used for attendance registers |
| Approved Darshak | An existing member of another Sangha who has completed the three-step approval to attend a different Sakha |

**"Darshak" is NOT a membership type** (per MBR-007). This table
uses "Darshak" strictly as an operational term for cross-Sakha
attendance.

---

# 3. Scope — Who Gets a Darshak Registration

This table applies to:

1. **Regular Members attending another Sakha as Darshak** — holds
   Parichaya Patra at home Sakha, approved to attend a different Sakha.

2. **Probationary Members attending another Sakha as Darshak** — holds
   Anumati Patra at their enrolling Sakha, approved to attend a
   different Sakha.

This table does NOT apply to:

- **Visitors** (attending ≤4 consecutive Sundays without approval) — no
  registration record; attendance only.
- **Probationary Members at their enrolling Sakha** — that is their
  home Sakha; they receive a Local Sakha ERP ID via
  `membership_sakha_affiliation` (not this table).
- **Transfers** — when a member permanently moves to another Sakha,
  that is handled by `membership_transfer_history` +
  `membership_sakha_affiliation`.

---

# 4. Business Rules

## DAR-001 — Darshak Attendance Requires Three-Step Approval

A member wishing to attend another Sakha as Darshak must obtain
approval in sequence:

```text
Step 1: Home Sakha approval (Secretary or President)
Step 2: Parichalak approval (Kendra level)
Step 3: Target Sakha President approval
```

All three approvals must be obtained before the member is recognized
as an Approved Darshak at the target Sakha.

---

## DAR-002 — One Active Darshak Attendance at a Time

A member may hold only **one** active Darshak attendance registration
at any time. To attend a different Sakha as Darshak, the current
registration must first be archived (or revoked).

---

## DAR-003 — Darshak Local Number Assigned by Attending Sakha

The attending Sakha assigns a Darshak local number to the approved
attendee. This number is:

- A simple numeric sequence (not the `<short_code><sequence>` format
  used for Local Sakha ERP ID)
- Scoped to the attending Sakha — unique within that Sakha's Darshak
  register
- Assigned after Step 3 approval is complete

---

## DAR-004 — Darshak Local Number Is Persistent

If a member stops attending a Sakha as Darshak and later returns
(with fresh approval), the **same** Darshak local number is
reactivated. The number is never reassigned to another person at
that Sakha.

---

## DAR-005 — Darshak Does Not Replace Membership Affiliation

Darshak attendance registration does not affect
`membership_sakha_affiliation`. The member's home-Sakha Local Sakha
ERP ID and active affiliation remain unchanged.

```text
membership_sakha_affiliation:  ESS1192  ACTIVE  (home Sakha — unchanged)
darshak_attendance_registration:  42   ACTIVE  (attending Sakha — separate)
```

---

## DAR-006 — Home and Attending Sakha Must Differ

A member cannot register as Darshak at their own home Sakha.

---

## DAR-007 — Darshak Registration Does Not Grant Governance Rights

Darshak attendance at a Sakha does not grant the member any governance
position, voting rights, or administrative authority at the attending
Sakha.

---

## DAR-008 — Darshak to Transfer Transition

If a Darshak attendee later transfers to the attending Sakha, the
Darshak attendance registration is archived. The member receives a
new `membership_sakha_affiliation` row at the new Sakha via the
normal transfer workflow.

---

## DAR-009 — Request Initiation Source

A Darshak attendance request may be raised by:

- **the member himself** — `request_source = MEMBER_SELF`, or
- **an admin, on the member's behalf** — `request_source = ADMIN_AUTOMATIC_ENTRY`

The request form records who raised it (`initiated_by_sangha_sevi_pk`)
and the `request_source` value. This is a record-keeping distinction
only — **it does not change, skip, or auto-approve any step of the
three-step approval in DAR-001**. An admin-initiated ("Automatic
Entry") request still requires Home Sakha, Parichalak, and Target
Sakha approval in sequence, exactly like a member-initiated request.

---

# 5. Approval Workflow Status Transitions

```text
PENDING_HOME_SAKHA
    │
    ▼ (Home Sakha approves)
PENDING_PARICHALAK
    │
    ▼ (Parichalak approves)
PENDING_TARGET_SAKHA
    │
    ▼ (Target Sakha President approves + assigns local number)
APPROVED
    │
    ├──▶ ARCHIVED  (member stops attending, or transfers)
    │
    └──▶ REVOKED   (approval withdrawn by any authority)

Any PENDING state may also → REJECTED
```

---

# 6. Table Design — `nss.darshak_attendance_registration`

**Owner:** Membership

## Columns

```text
darshak_attendance_registration_pk   UUID PK  DEFAULT gen_random_uuid()
sangha_sevi_pk                       FK → sangha_sevi  NOT NULL
home_organization_pk                 FK → organization  NOT NULL
attending_organization_pk            FK → organization  NOT NULL
initiated_by_sangha_sevi_pk          FK → sangha_sevi  NOT NULL
                                       (who raised the request — the member himself,
                                       or the admin acting on his behalf)
request_source                       VARCHAR(20)  NOT NULL
                                       MEMBER_SELF / ADMIN_AUTOMATIC_ENTRY (DAR-009;
                                       record-keeping only — does not affect approval)
darshak_local_number                 VARCHAR(30)  NULL
                                       (assigned on APPROVED — NULL while pending)
approval_status                      VARCHAR(30)  NOT NULL
                                       PENDING_HOME_SAKHA / PENDING_PARICHALAK /
                                       PENDING_TARGET_SAKHA / APPROVED /
                                       REJECTED / REVOKED
approved_by_home_sakha_sevi_pk       FK → sangha_sevi  NULL
approved_by_home_sakha_at            TIMESTAMPTZ  NULL
approved_by_parichalak_sevi_pk       FK → sangha_sevi  NULL
approved_by_parichalak_at            TIMESTAMPTZ  NULL
approved_by_target_sakha_sevi_pk     FK → sangha_sevi  NULL
approved_by_target_sakha_at          TIMESTAMPTZ  NULL
rejection_reason                     TEXT  NULL
effective_from                       DATE  NULL
                                       (set when APPROVED)
effective_to                         DATE  NULL
                                       (NULL = currently active)
registration_status                  VARCHAR(20)  NOT NULL
                                       ACTIVE / ARCHIVED
remarks                              TEXT  NULL
is_active                            BOOLEAN  NOT NULL  DEFAULT TRUE
created_at                           TIMESTAMPTZ  NOT NULL  DEFAULT CURRENT_TIMESTAMP
created_by_sangha_sevi_pk            UUID  NULL
updated_at                           TIMESTAMPTZ  NULL
updated_by_sangha_sevi_pk            UUID  NULL
```

## Constraints

```text
-- No two people share the same Darshak number at a Sakha
UNIQUE(attending_organization_pk, darshak_local_number)

-- One active Darshak attendance per person at a time (DAR-002)
UNIQUE(sangha_sevi_pk) WHERE registration_status = 'ACTIVE'

-- Cannot be Darshak at own home Sakha (DAR-006)
CHECK(home_organization_pk != attending_organization_pk)

-- Request source controlled (DAR-009)
CHECK(request_source IN ('MEMBER_SELF', 'ADMIN_AUTOMATIC_ENTRY'))

-- Approval status controlled
CHECK(approval_status IN (
    'PENDING_HOME_SAKHA',
    'PENDING_PARICHALAK',
    'PENDING_TARGET_SAKHA',
    'APPROVED',
    'REJECTED',
    'REVOKED'
))

-- Registration status controlled
CHECK(registration_status IN ('ACTIVE', 'ARCHIVED'))

-- Darshak local number required when APPROVED
CHECK(
    (approval_status = 'APPROVED' AND darshak_local_number IS NOT NULL)
    OR
    (approval_status != 'APPROVED')
)

-- Effective dates consistency
CHECK(
    effective_to IS NULL
    OR effective_to >= effective_from
)
```

## Indexes

```text
idx_dar_att_reg_sevi              (sangha_sevi_pk)
idx_dar_att_reg_home_org          (home_organization_pk)
idx_dar_att_reg_attending_org     (attending_organization_pk)
idx_dar_att_reg_approval_status   (approval_status)
idx_dar_att_reg_registration_status (registration_status)
uq_dar_att_reg_active             UNIQUE(sangha_sevi_pk) WHERE registration_status = 'ACTIVE'
```

---

# 7. Relationship to Existing Tables

```text
PERSON
   |
   +-- SANGHA_SEVI
          |
          +-- MEMBERSHIP_SAKHA_AFFILIATION
          |         (home Sakha — Local Sakha ERP ID)
          |
          +-- DARSHAK_ATTENDANCE_REGISTRATION
                    (attending Sakha — Darshak local number)
```

The two tables serve distinct purposes:

| Aspect | membership_sakha_affiliation | darshak_attendance_registration |
|--------|----------------------------|-------------------------------|
| Purpose | Home Sakha membership affiliation | Cross-Sakha Darshak attendance |
| ID format | `<short_code><sequence>` (e.g. ESS1192) | Simple number (e.g. 42) |
| Parichaya Patra | Resides here | Stays at home Sakha |
| Governance | Determines Sakha membership | No governance rights |
| Transfer | Triggers archive + new row | Independent; archived if transfer occurs |
| Approval | Admin approval at enrollment/transfer | Three-step: Home → Parichalak → Target |

---

# 8. Impact on CROSS_MODULE_PRINCIPLES

The statement in CROSS_MODULE_PRINCIPLES.md §20.2:

> "Approved Darshak (existing member of another Sangha) — No local Sakha
> number issued by receiving Sakha"

is **corrected** by this document:

> Some Sakhas assign a Darshak local number to Approved Darshak
> attendees for their attendance register. This number is stored in
> `darshak_attendance_registration.darshak_local_number` and is
> operationally distinct from the Local Sakha ERP ID on
> `membership_sakha_affiliation`.

The CROSS_MODULE_PRINCIPLES Issuance Rules table should be updated:

| Scenario | Local ERP ID issued? | Darshak local number issued? |
|----------|:---:|:---:|
| Home Sakha member | Yes | N/A |
| Probationary Member at enrolling Sakha | Yes | N/A |
| Approved Darshak at another Sakha | No | Yes (by attending Sakha) |
| Visitor (≤4 Sundays, no approval) | No | No |

---

# 9. Frozen Decisions

```text
Darshak attendance registration is separate from membership affiliation

One active Darshak attendance per person at a time

Three-step approval: Home Sakha → Parichalak → Target Sakha President

Darshak local number is persistent per person per Sakha (never reassigned)

Darshak local number is a simple number (not <short_code><sequence> format)

Darshak does not grant governance rights at attending Sakha

Darshak registration is archived on transfer to attending Sakha

Request initiation source (member self vs. admin automatic entry) is
record-keeping only — it never changes or skips the three-step approval
```

---
