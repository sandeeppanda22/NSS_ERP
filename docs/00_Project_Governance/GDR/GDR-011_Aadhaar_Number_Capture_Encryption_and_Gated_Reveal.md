# GDR-011 — Aadhaar Number Capture, Encryption and Gated Reveal

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-011 |
| Decision Title | Aadhaar Number Capture, Encryption and Gated Reveal |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body (GOV-ROLE-006) |
| Approver | Project owner — **approval pending** |
| Decision Status | Proposed |
| Effective Date | Not yet effective as a decision. The design below is implemented in code (written 2026-11-04) on the project owner's instruction ("implement both: capture the full number, and gate last-4 and the full number behind PERSON_VIEW_SENSITIVE"); it is inert until encryption keys are configured, and no full number can be stored before then. |
| Affected Documents | SOL-PER-003 (Person Business Rules) PER-BR-080/081; SOL-PER-004 (Person Table Design) §49; AUTH/ADMIN permission tables (`PERSON_VIEW_SENSITIVE`); API_CONTRACT; PERSON_API_CONTRACT |
| Related Change Request | N/A |

> **Approval note.** Drafted by the implementation on 2026-11-04 from the project owner's decision to (a) capture the full Aadhaar number, encrypted, and (b) gate `aadhaar_last4` and any reveal of the full number behind `PERSON_VIEW_SENSITIVE`. It is **Proposed**: the owner has not approved the record, and — above all — **the legal position of storing Aadhaar numbers has not been confirmed (§6)**. Nothing here is a legal conclusion. Never change this status on the implementation's own authority.

---

## 1. Background

The `person` table has carried `aadhaar_encrypted` (BYTEA), `aadhaar_hash` (VARCHAR 64) and `aadhaar_last4` (VARCHAR 4), all-or-nothing (`chk_person_aadhaar_consistency`), plus a partial unique index `uq_person_aadhaar_hash`, since the Person design was frozen (SOL-PER-004 §49). No code ever wrote them: no endpoint accepted an Aadhaar number, and `aadhaar_last4` was returned unconditionally in the person detail response (`PersonResponse`), i.e. to any administrator with `PERSON_VIEW`, the person, and any current relative. `PERSON_VIEW_SENSITIVE` ("Access to Aadhaar and other sensitive identity fields") was seeded but unwired. PER-BR-081 requires that sensitive identity data is not unnecessarily exposed through UI, API, reports, URLs, logs or search results.

## 2. Decision

### 2.1 Capture

- Every writer of a person record that can reasonably carry the number accepts an optional `aadhaar_number`: self-registration (`POST /api/v1/register`), admin Create Person (`POST /api/v1/admin/persons`), admin profile correction (`PATCH /api/v1/admin/persons/{pk}`) and the pre-approval claim edit (`PATCH /api/v1/admin/claims/{pk}`). The self-service `PATCH /api/v1/auth/profile` deliberately does **not** (unchanged: Aadhaar stays out of member self-edit).
- The value is the full 12-digit number; spaces and hyphens are stripped. It must be 12 ASCII digits, not start with 0 or 1, and pass the Verhoeff checksum; anything else is HTTP 422. On the PATCH surfaces a blank string clears all three columns to NULL.
- All writers go through ONE function, `api/services/aadhaar_service.py::set_person_aadhaar()`, which derives and stores ciphertext + hash + last-4 together. `aadhaar_last4` is never supplied by a client.
- Duplicates: the existing unique index `uq_person_aadhaar_hash` (one Aadhaar per person) is the only duplicate rule; a clash returns HTTP 409 with a message that does not name the other person. No new rule is invented.
- Optional everywhere: nobody is forced to supply a number; existing last-4-only legacy rows (none are known) are not backfilled.

### 2.2 Encryption scheme (amends SOL-PER-004 §49 "pgcrypto-encrypted" / "SHA-256")

- **Application-side AES-256-GCM** (library `cryptography`), random 96-bit nonce per encryption, associated data = the `person_pk`; the stored blob is `v1:<key_id>:<base64 nonce>:<base64 ciphertext+tag>` in `aadhaar_encrypted`. A blob moved to another person's row, or altered, fails authentication. Application-side rather than pgcrypto so the key never enters the database, its logs or `pg_stat_statements`, and a database dump alone cannot be decrypted.
- **`aadhaar_hash`** = HMAC-SHA256 (hex, 64 chars) of the digits keyed with a pepper that is SEPARATE from the encryption keys (SOL-PER-004 §49 said a bare SHA-256; a bare hash of a 12-digit number is brute-forceable in seconds, so a keyed hash is used). It backs only the uniqueness rule; it is never returned.
- **Keys** live only in the environment, never in the database or repository: `AADHAAR_ENCRYPTION_KEYS` (`key_id:base64-32-bytes` pairs; the first encrypts, later ones decrypt only — rotation), `AADHAAR_HASH_PEPPER`, `AADHAAR_REVEAL_RATE_LIMIT` (default `10/minute`). `scripts/generate_aadhaar_keys.py` prints a fresh pair. The application still starts without them; capturing a number then returns HTTP 503 with a clear message — it never silently falls back to storing only the last four. Rotation = new key id first, old keys kept; a re-encryption script is out of scope. **A lost key makes the stored ciphertext unrecoverable, and a changed pepper orphans every stored hash.**

### 2.3 Who sees what

| Field / endpoint | Visible to |
|---|---|
| `aadhaar_last4` and `aadhaar_full_on_file` in person responses | the person themself; or a holder of `PERSON_VIEW_SENSITIVE` whose admin scope covers the person (NSS_ERP_ADMIN global as elsewhere; the permission alone never confers global reach). Everyone else — ordinary administrators, current relatives, the Auditor (grant revoked, see §2.6) — receives `null`. One shared helper (`person_scope.gate_aadhaar_fields`) applies this to every response that carries the fields. |
| `GET /api/v1/person/persons/{pk}/aadhaar` (full decrypted digits) | `PERSON_VIEW_SENSITIVE` **and** admin scope over the person. The person themself does **not** receive the full number (masked last-4 only). 404 "Full Aadhaar not on record" when there is no ciphertext. Per-user rate limit. |
| `aadhaar_encrypted`, `aadhaar_hash` | nobody, through any endpoint, ever. |

PER-BR-081 ("the ciphertext and hash are never returned") therefore remains true for the columns; the reveal endpoint returns the **decrypted number**, never the ciphertext or the hash. This **amends** PER-BR-081's "no unnecessary exposure": the full number is now deliberately obtainable by an authorised, scoped, audited reveal (and nowhere else).

### 2.4 Audit

- Each successful reveal writes a `system_event_log` row (`action = VIEW_SENSITIVE`, table `person`, record = the person, actor = the revealer) whose summary and detail carry **no value**. A decryption failure fails the request with HTTP 500 and no value, and logs an ERROR (person, exception type, acting account; never a value). No failure audit row is written, because the write dependency rolls the transaction back on the 500.
- The generic DB audit trigger would otherwise copy the Aadhaar columns into `field_change_log` and the `system_event_log` detail. `database/ddl/01_foundation/15_audit_trigger.sql` (v1.4, idempotent `CREATE OR REPLACE`, re-applied by every build) now **redacts** `person.aadhaar_encrypted`, `aadhaar_hash` and `aadhaar_last4`: the change is logged (field, action, actor, time, and whether a value was set or cleared) but the value is the literal `[REDACTED]`. This is a redaction, not an exclusion; recorded in `CROSS_MODULE_PRINCIPLES.md` §7.1.

### 2.5 Retention

No change to "history is never hard-deleted": a cleared number sets the three columns to NULL (the redacted audit rows record that it was cleared, not what it was). No retention period, purge or crypto-shredding policy is defined — owner/compliance question (§6).

### 2.6 Permission footprint

`PERSON_VIEW_SENSITIVE` stays granted to `NSS_ERP_ADMIN` and `NSS_ERP_KENDRA_ADMIN`. The seed description said "ADMIN + KENDRA + AUDITOR only"; the Auditor's grant is **soft-deleted** by `database/seed/00_bootstrap/07_person_view_sensitive_auditor_revoke_patch.sql` (idempotent; the existence-gated base seed still inserts the row on a fresh build and the patch, which runs after it in every build, withdraws it — the same arrangement as the Assets & Property revoke patch), so the Auditor sees no Aadhaar data. Re-grant is a one-row data change if the owner wants it (an Auditor would then still need admin scope for any non-self reveal).

## 3. Rules affected

| Rule | Effect |
|---|---|
| PER-BR-080 | Unchanged — access still goes through the common authentication/RBAC framework. |
| PER-BR-081 | Amended as in §2.3: the columns `aadhaar_encrypted`/`aadhaar_hash` are never returned; the decrypted number is returned only by the gated, audited reveal; last-4 is gated rather than universal. |
| SOL-PER-004 §49 | Amended: encryption is application-side AES-256-GCM (not pgcrypto) and the hash is HMAC-SHA256 with a separate pepper (not bare SHA-256). Columns, CHECKs and the unique index are unchanged — no DDL change. |

## 4. Alternatives Considered

- **pgcrypto symmetric encryption in SQL (as SOL-PER-004 §49 wording suggests).** Rejected: the key would travel in SQL text (logs, `pg_stat_statements`) and sit next to the data.
- **A bare SHA-256 hash.** Rejected: only 10^9 plausible numbers (Verhoeff-valid, 12 digits); brute force is instant. HMAC with a secret pepper makes a stolen hash column useless without the pepper.
- **Capturing only the last four digits (status quo) and masking everyone else.** Rejected by the owner: the full number is wanted.
- **Letting the person see their own full number.** Not adopted: a stolen session would then expose it; the person sees masked last-4 only.
- **Returning the number in every person response to authorised admins.** Rejected: reveal is an explicit, rate-limited, audited action.
- **Storing the key in the database / per-person keys.** Rejected: environment-held keys keep a database compromise from yielding numbers.

## 5. Impact Assessment

- New: `api/services/aadhaar_service.py`, `scripts/generate_aadhaar_keys.py`, endpoint `GET /api/v1/person/persons/{pk}/aadhaar` (1 route; 284 in total), request field `aadhaar_number` on four writers, response fields `aadhaar_last4` (now gated) and `aadhaar_full_on_file` on `PersonResponse` and the admin `PersonProfileResponse`, config `AADHAAR_ENCRYPTION_KEYS` / `AADHAAR_HASH_PEPPER` / `AADHAAR_REVEAL_RATE_LIMIT`, dependency `cryptography` (installation on the Render Python 3.15.2 pin is **unverified**).
- No table/column change. Changed: `15_audit_trigger.sql` (redaction; re-applied each build), the Auditor revoke patch.
- The frontend (admin Create/Edit Person, registration form, claim edit, person card, a "Reveal Aadhaar" action) is a separate piece of work.

## 6. Open Questions (owner decisions needed)

1. **Legal / compliance (blocking before go-live).** Storing and displaying Aadhaar numbers is regulated in India (the Aadhaar Act and its regulations, UIDAI's storage/masking/usage circulars, and the Digital Personal Data Protection Act, 2023). This record draws **no legal conclusion**. The owner must obtain compliance/legal confirmation that NSS may collect and store the full number, on what basis and with what notice/consent text, whether the number may be collected at all from a public self-registration form, and whether an **Aadhaar Data Vault** (or a tokenised/reference-key arrangement) is required instead of, or in addition to, application-side encryption.
2. Key management: who holds the key and pepper (a Render secret, a KMS), who may rotate, backup/escrow so a lost key does not destroy the data, and whether an HSM/KMS-backed envelope scheme is wanted instead of an environment variable.
3. Retention/erasure: how long a number is kept, whether erasing a person means clearing it (NULL, as implemented) and whether crypto-shredding of audit rows is needed (audit rows hold no value).
4. Consent/notice: wording shown at registration and who may enter a number on someone else's behalf (admin Create/Edit).
5. Duplicate disclosure: the 409 on a duplicate number confirms that the number is already on record, which on the public registration form is a small enumeration oracle (global rate limit applies). Accept, or return a neutral message?
6. Whether changing/clearing an existing number should require `PERSON_VIEW_SENSITIVE` (today it follows the existing profile-edit gates: `ADMIN_USER_MANAGE`/`PERSON_MANAGE` in scope, `MEMBERSHIP_APPROVE`/`ADMIN_USER_MANAGE` for claim edit).
7. Whether the Auditor (grant revoked, §2.6) or any other role should view last-4.
8. Whether a re-encryption/rotation script and a backfill of legacy last-4-only rows are wanted (neither is written).
9. `field_change_log`/`system_event_log` rows already holding `person.aadhaar_*` values: none are expected (no writer existed); the owner should confirm on the live DB before the first capture.

## 7. Approval

**Pending.** Record the approver, date and reference here when the project owner (or the NSS Governing Body) decides, after the §6.1 legal confirmation; on approval change the Decision Status to `Approved`, set the Effective Date and add the date to the index in `GDR/README.md`.

---

# End of Document
