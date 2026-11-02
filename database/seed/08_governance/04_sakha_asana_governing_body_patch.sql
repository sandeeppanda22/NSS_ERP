-- =====================================================
-- NSS ERP
-- Module: Governance (seed patch)
-- File: 04_sakha_asana_governing_body_patch.sql
-- Version: 1.0 (2026-10-30, owner decision)
--
-- Purpose:
--   A Sakha Asana (organization type SAKHA_ASANA) is a Sakha Sangha without its
--   own building: it has its own Governing Body and President exactly like a
--   Sakha Sangha. 03_body_master.sql seeds one empty SAKHA_GOVERNING_BODY shell
--   per active SAKHA_SANGHA organization only, and that seed is existence-gated
--   (skipped on any database where nss.body_master already exists). This
--   idempotent patch (run_sql after the seed in 02_build.sh / 02_build.ps1 /
--   render_build.sh) gives every ACTIVE SAKHA_ASANA organization that has no
--   active SAKHA_GOVERNING_BODY a shell with the same shape/naming as the seed.
--   No-op when every Asana already has one (and on a database with no Asana).
--   Office-holders are never seeded; the Sakha re-parent approval chain
--   (api/services/org_reparent_service.py) resolves the Asana's own President
--   from this body, falling back to the Kendra President only while the seat is
--   vacant or the requester holds it.
-- =====================================================

INSERT INTO nss.body_master (body_type_master_pk, body_code, body_name, description, organization_pk, effective_from)
SELECT
    bt.body_type_master_pk,
    COALESCE(o.organization_code, o.organization_pk::text) || '_GB',
    o.organization_name || ' — Governing Body',
    'Sakha Governing Body for ' || o.organization_name || ' (Sakha Asana). Org-scoped; auto-created shell, office-holders assigned via election/appointment.',
    o.organization_pk,
    CURRENT_DATE
FROM nss.organization o
JOIN nss.master_data ot
    ON ot.master_data_pk = o.organization_type_master_data_pk
JOIN nss.master_category mc_type
    ON mc_type.master_category_pk = ot.master_category_pk
JOIN nss.master_data os
    ON os.master_data_pk = o.status_master_data_pk
JOIN nss.master_category mc_status
    ON mc_status.master_category_pk = os.master_category_pk
CROSS JOIN nss.body_type_master bt
WHERE mc_type.category_code   = 'ORGANIZATION_TYPE'
  AND ot.value_code           = 'SAKHA_ASANA'
  AND mc_status.category_code = 'STATUS'
  AND os.value_code           = 'ACTIVE'
  AND o.is_active             = TRUE
  AND bt.body_type_code       = 'SAKHA_GOVERNING_BODY'
  AND NOT EXISTS (
      SELECT 1 FROM nss.body_master bm
      WHERE bm.organization_pk = o.organization_pk
        AND bm.body_type_master_pk = bt.body_type_master_pk
        AND bm.is_active = TRUE
  )
ON CONFLICT (body_code) DO NOTHING;
