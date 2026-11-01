# GDR-009 — Legacy Members Supply Their Existing Local Sakha Number; All Others Are Auto-Numbered

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-009 |
| Decision Title | Legacy Members Supply Their Existing Local Sakha Number; All Others Are Auto-Numbered |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body (GOV-ROLE-006) |
| Approver | Project Steering Committee |
| Decision Status | Proposed |
| Effective Date | TBD (on ratification; implementation already in the working tree as of 2026-11-01) |
| Affected Documents | SOL-AUTH-006 (AUTH-BR-085, AUTH-BR-086, AUTH-BR-087), SOL-AUTH-007 (registration_claim table design), SOL-MEM-004 (MBR-030, MBR-030A, MBR-030C, MBR-030H, MBR-048), API_CONTRACT |
| Related Change Request | N/A (owner-directed decision, 2026-11-01) |

> **Ratification flag.** This decision was directed by the project owner on 2026-11-01 and is recorded here per GDR-001 (GDR-DEC-001). GDR-001 and GOV-ROLE-006 place final decision authority with the NSS Governing Body; no evidence of that body's approval is available in the repository, so Decision Status is `Proposed`, not `Approved`. Advance it to `Approved` (and then `Implemented`) only once the NSS Governing Body / Project Steering Committee ratification is confirmed, and record that in this document.

---

## 1. Background

AUTH-BR-086 made the Local Sakha Number REQUIRED for every non-Darshaka registration claim and OPTIONAL for Darshaka, while MBR-030/MBR-030C/MBR-048 describe the number as auto-generated at enrollment, with an explicit number retained only for legacy-register import. The two did not line up: a brand-new Regular member (who has no card yet) was forced to invent a number, and a legacy Darshak could not be distinguished from a new one. Whether the number is typed or generated was inferred from whether a number happened to be present.

## 2. Decision

1. **Legacy vs new.** A person who was ALREADY a member — Regular/Associate or Darshak/Darshaka — before this application existed is a **legacy member** and MUST provide the existing Local Sakha Number printed on their card. Anyone who is not a legacy member has the Local Sakha Number **auto-generated** by the system: the next number in the Regular/Associate series, or in the Darshak series of that Sakha (MBR-030C), from the shared allocator `nss.fn_next_sakha_local_number()`.
2. This applies to both membership families, and to self-registration claims **and** to admin-created members (Create User / Create Sangha Sevi).
3. **Explicit indicator.** Legacy status is an explicit boolean, never inferred from "a number was typed": `registration_claim.is_legacy_member`, and the same field on the admin create requests. A number sent with `is_legacy_member = false` is a clear 422 (a client/flag mismatch is caught, not ignored); `is_legacy_member = true` without a number is a 422; a legacy number already used in that Sakha is a 409.
4. **Attending another Sakha.** The cross-Sakha Darshak attendance affiliation (claim approval) follows the same rule *at the attended Sakha*: a legacy attendee supplies their existing Darshak number there, otherwise the system allocates the next number in that Sakha's Darshak series. Legacy status is therefore **per Sakha**: it is stored separately as `registration_claim.darshak_is_legacy_member` (a person can be a legacy home-Sakha member and a new attendee elsewhere, or the reverse). The previous silent `ON CONFLICT DO NOTHING` is replaced: the affiliation is skipped only when the member already has an OPEN affiliation at that Sakha; any other collision is a 409 that rolls the whole approval back.
5. **Admin verifies.** The admin verifies the flag(s) and number(s) at approval and may correct them through the existing claim edit (`PATCH /admin/claims/{pk}`), where flag and number are validated together; on admin creation the admin is the one supplying them.
6. **One rule, one validator.** `api/helpers.py::resolve_legacy_local_number()` (via `validate_claim_local_numbers()` for claims) is the single implementation, called by registration, the register-claim endpoint, claim PATCH/approval, admin `create_user`/`create_sangha_sevi`, and `ensure_darshak_attendance_affiliation()` takes its already-validated result.

## 2A. Decision (extension, 2026-11-01): the Parichaya / Anumati Patra Number

The same split applies to the card ("Kendra") number, driven by the SAME flag (`is_legacy_member` — a person who already holds a card is by definition already a member, so no second flag or column is added):

1. **Legacy** — MUST supply the number printed on the existing card, strictly `<seq>/<yyyy>/<yyyy+1>` (MBR-030A): positive whole number with no leading zeros, two four-digit consecutive years, first year 2000..current year. The year may be any previous or the current one (it is NOT pinned to an issue date as MBR-030H pins a newly issued Patra). Stored as given; a number already issued is a 409. A legacy Darshaka supplies their Anumati Patra number the same way (Associate: Parichaya, no Anumati).
2. **Everyone else** — supplies none (422 if sent); the number is auto-minted at claim approval or admin creation. Every member holds exactly one credential — an Anumati Patra (Darshaka) or a Parichaya Patra (Regular/Associate) — so none is ever left without one. The card's issue date and validity are pinned to Dola Purnima (FC-DECISION-01): `issue_membership_credential()` uses the most recent confirmed Dola Purnima for a Parichaya Patra, and a missing confirmed date blocks issuance with the existing 422. The Parichaya requirement at registration is removed for a new member.
3. **Numbering rule (unchanged, MBR-030A):** one Kendra-wide counter for the Parichaya Patra (NSS-unique), one counter per Sakha for the Anumati Patra, resetting each year. Because a legacy member may hold a number from the current year, the allocator skips any existing candidate (never reusing or duplicating a number), as `fn_next_sakha_local_number()` does — needed because minting must never collide with a legacy member's number.
4. **One validator (and one enrolment step):** `api/helpers.py::resolve_legacy_patra_number()` (format via `parse_legacy_patra_number()`, uniqueness via `patra_number_exists()`), called by registration, `/register/claim`, claim PATCH and approval, admin `create_user`/`create_sangha_sevi`; `issue_credential_at_enrolment()` is the single enrolment-time credential step for claim approval and both admin creates (legacy number recorded, else minted) and calls `issue_membership_credential(is_legacy=True)` to record the validated number. The admin verifies at approval or corrects through claim edit; the admin forms show the Patra number only when "Legacy member" is ticked.
5. The invariant "every active, non-system member holds an ACTIVE credential of the type their membership type requires" is checked by a `03_validate` WARN (no DB trigger, no backfill). No schema change: the existing column `registration_claim.claimed_credential_document_number` is simply governed by the flag. The agreement is application-level (no CHECK) because pre-existing rows may carry a number without the flag; such a claim 422s at approval until corrected.

## 2B. Decision (extension, 2026-11-01): a Darshaka has no cross-Sakha attendance

The attendance-Sakha affiliation of §2 item 4 (and `Apply for Darshak`, MBR-049) applies **only to Regular and Associate members**. A Darshaka (PROBATIONARY) who attends or moves to another Sakha makes that Sakha his home Sakha — he must do a Sakha Transfer (MBR-048); he cannot hold a second, Darshak-series attendance affiliation. Refused with 422 ("A Darshaka who attends another Sakha must transfer to it; use Sakha Transfer") in registration (`POST /register`, `/register/claim`), claim edit (the stored attendance Sakha of a Darshaka claim is cleared by the edit, supplying one is a 422) and approval, and the `DARSHAK` change request (at filing and at destination acceptance); the register form hides the attendance section for a Darshaka and the dashboard hides the Apply for Darshak button. Shared check: `helpers.require_non_darshaka_for_attendance()`. Regular/Associate attendance affiliations are unchanged. Read-only displays that join an attendance affiliation (member/org Darshak summary, attendance roster) are left as is.

## 3. Rationale

A person who holds a number on a card must keep that number (Local Sakha Numbers are never reassigned — MBR-030C); a person who does not should not be asked for one, and must not be able to choose their own. Making the status an explicit, audited fact removes the guesswork and lets the approver see exactly what was claimed.

## 4. Alternatives Considered

- **Infer legacy from "a number was supplied".** Rejected: indistinguishable from a typo or a guessed number; no way to tell the approver what the registrant meant.
- **A single legacy flag for the claim.** Rejected: legacy status differs per Sakha (home vs attended).

## 5. Impact Assessment

- Amendment notes on SOL-AUTH-006 (AUTH-BR-085/086/087), SOL-AUTH-007 and SOL-MEM-004 (MBR-030, MBR-030C, MBR-048).
- Schema: two NOT NULL BOOLEAN columns (default FALSE) and two agreement CHECKs on `nss.registration_claim`; carried to existing databases by the idempotent patch `database/ddl/06_authentication/06_registration_claim_legacy_member_patch.sql` (existing claims: legacy iff they already carry a number). No backfill of members.
- API: `is_legacy_member` / `darshak_is_legacy_member` on `POST /register`, `POST /register/claim`, claim detail/PATCH, and `is_legacy_member` on `POST /admin/users` and `POST /admin/sangha-sevi`. Breaking for clients that send a number without the flag.
- Patra number (§2A): no schema change. Breaking for clients that send a Patra number without `is_legacy_member = true`, and for clients that relied on it being required for a new Regular member. Admin create requests now require `credential_document_number` for a legacy member and reject it otherwise.
- Not changed: the member-initiated Sakha Transfer / Apply for Darshak change request keeps its own `is_legacy_import` flag (same shape, MBR-048); the MBR-030H entry rules on the promote endpoint and admin correction.

## 6. Open Questions

None outstanding. (The earlier question whether a new Regular/Associate registrant must supply a Parichaya Patra number is resolved by §2A: no, it is auto-generated.)

## 7. Approval

Recorded under GDR-001; approval pending per the Ratification flag above.

---

# End of Document
