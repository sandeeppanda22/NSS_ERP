# =====================================================
# NSS ERP — Full Database Build (PowerShell)
# =====================================================
#
# Executes all DDL and seed scripts in the frozen
# SOL-ARCH-011 phase order for currently implemented
# modules only.
#
# Authority: SOL-ARCH-010, SOL-ARCH-011
# Version: 2.6  - reinstate post_office (SOL-ARCH-010 Amendment, 2026-10-03:
#          Member-Assisted Geographic Entry). A PIN can hold many post
#          offices; post_office is one of the four member-writable
#          geographic levels. Supersedes the v2.5 retirement note below.
# Version: 2.5  - drop post_office (retired 2026-10-02: Simplified Geography
#          Model - district now lives on city_village, not a separate
#          office-grain table)
#
# Usage:
#   .\database\scripts\02_build.ps1 [-DbName nss_erp] [-DbUser nss_db_owner] [-DbHost localhost] [-DbPort 5432]
#
# Prerequisites:
#   - PostgreSQL running and accessible
#   - Database and roles created (see 00_create_database.sql)
#   - Extensions installed (see 01_extensions.sql)
#   - Role passwords set and api/.env generated (see 06_setup_env.sh)
#   - Run from the repository root directory
#
# Implemented phases:
#   Phase 0  - Bootstrap RBAC (3 tables + seed)
#   Phase 1  - Foundation DDL (14 tables: 02-13 + 16-17; system_event_log is
#              created separately in Phase 14)
#   Phase 2  - Foundation seed data (incl. ORGANIZATION_TYPE
#              category and unified STATUS category in master_data)
#   Phase 3  - Organization DDL (1 table)
#   Phase 4  - Organization seed data
#   Phase 5  - Person DDL (2 tables)
#   Phase 6  - Family DDL (6 tables)
#   Phase 7  - Membership DDL (14 tables)
#   Phase 7b - Deferred Foundation audit FKs (16_foundation_audit_fk.sql)
#   Phase 8  - Tier 4 Verification Seed Data (removed - no demo data)
#   Phase 9  - Grant nss_db_backend read-only access
#   Phase 10 - Authentication DDL (5 tables: user_account,
#              password_history, registration_claim, password_reset_token,
#              user_session)
#   Phase 11 - Administration DDL (2 tables)
#   Phase 11b- Governance DDL (10 tables: body_type_master,
#              position_master, body_master, body_member_assignment,
#              acting_position_assignment, election, election_nomination,
#              election_vote, election_result, election_vote_participation)
#              + ballot-immutability triggers (11_governance_immutability.sql)
#              + seat-count triggers (12_governance_seat_limits.sql)
#   Phase 11c- Governance Seed Data (body_type_master, position_master, body_master)
#   Phase 11d- Correspondence DDL (5 tables: correspondence,
#              correspondence_document, correspondence_finance_reference,
#              correspondence_sequence_counter, correspondence_approval_step -
#              Tier 6, Administration-owned; moved from Tier 5,
#              owner-confirmed 2026-10-16)
#   Phase 11e- Attendance DDL (4 tables: weekly_sangha_puja,
#              weekly_sangha_puja_attendance, attendance_exception,
#              attendance_review - Tier 6, owner-confirmed 2026-10-27)
#   Phase 12 - Grant nss_db_writer write access (Tier 5)
#   Phase 13 - Admin bootstrap seed (NSS Admin superuser)
#   Phase 13b- Geo attribution backfill (city_village/postal_code/
#              post_office submitted_by_person_pk -> P1, for rows the
#              Phase 2 bulk seed left unattributed; must run after
#              Phase 13 since P1's person_pk doesn't exist before it)
#   Phase 14 - Audit DDL (system_event_log table + DB trigger)
#   Phase 15 - (OPTIONAL, local dev only) demo/test seed, run only when
#              $env:RUN_DEMO_SEED is truthy and database\seed\demo\nss_demo_seed.sql
#              exists (gitignored; never on Render)
#
# NOT executed:
#   - database/seed/03_person/ (no seed data - Person data lives in
#     Foundation master_data; the superseded 01_person_master_tables.sql
#     DDL/seed were removed 2026-10-01, dead code with zero references)
#   - Pass 2 audit-actor FK constraints (deferred)
# =====================================================

param(
    [string]$DbName = "nss_erp",
    [string]$DbUser = "nss_db_owner",
    [string]$DbHost = "localhost",
    [int]$DbPort = 5432
)

$ErrorActionPreference = "Stop"

# Prompt for password once; export so all psql calls reuse it.
if (-not $env:PGPASSWORD) {
    $securePass = Read-Host "Password for ${DbUser}@${DbHost}:${DbPort}/${DbName}" -AsSecureString
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePass)
    )
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..\..").Path
$DdlBase = "$RepoRoot\database\ddl"
$SeedBase = "$RepoRoot\database\seed"

# -------------------------------------------------
# Install Python dependencies
# -------------------------------------------------
Write-Host "=== Installing Python dependencies ===" -ForegroundColor Cyan
& python3 -m pip install -r "$RepoRoot\requirements.txt"
Write-Host ""

$total = 0
$failed = 0
$skipped = 0

function Invoke-Sql {
    param([string]$Label, [string]$File)
    $script:total++
    $output = & psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -f $File 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK]   $Label" -ForegroundColor Green
    } else {
        # Check for idempotent-safe errors (table/index already exists,
        # duplicate seed rows).  These are expected on re-runs and should
        # not abort the build.
        $outputText = ($output | Out-String)
        if ($outputText -match 'already exists|duplicate key value violates unique constraint') {
            Write-Host "  [SKIP] $Label  (already exists)" -ForegroundColor Yellow
            $script:skipped++
        } else {
            Write-Host "  [FAIL] $Label" -ForegroundColor Red
            Write-Host "  Error:" -ForegroundColor Red
            $output | ForEach-Object { Write-Host "         $_" }
            $script:failed++
            Write-Host "  Aborting - fix the above error before continuing." -ForegroundColor Red
            exit 1
        }
    }
}

# -- Existence-gated table creation / seeding ----------------
# Same deterministic model as 02_build.sh and render_build.sh:
# "only genuinely new tables are ever created or seeded; a table
# that already exists is never dropped, re-created, or re-seeded,
# so its local data is never touched."
#
# $PreExisting holds the tables that were already present at the
# START of this run. A pre-existing table has its DDL AND its seed
# skipped. A table absent at start is created, then seeded once.
$PreExisting = @{}

# Deterministic catalog check (no error-string guessing).
# to_regclass returns the OID (non-NULL) iff the relation exists.
function Test-TableExists {
    param([string]$Table)
    $res = & psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -tA -c "SELECT to_regclass('nss.$Table') IS NOT NULL;" 2>$null
    return ((($res | Out-String).Trim()) -eq "t")
}

# Create a table only if it does not already exist.
#   Invoke-Ddl <label> <table_name> <ddl_file>
function Invoke-Ddl {
    param([string]$Label, [string]$Table, [string]$File)
    Write-Host "  [CHECK] $Label  (nss.$Table) ..." -ForegroundColor Cyan
    if (Test-TableExists $Table) {
        $script:PreExisting[$Table] = $true
        $script:total++
        $script:skipped++
        Write-Host "  [EXISTS] $Label  (nss.$Table already present - DDL + seed skipped, local data preserved)" -ForegroundColor Yellow
        return
    }
    Write-Host "  [NEW]  $Label  (nss.$Table absent - creating)" -ForegroundColor Green
    Invoke-Sql $Label $File
}

# Seed a table ONLY if it was newly created in this run.
#   Invoke-Seed <label> <target_table> <seed_file>
function Invoke-Seed {
    param([string]$Label, [string]$Table, [string]$File)
    if ($script:PreExisting.ContainsKey($Table)) {
        $script:total++
        $script:skipped++
        Write-Host "  [SKIP] $Label  (nss.$Table pre-existed - seed skipped, local data preserved)" -ForegroundColor Yellow
        return
    }
    Invoke-Sql $Label $File
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  NSS ERP - Full Database Build" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Database: $DbName"
Write-Host "  User:     $DbUser"
Write-Host "  Host:     ${DbHost}:${DbPort}"
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Phase 0: Bootstrap RBAC
Write-Host "[Phase 0] Bootstrap RBAC - DDL" -ForegroundColor Cyan
Invoke-Ddl "role_master"       "role_master"       "$DdlBase\00_bootstrap\01_role_master.sql"
Invoke-Ddl "permission_master" "permission_master" "$DdlBase\00_bootstrap\02_permission_master.sql"
Invoke-Ddl "role_permission"   "role_permission"   "$DdlBase\00_bootstrap\03_role_permission.sql"
Write-Host ""

Write-Host "[Phase 0] Bootstrap RBAC - Seed" -ForegroundColor Cyan
Invoke-Seed "permission_master (seed)" "permission_master" "$SeedBase\00_bootstrap\01_permission_master.sql"
Invoke-Seed "role_master (seed)"       "role_master"       "$SeedBase\00_bootstrap\02_role_master.sql"
Invoke-Seed "role_permission (seed)"   "role_permission"   "$SeedBase\00_bootstrap\03_role_permission.sql"
Write-Host ""

# Phase 1: Foundation DDL
# Note: festival_master/festival_calendar_date (16/17) are
#       file-numbered after system_event_log/audit_trigger
#       (14/15) but run here in Phase 1 so the Phase 14 audit
#       trigger (which enumerates pg_tables at execution time)
#       still attaches to them.
Write-Host "[Phase 1] Foundation - DDL (14 tables)" -ForegroundColor Cyan
$foundationDdl = @(
    @("master_category",              "02_master_category.sql"),
    @("system_setting",               "03_system_setting.sql"),
    @("id_sequence_master",           "04_id_sequence_master.sql"),
    @("country",                      "05_country.sql"),
    @("document_master",              "06_document_master.sql"),
    @("field_change_log",             "07_field_change_log.sql"),
    @("master_data",                  "08_master_data.sql"),
    @("state",                        "09_state.sql"),
    @("district",                     "10_district.sql"),
    @("postal_code",                  "12_postal_code.sql"),
    @("post_office",                  "13_post_office.sql"),
    @("city_village",                "11_city_village.sql"),
    @("festival_master",              "16_festival_master.sql"),
    @("festival_calendar_date",       "17_festival_calendar_date.sql")
)
foreach ($entry in $foundationDdl) {
    Invoke-Ddl $entry[0] $entry[0] "$DdlBase\01_foundation\$($entry[1])"
}
Write-Host ""

# Phase 2: Foundation Seed (includes ORGANIZATION_TYPE + unified STATUS in master_data)
Write-Host "[Phase 2] Foundation - Seed Data" -ForegroundColor Cyan
$foundationSeed = @(
    @("master_category (seed)",    "master_category",        "01_master_category.sql"),
    @("master_data (seed)",        "master_data",            "02_master_data.sql"),
    @("id_sequence_master (seed)", "id_sequence_master",     "03_id_sequence_master.sql"),
    @("country (seed)",            "country",                "04_country.sql"),
    @("state (seed)",              "state",                  "05_state.sql"),
    @("district (seed)",           "district",               "06_district.sql"),
    @("system_setting (seed)",     "system_setting",         "07_system_setting.sql"),
    @("postal_code (seed)",        "postal_code",            "08_postal_code.sql"),
    @("postal_code bulk (seed)",   "postal_code",            "08b_postal_code_bulk.sql"),
    @("post_office bulk (seed)",   "post_office",            "08c_post_office_bulk.sql"),
    @("festival_calendar (seed)",  "festival_calendar_date", "10_festival_calendar.sql"),
    @("city_village (seed)",       "city_village",           "11_city_village.sql"),
    @("city_village urban recovery (seed)", "city_village",  "11b_city_village_urban_recovery.sql")
)
foreach ($entry in $foundationSeed) {
    Invoke-Seed $entry[0] $entry[1] "$SeedBase\01_foundation\$($entry[2])"
}
Write-Host ""

# Phase 3: Organization DDL (1 table — type/status now in Foundation master_data)
Write-Host "[Phase 3] Organization - DDL (1 table + address-restriction trigger + Kumari/Sevak one-per-Sakha trigger)" -ForegroundColor Cyan
Invoke-Ddl "organization"               "organization" "$DdlBase\02_organization\03_organization.sql"
Invoke-Sql "organization_address_restriction_trigger" "$DdlBase\02_organization\04_organization_address_restriction_trigger.sql"
Invoke-Sql "organization_kumari_sevak_uniqueness_trigger" "$DdlBase\02_organization\05_organization_kumari_sevak_uniqueness_trigger.sql"
Write-Host ""

# Phase 4: Organization Seed
Write-Host "[Phase 4] Organization - Seed Data" -ForegroundColor Cyan
Invoke-Seed "organization (seed)"               "organization"       "$SeedBase\02_organization\03_organization.sql"
Invoke-Seed "sakha postal codes (seed)"         "postal_code"        "$SeedBase\01_foundation\09_sakha_postal_codes.sql"
Invoke-Seed "sakha branches (seed)"             "organization"       "$SeedBase\02_organization\05_sakha_branches.sql"
Invoke-Seed "id_sequence_master (org sync)"     "id_sequence_master" "$SeedBase\02_organization\06_id_sequence_org_sync.sql"
Write-Host ""

# Phase 5: Person DDL
# Note: the superseded 01_person_master_tables.sql DDL/seed
#       were removed 2026-10-01 - dead code, zero references.
#       gender/marital_status/address_type data lives in
#       Foundation master_data seed.
Write-Host "[Phase 5] Person - DDL (2 tables)" -ForegroundColor Cyan
Invoke-Ddl "person"         "person"         "$DdlBase\03_person\02_person.sql"
Invoke-Ddl "person_address" "person_address" "$DdlBase\03_person\03_person_address.sql"
Write-Host ""

# Phase 6: Family DDL (6 tables)
# Note: family_link stores only direct PARENT_OF/
#       SPOUSE_OF edges; all other relationship labels
#       are computed dynamically via BFS traversal.
Write-Host "[Phase 6] Family - DDL (6 tables + move-transition guard)" -ForegroundColor Cyan
Invoke-Ddl "family_group"              "family_group"              "$DdlBase\04_family\01_family_group.sql"
Invoke-Ddl "family_relationship"       "family_relationship"       "$DdlBase\04_family\02_family_relationship.sql"
Invoke-Ddl "family_head_history"       "family_head_history"       "$DdlBase\04_family\03_family_head_history.sql"
Invoke-Ddl "family_transition_history" "family_transition_history" "$DdlBase\04_family\04_family_transition_history.sql"
Invoke-Ddl "family_link"               "family_link"               "$DdlBase\04_family\05_family_link.sql"
Invoke-Ddl "family_admin"              "family_admin"              "$DdlBase\04_family\06_family_admin.sql"
Invoke-Sql "family_move_transition_guard" "$DdlBase\04_family\07_family_move_transition_guard.sql"
Write-Host ""

# Phase 7: Membership DDL (14 tables)
# Note: sangha_sevi must be created first - all
#       other membership tables depend on it.
Write-Host "[Phase 7] Membership - DDL (16 tables + Sakha-only trigger)" -ForegroundColor Cyan
Invoke-Ddl "sangha_sevi"                    "sangha_sevi"                    "$DdlBase\05_membership\01_sangha_sevi.sql"
Invoke-Ddl "membership_status_history"      "membership_status_history"      "$DdlBase\05_membership\02_membership_status_history.sql"
Invoke-Ddl "membership_renewal_request"     "membership_renewal_request"     "$DdlBase\05_membership\03_membership_renewal_request.sql"
Invoke-Ddl "membership_renewal_history"     "membership_renewal_history"     "$DdlBase\05_membership\04_membership_renewal_history.sql"
Invoke-Ddl "membership_transfer_history"    "membership_transfer_history"    "$DdlBase\05_membership\05_membership_transfer_history.sql"
Invoke-Ddl "membership_sakha_affiliation"   "membership_sakha_affiliation"   "$DdlBase\05_membership\06_membership_sakha_affiliation.sql"
Invoke-Ddl "membership_journey_event"       "membership_journey_event"       "$DdlBase\05_membership\07_membership_journey_event.sql"
Invoke-Ddl "probationary_member_review"     "probationary_member_review"     "$DdlBase\05_membership\08_probationary_member_review.sql"
Invoke-Ddl "parichaya_patra"                "parichaya_patra"                "$DdlBase\05_membership\09_parichaya_patra.sql"
Invoke-Ddl "parichaya_patra_history"        "parichaya_patra_history"        "$DdlBase\05_membership\10_parichaya_patra_history.sql"
Invoke-Ddl "anumati_patra"                  "anumati_patra"                  "$DdlBase\05_membership\11_anumati_patra.sql"
Invoke-Ddl "anumati_patra_history"          "anumati_patra_history"          "$DdlBase\05_membership\12_anumati_patra_history.sql"
Invoke-Ddl "darshak_attendance_registration" "darshak_attendance_registration" "$DdlBase\05_membership\13_darshak_attendance_registration.sql"
Invoke-Sql "sakha_only_membership_trigger"  "$DdlBase\05_membership\14_sakha_only_membership_trigger.sql"
Invoke-Ddl "credential_sequence_counter"    "credential_sequence_counter"    "$DdlBase\05_membership\15_credential_sequence_counter.sql"
Invoke-Ddl "sakha_local_number_counter"     "sakha_local_number_counter"     "$DdlBase\05_membership\17_sakha_local_number_counter.sql"
Invoke-Ddl "membership_change_request"      "membership_change_request"      "$DdlBase\05_membership\18_membership_change_request.sql"
Write-Host ""

# Phase 7b: Deferred Foundation Audit FKs
# Wires the real FK constraints on district/postal_code/
# post_office/city_village's submitted_by/reviewed_by
# columns to sangha_sevi, now that sangha_sevi exists.
Write-Host "[Phase 7b] Deferred Foundation Audit FKs" -ForegroundColor Cyan
Invoke-Sql "foundation_audit_fk" "$DdlBase\05_membership\16_foundation_audit_fk.sql"
Write-Host ""

# Phase 8: Tier 4 Verification Seed Data
# Order: Organization -> Person -> Family -> Membership
# Phase 8: (Tier 4 test seeds removed — no demo data)
Write-Host ""

# Phase 9: Grant nss_db_backend read-only access
Write-Host "[Phase 9] Grant nss_db_backend read-only access" -ForegroundColor Cyan
Invoke-Sql "grant_backend" "$ScriptDir\04_grant_backend.sql"
Write-Host ""

# -------------------------------------------------
# Phase 10: Authentication DDL (5 tables, Depths 3-4)
# user_account FK -> person (Depth 3)
# password_history FK -> user_account (Depth 4)
# registration_claim FK -> user_account, person, organization, master_data (Depth 5)
# password_reset_token FK -> user_account (Depth 4)
# user_session FK -> user_account (Depth 4)
# -------------------------------------------------
Write-Host "[Phase 10] Authentication - DDL (5 tables)" -ForegroundColor Cyan
Invoke-Ddl "user_account"           "user_account"         "$DdlBase\06_authentication\01_user_account.sql"
Invoke-Ddl "password_history"       "password_history"     "$DdlBase\06_authentication\02_password_history.sql"
Invoke-Ddl "registration_claim"     "registration_claim"   "$DdlBase\06_authentication\03_registration_claim.sql"
Invoke-Ddl "password_reset_token"   "password_reset_token" "$DdlBase\06_authentication\04_password_reset_token.sql"
Invoke-Ddl "user_session"           "user_session"         "$DdlBase\06_authentication\05_user_session.sql"
Write-Host ""

# -------------------------------------------------
# Phase 11: Administration DDL (2 tables, Depths 4-5)
# user_role FK -> user_account + role_master (Depth 4)
# admin_scope FK -> user_role + organization (Depth 5)
# -------------------------------------------------
Write-Host "[Phase 11] Administration - DDL (2 tables)" -ForegroundColor Cyan
Invoke-Ddl "user_role"    "user_role"   "$DdlBase\07_administration\01_user_role.sql"
Invoke-Ddl "admin_scope"  "admin_scope" "$DdlBase\07_administration\02_admin_scope.sql"
Write-Host ""

# -------------------------------------------------
# Phase 11b: Governance DDL (10 tables, Tier 6, Depths 0-6)
# Unified Body Governance Model (GOV-BR-004). Depends only on
# body_type_master/position_master (Depth 0), organization,
# person, sangha_sevi - all created in earlier phases - so it
# slots in after Administration and before the writer grant,
# letting Phase 12 GRANT ON ALL TABLES and Phase 14 attach the
# audit trigger to these tables too.
# -------------------------------------------------
Write-Host "[Phase 11b] Governance - DDL (10 tables + ballot immutability + seat-count limits)" -ForegroundColor Cyan
Invoke-Ddl "body_type_master"           "body_type_master"           "$DdlBase\08_governance\01_body_type_master.sql"
Invoke-Ddl "position_master"            "position_master"            "$DdlBase\08_governance\02_position_master.sql"
Invoke-Ddl "body_master"                "body_master"                "$DdlBase\08_governance\03_body_master.sql"
Invoke-Ddl "body_member_assignment"     "body_member_assignment"     "$DdlBase\08_governance\04_body_member_assignment.sql"
Invoke-Ddl "acting_position_assignment" "acting_position_assignment" "$DdlBase\08_governance\05_acting_position_assignment.sql"
Invoke-Ddl "election"                   "election"                   "$DdlBase\08_governance\06_election.sql"
Invoke-Ddl "election_nomination"        "election_nomination"        "$DdlBase\08_governance\07_election_nomination.sql"
Invoke-Ddl "election_vote"              "election_vote"              "$DdlBase\08_governance\08_election_vote.sql"
Invoke-Ddl "election_result"            "election_result"            "$DdlBase\08_governance\09_election_result.sql"
Invoke-Ddl "election_vote_participation" "election_vote_participation" "$DdlBase\08_governance\10_election_vote_participation.sql"
# Ballot immutability: function + BEFORE UPDATE triggers on
# election_vote and election_vote_participation. Not a table —
# Invoke-Sql (CREATE OR REPLACE / DROP..CREATE TRIGGER are idempotent).
Invoke-Sql "governance_immutability"    "$DdlBase\08_governance\11_governance_immutability.sql"
# Seat-count backstop: two functions + BEFORE INSERT OR UPDATE triggers
# on body_member_assignment (flat per-body cap + Advisory Board
# one-seat-per-Sakha). Not a table — Invoke-Sql, same as
# governance_immutability above. NOTE: the companion
# body_type_master.max_members column (01_body_type_master.sql) and
# its seed UPDATE (seed/08_governance/01_body_type_master.sql) are
# existence-gated by Invoke-Ddl/Invoke-Seed above and will NOT reach
# an already-bootstrapped nss.body_type_master without a full hard
# rebuild.
Invoke-Sql "governance_seat_limits"     "$DdlBase\08_governance\12_governance_seat_limits.sql"
Write-Host ""

# -------------------------------------------------
# Phase 11c: Governance — Seed Data
# Starter catalogues for the two Depth-0 masters (body_type_master,
# position_master), plus the 3 NSS-wide singleton body_master rows,
# existence-gated.
# -------------------------------------------------
Write-Host "[Phase 11c] Governance - Seed Data" -ForegroundColor Cyan
Invoke-Seed "body_type_master (seed)" "body_type_master" "$SeedBase\08_governance\01_body_type_master.sql"
Invoke-Seed "position_master (seed)"  "position_master"  "$SeedBase\08_governance\02_position_master.sql"
Invoke-Seed "body_master (seed)"      "body_master"       "$SeedBase\08_governance\03_body_master.sql"
Write-Host ""

# -------------------------------------------------
# Phase 11d: Correspondence DDL (5 tables, Tier 6, Depths 1-5)
# correspondence FK -> person, organization, master_data (Depth 4)
# correspondence_document FK -> correspondence, document_master (Depth 5)
# correspondence_finance_reference FK -> correspondence only in Pass 1;
# financial_transaction FK deferred to Pass 2 (Finance/Tier 12 not yet
# built) per SOL-ADMIN-009 Sec 6.8/7.2.
# correspondence_sequence_counter FK -> organization only (Depth 1);
# backs api/helpers.py::next_correspondence_reference_number() (CORR-EXT-001).
# correspondence_approval_step FK -> correspondence, person,
# position_master, organization (Depth 5) - additive Sakha-President ->
# Kendra-office-bearer approval-chain overlay for the member dashboard's
# "Send Application" feature (owner request, 2026-10-21); placed last so
# it can FK to position_master from Phase 11b/11c.
# Administration-owned capability; moved from Tier 5 to Tier 6
# (owner-confirmed 2026-10-16). Placed after Governance so Phase 12's
# writer grant and Phase 14's audit trigger both cover these tables too.
# -------------------------------------------------
Write-Host "[Phase 11d] Correspondence - DDL (4 tables)" -ForegroundColor Cyan
Invoke-Ddl "correspondence"                   "correspondence"                   "$DdlBase\09_correspondence\01_correspondence.sql"
Invoke-Ddl "correspondence_document"          "correspondence_document"          "$DdlBase\09_correspondence\02_correspondence_document.sql"
Invoke-Ddl "correspondence_finance_reference" "correspondence_finance_reference" "$DdlBase\09_correspondence\03_correspondence_finance_reference.sql"
Invoke-Ddl "correspondence_sequence_counter"  "correspondence_sequence_counter"  "$DdlBase\09_correspondence\04_correspondence_sequence_counter.sql"
Write-Host ""

# -------------------------------------------------
# Phase 11e: Attendance DDL (4 tables, Tier 6, owner-confirmed 2026-10-27)
# weekly_sangha_puja FK -> organization (Depth 1)
# weekly_sangha_puja_attendance FK -> weekly_sangha_puja, sangha_sevi,
# master_data (ATTENDANCE_STATUS), organization (Depth 2)
# attendance_exception FK -> sangha_sevi, master_data
# (ATTENDANCE_EXCEPTION_TYPE) (Depth 2)
# attendance_review FK -> sangha_sevi, organization, master_data
# (ATTENDANCE_REVIEW_STATUS) (Depth 3)
# Placed after Governance/Correspondence so Phase 12's writer grant and
# Phase 14's audit trigger both cover these tables too.
# -------------------------------------------------
Write-Host "[Phase 11e] Attendance - DDL (4 tables)" -ForegroundColor Cyan
Invoke-Ddl "weekly_sangha_puja"            "weekly_sangha_puja"            "$DdlBase\10_attendance\01_weekly_sangha_puja.sql"
Invoke-Ddl "weekly_sangha_puja_attendance" "weekly_sangha_puja_attendance" "$DdlBase\10_attendance\02_weekly_sangha_puja_attendance.sql"
Invoke-Ddl "attendance_exception"          "attendance_exception"          "$DdlBase\10_attendance\03_attendance_exception.sql"
Invoke-Ddl "attendance_review"             "attendance_review"             "$DdlBase\10_attendance\04_attendance_review.sql"
Write-Host ""

# -------------------------------------------------
# Phase 12: Grant nss_db_writer write access (Tier 5)
# Must run AFTER Auth + Admin DDL so the tables exist.
# Grants SELECT on ALL tables (login lookups) +
# INSERT/UPDATE on ALL nss tables, incl. future ones
# (no DELETE, no DDL).
# -------------------------------------------------
Write-Host "[Phase 12] Grant nss_db_writer write access" -ForegroundColor Cyan
Invoke-Sql "create_writer_role" "$ScriptDir\05_create_writer_role.sql"
Write-Host ""

# -------------------------------------------------
# Phase 13: Admin Bootstrap Seed
# Seeds NSS Admin superuser (P1 / SS1 / Admin@123)
# with NSS_ERP_ADMIN role and NSS-WIDE scope.
# Must run AFTER Auth + Admin DDL (Phases 10-11)
# and AFTER Foundation + Organization seeds.
#
# Uses the Python bootstrap script (not psql) because
# the user_account INSERT requires an Argon2 password
# hash generated at runtime.
# -------------------------------------------------
Write-Host "[Phase 13] Admin Bootstrap Seed" -ForegroundColor Cyan
$script:total++
try {
    $output = & python3 "$RepoRoot\scripts\bootstrap_admin.py" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK]   admin_bootstrap" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] admin_bootstrap" -ForegroundColor Red
        Write-Host "  Error: $output"
        $script:failed++
    }
} catch {
    Write-Host "  [FAIL] admin_bootstrap" -ForegroundColor Red
    Write-Host "  Error: $_"
    $script:failed++
}
Write-Host ""

# -------------------------------------------------
# Phase 13b: Geo Attribution Backfill (Bulk-Reference-Seeded Rows)
# Registration-Time Geography Creation (2026-10-21) added
# submitted_by_person_pk to city_village/postal_code/post_office
# (district is out of scope - never auto-created at registration).
# The ~614K city_village and ~17.8K postal_code rows the Phase 2
# Foundation seed bulk-loads have no submitter (nobody "submitted"
# them via the app) - backfill them to point at the NSS Admin's
# person_pk (P1) for attribution consistency, instead of leaving
# them NULL forever.
#
# Must run AFTER Phase 13: P1's person row does not exist until the
# admin bootstrap above creates it.
#
# Idempotent and safe to re-run: only touches rows where
# submitted_by_person_pk IS NULL, and the submitted_by_sangha_sevi_pk
# IS NULL guard means a real member-proposed or registration-origin
# submitter is never overwritten. If P1 does not exist for any
# reason, the subquery returns NULL and the UPDATE is a harmless
# no-op.
# -------------------------------------------------
Write-Host "[Phase 13b] Geo Attribution Backfill (bulk-seeded rows -> P1)" -ForegroundColor Cyan
$script:total++
$backfillSql = @"
UPDATE nss.city_village SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
UPDATE nss.postal_code SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
UPDATE nss.post_office SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
"@
$output = & psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -c $backfillSql 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK]   geo_attribution_backfill" -ForegroundColor Green
    $output | ForEach-Object { Write-Host "  $_" }
} else {
    $outputText = ($output | Out-String)
    if ($outputText -match 'column .* does not exist') {
        # Existing-table DDL change (submitted_by_person_pk) was skipped by
        # an incremental build against an already-bootstrapped
        # city_village/postal_code/post_office. Not fatal: SKIP, not FAIL.
        Write-Host "  [SKIP] geo_attribution_backfill  (submitted_by_person_pk column absent - needs a full hard rebuild)" -ForegroundColor Yellow
        $script:skipped++
    } else {
        Write-Host "  [FAIL] geo_attribution_backfill" -ForegroundColor Red
        Write-Host "  Error: $output"
        $script:failed++
    }
}
Write-Host ""

# -------------------------------------------------
# Phase 14: Audit DDL (system_event_log + DB trigger)
# Must run AFTER all other DDL so the trigger can
# attach to every table in the nss schema.
# -------------------------------------------------
Write-Host "[Phase 14] Audit - DDL (1 table + trigger)" -ForegroundColor Cyan
Invoke-Ddl "system_event_log"  "system_event_log" "$DdlBase\01_foundation\14_system_event_log.sql"
Invoke-Sql "audit_trigger"     "$DdlBase\01_foundation\15_audit_trigger.sql"
Write-Host ""

# -------------------------------------------------
# Phase 15 (OPTIONAL): Demo / test seed - LOCAL DEV ONLY.
# Gitignored (database\seed\demo\), so absent from clean clones and
# never on Render. Runs ONLY when $env:RUN_DEMO_SEED is truthy AND the
# file is present; otherwise skipped silently. Runs AFTER the audit
# trigger so demo rows are audited like any real insert. NOT mirrored
# into render_build.sh - demo data must never land in a deployed env.
# -------------------------------------------------
$DemoSeedFile = "$SeedBase\demo\nss_demo_seed.sql"
$runDemo = ("$($env:RUN_DEMO_SEED)").Trim().ToLower()
if ($runDemo -in @('true','1','yes','on')) {
    if (Test-Path $DemoSeedFile) {
        Write-Host "[Phase 15] Demo / test seed (RUN_DEMO_SEED set)" -ForegroundColor Cyan
        Invoke-Sql "demo_seed" $DemoSeedFile
        Write-Host ""
    } else {
        Write-Host "[Phase 15] RUN_DEMO_SEED set but $DemoSeedFile not found - skipped." -ForegroundColor Yellow
        Write-Host ""
    }
}

# -------------------------------------------------
# Summary
# -------------------------------------------------
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  BUILD SUMMARY" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Scripts executed: $total"
Write-Host "  Skipped:          $skipped  (already existed)"
Write-Host "  Failed:           $failed"
Write-Host ""

if ($failed -eq 0) {
    Write-Host "  Database build completed successfully." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Not executed (future phases):" -ForegroundColor Yellow
    Write-Host "    - Pass 2 audit-actor FK constraints"
    exit 0
} else {
    Write-Host "  Database build FAILED ($failed errors)." -ForegroundColor Red
    exit 1
}
