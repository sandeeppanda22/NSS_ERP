#!/usr/bin/env bash
# =====================================================
# NSS ERP — Foundation Vertical Slice Validation
# =====================================================
#
# Runs all Foundation DDL + seed scripts in the correct
# depth/dependency order against a PostgreSQL instance.
#
# Authority: SOL-ARCH-010, SOL-FND-004
#
# Usage:
#   ./validate_foundation.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
#
# Defaults:
#   DB_NAME  = nss_erp
#   DB_USER  = nss_admin
#   DB_HOST  = localhost
#   DB_PORT  = 5432
#
# Prerequisites:
#   - PostgreSQL running and accessible
#   - Target database created (CREATE DATABASE nss_erp)
#   - User has CREATE TABLE / INSERT privileges
#
# What this script does:
#   1. Creates required PostgreSQL extensions
#   2. Runs Foundation DDL in depth order (12 tables)
#   3. Runs Foundation seed data in dependency order
#   4. Validates table creation and row counts
#
# What this script does NOT do:
#   - Does not create/drop the database itself
#   - Does not run non-Foundation DDL (Organization, Person, etc.)
#   - Does not add Pass 2 deferred constraints
# =====================================================

set -euo pipefail

DB_NAME="${1:-nss_erp}"
DB_USER="${2:-nss_admin}"
DB_HOST="${3:-localhost}"
DB_PORT="${4:-5432}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DDL_DIR="${SCRIPT_DIR}/database/ddl/01_foundation"
SEED_DIR="${SCRIPT_DIR}/database/seed/01_foundation"

PSQL="psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -v ON_ERROR_STOP=1"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass_count=0
fail_count=0

log_info()  { echo -e "${GREEN}[OK]${NC}   $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_fail()  { echo -e "${RED}[FAIL]${NC} $1"; fail_count=$((fail_count + 1)); }
log_pass()  { echo -e "${GREEN}[PASS]${NC} $1"; pass_count=$((pass_count + 1)); }

echo "============================================="
echo "NSS ERP — Foundation Vertical Slice Validation"
echo "============================================="
echo "Database: ${DB_NAME}"
echo "User:     ${DB_USER}"
echo "Host:     ${DB_HOST}:${DB_PORT}"
echo "============================================="
echo ""

# -------------------------------------------------
# Phase 1: Extensions
# -------------------------------------------------
echo "--- Phase 1: Extensions ---"

if ${PSQL} -f "${DDL_DIR}/01_extensions.sql" > /dev/null 2>&1; then
    log_info "Extensions created (pgcrypto, pg_trgm, btree_gin)"
else
    log_fail "Extensions creation failed"
    echo "Cannot proceed without extensions. Exiting."
    exit 1
fi

echo ""

# -------------------------------------------------
# Phase 2: DDL — Foundation tables in depth order
# -------------------------------------------------
echo "--- Phase 2: DDL (12 Foundation tables) ---"

# Depth 0 (6 tables)
DDL_FILES_D0=(
    "02_master_category.sql"
    "03_system_setting.sql"
    "04_id_sequence_master.sql"
    "05_country.sql"
    "06_document_master.sql"
    "07_field_change_log.sql"
)

# Depth 1 (2 tables)
DDL_FILES_D1=(
    "08_master_data.sql"
    "09_state.sql"
)

# Depth 2 (2 tables)
DDL_FILES_D2=(
    "10_district.sql"
    "12_postal_code.sql"
)

# Depth 3 (1 table)
DDL_FILES_D3=(
    "11_city_village.sql"
)

# Depth 4 (1 table)
DDL_FILES_D4=(
    "13_city_village_postal_code_map.sql"
)

run_ddl_depth() {
    local depth=$1
    shift
    local files=("$@")
    echo "  Depth ${depth}:"
    for f in "${files[@]}"; do
        local table_name
        table_name=$(echo "$f" | sed 's/^[0-9]*_//' | sed 's/\.sql$//')
        if ${PSQL} -f "${DDL_DIR}/${f}" > /dev/null 2>&1; then
            log_pass "  ${table_name}"
        else
            log_fail "  ${table_name} — DDL execution failed"
        fi
    done
}

run_ddl_depth 0 "${DDL_FILES_D0[@]}"
run_ddl_depth 1 "${DDL_FILES_D1[@]}"
run_ddl_depth 2 "${DDL_FILES_D2[@]}"
run_ddl_depth 3 "${DDL_FILES_D3[@]}"
run_ddl_depth 4 "${DDL_FILES_D4[@]}"

echo ""

# -------------------------------------------------
# Phase 3: Seed data in dependency order
# -------------------------------------------------
echo "--- Phase 3: Seed Data ---"

SEED_FILES=(
    "01_master_category.sql"
    "02_master_data.sql"
    "03_id_sequence_master.sql"
    "04_country.sql"
    "05_state.sql"
    "06_district.sql"
    "07_system_setting.sql"
)

for f in "${SEED_FILES[@]}"; do
    local_name=$(echo "$f" | sed 's/^[0-9]*_//' | sed 's/\.sql$//')
    if ${PSQL} -f "${SEED_DIR}/${f}" > /dev/null 2>&1; then
        log_pass "Seed: ${local_name}"
    else
        log_fail "Seed: ${local_name} — execution failed"
    fi
done

echo ""

# -------------------------------------------------
# Phase 4: Validation queries
# -------------------------------------------------
echo "--- Phase 4: Validation ---"

# Check all 12 Foundation tables exist
EXPECTED_TABLES=(
    "master_category"
    "system_setting"
    "id_sequence_master"
    "country"
    "document_master"
    "field_change_log"
    "master_data"
    "state"
    "district"
    "city_village"
    "postal_code"
    "city_village_postal_code_map"
)

echo "  Table existence:"
for t in "${EXPECTED_TABLES[@]}"; do
    exists=$(${PSQL} -t -A -c "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '${t}');" 2>/dev/null || echo "f")
    if [ "$exists" = "t" ]; then
        log_pass "  ${t} exists"
    else
        log_fail "  ${t} MISSING"
    fi
done

echo ""
echo "  Row counts:"

COUNT_QUERIES=(
    "master_category|SELECT COUNT(*) FROM master_category"
    "master_data|SELECT COUNT(*) FROM master_data"
    "id_sequence_master|SELECT COUNT(*) FROM id_sequence_master"
    "country|SELECT COUNT(*) FROM country"
    "state|SELECT COUNT(*) FROM state"
    "district|SELECT COUNT(*) FROM district"
    "system_setting|SELECT COUNT(*) FROM system_setting"
)

for entry in "${COUNT_QUERIES[@]}"; do
    tbl="${entry%%|*}"
    qry="${entry##*|}"
    count=$(${PSQL} -t -A -c "${qry}" 2>/dev/null || echo "ERROR")
    if [ "$count" != "ERROR" ] && [ "$count" -gt 0 ] 2>/dev/null; then
        log_pass "  ${tbl}: ${count} rows"
    else
        log_warn "  ${tbl}: ${count} rows"
    fi
done

# Verify specific constraints
echo ""
echo "  Constraint checks:"

# master_category unique codes
dup_check=$(${PSQL} -t -A -c "SELECT COUNT(*) FROM (SELECT category_code FROM master_category GROUP BY category_code HAVING COUNT(*) > 1) x;" 2>/dev/null || echo "ERROR")
if [ "$dup_check" = "0" ]; then
    log_pass "  master_category: no duplicate category_code"
else
    log_fail "  master_category: duplicate category_code found"
fi

# country unique codes
dup_check=$(${PSQL} -t -A -c "SELECT COUNT(*) FROM (SELECT country_code FROM country GROUP BY country_code HAVING COUNT(*) > 1) x;" 2>/dev/null || echo "ERROR")
if [ "$dup_check" = "0" ]; then
    log_pass "  country: no duplicate country_code"
else
    log_fail "  country: duplicate country_code found"
fi

# state FK integrity
orphan_check=$(${PSQL} -t -A -c "SELECT COUNT(*) FROM state s LEFT JOIN country c ON s.country_pk = c.country_pk WHERE c.country_pk IS NULL;" 2>/dev/null || echo "ERROR")
if [ "$orphan_check" = "0" ]; then
    log_pass "  state: all FK references valid"
else
    log_fail "  state: ${orphan_check} orphaned rows"
fi

# district FK integrity
orphan_check=$(${PSQL} -t -A -c "SELECT COUNT(*) FROM district d LEFT JOIN state s ON d.state_pk = s.state_pk WHERE s.state_pk IS NULL;" 2>/dev/null || echo "ERROR")
if [ "$orphan_check" = "0" ]; then
    log_pass "  district: all FK references valid"
else
    log_fail "  district: ${orphan_check} orphaned rows"
fi

# postal_code FK integrity
orphan_check=$(${PSQL} -t -A -c "SELECT COUNT(*) FROM postal_code p LEFT JOIN country c ON p.country_pk = c.country_pk WHERE c.country_pk IS NULL;" 2>/dev/null || echo "ERROR")
if [ "$orphan_check" = "0" ]; then
    log_pass "  postal_code: country FK valid"
else
    log_fail "  postal_code: ${orphan_check} orphaned country refs"
fi

orphan_check=$(${PSQL} -t -A -c "SELECT COUNT(*) FROM postal_code p LEFT JOIN state s ON p.state_pk = s.state_pk WHERE s.state_pk IS NULL;" 2>/dev/null || echo "ERROR")
if [ "$orphan_check" = "0" ]; then
    log_pass "  postal_code: state FK valid"
else
    log_fail "  postal_code: ${orphan_check} orphaned state refs"
fi

# document_master nullable columns present
col_check=$(${PSQL} -t -A -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'document_master' AND column_name IN ('person_pk', 'uploaded_by_sangha_sevi_pk');" 2>/dev/null || echo "0")
if [ "$col_check" = "2" ]; then
    log_pass "  document_master: person_pk + uploaded_by_sangha_sevi_pk present"
else
    log_fail "  document_master: missing deferred columns (found ${col_check}/2)"
fi

echo ""
echo "============================================="
echo "RESULTS"
echo "============================================="
echo -e "Passed: ${GREEN}${pass_count}${NC}"
echo -e "Failed: ${RED}${fail_count}${NC}"
echo ""

if [ "$fail_count" -eq 0 ]; then
    echo -e "${GREEN}Foundation vertical slice validation PASSED${NC}"
    exit 0
else
    echo -e "${RED}Foundation vertical slice validation FAILED (${fail_count} failures)${NC}"
    exit 1
fi
