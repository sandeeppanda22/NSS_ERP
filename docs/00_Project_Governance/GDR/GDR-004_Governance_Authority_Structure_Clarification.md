# GDR-004 — Governance Authority Structure Clarification

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-004 |
| Decision Title | Governance Authority Structure Clarification |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body |
| Approver | Project Steering Committee |
| Decision Status | Approved |
| Effective Date | 2026-08-14 |
| Affected Documents | GOV-001, GOV-002, GOV-003, GOV-004, GOV-005, GDR-001, GDR-002, GDR-003 |
| Related Change Request | N/A (open governance question tracked in CLAUDE.md §6, resolved via explicit user decision during this session) |

---

## 1. Background

CLAUDE.md §6 had flagged the exact relationship between "Governance Authority," "Decision Authority," "Approving Authority," "Project Owner," and "Project Steering Committee" as the last unresolved open governance decision.

Investigation found:

- `Project Owner` and `Governance Authority` are formally defined roles in GOV-001 (`GOV-ROLE-001`, `GOV-ROLE-002`), but neither is tied to a specific named body.
- `Project Steering Committee` and `NSS ERP Governance Committee` are used as concrete values in document metadata (`Approver` and `Owner` fields respectively, across GOV-002 through GOV-005 and GDR-001; `NSS ERP Governance Committee` is also used as `Decision Authority` in the already-approved GDR-002 and GDR-003), but neither is formally defined as a role anywhere.
- `Approving Authority` never appears anywhere in the actual governance corpus — only inside CLAUDE.md's own description of this open question, similar to the `"Non-Conformity"` phantom term resolved earlier in this session.

## 2. Decision

1. **Project Owner = Nilachala Saraswata Sangha (NSS) itself.** `GOV-ROLE-001` in GOV-001 is amended to state this explicitly.
2. **Governance Authority = Project Steering Committee.** These are the same body, not two distinct ones. `GOV-ROLE-002` in GOV-001 is amended to state this explicitly. The `Owner` metadata field in GOV-002 through GOV-005 and GDR-001 — previously `NSS ERP Governance Committee` — is corrected to `Project Steering Committee` to match. The `Approver` field (already `Project Steering Committee` everywhere) is unchanged.
3. **Final decision authority for governance decisions recorded in the GDR rests with the NSS Governing Body** — the statutory governing body of NSS (REF-003-C(i)(1)) — exercised through its President (REF-003-C(i)(3)) and/or Parichalak (REF-003-C(i)(8)), not the Governance Authority/Project Steering Committee. A new rule, `GOV-ROLE-006 — Final Decision Authority`, is added to GOV-001 §6 to state this.
4. The `Decision Authority` field in the already-approved GDR-002 and GDR-003 — previously `NSS ERP Governance Committee` — is corrected to `NSS Governing Body`, with a Correction Note added to each preserving the original attribution per `GDR-DATA-003` (Complete Decision History). The substance of both prior decisions is unaffected.
5. `Approving Authority` is retired from CLAUDE.md's open-question tracking as a phantom term, matching the earlier `"Non-Conformity"` resolution — it was never introduced anywhere and does not need a definition.

This establishes the following governance hierarchy for the NSS ERP project:

```text
NSS (Project Owner)
    │
    ▼
NSS Governing Body (Final Decision Authority — GOV-ROLE-006)
  exercised through President / Parichalak
    │
    ▼
Project Steering Committee (Governance Authority — GOV-ROLE-002)
  maintains framework, reviews proposals, evaluates GDR entries, monitors compliance
```

## 3. Rationale

- **Resolves a real structural gap, not just a naming inconsistency.** Two named bodies (`Project Steering Committee`, `NSS ERP Governance Committee`) were already in active use across seven documents without ever being formally defined or related to the roles GOV-001 does define.
- **Separates day-to-day framework maintenance from final governance decision authority.** The Project Steering Committee (= Governance Authority) handles routine framework stewardship; escalating actual governance *decisions* to the NSS Governing Body keeps ultimate authority with NSS's real statutory structure, consistent with GOV-ORG-001 (Statutory Authority) and GOV-ORG-004 (Separation of Governance and Implementation).
- **Corrects, rather than silently rewrites, already-approved decisions.** GDR-DATA-002/GDR-DATA-003 require immutable decision identity and a complete historical record; the correction notes preserve traceability instead of erasing the original (incorrect) attribution.

## 4. Alternatives Considered

- **Leave `NSS ERP Governance Committee` as Decision Authority in GDR-002/GDR-003.** Rejected — the user explicitly stated final decision authority belongs to the NSS Governing Body/President/Parichalak, not an ERP-internal committee; leaving it uncorrected would misrepresent actual statutory authority in the permanent decision record.
- **Treat Project Steering Committee and Governance Authority as distinct bodies.** Rejected per explicit user clarification — the user's description of the Project Steering Committee's responsibilities ("maintains the governance framework, reviews proposals, evaluates GDR entries, monitors compliance") is verbatim what `GOV-ROLE-002` already defines for Governance Authority.
- **Keep tracking `Approving Authority` as an open term.** Rejected — it has never been used anywhere in the corpus; tracking it further would be tracking a non-issue.

## 5. Impact Assessment

- **GOV-001:** Normative addition (`GOV-ROLE-006`); clarifying amendments to `GOV-ROLE-001`/`GOV-ROLE-002` (no responsibility changes, identity clarification only); Version 1.1.0 → 1.2.0.
- **GOV-002, GOV-003, GOV-004, GOV-005, GDR-001:** `Owner` field corrected from `NSS ERP Governance Committee` to `Project Steering Committee`; no other content change.
- **GDR-002, GDR-003:** `Decision Authority` field corrected from `NSS ERP Governance Committee` to `NSS Governing Body`; Correction Note added to each; original decision substance unaffected.
- **AUTH-001:** No change — does not use the Owner/Approver/Decision Authority fields affected here.
- **CLAUDE.md:** §6/§13's last remaining open governance decision is resolved; §12 gains a session-log entry.

## 6. Approval

Approved under the Governance Change Control process (GOV-LIFE-002) and the Governance Decision Register process (GDR-001, AUTH-GOV-002), with final decision authority exercised per the structure this decision itself establishes (`GOV-ROLE-006`) — i.e. by the NSS Governing Body.

---

# End of Document
