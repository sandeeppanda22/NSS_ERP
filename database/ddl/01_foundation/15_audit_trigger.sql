-- =====================================================
-- NSS ERP
-- Module: Foundation / Audit
-- File: 15_audit_trigger.sql
-- Purpose: Database-level audit trigger that fires on
--          EVERY INSERT, UPDATE, DELETE across all nss
--          business tables. Writes row-level events to
--          system_event_log and field-level detail (one
--          row per field, for all three operations) to
--          field_change_log — all automatically, so no
--          application code can bypass it.
-- Version: 1.3
-- Authority: SOL-AUDIT-004
-- Owner: NSS_ERP_ADMIN
-- Depends: 14_system_event_log.sql, 07_field_change_log.sql
--
-- PK resolution: reads the table's real single-column primary key from
-- pg_constraint/pg_attribute rather than assuming the <table>_pk naming
-- convention — nss.weekly_sangha_puja_attendance (attendance_pk),
-- nss.attendance_exception (exception_pk) and nss.attendance_review
-- (review_pk) deliberately deviate from it. Falls back to the
-- convention-based name only if no single-column PK is found.
--
-- Actor resolution: the trigger reads session variables
--   nss.actor_sangha_sevi_pk
--   nss.actor_user_account_pk
-- set by the application on the WRITE connection (see
-- api/dependencies/auth.py::get_write_connection) — the
-- same connection the trigger runs on. Both are recorded,
-- because an authenticated account does not always have a
-- Sangha Sevi record. If neither is set, actor columns are
-- NULL (public registration / system / seed operations).
-- =====================================================

-- ── Trigger function ────────────────────────────────

CREATE OR REPLACE FUNCTION nss.fn_audit_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_action        VARCHAR(50);
    v_record_pk     UUID;
    v_old_data      JSONB := NULL;
    v_new_data      JSONB := NULL;
    v_changed       JSONB := NULL;
    v_actor_ss      UUID  := NULL;
    v_actor_ua      UUID  := NULL;
    v_pk_col        TEXT;
    -- Bookkeeping columns kept out of field_change_log:
    -- they change on every write and carry no business meaning
    -- ("when" is already recorded by changed_at).
    v_skip_cols     TEXT[] := ARRAY['created_at', 'updated_at'];
    -- Tables kept out of field_change_log entirely. The ID and
    -- credential counters mutate on EVERY id mint, so their
    -- field-level diffs are mechanical noise
    -- ("current_value: 41 → 42") with no audit value — the real
    -- event (the person/Patra that consumed the number) is logged
    -- against its own table. They still get row-level rows in
    -- system_event_log, so trigger coverage stays complete.
    v_skip_field_log_tables TEXT[] := ARRAY[
        'id_sequence_master',
        'credential_sequence_counter'
    ];
    v_log_fields    BOOLEAN;
BEGIN
    -- ── Determine action ────────────────────────────
    IF TG_OP = 'INSERT' THEN
        v_action := 'CREATE';
    ELSIF TG_OP = 'UPDATE' THEN
        v_action := 'UPDATE';
    ELSIF TG_OP = 'DELETE' THEN
        v_action := 'DELETE';
    END IF;

    -- ── Resolve the PK column ───────────────────────
    -- Most tables follow the <table>_pk naming convention, but a few
    -- (nss.weekly_sangha_puja_attendance.attendance_pk,
    -- nss.attendance_exception.exception_pk,
    -- nss.attendance_review.review_pk — deliberate, see their DDL notes)
    -- do not. Read the real single-column primary key from the catalog
    -- instead of assuming the convention, so the trigger works for every
    -- table regardless of its PK column name. Falls back to the
    -- convention if, for any reason, no single-column PK is found.
    SELECT a.attname
      INTO v_pk_col
      FROM pg_constraint c
      JOIN pg_attribute a
        ON a.attrelid = c.conrelid
       AND a.attnum = c.conkey[1]
     WHERE c.contype = 'p'
       AND c.conrelid = TG_RELID
       AND array_length(c.conkey, 1) = 1;

    IF v_pk_col IS NULL THEN
        v_pk_col := TG_TABLE_NAME || '_pk';
    END IF;

    -- ── Extract record PK ───────────────────────────
    IF TG_OP = 'DELETE' THEN
        EXECUTE format('SELECT ($1).%I::UUID', v_pk_col)
            INTO v_record_pk USING OLD;
    ELSE
        EXECUTE format('SELECT ($1).%I::UUID', v_pk_col)
            INTO v_record_pk USING NEW;
    END IF;

    -- ── Capture row data as JSONB ───────────────────
    IF TG_OP = 'DELETE' THEN
        v_old_data := to_jsonb(OLD);
    ELSIF TG_OP = 'INSERT' THEN
        v_new_data := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        v_old_data := to_jsonb(OLD);
        v_new_data := to_jsonb(NEW);
        -- Build a diff: only changed columns
        SELECT jsonb_object_agg(key, jsonb_build_object(
                   'old', v_old_data -> key,
                   'new', value
               ))
          INTO v_changed
          FROM jsonb_each(v_new_data)
         WHERE v_old_data -> key IS DISTINCT FROM value;
    END IF;

    -- ── Read actor from session variables ───────────
    BEGIN
        v_actor_ss := current_setting('nss.actor_sangha_sevi_pk', TRUE)::UUID;
    EXCEPTION WHEN OTHERS THEN
        v_actor_ss := NULL;
    END;

    BEGIN
        v_actor_ua := current_setting('nss.actor_user_account_pk', TRUE)::UUID;
    EXCEPTION WHEN OTHERS THEN
        v_actor_ua := NULL;
    END;

    -- ── Field-level change log (ALL operations) ──────
    -- One row per field, for every INSERT / UPDATE / DELETE,
    -- so nss.field_change_log (surfaced by
    -- GET /api/v1/audit/change-log) answers what changed,
    -- who changed it and when, for every table.
    --   CREATE → one row per populated field (old = NULL)
    --   UPDATE → one row per CHANGED field (old + new)
    --   DELETE → one row per populated field (new = NULL)
    -- created_at/updated_at are bookkeeping noise and are
    -- skipped; changed_at already records "when". The counter
    -- tables are skipped wholesale (see v_skip_field_log_tables).
    v_log_fields := NOT (TG_TABLE_NAME = ANY(v_skip_field_log_tables));

    IF v_log_fields AND TG_OP = 'UPDATE' THEN
        INSERT INTO nss.field_change_log (
            action, table_name, record_pk, field_name,
            old_value, new_value,
            changed_by_sangha_sevi_pk, changed_by_user_account_pk
        )
        SELECT 'UPDATE', TG_TABLE_NAME, v_record_pk, ec.key,
               v_old_data ->> ec.key,
               v_new_data ->> ec.key,
               v_actor_ss, v_actor_ua
          FROM jsonb_each(v_new_data) AS ec(key, value)
         WHERE v_old_data -> ec.key IS DISTINCT FROM ec.value
           AND NOT (ec.key = ANY(v_skip_cols));

    ELSIF v_log_fields AND TG_OP = 'INSERT' THEN
        INSERT INTO nss.field_change_log (
            action, table_name, record_pk, field_name,
            old_value, new_value,
            changed_by_sangha_sevi_pk, changed_by_user_account_pk
        )
        SELECT 'CREATE', TG_TABLE_NAME, v_record_pk, ec.key,
               NULL,
               v_new_data ->> ec.key,
               v_actor_ss, v_actor_ua
          FROM jsonb_each(v_new_data) AS ec(key, value)
         WHERE ec.value IS DISTINCT FROM 'null'::jsonb
           AND NOT (ec.key = ANY(v_skip_cols));

    ELSIF v_log_fields AND TG_OP = 'DELETE' THEN
        INSERT INTO nss.field_change_log (
            action, table_name, record_pk, field_name,
            old_value, new_value,
            changed_by_sangha_sevi_pk, changed_by_user_account_pk
        )
        SELECT 'DELETE', TG_TABLE_NAME, v_record_pk, ec.key,
               v_old_data ->> ec.key,
               NULL,
               v_actor_ss, v_actor_ua
          FROM jsonb_each(v_old_data) AS ec(key, value)
         WHERE ec.value IS DISTINCT FROM 'null'::jsonb
           AND NOT (ec.key = ANY(v_skip_cols));
    END IF;

    -- ── Insert audit row ────────────────────────────
    INSERT INTO nss.system_event_log (
        action,
        table_name,
        record_pk,
        actor_sangha_sevi_pk,
        actor_user_account_pk,
        module,
        summary,
        detail
    ) VALUES (
        v_action,
        TG_TABLE_NAME,
        v_record_pk,
        v_actor_ss,
        v_actor_ua,
        'trigger',
        v_action || ' on ' || TG_TABLE_NAME,
        CASE
            WHEN TG_OP = 'INSERT' THEN jsonb_build_object('new', v_new_data)
            WHEN TG_OP = 'DELETE' THEN jsonb_build_object('old', v_old_data)
            WHEN TG_OP = 'UPDATE' THEN jsonb_build_object('changed', v_changed)
        END
    );

    -- Return the appropriate row
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$;


-- ── Attach trigger to ALL business tables ───────────
-- Excludes: system_event_log (self), field_change_log (audit infra)

DO $$
DECLARE
    t TEXT;
    trigger_name TEXT;
    excluded_tables TEXT[] := ARRAY[
        'system_event_log',
        'field_change_log'
    ];
BEGIN
    FOR t IN
        SELECT tablename
          FROM pg_tables
         WHERE schemaname = 'nss'
           AND tablename != ALL(excluded_tables)
         ORDER BY tablename
    LOOP
        trigger_name := 'trg_audit_' || t;

        -- Drop if exists (idempotent re-run)
        EXECUTE format(
            'DROP TRIGGER IF EXISTS %I ON nss.%I',
            trigger_name, t
        );

        -- Create AFTER trigger for INSERT, UPDATE, DELETE
        EXECUTE format(
            'CREATE TRIGGER %I '
            'AFTER INSERT OR UPDATE OR DELETE ON nss.%I '
            'FOR EACH ROW EXECUTE FUNCTION nss.fn_audit_trigger()',
            trigger_name, t
        );

        RAISE NOTICE 'Attached audit trigger to nss.%', t;
    END LOOP;
END;
$$;
