#!/usr/bin/env bash
# =====================================================
# NSS ERP — Post-Build Validation
# =====================================================
#
# Validates that all implemented modules were built
# correctly. Does NOT execute any DDL or seed scripts —
# run 02_build.sh first.
#
# Checks: table existence, row counts, unique constraints,
# FK integrity, and deferred column presence.
#
# Authority: SOL-ARCH-010, SOL-ARCH-011
#
# Usage:
#   ./database/scripts/03_validate.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
#
# Defaults:
#   DB_NAME  = nss_erp
#   DB_USER  = nss_db_owner
#   DB_HOST  = localhost
#   DB_PORT  = 5432
#
# Modules validated:
#   - Bootstrap RBAC (3 tables)
#   - Foundation (12 tables)
#   - Organization (1 table — type/status in Foundation master_data)
#   - Person (2 tables + address FK columns on person)
#   - Authentication (5 tables)
#   - Administration (2 tables)
#   - Family (6), Membership (14, incl. credential_sequence_counter), system_event_log — existence only
#   - Governance (9 tables — existence only, no seed)
#
# Extend this script when new modules are added.
# =====================================================

set -euo pipefail

DB_NAME="${1:-nss_erp}"
DB_USER="${2:-nss_db_owner}"
DB_HOST="${3:-localhost}"
DB_PORT="${4:-5432}"

# Prompt for password once; export so all psql calls reuse it.
if [ -z "${PGPASSWORD:-}" ]; then
    read -rsp "Password for ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}: " PGPASSWORD
    echo ""
    export PGPASSWORD
fi

PSQL="psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -t -A"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass_count=0
fail_count=0
warn_count=0

log_pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; pass_count=$((pass_count + 1)); }
log_fail() { echo -e "  ${RED}[FAIL]${NC} $1"; fail_count=$((fail_count + 1)); }
log_warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; warn_count=$((warn_count + 1)); }

# --- helpers ------------------------------------------

check_table_exists() {
    local table="$1"
    local result
    result=$(${PSQL} -c "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nss' AND table_name = '${table}');" 2>&1 || echo "f")
    if [ "$result" = "t" ]; then
        log_pass "${table} exists"
    else
        log_fail "${table} MISSING"
    fi
}

check_row_count() {
    local table="$1"
    local expected="$2"
    local count
    count=$(${PSQL} -c "SELECT COUNT(*) FROM nss.${table};" 2>&1 || echo "ERROR")
    if [ "$count" = "ERROR" ]; then
        log_fail "${table}: query failed"
    elif [ "$count" -ge "$expected" ] 2>/dev/null; then
        log_pass "${table}: ${count} rows (expected >= ${expected})"
    else
        log_warn "${table}: ${count} rows (expected >= ${expected})"
    fi
}

check_no_duplicates() {
    local table="$1"
    local column="$2"
    local dups
    dups=$(${PSQL} -c "SELECT COUNT(*) FROM (SELECT ${column} FROM nss.${table} GROUP BY ${column} HAVING COUNT(*) > 1) x;" 2>&1 || echo "ERROR")
    if [ "$dups" = "0" ]; then
        log_pass "${table}: no duplicate ${column}"
    elif [ "$dups" = "ERROR" ]; then
        log_fail "${table}: duplicate check failed"
    else
        log_fail "${table}: ${dups} duplicate ${column} values"
    fi
}

check_fk_integrity() {
    local label="$1"
    local query="$2"
    local orphans
    orphans=$(${PSQL} -c "${query}" 2>&1 || echo "ERROR")
    if [ "$orphans" = "0" ]; then
        log_pass "${label}: FK integrity valid"
    elif [ "$orphans" = "ERROR" ]; then
        log_fail "${label}: FK check failed"
    else
        log_fail "${label}: ${orphans} orphaned rows"
    fi
}

check_min_percentage() {
    local label="$1"
    local query="$2"      # must SELECT a single numeric percentage (0-100)
    local min_pct="$3"
    local pct
    pct=$(${PSQL} -c "${query}" 2>&1 || echo "ERROR")
    if [ "$pct" = "ERROR" ]; then
        log_fail "${label}: query failed"
    elif awk -v p="$pct" -v m="$min_pct" 'BEGIN{exit !(p>=m)}'; then
        log_pass "${label}: ${pct}% (expected >= ${min_pct}%)"
    else
        log_fail "${label}: ${pct}% (expected >= ${min_pct}%)"
    fi
}

check_column_exists() {
    local table="$1"
    local column="$2"
    local result
    result=$(${PSQL} -c "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'nss' AND table_name = '${table}' AND column_name = '${column}');" 2>&1 || echo "f")
    if [ "$result" = "t" ]; then
        log_pass "${table}.${column} present"
    else
        log_fail "${table}.${column} MISSING"
    fi
}

# --- header -------------------------------------------

echo ""
echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN}  NSS ERP — Post-Build Validation${NC}"
echo -e "${CYAN}=============================================${NC}"
echo "  Database: ${DB_NAME}"
echo "  User:     ${DB_USER}"
echo "  Host:     ${DB_HOST}:${DB_PORT}"
echo -e "${CYAN}=============================================${NC}"
echo ""

# =====================================================
# Module 1: Bootstrap RBAC (3 tables)
# =====================================================
echo -e "${CYAN}--- Bootstrap RBAC ---${NC}"
echo "  Tables:"
check_table_exists "role_master"
check_table_exists "permission_master"
check_table_exists "role_permission"

echo "  Row counts:"
check_row_count "role_master" 10

echo "  Unique constraints:"
check_no_duplicates "role_master" "role_code"

echo "  FK integrity:"
check_fk_integrity "role_permission -> role_master" \
    "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.role_master rm ON rp.role_master_pk = rm.role_master_pk WHERE rm.role_master_pk IS NULL;"
check_fk_integrity "role_permission -> permission_master" \
    "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.permission_master pm ON rp.permission_master_pk = pm.permission_master_pk WHERE pm.permission_master_pk IS NULL;"
echo ""

# =====================================================
# Module 2: Foundation (11 tables)
# =====================================================
echo -e "${CYAN}--- Foundation ---${NC}"
echo "  Tables:"
FOUNDATION_TABLES=(
    "master_category" "system_setting" "id_sequence_master"
    "country" "document_master" "field_change_log"
    "master_data" "state" "district"
    "city_village" "postal_code"
)
for t in "${FOUNDATION_TABLES[@]}"; do
    check_table_exists "$t"
done

echo "  Row counts:"
check_row_count "master_category" 13
check_row_count "master_data" 89
check_row_count "id_sequence_master" 14
check_row_count "country" 5
check_row_count "state" 112
check_row_count "district" 780
check_row_count "system_setting" 5
check_row_count "postal_code" 17800
check_row_count "city_village" 673000

echo "  Unique constraints:"
check_no_duplicates "master_category" "category_code"
check_no_duplicates "country" "country_code"
check_no_duplicates "id_sequence_master" "sequence_code"
check_no_duplicates "postal_code" "postal_code"

echo "  FK integrity:"
check_fk_integrity "master_data -> master_category" \
    "SELECT COUNT(*) FROM nss.master_data md LEFT JOIN nss.master_category mc ON md.master_category_pk = mc.master_category_pk WHERE mc.master_category_pk IS NULL;"
check_fk_integrity "state -> country" \
    "SELECT COUNT(*) FROM nss.state s LEFT JOIN nss.country c ON s.country_pk = c.country_pk WHERE c.country_pk IS NULL;"
check_fk_integrity "district -> state" \
    "SELECT COUNT(*) FROM nss.district d LEFT JOIN nss.state s ON d.state_pk = s.state_pk WHERE s.state_pk IS NULL;"
check_fk_integrity "postal_code -> state" \
    "SELECT COUNT(*) FROM nss.postal_code p LEFT JOIN nss.state s ON p.state_pk = s.state_pk WHERE s.state_pk IS NULL;"
check_fk_integrity "city_village -> postal_code" \
    "SELECT COUNT(*) FROM nss.city_village cv LEFT JOIN nss.postal_code pc ON cv.postal_code_pk = pc.postal_code_pk WHERE cv.postal_code_pk IS NOT NULL AND pc.postal_code_pk IS NULL;"
check_fk_integrity "city_village -> district" \
    "SELECT COUNT(*) FROM nss.city_village cv LEFT JOIN nss.district d ON cv.district_pk = d.district_pk WHERE cv.district_pk IS NOT NULL AND d.district_pk IS NULL;"

echo "  Geography model (SOL-ARCH-010 Amendment, 2026-10-02 — district at city_village grain):"
check_column_exists "city_village" "district_pk"
check_min_percentage "city_village district_pk coverage" \
    "SELECT ROUND(COUNT(*) FILTER (WHERE district_pk IS NOT NULL) * 100.0 / NULLIF(COUNT(*),0), 2) FROM nss.city_village;" \
    98

echo "  Deferred columns:"
check_column_exists "document_master" "person_pk"
check_column_exists "document_master" "uploaded_by_sangha_sevi_pk"
echo ""

# =====================================================
# Module 3: Organization (1 table — type/status via master_data)
# =====================================================
echo -e "${CYAN}--- Organization ---${NC}"
echo "  Tables:"
check_table_exists "organization"

echo "  Row counts:"
check_row_count "organization" 178

echo "  Unique constraints:"
check_no_duplicates "organization" "organization_code"

echo "  FK integrity:"
check_fk_integrity "organization -> master_data (type)" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.master_data md ON o.organization_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
check_fk_integrity "organization -> master_data (status)" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.master_data md ON o.status_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
check_fk_integrity "organization -> country" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.country c ON o.country_pk = c.country_pk WHERE o.country_pk IS NOT NULL AND c.country_pk IS NULL;"
check_fk_integrity "organization -> city_village" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.city_village cv ON o.city_village_pk = cv.city_village_pk WHERE o.city_village_pk IS NOT NULL AND cv.city_village_pk IS NULL;"
check_fk_integrity "organization -> postal_code" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.postal_code pc ON o.postal_code_pk = pc.postal_code_pk WHERE o.postal_code_pk IS NOT NULL AND pc.postal_code_pk IS NULL;"
echo ""

# =====================================================
# Module 4: Person (2 tables — no seed data)
# =====================================================
echo -e "${CYAN}--- Person ---${NC}"
echo "  Tables:"
check_table_exists "person"
check_table_exists "person_address"

echo "  Row counts (no seed — expect 0):"
check_row_count "person" 0
check_row_count "person_address" 0

echo "  FK integrity:"
check_fk_integrity "person -> master_data (gender)" \
    "SELECT COUNT(*) FROM nss.person p LEFT JOIN nss.master_data md ON p.gender_master_data_pk = md.master_data_pk WHERE p.gender_master_data_pk IS NOT NULL AND md.master_data_pk IS NULL;"
check_fk_integrity "person -> master_data (marital_status)" \
    "SELECT COUNT(*) FROM nss.person p LEFT JOIN nss.master_data md ON p.marital_status_master_data_pk = md.master_data_pk WHERE p.marital_status_master_data_pk IS NOT NULL AND md.master_data_pk IS NULL;"
check_fk_integrity "person -> master_data (blood_group)" \
    "SELECT COUNT(*) FROM nss.person p LEFT JOIN nss.master_data md ON p.blood_group_master_data_pk = md.master_data_pk WHERE p.blood_group_master_data_pk IS NOT NULL AND md.master_data_pk IS NULL;"
check_fk_integrity "person_address -> person" \
    "SELECT COUNT(*) FROM nss.person_address pa LEFT JOIN nss.person p ON pa.person_pk = p.person_pk WHERE p.person_pk IS NULL;"
check_fk_integrity "person_address -> master_data (address_type)" \
    "SELECT COUNT(*) FROM nss.person_address pa LEFT JOIN nss.master_data md ON pa.address_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"

echo "  Person address FK columns:"
check_column_exists "person" "country_pk"
check_column_exists "person" "state_pk"
check_column_exists "person" "district_pk"
check_column_exists "person" "city_village_pk"
check_column_exists "person" "postal_code_pk"
echo ""

# =====================================================
# Module 5: Authentication (5 tables)
# =====================================================
echo -e "${CYAN}--- Authentication ---${NC}"
echo "  Tables:"
check_table_exists "user_account"
check_table_exists "password_history"
check_table_exists "registration_claim"
check_table_exists "password_reset_token"
check_table_exists "user_session"

echo "  Row counts:"
check_row_count "user_account" 1
check_row_count "password_history" 0

echo "  Key columns:"
check_column_exists "user_account" "person_pk"
check_column_exists "user_account" "password_hash"
check_column_exists "user_account" "account_status"
check_column_exists "user_account" "is_active"
check_column_exists "user_account" "failed_login_attempts"
check_column_exists "user_account" "locked_until"
check_column_exists "user_account" "password_expires_at"
check_column_exists "user_account" "force_password_change"
check_column_exists "user_account" "last_login_at"
check_column_exists "password_history" "user_account_pk"
check_column_exists "password_history" "password_hash"
check_column_exists "user_session" "user_account_pk"
check_column_exists "user_session" "revoked_at"
check_column_exists "user_session" "expires_at"
check_column_exists "user_session" "device_label"

echo "  Unique constraints:"
check_no_duplicates "user_account" "person_pk"

echo "  FK integrity:"
check_fk_integrity "user_account -> person" \
    "SELECT COUNT(*) FROM nss.user_account ua LEFT JOIN nss.person p ON ua.person_pk = p.person_pk WHERE p.person_pk IS NULL;"
check_fk_integrity "user_session -> user_account" \
    "SELECT COUNT(*) FROM nss.user_session us LEFT JOIN nss.user_account ua ON us.user_account_pk = ua.user_account_pk WHERE ua.user_account_pk IS NULL;"
check_fk_integrity "password_history -> user_account" \
    "SELECT COUNT(*) FROM nss.password_history ph LEFT JOIN nss.user_account ua ON ph.user_account_pk = ua.user_account_pk WHERE ua.user_account_pk IS NULL;"
echo ""

# =====================================================
# Module 6: Administration (2 tables)
# =====================================================
echo -e "${CYAN}--- Administration ---${NC}"
echo "  Tables:"
check_table_exists "user_role"
check_table_exists "admin_scope"

echo "  Row counts:"
check_row_count "user_role" 1
check_row_count "admin_scope" 1

echo "  Key columns:"
check_column_exists "user_role" "user_account_pk"
check_column_exists "user_role" "role_master_pk"
check_column_exists "user_role" "is_active"
check_column_exists "admin_scope" "user_role_pk"
check_column_exists "admin_scope" "scope_level"
check_column_exists "admin_scope" "organization_pk"

echo "  FK integrity:"
check_fk_integrity "user_role -> user_account" \
    "SELECT COUNT(*) FROM nss.user_role ur LEFT JOIN nss.user_account ua ON ur.user_account_pk = ua.user_account_pk WHERE ua.user_account_pk IS NULL;"
check_fk_integrity "user_role -> role_master" \
    "SELECT COUNT(*) FROM nss.user_role ur LEFT JOIN nss.role_master rm ON ur.role_master_pk = rm.role_master_pk WHERE rm.role_master_pk IS NULL;"
check_fk_integrity "admin_scope -> user_role" \
    "SELECT COUNT(*) FROM nss.admin_scope asc2 LEFT JOIN nss.user_role ur ON asc2.user_role_pk = ur.user_role_pk WHERE ur.user_role_pk IS NULL;"
check_fk_integrity "admin_scope -> organization" \
    "SELECT COUNT(*) FROM nss.admin_scope asc2 LEFT JOIN nss.organization o ON asc2.organization_pk = o.organization_pk WHERE asc2.organization_pk IS NOT NULL AND o.organization_pk IS NULL;"
echo ""

# =====================================================
# Module 7: Family, Membership, audit
# =====================================================
echo -e "${CYAN}--- Family / Membership / Audit ---${NC}"
echo "  Tables (existence only — no seed data):"
check_table_exists "family_group"
check_table_exists "family_relationship"
check_table_exists "family_transition_history"
check_table_exists "family_head_history"
check_table_exists "family_link"
check_table_exists "family_admin"
check_table_exists "sangha_sevi"
check_table_exists "membership_status_history"
check_table_exists "membership_renewal_request"
check_table_exists "membership_renewal_history"
check_table_exists "membership_transfer_history"
check_table_exists "membership_sakha_affiliation"
check_table_exists "membership_journey_event"
check_table_exists "probationary_member_review"
check_table_exists "parichaya_patra"
check_table_exists "parichaya_patra_history"
check_table_exists "anumati_patra"
check_table_exists "anumati_patra_history"
check_table_exists "darshak_attendance_registration"
check_table_exists "credential_sequence_counter"
check_table_exists "sakha_local_number_counter"
check_table_exists "membership_change_request"
check_table_exists "system_event_log"
echo ""

# =====================================================
# Module 8: Governance (10 tables — existence only, no seed)
# Unified Body Governance Model (GOV-BR-004).
# =====================================================
echo -e "${CYAN}--- Governance ---${NC}"
echo "  Tables (existence only — no seed data):"
check_table_exists "body_type_master"
check_table_exists "position_master"
check_table_exists "body_master"
check_table_exists "body_member_assignment"
check_table_exists "acting_position_assignment"
check_table_exists "election"
check_table_exists "election_nomination"
check_table_exists "election_vote"
check_table_exists "election_vote_participation"
check_table_exists "election_result"
echo "  Key columns:"
check_column_exists "body_master" "body_type_master_pk"
check_column_exists "body_member_assignment" "person_pk"
check_column_exists "election_vote" "voter_person_pk"
echo "  FK integrity (no orphans — vacuously true until seeded):"
check_fk_integrity "body_master -> body_type_master" \
    "SELECT COUNT(*) FROM nss.body_master bm LEFT JOIN nss.body_type_master bt ON bm.body_type_master_pk = bt.body_type_master_pk WHERE bt.body_type_master_pk IS NULL;"
check_fk_integrity "body_member_assignment -> body_master" \
    "SELECT COUNT(*) FROM nss.body_member_assignment bma LEFT JOIN nss.body_master bm ON bma.body_master_pk = bm.body_master_pk WHERE bm.body_master_pk IS NULL;"
check_fk_integrity "election_result -> election" \
    "SELECT COUNT(*) FROM nss.election_result er LEFT JOIN nss.election e ON er.election_pk = e.election_pk WHERE e.election_pk IS NULL;"
echo ""

# =====================================================
# Correspondence (4 tables, Tier 6 — existence only, no seed)
# Administration-owned capability; moved from Tier 5 to Tier 6
# (owner-confirmed 2026-10-16). financial_transaction FK on
# correspondence_finance_reference is deferred to Pass 2 (Finance/
# Tier 12 not yet built) — not checked here.
# =====================================================
echo -e "${CYAN}--- Correspondence ---${NC}"
echo "  Tables (existence only — no seed data):"
check_table_exists "correspondence"
check_table_exists "correspondence_document"
check_table_exists "correspondence_finance_reference"
check_table_exists "correspondence_sequence_counter"
echo "  Key columns:"
check_column_exists "correspondence" "reference_number"
check_column_exists "correspondence" "register_organization_pk"
check_column_exists "correspondence" "sender_person_capacity"
check_column_exists "correspondence_document" "correspondence_pk"
check_column_exists "correspondence_finance_reference" "relationship_type_master_data_pk"
check_column_exists "correspondence_sequence_counter" "register_organization_pk"
check_column_exists "correspondence_sequence_counter" "direction"
check_column_exists "correspondence_sequence_counter" "financial_year_start"
check_column_exists "correspondence_sequence_counter" "current_value"
echo "  FK integrity (no orphans — vacuously true until seeded):"
check_fk_integrity "correspondence -> organization (register owner)" \
    "SELECT COUNT(*) FROM nss.correspondence c LEFT JOIN nss.organization o ON c.register_organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"
check_fk_integrity "correspondence_document -> correspondence" \
    "SELECT COUNT(*) FROM nss.correspondence_document cd LEFT JOIN nss.correspondence c ON cd.correspondence_pk = c.correspondence_pk WHERE c.correspondence_pk IS NULL;"
check_fk_integrity "correspondence_finance_reference -> correspondence" \
    "SELECT COUNT(*) FROM nss.correspondence_finance_reference cfr LEFT JOIN nss.correspondence c ON cfr.correspondence_pk = c.correspondence_pk WHERE c.correspondence_pk IS NULL;"
check_fk_integrity "correspondence_finance_reference -> master_data (relationship_type)" \
    "SELECT COUNT(*) FROM nss.correspondence_finance_reference cfr LEFT JOIN nss.master_data md ON cfr.relationship_type_master_data_pk = md.master_data_pk WHERE md.master_data_pk IS NULL;"
check_fk_integrity "correspondence_sequence_counter -> organization" \
    "SELECT COUNT(*) FROM nss.correspondence_sequence_counter csc LEFT JOIN nss.organization o ON csc.register_organization_pk = o.organization_pk WHERE o.organization_pk IS NULL;"
echo "  Unique constraints:"
check_no_duplicates "correspondence" "reference_number"
echo ""

# =====================================================
# Summary
# =====================================================
echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN}  VALIDATION RESULTS${NC}"
echo -e "${CYAN}=============================================${NC}"
echo -e "  Passed:   ${GREEN}${pass_count}${NC}"
echo -e "  Warnings: ${YELLOW}${warn_count}${NC}"
echo -e "  Failed:   ${RED}${fail_count}${NC}"
echo ""

if [ "$fail_count" -eq 0 ] && [ "$warn_count" -eq 0 ]; then
    echo -e "  ${GREEN}All validations PASSED${NC}"
    exit 0
elif [ "$fail_count" -eq 0 ]; then
    echo -e "  ${YELLOW}Passed with warnings (${warn_count})${NC}"
    exit 0
else
    echo -e "  ${RED}Validation FAILED (${fail_count} failures)${NC}"
    exit 1
fi
