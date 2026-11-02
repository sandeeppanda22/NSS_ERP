-- =====================================================
-- NSS ERP
-- Module: Governance
-- File: 12_governance_seat_limits.sql
-- Purpose: Enforce, at the DATABASE level, the total
--          member-count cap per governing body as a
--          backstop behind the existing API-layer
--          enforcement (api/routers/governance.py,
--          _COMPOSITION_RULES / _resolve_seat_limit /
--          "one_seat_per_sakha"). The Python rules remain
--          the primary, UX-facing validation (clear error
--          messages, position-specific checks, gender/
--          eligibility rules — none of that is touched or
--          duplicated here); this file only guards the
--          same numeric ceilings a second time, so a
--          future write path that bypasses the API (a
--          script, a different endpoint, a bug) cannot
--          silently over-seat a body.
-- Version: 1.0
-- Authority: GOV-BR-010/011/023/024/025/031/032/033/034/035
--            (see api/routers/governance.py _COMPOSITION_RULES
--            for the authoritative per-body-type breakdown this
--            mirrors), owner-confirmed 2026-10-21 (DB-level
--            seat-count backstop).
-- Owner: Governance
-- Depends: 01_body_type_master.sql (max_members column),
--          03_body_master.sql, 04_body_member_assignment.sql
--
-- Scope — COUNT enforcement only. Gender composition,
-- position eligibility, "officers chosen from members",
-- single-holder-per-position, NSS-wide singleton posts
-- (Parichalak/Mukhya Pujaka) and every other
-- _COMPOSITION_RULES check stay exactly as they are today:
-- Python-only, unchanged. This file never touches
-- api/routers/governance.py.
--
-- Why a trigger and not a GRANT/REVOKE or a CHECK
-- constraint: the limit depends on an aggregate (COUNT of
-- other rows) and, for two body types, on a sibling row's
-- own column (body_master.organization_pk) — neither is
-- expressible as a single-row CHECK. A BEFORE INSERT OR
-- UPDATE trigger that RAISEs is the portable, explicit
-- guard, same idiom as nss.fn_block_update() in
-- 11_governance_immutability.sql.
--
-- Two independent trigger functions are attached, both
-- BEFORE INSERT OR UPDATE on nss.body_member_assignment:
--
--   1. nss.fn_enforce_body_seat_limit() — flat per-body
--      occupancy cap. Resolution order for the limit:
--        a. nss.body_type_master.max_members, if NOT NULL
--           for the row's body type — used as-is (covers
--           KENDRA_GOVERNING_BODY=9, SAKHA_GOVERNING_BODY=9,
--           SEVAK_SANGHA_EXECUTIVE=3, ANCHALIKA_GOVERNING_BODY=3,
--           ZILLA_GOVERNING_BODY=3, PATHA_CHAKRA_GOVERNING_BODY=3).
--        b. body_type_code = 'MAHILA_PARICHALANA_MANDALI' and
--           max_members IS NULL (always true for this type,
--           see 01_body_type_master.sql) — a single constant
--           cannot express this body's two-tier cap, so it is
--           derived here from the OWNING body_master row:
--           8 when body_master.organization_pk IS NULL
--           (Kendra-level; the Bye-Law's 9th seat, Parichalak,
--           is inherited from the Kendra Governing Body and is
--           NEVER a body_member_assignment row for this body —
--           see api/routers/governance.py's
--           _COMPOSITION_RULES["MAHILA_PARICHALANA_MANDALI"]
--           comment — so 8 is the correct row-count ceiling),
--           else 3 (Sakha-level, organization_pk IS NOT NULL).
--        c. body_type_code = 'ADVISORY_BOARD' — the flat-count
--           check is skipped entirely here. Its real limit
--           (one seat per active Sakha, a number that grows
--           with the Sakha count) is not a fixed ceiling and is
--           instead enforced by the second trigger below.
--        d. Anything else with max_members NULL — no
--           enforcement (unanticipated/custom body types added
--           via POST /body-types stay ungated at the DB level,
--           same as today).
--      "Occupying a seat" uses the same assignment_status set
--      the API treats as current (_CURRENT_ASSIGNMENT_SQL):
--      ASSIGNED, ACTIVE, PENDING_REMOVAL (a forced-removal-in-
--      progress row still occupies its seat until the body's
--      President approves/rejects it). The row being
--      UPDATEd is excluded from its own count.
--
--   2. nss.fn_enforce_advisory_one_seat_per_sakha() — the
--      Advisory Board's real rule: one representative PER
--      SAKHA (GOV-BR-023/024/025; api/routers/governance.py
--      "one_seat_per_sakha", _home_sakha). Scoped to rows
--      whose body is body_type_code = 'ADVISORY_BOARD'. Derives
--      the new row's Sakha via person_pk -> that person's own
--      active nss.sangha_sevi -> sangha_sevi.organization_pk
--      (filtered to organization_type MASTER_DATA value_code
--      Sakha-like via nss.fn_is_sakha_like_org_type: SAKHA_SANGHA or SAKHA_ASANA, same anchor _home_sakha uses), then
--      rejects the write if another PERSON already holds a
--      current seat on the same Advisory Board body whose own
--      home Sakha is identical. Mirrors the API precisely: the
--      SAME person taking a second position on the board
--      (Member -> President) is fine and is not blocked — only
--      a DIFFERENT person from an already-represented Sakha is
--      rejected.
-- =====================================================

-- ── Trigger function 1: flat per-body seat-count cap ────

CREATE OR REPLACE FUNCTION nss.fn_enforce_body_seat_limit()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_body_type_code   VARCHAR(50);
    v_organization_pk  UUID;
    v_max_members      INTEGER;
    v_current_count    INTEGER;
BEGIN
    -- Only rows claiming an occupied seat need to be checked.
    IF NOT (NEW.is_active = TRUE
            AND NEW.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')) THEN
        RETURN NEW;
    END IF;

    SELECT bt.body_type_code, bm.organization_pk, bt.max_members
      INTO v_body_type_code, v_organization_pk, v_max_members
    FROM nss.body_master bm
    JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
    WHERE bm.body_master_pk = NEW.body_master_pk;

    IF v_body_type_code IS NULL THEN
        -- Orphan body_master_pk — the FK constraint will reject this
        -- row anyway; nothing for this trigger to enforce.
        RETURN NEW;
    END IF;

    IF v_max_members IS NULL THEN
        IF v_body_type_code = 'MAHILA_PARICHALANA_MANDALI' THEN
            -- Two-tier cap by org-nullness; max_members stays NULL on
            -- body_type_master for this type on purpose (see header).
            IF v_organization_pk IS NULL THEN
                v_max_members := 8;
            ELSE
                v_max_members := 3;
            END IF;
        ELSIF v_body_type_code = 'ADVISORY_BOARD' THEN
            -- Not a flat count — enforced by
            -- fn_enforce_advisory_one_seat_per_sakha() instead.
            RETURN NEW;
        ELSE
            -- Unanticipated/custom body type with no configured limit —
            -- leave ungated at the DB level, same as today.
            RETURN NEW;
        END IF;
    END IF;

    SELECT COUNT(*)
      INTO v_current_count
    FROM nss.body_member_assignment a
    WHERE a.body_master_pk = NEW.body_master_pk
      AND a.is_active = TRUE
      AND a.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')
      AND a.body_member_assignment_pk <> NEW.body_member_assignment_pk;

    IF v_current_count >= v_max_members THEN
        RAISE EXCEPTION
            'Governance body % already has % active seat(s), at its maximum of % for body type %.',
            NEW.body_master_pk, v_current_count, v_max_members, v_body_type_code
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$;

-- ── Trigger function 2: Advisory Board — one seat per Sakha ──

CREATE OR REPLACE FUNCTION nss.fn_enforce_advisory_one_seat_per_sakha()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_body_type_code  VARCHAR(50);
    v_sakha_org_pk    UUID;
    v_conflict_exists BOOLEAN;
BEGIN
    IF NOT (NEW.is_active = TRUE
            AND NEW.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')) THEN
        RETURN NEW;
    END IF;

    SELECT bt.body_type_code
      INTO v_body_type_code
    FROM nss.body_master bm
    JOIN nss.body_type_master bt ON bt.body_type_master_pk = bm.body_type_master_pk
    WHERE bm.body_master_pk = NEW.body_master_pk;

    IF v_body_type_code IS DISTINCT FROM 'ADVISORY_BOARD' THEN
        RETURN NEW;
    END IF;

    -- The nominee's home Sakha, via their own active Sangha Sevi record
    -- (same anchor as api/routers/governance.py::_home_sakha). A nominee
    -- with no active Sakha-level membership has no home Sakha to check
    -- here; the API's own 422 ("must belong to a Sakha Sangha") already
    -- blocks that case earlier, so this trigger simply has nothing to
    -- compare and lets the row through.
    SELECT ss.organization_pk
      INTO v_sakha_org_pk
    FROM nss.sangha_sevi ss
    JOIN nss.organization o ON o.organization_pk = ss.organization_pk
    JOIN nss.master_data md ON md.master_data_pk = o.organization_type_master_data_pk
    WHERE ss.person_pk = NEW.person_pk
      AND ss.is_active = TRUE
      AND nss.fn_is_sakha_like_org_type(md.value_code)
    LIMIT 1;

    IF v_sakha_org_pk IS NULL THEN
        RETURN NEW;
    END IF;

    -- A different PERSON from the same Sakha already holding a current
    -- seat on this same Advisory Board body is the conflict. The same
    -- person taking a second position (Member -> President) is fine —
    -- excluded via a.person_pk <> NEW.person_pk, mirroring the API.
    SELECT EXISTS (
        SELECT 1
        FROM nss.body_member_assignment a
        JOIN nss.sangha_sevi ss
             ON ss.person_pk = a.person_pk AND ss.is_active = TRUE
        WHERE a.body_master_pk = NEW.body_master_pk
          AND a.person_pk <> NEW.person_pk
          AND a.body_member_assignment_pk <> NEW.body_member_assignment_pk
          AND a.is_active = TRUE
          AND a.assignment_status IN ('ASSIGNED', 'ACTIVE', 'PENDING_REMOVAL')
          AND ss.organization_pk = v_sakha_org_pk
    ) INTO v_conflict_exists;

    IF v_conflict_exists THEN
        RAISE EXCEPTION
            'This Sakha Sangha is already represented on the Advisory Board (body %) by another member; only one seat per Sakha is permitted.',
            NEW.body_master_pk
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$;

-- ── Attach both triggers to nss.body_member_assignment ──

DROP TRIGGER IF EXISTS trg_enforce_body_seat_limit
    ON nss.body_member_assignment;
CREATE TRIGGER trg_enforce_body_seat_limit
    BEFORE INSERT OR UPDATE ON nss.body_member_assignment
    FOR EACH ROW EXECUTE FUNCTION nss.fn_enforce_body_seat_limit();

DROP TRIGGER IF EXISTS trg_enforce_advisory_one_seat_per_sakha
    ON nss.body_member_assignment;
CREATE TRIGGER trg_enforce_advisory_one_seat_per_sakha
    BEFORE INSERT OR UPDATE ON nss.body_member_assignment
    FOR EACH ROW EXECUTE FUNCTION nss.fn_enforce_advisory_one_seat_per_sakha();
