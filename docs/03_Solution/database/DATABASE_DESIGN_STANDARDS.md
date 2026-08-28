# NSS ERP — Database Design Standards

**Document ID:** SOL-DB-001
**Version:** 1.0.0
**Status:** DRAFT — SOURCE ALIGNED (Consolidation)
**Scope:** Cross-Module Database Architecture
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document consolidates the cross-module database conventions
established across the approved module table-design documents and project
governance standards into a single reference.

It does not introduce new rules. Every standard stated here is already
established by one or more existing module documents and the project
governance framework.

This document exists so that:

- DDL authors have one authoritative conventions reference
- New module designers do not need to extract conventions from 19 files
- Cross-module consistency is explicitly stated rather than implicit

---

# 2. Governing Documents

| Source | Authority |
|--------|-----------|
| `00_Project_Governance/STD/` | Project-wide standards |
| `03_Solution/modules/<module>/04_*_table_design.md` | Per-module frozen designs |
| `03_Solution/architecture/TECH_STACK_DECISIONS.md` | Technology choices |
| NSS Bye-Law | Supreme authority for business rules |

This document consolidates; those documents remain authoritative.

---

# 3. Database Engine

PostgreSQL.

Current development/deployment environment: Neon PostgreSQL.

Extensions currently identified/approved for evaluation:

```
uuid-ossp          — UUID generation
pg_trgm            — Trigram similarity search
btree_gin          — GIN indexing for combined queries
```

The actual `CREATE EXTENSION` list is finalized during DDL authoring.
Additional extensions may be adopted but must be documented.

---

# 4. Technical Primary Key Convention

Every table shall have a single technical primary key named:

```
<table_name>_pk
```

Examples:

```
person_pk
organization_pk
master_category_pk
body_member_assignment_pk
audit_master_pk
```

This convention is stated in all 19 module table-design documents.

---

# 5. Primary Key Type

All technical primary keys use UUID.

```
<table_name>_pk UUID PRIMARY KEY
```

UUIDs provide:

- Global uniqueness without coordination
- Safe distributed generation
- No sequential information leakage
- Stable cross-module references

The exact UUID generation strategy (v4, v7, database-generated vs
application-generated) is an implementation decision finalized during DDL
authoring.

---

# 6. Business Identifier Convention

Where a table requires a human-readable identifier, it shall be a
separate column from the technical PK.

Naming pattern:

```
<table_name>_id      — sequential business identifier
<table_name>_code    — stable classification code
```

Examples:

```
person_pk            — internal UUID (relational)
person_id            — human-readable (P00000001)

organization_pk      — internal UUID
organization_id      — human-readable (ANC0001)

organization_type_pk   — internal UUID
organization_type_code — stable machine-readable code (SAKHA)
```

---

# 7. Business ID Properties

Business identifiers that require centrally sequenced generation shall
use `id_sequence_master`.

Such identifiers shall be:

- Unique
- System-generated
- Permanent
- Never reused
- Immutable after creation

No application-local counter shall generate sequenced business IDs.

Note: stable classification codes (e.g., `SAKHA`, `BOOK`) are master-data
codes (`_code` suffix), not sequenced business IDs. They do not require
`id_sequence_master`.

---

# 8. Foreign Key Convention

Foreign keys reference the internal technical primary key (`_pk`), never
the business identifier (`_id` or `_code`).

```
CORRECT:
    document_master.person_pk → person.person_pk

INCORRECT:
    document_master.person_id → person.person_id
```

This ensures relational integrity is independent of business-ID format
changes.

---

# 9. Foreign Key Naming

Foreign key columns use the parent table's PK column name directly:

```
organization.parent_organization_pk  → organization.organization_pk
organization.organization_type_pk    → organization_type_master.organization_type_pk
organization.district_pk             → district.district_pk
```

Where multiple FKs reference the same parent table, a prefix or context
differentiates:

```
person.created_by_sangha_sevi_pk
person.updated_by_sangha_sevi_pk
person.deleted_by_sangha_sevi_pk
```

---

# 10. Audit Columns

The following audit/lifecycle columns apply to all major transactional
and entity tables:

```
created_at                  TIMESTAMP NOT NULL
created_by_sangha_sevi_pk   UUID (FK)

updated_at                  TIMESTAMP NOT NULL
updated_by_sangha_sevi_pk   UUID (FK)

deleted_at                  TIMESTAMP (NULL = not deleted)
deleted_by_sangha_sevi_pk   UUID (FK)

is_active                   BOOLEAN NOT NULL DEFAULT TRUE
```

Applicability:

| Table Category | Audit Columns |
|---------------|---------------|
| Major entity tables (person, organization, membership) | Full set |
| Master/reference tables (type masters, status masters) | created_at + updated_at minimum |
| Infrastructure tables (id_sequence_master) | Contextual |

The exact applicability per table is defined in its module table-design
document.

---

# 11. Audit FK Target

The `*_by_sangha_sevi_pk` columns reference the authorized user/member
identity from the Authentication/Membership architecture.

The exact FK target table is finalized when the cross-module FK
dependency order is resolved during DDL authoring (to avoid circular
creation dependencies between Foundation, Person, and Authentication).

---

# 12. Soft Delete

The project standard prohibits ordinary physical deletion of major
transactional records.

Soft-delete semantics:

```
is_active = FALSE
deleted_at = <timestamp>
deleted_by_sangha_sevi_pk = <actor UUID>
```

Physical deletion is reserved for:

- Data correction of erroneous test/seed records
- Legal/compliance requirements (with approved process)
- Never as normal application lifecycle

---

# 13. `is_active` Column

`is_active` represents the operational state of the record.

It is distinct from domain-specific status fields:

```
is_active              → record-level operational flag
organization_status_pk → domain lifecycle status (PROPOSED/ACTIVE/SUSPENDED)
```

A record may be `is_active = TRUE` while having a domain status of
SUSPENDED or PROPOSED. The two concepts are complementary, not
redundant.

---

# 14. Historical Data Preservation

Records referenced by historical business data must remain
interpretable even after becoming inactive or soft-deleted.

This applies to:

- Master data values
- Geographic references
- Person records
- Organization records
- Membership records
- Governance assignments

No `ON DELETE CASCADE` shall destroy historical references.

---

# 15. Identifier Sequence Infrastructure

Business identifiers are generated through the centralized:

```
id_sequence_master
```

table (Foundation Module).

Each business identifier space has one authoritative sequence definition.

Owning modules define the business meaning; Foundation provides the
sequence mechanism.

| Module | Business ID | Format |
|--------|-------------|--------|
| Person | person_id | P00000001 |
| Membership | sangha_sevi_id | SS00000001 |
| Organization | organization_id | ANC0001, SAK0001, etc. |

Concurrent generation safety is a mandatory DDL requirement.

---

# 16. Master Data Architecture

The project uses a two-tier generic master framework:

```
master_category (Foundation)
      │
      └──< master_data (Foundation)
```

Plus domain-specific master tables where the business requires
independent lifecycle or additional attributes:

```
organization_type_master
organization_status_master
publication_type_master
publication_language_master
body_type_master
position_master
report_category_master
```

Decision criteria for generic vs domain master:

| Use Generic Master | Use Domain Master |
|-------------------|-------------------|
| Simple code + name + active | Complex lifecycle |
| Shared across modules | Module-specific metadata |
| No additional columns needed | Additional columns required |
| Low governance overhead | Governance-controlled vocabulary |

---

# 17. Master Data Governance

- Master category codes shall be unique
- Master value codes shall be unique within their category
- No duplicate categories across modules
- Inactive values remain for historical reference
- Inactive values are not selectable for new transactions
- Foundation owns the mechanism; business modules own the meaning

---

# 18. Cross-Module FK Principles

Foreign keys cross module boundaries through the internal PK:

```
Module A table.column_pk → Module B table.column_pk
```

Cross-module FK rules:

1. Reference the internal PK, never the business ID
2. The referenced table must exist before the referencing table (DDL order)
3. No circular FK dependencies at the DDL creation level
4. ON DELETE behaviour must be explicitly defined (no implicit CASCADE)
5. Cross-module references do not transfer ownership of the referenced entity

Common cross-module references:

| Referencing Module | Referenced Module | Through |
|-------------------|------------------|---------|
| Membership | Person | person_pk |
| Organization | Foundation (Geo) | district_pk, state_pk, country_pk |
| Governance | Person | person_pk |
| Governance | Organization | organization_pk |
| Attendance | Person | person_pk |
| Attendance | Organization | organization_pk |
| All modules | Foundation | master_data_pk |
| All modules | Authentication | user identity (via audit columns) |

---

# 19. Table Naming

Tables use lowercase `snake_case`:

```
person
organization
master_category
body_member_assignment
id_sequence_master
```

No prefix per module. No plural names.

---

# 20. Column Naming

Columns use lowercase `snake_case`:

```
first_name
date_of_birth
organization_type_code
created_at
is_active
```

Boolean columns use `is_` prefix:

```
is_active
is_verified
is_published
```

Timestamp columns use `_at` suffix:

```
created_at
updated_at
deleted_at
uploaded_at
```

---

# 21. Uniqueness Constraints

Business identifiers and codes require uniqueness:

```
person_id           → UNIQUE
organization_id     → UNIQUE
organization_type_code → UNIQUE
mobile_number       → UNIQUE (when supplied, NULL-aware)
```

Composite uniqueness where applicable:

```
master_category + value_code → UNIQUE
country + state_code         → UNIQUE
state + district_code        → UNIQUE
```

---

# 22. NULL-Aware Uniqueness

Where a column is unique only when supplied (e.g., `mobile_number`):

```
NULL values do not violate uniqueness
Non-NULL values must be globally unique
```

PostgreSQL natively supports this (NULLs are distinct in UNIQUE
constraints). No special implementation required.

---

# 23. ON DELETE Behaviour

The project default is **RESTRICT** (prevent deletion of referenced
parent).

```
ON DELETE RESTRICT   — default for all FKs
ON DELETE SET NULL   — only where explicitly designed (e.g., optional parent)
ON DELETE CASCADE    — prohibited for historical/business cross-module
                      relationships unless explicitly approved
```

Rationale: soft-delete means parent rows are never physically deleted in
normal operation, so RESTRICT prevents accidental data loss during
exceptional administrative operations.

Purely dependent metadata relationships within the same module may use
CASCADE where the owning module's table design explicitly approves it.

---

# 24. Indexing Philosophy

Indexes are implementation decisions finalized during DDL authoring.

Logical access paths that should receive indexes:

1. All foreign key columns (PostgreSQL does not auto-index FKs)
2. Business identifier columns (already covered by UNIQUE constraint)
3. Columns frequently used in WHERE clauses (status, is_active, type)
4. Columns used in ORDER BY for common queries
5. Geographic parent traversal paths
6. Search-optimized columns (via pg_trgm where applicable)

Composite indexes are deferred to query-pattern analysis.

---

# 25. No Table Duplication

A table defined in one module shall not be independently recreated in
another module.

Examples of prohibited duplication:

```
person        — only in Person Module
organization  — only in Organization Module
country       — only in Foundation
audit_master  — only in Audit Module
user_account  — shared Auth/Admin (one definition)
```

Cross-module consumption is through FK references, not table copies.

---

# 26. Module Ownership Boundaries

Each table has exactly one owning module:

| Module | Owns |
|--------|------|
| Foundation | master_category, master_data, system_setting, id_sequence_master, country, state, district, city_village |
| Heritage | founder_master, founder_teaching, nss_objective_master, nss_historical_milestone, nss_publication, historical_office_bearer, publication_type_master, publication_language_master |
| Organization | organization_type_master, organization_status_master, organization |
| Person | person, document_master |
| Governance | body_type_master, body_master, position_master, body_member_assignment, acting_position_assignment, election, election_nomination, election_vote, election_result |
| Authentication | user_account, password_history |
| Administration | role_master, permission_master, role_permission, user_role, admin_scope |
| UPBS | upbs_event, upbs_registration, delegate_card, prasad_patra, accommodation_allocation, camp_master, guest_reference |
| Reports | report_category_master, report_definition, report_filter_definition, dashboard, dashboard_widget |
| Audit | audit_master, system_event_log |
| Backup & Technical | backup_master, restore_history |

Shared tables (user_account between Auth and Admin) have one physical
definition with documented dual ownership.

---

# 27. DDL Build Order

The DDL build sequence must respect FK dependencies:

```
01_extensions.sql         — PostgreSQL extensions
02_foundation.sql         — Foundation (no FK dependencies)
03_master_tables.sql      — master_category, master_data
04_system_setting.sql     — system_setting
05_id_sequence_master.sql — id_sequence_master
06_geo_tables.sql         — country, state, district, city_village
07_person.sql             — person, document_master (depends on Foundation)
08_organization.sql       — organization tables (depends on Foundation geo)
09_authentication.sql     — user_account, password_history
10_administration.sql     — RBAC tables (depends on Auth)
...subsequent modules per frozen implementation order
```

Exact ordering is finalized during DDL authoring to resolve any circular
audit-FK bootstrapping.

---

# 28. Geographic vs Organizational Hierarchy

These are separate models that must never be conflated:

```
GEOGRAPHIC (Foundation)        ORGANIZATIONAL (Organization Module)

Country                        Kendra
   └── State                      ├── Anchalika
         └── District             ├── Zilla
               └── City/Village   └── Sakha
                                        ├── Mahila Sangha
                                        ├── Sevak Sangha
                                        └── Kumari Sangha
```

An Organization may reference a geographic location (via district_pk,
state_pk, country_pk), but geographic hierarchy does not determine
organizational reporting.

---

# 29. Self-Referencing Hierarchy

Where a table uses self-referencing hierarchy (e.g., `organization`):

```
organization.parent_organization_pk → organization.organization_pk
```

Required integrity:

- Exactly one root (parent = NULL)
- No circular references
- No orphans (non-root with NULL parent)
- Complete lineage traversal to root

Implementation mechanism (CTE, trigger, application check) is a DDL
decision.

---

# 30. Data Type Boundary

This document does not freeze:

```
Exact VARCHAR lengths
Exact TIMESTAMP precision
Exact NUMERIC precision/scale
Exact ENUM values vs master-table lookup
```

These are implementation decisions resolved during DDL authoring, guided
by actual data analysis and business requirements.

The following are frozen:

```
UUID for all _pk columns
BOOLEAN for is_active / is_* columns
TIMESTAMP for _at columns
```

---

# 31. Schema Naming

All tables reside in the `public` schema unless a future architectural
decision establishes module-specific schemas.

No schema-per-module decision has been frozen.

---

# 32. Seed Data Governance

Initial master/reference data (seed) shall be:

- Documented in the owning module's design
- Loaded via repeatable SQL scripts (not ad-hoc INSERT)
- Version-controlled alongside DDL
- Approved before insertion

Seed categories shall not be duplicated across modules.

---

# 33. Database-First Rule

The project follows strict Database-First methodology:

```
Business Rules
      ↓
ERD
      ↓
Table Design (this layer — logical)
      ↓
PostgreSQL DDL (physical)
      ↓
Django Models (rewritten to match DDL)
      ↓
FastAPI Endpoints
      ↓
UI
```

No DDL shall be generated from assumptions unsupported by the frozen
table design.

No Django model shall define schema that contradicts the DDL.

---

# 34. Implementation Boundary

This document does not define:

```
CREATE TABLE statements
ALTER TABLE statements
CHECK CONSTRAINT SQL
TRIGGER SQL
VIEW definitions
Materialized views
Django model code
FastAPI endpoint design
```

Those belong to the implementation phase and will reference this document
for conventions.

---

# 35. Open Items (Pending DDL Phase)

| Item | Status | Notes |
|------|--------|-------|
| `hierarchical_level` datatype | OPEN | Organization Module — physical type TBD |
| Audit FK bootstrapping order | OPEN | Circular dependency resolution |
| `audit_master` ↔ `system_event_log` FK | OPEN | Relationship design pending |
| `backup_master` → `restore_history` FK | OPEN | Relationship design pending |
| Exact VARCHAR lengths | OPEN | Per-column, resolved during DDL |
| `ON DELETE` per FK | OPEN | Default RESTRICT, exceptions documented |
| Index strategy | OPEN | Query-pattern driven |
| UUID generation strategy (v4 vs v7) | OPEN | Performance vs ordering trade-off |

---

# 36. Document Relationship

```
DATABASE_DESIGN_STANDARDS.md (this document)
            │
            │ consolidates conventions from
            │
            ├── modules/foundation/04_foundation_table_design.md
            ├── modules/person/04_person_table_design.md
            ├── modules/organization/05_organization_table_design.md
            ├── modules/governance/04_governance_table_design.md
            ├── modules/authentication/04_authentication_security_table_design.md
            ├── modules/administration/04_administration_table_design.md
            ├── modules/heritage/05_founder_heritage_table_design.md
            ├── modules/membership/05_membership_table_design.md
            ├── modules/family/04_family_table_design.md
            ├── modules/attendance/04_attendance_table_design.md
            ├── modules/kumari/05_kumari_table_design.md
            ├── modules/kishor/05_kishor_table_design.md
            ├── modules/mahila/05_mahila_table_design.md
            ├── modules/sevak/06_sevak_table_design.md
            ├── modules/publications/04_publications_table_design.md
            ├── modules/upbs/04_upbs_table_design.md
            ├── modules/audit/04_audit_table_design.md
            ├── modules/backup_technical/04_backup_technical_table_design.md
            └── modules/reports/04_reports_table_design.md
```

---

# 37. Status

```
DOCUMENT STATUS:
DRAFT — SOURCE ALIGNED (Consolidation)

VERSION:
1.0.0
```

This document consolidates existing frozen conventions. It does not
introduce new design decisions.

---

# End of Document
