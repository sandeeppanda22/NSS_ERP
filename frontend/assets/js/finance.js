/**
 * Finance admin screens (Tier 12) — mixed into `adminPanel()` (admin.js), which
 * owns the sidebar, the tab state and the /admin entry guard.
 *
 * Four tabs share this one mixin (prefix `fin`):
 *   finOverview      summary dashboard (totals, pending work, per-fund balances, per-category totals)
 *   finStructure     financial years, financial scopes and the funds of a scope
 *   finTransactions  the unified transaction list/detail with receipt + payment evidence
 *   finTransfers     transfers between two financial scopes
 *
 * Authorization is the server's (api/routers/finance.py): FINANCE_VIEW reads,
 * FINANCE_MANAGE records / edits / submits, FINANCE_APPROVE approves / posts /
 * executes / cancels / opens and closes — all bounded by admin scope on the
 * financial scope's organization. This file only HIDES controls the API would
 * refuse (canManageFinance / canApproveFinance, and the lifecycle buttons come
 * from the server's own table via GET /finance/reference, so they can never
 * drift from it) and shows the server's message verbatim (NSS.extractError /
 * NSS.errorMessage) for everything else.
 *
 * Money arrives as decimal strings and is shown with NSS.formatMoney. Payment
 * methods (UPI, cash, ...) are master data served by /finance/reference.
 * Every loader captures a sequence number and discards its response when the
 * user has since moved on (stale-response guard), like assets-property.js.
 */
(function () {
    "use strict";

    const BASE = "/api/v1/finance";
    const JSON_HEADERS = { "Content-Type": "application/json" };
    const MONEY_RE = /^\d+(\.\d{1,2})?$/;

    const blank = (v) => {
        const t = (v == null ? "" : String(v)).trim();
        return t === "" ? null : t;
    };
    const isoToday = () => {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    };
    const emptyPicker = (extra) => ({ query: "", results: [], searching: false, selected: null, ...(extra || {}) });

    // Verbs for the lifecycle buttons, keyed by the TARGET status.
    const STEP_VERBS = {
        OPEN: "Open year", CLOSING: "Start closing", CLOSED: "Close",
        ACTIVE: "Activate", INACTIVE: "Deactivate",
        PENDING_APPROVAL: "Submit for approval", APPROVED: "Approve", REJECTED: "Reject",
        POSTED: "Post", SETTLED: "Mark settled", CANCELLED: "Cancel",
        ISSUED: "Issue receipt", INITIATED: "Initiate payment", COMPLETED: "Mark completed", EXECUTED: "Execute",
    };

    const newTx = () => ({ show: false, saving: false, error: "", entity: "", pk: "", label: "", target: "", remarks: "", remarksRequired: false });
    const newYearForm = () => ({ show: false, saving: false, error: "", start_year: "" });
    const newScopeForm = () => ({
        show: false, saving: false, error: "", scope_code: "", scope_name: "", scope_type: "ORGANIZATION",
        organization: emptyPicker(), financial_year_pk: "", parent_scope_pk: "",
    });
    const newScopeEdit = () => ({ show: false, saving: false, error: "", name: "" });
    const newFundForm = () => ({
        show: false, saving: false, error: "", fund_code: "", fund_name: "", fund_type: "GENERAL",
        is_restricted: false, restriction_purpose: "", organization: emptyPicker({ typeCodes: NSS.SAKHA_LIKE_ORG_TYPES }),
    });
    const newFundEdit = () => ({ pk: "", saving: false, error: "", name: "", purpose: "" });
    const newTxnForm = () => ({
        show: false, mode: "create", pk: "", saving: false, error: "",
        financial_year_pk: "", financial_scope_pk: "", fund_master_pk: "", transaction_type: "INCOME",
        transaction_category: "", amount: "", transaction_date: "", description: "", sangha_sevi_id: "",
    });
    const newReceiptForm = () => ({
        show: false, saving: false, error: "", receipt_date: "", amount: "", received_from: "",
        payment_method_code: "", instrument_reference: "",
    });
    const newPaymentForm = () => ({
        show: false, saving: false, error: "", payment_date: "", amount: "", paid_to: "",
        payment_method_code: "", instrument_reference: "",
    });
    const newTransferForm = () => ({
        show: false, saving: false, error: "", financial_year_pk: "", source_scope_pk: "", destination_scope_pk: "",
        source_fund_pk: "", destination_fund_pk: "", amount: "", transfer_date: "", purpose: "",
    });

    function financeMixin() {
        return {
            // ── Permissions (the live /auth/me payload) ────────────────
            _finPerms() {
                return (this.currentUser || NSSAuth.getCachedUser() || {}).permissions || [];
            },
            get canViewFinance() {
                const p = this._finPerms();
                return p.includes("FINANCE_VIEW") || p.includes("FINANCE_MANAGE") || p.includes("FINANCE_APPROVE");
            },
            get canManageFinance() {
                const p = this._finPerms();
                return p.includes("FINANCE_MANAGE") || p.includes("FINANCE_APPROVE");
            },
            get canApproveFinance() {
                return this._finPerms().includes("FINANCE_APPROVE");
            },

            // ── Reference data (pick-lists + the server's lifecycle table) ──
            finRef: null,
            finNotice: "",
            finTx: newTx(),          // the one lifecycle dialog (remarks) shared by every entity

            async finLoadRef() {
                if (this.finRef) return;
                try {
                    this.finRef = await this._finGet("/reference");
                } catch { /* non-fatal: the pick-lists stay empty and the next open retries */ }
            },
            get finPaymentMethods() { return (this.finRef && this.finRef.payment_methods) || []; },
            get finFundTypes() { return (this.finRef && this.finRef.fund_types) || []; },
            get finScopeTypes() { return (this.finRef && this.finRef.scope_types) || []; },
            get finTxnTypes() { return (this.finRef && this.finRef.transaction_types) || []; },
            get finStatuses() { return (this.finRef && this.finRef.statuses) || {}; },

            finLabel(status) { return NSS.financeStatusLabel(status); },
            finBadge(status) { return NSS.financeStatusBadgeClass(status); },
            finMoney(v) { return NSS.formatMoney(v); },
            finCode(code) { return NSS.codeLabel(code); },

            // ── Small request helpers ─────────────────────────────────
            async _finGet(path, params) {
                const qs = params ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)) : "";
                const res = await NSSAuth.apiFetch(BASE + path + qs);
                if (!res.ok) throw new Error(await NSS.extractError(res));
                return res.json();
            },
            async _finSend(method, path, body) {
                const res = await NSSAuth.apiFetch(BASE + path, {
                    method, headers: JSON_HEADERS, body: body === undefined ? undefined : JSON.stringify(body),
                });
                if (!res.ok) throw new Error(await NSS.extractError(res));
                return res.json();
            },
            _finNote(text) {
                this.finNotice = text;
                clearTimeout(this._finNoticeTimer);
                this._finNoticeTimer = setTimeout(() => { this.finNotice = ""; }, 6000);
            },
            _finMoneyOk(value, label) {
                if (!MONEY_RE.test(String(value || "").trim()) || Number(value) <= 0) {
                    return `${label} must be a positive amount with at most two decimals.`;
                }
                return "";
            },

            // ── Lifecycle buttons from the server's own table ─────────
            // entity: year | scope | fund | transaction | receipt | payment | transfer
            finActions(entity, status) {
                if (!this.finRef) return [];
                return (this.finRef.transitions[entity] || [])
                    .filter((t) => t.from === status)
                    .filter((t) => (t.permission === "FINANCE_APPROVE" ? this.canApproveFinance : this.canManageFinance))
                    .map((t) => ({ to: t.to, label: STEP_VERBS[t.to] || NSS.codeLabel(t.to), remarks: t.remarks, danger: ["REJECTED", "CANCELLED", "CLOSED", "INACTIVE"].includes(t.to) }));
            },

            finAskTransition(entity, pk, label, action) {
                this.finTx = {
                    ...newTx(), show: true, entity, pk, label, target: action.to,
                    remarksRequired: !!action.remarks, verb: action.label,
                };
            },
            finCancelTransition() { this.finTx = newTx(); },

            async finConfirmTransition() {
                const t = this.finTx;
                if (t.remarksRequired && !blank(t.remarks)) {
                    t.error = "Please give a reason (remarks).";
                    return;
                }
                t.saving = true; t.error = "";
                try {
                    await this._finSend("POST", `/${t.entity === "year" ? "years" : t.entity + "s"}/${t.pk}/transition`,
                        { status: t.target, remarks: blank(t.remarks) });
                    const note = `${t.label}: ${NSS.financeStatusLabel(t.target)}.`;
                    this.finTx = newTx();
                    this._finNote(note);
                    await this._finReloadAfter(t.entity);
                } catch (err) {
                    t.error = err.message || "The change was refused.";
                } finally {
                    t.saving = false;
                }
            },

            async _finReloadAfter(entity) {
                if (entity === "year") { await this.finLoadYears(); if (this.activeTab === "finOverview") await this.finLoadSummary(); return; }
                if (entity === "scope" || entity === "fund") {
                    await this.finLoadScopes({ silent: true });
                    if (this.finScope) await this.finReloadScope();
                    return;
                }
                if (entity === "transfer") { await this.finLoadTransfers({ silent: true }); if (this.finTransfer) await this.finReloadTransfer(); return; }
                await this.finLoadTxns({ silent: true });                         // transaction / receipt / payment
                if (this.finTxn) await this.finReloadTxn();
            },

            // ── Tab entry ─────────────────────────────────────────────
            async finEnterTab(tab) {
                if (tab) this.activeTab = tab;
                this.finNotice = "";
                this.finTx = newTx();
                await this.finLoadRef();
                if (this.activeTab === "finOverview") {
                    await this.finLoadYears();
                    await this.finLoadSummary();
                } else if (this.activeTab === "finStructure") {
                    this.finScope = null; this.finScopeForm = newScopeForm(); this.finYearForm = newYearForm();
                    await Promise.all([this.finLoadYears(), this.finLoadScopes()]);
                } else if (this.activeTab === "finTransactions") {
                    this.finTxn = null; this.finTxnForm = newTxnForm();
                    await Promise.all([this.finLoadYears(), this.finLoadScopeOptions(), this.finLoadTxns()]);
                } else if (this.activeTab === "finTransfers") {
                    this.finTransfer = null; this.finTransferForm = newTransferForm();
                    await Promise.all([this.finLoadYears(), this.finLoadScopeOptions(), this.finLoadTransfers()]);
                }
            },

            // Live refresh hooks (LIVE_REFRESH_CONFIG in admin.js)
            finLiveBusy() {
                return [this.finYearForm, this.finScopeForm, this.finScopeEdit, this.finFundForm, this.finTxnForm,
                    this.finReceiptForm, this.finPaymentForm, this.finTransferForm, this.finTx]
                    .some((f) => f && (f.show || f.saving)) || !!this.finFundEdit.pk;
            },
            async finLiveReload() {
                const tab = this.activeTab;
                if (tab === "finOverview") { await this.finLoadYears(); await this.finLoadSummary({ silent: true }); }
                else if (tab === "finStructure") {
                    await this.finLoadYears();
                    if (this.finScope) await this.finReloadScope(); else await this.finLoadScopes({ silent: true });
                } else if (tab === "finTransactions") {
                    if (this.finTxn) await this.finReloadTxn(); else await this.finLoadTxns({ silent: true });
                } else if (tab === "finTransfers") {
                    if (this.finTransfer) await this.finReloadTransfer(); else await this.finLoadTransfers({ silent: true });
                }
            },

            // ═════════════════════════════════════════════════════════
            // Years
            // ═════════════════════════════════════════════════════════
            finYears: [], finYearsError: "", finYearForm: newYearForm(),
            get finOpenYears() { return this.finYears.filter((y) => y.status === "OPEN"); },

            async finLoadYears() {
                try {
                    this.finYears = (await this._finGet("/years")).items;
                    this.finYearsError = "";
                } catch (err) {
                    this.finYearsError = err.message || "Failed to load financial years.";
                }
            },
            finOpenYearForm() {
                const latest = this.finYears.length ? Math.max(...this.finYears.map((y) => Number(y.year_code.slice(0, 4)))) : new Date().getFullYear() - 1;
                this.finYearForm = { ...newYearForm(), show: true, start_year: String(latest + 1) };
            },
            async finSubmitYear() {
                const f = this.finYearForm;
                const y = Number(f.start_year);
                if (!Number.isInteger(y) || y < 2000 || y > 2100) { f.error = "Enter a starting year between 2000 and 2100."; return; }
                f.saving = true; f.error = "";
                try {
                    const created = await this._finSend("POST", "/years", { start_year: y });
                    this.finYearForm = newYearForm();
                    this._finNote(`Financial year ${created.year_code} created (Planned). Open it to start recording.`);
                    await this.finLoadYears();
                } catch (err) {
                    f.error = err.message || "Could not create the financial year.";
                } finally {
                    f.saving = false;
                }
            },

            // ═════════════════════════════════════════════════════════
            // Summary
            // ═════════════════════════════════════════════════════════
            finSummary: null, finSummaryError: "", finSummaryLoading: false,
            finSumYear: "", finSumScope: "", _finSumSeq: 0,

            async finLoadSummary(opts = {}) {
                const seq = ++this._finSumSeq;
                if (!opts.silent) { this.finSummaryLoading = true; this.finSummaryError = ""; }
                try {
                    if (!this.finScopeOptions.length) await this.finLoadScopeOptions();
                    const data = await this._finGet("/summary", { financial_year_pk: this.finSumYear, financial_scope_pk: this.finSumScope });
                    if (seq !== this._finSumSeq) return;
                    this.finSummary = data;
                    if (!this.finSumYear && data.financial_year_pk) this.finSumYear = data.financial_year_pk;
                } catch (err) {
                    if (seq !== this._finSumSeq || opts.silent) return;
                    this.finSummary = null;
                    this.finSummaryError = err.message || "Failed to load the summary.";
                } finally {
                    if (seq === this._finSumSeq) this.finSummaryLoading = false;
                }
            },
            finSummaryChanged() { return this.finLoadSummary(); },
            get finPending() {
                return this.finSummary ? this.finSummary.pending_transactions + this.finSummary.pending_transfers : 0;
            },

            // ═════════════════════════════════════════════════════════
            // Scopes (+ funds of the open scope)
            // ═════════════════════════════════════════════════════════
            finScopes: [], finScopesTotal: 0, finScopesPage: 1, finScopesPageSize: 20,
            finScopeQ: "", finScopeTypeFilter: "", finScopeStatusFilter: "",
            finScopesLoading: false, finScopesError: "", _finScopeSeq: 0,
            finScopeForm: newScopeForm(), finScopeEdit: newScopeEdit(),
            finScope: null, finScopeDetailError: "",
            finFunds: [], finFundsError: "", finFundForm: newFundForm(), finFundEdit: newFundEdit(),
            // Every ACTIVE scope, for the pick-lists of the transaction / transfer forms and the summary.
            finScopeOptions: [], finFundOptions: {},          // scope_pk -> [ACTIVE funds]

            get finScopesTotalPages() { return Math.max(1, Math.ceil(this.finScopesTotal / this.finScopesPageSize)); },

            async finLoadScopeOptions() {
                try {
                    this.finScopeOptions = (await this._finGet("/scopes", { status: "ACTIVE", page_size: 100 })).items;
                } catch { /* the pick-lists stay empty */ }
            },
            async finFundsFor(scopePk) {
                if (!scopePk) return [];
                if (!this.finFundOptions[scopePk]) {
                    try {
                        const items = (await this._finGet("/funds", { financial_scope_pk: scopePk, status: "ACTIVE", page_size: 100 })).items;
                        this.finFundOptions = { ...this.finFundOptions, [scopePk]: items };
                    } catch { return []; }
                }
                return this.finFundOptions[scopePk];
            },

            async finLoadScopes(opts = {}) {
                const seq = ++this._finScopeSeq;
                if (!opts.silent) { this.finScopesLoading = true; this.finScopesError = ""; }
                try {
                    const data = await this._finGet("/scopes", {
                        q: this.finScopeQ.trim(), scope_type: this.finScopeTypeFilter, status: this.finScopeStatusFilter,
                        page: this.finScopesPage, page_size: this.finScopesPageSize,
                    });
                    if (seq !== this._finScopeSeq) return;
                    this.finScopes = data.items; this.finScopesTotal = data.total;
                } catch (err) {
                    if (seq !== this._finScopeSeq || opts.silent) return;
                    this.finScopes = []; this.finScopesTotal = 0;
                    this.finScopesError = err.message || "Failed to load financial scopes.";
                } finally {
                    if (seq === this._finScopeSeq) this.finScopesLoading = false;
                }
            },
            finApplyScopeFilters() { this.finScopesPage = 1; return this.finLoadScopes(); },
            finClearScopeFilters() { this.finScopeQ = ""; this.finScopeTypeFilter = ""; this.finScopeStatusFilter = ""; return this.finApplyScopeFilters(); },
            finScopesPageBy(d) { this.finScopesPage = Math.min(Math.max(1, this.finScopesPage + d), this.finScopesTotalPages); return this.finLoadScopes(); },

            finOpenScopeForm() {
                this.finScope = null;
                this.finScopeForm = { ...newScopeForm(), show: true };
            },
            async finSubmitScope() {
                const f = this.finScopeForm;
                if (!blank(f.scope_code) || !blank(f.scope_name)) { f.error = "Scope code and name are required."; return; }
                if (f.scope_type === "ORGANIZATION" && !f.organization.selected) { f.error = "An organization scope must name its organization."; return; }
                f.saving = true; f.error = "";
                try {
                    const body = {
                        scope_code: f.scope_code.trim(), scope_name: f.scope_name.trim(), scope_type: f.scope_type,
                        organization_pk: f.organization.selected ? f.organization.selected.organization_pk : null,
                        financial_year_pk: f.financial_year_pk || null, parent_scope_pk: f.parent_scope_pk || null,
                    };
                    const created = await this._finSend("POST", "/scopes", body);
                    this.finScopeForm = newScopeForm();
                    this._finNote(`Scope ${created.scope_code} created (Draft). Activate it to take transactions.`);
                    this.finFundOptions = {};
                    await Promise.all([this.finLoadScopes({ silent: true }), this.finLoadScopeOptions()]);
                    await this.finOpenScope(created.financial_scope_pk);
                } catch (err) {
                    f.error = err.message || "Could not create the scope.";
                } finally {
                    f.saving = false;
                }
            },

            async finOpenScope(pk) {
                this.finScopeDetailError = ""; this.finFundForm = newFundForm(); this.finFundEdit = newFundEdit(); this.finScopeEdit = newScopeEdit();
                try {
                    this.finScope = await this._finGet(`/scopes/${pk}`);
                    await this.finLoadFunds();
                } catch (err) {
                    this.finScope = null;
                    this.finScopesError = err.message || "Could not open the scope.";
                }
            },
            async finReloadScope() {
                if (!this.finScope) return;
                try {
                    this.finScope = await this._finGet(`/scopes/${this.finScope.financial_scope_pk}`);
                    await this.finLoadFunds();
                } catch (err) {
                    this.finScope = null;                      // gone / out of scope
                    await this.finLoadScopes({ silent: true });
                }
            },
            finBackToScopes() { this.finScope = null; this.finFunds = []; return this.finLoadScopes({ silent: true }); },

            finStartScopeEdit() { this.finScopeEdit = { ...newScopeEdit(), show: true, name: this.finScope.scope_name }; },
            async finSaveScopeEdit() {
                const e = this.finScopeEdit;
                if (!blank(e.name)) { e.error = "The name cannot be blank."; return; }
                e.saving = true; e.error = "";
                try {
                    this.finScope = await this._finSend("PATCH", `/scopes/${this.finScope.financial_scope_pk}`, { scope_name: e.name.trim() });
                    this.finScopeEdit = newScopeEdit();
                    this.finFundOptions = {};
                    await Promise.all([this.finLoadScopes({ silent: true }), this.finLoadScopeOptions()]);
                } catch (err) {
                    e.error = err.message || "Could not save the scope.";
                } finally {
                    e.saving = false;
                }
            },

            // Funds of the open scope
            async finLoadFunds() {
                if (!this.finScope) return;
                try {
                    this.finFunds = (await this._finGet("/funds", { financial_scope_pk: this.finScope.financial_scope_pk, page_size: 100 })).items;
                    this.finFundsError = "";
                } catch (err) {
                    this.finFundsError = err.message || "Failed to load funds.";
                }
            },
            get finFundNeedsSakha() { return this.finFundForm.fund_type === "SINKING_FUND"; },
            finOpenFundForm() { this.finFundForm = { ...newFundForm(), show: true }; },
            async finSubmitFund() {
                const f = this.finFundForm;
                if (!blank(f.fund_code) || !blank(f.fund_name)) { f.error = "Fund code and name are required."; return; }
                if (f.is_restricted && !blank(f.restriction_purpose)) { f.error = "A restricted fund must state its purpose."; return; }
                if (this.finFundNeedsSakha && !f.organization.selected) { f.error = "A Sinking Fund must name its Sakha."; return; }
                f.saving = true; f.error = "";
                try {
                    const created = await this._finSend("POST", "/funds", {
                        fund_code: f.fund_code.trim(), fund_name: f.fund_name.trim(), fund_type: f.fund_type,
                        financial_scope_pk: this.finScope.financial_scope_pk, is_restricted: f.is_restricted,
                        restriction_purpose: f.is_restricted ? f.restriction_purpose.trim() : null,
                        organization_pk: f.organization.selected ? f.organization.selected.organization_pk : null,
                    });
                    this.finFundForm = newFundForm();
                    this._finNote(`Fund ${created.fund_code} created (Draft). Activate it to use it.`);
                    this.finFundOptions = {};
                    await this.finReloadScope();
                } catch (err) {
                    f.error = err.message || "Could not create the fund.";
                } finally {
                    f.saving = false;
                }
            },
            finStartFundEdit(fund) {
                this.finFundEdit = { pk: fund.fund_master_pk, saving: false, error: "", name: fund.fund_name, purpose: fund.restriction_purpose || "", restricted: fund.is_restricted };
            },
            async finSaveFundEdit() {
                const e = this.finFundEdit;
                if (!blank(e.name)) { e.error = "The name cannot be blank."; return; }
                if (e.restricted && !blank(e.purpose)) { e.error = "A restricted fund must state its purpose."; return; }
                e.saving = true; e.error = "";
                try {
                    await this._finSend("PATCH", `/funds/${e.pk}`, { fund_name: e.name.trim(), restriction_purpose: e.restricted ? e.purpose.trim() : null });
                    this.finFundEdit = newFundEdit();
                    this.finFundOptions = {};
                    await this.finLoadFunds();
                } catch (err) {
                    e.error = err.message || "Could not save the fund.";
                } finally {
                    e.saving = false;
                }
            },

            // ═════════════════════════════════════════════════════════
            // Transactions (+ receipts / payments)
            // ═════════════════════════════════════════════════════════
            finTxns: [], finTxnsTotal: 0, finTxnsPage: 1, finTxnsPageSize: 20,
            finTxnQ: "", finTxnYear: "", finTxnScope: "", finTxnTypeFilter: "", finTxnStatusFilter: "", finTxnFrom: "", finTxnTo: "",
            finTxnsLoading: false, finTxnsError: "", _finTxnSeq: 0,
            finTxnForm: newTxnForm(), finTxn: null, finTxnDetailError: "",
            finReceipts: [], finPayments: [], finEvidenceError: "",
            finReceiptForm: newReceiptForm(), finPaymentForm: newPaymentForm(),
            finTxnFormFunds: [],

            get finTxnsTotalPages() { return Math.max(1, Math.ceil(this.finTxnsTotal / this.finTxnsPageSize)); },
            get finCategoryChoices() {
                if (!this.finRef) return [];
                const t = this.finTxnForm.transaction_type;
                return t === "INCOME" ? this.finRef.income_categories
                    : t === "EXPENSE" ? this.finRef.expense_categories
                        : [...this.finRef.income_categories, ...this.finRef.expense_categories];
            },
            // How much of the open transaction is not yet covered by receipts / payments.
            get finReceiptRemaining() {
                if (!this.finTxn) return 0;
                const live = this.finReceipts.filter((r) => r.status !== "CANCELLED").reduce((s, r) => s + Number(r.amount), 0);
                return Math.max(0, Number(this.finTxn.amount) - live);
            },
            get finPaymentRemaining() {
                if (!this.finTxn) return 0;
                const live = this.finPayments.filter((p) => p.status !== "CANCELLED").reduce((s, p) => s + Number(p.amount), 0);
                return Math.max(0, Number(this.finTxn.amount) - live);
            },
            get finCanReceipt() {
                return !!this.finTxn && this.canManageFinance && this.finTxn.transaction_type === "INCOME"
                    && ["POSTED", "SETTLED"].includes(this.finTxn.status) && this.finReceiptRemaining > 0;
            },
            get finCanPayment() {
                return !!this.finTxn && this.canManageFinance && this.finTxn.transaction_type === "EXPENSE"
                    && ["APPROVED", "POSTED", "SETTLED"].includes(this.finTxn.status) && this.finPaymentRemaining > 0;
            },

            async finLoadTxns(opts = {}) {
                const seq = ++this._finTxnSeq;
                if (!opts.silent) { this.finTxnsLoading = true; this.finTxnsError = ""; }
                try {
                    const data = await this._finGet("/transactions", {
                        q: this.finTxnQ.trim(), financial_year_pk: this.finTxnYear, financial_scope_pk: this.finTxnScope,
                        transaction_type: this.finTxnTypeFilter, status: this.finTxnStatusFilter,
                        date_from: this.finTxnFrom, date_to: this.finTxnTo,
                        page: this.finTxnsPage, page_size: this.finTxnsPageSize,
                    });
                    if (seq !== this._finTxnSeq) return;
                    this.finTxns = data.items; this.finTxnsTotal = data.total;
                } catch (err) {
                    if (seq !== this._finTxnSeq || opts.silent) return;
                    this.finTxns = []; this.finTxnsTotal = 0;
                    this.finTxnsError = err.message || "Failed to load transactions.";
                } finally {
                    if (seq === this._finTxnSeq) this.finTxnsLoading = false;
                }
            },
            finApplyTxnFilters() { this.finTxnsPage = 1; return this.finLoadTxns(); },
            finClearTxnFilters() {
                this.finTxnQ = ""; this.finTxnYear = ""; this.finTxnScope = ""; this.finTxnTypeFilter = "";
                this.finTxnStatusFilter = ""; this.finTxnFrom = ""; this.finTxnTo = "";
                return this.finApplyTxnFilters();
            },
            finTxnsPageBy(d) { this.finTxnsPage = Math.min(Math.max(1, this.finTxnsPage + d), this.finTxnsTotalPages); return this.finLoadTxns(); },

            // Create / edit
            finOpenTxnForm(txn) {
                this.finTxn = txn ? this.finTxn : null;
                const open = this.finOpenYears;
                const f = { ...newTxnForm(), show: true };
                if (txn) {
                    Object.assign(f, {
                        mode: "edit", pk: txn.financial_transaction_pk, financial_year_pk: txn.financial_year_pk,
                        financial_scope_pk: txn.financial_scope_pk, fund_master_pk: txn.fund_master_pk || "",
                        transaction_type: txn.transaction_type, transaction_category: txn.transaction_category,
                        amount: String(txn.amount), transaction_date: txn.transaction_date, description: txn.description || "",
                        sangha_sevi_id: txn.sangha_sevi_id || "",
                    });
                } else if (open.length === 1) {
                    f.financial_year_pk = open[0].financial_year_pk;
                    f.transaction_date = this._finClampDate(open[0]);
                }
                this.finTxnForm = f;
                return this.finTxnFormScopeChanged(true);
            },
            _finClampDate(year) {
                const t = isoToday();
                return t < year.start_date ? year.start_date : t > year.end_date ? year.end_date : t;
            },
            finTxnFormYearChanged() {
                const y = this.finYears.find((x) => x.financial_year_pk === this.finTxnForm.financial_year_pk);
                if (y) this.finTxnForm.transaction_date = this._finClampDate(y);
            },
            async finTxnFormScopeChanged(keepFund) {
                if (!keepFund) this.finTxnForm.fund_master_pk = "";
                this.finTxnFormFunds = await this.finFundsFor(this.finTxnForm.financial_scope_pk);
            },
            finTxnFormTypeChanged() {
                if (!this.finCategoryChoices.includes(this.finTxnForm.transaction_category)) this.finTxnForm.transaction_category = "";
            },
            async finSubmitTxn() {
                const f = this.finTxnForm;
                if (!f.financial_year_pk || !f.financial_scope_pk) { f.error = "Choose the financial year and scope."; return; }
                if (!f.transaction_category) { f.error = "Choose a category."; return; }
                const bad = this._finMoneyOk(f.amount, "Amount");
                if (bad) { f.error = bad; return; }
                if (!f.transaction_date) { f.error = "Choose the transaction date."; return; }
                f.saving = true; f.error = "";
                try {
                    const body = {
                        financial_year_pk: f.financial_year_pk, financial_scope_pk: f.financial_scope_pk,
                        fund_master_pk: f.fund_master_pk || null, transaction_type: f.transaction_type,
                        transaction_category: f.transaction_category, amount: f.amount.trim(),
                        transaction_date: f.transaction_date, description: blank(f.description),
                        // The member this money is from; it shows up in that member's own Pranami tab.
                        sangha_sevi_id: blank(f.sangha_sevi_id),
                    };
                    const saved = f.mode === "edit"
                        ? await this._finSend("PATCH", `/transactions/${f.pk}`, body)
                        : await this._finSend("POST", "/transactions", body);
                    this.finTxnForm = newTxnForm();
                    this._finNote(f.mode === "edit" ? `Transaction ${saved.transaction_reference} updated.` : `Transaction ${saved.transaction_reference} recorded as a draft.`);
                    await this.finLoadTxns({ silent: true });
                    await this.finOpenTxn(saved.financial_transaction_pk);
                } catch (err) {
                    f.error = err.message || "Could not save the transaction.";
                } finally {
                    f.saving = false;
                }
            },

            // Detail
            async finOpenTxn(pk) {
                this.finTxnDetailError = ""; this.finReceiptForm = newReceiptForm(); this.finPaymentForm = newPaymentForm();
                try {
                    this.finTxn = await this._finGet(`/transactions/${pk}`);
                    await this._finLoadEvidence();
                } catch (err) {
                    this.finTxn = null;
                    this.finTxnsError = err.message || "Could not open the transaction.";
                }
            },
            async finReloadTxn() {
                if (!this.finTxn) return;
                try {
                    this.finTxn = await this._finGet(`/transactions/${this.finTxn.financial_transaction_pk}`);
                    await this._finLoadEvidence();
                } catch {
                    this.finTxn = null;                       // gone / out of scope
                    await this.finLoadTxns({ silent: true });
                }
            },
            async _finLoadEvidence() {
                const pk = this.finTxn.financial_transaction_pk;
                try {
                    if (this.finTxn.transaction_type === "INCOME") {
                        this.finReceipts = (await this._finGet("/receipts", { financial_transaction_pk: pk, page_size: 100 })).items;
                        this.finPayments = [];
                    } else if (this.finTxn.transaction_type === "EXPENSE") {
                        this.finPayments = (await this._finGet("/payments", { financial_transaction_pk: pk, page_size: 100 })).items;
                        this.finReceipts = [];
                    } else {
                        this.finReceipts = []; this.finPayments = [];
                    }
                    this.finEvidenceError = "";
                } catch (err) {
                    this.finEvidenceError = err.message || "Failed to load receipts / payments.";
                }
            },
            finBackToTxns() { this.finTxn = null; return this.finLoadTxns({ silent: true }); },

            // Receipts
            finOpenReceiptForm() {
                const defaultMethod = (this.finPaymentMethods.find((m) => m.code === "UPI") || {}).code || "";
                this.finReceiptForm = {
                    ...newReceiptForm(), show: true, receipt_date: this.finTxn.transaction_date,
                    amount: this.finReceiptRemaining.toFixed(2), payment_method_code: defaultMethod,
                };
            },
            async finSubmitReceipt() {
                const f = this.finReceiptForm;
                const bad = this._finMoneyOk(f.amount, "Amount");
                if (bad) { f.error = bad; return; }
                if (!f.receipt_date) { f.error = "Choose the receipt date."; return; }
                f.saving = true; f.error = "";
                try {
                    const r = await this._finSend("POST", `/transactions/${this.finTxn.financial_transaction_pk}/receipts`, {
                        receipt_date: f.receipt_date, amount: f.amount.trim(), received_from: blank(f.received_from),
                        payment_method_code: f.payment_method_code || null, instrument_reference: blank(f.instrument_reference),
                    });
                    this.finReceiptForm = newReceiptForm();
                    this._finNote(`Receipt ${r.receipt_number} drafted. Issue it to make it official.`);
                    await this.finReloadTxn();
                } catch (err) {
                    f.error = err.message || "Could not draft the receipt.";
                } finally {
                    f.saving = false;
                }
            },

            // Payments
            finOpenPaymentForm() {
                const defaultMethod = (this.finPaymentMethods.find((m) => m.code === "UPI") || {}).code || "";
                this.finPaymentForm = {
                    ...newPaymentForm(), show: true, payment_date: this.finTxn.transaction_date,
                    amount: this.finPaymentRemaining.toFixed(2), payment_method_code: defaultMethod,
                };
            },
            async finSubmitPayment() {
                const f = this.finPaymentForm;
                const bad = this._finMoneyOk(f.amount, "Amount");
                if (bad) { f.error = bad; return; }
                if (!f.payment_date) { f.error = "Choose the payment date."; return; }
                f.saving = true; f.error = "";
                try {
                    const p = await this._finSend("POST", `/transactions/${this.finTxn.financial_transaction_pk}/payments`, {
                        payment_date: f.payment_date, amount: f.amount.trim(), paid_to: blank(f.paid_to),
                        payment_method_code: f.payment_method_code || null, instrument_reference: blank(f.instrument_reference),
                    });
                    this.finPaymentForm = newPaymentForm();
                    this._finNote(`Payment ${p.payment_reference} drafted. It needs approval before it is initiated.`);
                    await this.finReloadTxn();
                } catch (err) {
                    f.error = err.message || "Could not draft the payment.";
                } finally {
                    f.saving = false;
                }
            },

            // ═════════════════════════════════════════════════════════
            // Transfers
            // ═════════════════════════════════════════════════════════
            finTransfers: [], finTransfersTotal: 0, finTransfersPage: 1, finTransfersPageSize: 20,
            finTransferQ: "", finTransferYear: "", finTransferScope: "", finTransferStatusFilter: "",
            finTransfersLoading: false, finTransfersError: "", _finTransferSeq: 0,
            finTransferForm: newTransferForm(), finTransfer: null,
            finTransferSourceFunds: [], finTransferDestFunds: [],

            get finTransfersTotalPages() { return Math.max(1, Math.ceil(this.finTransfersTotal / this.finTransfersPageSize)); },

            async finLoadTransfers(opts = {}) {
                const seq = ++this._finTransferSeq;
                if (!opts.silent) { this.finTransfersLoading = true; this.finTransfersError = ""; }
                try {
                    const data = await this._finGet("/transfers", {
                        q: this.finTransferQ.trim(), financial_year_pk: this.finTransferYear, financial_scope_pk: this.finTransferScope,
                        status: this.finTransferStatusFilter, page: this.finTransfersPage, page_size: this.finTransfersPageSize,
                    });
                    if (seq !== this._finTransferSeq) return;
                    this.finTransfers = data.items; this.finTransfersTotal = data.total;
                } catch (err) {
                    if (seq !== this._finTransferSeq || opts.silent) return;
                    this.finTransfers = []; this.finTransfersTotal = 0;
                    this.finTransfersError = err.message || "Failed to load transfers.";
                } finally {
                    if (seq === this._finTransferSeq) this.finTransfersLoading = false;
                }
            },
            finApplyTransferFilters() { this.finTransfersPage = 1; return this.finLoadTransfers(); },
            finClearTransferFilters() {
                this.finTransferQ = ""; this.finTransferYear = ""; this.finTransferScope = ""; this.finTransferStatusFilter = "";
                return this.finApplyTransferFilters();
            },
            finTransfersPageBy(d) { this.finTransfersPage = Math.min(Math.max(1, this.finTransfersPage + d), this.finTransfersTotalPages); return this.finLoadTransfers(); },

            finOpenTransferForm() {
                this.finTransfer = null;
                const open = this.finOpenYears;
                const f = { ...newTransferForm(), show: true };
                if (open.length === 1) { f.financial_year_pk = open[0].financial_year_pk; f.transfer_date = this._finClampDate(open[0]); }
                this.finTransferForm = f; this.finTransferSourceFunds = []; this.finTransferDestFunds = [];
            },
            finTransferFormYearChanged() {
                const y = this.finYears.find((x) => x.financial_year_pk === this.finTransferForm.financial_year_pk);
                if (y) this.finTransferForm.transfer_date = this._finClampDate(y);
            },
            async finTransferScopeChanged(side) {
                const f = this.finTransferForm;
                if (side === "source") { f.source_fund_pk = ""; this.finTransferSourceFunds = await this.finFundsFor(f.source_scope_pk); }
                else { f.destination_fund_pk = ""; this.finTransferDestFunds = await this.finFundsFor(f.destination_scope_pk); }
            },
            async finSubmitTransfer() {
                const f = this.finTransferForm;
                if (!f.financial_year_pk) { f.error = "Choose the financial year."; return; }
                if (!f.source_scope_pk || !f.destination_scope_pk) { f.error = "Choose the source and destination scopes."; return; }
                if (f.source_scope_pk === f.destination_scope_pk) { f.error = "A transfer needs two different scopes."; return; }
                const bad = this._finMoneyOk(f.amount, "Amount");
                if (bad) { f.error = bad; return; }
                if (!f.transfer_date) { f.error = "Choose the transfer date."; return; }
                if (!blank(f.purpose)) { f.error = "State the purpose of the transfer."; return; }
                f.saving = true; f.error = "";
                try {
                    const t = await this._finSend("POST", "/transfers", {
                        financial_year_pk: f.financial_year_pk, source_scope_pk: f.source_scope_pk,
                        destination_scope_pk: f.destination_scope_pk, source_fund_pk: f.source_fund_pk || null,
                        destination_fund_pk: f.destination_fund_pk || null, amount: f.amount.trim(),
                        transfer_date: f.transfer_date, purpose: f.purpose.trim(),
                    });
                    this.finTransferForm = newTransferForm();
                    this._finNote(`Transfer ${t.transfer_reference} recorded as a draft.`);
                    await this.finLoadTransfers({ silent: true });
                    await this.finOpenTransfer(t.financial_transfer_pk);
                } catch (err) {
                    f.error = err.message || "Could not save the transfer.";
                } finally {
                    f.saving = false;
                }
            },
            async finOpenTransfer(pk) {
                try {
                    this.finTransfer = await this._finGet(`/transfers/${pk}`);
                } catch (err) {
                    this.finTransfer = null;
                    this.finTransfersError = err.message || "Could not open the transfer.";
                }
            },
            async finReloadTransfer() {
                if (!this.finTransfer) return;
                try {
                    this.finTransfer = await this._finGet(`/transfers/${this.finTransfer.financial_transfer_pk}`);
                } catch {
                    this.finTransfer = null;
                    await this.finLoadTransfers({ silent: true });
                }
            },
            finBackToTransfers() { this.finTransfer = null; return this.finLoadTransfers({ silent: true }); },
        };
    }

    /**
     * Mix the Finance screens into a host Alpine component. Uses property
     * DESCRIPTORS (not spread) so getters stay live, and never overwrites a
     * property the host already owns — same contract as NSSAssetsProperty.install().
     */
    window.NSSFinance = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(financeMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
