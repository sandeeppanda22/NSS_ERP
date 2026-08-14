# GDR-003 — Governance Document Status Lifecycle and Rule Maturity Separation

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-003 |
| Decision Title | Governance Document Status Lifecycle and Rule Maturity Separation |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body |
| Approver | Project Steering Committee |
| Decision Status | Approved |
| Effective Date | 2026-08-13 |
| Affected Documents | GOV-001, AUTH-001 |
| Related Change Request | N/A (open governance question tracked in CLAUDE.md §6, resolved via explicit user decision during this session) |

---

## 1. Background

CLAUDE.md §6 had flagged the governance document status lifecycle as an unresolved open question: the metadata "Status" field on governance documents (AUTH-001, GOV-001 through GOV-005, GDR-001, GDR-002) had only ever been set to `Draft` or `Approved` in practice, with no formally adopted lifecycle governing what values are valid or what each means.

Investigation during this session surfaced a more specific problem than "no lifecycle exists": the same field name, "Status," was already being used for two unrelated concepts without any document distinguishing them:

- **Document-level Status** — the approval state of a governance document as a whole (only `Draft`/`Approved` seen in practice; AUTH-001 separately defines an unrelated 4-state Status lifecycle for REF documents in AUTH-META-002; GDR-001 separately defines a 5-state "Decision Status" lifecycle for individual GDR entries).
- **Rule-level Status** — an attribute on individual normative rules (e.g. `AUTH-ORG-001 — Status: Frozen`), present on every rule in AUTH-001 (44 occurrences) and GOV-001 (20 occurrences), always set to `Frozen`.

This produced a real contradiction: both AUTH-001 and GOV-001 showed document-level Status `Draft`, while every rule inside them was simultaneously marked `Frozen` (immutable, binding) and was already being cited project-wide as authoritative governance (including throughout CLAUDE.md). A document cannot coherently be "not yet approved" while all of its content is already treated as locked and binding.

## 2. Decision

1. The two concepts are formally separated. The per-rule field is renamed from `Status` to **`Rule Maturity`** in AUTH-001 (44 rule blocks) and GOV-001 (20 pre-existing rule blocks), with no change to rule content or values (`Frozen` throughout, unchanged). The document-level metadata field keeps the name `Status`.
2. A new normative rule, **GOV-LIFE-006 — Governance Document Status Lifecycle**, is added to GOV-001 §5, defining the Document Status lifecycle as:
   ```text
   Draft → Review → Approved → Superseded / Retired
   ```
3. GOV-001 §3 Definitions gains two new terms, **Document Status** and **Rule Maturity**, cross-referencing GOV-LIFE-006, GDR-001's Decision Status, and AUTH-001's REF-document Status (AUTH-META-002), so all four "status"-shaped concepts in the project are distinguishable from one another. AUTH-001 §3 Definitions gains a matching `Rule Maturity` entry, since AUTH-001 uses the field most heavily.
4. AUTH-001's and GOV-001's own document-level Status is advanced from `Draft` to `Approved`, reflecting that both documents' content is already in active, binding use throughout the project. Both documents' Version is bumped to `1.1.0` with a corresponding Revision History entry.

## 3. Rationale

- **Resolves a real contradiction, not just a labeling gap.** The Draft/Frozen conflict was already visible in the live documents, not hypothetical.
- **Four distinct "status" concepts already existed in the project** (document Status, rule Status, GDR Decision Status, REF document Status) under overlapping terminology; disambiguating them by name is lower-risk than forcing them into one unified lifecycle, which would have required overriding the meaning of `Frozen` already used elsewhere in the project as the Governance Baseline's own label (CLAUDE.md §2: "Governance Baseline v1.0 — FROZEN").
- **A 4-state lifecycle with no document-level `Frozen`** avoids giving that term a third meaning — it already labels the whole Governance Baseline and, going forward, Rule Maturity.
- **Renaming, not restating, the rule-level field** preserves every rule's actual maturity value and ID — no substantive rule content changed, keeping this within the editorial/structural correction pattern already used for the AUTH-001/GOV-001–005/GDR-001 six-phase review (CLAUDE.md §6).

## 4. Alternatives Considered

- **Unify document Status and rule Status into a single field/lifecycle.** Rejected — would require either reinterpreting every `Frozen` rule as document-level-approved (masking that individual rules can stabilize before the surrounding document completes review) or reinterpreting `Draft` documents as containing not-yet-binding rules (contradicting how the rules are actually used today).
- **5-state lifecycle including a document-level `Frozen` state** (`Draft → Review → Approved → Frozen → Superseded/Retired`), matching earlier unverified speculation in CLAUDE.md. Rejected — `Frozen` already carries two other meanings in this project (Governance Baseline v1.0 as a whole; Rule Maturity per rule); adding a third, document-level meaning increases ambiguity rather than resolving it.
- **Leave AUTH-001/GOV-001 at Status `Draft`.** Rejected — leaves the original contradiction unresolved and misrepresents how these documents are actually used across the project.

## 5. Impact Assessment

- **GOV-001:** Normative addition (new rule GOV-LIFE-006; two new §3 definitions); editorial rename of 20 existing rule-level Status labels to Rule Maturity (no value/content change); Version 1.0.0 → 1.1.0; Status Draft → Approved.
- **AUTH-001:** One new §3 definition (Rule Maturity); editorial rename of 44 rule-level Status labels to Rule Maturity (no value/content change); Version 1.0.0 → 1.1.0; Status Draft → Approved.
- **GOV-002 through GOV-005, GDR-001, GDR-002:** No change — these documents do not use the per-rule Status/Rule Maturity field, and their document-level Status was already `Approved`.
- **Repository:** No file moves or renames. No REF documents affected — REF document Status (AUTH-META-002) is a separate, pre-existing concept, not modified by this decision.
- **CLAUDE.md:** §6's "Governance document status lifecycle" open question is resolved; §12 gains a session-log entry.

## 6. Approval

Approved as a normative addition to GOV-001 (new rule) and an editorial correction to GOV-001/AUTH-001 (field rename, Status advancement) under the Governance Change Control process (GOV-LIFE-002) and the Governance Decision Register process (GDR-001, AUTH-GOV-002).

---

## Correction Note (2026-08-14, per GDR-004)

The `Decision Authority` field originally read `NSS ERP Governance Committee`. Following the governance authority structure clarification in GDR-004, this is corrected to `NSS Governing Body` — the project's actual final decision authority (GOV-ROLE-006). The substance of this decision (the governance document status lifecycle, GOV-LIFE-006) is unaffected by this correction; only the recorded Decision Authority attribution is updated. Preserved here per GDR-DATA-003 (Complete Decision History).

---

# End of Document
