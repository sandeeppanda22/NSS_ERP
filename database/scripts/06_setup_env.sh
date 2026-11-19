#!/usr/bin/env bash
# =====================================================
# NSS ERP — Local Development Environment Setup
# =====================================================
#
# Generates api/.env with all required variables and
# sets matching passwords on PostgreSQL roles so the
# application can connect without manual configuration.
#
# Run ONCE after 00_create_database.sql (which creates
# the roles without passwords).
#
# Usage:
#   ./database/scripts/06_setup_env.sh [--force]
#
#   --force   Overwrite existing api/.env (default: skip)
#
# Requires:
#   - psql accessible
#   - PostgreSQL superuser password (prompted)
#   - Roles nss_db_owner, nss_db_backend, nss_db_writer
#     must already exist (created by 00_create_database.sql)
#
# Passwords (local dev only — never commit to repo):
#   Prompted interactively for each role.
#
# This script is idempotent — safe to re-run with --force.
# =====================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/api/.env"

# -- colours -----------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# -- flags -------------------------------------------------
FORCE=false
if [ "${1:-}" = "--force" ]; then
    FORCE=true
fi

# -- check existing .env -----------------------------------
if [ -f "${ENV_FILE}" ] && [ "$FORCE" = false ]; then
    echo -e "${YELLOW}api/.env already exists.${NC}"
    echo "  Use --force to overwrite."
    echo "  Current file: ${ENV_FILE}"
    exit 0
fi

# -- PostgreSQL connection ---------------------------------
DB_HOST="localhost"
DB_PORT="5432"
PG_USER="${1:-postgres}"
# Strip --force from positional if it was first arg
if [ "$PG_USER" = "--force" ]; then
    PG_USER="postgres"
fi

echo ""
echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN}  NSS ERP — Local Dev Environment Setup${NC}"
echo -e "${CYAN}=============================================${NC}"
echo ""

# Prompt for superuser password
if [ -z "${PGPASSWORD:-}" ]; then
    read -rsp "PostgreSQL superuser (${PG_USER}) password: " PGPASSWORD
    echo ""
    export PGPASSWORD
fi

PSQL="psql -h ${DB_HOST} -p ${DB_PORT} -U ${PG_USER} -d postgres -t -A"

# -- verify connection -------------------------------------
echo -e "${CYAN}[1/4] Verifying PostgreSQL connection...${NC}"
if ! ${PSQL} -c "SELECT 1;" >/dev/null 2>&1; then
    echo -e "${RED}Cannot connect to PostgreSQL as ${PG_USER}@${DB_HOST}:${DB_PORT}${NC}"
    echo "  Check that PostgreSQL is running and the password is correct."
    exit 1
fi
echo -e "  ${GREEN}[OK]${NC} Connected to PostgreSQL"

# -- verify roles exist ------------------------------------
for role in nss_db_owner nss_db_backend nss_db_writer; do
    exists=$(${PSQL} -c "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${role}');" 2>/dev/null || echo "f")
    if [ "$exists" != "t" ]; then
        echo -e "  ${RED}[FAIL]${NC} Role ${role} does not exist."
        echo "  Run 00_create_database.sql first."
        exit 1
    fi
    echo -e "  ${GREEN}[OK]${NC} Role ${role} exists"
done
echo ""

# -- role passwords (prompted) -----------------------------
# Each role gets its own password. These are for local dev
# only — production must use strong, unique passwords set
# via deployment config.
echo -e "${CYAN}[2/4] Set passwords for PostgreSQL roles${NC}"
echo "  (These will be stored in api/.env and set on the PostgreSQL roles.)"
echo ""

read -rsp "  Password for nss_db_owner:   " OWNER_PASS
echo ""
read -rsp "  Password for nss_db_backend: " BACKEND_PASS
echo ""
read -rsp "  Password for nss_db_writer:  " WRITER_PASS
echo ""
echo ""

# Validate non-empty
if [ -z "$OWNER_PASS" ] || [ -z "$BACKEND_PASS" ] || [ -z "$WRITER_PASS" ]; then
    echo -e "${RED}All three passwords are required. Aborting.${NC}"
    exit 1
fi

# -- generate JWT secret -----------------------------------
# Use openssl if available, otherwise Python
if command -v openssl >/dev/null 2>&1; then
    JWT_SECRET=$(openssl rand -hex 32)
else
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
fi

# -- set PostgreSQL role passwords -------------------------
echo -e "${CYAN}[3/4] Setting PostgreSQL role passwords...${NC}"
for pair in "nss_db_owner:${OWNER_PASS}" "nss_db_backend:${BACKEND_PASS}" "nss_db_writer:${WRITER_PASS}"; do
    role="${pair%%:*}"
    pass="${pair##*:}"
    if ${PSQL} -c "ALTER ROLE ${role} PASSWORD '${pass}';" >/dev/null 2>&1; then
        echo -e "  ${GREEN}[OK]${NC} ${role} password set"
    else
        echo -e "  ${RED}[FAIL]${NC} Could not set password for ${role}"
        exit 1
    fi
done
echo ""

# -- write api/.env ----------------------------------------
echo -e "${CYAN}[4/4] Writing api/.env...${NC}"

# Keep every setting this script does not generate (UPI_* gateway keys, AADHAAR_* keys, DEBUG_MODE ...): re-running with --force must never
# throw away the owner's own lines (a lost AADHAAR key would destroy the stored numbers; a lost UPI line switched the pay flow off).
PRESERVED=""
if [ -f "${ENV_FILE}" ]; then
    PRESERVED="$(grep -Ev '^[[:space:]]*(#|$)|^(DB_NAME|DB_USER|DB_PASSWORD|DB_HOST|DB_PORT|DB_WRITE_USER|DB_WRITE_PASSWORD|JWT_SECRET_KEY|JWT_ACCESS_TOKEN_MINUTES|JWT_REFRESH_TOKEN_DAYS|JWT_ABSOLUTE_SESSION_DAYS)=' "${ENV_FILE}" || true)"
fi

cat > "${ENV_FILE}" << EOF
# =====================================================
# NSS ERP — Local Development Environment
# =====================================================
# Generated by: database/scripts/06_setup_env.sh
# WARNING: Do not commit this file. It is in .gitignore.
# =====================================================

# ── Database (read-only pool) ───────────────────────
DB_NAME=nss_erp
DB_USER=nss_db_backend
DB_PASSWORD=${BACKEND_PASS}
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}

# ── Database (write pool — Tier 5) ──────────────────
DB_WRITE_USER=nss_db_writer
DB_WRITE_PASSWORD=${WRITER_PASS}

# ── JWT (Tier 5 — Authentication) ───────────────────
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ACCESS_TOKEN_MINUTES=30
JWT_REFRESH_TOKEN_DAYS=7
JWT_ABSOLUTE_SESSION_DAYS=30
EOF

if [ -n "${PRESERVED}" ]; then
    {
        echo ""
        echo "# ── Kept from the previous api/.env (not generated by this script) ──"
        echo "${PRESERVED}"
    } >> "${ENV_FILE}"
    echo -e "  ${GREEN}[OK]${NC} kept $(echo "${PRESERVED}" | wc -l | tr -d ' ') existing setting(s) (UPI_*, AADHAAR_* ...)"
fi

echo -e "  ${GREEN}[OK]${NC} ${ENV_FILE}"
echo ""

# -- summary -----------------------------------------------
echo -e "${CYAN}=============================================${NC}"
echo -e "${CYAN}  SETUP COMPLETE${NC}"
echo -e "${CYAN}=============================================${NC}"
echo ""
echo -e "  ${GREEN}PostgreSQL role passwords set${NC}"
echo -e "  ${GREEN}api/.env generated${NC}"
echo ""
echo "  Roles configured:"
echo "    nss_db_owner   (DDL/schema owner)"
echo "    nss_db_backend (read-only runtime pool)"
echo "    nss_db_writer  (write pool — auth + admin)"
echo ""
echo "  JWT secret: (random — see api/.env)"
echo ""
echo "  Next steps:"
echo "    1. Run the database build:  ./database/scripts/02_build.sh"
echo "    2. Start the server (from the repo root, NOT from api/):"
echo "                                python3 -m uvicorn api.main:app --reload --port 8001"
echo "    3. Open:                    http://localhost:8001/login"
echo ""
