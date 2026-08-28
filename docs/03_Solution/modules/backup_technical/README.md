# NSS ERP Backup & Technical Module

Status: DRAFT — SOURCE ALIGNED, v1.0.0. Full Solution design complete (4 files); there is no
`backend/backup_technical/` (or similarly-named) Django app. Infrastructure module, not a
member/organization-facing business module.

---

## Documents

01_backup_technical_module_overview.md (`SOL-BACKUP-001`) — Version 1.0.0
Purpose: Technical foundation for protecting NSS ERP data and restoring it after a failure —
backup management, backup records, restore history, recovery traceability.

02_backup_technical_erd.md — Version 1.0.0
Purpose: Entity relationship design for the two frozen tables.

03_backup_technical_business_rules.md — Version 1.0.0, BACKUP-BR-001–BACKUP-BR-053
Purpose: Business rules — explicitly marks storage/schedule/retention/disaster-recovery/
failover, backup-verification mechanism, and controlled status values as PENDING/not frozen.

04_backup_technical_table_design.md — Version 1.0.0
Purpose: Physical table design — `backup_master`, `restore_history`. No assumed FK between the
two tables; the backup-to-restore relationship is documented as logical/pending, not a frozen
FK.

---

## Key facts

- Two frozen foundation tables only: `backup_master`, `restore_history`.
- History Never Deleted applies to backup/restore records themselves.
- Storage location, schedule/retention policy, DR/failover strategy are all explicitly open —
  do not assume any specific backup tooling or cadence from this doc set.

---

## Current Status

Design Complete · ERD Complete · Business Rules Drafted (SOURCE ALIGNED) · Table Design
Drafted (SOURCE ALIGNED) · SQL Implementation Not Started · no corresponding Django app exists
yet
