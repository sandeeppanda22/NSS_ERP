# Finance Module

Solution-layer design for the Finance module — the common financial-management framework for
NSS. Five files, `v1.0.0 DRAFT — SOURCE ALIGNED` (ERD is tagged `DRAFT —
LOGICAL DESIGN`; the document-level `Status` field remains `DRAFT` throughout, same convention
as every other module).

## Documents

| # | File | Document ID | Covers |
|--:|------|--------------|--------|
| 1 | `01_finance_design.md` | `SOL-FIN-001` | Purpose, source authority, module scope, the Financial Scope Independence principle (`FIN-ARCH-001`) |
| 2 | `02_finance_erd.md` | `SOL-FIN-002` | Entity-relationship design (logical) |
| 3 | `03_finance_business_rules.md` | `SOL-FIN-003` | Business rules `FIN-BR-001`–`FIN-BR-068` |
| 4 | `04_finance_table_design.md` | `SOL-FIN-004` | Table design — 7 tables |
| 5 | `05_finance_lifecycle.md` | `SOL-FIN-005` | Lifecycle rules |

## Source authority

Derives from `REF-003-F[A]`/`F[b]`/`F[c]` (NSS Bye-Law, Section F — Funds of the Kendra Sangha)
and `REF-MS-7(i)`–`(iii)` (Mahila Sangha Bye-Law, Clause 7 — Funds). The module explicitly does
not supersede either Bye-Law — where a conflict exists, the authoritative provision prevails.

## Tables (7)

`financial_year`, `financial_scope`, `fund_master`, `financial_transaction`,
`financial_receipt`, `financial_payment`, `financial_transfer`.

## Key design points

- **Financial Scope ≠ Organization** (`FIN-ARCH-001`) — a Financial Scope is an explicit
  financial context (organizational, special-event, or specific-purpose) that an organization
  may have several of (e.g. "Regular Kendra Finance" and "Janmautsaba 2027 Finance" as two
  separate scopes under one Kendra). Common financial framework — no independent finance system
  per module.
- **Unified financial transaction model** (`FIN-BR-011`) — `financial_transaction` is the single
  transaction table; `financial_receipt`/`financial_payment`/`financial_transfer` attach as
  evidence/detail rather than duplicating the ledger.
- **Business identifier convention followed correctly** — unlike the `_id`/`_code` conflict
  flagged elsewhere (`docs/PROJECT_DOCUMENTATION.md` → "Open questions / TODOs",
  `DATABASE_DESIGN_STANDARDS.md`), this module's own §4.3
  explicitly specifies `year_code` (not `year_id`) alongside the UUID `financial_year_pk`,
  matching the project's actual frozen `_code` convention.

## Backend/DDL reality

Implemented on `feature/tier12-finance` (uncommitted): DDL in `database/ddl/14_finance/` (12 tables, build Phase 11i), API in `api/routers/finance.py` (31 endpoints), `finance_setup.py` (11: accounts, per-Sangha finance heads), `finance_upi.py` (11: UPI payment requests, webhook, member pay) and `finance_authority.py` (6: Bye-Law disbursement controls for Kendra / central Mahila money — see FIN-BR-040/045/046; online payment gateway and digital payment integration remain listed as NOT frozen in the business rules §20 and were added on the owner's instruction of 2026-11-10), admin UI group "Finance" (`frontend/assets/js/finance.js`) and a member-facing "Pranami" tab in `dashboard.html`, seeds in `database/seed/12_finance/` and `database/seed/00_bootstrap/08_finance_permissions_patch.sql`. Decisions the design left open (payment methods as `master_data`, `NUMERIC(14,2)` amounts, status CHECK lists, proposed RBAC grants, maker-checker) are listed in `CLAUDE.md` -> Open items and `database/ddl/14_finance/README.md`; none of them amends the frozen design documents. Only the DB-free tests have run.

## Not yet reconciled

The cross-module consolidation docs
(`docs/03_Solution/database/DATABASE_DESIGN_STANDARDS.md`, `docs/03_Solution/security/
SECURITY_ARCHITECTURE.md`) don't list Finance's 7 tables in their source inventory. Not a
contradiction, just an update those docs haven't caught up to yet.
