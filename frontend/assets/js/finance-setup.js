/**
 * Finance customization + UPI collection screens (Tier 12) — a second Finance mixin, mixed into `adminPanel()` (admin.js)
 * next to finance.js (which owns the permission getters, the lifecycle dialog, Overview / Years & Scopes / Transactions /
 * Transfers).
 *
 *   finSetup        Heads & Accounts: each Sangha's finance heads (adopted from Kendra templates or its own) and its
 *                   receiving accounts. Configuration is a FINANCE_APPROVE decision on the server; the buttons are only
 *                   hidden here (canApproveFinance).
 *   finCollections  UPI Collections: ask a payer to pay by UPI, follow the request, and resolve payments the books
 *                   could not take on their own (the review queue). The gateway's signed webhook — never this page —
 *                   is what marks a request paid.
 *
 * Authorization is the server's (api/routers/finance_setup.py, finance_upi.py): admin scope on the owning Sangha plus
 * FINANCE_VIEW / MANAGE / APPROVE. This file shows the server's message verbatim (NSS.extractError) for everything
 * it refuses, and takes lifecycle buttons from the server's own table (finActions). It never holds a secret: an
 * account carries only the NAME of a server-side credential set.
 *
 * Links from the gateway are only ever rendered when they have the expected scheme (https for a hosted page,
 * upi://pay for a UPI app), so a hostile response could not inject a javascript: URL.
 */
(function () {
    "use strict";

    const emptyPicker = (extra) => ({ query: "", results: [], searching: false, selected: null, ...(extra || {}) });
    const blank = (v) => {
        const t = (v == null ? "" : String(v)).trim();
        return t === "" ? null : t;
    };
    const MONEY_RE = /^\d+(\.\d{1,2})?$/;

    const newHeadForm = () => ({
        show: false, mode: "create", pk: "", saving: false, error: "", template: false, organization: emptyPicker(),
        head_code: "", head_name: "", description: "", direction: "INCOME", is_restricted: false, restriction_purpose: "",
        required_fund_type: "", is_pranami: false, allow_upi: false, collection_scope_pk: "", collection_fund_pk: "",
        collection_account_pk: "", display_order: 100, lockedShape: false,
    });
    const newAcctForm = () => ({
        show: false, mode: "create", pk: "", saving: false, error: "", organization: emptyPicker(), account_label: "",
        account_type: "BANK", bank_name: "", branch_name: "", account_holder_name: "", account_number_last4: "", ifsc_code: "",
        upi_vpa: "", gateway_provider: "", gateway_credential_ref: "", gateway_merchant_ref: "", is_default: false,
    });
    const newReqForm = () => ({ show: false, saving: false, error: "", finance_head_pk: "", amount: "", sangha_sevi_id: "", payer_name: "", note: "" });

    function financeSetupMixin() {
        return {
            // ═════════════════════════════════════════════════════════
            // Tab entry + live refresh (called by finance.js' finEnterTab / finLiveReload / finLiveBusy)
            // ═════════════════════════════════════════════════════════
            async finSetupEnter() {
                this.finHeadForm = newHeadForm(); this.finAcctForm = newAcctForm();
                await Promise.all([this.finHeadsLoad(), this.finAcctsLoad()]);
            },
            async finSetupReload() {
                await Promise.all([this.finHeadsLoad({ silent: true }), this.finAcctsLoad({ silent: true })]);
            },
            finSetupBusy() { return !!(this.finHeadForm.show || this.finAcctForm.show || this.finHeadForm.saving || this.finAcctForm.saving); },

            async finReqEnter() {
                this.finReq = null; this.finReqForm = newReqForm();
                await Promise.all([this.finReqLoad(), this.finReqLoadHeads()]);
            },
            async finReqReload() {
                await this.finReqLoad({ silent: true });
                if (this.finReq) await this.finReqRefreshOpen();
            },
            finReqBusy() { return !!(this.finReqForm.show || this.finReqForm.saving || this.finReqActing); },

            // ═════════════════════════════════════════════════════════
            // Shared: the Sangha being configured
            // ═════════════════════════════════════════════════════════
            finSetupOrg: emptyPicker(),            // optional filter: one Sangha's heads / accounts
            get finSetupOrgPk() { return this.finSetupOrg.selected ? this.finSetupOrg.selected.organization_pk : ""; },
            finSetupOrgChanged() { return this.finSetupReload(); },
            finSetupClearOrg() { this.corrClearPicker(this.finSetupOrg); return this.finSetupReload(); },

            // ═════════════════════════════════════════════════════════
            // Finance heads
            // ═════════════════════════════════════════════════════════
            finHeads: [], finHeadsTotal: 0, finHeadsLoading: false, finHeadsError: "", _finHeadsSeq: 0,
            finHeadView: "sangha",                 // "sangha" | "templates"
            finHeadQ: "", finHeadDirFilter: "", finHeadStatusFilter: "",
            finHeadForm: newHeadForm(), finHeadScopes: [], finHeadFunds: [], finHeadAccounts: [],
            finHeadOptions: { fundTypes: [] },

            get finHeadsAreTemplates() { return this.finHeadView === "templates"; },

            async finHeadsLoad(opts = {}) {
                const seq = ++this._finHeadsSeq;
                if (!opts.silent) { this.finHeadsLoading = true; this.finHeadsError = ""; }
                try {
                    const data = await this._finGet("/heads", {
                        q: this.finHeadQ.trim(), direction: this.finHeadDirFilter, status: this.finHeadStatusFilter, page_size: 200,
                        ...(this.finHeadsAreTemplates ? { templates_only: "true" } : { with_templates: "false", organization_pk: this.finSetupOrgPk }),
                    });
                    if (seq !== this._finHeadsSeq) return;
                    this.finHeads = data.items; this.finHeadsTotal = data.total;
                } catch (err) {
                    if (seq !== this._finHeadsSeq || opts.silent) return;
                    this.finHeads = []; this.finHeadsTotal = 0;
                    this.finHeadsError = err.message || "Failed to load finance heads.";
                } finally {
                    if (seq === this._finHeadsSeq) this.finHeadsLoading = false;
                }
            },
            finHeadsApply() { return this.finHeadsLoad(); },
            finHeadSetView(view) { this.finHeadView = view; this.finHeadForm = newHeadForm(); return this.finHeadsLoad(); },

            // Create / edit
            finHeadOpenCreate() {
                this.finHeadForm = { ...newHeadForm(), show: true, template: this.finHeadsAreTemplates };
                if (!this.finHeadsAreTemplates && this.finSetupOrg.selected) {
                    this.finHeadForm.organization = { ...emptyPicker(), selected: this.finSetupOrg.selected, query: this.finSetupOrg.selected.organization_name };
                    return this.finHeadFormOrgChanged();
                }
            },
            async finHeadOpenEdit(h) {
                this.finHeadForm = {
                    ...newHeadForm(), show: true, mode: "edit", pk: h.finance_head_pk, template: h.is_template, lockedShape: true,
                    organization: { ...emptyPicker(), selected: h.organization_pk ? { organization_pk: h.organization_pk, organization_name: h.organization_name } : null },
                    head_code: h.head_code, head_name: h.head_name, description: h.description || "", direction: h.direction,
                    is_restricted: h.is_restricted, restriction_purpose: h.restriction_purpose || "", required_fund_type: h.required_fund_type || "",
                    is_pranami: h.is_pranami, allow_upi: h.allow_upi, collection_scope_pk: h.collection_scope_pk || "",
                    collection_fund_pk: h.collection_fund_pk || "", collection_account_pk: h.collection_account_pk || "", display_order: h.display_order,
                };
                await this.finHeadFormOrgChanged(true);
            },
            finHeadCancel() { this.finHeadForm = { ...this.finHeadForm, show: false }; },

            // The collection targets are chosen from the Sangha's own ACTIVE scopes / funds / accounts.
            async finHeadFormOrgChanged(keepTargets) {
                const f = this.finHeadForm;
                const org = f.organization.selected ? f.organization.selected.organization_pk : "";
                if (!keepTargets) { f.collection_scope_pk = ""; f.collection_fund_pk = ""; f.collection_account_pk = ""; }
                this.finHeadScopes = []; this.finHeadFunds = []; this.finHeadAccounts = [];
                if (!org) return;
                try {
                    const [scopes, accounts] = await Promise.all([
                        this._finGet("/scopes", { organization_pk: org, status: "ACTIVE", page_size: 100 }),
                        this._finGet("/accounts", { organization_pk: org, status: "ACTIVE", page_size: 100 }),
                    ]);
                    this.finHeadScopes = scopes.items; this.finHeadAccounts = accounts.items;
                } catch { /* the pick-lists stay empty; the server explains on save */ }
                await this.finHeadFormScopeChanged(true);
            },
            async finHeadFormScopeChanged(keepFund) {
                const f = this.finHeadForm;
                if (!keepFund) f.collection_fund_pk = "";
                this.finHeadFunds = [];
                if (!f.collection_scope_pk) return;
                try {
                    this.finHeadFunds = (await this._finGet("/funds", { financial_scope_pk: f.collection_scope_pk, status: "ACTIVE", page_size: 100 })).items;
                } catch { /* ignore */ }
            },

            async finHeadSubmit() {
                const f = this.finHeadForm;
                const edit = f.mode === "edit";
                if (!blank(f.head_name)) { f.error = "The head needs a name."; return; }
                if (!edit) {
                    if (!blank(f.head_code)) { f.error = "The head needs a code (letters, digits and underscores, e.g. FESTIVAL_DONATION)."; return; }
                    if (!f.template && !f.organization.selected) { f.error = "Choose the Sangha this head belongs to."; return; }
                }
                if (f.is_restricted && !blank(f.restriction_purpose)) { f.error = "A restricted head must state what it is restricted to."; return; }
                if (f.allow_upi && (!f.collection_scope_pk || !f.collection_account_pk)) { f.error = "UPI collection needs a collection scope and a receiving account."; return; }
                f.saving = true; f.error = "";
                try {
                    const targets = {
                        is_pranami: f.is_pranami, allow_upi: f.allow_upi, collection_scope_pk: f.collection_scope_pk || null,
                        collection_fund_pk: f.collection_fund_pk || null, collection_account_pk: f.collection_account_pk || null,
                    };
                    if (edit) {
                        await this._finSend("PATCH", `/heads/${f.pk}`, {
                            head_name: f.head_name.trim(), description: blank(f.description), display_order: Number(f.display_order) || 0,
                            ...(f.is_restricted ? { restriction_purpose: f.restriction_purpose.trim() } : {}), ...targets,
                        });
                    } else {
                        await this._finSend("POST", "/heads", {
                            organization_pk: f.template ? null : f.organization.selected.organization_pk,
                            head_code: f.head_code.trim().toUpperCase(), head_name: f.head_name.trim(), description: blank(f.description),
                            direction: f.direction, is_restricted: f.is_restricted, restriction_purpose: f.is_restricted ? f.restriction_purpose.trim() : null,
                            required_fund_type: f.required_fund_type || null, display_order: Number(f.display_order) || 100, ...targets,
                        });
                    }
                    this.finHeadForm = newHeadForm();
                    this._finNote(edit ? "Finance head updated." : "Finance head created.");
                    this.finFundOptions = {};
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    f.error = err.message || "Could not save the finance head.";
                } finally {
                    f.saving = false;
                }
            },

            // Copy the Kendra templates into the chosen Sangha's catalogue (idempotent).
            async finHeadAdopt() {
                if (!this.finSetupOrgPk) { this.finHeadsError = "Choose the Sangha first (the filter above), then add the Kendra templates to it."; return; }
                this.finHeadsError = "";
                try {
                    const r = await this._finSend("POST", "/heads/adopt-templates", { organization_pk: this.finSetupOrgPk });
                    this._finNote(r.created ? `${r.created} head(s) added from the Kendra templates (${r.skipped} already there).` : `Nothing new to add: all ${r.skipped} templates are already in this Sangha's catalogue.`);
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    this.finHeadsError = err.message || "Could not add the templates.";
                }
            },

            finHeadRules(h) {
                const bits = [];
                if (h.is_restricted) bits.push("Restricted");
                if (h.required_fund_type) bits.push(NSS.codeLabel(h.required_fund_type) + " fund");
                if (h.is_pranami) bits.push("Pranami");
                if (h.allow_upi) bits.push("UPI");
                return bits;
            },

            // ═════════════════════════════════════════════════════════
            // Receiving accounts
            // ═════════════════════════════════════════════════════════
            finAccounts: [], finAccountsTotal: 0, finAcctsLoading: false, finAcctsError: "", _finAcctsSeq: 0, finAcctQ: "",
            finAcctForm: newAcctForm(),

            // Providers the server can use now, plus whichever one an existing account already names.
            get finAcctProviders() { return (this.finRef && this.finRef.gateway_providers) || []; },

            async finAcctsLoad(opts = {}) {
                const seq = ++this._finAcctsSeq;
                if (!opts.silent) { this.finAcctsLoading = true; this.finAcctsError = ""; }
                try {
                    const data = await this._finGet("/accounts", { q: this.finAcctQ.trim(), organization_pk: this.finSetupOrgPk, page_size: 100 });
                    if (seq !== this._finAcctsSeq) return;
                    this.finAccounts = data.items; this.finAccountsTotal = data.total;
                } catch (err) {
                    if (seq !== this._finAcctsSeq || opts.silent) return;
                    this.finAccounts = []; this.finAccountsTotal = 0;
                    this.finAcctsError = err.message || "Failed to load receiving accounts.";
                } finally {
                    if (seq === this._finAcctsSeq) this.finAcctsLoading = false;
                }
            },
            finAcctOpenCreate() {
                this.finAcctForm = { ...newAcctForm(), show: true };
                if (this.finSetupOrg.selected) this.finAcctForm.organization = { ...emptyPicker(), selected: this.finSetupOrg.selected, query: this.finSetupOrg.selected.organization_name };
            },
            finAcctOpenEdit(a) {
                this.finAcctForm = {
                    ...newAcctForm(), show: true, mode: "edit", pk: a.financial_account_pk,
                    organization: { ...emptyPicker(), selected: { organization_pk: a.organization_pk, organization_name: a.organization_name } },
                    account_label: a.account_label, account_type: a.account_type, bank_name: a.bank_name || "", branch_name: a.branch_name || "",
                    account_holder_name: a.account_holder_name, account_number_last4: a.account_number_last4 || "", ifsc_code: a.ifsc_code || "",
                    upi_vpa: a.upi_vpa || "", gateway_provider: a.gateway_provider || "", gateway_credential_ref: a.gateway_credential_ref || "",
                    gateway_merchant_ref: a.gateway_merchant_ref || "", is_default: a.is_default,
                };
            },
            finAcctCancel() { this.finAcctForm = { ...this.finAcctForm, show: false }; },
            async finAcctSubmit() {
                const f = this.finAcctForm;
                const edit = f.mode === "edit";
                if (!blank(f.account_label) || !blank(f.account_holder_name)) { f.error = "The account needs a label and a holder name."; return; }
                if (!edit && !f.organization.selected) { f.error = "Choose the Sangha this account belongs to."; return; }
                if (blank(f.account_number_last4) && !/^\d{4}$/.test(f.account_number_last4.trim())) { f.error = "Enter the LAST FOUR digits only (the full account number is never stored)."; return; }
                if (blank(f.gateway_provider) && !blank(f.gateway_credential_ref)) { f.error = "A payment gateway needs the name of its credential set."; return; }
                f.saving = true; f.error = "";
                try {
                    const body = {
                        account_label: f.account_label.trim(), account_type: f.account_type, bank_name: blank(f.bank_name), branch_name: blank(f.branch_name),
                        account_holder_name: f.account_holder_name.trim(), account_number_last4: blank(f.account_number_last4),
                        ifsc_code: blank(f.ifsc_code), upi_vpa: blank(f.upi_vpa), gateway_provider: blank(f.gateway_provider),
                        gateway_credential_ref: blank(f.gateway_credential_ref), gateway_merchant_ref: blank(f.gateway_merchant_ref), is_default: f.is_default,
                    };
                    if (edit) await this._finSend("PATCH", `/accounts/${f.pk}`, body);
                    else await this._finSend("POST", "/accounts", { organization_pk: f.organization.selected.organization_pk, ...body });
                    this.finAcctForm = newAcctForm();
                    this._finNote(edit ? "Receiving account updated." : "Receiving account added.");
                    await this.finAcctsLoad({ silent: true });
                } catch (err) {
                    f.error = err.message || "Could not save the receiving account.";
                } finally {
                    f.saving = false;
                }
            },

            // ═════════════════════════════════════════════════════════
            // UPI collections
            // ═════════════════════════════════════════════════════════
            finReqs: [], finReqsTotal: 0, finReqsPage: 1, finReqsPageSize: 20, finReqsLoading: false, finReqsError: "", _finReqSeq: 0,
            finReqQ: "", finReqStatus: "", finReqReview: false,
            finReqForm: newReqForm(), finReqHeads: [], finReq: null, finReqActing: false, finReqActionError: "", finReqCopied: "",
            finReqSimAmount: "",

            get finReqsTotalPages() { return Math.max(1, Math.ceil(this.finReqsTotal / this.finReqsPageSize)); },
            get finReqCanSimulate() {
                return !!this.finReq && this.canManageFinance && this.finReq.provider === "MOCK"
                    && this.finAcctProviders.includes("MOCK") && ["CREATED", "PENDING", "EXPIRED", "CANCELLED"].includes(this.finReq.status);
            },
            get finReqNeedsBooking() { return !!this.finReq && this.finReq.status === "PAID" && !this.finReq.transaction_reference; },

            // Only render a link whose scheme is the expected one.
            finReqSafeUrl(url) { return typeof url === "string" && /^https:\/\//i.test(url) ? url : ""; },
            finReqSafeUpi(uri) { return typeof uri === "string" && /^upi:\/\/pay\?/i.test(uri) ? uri : ""; },

            async finReqLoadHeads() {
                try {
                    this.finReqHeads = (await this._finGet("/heads", { allow_upi: "true", status: "ACTIVE", with_templates: "false", page_size: 200 })).items;
                } catch { this.finReqHeads = []; }
            },
            async finReqLoad(opts = {}) {
                const seq = ++this._finReqSeq;
                if (!opts.silent) { this.finReqsLoading = true; this.finReqsError = ""; }
                try {
                    const data = await this._finGet("/payment-requests", {
                        q: this.finReqQ.trim(), status: this.finReqStatus, needs_review: this.finReqReview ? "true" : "",
                        page: this.finReqsPage, page_size: this.finReqsPageSize,
                    });
                    if (seq !== this._finReqSeq) return;
                    this.finReqs = data.items; this.finReqsTotal = data.total;
                } catch (err) {
                    if (seq !== this._finReqSeq || opts.silent) return;
                    this.finReqs = []; this.finReqsTotal = 0;
                    this.finReqsError = err.message || "Failed to load payment requests.";
                } finally {
                    if (seq === this._finReqSeq) this.finReqsLoading = false;
                }
            },
            finReqApply() { this.finReqsPage = 1; return this.finReqLoad(); },
            finReqClear() { this.finReqQ = ""; this.finReqStatus = ""; this.finReqReview = false; return this.finReqApply(); },
            finReqPageBy(d) { this.finReqsPage = Math.min(Math.max(1, this.finReqsPage + d), this.finReqsTotalPages); return this.finReqLoad(); },

            finReqOpenForm() { this.finReq = null; this.finReqForm = { ...newReqForm(), show: true }; },
            async finReqSubmit() {
                const f = this.finReqForm;
                if (!f.finance_head_pk) { f.error = "Choose the finance head this payment is for."; return; }
                if (!MONEY_RE.test(String(f.amount || "").trim()) || Number(f.amount) <= 0) { f.error = "Amount must be a positive amount with at most two decimals."; return; }
                f.saving = true; f.error = "";
                try {
                    const created = await this._finSend("POST", "/payment-requests", {
                        finance_head_pk: f.finance_head_pk, amount: f.amount.trim(), sangha_sevi_id: blank(f.sangha_sevi_id),
                        payer_name: blank(f.payer_name), note: blank(f.note),
                    });
                    this.finReqForm = newReqForm();
                    this._finNote(`Payment request ${created.request_reference} created. Share the payment link / UPI link with the payer.`);
                    await this.finReqLoad({ silent: true });
                    this.finReq = created;
                } catch (err) {
                    f.error = err.message || "Could not create the payment request.";
                } finally {
                    f.saving = false;
                }
            },
            async finReqOpen(pk) {
                this.finReqActionError = ""; this.finReqCopied = ""; this.finReqSimAmount = "";
                try { this.finReq = await this._finGet(`/payment-requests/${pk}`); }
                catch (err) { this.finReq = null; this.finReqsError = err.message || "Could not open the request."; }
            },
            async finReqRefreshOpen() {
                if (!this.finReq) return;
                try { this.finReq = await this._finGet(`/payment-requests/${this.finReq.upi_payment_request_pk}`); }
                catch { this.finReq = null; await this.finReqLoad({ silent: true }); }
            },
            finReqBack() { this.finReq = null; return this.finReqLoad({ silent: true }); },

            async _finReqAct(label, path, method = "POST") {
                this.finReqActing = true; this.finReqActionError = "";
                try {
                    this.finReq = await this._finSend(method, `/payment-requests/${this.finReq.upi_payment_request_pk}${path}`);
                    this._finNote(label);
                    await this.finReqLoad({ silent: true });
                } catch (err) {
                    this.finReqActionError = err.message || "The action was refused.";
                    await this.finReqRefreshOpen();                          // a refused booking still updates the review reason
                } finally {
                    this.finReqActing = false;
                }
            },
            finReqRefresh() { return this._finReqAct("Asked the gateway for the latest status.", "/refresh"); },
            finReqBook() { return this._finReqAct("Payment booked.", "/post"); },
            finReqSimulate(outcome) {
                const amt = blank(this.finReqSimAmount);
                if (amt && !MONEY_RE.test(amt)) { this.finReqActionError = "Enter the simulated amount with at most two decimals."; return; }
                return this._finReqAct(`Simulated: ${outcome}.`, `/mock-pay?outcome=${encodeURIComponent(outcome)}${amt ? "&amount=" + encodeURIComponent(amt) : ""}`);
            },
            async finReqCopy(text, key) {
                try {
                    await navigator.clipboard.writeText(text);
                    this.finReqCopied = key;
                    setTimeout(() => { if (this.finReqCopied === key) this.finReqCopied = ""; }, 2500);
                } catch { this.finReqActionError = "Copying is not available in this browser; select the text instead."; }
            },
        };
    }

    window.NSSFinanceSetup = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(financeSetupMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
