-- =====================================================
-- NSS ERP
-- Script: 01_extensions.sql
-- Purpose: Install PostgreSQL extensions and create nss schema
-- Authority: SOL-ARCH-010, SOL-FND-004
-- Version: 1.0
-- =====================================================
--
-- Run as PostgreSQL SUPERUSER against the nss_erp database
-- AFTER 00_create_database.sql has been executed:
--
--   psql -U postgres -d nss_erp -f database/scripts/01_extensions.sql
--
-- Extensions must be created by a superuser. nss_admin
-- (NOSUPERUSER) cannot create them.
--
-- This script is idempotent — safe to re-run.
-- =====================================================

-- UUID generation (gen_random_uuid for PK defaults)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Trigram indexes for fuzzy/partial text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN indexes on non-array scalar types (composite indexes)
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Geospatial types, indexes, and functions (distance, containment, etc.)
CREATE EXTENSION IF NOT EXISTS postgis;

-- -------------------------------------------------
-- Schema: nss
-- All NSS ERP application tables live here.
-- The public schema is reserved for extensions.
-- -------------------------------------------------
CREATE SCHEMA IF NOT EXISTS nss;

-- nss_admin owns the schema and all objects within it
ALTER SCHEMA nss OWNER TO nss_admin;

-- Set default search_path so unqualified table names resolve to nss
ALTER DATABASE nss_erp SET search_path TO nss, public;
