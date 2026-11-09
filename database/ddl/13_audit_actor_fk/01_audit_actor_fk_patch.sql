-- =====================================================
-- NSS ERP
-- Module: Audit (cross-cutting, "Pass 2" audit-actor foreign keys)
-- File: 01_audit_actor_fk_patch.sql (idempotent - run_sql / Invoke-Sql on EVERY build)
-- Not a table. Build Phase 13c: after Phase 13 (admin bootstrap) and 13b, before
-- Phase 14 (audit trigger), i.e. after EVERY table exists.
-- Version: 1.0 (2026-11-04, owner decision: "FKs on every audit-actor column")
--
-- What it does
--   For every base-table column in schema nss whose name ends in
--   `_by_sangha_sevi_pk` (created_/updated_/deleted_/approved_/reviewed_/
--   submitted_/requested_/changed_/uploaded_/... _by_sangha_sevi_pk) it makes
--   sure there is a FOREIGN KEY to nss.sangha_sevi (sangha_sevi_pk):
--     * a column that ALREADY has any FK to nss.sangha_sevi (e.g. the four
--       Foundation geography tables from 05_membership/16_foundation_audit_fk.sql
--       or any column declared with an inline REFERENCES) is left alone;
--     * every other column gets  fk_<table>_<column>  (truncated + md5 suffix
--       when longer than 63 characters), added NOT VALID: it is enforced for
--       every NEW or UPDATED row immediately, but existing rows are not
--       scanned, so a dangling historical value (dev DB, rows written before
--       the FK existed) can never break a rebuild;
--     * afterwards every NOT VALID actor FK (new ones and ones left NOT VALID
--       by an earlier run) gets a VALIDATE attempt; a failure is a WARNING and
--       the constraint simply stays NOT VALID until the dangling rows are fixed
--       (find them with the diagnostic SELECT in database/scripts/README.md).
--   A column that cannot take the FK (wrong data type) is reported as a
--   WARNING and skipped; the build never fails on this file.
--
-- Why one patch and not ~70 DDL edits
--   Builds are existence-gated (an existing table's DDL is skipped) and many
--   tables are created before nss.sangha_sevi, so the FK cannot live in each
--   CREATE TABLE. This file is the single place; re-running it picks up any
--   table or column added later automatically (the loop is catalog-driven).
--   Existing: 05_membership/16_foundation_audit_fk.sql stays as it is.
--
-- Notes
--   * sangha_sevi's own created_by/updated_by/deleted_by self-reference is
--     covered by the same loop.
--   * Referential checks run with the owner's privileges, so nss_db_writer
--     (SELECT/INSERT/UPDATE only, no REFERENCES) can still write.
--   * No ON DELETE action: sangha_sevi rows are never hard-deleted.
--   * system_event_log.actor_sangha_sevi_pk is NOT covered (the name does not
--     match; the event log must never reject an event). field_change_log.
--     changed_by_sangha_sevi_pk IS covered (it matches the pattern); the audit
--     trigger only ever writes the real actor of the session or NULL.
--   * Actors that are not Sangha Sevis (system jobs, a NULL actor) must write
--     NULL; a bogus uuid is now rejected by the database.
-- =====================================================

DO $actor_fk$
DECLARE
    r        RECORD;
    v_name   TEXT;
    v_added  INT := 0;
    v_valid  INT := 0;
    v_left   INT := 0;
BEGIN
    -- 1. Add the missing FKs (NOT VALID).
    FOR r IN
        SELECT c.relname AS tbl, a.attname AS col, a.attnum
          FROM pg_attribute a
          JOIN pg_class c      ON c.oid = a.attrelid
          JOIN pg_namespace n  ON n.oid = c.relnamespace
         WHERE n.nspname = 'nss'
           AND c.relkind IN ('r', 'p')
           AND a.attnum > 0
           AND NOT a.attisdropped
           AND a.attname LIKE '%\_by\_sangha\_sevi\_pk'
           AND NOT EXISTS (
                 SELECT 1 FROM pg_constraint k
                  WHERE k.conrelid  = c.oid
                    AND k.contype   = 'f'
                    AND k.confrelid = 'nss.sangha_sevi'::regclass
                    AND k.conkey    = ARRAY[a.attnum]::smallint[])
         ORDER BY c.relname, a.attname
    LOOP
        v_name := format('fk_%s_%s', r.tbl, r.col);
        IF length(v_name) > 63 THEN
            v_name := left(v_name, 54) || '_' || left(md5(v_name), 8);
        END IF;
        BEGIN
            EXECUTE format(
                'ALTER TABLE nss.%I ADD CONSTRAINT %I FOREIGN KEY (%I) '
                'REFERENCES nss.sangha_sevi (sangha_sevi_pk) NOT VALID',
                r.tbl, v_name, r.col);
            v_added := v_added + 1;
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING 'audit actor FK skipped for nss.%.%: % (%)',
                r.tbl, r.col, SQLERRM, SQLSTATE;
        END;
    END LOOP;

    -- 2. Try to validate every NOT VALID actor FK.
    FOR r IN
        SELECT c.relname AS tbl, k.conname
          FROM pg_constraint k
          JOIN pg_class c      ON c.oid = k.conrelid
          JOIN pg_namespace n  ON n.oid = c.relnamespace
          JOIN pg_attribute a  ON a.attrelid = c.oid AND a.attnum = k.conkey[1]
         WHERE n.nspname = 'nss'
           AND k.contype = 'f'
           AND k.confrelid = 'nss.sangha_sevi'::regclass
           AND array_length(k.conkey, 1) = 1
           AND a.attname LIKE '%\_by\_sangha\_sevi\_pk'
           AND NOT k.convalidated
         ORDER BY c.relname, k.conname
    LOOP
        BEGIN
            EXECUTE format('ALTER TABLE nss.%I VALIDATE CONSTRAINT %I', r.tbl, r.conname);
            v_valid := v_valid + 1;
        EXCEPTION WHEN OTHERS THEN
            v_left := v_left + 1;
            RAISE WARNING 'audit actor FK % on nss.% left NOT VALID (dangling values): % - see the diagnostic SELECT in database/scripts/README.md',
                r.conname, r.tbl, SQLERRM;
        END;
    END LOOP;

    RAISE NOTICE 'audit actor FKs: % added, % validated, % left NOT VALID', v_added, v_valid, v_left;
END
$actor_fk$;
