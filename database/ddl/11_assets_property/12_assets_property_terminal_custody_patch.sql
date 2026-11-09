-- =====================================================
-- NSS ERP
-- Module: Assets & Property (Module #22)
-- File: 12_assets_property_terminal_custody_patch.sql (idempotent patch)
-- Not a table - run with run_sql / Invoke-Sql on every build, AFTER
-- seed/11_assets_property/01_assets_property_reference_data_patch.sql (it
-- needs the DISPOSED / RETIRED custodianship end reasons that file seeds).
-- Version: 1.0 (2026-11-03)
-- Authority: owner decision 2026-11-03, GDR-010 §2F, open question 3 (decided): disposal /
--            retirement CLOSES the active custodianship.
--
-- Going forward the API closes the ACTIVE custodianship in the same
-- transaction as the DISPOSED / RETIRED transition (end reason DISPOSED /
-- RETIRED, effective_to = the transition date). This patch brings records that
-- were disposed/retired BEFORE that rule in line: every still-ACTIVE
-- custodianship of a DISPOSED property / RETIRED asset becomes ENDED with the
-- matching end reason. effective_to is the date the record last changed
-- (updated_at, capped at today) but never before effective_from.
--
-- Idempotent: once the rows are ENDED the WHERE clause matches nothing, so a
-- re-run (and every fresh build) changes zero rows. The custodianship guard
-- (08) permits ACTIVE -> ENDED; ENDED rows are never modified.
-- =====================================================

UPDATE nss.custodianship c
SET status = 'ENDED',
    effective_to = GREATEST(c.effective_from, LEAST(COALESCE(p.updated_at, CURRENT_TIMESTAMP)::date, CURRENT_DATE)),
    end_reason_master_data_pk = er.master_data_pk,
    updated_at = CURRENT_TIMESTAMP
FROM nss.property p,
     nss.master_data er
JOIN nss.master_category erc ON erc.master_category_pk = er.master_category_pk
                            AND erc.category_code = 'CUSTODIANSHIP_END_REASON'
WHERE c.property_pk = p.property_pk
  AND p.status = 'DISPOSED'
  AND c.status = 'ACTIVE'
  AND c.is_active = TRUE
  AND er.value_code = 'DISPOSED';

UPDATE nss.custodianship c
SET status = 'ENDED',
    effective_to = GREATEST(c.effective_from, LEAST(COALESCE(a.updated_at, CURRENT_TIMESTAMP)::date, CURRENT_DATE)),
    end_reason_master_data_pk = er.master_data_pk,
    updated_at = CURRENT_TIMESTAMP
FROM nss.asset a,
     nss.master_data er
JOIN nss.master_category erc ON erc.master_category_pk = er.master_category_pk
                            AND erc.category_code = 'CUSTODIANSHIP_END_REASON'
WHERE c.asset_pk = a.asset_pk
  AND a.status = 'RETIRED'
  AND c.status = 'ACTIVE'
  AND c.is_active = TRUE
  AND er.value_code = 'RETIRED';
