# database/ddl/14_finance/

Finance module DDL — **11 tables** (Tier 12, work in progress on `feature/tier12-finance`, **uncommitted**). Built as
Phase 11i of `02_build.sh`/`.ps1` and `render_build.sh` (after Live refresh, before the Phase 12 writer grant and
Phase 14 audit trigger, so both cover these tables; the live-refresh trigger file is invoked at the END of the phase).
Design authority: `docs/03_Solution/modules/finance/` (`SOL-FIN-001`..`005`, `DRAFT — SOURCE ALIGNED`) as amended by
the owner decisions of 2026-11-10 below. File numbers are the build (dependency) order.

| File | Table | Notes |
|---|---|---|
| `01_financial_year.sql` | `financial_year` | `year_code` unique (e.g. `2026-27`); status PLANNED/OPEN/CLOSING/CLOSED; `start_date < end_date`. |
| `02_financial_scope.sql` | `financial_scope` | Not an Organization (FIN-ARCH-001): nullable `organization_pk`, optional year, self-referencing `parent_scope_pk`; type ORGANIZATION/EVENT/SPECIAL_PURPOSE/RESTRICTED_FUND; status DRAFT/ACTIVE/CLOSING/CLOSED. |
| `03_fund_master.sql` | `fund_master` | `(financial_scope_pk, fund_code)` unique; 10 fund types; restricted fund must carry `restriction_purpose`; status DRAFT/ACTIVE/INACTIVE. |
| `04_financial_account.sql` | `financial_account` | **A Sangha's receiving account** (owner decision: UPI into each Sangha's own account). Stores the **last four digits only** (`account_number_last4`), never a full number, and **no secret**: `gateway_credential_ref` is the NAME of a server-side credential set (env `UPI_<REF>_KEY_ID`/`_KEY_SECRET`/`_WEBHOOK_SECRET`); format CHECKs on IFSC, UPI id and the credential-name pattern; one default per organization (partial unique index). `gateway_provider` is validated by the API against the adapter registry, not a CHECK (a new adapter needs no rebuild). |
| `05_finance_head.sql` | `finance_head` | **The customizable purpose of a transaction** (replaces the former fixed 12-value category CHECK). `organization_pk NULL` = a Kendra **template**; a Sangha adopts templates into its own catalogue (`organization_pk` = the Sangha, `template_head_pk` = source). Each head carries its rules: `direction`, `is_restricted` (+ purpose), `required_fund_type` (e.g. `SINKING_FUND`), `is_pranami` (shown in the member's Pranami tab), `allow_upi` + `collection_scope_pk`/`collection_fund_pk`/`collection_account_pk`. DB CHECKs: code format, restricted needs a purpose, Pranami/UPI are income-only, UPI needs a scope + account, a template is inert (never collects). Templates have their own partial unique index (NULL organizations are distinct in a plain UNIQUE). |
| `06_financial_transaction.sql` | `financial_transaction` | The single ledger table; `finance_head_pk NOT NULL`; `transaction_category` kept as an **immutable snapshot of the head's code**; year + scope mandatory; `amount NUMERIC(14,2) > 0`, direction by `transaction_type`. |
| `07_financial_receipt.sql` | `financial_receipt` | Evidence for a transaction; DRAFT/ISSUED/CANCELLED; cancellation needs a reason; payment method (`master_data`) + `instrument_reference`; never deleted. |
| `08_financial_payment.sql` | `financial_payment` | Evidence for a transaction; payment method via `master_data` + `instrument_reference`. |
| `09_financial_transfer.sql` | `financial_transfer` | Between two DIFFERENT scopes (CHECK); optional source/destination fund. |
| `10_upi_payment_request.sql` | `upi_payment_request` | One request to collect money by UPI: head, account, scope, optional fund, payer (member or name), `provider` + unique `provider_order_id`, `pay_url`/`upi_uri`, expiry, status CREATED/PENDING/PAID/FAILED/EXPIRED/CANCELLED. CHECKs: a PAID request carries its evidence (`provider_payment_id`, `paid_amount`, `paid_at`); a transaction hangs off a PAID request only. `review_reason` explains a PAID request waiting for a treasurer. |
| `11_finance_gateway_event.sql` | `finance_gateway_event` | **Append-only** log of every webhook the gateway sent. A partial unique index on `(provider, event_id) WHERE signature_valid` makes processing idempotent while a FORGED event can never block a real one. No soft delete, off the live feed (it carries payer details; retention is an owner decision). |
| `12_finance_heads_patch.sql` | (patch) | Idempotent `run_sql`, runs AFTER `seed/12_finance/02_finance_head_templates_patch.sql`: brings a database built with the OLD `financial_transaction` (fixed category CHECK, no head) to the new shape by mapping every existing row onto the template with the same old category code. A no-op on a fresh build. |

Reference data and RBAC: `database/seed/12_finance/01_finance_reference_data_patch.sql` (`PAYMENT_METHOD` incl. UPI, id
sequences `FTX`/`RCT`/`PAY`/`FTR`/`PRQ`, initial year 2026-27), `database/seed/12_finance/02_finance_head_templates_patch.sql`
(the 12 Kendra templates: the former category codes verbatim, so nothing is lost) and
`database/seed/00_bootstrap/08_finance_permissions_patch.sql` (`FINANCE_VIEW`/`FINANCE_MANAGE`/`FINANCE_APPROVE`).

**Proposed, not frozen (owner to confirm):** `NUMERIC(14,2)` strictly-positive amounts (the `ADJUSTMENT` sign / reversal rule
is PENDING, lifecycle §40); status CHECK lists from the lifecycle doc; the `FINANCE_*` grants; that a head's code, direction,
restriction and required fund type never change after creation; the head/template model itself; and the retention of
`finance_gateway_event.payload`. Heads that existing rows were backfilled to are the global TEMPLATES (historical only):
the API requires NEW transactions to use a head owned by the scope's organization.

**Verification (2026-11-10).** The real `02_build.sh` and `03_validate.sh` were run, unmodified, against a throwaway
single-user PostgreSQL 18 through a `psql` stand-in (the authoring sandbox forbids sockets, so this is not the project
database): fresh build — every Finance phase `[OK]`, 90 tables, live triggers + marker rows on the 10 live tables, audit
trigger on all 11, writer role INSERT/UPDATE but no DELETE, backend SELECT only; `03_validate` 350 passed / 0 failed; a
second `02_build` run skipped 114 scripts and duplicated nothing; an OLD-shape database holding rows was upgraded by the
patch with every existing transaction mapped to its head; `tests/db/test_finance_schema.py` 103/103 (55 DB-free + 48
against that database). Not verified: anything on the project database, PowerShell scripts, Render/Neon.
