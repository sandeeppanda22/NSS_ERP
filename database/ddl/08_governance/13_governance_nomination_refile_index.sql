-- =====================================================
-- 13_governance_nomination_refile_index.sql
-- Re-files after WITHDRAWN/REJECTED nominations (2026-10-28)
-- =====================================================
-- uq_election_nomination_active_candidate (07_election_nomination.sql) is now
-- unique over LIVE nominations only (is_active AND status NOMINATED/ACCEPTED),
-- so a WITHDRAWN or REJECTED nomination no longer blocks a candidate from
-- being nominated again (GOV-BR-035).
--
-- 07_election_nomination.sql is existence-gated by the build scripts and is
-- skipped on any database that already has the table, so this file carries
-- the change to existing databases. Not a table: applied with run_sql and
-- idempotent (a no-op once the index definition already matches).
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'nss'
          AND indexname  = 'uq_election_nomination_active_candidate'
          AND indexdef LIKE '%nomination_status%'
    ) THEN
        DROP INDEX IF EXISTS nss.uq_election_nomination_active_candidate;
        CREATE UNIQUE INDEX uq_election_nomination_active_candidate
            ON nss.election_nomination (election_pk, position_master_pk, candidate_person_pk)
            WHERE is_active = TRUE AND nomination_status IN ('NOMINATED', 'ACCEPTED');
    END IF;
END $$;
