/**
 * Audit & Diagnostics admin screens - mixed into `adminApp()` (admin.js), which
 * owns the sidebar, the tab state and the /admin entry guard. Both tabs are
 * read-only and gated by the AUDIT_VIEW permission (canViewAudit); the server
 * (api/routers/audit.py) enforces it again.
 *
 *   auditEvents   System Event Log explorer - GET /api/v1/audit/events (server
 *                 side filtering / sorting / paging), /events/facets (dropdowns),
 *                 /events/{pk} (JSON detail) and the existing /audit/change-log
 *                 for the field-level changes of the same transaction
 *                 (field_change_log stays under audit.py, never /foundation).
 *   liveMarkers   nss.live_change_marker diagnostics - GET
 *                 /api/v1/audit/live-change-markers.
 *
 * Refresh policy (one place: AUDIT_POLL). system_event_log is NOT on the live
 * feed whitelist (and must not be), so this file does not use live-refresh.js:
 *   - events: a manual Refresh button plus an opt-in (default OFF) timed
 *     reload, never faster than AUDIT_POLL.EVENTS_MS (10 s+), skipped while the
 *     browser tab is hidden or another admin tab is open.
 *   - markers: a diagnostics page polls its own endpoint every
 *     AUDIT_POLL.MARKERS_MS (5 s) while its tab is on screen; no request while
 *     document.hidden, one at once on return. A row whose change_seq grew since
 *     the previous poll gets the "just changed" highlight until the next poll.
 *
 * Pure helpers (no DOM, tested under node): changedMarkers, relativeTime.
 */
(function () {
    "use strict";

    const BASE = "/api/v1/audit";

    const AUDIT_POLL = Object.freeze({
        EVENTS_MS: 15000,   // optional auto-refresh of the event explorer (>= 10 s)
        MARKERS_MS: 5000,   // marker diagnostics page
    });
    const PAGE_SIZE = 50;
    const DEFAULT_WINDOW_MS = 24 * 3600 * 1000;

    // Friendly names for the admin tabs named in LIVE_TABLE_TABS (admin.js).
    const TAB_LABELS = Object.freeze({
        claims: "Claims", claimsBadge: "Claims badge", changeRequests: "Change Requests",
        changeRequestsBadge: "Change Requests badge", correspondence: "Correspondence",
        govBodies: "Governance Bodies", govAssignments: "Assignments", govElections: "Elections",
        orgDashboard: "Organization dashboards", properties: "Properties", assets: "Assets",
        users: "Users", detail: "User detail", organizations: "Organizations", orgHierarchy: "Organization Hierarchy",
        personDir: "Person Directory", memberDir: "Member Directory", credentials: "Credentials",
        credentialsBadge: "Credentials badge", refData: "Reference Data", geography: "Geography",
        geoApprovals: "Location Approvals", geoApprovalsBadge: "Location Approvals badge",
        sysSettings: "System Settings",
    });

    /** Rows whose change_seq is larger than the one seen before (pure). `seen` {table: seq} -> {changed, seen}. */
    function changedMarkers(markers, seen) {
        const next = {};
        const changed = [];
        for (const m of markers || []) {
            next[m.table_name] = m.change_seq;
            if (seen && Object.prototype.hasOwnProperty.call(seen, m.table_name) && m.change_seq > seen[m.table_name]) {
                changed.push(m.table_name);
            }
        }
        return { changed, seen: next };
    }

    /** "5 s ago" / "3 min ago" / "2 h ago" / "4 d ago" (pure; `now`/`then` are ms). */
    function relativeTime(then, now) {
        const s = Math.max(0, Math.round((now - then) / 1000));
        if (s < 60) return `${s} s ago`;
        if (s < 3600) return `${Math.floor(s / 60)} min ago`;
        if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
        return `${Math.floor(s / 86400)} d ago`;
    }

    /** Local "YYYY-MM-DDTHH:mm" for <input type="datetime-local"> (pure given a Date). */
    function toLocalInput(d) {
        const p = (n) => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
    }

    function csvCell(v) {
        const t = v == null ? "" : String(v);
        return /[",\n\r]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
    }

    const newFilters = () => ({
        table: "", action: "", module: "", actor: "", record: "", success: "", q: "",
        from: toLocalInput(new Date(Date.now() - DEFAULT_WINDOW_MS)), to: "",
    });

    function auditDiagnosticsMixin() {
        return {
            // ── Permission ───────────────────────────────────────────
            get canViewAudit() {
                const p = (this.currentUser || NSSAuth.getCachedUser() || {}).permissions || [];
                return p.includes("AUDIT_VIEW");
            },

            // ── System Event Log explorer state ──────────────────────
            aeFilters: newFilters(),
            aeSort: "desc",
            aePage: 1,
            aePageSize: PAGE_SIZE,
            aeItems: [],
            aeTotal: 0,
            aeCapped: false,
            aeAppliedFrom: null,
            aeLoading: false,
            aeError: "",
            aeFacets: { tables: [], actions: [], modules: [] },
            aeAuto: false,
            aeSelected: null,        // event detail (with .detail JSON)
            aeSelectedLoading: false,
            aeSelectedError: "",
            aeFields: [],            // field_change_log rows of the same transaction
            aeFieldsLoading: false,
            aeFieldsError: "",
            _aeSeq: 0,
            _aeTimer: null,

            get aePages() { return Math.max(1, Math.ceil(this.aeTotal / this.aePageSize)); },
            get aeTotalLabel() {
                return (this.aeCapped ? this.aeTotal.toLocaleString("en-IN") + "+" : this.aeTotal.toLocaleString("en-IN")) + " events";
            },
            get aeDetailJson() {
                const d = this.aeSelected && this.aeSelected.detail;
                return d == null ? "" : JSON.stringify(d, null, 2);
            },

            async auditEventsEnter() {
                this.activeTab = "auditEvents";
                if (this.aeFacets.tables.length === 0) this.aeLoadFacets();
                await this.aeLoad();
                this._aeSchedule();
            },

            async aeLoadFacets() {
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/events/facets`);
                    if (res.ok) this.aeFacets = await res.json();
                } catch (e) { /* dropdowns stay empty; free-text filters still work */ }
            },

            _aeParams() {
                const f = this.aeFilters;
                const params = new URLSearchParams({
                    limit: String(this.aePageSize),
                    offset: String((this.aePage - 1) * this.aePageSize),
                    sort: this.aeSort,
                });
                if (f.table) params.set("table_name", f.table);
                if (f.action) params.set("action", f.action);
                if (f.module) params.set("module", f.module);
                if (f.actor.trim()) params.set("actor_sangha_sevi_id", f.actor.trim());
                if (f.record.trim()) params.set("record_pk", f.record.trim());
                if (f.success) params.set("is_success", f.success);
                if (f.q.trim()) params.set("q", f.q.trim());
                if (f.from) params.set("event_from", new Date(f.from).toISOString());
                if (f.to) params.set("event_to", new Date(f.to).toISOString());
                return params;
            },

            /** Load the current page. opts.silent keeps rows and spinner as they are (timed refresh). */
            async aeLoad(opts = {}) {
                const seq = ++this._aeSeq;
                if (!opts.silent) { this.aeLoading = true; this.aeError = ""; }
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/events?${this._aeParams()}`);
                    if (seq !== this._aeSeq) return;
                    if (!res.ok) throw new Error(await NSS.extractError(res));
                    const data = await res.json();
                    if (seq !== this._aeSeq) return;
                    this.aeItems = data.items;
                    this.aeTotal = data.total;
                    this.aeCapped = data.total_capped;
                    this.aeAppliedFrom = data.event_from;
                    this.aeError = "";
                } catch (err) {
                    if (seq !== this._aeSeq || opts.silent) return;
                    this.aeItems = []; this.aeTotal = 0; this.aeCapped = false;
                    this.aeError = err.message || "Failed to load the system event log.";
                } finally {
                    if (seq === this._aeSeq && !opts.silent) this.aeLoading = false;
                }
            },

            aeApply() { this.aePage = 1; return this.aeLoad(); },
            aeReset() { this.aeFilters = newFilters(); this.aeSort = "desc"; return this.aeApply(); },
            aeToggleSort() { this.aeSort = this.aeSort === "desc" ? "asc" : "desc"; return this.aeApply(); },
            aePrev() { if (this.aePage > 1) { this.aePage--; return this.aeLoad(); } },
            aeNext() { if (this.aePage < this.aePages) { this.aePage++; return this.aeLoad(); } },

            // Timed refresh (opt-in). Re-arms itself; does nothing off-tab / hidden.
            aeSetAuto(on) {
                this.aeAuto = !!on;
                this._aeSchedule();
            },
            _aeSchedule() {
                if (this._aeTimer) { clearTimeout(this._aeTimer); this._aeTimer = null; }
                if (!this.aeAuto || this.activeTab !== "auditEvents") return;
                this._aeTimer = setTimeout(async () => {
                    this._aeTimer = null;
                    if (this.activeTab !== "auditEvents" || !this.aeAuto) return;
                    // Keep the user's place: no reload while a record drawer is open.
                    if (!document.hidden && !this.aeSelected) await this.aeLoad({ silent: true });
                    this._aeSchedule();
                }, AUDIT_POLL.EVENTS_MS);
            },

            async aeOpen(row) {
                this.aeSelected = { ...row, detail: null };
                this.aeSelectedLoading = true; this.aeSelectedError = "";
                this.aeFields = []; this.aeFieldsError = "";
                const pk = row.system_event_log_pk;
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/events/${pk}`);
                    if (!res.ok) throw new Error(await NSS.extractError(res));
                    const full = await res.json();
                    if (!this.aeSelected || this.aeSelected.system_event_log_pk !== pk) return;
                    this.aeSelected = full;
                } catch (err) {
                    this.aeSelectedError = err.message || "Failed to load the event.";
                } finally {
                    this.aeSelectedLoading = false;
                }
                this.aeLoadFields(row);
            },

            /** Field-level rows written in the SAME transaction (same table, record and changed_at = event_at). */
            async aeLoadFields(row) {
                const pk = row.system_event_log_pk;
                this.aeFieldsLoading = true;
                try {
                    const params = new URLSearchParams({
                        table_name: row.table_name, record_pk: row.record_pk,
                        changed_from: row.event_at, changed_to: row.event_at, limit: "500",
                    });
                    const res = await NSSAuth.apiFetch(`${BASE}/change-log?${params}`);
                    if (!this.aeSelected || this.aeSelected.system_event_log_pk !== pk) return;
                    if (!res.ok) throw new Error(await NSS.extractError(res));
                    this.aeFields = await res.json();
                } catch (err) {
                    this.aeFieldsError = err.message || "Failed to load the field changes.";
                } finally {
                    if (this.aeSelected && this.aeSelected.system_event_log_pk === pk) this.aeFieldsLoading = false;
                }
            },

            aeClose() { this.aeSelected = null; this.aeFields = []; },

            /** All events of the opened record, newest first, any date. */
            aeFilterToRecord() {
                if (!this.aeSelected) return;
                this.aeFilters = { ...newFilters(), from: "", record: this.aeSelected.record_pk };
                this.aeClose();
                return this.aeApply();
            },

            aeActorLabel(r) {
                if (r.actor_name && r.actor_sangha_sevi_id) return `${r.actor_name} (${r.actor_sangha_sevi_id})`;
                return r.actor_name || r.actor_sangha_sevi_id || "System / unattributed";
            },

            /** CSV of the rows on screen (this page only; same data the table shows). */
            aeExportCsv() {
                const head = ["event_at", "action", "table_name", "record_pk", "module", "summary", "is_success", "actor_sangha_sevi_id", "actor_name"];
                const lines = [head.join(",")].concat(
                    this.aeItems.map((r) => head.map((h) => csvCell(r[h])).join(",")));
                const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = "system_event_log_page.csv";
                document.body.appendChild(a); a.click(); a.remove();
                setTimeout(() => URL.revokeObjectURL(a.href), 1000);
            },

            // ── Live change markers state ────────────────────────────
            lmRows: [],
            lmFilter: "",
            lmLoading: false,
            lmError: "",
            lmServerTime: null,
            lmNowMs: Date.now(),
            lmLatestSeq: null,
            lmLatestTable: null,
            lmWhitelistSize: 0,
            lmMissing: [],
            lmFlash: {},             // table -> true until the next poll
            lmLastPollAt: null,
            _lmSeen: null,
            _lmTimer: null,
            _lmSeq: 0,
            _lmVisBound: false,

            get lmFiltered() {
                const q = this.lmFilter.trim().toLowerCase();
                // server order = change_seq DESC = most recent first
                return q ? this.lmRows.filter((m) => m.table_name.toLowerCase().includes(q)
                    || this.lmScreens(m.table_name).toLowerCase().includes(q)) : this.lmRows;
            },

            async liveMarkersEnter() {
                this.activeTab = "liveMarkers";
                if (!this._lmVisBound) {
                    this._lmVisBound = true;
                    document.addEventListener("visibilitychange", () => {
                        if (!document.hidden && this.activeTab === "liveMarkers") this.lmLoad({ silent: true });
                    });
                }
                this._lmSeen = null;
                this.lmFlash = {};
                await this.lmLoad();
                this._lmSchedule();
            },

            async lmLoad(opts = {}) {
                const seq = ++this._lmSeq;
                if (!opts.silent) { this.lmLoading = true; this.lmError = ""; }
                try {
                    const res = await NSSAuth.apiFetch(`${BASE}/live-change-markers`);
                    if (seq !== this._lmSeq) return;
                    if (!res.ok) throw new Error(await NSS.extractError(res));
                    const data = await res.json();
                    if (seq !== this._lmSeq) return;
                    const diff = changedMarkers(data.markers, this._lmSeen);
                    this._lmSeen = diff.seen;
                    this.lmFlash = Object.fromEntries(diff.changed.map((t) => [t, true]));
                    this.lmRows = data.markers;
                    this.lmServerTime = data.server_time;
                    this.lmNowMs = new Date(data.server_time).getTime();
                    this.lmLatestSeq = data.latest_change_seq;
                    this.lmLatestTable = data.latest_table_name;
                    this.lmWhitelistSize = data.whitelist_size;
                    this.lmMissing = data.whitelist_without_marker;
                    this.lmLastPollAt = new Date();
                    this.lmError = "";
                } catch (err) {
                    if (seq !== this._lmSeq) return;
                    this.lmError = err.message || "Failed to load the live change markers.";
                } finally {
                    if (seq === this._lmSeq) this.lmLoading = false;
                }
            },

            _lmSchedule() {
                if (this._lmTimer) { clearTimeout(this._lmTimer); this._lmTimer = null; }
                if (this.activeTab !== "liveMarkers") return;
                this._lmTimer = setTimeout(async () => {
                    this._lmTimer = null;
                    if (this.activeTab !== "liveMarkers") return;
                    if (!document.hidden) await this.lmLoad({ silent: true });
                    this._lmSchedule();
                }, AUDIT_POLL.MARKERS_MS);
            },

            lmRelative(iso) { return relativeTime(new Date(iso).getTime(), this.lmNowMs); },

            /** Admin tab(s) this table refreshes (LIVE_TABLE_TABS in admin.js); dashboard-only tabs are not listed. */
            lmScreens(table) {
                const map = typeof LIVE_TABLE_TABS === "undefined" ? {} : LIVE_TABLE_TABS;
                return (map[table] || []).map((t) => TAB_LABELS[t] || t).join(", ");
            },

            /** Called by admin.js when the active tab changes: stops timers of tabs that are no longer on screen. */
            auditTabChanged(tab) {
                if (tab !== "auditEvents" && this._aeTimer) { clearTimeout(this._aeTimer); this._aeTimer = null; }
                if (tab !== "liveMarkers" && this._lmTimer) { clearTimeout(this._lmTimer); this._lmTimer = null; }
                if (tab === "auditEvents") this._aeSchedule();
                if (tab === "liveMarkers" && !this._lmTimer) this._lmSchedule();
            },
        };
    }

    window.NSSAuditDiagnostics = {
        AUDIT_POLL,
        changedMarkers,
        relativeTime,
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(auditDiagnosticsMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
