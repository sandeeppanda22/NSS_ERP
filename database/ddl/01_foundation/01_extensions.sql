-- =====================================================
-- NSS ERP
-- Module: Foundation
-- File: 01_extensions.sql
-- Version: 2.0
-- Authority: SOL-ARCH-010, SOL-FND-004
-- Owner: NSS_ADMIN
-- =====================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
