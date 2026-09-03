#!/usr/bin/env bash
# =====================================================
# NSS ERP — Full Database Build
# =====================================================
#
# Executes all DDL and seed scripts in the frozen
# SOL-ARCH-011 phase order for currently implemented
# modules only.
#
# Authority: SOL-ARCH-010 (DDL Creation Order),
#            SOL-ARCH-011 (Bootstrap Architecture)
# Version: 1.0
#
# Usage:
#   ./database/scripts/02_build.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
#
# Defaults:
#   DB_NAME  = nss_erp
#   DB_USER  = nss_admin
#   DB_HOST  = localhost
#   DB_PORT  = 5432
#
# Prerequisites:
#   - PostgreSQL running and accessible
#   - Database and roles created (see 00_create_database.sql)
#   - Extensions installed (see 01_extensions.sql)
#   - Run from the repository root directory
#
# Implemented phases:
#   Phase 0  — Bootstrap RBAC (3 tables + seed)
#   Phase 1  — Foundation DDL (12 tables)
#   Phase 2  — Foundation seed data
#   Phase 3  — Organization DDL (3 tables)
#   Phase 4  — Organization seed data
#
# NOT executed:
#   - database/ddl/03_person/  (superseded prototype)
#   - database/seed/03_person/ (superseded prototype)
#   - Pass 2 audit-actor FK constraints (deferred)
# =====================================================

set -euo pipefail

DB_NAME="${1:-nss_erp}"
DB_USER="${2:-nss_admin}"
DB_HOST="${3:-localhost}"
DB_PORT="${4:-5432}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DDL_BASE="${REPO_ROOT}/database/ddl"
SEED_BASE="${REPO_ROOT}/database/seed"

PSQL="psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -v ON_ERROR_STOP=1"

# -- colours -----------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

total=0
failed=0

run_sql() {
    local label="$1"
    local file="$2"
    total=$((total + 1))
    if ${PSQL} -f "${file}" > /dev/null 2>&1; then
        echo -e "  ${GREEN}[OK]${NC}   ${label}"
    else
        echo -e "  ${RED}[FAIL]${NC} ${label}"
        failed=$((failed + 1))
        echo -e "  ${RED}Aborting — fix the above error before continuing.${NC}"
        exit 1
    fi
}

echo ""
echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN}  NSS ERP — Full Database Build${NC}"
echo -e "${CYAN}=============================================${NC}"
echo "  Database: ${DB_NAME}"
echo "  User:     ${DB_USER}"
echo "  Host:     ${DB_HOST}:${DB_PORT}"
echo -e "${CYAN}=============================================${NC}"
echo ""

# -------------------------------------------------
# Phase 0: Bootstrap RBAC (SOL-ARCH-011 §4)
# -------------------------------------------------
echo -e "${CYAN}[Phase 0] Bootstrap RBAC — DDL${NC}"
run_sql "role_master"       "${DDL_BASE}/00_bootstrap/01_role_master.sql"
run_sql "permission_master" "${DDL_BASE}/00_bootstrap/02_permission_master.sql"
run_sql "role_permission"   "${DDL_BASE}/00_bootstrap/03_role_permission.sql"
echo ""

echo -e "${CYAN}[Phase 0] Bootstrap RBAC — Seed${NC}"
run_sql "permission_master (seed)" "${SEED_BASE}/00_bootstrap/01_permission_master.sql"
run_sql "role_master (seed)"       "${SEED_BASE}/00_bootstrap/02_role_master.sql"
run_sql "role_permission (seed)"   "${SEED_BASE}/00_bootstrap/03_role_permission.sql"
echo ""

# -------------------------------------------------
# Phase 1: Foundation DDL (12 tables, Depths 0–4)
# -------------------------------------------------
echo -e "${CYAN}[Phase 1] Foundation — DDL (12 tables)${NC}"
FOUNDATION_DDL=(
    "master_category|02_master_category.sql"
    "system_setting|03_system_setting.sql"
    "id_sequence_master|04_id_sequence_master.sql"
    "country|05_country.sql"
    "document_master|06_document_master.sql"
    "field_change_log|07_field_change_log.sql"
    "master_data|08_master_data.sql"
    "state|09_state.sql"
    "district|10_district.sql"
    "city_village|11_city_village.sql"
    "postal_code|12_postal_code.sql"
    "city_village_postal_code_map|13_city_village_postal_code_map.sql"
)
for entry in "${FOUNDATION_DDL[@]}"; do
    label="${entry%%|*}"
    file="${entry##*|}"
    run_sql "${label}" "${DDL_BASE}/01_foundation/${file}"
done
echo ""

# -------------------------------------------------
# Phase 2: Foundation Seed Data
# -------------------------------------------------
echo -e "${CYAN}[Phase 2] Foundation — Seed Data${NC}"
FOUNDATION_SEED=(
    "master_category (seed)|01_master_category.sql"
    "master_data (seed)|02_master_data.sql"
    "id_sequence_master (seed)|03_id_sequence_master.sql"
    "country (seed)|04_country.sql"
    "state (seed)|05_state.sql"
    "district (seed)|06_district.sql"
    "system_setting (seed)|07_system_setting.sql"
    "postal_code (seed)|08_postal_code.sql"
)
for entry in "${FOUNDATION_SEED[@]}"; do
    label="${entry%%|*}"
    file="${entry##*|}"
    run_sql "${label}" "${SEED_BASE}/01_foundation/${file}"
done
echo ""

# -------------------------------------------------
# Phase 3: Organization DDL (3 tables, Depths 0–3)
# -------------------------------------------------
echo -e "${CYAN}[Phase 3] Organization — DDL (3 tables)${NC}"
run_sql "organization_type_master"   "${DDL_BASE}/02_organization/01_organization_type_master.sql"
run_sql "organization_status_master" "${DDL_BASE}/02_organization/02_organization_status_master.sql"
run_sql "organization"               "${DDL_BASE}/02_organization/03_organization.sql"
echo ""

# -------------------------------------------------
# Phase 4: Organization Seed Data
# -------------------------------------------------
echo -e "${CYAN}[Phase 4] Organization — Seed Data${NC}"
run_sql "organization_type_master (seed)"   "${SEED_BASE}/02_organization/01_organization_type_master.sql"
run_sql "organization_status_master (seed)" "${SEED_BASE}/02_organization/02_organization_status_master.sql"
run_sql "organization (seed)"               "${SEED_BASE}/02_organization/03_organization.sql"
echo ""

# -------------------------------------------------
# Summary
# -------------------------------------------------
echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN}  BUILD SUMMARY${NC}"
echo -e "${CYAN}=============================================${NC}"
echo -e "  Scripts executed: ${total}"
echo -e "  Failed:           ${failed}"
echo ""

if [ "$failed" -eq 0 ]; then
    echo -e "  ${GREEN}Database build completed successfully.${NC}"
    echo ""
    echo -e "  ${YELLOW}Not executed (future phases):${NC}"
    echo "    - Person DDL (03_person/ is superseded — awaiting rewrite)"
    echo "    - Authentication, Administration, remaining modules"
    echo "    - Pass 2 audit-actor FK constraints"
    exit 0
else
    echo -e "  ${RED}Database build FAILED (${failed} errors).${NC}"
    exit 1
fi
