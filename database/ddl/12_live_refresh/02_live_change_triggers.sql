-- =====================================================
-- NSS ERP
-- Module: Live refresh (cross-cutting; owner decision 2026-11-03)
-- File: 02_live_change_triggers.sql (idempotent - run_sql / Invoke-Sql on EVERY build)
-- Not a table. Run after 01_live_change_marker.sql and after every table named
-- below exists (build Phase 11h, after Assets & Property).
-- Version: 1.1 (2026-11-03: batch 2 - Users, Organizations, directories,
--   reference data, geography, settings, member dashboard; per-table
--   "ignored UPDATE columns")
--
-- nss.fn_live_change_marker()   AFTER INSERT OR UPDATE OR DELETE ... FOR EACH
--   STATEMENT: upserts the marker row of TG_TABLE_NAME with a fresh
--   nextval('nss.live_change_seq'). One short statement; a multi-row write is
--   still ONE bump. The new value is assigned in the DO UPDATE branch, i.e.
--   AFTER the row lock is obtained, so for one table change_seq order equals
--   commit order (concurrent writers to a table queue on its marker row until
--   the first one commits - API writes are millisecond transactions).
--   Visible at COMMIT, discarded on ROLLBACK.
--   SECURITY DEFINER (owned by the build role nss_db_owner): the API's
--   nss_db_writer holds INSERT/UPDATE on tables but no sequence USAGE, and
--   must not be able to write the marker table directly. search_path is
--   pinned. The function is only reachable as a trigger.
--
-- THE LIST BELOW is the single SQL source of the watched tables. The Python
-- whitelist api/routers/live.py::LIVE_FEED_TABLES must equal it
-- (tests/api/test_live_changes.py parses this file). Add a table: add it
-- here AND there, re-run the build. A table removed from the list loses its
-- trigger on the next run. Tables that do not exist yet are skipped.
-- election_vote / election_vote_participation are withheld on purpose (ballot
-- timing stays private).
--
-- ENTRY FORMAT in the list: 'table_name' (INSERT/UPDATE/DELETE of any column
-- bumps the marker) or 'table_name!col1,col2,...' = "the columns after the !
-- are ROUTINE CHURN": the trigger is created as
-- AFTER INSERT OR DELETE OR UPDATE OF <every column EXCEPT those>, so an
-- UPDATE whose SET list names only the ignored columns does not bump the
-- marker. (A column-list trigger fires when a column is NAMED in the SET
-- list even if its value is unchanged - hence the list is of columns the
-- routine statement writes, not of "unchanged" ones.) The column list is
-- computed from pg_attribute at build time, so a column added later counts as
-- meaningful by default (re-run the file to pick it up). Today only
-- user_account uses it: every login rewrites failed_login_attempts /
-- locked_until / last_login_at (+ updated_at) and every failed attempt
-- rewrites failed_login_attempts / locked_until / (updated_at), which would
-- otherwise refresh every admin's Users page on each login. Every ADMIN write
-- (status, password reset, soft delete, reactivation) also names a
-- non-ignored column, so they still bump. The Python whitelist names tables
-- only; tests/api/test_live_changes.py parses both forms.
--
-- Existing databases: re-run THIS file (build Phase 11h runs it on every
-- build) to get the new triggers and marker rows; nothing else is needed.
-- =====================================================

CREATE OR REPLACE FUNCTION nss.fn_live_change_marker()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = nss, pg_temp
AS $$
BEGIN
    INSERT INTO nss.live_change_marker AS m (table_name, change_seq)
    VALUES (TG_TABLE_NAME, nextval('nss.live_change_seq'))
    ON CONFLICT (table_name) DO UPDATE
        SET change_seq = nextval('nss.live_change_seq'),
            changed_at = clock_timestamp();
    RETURN NULL;
END;
$$;

DO $$
DECLARE
    watched TEXT[] := ARRAY[
        -- Registration / claim approvals + change requests
        'registration_claim', 'membership_change_request',
        -- Correspondence (list, detail, approval chain)
        'correspondence', 'correspondence_document', 'correspondence_finance_reference',
        'correspondence_approval_step',
        -- Governance (bodies, assignments, acting, elections / nominations / results)
        'body_master', 'body_member_assignment', 'acting_position_assignment',
        'election', 'election_nomination', 'election_result',
        -- Organization dashboards (stats cards)
        'organization', 'membership_sakha_affiliation', 'parichaya_patra',
        'family_group', 'darshak_attendance_registration',
        -- Assets & Property
        'property', 'asset', 'custodianship', 'maintenance_record',
        'property_statutory_record', 'property_document', 'asset_document',
        -- Finance (Tier 12)
        'financial_year', 'financial_scope', 'fund_master', 'financial_transaction',
        'financial_receipt', 'financial_payment', 'financial_transfer',
        'financial_account', 'finance_head', 'upi_payment_request', 'finance_disbursement_authority',
        -- Member dashboard "Pending Items"
        'organization_reparent_request', 'organization_reparent_step',
        -- Batch 2 - Users tab + user detail (roles, admin scope). user_account: login churn ignored.
        'user_account!failed_login_attempts,locked_until,last_failed_login_at,last_login_at,updated_at',
        'user_role', 'admin_scope', 'role_master',
        -- Person / Member directories, credentials, member dashboard personal + membership tabs
        'person', 'person_address', 'sangha_sevi', 'anumati_patra', 'membership_journey_event',
        'membership_renewal_request',
        -- Member dashboard family tab
        'family_relationship', 'family_head_history', 'family_admin', 'family_link',
        'family_transition_history',
        -- Governance catalogue shown on the member dashboard
        'body_type_master', 'position_master',
        -- Reference data, geography (+ location approvals), system settings, festival calendar
        'master_category', 'master_data', 'document_master',
        'country', 'state', 'district', 'city_village', 'postal_code', 'post_office',
        'system_setting', 'festival_master', 'festival_calendar_date'
    ];
    t TEXT;           -- table name (entry before any '!')
    ign TEXT[];       -- ignored UPDATE columns of the entry
    cols TEXT;        -- computed column list for UPDATE OF
    e TEXT;
    names TEXT[] := ARRAY[]::TEXT[];
    r RECORD;
BEGIN
    -- Table names only (strip any '!ignored,columns' suffix).
    FOREACH e IN ARRAY watched LOOP
        names := names || split_part(e, '!', 1);
    END LOOP;

    -- Drop the trigger from any table that is no longer in the list.
    FOR r IN
        SELECT c.relname AS tbl
          FROM pg_trigger g
          JOIN pg_class c ON c.oid = g.tgrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'nss'
           AND g.tgname = 'trg_live_change_marker'
           AND NOT g.tgisinternal
           AND c.relname <> ALL (names)
    LOOP
        EXECUTE format('DROP TRIGGER trg_live_change_marker ON nss.%I', r.tbl);
    END LOOP;

    FOREACH e IN ARRAY watched LOOP
        t := split_part(e, '!', 1);
        ign := CASE WHEN position('!' IN e) > 0
                    THEN string_to_array(substr(e, position('!' IN e) + 1), ',')
                    ELSE NULL END;
        IF to_regclass('nss.' || quote_ident(t)) IS NULL THEN
            RAISE NOTICE 'live_change_marker: nss.% does not exist yet - skipped', t;
            CONTINUE;
        END IF;
        EXECUTE format('DROP TRIGGER IF EXISTS trg_live_change_marker ON nss.%I', t);
        IF ign IS NULL THEN
            EXECUTE format(
                'CREATE TRIGGER trg_live_change_marker '
                'AFTER INSERT OR UPDATE OR DELETE ON nss.%I '
                'FOR EACH STATEMENT EXECUTE FUNCTION nss.fn_live_change_marker()', t);
        ELSE
            SELECT string_agg(quote_ident(a.attname), ', ' ORDER BY a.attnum) INTO cols
              FROM pg_attribute a
             WHERE a.attrelid = to_regclass('nss.' || quote_ident(t))
               AND a.attnum > 0 AND NOT a.attisdropped
               AND a.attname <> ALL (ign);
            EXECUTE format(
                'CREATE TRIGGER trg_live_change_marker '
                'AFTER INSERT OR DELETE OR UPDATE OF %s ON nss.%I '
                'FOR EACH STATEMENT EXECUTE FUNCTION nss.fn_live_change_marker()', cols, t);
        END IF;
        -- Seed so a client's very first poll sees every watched table.
        INSERT INTO nss.live_change_marker (table_name, change_seq)
        VALUES (t, nextval('nss.live_change_seq'))
        ON CONFLICT (table_name) DO NOTHING;
    END LOOP;
END;
$$;

-- Read access for the API's read pool (the build's default-privilege grants
-- already cover new tables; this makes the table safe on any history).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nss_db_backend') THEN
        GRANT SELECT ON nss.live_change_marker TO nss_db_backend;
    END IF;
END;
$$;
