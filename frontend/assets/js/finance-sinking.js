/**
 * Finance "Sinking Fund dues" tab (Tier 12, owner request 2026-11-24; Bye-Law C(i)(2)(xviii), FIN-BR-026).
 *
 * When the Kendra temporarily takes over the seva and pujas of a Sakha, what it spends out of that Sakha's Sinking Fund "shall be reimbursed by
 * the Sakha Sangha subsequently". The screen has two jobs, both on the server's rules (api/services/finance_sinking.py is the ONE home):
 *   1. register a posted Sinking Fund expenditure as a take-over expenditure - the Sakha now owes that amount, with the reason on record;
 *   2. record what the Sakha pays back (part payments are fine) - an ordinary income entry in the same fund, posted like any other; it counts
 *      as reimbursed only once posted, so what is owed is always read from the books.
 *
 * A fifth Finance mixin, mixed into `adminPanel()` (admin.js) beside finance.js, finance-setup.js, finance-funds.js and finance-budget.js, using
 * their helpers (_finGet / _finSend / finMoney / finBadge / _finNote / canManageFinance). The page decides nothing about who may act: the server
 * checks FINANCE_VIEW / FINANCE_MANAGE and admin scope on the scope the money was spent in.
 */
(function () {
    "use strict";

    const newRegister = () => ({ show: false, expenditure: "", reason: "", resolution: "", saving: false, error: "" });
    const newPay = () => ({ show: false, amount: "", date: "", description: "", saving: false, error: "" });
    const newRemove = () => ({ show: false, reason: "", saving: false, error: "" });
    const LABELS = { OPEN: "Owed", PARTLY_REIMBURSED: "Part reimbursed", REIMBURSED: "Reimbursed" };

    function financeSinkingMixin() {
        return {
            finSinkings: [], finSinkingsLoading: false, finSinkingsError: "", finSinkingStatus: "", finSinkingSakha: "",
            finSinkingSummary: [],                     // the Kendra's page Sakha by Sakha (GET /sinking-reimbursements/summary)
            finSinking: null,                          // the open obligation with its reimbursements (GET /sinking-reimbursements/{pk})
            finSinkingOptions: [],                     // posted Sinking Fund expenditures not yet registered as owed (the Kendra's side)
            finSinkingError: "",
            finSinkingRegister: newRegister(), finSinkingPay: newPay(), finSinkingRemove: newRemove(),

            finSinkingLabel(state) { return LABELS[state] || NSS.financeStatusLabel(state); },
            // The whole tab is the Kendra's procedure (the sidebar shows it only when finKendraSide); the server checks scope on every call.
            get finSinkingCanAct() { return this.canManageFinance && this.finKendraSide; },
            get finSinkingToday() { return new Date().toISOString().slice(0, 10); },
            // What has been spent from a Sakha's Sinking Fund but not registered yet, Sakha by Sakha then newest first.
            get finSinkingWaiting() {
                return [...this.finSinkingOptions].sort((a, b) => a.sakha_name.localeCompare(b.sakha_name) || String(b.transaction_date).localeCompare(String(a.transaction_date)));
            },
            // Money still owed across the list (what the Sakhas have not paid back yet) - read from the rows the server computed.
            get finSinkingOwed() {
                return this.finSinkings.reduce((sum, r) => sum + Number(r.outstanding_amount || 0), 0).toFixed(2);
            },
            // What can still be recorded on the open obligation: owed, less what is posted and what is already recorded and on its way.
            get finSinkingRoom() {
                const r = this.finSinking;
                if (!r) return 0;
                return Math.max(Number(r.amount_due) - Number(r.reimbursed_amount) - Number(r.pending_amount), 0);
            },

            async finSinkingEnter() {
                this.finSinking = null; this.finSinkingError = "";
                this.finSinkingRegister = newRegister(); this.finSinkingPay = newPay(); this.finSinkingRemove = newRemove();
                await Promise.all([this.finSinkingsLoad(), this.finSinkingSummaryLoad()]);
            },
            // The Sakha-wise table and the spending still waiting to be registered (both only what the caller may see).
            async finSinkingSummaryLoad() {
                try {
                    const [summary, waiting] = await Promise.all([this._finGet("/sinking-reimbursements/summary"), this._finGet("/sinking-reimbursements/expenditures")]);
                    this.finSinkingSummary = summary.items; this.finSinkingOptions = waiting.items;
                } catch { /* the list below still works; the table stays as it was */ }
            },
            // Click a Sakha in the table to see only its dues (click again to see them all).
            finSinkingPickSakha(pk) {
                this.finSinkingSakha = this.finSinkingSakha === pk ? "" : pk;
                return this.finSinkingsLoad();
            },
            async finSinkingsLoad(opts = {}) {
                if (!opts.silent) { this.finSinkingsLoading = true; this.finSinkingsError = ""; }
                try {
                    const params = {};
                    if (this.finSinkingStatus) params.status = this.finSinkingStatus;
                    if (this.finSinkingSakha) params.organization_pk = this.finSinkingSakha;
                    this.finSinkings = (await this._finGet("/sinking-reimbursements", params)).items;
                } catch (err) {
                    if (!opts.silent) this.finSinkingsError = err.message || "Failed to load the Sinking Fund dues.";
                } finally {
                    this.finSinkingsLoading = false;
                }
            },
            async finSinkingOpen(pk) {
                this.finSinkingError = "";
                try {
                    this._finSinkingSet(await this._finGet(`/sinking-reimbursements/${pk}`));
                } catch (err) {
                    this.finSinkingError = err.message || "Failed to load it.";
                }
            },
            finSinkingClose() {
                this.finSinking = null; this.finSinkingError = "";
                return Promise.all([this.finSinkingsLoad({ silent: true }), this.finSinkingSummaryLoad()]);
            },
            // The open one changed: show the server's new picture and reset the forms that belonged to the old one.
            _finSinkingSet(detail) {
                this.finSinking = detail;
                this.finSinkingPay = newPay(); this.finSinkingRemove = newRemove();
            },

            // ── Register an expenditure as owed ────────────────────
            // From the button (nothing chosen) or from a row of the waiting table (that expenditure chosen).
            async finSinkingRegisterOpen(expenditurePk) {
                this.finSinkingRegister = { ...newRegister(), show: true, expenditure: expenditurePk || "" };
                await this.finSinkingSummaryLoad();
                if (expenditurePk && this.$nextTick) this.$nextTick(() => { const box = document.getElementById("sink-register-box"); if (box) box.scrollIntoView({ behavior: "smooth", block: "center" }); });
            },
            finSinkingOption(pk) { return this.finSinkingOptions.find((o) => o.financial_transaction_pk === pk) || null; },
            async finSinkingRegisterSubmit() {
                const f = this.finSinkingRegister;
                if (!f.expenditure) { f.error = "Choose the expenditure."; return; }
                if (!f.reason.trim()) { f.error = "Say why the Kendra took over the Sakha's seva / pujas."; return; }
                f.saving = true; f.error = "";
                try {
                    const detail = await this._finSend("POST", "/sinking-reimbursements",
                        { expenditure_transaction_pk: f.expenditure, takeover_reason: f.reason.trim(), resolution_reference: f.resolution.trim() || null });
                    this.finSinkingRegister = newRegister();
                    this._finSinkingSet(detail);
                    this.finSinkingSummaryLoad();
                    this._finNote("Registered. The Sakha now owes this amount to its Sinking Fund.");
                } catch (err) {
                    f.error = err.message || "Could not register it.";
                } finally {
                    f.saving = false;
                }
            },

            // ── Record a reimbursement ─────────────────────────────
            finSinkingPayOpen() {
                this.finSinkingPay = { ...newPay(), show: true, amount: String(this.finSinkingRoom.toFixed(2)) };
            },
            async finSinkingPaySubmit() {
                const f = this.finSinkingPay;
                const bad = this._finMoneyOk(f.amount, "Amount");
                if (bad) { f.error = bad; return; }
                if (Number(f.amount) > this.finSinkingRoom + 0.0001) { f.error = `The Sakha owes at most ${this.finMoney(this.finSinkingRoom)} more.`; return; }
                f.saving = true; f.error = "";
                try {
                    const pk = this.finSinking.finance_sinking_reimbursement_pk;
                    this._finSinkingSet(await this._finSend("POST", `/sinking-reimbursements/${pk}/reimbursements`,
                        { amount: String(f.amount).trim(), transaction_date: f.date || null, description: f.description.trim() || null }));
                    this._finNote("Reimbursement recorded as a draft entry in the Sinking Fund. Post it under Transactions; it counts as reimbursed once posted.");
                } catch (err) {
                    f.error = err.message || "Could not record it.";
                } finally {
                    f.saving = false;
                }
            },

            // ── Remove a registration made by mistake ──────────────
            finSinkingRemoveOpen() { this.finSinkingRemove = { ...newRemove(), show: true }; },
            async finSinkingRemoveSubmit() {
                const f = this.finSinkingRemove;
                if (!f.reason.trim()) { f.error = "Say why it is being removed."; return; }
                f.saving = true; f.error = "";
                try {
                    const pk = this.finSinking.finance_sinking_reimbursement_pk;
                    await this._finSend("DELETE", `/sinking-reimbursements/${pk}?reason=${encodeURIComponent(f.reason.trim())}`);
                    this._finNote("Removed. The expenditure can be registered again.");
                    await this.finSinkingClose();
                } catch (err) {
                    f.error = err.message || "Could not remove it.";
                } finally {
                    f.saving = false;
                }
            },

            // ── Live refresh (finance.js finLiveReload / finLiveBusy call these) ──
            finSinkingBusy() {
                return [this.finSinkingRegister, this.finSinkingPay, this.finSinkingRemove].some((f) => f.show || f.saving);
            },
            async finSinkingReload() {
                if (!this.finSinking) return Promise.all([this.finSinkingsLoad({ silent: true }), this.finSinkingSummaryLoad()]);
                try { this.finSinking = await this._finGet(`/sinking-reimbursements/${this.finSinking.finance_sinking_reimbursement_pk}`); }
                catch { /* the open one stays as it was; a manual reopen explains */ }
            },
        };
    }

    window.NSSFinanceSinking = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(financeSinkingMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
