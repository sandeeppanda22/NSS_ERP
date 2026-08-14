# docs/00_Project_Governance/GOV/

Governance framework standards, all parented under GOV-001 (Status: Approved, v1.2.0).

- `GOV-001_Project_Governance_Principles.md` — top-level lifecycle hierarchy (Constitution →
  REF → AUTH → GOV → REQ → SOLUTION → CODE → TEST → RELEASE), constitutional authority
  supremacy, roles, compliance rules, the governance document Status lifecycle
  (`GOV-LIFE-006`: Draft → Review → Approved → Superseded/Retired), and the governance
  authority structure (`GOV-ROLE-006`: Project Owner = NSS, Governance Authority = Project
  Steering Committee, Final Decision Authority = NSS Governing Body). GDR is cross-cutting,
  not a sequential layer.
- `GOV-002_Organizational_Governance_Standard.md` — how the ERP's organizational hierarchy
  (Kendra → Anchalika/Zilla → Sakha) must mirror constitutional structure: single apex org,
  parent-child integrity, no circular refs, immutable org identifiers.
- `GOV-003_Repository_Governance_Standard.md` — governs the whole repository (docs, code, DB
  scripts, tests) as single source of truth: directory structure, naming, versioning, access
  control, auditability, backup/recovery.
- `GOV-004_Requirement_Traceability_Standard.md` — end-to-end traceability model
  (REF→REQ→SOL→DB/API/UI→TEST→RELEASE), requirement identity, Requirement Traceability Matrix.
- `GOV-005_Governance_Change_Control_Standard.md` — formal change-control process for
  governance artifacts: change request → review → impact assessment → approval →
  implementation → verification → closure, tied to the GDR.
