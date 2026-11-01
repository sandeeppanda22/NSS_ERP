# NSS ERP — Registration Claim Table Design

**Document ID:** SOL-AUTH-007
**Version:** 1.0.0
**Status:** DRAFT — PENDING REVIEW
**Module:** Authentication & Security
**Parent System:** Nilachala Saraswata Sangha ERP
**Depends On:** SOL-AUTH-004 (Table Design), SOL-AUTH-006 (Registration Claim Business Rules)

---

# 1. Purpose

This document defines the table design for `nss.registration_claim`,
a new table that supports the admin-approval registration workflow.

This table is NOT part of the original 7-table frozen security foundation.
It is an extension owned by the Authentication & Security module.

---

# 2. Updated Table Set

| # | Table | Responsibility | Status |
|---:|---|---|---|
| 1 | `user_account` | ERP authentication account | FROZEN |
| 2 | `password_history` | Password-history/security record | FROZEN |
| 3 | `role_master` | Application role definition | FROZEN |
| 4 | `permission_master` | Application permission definition | FROZEN |
| 5 | `role_permission` | Role-to-permission relationship | FROZEN |
| 6 | `user_role` | User-to-role relationship | FROZEN |
| 7 | `admin_scope` | Organizational authorization scope | FROZEN |
| 8 | `registration_claim` | Pending membership claim from registration | DRAFT |

---

# 3. Changes to Existing Tables

## 3.1 user_account — PENDING_APPROVAL Status

The `chk_user_account_status` CHECK constraint is amended to include
a fourth status value:

    ACTIVE
    LOCKED
    INACTIVE
    PENDING_APPROVAL

This is a non-breaking change — existing rows with ACTIVE/LOCKED/INACTIVE
remain valid.

**Authority:** AUTH-BR-088

---

# 4. `registration_claim`

## 4.1 Purpose

`registration_claim` stores the membership claims made by a registrant
during self-registration. The claim is pending until a Sakha administrator
reviews and approves or rejects it.

A claim is NOT a membership record. It is a declaration that requires
administrative verification.

---

## 4.2 Primary Key

Logical primary key:

    registration_claim_pk

Type: UUID, auto-generated via `gen_random_uuid()`.

---

## 4.3 Relationship to user_account

Each registration_claim is associated with exactly one user_account:

    user_account
       ↓
    registration_claim (one-to-many)

A user_account may have multiple claims over time (if prior claims were
rejected and the person resubmitted), but at most one claim may be in
PENDING status at any time (AUTH-BR-083).

Foreign key: `user_account_pk REFERENCES nss.user_account(user_account_pk)`

---

## 4.4 Relationship to person

Each registration_claim is also linked to a person for direct querying:

    person
       ↓
    registration_claim

Foreign key: `person_pk REFERENCES nss.person(person_pk)`

This is a denormalization for query convenience — the canonical path is
person → user_account → registration_claim.

---

## 4.5 Claimed Organization

The registrant selects a Sakha during registration. This is stored as:

    claimed_organization_pk UUID NOT NULL

Foreign key: `REFERENCES nss.organization(organization_pk)`

This is the organization whose admin will review the claim.

---

## 4.6 Claimed Membership Type

The registrant selects a membership type:

    claimed_membership_type_master_data_pk UUID NOT NULL

Foreign key: `REFERENCES nss.master_data(master_data_pk)`

Expected values: PROBATIONARY (Darshaka), or the member's actual
membership type (SADHARAN, BISISTA, etc.).

---

## 4.7 Claimed Local Sakha Number

    claimed_local_sakha_number VARCHAR(20) NULL

This is the member's self-declared Local Sakha Number (same as SS ID).

- NULL for Darshaka members who do not have one
- Non-NULL for non-Darshaka members (application-level enforcement)
- Not validated against sangha_sevi at registration time (AUTH-BR-087)

> **Amendment (2026-11-01, owner-directed, GDR-009):** the two bullets above ("NULL for Darshaka" / "Non-NULL for non-Darshaka") are replaced by the legacy-vs-new rule. The column is non-NULL **iff** the registrant is a legacy member, recorded explicitly in two new columns added by the idempotent patch `ddl/06_authentication/06_registration_claim_legacy_member_patch.sql`:
>
>     is_legacy_member          BOOLEAN NOT NULL DEFAULT FALSE   -- home Sakha
>     darshak_is_legacy_member  BOOLEAN NOT NULL DEFAULT FALSE   -- attendance Sakha (darshak_organization_pk), independent of the first
>
> with `chk_registration_claim_legacy_home` (`is_legacy_member = (claimed_local_sakha_number IS NOT NULL)`) and `chk_registration_claim_legacy_darshak` (same for `darshak_local_sakha_number`). A new member's number is NULL and is generated at approval. Existing claims are defaulted once, when the columns are added: legacy iff they already carried a number.

> **Amendment (2026-11-01, owner-directed, GDR-009 §2B):** for a PROBATIONARY (Darshaka) claim `darshak_organization_pk`, `darshak_is_legacy_member` and `darshak_local_sakha_number` must be NULL/FALSE — a Darshaka cannot attend another Sakha (Sakha Transfer instead). Application-enforced (no CHECK); the claim edit clears them when the claim is, or becomes, a Darshaka claim.

---

## 4.7A Claimed Parichaya / Anumati Patra Number

    claimed_credential_document_number VARCHAR(30) NULL

The card ("Kendra") number a registrant who already holds a Parichaya Patra (Regular/Associate) or Anumati Patra (Darshaka) declares, in the form `<seq>/<yyyy>/<yyyy+1>` (e.g. `345/2026/2027`).

> **Amendment (2026-11-01, owner-directed, GDR-009):** the column is non-NULL **only** for a legacy member (`is_legacy_member = TRUE`), under the SAME flag as `claimed_local_sakha_number` — no new column and no DDL patch. It is application-enforced (not a CHECK), because pre-existing rows may still hold a number without the flag: such a claim 422s at approval until the admin corrects it through claim edit. For a new member it is NULL and the number is minted at approval by `next_credential_document_number()` (Anumati for a Darshaka, Parichaya for Regular/Associate). A legacy number is stored in canonical form (no leading zeros), is never replaced by the counter, and is a 409 if the same document number is already issued (Parichaya: NSS-wide; Anumati: per issuing Sakha).

---

## 4.8 Claimed Joining Date

    claimed_joining_date DATE NULL

The date the registrant claims to have joined the Sakha.
NULL if the registrant did not provide one.

---

## 4.9 Darshak Attendance

    darshak_organization_pk UUID NULL

If the registrant is attending another Sangha as Darshak, this stores
the UUID of that other organization.

Foreign key: `REFERENCES nss.organization(organization_pk)`

NULL if not attending another Sangha as Darshak.

---

## 4.10 Claim Status

    claim_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'

Valid values:

    PENDING     — awaiting admin review
    APPROVED    — admin verified and approved
    REJECTED    — admin rejected the claim

CHECK constraint enforces these three values.

---

## 4.11 Review Fields

    reviewed_by_user_account_pk UUID NULL
    reviewed_at TIMESTAMPTZ NULL
    admin_remarks TEXT NULL

These are populated when a Sakha admin acts on the claim:

- `reviewed_by_user_account_pk` — the admin who approved/rejected
- `reviewed_at` — timestamp of the decision
- `admin_remarks` — reason for rejection or notes on approval

All three are NULL while claim_status = 'PENDING'.

---

## 4.12 Audit Columns

Standard project audit columns:

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    updated_at TIMESTAMPTZ NULL
    is_active BOOLEAN NOT NULL DEFAULT TRUE
    deleted_at TIMESTAMPTZ NULL

Soft-delete CHECK constraint:

    (is_active = TRUE AND deleted_at IS NULL)
    OR
    (is_active = FALSE AND deleted_at IS NOT NULL)

---

## 4.13 Indexes

| Index | Columns | Condition |
|---|---|---|
| `idx_registration_claim_user_account` | `user_account_pk` | — |
| `idx_registration_claim_person` | `person_pk` | — |
| `idx_registration_claim_status` | `claim_status` | — |
| `idx_registration_claim_organization` | `claimed_organization_pk` | — |
| `idx_registration_claim_pending` | `user_account_pk` | `WHERE claim_status = 'PENDING'` |

The partial index `idx_registration_claim_pending` supports the
one-active-claim constraint check (AUTH-BR-083).

---

## 4.14 Unique Constraint

A partial unique constraint enforces one PENDING claim per user_account:

    UNIQUE (user_account_pk) WHERE claim_status = 'PENDING'

This is implemented as a unique partial index (PostgreSQL).

---

## 4.15 Depth

Depth: 3

    person (depth 0)
      → user_account (depth 2, depends on person)
        → registration_claim (depth 3)

Also depends on organization (depth 1) and master_data (depth 1).

---

## 4.16 DDL File

    database/ddl/06_authentication/03_registration_claim.sql

---

# 5. Status

DOCUMENT STATUS:

```
DRAFT — PENDING REVIEW
```

VERSION:

```
1.0.0
```

---
