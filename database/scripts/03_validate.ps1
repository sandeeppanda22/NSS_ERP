# =====================================================
# NSS ERP — Post-Build Validation (PowerShell)
# =====================================================
#
# Validates that all implemented modules were built
# correctly. Does NOT execute any DDL or seed scripts -
# run 02_build.ps1 first.
#
# Authority: SOL-ARCH-010, SOL-ARCH-011
# Version: 1.2 — add Auth (5 tables), Admin (2 tables),
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
Check-RowCount "permission_master" 28
Check-RowCount "role_permission" 155

Write-Host "  Unique constraints:"
Check-NoDuplicates "role_master" "role_code"

Write-Host "  FK integrity:"
Check-FkIntegrity "role_permission -> role_master" "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.role_master rm ON rp.role_master_pk = rm.role_master_pk WHERE rm.role_master_pk IS NULL;"
Check-FkIntegrity "role_permission -> permission_master" "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.permission_master pm ON rp.permission_master_pk = pm.permission_master_pk WHERE pm.permission_master_pk IS NULL;"
Write-Host ""

# Foundation
Write-Host "--- Foundation ---" -ForegroundColor Cyan
Write-Host "  Tables:"
$foundationTables = @("master_category","system_setting","id_sequence_master","country","document_master","field_change_log","master_data","state","district","city_village","postal_code")
foreach ($t in $foundationTables) { Check-TableExists $t }

Write-Host "  Row counts:"
Check-RowCount "master_category" 13
Check-RowCount "master_data" 89
Check-RowCount "id_sequence_master" 14
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
Check-RowCount "organization" 178

Write-Host "  Unique constraints:"
Check-NoDuplicates "organization" "organization_code"

Write-Host "  FK integrity:"
Check-FkIntegrity "organization -> master_data (type)" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.master_data md ON o.organization_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "organization -> master_data (status)" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.master_data md ON o.status_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "organization -> country" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.country c ON o.country_pk = c.country_pk WHERE o.country_pk IS NOT NULL AND c.country_pk IS NULL;"
Check-FkIntegrity "organization -> city_village" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.city_village cv ON o.city_village_pk = cv.city_village_pk WHERE o.city_village_pk IS NOT NULL AND cv.city_village_pk IS NULL;"
Check-FkIntegrity "organization -> postal_code" "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.postal_code pc ON o.postal_code_pk = pc.postal_code_pk WHERE o.postal_code_pk IS NOT NULL AND pc.postal_code_pk IS NULL;"
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
Check-ColumnExists "election_vote" "voter_person_pk"
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
Check-FkIntegrity "weekly_sangha_puja_attendance -> weekly_sangha_puja" "SELECT COUNT(*) FROM nss.weekly_sangha_puja_attendance a LEFT JOIN nss.weekly_sangha_puja w ON a.weekly_sangha_puja_pk = w.weekly_sangha_puja_pk WHERE w.weekly_sangha_puja_pk IS NULL;"
Check-FkIntegrity "weekly_sangha_puja_attendance -> sangha_sevi" "SELECT COUNT(*) FROM nss.weekly_sangha_puja_attendance a LEFT JOIN nss.sangha_sevi s ON a.sangha_sevi_pk = s.sangha_sevi_pk WHERE s.sangha_sevi_pk IS NULL;"
Check-FkIntegrity "weekly_sangha_puja_attendance -> master_data (status)" "SELECT COUNT(*) FROM nss.weekly_sangha_puja_attendance a LEFT JOIN nss.master_data md ON a.attendance_status_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
Check-FkIntegrity "attendance_exception -> sangha_sevi" "SELECT COUNT(*) FROM nss.attendance_exception e LEFT JOIN nss.sangha_sevi s ON e.sangha_sevi_pk = s.sangha_sevi_pk WHERE s.sangha_sevi_pk IS NULL;"
Check-FkIntegrity "attendance_review -> sangha_sevi" "SELECT COUNT(*) FROM nss.attendance_review r LEFT JOIN nss.sangha_sevi s ON r.sangha_sevi_pk = s.sangha_sevi_pk WHERE s.sangha_sevi_pk IS NULL;"
Check-FkIntegrity "attendance_review -> organization" "SELECT COUNT(*) FROM nss.attendance_review r LEFT JOIN nss.organization o ON r.organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"

Write-Host "  Unique constraints:"
Check-NoDuplicates "weekly_sangha_puja" "sakha_pk, puja_date"
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
