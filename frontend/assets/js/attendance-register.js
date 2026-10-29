/**
 * Shared Attendance Register (Tier 6) — the one implementation of
 * "mark attendance for a Weekly Sangha Puja", mixed into BOTH hosts:
 *
 *   - admin.js   `adminPanel()`      — the Administration > Attendance tab
 *   - org-dashboard.js `orgDashboardTab()` — the Sakha dashboard's own
 *     Attendance Register (owner ask 2026-10-28: "add it to the dashboard
 *     itself for the designated person, who will register attendance. so
 *     that that person dont need admin acces.. just attendance register
 *     access will be enough")
 *
 * Before this module the roster/search/toggle/submit logic existed only
 * inside admin.js, so putting an attendance register on the member
 * dashboard would have meant a second copy — this project's standing
 * no-duplicate-code rule. Everything genuinely common lives here; what
 * legitimately differs stays with the host:
 *
 *   - the admin tab picks a Sakha from a cross-Sakha scoped list and
 *     lists every puja it can reach;
 *   - the dashboard is already scoped to the ONE org being viewed.
 *
 * Hosts override a hook simply by defining it themselves: install()
 * never overwrites a property the host already owns (see below), so
 * `_afterAttendanceSaved` resolves to the host's own refresh.
 *
 * Permissions are read from the cached /auth/me payload via NSSAuth
 * rather than a host field, because the two hosts name it differently
 * (dashboard.js `user`, admin.js `currentUser`) and the member dashboard
 * defines neither attendance getter — which is exactly why the first cut
 * of the dashboard quick-mark widget silently never rendered.
 */
(function () {
    "use strict";

    function attendanceRegisterMixin() {
        return {
            // ── Permissions ────────────────────────────────────────────
            _attPerms() {
                return (NSSAuth.getCachedUser() || {}).permissions || [];
            },
            get canViewAttendance() {
                const p = this._attPerms();
                return p.includes("ATTENDANCE_VIEW") || p.includes("ATTENDANCE_MANAGE");
            },
            get canManageAttendance() {
                return this._attPerms().includes("ATTENDANCE_MANAGE");
            },

            // ── Mark-attendance state ─────────────────────────────────
            attMarkPuja: null,
            attMarkRows: [],
            attMarkLoading: false,
            attMarkSaving: false,
            attMarkError: "",
            attMarkFilter: "ALL",  // ALL | PRESENT | ABSENT | EXCUSED_ABSENCE

            // Live P/A/E tallies over the current rows — drives the status
            // bar and the filter chips. Attendance % excludes
            // EXCUSED_ABSENCE from the denominator (ATT-008).
            get attMarkCounts() {
                const c = { present: 0, absent: 0, excused: 0, total: this.attMarkRows.length };
                for (const r of this.attMarkRows) {
                    if (r.attendance_status_code === "PRESENT") c.present++;
                    else if (r.attendance_status_code === "ABSENT") c.absent++;
                    else if (r.attendance_status_code === "EXCUSED_ABSENCE") c.excused++;
                }
                const denom = c.present + c.absent;
                c.percentage = denom ? Math.round(c.present / denom * 100) : null;
                return c;
            },

            attMarkVisibleRows() {
                if (this.attMarkFilter === "ALL") return this.attMarkRows;
                return this.attMarkRows.filter(r => r.attendance_status_code === this.attMarkFilter);
            },

            // Home-Sakha members only (the main grid); darshak visitors
            // render in their own section.
            attMarkHomeRows() {
                return this.attMarkVisibleRows().filter(r => !r.is_darshak);
            },
            attMarkDarshakRows() {
                return this.attMarkRows.filter(r => r.is_darshak);
            },

            // Bulk set — the common real-world case is "everyone showed up
            // except a few", so marking all Present and then correcting the
            // exceptions is far fewer clicks than touching every row.
            // Honours the active filter: with a chip selected it only
            // retags the rows actually on screen.
            attMarkSetAll(statusCode) {
                for (const r of this.attMarkVisibleRows()) r.attendance_status_code = statusCode;
            },

            /**
             * Open the register for one puja.
             *
             * The roster comes from the general-member Member Directory
             * (GET /membership/directory?organization_pk=) rather than
             * /membership/members (MEMBERSHIP_VIEW), so a designated
             * Attendance Marker holding no MEMBERSHIP_VIEW can still see
             * who to mark — the whole point of the dashboard register.
             * Each row is pre-filled with any status already recorded for
             * this puja (GET /attendance/records), so reopening the
             * register shows previous work instead of resetting it.
             */
            async openMarkAttendance(puja) {
                this.attMarkPuja = puja;
                this.attMarkRows = [];
                this.attMarkFilter = "ALL";
                this.attMarkError = "";
                this.attMarkSearchQuery = "";
                this.attMarkSearchResults = [];
                this.attMarkLoading = true;
                try {
                    const rosterParams = new URLSearchParams({
                        organization_pk: puja.sakha_pk,
                        limit: String(NSS.MAX_PAGE_SIZE),
                    });
                    const rosterRes = await NSSAuth.apiFetch(`/api/v1/membership/directory?${rosterParams}`);
                    if (!rosterRes.ok) throw new Error("Failed to load this Sakha's member roster.");
                    const roster = await rosterRes.json();

                    // list_records() caps page_size at 200 (NOT NSS.MAX_PAGE_SIZE) — page
                    // through, narrowed server-side to this puja so a long-lived Sakha's
                    // whole history is never pulled.
                    const existingByPk = {};
                    for (let page = 1; ; page++) {
                        const recRes = await NSSAuth.apiFetch(
                            `/api/v1/attendance/records?${new URLSearchParams({
                                organization_pk: puja.sakha_pk,
                                weekly_sangha_puja_pk: puja.weekly_sangha_puja_pk,
                                page_size: "200",
                                page: String(page),
                            })}`
                        );
                        if (!recRes.ok) break;
                        const recData = await recRes.json();
                        const pageRecords = recData.records || [];
                        for (const r of pageRecords) {
                            if (r.weekly_sangha_puja_pk === puja.weekly_sangha_puja_pk) {
                                existingByPk[r.sangha_sevi_pk] = r;
                            }
                        }
                        if (pageRecords.length < 200) break;
                    }
                    this.attMarkRows = (roster.members || []).map(
                        m => this._attMarkRow(m, existingByPk[m.sangha_sevi_pk])
                    );
                } catch (e) {
                    this.attMarkError = e.message || "Failed to load roster.";
                } finally {
                    this.attMarkLoading = false;
                }
            },

            // Build one row from a Member Directory member. is_darshak =
            // the member's home Sakha differs from the puja's Sakha
            // (ATT-029/030); the backend recomputes this authoritatively
            // on save, this is only the live pre-save hint.
            _attMarkRow(m, existing) {
                return {
                    sangha_sevi_pk: m.sangha_sevi_pk,
                    sangha_sevi_id: m.sangha_sevi_id,
                    local_sakha_erp_id: m.local_sakha_erp_id || "",
                    person_name: [m.first_name, m.middle_name, m.last_name].filter(Boolean).join(" "),
                    home_org_pk: m.organization_pk,
                    home_org_name: m.organization_name,
                    membership_type_code: m.membership_type_code,
                    is_darshak: m.organization_pk !== this.attMarkPuja.sakha_pk,
                    attendance_status_code: (existing || {}).attendance_status_code || "PRESENT",
                    already_marked: !!existing,
                };
            },

            // ── Search-to-mark ────────────────────────────────────────
            // The designated marker searches ANY member NSS-wide by name /
            // Sangha Sevi ID / local Sakha number and adds them to this
            // puja — this is also how a cross-Sakha Darshak visitor gets
            // marked, since they are not in the home roster. Reuses
            // /membership/directory?q= (the same matcher the Member
            // Directory uses: name / SS-ID / local Sakha id / mobile /
            // email / Kendra number / Sakha name).
            attMarkSearchQuery: "",
            attMarkSearchResults: [],
            attMarkSearching: false,
            _attMarkSearchDebounce: null,

            searchAttMarkMember() {
                const q = (this.attMarkSearchQuery || "").trim();
                if (this._attMarkSearchDebounce) clearTimeout(this._attMarkSearchDebounce);
                if (q.length < 2) {
                    this.attMarkSearchResults = [];
                    this.attMarkSearching = false;
                    return;
                }
                this.attMarkSearching = true;
                this._attMarkSearchDebounce = setTimeout(async () => {
                    try {
                        const res = await NSSAuth.apiFetch(
                            `/api/v1/membership/directory?q=${encodeURIComponent(q)}&limit=10`
                        );
                        if (res.ok) {
                            const data = await res.json();
                            // Drop anyone already in the grid.
                            const present = new Set(this.attMarkRows.map(r => r.sangha_sevi_pk));
                            this.attMarkSearchResults = (data.members || [])
                                .filter(m => !present.has(m.sangha_sevi_pk));
                        }
                    } catch (e) {
                        console.error("Attendance mark search failed", e);
                    } finally {
                        this.attMarkSearching = false;
                    }
                }, 300);
            },

            addAttMarkMember(m) {
                if (this.attMarkRows.some(r => r.sangha_sevi_pk === m.sangha_sevi_pk)) return;
                this.attMarkRows.push(this._attMarkRow(m, null));
                this.attMarkSearchResults = this.attMarkSearchResults
                    .filter(x => x.sangha_sevi_pk !== m.sangha_sevi_pk);
                this.attMarkSearchQuery = "";
            },

            attMarkClearSearch() {
                this.attMarkSearchQuery = "";
                this.attMarkSearchResults = [];
                this.attMarkSearching = false;
            },

            // Avatar initials for the search results — kept here rather
            // than leaning on a host helper, because dashboard.js's
            // _getInitials() lives in the OUTER Alpine scope and is not
            // reachable from the nested org-dashboard component.
            _attInitials(m) {
                const first = (m.first_name || "")[0] || "";
                const last = (m.last_name || "")[0] || "";
                return (first + last).toUpperCase() || "?";
            },

            // ── Save ──────────────────────────────────────────────────
            closeMarkAttendance() {
                this.attMarkPuja = null;
                this.attMarkRows = [];
                this.attMarkClearSearch();
            },

            async submitMarkAttendance() {
                if (!this.attMarkPuja) return;
                this.attMarkSaving = true;
                this.attMarkError = "";
                try {
                    const records = this.attMarkRows.map(r => ({
                        sangha_sevi_pk: r.sangha_sevi_pk,
                        attendance_status_code: r.attendance_status_code,
                    }));
                    const res = await NSSAuth.apiFetch(
                        `/api/v1/attendance/pujas/${this.attMarkPuja.weekly_sangha_puja_pk}/attendance`,
                        { method: "POST", body: JSON.stringify({ records }) }
                    );
                    const data = await res.json();
                    if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                    this.closeMarkAttendance();
                    await this._afterAttendanceSaved();
                } catch (e) {
                    this.attMarkError = e.message || "Failed to save attendance.";
                } finally {
                    this.attMarkSaving = false;
                }
            },

            // Host hook — what to refresh once attendance saved. Default
            // is a no-op; each host defines its own (admin.js reloads the
            // puja list, org-dashboard.js reloads the dashboard card), and
            // install() leaves a host-defined version alone.
            _afterAttendanceSaved() {},
        };
    }

    /**
     * Mix the register into a host Alpine component.
     *
     * Uses property DESCRIPTORS, not object spread: `{...mixin}` would
     * evaluate every getter once and freeze it as a static value, so
     * canManageAttendance / attMarkCounts would stop tracking. A fresh
     * mixin is built per call so two components on the same page (the
     * admin panel and the embedded org dashboard, both live in
     * admin.html) never share one another's rows.
     *
     * A property the host already owns is never overwritten — that is how
     * a host supplies its own `_afterAttendanceSaved`.
     */
    window.NSSAttendanceRegister = {
        install(target) {
            const descriptors = Object.getOwnPropertyDescriptors(attendanceRegisterMixin());
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
