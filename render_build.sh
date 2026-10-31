#!/usr/bin/env bash
# ==========================================================
# render_build.sh — Render.com build script
# ==========================================================
#
# Runs on every deploy. Installs Python dependencies, and —
# ONLY when explicitly requested — bootstraps the PostgreSQL
# database (DDL + seed).
#
# RUN_DB_BOOTSTRAP (decided 2026-10-05, corrected 2026-10-05):
# gates ONLY the Phase 13 NSSAdmin seed step (scripts/bootstrap_admin.py),
# not the DDL/seed phases. Everything else (Phase 0-12, 14) always runs,
# idempotently (skip-on-exists) — same as database/scripts/02_build.sh —
# so a routine deploy safely picks up any DDL/seed added since the last
# deploy (e.g. a new table like user_session) without needing to drop
# and recreate anything.
#
# An earlier version of this script wrapped the entire DDL+seed bootstrap
# (every phase) behind this flag with a single `exit 0` gate at the top.
# That was wrong: setting RUN_DB_BOOTSTRAP=false to skip re-seeding the
# admin account also silently skipped all DDL, including newly-added
# tables (e.g. user_session never got created), and because the flag
# defaults to false, every subsequent deploy became a complete no-op
# that still reported a clean build. Fixed by moving the gate down to
# wrap only the Phase 13 call.
#
# Existence-gated bootstrap (Version 3.0, 2026-10-05) —
# "only genuinely new tables are ever created or seeded; a
# table that already exists is never dropped, re-created, or
# re-seeded, so its live data is never touched."
#
# Before this version the build relied on error-string matching
# (catch "already exists" / "duplicate key" and SKIP). That is
# fragile: it depends on the exact wording of Postgres errors and
# cannot distinguish "this seed row already exists" from "this
# seed would have overwritten/changed live data". It replaces it
# with a deterministic catalog check: for every business table we
# ask the Postgres catalog -- to_regclass('nss.<table>') -- whether
# the table exists BEFORE doing anything.
#
#   table EXISTS  -> skip its DDL *and* its seed entirely.
#                    Live data is never read or written.
#   table ABSENT  -> create it (run DDL), then run its seed.
#                    This is the only path that writes seed data.
#
# A redeploy against the current live DB therefore reports
# [EXISTS] skip for every table that is already there, and only
# creates the genuinely new ones (e.g. user_session) — with zero
# risk to existing rows.
#
# CAVEAT — existence-gating is per-TABLE, not per-ROW or per-CONSTRAINT.
# A routine redeploy only ever adds genuinely NEW tables. If a table
# already exists, its DDL AND its seed are skipped wholesale — this
# build has no "content changed, re-apply it" detection. Concretely,
# for the 2026-10-09 §63 composite auto-grant rule changes:
#   - database/seed/00_bootstrap/02_role_master.sql (v1.3, +1 row:
#     NSS_ERP_ADVISORY_BOARD_ADMIN) will NOT be inserted on any
#     environment where role_master already exists.
#   - database/seed/08_governance/01_body_type_master.sql (v1.1, +3
#     rows: ANCHALIKA_GOVERNING_BODY, ZILLA_GOVERNING_BODY,
#     PATHA_CHAKRA_GOVERNING_BODY) will NOT be inserted on any
#     environment where body_type_master already exists.
#   - database/ddl/07_administration/02_admin_scope.sql (v1.1, widened
#     chk_admin_scope_org_consistency CHECK to also exempt KENDRA /
#     KENDRA_MAHILA_SANGHA) will NOT be applied on any environment
#     where admin_scope already exists — the table keeps its OLD
#     constraint indefinitely.
# and for the 2026-10-09 nomination-vs-election mode change:
#   - database/ddl/08_governance/06_election.sql (added the
#     election_type column plus chk_election_type and
#     chk_election_nomination_mode_no_voting) will NOT be applied on
#     any environment where election already exists. Because the API
#     now SELECTs and INSERTs election_type, an environment that skips
#     this DDL will fail on every election read/write with
#     'column "election_type" does not exist' — this one is not a
#     silent no-op, it breaks the governance module outright.
# and for the 2026-10-21 DB-level governance seat-count backstop:
#   - database/ddl/08_governance/01_body_type_master.sql (added the
#     max_members column plus chk_body_type_master_max_members) will
#     NOT be applied on any environment where body_type_master already
#     exists.
#   - database/seed/08_governance/01_body_type_master.sql (added an
#     UPDATE setting max_members for the 6 fixed-count body types) will
#     NOT run either, since run_seed skips a pre-existing table's seed
#     wholesale.
#   - Net effect on a routine redeploy: nss.fn_enforce_body_seat_limit()
#     (database/ddl/08_governance/12_governance_seat_limits.sql, wired
#     below via run_sql so the trigger functions themselves DO get
#     (re)attached every run) will see max_members IS NULL for every
#     body type and silently enforce NOTHING beyond the
#     MAHILA_PARICHALANA_MANDALI/ADVISORY_BOARD special cases, which are
#     derived independently of this column. This is a silent
#     under-enforcement, not a crash — the existing API-layer
#     _COMPOSITION_RULES checks in api/routers/governance.py remain the
#     primary, unaffected guard either way. Only a full hard rebuild
#     makes the DB-level flat-count backstop active for
#     KENDRA_GOVERNING_BODY / SAKHA_GOVERNING_BODY / SEVAK_SANGHA_EXECUTIVE
#     / ANCHALIKA_GOVERNING_BODY / ZILLA_GOVERNING_BODY /
#     PATHA_CHAKRA_GOVERNING_BODY.
# and for the 2026-10-21 Registration-Time Geography Creation feature:
#   - database/ddl/01_foundation/11_city_village.sql, 12_postal_code.sql,
#     13_post_office.sql (added submitted_by_person_pk + its Phase 7b FK
#     to nss.person) will NOT be applied on any environment where those
#     tables already exist. Unlike the max_members case, this is NOT a
#     silent no-op: api/routers/registration.py always calls
#     resolve_or_create_city_village/postal_code/post_office with
#     pending_submitter_person_pk set, and the INSERT built when that's
#     non-None names the column explicitly — so on an un-rebuilt
#     environment, every self-registration that creates a genuinely new
#     geo row 500s with "column submitted_by_person_pk does not exist"
#     (mirrors the election_type case). The new Phase 13b backfill step
#     below tolerates this specific condition itself (SKIP, not FAIL, on
#     a "column ... does not exist" error) so a routine redeploy against
#     an un-rebuilt environment is not additionally broken by this step —
#     but the registration 500s above still require a full hard rebuild
#     to fix.
# This is "expected" per this project's no-migrations, hard-rebuild
# methodology, but it means a routine Render redeploy will silently
# NOT pick up any of the changes above. Only a full hard rebuild
# (DROP SCHEMA nss CASCADE, then rebuild from scratch) does. See
# docs/03_Solution/architecture/GETTING_STARTED.md §7a-2 "Incremental
# Rebuild is NOT enough".
#
# Non-table objects (schema, extensions, triggers, functions,
# deferred FK wiring, GRANTs, role creation) stay on run_sql():
# they are independently idempotent (CREATE OR REPLACE, DROP
# TRIGGER IF EXISTS + CREATE, IF NOT EXISTS, additive GRANTs) and
# carry no business data, so re-running them is always safe. The
# Phase 14 audit-trigger DO block in particular re-scans the nss
# schema on every run and (re)attaches the audit trigger to EVERY
# table present — including any table newly created this run.
#
# Database: Neon.dev (per TECH_STACK_DECISIONS.md §1)
# App host: Render.com (per TECH_STACK_DECISIONS.md §2)
#
# Required env vars (set in Render dashboard):
#   DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
#   DB_WRITE_USER, DB_WRITE_PASSWORD (Tier 5 nss_db_writer pool)
#   JWT_SECRET_KEY (Tier 5 auth)
#   RUN_DB_BOOTSTRAP (optional; truthy = true/1/yes/on, case-
#                     insensitive, whitespace-tolerant; default: skipped)
#
# Keep phase order in sync with database/scripts/02_build.sh
# if it changes.
# ==========================================================

set -euo pipefail

echo "=== Building Tailwind CSS (tree-shaken + DaisyUI) ==="
npm install
npx tailwindcss -i frontend/assets/css/tailwind-input.css -o frontend/assets/css/tailwind.min.css --minify

echo ""
echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo ""
# Normalise the flag so Render-dashboard values like "True", "TRUE",
# " true" (stray space), "1", "yes", "on" all count — the earlier
# exact "== true" check silently skipped on any of those. Lowercase +
# strip all whitespace, then match a small set of truthy spellings.
# Only consumed down at Phase 13 (NSSAdmin seed) — does NOT gate DDL/seed.
echo "=== RUN_DB_BOOTSTRAP raw value: '${RUN_DB_BOOTSTRAP:-<unset>}' ==="
RUN_DB_BOOTSTRAP_NORM="$(printf '%s' "${RUN_DB_BOOTSTRAP:-false}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
case "${RUN_DB_BOOTSTRAP_NORM}" in
    true|1|yes|on) RUN_BOOTSTRAP=1 ;;
    *)             RUN_BOOTSTRAP=0 ;;
esac

echo "=== Bootstrapping database (Neon.dev) ==="

# Neon uses standard PostgreSQL wire protocol — psql works directly.
export PGPASSWORD="${DB_PASSWORD}"
PSQL="psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -v ON_ERROR_STOP=1"

# Neon requires SSL
export PGSSLMODE="require"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DDL_BASE="${REPO_ROOT}/database/ddl"
SEED_BASE="${REPO_ROOT}/database/seed"

run_sql() {
    local label="$1"
    local file="$2"
    local output
    if output=$(${PSQL} -f "${file}" 2>&1); then
        echo "  [OK]   ${label}"
    else
        # Idempotent-safe errors (table/index already exists, duplicate
        # seed rows) are expected on re-runs and should not abort the
        # build — matches database/scripts/02_build.sh's behaviour.
        if echo "${output}" | grep -qiE 'already exists|duplicate key value violates unique constraint'; then
            echo "  [SKIP] ${label}  (already exists)"
        else
            echo "  [FAIL] ${label}"
            echo "${output}" | sed 's/^/         /'
            exit 1
        fi
    fi
}

# ── Existence-gated table creation / seeding ────────────────
# PREEXISTING_LIST is a space-delimited list of table names that
# were already present in the database at the START of this run
# (bash 3.2 — Apple's stock /bin/bash, in case this script is ever
# run locally too — has no associative arrays, so this avoids
# `declare -A`, which fails with "invalid option" there). A
# pre-existing table has its DDL AND its seed skipped — its live
# data is never touched. A table absent at start is created and
# then seeded exactly once.
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
# If the table exists we record it in PREEXISTING_LIST (so run_seed
# skips its seed too) and do nothing. Otherwise we create it.
run_ddl() {
    local label="$1" table="$2" file="$3"
    echo "  [CHECK] ${label}  (nss.${table}) ..."
    if table_exists "${table}"; then
        mark_preexisting "${table}"
        echo "  [EXISTS] ${label}  (nss.${table} already present — DDL + seed skipped, live data preserved)"
        return 0
    fi
    echo "  [NEW]  ${label}  (nss.${table} absent — creating)"
    run_sql "${label}" "${file}"
}

# Seed a table ONLY if it was newly created in this run.
#   run_seed <label> <target_table> <seed_file>
# A pre-existing target table keeps its live data untouched; its
# seed never runs. A freshly-created table is seeded exactly once.
run_seed() {
    local label="$1" table="$2" file="$3"
    if is_preexisting "${table}"; then
        echo "  [SKIP] ${label}  (nss.${table} pre-existed — seed skipped, live data preserved)"
        return 0
    fi
    run_sql "${label}" "${file}"
}

echo "--- Creating nss schema ---"
${PSQL} -c "CREATE SCHEMA IF NOT EXISTS nss;"
${PSQL} -c "ALTER DATABASE ${DB_NAME} SET search_path TO nss, public;"
${PSQL} -c "SET search_path TO nss, public;"

echo "--- Installing extensions (best-effort) ---"
${PSQL} -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" 2>/dev/null || echo "  pgcrypto not available — skipping"
${PSQL} -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" 2>/dev/null || echo "  pg_trgm not available — skipping"
${PSQL} -c "CREATE EXTENSION IF NOT EXISTS btree_gin;" 2>/dev/null || echo "  btree_gin not available — skipping"

echo ""
echo "--- Phase 0: Bootstrap RBAC — DDL ---"
run_ddl "role_master"       "role_master"       "${DDL_BASE}/00_bootstrap/01_role_master.sql"
run_ddl "permission_master" "permission_master" "${DDL_BASE}/00_bootstrap/02_permission_master.sql"
run_ddl "role_permission"   "role_permission"   "${DDL_BASE}/00_bootstrap/03_role_permission.sql"

echo "--- Phase 0: Bootstrap RBAC — Seed ---"
run_seed "permission_master (seed)" "permission_master" "${SEED_BASE}/00_bootstrap/01_permission_master.sql"
run_seed "role_master (seed)"       "role_master"       "${SEED_BASE}/00_bootstrap/02_role_master.sql"
run_seed "role_permission (seed)"   "role_permission"   "${SEED_BASE}/00_bootstrap/03_role_permission.sql"
# Idempotent patch: the seed above is existence-gated, so rows added to it later
# (Mahila admin 15->18, Advisory Board admin 0->7, 2026-10-30) reach existing DBs here.
run_sql "role_permission mahila/advisory-board patch" "${SEED_BASE}/00_bootstrap/04_role_permission_mahila_advisory_board_patch.sql"

echo ""
echo "--- Phase 1: Foundation — DDL (14 tables) ---"
run_ddl "master_category"                "master_category"        "${DDL_BASE}/01_foundation/02_master_category.sql"
run_ddl "system_setting"                 "system_setting"         "${DDL_BASE}/01_foundation/03_system_setting.sql"
run_ddl "id_sequence_master"             "id_sequence_master"     "${DDL_BASE}/01_foundation/04_id_sequence_master.sql"
run_ddl "country"                        "country"                "${DDL_BASE}/01_foundation/05_country.sql"
run_ddl "document_master"                "document_master"        "${DDL_BASE}/01_foundation/06_document_master.sql"
run_ddl "field_change_log"               "field_change_log"       "${DDL_BASE}/01_foundation/07_field_change_log.sql"
run_ddl "master_data"                    "master_data"            "${DDL_BASE}/01_foundation/08_master_data.sql"
run_ddl "state"                          "state"                  "${DDL_BASE}/01_foundation/09_state.sql"
run_ddl "district"                       "district"               "${DDL_BASE}/01_foundation/10_district.sql"
run_ddl "postal_code"                    "postal_code"            "${DDL_BASE}/01_foundation/12_postal_code.sql"
run_ddl "post_office"                    "post_office"            "${DDL_BASE}/01_foundation/13_post_office.sql"
run_ddl "city_village"                   "city_village"           "${DDL_BASE}/01_foundation/11_city_village.sql"
run_ddl "festival_master"                "festival_master"        "${DDL_BASE}/01_foundation/16_festival_master.sql"
run_ddl "festival_calendar_date"         "festival_calendar_date" "${DDL_BASE}/01_foundation/17_festival_calendar_date.sql"

echo ""
echo "--- Phase 2: Foundation — Seed ---"
run_seed "master_category (seed)"    "master_category"    "${SEED_BASE}/01_foundation/01_master_category.sql"
run_seed "master_data (seed)"        "master_data"        "${SEED_BASE}/01_foundation/02_master_data.sql"
run_seed "id_sequence_master (seed)" "id_sequence_master" "${SEED_BASE}/01_foundation/03_id_sequence_master.sql"
run_seed "country (seed)"            "country"            "${SEED_BASE}/01_foundation/04_country.sql"
run_seed "state (seed)"              "state"              "${SEED_BASE}/01_foundation/05_state.sql"
run_seed "district (seed)"           "district"           "${SEED_BASE}/01_foundation/06_district.sql"
run_seed "system_setting (seed)"     "system_setting"     "${SEED_BASE}/01_foundation/07_system_setting.sql"
run_seed "postal_code (seed)"        "postal_code"        "${SEED_BASE}/01_foundation/08_postal_code.sql"
run_seed "postal_code bulk (seed)"   "postal_code"        "${SEED_BASE}/01_foundation/08b_postal_code_bulk.sql"
run_seed "post_office bulk (seed)"   "post_office"        "${SEED_BASE}/01_foundation/08c_post_office_bulk.sql"
run_seed "festival_calendar (seed)"  "festival_calendar_date" "${SEED_BASE}/01_foundation/10_festival_calendar.sql"
run_seed "city_village (seed)"       "city_village"       "${SEED_BASE}/01_foundation/11_city_village.sql"
run_seed "city_village urban recovery (seed)" "city_village" "${SEED_BASE}/01_foundation/11b_city_village_urban_recovery.sql"

echo ""
echo "--- Phase 3: Organization — DDL (1 table + address-restriction trigger + Kumari/Sevak one-per-Sakha trigger; type via ORGANIZATION_TYPE, status via unified STATUS in Foundation master_data) ---"
run_ddl "organization"               "organization" "${DDL_BASE}/02_organization/03_organization.sql"
run_sql "organization_address_restriction_trigger" "${DDL_BASE}/02_organization/04_organization_address_restriction_trigger.sql"
run_sql "organization_kumari_sevak_uniqueness_trigger" "${DDL_BASE}/02_organization/05_organization_kumari_sevak_uniqueness_trigger.sql"
run_sql "organization_singleton_trigger" "${DDL_BASE}/02_organization/08_organization_singleton_trigger.sql"
# Idempotent patch (owner 2026-10-31): the single SQL definition of Sakha-like org types (SAKHA_SANGHA + SAKHA_ASANA); the MBR-038A membership triggers and the Advisory Board one-seat-per-Sakha trigger call it, so it must exist before them.
run_sql "sakha_like_org_type_function" "${DDL_BASE}/02_organization/10_sakha_like_org_type_function.sql"

echo ""
echo "--- Phase 4: Organization — Seed ---"
run_seed "organization (seed)"               "organization"       "${SEED_BASE}/02_organization/03_organization.sql"
run_seed "sakha postal codes (seed)"         "postal_code"        "${SEED_BASE}/01_foundation/09_sakha_postal_codes.sql"
run_seed "sakha branches (seed)"             "organization"       "${SEED_BASE}/02_organization/05_sakha_branches.sql"
run_seed "id_sequence_master (org sync)"     "id_sequence_master" "${SEED_BASE}/02_organization/06_id_sequence_org_sync.sql"
# Idempotent patch: the ORGANIZATION_TYPE value ADVISORY_BOARD + the singleton 'Advisory Board'
# organization (owner decision 2026-10-30). Existence-gated seeds above never reach existing DBs.
run_sql "advisory_board organization patch"  "${SEED_BASE}/02_organization/07_advisory_board_organization_patch.sql"

echo ""
echo "--- Phase 5: Person — DDL (2 tables) ---"
run_ddl "person"         "person"         "${DDL_BASE}/03_person/02_person.sql"
run_ddl "person_address" "person_address" "${DDL_BASE}/03_person/03_person_address.sql"

echo ""
echo "--- Phase 6: Family — DDL (6 tables + move-transition guard) ---"
run_ddl "family_group"              "family_group"              "${DDL_BASE}/04_family/01_family_group.sql"
run_ddl "family_relationship"       "family_relationship"       "${DDL_BASE}/04_family/02_family_relationship.sql"
run_ddl "family_head_history"       "family_head_history"       "${DDL_BASE}/04_family/03_family_head_history.sql"
run_ddl "family_transition_history" "family_transition_history" "${DDL_BASE}/04_family/04_family_transition_history.sql"
run_ddl "family_link"               "family_link"               "${DDL_BASE}/04_family/05_family_link.sql"
run_ddl "family_admin"              "family_admin"              "${DDL_BASE}/04_family/06_family_admin.sql"
run_sql "family_move_transition_guard" "${DDL_BASE}/04_family/07_family_move_transition_guard.sql"
# Audit columns the API already writes (updated_at) but the original CREATE
# TABLE lacked; 03_family_head_history.sql is existence-gated, so this
# idempotent patch carries them to existing databases.
run_sql "family_head_history_audit_columns" "${DDL_BASE}/04_family/08_family_head_history_audit_columns.sql"

echo ""
echo "--- Phase 7: Membership — DDL (16 tables + Sakha-only trigger) ---"
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
echo "--- Phase 7b: Deferred Foundation Audit FKs ---"
# Wires the real FK constraints on district/postal_code/post_office/
# city_village's submitted_by/reviewed_by columns to sangha_sevi, now
# that sangha_sevi exists. Not a migration — runs every full rebuild
# against brand-new, empty tables (circular-dependency handling).
run_sql "foundation_audit_fk" "${DDL_BASE}/05_membership/16_foundation_audit_fk.sql"

echo ""
echo "--- Ensuring nss_db_owner, nss_db_backend, and nss_db_writer roles exist ---"
# database/scripts/00_create_database.sql normally creates both roles,
# but that script requires a true Postgres superuser + dblink back to
# localhost -- meaningless on managed Neon -- so it's never been run
# there. Created here instead, idempotently, so the naming convention
# matches local dev and Phase 9's GRANT has a target role. Both reuse
# DB_PASSWORD since Render only configures one credential set for this
# service; note the running API here connects as whatever DB_USER is
# (the Neon-provided owner role used to run this whole build), not as
# nss_db_backend -- so the grant below is not yet actually enforcing
# least-privilege access in this deployment, only preparing for it.
${PSQL} <<SQL
DO \$do\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'nss_db_owner') THEN
        CREATE ROLE nss_db_owner LOGIN PASSWORD '${DB_PASSWORD}';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'nss_db_backend') THEN
        CREATE ROLE nss_db_backend LOGIN PASSWORD '${DB_PASSWORD}';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'nss_db_writer') THEN
        CREATE ROLE nss_db_writer LOGIN PASSWORD '${DB_WRITE_PASSWORD:-${DB_PASSWORD}}';
    END IF;
END
\$do\$;
SQL

echo ""
echo "--- Phase 9: Grant nss_db_backend read-only access ---"
run_sql "grant_backend" "${REPO_ROOT}/database/scripts/04_grant_backend.sql"

echo ""
echo "--- Phase 10: Authentication — DDL (5 tables) ---"
run_ddl "user_account"           "user_account"         "${DDL_BASE}/06_authentication/01_user_account.sql"
run_ddl "password_history"       "password_history"     "${DDL_BASE}/06_authentication/02_password_history.sql"
run_ddl "registration_claim"     "registration_claim"   "${DDL_BASE}/06_authentication/03_registration_claim.sql"
run_ddl "password_reset_token"   "password_reset_token" "${DDL_BASE}/06_authentication/04_password_reset_token.sql"
run_ddl "user_session"           "user_session"         "${DDL_BASE}/06_authentication/05_user_session.sql"

echo ""
echo "--- Phase 11: Administration — DDL (2 tables) ---"
run_ddl "user_role"    "user_role"   "${DDL_BASE}/07_administration/01_user_role.sql"
run_ddl "admin_scope"  "admin_scope" "${DDL_BASE}/07_administration/02_admin_scope.sql"

echo ""
# NOTE: body_type_master/role_master seed content and admin_scope's CHECK
# constraint changed on 2026-10-09 (§63 composite auto-grant rule), and the
# election table gained election_type the same day (nomination-vs-election
# mode, GOV-BR-042). Per the existence-gating caveat above, those changes
# only take effect on a fresh table — a redeploy against an existing
# database will skip them, and skipping election_type will break every
# governance election endpoint.
echo "--- Phase 11b: Governance — DDL (10 tables + ballot immutability + seat-count limits) ---"
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
run_sql "governance_immutability"    "${DDL_BASE}/08_governance/11_governance_immutability.sql"
# Seat-count backstop: two functions + BEFORE INSERT OR UPDATE triggers
# on body_member_assignment. Not a table — run_sql, so the functions/
# triggers themselves are (re)applied on every redeploy regardless of
# the existence-gating caveat above (which affects only the
# body_type_master.max_members column and its seed, not these
# triggers).
run_sql "governance_seat_limits"     "${DDL_BASE}/08_governance/12_governance_seat_limits.sql"
# Re-file index: 07_election_nomination.sql is existence-gated, so its
# changed uq_election_nomination_active_candidate (live nominations only)
# never reaches an existing database. This idempotent patch does.
run_sql "governance_nomination_refile_index" "${DDL_BASE}/08_governance/13_governance_nomination_refile_index.sql"

echo ""
echo "--- Phase 11c: Governance — Seed Data ---"
run_seed "body_type_master (seed)" "body_type_master" "${SEED_BASE}/08_governance/01_body_type_master.sql"
run_seed "position_master (seed)"  "position_master"  "${SEED_BASE}/08_governance/02_position_master.sql"
run_seed "body_master (seed)"      "body_master"       "${SEED_BASE}/08_governance/03_body_master.sql"
# Idempotent patch: a Sakha Asana has its own Governing Body shell like a Sakha Sangha (owner 2026-10-30); the seed above covers SAKHA_SANGHA only and is existence-gated.
run_sql "sakha_asana governing body patch" "${SEED_BASE}/08_governance/04_sakha_asana_governing_body_patch.sql"

echo ""
echo "--- Phase 11d: Correspondence — DDL (5 tables, Tier 6: correspondence, correspondence_document, correspondence_finance_reference, correspondence_sequence_counter, correspondence_approval_step) ---"
run_ddl "correspondence"                   "correspondence"                   "${DDL_BASE}/09_correspondence/01_correspondence.sql"
run_ddl "correspondence_document"          "correspondence_document"          "${DDL_BASE}/09_correspondence/02_correspondence_document.sql"
run_ddl "correspondence_finance_reference" "correspondence_finance_reference" "${DDL_BASE}/09_correspondence/03_correspondence_finance_reference.sql"
run_ddl "correspondence_sequence_counter"  "correspondence_sequence_counter"  "${DDL_BASE}/09_correspondence/04_correspondence_sequence_counter.sql"
run_ddl "correspondence_approval_step"     "correspondence_approval_step"     "${DDL_BASE}/09_correspondence/05_correspondence_approval_step.sql"

echo ""
echo "--- Phase 11e: Attendance — DDL (4 tables, Tier 6: weekly_sangha_puja, weekly_sangha_puja_attendance, attendance_exception, attendance_review) ---"
run_ddl "weekly_sangha_puja"            "weekly_sangha_puja"            "${DDL_BASE}/10_attendance/01_weekly_sangha_puja.sql"
run_ddl "weekly_sangha_puja_attendance" "weekly_sangha_puja_attendance" "${DDL_BASE}/10_attendance/02_weekly_sangha_puja_attendance.sql"
run_ddl "attendance_exception"          "attendance_exception"          "${DDL_BASE}/10_attendance/03_attendance_exception.sql"
run_ddl "attendance_review"             "attendance_review"             "${DDL_BASE}/10_attendance/04_attendance_review.sql"

echo ""
echo "--- Phase 11f: Organization re-parent approval — DDL (2 tables: organization_reparent_request, organization_reparent_step) ---"
run_ddl "organization_reparent_request" "organization_reparent_request" "${DDL_BASE}/02_organization/06_organization_reparent_request.sql"
run_ddl "organization_reparent_step"    "organization_reparent_step"    "${DDL_BASE}/02_organization/07_organization_reparent_step.sql"
# Idempotent patch (owner 2026-10-31): widens the existing organization_reparent_step CHECKs for the new SOURCE_PARENT_PRESIDENT step (step_role + step_order 1..4); the table DDL above is existence-gated.
run_sql "organization_reparent_step source-role patch" "${DDL_BASE}/02_organization/09_organization_reparent_step_source_role_patch.sql"

echo ""
echo "--- Phase 12: Grant nss_db_writer write access ---"
run_sql "create_writer_role" "${REPO_ROOT}/database/scripts/05_create_writer_role.sql"

echo ""
echo "--- Phase 13: Admin Bootstrap Seed ---"
# Gated by RUN_DB_BOOTSTRAP (normalised to RUN_BOOTSTRAP above). This is
# the ONLY step the flag controls: re-seeding the NSSAdmin account. Set
# RUN_DB_BOOTSTRAP=false (default) on routine deploys to leave the live
# admin account untouched; set it truthy only when you intend to (re)seed
# the admin. The script itself is NOT EXISTS-guarded, so even when it runs
# it will not overwrite an existing admin — the flag is a second, explicit
# safety gate on top of that.
if [ "${RUN_BOOTSTRAP}" = "1" ]; then
    echo "  RUN_DB_BOOTSTRAP truthy — running admin bootstrap"
    python3 "${REPO_ROOT}/scripts/bootstrap_admin.py" || echo "  [WARN] admin_bootstrap (may already exist)"
else
    echo "  [SKIP] admin bootstrap (RUN_DB_BOOTSTRAP not truthy — live admin account untouched)"
fi

echo ""
echo "--- Phase 13b: Geo Attribution Backfill (bulk-seeded rows -> P1) ---"
# Registration-Time Geography Creation (2026-10-21) added
# submitted_by_person_pk to city_village/postal_code/post_office
# (district is out of scope). The bulk-reference-seeded rows from
# Phase 2 have no submitter — backfill them to the NSS Admin's
# person_pk (P1) for attribution consistency. Runs unconditionally
# (not gated by RUN_DB_BOOTSTRAP): it only touches rows where
# submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS
# NULL, so it never overwrites a real submitter, and if P1 doesn't
# exist yet (RUN_DB_BOOTSTRAP left at its default false on this
# environment) the subquery returns NULL and the UPDATE is a
# harmless no-op — safe and idempotent either way.
if output=$(${PSQL} -c "
    UPDATE nss.city_village SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
    UPDATE nss.postal_code SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
    UPDATE nss.post_office SET submitted_by_person_pk = (SELECT person_pk FROM nss.person WHERE person_id = 'P1') WHERE submitted_by_person_pk IS NULL AND submitted_by_sangha_sevi_pk IS NULL;
" 2>&1); then
    echo "  [OK]   geo_attribution_backfill"
    echo "${output}" | sed 's/^/  /'
elif echo "${output}" | grep -qiE 'column .* does not exist'; then
    # Existing-table DDL change (submitted_by_person_pk) was skipped on an
    # already-bootstrapped city_village/postal_code/post_office — same
    # existence-gating caveat as every other existing-table column add.
    # Not fatal: SKIP, not FAIL, so this step never breaks a routine
    # Render redeploy.
    echo "  [SKIP] geo_attribution_backfill  (submitted_by_person_pk column absent — needs a full hard rebuild)"
else
    echo "  [FAIL] geo_attribution_backfill"
    echo "${output}" | sed 's/^/         /'
    exit 1
fi

echo ""
echo "--- Phase 14: Audit — DDL (1 table + trigger) ---"
run_ddl "system_event_log"  "system_event_log" "${DDL_BASE}/01_foundation/14_system_event_log.sql"
run_sql "audit_trigger"     "${DDL_BASE}/01_foundation/15_audit_trigger.sql"

echo ""
echo "=== Database bootstrap complete (Neon.dev) ==="
echo ""
echo "=== Build finished ==="
