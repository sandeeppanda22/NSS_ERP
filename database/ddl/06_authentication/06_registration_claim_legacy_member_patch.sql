-- =====================================================
-- 06_registration_claim_legacy_member_patch.sql
-- Legacy-vs-new Local Sakha Number flags on nss.registration_claim
-- (GDR-009, owner 2026-11-01)
-- =====================================================
-- 03_registration_claim.sql now declares is_legacy_member and
-- darshak_is_legacy_member plus the two agreement CHECKs, but it is
-- existence-gated by the build scripts and skipped on any database that
-- already has the table, so this idempotent patch (run_sql) carries them to
-- existing databases.
--
-- Defaults for EXISTING claims (the only data change, done once, when the
-- column is first added): a claim that already carries a number is LEGACY
-- (that number was typed from a card), otherwise NEW. Blank/whitespace
-- numbers are normalised to NULL first so the flag and the number agree
-- before the CHECKs are added. Re-running the patch is a no-op.
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'nss' AND table_name = 'registration_claim'
          AND column_name = 'is_legacy_member'
    ) THEN
        ALTER TABLE nss.registration_claim
            ADD COLUMN is_legacy_member BOOLEAN NOT NULL DEFAULT FALSE;

        UPDATE nss.registration_claim
           SET claimed_local_sakha_number = NULLIF(BTRIM(claimed_local_sakha_number), '')
         WHERE claimed_local_sakha_number IS NOT NULL
           AND claimed_local_sakha_number IS DISTINCT FROM NULLIF(BTRIM(claimed_local_sakha_number), '');

        UPDATE nss.registration_claim
           SET is_legacy_member = TRUE
         WHERE claimed_local_sakha_number IS NOT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'nss' AND table_name = 'registration_claim'
          AND column_name = 'darshak_is_legacy_member'
    ) THEN
        ALTER TABLE nss.registration_claim
            ADD COLUMN darshak_is_legacy_member BOOLEAN NOT NULL DEFAULT FALSE;

        UPDATE nss.registration_claim
           SET darshak_local_sakha_number = NULLIF(BTRIM(darshak_local_sakha_number), '')
         WHERE darshak_local_sakha_number IS NOT NULL
           AND darshak_local_sakha_number IS DISTINCT FROM NULLIF(BTRIM(darshak_local_sakha_number), '');

        UPDATE nss.registration_claim
           SET darshak_is_legacy_member = TRUE
         WHERE darshak_local_sakha_number IS NOT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_registration_claim_legacy_home'
          AND conrelid = 'nss.registration_claim'::regclass
    ) THEN
        ALTER TABLE nss.registration_claim
            ADD CONSTRAINT chk_registration_claim_legacy_home
            CHECK (is_legacy_member = (claimed_local_sakha_number IS NOT NULL));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_registration_claim_legacy_darshak'
          AND conrelid = 'nss.registration_claim'::regclass
    ) THEN
        ALTER TABLE nss.registration_claim
            ADD CONSTRAINT chk_registration_claim_legacy_darshak
            CHECK (darshak_is_legacy_member = (darshak_local_sakha_number IS NOT NULL));
    END IF;
END
$$;
