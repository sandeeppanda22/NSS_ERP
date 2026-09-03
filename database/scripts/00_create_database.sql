-- =====================================================
-- NSS ERP
-- Script: 00_create_database.sql
-- Purpose: Create database and PostgreSQL technical roles
-- Authority: SOL-ARCH-011 §7.2
-- Version: 1.0
-- =====================================================
--
-- Run as a PostgreSQL SUPERUSER (e.g. postgres):
--
--   psql -U postgres -f database/scripts/00_create_database.sql
--
-- This script creates:
--   1. Role: nss_admin   — owns all schema objects, executes DDL/seed
--   2. Role: app_backend — runtime read/write for the application layer
--   3. Database: nss_erp — owned by nss_admin
--
-- IMPORTANT DISTINCTION (SOL-ARCH-011 §7.2):
--   PostgreSQL role "nss_admin" is the DATABASE-LEVEL owner.
--   ERP role "NSS_ADMIN" is an APPLICATION-LEVEL RBAC role
--   (a row in role_master, enforced by the application layer).
--   These are separate security boundaries.
--
-- This script is idempotent — safe to re-run.
-- It does NOT drop any existing objects.
-- No credentials are stored here; set passwords externally
-- via ALTER ROLE or .pgpass / environment variables.
-- =====================================================

-- -------------------------------------------------
-- 1. PostgreSQL role: nss_admin (DDL / schema owner)
-- -------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'nss_admin'
    ) THEN
        CREATE ROLE nss_admin WITH
            LOGIN
            NOSUPERUSER
            CREATEDB
            NOCREATEROLE;
        RAISE NOTICE 'Role nss_admin created.';
    ELSE
        RAISE NOTICE 'Role nss_admin already exists — skipping.';
    END IF;
END
$$;

-- -------------------------------------------------
-- 2. PostgreSQL role: app_backend (runtime)
-- -------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'app_backend'
    ) THEN
        CREATE ROLE app_backend WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE;
        RAISE NOTICE 'Role app_backend created.';
    ELSE
        RAISE NOTICE 'Role app_backend already exists — skipping.';
    END IF;
END
$$;

-- -------------------------------------------------
-- 3. Database: nss_erp (owned by nss_admin)
-- -------------------------------------------------
-- Note: CREATE DATABASE cannot run inside a transaction
-- block. If using psql, this works as a top-level statement.
-- If the database already exists, this will raise a
-- non-fatal notice and continue.
-- -------------------------------------------------

SELECT 'CREATE DATABASE nss_erp OWNER nss_admin'
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'nss_erp'
);

-- The SELECT above only prints the command text as a hint.
-- PostgreSQL does not support IF NOT EXISTS for CREATE DATABASE
-- in plain SQL. Use the conditional below instead:

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = 'nss_erp'
    ) THEN
        PERFORM dblink_exec(
            'dbname=postgres',
            'CREATE DATABASE nss_erp OWNER nss_admin'
        );
        RAISE NOTICE 'Database nss_erp created.';
    ELSE
        RAISE NOTICE 'Database nss_erp already exists — skipping.';
    END IF;
EXCEPTION
    WHEN undefined_function THEN
        -- dblink not available; fall back to manual instruction
        RAISE NOTICE 'dblink not available. Run manually if needed:';
        RAISE NOTICE '  CREATE DATABASE nss_erp OWNER nss_admin;';
END
$$;

-- -------------------------------------------------
-- 4. Grant app_backend CONNECT on nss_erp
-- -------------------------------------------------
-- This must run after the database exists.
-- Additional table-level GRANTs for app_backend will be
-- added when the API layer is implemented (Phase 7+).
-- -------------------------------------------------
GRANT CONNECT ON DATABASE nss_erp TO app_backend;
