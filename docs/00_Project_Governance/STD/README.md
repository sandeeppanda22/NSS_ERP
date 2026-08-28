# docs/00_Project_Governance/STD/

Concrete, code-facing engineering standards (Version 1.0, Status: FROZEN) — more operational
than the AUTH/GOV/GDR governance-process documents; this is what the current codebase is meant
to converge on.

- `01_project_standards.md` — core principles (Person≠Member, Family First, History Never
  Deleted, etc.), tech stack, DB principles (UUID PKs + business IDs, soft delete only), audit
  columns, security principles, dev workflow, deployment environments.
- `02_naming_conventions.md` — snake_case tables, `_pk`/business-identifier conventions,
  FK/index/constraint/sequence naming, SQL file naming, Django PascalCase models, kebab-case
  APIs, git branch naming.
- `03_master_data_catalog.md` — catalog of planned master/lookup tables across the whole
  system (geography, organization, membership, family, governance, attendance, RBAC, workflow,
  publications/heritage, Kumari/Kishor/Sevak, UPBS, finance) with example seed values — spans
  far more modules than are currently implemented.
- `04_audit_standards.md` — mandatory audit columns, soft-delete-only rule, dedicated history
  tables, central `audit_master` design, per-module audit requirements, retention policy.
- `05_security_standards.md` — auth model, password policy, account lockout, session timeout,
  RBAC table set, Row Level Security by organizational scope, encryption/logging rules.

See `docs/PROJECT_DOCUMENTATION.md` → Conventions & gotchas for where the current code diverges
from these standards (e.g. actual DDL uses `_code` not `_id` for business identifiers).
