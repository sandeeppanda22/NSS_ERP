# NSS ERP — Registration Claim Business Rules

**Document ID:** SOL-AUTH-006
**Version:** 1.0.0
**Status:** DRAFT — PENDING REVIEW
**Module:** Authentication & Security
**Parent System:** Nilachala Saraswata Sangha ERP
**Depends On:** SOL-AUTH-003 (Authentication Business Rules), SOL-AUTH-005 (Table Design)

---

# 1. Purpose

This document defines the business rules governing the self-registration
claim workflow. Under this model, a person who registers through the
public registration form does not receive immediate access. Instead,
their membership claim is recorded for review by the relevant Sakha
administrator. Access is granted only after administrative approval.

This replaces the prior immediate-activation registration model.

---

# 2. Rule Classification

Rules are classified as:

- FROZEN — explicitly established by the project source
- SOURCE-ALIGNED — directly supported by project standards
- PENDING — requires further approval
- FUTURE — outside the current frozen scope

---

# 3. Registration Scope

## AUTH-BR-081 — Registration Creates Person and Pending Account Only

**Status:** SOURCE-ALIGNED

Self-registration shall create:

    1. A person record
    2. A user_account record with account_status = 'PENDING_APPROVAL'

Self-registration shall NOT create:

    sangha_sevi record
    membership_sakha_affiliation record

These records are created only upon administrative approval.

**Authority:** AUTH-BR-006 (User Account Does Not Create Membership — FROZEN)

---

## AUTH-BR-082 — Registration Claim Records Membership Intent

**Status:** SOURCE-ALIGNED

When a registrant claims membership in a Sakha, the registration
system shall record the claim in nss.registration_claim, including:

    claimed_organization_pk — the Sakha the person claims to belong to
    claimed_membership_type_master_data_pk — the claimed membership type
    claimed_local_sakha_number — the local Sakha number (if provided)
    claimed_joining_date — the date the person claims to have joined

The claim is a declaration by the registrant, not a verified fact.

---

## AUTH-BR-083 — One Active Claim Per Person

**Status:** SOURCE-ALIGNED

A person may have at most one registration claim in PENDING status
at any time. A new claim may be submitted only after the previous
claim has been resolved (APPROVED or REJECTED).

---

## AUTH-BR-084 — Claim Status Lifecycle

**Status:** SOURCE-ALIGNED

A registration claim progresses through the following statuses:

    PENDING    — initial state after registration
    APPROVED   — Sakha admin has verified and approved the claim
    REJECTED   — Sakha admin has rejected the claim

Transitions:

    PENDING  -> APPROVED  (by Sakha admin)
    PENDING  -> REJECTED  (by Sakha admin)

A REJECTED claim may be followed by a new PENDING claim if the
person resubmits with corrected information.

---

# 4. Local Sakha Number

## AUTH-BR-085 — Local Sakha Number Replaces SS ID on Registration

**Status:** SOURCE-ALIGNED

> **Amendment (2026-11-01, owner-directed, GDR-009):** the registration form first asks "Were you already a member of NSS before this system? (Regular or Darshak)" (after the Sakha is selected); the Local Sakha Number field is shown and required only for *Yes*, and for *No* a note says the number is assigned automatically. The question is asked again, separately, for an attendance Sakha.

The registration form shall ask for "Local Sakha Number" instead of
"SS ID" or "Sangha Sevi ID". The field is presented after the
registrant selects their Sakha.

The Local Sakha Number and SS ID are the same identifier (Sakha-scoped
member number), but the user-facing label shall be "Local Sakha Number"
because at registration time the identity has not yet been verified.

---

## AUTH-BR-086 — Local Sakha Number Requirement by Membership Type

**Status:** SOURCE-ALIGNED

> **Amendment (2026-11-01, owner-directed, GDR-009):** the requirement below is replaced by the legacy-vs-new rule. A registrant who was ALREADY a member (Regular/Associate or Darshak/Darshaka) before this system existed is a *legacy member* (`registration_claim.is_legacy_member = TRUE`) and MUST supply the Local Sakha Number on their card; anyone else is a *new* member (`FALSE`), supplies none (a number sent with `FALSE` is a 422), and receives an auto-generated number at approval — next in the Regular/Associate series, or the Darshak series for a Darshaka. This applies to Regular, Associate and Darshaka alike. "Non-Darshaka REQUIRED / Darshaka OPTIONAL" no longer applies; the only remaining 422 is a *legacy* claim with no number. The cross-Sakha attendance affiliation follows the same rule at the attended Sakha, with its own flag (`darshak_is_legacy_member`). The admin verifies (and may correct, via claim edit) the flags and numbers at approval.

> **Amendment (2026-11-01, owner-directed, GDR-009):** the **Parichaya / Anumati Patra ("Kendra") number** claimed at registration (`registration_claim.claimed_credential_document_number`; previously REQUIRED for every non-Darshaka claim and optional for a Darshaka, and not covered by a numbered AUTH rule) follows the SAME explicit flag and the SAME legacy-vs-new split as the Local Sakha Number — there is no separate Patra flag, because a person who already holds a card is by definition already a member. A *legacy* claim (`is_legacy_member = TRUE`) MUST carry the number printed on the member's card, in the MBR-030A form `<seq>/<yyyy>/<yyyy+1>` (Parichaya Patra for Regular/Associate, Anumati Patra for a Darshaka); a *new* claim carries none (a number sent with `FALSE` is a 422) and the system mints one at approval (Anumati Patra for a Darshaka, Parichaya Patra for Regular/Associate — every member holds exactly one credential). The format is checked at registration, claim edit and approval, and a number already issued is a 409; the approver verifies and may correct it via claim edit. Rule text: MBR-030A (amended) and GDR-009 §2A.

> **Amendment (2026-11-01, owner-directed, GDR-009 §2B):** the registration claim's cross-Sakha attendance Sakha (`darshak_organization_pk`, `darshak_is_legacy_member`, `darshak_local_sakha_number`) is available to Regular/Associate registrants only. A Darshaka (PROBATIONARY) claim that carries one is refused with 422 ("A Darshaka who attends another Sakha must transfer to it; use Sakha Transfer") at registration, claim edit (a Darshaka claim's stored attendance Sakha is removed by the edit) and approval.

Local Sakha Number requirement depends on membership type:

    Non-Darshaka members: REQUIRED
        The Local Sakha Number is mandatory. The registrant must
        provide the number assigned to them by their Sakha.

    Darshaka (Probationary) members: OPTIONAL
        Some Sakhas assign Local Sakha Numbers to Darshaka members;
        others do not. The field shall accept input but not require it.

---

## AUTH-BR-087 — Local Sakha Number Is Not Validated at Registration

**Status:** SOURCE-ALIGNED

> **Amendment (2026-11-01, owner-directed, GDR-009):** unchanged in substance — the number is never checked against existing `sangha_sevi` records at registration — but registration does enforce the legacy rule's *shape* (legacy ⇒ a well-formed number is required; new ⇒ none may be sent). Uniqueness (409) and correctness remain the approver's / the database's job.

The Local Sakha Number provided during registration is stored as a
claim only. The system shall NOT validate it against existing
sangha_sevi records at registration time.

Validation is performed by the Sakha administrator during the
approval step.

**Rationale:** The registrant may mistype, use an outdated number,
or be a Darshaka who has not yet been assigned one. Validation
belongs in the admin approval workflow, not in the public form.

---

# 5. Account Status

## AUTH-BR-088 — PENDING_APPROVAL Account Status

**Status:** SOURCE-ALIGNED

The user_account CHECK constraint shall include PENDING_APPROVAL as
a valid account_status value:

    ACTIVE
    LOCKED
    INACTIVE
    PENDING_APPROVAL

Accounts created via self-registration shall have:

    account_status = 'PENDING_APPROVAL'

**Authority:** AUTH-BR-008 (Account Lifecycle supports PENDING states)

---

## AUTH-BR-089 — PENDING_APPROVAL Blocks Login

**Status:** SOURCE-ALIGNED

A user_account with account_status = 'PENDING_APPROVAL' shall not
be permitted to authenticate. The login service shall reject
authentication attempts for PENDING_APPROVAL accounts with a
generic failure message (per AUTH-BR-075 — Minimize Security
Disclosure).

The rejection message shall not reveal the specific account state.

---

## AUTH-BR-090 — PENDING_APPROVAL to ACTIVE Transition

**Status:** SOURCE-ALIGNED

The transition from PENDING_APPROVAL to ACTIVE occurs only when
a Sakha administrator approves the associated registration_claim:

    1. Admin reviews the registration_claim
    2. Admin verifies claimed details against Sakha records
    3. Admin approves the claim
    4. System creates sangha_sevi record (or links to existing one)
    5. System creates membership_sakha_affiliation record
    6. System sets user_account.account_status = 'ACTIVE'
    7. registration_claim.claim_status = 'APPROVED'

Until step 6, the account remains PENDING_APPROVAL and login is
blocked.

---

# 6. Registration Response

## AUTH-BR-091 — Registration Success Response

**Status:** SOURCE-ALIGNED

Upon successful registration, the system shall return:

    person_pk — internal UUID (for API use)
    person_id — business ID (e.g. P42)

The response shall NOT include:

    sangha_sevi_id — not yet assigned
    any credential or token — no login until approval

The success message shall indicate that the registration is
pending administrative approval. It shall NOT say "You can now
log in."

---

# 7. Approval Workflow

## AUTH-BR-092 — Approval Authority

**Status:** SOURCE-ALIGNED

Registration claims are approved by the administrator(s) of the
Sakha that the registrant claims to belong to. The approving admin
must have admin_scope covering that organization_pk.

---

## AUTH-BR-093 — Rejection Handling

**Status:** SOURCE-ALIGNED

When a registration claim is rejected:

    1. registration_claim.claim_status = 'REJECTED'
    2. registration_claim.reviewed_by_user_account_pk = approving admin
    3. registration_claim.reviewed_at = current timestamp
    4. registration_claim.admin_remarks = reason for rejection
    5. user_account.account_status remains 'PENDING_APPROVAL'

The person retains their person record and user_account. They
may submit a new registration_claim with corrected information.

---

## AUTH-BR-094 — Approval Creates Membership Records

**Status:** SOURCE-ALIGNED

When a Sakha admin approves a registration claim, the system shall:

    1. Generate a new sangha_sevi_id (for new Darshaka members)
       OR verify and link to the existing sangha_sevi record
       (for non-Darshaka members using their Local Sakha Number)

    2. Create or link the sangha_sevi record to the person

    3. Create the membership_sakha_affiliation record linking
       sangha_sevi to the claimed organization

    4. Set user_account.account_status = 'ACTIVE'

This aligns with AUTH-BR-006: the user account does not create
membership. Membership is created by administrative action.

---

# 8. Darshak Attendance

## AUTH-BR-095 — Darshak Attendance Claim

**Status:** PENDING

If the registrant indicates attendance at another Sangha as
Darshak, this information shall be stored in the registration_claim
(darshak_organization_pk field) and processed during approval.

The darshak affiliation record is created only upon claim approval,
not at registration time.

---

# 9. Table Ownership

## AUTH-BR-096 — Registration Claim Table Ownership

**Status:** SOURCE-ALIGNED

The nss.registration_claim table is owned by the Authentication &
Security module. It is a bridge between public registration and
administrative membership approval.

It does NOT belong to the Membership module because:

    - It is part of the account-activation lifecycle
    - It stores pre-verification claims, not verified membership data
    - Its lifecycle is tied to user_account.account_status transitions

---

# 10. Security

## AUTH-BR-097 — Registration Claim Data Visibility

**Status:** SOURCE-ALIGNED

Registration claim data (including claimed_local_sakha_number) is
visible only to:

    - The registrant (their own claim)
    - Sakha administrators with admin_scope for the claimed organization
    - System administrators

It shall not be visible to other registered users or the public.

---

## AUTH-BR-098 — No Lookup Endpoint at Registration

**Status:** SOURCE-ALIGNED

The registration form shall NOT provide a lookup endpoint for
verifying Local Sakha Numbers in real time. The existing
GET /api/v1/register/lookup-sevi endpoint shall be removed or
disabled.

**Rationale:** Under the claim-based model, the registrant
declares their Local Sakha Number and the admin verifies it.
Real-time lookup would allow enumeration of valid Sangha Sevi IDs,
which is a security concern (AUTH-BR-075).

---
