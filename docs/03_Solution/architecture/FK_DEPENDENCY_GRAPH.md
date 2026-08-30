# NSS ERP — Physical FK Dependency Graph

**Document ID:** SOL-ARCH-009
**Version:** 1.0.0
**Status:** FROZEN
**Date:** 2026-08-28
**Parent Documents:**
- IMPLEMENTATION_DEPENDENCY_ORDER.md (SOL-ARCH-008)
- MODULE_DEPENDENCY_MAP.md
- Individual Module Table Design documents (all 22 modules)

**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document maps every table-to-table foreign key dependency in the
NSS ERP schema. It determines the physical DDL creation order —
referenced tables must exist before referencing tables can be created.

This is Gate ⑧ of the pre-DDL architecture gates.

---

# 2. Scope

- Every frozen/documented table across all 22 modules
- Every explicit FK column identified in table design documents
- Audit-actor FKs (`*_by_sangha_sevi_pk`) treated as a special class
- Self-referencing FKs noted but not blocking

## 2.1 Table Classification

| Category | Count | DDL Status |
|----------|------:|------------|
| Frozen (executable) | 86 | Ready for DDL creation |
| Candidate (P&E — Module #21 pending freeze) | 7 | NOT executable until formal module freeze |
| Deferred FK only (no new table) | 1 | Phase 6 ALTER TABLE |
| **Total mapped** | **94** | — |

## 2.2 Explicitly NOT Mapped

- **UPBS** — table designs predate the P&E reconciliation; UPBS tables
  will be remapped after P&E is formally frozen and UPBS extensions are
  defined against the common Event model.
- **Mahila** — no module-owned tables (operates through configuration/
  governance assignments on shared tables).
- **Reports** — query/view layer; no module-owned transactional tables.
- **Backup & Technical** — infrastructure; no business-domain FKs.

## 2.3 Important Distinction

```text
Module implementation tier  ≠  Table creation depth
```

A table may have zero FK dependencies (e.g., `financial_year`) and
therefore appear at Depth 0 in the creation order, even though its
owning module is in a later implementation tier. The tier governs
when the module's vertical slice (DB → API → UI) begins; the creation
depth governs only the physical DDL execution sequence.

---

# 3. Audit FK Bootstrap Problem

Almost every table contains:

```text
created_by_sangha_sevi_pk  → sangha_sevi.sangha_sevi_pk
updated_by_sangha_sevi_pk  → sangha_sevi.sangha_sevi_pk
deleted_by_sangha_sevi_pk  → sangha_sevi.sangha_sevi_pk
```

`sangha_sevi` is in the Membership module (Tier 4). This creates a
circular dependency: Foundation tables need `sangha_sevi` for audit
columns, but `sangha_sevi` needs Foundation's `master_data` for
`membership_type_pk` and `membership_status_pk`.

### Resolution Strategy: Two-Pass DDL

```text
PASS 1 — Create all tables WITHOUT audit-actor FK constraints
PASS 2 — ALTER TABLE ADD CONSTRAINT for audit-actor FKs
```

This is the approved audit-FK bootstrap mechanism. Audit-actor FKs are
therefore EXCLUDED from the dependency graph below — they do not affect
table creation order.

---

# 4. Complete Table Inventory (by module)

## Foundation (10 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `master_category` | — | — |
| 2 | `master_data` | master_category_pk → master_category | — |
| 3 | `system_setting` | — | — |
| 4 | `id_sequence_master` | — | — |
| 5 | `country` | — | — |
| 6 | `state` | country_pk → country | — |
| 7 | `district` | state_pk → state | — |
| 8 | `city_village` | district_pk → district | — |
| 9 | `document_master` | — | — |
| 10 | `field_change_log` | — | — |

## Person (1 table)

| # | Table | Cross-module FKs |
|--:|-------|-----------------|
| 1 | `person` | gender_pk → master_data (Foundation) |

## Organization (3 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `organization_type_master` | — | — |
| 2 | `organization_status_master` | — | — |
| 3 | `organization` | organization_type_pk → organization_type_master, organization_status_pk → organization_status_master, parent_organization_pk → organization (self) | district_pk → district (Foundation), state_pk → state (Foundation), country_pk → country (Foundation) |

## Heritage (4 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `founder` | — | photo_document_pk → document_master (Foundation) |
| 2 | `founder_timeline` | founder_pk → founder | — |
| 3 | `spiritual_literature` | — | photo_document_pk → document_master (Foundation), publication_type_pk → master_data (Foundation), language_pk → master_data (Foundation), document_pk → document_master (Foundation), cover_photo_document_pk → document_master (Foundation) |
| 4 | `founder_gallery` | founder_pk → founder | photo_document_pk → document_master (Foundation) |

Note: Heritage's `spiritual_literature` uses `publication_type_pk` and
`language_pk` referencing Foundation's `master_data` table.

## Family (4 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `family_group` | — | sakha_pk → organization (Organization) |
| 2 | `family_relationship` | family_group_pk → family_group | person_pk → person (Person), relationship_type_pk → master_data (Foundation) |
| 3 | `family_head_history` | family_group_pk → family_group | person_pk → person (Person) |
| 4 | `family_transition_history` | old_family_group_pk → family_group, new_family_group_pk → family_group | person_pk → person (Person) |

## Membership (11 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `sangha_sevi` | — | person_pk → person (Person), membership_type_pk → master_data (Foundation), membership_status_pk → master_data (Foundation), organization_pk → organization (Organization) |
| 2 | `membership_status_history` | sangha_sevi_pk → sangha_sevi | membership_status_pk → master_data (Foundation) |
| 3 | `membership_renewal_request` | sangha_sevi_pk → sangha_sevi, requested_by_sangha_sevi_pk → sangha_sevi, reviewed_by_sangha_sevi_pk → sangha_sevi | — |
| 4 | `membership_renewal_history` | sangha_sevi_pk → sangha_sevi, approved_by_sangha_sevi_pk → sangha_sevi | — |
| 5 | `membership_transfer_history` | sangha_sevi_pk → sangha_sevi, approved_by_sangha_sevi_pk → sangha_sevi | old_organization_pk → organization (Organization), new_organization_pk → organization (Organization) |
| 6 | `membership_journey_event` | sangha_sevi_pk → sangha_sevi | — |
| 7 | `probationary_member_review` | sangha_sevi_pk → sangha_sevi, reviewed_by_sangha_sevi_pk → sangha_sevi | — |
| 8 | `anumati_patra` | sangha_sevi_pk → sangha_sevi | — |
| 9 | `anumati_patra_history` | anumati_patra_pk → anumati_patra | — |
| 10 | `parichaya_patra` | sangha_sevi_pk → sangha_sevi | — |
| 11 | `parichaya_patra_history` | parichaya_patra_pk → parichaya_patra | — |

## Authentication (2 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `user_account` | — | person_pk → person (Person) |
| 2 | `password_history` | user_account_pk → user_account | — |

## Administration (8 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `role_master` | — | — |
| 2 | `permission_master` | — | — |
| 3 | `role_permission` | role_master_pk → role_master, permission_master_pk → permission_master | — |
| 4 | `user_role` | role_master_pk → role_master | user_account_pk → user_account (Authentication) |
| 5 | `admin_scope` | role_master_pk → role_master | user_account_pk → user_account (Authentication), organization_pk → organization (Organization) |
| 6 | `correspondence` | — | sender_person_pk → person (Person), sender_organization_pk → organization (Organization), recipient_person_pk → person (Person), recipient_organization_pk → organization (Organization), responsible_person_pk → person (Person), responsible_organization_pk → organization (Organization), medium_master_data_pk → master_data (Foundation), status_master_data_pk → master_data (Foundation) |
| 7 | `correspondence_document` | correspondence_pk → correspondence | document_master_pk → document_master (Foundation) |
| 8 | `correspondence_finance_reference` | correspondence_pk → correspondence | financial_transaction_pk → financial_transaction (Finance) |

## Audit (2 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `audit_master` | — | — |
| 2 | `system_event_log` | — | — |

Note: Audit tables have minimal FKs. The audit actor columns on OTHER
tables reference Membership — handled by the two-pass strategy (§3).

## Attendance (4 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `weekly_sangha_puja` | — | sakha_pk → organization (Organization) |
| 2 | `weekly_sangha_puja_attendance` | weekly_sangha_puja_pk → weekly_sangha_puja | sangha_sevi_pk → sangha_sevi (Membership), attendance_sakha_pk → organization (Organization) |
| 3 | `attendance_exception` | — | sangha_sevi_pk → sangha_sevi (Membership) |
| 4 | `attendance_review` | — | sangha_sevi_pk → sangha_sevi (Membership) |

## Governance (9 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `body_type_master` | — | — |
| 2 | `body_master` | body_type_master_pk → body_type_master | organization_pk → organization (Organization) |
| 3 | `position_master` | — | — |
| 4 | `body_member_assignment` | body_master_pk → body_master, position_master_pk → position_master | person_pk → person (Person), sangha_sevi_pk → sangha_sevi (Membership) |
| 5 | `acting_position_assignment` | body_master_pk → body_master, position_master_pk → position_master | person_pk → person (Person) |
| 6 | `election` | body_master_pk → body_master | organization_pk → organization (Organization) |
| 7 | `election_nomination` | election_pk → election | person_pk → person (Person) |
| 8 | `election_vote` | election_pk → election | — |
| 9 | `election_result` | election_pk → election | person_pk → person (Person) |

## Assets & Property (7 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `property` | — | — |
| 2 | `asset` | — | — |
| 3 | `custodianship` | property_pk → property (nullable), asset_pk → asset (nullable) | custodian_organization_pk → organization (Organization) |
| 4 | `property_statutory_record` | property_pk → property | — |
| 5 | `maintenance_record` | property_pk → property (nullable), asset_pk → asset (nullable) | — |
| 6 | `property_document` | property_pk → property | document_master_pk → document_master (Foundation) |
| 7 | `asset_document` | asset_pk → asset | document_master_pk → document_master (Foundation) |

## Programme & Events (7 candidate tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `programme_type` | — | — |
| 2 | `event` | programme_type_pk → programme_type | organizer_organization_pk → organization (Organization) |
| 3 | `event_day` | event_pk → event | — |
| 4 | `event_session` | event_day_pk → event_day | — |
| 5 | `event_registration` | event_pk → event | person_pk → person (Person), sangha_sevi_pk → sangha_sevi (Membership) |
| 6 | `event_location` | event_pk → event | organization_pk → organization (Organization) |
| 7 | `event_history` | event_pk → event | — |

Status: CANDIDATE — Module #21 pending formal freeze.

## Kumari (5 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `kumari_sangha` | — | organization_pk → organization (Organization) |
| 2 | `kumari_membership` | kumari_sangha_pk → kumari_sangha | person_pk → person (Person), sangha_sevi_pk → sangha_sevi (Membership) |
| 3 | `kumari_activity` | kumari_sangha_pk → kumari_sangha | — |
| 4 | `kumari_activity_participant` | kumari_activity_pk → kumari_activity, kumari_membership_pk → kumari_membership | — |
| 5 | `kumari_membership_transition` | kumari_membership_pk → kumari_membership | sangha_sevi_pk → sangha_sevi (Membership) |

## Kishor (5 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `kishor_participant` | — | person_pk → person (Person), sakha_organization_pk → organization (Organization), guardian_sangha_sevi_pk → sangha_sevi (Membership), assigned_by_sakha_pk → organization (Organization) |
| 2 | `kishor_event` | — | host_organization_pk → organization (Organization), location_pk → (TBD — P&E event_location or Organization) |
| 3 | `kishor_event_registration` | kishor_participant_pk → kishor_participant, kishor_event_pk → kishor_event | sakha_organization_pk → organization (Organization), guardian_sangha_sevi_pk → sangha_sevi (Membership) |
| 4 | `kishor_guardian_history` | kishor_participant_pk → kishor_participant | sangha_sevi_pk → sangha_sevi (Membership) |
| 5 | `kishor_transition` | kishor_participant_pk → kishor_participant | sangha_sevi_pk → sangha_sevi (Membership) |

## Sevak (4 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `sevak_participation` | — | person_pk → person (Person), sangha_sevi_pk → sangha_sevi (Membership) |
| 2 | `sevak_sakha_association` | sevak_participation_pk → sevak_participation | organization_pk → organization (Organization) |
| 3 | `sevak_status_history` | sevak_participation_pk → sevak_participation | — |
| 4 | `sevak_reactivation_review` | sevak_sakha_association_pk → sevak_sakha_association | — |

## Mahila (0 module-owned tables)

No dedicated physical tables. Mahila operates through configuration,
governance body assignments, and permissions on shared tables.

## Publications (1+ tables — exact count pending freeze)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `publication` | — | publication_type_pk → master_data (Foundation), language_pk → master_data (Foundation), document_pk → document_master (Foundation), cover_photo_document_pk → document_master (Foundation) |

## UPBS (domain-specific tables — pending P&E reconciliation)

UPBS tables will become extensions of the common Event model after
Programme & Events is formally frozen. Exact table list deferred.

## Finance (7 tables)

| # | Table | Module-internal FKs | Cross-module FKs |
|--:|-------|--------------------|--------------------|
| 1 | `financial_year` | — | — |
| 2 | `financial_scope` | — | organization_pk → organization (Organization) |
| 3 | `fund_master` | financial_scope_pk → financial_scope | organization_pk → organization (Organization) |
| 4 | `financial_transaction` | financial_year_pk → financial_year, financial_scope_pk → financial_scope, fund_master_pk → fund_master | person_pk → person (Person), membership_pk → sangha_sevi (Membership) |
| 5 | `financial_receipt` | financial_transaction_pk → financial_transaction | person_pk → person (Person) |
| 6 | `financial_payment` | financial_transaction_pk → financial_transaction | person_pk → person (Person) |
| 7 | `financial_transfer` | source_scope_pk → financial_scope, destination_scope_pk → financial_scope, source_fund_pk → fund_master, destination_fund_pk → fund_master | financial_year_pk → financial_year |

## Reports (0 module-owned tables)

Reports is a query/view layer — no module-owned transactional tables.

## Backup & Technical (0 module-owned tables for FK purposes)

Infrastructure/configuration tables with no business-domain FKs.

---

# 5. Cross-Module FK Dependency Matrix

This matrix shows which modules a given module depends on (through FK
references to tables owned by that module):

| Module | Depends on (via FK) |
|--------|---------------------|
| Foundation | — (root) |
| Person | Foundation |
| Organization | Foundation |
| Heritage | Foundation |
| Family | Foundation, Person, Organization |
| Membership | Foundation, Person, Organization |
| Authentication | Person |
| Administration | Foundation, Person, Organization, Authentication, Finance* |
| Audit | — (no cross-module FKs) |
| Attendance | Organization, Membership |
| Governance | Organization, Person, Membership |
| Assets & Property | Foundation, Organization |
| Programme & Events | Organization, Person, Membership |
| Kumari | Organization, Person, Membership |
| Kishor | Organization, Person, Membership |
| Sevak | Organization, Person, Membership |
| Publications | Foundation |
| Finance | Organization, Person, Membership |
| Mahila | — (no owned tables) |
| Reports | — (no owned tables) |
| Backup & Technical | — (no owned tables) |

`*` Administration's `correspondence_finance_reference` has an FK to
`financial_transaction` (Finance). This is a nullable optional reference
— Administration can be created without it and the FK added later (same
two-pass approach as audit FKs).

---

# 6. DDL Creation Order (FROZEN tables only)

Based on the dependency graph, verified by machine topological sort
(Kahn's algorithm — see §6.1), the physical table creation order is:

## 6.1 Cycle Verification

```text
Algorithm:   Kahn's topological sort
Input:       86 frozen tables, all explicit FK edges (excluding audit-actor)
Result:      ALL 86 tables successfully ordered — NO CYCLES
Max depth:   7
```

This confirms the "no circular FK dependencies" claim is machine-verified,
not merely asserted from documentation review.

```text
PHASE 1 — No cross-module dependencies (root tables)
───────────────────────────────────────────────────
  Foundation:
    master_category
    system_setting
    id_sequence_master
    country
    document_master
    field_change_log

  Foundation (depends on Foundation-internal):
    master_data          (← master_category)
    state                (← country)
    district             (← state)
    city_village         (← district)

  Organization (standalone masters):
    organization_type_master
    organization_status_master

  Audit:
    audit_master
    system_event_log

PHASE 2 — Depends on Foundation + Organization internals
──────────────────────────────────────────────────────────
  Person:
    person               (← master_data)

  Organization:
    organization         (← org_type_master, org_status_master,
                           district, state, country, self-ref)

PHASE 3 — Depends on Person + Organization
────────────────────────────────────────────
  Heritage:
    founder              (← document_master)
    founder_timeline     (← founder)
    spiritual_literature (← master_data, document_master)
    founder_gallery      (← founder, document_master)

  Family:
    family_group         (← organization)
    family_relationship  (← family_group, person, master_data)
    family_head_history  (← family_group, person)
    family_transition_history (← family_group, person)

  Membership:
    sangha_sevi          (← person, master_data, organization)

  Authentication:
    user_account         (← person)
    password_history     (← user_account)

PHASE 4 — Depends on Membership (sangha_sevi)
─────────────────────────────────────────────────
  Membership (remaining):
    membership_status_history     (← sangha_sevi, master_data)
    membership_renewal_request    (← sangha_sevi)
    membership_renewal_history    (← sangha_sevi)
    membership_transfer_history   (← sangha_sevi, organization)
    membership_journey_event      (← sangha_sevi)
    probationary_member_review    (← sangha_sevi)
    anumati_patra                 (← sangha_sevi)
    anumati_patra_history         (← anumati_patra)
    parichaya_patra               (← sangha_sevi)
    parichaya_patra_history       (← parichaya_patra)

  Administration (RBAC):
    role_master
    permission_master
    role_permission              (← role_master, permission_master)
    user_role                    (← role_master, user_account)
    admin_scope                  (← role_master, user_account, organization)

  Administration (Correspondence):
    correspondence               (← person, organization, master_data)
    correspondence_document      (← correspondence, document_master)

  Attendance:
    weekly_sangha_puja           (← organization)
    weekly_sangha_puja_attendance (← weekly_sangha_puja, sangha_sevi, organization)
    attendance_exception         (← sangha_sevi)
    attendance_review            (← sangha_sevi)

  Governance:
    body_type_master
    body_master                  (← body_type_master, organization)
    position_master
    body_member_assignment       (← body_master, position_master, person, sangha_sevi)
    acting_position_assignment   (← body_master, position_master, person)
    election                     (← body_master, organization)
    election_nomination          (← election, person)
    election_vote                (← election)
    election_result              (← election, person)

  Assets & Property:
    property
    asset
    custodianship                (← property, asset, organization)
    property_statutory_record    (← property)
    maintenance_record           (← property, asset)
    property_document            (← property, document_master)
    asset_document               (← asset, document_master)

PHASE 5 — Depends on Phase 4 (Membership + Organization + Person)
──────────────────────────────────────────────────────────────────────
  Finance:
    financial_year
    financial_scope              (← organization)
    fund_master                  (← financial_scope, organization)
    financial_transaction        (← financial_year, financial_scope, fund_master,
                                    person, sangha_sevi)
    financial_receipt            (← financial_transaction, person)
    financial_payment            (← financial_transaction, person)
    financial_transfer           (← financial_year, financial_scope, fund_master)

  Programme & Events (CANDIDATE — NOT EXECUTABLE until Module #21 freeze):
    programme_type
    event                        (← programme_type, organization)
    event_day                    (← event)
    event_session                (← event_day)
    event_registration           (← event, person, sangha_sevi)
    event_location               (← event, organization)
    event_history                (← event)

  Kumari:
    kumari_sangha                (← organization)
    kumari_membership            (← kumari_sangha, person, sangha_sevi)
    kumari_activity              (← kumari_sangha)
    kumari_activity_participant  (← kumari_activity, kumari_membership)
    kumari_membership_transition (← kumari_membership, sangha_sevi)

  Kishor:
    kishor_participant           (← person, organization, sangha_sevi)
    kishor_event                 (← organization)
    kishor_event_registration    (← kishor_participant, kishor_event,
                                    organization, sangha_sevi)
    kishor_guardian_history      (← kishor_participant, sangha_sevi)
    kishor_transition            (← kishor_participant, sangha_sevi)

  Sevak:
    sevak_participation          (← person, sangha_sevi)
    sevak_sakha_association      (← sevak_participation, organization)
    sevak_status_history         (← sevak_participation)
    sevak_reactivation_review    (← sevak_sakha_association)

  Publications:
    publication                  (← master_data, document_master)

PHASE 6 — Deferred FK (two-pass addition)
──────────────────────────────────────────────
  Administration:
    correspondence_finance_reference (← correspondence, financial_transaction)

  ALL TABLES:
    ALTER TABLE ADD CONSTRAINT for audit-actor FKs:
      created_by_sangha_sevi_pk  → sangha_sevi
      updated_by_sangha_sevi_pk  → sangha_sevi
      deleted_by_sangha_sevi_pk  → sangha_sevi
```

---

# 7. Dependency Graph (Visual)

```text
                    ┌─────────────┐
                    │  Foundation  │
                    │  (Phase 1)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌────────┐
        │  Person  │ │   Org    │ │Heritage│
        │(Phase 2) │ │(Phase 2) │ │(Ph 3)  │
        └────┬─────┘ └────┬─────┘ └────────┘
             │            │
             └─────┬──────┘
                   │
    ┌──────────────┼──────────────────────┐
    │              │                      │
    ▼              ▼                      ▼
┌────────┐  ┌───────────┐         ┌──────────────┐
│ Family │  │Membership │         │Authentication│
│(Ph 3)  │  │ (Ph 3-4)  │         │   (Ph 3)     │
└────────┘  └─────┬─────┘         └──────┬───────┘
                  │                       │
    ┌─────────────┼───────────────────────┤
    │             │                       │
    ▼             ▼                       ▼
┌──────────┐ ┌──────────┐         ┌──────────────┐
│Attendance│ │Governance│         │Administration│
│ (Ph 4)   │ │  (Ph 4)  │         │   (Ph 4)     │
└──────────┘ └──────────┘         └──────────────┘
                  │
    ┌─────────────┼───────────────┐
    │             │               │
    ▼             ▼               ▼
┌────────┐  ┌─────────┐   ┌──────────────┐
│Finance │  │  P & E  │   │Kumari/Kishor │
│(Ph 5)  │  │ (Ph 5)  │   │ Sevak (Ph 5) │
└────────┘  └─────────┘   └──────────────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │ Publications │
                          │   (Ph 5)     │
                          └──────────────┘

PHASE 6: Deferred FK constraints (audit-actor + correspondence_finance_reference)
```

---

# 8. Key Observations

1. **No circular FK dependencies exist** once audit-actor FKs are
   deferred to Phase 6.

2. **Foundation is truly root** — depends on nothing external.

3. **Person and Organization can be created in parallel** — both depend
   only on Foundation tables.

4. **`sangha_sevi` is the critical pivot table** — it unlocks most
   downstream modules (Attendance, Governance, Finance, Kumari, Kishor,
   Sevak, P&E).

5. **Administration has a split dependency** — RBAC tables need only
   Authentication + Organization; Correspondence tables need Person +
   Organization + Foundation; `correspondence_finance_reference` needs
   Finance (deferred to Phase 6).

6. **Assets & Property has no Membership FK** — it can be created as
   early as Phase 4, after Organization and Foundation are available.

7. **Finance standalone masters** (`financial_year`) have no
   dependencies — but transactional tables need Person + Membership +
   Organization.

8. **Programme & Events** tables remain CANDIDATE — included in the
   graph for completeness but not executable until Module #21 is
   formally frozen.

---

# 9. Self-Referencing FKs

| Table | Column | Notes |
|-------|--------|-------|
| `organization` | `parent_organization_pk` → `organization.organization_pk` | Create table first, add self-FK in same DDL or immediately after |
| `sangha_sevi` | `created_by_sangha_sevi_pk` → `sangha_sevi.sangha_sevi_pk` | Handled by audit-FK deferral (Phase 6) |

---

# 9.1 Machine-Verified Topological Depth (Frozen Tables)

The following creation depths were produced by Kahn's algorithm. All
86 frozen tables sort successfully — confirming zero cycles.

| Depth | Count | Tables |
|------:|------:|--------|
| 0 | 17 | asset, audit_master, body_type_master, country, document_master, field_change_log, financial_year, id_sequence_master, master_category, organization_status_master, organization_type_master, permission_master, position_master, property, role_master, system_event_log, system_setting |
| 1 | 8 | asset_document, founder, maintenance_record, master_data, property_document, property_statutory_record, role_permission, state |
| 2 | 6 | district, founder_gallery, founder_timeline, person, publication, spiritual_literature |
| 3 | 3 | city_village, organization, user_account |
| 4 | 12 | admin_scope, body_master, correspondence, custodianship, family_group, financial_scope, kishor_event, kumari_sangha, password_history, sangha_sevi, user_role, weekly_sangha_puja |
| 5 | 23 | acting_position_assignment, anumati_patra, attendance_exception, attendance_review, body_member_assignment, correspondence_document, election, family_head_history, family_relationship, family_transition_history, fund_master, kishor_participant, kumari_activity, kumari_membership, membership_journey_event, membership_renewal_history, membership_renewal_request, membership_status_history, membership_transfer_history, parichaya_patra, probationary_member_review, sevak_participation, weekly_sangha_puja_attendance |
| 6 | 14 | anumati_patra_history, election_nomination, election_result, election_vote, financial_transaction, financial_transfer, kishor_event_registration, kishor_guardian_history, kishor_transition, kumari_activity_participant, kumari_membership_transition, parichaya_patra_history, sevak_sakha_association, sevak_status_history |
| 7 | 3 | financial_payment, financial_receipt, sevak_reactivation_review |

**Total: 86 tables across 8 depths (0–7).**

---

# 10. Status

```text
DOCUMENT STATUS:
FROZEN

VERSION:
1.0.0

DATE:
2026-08-28

FROZEN TABLES:
86

CANDIDATE TABLES (P&E):
7 (not executable until Module #21 formal freeze)

DEFERRED FK:
1 (correspondence_finance_reference)

TOTAL MAPPED:
94

NOT MAPPED (deferred):
UPBS (pending P&E propagation)

CIRCULAR DEPENDENCIES:
NONE — machine-verified via topological sort (Kahn's algorithm)

AUDIT FK STRATEGY:
TWO-PASS DDL (Phase 6 deferred constraints)
Audit-actor FK convention FROZEN (not weakened)
Referential integrity preserved (deferred, not abandoned)

DDL CREATION DEPTHS:
8 (Depth 0 through Depth 7)

NEXT:
DDL CREATION ORDER SCRIPT → FOUNDATION VERTICAL SLICE
```
