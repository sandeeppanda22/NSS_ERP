# database/ddl/14_finance/

Finance module DDL — 7 tables (Tier 12, **work in progress on `feature/tier12-finance`, uncommitted**). Built as
Phase 11i of `02_build.sh`/`.ps1` and `render_build.sh` (after Live refresh, before the Phase 12 writer grant and
Phase 14 audit trigger, so both cover these tables). Design authority: `docs/03_Solution/modules/finance/`
(`SOL-FIN-001`..`005`, status `DRAFT — SOURCE ALIGNED`).

| File | Table | Notes |
|---|---|---|
| `01_financial_year.sql` | `financial_year` | `year_code` unique (e.g. `2026-27`); status PLANNED/OPEN/CLOSING/CLOSED; `start_date < end_date`. |
| `02_financial_scope.sql` | `financial_scope` | Not an Organization (FIN-ARCH-001): nullable `organization_pk`, optional year, self-referencing `parent_scope_pk`; type ORGANIZATION/EVENT/SPECIAL_PURPOSE/RESTRICTED_FUND; status DRAFT/ACTIVE/CLOSING/CLOSED. |
| `03_fund_master.sql` | `fund_master` | `(financial_scope_pk, fund_code)` unique; 10 fund types; restricted fund must carry `restriction_purpose`; status DRAFT/ACTIVE/INACTIVE. |
| `04_financial_transaction.sql` | `financial_transaction` | The single ledger table; year + scope mandatory, fund/person/sangha_sevi optional; `amount NUMERIC(14,2) > 0`; direction by `transaction_type`. |
| `05_financial_receipt.sql` | `financial_receipt` | Evidence for a transaction; DRAFT/ISSUED/CANCELLED; cancellation needs a reason; never deleted. |
| `06_financial_payment.sql` | `financial_payment` | Evidence for a transaction; payment method via `master_data` (catalogue pending, seeded candidates). |
| `07_financial_transfer.sql` | `financial_transfer` | Between two DIFFERENT scopes (CHECK); optional source/destination fund. |

Payment method (`financial_receipt` / `financial_payment`): `payment_method_master_data_pk` -> `master_data` category `PAYMENT_METHOD` (owner decision 2026-11-10; UPI is the demo method) plus a free-text `instrument_reference` (UPI id / cheque no.) - both additions to SOL-FIN-004. Reference data and RBAC: `database/seed/12_finance/01_finance_reference_data_patch.sql` (payment methods, id sequences `FTX`/`RCT`/`PAY`/`FTR`, initial year 2026-27) and `database/seed/00_bootstrap/08_finance_permissions_patch.sql`.

**Proposed, not frozen (owner to confirm):** `NUMERIC(14,2)` precision and strictly-positive amounts (the
`ADJUSTMENT` sign convention and reversal mechanism are PENDING, lifecycle §40); status values taken from the
lifecycle doc as CHECK lists (not `master_data`) plus `REJECTED`/`CANCELLED` where the lifecycle names them;
`transaction_reference`/`receipt_number`/`payment_reference`/`transfer_reference` generators (`next_id()` rows) are
not seeded yet. Built on top: API `api/routers/finance.py`, admin UI `frontend/assets/js/finance.js`, `03_validate` checks, live-refresh watch list (the 7 tables), tests under `tests/{api,security,db,ui}/*finance*`.

Verified only in a throwaway PostgreSQL 18 single-user instance (stub parent tables): all 7 tables create, a re-run is
idempotent, and the key CHECK constraints reject bad rows. Not run against the project DB.
