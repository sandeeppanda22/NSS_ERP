/**
 * Finance "Close the year, Sangha by Sangha" card (Tier 12, owner request 2026-11-25: "year closing should be Sakha and Kendra wise").
 *
 * The financial year stays one calendar record (finance.js: PLANNED -> OPEN -> CLOSING -> CLOSED, set by the NSS-wide authority). On top of it each
 * Sangha - every Sakha, and the Kendra - closes ITS OWN books for the year: start closing (no new entries, finish what is in progress), then close
 * (nothing unfinished may remain). The card sits on the Years & Scopes tab and lists the Sanghas with activity in the current year, what each has
 * and what is unfinished, with the step the signed-in person may take for each one. The rules are the server's (api/services/finance_year_closing.py);
 * the page only shows what the server says (`can_act`, `next_status`) and what stands in the way.
 *
 * A sixth Finance mixin, mixed into `adminPanel()` (admin.js) beside the others, using their helpers (_finGet / _finSend / _finNote / finBadge / finLabel).
 */
(function () {
    "use strict";

    const LABELS = { OPEN: "Open", CLOSING: "Closing", CLOSED: "Closed" };
    const STEP_LABELS = { CLOSING: "Start closing", CLOSED: "Close books" };

    function financeClosingMixin() {
        return {
            finClosings: [], finClosingYear: null,          // {financial_year_pk, year_code, year_status} of the year the card is about
            finClosingsLoading: false, finClosingsError: "", finClosingActing: "",

            finClosingLabel(state) { return LABELS[state] || NSS.financeStatusLabel(state); },
            finClosingStepLabel(step) { return STEP_LABELS[step] || step; },
            // The card is about the current year while it can still close (OPEN or CLOSING); a year that has not started or is closed has nothing to close.
            get finClosingTarget() {
                const y = this.finCurrentYear;
                return y && ["OPEN", "CLOSING"].includes(y.status) ? y : null;
            },
            // ALL in-progress work counts (owner 2026-11-25): transactions, transfers, draft receipts, payments not completed, online payments not booked.
            finClosingUnfinishedCount(c) {
                return ["unfinished_transactions", "unfinished_transfers", "unfinished_receipts", "unfinished_payments", "unfinished_online_payments"]
                    .reduce((sum, key) => sum + Number(c[key] || 0), 0);
            },
            finClosingUnfinishedText(c) {
                return [[c.unfinished_transactions, "transaction(s)"], [c.unfinished_transfers, "transfer(s)"], [c.unfinished_receipts, "draft receipt(s)"],
                        [c.unfinished_payments, "payment(s)"], [c.unfinished_online_payments, "online payment(s)"]]
                    .filter(([n]) => Number(n) > 0).map(([n, what]) => `${n} ${what}`).join(", ");
            },
            get finClosingsOpenCount() { return this.finClosings.filter((c) => c.status !== "CLOSED").length; },

            async finClosingsLoad(opts = {}) {
                const year = this.finClosingTarget;
                if (!year) { this.finClosings = []; this.finClosingYear = null; return; }
                if (!opts.silent) { this.finClosingsLoading = true; this.finClosingsError = ""; }
                try {
                    const data = await this._finGet(`/years/${year.financial_year_pk}/closings`);
                    this.finClosings = data.items;
                    this.finClosingYear = { financial_year_pk: data.financial_year_pk, year_code: data.year_code, year_status: data.year_status };
                } catch (err) {
                    if (!opts.silent) this.finClosingsError = err.message || "Failed to load the year's closing.";
                } finally {
                    this.finClosingsLoading = false;
                }
            },

            // One Sangha takes its next step. CLOSED is refused by the server, naming what is unfinished, when anything is; the page shows that text.
            async finClosingAct(row, step) {
                const year = this.finClosingYear;
                if (!year || !row.can_act) return;
                const what = step === "CLOSED"
                    ? `Close the books of ${row.organization_name} for ${year.year_code}? Nothing more can be recorded for it in that year.`
                    : `Start closing ${row.organization_name} for ${year.year_code}? It takes no new entries or transfers in that year; what is in progress can still be finished.`;
                const ok = await NSSDialog.confirm(what, { title: this.finClosingStepLabel(step), confirmText: this.finClosingStepLabel(step), confirmClass: step === "CLOSED" ? "danger" : "primary" });
                if (!ok) return;
                this.finClosingActing = row.organization_pk; this.finClosingsError = "";
                try {
                    const done = await this._finSend("POST", `/years/${year.financial_year_pk}/closings`, { organization_pk: row.organization_pk, status: step });
                    this._finNote(done.year_closed
                        ? `${row.organization_name} has closed its books. That was the last one, so financial year ${year.year_code} is now closed.`
                        : `${row.organization_name}: ${this.finClosingLabel(done.status).toLowerCase()} for ${year.year_code}.`);
                    await Promise.all([this.finClosingsLoad({ silent: true }), this.finLoadYears()]);
                } catch (err) {
                    this.finClosingsError = err.message || "Could not change it.";
                } finally {
                    this.finClosingActing = "";
                }
            },
        };
    }

    window.NSSFinanceClosing = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(financeClosingMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
