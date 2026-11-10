# =====================================================
# NSS ERP — Post-Build Validation (PowerShell)
# =====================================================
#
# Validates that all implemented modules were built
# correctly. Does NOT execute any DDL or seed scripts -
# run 02_build.ps1 first.
#
# Authority: SOL-ARCH-010, SOL-ARCH-011
# Version: 1.8 - Finance now 11 tables (90 total): + financial_account, finance_head, upi_payment_request, finance_gateway_event, head/UPI checks (2026-11-10; desk-checked, never run on PowerShell).
# Version: 1.7 - add Finance (7 tables, 86 total), FINANCE_* / PAYMENT_METHOD patch checks, raised minimums: permission_master 33,
#                 role_permission 192, master_category 27, master_data 162, id_sequence_master 21 (2026-11-10; desk-checked, never run on PowerShell).
# Version: 1.6 - add Module 11 live_change_marker (1 table, 79 total) (2026-11-03; desk-checked, never run on PowerShell).
# Version: 1.5 - minimums recomputed after ACQUISITION_METHOD + DISPOSED/RETIRED end reasons: master_category 26,
#                 master_data 156 (2026-11-03; desk-checked, never run on PowerShell).
# Version: 1.4 - add Assets & Property (7 tables, 78 total), ASSET_* grants, raised
#                 permission_master/role_permission/master_category/master_data/
#                 id_sequence_master minimums (2026-11-02; desk-checked, never run on PowerShell).
# Version: 1.3 - parity re-audit vs 03_validate.sh (2026-11-01): patch-delivered
#                 object checks, corrected master_category/master_data minimums.
# Version: 1.2 - add Auth (5 tables), Admin (2 tables),
#                 person address FK columns; Governance key-column
#                 + FK-integrity checks (parity with 03_validate.sh)
#
# Usage:
#   .\database\scripts\03_validate.ps1 [-DbName nss_erp] [-DbUser nss_db_owner] [-DbHost localhost] [-DbPort 5432]
#
# =====================================================

param(
    [string]$DbName = "nss_erp",
    [string]$DbUser = "nss_db_owner",
    [string]$DbHost = "localhost",
    [int]$DbPort = 5432
)

# Prompt for password once; export so all psql calls reuse it.
if (-not $env:PGPASSWORD) {
    $securePass = Read-Host "Password for ${DbUser}@${DbHost}:${DbPort}/${DbName}" -AsSecureString
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePass)
    )
}

$pass_count = 0
$fail_count = 0
$warn_count = 0

function Invoke-PsqlQuery {
    param([string]$Query)
    $result = & psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -t -A -c $Query 2>&1
    if ($LASTEXITCODE -ne 0) { return "ERROR" }
    return ($result | Out-String).Trim()
}

function Log-Pass { param([string]$Msg); Write-Host "  [PASS] $Msg" -ForegroundColor Green; $script:pass_count++ }
function Log-Fail { param([string]$Msg); Write-Host "  [FAIL] $Msg" -ForegroundColor Red; $script:fail_count++ }
function Log-Warn { param([string]$Msg); Write-Host "  [WARN] $Msg" -ForegroundColor Yellow; $script:warn_count++ }

function Check-TableExists {
    param([string]$Table)
    $result = Invoke-PsqlQuery "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nss' AND table_name = '$Table');"
    if ($result -eq "t") { Log-Pass "$Table exists" } else { Log-Fail "$Table MISSING" }
}

function Check-RowCount {
    param([string]$Table, [int]$Expected)
    $count = Invoke-PsqlQuery "SELECT COUNT(*) FROM nss.$Table;"
    if ($count -eq "ERROR") { Log-Fail "${Table}: query failed" }
    elseif ([int]$count -ge $Expected) { Log-Pass "${Table}: $count rows (expected >= $Expected)" }
    else { Log-Warn "${Table}: $count rows (expected >= $Expected)" }
}

function Check-NoDuplicates {
    param([string]$Table, [string]$Column)
    $dups = Invoke-PsqlQuery "SELECT COUNT(*) FROM (SELECT $Column FROM nss.$Table GROUP BY $Column HAVING COUNT(*) > 1) x;"
    if ($dups -eq "0") { Log-Pass "${Table}: no duplicate $Column" }
    elseif ($dups -eq "ERROR") { Log-Fail "${Table}: duplicate check failed" }
    else { Log-Fail "${Table}: $dups duplicate $Column values" }
}

function Check-FkIntegrity {
    param([string]$Label, [string]$Query)
    $orphans = Invoke-PsqlQuery $Query
    if ($orphans -eq "0") { Log-Pass "${Label}: FK integrity valid" }
    elseif ($orphans -eq "ERROR") { Log-Fail "${Label}: FK check failed" }
    else { Log-Fail "${Label}: $orphans orphaned rows" }
}

function Check-WarnCount {
    param([string]$Label, [string]$Query)
    $n = Invoke-PsqlQuery $Query
    if ($n -eq "0") { Log-Pass "${Label}: none" }
    elseif ($n -eq "ERROR") { Log-Fail "${Label}: check failed" }
    else { Log-Warn "${Label}: $n row(s) - see database/scripts/README.md diagnostic SELECT" }
}

function Check-ColumnExists {
    param([string]$Table, [string]$Column)
    $result = Invoke-PsqlQuery "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'nss' AND table_name = '$Table' AND column_name = '$Column');"
    if ($result -eq "t") { Log-Pass "${Table}.${Column} present" } else { Log-Fail "${Table}.${Column} MISSING" }
}

function Check-MinPercentage {
    param([string]$Label, [string]$Query, [double]$MinPct)
    $pct = Invoke-PsqlQuery $Query
    if ($pct -eq "ERROR") { Log-Fail "${Label}: query failed" }
    elseif ([double]$pct -ge $MinPct) { Log-Pass "${Label}: ${pct}% (expected >= ${MinPct}%)" }
    else { Log-Fail "${Label}: ${pct}% (expected >= ${MinPct}%)" }
}

# Header
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  NSS ERP - Post-Build Validation" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Database: $DbName"
Write-Host "  User:     $DbUser"
Write-Host "  Host:     ${DbHost}:${DbPort}"
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Bootstrap RBAC
Write-Host "--- Bootstrap RBAC ---" -ForegroundColor Cyan
Write-Host "  Tables:"
Check-TableExists "role_master"
Check-TableExists "permission_master"
Check-TableExists "role_permission"

Write-Host "  Row counts:"
Check-RowCount "role_master" 11
Check-RowCount "permission_master" 33
# 178 = 166 + 12 asset grants. A DB that ran the original 16-row patch holds 182 rows, 4 of them
# soft-deleted (is_active = FALSE, history is never hard-deleted): still >= 178, so the minimum holds.
# Since 2026-11-04 (GDR-011) one more row (Auditor PERSON_VIEW_SENSITIVE) is soft-deleted by patch 07: 178 rows, 177 active; the minimum counts all rows.
Check-RowCount "role_permission" 192

Write-Host "  Unique constraints:"
Check-NoDuplicates "role_master" "role_code"

Write-Host "  FK integrity:"
Check-FkIntegrity "role_permission -> role_master" "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.role_master rm ON rp.role_master_pk = rm.role_master_pk WHERE rm.role_master_pk IS NULL;"
Check-FkIntegrity "role_permission -> permission_master" "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.permission_master pm ON rp.permission_master_pk = pm.permission_master_pk WHERE pm.permission_master_pk IS NULL;"
Write-Host "  Per-role permission minimums (a skipped patch would leave a role short):"
Check-FkIntegrity "role_permission: NSS_ERP_ADVISORY_BOARD_ADMIN has >= 8 rows" "SELECT GREATEST(8 - COUNT(*), 0) FROM nss.role_permission rp JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk WHERE rm.role_code = 'NSS_ERP_ADVISORY_BOARD_ADMIN';"
Check-FkIntegrity "role_permission: NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN has >= 18 rows" "SELECT GREATEST(18 - COUNT(*), 0) FROM nss.role_permission rp JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk WHERE rm.role_code = 'NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN';"
Check-FkIntegrity "role_permission: NSS_ERP_ATTENDANCE_MARKER has >= 2 rows" "SELECT GREATEST(2 - COUNT(*), 0) FROM nss.role_permission rp JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk WHERE rm.role_code = 'NSS_ERP_ATTENDANCE_MARKER';"
Check-FkIntegrity "role_permission: NSS_ERP_SAKHA_ADMIN has >= 18 rows" "SELECT GREATEST(18 - COUNT(*), 0) FROM nss.role_permission rp JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk WHERE rm.role_code = 'NSS_ERP_SAKHA_ADMIN';"
Write-Host ""

# Foundation
Write-Host "--- Foundation ---" -ForegroundColor Cyan
Write-Host "  Tables:"
$foundationTables = @("master_category","system_setting","id_sequence_master","country","document_master","field_change_log","master_data","state","district","city_village","postal_code","festival_master","festival_calendar_date")
foreach ($t in $foundationTables) { Check-TableExists $t }

Write-Host "  Row counts:"
Check-RowCount "master_category" 27
Check-RowCount "master_data" 162
Check-RowCount "id_sequence_master" 21
Check-RowCount "country" 5
Check-RowCount "state" 112
Check-RowCount "district" 780
Check-RowCount "system_setting" 5
Check-RowCount "postal_code" 17800
Check-RowCount "city_village" 659000

Write-Host "  Unique constraints:"
Check-NoDuplicates "master_category" "category_code"
Check-NoDuplicates "country" "country_code"
Check-NoDuplicates "id_sequence_master" "sequence_code"
Check-NoDuplicates "postal_code" "postal_code"

Write-Host "  FK integrity:"
Check-FkIntegrity "master_data -> master_category" "SELECT COUNT(*) FROM nss.master_data md LEFT JOIN nss.master_category mc ON md.master_category_pk = mc.master_category_pk WHERE mc.master_category_pk IS NULL;"
Check-FkIntegrity "state -> country" "SELECT COUNT(*) FROM nss.state s LEFT JOIN nss.country c ON s.country_pk = c.country_pk WHERE c.country_pk IS NULL;"
Check-FkIntegrity "district -> state" "SELECT COUNT(*) FROM nss.district d LEFT JOIN nss.state s ON d.state_pk = s.state_pk WHERE s.state_pk IS NULL;"
Check-FkIntegrity "postal_code -> state" "SELECT COUNT(*) FROM nss.postal_code p LEFT JOIN nss.state s ON p.state_pk = s.state_pk WHERE s.state_pk IS NULL;"
Check-FkIntegrity "city_village -> postal_code" "SELECT COUNT(*) FROM nss.city_village cv LEFT JOIN nss.postal_code pc ON cv.postal_code_pk = pc.postal_code_pk WHERE cv.postal_code_pk IS NOT NULL AND pc.postal_code_pk IS NULL;"
Check-FkIntegrity "city_village -> district" "SELECT COUNT(*) FROM nss.city_village cv LEFT JOIN nss.district d ON cv.district_pk = d.district_pk WHERE cv.district_pk IS NOT NULL AND d.district_pk IS NULL;"

Write-Host "  Geography model (SOL-ARCH-010 Amendment, 2026-10-02 - district at city_village grain):"
Check-ColumnExists "city_village" "district_pk"
Check-MinPercentage "city_village district_pk coverage" "SELECT ROUND(COUNT(*) FILTER (WHERE district_pk IS NOT NULL) * 100.0 / NULLIF(COUNT(*),0), 2) FROM nss.city_village;" 98

Write-Host "  Deferred columns:"
Check-ColumnExists "document_master" "person_pk"
Check-ColumnExists "document_master" "uploaded_by_sangha_sevi_pk"
Write-Host ""

Write-Host "  Registration-Time Geography Creation (2026-10-21 - submitted_by_person_pk):"
Check-ColumnExists "city_village" "submitted_by_person_pk"
Check-ColumnExists "postal_code" "submitted_by_person_pk"
Check-ColumnExists "post_office" "submitted_by_person_pk"
Write-Host ""

# Organization (1 table - type/status via master_data)
Write-Host "--- Organization ---" -ForegroundColor Cyan
Write-Host "  Tables:"
Check-TableExists "organization"

Write-Host "  Row counts:"
Check-RowCount "organization" 179

Write-Host "  Unique constraints:"
Check-NoDuplicates "organization" "organization_code"

Write-Host "  FK integrity:"
Check-FkIntegrity "organization -> master_data (type)" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.master_data md ON o.organization_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "organization -> master_data (status)" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.master_data md ON o.status_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "organization -> country" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.country c ON o.country_pk = c.country_pk WHERE o.country_pk IS NOT NULL AND c.country_pk IS NULL;"
Check-FkIntegrity "organization -> city_village" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.city_village cv ON o.city_village_pk = cv.city_village_pk WHERE o.city_village_pk IS NOT NULL AND cv.city_village_pk IS NULL;"
Check-FkIntegrity "organization -> postal_code" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.postal_code pc ON o.postal_code_pk = pc.postal_code_pk WHERE o.postal_code_pk IS NOT NULL AND pc.postal_code_pk IS NULL;"
Check-FkIntegrity "organization: exactly one active ADVISORY_BOARD organization (patch 07_advisory_board_organization_patch.sql ran)" "SELECT CASE WHEN (SELECT COUNT(*) FROM nss.organization o JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk WHERE md.value_code = 'ADVISORY_BOARD' AND o.is_active = TRUE) = 1 THEN 0 ELSE 1 END;"
Check-FkIntegrity "organization: ORGANIZATION_TYPE has all 14 values (13 Bye-Law types + ADVISORY_BOARD)" "SELECT CASE WHEN (SELECT COUNT(*) FROM nss.master_data md JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk WHERE mc.category_code = 'ORGANIZATION_TYPE' AND md.is_active = TRUE) >= 14 THEN 0 ELSE 1 END;"
Check-FkIntegrity "organization: fn_is_sakha_like_org_type() present" "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'nss' AND p.proname = 'fn_is_sakha_like_org_type') THEN 0 ELSE 1 END;"
Check-FkIntegrity "organization: every active SAKHA_ASANA has a SAKHA_GOVERNING_BODY (patch 04_sakha_asana_governing_body_patch.sql ran)" "SELECT COUNT(*) FROM nss.organization o JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk WHERE md.value_code = 'SAKHA_ASANA' AND o.is_active = TRUE AND NOT EXISTS (SELECT 1 FROM nss.body_master bm JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk WHERE bm.organization_pk = o.organization_pk AND bt.body_type_code = 'SAKHA_GOVERNING_BODY');"
Check-FkIntegrity "organization: singleton trigger present" "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_enforce_organization_singleton' AND NOT tgisinternal) THEN 0 ELSE 1 END;"
Check-FkIntegrity "organization: at most one active row per singleton rule (KENDRA, NILACHALA_KUTIRA, SMRUTI_MANDIRA, ADVISORY_BOARD, central Mahila Sangha)" "SELECT COALESCE(SUM(GREATEST(g.n - 1, 0)), 0) FROM (SELECT COUNT(*) AS n FROM (SELECT md.value_code AS rule FROM nss.organization o JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk WHERE o.is_active = TRUE AND md.value_code IN ('KENDRA', 'NILACHALA_KUTIRA', 'SMRUTI_MANDIRA', 'ADVISORY_BOARD') UNION ALL SELECT 'CENTRAL_MAHILA_SANGHA' FROM nss.organization o JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk JOIN nss.organization p ON p.organization_pk = o.parent_organization_pk JOIN nss.master_data pmd ON pmd.master_data_pk = p.organization_type_master_data_pk WHERE o.is_active = TRUE AND md.value_code = 'MAHILA_SANGHA' AND pmd.value_code = 'KENDRA') r GROUP BY r.rule) g;"
Write-Host ""

# Person (2 tables - no seed data)
Write-Host "--- Person ---" -ForegroundColor Cyan
Write-Host "  Tables:"
Check-TableExists "person"
Check-TableExists "person_address"

Write-Host "  Row counts (no seed - expect 0):"
Check-RowCount "person" 0
Check-RowCount "person_address" 0

Write-Host "  FK integrity:"
Check-FkIntegrity "person -> master_data (gender)" "SELECT COUNT(*) FROM nss.person p LEFT JOIN nss.master_data md ON p.gender_master_data_pk = md.master_data_pk WHERE p.gender_master_data_pk IS NOT NULL AND md.master_data_pk IS NULL;"
Check-FkIntegrity "person -> master_data (marital_status)" "SELECT COUNT(*) FROM nss.person p LEFT JOIN nss.master_data md ON p.marital_status_master_data_pk = md.master_data_pk WHERE p.marital_status_master_data_pk IS NOT NULL AND md.master_data_pk IS NULL;"
Check-FkIntegrity "person -> master_data (blood_group)" "SELECT COUNT(*) FROM nss.person p LEFT JOIN nss.master_data md ON p.blood_group_master_data_pk = md.master_data_pk WHERE p.blood_group_master_data_pk IS NOT NULL AND md.master_data_pk IS NULL;"
Check-FkIntegrity "person_address -> person" "SELECT COUNT(*) FROM nss.person_address pa LEFT JOIN nss.person p ON pa.person_pk = p.person_pk WHERE p.person_pk IS NULL;"
Check-FkIntegrity "person_address -> master_data (address_type)" "SELECT COUNT(*) FROM nss.person_address pa LEFT JOIN nss.master_data md ON pa.address_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"

Write-Host "  Person address FK columns:"
Check-ColumnExists "person" "country_pk"
Check-ColumnExists "person" "state_pk"
Check-ColumnExists "person" "district_pk"
Check-ColumnExists "person" "city_village_pk"
Check-ColumnExists "person" "postal_code_pk"
Write-Host ""

# Authentication (5 tables)
Write-Host "--- Authentication ---" -ForegroundColor Cyan
Write-Host "  Tables:"
Check-TableExists "user_account"
Check-TableExists "password_history"
Check-TableExists "registration_claim"
Check-TableExists "password_reset_token"
Check-TableExists "user_session"

Write-Host "  Row counts:"
Check-RowCount "user_account" 1
Check-RowCount "password_history" 0

Write-Host "  Key columns:"
Check-ColumnExists "user_account" "person_pk"
Check-ColumnExists "user_account" "password_hash"
Check-ColumnExists "user_account" "account_status"
Check-ColumnExists "user_account" "is_active"
Check-ColumnExists "user_account" "failed_login_attempts"
Check-ColumnExists "user_account" "locked_until"
Check-ColumnExists "user_account" "password_expires_at"
Check-ColumnExists "user_account" "force_password_change"
Check-ColumnExists "user_account" "last_login_at"
Check-ColumnExists "password_history" "user_account_pk"
Check-ColumnExists "password_history" "password_hash"
Check-ColumnExists "user_session" "user_account_pk"
Check-ColumnExists "user_session" "revoked_at"
Check-ColumnExists "user_session" "expires_at"
Check-ColumnExists "user_session" "device_label"

Write-Host "  Unique constraints:"
Check-NoDuplicates "user_account" "person_pk"

Write-Host "  FK integrity:"
Check-FkIntegrity "user_account -> person" "SELECT COUNT(*) FROM nss.user_account ua LEFT JOIN nss.person p ON ua.person_pk = p.person_pk WHERE p.person_pk IS NULL;"
Check-FkIntegrity "user_session -> user_account" "SELECT COUNT(*) FROM nss.user_session us LEFT JOIN nss.user_account ua ON us.user_account_pk = ua.user_account_pk WHERE ua.user_account_pk IS NULL;"
Check-FkIntegrity "password_history -> user_account" "SELECT COUNT(*) FROM nss.password_history ph LEFT JOIN nss.user_account ua ON ph.user_account_pk = ua.user_account_pk WHERE ua.user_account_pk IS NULL;"
Write-Host ""

# Administration (2 tables)
Write-Host "--- Administration ---" -ForegroundColor Cyan
Write-Host "  Tables:"
Check-TableExists "user_role"
Check-TableExists "admin_scope"

Write-Host "  Row counts:"
Check-RowCount "user_role" 1
Check-RowCount "admin_scope" 1

Write-Host "  Key columns:"
Check-ColumnExists "user_role" "user_account_pk"
Check-ColumnExists "user_role" "role_master_pk"
Check-ColumnExists "user_role" "is_active"
Check-ColumnExists "admin_scope" "user_role_pk"
Check-ColumnExists "admin_scope" "scope_level"
Check-ColumnExists "admin_scope" "organization_pk"

Write-Host "  FK integrity:"
Check-FkIntegrity "user_role -> user_account" "SELECT COUNT(*) FROM nss.user_role ur LEFT JOIN nss.user_account ua ON ur.user_account_pk = ua.user_account_pk WHERE ua.user_account_pk IS NULL;"
Check-FkIntegrity "user_role -> role_master" "SELECT COUNT(*) FROM nss.user_role ur LEFT JOIN nss.role_master rm ON ur.role_master_pk = rm.role_master_pk WHERE rm.role_master_pk IS NULL;"
Check-FkIntegrity "admin_scope -> user_role" "SELECT COUNT(*) FROM nss.admin_scope asc2 LEFT JOIN nss.user_role ur ON asc2.user_role_pk = ur.user_role_pk WHERE ur.user_role_pk IS NULL;"
Check-FkIntegrity "admin_scope -> organization" "SELECT COUNT(*) FROM nss.admin_scope asc2 LEFT JOIN nss.organization o ON asc2.organization_pk = o.organization_pk WHERE asc2.organization_pk IS NOT NULL AND o.organization_pk IS NULL;"
Write-Host ""

# Family, Membership, audit (existence only - no seed data)
Write-Host "--- Family / Membership / Audit ---" -ForegroundColor Cyan
Write-Host "  Tables (existence only - no seed data):"
Check-TableExists "family_group"
Check-TableExists "family_relationship"
Check-TableExists "family_transition_history"
Check-TableExists "family_head_history"
Check-TableExists "family_link"
Check-TableExists "family_admin"
Check-TableExists "sangha_sevi"
Check-TableExists "membership_status_history"
Check-TableExists "membership_renewal_request"
Check-TableExists "membership_renewal_history"
Check-TableExists "membership_transfer_history"
Check-TableExists "membership_sakha_affiliation"
Check-TableExists "membership_journey_event"
Check-TableExists "probationary_member_review"
Check-TableExists "parichaya_patra"
Check-TableExists "parichaya_patra_history"
Check-TableExists "anumati_patra"
Check-TableExists "anumati_patra_history"
Check-TableExists "darshak_attendance_registration"
Check-TableExists "credential_sequence_counter"
Check-TableExists "sakha_local_number_counter"
Check-TableExists "membership_change_request"
Check-TableExists "system_event_log"
Write-Host "  Local Sakha ID allocator + home-affiliation guard (files 19/20):"
Check-FkIntegrity "membership: nss.fn_next_sakha_local_number() present" "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'nss' AND p.proname = 'fn_next_sakha_local_number') THEN 0 ELSE 1 END;"
Check-FkIntegrity "membership: nss.fn_assert_sevi_has_home_affiliation() present" "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'nss' AND p.proname = 'fn_assert_sevi_has_home_affiliation') THEN 0 ELSE 1 END;"
Check-FkIntegrity "membership: deferred home-affiliation constraint triggers present" "SELECT CASE WHEN (SELECT COUNT(*) FROM pg_trigger WHERE tgname IN ('ctrg_sevi_home_affiliation', 'ctrg_affiliation_home_affiliation') AND tgconstraint <> 0 AND tgdeferrable AND tginitdeferred AND NOT tgisinternal) = 2 THEN 0 ELSE 1 END;"
Check-WarnCount "membership: active Sangha Sevis with NO open home affiliation / Local Sakha ID (not auto-repaired)" "SELECT COUNT(*) FROM nss.sangha_sevi ss WHERE ss.is_active = TRUE AND ss.is_system_account = FALSE AND NOT EXISTS (SELECT 1 FROM nss.membership_sakha_affiliation msa WHERE msa.sangha_sevi_pk = ss.sangha_sevi_pk AND msa.organization_pk = ss.organization_pk AND msa.effective_to IS NULL AND msa.affiliation_status IN ('ACTIVE', 'REACTIVATED') AND btrim(msa.local_sakha_erp_id) <> '');"
Write-Host "  Legacy-vs-new Local Sakha Number flags (registration_claim, GDR-009):"
Check-FkIntegrity "registration_claim: is_legacy_member + darshak_is_legacy_member columns present" "SELECT CASE WHEN (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'nss' AND table_name = 'registration_claim' AND column_name IN ('is_legacy_member', 'darshak_is_legacy_member')) = 2 THEN 0 ELSE 1 END;"
Check-FkIntegrity "registration_claim: legacy flag/number agreement CHECKs present" "SELECT CASE WHEN (SELECT COUNT(*) FROM pg_constraint WHERE conrelid = 'nss.registration_claim'::regclass AND conname IN ('chk_registration_claim_legacy_home', 'chk_registration_claim_legacy_darshak')) = 2 THEN 0 ELSE 1 END;"
Check-WarnCount "registration_claim: rows whose legacy flag disagrees with the stored number (must be 0)" "SELECT COUNT(*) FROM nss.registration_claim WHERE is_legacy_member <> (claimed_local_sakha_number IS NOT NULL) OR darshak_is_legacy_member <> (darshak_local_sakha_number IS NOT NULL);"
Check-WarnCount "membership: active, non-system Sangha Sevis lacking an ACTIVE credential of the type their membership type requires (Parichaya for Regular/Associate, Anumati for Probationary; GDR-009 invariant, not auto-repaired)" "SELECT COUNT(*) FROM nss.sangha_sevi ss JOIN nss.master_data mt ON mt.master_data_pk = ss.membership_type_master_data_pk WHERE ss.is_active = TRUE AND ss.is_system_account = FALSE AND CASE WHEN mt.value_code = 'PROBATIONARY' THEN NOT EXISTS (SELECT 1 FROM nss.anumati_patra ap WHERE ap.sangha_sevi_pk = ss.sangha_sevi_pk AND ap.status = 'ACTIVE') ELSE NOT EXISTS (SELECT 1 FROM nss.parichaya_patra pp WHERE pp.sangha_sevi_pk = ss.sangha_sevi_pk AND pp.status = 'ACTIVE') END;"
Write-Host ""

# Governance (10 tables - existence only, no seed)
Write-Host "--- Governance ---" -ForegroundColor Cyan
Check-TableExists "body_type_master"
Check-TableExists "position_master"
Check-TableExists "body_master"
Check-TableExists "body_member_assignment"
Check-TableExists "acting_position_assignment"
Check-TableExists "election"
Check-TableExists "election_nomination"
Check-TableExists "election_vote"
Check-TableExists "election_vote_participation"
Check-TableExists "election_result"
Write-Host "  Key columns:"
Check-ColumnExists "body_master" "body_type_master_pk"
Check-ColumnExists "body_member_assignment" "person_pk"
Check-ColumnExists "family_head_history" "updated_at"
Check-ColumnExists "election_vote" "voter_person_pk"
Check-FkIntegrity "uq_election_nomination_active_candidate is live-only (re-file index)" "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'nss' AND indexname = 'uq_election_nomination_active_candidate' AND indexdef LIKE '%nomination_status%') THEN 0 ELSE 1 END;"
Write-Host "  FK integrity (no orphans - vacuously true until seeded):"
Check-FkIntegrity "body_master -> body_type_master" "SELECT COUNT(*) FROM nss.body_master bm LEFT JOIN nss.body_type_master bt ON bm.body_type_master_pk = bt.body_type_master_pk WHERE bt.body_type_master_pk IS NULL;"
Check-FkIntegrity "body_member_assignment -> body_master" "SELECT COUNT(*) FROM nss.body_member_assignment bma LEFT JOIN nss.body_master bm ON bma.body_master_pk = bm.body_master_pk WHERE bm.body_master_pk IS NULL;"
Check-FkIntegrity "election_result -> election" "SELECT COUNT(*) FROM nss.election_result er LEFT JOIN nss.election e ON er.election_pk = e.election_pk WHERE e.election_pk IS NULL;"
Write-Host ""

# Correspondence (5 tables, Tier 6 - existence only, no seed)
# Administration-owned capability; moved from Tier 5 to Tier 6
# (owner-confirmed 2026-10-16). financial_transaction FK on
# correspondence_finance_reference is deferred to Pass 2 (Finance/
# Tier 12 not yet built) - not checked here.
# correspondence_approval_step is the additive Sakha-President ->
# Kendra-office-bearer approval-chain overlay (owner request, 2026-10-21)
# - existence/FK checks only, same as its siblings (no seed either).
Write-Host "--- Correspondence ---" -ForegroundColor Cyan
Write-Host "  Tables (existence only - no seed data):"
Check-TableExists "correspondence"
Check-TableExists "correspondence_document"
Check-TableExists "correspondence_finance_reference"
Check-TableExists "correspondence_sequence_counter"
Check-TableExists "correspondence_approval_step"

Write-Host "  Key columns:"
Check-ColumnExists "correspondence" "reference_number"
Check-ColumnExists "correspondence" "register_organization_pk"
Check-ColumnExists "correspondence" "sender_person_capacity"
Check-ColumnExists "correspondence_document" "correspondence_pk"
Check-ColumnExists "correspondence_finance_reference" "relationship_type_master_data_pk"
Check-ColumnExists "correspondence_sequence_counter" "register_organization_pk"
Check-ColumnExists "correspondence_sequence_counter" "direction"
Check-ColumnExists "correspondence_sequence_counter" "financial_year_start"
Check-ColumnExists "correspondence_sequence_counter" "current_value"
Check-ColumnExists "correspondence_approval_step" "correspondence_pk"
Check-ColumnExists "correspondence_approval_step" "step_number"
Check-ColumnExists "correspondence_approval_step" "approver_person_pk"
Check-ColumnExists "correspondence_approval_step" "step_status"

Write-Host "  FK integrity (no orphans - vacuously true until seeded):"
Check-FkIntegrity "correspondence -> organization (register owner)" "SELECT COUNT(*) FROM nss.correspondence c LEFT JOIN nss.organization o ON c.register_organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"
Check-FkIntegrity "correspondence_document -> correspondence" "SELECT COUNT(*) FROM nss.correspondence_document cd LEFT JOIN nss.correspondence c ON cd.correspondence_pk = c.correspondence_pk WHERE c.correspondence_pk IS NULL;"
Check-FkIntegrity "correspondence_finance_reference -> correspondence" "SELECT COUNT(*) FROM nss.correspondence_finance_reference cfr LEFT JOIN nss.correspondence c ON cfr.correspondence_pk = c.correspondence_pk WHERE c.correspondence_pk IS NULL;"
Check-FkIntegrity "correspondence_finance_reference -> master_data (relationship_type)" "SELECT COUNT(*) FROM nss.correspondence_finance_reference cfr LEFT JOIN nss.master_data md ON cfr.relationship_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "correspondence_sequence_counter -> organization" "SELECT COUNT(*) FROM nss.correspondence_sequence_counter csc LEFT JOIN nss.organization o ON csc.register_organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"
Check-FkIntegrity "correspondence_approval_step -> correspondence" "SELECT COUNT(*) FROM nss.correspondence_approval_step cas LEFT JOIN nss.correspondence c ON cas.correspondence_pk = c.correspondence_pk WHERE c.correspondence_pk IS NULL;"
Check-FkIntegrity "correspondence_approval_step -> person (approver)" "SELECT COUNT(*) FROM nss.correspondence_approval_step cas LEFT JOIN nss.person p ON cas.approver_person_pk = p.person_pk WHERE p.person_pk IS NULL;"
Check-FkIntegrity "correspondence_approval_step -> position_master" "SELECT COUNT(*) FROM nss.correspondence_approval_step cas LEFT JOIN nss.position_master pm ON cas.approver_position_master_pk = pm.position_master_pk WHERE pm.position_master_pk IS NULL;"

Write-Host "  Unique constraints:"
Check-NoDuplicates "correspondence" "reference_number"
Write-Host ""

# Attendance (4 tables, Tier 6 - existence only, no seed, owner-confirmed
# 2026-10-27)
Write-Host "--- Attendance ---" -ForegroundColor Cyan
Write-Host "  Tables (existence only - no seed data):"
Check-TableExists "weekly_sangha_puja"
Check-TableExists "weekly_sangha_puja_attendance"
Check-TableExists "attendance_exception"
Check-TableExists "attendance_review"

Write-Host "  Key columns:"
Check-ColumnExists "weekly_sangha_puja" "sakha_pk"
Check-ColumnExists "weekly_sangha_puja" "puja_date"
Check-ColumnExists "weekly_sangha_puja_attendance" "weekly_sangha_puja_pk"
Check-ColumnExists "weekly_sangha_puja_attendance" "sangha_sevi_pk"
Check-ColumnExists "weekly_sangha_puja_attendance" "attendance_status_master_data_pk"
Check-ColumnExists "weekly_sangha_puja_attendance" "attendance_sakha_pk"
Check-ColumnExists "attendance_exception" "sangha_sevi_pk"
Check-ColumnExists "attendance_exception" "exception_type_master_data_pk"
Check-ColumnExists "attendance_review" "sangha_sevi_pk"
Check-ColumnExists "attendance_review" "review_status_master_data_pk"
Check-ColumnExists "attendance_review" "assigned_to_role"

Write-Host "  FK integrity (no orphans - vacuously true until seeded):"
Check-FkIntegrity "weekly_sangha_puja -> organization (sakha)" "SELECT COUNT(*) FROM nss.weekly_sangha_puja w LEFT JOIN nss.organization o ON w.sakha_pk = o.organization_pk WHERE o.organization_pk IS NULL;"
Check-FkIntegrity "weekly_sangha_puja_attendance: idx_wspa_puja_last_change present (patch 05_attendance_live_version_index_patch.sql ran)" "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'nss' AND indexname = 'idx_wspa_puja_last_change') THEN 0 ELSE 1 END;"
Check-FkIntegrity "weekly_sangha_puja_attendance -> weekly_sangha_puja" "SELECT COUNT(*) FROM nss.weekly_sangha_puja_attendance a LEFT JOIN nss.weekly_sangha_puja w ON a.weekly_sangha_puja_pk = w.weekly_sangha_puja_pk WHERE w.weekly_sangha_puja_pk IS NULL;"
Check-FkIntegrity "weekly_sangha_puja_attendance -> sangha_sevi" "SELECT COUNT(*) FROM nss.weekly_sangha_puja_attendance a LEFT JOIN nss.sangha_sevi s ON a.sangha_sevi_pk = s.sangha_sevi_pk WHERE s.sangha_sevi_pk IS NULL;"
Check-FkIntegrity "weekly_sangha_puja_attendance -> master_data (status)" "SELECT COUNT(*) FROM nss.weekly_sangha_puja_attendance a LEFT JOIN nss.master_data md ON a.attendance_status_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "attendance_exception -> sangha_sevi" "SELECT COUNT(*) FROM nss.attendance_exception e LEFT JOIN nss.sangha_sevi s ON e.sangha_sevi_pk = s.sangha_sevi_pk WHERE s.sangha_sevi_pk IS NULL;"
Check-FkIntegrity "attendance_review -> sangha_sevi" "SELECT COUNT(*) FROM nss.attendance_review r LEFT JOIN nss.sangha_sevi s ON r.sangha_sevi_pk = s.sangha_sevi_pk WHERE s.sangha_sevi_pk IS NULL;"
Check-FkIntegrity "attendance_review -> organization" "SELECT COUNT(*) FROM nss.attendance_review r LEFT JOIN nss.organization o ON r.organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"

Write-Host "  Unique constraints:"
Check-NoDuplicates "weekly_sangha_puja" "sakha_pk, puja_date"
Write-Host ""

# Organization re-parent approval (2 tables - existence only, no seed;
# Sakha re-parenting approval chain, owner rule 2026-10-30)
Write-Host "--- Organization re-parent approval ---" -ForegroundColor Cyan
Write-Host "  Tables (existence only - no seed data):"
Check-TableExists "organization_reparent_request"
Check-TableExists "organization_reparent_step"
Write-Host "  Key columns:"
Check-ColumnExists "organization_reparent_request" "sakha_organization_pk"
Check-ColumnExists "organization_reparent_request" "to_parent_organization_pk"
Check-ColumnExists "organization_reparent_request" "request_status"
Check-ColumnExists "organization_reparent_step" "organization_reparent_request_pk"
Check-ColumnExists "organization_reparent_step" "step_order"
Check-ColumnExists "organization_reparent_step" "assigned_body_master_pk"
Check-ColumnExists "organization_reparent_step" "step_status"
Write-Host "  FK integrity (no orphans - vacuously true until used):"
Check-FkIntegrity "organization_reparent_request -> organization (sakha)" "SELECT COUNT(*) FROM nss.organization_reparent_request r LEFT JOIN nss.organization o ON r.sakha_organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"
Check-FkIntegrity "organization_reparent_request -> organization (to parent)" "SELECT COUNT(*) FROM nss.organization_reparent_request r LEFT JOIN nss.organization o ON r.to_parent_organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"
Check-FkIntegrity "organization_reparent_step -> organization_reparent_request" "SELECT COUNT(*) FROM nss.organization_reparent_step s LEFT JOIN nss.organization_reparent_request r ON s.organization_reparent_request_pk = r.organization_reparent_request_pk WHERE r.organization_reparent_request_pk IS NULL;"
Check-FkIntegrity "organization_reparent_step: step_role CHECK allows SOURCE_PARENT_PRESIDENT (patch 09 ran)" "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'nss.organization_reparent_step'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%SOURCE_PARENT_PRESIDENT%') THEN 0 ELSE 1 END;"
Check-FkIntegrity "organization_reparent_step -> body_master" "SELECT COUNT(*) FROM nss.organization_reparent_step s LEFT JOIN nss.body_master b ON s.assigned_body_master_pk = b.body_master_pk WHERE b.body_master_pk IS NULL;"
Write-Host ""

# Assets & Property (7 tables, Module #22, Tier 6 - existence only, runtime data;
# reference data delivered by the idempotent patches)
Write-Host "--- Assets & Property ---" -ForegroundColor Cyan
Write-Host "  Tables (existence only - runtime data, no seed rows):"
Check-TableExists "property"
Check-TableExists "asset"
Check-TableExists "custodianship"
Check-TableExists "property_statutory_record"
Check-TableExists "maintenance_record"
Check-TableExists "property_document"
Check-TableExists "asset_document"

Write-Host "  Key columns:"
Check-ColumnExists "property" "property_id"
Check-ColumnExists "property" "property_type_master_data_pk"
Check-ColumnExists "property" "status"
Check-ColumnExists "asset" "asset_id"
Check-ColumnExists "asset" "asset_type_master_data_pk"
Check-ColumnExists "asset" "status"
Check-ColumnExists "property" "belongs_to_organization_pk"
Check-ColumnExists "asset" "belongs_to_organization_pk"
Check-ColumnExists "property" "acquisition_method_master_data_pk"
Check-ColumnExists "asset" "acquisition_method_master_data_pk"
Check-ColumnExists "custodianship" "custodian_organization_pk"
Check-ColumnExists "custodianship" "effective_from"
Check-ColumnExists "custodianship" "end_reason_master_data_pk"
Check-ColumnExists "property_statutory_record" "obligation_type_master_data_pk"
Check-ColumnExists "maintenance_record" "maintenance_type_master_data_pk"
Check-ColumnExists "property_document" "document_master_pk"
Check-ColumnExists "asset_document" "document_master_pk"

Write-Host "  Patch-delivered objects, FK integrity and invariants (no orphans / violations - vacuously true until used):"
Check-FkIntegrity "property -> master_data (property type)" "SELECT COUNT(*) FROM nss.property p LEFT JOIN nss.master_data md ON p.property_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "asset -> master_data (asset type)" "SELECT COUNT(*) FROM nss.asset a LEFT JOIN nss.master_data md ON a.asset_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "custodianship -> property" "SELECT COUNT(*) FROM nss.custodianship c LEFT JOIN nss.property p ON c.property_pk = p.property_pk WHERE c.property_pk IS NOT NULL AND p.property_pk IS NULL;"
Check-FkIntegrity "custodianship -> asset" "SELECT COUNT(*) FROM nss.custodianship c LEFT JOIN nss.asset a ON c.asset_pk = a.asset_pk WHERE c.asset_pk IS NOT NULL AND a.asset_pk IS NULL;"
Check-FkIntegrity "custodianship -> organization (custodian)" "SELECT COUNT(*) FROM nss.custodianship c LEFT JOIN nss.organization o ON c.custodian_organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"
Check-FkIntegrity "custodianship: property XOR asset (AP-019)" "SELECT COUNT(*) FROM nss.custodianship WHERE (property_pk IS NULL) = (asset_pk IS NULL);"
Check-FkIntegrity "custodianship: at most one ACTIVE per property/asset (AP-017)" "SELECT COUNT(*) FROM (SELECT COALESCE(property_pk, asset_pk) FROM nss.custodianship WHERE status = 'ACTIVE' AND is_active = TRUE GROUP BY 1 HAVING COUNT(*) > 1) d;"
Check-FkIntegrity "property_statutory_record -> property" "SELECT COUNT(*) FROM nss.property_statutory_record r LEFT JOIN nss.property p ON r.property_pk = p.property_pk WHERE p.property_pk IS NULL;"
Check-FkIntegrity "maintenance_record: property XOR asset" "SELECT COUNT(*) FROM nss.maintenance_record WHERE (property_pk IS NULL) = (asset_pk IS NULL);"
Check-FkIntegrity "property_document -> document_master" "SELECT COUNT(*) FROM nss.property_document d LEFT JOIN nss.document_master dm ON d.document_master_pk = dm.document_master_pk WHERE dm.document_master_pk IS NULL;"
Check-FkIntegrity "asset_document -> document_master" "SELECT COUNT(*) FROM nss.asset_document d LEFT JOIN nss.document_master dm ON d.document_master_pk = dm.document_master_pk WHERE dm.document_master_pk IS NULL;"
Check-FkIntegrity "Assets & Property guard triggers present (08_assets_property_guards.sql ran)" "SELECT 3 - COUNT(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_property_guard', 'trg_asset_guard', 'trg_custodianship_guard');"
Check-FkIntegrity "Assets & Property id sequences PROPERTY + ASSET present (reference-data patch ran)" "SELECT 2 - COUNT(*) FROM nss.id_sequence_master WHERE sequence_code IN ('PROPERTY', 'ASSET');"
Check-FkIntegrity "Assets & Property master categories seeded with values (reference-data patch ran)" "SELECT 7 - COUNT(DISTINCT mc.category_code) FROM nss.master_category mc JOIN nss.master_data md ON md.master_category_pk = mc.master_category_pk WHERE mc.category_code IN ('PROPERTY_TYPE', 'ASSET_TYPE', 'CUSTODIANSHIP_END_REASON', 'STATUTORY_OBLIGATION_TYPE', 'MAINTENANCE_TYPE', 'ASSET_PROPERTY_DOCUMENT_RELATIONSHIP', 'ACQUISITION_METHOD');"
Check-FkIntegrity "ASSET_MANAGE actively granted to >= 4 roles (permissions patch ran; owner decision 2026-11-02: ADMIN/KENDRA/SAKHA/PATHA_CHAKRA only)" "SELECT GREATEST(4 - COUNT(*), 0) FROM nss.role_permission rp JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk WHERE pm.permission_code = 'ASSET_MANAGE' AND rp.is_active = TRUE;"
Check-FkIntegrity "ASSET_VIEW actively granted to >= 8 roles (permissions patch ran)" "SELECT GREATEST(8 - COUNT(*), 0) FROM nss.role_permission rp JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk WHERE pm.permission_code = 'ASSET_VIEW' AND rp.is_active = TRUE;"
Check-FkIntegrity "Assets & Property: the 4 withdrawn grants are NOT active (Mahila VIEW+MANAGE, Anchalika/Zilla MANAGE - 06_assets_property_permissions_revoke_patch.sql ran)" "SELECT COUNT(*) FROM nss.role_permission rp JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk WHERE rp.is_active = TRUE AND ((rm.role_code = 'NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN' AND pm.permission_code IN ('ASSET_VIEW', 'ASSET_MANAGE')) OR (rm.role_code IN ('NSS_ERP_ANCHALIKA_ADMIN', 'NSS_ERP_ZILLA_ADMIN') AND pm.permission_code = 'ASSET_MANAGE'));"
Check-FkIntegrity "PERSON_VIEW_SENSITIVE is NOT active for NSS_ERP_AUDITOR (07_person_view_sensitive_auditor_revoke_patch.sql ran, GDR-011)" "SELECT COUNT(*) FROM nss.role_permission rp JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk WHERE rp.is_active = TRUE AND rm.role_code = 'NSS_ERP_AUDITOR' AND pm.permission_code = 'PERSON_VIEW_SENSITIVE';"
Check-FkIntegrity "PERSON_VIEW_SENSITIVE active for NSS_ERP_ADMIN" "SELECT CASE WHEN EXISTS (SELECT 1 FROM nss.role_permission rp JOIN nss.role_master rm ON rm.role_master_pk = rp.role_master_pk JOIN nss.permission_master pm ON pm.permission_master_pk = rp.permission_master_pk WHERE rp.is_active = TRUE AND rm.role_code = 'NSS_ERP_ADMIN' AND pm.permission_code = 'PERSON_VIEW_SENSITIVE') THEN 0 ELSE 1 END;"
Check-FkIntegrity "property -> organization (belongs-to)" "SELECT COUNT(*) FROM nss.property p LEFT JOIN nss.organization o ON p.belongs_to_organization_pk = o.organization_pk WHERE p.belongs_to_organization_pk IS NOT NULL AND o.organization_pk IS NULL;"
Check-FkIntegrity "asset -> organization (belongs-to)" "SELECT COUNT(*) FROM nss.asset a LEFT JOIN nss.organization o ON a.belongs_to_organization_pk = o.organization_pk WHERE a.belongs_to_organization_pk IS NOT NULL AND o.organization_pk IS NULL;"
Check-FkIntegrity "Assets & Property: fn_is_asset_custodian_org_type() + custodian-eligibility trigger present (09_asset_custodian_org_type_function.sql ran)" "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'nss' AND p.proname = 'fn_is_asset_custodian_org_type') AND EXISTS (SELECT 1 FROM pg_trigger WHERE NOT tgisinternal AND tgname = 'trg_custodianship_custodian_guard' AND tgrelid = 'nss.custodianship'::regclass) THEN 0 ELSE 1 END;"
Check-FkIntegrity "property -> master_data (acquisition method)" "SELECT COUNT(*) FROM nss.property p LEFT JOIN nss.master_data md ON p.acquisition_method_master_data_pk = md.master_data_pk WHERE p.acquisition_method_master_data_pk IS NOT NULL AND md.master_data_pk IS NULL;"
Check-FkIntegrity "asset -> master_data (acquisition method)" "SELECT COUNT(*) FROM nss.asset a LEFT JOIN nss.master_data md ON a.acquisition_method_master_data_pk = md.master_data_pk WHERE a.acquisition_method_master_data_pk IS NOT NULL AND md.master_data_pk IS NULL;"
Check-FkIntegrity "ACQUISITION_METHOD master category seeded with values (reference-data patch ran)" "SELECT CASE WHEN EXISTS (SELECT 1 FROM nss.master_category mc JOIN nss.master_data md ON md.master_category_pk = mc.master_category_pk WHERE mc.category_code = 'ACQUISITION_METHOD') THEN 0 ELSE 1 END;"
Check-FkIntegrity "CUSTODIANSHIP_END_REASON has DISPOSED + RETIRED (reference-data patch ran)" "SELECT 2 - COUNT(*) FROM nss.master_data md JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk WHERE mc.category_code = 'CUSTODIANSHIP_END_REASON' AND md.value_code IN ('DISPOSED', 'RETIRED');"
Check-FkIntegrity "no ACTIVE custodianship on a DISPOSED property / RETIRED asset (12_assets_property_terminal_custody_patch.sql ran; GDR-010 §2F)" "SELECT (SELECT COUNT(*) FROM nss.custodianship c JOIN nss.property p ON p.property_pk = c.property_pk WHERE p.status = 'DISPOSED' AND c.status = 'ACTIVE' AND c.is_active = TRUE) + (SELECT COUNT(*) FROM nss.custodianship c JOIN nss.asset a ON a.asset_pk = c.asset_pk WHERE a.status = 'RETIRED' AND c.status = 'ACTIVE' AND c.is_active = TRUE);"
Check-FkIntegrity "Assets & Property: terminal-record custodianship insert guard present (08_assets_property_guards.sql ran)" "SELECT 1 - COUNT(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname = 'trg_custodianship_terminal_guard' AND tgrelid = 'nss.custodianship'::regclass;"
Check-WarnCount "Assets & Property: existing custodianships held by a NON-eligible (conceptual/wing/Advisory Board) organization (GDR-010 §2C, not auto-repaired)" "SELECT COUNT(*) FROM nss.custodianship c JOIN nss.organization o ON o.organization_pk = c.custodian_organization_pk JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk WHERE c.is_active = TRUE AND NOT nss.fn_is_asset_custodian_org_type(md.value_code);"

Write-Host "  Unique constraints:"
Check-NoDuplicates "property" "property_id"
Check-NoDuplicates "asset" "asset_id"
Write-Host ""

Write-Host "Module 11: Live refresh" -ForegroundColor Cyan
Check-TableExists "live_change_marker"
Check-ColumnExists "live_change_marker" "table_name"
Check-ColumnExists "live_change_marker" "change_seq"
Check-FkIntegrity "live_change_marker: change-marker triggers present (02_live_change_triggers.sql ran)" "SELECT 1 - LEAST(1, COUNT(*)) FROM pg_trigger WHERE NOT tgisinternal AND tgname = 'trg_live_change_marker';"
Check-WarnCount "live_change_marker: watched tables whose trigger has no marker row (re-run the build)" "SELECT COUNT(*) FROM pg_trigger g JOIN pg_class c ON c.oid = g.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'nss' AND g.tgname = 'trg_live_change_marker' AND NOT g.tgisinternal AND NOT EXISTS (SELECT 1 FROM nss.live_change_marker m WHERE m.table_name = c.relname);"
Check-FkIntegrity "live_change_marker is NOT audited (excluded in 15_audit_trigger.sql)" "SELECT COUNT(*) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid = 'nss.live_change_marker'::regclass AND tgname LIKE 'trg_audit_%';"
Write-Host ""

# Audit-actor foreign keys (Phase 13c, owner decision 2026-11-04)
Write-Host "--- Audit-actor FKs ---" -ForegroundColor Cyan
Check-WarnCount "audit actor columns (*_by_sangha_sevi_pk) WITHOUT a foreign key to sangha_sevi (re-run the build: Phase 13c, ddl/13_audit_actor_fk)" "SELECT COUNT(*) FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'nss' AND c.relkind IN ('r','p') AND a.attnum > 0 AND NOT a.attisdropped AND a.attname LIKE '%\_by\_sangha\_sevi\_pk' AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'f' AND k.confrelid = 'nss.sangha_sevi'::regclass AND k.conkey = ARRAY[a.attnum]::smallint[]);"
Check-WarnCount "audit actor FKs still NOT VALID (dangling actor values exist; find them with the diagnostic SELECT in database/scripts/README.md, fix, re-run the build)" "SELECT COUNT(*) FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.conkey[1] WHERE n.nspname = 'nss' AND k.contype = 'f' AND k.confrelid = 'nss.sangha_sevi'::regclass AND NOT k.convalidated AND a.attname LIKE '%\_by\_sangha\_sevi\_pk';"
Write-Host ""
# Finance (7 tables, Tier 12 - existence only; initial Financial Year, PAYMENT_METHOD master data and
# FINANCE_* permissions come from the idempotent patches)
Write-Host "--- Finance ---" -ForegroundColor Cyan
Write-Host "  Tables (existence only):"
Check-TableExists "financial_year"
Check-TableExists "financial_scope"
Check-TableExists "fund_master"
Check-TableExists "financial_transaction"
Check-TableExists "financial_receipt"
Check-TableExists "financial_payment"
Check-TableExists "financial_transfer"
Check-TableExists "financial_account"
Check-TableExists "finance_head"
Check-TableExists "upi_payment_request"
Check-TableExists "finance_gateway_event"

Check-ColumnExists "financial_scope" "scope_code"
Check-ColumnExists "financial_scope" "organization_pk"
Check-ColumnExists "fund_master" "financial_scope_pk"
Check-ColumnExists "financial_transaction" "financial_year_pk"
Check-ColumnExists "financial_transaction" "financial_scope_pk"
Check-ColumnExists "financial_transaction" "amount"
Check-ColumnExists "financial_receipt" "payment_method_master_data_pk"
Check-ColumnExists "financial_payment" "payment_method_master_data_pk"
Check-ColumnExists "financial_transfer" "source_scope_pk"
Check-ColumnExists "financial_transfer" "destination_scope_pk"
Check-ColumnExists "financial_account" "organization_pk"
Check-ColumnExists "financial_account" "upi_vpa"
Check-ColumnExists "financial_account" "gateway_credential_ref"
Check-ColumnExists "finance_head" "organization_pk"
Check-ColumnExists "finance_head" "head_code"
Check-ColumnExists "finance_head" "direction"
Check-ColumnExists "finance_head" "collection_account_pk"
Check-ColumnExists "financial_transaction" "finance_head_pk"
Check-ColumnExists "upi_payment_request" "financial_account_pk"
Check-ColumnExists "upi_payment_request" "provider_order_id"
Check-ColumnExists "finance_gateway_event" "event_id"
Check-ColumnExists "finance_gateway_event" "signature_valid"

Write-Host "  FK integrity (no orphans - vacuously true until used):"
Check-FkIntegrity "financial_scope -> financial_year" "SELECT COUNT(*) FROM nss.financial_scope c LEFT JOIN nss.financial_year p ON c.financial_year_pk = p.financial_year_pk WHERE p.financial_year_pk IS NULL;"
Check-FkIntegrity "fund_master -> financial_scope" "SELECT COUNT(*) FROM nss.fund_master c LEFT JOIN nss.financial_scope p ON c.financial_scope_pk = p.financial_scope_pk WHERE p.financial_scope_pk IS NULL;"
Check-FkIntegrity "financial_transaction -> financial_year" "SELECT COUNT(*) FROM nss.financial_transaction c LEFT JOIN nss.financial_year p ON c.financial_year_pk = p.financial_year_pk WHERE p.financial_year_pk IS NULL;"
Check-FkIntegrity "financial_transaction -> financial_scope" "SELECT COUNT(*) FROM nss.financial_transaction c LEFT JOIN nss.financial_scope p ON c.financial_scope_pk = p.financial_scope_pk WHERE p.financial_scope_pk IS NULL;"
Check-FkIntegrity "financial_receipt -> financial_transaction" "SELECT COUNT(*) FROM nss.financial_receipt c LEFT JOIN nss.financial_transaction p ON c.financial_transaction_pk = p.financial_transaction_pk WHERE p.financial_transaction_pk IS NULL;"
Check-FkIntegrity "financial_payment -> financial_transaction" "SELECT COUNT(*) FROM nss.financial_payment c LEFT JOIN nss.financial_transaction p ON c.financial_transaction_pk = p.financial_transaction_pk WHERE p.financial_transaction_pk IS NULL;"
Check-FkIntegrity "financial_transfer -> financial_scope (source)" "SELECT COUNT(*) FROM nss.financial_transfer c LEFT JOIN nss.financial_scope p ON c.source_scope_pk = p.financial_scope_pk WHERE p.financial_scope_pk IS NULL;"
Check-FkIntegrity "financial_transfer -> financial_scope (destination)" "SELECT COUNT(*) FROM nss.financial_transfer c LEFT JOIN nss.financial_scope p ON c.destination_scope_pk = p.financial_scope_pk WHERE p.financial_scope_pk IS NULL;"
Check-FkIntegrity "financial_account -> organization" "SELECT COUNT(*) FROM nss.financial_account c LEFT JOIN nss.organization p ON c.organization_pk = p.organization_pk WHERE c.organization_pk IS NOT NULL AND p.organization_pk IS NULL;"
Check-FkIntegrity "finance_head -> financial_account (collection)" "SELECT COUNT(*) FROM nss.finance_head c LEFT JOIN nss.financial_account p ON c.collection_account_pk = p.financial_account_pk WHERE c.collection_account_pk IS NOT NULL AND p.financial_account_pk IS NULL;"
Check-FkIntegrity "financial_transaction -> finance_head" "SELECT COUNT(*) FROM nss.financial_transaction c LEFT JOIN nss.finance_head p ON c.finance_head_pk = p.finance_head_pk WHERE c.finance_head_pk IS NOT NULL AND p.finance_head_pk IS NULL;"
Check-FkIntegrity "upi_payment_request -> financial_account" "SELECT COUNT(*) FROM nss.upi_payment_request c LEFT JOIN nss.financial_account p ON c.financial_account_pk = p.financial_account_pk WHERE c.financial_account_pk IS NOT NULL AND p.financial_account_pk IS NULL;"
Check-FkIntegrity "upi_payment_request -> finance_head" "SELECT COUNT(*) FROM nss.upi_payment_request c LEFT JOIN nss.finance_head p ON c.finance_head_pk = p.finance_head_pk WHERE c.finance_head_pk IS NOT NULL AND p.finance_head_pk IS NULL;"
Check-FkIntegrity "finance_gateway_event -> upi_payment_request" "SELECT COUNT(*) FROM nss.finance_gateway_event c LEFT JOIN nss.upi_payment_request p ON c.upi_payment_request_pk = p.upi_payment_request_pk WHERE c.upi_payment_request_pk IS NOT NULL AND p.upi_payment_request_pk IS NULL;"
Check-FkIntegrity "every transaction has a finance head (heads structure patch ran)" "SELECT COUNT(*) FROM nss.financial_transaction WHERE finance_head_pk IS NULL;"
Check-FkIntegrity "no UPI-enabled head without a collection scope and account" "SELECT COUNT(*) FROM nss.finance_head WHERE allow_upi AND (collection_scope_pk IS NULL OR collection_account_pk IS NULL);"
Check-FkIntegrity "no PAID UPI request left unposted without a review reason" "SELECT COUNT(*) FROM nss.upi_payment_request WHERE status = 'PAID' AND financial_transaction_pk IS NULL AND review_reason IS NULL;"
Check-FkIntegrity "Kendra template finance heads present (head templates patch ran)" "SELECT CASE WHEN (SELECT COUNT(*) FROM nss.finance_head WHERE organization_pk IS NULL) >= 12 THEN 0 ELSE 1 END;"
Check-FkIntegrity "PAYMENT_METHOD master_data present (reference-data patch ran)" "SELECT CASE WHEN EXISTS (SELECT 1 FROM nss.master_data md JOIN nss.master_category mc ON mc.master_category_pk = md.master_category_pk WHERE mc.category_code = 'PAYMENT_METHOD' AND md.value_code = 'UPI') THEN 0 ELSE 1 END;"
Check-FkIntegrity "FINANCE_* permissions present (permissions patch ran)" "SELECT CASE WHEN (SELECT COUNT(*) FROM nss.permission_master WHERE permission_code LIKE 'FINANCE\_%') = 3 THEN 0 ELSE 1 END;"

Write-Host "  Seed (initial Financial Year from the reference-data patch):"
Check-RowCount "financial_year" 1
Write-Host "  Unique constraints:"
Check-NoDuplicates "financial_transaction" "transaction_reference"
Check-NoDuplicates "financial_year" "year_code"
Write-Host ""


# Summary
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  VALIDATION RESULTS" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Passed:   $pass_count" -ForegroundColor Green
Write-Host "  Warnings: $warn_count" -ForegroundColor Yellow
Write-Host "  Failed:   $fail_count" -ForegroundColor Red
Write-Host ""

if ($fail_count -eq 0 -and $warn_count -eq 0) {
    Write-Host "  All validations PASSED" -ForegroundColor Green
    exit 0
} elseif ($fail_count -eq 0) {
    Write-Host "  Passed with warnings ($warn_count)" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "  Validation FAILED ($fail_count failures)" -ForegroundColor Red
    exit 1
}
