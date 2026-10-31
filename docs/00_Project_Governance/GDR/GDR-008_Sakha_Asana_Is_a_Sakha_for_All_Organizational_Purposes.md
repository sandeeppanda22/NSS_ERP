# GDR-008 — Sakha Asana Is a Sakha for All Organizational Purposes, Including Hosting Wing Organizations

## Document Metadata

| Attribute | Value |
|----------|-------|
| Decision Identifier | GDR-008 |
| Decision Title | Sakha Asana Is a Sakha for All Organizational Purposes, Including Hosting Wing Organizations |
| Decision Type | Governance Decision Record |
| Register | Governance Decision Register (GDR-001) |
| Decision Authority | NSS Governing Body (GOV-ROLE-006) |
| Approver | Project Steering Committee |
| Decision Status | Proposed |
| Effective Date | TBD (on ratification; implementation already in the working tree as of 2026-10-31) |
| Affected Documents | SOL-ORG-004 (ORG-BR-091, ORG-BR-092, ORG-BR-094, ORG-BR-104), ORGANIZATION_API_CONTRACT, FK_DEPENDENCY_GRAPH, GDR-007 |
| Related Change Request | N/A (owner-directed decision, 2026-10-31) |

> **Ratification flag.** This decision was directed by the project owner on 2026-10-31 and is recorded here per GDR-001 (GDR-DEC-001). GDR-001 and GOV-ROLE-006 place final decision authority with the NSS Governing Body; no evidence of that body's approval is available in the repository, so Decision Status is `Proposed`, not `Approved`. Advance it to `Approved` (and then `Implemented`) only once the NSS Governing Body / Project Steering Committee ratification is confirmed, and record that in this document.

---

## 1. Background

GDR-007 (item 5) made `SAKHA_ASANA` a full Sakha for membership, Advisory Board representation, attendance, correspondence, pickers and the re-parenting chain, but deliberately left the wing parenting rules (ORG-BR-091/092/094) unchanged: `KUMARI_SANGHA`, `SEVAK_SANGHA`, the local `MAHILA_SANGHA` and `PARIBARIK_ASANA` could be parented only by `SAKHA_SANGHA`, so a Sakha Asana could not host them.

## 2. Decision

1. A Sakha Asana can host **all** the wing/child organizations a Sakha Sangha can. The permitted parents become the shared Sakha-like set (`SAKHA_SANGHA` or `SAKHA_ASANA`) for:
   - `KUMARI_SANGHA` (ORG-BR-092)
   - `SEVAK_SANGHA` (ORG-BR-092)
   - `MAHILA_SANGHA` local, per-Sakha tier (ORG-BR-091) — the `KENDRA` parent option and the single-central-Mahila-Sangha singleton rule are unchanged
   - `PARIBARIK_ASANA` (ORG-BR-094; still an implementation proxy for the attached `sangha_sevi`'s current Sakha)
2. The one-active-`KUMARI_SANGHA`-and-one-active-`SEVAK_SANGHA` **per Sakha** rule (ORG-BR-102) applies per Sakha-like parent: an Asana may have one of each, independent of any Sangha.
3. A Sakha's own `NSS_ERP_SAKHA_ADMIN` (scoped to an Asana) may create Kumari/Sevak Sangha for that Asana exactly as for a Sakha Sangha (ORG-BR-101/102); the NSS-wide parent picker lists both Sakha-like types.
4. Implementation: a single definition per layer (`api/helpers.py::SAKHA_LIKE_ORG_TYPES`, `nss.fn_is_sakha_like_org_type()`, `NSS.SAKHA_LIKE_ORG_TYPES`); the parent matrix `ALLOWED_PARENT_TYPES` and its JS mirror derive from it with no new literal lists. No database trigger or DDL change is needed: the Kumari/Sevak uniqueness trigger keys on `parent_organization_pk`, and the singleton/address triggers never look at a Sakha-type literal.
5. Unchanged on purpose: ORG-BR-096 (an Asana is not created through the standard Create Organization flow), ORG-BR-098 (premises is an attribute of `SAKHA_SANGHA`), id-sequence/code generation per stored type, seed data.

## 3. Rationale

An Asana is a Sakha without its own building, with its own Governing Body, President and members (GDR-007). Its Kumari/Sevak/Mahila/Paribarik activities exist like any Sakha's; restricting wing parents to `SAKHA_SANGHA` would make an Asana a second-class Sakha for no Bye-Law reason.

## 4. Alternatives Considered

- **Keep wings Sakha-Sangha-only (GDR-007 status quo).** Rejected by the owner.
- **Re-type an Asana to `SAKHA_SANGHA` with `has_own_premises = FALSE`.** Not adopted: `SAKHA_ASANA` is a recognised stored type (ORG-BR-090).

## 5. Impact Assessment

SOL-ORG-004 amendment notes on ORG-BR-091/092/094; ORGANIZATION_API_CONTRACT parent matrix; FK_DEPENDENCY_GRAPH. No schema change. Existing wing rows (all under `SAKHA_SANGHA`) remain valid.

## 6. Approval

Recorded under GDR-001; approval pending per the Ratification flag above.

---

# End of Document
