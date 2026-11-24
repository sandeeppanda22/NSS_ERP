/**
 * Finance "Budget" tab (Tier 12, owner request 2026-11-22; Bye-Law FIN-BR-041) - the Kendra's annual budget.
 *
 * The Kendra Governing Body passes an annual budget; the draft is first referred to the Advisory Board for its considered views.
 * The screen walks the four steps the server enforces (api/services/finance_budget.py is the ONE home of the rules):
 *   Draft (lines) -> Referred to the Advisory Board -> Views received -> Passed by the Governing Body.
 * Each step records a reference and a date; the Advisory Board's views must be on file before the budget can pass, but they are views,
 * not a veto; a budget can go back to draft until it has passed. The budget only FLAGS spending (over a line, or on a head with no
 * line) - it never blocks it.
 *
 * A fourth Finance mixin, mixed into `adminPanel()` (admin.js) beside finance.js, finance-setup.js and finance-funds.js, using their
 * helpers (_finGet / _finSend / finMoney / finBadge / finLoadYears / canManageFinance). The page decides nothing about who may act: the
 * server checks FINANCE_VIEW / FINANCE_MANAGE and admin scope on the Kendra (a Sakha admin simply sees no budget).
 */
(function () {
    "use strict";

    const STEPS = [
        { key: "DRAFT", label: "Draft" },
        { key: "REFERRED", label: "Referred to the Advisory Board" },
        { key: "VIEWS_RECEIVED", label: "Advisory Board's views on file" },
        { key: "PASSED", label: "Passed by the Governing Body" },
    ];
    const newStart = () => ({ show: false, year: "", saving: false, error: "" });
    // The line form and the reason box appear only in EDIT MODE (finBudgetEditing, opened by "Edit budget", closed by Cancel); the Edit button
    // itself is offered in every status. Change on a row fills the form.
    const newLine = () => ({ show: true, head: "", amount: "", notes: "", editing: false, saving: false, error: "" });
    const newRefer = () => ({ date: "", saving: false, error: "" });
    const newViews = () => ({ date: "", summary: "", saving: false, error: "" });
    const newPass = () => ({ reference: "", date: "", saving: false, error: "" });
    const newBack = () => ({ show: false, remarks: "", saving: false, error: "" });
    // Correcting what was recorded (owner 2026-11-24): the Advisory Board's summary, and - once passed - the resolution reference, with a reason.
    const newFix = () => ({ show: false, summary: "", reference: "", reason: "", saving: false, error: "" });
    const today = () => new Date().toISOString().slice(0, 10);

    function financeBudgetMixin() {
        return {
            finBudgets: [], finBudgetsLoading: false, finBudgetsError: "",
            finBudget: null,                           // the open budget with its lines (GET /budgets/{pk})
            finBudgetHeads: [],                        // the Kendra's ACTIVE heads, for the line form
            finBudgetHeadsNote: "",                    // why there are none, when there are none
            finBudgetError: "", finBudgetReason: "", finBudgetEditing: false,
            finBudgetStart: newStart(), finBudgetLine: newLine(), finBudgetRefer: newRefer(),
            finBudgetViews: newViews(), finBudgetPass: newPass(), finBudgetBack: newBack(), finBudgetFix: newFix(),

            get finBudgetToday() { return today(); },
            get finBudgetSteps() {
                const at = this.finBudget ? STEPS.findIndex((s) => s.key === this.finBudget.status) : -1;
                return STEPS.map((s, i) => ({ ...s, done: i < at || (i === at && s.key === "PASSED"), current: i === at && s.key !== "PASSED" }));
            },
            // The year a budget is started for: the CURRENT one, chosen for the user and not changeable (owner 2026-11-23), and only while it is not CLOSED
            // and has no budget yet (one budget per year); finBudgetYearTaken says when it already has one.
            get finBudgetYearTaken() {
                const y = this.finScopeYear;
                return !!y && this.finBudgets.some((b) => b.financial_year_pk === y.financial_year_pk);
            },
            get finBudgetYear() { return this.finBudgetYearTaken ? null : this.finScopeYear; },
            // The Kendra may also prepare NEXT year's budget in advance (owner 2026-11-24): the next year after the current one, while it is not CLOSED
            // and has no budget yet. Everything else about the current year stays as it was.
            get finBudgetNextYear() {
                const current = this.finScopeYear;
                if (!current) return null;
                const start = (y) => Number(String(y.year_code).slice(0, 4));
                const next = this.finYears.filter((y) => y.status !== "CLOSED" && start(y) > start(current)).sort((a, b) => start(a) - start(b))[0];
                return next && !this.finBudgets.some((b) => b.financial_year_pk === next.financial_year_pk) ? next : null;
            },
            get finBudgetCanStart() { return !!(this.finBudgetYear || this.finBudgetNextYear); },
            get finBudgetIncomeLines() { return this.finBudget ? this.finBudget.lines.filter((l) => l.direction === "INCOME") : []; },
            get finBudgetExpenseLines() { return this.finBudget ? this.finBudget.lines.filter((l) => l.direction === "EXPENSE") : []; },
            // Heads with no line yet (a head that already has one is changed from its row, not picked again).
            get finBudgetFreeHeads() {
                const used = new Set((this.finBudget ? this.finBudget.lines : []).map((l) => l.finance_head_pk));
                return this.finBudgetHeads.filter((h) => !used.has(h.finance_head_pk));
            },
            // A line can be changed in ANY status (owner 2026-11-22, "edit always"); past DRAFT the server wants a reason, kept in the record.
            get finBudgetCanEditLines() { return !!this.finBudget && this.canManageFinance; },
            get finBudgetNeedsReason() { return !!this.finBudget && !!this.finBudget.changes_need_reason; },
            get finBudgetCanAct() { return !!this.finBudget && this.canManageFinance; },
            // "Edit budget" is offered in every status. It opens edit mode on the lines (the reason box, the line form, Change / Remove on each
            // row); Cancel closes it and drops whatever was typed. Sending a referred budget back to draft is a separate, deliberate step.
            get finBudgetCanEdit() { return !!this.finBudget && this.canManageFinance; },
            finBudgetEdit() {
                this.finBudgetEditing = true; this.finBudgetLine = newLine(); this.finBudgetReason = "";
                if (this.$nextTick) this.$nextTick(() => { const box = document.getElementById("bud-lines-card"); if (box) box.scrollIntoView({ behavior: "smooth", block: "start" }); });
            },
            finBudgetEditCancel() { this.finBudgetEditing = false; this.finBudgetLine = newLine(); this.finBudgetReason = ""; this.finBudgetError = ""; },
            finBudgetSendBack() {
                this.finBudgetBack = { ...newBack(), show: true };
                if (this.$nextTick) this.$nextTick(() => { const box = document.getElementById("bud-back-box"); if (box) box.scrollIntoView({ behavior: "smooth", block: "center" }); });
            },
            finBudgetUsedPercent(line) {
                const planned = Number(line.amount) || 0;
                return planned > 0 ? Math.min(100, Math.round((Number(line.actual) / planned) * 100)) : 0;
            },

            async finBudgetEnter() {
                this.finBudget = null; this.finBudgetError = ""; this.finBudgetEditing = false;
                this.finBudgetStart = newStart(); this.finBudgetLine = newLine(); this.finBudgetBack = newBack();
                await Promise.all([this.finLoadYears(), this.finBudgetsLoad()]);
            },
            async finBudgetsLoad(opts = {}) {
                if (!opts.silent) { this.finBudgetsLoading = true; this.finBudgetsError = ""; }
                try {
                    this.finBudgets = (await this._finGet("/budgets")).items;
                } catch (err) {
                    if (!opts.silent) this.finBudgetsError = err.message || "Failed to load the budgets.";
                } finally {
                    this.finBudgetsLoading = false;
                }
            },
            async finBudgetOpen(pk) {
                this.finBudgetError = "";
                try {
                    this._finBudgetSet(await this._finGet(`/budgets/${pk}`));
                    await this._finBudgetLoadHeads();
                } catch (err) {
                    this.finBudgetError = err.message || "Failed to load the budget.";
                }
            },
            finBudgetClose() {
                this.finBudget = null; this.finBudgetError = ""; this.finBudgetEditing = false;
                return this.finBudgetsLoad({ silent: true });
            },
            // The open budget changed (a step, a line): show the server's new picture and reset every form that belonged to the old one.
            _finBudgetSet(detail) {
                this.finBudget = detail;
                this.finBudgetLine = newLine(); this.finBudgetRefer = newRefer(); this.finBudgetViews = newViews();
                this.finBudgetPass = newPass(); this.finBudgetBack = newBack(); this.finBudgetFix = newFix(); this.finBudgetReason = "";
            },
            async _finBudgetLoadHeads() {
                if (!this.finBudget || this.finBudgetHeads.length) return;
                const params = { organization_pk: this.finBudget.organization_pk, with_templates: false, status: "ACTIVE", page_size: 200 };
                this.finBudgetHeadsNote = "";
                try {
                    let res = await this._finGet("/heads", params);
                    // The Kendra has no heads of its own until the standard ones are copied in (the same step a new scope takes). Do it here so a
                    // budget works out of the box, for someone who may configure finance; anyone else is told whom to ask.
                    if (res.items.length === 0 && this.canConfigureFinance) {
                        await this._finSend("POST", "/heads/adopt-templates", { organization_pk: this.finBudget.organization_pk });
                        res = await this._finGet("/heads", params);
                    }
                    this.finBudgetHeads = res.items;
                    if (res.items.length === 0) {
                        this.finBudgetHeadsNote = this.canConfigureFinance
                            ? "The Kendra has no finance heads yet. Add them under Finance > Heads, then come back."
                            : "The Kendra has no finance heads yet. Someone who can configure finance must add them first (Finance > Heads).";
                    }
                } catch (err) { this.finBudgetHeadsNote = err.message || "Could not load the finance heads."; }
            },

            // ── Start a budget ─────────────────────────────────────
            finBudgetStartOpen() {
                const first = this.finBudgetYear || this.finBudgetNextYear;
                this.finBudgetStart = { ...newStart(), show: true, year: first ? first.financial_year_pk : "" };
            },
            async finBudgetStartSubmit() {
                const f = this.finBudgetStart;
                if (!f.year) { f.error = "There is no current financial year to start a budget for."; return; }
                f.saving = true; f.error = "";
                try {
                    const detail = await this._finSend("POST", "/budgets", { financial_year_pk: f.year });
                    this.finBudgetStart = newStart();
                    this._finBudgetSet(detail); this.finBudgetHeads = [];
                    await this._finBudgetLoadHeads();
                    this._finNote("Budget started. Add the budget lines, then refer the draft to the Advisory Board.");
                } catch (err) {
                    f.error = err.message || "Could not start the budget.";
                } finally {
                    f.saving = false;
                }
            },

            // ── Lines ──────────────────────────────────────────────
            finBudgetLineOpen(line) {
                this.finBudgetLine = line
                    ? { ...newLine(), editing: true, head: line.finance_head_pk, amount: String(line.amount), notes: line.notes || "" }
                    : newLine();
                if (line && this.$nextTick) this.$nextTick(() => { const box = document.getElementById("bud-line-form"); if (box) box.scrollIntoView({ behavior: "smooth", block: "center" }); });
            },

            async finBudgetLineSave() {
                const f = this.finBudgetLine;
                if (!f.head) { f.error = "Choose the head."; return; }
                const bad = this._finMoneyOk(f.amount, "Amount");
                if (bad) { f.error = bad; return; }
                if (this.finBudgetNeedsReason && !this.finBudgetReason.trim()) { f.error = "Say why the line is changing (the reason box above the lines)."; return; }
                f.saving = true; f.error = "";
                try {
                    this._finBudgetSet(await this._finSend("PUT", `/budgets/${this.finBudget.finance_budget_pk}/lines`,
                        { finance_head_pk: f.head, amount: String(f.amount).trim(), notes: f.notes.trim() || null, reason: this.finBudgetReason.trim() || null }));
                    this._finNote("Budget line saved.");
                } catch (err) {
                    f.error = err.message || "Could not save the line.";
                } finally {
                    f.saving = false;
                }
            },
            async finBudgetLineRemove(line) {
                if (this.finBudgetNeedsReason && !this.finBudgetReason.trim()) { this.finBudgetError = "Say why the line is being removed (the reason box above the lines)."; return; }
                const ok = await NSSDialog.confirm(`Remove the budget line for ${line.head_name}?`, { title: "Remove budget line", confirmText: "Remove", confirmClass: "danger" });
                if (!ok) return;
                this.finBudgetError = "";
                try {
                    const path = `/budgets/${this.finBudget.finance_budget_pk}/lines/${line.finance_budget_line_pk}`
                        + (this.finBudgetReason.trim() ? "?reason=" + encodeURIComponent(this.finBudgetReason.trim()) : "");
                    this._finBudgetSet(await this._finSend("DELETE", path));
                    this._finNote("Budget line removed.");
                } catch (err) {
                    this.finBudgetError = err.message || "Could not remove the line.";
                }
            },

            // ── The steps ──────────────────────────────────────────
            // Each caller names its own route (literal, so it can be checked against the router); this runs the request and shows the result.
            async _finBudgetStep(form, send, done) {
                form.saving = true; form.error = "";
                try {
                    this._finBudgetSet(await send());
                    this._finNote(done);
                } catch (err) {
                    form.error = err.message || "That step could not be recorded.";
                } finally {
                    form.saving = false;
                }
            },
            // Referring files a numbered letter in Correspondence (the server does it); the date is today unless one is chosen.
            finBudgetDoRefer() {
                const f = this.finBudgetRefer, pk = this.finBudget.finance_budget_pk;
                return this._finBudgetStep(f, () => this._finSend("POST", `/budgets/${pk}/refer`, { referred_on: f.date || null }),
                    "Referred to the Advisory Board. The letter is filed in Correspondence.");
            },
            // The Advisory Board's reply is filed the same way and its number becomes the reference: only what it said is typed.
            finBudgetDoViews() {
                const f = this.finBudgetViews, pk = this.finBudget.finance_budget_pk;
                if (!f.summary.trim()) { f.error = "Enter what the Advisory Board said."; return; }
                return this._finBudgetStep(f, () => this._finSend("POST", `/budgets/${pk}/advisory-views`,
                    { advisory_views_date: f.date || null, advisory_views_summary: f.summary.trim() }),
                    "The Advisory Board's views are on file. Its reply is filed in Correspondence.");
            },
            finBudgetDoPass() {
                const f = this.finBudgetPass, pk = this.finBudget.finance_budget_pk;
                if (!f.reference.trim() || !f.date) { f.error = "Enter the Governing Body's resolution reference and its date."; return; }
                return this._finBudgetStep(f, () => this._finSend("POST", `/budgets/${pk}/pass`,
                    { resolution_reference: f.reference.trim(), resolution_date: f.date }), "The budget is passed.");
            },
            finBudgetDoBack() {
                const f = this.finBudgetBack, pk = this.finBudget.finance_budget_pk;
                if (!f.remarks.trim()) { f.error = "Say why the draft goes back."; return; }
                return this._finBudgetStep(f, () => this._finSend("POST", `/budgets/${pk}/reopen`, { remarks: f.remarks.trim() }),
                    "Sent back to draft. Refer it again once it is changed.");
            },

            // A correction is offered once the Advisory Board's views are on file (its summary) and, once passed, for the resolution reference too.
            get finBudgetCanCorrect() { return !!this.finBudget && this.canManageFinance && ["VIEWS_RECEIVED", "PASSED"].includes(this.finBudget.status); },
            finBudgetFixOpen() {
                const b = this.finBudget;
                this.finBudgetFix = { ...newFix(), show: true, summary: b.advisory_views_summary || "", reference: b.resolution_reference || "" };
            },
            finBudgetDoFix() {
                const f = this.finBudgetFix, b = this.finBudget;
                if (!f.reason.trim()) { f.error = "Say why it is being corrected."; return; }
                const body = { reason: f.reason.trim() };
                if (f.summary.trim() !== (b.advisory_views_summary || "")) body.advisory_views_summary = f.summary.trim();
                if (b.status === "PASSED" && f.reference.trim() !== (b.resolution_reference || "")) body.resolution_reference = f.reference.trim();
                if (Object.keys(body).length === 1) { f.error = "Change the summary or the resolution reference first."; return; }
                return this._finBudgetStep(f, () => this._finSend("POST", `/budgets/${b.finance_budget_pk}/correct`, body),
                    "Corrected. The reason and the old text are kept in the record.");
            },

            // ── Live refresh (finance.js finLiveReload / finLiveBusy call these) ──
            finBudgetBusy() {
                return this.finBudgetEditing || [this.finBudgetStart, this.finBudgetBack, this.finBudgetFix].some((f) => f.show || f.saving)
                    || [this.finBudgetRefer, this.finBudgetViews, this.finBudgetPass].some((f) => f.saving
                        || Object.entries(f).some(([k, v]) => ["date", "reference", "summary"].includes(k) && String(v).trim() !== ""));
            },
            async finBudgetReload() {
                if (!this.finBudget) return this.finBudgetsLoad({ silent: true });
                try { this.finBudget = await this._finGet(`/budgets/${this.finBudget.finance_budget_pk}`); }
                catch { /* the open budget stays as it was; a manual reopen explains */ }
            },
        };
    }

    window.NSSFinanceBudget = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(financeBudgetMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
