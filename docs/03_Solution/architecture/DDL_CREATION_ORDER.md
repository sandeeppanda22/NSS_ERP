# NSS ERP — DDL Creation Order

**Document ID:** SOL-ARCH-010
**Version:** 1.1.0
**Status:** FROZEN
**Date:** 2026-08-28
**Amendment:** 2026-08-28 — PIN Code Geographic Model (§12 added)
**Parent Documents:**
- SOL-ARCH-009 — Physical FK Dependency Graph
- SOL-ARCH-008 — Implementation Dependency Order
- DATABASE_DESIGN_STANDARDS.md

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the exact physical CREATE TABLE execution sequence
for the NSS ERP PostgreSQL database.

This is Gate ⑨ of the pre-DDL architecture gates.

The sequence is derived directly from the machine-verified topological
depth output in SOL-ARCH-009 §9.1. No new dependency decisions are
introduced by this document.

---

# 2. Authority Chain

```text
SOL-ARCH-008 — Implementation Tier Order (module grouping)
        │
        ▼
SOL-ARCH-009 — Physical FK Dependency Graph (table-level FKs)
        │
        ▼
SOL-ARCH-010 — DDL Creation Order (this document)
        │
        ▼
Foundation Vertical Slice (actual CREATE TABLE DDL)
```

---

# 3. Ordering Principles

1. A referenced table must exist before any table that declares an FK
   to it can be created.

2. Table creation depth takes precedence over module tier. A table with
   zero FK dependencies (e.g., `financial_year`) is created at Depth 0,
   regardless of its owning module's implementation tier.

3. Tables at the same depth have no mutual FK dependency and may be
   created in any order or in parallel.

4. Self-referencing FKs are added within the same CREATE TABLE statement
   or immediately after table creation (same depth — no ordering issue).

5. Audit-actor FKs (`*_by_sangha_sevi_pk`) are deliberately excluded
   from Depths 0–7 and added in a separate deferred pass after
   `sangha_sevi` exists and contains at least one record.

6. The `correspondence_finance_reference` FK to `financial_transaction`
   is deferred to the same pass because it crosses an otherwise
   unrelated module boundary.

7. Candidate (P&E) tables are documented for completeness but are NOT
   part of the frozen executable sequence.

---

# 4. Frozen Executable Sequence (86 tables)

## Depth 0 — Root Tables (17)

No FK dependencies. Can be created in any order.

```text
 1. master_category               Foundation
 2. system_setting                 Foundation
 3. id_sequence_master             Foundation
 4. country                        Foundation
 5. document_master                Foundation
 6. field_change_log               Foundation
 7. organization_type_master       Organization
 8. organization_status_master     Organization
 9. audit_master                   Audit
10. system_event_log               Audit
11. body_type_master               Governance
12. position_master                Governance
13. role_master                    Administration
14. permission_master              Administration
15. property                       Assets & Property
16. asset                          Assets & Property
17. financial_year                 Finance
```

---

## Depth 1 — Depends only on Depth 0 (8)

```text
18. master_data                    Foundation        ← master_category
19. state                          Foundation        ← country
20. role_permission                Administration    ← role_master, permission_master
21. founder                        Heritage          ← document_master
22. property_document              Assets & Property ← property, document_master
23. asset_document                 Assets & Property ← asset, document_master
24. property_statutory_record      Assets & Property ← property
25. maintenance_record             Assets & Property ← property, asset
```

---

## Depth 2 — Depends on Depth 0–1 (6)

```text
26. district                       Foundation        ← state
27. person                         Person            ← master_data
28. publication                    Publications      ← master_data, document_master
29. founder_timeline               Heritage          ← founder
30. founder_gallery                Heritage          ← founder, document_master
31. spiritual_literature           Heritage          ← master_data, document_master
```

---

## Depth 3 — Depends on Depth 0–2 (3)

```text
32. city_village                   Foundation        ← district
33. organization                   Organization      ← organization_type_master,
                                                       organization_status_master,
                                                       district, state, country
34. user_account                   Authentication    ← person
```

Self-referencing FK: `organization.parent_organization_pk` references
`organization.organization_pk` — added in the same CREATE TABLE or as
an immediate ALTER TABLE within this depth.

---

## Depth 4 — Depends on Depth 0–3 (12)

```text
35. sangha_sevi                    Membership        ← person, master_data, organization
36. family_group                   Family            ← organization
37. weekly_sangha_puja             Attendance        ← organization
38. body_master                    Governance        ← body_type_master, organization
39. correspondence                 Administration    ← person, organization, master_data
40. admin_scope                    Administration    ← role_master, user_account, organization
41. user_role                      Administration    ← role_master, user_account
42. password_history               Authentication    ← user_account
43. custodianship                  Assets & Property ← property, asset, organization
44. financial_scope                Finance           ← organization
45. kumari_sangha                  Kumari            ← organization
46. kishor_event                   Kishor            ← organization
```

**Critical milestone:** `sangha_sevi` (table #35) is created here.
This enables all downstream tables that reference membership identity,
and is required before the deferred audit-actor FK pass.

---

## Depth 5 — Depends on Depth 0–4 (23)

```text
47. membership_status_history      Membership        ← sangha_sevi, master_data
48. membership_renewal_request     Membership        ← sangha_sevi
49. membership_renewal_history     Membership        ← sangha_sevi
50. membership_transfer_history    Membership        ← sangha_sevi, organization
51. membership_journey_event       Membership        ← sangha_sevi
52. probationary_member_review     Membership        ← sangha_sevi
53. anumati_patra                  Membership        ← sangha_sevi
54. parichaya_patra                Membership        ← sangha_sevi
55. family_relationship            Family            ← family_group, person, master_data
56. family_head_history            Family            ← family_group, person
57. family_transition_history      Family            ← family_group, person
58. weekly_sangha_puja_attendance  Attendance        ← weekly_sangha_puja, sangha_sevi,
                                                       organization
59. attendance_exception           Attendance        ← sangha_sevi
60. attendance_review              Attendance        ← sangha_sevi
61. body_member_assignment         Governance        ← body_master, position_master,
                                                       person, sangha_sevi
62. acting_position_assignment     Governance        ← body_master, position_master, person
63. election                       Governance        ← body_master, organization
64. correspondence_document        Administration    ← correspondence, document_master
65. fund_master                    Finance           ← financial_scope, organization
66. kishor_participant             Kishor            ← person, organization, sangha_sevi
67. kumari_membership              Kumari            ← kumari_sangha, person, sangha_sevi
68. kumari_activity                Kumari            ← kumari_sangha
69. sevak_participation            Sevak             ← person, sangha_sevi
```

---

## Depth 6 — Depends on Depth 0–5 (14)

```text
70. anumati_patra_history          Membership        ← anumati_patra
71. parichaya_patra_history        Membership        ← parichaya_patra
72. election_nomination            Governance        ← election, person
73. election_vote                  Governance        ← election
74. election_result                Governance        ← election, person
75. financial_transaction          Finance           ← financial_year, financial_scope,
                                                       fund_master, person, sangha_sevi
76. financial_transfer             Finance           ← financial_year, financial_scope,
                                                       fund_master
77. kishor_event_registration      Kishor            ← kishor_participant, kishor_event,
                                                       organization, sangha_sevi
78. kishor_guardian_history         Kishor            ← kishor_participant, sangha_sevi
79. kishor_transition              Kishor            ← kishor_participant, sangha_sevi
80. kumari_activity_participant    Kumari            ← kumari_activity, kumari_membership
81. kumari_membership_transition   Kumari            ← kumari_membership, sangha_sevi
82. sevak_sakha_association        Sevak             ← sevak_participation, organization
83. sevak_status_history           Sevak             ← sevak_participation
```

---

## Depth 7 — Deepest Leaf Tables (3)

```text
84. financial_receipt              Finance           ← financial_transaction, person
85. financial_payment              Finance           ← financial_transaction, person
86. sevak_reactivation_review      Sevak             ← sevak_sakha_association
```

---

# 5. Deferred Constraints (Pass 2)

After all 86 tables exist and foundational seed data has been inserted:

## 5.1 Audit-Actor FK Constraints

Add to EVERY table that carries audit-actor columns:

```text
ALTER TABLE <table_name>
  ADD CONSTRAINT fk_<table>_created_by
    FOREIGN KEY (created_by_sangha_sevi_pk)
    REFERENCES sangha_sevi (sangha_sevi_pk);

ALTER TABLE <table_name>
  ADD CONSTRAINT fk_<table>_updated_by
    FOREIGN KEY (updated_by_sangha_sevi_pk)
    REFERENCES sangha_sevi (sangha_sevi_pk);

ALTER TABLE <table_name>
  ADD CONSTRAINT fk_<table>_deleted_by
    FOREIGN KEY (deleted_by_sangha_sevi_pk)
    REFERENCES sangha_sevi (sangha_sevi_pk);
```

Precondition: `sangha_sevi` must contain at least one record (the
initial data-loading identity) before these constraints are enforced.

## 5.2 Correspondence → Finance FK

```text
ALTER TABLE correspondence_finance_reference
  ADD CONSTRAINT fk_corr_fin_ref_transaction
    FOREIGN KEY (financial_transaction_pk)
    REFERENCES financial_transaction (financial_transaction_pk);
```

Precondition: `financial_transaction` table exists (Depth 6, table #75).

---

# 6. Candidate Tables — NOT EXECUTABLE

The following 7 tables belong to Programme & Events (Module #21).
They are included for planning purposes only and SHALL NOT be created
until Module #21 is formally frozen.

```text
C1. programme_type               P&E              (Depth 0 equivalent)
C2. event                        P&E              ← programme_type, organization
C3. event_day                    P&E              ← event
C4. event_session                P&E              ← event_day
C5. event_registration           P&E              ← event, person, sangha_sevi
C6. event_location               P&E              ← event, organization
C7. event_history                P&E              ← event
```

When Module #21 is frozen, these tables will be assigned to appropriate
depths and the frozen sequence will be versioned (SOL-ARCH-010 v1.1+).

---

# 7. Self-Referencing FKs

| Table | Column | Strategy |
|-------|--------|----------|
| `organization` | `parent_organization_pk` → `organization.organization_pk` | Include in CREATE TABLE (REFERENCES same table) or ADD CONSTRAINT immediately after CREATE — both valid since the table already exists at that point |

No other self-referencing FKs exist in the frozen schema.

---

# 8. Seed-Data Ordering

Seed data insertion follows the same depth order as table creation.
Only already-established seed requirements are documented here:

| Depth | Seed requirement | Source |
|------:|-----------------|--------|
| 0 | `master_category` values (GENDER, MEMBERSHIP_TYPE, MEMBERSHIP_STATUS, etc.) | Foundation table design §6.4 |
| 0 | `country` (at minimum India) | Foundation geographic hierarchy |
| 1 | `master_data` values for each seeded category | Foundation table design §7 |
| 1 | `state` (at minimum Odisha) | Foundation geographic hierarchy |
| 2 | `district` (at minimum relevant districts) | Foundation geographic hierarchy |
| 3 | `organization_type_master` values (KENDRA, SAKHA, PATHA_CHAKRA) | Organization table design §9 |
| 3 | `organization_status_master` values (PROPOSED, APPROVED, ACTIVE, INACTIVE, ARCHIVED) | Organization table design §16 |
| 3 | `organization` (at minimum Kendra) | Required for downstream FKs |

No new mandatory seed requirements are introduced by this document.
Additional seed data will be defined during each module's vertical slice.

---

# 9. Implementation Notes

## 9.1 Vertical Slice Alignment

During implementation, a vertical slice creates only the tables
belonging to its module (plus any prerequisites already created by
earlier slices). The depth numbers above are the GLOBAL creation order
— not the per-slice order.

Example — Foundation vertical slice creates:

```text
Depth 0: master_category, system_setting, id_sequence_master,
         country, document_master, field_change_log
Depth 1: master_data, state
Depth 2: district
Depth 3: city_village
```

Then inserts Foundation seed data before proceeding to API/UI.

## 9.2 Parallel Creation Within a Depth

Tables at the same depth have no mutual FK dependency. An
implementation may create them in parallel, in any order, or in
alphabetical order within a single migration file — all are valid.

## 9.3 Constraint Naming Convention

FK constraint names shall follow:

```text
fk_<source_table>_<fk_column_without_suffix>
```

Example:

```text
fk_sangha_sevi_person
fk_sangha_sevi_organization
fk_family_relationship_family_group
```

The exact naming convention may be refined in DATABASE_DESIGN_STANDARDS.md
during the Foundation vertical slice. This document establishes the
principle; the standard establishes the exact format.

---

# 10. What This Document Does NOT Do

- Does not generate actual PostgreSQL DDL syntax
- Does not define column types, constraints, or indexes
- Does not create seed-data catalogues beyond what is already frozen
- Does not override module table-design documents
- Does not make P&E candidate tables executable

---

# 11. Amendment — PIN Code Geographic Model (2026-08-28)

## 11.1 Decision

The Foundation geographic reference hierarchy is extended to include
PIN codes (postal codes) as a searchable geographic entity with an M:N
relationship to `city_village`.

## 11.2 Rationale

PIN codes are part of the canonical searchable geographic hierarchy, not
merely display fields. They support:

- Hierarchical location search
- Address validation and autocomplete
- Map visualization ("find nearby Sanghas")
- Consistent location model across Organization and Person

## 11.3 Tables Added

| Table | Depth | FK Dependencies | Module |
|-------|------:|-----------------|--------|
| `postal_code` | 1 | `country` | Foundation |
| `city_village_postal_code_map` | 4 | `city_village`, `postal_code` | Foundation |

## 11.4 Updated Sequence

```text
87. postal_code                   Foundation        ← country
88. city_village_postal_code_map  Foundation        ← city_village, postal_code
```

`postal_code` is Depth 1 (depends only on `country`, Depth 0).
`city_village_postal_code_map` is Depth 4 (depends on `city_village` at
Depth 3 and `postal_code` at Depth 1).

## 11.5 Impact on Global Inventory

- Frozen executable tables: 86 → **88**
- Foundation tables: 10 → **12**
- Creation depths: unchanged (still Depth 0 through Depth 7)
- Cycle-free: YES (no new cycles — both tables are leaf additions)
- Candidate tables: unchanged (7, Programme & Events)

## 11.6 Organization Dependency (noted, not owned by this document)

`organization` will reference:

```text
city_village_pk    → city_village (Foundation)
postal_code        → VARCHAR (denormalized for display/search)
latitude           → DECIMAL (exact physical location)
longitude          → DECIMAL (exact physical location)
```

Latitude/longitude describe the physical location of a specific
organization, not a geographic reference entity. They remain on
`organization`, not on Foundation tables.

---

# 12. Status

```text
DOCUMENT STATUS:
FROZEN

DOCUMENT ID:
SOL-ARCH-010

VERSION:
1.1.0

DATE:
2026-08-28

AMENDMENT:
PIN Code Geographic Model (2026-08-28)

FROZEN TABLES IN SEQUENCE:
88

CREATION DEPTHS:
8 (Depth 0 through Depth 7)

DEFERRED CONSTRAINTS:
Audit-actor FKs (all tables) + correspondence_finance_reference

CANDIDATE (NOT EXECUTABLE):
7 (Programme & Events)

CYCLE-FREE:
YES — machine-verified (SOL-ARCH-009 §9.1) + amendment adds no cycles

AUTHORITY:
This is the DDL creation-order authority for the NSS ERP.

NEXT:
Foundation Vertical Slice → actual CREATE TABLE DDL
```
