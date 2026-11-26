/**
 * Finance "Annual Audit" tab (Tier 12, owner request 2026-11-26; Bye-Law Section G, REF-003-G) - the audit of the Kendra's accounts.
 *
 * "The Accounts of the Kendra Sangha shall be audited every year by appointing a qualified Auditor by the Governing Body and the Audit Report shall be
 * placed first before the Governing Body and then in the combined meeting of the Governing Body and the Advisory Board for their approval only after
 * which the same will be placed before the General Body of the Kendra Sangha by the Secretary."
 * The screen walks the five steps the server enforces (api/services/finance_audit.py is the ONE home of the rules):
 *   Auditor appointed -> Report received -> Placed before the Governing Body -> Approved by the combined meeting -> Placed before the General Body.
 * Each step records a date and a reference and none can be skipped. Any financial year may be audited, whatever its status. Placing the report before
 * the Governing Body files a numbered letter to the Advisory Board in Correspondence by itself. The Parichalak's personal expenditure is not subject to
 * audit (Bye-Law clause 17) and is only shown, never counted.
 *
 * A seventh Finance mixin, mixed into `adminPanel()` (admin.js) beside the others, using their helpers (_finGet / _finSend / _finNote / finBadge /
 * finDate / finMoney / finLoadYears / canManageFinance / finKendraSide). The page decides nothing about who may act: the server checks FINANCE_VIEW /
 * FINANCE_MANAGE and admin scope on the Kendra (a Sakha admin simply sees no audit, and the sidebar hides the tab from them).
 */
(function () {
    "use strict";

    const STEPS = [
        { key: "APPOINTED", label: "Auditor appointed by the Governing Body" },
        { key: "REPORT_RECEIVED", label: "Audit Report received" },
        { key: "PLACED_BEFORE_GB", label: "Placed before the Governing Body" },
        { key: "APPROVED", label: "Approved by the combined meeting" },
        { key: "PLACED_BEFORE_GENERAL_BODY", label: "Placed before the General Body" },
    ];
    const today = () => new Date().toISOString().slice(0, 10);
    const newStart = () => ({ show: false, year: "", name: "", firm: "", date: "", reference: "", notes: "", saving: false, error: "" });
    const newReport = () => ({ reference: "", date: "", link: "", saving: false, error: "" });
    const newGb = () => ({ date: "", reference: "", saving: false, error: "" });
    const newApproval = () => ({ date: "", reference: "", saving: false, error: "" });
    const newGeneral = () => ({ date: "", reference: "", saving: false, error: "" });
    const newFix = () => ({ show: false, name: "", firm: "", appointment: "", report: "", link: "", gb: "", approval: "", general: "", reason: "", saving: false, error: "" });

    function financeAuditMixin() {
        return {
            finAudits: [], finAuditsLoading: false, finAuditsError: "",
            finAudit: null,                            // the open audit (GET /audits/{pk})
            finAuditError: "",
            finAuditStart: newStart(), finAuditReport: newReport(), finAuditGb: newGb(), finAuditApproval: newApproval(), finAuditGeneral: newGeneral(),
            finAuditFix: newFix(),

            finAuditLabel(state) { return NSS.financeStatusLabel(state); },
            get finAuditToday() { return today(); },
            // The whole tab is the Kendra's (the sidebar shows it only when finKendraSide); the server checks scope on every call.
            get finAuditCanAct() { return this.canManageFinance && this.finKendraSide; },
            get finAuditSteps() {
                const at = this.finAudit ? STEPS.findIndex((s) => s.key === this.finAudit.status) : -1;
                const last = STEPS.length - 1;
                return STEPS.map((s, i) => ({ ...s, done: i < at || (i === at && i === last), current: i === at && i !== last }));
            },
            // Any year may be audited (owner 2026-11-26), but each year has one audit: the years without one yet, newest first.
            get finAuditYearChoices() {
                const taken = new Set(this.finAudits.map((a) => a.financial_year_pk));
                return [...(this.finYears || [])].filter((y) => !taken.has(y.financial_year_pk))
                    .sort((a, b) => String(b.year_code).localeCompare(String(a.year_code)));
            },

            async finAuditEnter() {
                this.finAudit = null; this.finAuditError = "";
                this.finAuditStart = newStart(); this.finAuditFix = newFix();
                await Promise.all([this.finLoadYears(), this.finAuditsLoad()]);
            },
            async finAuditsLoad(opts = {}) {
                if (!opts.silent) { this.finAuditsLoading = true; this.finAuditsError = ""; }
                try {
                    this.finAudits = (await this._finGet("/audits")).items;
                } catch (err) {
                    if (!opts.silent) this.finAuditsError = err.message || "Failed to load the audits.";
                } finally {
                    this.finAuditsLoading = false;
                }
            },
            async finAuditOpen(pk) {
                this.finAuditError = "";
                try {
                    this._finAuditSet(await this._finGet(`/audits/${pk}`));
                } catch (err) {
                    this.finAuditError = err.message || "Failed to load it.";
                }
            },
            finAuditClose() {
                this.finAudit = null; this.finAuditError = "";
                return this.finAuditsLoad({ silent: true });
            },
            // The open one changed: show the server's new picture and reset the forms that belonged to the old one.
            _finAuditSet(detail) {
                this.finAudit = detail;
                this.finAuditReport = newReport(); this.finAuditGb = newGb(); this.finAuditApproval = newApproval(); this.finAuditGeneral = newGeneral();
                this.finAuditFix = newFix();
            },

            // ── Start: the Governing Body appoints the Auditor ─────
            finAuditStartOpen() {
                this.finAuditStart = { ...newStart(), show: true, date: today() };
            },
            async finAuditStartSubmit() {
                const f = this.finAuditStart;
                if (!f.year) { f.error = "Choose the financial year."; return; }
                if (!f.name.trim()) { f.error = "Enter the Auditor's name."; return; }
                if (!f.date) { f.error = "Enter the date of the appointment."; return; }
                if (!f.reference.trim()) { f.error = "Enter the Governing Body's resolution reference."; return; }
                f.saving = true; f.error = "";
                try {
                    const detail = await this._finSend("POST", "/audits", {
                        financial_year_pk: f.year, auditor_name: f.name.trim(), auditor_firm: f.firm.trim() || null, appointed_on: f.date,
                        appointment_reference: f.reference.trim(), notes: f.notes.trim() || null,
                    });
                    this.finAuditStart = newStart();
                    this._finAuditSet(detail);
                    this._finNote("The audit has begun: the Governing Body's appointment of the Auditor is on record.");
                } catch (err) {
                    f.error = err.message || "Could not start the audit.";
                } finally {
                    f.saving = false;
                }
            },

            // One step of the chain: validate what the page can, send (the caller supplies the request, so every path is written out where it is used),
            // show the server's new picture. The server decides everything else.
            async _finAuditStep(form, send, note, check) {
                const problem = check();
                if (problem) { form.error = problem; return; }
                form.saving = true; form.error = "";
                try {
                    this._finAuditSet(await send(this.finAudit.finance_year_audit_pk));
                    this._finNote(note);
                } catch (err) {
                    form.error = err.message || "Could not record it.";
                } finally {
                    form.saving = false;
                }
            },
            finAuditReportSubmit() {
                const f = this.finAuditReport;
                return this._finAuditStep(f, (pk) => this._finSend("POST", `/audits/${pk}/report`, { report_reference: f.reference.trim(), report_date: f.date, report_link: f.link.trim() || null }),
                    "The Audit Report is on record.", () => !f.reference.trim() ? "Enter the Audit Report's reference." : !f.date ? "Enter the date of the report."
                        : f.link.trim() && !/^https:\/\//i.test(f.link.trim()) ? "The link must start with https://." : "");
            },
            finAuditGbSubmit() {
                const f = this.finAuditGb;
                return this._finAuditStep(f, (pk) => this._finSend("POST", `/audits/${pk}/governing-body`, { gb_placed_on: f.date || null, gb_reference: f.reference.trim() }),
                    "Placed before the Governing Body. A numbered letter to the Advisory Board has been filed in Correspondence for the combined meeting.",
                    () => !f.reference.trim() ? "Enter the Governing Body's resolution / minute reference." : "");
            },
            finAuditApprovalSubmit() {
                const f = this.finAuditApproval;
                return this._finAuditStep(f, (pk) => this._finSend("POST", `/audits/${pk}/approval`, { approved_on: f.date, approval_reference: f.reference.trim() }),
                    "The combined meeting's approval is on record.",
                    () => !f.date ? "Enter the date of the combined meeting." : !f.reference.trim() ? "Enter the combined meeting's resolution / minute reference." : "");
            },
            async finAuditGeneralSubmit() {
                const f = this.finAuditGeneral;
                const ok = f.date && f.reference.trim() && await NSSDialog.confirm(
                    "Record that the Secretary placed the approved Audit Report before the General Body? This is the last step.",
                    { title: "Place before the General Body", confirmText: "Record", confirmClass: "primary" });
                if (f.date && f.reference.trim() && !ok) return;
                return this._finAuditStep(f, (pk) => this._finSend("POST", `/audits/${pk}/general-body`, { general_body_on: f.date, general_body_reference: f.reference.trim() }),
                    "The audit is complete: the report has been placed before the General Body.",
                    () => !f.date ? "Enter the date of the General Body meeting." : !f.reference.trim() ? "Enter the General Body's agenda / minute reference." : "");
            },

            // ── Correct recorded text (with a reason; the status does not move) ──
            finAuditFixOpen() {
                const a = this.finAudit;
                this.finAuditFix = { ...newFix(), show: true, name: a.auditor_name || "", firm: a.auditor_firm || "", appointment: a.appointment_reference || "",
                    report: a.report_reference || "", link: a.report_link || "", gb: a.gb_reference || "", approval: a.approval_reference || "", general: a.general_body_reference || "" };
            },
            async finAuditFixSubmit() {
                const f = this.finAuditFix, a = this.finAudit;
                if (!f.reason.trim()) { f.error = "Say why it is being corrected."; return; }
                // Send only what differs from the record, so the server's "nothing to correct" is a real signal.
                const body = {};
                const same = (now, was) => (now || "").trim() === (was || "").trim();
                if (!same(f.name, a.auditor_name)) body.auditor_name = f.name.trim();
                if (!same(f.firm, a.auditor_firm)) body.auditor_firm = f.firm.trim();
                if (!same(f.appointment, a.appointment_reference)) body.appointment_reference = f.appointment.trim();
                if (a.report_reference && !same(f.report, a.report_reference)) body.report_reference = f.report.trim();
                if (a.report_reference && !same(f.link, a.report_link)) body.report_link = f.link.trim();
                if (a.gb_reference && !same(f.gb, a.gb_reference)) body.gb_reference = f.gb.trim();
                if (a.approval_reference && !same(f.approval, a.approval_reference)) body.approval_reference = f.approval.trim();
                if (a.general_body_reference && !same(f.general, a.general_body_reference)) body.general_body_reference = f.general.trim();
                if (Object.keys(body).length === 0) { f.error = "Nothing has been changed."; return; }
                f.saving = true; f.error = "";
                try {
                    this._finAuditSet(await this._finSend("POST", `/audits/${a.finance_year_audit_pk}/correct`, { ...body, reason: f.reason.trim() }));
                    this._finNote("Corrected. The old and new text are kept in the audit trail.");
                } catch (err) {
                    f.error = err.message || "Could not correct it.";
                } finally {
                    f.saving = false;
                }
            },

            // Live refresh (finance.js finLiveBusy / finLiveReload): never replace the page under a form that is being filled in.
            finAuditBusy() {
                return [this.finAuditStart, this.finAuditFix].some((f) => f.show || f.saving)
                    || [this.finAuditReport, this.finAuditGb, this.finAuditApproval, this.finAuditGeneral].some((f) => f.saving
                        || ["date", "reference", "link"].some((k) => String(f[k] || "").trim() !== ""));
            },
            async finAuditReload() {
                if (!this.finAudit) return this.finAuditsLoad({ silent: true });
                try { this._finAuditKeepForms(await this._finGet(`/audits/${this.finAudit.finance_year_audit_pk}`)); }
                catch { /* the open audit stays as it was; a manual reopen explains */ }
            },
            _finAuditKeepForms(detail) { this.finAudit = detail; },
        };
    }

    window.NSSFinanceAudit = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(financeAuditMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
