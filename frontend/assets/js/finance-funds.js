/**
 * Finance "Funds" tab (Tier 12, owner request 2026-11-20) - every fund the admin may see, across all financial scopes, in one place:
 * search and filter, create a fund in any open scope, rename / re-purpose it, and run its lifecycle (Draft -> Active -> Inactive).
 *
 * A third Finance mixin, mixed into `adminPanel()` (admin.js) beside finance.js and finance-setup.js. It owns only the LIST and its
 * filters. Creating, editing and the lifecycle buttons are the SAME code the "Funds in this scope" card on Years & Scopes uses
 * (finance.js: finFundForm / finSubmitFund / finFundEdit / finSaveFundEdit, finActions + finAskTransition) - not a second copy.
 *
 * Authorization is the server's (api/routers/finance.py: GET/POST/PATCH /funds, POST /funds/{pk}/transition): FINANCE_VIEW / MANAGE plus
 * admin scope on the fund's scope organization. The buttons are only hidden here (canManageFinance), and the lifecycle buttons come from
 * the server's own table (finActions).
 */
(function () {
    "use strict";

    const PAGE_SIZE = 25;
    const emptyPicker = () => ({ query: "", results: [], searching: false, selected: null });
    const newFilters = () => ({ q: "", scope: "", type: "", status: "", restricted: "" });

    function financeFundsMixin() {
        return {
            finFundsAll: [], finFundsAllTotal: 0, finFundsAllLoading: false, finFundsAllError: "",
            finFundsFilter: newFilters(), finFundsPage: 1,
            finFundScopes: [],                 // the scopes of the chosen Sangha (or every scope the admin can see): the filter + a new fund's scope
            // The Sangha whose funds are shown. A Sakha admin's admin scope names exactly one (finSetupScopeOrg, finance-setup.js): it is selected and
            // locked, so the admin never picks (or can pick) another; wider admins may search one Sangha or leave it empty for all in their scope.
            finFundsOrg: emptyPicker(),
            get finFundsOrgPk() { return this.finFundsOrg.selected ? this.finFundsOrg.selected.organization_pk : ""; },
            get finFundsOrgLocked() { return !!this.finSetupScopeOrg; },

            get finFundsPages() { return Math.max(1, Math.ceil(this.finFundsAllTotal / PAGE_SIZE)); },
            get finFundScopesOpen() { return this.finFundScopes.filter((s) => s.status === "DRAFT" || s.status === "ACTIVE"); },
            // Figures for the tiles: the status split and the balance are of the funds on THIS page; the total is the server's count.
            get finFundsActiveCount() { return this.finFundsAll.filter((f) => f.status === "ACTIVE").length; },
            get finFundsRestrictedCount() { return this.finFundsAll.filter((f) => f.is_restricted).length; },
            get finFundsBalance() { return this.finFundsAll.reduce((n, f) => n + Number(f.balance || 0), 0); },
            get finFundsPartial() { return this.finFundsAllTotal > this.finFundsAll.length; },
            get finFundsFiltered() {
                const f = this.finFundsFilter;
                return !!(f.q.trim() || f.scope || f.type || f.status || f.restricted);
            },
            // The scope a new fund defaults to: the one being filtered on; else the Sangha's general scope (an ACTIVE ORGANIZATION one); else the only open scope.
            get finFundsDefaultScope() {
                if (this.finFundsFilter.scope) return this.finFundsFilter.scope;
                const open = this.finFundScopesOpen;
                const general = open.find((s) => s.status === "ACTIVE" && s.scope_type === "ORGANIZATION");
                return general ? general.financial_scope_pk : (open.length === 1 ? open[0].financial_scope_pk : "");
            },

            async finFundsEnter() {
                this.finFundsFilter = newFilters(); this.finFundsPage = 1;
                this.finFundForm = { ...this.finFundForm, show: false };
                const own = this.finSetupScopeOrg;
                if (own && this.finFundsOrgPk !== own.organization_pk) this.corrSelectOrg(this.finFundsOrg, own);
                await Promise.all([this.finFundsLoadScopes(), this.finFundsLoadAll()]);
            },
            async finFundsLoadScopes() {
                const params = { page_size: 100 };
                if (this.finFundsOrgPk) params.organization_pk = this.finFundsOrgPk;
                try { this.finFundScopes = (await this._finGet("/scopes", params)).items; }
                catch { /* the filter and the form list stay empty; the server explains on save */ }
            },
            // The Sangha was picked or cleared: its scopes replace the list, the scope filter resets, the funds are re-read.
            async finFundsOrgChanged() {
                this.finFundsFilter.scope = ""; this.finFundsPage = 1;
                await Promise.all([this.finFundsLoadScopes(), this.finFundsLoadAll()]);
            },
            finFundsClearOrg() { this.corrClearPicker(this.finFundsOrg); return this.finFundsOrgChanged(); },
            async finFundsLoadAll(opts = {}) {
                if (!opts.silent) { this.finFundsAllLoading = true; this.finFundsAllError = ""; }
                const f = this.finFundsFilter;
                const params = { page: this.finFundsPage, page_size: PAGE_SIZE };
                if (f.q.trim()) params.q = f.q.trim();
                if (this.finFundsOrgPk) params.organization_pk = this.finFundsOrgPk;
                if (f.scope) params.financial_scope_pk = f.scope;
                if (f.type) params.fund_type = f.type;
                if (f.status) params.status = f.status;
                if (f.restricted !== "") params.is_restricted = f.restricted === "yes";
                try {
                    const res = await this._finGet("/funds", params);
                    this.finFundsAll = res.items; this.finFundsAllTotal = res.total;
                } catch (err) {
                    if (!opts.silent) this.finFundsAllError = err.message || "Failed to load funds.";
                } finally {
                    this.finFundsAllLoading = false;
                }
            },
            finFundsApply() { this.finFundsPage = 1; return this.finFundsLoadAll(); },
            finFundsClear() { this.finFundsFilter = newFilters(); return this.finFundsApply(); },
            finFundsGo(page) { this.finFundsPage = Math.min(Math.max(1, page), this.finFundsPages); return this.finFundsLoadAll(); },
            // After a create / edit / lifecycle change, and for the live feed.
            finFundsReload() { return this.finFundsLoadAll({ silent: true }); },

            // "+ New fund": the shared fund form, with the scope chosen here (a fund belongs to exactly one scope)
            finFundsOpenNew() {
                this.finFundForm = { ...this.finFundForm, show: true, financial_scope_pk: this.finFundsDefaultScope, error: "", organization: this._finOwnOrgPicker({ typeCodes: NSS.SAKHA_LIKE_ORG_TYPES }) };
            },
        };
    }

    window.NSSFinanceFunds = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(financeFundsMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
