# docs/00_Project_Governance/GDR/

Governance Decision Register — the cross-cutting mechanism for proposing, reviewing,
approving, recording, monitoring, and retiring individual governance decisions.

- `GDR-001_Governance_Decision_Register_Standard.md` — defines the register process and
  template (Decision Identifier, Rationale, Authority, Status, etc.).
- `GDR-002_Creation_of_the_REF-MS_Authoritative_Reference_Family.md` — the first recorded
  decision using the GDR-001 process: approves creation of the `REF-MS` REF family
  (Nilachala Saraswata Mahila Sangha's Bye-Law) and the general `AUTH-ID-002A` rule in
  `AUTH-001` for creating future REF families.
- `GDR-003_Governance_Document_Status_Lifecycle_and_Rule_Maturity_Separation.md` — separates
  document-level `Status` from per-rule `Rule Maturity`, adds `GOV-LIFE-006` (Draft → Review →
  Approved → Superseded/Retired) to `GOV-001`, and advances `AUTH-001`/`GOV-001` from Draft to
  Approved.
- `GDR-004_Governance_Authority_Structure_Clarification.md` — establishes that Project Owner =
  NSS itself, Governance Authority = Project Steering Committee (same body), and final Decision
  Authority = NSS Governing Body (via President/Parichalak). Adds `GOV-ROLE-006` to `GOV-001`;
  corrects the `Owner` field in `GOV-002..005`/`GDR-001` and the `Decision Authority` field in
  `GDR-002`/`GDR-003` (via preserved correction notes) to match.
- `GDR-005_Advisory_Board_as_a_Singleton_Organization.md` — owner-directed (2026-10-30): the Advisory
  Board becomes the 14th organization type `ADVISORY_BOARD` (singleton `ADB`/`NSSAB`, parent Kendra,
  immutable name, DB singleton trigger — generalised 2026-10-30 to KENDRA / NILACHALA_KUTIRA / SMRUTI_MANDIRA / ADVISORY_BOARD and the central Kendra-parented Mahila Sangha) while the Advisory Board governance body stays NULL-org.
  Status `Proposed` (NSS Governing Body ratification not verifiable).
- `GDR-006_NULL_Organization_Administrative_Scopes.md` — owner-directed (2026-10-30): NULL-organization
  admin scopes (`KENDRA_MAHILA_SANGHA` → all `MAHILA_SANGHA` orgs; `ADVISORY_BOARD` → the AB org) and
  body-level `NULL_ORG_SCOPE_BODY_TYPES`, with final permission lists. Status `Proposed`.
- `GDR-007_Sakha_Re-Parenting_Requires_President_Chain_Approval.md` — owner-directed (2026-10-30): Sakha
  (Sakha Sangha and Sakha Asana alike) needs the President chain unless the actor is a Kendra Governing
  Body member (§63 composite `NSS_ERP_KENDRA_ADMIN`) or the `NSS_ERP_ADMIN` super administrator (by role).
  Status `Proposed`.
- `GDR-008_Sakha_Asana_Is_a_Sakha_for_All_Organizational_Purposes.md` — owner-directed (2026-10-31): a Sakha
  Asana hosts every wing a Sakha Sangha can (Kumari, Sevak, local Mahila, Paribarik Asana); amends
  ORG-BR-091/092/094 (wing parents = the shared Sakha-like set). No schema change. Status `Proposed`.
