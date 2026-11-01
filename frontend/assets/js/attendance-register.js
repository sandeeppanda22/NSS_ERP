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

    /**
     * Live-register poll interval (owner decision "Option B": explicit Save,
     * other markers' Saves reach this screen within ~2 s by polling
     * GET /attendance/pujas/{pk}/live). The ONE place the number lives;
     * tests/ui/test_ui_attendance.py pins it.
     *   - POLL_MS: fixed interval while the panel is open.
     * Deliberately NOT implemented yet (owner: "remove for now"): idle
     * slow-down, hidden-tab pause, error back-off, and the per-user rate
     * limit on /live. With many markers behind one IP the global 300/min
     * per-IP limit can be hit — see the open item in CLAUDE.md.
     */
    const LIVE_POLL = Object.freeze({
        POLL_MS: 2000,
    });
    const ATT_STATUS_LABEL = { PRESENT: "Present", ABSENT: "Absent", EXCUSED_ABSENCE: "Excused" };
    const FLASH_MS = 1600;
    const SAVED_NOTE_MS = 4000;

    /**
     * THE attendance-percentage formula of the register screen (owner
     * 2026-11-01): present / (roster total - excused), rounded, null when the
     * denominator is 0. UNMARKED members stay in the denominator (the figure
     * is "out of the whole Sakha", not "out of those marked so far");
     * EXCUSED_ABSENCE members are left out, as ATT-008 excludes them. Pure,
     * and the only place the formula lives - attMarkCounts is its only caller.
     */
    function registerAttendancePercentage(present, excused, total) {
        const denom = total - excused;
        return denom > 0 ? Math.round(present / denom * 100) : null;
    }

    function attendanceRegisterMixin() {
        return {
            // ── Permissions ────────────────────────────────────────────
            // Reads the component's live currentUser (set from /auth/me on
            // every page load; reactive, so getters like canManageAttendance
            // re-evaluate once it arrives), falling back to the localStorage
            // cache only before that. The cache alone is a login-time
            // snapshot: a role granted after login (e.g. Attendance Marker)
            // never showed, and a revoked one lingered, until re-login.
            _attPerms() {
                return (this.currentUser || NSSAuth.getCachedUser() || {}).permissions || [];
            },
            get canViewAttendance() {
                const p = this._attPerms();
                return p.includes("ATTENDANCE_VIEW") || p.includes("ATTENDANCE_MANAGE");
            },
            get canManageAttendance() {
                return this._attPerms().includes("ATTENDANCE_MANAGE");
            },

            // ── Mark-attendance state ─────────────────────────────────
            // Several markers of one Sakha open this register at once, so
            // each row separates THREE things:
            //   attendance_status_code - what is on screen (this marker's own
            //                            edit when dirty, else the server's);
            //   serverState            - the latest status/version/marker the
            //                            server told us (status null = unmarked);
            //   dirty / ackVersion     - whether THIS marker changed it, and the
            //                            version they last saw (sent as
            //                            expected_version; verbatim string).
            // Save sends only dirty rows; see submitMarkAttendance().
            attMarkPuja: null,
            attMarkRows: [],
            attMarkLoading: false,
            attMarkSaving: false,
            attMarkError: "",
            attMarkSavedNote: "",
            attLiveReconnecting: false,
            attMarkFilter: "ALL",  // ALL | NOT_MARKED | PRESENT | ABSENT | EXCUSED_ABSENCE

            // Live P/A/E tallies over the current rows - drives the status
            // bar, the progress banner and the filter chips. `marked` /
            // `unmarked` count rows with / without a status. `percentage` is
            // registerAttendancePercentage() (present / (total - excused)).
            get attMarkCounts() {
                const c = { present: 0, absent: 0, excused: 0, total: this.attMarkRows.length, marked: 0, unmarked: 0 };
                for (const r of this.attMarkRows) {
                    if (r.attendance_status_code === "PRESENT") c.present++;
                    else if (r.attendance_status_code === "ABSENT") c.absent++;
                    else if (r.attendance_status_code === "EXCUSED_ABSENCE") c.excused++;
                    if (r.attendance_status_code) c.marked++; else c.unmarked++;
                }
                c.percentage = registerAttendancePercentage(c.present, c.excused, c.total);
                return c;
            },
            get attMarkProgressText() {
                const c = this.attMarkCounts;
                return `${c.marked} of ${c.total} marked`;
            },
            get attMarkProgressPercent() {
                const c = this.attMarkCounts;
                return c.total ? Math.round(c.marked / c.total * 100) : 0;
            },
            get attMarkDirtyCount() {
                return this.attMarkRows.filter(r => r.dirty).length;
            },

            attMarkVisibleRows() {
                if (this.attMarkFilter === "ALL") return this.attMarkRows;
                if (this.attMarkFilter === "NOT_MARKED") return this.attMarkRows.filter(r => !r.attendance_status_code);
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

            // The sync primitive every status edit ends in. A row is dirty
            // only while it differs from what the server last said, so
            // toggling back to the server's value (or someone else saving the
            // same value) clears it - and with it any overwrite confirmation.
            // The P/A/E buttons go through attMarkTap() (asks first when the
            // row was marked by someone else); this never asks.
            attMarkSet(row, statusCode) {
                row.attendance_status_code = statusCode;
                row.dirty = statusCode !== ((row.serverState || {}).status || null);
                if (!row.dirty) {
                    row.ackVersion = (row.serverState || {}).version || null;
                    row.confirmedOverwrite = false;
                }
            },

            // Business id of the signed-in Sangha Sevi (compared with the
            // marker id the server reports per row).
            _attMySeviId() {
                return (this.currentUser || NSSAuth.getCachedUser() || {}).sangha_sevi_id || null;
            },

            // True when `row` is marked on the server by a known person other
            // than the current user and `statusCode` would change that mark
            // and the user has not already agreed to overwrite it.
            _attNeedsOverwriteConfirm(row, statusCode) {
                const st = row.serverState || {};
                return !!st.status && st.status !== statusCode && !row.confirmedOverwrite
                    && !!st.markedBySeviId && st.markedBySeviId !== this._attMySeviId();
            },

            // P/A/E tap on one row. Changing another marker's mark asks first
            // ("ask, naming who changed it"); Cancel keeps their mark, OK edits
            // locally and flags the row so Save sends it in
            // overwrite_sangha_sevi_pks. Your own marks never ask. Runs
            // synchronously (no await) when no question is needed.
            attMarkTap(row, statusCode) {
                if (!this._attNeedsOverwriteConfirm(row, statusCode)) return this.attMarkSet(row, statusCode);
                const st = row.serverState;
                return NSSDialog.confirm(
                    `Marked ${ATT_STATUS_LABEL[st.status] || st.status} by ${st.markedBy || st.markedBySeviId}`
                    + `${st.markedAt ? " at " + this._attFmtTime(st.markedAt) : ""} \u2014 change it?`,
                    { title: "Marked by someone else", confirmText: "Change it", cancelText: "Keep their mark", confirmClass: "warning" }
                ).then(ok => {
                    if (!ok) return;
                    row.confirmedOverwrite = true;
                    this.attMarkSet(row, statusCode);
                });
            },

            // Bulk set - the common real-world case is "everyone showed up
            // except a few", so marking all Present and then correcting the
            // exceptions is far fewer clicks than touching every row.
            // Honours the active filter: with a chip selected it only
            // retags the rows actually on screen. Rows marked by someone
            // else (with a different status) are SKIPPED unless the user
            // confirms once for the whole batch (the dialog says how many).
            // Fully synchronous when no such row is on screen.
            attMarkSetAll(statusCode) {
                const rows = this.attMarkVisibleRows();
                const others = rows.filter(r => this._attNeedsOverwriteConfirm(r, statusCode));
                for (const r of rows) if (!others.includes(r)) this.attMarkSet(r, statusCode);
                if (!others.length) return undefined;
                const n = others.length;
                return NSSDialog.confirm(
                    `${n} ${n === 1 ? "member was" : "members were"} marked by someone else. `
                    + `Change ${n === 1 ? "that mark" : "those marks"} to ${ATT_STATUS_LABEL[statusCode] || statusCode} too?`,
                    { title: "Marked by someone else", confirmText: `Change ${n === 1 ? "it" : "all " + n}`, cancelText: "Skip them", confirmClass: "warning" }
                ).then(ok => {
                    if (!ok) return;
                    for (const r of others) { r.confirmedOverwrite = true; this.attMarkSet(r, statusCode); }
                });
            },

            // ── Per-row attribution / conflict display ───────────────
            _attFmtTime(iso) {
                const d = iso ? new Date(iso) : null;
                if (!d || isNaN(d)) return "";
                const t = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                return d.toDateString() === new Date().toDateString()
                    ? t : `${d.toLocaleDateString([], { day: "2-digit", month: "short" })} ${t}`;
            },
            // "by Asha Devi, 10:32" - who last changed the row on the server.
            attRowMeta(row) {
                if (row.dirty) return "Unsaved change";
                const st = row.serverState || {};
                if (!st.status) return "Not marked";
                const by = st.markedBy || st.markedBySeviId;
                return `${by ? "by " + by + ", " : ""}${this._attFmtTime(st.markedAt)}`.replace(/, $/, "");
            },
            // This marker has a pending edit, and the server's row moved
            // under it to a different status since they last saw it.
            attRowStale(row) {
                const st = row.serverState || {};
                return !!row.dirty && (st.version || null) !== (row.ackVersion || null)
                    && (st.status || null) !== row.attendance_status_code;
            },
            attRowHint(row) {
                const st = row.serverState || {};
                const who = st.markedBy || st.markedBySeviId || "Someone";
                const what = st.status ? `marked ${ATT_STATUS_LABEL[st.status] || st.status}` : "removed the mark";
                return `${who} ${what} at ${this._attFmtTime(st.markedAt)}`;
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
                this._attStopPolling();
                this.attMarkPuja = puja;
                this.attMarkRows = [];
                this.attMarkFilter = "ALL";
                this.attMarkError = "";
                this.attMarkSavedNote = "";
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

                    const existingByPk = {};
                    for (const r of await this._attFetchPujaRecords(puja)) existingByPk[r.sangha_sevi_pk] = r;
                    // Roster members first (untouched = unmarked, NOT a default
                    // status - an untouched row is never saved), then anyone
                    // already marked for this puja who is not on the home roster
                    // (a Darshak visitor another marker added).
                    const rows = (roster.members || []).map(m => this._attMarkRow(m, existingByPk[m.sangha_sevi_pk]));
                    const onRoster = new Set(rows.map(r => r.sangha_sevi_pk));
                    for (const rec of Object.values(existingByPk)) {
                        if (!onRoster.has(rec.sangha_sevi_pk)) rows.push(this._attRowFromRecord(rec));
                    }
                    this.attMarkRows = rows;
                    this._attStartPolling();
                } catch (e) {
                    this.attMarkError = e.message || "Failed to load roster.";
                } finally {
                    this.attMarkLoading = false;
                }
            },

            // Every attendance record of one puja. list_records() caps
            // page_size at 200 (NOT NSS.MAX_PAGE_SIZE) - page through,
            // narrowed server-side to this puja so a long-lived Sakha's
            // whole history is never pulled. Shared by the initial load and
            // by the live poller when it meets a member it has no row for.
            async _attFetchPujaRecords(puja) {
                const out = [];
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
                        if (r.weekly_sangha_puja_pk === puja.weekly_sangha_puja_pk) out.push(r);
                    }
                    if (pageRecords.length < 200) break;
                }
                return out;
            },

            // What the server last said about one member's row, from either
            // an AttendanceRecordResponse or a LiveAttendanceRow.
            _attServerState(rec, isActive = true) {
                return {
                    status: isActive ? (rec.attendance_status_code || null) : null,
                    version: rec.version || null,
                    markedBy: rec.marked_by_name || null,
                    markedBySeviId: rec.marked_by_sangha_sevi_id || null,
                    markedAt: rec.marked_at || null,
                };
            },

            // Build one row from a Member Directory member. is_darshak =
            // the member's home Sakha differs from the puja's Sakha
            // (ATT-029/030); the backend recomputes this authoritatively
            // on save, this is only the live pre-save hint. `existing` is
            // the AttendanceRecordResponse already saved for this puja, if
            // any - otherwise the row starts UNMARKED (null status).
            _attMarkRow(m, existing) {
                const serverState = this._attServerState(existing || {});
                return {
                    sangha_sevi_pk: m.sangha_sevi_pk,
                    sangha_sevi_id: m.sangha_sevi_id,
                    local_sakha_erp_id: m.local_sakha_erp_id || "",
                    person_name: [m.first_name, m.middle_name, m.last_name].filter(Boolean).join(" "),
                    home_org_pk: m.organization_pk,
                    home_org_name: m.organization_name,
                    membership_type_code: m.membership_type_code,
                    is_darshak: m.organization_pk !== this.attMarkPuja.sakha_pk,
                    attendance_status_code: serverState.status,
                    already_marked: !!existing,
                    serverState,
                    dirty: false,
                    confirmedOverwrite: false,
                    ackVersion: serverState.version,
                    flash: false,
                };
            },

            // Same row, built from an attendance record alone (no directory
            // member) - for people marked by another marker who are not in
            // the home roster.
            _attRowFromRecord(rec) {
                return this._attMarkRow({
                    sangha_sevi_pk: rec.sangha_sevi_pk,
                    sangha_sevi_id: rec.sangha_sevi_id,
                    local_sakha_erp_id: rec.local_sakha_erp_id,
                    first_name: rec.person_name,
                    organization_pk: rec.home_organization_pk,
                    organization_name: rec.home_organization_name,
                    membership_type_code: rec.membership_type_code,
                }, rec);
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
                this._attStopPolling();
                this.attMarkPuja = null;
                this.attMarkRows = [];
                this.attMarkSavedNote = "";
                this.attMarkClearSearch();
            },

            // Drop this marker's edit on a row and show the server's value.
            _attRevertRow(row) {
                const st = row.serverState || {};
                row.attendance_status_code = st.status || null;
                row.dirty = false;
                row.confirmedOverwrite = false;
                row.ackVersion = st.version || null;
            },

            // Ask the marker what to do about members someone else changed.
            // `items` = [{ row, statusNow, by, at, wanted }]. true = overwrite
            // them, false = keep theirs.
            async _attAskConflicts(items) {
                const lines = items.map(i => {
                    const now = i.statusNow ? `marked ${ATT_STATUS_LABEL[i.statusNow] || i.statusNow}` : "unmarked";
                    return `\u2022 ${i.row.person_name} (${i.row.sangha_sevi_id}): ${now} by ${i.by || "someone"} at ${this._attFmtTime(i.at)}`
                        + ` \u2014 you chose ${ATT_STATUS_LABEL[i.wanted] || i.wanted}`;
                });
                return NSSDialog.confirm(
                    `Someone else changed ${items.length === 1 ? "this member" : "these members"} since you last saw `
                    + `${items.length === 1 ? "them" : "them"}:\n\n${lines.join("\n")}\n\nOverwrite with your choice, or keep theirs?`,
                    { title: "Changed by someone else", confirmText: "Overwrite these", cancelText: "Keep theirs", confirmClass: "warning" }
                );
            },

            /**
             * Save ONLY the rows this marker changed (dirty), each with the
             * version they last saw as expected_version - never the whole
             * roster, so one marker's Save cannot clobber another's work.
             * A member someone else changed meanwhile is confirmed first:
             * the dialog names who changed it and when; "Overwrite these"
             * resends them as confirmed, "Keep theirs" drops those edits.
             * The panel stays open afterwards (live register) and the host
             * refresh hook still runs.
             */
            async submitMarkAttendance() {
                if (!this.attMarkPuja || this.attMarkSaving) return;
                this.attMarkSaving = true;
                this.attMarkError = "";
                this.attMarkSavedNote = "";
                try {
                    let toSend = this.attMarkRows.filter(r => r.dirty && r.attendance_status_code);
                    if (!toSend.length) {
                        this._attNoteSaved("Nothing to save.");
                        return;
                    }
                    // Edits we already know are stale (the poller saw the
                    // other marker's change): ask before even sending.
                    const stale = toSend.filter(r => this.attRowStale(r));
                    if (stale.length) {
                        const overwrite = await this._attAskConflicts(stale.map(r => ({
                            row: r, statusNow: r.serverState.status, by: r.serverState.markedBy || r.serverState.markedBySeviId,
                            at: r.serverState.markedAt, wanted: r.attendance_status_code,
                        })));
                        for (const r of stale) {
                            if (overwrite) r.ackVersion = r.serverState.version || null;
                            else this._attRevertRow(r);
                        }
                        toSend = toSend.filter(r => r.dirty);
                    }
                    // Rows whose OTHER-marker mark the user already agreed to change.
                    const overwritePks = toSend.filter(r => r.confirmedOverwrite).map(r => r.sangha_sevi_pk);
                    let saved = 0;
                    for (let attempt = 0; toSend.length && attempt < 4; attempt++) {
                        const res = await NSSAuth.apiFetch(
                            `/api/v1/attendance/pujas/${this.attMarkPuja.weekly_sangha_puja_pk}/attendance`,
                            {
                                method: "POST",
                                body: JSON.stringify({
                                    // expected_version is ALWAYS present (null = "I saw it
                                    // unmarked"), which switches on the server-side check.
                                    records: toSend.map(r => ({
                                        sangha_sevi_pk: r.sangha_sevi_pk,
                                        attendance_status_code: r.attendance_status_code,
                                        expected_version: r.ackVersion || null,
                                    })),
                                    overwrite_sangha_sevi_pks: overwritePks,
                                }),
                            }
                        );
                        const data = await res.json();
                        if (res.status === 409 && data && data.detail && Array.isArray(data.detail.conflicts)) {
                            const byPk = new Map(toSend.map(r => [r.sangha_sevi_pk, r]));
                            const conflicts = data.detail.conflicts.filter(c => byPk.has(c.sangha_sevi_pk));
                            const overwrite = await this._attAskConflicts(conflicts.map(c => ({
                                row: byPk.get(c.sangha_sevi_pk), statusNow: c.current_status_code,
                                by: c.changed_by_name || c.changed_by_sangha_sevi_id, at: c.changed_at,
                                wanted: c.requested_status_code,
                            })));
                            for (const c of conflicts) {
                                const row = byPk.get(c.sangha_sevi_pk);
                                row.serverState = this._attServerState({
                                    attendance_status_code: c.current_status_code, version: c.changed_at,
                                    marked_by_name: c.changed_by_name, marked_by_sangha_sevi_id: c.changed_by_sangha_sevi_id,
                                    marked_at: c.changed_at,
                                });
                                if (overwrite) overwritePks.push(c.sangha_sevi_pk);
                                else this._attRevertRow(row);
                            }
                            toSend = toSend.filter(r => r.dirty);
                            continue;
                        }
                        if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                        // Rebaseline: what we just wrote is now the acknowledged server state.
                        const byPk = new Map(this.attMarkRows.map(r => [r.sangha_sevi_pk, r]));
                        for (const rec of data.records || []) {
                            const row = byPk.get(rec.sangha_sevi_pk);
                            if (!row) continue;
                            row.serverState = this._attServerState(rec);
                            row.attendance_status_code = row.serverState.status;
                            row.ackVersion = row.serverState.version;
                            row.dirty = false;
                            row.confirmedOverwrite = false;
                            row.already_marked = true;
                        }
                        saved = (data.records || []).length;
                        toSend = [];
                    }
                    if (saved) {
                        this._attNoteSaved(`Saved ${saved} ${saved === 1 ? "change" : "changes"}.`);
                        await this._afterAttendanceSaved();
                    } else {
                        this._attNoteSaved("No changes were saved.");
                    }
                } catch (e) {
                    this.attMarkError = e.message || "Failed to save attendance.";
                } finally {
                    this.attMarkSaving = false;
                }
            },

            _attNoteSaved(text) {
                this.attMarkSavedNote = text;
                clearTimeout(this._attSavedTimer);
                this._attSavedTimer = setTimeout(() => { this.attMarkSavedNote = ""; }, SAVED_NOTE_MS);
            },

            // ── Live poller ───────────────────────────────────────────
            // Policy constants: LIVE_POLL at the top of this file.
            _attPollGen: 0,
            _attPollTimer: null,
            _attPollEtag: null,
            _attPollSince: null,
            _attPollFailures: 0,
            _attPollBusy: false,
            _attPolling: false,
            _attSavedTimer: null,

            // Fixed-interval poll (LIVE_POLL.POLL_MS). Adaptive cadence
            // (idle slow-down, hidden-tab pause, error back-off) and the
            // per-user rate limit were deliberately left out for now — see
            // the open item in CLAUDE.md.
            _attStartPolling() {
                this._attStopPolling();
                this._attPollGen++;
                this._attPolling = true;
                this._attSchedulePoll(LIVE_POLL.POLL_MS);
            },

            _attStopPolling() {
                this._attPollGen++;
                clearTimeout(this._attPollTimer);
                this._attPollTimer = null;
                this._attPolling = false;
                this._attPollEtag = null;
                this._attPollSince = null;
                this._attPollFailures = 0;
                this._attPollBusy = false;
                this.attLiveReconnecting = false;
            },

            _attSchedulePoll(delayMs) {
                clearTimeout(this._attPollTimer);
                if (!this.attMarkPuja || !this._attPolling) return;
                const gen = this._attPollGen;
                this._attPollTimer = setTimeout(() => this._attPollOnce(gen), delayMs);
            },

            async _attPollOnce(gen) {
                if (gen !== this._attPollGen || !this.attMarkPuja) return;
                if (this._attPollBusy) return;
                this._attPollBusy = true;
                try {
                    const base = `/api/v1/attendance/pujas/${this.attMarkPuja.weekly_sangha_puja_pk}/live`;
                    const url = this._attPollSince ? `${base}?since=${encodeURIComponent(this._attPollSince)}` : base;
                    const res = await NSSAuth.apiFetch(
                        url,
                        this._attPollEtag ? { headers: { "If-None-Match": this._attPollEtag } } : {}
                    );
                    if (gen !== this._attPollGen) return;
                    if (res.status === 304) {
                        // unchanged
                    } else if (res.ok) {
                        const data = await res.json();
                        if (gen !== this._attPollGen) return;
                        await this._attApplyLive(data);
                        this._attPollSince = data.server_time;
                        this._attPollEtag = res.headers.get("ETag") || null;
                    } else {
                        throw new Error(`Live update failed (${res.status})`);
                    }
                    this._attPollFailures = 0;
                    this.attLiveReconnecting = false;
                } catch (e) {
                    if (gen !== this._attPollGen) return;
                    this._attPollFailures++;
                    this.attLiveReconnecting = true;
                } finally {
                    if (gen === this._attPollGen) {
                        this._attPollBusy = false;
                        this._attSchedulePoll(LIVE_POLL.POLL_MS);
                    }
                }
            },

            /**
             * Merge a LiveAttendanceResponse into the grid. Idempotent (the
             * server re-sends a 1 s overlap): a row whose version we already
             * have, or an older one, is skipped. An untouched row updates in
             * place with a brief flash; a dirty row keeps the marker's edit
             * and only records the new server state (attRowStale() then
             * shows the hint and Save asks first). A dirty edit that now
             * equals the server's value simply stops being dirty.
             */
            async _attApplyLive(data) {
                const byPk = new Map(this.attMarkRows.map(r => [r.sangha_sevi_pk, r]));
                const unknown = new Set();
                let changedAnything = false;
                for (const ch of data.changed || []) {
                    const row = byPk.get(ch.sangha_sevi_pk);
                    if (!row) { if (ch.is_active) unknown.add(ch.sangha_sevi_pk); continue; }
                    const cur = row.serverState || {};
                    if (cur.version && (ch.version === cur.version || Date.parse(ch.version) < Date.parse(cur.version))) continue;
                    row.serverState = this._attServerState(ch, ch.is_active);
                    row.confirmedOverwrite = false;   // the mark they agreed to change is gone
                    changedAnything = true;
                    if (row.dirty) {
                        if (row.attendance_status_code === row.serverState.status) {
                            row.dirty = false;
                            row.ackVersion = row.serverState.version;
                        }
                    } else {
                        row.attendance_status_code = row.serverState.status;
                        row.ackVersion = row.serverState.version;
                        row.flash = true;
                        setTimeout(() => { row.flash = false; }, FLASH_MS);
                    }
                }
                if (unknown.size) {
                    // Someone added a member (e.g. a Darshak visitor) this grid has no row for.
                    for (const rec of await this._attFetchPujaRecords(this.attMarkPuja)) {
                        if (!unknown.has(rec.sangha_sevi_pk)) continue;
                        const row = this._attRowFromRecord(rec);
                        this.attMarkRows.push(row);
                        row.flash = true;
                        setTimeout(() => { row.flash = false; }, FLASH_MS);
                        changedAnything = true;
                    }
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
        LIVE_POLL,
        registerAttendancePercentage,
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
