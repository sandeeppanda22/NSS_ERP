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
#   DB_USER  = nss_admin
#   DB_HOST  = localhost
#   DB_PORT  = 5432
#
# Modules validated:
#   - Bootstrap RBAC (3 tables)
#   - Foundation (12 tables)
#   - Organization (3 tables)
#
# Extend this script when new modules are added.
# =====================================================

set -euo pipefail

DB_NAME="${1:-nss_erp}"
DB_USER="${2:-nss_admin}"
DB_HOST="${3:-localhost}"
DB_PORT="${4:-5432}"

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
    result=$(${PSQL} -c "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nss' AND table_name = '${table}');" 2>/dev/null || echo "f")
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
    count=$(${PSQL} -c "SELECT COUNT(*) FROM nss.${table};" 2>/dev/null || echo "ERROR")
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
    dups=$(${PSQL} -c "SELECT COUNT(*) FROM (SELECT ${column} FROM nss.${table} GROUP BY ${column} HAVING COUNT(*) > 1) x;" 2>/dev/null || echo "ERROR")
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
    orphans=$(${PSQL} -c "${query}" 2>/dev/null || echo "ERROR")
    if [ "$orphans" = "0" ]; then
        log_pass "${label}: FK integrity valid"
    elif [ "$orphans" = "ERROR" ]; then
        log_fail "${label}: FK check failed"
    else
        log_fail "${label}: ${orphans} orphaned rows"
    fi
}

check_column_exists() {
    local table="$1"
    local column="$2"
    local result
    result=$(${PSQL} -c "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'nss' AND table_name = '${table}' AND column_name = '${column}');" 2>/dev/null || echo "f")
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
check_row_count "role_master" 8

echo "  Unique constraints:"
check_no_duplicates "role_master" "role_code"

echo "  FK integrity:"
check_fk_integrity "role_permission -> role_master" \
    "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.role_master rm ON rp.role_master_pk = rm.role_master_pk WHERE rm.role_master_pk IS NULL;"
check_fk_integrity "role_permission -> permission_master" \
    "SELECT COUNT(*) FROM nss.role_permission rp LEFT JOIN nss.permission_master pm ON rp.permission_master_pk = pm.permission_master_pk WHERE pm.permission_master_pk IS NULL;"
echo ""

# =====================================================
# Module 2: Foundation (12 tables)
# =====================================================
echo -e "${CYAN}--- Foundation ---${NC}"
echo "  Tables:"
FOUNDATION_TABLES=(
    "master_category" "system_setting" "id_sequence_master"
    "country" "document_master" "field_change_log"
    "master_data" "state" "district"
    "city_village" "postal_code" "city_village_postal_code_map"
)
for t in "${FOUNDATION_TABLES[@]}"; do
    check_table_exists "$t"
done

echo "  Row counts:"
check_row_count "master_category" 11
check_row_count "master_data" 40
check_row_count "id_sequence_master" 9
check_row_count "country" 5
check_row_count "state" 112
check_row_count "district" 700
check_row_count "system_setting" 5
check_row_count "postal_code" 2

echo "  Unique constraints:"
check_no_duplicates "master_category" "category_code"
check_no_duplicates "country" "country_code"
check_no_duplicates "id_sequence_master" "sequence_code"

echo "  FK integrity:"
check_fk_integrity "master_data -> master_category" \
    "SELECT COUNT(*) FROM nss.master_data md LEFT JOIN nss.master_category mc ON md.master_category_pk = mc.master_category_pk WHERE mc.master_category_pk IS NULL;"
check_fk_integrity "state -> country" \
    "SELECT COUNT(*) FROM nss.state s LEFT JOIN nss.country c ON s.country_pk = c.country_pk WHERE c.country_pk IS NULL;"
check_fk_integrity "district -> state" \
    "SELECT COUNT(*) FROM nss.district d LEFT JOIN nss.state s ON d.state_pk = s.state_pk WHERE s.state_pk IS NULL;"
check_fk_integrity "postal_code -> country" \
    "SELECT COUNT(*) FROM nss.postal_code p LEFT JOIN nss.country c ON p.country_pk = c.country_pk WHERE c.country_pk IS NULL;"
check_fk_integrity "postal_code -> state" \
    "SELECT COUNT(*) FROM nss.postal_code p LEFT JOIN nss.state s ON p.state_pk = s.state_pk WHERE s.state_pk IS NULL;"

echo "  Deferred columns:"
check_column_exists "document_master" "person_pk"
check_column_exists "document_master" "uploaded_by_sangha_sevi_pk"
echo ""

# =====================================================
# Module 3: Organization (3 tables)
# =====================================================
echo -e "${CYAN}--- Organization ---${NC}"
echo "  Tables:"
check_table_exists "organization_type_master"
check_table_exists "organization_status_master"
check_table_exists "organization"

echo "  Row counts:"
check_row_count "organization_type_master" 8
check_row_count "organization_status_master" 6
check_row_count "organization" 3

echo "  Unique constraints:"
check_no_duplicates "organization_type_master" "organization_type_code"
check_no_duplicates "organization_status_master" "organization_status_code"
check_no_duplicates "organization" "organization_code"

echo "  FK integrity:"
check_fk_integrity "organization -> organization_type_master" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.organization_type_master otm ON o.organization_type_pk = otm.organization_type_pk WHERE otm.organization_type_pk IS NULL;"
check_fk_integrity "organization -> organization_status_master" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.organization_status_master osm ON o.organization_status_pk = osm.organization_status_pk WHERE osm.organization_status_pk IS NULL;"
check_fk_integrity "organization -> country" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.country c ON o.country_pk = c.country_pk WHERE o.country_pk IS NOT NULL AND c.country_pk IS NULL;"
check_fk_integrity "organization -> city_village" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.city_village cv ON o.city_village_pk = cv.city_village_pk WHERE o.city_village_pk IS NOT NULL AND cv.city_village_pk IS NULL;"
check_fk_integrity "organization -> postal_code" \
    "SELECT COUNT(*) FROM nss.organization o LEFT JOIN nss.postal_code pc ON o.postal_code_pk = pc.postal_code_pk WHERE o.postal_code_pk IS NOT NULL AND pc.postal_code_pk IS NULL;"
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
