# GDR-002 — Creation of the REF-MS Authoritative Reference Family

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-002 |
| Decision Title | Creation of the REF-MS Authoritative Reference Family |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body |
| Approver | Project Steering Committee |
| Decision Status | Approved |
| Effective Date | 2026-08-12 |
| Affected Documents | AUTH-001 |
| Related Change Request | N/A (documentation correction identified during REF corpus verification work) |

---

## 1. Background

During the transcription and verification of the Nilachala Saraswata Mahila Sangha's Bye-Law into the Authoritative Reference (REF) repository, it was identified that the Mahila Sangha is a **separately and independently registered entity** (Regn. No. 7726/79 of 1974-75) with its **own official governing document** (its own Bye-Law), rather than a section of the Nilachala Saraswata Sangha's own Bye-Law.

AUTH-001's existing REF family scheme (`REF-001` through `REF-010`) is explicitly defined around sections of the NSS Bye-Law itself (Section A through Section J). Assigning Mahila Sangha's authoritative references into that same numbered scheme (e.g. as `REF-004` or `REF-005`, as an earlier unverified project handoff document had speculated) would have incorrectly implied that the Mahila Sangha's Bye-Law is a section of the NSS Bye-Law, when it is in fact a distinct governing document belonging to a distinct, subordinate registered entity.

## 2. Decision

A new, dedicated REF family — **`REF-MS`** — is established for the Constitution & Bye-Laws of the Nilachala Saraswata Mahila Sangha, separate from the `REF-00X` family reserved for NSS's own Bye-Law sections.

AUTH-001 is amended to:

1. Add a new rule, **AUTH-ID-002A — New REF Family Creation**, defining the general principle that a dedicated REF family (rather than an extension of the `REF-00X` numbering) shall be created whenever authoritative reference material originates from a distinct, separately registered governing entity with its own governing document.
2. Add `REF-MS` to **Appendix B — REF Family Mapping**, documenting it as the family for the Mahila Sangha's Bye-Law.

## 3. Rationale

- **Constitutional accuracy:** The Mahila Sangha's Bye-Law is not a section of the NSS Bye-Law; folding it into the `REF-00X` numbering would misrepresent the actual constitutional relationship between the two documents.
- **Consistency with GOV-ORG-001/002:** The Mahila Sangha is subordinate to NSS in organizational authority, but that subordination is expressed through its own governing document, not by being absorbed into NSS's document structure. A separate REF family correctly reflects "distinct document, subordinate entity" rather than conflating it with "section of the same document."
- **Extensibility:** Establishing a general rule (AUTH-ID-002A) for creating new REF families — rather than deciding this ad hoc for Mahila Sangha alone — provides a repeatable, governed process for any future subordinate entity with its own governing document (e.g. a future Sakha Sangha or Sikshya Kendra, should one obtain formal independent governing document recognition per GOV-ORG-004).

## 4. Alternatives Considered

- **Extend the `REF-00X` sequence** (e.g. `REF-004` = Mahila Sangha), as speculated in an earlier, unverified project handoff document. Rejected: this was never verified against AUTH-001's actual definition (which ties `REF-00X` to NSS Bye-Law sections specifically) and would misrepresent the Mahila Sangha's Bye-Law as part of the NSS document.
- **Use the existing top-level `RESOLUTIONS/` or a new generic `OTHER/` reference family.** Rejected: Mahila Sangha's Bye-Law is a full constitutional document in its own right, not a resolution or miscellaneous reference; it warrants the same document-family treatment as NSS's own Bye-Law, just under a distinct identifier.

## 5. Impact Assessment

- **AUTH-001:** Normative addition (new rule AUTH-ID-002A; new Appendix B rows). No existing rule content, IDs, or REF-00X mappings were altered.
- **Repository:** No renaming of existing files. The 22 `REF-MS-*` documents already created under `docs/01_Authoritative_References/MAHILA_SANGHA/` are retroactively brought into full compliance with AUTH-001 by this decision — they had already been created using the `REF-MS` naming pattern in anticipation of this governance change being formalized.
- **Future work:** Establishes the process (AUTH-ID-002A) for any future subordinate-entity governing documents needing their own REF family.

## 6. Approval

Approved as a normative addition to AUTH-001 under the Governance Change Control process (GOV-005) and the Governance Decision Register process (GDR-001, AUTH-GOV-002).

---

## Correction Note (2026-08-14, per GDR-004)

The `Decision Authority` field originally read `NSS ERP Governance Committee`. Following the governance authority structure clarification in GDR-004, this is corrected to `NSS Governing Body` — the project's actual final decision authority (GOV-ROLE-006). The substance of this decision (creation of the `REF-MS` REF family) is unaffected by this correction; only the recorded Decision Authority attribution is updated. Preserved here per GDR-DATA-003 (Complete Decision History).

---

# End of Document
