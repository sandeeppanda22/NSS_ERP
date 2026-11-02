-- =====================================================
-- NSS ERP
-- Module: Organization (Sakha re-parenting approval workflow)
-- File: 09_organization_reparent_step_source_role_patch.sql
-- Table: nss.organization_reparent_step (existing-table patch)
-- Version: 1.0 (2026-10-31)
-- Authority: Owner decision 2026-10-31 (GDR-007 amendment): the chain is
--   Sakha President -> LEAVING Anchalika/Zilla President -> DESTINATION
--   Anchalika/Zilla President -> Kendra President.
--
-- 07_organization_reparent_step.sql is existence-gated in the build scripts,
-- so a DB that already has the table keeps the old CHECKs
-- (step_role in 3 values, step_order 1..3). This idempotent patch widens
-- both: step_role gains SOURCE_PARENT_PRESIDENT, step_order becomes 1..4.
-- Each constraint is replaced only when its live definition lacks the new
-- value, so re-runs (and fresh builds, whose CREATE TABLE already has them)
-- are no-ops. Existing rows satisfy the wider CHECKs, so ADD never fails
-- on data. Runs via run_sql after the table DDL.
-- =====================================================

DO $$
BEGIN
    IF to_regclass('nss.organization_reparent_step') IS NULL THEN
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'nss.organization_reparent_step'::regclass
          AND conname = 'chk_org_reparent_step_role'
          AND pg_get_constraintdef(oid) LIKE '%SOURCE_PARENT_PRESIDENT%'
    ) THEN
        ALTER TABLE nss.organization_reparent_step
            DROP CONSTRAINT IF EXISTS chk_org_reparent_step_role;
        ALTER TABLE nss.organization_reparent_step
            ADD CONSTRAINT chk_org_reparent_step_role
            CHECK (step_role IN ('SAKHA_PRESIDENT', 'SOURCE_PARENT_PRESIDENT',
                                 'DEST_PARENT_PRESIDENT', 'KENDRA_PRESIDENT'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'nss.organization_reparent_step'::regclass
          AND conname = 'chk_org_reparent_step_order'
          AND pg_get_constraintdef(oid) LIKE '%4%'
    ) THEN
        ALTER TABLE nss.organization_reparent_step
            DROP CONSTRAINT IF EXISTS chk_org_reparent_step_order;
        ALTER TABLE nss.organization_reparent_step
            ADD CONSTRAINT chk_org_reparent_step_order
            CHECK (step_order BETWEEN 1 AND 4);
    END IF;
END $$;
