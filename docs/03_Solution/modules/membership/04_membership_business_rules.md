# NSS ERP — Membership Business Rules

---

## Document Metadata

| Item | Value |
|---|---|
| Document Name | Membership Business Rules |
| Document ID | SOL-MEM-004 |
| Domain | Membership |
| Repository Path | docs/03_Solution/modules/membership/04_membership_business_rules.md |
| Version | 1.1.0 |
| Status | Draft — Governance Aligned |
| Authority | NSS ERP Membership Module |
| Parent Document | 01_membership_module_overview.md |
| Related Documents | 02_membership_erd.md, 03_membership_lifecycle.md, 05_membership_table_design.md |
| Effective Date | TBD |

---

# 1. Purpose

This document defines the business rules governing the NSS ERP Membership Module.

These rules translate approved NSS Membership principles and authoritative Bye-Law provisions into ERP implementation requirements.

Where an authoritative NSS Bye-Law conflicts with an ERP rule, the authoritative Bye-Law shall prevail.

---

# 2. Membership Identity Rules

## MBR-001 — Person Is Not Membership

A Person record shall not automatically create a Membership.

```text
Person is not equal to Member
```

A Person may exist without Membership.

---

## MBR-002 — Membership Requires Person

Every Membership shall belong to exactly one Person.

A Membership shall not exist without a Person.

---

## MBR-003 — One Person One Membership

A Person may have only one active Membership identity.

```text
One Person
    |
One Membership
```

---

## MBR-004 — Sangha Sevi ID

Every Membership shall have one Sangha Sevi ID.

The Sangha Sevi ID shall be:

* System generated.
* Globally unique.
* Permanent.
* Never reused.
* Never changed.

---

## MBR-005 — Membership Identity Preservation

Membership identity shall remain unchanged throughout Membership lifecycle events unless an authoritative rule explicitly requires otherwise.

---

# 3. Membership Type Rules

## MBR-006 — Official Membership Types

The Membership Type master shall support:

```text
PROBATIONARY
REGULAR
ASSOCIATE
```

These correspond to the official NSS Bye-Law categories.

---

## MBR-007 — Darshak Is Not Membership Type

DARSHAK shall not be stored as a Membership Type.

The operational Darshak concept is defined separately by:

```text
DARSHAK_BUSINESS_RULE.md
```

In the portal UI, a Probationary Member shall be displayed as
**"Darshaka"**. This is an operational/UI label only — the database
stores `PROBATIONARY`. The mapping is:

```text
Database value:  PROBATIONARY
Portal display:  Darshaka
```

---

## MBR-008 — Full Member Terminology

FULL_MEMBER shall not be used as the authoritative database Membership Type.

The official ERP value is:

```text
REGULAR
```

---

# 4. Probationary Membership Rules

## MBR-009 — Probationary Enrollment

A Person may be enrolled as a Probationary Member after satisfying the applicable authoritative qualifications and enrollment process.

---

## MBR-010 — Anumati Patra

A Probationary Member shall be associated with an Anumati Patra according to the applicable NSS process.

The Bye-Law states that an enrolled Probationary Member is issued an Anumati Patra.

When a Probationary Member progresses to Regular Membership, their
Anumati Patra record shall be preserved with `EXPIRED` status. The
historical Anumati Patra remains visible in the member's credential
history alongside any subsequent Parichaya Patra.

CROSS-REFERENCE (SOL-ARCH-013 FC-DECISION-01, 2026-10-01): the Anumati
Patra's `valid_from`/`valid_to` are Dola-Purnima-based (the membership
year runs Dola Purnima to the following Dola Purnima), resolved via
`next_festival_date_on_or_after()` in `issue_membership_credential()`
(`api/helpers.py`) — not the financial year used for `document_number`.

---

## MBR-011 — Probationary Duration

The normal progression to Regular Membership requires the prescribed Probationary period.

SOURCE-DERIVED (Bye-Law §B(b), REF-002-003) — Regular Membership lists two
qualifying clauses:

- (i) continued as a Probationary Member of any Sakha Sangha (including Mahila
  Sanghas) holding a valid Anumati Patra **at least for a period of one year**;
- (ii) on recommendation of the Sakha, **undergone training for at least one
  year** under the guidance of the Kendra Sangha.

ARCHITECTURAL INTERPRETATION (confirmed by NSS practice) — clauses (i) and
(ii) describe **one concurrent year, not two consecutive years.** The training
under Kendra Sangha guidance is conducted *within* the same Probationary year;
it is not a second year served after probation ends. The prescribed
normal-route minimum tenure is therefore **one year in total**, counted from
Probationary enrollment / Anumati Patra validity start.

The clauses are worded separately in the source and could be read literally as
a ~2-year cumulative requirement. That literal reading is **rejected**: NSS
operates it as a single year satisfying both conditions. Any future tenure
check must use a one-year floor.

Completing the one-year minimum does **not** itself trigger conversion — see
MBR-011A. The one year is a floor, not a trigger.

---

## MBR-011A — Dola Purnima as the Regular Enrollment Date

Regular enrollment via the normal progression route (MBR-013) does not happen
continuously as individual Probationary Members complete their one-year
Probationary-plus-training period (MBR-011). It is batched annually to
**Dola Purnima** — the same annual
reference date NSS already uses for the membership renewal deadline (no grace
period) and for Membership Transfer's effective date (MBR-029).

A Probationary Member who has completed the prescribed period (MBR-011,
MBR-013) **before** the upcoming Dola Purnima converts to Regular, and
receives their Parichaya Patra, on that Dola Purnima. A Probationary Member
who completes the prescribed period **after** a given Dola Purnima has
passed must wait for the **next** occurrence of Dola Purnima — completing
the requirement mid-year does not advance or shortcut the conversion date.

This does not apply to Direct Regular Enrollment (MBR-015), which the
Parichalak may grant at any time, independent of Dola Purnima.

ARCHITECTURAL NOTE: Dola Purnima is a lunar-calendar (Phalguna Purnima)
festival date that shifts every Gregorian year — it cannot be computed from a
fixed month/day formula. It is now represented in the schema via
`nss.festival_master` / `nss.festival_calendar_date`
(**SOL-ARCH-013**, APPROVED 2026-10-01 —
`docs/03_Solution/architecture/FESTIVAL_CALENDAR_ARCHITECTURE.md`), with the
observed date entered and confirmed by an administrator (NSS_ERP_ADMIN only —
OPEN-FC-03), never computed. The resolver primitives
`festival_date_for_year()` / `next_festival_date_on_or_after()`
(`api/helpers.py`) are this rule's date source, along with the renewal
deadline (MBR-030A-adjacent) and the Membership Transfer effective date
(MBR-029) — the same two sibling rules named in the prior version of this
note. Seed dates for 2024–2028 are recorded per FC-DECISION-02; 2027 is
seeded as provisional (`is_confirmed = FALSE`) pending Kendra Sangha
confirmation.

---

# 5. Regular Membership Rules

## MBR-012 — Regular Membership

Regular Membership is the full-fledged Membership category defined by the NSS Bye-Law.

---

## MBR-013 — Normal Regular Progression

The normal progression is:

```text
Probationary
    |
Required Period — one year, with Training conducted within it (MBR-011)
    |
Sakha Recommendation
    |
Regular  (conversion date = next Dola Purnima — see MBR-011A)
```

The Bye-Law's two Regular-Membership clauses — one year as a Probationary
Member holding a valid Anumati Patra, and one year of training under Kendra
Sangha guidance on the Sakha's recommendation — are satisfied **concurrently
within a single year**, not across two consecutive years (see MBR-011 for the
source text and the interpretation). Reaching that one-year milestone makes a
member *eligible*; actual Regular enrollment and Parichaya Patra issuance
occurs on the next Dola Purnima per MBR-011A, not immediately on eligibility.

---

## MBR-014 — Parichaya Patra

A Regular Member or Associate Member shall be associated with a Parichaya Patra according to the applicable NSS process.

The Bye-Law section (d) Cessation of Membership states that membership
ceases on non-renewal of "the Annual Parichaya Patra (Identity Card)
or Anumati Patra (Admit Card) as the case may be." This applies to
all membership types that hold a Parichaya Patra — Regular and
Associate.

CROSS-REFERENCE (SOL-ARCH-013 FC-DECISION-01, 2026-10-01): the Parichaya
Patra's `valid_from`/`valid_to` are Dola-Purnima-based (the renewal
deadline this rule's "Annual" cessation clause refers to), resolved via
`next_festival_date_on_or_after()` in `issue_membership_credential()`
(`api/helpers.py`) — not the financial year used for `document_number`
(MBR-030A, unchanged). Gruhasana (Paribarik Asana) inherits this window
rather than carrying an independent one (ORG-BR-094).

---

## MBR-015 — Direct Regular Enrollment

The ERP shall support direct Regular enrollment where authorized by the Parichalak under the Bye-Law.

The direct-enrollment path shall be recorded as a Membership journey event.

---

# 6. Associate Membership Rules

## MBR-016 — Associate Membership

Associate Membership is an independent official Membership category.

---

## MBR-017 — Associate Enrollment Authority

Associate Membership may be enrolled by the Parichalak suo motu or on recommendation of a Sakha Sangha, subject to the applicable NSS rules.

---

## MBR-018 — Associate Participation

Associate Members may attend functions of Sakha Sanghas and the Kendra Sangha according to the Bye-Law.

---

## MBR-019 — Associate Governance Restrictions

Associate Members shall not be granted governance rights beyond those permitted by the authoritative NSS rules.

The ERP shall derive governance eligibility from the Governance Module rather than assuming that Membership alone grants governance authority.

---

## MBR-019A — Associate Parichaya Patra

An Associate Member shall be issued a Parichaya Patra (Identity Card)
upon enrollment. The Bye-Law's cessation clause (section (d)) applies
the Parichaya Patra renewal requirement to Associate Members.

**Source:** NSS Bye-Law, section (d) Cessation of Membership — "non-renewal
of the Annual Parichaya Patra (Identity Card) or Anumati Patra (Admit Card)
as the case may be."

---

## MBR-019B — Associate Members Do Not Receive Anumati Patra

An Associate Member shall NOT be issued an Anumati Patra. The Anumati
Patra is exclusive to Probationary Members per the Bye-Law.

Associate Members are enrolled directly (no probationary period),
therefore the Anumati Patra pathway does not apply.

**Credential matrix by type:**

| Membership Type | Anumati Patra | Parichaya Patra |
|-----------------|---------------|-----------------|
| PROBATIONARY    | Yes (ACTIVE)  | No              |
| REGULAR         | Depends on admission path — see MBR-019C | Yes (ACTIVE) |
| ASSOCIATE       | No            | Yes (ACTIVE)    |

---

## MBR-019C — Darshaka Stage Is Not Mandatory for Kishor/Kumari-Origin Regular Members

For a non-youth applicant, enrollment as a Probationary/Darshaka member
is mandatory before promotion to Regular. A Darshaka holds an Anumati
Patra that expires on promotion, so these Regular members always carry
a historical EXPIRED Anumati Patra.

For an applicant who came up through Kishor Puja participation or
Kumari Sangha membership, the Darshaka stage is optional: the
sanctioning Sangha President may admit them directly to Regular
membership. In that case no Anumati Patra — active or historical —
exists for that member at all.

Consequently, "a Regular member has a historical EXPIRED Anumati
Patra" is true for members who came up through the Darshaka pathway,
but not universally true for every Regular member — Kishor/Kumari-origin
members admitted directly are a legitimate exception.

**Rule maturity:** ERP-OPERATIONAL

---

# 7. Membership Status Rules

## MBR-020 — Type and Status Separation

Membership Type and Membership Status shall be maintained independently.

Example:

```text
Membership Type:
REGULAR

Membership Status:
ACTIVE
```

---

## MBR-021 — Status History

Every Membership status transition shall be recorded historically.

---

## MBR-022 — No Physical Deletion

Membership records and historical status records shall not be physically deleted.

---

# 8. Renewal Rules

## MBR-023 — Renewal Identity

Membership renewal shall not create a new Sangha Sevi ID.

---

## MBR-024 — Renewal History

Every approved renewal shall be preserved in Membership renewal history.

---

## MBR-025 — Renewal Request

A renewal request shall be separately identifiable from the final renewal history.

---

## MBR-026 — Renewal Status

The ERP shall support a controlled renewal workflow.

The exact renewal dates and deadline rules shall follow the approved NSS Membership Renewal rules and applicable authoritative references.

---

# 9. Transfer Rules

## MBR-027 — Transfer Identity

Membership transfer shall not change the Sangha Sevi ID.

---

## MBR-028 — Transfer History

Every Membership transfer shall be recorded in:

```text
membership_transfer_history
```

---

## MBR-029 — Transfer Effective Date

The approved Membership Transfer workflow establishes Dola Purnima as the effective date of transfer.

---

## MBR-030 — Local Sakha ERP Number (ERP Number)

A Member may receive a new Local Sakha ERP Number following transfer.

The Local Sakha Number and ERP Number are the same identity — these are
two names for a single concept.

```text
Local Sakha Number = ERP Number
```

The Local Sakha ERP Number is scoped to the member's recognized/base Sakha
and is **auto-generated** by the system at enrollment or transfer:

```text
Format:  <Sakha Short Code><sequence>
Example: ESS1192 (Ekamra Sakha), CTC42 (Cuttack Sakha)
```

The local number is not the global Membership identity. The global
identity is the Sangha Sevi ID (Tier 1).

Stored on: `membership_sakha_affiliation.local_sakha_erp_id`

---

## MBR-030A — Kendra Number

A Regular Member's Parichaya Patra carries a Kendra Number as the
`document_number`.

```text
Format:  <number>/<financial_year_start>/<financial_year_end>
Example: 345/2026/2027
```

The Kendra Number is the Kendra Sangha's own registration reference
for the member.

The Kendra Number does not change on Sakha transfer.

Stored on: `parichaya_patra.document_number`

CROSS-REFERENCE (SOL-ARCH-013 FC-DECISION-01, 2026-10-01): this
financial-year numbering is explicitly UNCHANGED and stays decoupled from
`valid_from`/`valid_to`, which moved to a Dola-Purnima basis (MBR-014).
`next_credential_document_number()` (`api/helpers.py`) now returns only
`document_number`; validity dates come from
`dola_purnima_credential_validity_window()` instead.

---

## MBR-030H — Patra Number Entry, Year Normalization and Admin Correction

AUTHORITY: user decision, 2026-10-03. SUPERSEDES the 2026-10-01 note
"no one, legacy or new, is ever asked to supply a year", which is hereby
retired. Applies identically to **Parichaya Patra** and **Anumati Patra**.

Nobody is ever *required* to type a year. Whoever enters a Patra number —
member, Sangha Sevi, or admin, at registration, claim approval, or member
creation — may type either form:

```text
Number only       1              -> stored as 1/2026/2027
Number with year  1/2026/2027    -> validated, then stored as given
```

### Year pair derivation

The authoritative year pair is derived from the Patra's **issue date**:

```text
year_pair = <issue_date.calendar_year>/<issue_date.calendar_year + 1>
```

A Patra issued any time in 2026 — including a March 2026 Dola Purnima —
carries `2026/2027`. This is deliberate: a March-issued Parichaya Patra
opens the INCOMING membership year, not the outgoing financial year its
March date happens to fall in.

### Entry rules

1. **Number only** — the backend appends the derived year pair. No error.
2. **Number with a year pair** — the supplied years MUST equal the derived
   year pair. On mismatch, REJECT with a message naming the expected year,
   so the entrant can supply that year's Patra number instead. Never
   silently rewrite a supplied year.
3. **Number omitted entirely** — unchanged behaviour: auto-mint the next
   sequence number for the scope and financial year (MBR-030A).
4. A supplied number is **trusted as typed** — it is not replaced by the
   counter's next value. Correctness of a supplied number is the
   *approving admin's* responsibility (see below). Genuine duplicates are
   still refused by the uniqueness constraint.

### Admin correction

A Patra number is correctable after issuance, by admin only. The
correcting admin supplies a replacement number subject to the same two
entry rules above. Every correction is audit-logged with the old and new
value. No other role may change an issued Patra number.

Stored on: `parichaya_patra.document_number`,
`anumati_patra.document_number`

---

## MBR-030B — Three-Tier Identity Summary

Every NSS Member is identified by three distinct identity tiers:

```text
Tier 1: Sangha Sevi ID          — NSS-wide, permanent
Tier 2: Local Sakha ERP Number  — Sakha-scoped (= ERP Number)
Tier 3: Kendra Number           — via Parichaya Patra document_number
```

Only Tier 2 (Local Sakha ERP Number) changes on transfer.

---

## MBR-030C — Local Sakha Numbering Is Namespace-Separated by Membership State

**Status:** FROZEN (format and no-reuse rule) — AUTO-SEQUENCING RESOLVED (see "Numeric portion"
below and MBR-048)

Tier 2 Local Sakha numbering is separated into two namespaces within the same
Sakha, distinguished by a state marker placed after the Sakha short code:

```text
Regular / Associate:     <SakhaShortCode><Number>          e.g. ESS000123
Darshak / Probationary:  <SakhaShortCode><Marker><Number>  e.g. ESSD000045
```

The marker is a configured value, not a literal embedded in code. It is stored
as the `MEMBERSHIP_DARSHAK_LOCAL_ID_MARKER` row in `nss.system_setting` and is
seeded with `D`. Composition must read it from configuration; no module may
hardcode the marker. Where the marker is absent from configuration, ID
composition shall fail loudly rather than fall back to a default, because a
silently empty marker would compose a Darshak identifier inside the Regular
namespace and collide.

### Why namespaces rather than a type-discriminated counter

Because the marker is part of the identifier string, `ESS000001` and
`ESSD000001` are already distinct values. The two namespaces therefore coexist
without any change to the existing uniqueness constraints:

```text
uq_mem_sakha_aff_local_id   UNIQUE (organization_pk, local_sakha_erp_id)
uq_dar_att_reg_local_number UNIQUE (attending_organization_pk, darshak_local_number)
```

Both constraints remain correct and unmodified. The "same number held by a
Regular and a Darshak" case is expressed as two different identifiers, not as
one identifier permitted twice.

### Numeric portion

The numeric portion is Sakha-local and independently sequenced per namespace.
`ESS` and `ESSD` advance on separate counters, so `ESS000004` and `ESSD000004`
may both exist in the same Sakha and refer to different members.

**RESOLVED (MBR-048):** per-Sakha, per-namespace counter infrastructure now exists —
`nss.sakha_local_number_counter` (`database/ddl/05_membership/17_sakha_local_number_counter.sql`),
one row per (`organization_pk`, `namespace`), incremented atomically by
`api/helpers.py::next_sakha_local_number()`. Unlike `nss.id_sequence_master` (global counters)
or `nss.credential_sequence_counter` (resets every financial year), this counter is permanent
and per-Sakha-per-namespace, matching the "never reassigned" rule above. Auto-generation is the
default path: `api/helpers.py::insert_sakha_affiliation()` calls it whenever a caller omits an
explicit `local_number`. A caller MAY still supply an explicit number — this is retained
deliberately for legacy-register-import cases (a paper-register number predates the ERP and must
be preserved verbatim), exposed at the API layer as an explicit admin choice
(`is_legacy_import`), never as a silent fallback.

### Progression and archival

Promotion from Probationary to Regular issues a new Regular-namespace
identifier and archives the Darshak-namespace one:

```text
ESSD000045  ──(Parichaya Patra issued)──▶  ESS000123
   │
   └── archived (registration_status / affiliation_status = ARCHIVED),
       never deleted, never reassigned to another person
```

An archived Darshak identifier shall never be reissued to a different person,
even after the original holder becomes a Regular Member (MBR-022, ADMIN-BR-066).

### Identity anchoring

The Darshak-namespace identifier is **not** a second permanent identity. It is
a local Sakha identifier scoped to the Darshak state. The permanent identity
anchor remains the Sangha Sevi ID (MBR-004), which does not change on
promotion, transfer, or archival:

```text
One Person → One Sangha Sevi ID → a lifecycle of local Sakha identifiers
```

This preserves MBR-003 (One Person One Membership) and MBR-004. No separate
permanent probationer identity namespace is created at Tier 1.

### Visiting Regular Members

A Regular Member of one Sakha attending another Sakha as a Darshak receives a
Darshak-namespace identifier from the attending Sakha, recorded on
`darshak_attendance_registration.darshak_local_number`. The member's home-Sakha
Regular identifier is unaffected, and both trace to the same Sangha Sevi ID:

```text
SS00007891 ─┬─ ESS00231   home Sakha, Regular membership identity
            └─ ESSD000087 attending Sakha, Darshak attendance identity
```

This makes the attendance context readable from the identifier alone, which is
the operational distinction MBR-007 requires without storing "Darshak" as a
membership type.

**PENDING — known nonconformance.** The registration-claim approval path
currently writes the member's *Sangha Sevi ID* into the Tier 2 column for a
Darshak attendance affiliation, rather than a Darshak-namespace local
identifier. It also does so under `ON CONFLICT DO NOTHING`, which silently
discards the row on collision. Both behaviours predate this rule and are left
unchanged here because issuing a conforming `ESSD` identifier requires the
per-Sakha namespace counter recorded as PENDING above. This rule now defines
the target state; the gap is explicit rather than implied.

---

## MBR-031 — Transfer History Preservation

Previous Sakha association shall remain historically traceable.

---

## MBR-048 — Membership Change Request Workflow (Sakha Transfer)

**Status:** FROZEN (2026-10-10 design decision)

A member-initiated or admin-filed Sakha Transfer is a two-step request/release/accept workflow,
recorded in `nss.membership_change_request` (`request_type = 'TRANSFER'`), not an immediate
write to `membership_sakha_affiliation`:

```text
PENDING_SOURCE_RELEASE
   -> source Sakha releases   -> PENDING_DESTINATION_ACCEPT
   -> source Sakha rejects    -> REJECTED_BY_SOURCE          [terminal]
PENDING_DESTINATION_ACCEPT
   -> destination Sakha accepts  -> COMPLETED                [terminal]
   -> destination Sakha rejects  -> REJECTED_BY_DESTINATION   [terminal]
```

Both decision stages are gated by `MEMBERSHIP_APPROVE` plus admin scope over the deciding Sakha
— no new governance-position-checking logic is required, because `MEMBERSHIP_APPROVE` is already
auto-granted to a Sakha's sitting President/Secretary (and acting officeholders) scoped to that
Sakha's own `organization_pk` (§63 composite-grant mechanism).

On `COMPLETED`:

- The old (`old_organization_pk`) `membership_sakha_affiliation` row is closed
  (`effective_to` set, `affiliation_status = 'ARCHIVED'`) — MBR-031's "never deleted" rule
  governs this exactly as it already does for any other transfer.
- A new affiliation row is opened at `new_organization_pk` with a new Local Sakha ERP Number
  (MBR-030, MBR-030C/MBR-048 auto-sequencing by default).
- A `membership_transfer_history` row is written (MBR-028), and a `TRANSFER`
  `membership_journey_event` is recorded (MBR-021/043), referencing the change-request PK.
- `effective_date` (MBR-029) is resolved to the next confirmed Dola Purnima on or after the
  destination-accept date, via the same festival-calendar lookup
  `issue_membership_credential()` already uses — never computed independently.

A member may have at most one open (non-terminal) change request at a time (DB-enforced, partial
unique index on `membership_change_request`).

---

## MBR-049 — Apply for Darshak Is a Change Request, Not a Transfer

**Status:** FROZEN (2026-10-10 design decision)

"Apply for Darshak" (attending Sangha Puja as a Darshak at a Sakha other than one's own) shares
MBR-048's two-step request/release/accept workflow shape (`membership_change_request`,
`request_type = 'DARSHAK'`), but is explicitly **not** a transfer:

- On `COMPLETED`, the member's home-Sakha `membership_sakha_affiliation` row is **not** closed. A
  second, concurrently-active affiliation row is opened at the destination Sakha instead — legal
  because `uq_mem_sakha_aff_active` is scoped per `(sangha_sevi_pk, organization_pk)`, not per
  member alone, so a home affiliation and a Darshak affiliation at a different Sakha coexist.
- No `membership_transfer_history` row is written — nothing was transferred, the member's home
  Sakha and home Local Sakha ERP Number are unaffected.
- A `membership_journey_event` is still recorded, documenting the start of Darshak attendance at
  the new Sakha.

`old_organization_pk` on a `DARSHAK`-type change request names the member's home Sakha for
display/audit purposes only — it carries no release-of-affiliation meaning the way it does for a
`TRANSFER` request.

---

# 10. Probationary Review Rules

## MBR-032 — Review History

Probationary Member reviews shall be historically preserved.

---

## MBR-033 — Review Does Not Delete Membership

A review shall not delete the underlying Membership record.

---

## MBR-034 — Review Outcome

Review outcomes shall be recorded as controlled journey/review events.

The exact review outcomes shall follow the approved Membership progression rules.

---

# 11. Attendance Relationship

## MBR-035 — Attendance Is Separate

Attendance belongs to the Attendance Module.

Membership stores the Membership identity and lifecycle.

---

## MBR-036 — Attendance Review

Attendance may result in an Attendance Review.

Attendance Review is not itself a Membership status.

---

## MBR-037 — No Automatic Membership Action

Attendance alone shall not automatically:

* Suspend Membership.
* Cancel Membership.
* Change Membership Type.
* Revoke identity documents.

A formal review and authorized decision are required before Membership action.

---

# 12. Organization Relationship

## MBR-038 — Current Organization

The Membership record shall identify the Member's current organizational association.

---

## MBR-038A — Member's Current Organization Must Be a Sakha Sangha

**Status:** FROZEN (governance decision, 2026-09-26)

A Member's current organizational association (MBR-038) shall reference an organization of
type `SAKHA_SANGHA`. A Member is affiliated to NSS *through a Sakha only* — there is no
alternative primary affiliation.

**Single exception — the system account.** Exactly one reserved bootstrap identity
(`sangha_sevi.is_system_account = TRUE`) may be associated directly with the apex `KENDRA`
organization, representing the NSS-wide global administrator (the seeded `SS1` record). This
is an identity property of one specific record, **not** a capability: holding the
`NSS_ERP_ADMIN` role does not confer it, and it is never granted or revoked through the API or
UI.

**Enforcement.** A `BEFORE INSERT/UPDATE` trigger on both `sangha_sevi.organization_pk` and
`membership_sakha_affiliation.organization_pk` shall reject any non-`SAKHA_SANGHA`
organization unless `is_system_account = TRUE`, mirrored by API-layer validation. A partial
unique index (`... WHERE is_system_account`) shall guarantee at most one system account can
ever exist.

This supersedes the prior convention-only reading of MBR-038 — the restriction is now a real
invariant, not a UI convenience.

---

## MBR-039 — Historical Organization

Previous organizational associations shall remain available through transfer history.

---

## MBR-046 — Wing Sangha Membership Is an Affiliation, Not a Separate Identity

**Status:** FROZEN (governance decision, 2026-09-26)

A Sakha Member may additionally hold membership in a wing body — Mahila Sangha (all female
members), Kumari Sangha (unmarried girls), or Sevak Sangha (male devotees electing to join).
Wing membership is an **affiliation layered on the existing Sangha Sevi record**, not a second
membership.

Consequently a wing member takes **no new identifier**: they retain the same Sangha Sevi ID
(Tier 1, MBR-004) and the same Local Sakha ERP Number (Tier 2, MBR-030) as their Sakha
membership. No wing-specific ID sequence exists.

This preserves MBR-003 (One Person, One Membership) — wing membership does not create an
alternate `organization_pk` a member "belongs to." See ORG-BR-096 for how the underlying
Mahila/Kumari/Sevak Sangha organization rows are created.

---

# 13. Governance Eligibility

## MBR-040 — Membership Is Not Governance Authority

Membership does not automatically grant a governance position.

Governance eligibility shall be determined by Governance rules.

---

## MBR-041 — Governance Traceability

Where Membership eligibility affects a governance workflow, the relationship shall remain traceable.

---

# 14. Audit Rules

## MBR-042 — Auditability

Membership actions shall preserve:

```text
Created By
Created At
Updated By
Updated At
```

where applicable.

---

## MBR-043 — Historical Traceability

Membership history shall remain traceable throughout the lifecycle.

---

# 15. Deletion Rules

## MBR-044 — Physical Deletion Prohibited

Physical deletion of Membership history is prohibited.

---

## MBR-045 — Status-Based Lifecycle

When Membership ceases or becomes inactive, the ERP shall record the appropriate status/event rather than physically deleting the Membership record.

---

# 16. Core Frozen Rules

The following principles are frozen at the project level:

```text
Person is not equal to Member

One Person = One Membership

One Membership = One Sangha Sevi ID

Sangha Sevi ID Permanent

Sangha Sevi ID Never Reused

Transfer Does Not Change Sangha Sevi ID

Membership History Never Deleted

Physical Delete Prohibited

Attendance Review Required Before Membership Action
```

---

# 17. Authority Hierarchy

Membership rules shall be interpreted according to:

```text
NSS Bye-Law
      |
Authoritative REF
      |
Approved Governance Decision
      |
Approved Membership Business Rule
      |
Solution Design
      |
Implementation
```

Where a conflict exists, the higher authority shall prevail.

---

# End of Document
