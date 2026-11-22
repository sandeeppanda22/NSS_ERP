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
    // A picker already holding its Sangha (edit forms): the name goes in the text box too, not only in the "Belongs to" hint under it.
    const pickerWith = (pk, name) => ({ ...emptyPicker(), selected: pk ? { organization_pk: pk, organization_name: name } : null, query: pk ? (name || "") : "" });
    const blank = (v) => {
        const t = (v == null ? "" : String(v)).trim();
        return t === "" ? null : t;
    };
    const MONEY_RE = /^\d+(\.\d{1,2})?$/;

    const newHeadForm = () => ({
        show: false, mode: "create", pk: "", saving: false, error: "", template: false, organization: emptyPicker(),
        head_code: "", head_name: "", description: "", direction: "INCOME", is_restricted: false, restriction_purpose: "",
        required_fund_type: "", is_pranami: false, allow_upi: false, collection_scope_pk: "", collection_fund_pk: "",
        collection_account_pk: "", lockedShape: false,
        kind: "normal",            // edit only: "copy" = a Sakha's copy of a Kendra head (only its account changes), "source" = a head for all Sakhas (no collection targets)
        fixed_amount: "", due_period: "", allow_part_payment: false,
        skips_approval: false, treasurer_limit: "", requires_member: false,
    });
    // The SIMPLE contribution form (owner 2026-11-15): name, optional fixed amount, how often, part payment. Everything else
    // (code, income, member-visible, UPI, scope, default account) is filled in by the server.
    const newContribForm = () => ({
        show: false, saving: false, error: "", organization: emptyPicker(), applies_to: "ORGANIZATION", head_name: "", description: "",
        fixed_amount: "", due_period: "YEARLY", allow_part_payment: false, collection_account_pk: "",
        collection_scope_pk: "", collection_fund_pk: "",     // optional: left empty the server uses the Sangha's general scope and no fund
        direction: "INCOME",       // INCOME: members pay it in; EXPENSE: money the Sangha spends
    });
    const newPolicy = () => ({ loaded: false, saving: false, error: "", current: null, input: "" });
    // A Sakha's copy of a Kendra head: only the receiving account is the Sakha's to choose.
    const newCopyForm = () => ({ show: false, saving: false, error: "", pk: "", name: "", organization_pk: "", collection_account_pk: "" });
    // An event a Sangha collects for (e.g. Rasa): one step creates its EVENT scope and a member-payable UPI head.
    const newEventForm = () => ({
        show: false, saving: false, error: "", organization: emptyPicker(), event_name: "", description: "", collection_account_pk: "",
    });
    const newAcctForm = () => ({
        show: false, mode: "create", pk: "", saving: false, error: "", organization: emptyPicker(), account_label: "",
        account_type: "BANK", bank_name: "", branch_name: "", account_holder_name: "", account_number_last4: "", ifsc_code: "",
        upi_vpa: "", gateway_provider: "", gateway_credential_ref: "", gateway_merchant_ref: "", is_default: false,
    });
    // member = the payer picker: type a name / ID, choose from the matches (sangha_sevi_id is then set); a payer who is not a member is typed in payer_name.
    const newReqForm = () => ({ show: false, saving: false, error: "", finance_head_pk: "", amount: "", sangha_sevi_id: "", payer_name: "", note: "",
                                member: { query: "", results: [], searching: false, selected: null } });

    function financeSetupMixin() {
        return {
            // ═════════════════════════════════════════════════════════
            // Tab entry + live refresh (called by finance.js' finEnterTab / finLiveReload / finLiveBusy)
            // ═════════════════════════════════════════════════════════
            async finSetupEnter() {
                this.finHeadForm = newHeadForm(); this.finAcctForm = newAcctForm(); this.finEventForm = newEventForm();
                this.finContribForm = newContribForm(); this.finCopyForm = newCopyForm();
                // A scope that names exactly one Sangha (a Sakha admin) has nothing to choose: select it.
                const own = this.finSetupScopeOrg;
                if (own && this.finSetupOrgPk !== own.organization_pk) { this.corrSelectOrg(this.finSetupOrg, own); await this.finPolicyLoad(); }
                await this.finEnsureDefaultHeads();
                await Promise.all([this.finHeadsLoad(), this.finAcctsLoad()]);
            },
            async finSetupReload() {
                await Promise.all([this.finHeadsLoad({ silent: true }), this.finAcctsLoad({ silent: true }), this.finGatewayRefresh()]);
            },
            finSetupBusy() { return !!(this.finPolicy.saving || this.finContribForm.show || this.finPortalForm.show || this.finCopyForm.show || this.finHeadForm.show || this.finAcctForm.show || this.finEventForm.show || this.finEventForm.saving || this.finHeadForm.saving || this.finAcctForm.saving); },

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
            // The one Sangha the caller's admin scope names, or null when it names none (NSS-wide / Kendra / a null-organization scope)
            // or several (they choose). Read from the login's own scopes, so it needs no extra request.
            get finSetupScopeOrg() {
                if (this.isNssAdmin || this.isGovNssWideAdmin) return null;
                const named = new Map();
                for (const sc of (this.currentUser?.scopes || [])) if (sc.organization_pk) named.set(sc.organization_pk, sc);
                if (named.size !== 1) return null;
                const sc = [...named.values()][0];
                return { organization_pk: sc.organization_pk, organization_name: sc.organization_name,
                         organization_type_code: sc.organization_type_code, type_name: NSS.codeLabel(sc.organization_type_code) };
            },
            get finSetupOrgLocked() { return !!this.finSetupScopeOrg; },
            // Owner 2026-11-20: whoever reaches Finance ONLY through the Treasurer seat (role NSS_ERP_SAKHA_TREASURER, no admin role) configures heads, contributions,
            // events and accounts, but cannot change the controls that bind the Treasurer: the approval limit and a head's "needs no approval" flag. The server refuses
            // it by SEAT (finance_approval.require_not_the_treasurer); this only greys the fields out and says why.
            get finControlsLocked() {
                const roles = ((this.currentUser && this.currentUser.scopes) || []).map((s) => s.role_code);
                // Whoever also holds a Finance role (the President / Secretary by seat, or an admin given one) or is the NSS ERP Administrator may change them.
                return roles.includes("NSS_ERP_SAKHA_TREASURER") && !roles.some((r) => ["NSS_ERP_ADMIN", "NSS_ERP_SAKHA_FINANCE_ADMIN", "NSS_ERP_KENDRA_FINANCE_ADMIN"].includes(r));
            },
            async finSetupOrgChanged() { await this.finEnsureDefaultHeads(); return Promise.all([this.finSetupReload(), this.finPolicyLoad()]); },

            // The standard (Kendra template) heads - Membership subscription, Parichaya Patra, Anumati Patra, Annual / Special Pranami,
            // donations, grant, expenses ... - are in a Sangha's list from the start (owner 2026-11-18): the first time a configurer
            // looks at a Sangha's heads in this session they are copied in. Safe to repeat: heads the Sangha already has (same code,
            // even renamed or switched off) are skipped, and every copy starts with its payment portal closed.
            _finDefaultsSeen: {},
            async finEnsureDefaultHeads() {
                const pk = this.finSetupOrgPk;
                if (!pk || !this.canConfigureFinance || this._finDefaultsSeen[pk]) return;
                this._finDefaultsSeen[pk] = true;
                try {
                    const r = await this._finSend("POST", "/heads/adopt-templates", { organization_pk: pk });
                    if (r.created) this._finNote(`${r.created} standard finance head(s) added to this Sangha. Open a head's payment portal when members should pay it.`);
                } catch { /* the list still loads; "Create head" works without the defaults */ }
            },
            finSetupClearOrg() { this.corrClearPicker(this.finSetupOrg); this.finPolicy = newPolicy(); return this.finSetupReload(); },

            // The Treasurer's default approval limit of the chosen Sakha (owner 2026-11-17): what the Treasurer may approve alone on
            // an expense head with no limit of its own. Setting it widens the Treasurer's power, so it needs FINANCE_CONFIGURE.
            finPolicy: newPolicy(),
            get finPolicyApplies() {
                const o = this.finSetupOrg.selected;
                return !!o && (NSS.SAKHA_LIKE_ORG_TYPES || []).includes(o.type_code);
            },
            async finPolicyLoad() {
                this.finPolicy = newPolicy();
                if (!this.finPolicyApplies) return;
                try {
                    const r = await this._finGet("/approval-policy", { organization_pk: this.finSetupOrgPk });
                    this.finPolicy = { ...newPolicy(), loaded: true, current: r.default_treasurer_limit, input: r.default_treasurer_limit == null ? "" : String(r.default_treasurer_limit) };
                } catch (err) { this.finPolicy = { ...newPolicy(), error: err.message || "Could not load the approval limit." }; }
            },
            async finPolicySave() {
                const p = this.finPolicy;
                const v = blank(p.input);
                if (v && (!MONEY_RE.test(v) || Number(v) <= 0)) { p.error = "Enter a positive amount with at most two decimals, or leave it empty for no default."; return; }
                p.saving = true; p.error = "";
                try {
                    const r = await this._finSend("PUT", "/approval-policy", { organization_pk: this.finSetupOrgPk, default_treasurer_limit: v });
                    this.finPolicy = { ...newPolicy(), loaded: true, current: r.default_treasurer_limit, input: r.default_treasurer_limit == null ? "" : String(r.default_treasurer_limit) };
                    this._finNote(r.default_treasurer_limit == null ? "The Treasurer no longer has a default limit: every spend needs the President too unless its head has its own limit."
                        : `The Treasurer may now approve up to ${NSS.formatMoney(r.default_treasurer_limit)} alone on a head with no limit of its own.`);
                } catch (err) { p.error = err.message || "Could not save the approval limit."; p.saving = false; }
            },

            // ═════════════════════════════════════════════════════════
            // Finance heads
            // ═════════════════════════════════════════════════════════
            finHeads: [], finHeadsTotal: 0, finHeadsLoading: false, finHeadsError: "", _finHeadsSeq: 0,
            finHeadView: "sangha",                 // "sangha" | "events" | "templates"
            finHeadQ: "", finHeadDirFilter: "", finHeadStatusFilter: "",
            finHeadForm: newHeadForm(), finHeadScopes: [], finHeadFunds: [], finHeadAccounts: [],
            finHeadOptions: { fundTypes: [] },

            get finHeadsAreTemplates() { return this.finHeadView === "templates"; },
            get finHeadsAreEvents() { return this.finHeadView === "events"; },

            async finHeadsLoad(opts = {}) {
                const seq = ++this._finHeadsSeq;
                if (!opts.silent) { this.finHeadsLoading = true; this.finHeadsError = ""; }
                try {
                    const data = await this._finGet("/heads", {
                        q: this.finHeadQ.trim(), direction: this.finHeadDirFilter, status: this.finHeadStatusFilter, page_size: 200,
                        ...(this.finHeadsAreTemplates ? { templates_only: "true" }
                            : { with_templates: "false", organization_pk: this.finSetupOrgPk, ...(this.finHeadView === "events" ? { events_only: "true" } : {}) }),
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
                    kind: h.is_kendra_copy ? "copy" : (h.applies_to_all_sakhas ? "source" : "normal"),
                    organization: pickerWith(h.organization_pk, h.organization_name),
                    head_code: h.head_code, head_name: h.head_name, description: h.description || "", direction: h.direction,
                    is_restricted: h.is_restricted, restriction_purpose: h.restriction_purpose || "", required_fund_type: h.required_fund_type || "",
                    is_pranami: h.is_pranami, allow_upi: h.allow_upi, collection_scope_pk: h.collection_scope_pk || "",
                    collection_fund_pk: h.collection_fund_pk || "", collection_account_pk: h.collection_account_pk || "",
                    fixed_amount: h.fixed_amount == null ? "" : String(h.fixed_amount), due_period: h.due_period || "", allow_part_payment: !!h.allow_part_payment,
                    skips_approval: !!h.skips_approval, treasurer_limit: h.treasurer_limit == null ? "" : String(h.treasurer_limit),
                    requires_member: !!h.requires_member,
                };
                await this.finHeadFormOrgChanged(true);
                if (h.collection_scope_pk && !this.finHeadScopes.some((sc) => sc.financial_scope_pk === h.collection_scope_pk)) {
                    this.finHeadScopes = [...this.finHeadScopes, { financial_scope_pk: h.collection_scope_pk, scope_code: h.collection_scope_code, scope_name: h.collection_scope_name }];
                }
                if (h.collection_fund_pk && !this.finHeadFunds.some((fd) => fd.fund_master_pk === h.collection_fund_pk)) {
                    this.finHeadFunds = [...this.finHeadFunds, { fund_master_pk: h.collection_fund_pk, fund_code: h.collection_fund_code, fund_name: h.collection_fund_name, is_restricted: false }];
                }
                // the form is above the list: bring it into view
                this.$nextTick(() => { const el = document.getElementById("head-form-card"); if (el) el.scrollIntoView({ behavior: "smooth", block: "start" }); });
            },
            // Delete a head. An UNUSED head is removed (a soft delete on the server). A head with money history is never deleted - history is never
            // erased - so the person is told why and offered the alternative, switching it OFF (members stop seeing it, nothing new can use it, the
            // history stays). A Sakha's copy of a Kendra head is switched off the same way. The server has the last word: a 409 gets the same offer.
            async finHeadDelete(h) {
                if (h.is_kendra_copy || Number(h.transaction_count) > 0) return this._finHeadOfferSwitchOff(h);
                const ok = await NSSDialog.confirm(
                    `Delete "${h.head_name}"? It has no payments or entries, so it is simply removed. ` +
                    (h.applies_to_all_sakhas ? "The copies the Sakhas received are removed with it. " : "") +
                    "A head that has been used can only be switched off.",
                    { title: "Delete finance head", confirmText: "Delete", confirmClass: "danger" });
                if (!ok) return;
                this.finHeadsError = "";
                try {
                    await this._finSend("DELETE", `/heads/${h.finance_head_pk}`);
                    if (this.finHeadForm.pk === h.finance_head_pk) this.finHeadForm = newHeadForm();
                    this._finNote(`Finance head "${h.head_name}" deleted.`);
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    if (err.status === 409 || err.status === 403) return this._finHeadOfferSwitchOff(h, err.message);
                    this.finHeadsError = err.message || "Could not delete the finance head.";
                }
            },
            async _finHeadOfferSwitchOff(h, reason) {
                const n = Number(h.transaction_count) || 0;
                const why = reason || (h.is_kendra_copy
                    ? `"${h.head_name}" comes from the Kendra, so it cannot be deleted here.`
                    : `"${h.head_name}" has ${n} ${n === 1 ? "entry" : "entries"} recorded on it, so it cannot be deleted: money history is never erased.`);
                const ok = await NSSDialog.confirm(
                    `${why} Switch it off instead? Members stop seeing it and nothing new can be recorded on it; everything already recorded stays, and you can switch it on again.`,
                    { title: "Switch the head off?", confirmText: "Switch off" });
                if (ok) return this.finHeadSwitch(h, "INACTIVE");
            },
            // Switch a head off (INACTIVE) or back on (ACTIVE) through the lifecycle endpoint; the server also moves every Sakha copy of a Kendra head.
            async finHeadSwitch(h, to) {
                this.finHeadsError = "";
                try {
                    await this._finSend("POST", `/heads/${h.finance_head_pk}/transition`, { status: to, remarks: null });
                    this._finNote(to === "INACTIVE" ? `"${h.head_name}" switched off.` : `"${h.head_name}" switched on.`);
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    this.finHeadsError = err.message || "Could not change the finance head.";
                }
            },
            async finHeadSwitchOff(h) {
                const ok = await NSSDialog.confirm(
                    `Switch "${h.head_name}" off? Members stop seeing it and nothing new can be recorded on it; everything already recorded stays, and you can switch it on again.`,
                    { title: "Switch the head off?", confirmText: "Switch off" });
                if (ok) return this.finHeadSwitch(h, "INACTIVE");
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
                if (f.kind === "normal" && f.allow_upi && (!f.collection_scope_pk || !f.collection_account_pk)) { f.error = "UPI collection needs a collection scope and a receiving account."; return; }
                const amount = blank(f.fixed_amount);
                if (edit && amount && !MONEY_RE.test(amount)) { f.error = "The amount must be a number with at most two decimals."; return; }
                if (edit && amount && !f.due_period) { f.error = "Choose how often the amount is due."; return; }
                const limit = blank(f.treasurer_limit);
                if (f.direction === "EXPENSE" && limit && (!MONEY_RE.test(limit) || Number(limit) <= 0)) { f.error = "The Treasurer's limit must be a positive amount with at most two decimals."; return; }
                f.saving = true; f.error = "";
                try {
                    // Sakha approval rules (owner 2026-11-17): income can skip approval; a spend can carry the Treasurer's own limit.
                    const approval = f.direction === "INCOME"
                        ? { skips_approval: f.skips_approval }
                        : { treasurer_limit: limit, requires_member: f.requires_member };
                    const fixed = f.direction === "INCOME"
                        ? { fixed_amount: amount, due_period: amount ? f.due_period : null, allow_part_payment: amount ? f.allow_part_payment : false }
                        : {};
                    const targets = {
                        ...approval,
                        is_pranami: f.is_pranami, allow_upi: f.allow_upi, collection_scope_pk: f.collection_scope_pk || null,
                        collection_fund_pk: f.collection_fund_pk || null, collection_account_pk: f.collection_account_pk || null,
                    };
                    if (edit && f.kind === "copy") {
                        // a Sakha's copy of a Kendra head: name, amount and schedule follow the Kendra; only the receiving account is the Sakha's
                        await this._finSend("PATCH", `/heads/${f.pk}`, { collection_account_pk: f.collection_account_pk || null });
                    } else if (edit) {
                        if (f.kind === "source") for (const k of ["allow_upi", "collection_scope_pk", "collection_fund_pk", "collection_account_pk"]) delete targets[k];
                        await this._finSend("PATCH", `/heads/${f.pk}`, {
                            head_name: f.head_name.trim(), description: blank(f.description),
                            ...(f.is_restricted ? { restriction_purpose: f.restriction_purpose.trim() } : {}), ...targets, ...fixed,
                        });
                    } else {
                        await this._finSend("POST", "/heads", {
                            organization_pk: f.template ? null : f.organization.selected.organization_pk,
                            head_code: f.head_code.trim().toUpperCase(), head_name: f.head_name.trim(), description: blank(f.description),
                            direction: f.direction, is_restricted: f.is_restricted, restriction_purpose: f.is_restricted ? f.restriction_purpose.trim() : null,
                            required_fund_type: f.required_fund_type || null, ...targets,
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

            // ── Contributions: the simple way to add a head ───────────────────────
            finContribForm: newContribForm(), finContribAccounts: [], finContribScopes: [], finContribFunds: [],
            finContribOpenCreate() {
                this.finContribForm = { ...newContribForm(), show: true };
                this.finContribAccounts = []; this.finContribScopes = []; this.finContribFunds = [];
                if (this.finSetupOrg.selected) {
                    this.finContribForm.organization = { ...emptyPicker(), selected: this.finSetupOrg.selected, query: this.finSetupOrg.selected.organization_name };
                    return this.finContribOrgChanged();
                }
            },
            finContribCancel() { this.finContribForm = { ...this.finContribForm, show: false }; },

            // Simple Heads & Accounts page (owner 2026-11-18): create a head, list the heads, open or close a head's payment portal.
            // Receiving accounts and the Treasurer's limit stay one click away under "More".
            finSetupMore: false,
            // The "go-live" checklist under "More": is the gateway enabled here, the webhook address to register with the provider, are the keys
            // in place, is the payment window long enough. Names and URLs only - no secret ever reaches the browser.
            finGateway: null, finGatewayError: "", finWebhookCopied: false,
            finToggleMore() {
                this.finSetupMore = !this.finSetupMore;
                if (this.finSetupMore) return this.finGatewayLoad();
            },
            async finGatewayLoad() {
                this.finGatewayError = "";
                try { this.finGateway = await this._finGet("/gateway/readiness"); }
                catch (err) { this.finGateway = null; this.finGatewayError = err.message || "Could not load the payment gateway checklist."; }
            },
            // The checklist counts accounts, so it is re-read whenever accounts change (and with the live refresh), not only when "More" is opened.
            finGatewayRefresh() { return this.finSetupMore ? this.finGatewayLoad() : Promise.resolve(); },
            finGatewayProvider(name) { return this.finGateway ? (this.finGateway.providers.find((p) => p.provider === name) || null) : null; },
            async finCopyWebhook(url) {
                try { await navigator.clipboard.writeText(url); this.finWebhookCopied = true; setTimeout(() => { this.finWebhookCopied = false; }, 2000); }
                catch { this.finWebhookCopied = false; }
            },
            // Is the head's payment portal open? Income heads only: members see it in the Pranami tab and can pay it. A head for every
            // Sakha is open once its copies exist; a copy is open while it collects into an account.
            finHeadPortalOpen(h) {
                if (h.direction !== "INCOME") return null;
                if (h.applies_to_all_sakhas) return !!h.is_pranami;
                return !!(h.is_pranami && h.allow_upi);
            },
            // Opening a portal asks what members are to pay first (amount, how often, part payments); closing needs nothing.
            finPortalForm: { show: false, saving: false, error: "", pk: "", name: "", description: "", follows_kendra: false, fixed_amount: "", due_period: "YEARLY",
                             due_date: "", due_touched: false, allow_part_payment: false },
            // A sensible due date for the chosen frequency: the end of the financial year (31 March), the end of this month, or none for a one-time
            // Pranami (the admin picks it). Offered, never forced: once the admin edits the date it is left alone.
            _finDefaultDueDate(period) {
                const pad = (n) => String(n).padStart(2, "0"), t = new Date();
                if (period === "YEARLY") return `${t.getMonth() >= 3 ? t.getFullYear() + 1 : t.getFullYear()}-03-31`;
                if (period === "MONTHLY") { const d = new Date(t.getFullYear(), t.getMonth() + 1, 0); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
                return "";
            },
            // The frequency only exists with a fixed amount; a free-amount head still has a due date (end of the financial year unless chosen).
            finPortalPeriodChanged() {
                const f = this.finPortalForm;
                if (!f.due_touched) f.due_date = this._finDefaultDueDate(blank(f.fixed_amount) ? "YEARLY" : f.due_period) || f.due_date;
            },
            finHeadPortalOpenForm(h) {
                const period = h.due_period || "YEARLY";
                this.finPortalForm = {
                    show: true, saving: false, error: "", pk: h.finance_head_pk, name: h.head_name, description: h.description || "", follows_kendra: !!h.is_kendra_copy,
                    fixed_amount: h.fixed_amount == null ? "" : String(h.fixed_amount), due_period: period, allow_part_payment: !!h.allow_part_payment,
                    due_date: h.due_date || this._finDefaultDueDate(h.fixed_amount == null ? "YEARLY" : period), due_touched: !!h.due_date,
                };
            },
            // What the member's card will read, for the preview beside the form.
            finPortalPreview() {
                const f = this.finPortalForm, amount = blank(f.fixed_amount);
                const per = { YEARLY: "per financial year", MONTHLY: "per month", ONE_TIME: "one time" }[f.due_period] || "";
                return { amount: amount ? NSS.formatMoney(amount) + (per ? " " + per : "") : "Any amount", due: f.due_date ? NSS.formatDate(f.due_date) : "" };
            },
            finPortalCancel() { this.finPortalForm = { ...this.finPortalForm, show: false }; },
            async finPortalSubmit() {
                const f = this.finPortalForm;
                const amount = blank(f.fixed_amount);
                if (!f.follows_kendra && amount && (!MONEY_RE.test(amount) || Number(amount) <= 0)) { f.error = "Enter a positive amount with at most two decimals, or leave it empty to let members pay any amount."; return; }
                if (!f.follows_kendra && !f.due_date) { f.error = "Choose the date this Pranami is due by."; return; }
                f.saving = true; f.error = "";
                try {
                    const body = f.follows_kendra ? { open: true }
                        : { open: true, fixed_amount: amount, due_period: amount ? f.due_period : null, due_date: f.due_date,
                            allow_part_payment: amount ? f.allow_part_payment : false };
                    await this._finSend("POST", `/heads/${f.pk}/portal`, body);
                    this.finPortalForm = { ...f, show: false, saving: false };
                    this._finNote(`Payment portal opened: members can now pay "${f.name}" from their Pranami tab` + (amount && !f.follows_kendra ? ` (${NSS.formatMoney(amount)}).` : "."));
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    f.error = err.message || "Could not open the payment portal.";
                    f.saving = false;
                }
            },
            // List helpers of the simple Heads page: the portal filter (browser side), the counts, the "Sangha" column only when several show.
            finHeadPortalFilter: "",
            finHeadsShown() {
                const f = this.finHeadPortalFilter;
                if (!f) return this.finHeads;
                return this.finHeads.filter((h) => this.finHeadPortalOpen(h) === (f === "OPEN"));
            },
            finHeadsPortalCount(open) { return this.finHeads.filter((h) => this.finHeadPortalOpen(h) === open && h.status === "ACTIVE").length; },
            finHeadsMultiOrg() { return new Set(this.finHeads.map((h) => h.organization_pk)).size > 1; },
            // "₹110.00 yearly" / "Any amount" for an income head with no fixed amount / "—" for money out.
            finHeadAmountLabel(h) {
                const per = this.finHeadAmountPer(h);
                return this.finHeadAmountMain(h) + (per ? " · " + per : "");
            },
            // The same label in two parts for the list (the figure on one line, "per financial year" under it)
            finHeadAmountMain(h) {
                if (h.direction !== "INCOME") return "—";
                return h.fixed_amount == null ? "Any amount" : NSS.formatMoney(h.fixed_amount);
            },
            finHeadAmountPer(h) {
                if (h.direction !== "INCOME" || h.fixed_amount == null) return "";
                return { YEARLY: "per financial year", MONTHLY: "per month", ONE_TIME: "one time" }[h.due_period] || "";
            },
            async finHeadPortal(h, open) {
                this.finHeadsError = "";
                try {
                    await this._finSend("POST", `/heads/${h.finance_head_pk}/portal`, { open });
                    this._finNote(open ? `Payment portal opened: members can now pay "${h.head_name}" from their Pranami tab.`
                                       : `Payment portal closed for "${h.head_name}"; members no longer see it.`);
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    this.finHeadsError = err.message || "Could not change the payment portal.";
                }
            },
            get finContribIsKendra() { const o = this.finContribForm.organization.selected; return !!o && o.type_code === "KENDRA"; },
            // The receiving account is chosen from the Sangha's own ACTIVE accounts; blank = its default account.
            async finContribOrgChanged() {
                const f = this.finContribForm;
                const org = f.organization.selected ? f.organization.selected.organization_pk : "";
                f.collection_account_pk = ""; f.collection_scope_pk = ""; f.collection_fund_pk = "";
                this.finContribAccounts = []; this.finContribScopes = []; this.finContribFunds = [];
                if (!this.finContribIsKendra) f.applies_to = "ORGANIZATION";
                if (!org) return;
                try {
                    const [accounts, scopes] = await Promise.all([
                        this._finGet("/accounts", { organization_pk: org, status: "ACTIVE", page_size: 100 }),
                        this._finGet("/scopes", { organization_pk: org, status: "ACTIVE", page_size: 100 }),
                    ]);
                    this.finContribAccounts = accounts.items; this.finContribScopes = scopes.items;
                } catch { /* the lists stay empty; the server uses the default account and the general scope */ }
            },
            // The funds offered are those of the chosen scope; none chosen = the Sangha's general scope is used and no fund.
            async finContribScopeChanged() {
                const f = this.finContribForm;
                f.collection_fund_pk = ""; this.finContribFunds = [];
                if (!f.collection_scope_pk) return;
                try {
                    this.finContribFunds = (await this._finGet("/funds", { financial_scope_pk: f.collection_scope_pk, status: "ACTIVE", page_size: 100 })).items;
                } catch { /* ignore */ }
            },
            async finContribSubmit() {
                const f = this.finContribForm;
                if (!f.organization.selected) { f.error = "Choose the Sangha that collects this Pranami."; return; }
                if (!blank(f.head_name)) { f.error = "The finance head needs a name."; return; }
                const amount = f.direction === "EXPENSE" ? null : blank(f.fixed_amount);
                if (amount && (!MONEY_RE.test(amount) || Number(amount) <= 0)) { f.error = "Enter a positive amount with at most two decimals, or leave it empty for any amount."; return; }
                if (amount && !f.due_period) { f.error = "Choose how often the amount is due."; return; }
                f.saving = true; f.error = "";
                try {
                    if (f.direction === "EXPENSE") {            // money the Sangha spends: a plain head (no amount, no portal)
                        await this._finSend("POST", "/heads", {
                            organization_pk: f.organization.selected.organization_pk, head_code: `HEAD_${Date.now().toString(36).toUpperCase()}`,
                            head_name: f.head_name.trim(), description: blank(f.description), direction: "EXPENSE",
                            collection_scope_pk: f.collection_scope_pk || null, collection_fund_pk: f.collection_fund_pk || null,
                        });
                        this.finContribForm = newContribForm();
                        this._finNote("Finance head created.");
                        await this.finHeadsLoad({ silent: true });
                        return;
                    }
                    const allSakhas = f.applies_to === "ALL_SAKHAS";
                    const r = await this._finSend("POST", "/contributions", {
                        organization_pk: f.organization.selected.organization_pk, applies_to: f.applies_to, head_name: f.head_name.trim(),
                        description: blank(f.description), fixed_amount: amount, due_period: amount ? f.due_period : null,
                        allow_part_payment: amount ? f.allow_part_payment : false,
                        collection_account_pk: null, open_portal: false,
                        collection_scope_pk: allSakhas ? null : (f.collection_scope_pk || null), collection_fund_pk: allSakhas ? null : (f.collection_fund_pk || null),
                    });
                    this.finContribForm = newContribForm();
                    this._finNote("Finance head created. Open its payment portal from the list when members should pay it.");
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    f.error = err.message || "Could not add the Pranami.";
                } finally {
                    f.saving = false;
                }
            },

            // The Kendra brings every Sakha's copy up to date (new Sakhas get one).
            async finHeadSyncCopies(h) {
                this.finHeadsError = "";
                try {
                    const r = await this._finSend("POST", `/heads/${h.finance_head_pk}/sync-copies`, {});
                    this._finNote(`Sakhas updated: ${r.created} new copy(ies), ${r.updated} refreshed.`);
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    this.finHeadsError = err.message || "Could not update the Sakhas.";
                }
            },

            // A Sakha's copy of a Kendra contribution: the Sakha chooses which of its own accounts collects.
            finCopyForm: newCopyForm(), finCopyAccounts: [],
            async finCopyOpen(h) {
                this.finCopyForm = { ...newCopyForm(), show: true, pk: h.finance_head_pk, name: h.head_name, organization_pk: h.organization_pk,
                                     collection_account_pk: h.collection_account_pk || "" };
                this.finCopyAccounts = [];
                try {
                    this.finCopyAccounts = (await this._finGet("/accounts", { organization_pk: h.organization_pk, status: "ACTIVE", page_size: 100 })).items;
                } catch { /* the server explains on save */ }
            },
            finCopyCancel() { this.finCopyForm = { ...this.finCopyForm, show: false }; },
            async finCopySubmit() {
                const f = this.finCopyForm;
                f.saving = true; f.error = "";
                try {
                    await this._finSend("PATCH", `/heads/${f.pk}`, { collection_account_pk: f.collection_account_pk || null });
                    this.finCopyForm = newCopyForm();
                    this._finNote("Receiving account saved.");
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    f.error = err.message || "Could not save the receiving account.";
                } finally {
                    f.saving = false;
                }
            },

            // ── Events (e.g. Rasa): configured by the concerned Sangha ─────────────
            finEventForm: newEventForm(), finEventAccounts: [],
            finEventOpenCreate() {
                this.finEventForm = { ...newEventForm(), show: true };
                this.finEventAccounts = [];
                if (this.finSetupOrg.selected) {
                    this.finEventForm.organization = { ...emptyPicker(), selected: this.finSetupOrg.selected, query: this.finSetupOrg.selected.organization_name };
                    return this.finEventOrgChanged();
                }
            },
            finEventCancel() { this.finEventForm = { ...this.finEventForm, show: false }; },
            // The receiving account is chosen from the Sangha's own ACTIVE accounts.
            async finEventOrgChanged() {
                const f = this.finEventForm;
                const org = f.organization.selected ? f.organization.selected.organization_pk : "";
                f.collection_account_pk = ""; this.finEventAccounts = [];
                if (!org) return;
                try {
                    this.finEventAccounts = (await this._finGet("/accounts", { organization_pk: org, status: "ACTIVE", page_size: 100 })).items;
                    if (this.finEventAccounts.length === 1) f.collection_account_pk = this.finEventAccounts[0].financial_account_pk;
                } catch { /* the list stays empty; the server explains on save */ }
            },
            async finEventSubmit() {
                const f = this.finEventForm;
                if (!f.organization.selected) { f.error = "Choose the Sangha running the event."; return; }
                if (!blank(f.event_name)) { f.error = "The event needs a name."; return; }
                if (!f.collection_account_pk) { f.error = "Choose the Sangha's receiving account (it needs a payment gateway)."; return; }
                f.saving = true; f.error = "";
                try {
                    await this._finSend("POST", "/events", {
                        organization_pk: f.organization.selected.organization_pk, event_name: f.event_name.trim(),
                        description: blank(f.description), collection_account_pk: f.collection_account_pk,
                    });
                    this.finEventForm = newEventForm();
                    this._finNote("Event created. Members of this Sangha (or all members, for the Kendra) can now pay towards it by UPI; switch its head off to stop collecting.");
                    this.finHeadView = "events";
                    await this.finHeadsLoad({ silent: true });
                } catch (err) {
                    f.error = err.message || "Could not create the event.";
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
                if (h.fixed_amount != null) {
                    const per = { YEARLY: "yearly", MONTHLY: "monthly", ONE_TIME: "one time" }[h.due_period] || "";
                    bits.push(NSS.formatMoney(h.fixed_amount) + (per ? " " + per : ""));
                    if (h.allow_part_payment) bits.push("Part payment");
                }
                if (h.skips_approval) bits.push("No approval needed");
                if (h.treasurer_limit != null) bits.push("Treasurer up to " + NSS.formatMoney(h.treasurer_limit));
                if (h.requires_member) bits.push("Names the member");
                if (h.applies_to_all_sakhas) bits.push(`All Sakhas (${h.copy_count})`);
                if (h.is_kendra_copy) bits.push(h.needs_account ? "Needs an account" : "From the Kendra");
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
                    organization: pickerWith(a.organization_pk, a.organization_name),
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
                    await Promise.all([this.finAcctsLoad({ silent: true }), this.finGatewayRefresh()]);
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
            // https only - plus this computer's own address (http://127.0.0.1 / localhost), where the local Razorpay rehearsal serves its pay page.
            finReqSafeUrl(url) { return typeof url === "string" && /^(https:\/\/|http:\/\/(127\.0\.0\.1|localhost)(:\d+)?\/)/i.test(url) ? url : ""; },
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

            // Payer picker: matches appear while typing (name, Sangha Sevi ID, mobile ...), from the member directory every signed-in admin may read.
            // Who may actually be asked is still decided by the server (the member must be inside the admin's scope).
            // The MEMBER PICKER, shared by the payer of a payment request (finReqForm) and the member of a finance entry (finTxnForm, finance.js):
            // `form` is the form object holding `member` (the typed box and its matches) and `sangha_sevi_id` (what is sent once a match is chosen).
            // Typing clears the choice; at least 2 characters are searched in the NSS-wide member directory, 300 ms after the last key.
            _finMemberTimer: null,
            finMemberInput(form) {
                clearTimeout(this._finMemberTimer);
                form.sangha_sevi_id = ""; form.member.selected = null;
                const q = form.member.query.trim();
                if (q.length < 2) { form.member.results = []; return; }
                this._finMemberTimer = setTimeout(() => this.finMemberSearch(form), 300);
            },
            async finMemberSearch(form) {
                const m = form.member;
                const q = m.query.trim();
                m.searching = true;
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/membership/directory?${new URLSearchParams({ q, limit: "8" })}`);
                    const data = res.ok ? await res.json() : { members: [] };
                    if (m.query.trim() === q && !m.selected) m.results = data.members || [];
                } catch { m.results = []; } finally { m.searching = false; }
            },
            finMemberName(x) { return [x.first_name, x.middle_name, x.last_name].filter(Boolean).join(" "); },
            finMemberPick(form, x) {
                form.sangha_sevi_id = x.sangha_sevi_id;
                if ("payer_name" in form) form.payer_name = "";                      // a payment request names EITHER a member or a typed payer
                form.member = { query: `${this.finMemberName(x)} (${x.sangha_sevi_id})`, results: [], searching: false, selected: x };
            },
            finMemberClear(form) { form.sangha_sevi_id = ""; form.member = { query: "", results: [], searching: false, selected: null }; },
            // The head chosen in the form (for the summary), and a fixed amount pre-fills the box once.
            finReqHeadSel() { return this.finReqHeads.find((x) => x.finance_head_pk === this.finReqForm.finance_head_pk) || null; },
            finReqHeadChanged() {
                const hd = this.finReqHeadSel();
                if (hd && hd.fixed_amount != null && !String(this.finReqForm.amount || "").trim()) this.finReqForm.amount = String(hd.fixed_amount);
            },
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
