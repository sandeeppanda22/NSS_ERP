# database/seed/02_organization/

Organization Module seed data — organizational type masters, status masters,
and the three unique organizations required before downstream modules.

Authority: SOL-ORG-005 §48, SOL-ARCH-010 §8

## Seed Execution Order

Execute AFTER:
- All Foundation DDL + seed (`database/ddl/01_foundation/`, `database/seed/01_foundation/`)
- All Organization DDL (`database/ddl/02_organization/`)

Files must be run in numeric order.

| # | File | Seeds Into | Depends On |
|--:|------|-----------|-----------|
| 01 | `01_organization_type_master.sql` | `organization_type_master` | DDL complete |
| 02 | `02_organization_status_master.sql` | `organization_status_master` | DDL complete |
| 03 | `03_organization.sql` | `organization` | `01_*`, `02_*`, Foundation `country` seed |

## Execution Command

```bash
# As NSS_ADMIN against the nss_erp database:
for f in database/seed/02_organization/0*.sql; do
    psql -U nss_admin -d nss_erp -f "$f"
done
```

---

## Seed File Descriptions

### 01_organization_type_master.sql

Seeds 8 frozen organization types (decided 2026-08-28):

| # | `organization_type_code` | Name | Cardinality |
|--:|--------------------------|------|-------------|
| 1 | `KENDRA` | Kendra Sangha | Unique |
| 2 | `NILACHALA_KUTIRA` | Nilachala Kutira | Unique |
| 3 | `SMRUTI_MANDIRA` | Smruti Mandira | Unique |
| 4 | `ANCHALIKA_SANGHA` | Anchalika Sangha | Multiple |
| 5 | `ZILLA_SANGHA` | Zilla Sangha | Multiple |
| 6 | `SAKHA_SANGHA` | Sakha Sangha | Multiple |
| 7 | `SAKHA_ASANA` | Sakha Asana | Multiple |
| 8 | `PATHA_CHAKRA` | Patha Chakra | Multiple |

---

### 02_organization_status_master.sql

Seeds 6 organizational lifecycle statuses per GOV-002:

| # | `organization_status_code` | Name | Purpose |
|--:|----------------------------|------|---------|
| 1 | `PROPOSED` | Proposed | Organization proposed, not yet approved |
| 2 | `APPROVED` | Approved | Approved by governance, pending activation |
| 3 | `ACTIVE` | Active | Currently operational |
| 4 | `INACTIVE` | Inactive | Temporarily non-operational |
| 5 | `SUSPENDED` | Suspended | Activities suspended by governance decision |
| 6 | `ARCHIVED` | Archived | Permanently closed, retained for history |

---

### 03_organization.sql

Seeds the 3 unique organizations of NSS. No `organization_id` — unique
organizations are identified by `organization_code` alone. Sequence-generated
IDs are for multi-instance org types (Sakha, Anchalika, etc.).

| # | `organization_code` | Name | Type | Parent |
|--:|---------------------|------|------|--------|
| 1 | `KEN` | Nilachala Saraswata Sangha | KENDRA | NULL (apex governing body) |
| 2 | `NKT` | Nilachala Kutira | NILACHALA_KUTIRA | NULL (Eternal Abode, Puri) |
| 3 | `SMR` | Sri Shri Nigamananda Smruti Mandir | SMRUTI_MANDIRA | NULL (memorial temple, Puri) |

All three are seeded as ACTIVE with country = IN (India).
Kendra's representative office address is seeded inline: Satsikshya Mandir,
A/4, Unit-9, Bhubaneswar - 751022, Odisha, India.

---

## Notes

- Organization types are frozen per SOL-ORG-005 §48 (decided 2026-08-28).
- Organization statuses are frozen per GOV-002 (decided 2026-09-01).
- **Unique org hierarchy (ERP-FROZEN, decided 2026-09-01):**
  KEN, NKT, SMR are peer root organizations (`parent = NULL`).
  KEN remains the apex governing body. Physical location/operational
  association ≠ organizational parent-child relationship.
  Constitutional/functional roles are distinguished by `organization_type_pk`.
- Unique organizations have no `organization_id` — identified by
  `organization_code` alone. `organization_id` (sequence-generated via
  `id_sequence_master`) is for multi-instance types only.
- Additional organizations (Anchalika, Zilla, Sakha, etc.) are created
  at runtime through governance workflows, not seeded.
- Foundation seed data (especially `country`) must be loaded before
  Organization seed.
- All addresses are editable at runtime — seed values are initial state only.
