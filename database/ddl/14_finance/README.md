# database/ddl/14_finance/

Finance module DDL — **12 tables** (Tier 12, work in progress on `feature/tier12-finance`, **uncommitted**). Built as
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
| `13_finance_disbursement_authority.sql` | `finance_disbursement_authority` | **Bye-Law controls on money leaving the Kendra / central Mahila Sangha.** One row per payment or transfer-out (exactly one target, CHECK). Keeps the three Kendra steps SEPARATE (FIN-BR-040): the Governing Body resolution + scheme + permitted purpose, the President's written order (CHECK: mandatory when `bye_law_basis = 'KENDRA'`, never before the resolution), then the Treasurer's and Secretary's signatures (F[b], MS-7(ii): two DIFFERENT persons, Secretary only after the Treasurer). Other levels have no row: their authorization matrix is PENDING (FIN-BR-044). |
| `12_finance_heads_patch.sql` | (patch) | Idempotent `run_sql`, runs AFTER `seed/12_finance/02_finance_head_templates_patch.sql`: brings a database built with the OLD `financial_transaction` (fixed category CHECK, no head) to the new shape by mapping every existing row onto the template with the same old category code. A no-op on a fresh build. |

Reference data and RBAC: `database/seed/12_finance/01_finance_reference_data_patch.sql` (`PAYMENT_METHOD` incl. UPI, id
sequences `FTX`/`RCT`/`PAY`/`FTR`/`PRQ`, initial year 2026-27), `database/seed/12_finance/02_finance_head_templates_patch.sql`
(the 12 Kendra templates: the former category codes verbatim, so nothing is lost), `database/seed/12_finance/03_finance_disbursement_purpose_patch.sql`
(`DISBURSEMENT_PURPOSE` master data: the 11 Kendra purposes of F[c](ii)-(v) and F[A](vi) and the 9 Mahila purposes of 7(iii), `KENDRA_*`/`MAHILA_*`) and
`database/seed/00_bootstrap/08_finance_permissions_patch.sql` (`FINANCE_VIEW`/`FINANCE_MANAGE`/`FINANCE_APPROVE`).

**Proposed, not frozen (owner to confirm):** `NUMERIC(14,2)` strictly-positive amounts (the `ADJUSTMENT` sign / reversal rule
is PENDING, lifecycle §40); status CHECK lists from the lifecycle doc; the `FINANCE_*` grants; that a head's code, direction,
restriction and required fund type never change after creation; the head/template model itself; and the retention of
`finance_gateway_event.payload`. Heads that existing rows were backfilled to are the global TEMPLATES (historical only):
the API requires NEW transactions to use a head owned by the scope's organization.

**Verification (2026-11-10).** The real `02_build.sh` and `03_validate.sh` were run, unmodified, against a throwaway
single-user PostgreSQL 18 through a `psql` stand-in (the authoring sandbox forbids sockets, so this is not the project
database): fresh build — every Finance phase `[OK]` (before the Bye-Law disbursement table was added: 90 tables, the harness has since applied that table and its seed patch and exercised its CHECKs; the full build was not re-run), 91 tables now, live triggers + marker rows on the 10 live tables, audit
trigger on all 11, writer role INSERT/UPDATE but no DELETE, backend SELECT only; `03_validate` 350 passed / 0 failed; a
second `02_build` run skipped 114 scripts and duplicated nothing; an OLD-shape database holding rows was upgraded by the
patch with every existing transaction mapped to its head; `tests/db/test_finance_schema.py` 103/103 (55 DB-free + 48
against that database). Not verified: anything on the project database, PowerShell scripts, Render/Neon.

**Fixed-amount contributions (2026-11-15).** `finance_head` gained `fixed_amount NUMERIC(14,2)`, `due_period`
(`YEARLY`/`MONTHLY`/`ONE_TIME`), `allow_part_payment` and `applies_to_all_sakhas` (CHECKs `chk_finance_head_fixed_amount`,
`_due_period`, `_amount_period`, `_all_sakhas`: an all-Sakhas source is an owned INCOME head that never collects itself). They
are in the `CREATE TABLE` for fresh builds and in `14_finance_head_fixed_amount_patch.sql` (idempotent `run_sql`, after
`12_finance_heads_patch.sql`, wired in `02_build.sh`/`.ps1`/`render_build.sh`) for existing databases. A Sakha's copy of a
Kendra head points back through `template_head_pk`. Checked only in a throwaway single-user PostgreSQL 18 (fresh table and
patched old-shape table behave the same, patch twice is a no-op); not run on the project database.

**Several contributions in one payment (2026-11-17).** `19_upi_payment_request_line.sql` (existence-gated table): one row per
contribution of a multi-item UPI payment (head, scope, fund, amount, and once booked its own transaction and receipt). The request's
head / scope / fund are the first line's (NOT NULL on the request) and its amount is the sum; a request with no lines is an ordinary
single-head payment. On the live-refresh list; checked by `03_validate`. The DDL was run (twice, idempotent) in a throwaway
single-user PostgreSQL 18 only.

**Sakha approval chain (2026-11-17).** `finance_head` gained `skips_approval`, `treasurer_limit`, `requires_member` (CHECKs
`chk_finance_head_skips_approval` / `_treasurer_limit` / `_requires_member`: income-only / expense-only) in the `CREATE TABLE` and in
`15_finance_head_approval_patch.sql` (idempotent `run_sql`, after the fixed-amount patch). Three new tables (existence-gated):
`16_finance_transaction_bill.sql` (a spend's bills: vendor, number, date, amount, optional `https` link; soft delete),
`17_finance_approval_step.sql` (one row per Treasurer / President / Secretary decision, keyed `(transaction, step_no)`, the
Secretary only as `cover_reason = PRESIDENT_SEAT_VACANT`) and `18_finance_approval_policy.sql` (the Sakha's default Treasurer
limit). `seed/12_finance/04_finance_head_approval_patch.sql` flags the pre-defined income templates (Parichaya Patra, Anumati
Patra, the Pranami heads, subscription) `skips_approval` and adds the `MEMBER_REIMBURSEMENT` template;
`seed/00_bootstrap/09_finance_configure_permission_patch.sql` adds `FINANCE_CONFIGURE` (admin, Kendra admin, Sakha admin). The three
tables are on the live-refresh list; `03_validate` checks them and expects four `FINANCE_*` permissions. Verified only in a throwaway
single-user PostgreSQL 18 (fresh vs patched old-shape table, constraints, idempotent patches); never run against the project database.

**Kendra annual budget (2026-11-22, FIN-BR-041).** Two new existence-gated tables, `21_finance_budget.sql` and `22_finance_budget_line.sql`
(`finance_budget` -> `finance_budget_line`, so 21 runs first; both are on the live-refresh list, `03_validate` checks them, rebuild needed).
`finance_budget`: one ACTIVE row per Kendra organization per financial year (partial unique index), `status` DRAFT -> REFERRED ->
VIEWS_RECEIVED -> PASSED, and the facts of each step - `referred_on`; `advisory_reference` / `advisory_views_date` /
`advisory_views_summary`; `resolution_reference` / `resolution_date`. CHECKs make each step's facts present from that step on and absent
before it, and keep the dates in that order (referral <= the Advisory Board's views <= the resolution), so the database says what the API
says. `finance_budget_line`: one ACTIVE planned amount (> 0) per finance head per budget. "Actual" is never stored: it is read from the
POSTED / SETTLED transactions. The rules live in `api/services/finance_budget.py`. Verified only in a throwaway single-user PostgreSQL 18
(the DDL, every CHECK and unique index, and the service's own queries against sample data).
`23_finance_budget_letters_patch.sql` (idempotent `run_sql` on every build, after the Correspondence DDL) adds `referral_correspondence_pk` and
`views_correspondence_pk` (FKs to `nss.correspondence`) for the letters the budget files automatically; a fresh build has them in `21_` already, and
the patch gives them to a database whose `finance_budget` was built before (checked on an old-shaped table, run twice).

**Sinking Fund reimbursement (2026-11-24, FIN-BR-026; Bye-Law C(i)(2)(xviii)).** Two new existence-gated tables, `24_finance_sinking_reimbursement.sql` (one row per take-over expenditure: the expenditure's transaction, the reason, an optional resolution, the amount owed fixed at registration, reference `SRB<n>`) and `25_finance_sinking_reimbursement_entry.sql` (links the income entries by which the Sakha pays back to the obligation). Who owes, the fund and the date are read from the expenditure and what is reimbursed from the POSTED / SETTLED linked entries, so neither is stored. One live obligation per expenditure and one live link per entry (partial unique indexes). The patch `seed/12_finance/07_sinking_reimbursement_patch.sql` adds the `SRB` sequence, the `SINKING_REIMBURSEMENT` Kendra head template and the `KENDRA_SAKHA_TAKEOVER` disbursement purpose.

**Kendra annual audit (2026-11-26, Bye-Law Section G).** One new existence-gated table, `27_finance_year_audit.sql`: one row per (financial year, Kendra organization) while active; status `APPOINTED` -> `REPORT_RECEIVED` -> `PLACED_BEFORE_GB` -> `APPROVED` -> `PLACED_BEFORE_GENERAL_BODY`, each step's facts present from that step on and absent before it (CHECKs), dates in order, the Advisory Board letter linked by `advisory_correspondence_pk`. The year's status gates nothing. Wired into `02_build.sh`/`.ps1`, `render_build.sh`, `03_validate.sh`/`.ps1` and the live-feed trigger list; a rebuild is needed for existing databases only to create the table (it is a new table, so `run_ddl` creates it without touching others).

**Closing the year Sakha by Sakha and Kendra (2026-11-25).** One new existence-gated table, `26_finance_year_closing.sql`: one row per (financial year, Sangha) once that Sangha starts closing its own books (CLOSING, then CLOSED with `closed_on`); no row means the Sangha is still OPEN. The year itself stays one calendar record in `financial_year`.
