# database/seed/08_governance/

Governance seed data (Tier 6, committed on `feature/tier6-governance`) — starter catalogues for
the two Depth-0 masters plus the 3 NSS-wide singleton bodies. Mirrors `database/ddl/08_governance/`.

Authority: GOV-BR-010/011/023/024/025/031/032, SOL-GOV-002 §4-5,
`docs/03_Solution/modules/governance/04_governance_business_rules.md`.

## Seed Execution Order

Run as **Phase 11c** of `database/scripts/02_build.sh`/`.ps1` and `render_build.sh`, right after
Phase 11b's governance DDL and before the Phase 12 `nss_db_writer` grant, via `run_seed`
(existence-gated: if `body_type_master` / `position_master` / `body_master` already exists, its
seed is skipped — see `database/scripts/README.md`). Order matters: `01` and `02` before `03`
(`03_body_master.sql` resolves `body_type_master` by code).

| File | Seeds |
|---|---|
| `01_body_type_master.sql` (v1.1) | 8 body types: `KENDRA_GOVERNING_BODY`, `SAKHA_GOVERNING_BODY`, `ADVISORY_BOARD`, `MAHILA_PARICHALANA_MANDALI`, `SEVAK_SANGHA_EXECUTIVE`, plus `ANCHALIKA_GOVERNING_BODY`, `ZILLA_GOVERNING_BODY`, `PATHA_CHAKRA_GOVERNING_BODY` (added 2026-10-09 for the §63 composite auto-grant rule) |
| `02_position_master.sql` | 10 positions: `PRESIDENT`, `VICE_PRESIDENT`, `PARICHALAK`, `SECRETARY`, `ASSISTANT_SECRETARY`, `JOINT_SECRETARY`, `TREASURER`, `CASHIER`, `MUKHYA_PUJAKA`, `MEMBER` |
| `03_body_master.sql` | 3 NSS-wide singleton bodies with `organization_pk = NULL`: `KENDRA_GB` (Kendra Governing Body), `ADVISORY_BOARD`, `KENDRA_MAHILA_PM` (central Mahila Parichalana Mandali) |

## Notes

- Every insert is `ON CONFLICT (...) DO NOTHING` (insert-if-missing), so a re-run never overwrites
  a row an admin has since edited through the Governance API/UI.
- Org-scoped bodies (Sakha Governing Body, per-Sakha Mahila Parichalana Mandali, Sakha-level
  Sevak Sangha Executive, and the Anchalika/Zilla/Patha Chakra bodies) are instance data created
  manually per organization and have intentionally **no** seed file.
- `body_type_master` rows are RBAC-significant: `api/services/rbac_service.py` reads body/position
  holdings to auto-grant the matching `NSS_ERP_*_ADMIN` role, so treat new rows as a potential
  permission-surface change.
- Both catalogues stay caller-extensible through the Governance API (`POST`/`PATCH /body-types`,
  `/positions`).
- `election`, assignments, nominations, ballots and results have no seed data.
