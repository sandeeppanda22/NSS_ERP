# NSS ERP Authentication Module

Status: NOT STARTED (Solution design) — the `backend/authentication/` Django app already has
real models (`Role`, `UserRole`, `LoginAudit`) and a working login view; see
`backend/authentication/README.md`.

Reserved for the Authentication module's Solution-level design documents (RBAC, session
management, audit), following the same `01_design` / `02_erd` / `03_business_rules` /
`04_table_design` pattern used by `docs/03_Solution/modules/organization/` and
`docs/03_Solution/modules/person/`. No content has been written yet — the target model is
`docs/00_Project_Governance/STD/05_security_standards.md`, which the current code does not yet
implement.
