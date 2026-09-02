# NSS ERP — Developer Reference Guide

**Document Type:** Solution Architecture — Developer Quick Reference
**Version:** 1.0
**Date:** 2026-08-16
**Status:** Approved
**Branch:** feature/ref-documentation

---

## Purpose

This document tells developers **which source documents to consult** before working on any module, in the exact order mandated by the governance lifecycle. Never code from memory — always trace back to the authoritative source.

---

## Governance Lifecycle (Mandatory Reading Order)

```
REF → AUTH → GOV → REQ → SOLUTION → CODE → TEST → RELEASE
```

For any piece of work, read the chain **top-down** before writing code. If a lower layer contradicts a higher layer, the higher layer wins.

### Layer Definitions

| Layer | Full Name | What It Contains | Developer Action |
|-------|-----------|-----------------|-----------------|
| **REF** | Authoritative Reference | Original statutory and bye-law text preserved verbatim. No interpretation, no ERP logic — just the official source wording. | Read to understand what the organization's governing documents actually say. This is the ultimate source of truth. |
| **AUTH** | Authoritative Reference Standard | Rules for how REF documents are organized, identified, versioned, and cross-referenced. Defines the `REF-00X` and `REF-MS-XXX` naming schemes. | Read if creating or modifying any REF document. Otherwise skip to GOV. |
| **GOV** | Governance Standards | How the ERP interprets and applies statutory authority. Contains frozen principles like NSS apex authority, organizational hierarchy integrity, immutable identifiers, and change control rules. | Read to understand what governance constraints your code must respect. If GOV says "only one active KENDRA allowed" — your code enforces it. |
| **REQ** | Requirements | Business and functional requirements derived from GOV and REF. Specifies what the system must do in concrete, testable terms (e.g. "membership renewal must be completed before Dola Purnima with no grace period"). | Read to understand the exact behavior your code must implement. Every feature maps to a REQ. |
| **SOLUTION** | Solution Design | Database schema, API design, UI specification, security architecture, deployment plan. The technical "how" that satisfies the REQ "what." Includes table designs, ERDs, and the Tech Stack Decisions document. | Read to understand the approved technical approach before coding. Do not invent your own schema — follow the SOLUTION doc. |
| **CODE** | Implementation | The actual Python/SQL/HTML/JS you write. Must trace to SOLUTION. Must not independently invent business rules — if a rule is missing from REQ/SOLUTION, flag it as **Pending**, do not assume. | This is where you work. Every model, view, endpoint, and template lives here. |
| **TEST** | Testing | Unit tests, integration tests, API tests, UI tests, database constraint tests. Validates that CODE correctly implements REQ. | Write tests that prove your code satisfies the requirements. Test database constraints (CHECK, UNIQUE) directly. |
| **RELEASE** | Release Documentation | Versioned release notes documenting what was delivered, what changed, and what was verified. Follows the `v0.X.Y` format under `docs/05_Releases/`. | Write release notes when a milestone is complete. Tag the commit. |

### GDR (Cross-Cutting)

The **Governance Decision Register** is not a lifecycle layer — it sits alongside the entire chain as the audit trail for governance decisions. Any normative change to AUTH, GOV, or frozen principles requires a GDR entry before implementation.

| When you need GDR | Example |
|-------------------|---------|
| Changing a frozen governance rule | Adding a new org type beyond KENDRA/ANCHALIKA/ZILLA/SAKHA/PATHA_CHAKRA |
| Modifying AUTH-001 or GOV-001..005 | Adding a new REF family, changing document status lifecycle |
| Resolving an open governance question | Defining who has final decision authority |
| Retiring or superseding a rule | Replacing GOV-DATA-001 with a newer formulation |

### Practical Example: Adding a New Feature

Suppose you need to implement **membership transfer**:

```
1. REF  → Read REF-002 (Section B) — does the bye-law mention transfer? What does it say?
2. AUTH → Not needed for this feature (no new REF docs being created)
3. GOV  → Read GOV-ORG-003 (hierarchy integrity) — transfer must maintain parent-child integrity
4. REQ  → Read/create the membership transfer requirement document
5. SOLUTION → Design the transfer table, API endpoint, UI flow
6. CODE → Implement Django model, FastAPI endpoint, HTMX form
7. TEST → Test that transfer respects all constraints (org hierarchy, membership status, audit trail)
8. RELEASE → Document in release notes
```

If at step 1 you find the bye-law says nothing about transfer, you **cannot invent a statutory rule**. You document it as an ERP implementation decision (not a statutory requirement) and proceed from REQ onward.

---

## Module-to-Document Reference Matrix

### Foundation and Location

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Location master (country, state, district, city, postal) | 1. Project Standards | `docs/00_Project_Governance/STD/01_project_standards.md` |
| | 2. Naming Conventions | `docs/00_Project_Governance/STD/02_naming_conventions.md` |
| | 3. Master Data Catalog | `docs/00_Project_Governance/STD/03_master_data_catalog.md` |
| | 4. Existing DDL (implemented) | `database/ddl/01_foundation/05_country.sql`, `09_state.sql`, `10_district.sql`, `11_city_village.sql`, `12_postal_code.sql`, `13_city_village_postal_code_map.sql` |
| | 5. Seed Data | `database/seed/01_foundation/04_country.sql`, `05_state.sql`, `06_district.sql` (city_village/postal_code seeded at deployment, not in repo) |
| ID Sequence (person code, sangha sevi, org code) | 1. Project Standards | `docs/00_Project_Governance/STD/01_project_standards.md` |
| | 2. Existing DDL (implemented) | `database/ddl/01_foundation/04_id_sequence_master.sql` |
| | 3. Seed Data | `database/seed/01_foundation/03_id_sequence_master.sql` |

---

### Person Module

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Person table, contact rules, address | 1. REF-002 (Membership Bye-Laws, Section B) | `docs/01_Authoritative_References/NSS/SECTION-B_MEMBERSHIPS/` |
| | 2. Person Design Doc | `docs/03_Solution/modules/person/01_person_design.md` |
| | 3. Person ERD | `docs/03_Solution/modules/person/02_person_erd.md` |
| | 4. Person Business Rules | `docs/03_Solution/modules/person/03_person_business_rules.md` |
| | 5. Person Table Design | `docs/03_Solution/modules/person/04_person_table_design.md` |
| | 6. Existing DDL | `database/ddl/03_person/` (all files) |
| | 7. Seed Data | `database/seed/03_person/01_person_master_tables.sql` |

---

### Organization Module

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Organization hierarchy (Kendra, Anchalika, Zilla, Sakha, Patha Chakra) | 1. REF-001 (Constitution, Section A) | `docs/01_Authoritative_References/NSS/SECTION-A_PRELIMINARY_AND_GENERAL_PROVISIONS/` |
| | 2. REF-003-C (Governance, Section C) | `docs/01_Authoritative_References/NSS/SECTION-C_CONSTITUTION_OF_THE_KENDRA_SANGHA/` |
| | 3. GOV-ORG-001 to GOV-ORG-005 | `docs/00_Project_Governance/GOV/GOV-002_Organizational_Governance_Standard.md` |
| | 4. Organization Module Overview | `docs/03_Solution/modules/organization/01_organization_module_overview.md` |
| | 5. Organization ERD | `docs/03_Solution/modules/organization/02_organization_erd.md` |
| | 6. Organization Lifecycle | `docs/03_Solution/modules/organization/03_organization_lifecycle.md` |
| | 7. Organization Business Rules (v1.1.0, GOVERNANCE ALIGNED — type-to-type parent matrix explicitly left open, not frozen) | `docs/03_Solution/modules/organization/04_organization_business_rules.md` |
| | 8. Organization Table Design (v1.1.0) | `docs/03_Solution/modules/organization/05_organization_table_design.md` |
| | 9. DDL (implemented, Organization Vertical Slice) | `database/ddl/02_organization/` |

---

### Membership Module

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Membership types, Sangha Sevi ID, renewal, transfer | 1. REF-002 (Membership Bye-Laws) | `docs/01_Authoritative_References/NSS/SECTION-B_MEMBERSHIPS/` |
| | 2. GOV-ORG-005 (Statutory Traceability) | `docs/00_Project_Governance/GOV/GOV-002_Organizational_Governance_Standard.md` |
| | 3. Membership Business Rules | `docs/03_Solution/modules/membership/` (when created) |
| | 4. CLAUDE.md (Frozen Principles) | `CLAUDE.md` |
| | 5. Tech Stack (ID sequence config) | `docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` |

---

### Family Module

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Family group, relationships, head history, transitions | 1. REF-001 Clause 12 (Mahila/Family context) | `docs/01_Authoritative_References/NSS/SECTION-A_PRELIMINARY_AND_GENERAL_PROVISIONS/` |
| | 2. CLAUDE.md (Family First Model) | `CLAUDE.md` |
| | 3. Family Business Rules | `docs/03_Solution/modules/family/` (when created) |
| | 4. Person Module (FK dependency) | `docs/03_Solution/modules/person/` |

---

### Governance Module

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Governing Body, Advisory Board, positions, elections | 1. REF-003-C (Governing Body) | `docs/01_Authoritative_References/NSS/SECTION-C_CONSTITUTION_OF_THE_KENDRA_SANGHA/` |
| | 2. REF-003-D (Advisory Board) | `docs/01_Authoritative_References/NSS/SECTION-D_ADVISORY_BOARD/` (or composite locator file) |
| | 3. REF-003-E (General Body) | `docs/01_Authoritative_References/NSS/SECTION-E_GENERAL_BODY/` (or composite locator file) |
| | 4. GOV-002 (Organizational Governance) | `docs/00_Project_Governance/GOV/GOV-002_Organizational_Governance_Standard.md` |
| | 5. GDR-004 (Authority Structure) | `docs/00_Project_Governance/GDR/GDR-004_Governance_Authority_Structure.md` |
| | 6. CLAUDE.md (Unified Body Governance Model) | `CLAUDE.md` |

---

### Attendance Module

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Weekly Sangha Puja attendance, review, enforcement | 1. REF-002 (Membership, attendance requirements) | `docs/01_Authoritative_References/NSS/SECTION-B_MEMBERSHIPS/` |
| | 2. CLAUDE.md (Attendance rules) | `CLAUDE.md` |
| | 3. Person Module (FK dependency) | `docs/03_Solution/modules/person/` |
| | 4. Membership Module (FK dependency) | Membership design docs |

---

### Authentication and Authorization

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Users, roles, permissions, scope, login | 1. Security Standards | `docs/00_Project_Governance/STD/05_security_standards.md` |
| | 2. CLAUDE.md (UUID PKs, DB naming) | `CLAUDE.md` |
| | 3. Organization Module (scope derives from org hierarchy) | `docs/03_Solution/modules/organization/` |
| | 4. Tech Stack (auth architecture) | `docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` |

---

### Mahila Sangha

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Mahila Parichalana Mandali, local Mahila Sanghas | 1. REF-001 Clause 12 (Mahila establishment) | `docs/01_Authoritative_References/NSS/SECTION-A_PRELIMINARY_AND_GENERAL_PROVISIONS/` |
| | 2. REF-MS corpus (Mahila Bye-Laws) | `docs/01_Authoritative_References/MAHILA_SANGHA/` (22 documents) |
| | 3. Mahila Module README (Mahila Sangha rules) | `docs/03_Solution/modules/mahila/README.md` |
| | 5. GOV-ORG-001, GOV-ORG-002 (apex authority, precedence) | `docs/00_Project_Governance/GOV/GOV-002_Organizational_Governance_Standard.md` |

---

### Kumari Sangha

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| KM identity, activities, training, transition to Membership | 1. Module Overview | `docs/03_Solution/modules/kumari/01_kumari_module_overview.md` |
| | 2. ERD | `docs/03_Solution/modules/kumari/02_kumari_erd.md` |
| | 3. Lifecycle | `docs/03_Solution/modules/kumari/03_kumari_lifecycle.md` |
| | 4. Business Rules (v1.0.0, SOURCE ALIGNED, KUM-001–KUM-080) | `docs/03_Solution/modules/kumari/04_kumari_business_rules.md` |
| | 5. Table Design (5 tables: kumari_sangha, kumari_membership, kumari_activity, kumari_activity_participant, kumari_membership_transition) | `docs/03_Solution/modules/kumari/05_kumari_table_design.md` |
| | 6. Existing DDL | none — no `backend/kumari/` app yet |

---

### Kishor Puja

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| KH identity, annual registration, Guardian assignment | 1. Module Overview | `docs/03_Solution/modules/kishor/01_kishor_module_overview.md` |
| | 2. ERD | `docs/03_Solution/modules/kishor/02_kishor_erd.md` |
| | 3. Lifecycle | `docs/03_Solution/modules/kishor/03_kishor_lifecycle.md` |
| | 4. Business Rules (v1.0.0, SOURCE ALIGNED, KISH-001–KISH-100, Guardian Model frozen v2.1) | `docs/03_Solution/modules/kishor/04_kishor_business_rules.md` |
| | 5. Table Design (4 tables: kishor_participant, kishor_event, kishor_event_registration, kishor_membership_transition) | `docs/03_Solution/modules/kishor/05_kishor_table_design.md` |
| | 6. Existing DDL | none — no `backend/kishor/` app yet |

---

### Sevak Sangha

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Sevak executive structure, seva/session/event rules (SEV-001–SEV-040) | 1. Module Overview | `docs/03_Solution/modules/sevak/01_sevak_module_overview.md` |
| | 2. ERD | `docs/03_Solution/modules/sevak/02_sevak_erd.md` |
| | 3. Lifecycle | `docs/03_Solution/modules/sevak/03_sevak_lifecycle.md` |
| | 4. Participation Rules | `docs/03_Solution/modules/sevak/04_sevak_participation_rules.md` |
| | 5. Business Rules | `docs/03_Solution/modules/sevak/05_sevak_business_rules.md` |
| | 6. Table Design (FROZEN — the only Frozen doc in this module) | `docs/03_Solution/modules/sevak/06_sevak_table_design.md` |
| | 7. Sangha/Seva/Events subdocs | `docs/03_Solution/modules/sevak/{sangha,seva,events}/` |
| | 8. Existing DDL | none — no `backend/sevak/` app yet |

---

### Heritage and Founder

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Founder record (singleton), teachings, publications, historical office bearers | 1. Module Overview (v1.0.0, SOURCE ALIGNED) | `docs/03_Solution/modules/heritage/01_founder_heritage_module_overview.md` |
| | 2. ERD | `docs/03_Solution/modules/heritage/02_founder_heritage_erd.md` |
| | 3. Lifecycle | `docs/03_Solution/modules/heritage/03_founder_heritage_lifecycle.md` |
| | 4. Business Rules (HER-001–HER-100) | `docs/03_Solution/modules/heritage/04_founder_heritage_business_rules.md` |
| | 5. Table Design (8 tables — only `founder_master` implemented in backend) | `docs/03_Solution/modules/heritage/05_founder_heritage_table_design.md` |
| | 6. Existing model (`founder_master` only) | `backend/heritage/models.py` |
| | 7. Heritage Module README (app status) | `docs/03_Solution/modules/heritage/README.md` |

---

### Events (UPBS, Janmotsava, Rasautsaba, etc.)

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Generic event engine, registration, delegate cards | 1. REF-003-C(i)(2) clause (x) — Janmotsava arrangements | `docs/01_Authoritative_References/NSS/SECTION-C_.../REF-003-C(i)(2).md` |
| | 2. REF-003-C(i)(2) clause (xii) — UPBS management | Same file |
| | 3. Tech Stack (offline capability section) | `docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` |
| | 4. UPBS Module README | `docs/03_Solution/modules/upbs/README.md` |

---

### Finance (Pranami, Receipts, Funds)

| Work Item | Documents to Read (in order) | Path |
|-----------|------------------------------|------|
| Funds, receipts, donations, budget | 1. REF-003-F (Funds of the Kendra Sangha) | `docs/01_Authoritative_References/NSS/SECTION-F_.../` (3 files: F[A], F[b], F[c]) |
| | 2. REF-003-G (Accounts and Audit) | `docs/01_Authoritative_References/NSS/SECTION-G_.../` |
| | 3. Finance Module README | `docs/03_Solution/modules/finance/README.md` |

---

## Key Rules for All Development

| Rule | Enforcement |
|------|------------|
| Never code a business rule from memory | Trace to REF or mark as explicit ERP implementation decision |
| Never modify a frozen module without GDR | Person, Organization, Membership identity, Family foundation are all frozen |
| Complete current feature branch before creating next | Git branch policy (`CLAUDE.md`) |
| DDL is authoritative, Django models must match it | Two-track reconciliation (`CLAUDE.md`) |
| Business IDs use `_code` suffix, never `_id` | DDL naming convention |
| FKs reference internal `_pk`, never business codes | Referential integrity standard |
| Every table needs audit columns | `created_at`, `updated_at`, `deleted_at`, `is_active` |
| Deliver complete files, never partials | Project working rule |

---

## Quick Lookup: Where Is This Rule Defined?

| If you need... | Look in... |
|----------------|-----------|
| Statutory wording (exact clauses) | `docs/01_Authoritative_References/NSS/` or `MAHILA_SANGHA/` |
| How the governance framework works | `docs/00_Project_Governance/GOV/GOV-001_Project_Governance_Principles.md` |
| How REF docs are managed | `docs/00_Project_Governance/AUTH/AUTH-001_Authoritative_Reference_Standard.md` |
| Organizational hierarchy rules | `docs/00_Project_Governance/GOV/GOV-002_Organizational_Governance_Standard.md` |
| Traceability requirements | `docs/00_Project_Governance/GOV/GOV-004_Requirement_Traceability_Standard.md` |
| Change control process | `docs/00_Project_Governance/GOV/GOV-005_Governance_Change_Control_Standard.md` |
| Past governance decisions | `docs/00_Project_Governance/GDR/GDR-001_Governance_Decision_Register.md` through `GDR-004` |
| Frozen architecture decisions | `CLAUDE.md` |
| Tech stack and hosting | `docs/03_Solution/architecture/TECH_STACK_DECISIONS.md` |
| DB naming and standards | `docs/00_Project_Governance/STD/02_naming_conventions.md` |
| Security requirements | `docs/00_Project_Governance/STD/05_security_standards.md` |

---

# End of Document
