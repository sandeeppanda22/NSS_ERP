-- =====================================================
-- NSS ERP
-- Module: Finance (Tier 12)
-- File: 04_finance_head_approval_patch.sql (idempotent patch)
-- Version: 1.0 (2026-11-17)
-- Authority: owner decision 2026-11-17: income on a pre-defined head (Pranami, Parichaya Patra, Anumati Patra, subscription)
--            needs no approval; reimbursing a member who paid on the Sangha's behalf is its own head that names the member.
-- =====================================================
-- Runs AFTER ddl/14_finance/15_finance_head_approval_patch.sql (the columns) and 02_finance_head_templates_patch.sql.
-- Only heads nobody has edited yet are touched (updated_at IS NULL), so an administrator's later choice is never overwritten
-- by a re-run. Sangha copies of a template (template_head_pk) follow the template they were adopted from.
-- =====================================================

UPDATE nss.finance_head
   SET skips_approval = TRUE
 WHERE organization_pk IS NULL
   AND head_code IN ('PARICHAYA_PATRA', 'ANUMATI_PATRA', 'PRANAMI_ANNUAL', 'PRANAMI_SPECIAL', 'PRANAMI_SINKING_FUND',
                     'MEMBERSHIP_SUBSCRIPTION')
   AND direction = 'INCOME' AND skips_approval = FALSE AND updated_at IS NULL;

UPDATE nss.finance_head c
   SET skips_approval = TRUE
  FROM nss.finance_head t
 WHERE c.template_head_pk = t.finance_head_pk AND t.organization_pk IS NULL AND t.skips_approval = TRUE
   AND c.direction = 'INCOME' AND c.skips_approval = FALSE AND c.updated_at IS NULL;

-- Every contribution a member pays by UPI (a Pranami head with UPI on) is already a pre-defined head.
UPDATE nss.finance_head
   SET skips_approval = TRUE
 WHERE is_pranami = TRUE AND direction = 'INCOME' AND skips_approval = FALSE AND updated_at IS NULL
   AND (allow_upi = TRUE OR applies_to_all_sakhas = TRUE OR template_head_pk IS NOT NULL);

INSERT INTO nss.finance_head
    (organization_pk, head_code, head_name, description, direction, is_restricted, restriction_purpose,
     required_fund_type, is_pranami, requires_member, display_order)
VALUES
    (NULL, 'MEMBER_REIMBURSEMENT', 'Member reimbursement',
     'Repaying a member who paid a Sangha expense out of their own pocket. The member must be named and the bills submitted.',
     'EXPENSE', FALSE, NULL, NULL, FALSE, TRUE, 115)
ON CONFLICT (head_code) WHERE organization_pk IS NULL DO NOTHING;
