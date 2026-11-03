/**
 * Assets & Property admin screens (Module #22, Tier 6) — mixed into
 * `adminPanel()` (admin.js), which owns the sidebar, the tab state and the
 * /admin entry guard.
 *
 * ONE implementation serves both tabs. 'Properties' (immovable) and 'Assets'
 * (movable) share every screen — list, create/edit form, detail, custody,
 * maintenance, documents — because the API is one set of handlers keyed by
 * {kind} (`properties` | `assets`, api/routers/assets_property.py). The active
 * kind is derived from the active tab (`apKind`), so the state below is a
 * single set that is reset when the tab changes; the only property-only
 * sections (holding arrangement, statutory records) switch on `apIsProperty`.
 * The markup in admin.html is likewise written once.
 *
 * Authorization is the server's: ASSET_VIEW/ASSET_MANAGE plus admin scope on
 * the record's EFFECTIVE custodian organization (the active one, or - for a
 * Disposed / Retired record, whose custody the terminal event ended - the last
 * one; the API flags it `custodian_is_last`). This file only HIDES controls
 * the API would refuse (canManageAssets, lifecycle table, NSS-wide-only
 * custodian assignment) and shows the server's message verbatim
 * (NSS.errorMessage) for everything else. The lifecycle tables, status labels
 * and badge classes live in nss-config.js (NSS.ASSET_PROPERTY_*).
 *
 * Custodian pickers (new record, assign, transfer, list filter) only offer
 * PHYSICAL organizations (NSS.ASSET_CUSTODIAN_ORG_TYPES, owner rule 2026-11-02,
 * GDR-010 §2C), via the typeCodes of the shared corr* picker; the list's
 * "Include sub-organizations" box sends include_sub_organizations.
 *
 * Organization pickers reuse the generic corr* type-ahead helpers of admin.js
 * (they call the scoped /organization/organizations/in-scope endpoint).
 * Every loader captures what it was asked for and discards its response when
 * the user has since moved on (stale-response guard).
 */
(function () {
    "use strict";

    const BASE = "/api/v1/assets-property";
    const MASTER = "/api/v1/foundation/master-data?category_code=";

    // Master-data categories this screen needs (value_code -> value_name).
    const CATEGORIES = [
        "PROPERTY_TYPE", "ASSET_TYPE", "CUSTODIANSHIP_END_REASON",
        "STATUTORY_OBLIGATION_TYPE", "MAINTENANCE_TYPE", "ASSET_PROPERTY_DOCUMENT_RELATIONSHIP",
        "ACQUISITION_METHOD",
    ];

    const JSON_HEADERS = { "Content-Type": "application/json" };
    const emptyPicker = () => ({ query: "", results: [], searching: false, selected: null });
    // Custodian pickers only offer PHYSICAL organizations (GDR-010 §2C): the
    // shared corr* type-ahead (admin.js corrSearchOrg) forwards `typeCodes` as
    // repeated ?type_code= to /organization/organizations/in-scope.
    const custodianPicker = () => ({ ...emptyPicker(), typeCodes: NSS.ASSET_CUSTODIAN_ORG_TYPES });
    // 'Belongs to' pickers (GDR-010 item 4) take ANY organization type, so they are a
    // plain emptyPicker() with NO typeCodes. They still go through the scoped
    // /organization/organizations/in-scope endpoint (corrSearchOrg): a scoped
    // admin can only pick organizations inside their own admin scope, an NSS-wide
    // admin can pick any. The server itself accepts any active organization.
    const BELONGS_TO_HINT = "Use this when an asset belongs to one organization (for example the Mahila Sangha) but is held under the supervision of a physical organization (for example the Kendra Sangha).";
    const CUSTODIAN_HINT = "Property and assets are held by physical organizations: Sakha, Patha Chakra, Kendra, Nilachala Kutira, Smruti Mandira.";
    const blank = (v) => {
        const t = (v == null ? "" : String(v)).trim();
        return t === "" ? null : t;
    };

    // Fresh state objects. Module-level so the initial state, the resets and
    // the forms' open/cancel paths all build them in exactly one place.
    const newSub = () => ({ items: [], loading: false, error: "" });
    const newSubs = () => ({ custody: newSub(), maintenance: newSub(), statutory: newSub(), documents: newSub() });
    const newForm = () => ({
        show: false, mode: "create", saving: false, error: "",
        name: "", type_code: "", location_description: "", extra: "", notes: "", acquired_at: "",
        acquisition_method_code: "",
        custodian: custodianPicker(), custodian_effective_from: "",
        belongsTo: emptyPicker(),
    });
    const newTransition = () => ({ show: false, saving: false, error: "", target: "", remarks: "" });
    const newTransfer = () => ({
        show: false, saving: false, error: "", newCustodian: custodianPicker(),
        end_reason_code: "TRANSFER", effective_from: "", notes: "", location_description: "",
    });
    const newAssign = () => ({ show: false, saving: false, error: "", custodian: custodianPicker(), effective_from: "", notes: "" });
    const newMaint = () => ({ show: false, saving: false, error: "", editPk: "", type_code: "", description: "", performed_at: "", notes: "" });
    const newStat = () => ({ show: false, saving: false, error: "", editPk: "", type_code: "", description: "", reference_number: "", notes: "" });
    const newDoc = () => ({ show: false, saving: false, error: "", document_master_pk: "", relationship_type_code: "", notes: "" });

    function assetsPropertyMixin() {
        return {
            // ── Permissions (read the live /auth/me payload) ───────────
            _apPerms() {
                return (this.currentUser || NSSAuth.getCachedUser() || {}).permissions || [];
            },
            get canViewAssets() {
                const p = this._apPerms();
                return p.includes("ASSET_VIEW") || p.includes("ASSET_MANAGE");
            },
            // Auditor / Report Viewer hold ASSET_VIEW only: every create / edit /
            // transition / transfer / archive / delete control is gated on this.
            get canManageAssets() {
                return this._apPerms().includes("ASSET_MANAGE");
            },

            // ── Kind (derived from the active tab) ─────────────────────
            get apKind() { return this.activeTab === "assets" ? "assets" : "properties"; },
            get apIsProperty() { return this.apKind === "properties"; },
            get apNoun() { return this.apIsProperty ? "property" : "asset"; },
            get apNounTitle() { return this.apIsProperty ? "Property" : "Asset"; },
            get apPluralTitle() { return this.apIsProperty ? "Properties" : "Assets"; },
            // API field names that differ between the two kinds.
            get apF() {
                return this.apIsProperty
                    ? { id: "property_id", pk: "property_pk", name: "property_name", type: "property_type_code",
                        typeName: "property_type_name", extra: "holding_arrangement", extraLabel: "Holding arrangement",
                        extraHint: "The recorded or legal holder, as free text. This is not the custodian." }
                    : { id: "asset_id", pk: "asset_pk", name: "asset_name", type: "asset_type_code",
                        typeName: "asset_type_name", extra: "condition", extraLabel: "Condition",
                        extraHint: "Free text. No condition grading is defined." };
            },
            get apTypeOptions() {
                return this.apCatalogs[this.apIsProperty ? "PROPERTY_TYPE" : "ASSET_TYPE"] || [];
            },
            get apStatusOptions() {
                return Object.keys(NSS.ASSET_PROPERTY_LIFECYCLE[this.apKind].transitions);
            },

            // ── State ─────────────────────────────────────────────────
            apCatalogs: {},          // category_code -> [{value_code, value_name}]
            apCatalogsLoaded: false,
            apNotice: "",            // success note shown above the list/detail

            apItems: [], apTotal: 0, apPage: 1, apPageSize: 20,
            apQ: "", apTypeFilter: "", apStatusFilter: "", apAcquisitionFilter: "", apCustodianFilter: custodianPicker(),
            apBelongsFilter: emptyPicker(),   // 'Belongs to' list filter (any organization type)
            apBelongsToHint: BELONGS_TO_HINT,
            apIncludeSub: false,     // "Include sub-organizations" (only sent with a custodian filter)
            apCustodianHint: CUSTODIAN_HINT,
            apLoading: false, apError: "",
            _apListSeq: 0, _apDetailSeq: 0,

            apSelected: null, apDetailLoading: false, apDetailError: "",
            apSub: newSubs(),        // { custody, maintenance, statutory, documents } each {items, loading, error}

            apForm: newForm(),       // create / edit form
            apTransition: newTransition(),  // lifecycle transition dialog
            apTransfer: newTransfer(),      // transfer-custody dialog
            apAssign: newAssign(),          // assign-first-custodian form
            apMaintForm: newMaint(),
            apStatForm: newStat(),
            apDocForm: newDoc(),
            apDocOptions: [], apDocOptionsError: "", apDocOptionsLoaded: false,

            get apSelectedPk() { return this.apSelected ? this.apSelected[this.apF.pk] : null; },
            get apTotalPages() { return Math.max(1, Math.ceil(this.apTotal / this.apPageSize)); },

            // Valid next states for the open record (SOL-AP-003). REGISTERED ->
            // first state needs a custodian; the server refuses it otherwise, so
            // the button is simply not offered until one exists.
            get apNextStatuses() {
                if (!this.apSelected) return [];
                const from = this.apSelected.status;
                const next = NSS.ASSET_PROPERTY_LIFECYCLE[this.apKind].transitions[from] || [];
                return next.filter((to) => !(from === "REGISTERED" && !this.apSelected.current_custodianship_pk));
            },
            get apCanArchive() {
                return !!this.apSelected && NSS.ASSET_PROPERTY_ARCHIVABLE_STATUSES.includes(this.apSelected.status);
            },
            get apIsTerminal() {
                return !!this.apSelected && this.apSelected.status === NSS.ASSET_PROPERTY_LIFECYCLE[this.apKind].terminal;
            },
            get apCanAssignCustodian() {
                return !!this.apSelected && this.canManageAssets && this.isGovNssWideAdmin
                    && !this.apSelected.current_custodianship_pk && !this.apIsTerminal;
            },
            get apCanTransferCustody() {
                return !!this.apSelected && this.canManageAssets
                    && !!this.apSelected.current_custodianship_pk && !this.apIsTerminal;
            },

            // ── Catalogs ──────────────────────────────────────────────
            apOptions(category) { return this.apCatalogs[category] || []; },

            async apLoadCatalogs() {
                if (this.apCatalogsLoaded) return;
                try {
                    const results = await Promise.all(
                        CATEGORIES.map((c) => NSSAuth.apiFetch(MASTER + c).then((r) => (r.ok ? r.json() : []))),
                    );
                    const cats = {};
                    CATEGORIES.forEach((c, i) => { cats[c] = results[i]; });
                    this.apCatalogs = cats;
                    this.apCatalogsLoaded = true;
                } catch { /* non-fatal — dropdowns stay empty, a retry happens on the next open */ }
            },

            // ── Tab entry / reset ─────────────────────────────────────
            // Called by the sidebar items, by init()'s #properties / #assets
            // deep-link loader and by the limited-admin landing branch.
            apEnterTab(kind) {
                if (kind) this.activeTab = kind;
                this.apResetAll();
                this.apLoadCatalogs();
                return this.apLoadList();
            },

            apResetAll() {
                this._apListSeq++;
                this._apDetailSeq++;
                this.apQ = ""; this.apTypeFilter = ""; this.apStatusFilter = ""; this.apAcquisitionFilter = "";
                this.apCustodianFilter = custodianPicker(); this.apIncludeSub = false;
                this.apBelongsFilter = emptyPicker();
                this.apPage = 1; this.apItems = []; this.apTotal = 0; this.apError = ""; this.apNotice = "";
                this.apSelected = null; this.apDetailError = ""; this.apDetailLoading = false;
                this._apResetRecordState();
                this.apForm = newForm();
            },

            // Everything that hangs off the OPEN record — cleared whenever the
            // selection changes so a form can never be submitted against the
            // wrong record.
            _apResetRecordState() {
                this.apSub = newSubs();
                this.apTransition = newTransition();
                this.apTransfer = newTransfer();
                this.apAssign = newAssign();
                this.apMaintForm = newMaint();
                this.apStatForm = newStat();
                this.apDocForm = newDoc();
            },

            // Stale-response guard: true when the open record / tab is no
            // longer the one a request was made for.
            _apStale(kind, pk) {
                return this.apKind !== kind || (pk != null && this.apSelectedPk !== pk);
            },

            // ── List ──────────────────────────────────────────────────
            async apLoadList() {
                const kind = this.apKind;
                const seq = ++this._apListSeq;
                this.apLoading = true;
                this.apError = "";
                try {
                    const params = new URLSearchParams({ page: this.apPage, page_size: this.apPageSize });
                    if (this.apQ.trim()) params.set("q", this.apQ.trim());
                    if (this.apTypeFilter) params.set("type_code", this.apTypeFilter);
                    if (this.apStatusFilter) params.set("status", this.apStatusFilter);
                    if (this.apAcquisitionFilter) params.set("acquisition_method_code", this.apAcquisitionFilter);
                    if (this.apBelongsFilter.selected) {
                        params.set("belongs_to_organization_pk", this.apBelongsFilter.selected.organization_pk);
                    }
                    if (this.apCustodianFilter.selected) {
                        params.set("custodian_organization_pk", this.apCustodianFilter.selected.organization_pk);
                        if (this.apIncludeSub) params.set("include_sub_organizations", "true");
                    }
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}?${params}`);
                    if (seq !== this._apListSeq) return;
                    if (!res.ok) throw new Error(await NSS.extractError(res));
                    const data = await res.json();
                    if (seq !== this._apListSeq) return;
                    this.apItems = data.items;
                    this.apTotal = data.total;
                } catch (err) {
                    if (seq !== this._apListSeq) return;
                    this.apItems = []; this.apTotal = 0;
                    this.apError = err.message || `Failed to load ${this.apPluralTitle.toLowerCase()}.`;
                } finally {
                    if (seq === this._apListSeq) this.apLoading = false;
                }
            },

            apApplyFilters() {
                this.apPage = 1;
                return this.apLoadList();
            },

            apClearFilters() {
                this.apQ = ""; this.apTypeFilter = ""; this.apStatusFilter = ""; this.apAcquisitionFilter = "";
                this.apCustodianFilter = custodianPicker(); this.apIncludeSub = false;
                this.apBelongsFilter = emptyPicker();
                return this.apApplyFilters();
            },

            // Picking / clearing the custodian filter (shared corr* org type-ahead).
            apPickCustodianFilter(org) {
                this.corrSelectOrg(this.apCustodianFilter, org);
                return this.apApplyFilters();
            },
            apClearCustodianFilter() {
                this.apCustodianFilter = custodianPicker();
                return this.apApplyFilters();
            },

            // Picking / clearing the 'Belongs to' filter (same shared type-ahead, no type restriction).
            apPickBelongsFilter(org) {
                this.corrSelectOrg(this.apBelongsFilter, org);
                return this.apApplyFilters();
            },
            apClearBelongsFilter() {
                this.apBelongsFilter = emptyPicker();
                return this.apApplyFilters();
            },

            apChangePage(delta) {
                this.apPage = Math.min(this.apTotalPages, Math.max(1, this.apPage + delta));
                return this.apLoadList();
            },

            // ── Detail ────────────────────────────────────────────────
            async apOpen(pk) {
                const kind = this.apKind;
                const seq = ++this._apDetailSeq;
                this.apNotice = "";
                this.apSelected = null;
                this.apDetailError = "";
                this.apDetailLoading = true;
                this._apResetRecordState();
                this.apForm = newForm();
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}`);
                    if (seq !== this._apDetailSeq) return;
                    if (!res.ok) throw new Error(await NSS.extractError(res));
                    const rec = await res.json();
                    if (seq !== this._apDetailSeq) return;
                    this.apSelected = rec;
                    this.apLoadCatalogs();
                    this.apLoadCustody();
                    this.apLoadMaintenance();
                    if (kind === "properties") this.apLoadStatutory();
                    this.apLoadDocuments();
                } catch (err) {
                    if (seq !== this._apDetailSeq) return;
                    this.apDetailError = err.message || `Failed to load this ${this.apNoun}.`;
                } finally {
                    if (seq === this._apDetailSeq) this.apDetailLoading = false;
                }
            },

            apBackToList() {
                this._apDetailSeq++;
                this.apSelected = null;
                this.apDetailError = "";
                this.apDetailLoading = false;
                this._apResetRecordState();
                this.apForm = newForm();
                return this.apLoadList();
            },

            // Re-read the open record after a write that does not return it.
            // A custody transfer can move the record out of the caller's scope;
            // the resulting 403 then means "leave the detail", not "error".
            async _apReloadSelected(leftScopeNotice) {
                const kind = this.apKind, pk = this.apSelectedPk;
                const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}`);
                if (this._apStale(kind, pk)) return;
                if (res.status === 403 || res.status === 404) {
                    this.apBackToList();
                    this.apNotice = leftScopeNotice;
                    return;
                }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.apSelected = await res.json();
            },

            // ── Create / edit form ────────────────────────────────────
            apOpenCreate() {
                this.apNotice = "";
                this.apLoadCatalogs();
                this.apForm = { ...newForm(), show: true, mode: "create" };
            },

            apOpenEdit() {
                const r = this.apSelected;
                if (!r) return;
                this.apLoadCatalogs();
                this.apForm = {
                    ...newForm(), show: true, mode: "edit",
                    name: r[this.apF.name] || "", type_code: r[this.apF.type] || "",
                    location_description: r.location_description || "", extra: r[this.apF.extra] || "",
                    notes: r.notes || "", acquired_at: r.acquired_at || "",
                    acquisition_method_code: r.acquisition_method_code || "",
                    belongsTo: r.belongs_to_organization_pk
                        ? { ...emptyPicker(), query: r.belongs_to_organization_name || "",
                            selected: { organization_pk: r.belongs_to_organization_pk, organization_name: r.belongs_to_organization_name } }
                        : emptyPicker(),
                };
            },

            apCancelForm() {
                this.apForm = newForm();
            },

            async apSubmitForm() {
                const f = this.apForm;
                f.error = "";
                if (!f.name.trim()) { f.error = `${this.apNounTitle} name is required.`; return; }
                if (!f.type_code) { f.error = `Select the ${this.apNoun} type.`; return; }
                const F = this.apF;
                const kind = this.apKind;
                f.saving = true;
                try {
                    let res;
                    if (f.mode === "create") {
                        const body = {
                            [F.name]: f.name.trim(), [F.type]: f.type_code,
                            location_description: blank(f.location_description), [F.extra]: blank(f.extra),
                            notes: blank(f.notes), acquired_at: f.acquired_at || null,
                        };
                        if (f.acquisition_method_code) body.acquisition_method_code = f.acquisition_method_code;
                        if (f.belongsTo.selected) body.belongs_to_organization_pk = f.belongsTo.selected.organization_pk;
                        if (f.custodian.selected) {
                            body.custodian_organization_pk = f.custodian.selected.organization_pk;
                            if (f.custodian_effective_from) body.custodian_effective_from = f.custodian_effective_from;
                        }
                        res = await NSSAuth.apiFetch(`${BASE}/${kind}`, {
                            method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body),
                        });
                    } else {
                        // PATCH semantics: send only what changed (an unchanged form is a no-op).
                        const r = this.apSelected;
                        const next = {
                            [F.name]: f.name.trim(), [F.type]: f.type_code,
                            location_description: blank(f.location_description), [F.extra]: blank(f.extra),
                            notes: blank(f.notes), acquired_at: f.acquired_at || null,
                            belongs_to_organization_pk: f.belongsTo.selected ? f.belongsTo.selected.organization_pk : null,
                            acquisition_method_code: f.acquisition_method_code || null,
                        };
                        const body = {};
                        for (const key of Object.keys(next)) {
                            if ((r[key] == null ? null : r[key]) !== next[key]) body[key] = next[key];
                        }
                        if (!Object.keys(body).length) { f.error = "No changes to save."; return; }
                        res = await NSSAuth.apiFetch(`${BASE}/${kind}/${this.apSelectedPk}`, {
                            method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(body),
                        });
                    }
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        f.error = NSS.errorMessage(data, res.status);
                        return;
                    }
                    const rec = await res.json();
                    if (this.apKind !== kind) return;
                    if (f.mode === "create") {
                        this.showToast(`${this.apNounTitle} ${rec[F.id]} registered.`);
                        await this.apOpen(rec[F.pk]);
                    } else {
                        this.apSelected = rec;
                        this.apForm = newForm();
                        this.showToast(`${this.apNounTitle} updated.`);
                    }
                } catch (err) {
                    f.error = err.message || `Failed to save the ${this.apNoun}.`;
                } finally {
                    f.saving = false;
                }
            },

            // ── Lifecycle transition ──────────────────────────────────
            // Disposal / retirement is RECORDED here, not approved: it asks for
            // the Governance decision reference (sent as `remarks`, kept in the
            // audit trail) and a confirmation. Other moves just confirm.
            apTransitionLabel(to) {
                return NSS.assetPropertyTransitionLabel(this.apSelected ? this.apSelected.status : "", to);
            },

            async apStartTransition(to) {
                this.apTransition = { ...newTransition(), target: to };
                if (to === NSS.ASSET_PROPERTY_LIFECYCLE[this.apKind].terminal) {
                    this.apTransition.show = true;
                    return;
                }
                const ok = await NSSDialog.confirm(
                    `${this.apTransitionLabel(to)}: change this ${this.apNoun} to "${NSS.assetPropertyStatusLabel(to)}"?`,
                    { title: this.apTransitionLabel(to), confirmText: "Confirm" },
                );
                if (ok) await this.apSubmitTransition();
            },

            apCancelTransition() {
                this.apTransition = newTransition();
            },

            async apConfirmTerminalTransition() {
                const t = this.apTransition;
                const label = NSS.assetPropertyStatusLabel(t.target).toLowerCase();
                const ok = await NSSDialog.confirm(
                    `Record this ${this.apNoun} as ${label}? This is permanent: a ${label} ${this.apNoun} cannot change status again. `
                    + "Its current custodianship will be ended today and kept in the history; the custodian stays on the record as the last custodian.",
                    { title: this.apTransitionLabel(t.target), confirmText: "Record", confirmClass: "danger" },
                );
                if (ok) await this.apSubmitTransition();
            },

            async apSubmitTransition() {
                const t = this.apTransition;
                const kind = this.apKind, pk = this.apSelectedPk;
                t.error = "";
                t.saving = true;
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}/transition`, {
                        method: "POST", headers: JSON_HEADERS,
                        body: JSON.stringify({ status: t.target, remarks: blank(t.remarks) }),
                    });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        const msg = NSS.errorMessage(data, res.status);
                        if (t.show) t.error = msg; else await NSSDialog.alert(msg);
                        return;
                    }
                    const rec = await res.json();
                    if (this._apStale(kind, pk)) return;
                    this.apSelected = rec;
                    this.apCancelTransition();
                    this.showToast(`${this.apNounTitle} is now ${NSS.assetPropertyStatusLabel(rec.status).toLowerCase()}.`);
                } catch (err) {
                    const msg = err.message || "Failed to record the lifecycle event.";
                    if (t.show) t.error = msg; else await NSSDialog.alert(msg);
                } finally {
                    t.saving = false;
                }
            },

            async apArchive() {
                const kind = this.apKind, pk = this.apSelectedPk;
                const ok = await NSSDialog.confirm(
                    `Archive this ${this.apNoun}? It disappears from the lists; its history is retained.`,
                    { title: `Archive ${this.apNoun}`, confirmText: "Archive", confirmClass: "danger" },
                );
                if (!ok) return;
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}`, { method: "DELETE" });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        await NSSDialog.alert(NSS.errorMessage(data, res.status));
                        return;
                    }
                    if (this._apStale(kind, pk)) return;
                    await this.apBackToList();
                    this.apNotice = `${this.apNounTitle} archived.`;
                } catch (err) {
                    await NSSDialog.alert(err.message || `Failed to archive the ${this.apNoun}.`);
                }
            },

            // ── Sub-resources: generic loader ─────────────────────────
            async _apLoadSub(key, suffix, failure) {
                const kind = this.apKind, pk = this.apSelectedPk;
                if (!pk) return;
                const s = this.apSub[key];
                s.loading = true;
                s.error = "";
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}/${suffix}`);
                    if (this._apStale(kind, pk)) return;
                    if (!res.ok) throw new Error(await NSS.extractError(res));
                    const data = await res.json();
                    if (this._apStale(kind, pk)) return;
                    s.items = data.items;
                } catch (err) {
                    if (!this._apStale(kind, pk)) s.error = err.message || failure;
                } finally {
                    s.loading = false;
                }
            },

            // Shared by maintenance + statutory delete (same shape: confirm, DELETE, reload).
            async _apDeleteSub(url, what, reload) {
                const kind = this.apKind, pk = this.apSelectedPk;
                const ok = await NSSDialog.confirm(
                    `Delete this ${what}? The entry is retracted but kept in the audit trail.`,
                    { title: `Delete ${what}`, confirmText: "Delete", confirmClass: "danger" },
                );
                if (!ok) return;
                try {
                    const res = await NSSAuth.apiFetch(url, { method: "DELETE" });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        await NSSDialog.alert(NSS.errorMessage(data, res.status));
                        return;
                    }
                    if (!this._apStale(kind, pk)) await reload();
                } catch (err) {
                    await NSSDialog.alert(err.message || `Failed to delete the ${what}.`);
                }
            },

            // ── Custody ───────────────────────────────────────────────
            apLoadCustody() {
                return this._apLoadSub("custody", "custodianships", "Failed to load custody history.");
            },

            apOpenAssign() {
                this.apAssign = { ...newAssign(), show: true };
            },
            apCancelAssign() {
                this.apAssign = newAssign();
            },

            async apSubmitAssign() {
                const a = this.apAssign;
                a.error = "";
                if (!a.custodian.selected) { a.error = "Select the custodian organization."; return; }
                const kind = this.apKind, pk = this.apSelectedPk;
                a.saving = true;
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}/custodianships`, {
                        method: "POST", headers: JSON_HEADERS,
                        body: JSON.stringify({
                            custodian_organization_pk: a.custodian.selected.organization_pk,
                            effective_from: a.effective_from || null, notes: blank(a.notes),
                        }),
                    });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        a.error = NSS.errorMessage(data, res.status);
                        return;
                    }
                    if (this._apStale(kind, pk)) return;
                    this.apCancelAssign();
                    this.showToast("Custodian assigned.");
                    await this._apReloadSelected("This record is outside your admin scope.");
                    await this.apLoadCustody();
                } catch (err) {
                    a.error = err.message || "Failed to assign the custodian.";
                } finally {
                    a.saving = false;
                }
            },

            apOpenTransfer() {
                this.apTransfer = { ...newTransfer(), show: true };
                this.apLoadCatalogs();
            },
            apCancelTransfer() {
                this.apTransfer = newTransfer();
            },

            async apSubmitTransfer() {
                const t = this.apTransfer;
                t.error = "";
                if (!t.newCustodian.selected) { t.error = "Select the receiving organization."; return; }
                const kind = this.apKind, pk = this.apSelectedPk;
                const body = {
                    new_custodian_organization_pk: t.newCustodian.selected.organization_pk,
                    end_reason_code: t.end_reason_code || "TRANSFER",
                    effective_from: t.effective_from || null, notes: blank(t.notes),
                };
                // Sent only when filled in: omitted means "leave the location as it is".
                if (blank(t.location_description) !== null) body.location_description = blank(t.location_description);
                const ok = await NSSDialog.confirm(
                    `Transfer custody of this ${this.apNoun} to ${t.newCustodian.selected.organization_name}? `
                    + "The current custodianship is ended and kept in the history.",
                    { title: "Transfer custody", confirmText: "Transfer" },
                );
                if (!ok) return;
                t.saving = true;
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}/custodianships/transfer`, {
                        method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body),
                    });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        t.error = NSS.errorMessage(data, res.status);
                        return;
                    }
                    if (this._apStale(kind, pk)) return;
                    this.apCancelTransfer();
                    this.showToast("Custody transferred.");
                    await this._apReloadSelected(
                        `Custody transferred. This ${this.apNoun} is now held outside your admin scope, so it is no longer listed for you.`,
                    );
                    if (this.apSelected) await this.apLoadCustody();
                } catch (err) {
                    t.error = err.message || "Failed to transfer custody.";
                } finally {
                    t.saving = false;
                }
            },

            // ── Maintenance records ───────────────────────────────────
            apLoadMaintenance() {
                return this._apLoadSub("maintenance", "maintenance-records", "Failed to load maintenance records.");
            },

            apToggleMaintForm() {
                const open = !this.apMaintForm.show;
                this.apMaintForm = { ...newMaint(), show: open };
                if (open) this.apLoadCatalogs();
            },

            apEditMaintenance(m) {
                this.apLoadCatalogs();
                this.apMaintForm = {
                    ...newMaint(), show: true, editPk: m.maintenance_record_pk,
                    type_code: m.maintenance_type_code, description: m.description || "",
                    performed_at: m.performed_at || "", notes: m.notes || "",
                };
            },

            async apSubmitMaintenance() {
                const f = this.apMaintForm;
                f.error = "";
                if (!f.type_code) { f.error = "Select the maintenance type."; return; }
                const kind = this.apKind, pk = this.apSelectedPk;
                const body = {
                    maintenance_type_code: f.type_code, description: blank(f.description),
                    performed_at: f.performed_at || null, notes: blank(f.notes),
                };
                f.saving = true;
                try {
                    const url = f.editPk ? `${BASE}/maintenance-records/${f.editPk}` : `${BASE}/${kind}/${pk}/maintenance-records`;
                    const res = await NSSAuth.apiFetch(url, {
                        method: f.editPk ? "PATCH" : "POST", headers: JSON_HEADERS, body: JSON.stringify(body),
                    });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        f.error = NSS.errorMessage(data, res.status);
                        return;
                    }
                    if (this._apStale(kind, pk)) return;
                    this.apMaintForm = newMaint();
                    await this.apLoadMaintenance();
                } catch (err) {
                    f.error = err.message || "Failed to save the maintenance record.";
                } finally {
                    f.saving = false;
                }
            },

            apDeleteMaintenance(m) {
                return this._apDeleteSub(`${BASE}/maintenance-records/${m.maintenance_record_pk}`,
                    "maintenance record", () => this.apLoadMaintenance());
            },

            // ── Statutory records (properties only, AP-040) ───────────
            apLoadStatutory() {
                return this._apLoadSub("statutory", "statutory-records", "Failed to load statutory records.");
            },

            apToggleStatForm() {
                const open = !this.apStatForm.show;
                this.apStatForm = { ...newStat(), show: open };
                if (open) this.apLoadCatalogs();
            },

            apEditStatutory(r) {
                this.apLoadCatalogs();
                this.apStatForm = {
                    ...newStat(), show: true, editPk: r.property_statutory_record_pk,
                    type_code: r.obligation_type_code, description: r.description || "",
                    reference_number: r.reference_number || "", notes: r.notes || "",
                };
            },

            async apSubmitStatutory() {
                const f = this.apStatForm;
                f.error = "";
                if (!f.type_code) { f.error = "Select the obligation type."; return; }
                const kind = this.apKind, pk = this.apSelectedPk;
                const body = {
                    obligation_type_code: f.type_code, description: blank(f.description),
                    reference_number: blank(f.reference_number), notes: blank(f.notes),
                };
                f.saving = true;
                try {
                    const url = f.editPk ? `${BASE}/statutory-records/${f.editPk}` : `${BASE}/properties/${pk}/statutory-records`;
                    const res = await NSSAuth.apiFetch(url, {
                        method: f.editPk ? "PATCH" : "POST", headers: JSON_HEADERS, body: JSON.stringify(body),
                    });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        f.error = NSS.errorMessage(data, res.status);
                        return;
                    }
                    if (this._apStale(kind, pk)) return;
                    this.apStatForm = newStat();
                    await this.apLoadStatutory();
                } catch (err) {
                    f.error = err.message || "Failed to save the statutory record.";
                } finally {
                    f.saving = false;
                }
            },

            apDeleteStatutory(r) {
                return this._apDeleteSub(`${BASE}/statutory-records/${r.property_statutory_record_pk}`,
                    "statutory record", () => this.apLoadStatutory());
            },

            // ── Documents (links to Foundation document_master) ───────
            // The document is chosen from the Foundation document registry
            // (GET /foundation/documents, FOUNDATION_VIEW — held by every role
            // that holds ASSET_VIEW). Files are not uploaded from here.
            apLoadDocuments() {
                return this._apLoadSub("documents", "documents", "Failed to load documents.");
            },

            async apLoadDocOptions() {
                if (this.apDocOptionsLoaded) return;
                try {
                    const res = await NSSAuth.apiFetch("/api/v1/foundation/documents");
                    if (res.ok) {
                        this.apDocOptions = await res.json();
                        this.apDocOptionsLoaded = true;
                    } else if (res.status === 403) {
                        this.apDocOptionsError = "You do not have permission to browse the document registry.";
                    } else {
                        this.apDocOptionsError = await NSS.extractError(res);
                    }
                } catch (err) {
                    this.apDocOptionsError = err.message || "Failed to load the document registry.";
                }
            },

            // Registry documents not already attached to the open record.
            get apDocChoices() {
                const attached = new Set(this.apSub.documents.items.map((d) => d.document_master_pk));
                return this.apDocOptions.filter((d) => !attached.has(d.document_master_pk));
            },

            apDocOptionLabel(d) {
                const type = NSS.codeLabel(d.document_type_code);
                return `${d.document_name} (${type}${d.document_number ? " · " + d.document_number : ""})`;
            },

            apToggleDocForm() {
                const open = !this.apDocForm.show;
                this.apDocForm = { ...newDoc(), show: open };
                if (open) { this.apLoadCatalogs(); this.apLoadDocOptions(); }
            },

            async apSubmitDocument() {
                const f = this.apDocForm;
                f.error = "";
                if (!f.document_master_pk) { f.error = "Select a document from the registry."; return; }
                const kind = this.apKind, pk = this.apSelectedPk;
                f.saving = true;
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}/documents`, {
                        method: "POST", headers: JSON_HEADERS,
                        body: JSON.stringify({
                            document_master_pk: f.document_master_pk,
                            relationship_type_code: f.relationship_type_code || null, notes: blank(f.notes),
                        }),
                    });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        f.error = NSS.errorMessage(data, res.status);
                        return;
                    }
                    if (this._apStale(kind, pk)) return;
                    this.apDocForm = newDoc();
                    await this.apLoadDocuments();
                } catch (err) {
                    f.error = err.message || "Failed to attach the document.";
                } finally {
                    f.saving = false;
                }
            },

            async apDetachDocument(d) {
                const kind = this.apKind, pk = this.apSelectedPk;
                const ok = await NSSDialog.confirm(
                    `Detach "${d.document_name}" from this ${this.apNoun}? The document stays in the registry.`,
                    { title: "Detach document", confirmText: "Detach", confirmClass: "danger" },
                );
                if (!ok) return;
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/${kind}/${pk}/documents/${d.link_pk}`, { method: "DELETE" });
                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        await NSSDialog.alert(NSS.errorMessage(data, res.status));
                        return;
                    }
                    if (!this._apStale(kind, pk)) await this.apLoadDocuments();
                } catch (err) {
                    await NSSDialog.alert(err.message || "Failed to detach the document.");
                }
            },
        };
    }

    /**
     * Mix the Assets & Property screens into a host Alpine component. Uses
     * property DESCRIPTORS (not spread) so getters stay live, and never
     * overwrites a property the host already owns — same contract as
     * NSSAttendanceRegister.install().
     */
    window.NSSAssetsProperty = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(assetsPropertyMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
