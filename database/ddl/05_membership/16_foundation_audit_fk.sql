-- =====================================================
-- NSS ERP
-- Module: Membership
-- File: 16_foundation_audit_fk.sql
-- Table: ALTER on nss.district, nss.postal_code,
--        nss.post_office, nss.city_village
-- Depth: Pass 2 (depends on sangha_sevi, Depth 2 of
--        this module; must run AFTER sangha_sevi exists)
-- Version: 1.0 — SOL-ARCH-010 Amendment (Member-Assisted
--          Geographic Entry, 2026-10-03).
-- Authority: SOL-FND-004 §16.8, FND-BR-085 .. FND-BR-090
-- Owner: NSS_ERP_ADMIN
--
-- Why this file exists (read before touching):
--   Foundation's four writable geographic tables
--   (district, postal_code, post_office, city_village —
--   01_foundation/10, 12, 13, 11) carry
--   submitted_by_sangha_sevi_pk / reviewed_by_sangha_sevi_pk
--   columns that logically reference nss.sangha_sevi.
--   sangha_sevi cannot exist before those four tables are
--   created (Phase 1), because sangha_sevi transitively
--   depends on nss.organization (Phase 3), which itself
--   has address FKs into city_village/postal_code (Foundation
--   geography). That is a genuine circular dependency, not a
--   style choice — no single CREATE-only ordering can satisfy
--   both directions.
--
--   This file is the resolution: the four columns are created
--   as plain nullable UUID (no FK) in their Phase 1 CREATE
--   TABLE statements, and THIS file adds the real FK
--   constraints as a normal, scripted step within the SAME
--   full-rebuild run — once sangha_sevi exists (end of
--   Phase 7). It is not a patch/migration against an existing
--   database with data; on every hard rebuild this runs
--   against four brand-new, empty tables. Run order in
--   02_build.sh: Phase 7 (sangha_sevi) -> this file.
-- =====================================================

ALTER TABLE nss.district
    ADD CONSTRAINT fk_district_submitted_by
        FOREIGN KEY (submitted_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),
    ADD CONSTRAINT fk_district_reviewed_by
        FOREIGN KEY (reviewed_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk);

ALTER TABLE nss.postal_code
    ADD CONSTRAINT fk_postal_code_submitted_by
        FOREIGN KEY (submitted_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),
    ADD CONSTRAINT fk_postal_code_reviewed_by
        FOREIGN KEY (reviewed_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),
    ADD CONSTRAINT fk_postal_code_submitted_by_person
        FOREIGN KEY (submitted_by_person_pk)
        REFERENCES nss.person (person_pk);

ALTER TABLE nss.post_office
    ADD CONSTRAINT fk_post_office_submitted_by
        FOREIGN KEY (submitted_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),
    ADD CONSTRAINT fk_post_office_reviewed_by
        FOREIGN KEY (reviewed_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),
    ADD CONSTRAINT fk_post_office_submitted_by_person
        FOREIGN KEY (submitted_by_person_pk)
        REFERENCES nss.person (person_pk);

ALTER TABLE nss.city_village
    ADD CONSTRAINT fk_city_village_submitted_by
        FOREIGN KEY (submitted_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),
    ADD CONSTRAINT fk_city_village_reviewed_by
        FOREIGN KEY (reviewed_by_sangha_sevi_pk)
        REFERENCES nss.sangha_sevi (sangha_sevi_pk),
    ADD CONSTRAINT fk_city_village_submitted_by_person
        FOREIGN KEY (submitted_by_person_pk)
        REFERENCES nss.person (person_pk);
