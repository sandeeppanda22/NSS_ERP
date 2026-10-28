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
# Version: 2.6  — reinstate post_office (SOL-ARCH-010 Amendment,
#            2026-10-03: Member-Assisted Geographic Entry). A PIN
#            can hold many post offices; post_office is one of the
#            four member-writable geographic levels. Supersedes the
#            v2.5 retirement note below.
# Version: 2.5  — drop post_office (retired 2026-10-02:
#            Simplified Geography Model — district now lives on
#            city_village, not a separate office-grain table)
#
# Usage:
#   ./database/scripts/02_build.sh [DB_NAME] [DB_USER] [DB_HOST] [DB_PORT]
#
# Defaults:
#   DB_NAME  = nss_erp
#   DB_USER  = nss_db_owner
#   DB_HOST  = localhost
#   DB_PORT  = 5432
#
# Prerequisites:
#   - PostgreSQL running and accessible
#   - Database and roles created (see 00_create_database.sql)
#   - Extensions installed (see 01_extensions.sql)
#   - Role passwords set and api/.env generated (see 06_setup_env.sh)
#   - Run from the repository root directory
#
# Implemented phases:
#   Phase 0  — Bootstrap RBAC (3 tables + seed)
#   Phase 1  — Foundation DDL (14 tables: 02-13 + 16-17; system_event_log is
#              created separately in Phase 14)
#   Phase 2  — Foundation seed data (incl. ORGANIZATION_TYPE
#              category and unified STATUS category in master_data)
#   Phase 3  — Organization DDL (1 table)
#   Phase 4  — Organization seed data
#   Phase 5  — Person DDL (2 tables)
#   Phase 6  — Family DDL (6 tables)
#   Phase 7  — Membership DDL (16 tables)
#   Phase 8  — Tier 4 Verification Seed Data (removed — no demo data)
#   Phase 9  — Grant nss_db_backend read-only access
#   Phase 10 — Authentication DDL (5 tables: user_account,
#              password_history, registration_claim, password_reset_token,
#              user_session)
#   Phase 11 — Administration DDL (2 tables)
#   Phase 11b— Governance DDL (10 tables: body_type_master,
#              position_master, body_master, body_member_assignment,
#              acting_position_assignment, election,
#              election_nomination, election_vote, election_result,
#              election_vote_participation) + ballot-immutability
#              triggers (11_governance_immutability.sql) + seat-count
#              triggers (12_governance_seat_limits.sql)
#   Phase 11c— Governance Seed Data (body_type_master, position_master)
#   Phase 11d— Correspondence DDL (5 tables: correspondence,
#              correspondence_document, correspondence_finance_reference,
#              correspondence_sequence_counter, correspondence_approval_step —
#              Tier 6, Administration-owned; moved from Tier 5,
#              owner-confirmed 2026-10-16)
#   Phase 11e— Attendance DDL (4 tables: weekly_sangha_puja,
#              weekly_sangha_puja_attendance, attendance_exception,
#              attendance_review — Tier 6, owner-confirmed 2026-10-27)
#   Phase 12 — Grant nss_db_writer write access (Tier 5)
#   Phase 13 — Admin bootstrap seed (NSS Admin superuser)
#   Phase 13b— Geo attribution backfill (city_village/postal_code/
#              post_office submitted_by_person_pk -> P1, for rows the
#              Phase 2 bulk seed left unattributed; must run after
#              Phase 13 since P1's person_pk doesn't exist before it)
#   Phase 14 — Audit DDL (system_event_log table + DB trigger)
#   Phase 15 — (OPTIONAL, local dev only) demo/test seed, run only when
#              RUN_DEMO_SEED is truthy and database/seed/demo/nss_demo_seed.sql
#              exists (gitignored; never on Render)
#
# NOT executed:
#   - database/seed/03_person/ (no seed data — Person data lives in
#     Foundation master_data; the superseded 01_person_master_tables.sql
#     DDL/seed were removed 2026-10-01, dead code with zero references)
#   - Pass 2 audit-actor FK constraints (deferred)
# =====================================================

set -euo pipefail

DB_NAME="${1:-nss_erp}"
DB_USER="${2:-nss_db_owner}"
DB_HOST="${3:-localhost}"
DB_PORT="${4:-5432}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DDL_BASE="${REPO_ROOT}/database/ddl"
SEED_BASE="${REPO_ROOT}/database/seed"

# -------------------------------------------------
# Install Python dependencies
# -------------------------------------------------
echo "=== Installing Python dependencies ==="
python3 -m pip install -r "${REPO_ROOT}/requirements.txt"
echo ""

# Prompt for password once; export so all psql calls reuse it.
if [ -z "${PGPASSWORD:-}" ]; then
    read -rsp "Password for ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}: " PGPASSWORD
    echo ""
    export PGPASSWORD
fi

PSQL="psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -v ON_ERROR_STOP=1"

# -- colours -----------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

total=0
failed=0
skipped=0

run_sql() {
    local label="$1"
    local file="$2"
    local output
    total=$((total + 1))
    if output=$(${PSQL} -f "${file}" 2>&1); then
        echo -e "  ${GREEN}[OK]${NC}   ${label}"
    else
        # Check for idempotent-safe errors (table/index already exists,
        # duplicate seed rows).  These are expected on re-runs and should
        # not abort the build.
        if echo "${output}" | grep -qiE 'already exists|duplicate key value violates unique constraint'; then
            echo -e "  ${YELLOW}[SKIP]${NC} ${label}  (already exists)"
            skipped=$((skipped + 1))
        else
            echo -e "  ${RED}[FAIL]${NC} ${label}"
            echo -e "  ${RED}Error:${NC}"
            echo "${output}" | sed 's/^/         /'
            failed=$((failed + 1))
            echo -e "  ${RED}Aborting — fix the above error before continuing.${NC}"
            exit 1
        fi
    fi
}

# ── Existence-gated table creation / seeding ────────────────
# Same deterministic model as render_build.sh (Version 3.0,
# 2026-10-05): "only genuinely new tables are ever created or
# seeded; a table that already exists is never dropped,
# re-created, or re-seeded, so its local data is never touched."
#
# PREEXISTING_LIST is a space-delimited list of table names that
# were already present at the START of this run (bash 3.2 —
# Apple's stock /bin/bash — has no associative arrays, so this
# avoids `declare -A`, which fails with "invalid option" there).
# A pre-existing table has its DDL AND its seed skipped. A table
# absent at start is created, then seeded exactly once.
PREEXISTING_LIST=" "

mark_preexisting() {
    PREEXISTING_LIST="${PREEXISTING_LIST}$1 "
}

is_preexisting() {
    case "${PREEXISTING_LIST}" in
        *" $1 "*) return 0 ;;
        *)        return 1 ;;
    esac
}

# Deterministic catalog check (no error-string guessing).
# to_regclass returns the OID (non-NULL) iff the relation exists.
table_exists() {
    local t="$1" res
    res=$(${PSQL} -tA -c "SELECT to_regclass('nss.${t}') IS NOT NULL;" 2>/dev/null | tr -d '[:space:]')
    [ "${res}" = "t" ]
}

# Create a table only if it does not already exist.
#   run_ddl <label> <table_name> <ddl_file>
#
# CAVEAT — existence-gating is per-TABLE, not per-COLUMN or
# per-CONSTRAINT. If the table is already present its DDL is skipped
# wholesale; there is no "the DDL file changed, re-apply it" detection.
# So editing a column or a CHECK in an existing table's DDL has NO
# effect on a re-run of this script — the live table keeps its old
# shape indefinitely. Only a hard rebuild (01_drop.sh / DROP SCHEMA nss
# CASCADE, then this script) picks such a change up. Same behaviour as
# render_build.sh; see the long caveat block there and
# docs/03_Solution/architecture/GETTING_STARTED.md §7a-2 "Incremental
# Rebuild is NOT enough".
#
# Known instances as of 2026-10-09:
#   - 08_governance/06_election.sql — new election_type column +
#     chk_election_type + chk_election_nomination_mode_no_voting. The
#     API SELECTs and INSERTs election_type, so an existing database
#     that skips this DDL fails every election endpoint with
#     'column "election_type" does not exist'. Hard rebuild required.
#   - 07_administration/02_admin_scope.sql — widened
#     chk_admin_scope_org_consistency.
# Added 2026-10-21:
#   - 08_governance/01_body_type_master.sql — new max_members column +
#     chk_body_type_master_max_members. An existing database that
#     skips this DDL never gets the column, so the seat-count
#     backstop triggers (12_governance_seat_limits.sql) always treat
#     every body type as uncapped at the DB level (max_members reads
#     NULL) until a hard rebuild. The API-layer _COMPOSITION_RULES
#     checks are unaffected either way. Hard rebuild required.
#   - 01_foundation/11_city_village.sql, 12_postal_code.sql,
#     13_post_office.sql — new submitted_by_person_pk column (+ its
#     Phase 7b FK to nss.person, Registration-Time Geography Creation).
#     An existing database that skips this DDL never gets the column.
#     Unlike the max_members case above, this is NOT a silent no-op:
#     api/routers/registration.py now always calls resolve_or_create_*
#     with pending_submitter_person_pk set, and the SQL INSERT built
#     when that's non-None names the column explicitly — so on an
#     un-rebuilt DB, every self-registration that creates a genuinely
#     new city_village/postal_code/post_office row 500s with "column
#     submitted_by_person_pk does not exist" (mirrors the election_type
#     case). Hard rebuild required.
run_ddl() {
    local label="$1" table="$2" file="$3"
    echo -e "  ${CYAN}[CHECK]${NC} ${label}  (nss.${table}) ..."
    if table_exists "${table}"; then
        mark_preexisting "${table}"
        total=$((total + 1))
        skipped=$((skipped + 1))
        echo -e "  ${YELLOW}[EXISTS]${NC} ${label}  (nss.${table} already present — DDL + seed skipped, local data preserved)"
        return 0
    fi
    echo -e "  ${GREEN}[NEW]${NC}  ${label}  (nss.${table} absent — creating)"
    run_sql "${label}" "${file}"
}

# Seed a table ONLY if it was newly created in this run.
#   run_seed <label> <target_table> <seed_file>
run_seed() {
    local label="$1" table="$2" file="$3"
    if is_preexisting "${table}"; then
        total=$((total + 1))
        skipped=$((skipped + 1))
        echo -e "  ${YELLOW}[SKIP]${NC} ${label}  (nss.${table} pre-existed — seed skipped, local data preserved)"
        return 0
    fi
    run_sql "${label}" "${file}"
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
run_ddl "role_master"       "role_master"       "${DDL_BASE}/00_bootstrap/01_role_master.sql"
run_ddl "permission_master" "permission_master" "${DDL_BASE}/00_bootstrap/02_permission_master.sql"
run_ddl "role_permission"   "role_permission"   "${DDL_BASE}/00_bootstrap/03_role_permission.sql"
echo ""

echo -e "${CYAN}[Phase 0] Bootstrap RBAC — Seed${NC}"
run_seed "permission_master (seed)" "permission_master" "${SEED_BASE}/00_bootstrap/01_permission_master.sql"
run_seed "role_master (seed)"       "role_master"       "${SEED_BASE}/00_bootstrap/02_role_master.sql"
run_seed "role_permission (seed)"   "role_permission"   "${SEED_BASE}/00_bootstrap/03_role_permission.sql"
echo ""

# -------------------------------------------------
# Phase 1: Foundation DDL (14 tables, Depths 0–3)
# Note: festival_master/festival_calendar_date (16/17)
#       are file-numbered after system_event_log/
#       audit_trigger (14/15) but are created here, in
#       Phase 1, so the Phase 14 audit trigger (which
#       enumerates pg_tables at execution time) still
#       attaches to them.
# -------------------------------------------------
echo -e "${CYAN}[Phase 1] Foundation — DDL (14 tables)${NC}"
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
    "postal_code|12_postal_code.sql"
    "post_office|13_post_office.sql"
    "city_village|11_city_village.sql"
    "festival_master|16_festival_master.sql"
    "festival_calendar_date|17_festival_calendar_date.sql"
)
for entry in "${FOUNDATION_DDL[@]}"; do
    label="${entry%%|*}"
    file="${entry##*|}"
    run_ddl "${label}" "${label}" "${DDL_BASE}/01_foundation/${file}"
done
echo ""

# -------------------------------------------------
# Phase 2: Foundation Seed Data
# (includes ORGANIZATION_TYPE + unified STATUS
#  categories and values in master_data)
# -------------------------------------------------
echo -e "${CYAN}[Phase 2] Foundation — Seed Data${NC}"
FOUNDATION_SEED=(
    "master_category (seed)|master_category|01_master_category.sql"
    "master_data (seed)|master_data|02_master_data.sql"
    "id_sequence_master (seed)|id_sequence_master|03_id_sequence_master.sql"
    "country (seed)|country|04_country.sql"
    "state (seed)|state|05_state.sql"
    "district (seed)|district|06_district.sql"
    "system_setting (seed)|system_setting|07_system_setting.sql"
    "postal_code (seed)|postal_code|08_postal_code.sql"
    "postal_code bulk (seed)|postal_code|08b_postal_code_bulk.sql"
    "post_office bulk (seed)|post_office|08c_post_office_bulk.sql"
    "festival_calendar (seed)|festival_calendar_date|10_festival_calendar.sql"
    "city_village (seed)|city_village|11_city_village.sql"
    "city_village urban recovery (seed)|city_village|11b_city_village_urban_recovery.sql"
)
for entry in "${FOUNDATION_SEED[@]}"; do
    label="$(echo "${entry}" | cut -d'|' -f1)"
    table="$(echo "${entry}" | cut -d'|' -f2)"
    file="$(echo "${entry}" | cut -d'|' -f3)"
    run_seed "${label}" "${table}" "${SEED_BASE}/01_foundation/${file}"
done
echo ""

# -------------------------------------------------
# Phase 3: Organization DDL (1 table, Depth 1)
# Note: organization_type_master and
#       organization_status_master are retired —
#       type/status now use Foundation master_data.
# -------------------------------------------------
echo -e "${CYAN}[Phase 3] Organization — DDL (1 table + address-restriction trigger + Kumari/Sevak one-per-Sakha trigger)${NC}"
run_ddl "organization"               "organization" "${DDL_BASE}/02_organization/03_organization.sql"
run_sql "organization_address_restriction_trigger" "${DDL_BASE}/02_organization/04_organization_address_restriction_trigger.sql"
run_sql "organization_kumari_sevak_uniqueness_trigger" "${DDL_BASE}/02_organization/05_organization_kumari_sevak_uniqueness_trigger.sql"
echo ""

# -------------------------------------------------
# Phase 4: Organization Seed Data
# -------------------------------------------------
echo -e "${CYAN}[Phase 4] Organization — Seed Data${NC}"
run_seed "organization (seed)"               "organization"       "${SEED_BASE}/02_organization/03_organization.sql"
run_seed "sakha postal codes (seed)"         "postal_code"        "${SEED_BASE}/01_foundation/09_sakha_postal_codes.sql"
run_seed "sakha branches (seed)"             "organization"       "${SEED_BASE}/02_organization/05_sakha_branches.sql"
run_seed "id_sequence_master (org sync)"     "id_sequence_master" "${SEED_BASE}/02_organization/06_id_sequence_org_sync.sql"
echo ""

# -------------------------------------------------
# Phase 5: Person DDL (2 tables, Depths 2–3)
# Note: the superseded 01_person_master_tables.sql
#       DDL/seed were removed 2026-10-01 — dead code,
#       zero references. gender/marital_status/address_type
#       data lives in Foundation master_data seed.
# -------------------------------------------------
echo -e "${CYAN}[Phase 5] Person — DDL (2 tables)${NC}"
run_ddl "person"         "person"         "${DDL_BASE}/03_person/02_person.sql"
run_ddl "person_address" "person_address" "${DDL_BASE}/03_person/03_person_address.sql"
echo ""

# -------------------------------------------------
# Phase 6: Family DDL (6 tables, Depths 2–3)
# Note: family_link stores only direct PARENT_OF/
#       SPOUSE_OF edges; every other relationship
#       label is computed dynamically (BFS traversal
#       in api/services/family_graph.py), not stored.
# -------------------------------------------------
echo -e "${CYAN}[Phase 6] Family — DDL (6 tables + move-transition guard)${NC}"
run_ddl "family_group"              "family_group"              "${DDL_BASE}/04_family/01_family_group.sql"
run_ddl "family_relationship"       "family_relationship"       "${DDL_BASE}/04_family/02_family_relationship.sql"
run_ddl "family_head_history"       "family_head_history"       "${DDL_BASE}/04_family/03_family_head_history.sql"
run_ddl "family_transition_history" "family_transition_history" "${DDL_BASE}/04_family/04_family_transition_history.sql"
run_ddl "family_link"               "family_link"               "${DDL_BASE}/04_family/05_family_link.sql"
run_ddl "family_admin"              "family_admin"              "${DDL_BASE}/04_family/06_family_admin.sql"
run_sql "family_move_transition_guard" "${DDL_BASE}/04_family/07_family_move_transition_guard.sql"
echo ""

# -------------------------------------------------
# Phase 7: Membership DDL (16 tables, Depths 2–4)
# Note: sangha_sevi must be created first — all
#       other membership tables depend on it.
# -------------------------------------------------
echo -e "${CYAN}[Phase 7] Membership — DDL (16 tables + Sakha-only trigger)${NC}"
run_ddl "sangha_sevi"                    "sangha_sevi"                    "${DDL_BASE}/05_membership/01_sangha_sevi.sql"
run_ddl "membership_status_history"      "membership_status_history"      "${DDL_BASE}/05_membership/02_membership_status_history.sql"
run_ddl "membership_renewal_request"     "membership_renewal_request"     "${DDL_BASE}/05_membership/03_membership_renewal_request.sql"
run_ddl "membership_renewal_history"     "membership_renewal_history"     "${DDL_BASE}/05_membership/04_membership_renewal_history.sql"
run_ddl "membership_transfer_history"    "membership_transfer_history"    "${DDL_BASE}/05_membership/05_membership_transfer_history.sql"
run_ddl "membership_sakha_affiliation"   "membership_sakha_affiliation"   "${DDL_BASE}/05_membership/06_membership_sakha_affiliation.sql"
run_ddl "membership_journey_event"       "membership_journey_event"       "${DDL_BASE}/05_membership/07_membership_journey_event.sql"
run_ddl "probationary_member_review"     "probationary_member_review"     "${DDL_BASE}/05_membership/08_probationary_member_review.sql"
run_ddl "parichaya_patra"                "parichaya_patra"                "${DDL_BASE}/05_membership/09_parichaya_patra.sql"
run_ddl "parichaya_patra_history"        "parichaya_patra_history"        "${DDL_BASE}/05_membership/10_parichaya_patra_history.sql"
run_ddl "anumati_patra"                  "anumati_patra"                  "${DDL_BASE}/05_membership/11_anumati_patra.sql"
run_ddl "anumati_patra_history"          "anumati_patra_history"          "${DDL_BASE}/05_membership/12_anumati_patra_history.sql"
run_ddl "darshak_attendance_registration" "darshak_attendance_registration" "${DDL_BASE}/05_membership/13_darshak_attendance_registration.sql"
run_sql "sakha_only_membership_trigger"  "${DDL_BASE}/05_membership/14_sakha_only_membership_trigger.sql"
run_ddl "credential_sequence_counter"    "credential_sequence_counter"    "${DDL_BASE}/05_membership/15_credential_sequence_counter.sql"
run_ddl "sakha_local_number_counter"     "sakha_local_number_counter"     "${DDL_BASE}/05_membership/17_sakha_local_number_counter.sql"
run_ddl "membership_change_request"      "membership_change_request"      "${DDL_BASE}/05_membership/18_membership_change_request.sql"
echo ""

# -------------------------------------------------
# Phase 7b: Deferred Foundation Audit FKs
# Wires the real FK constraints on district/postal_code/
# post_office/city_village's submitted_by/reviewed_by
# columns to sangha_sevi, now that sangha_sevi exists.
# Not a migration — runs every full rebuild against four
# brand-new, empty tables (see file header for the
# circular-dependency rationale).
# -------------------------------------------------
echo -e "${CYAN}[Phase 7b] Deferred Foundation Audit FKs${NC}"
run_sql "foundation_audit_fk" "${DDL_BASE}/05_membership/16_foundation_audit_fk.sql"
echo ""

# -------------------------------------------------
# Phase 8: Tier 4 Verification Seed Data
# Order: Organization → Person → Family → Membership
# (dependency chain respected)
# Phase 8: (Tier 4 test seeds removed — no demo data)
# -------------------------------------------------
echo ""

# -------------------------------------------------
# Phase 9: Grant nss_db_backend read-only access
# Must run AFTER all DDL so GRANT SELECT ON ALL
# TABLES covers every table just created.
# -------------------------------------------------
echo -e "${CYAN}[Phase 9] Grant nss_db_backend read-only access${NC}"
run_sql "grant_backend" "${SCRIPT_DIR}/04_grant_backend.sql"
echo ""

# -------------------------------------------------
# Phase 10: Authentication DDL (5 tables, Depths 3–5)
# user_account FK → person (Depth 3)
# password_history FK → user_account (Depth 4)
# registration_claim FK → user_account, person, organization, master_data (Depth 5)
# password_reset_token FK → user_account (Depth 4)
# user_session FK → user_account (Depth 4)
# -------------------------------------------------
echo -e "${CYAN}[Phase 10] Authentication — DDL (5 tables)${NC}"
run_ddl "user_account"           "user_account"         "${DDL_BASE}/06_authentication/01_user_account.sql"
run_ddl "password_history"       "password_history"     "${DDL_BASE}/06_authentication/02_password_history.sql"
run_ddl "registration_claim"     "registration_claim"   "${DDL_BASE}/06_authentication/03_registration_claim.sql"
run_ddl "password_reset_token"   "password_reset_token" "${DDL_BASE}/06_authentication/04_password_reset_token.sql"
run_ddl "user_session"           "user_session"         "${DDL_BASE}/06_authentication/05_user_session.sql"
echo ""

# -------------------------------------------------
# Phase 11: Administration DDL (2 tables, Depths 4–5)
# user_role FK → user_account + role_master (Depth 4)
# admin_scope FK → user_role + organization (Depth 5)
# -------------------------------------------------
echo -e "${CYAN}[Phase 11] Administration — DDL (2 tables)${NC}"
run_ddl "user_role"    "user_role"   "${DDL_BASE}/07_administration/01_user_role.sql"
run_ddl "admin_scope"  "admin_scope" "${DDL_BASE}/07_administration/02_admin_scope.sql"
echo ""

# -------------------------------------------------
# Phase 11b: Governance DDL (9 tables, Tier 6, Depths 0–6)
# Unified Body Governance Model (GOV-BR-004).
# Depends only on body_type_master/position_master (Depth 0),
# organization, person, sangha_sevi — all created in earlier
# phases — so it slots in after Administration and before the
# writer grant, letting Phase 12 GRANT ON ALL TABLES and
# Phase 14 attach the audit trigger to these tables too.
#   body_type_master, position_master       (Depth 0)
#   body_master                              (Depth 4)
#   body_member_assignment,
#   acting_position_assignment, election     (Depth 5)
#   election_nomination, election_vote,
#   election_result                          (Depth 6)
# -------------------------------------------------
echo -e "${CYAN}[Phase 11b] Governance — DDL (10 tables + ballot immutability + seat-count limits)${NC}"
run_ddl "body_type_master"           "body_type_master"           "${DDL_BASE}/08_governance/01_body_type_master.sql"
run_ddl "position_master"            "position_master"            "${DDL_BASE}/08_governance/02_position_master.sql"
run_ddl "body_master"                "body_master"                "${DDL_BASE}/08_governance/03_body_master.sql"
run_ddl "body_member_assignment"     "body_member_assignment"     "${DDL_BASE}/08_governance/04_body_member_assignment.sql"
run_ddl "acting_position_assignment" "acting_position_assignment" "${DDL_BASE}/08_governance/05_acting_position_assignment.sql"
run_ddl "election"                   "election"                   "${DDL_BASE}/08_governance/06_election.sql"
run_ddl "election_nomination"        "election_nomination"        "${DDL_BASE}/08_governance/07_election_nomination.sql"
run_ddl "election_vote"              "election_vote"              "${DDL_BASE}/08_governance/08_election_vote.sql"
run_ddl "election_result"            "election_result"            "${DDL_BASE}/08_governance/09_election_result.sql"
run_ddl "election_vote_participation" "election_vote_participation" "${DDL_BASE}/08_governance/10_election_vote_participation.sql"
# Ballot immutability: function + BEFORE UPDATE triggers on
# election_vote and election_vote_participation. Not a table —
# run_sql (CREATE OR REPLACE / DROP..CREATE TRIGGER are idempotent).
run_sql "governance_immutability"    "${DDL_BASE}/08_governance/11_governance_immutability.sql"
# Seat-count backstop: two functions + BEFORE INSERT OR UPDATE
# triggers on body_member_assignment (flat per-body cap +
# Advisory Board one-seat-per-Sakha). Not a table — run_sql, same
# as governance_immutability above. NOTE: the companion
# body_type_master.max_members column (01_body_type_master.sql)
# and its seed UPDATE (seed/08_governance/01_body_type_master.sql)
# are existence-gated by run_ddl/run_seed above and will NOT reach
# an already-bootstrapped nss.body_type_master without a full hard
# rebuild — see the CAVEAT above run_ddl().
run_sql "governance_seat_limits"     "${DDL_BASE}/08_governance/12_governance_seat_limits.sql"
echo ""

# -------------------------------------------------
# Phase 11c: Governance — Seed Data
# Starter catalogues for the two Depth-0 masters (body_type_master,
# position_master), plus the 3 NSS-wide singleton body_master rows
# (Kendra Governing Body, Advisory Board, central Mahila Parichalana
# Mandali) that are auto-created here rather than through the Add Body
# UI — only seeded if the table was newly created above, same
# existence-gated pattern as every other seed in this script.
# -------------------------------------------------
echo -e "${CYAN}[Phase 11c] Governance — Seed Data${NC}"
run_seed "body_type_master (seed)" "body_type_master" "${SEED_BASE}/08_governance/01_body_type_master.sql"
run_seed "position_master (seed)"  "position_master"  "${SEED_BASE}/08_governance/02_position_master.sql"
run_seed "body_master (seed)"      "body_master"       "${SEED_BASE}/08_governance/03_body_master.sql"
echo ""

# -------------------------------------------------
# Phase 11d: Correspondence DDL (5 tables, Tier 6, Depths 1-5)
# correspondence FK -> person, organization, master_data (Depth 4)
# correspondence_document FK -> correspondence, document_master (Depth 5)
# correspondence_finance_reference FK -> correspondence only in Pass 1;
#   financial_transaction FK deferred to Pass 2 (Finance/Tier 12 not
#   yet built) per SOL-ADMIN-009 §6.8/§7.2.
# correspondence_sequence_counter FK -> organization only (Depth 1);
#   backs api/helpers.py::next_correspondence_reference_number()
#   (CORR-EXT-001).
# correspondence_approval_step FK -> correspondence, person,
#   position_master, organization (Depth 5) — additive Sakha-President
#   ->Kendra-office-bearer approval-chain overlay for the member
#   dashboard's "Send Application" feature (owner request, 2026-10-21);
#   placed last so it can FK to position_master from Phase 11b/11c.
# Administration-owned capability; moved from Tier 5 to Tier 6
# (owner-confirmed 2026-10-16) since Tier 5 (v0.11.0) already shipped
# without it. Placed after Governance so Phase 12's writer grant and
# Phase 14's audit trigger both cover these tables too.
# -------------------------------------------------
echo -e "${CYAN}[Phase 11d] Correspondence — DDL (5 tables)${NC}"
run_ddl "correspondence"                   "correspondence"                   "${DDL_BASE}/09_correspondence/01_correspondence.sql"
run_ddl "correspondence_document"          "correspondence_document"          "${DDL_BASE}/09_correspondence/02_correspondence_document.sql"
run_ddl "correspondence_finance_reference" "correspondence_finance_reference" "${DDL_BASE}/09_correspondence/03_correspondence_finance_reference.sql"
run_ddl "correspondence_sequence_counter"  "correspondence_sequence_counter"  "${DDL_BASE}/09_correspondence/04_correspondence_sequence_counter.sql"
run_ddl "correspondence_approval_step"     "correspondence_approval_step"     "${DDL_BASE}/09_correspondence/05_correspondence_approval_step.sql"
echo ""

# -------------------------------------------------
# Phase 11e: Attendance DDL (4 tables, Tier 6, owner-confirmed 2026-10-27)
# weekly_sangha_puja FK -> organization (Depth 1)
# weekly_sangha_puja_attendance FK -> weekly_sangha_puja, sangha_sevi,
#   master_data (ATTENDANCE_STATUS, seeded in Foundation/Phase 1),
#   organization (Depth 2)
# attendance_exception FK -> sangha_sevi, master_data
#   (ATTENDANCE_EXCEPTION_TYPE) (Depth 2)
# attendance_review FK -> sangha_sevi, organization, master_data
#   (ATTENDANCE_REVIEW_STATUS) (Depth 3)
# Placed after Governance/Correspondence so Phase 12's writer grant and
# Phase 14's audit trigger both cover these tables too, same reasoning
# as Phase 11b/11d.
# -------------------------------------------------
echo -e "${CYAN}[Phase 11e] Attendance — DDL (4 tables)${NC}"
run_ddl "weekly_sangha_puja"            "weekly_sangha_puja"            "${DDL_BASE}/10_attendance/01_weekly_sangha_puja.sql"
run_ddl "weekly_sangha_puja_attendance" "weekly_sangha_puja_attendance" "${DDL_BASE}/10_attendance/02_weekly_sangha_puja_attendance.sql"
run_ddl "attendance_exception"          "attendance_exception"          "${DDL_BASE}/10_attendance/03_attendance_exception.sql"
run_ddl "attendance_review"             "attendance_review"             "${DDL_BASE}/10_attendance/04_attendance_review.sql"
echo ""

# -------------------------------------------------
# Phase 12: Grant nss_db_writer write access (Tier 5)
# Must run AFTER Auth + Admin DDL so the tables exist.
# Grants SELECT on ALL tables (login lookups) +
# INSERT/UPDATE on ALL nss tables, incl. future ones
# (no DELETE, no DDL).
# -------------------------------------------------
echo -e "${CYAN}[Phase 12] Grant nss_db_writer write access${NC}"
run_sql "create_writer_role" "${SCRIPT_DIR}/05_create_writer_role.sql"
echo ""

# -------------------------------------------------
# Phase 13: Admin Bootstrap Seed
# Seeds NSS Admin superuser (P1 / SS1 / Admin@123)
# with NSS_ERP_ADMIN role and NSS-WIDE scope.
# Must run AFTER Auth + Admin DDL (Phases 10–11)
# and AFTER Foundation + Organization seeds.
#
# Uses the Python bootstrap script (not psql) because
# the user_account INSERT requires an Argon2 password
# hash generated at runtime.
# -------------------------------------------------
echo -e "${CYAN}[Phase 13] Admin Bootstrap Seed${NC}"
total=$((total + 1))
if output=$(python3 "${REPO_ROOT}/scripts/bootstrap_admin.py" 2>&1); then
    echo -e "  ${GREEN}[OK]${NC}   admin_bootstrap"
else
    echo -e "  ${RED}[FAIL]${NC} admin_bootstrap"
    echo "  Error: ${output}"
    failed=$((failed + 1))
fi
echo ""

# -------------------------------------------------
# Phase 13b: Geo Attribution Backfill (Bulk-Reference-Seeded Rows)
# Registration-Time Geography Creation (2026-10-21) added
# submitted_by_person_pk to city_village/postal_code/post_office
# (district is out of scope — never auto-created at registration).
# The ~614K city_village and ~17.8K postal_code rows the Phase 2
# Foundation seed bulk-loads have no submitter (nobody "submitted"
# them via the app) — backfill them to point at the NSS Admin's
# person_pk (P1) for attribution consistency, instead of leaving
# them NULL forever.
#
# Must run AFTER Phase 13: P1's person row does not exist until the
# admin bootstrap above creates it (Phase 2's bulk geo seed runs 11
# phases earlier, before person/sangha_sevi exist at all — a genuine
# build-order constraint, not an oversight).
#
# Idempotent and safe to re-run: only touches rows where
# submitted_by_person_pk IS NULL, and the submitted_by_sangha_sevi_pk
# IS NULL guard means a real member-proposed or registration-origin
# submitter is never overwritten (those paths always set one or the
# other, never leave both NULL). If P1 does not exist for any reason,
# the subquery returns NULL and the UPDATE is a harmless no-op.
# -------------------------------------------------
echo -e "${CYAN}[Phase 13b] Geo Attribution Backfill (bulk-seeded rows -> P1)${NC}"
total=$((total + 1))
if output=$(${PSQL} -c "
    UPDATE nss.city_village SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
    UPDATE nss.postal_code SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
    UPDATE nss.post_office SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
" 2>&1); then
    echo -e "  ${GREEN}[OK]${NC}   geo_attribution_backfill"
    echo "${output}" | sed 's/^/  /'
elif echo "${output}" | grep -qiE 'column .* does not exist'; then
    # Existing-table DDL change (submitted_by_person_pk) was skipped by an
    # incremental build against an already-bootstrapped city_village/
    # postal_code/post_office — same existence-gating caveat as every
    # other existing-table column add in this script. Not fatal: SKIP,
    # not FAIL, so this step alone never aborts the whole build/deploy.
    echo -e "  ${YELLOW}[SKIP]${NC} geo_attribution_backfill  (submitted_by_person_pk column absent — needs a full hard rebuild)"
    skipped=$((skipped + 1))
else
    echo -e "  ${RED}[FAIL]${NC} geo_attribution_backfill"
    echo "  Error: ${output}"
    failed=$((failed + 1))
fi
echo ""

# -------------------------------------------------
# Phase 14: Audit DDL (system_event_log + DB trigger)
# Must run AFTER all other DDL so the trigger can
# attach to every table in the nss schema.
# -------------------------------------------------
echo -e "${CYAN}[Phase 14] Audit — DDL (1 table + trigger)${NC}"
run_ddl "system_event_log"  "system_event_log" "${DDL_BASE}/01_foundation/14_system_event_log.sql"
run_sql "audit_trigger"     "${DDL_BASE}/01_foundation/15_audit_trigger.sql"
echo ""

# -------------------------------------------------
# Phase 15 (OPTIONAL): Demo / test seed — LOCAL DEV ONLY.
# Gitignored (database/seed/demo/), so absent from clean clones and
# never on Render. Runs ONLY when RUN_DEMO_SEED is truthy AND the file
# is present; otherwise skipped silently. Runs AFTER the audit trigger
# so demo rows are audited like any real insert. NOT mirrored into
# render_build.sh — demo data must never land in a deployed environment.
# -------------------------------------------------
DEMO_SEED_FILE="${SEED_BASE}/demo/nss_demo_seed.sql"
case "$(printf '%s' "${RUN_DEMO_SEED:-}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')" in
    true|1|yes|on)
        if [ -f "${DEMO_SEED_FILE}" ]; then
            echo -e "${CYAN}[Phase 15] Demo / test seed (RUN_DEMO_SEED set)${NC}"
            run_sql "demo_seed" "${DEMO_SEED_FILE}"
            echo ""
        else
            echo -e "${YELLOW}[Phase 15] RUN_DEMO_SEED set but ${DEMO_SEED_FILE} not found — skipped.${NC}"
            echo ""
        fi
        ;;
    *)
        : # demo seed not requested — skip silently
        ;;
esac

# -------------------------------------------------
# Summary
# -------------------------------------------------
echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN}  BUILD SUMMARY${NC}"
echo -e "${CYAN}=============================================${NC}"
echo -e "  Scripts executed: ${total}"
echo -e "  Skipped:          ${skipped}  (already existed)"
echo -e "  Failed:           ${failed}"
echo ""

if [ "$failed" -eq 0 ]; then
    echo -e "  ${GREEN}Database build completed successfully.${NC}"
    echo ""
    echo -e "  ${YELLOW}Not executed (future phases):${NC}"
    echo "    - Pass 2 audit-actor FK constraints"
    exit 0
else
    echo -e "  ${RED}Database build FAILED (${failed} errors).${NC}"
    exit 1
fi
