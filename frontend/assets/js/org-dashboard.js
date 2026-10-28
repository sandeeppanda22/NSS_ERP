/**
 * NSS ERP — Org Dashboard tab (Tier 5)
 *
 * One component, six layouts — the rendered layout depends on the
 * viewed organization's type, each matching its own mockup exactly
 * (colors + structure): docs/03_Solution/ui/mockups/03_sakha_dashboard.html,
 * 05_anchalika_dashboard.html, 06_zilla_dashboard.html, 02_kendra_dashboard.html.
 * Patha Chakra and Mahila Sangha have no mockups of their own (added after
 * the four above) — they reuse the same card idiom as the other tiers rather
 * than introducing a new visual language.
 *
 * The six tiers are exactly the six ORGANIZATIONAL roles in role_master
 * (SOL-ADMIN-004 §8.7): every scoped-admin role has one dashboard, and no
 * dashboard exists without a role that can hold it.
 *
 * Embedded as a tab inside admin.html/dashboard.html's own sidebar+topbar
 * shell (not a standalone page) — both host pages instantiate this same
 * factory in a nested x-data scope and pass in the org PK to view via
 * init(orgPk); each host wires its own openOrgDashboard(orgPk)/
 * myOrgDashboardPk/myOrgDashboardLabel to switch tabs and re-init this
 * component when the viewed org changes.
 *
 * Every number shown is real (member/family counts, Darshak counts,
 * hierarchy) — attendance % and renewal tracking don't exist in this
 * system yet (no DB tables for either), so those mockup widgets are shown
 * as honest "not tracked yet" placeholders rather than fabricated figures.
 * The two Zilla "insights" mockup widgets that depended on attendance/
 * renewal data were swapped for ones backed by real data (largest/smallest
 * Sakha by member count) — same card layout, different, truthful content.
 */

function orgDashboardTab() {
    return {
        loading: true,
        error: "",
        org: null,

        // Sakha tier
        // null means "could not be determined" (request failed, no permission,
        // or no org_code to scope by) and renders as "—". 0 means a real zero.
        sakhaMemberTotal: null,
        sakhaFamilyTotal: null,
        // /family/families has no total, so the count above is a page length.
        // True when it saturated the page limit and is therefore a lower bound.
        sakhaFamilyTruncated: false,
        recentMembers: [],
        darshak: { home_probationary_count: 0, attending_from_other_sakha_count: 0 },

        // Anchalika / Zilla / Kendra tier
        childStats: [],
        sakhaCount: null,
        mahilaCount: null,
        renewalsDue: null,

        // Kendra tier — whole-subtree totals from /organizations/{pk}/stats.
        // Members split into its two constituent parts (these sum exactly to
        // the subtree member total, since every membership_type except
        // PROBATIONARY carries a Parichay Patra), plus one count per
        // constituent ORGANIZATION_TYPE beneath the Kendra.
        //
        // NOTE the Darshak figure here is HOME probationary members only. It
        // deliberately omits card-holders visiting from another Sakha — those
        // are already counted at their home Sakha, so including them would
        // count one person many times over a 175-Sakha rollup. The visiting
        // figure belongs to a single Sakha's own dashboard, and lives there.
        parichayPatraTotal: null,
        darshakTotal: null,
        // Kendra/Anchalika/Zilla-tier attendance rollup (Tier 6,
        // 2026-10-27), from the SAME /organizations/{pk}/stats call these
        // tiers already make — not the Sakha-tier attendanceStats
        // (that one is per-Sakha from attendance.py's own org-stats
        // endpoint; this one is the subtree rollup from organization.py).
        orgAttendancePct: null, orgAttendanceTracked: false,
        anchalikaCount: null,
        zillaCount: null,
        pathaChakraCount: null,
        paribarikCount: null,
        kumariCount: null,
        sevakCount: null,

        // ── Tier 6: Governance + Correspondence (per viewed org) ──
        // Both sections are keyed off the viewed org and re-fetched on every
        // org switch, because openOrgDashboard() toggles viewingOrgPk through
        // null and the host's x-if remounts this whole component (re-running
        // init()). They are NOT load-once latched, so switching orgs never
        // shows a stale body/register.
        govBodies: [],            // normalized [{body_name, body_type_name, body_status, members:[{position_name, position_code, person_name, sangha_sevi_id, sakha_name}], liveElection}]
        govSectionLoading: false,
        // Owner fix 2026-10-23: same show-9+leadership-priority+search-modal
        // pattern as the member dashboard's Governance tab (dashboard.js). The
        // cap/sort/filter logic itself is NOT reimplemented here — both files
        // delegate to the shared NSS.govBodyDisplayMembers/govBodyHasMore/
        // filterGovMembers helpers in nss-config.js (loaded by every
        // page). Only this modal-open/close state is a local, faithful copy —
        // org-dashboard.js is its own Alpine component with no access to
        // dashboard.js's instance methods (no shared-include mechanism
        // between module JS files in this static frontend).
        govMemberCap: 9,
        govAllMembers: { open: false, body: null, filter: "" },
        corrRecent: [],
        corrCount: null,
        corrSectionLoading: false,

        /**
         * Render a count that may be unknown. Keeps a real 0 visible while
         * showing "—" for null, so a failed/unscoped fetch is never displayed
         * as a confident zero.
         */
        statNum(v, truncated = false) {
            if (v === null || v === undefined) return "—";
            return truncated ? `${v}+` : String(v);
        },

        async init(orgPk) {
            if (!orgPk) {
                this.error = "No organization specified.";
                this.loading = false;
                return;
            }

            this.loading = true;
            this.error = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/organization/organizations/${orgPk}`);
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.org = await res.json();
                await this._loadTierData();
                // Tier 6 sections load independently (own loading flags) so
                // they never block the main card render. Fired after this.org
                // is set; each re-runs on org switch via the remount above.
                this._loadGovernanceSection();
                this._loadCorrespondenceSection();
                this._loadAttendanceCard();
            } catch (err) {
                this.error = err.message || "Failed to load organization.";
            } finally {
                this.loading = false;
            }
        },

        // ── Tier helpers ───────────────────────────────────

        get orgTypeCode() {
            return this.org?.organization_type_code || "";
        },
        get isSakha() { return this.orgTypeCode === "SAKHA_SANGHA"; },
        get isAnchalika() { return this.orgTypeCode === "ANCHALIKA_SANGHA"; },
        get isZilla() { return this.orgTypeCode === "ZILLA_SANGHA"; },
        get isKendra() { return this.orgTypeCode === "KENDRA"; },
        get isPathaChakra() { return this.orgTypeCode === "PATHA_CHAKRA"; },
        get isMahila() { return this.orgTypeCode === "MAHILA_SANGHA"; },
        get isChildOverviewTier() { return this.isAnchalika || this.isZilla; },

        // Sakha "Members" split (Sakha tier ONLY — deliberately not exposed
        // on Anchalika/Zilla/Kendra, which roll up member counts across many
        // Sakhas via childStats; mixing in cross-Sakha Darshak attendance
        // there would double-count the same person under two different
        // Sakhas and inflate the broader dashboards' totals).
        //
        // sakhaMemberTotal (from /membership/members?org_code=…) is every
        // active sangha_sevi whose HOME org is this Sakha, with no
        // membership_type filter — so it already includes this Sakha's own
        // PROBATIONARY ("Darshaka") home members alongside its REGULAR/
        // ASSOCIATE/HONORARY ones. A Parichay Patra is issued to every
        // membership_type EXCEPT PROBATIONARY (value_name "Darshaka" — see
        // MEMBERSHIP_TYPE seed), so subtracting darshak.home_probationary_count
        // yields the true card-holder count with no extra query.
        get parichayPatraHolderCount() {
            if (this.sakhaMemberTotal === null) return null;
            return this.sakhaMemberTotal - (this.darshak.home_probationary_count || 0);
        },

        // Visiting Darshaks: members whose Parichay Patra home Sakha is a
        // DIFFERENT organization, currently attending this Sakha — the
        // darshak-summary endpoint's attending_from_other_sakha_count.
        // Explicitly NOT the same as home_probationary_count (this Sakha's
        // own not-yet-confirmed members), which stays in the existing
        // Darshak card unchanged.
        get visitingDarshakCount() {
            return this.darshak.attending_from_other_sakha_count ?? null;
        },

        // Sakha "Darshaks" tile (Sakha tier ONLY): BOTH Darshak flavours —
        // this Sakha's own not-yet-confirmed PROBATIONARY entrants
        // (home_probationary_count) PLUS Parichay Patra holders whose home is
        // a DIFFERENT Sakha but who attend here (attending_from_other_sakha_count).
        get sakhaDarshakTotal() {
            return (this.darshak.home_probationary_count || 0)
                 + (this.darshak.attending_from_other_sakha_count || 0);
        },

        // Sakha "Total Members" (Sakha tier ONLY): everyone who counts as
        // attending THIS Sakha — its home card-holders + its home Darshaks
        // (both already inside sakhaMemberTotal, which is home-scoped by
        // org_code) PLUS visiting Darshaks whose Parichay Patra home is
        // another Sakha. So: parichay holders + home probationary + visiting.
        //
        // Deliberately DIFFERENT from the broad Kendra/Anchalika/Zilla tiers,
        // whose member totals are home-based (childStats.member_count) and
        // exclude visitors — adding cross-Sakha attendance there would count
        // the same person under two Sakhas and inflate the rollup. On a single
        // Sakha's own dashboard the visitor headcount is the point ("how many
        // are attending this Sangha"), so it belongs here and only here.
        get sakhaTotalMembers() {
            if (this.sakhaMemberTotal === null) return null;
            return this.sakhaMemberTotal
                 + (this.darshak.attending_from_other_sakha_count || 0);
        },

        // A Mahila Sangha hangs off either a Kendra (the central Mahila
        // Sangha) or a Sakha Sangha (a local one) — see
        // _ALLOWED_PARENT_TYPES in api/routers/organization.py. The tier
        // shows which, because the Parichalana Mandali's remit differs.
        get isCentralMahila() {
            return this.isMahila && this.org?.parent_organization_type_code === "KENDRA";
        },

        async _loadTierData() {
            if (this.isSakha) return this._loadSakhaData();
            if (this.isChildOverviewTier) return this._loadChildOrgData();
            if (this.isKendra) return this._loadKendraData();
            if (this.isPathaChakra) return this._loadPathaChakraData();
            // Mahila Sangha: there is no mahila module and no governance
            // tables in the DDL yet (00_bootstrap..07_administration), so its
            // Mandali membership/office-bearer widgets are honest placeholders
            // over the org identity init() already loaded.
        },

        // ── Sakha tier data ────────────────────────────────

        async _loadSakhaData() {
            const orgPk = this.org.organization_pk;
            const code = this.org.organization_code;

            // /membership/members can only be filtered by org_code. There is
            // deliberately NO fallback to org_type_code=SAKHA_SANGHA here: that
            // returns every Sakha member in the system, which was then
            // displayed as this one Sakha's member count. With no code there is
            // no way to scope the query, so the count stays null and the card
            // renders "—".
            const memberQs = code ? `org_code=${encodeURIComponent(code)}` : null;

            const FAMILY_LIMIT = 500;
            const [memberRes, familyRes, recentRes, darshakRes] = await Promise.all([
                memberQs
                    ? NSSAuth.apiFetch(`/api/v1/membership/members?${memberQs}&limit=1`)
                        .then(r => r.ok ? r.json() : null).catch(() => null)
                    : Promise.resolve(null),
                NSSAuth.apiFetch(`/api/v1/family/families?sakha_organization_pk=${orgPk}&limit=${FAMILY_LIMIT}`)
                    .then(r => r.ok ? r.json() : null).catch(() => null),
                memberQs
                    ? NSSAuth.apiFetch(`/api/v1/membership/members?${memberQs}&limit=5&sort_by=joining_date&sort_dir=desc`)
                        .then(r => r.ok ? r.json() : { members: [] }).catch(() => ({ members: [] }))
                    : Promise.resolve({ members: [] }),
                NSSAuth.apiFetch(`/api/v1/membership/organizations/${orgPk}/darshak-summary`)
                    .then(r => r.ok ? r.json() : null).catch(() => null),
            ]);

            // null (request failed / not permitted) is kept distinct from 0 so
            // a permission failure shows "—" rather than a confident zero.
            this.sakhaMemberTotal = memberRes ? (memberRes.total || 0) : null;

            // /family/families returns a bare list with no total, so this is a
            // page length, not a COUNT. Flag when it saturates the limit so the
            // card can show "500+" instead of a wrong exact figure.
            if (Array.isArray(familyRes)) {
                this.sakhaFamilyTotal = familyRes.length;
                this.sakhaFamilyTruncated = familyRes.length >= FAMILY_LIMIT;
            } else {
                this.sakhaFamilyTotal = null;
                this.sakhaFamilyTruncated = false;
            }

            this.recentMembers = recentRes.members || [];
            if (darshakRes) this.darshak = darshakRes;
        },

        // ── Anchalika / Zilla tier data ────────────────────

        async _loadChildOrgData() {
            const orgPk = this.org.organization_pk;
            const [childRes, statsRes] = await Promise.all([
                NSSAuth.apiFetch(`/api/v1/organization/organizations/${orgPk}/children-stats`)
                    .then(r => r.ok ? r.json() : []).catch(() => []),
                // Org-scoped totals (renewals due for Zilla, Mahila Sangha
                // count for Anchalika) for THIS org's subtree specifically —
                // not the viewer's own admin scope, which is what
                // /admin/dashboard-stats answers and would be wrong for a
                // drill-down into someone else's org. See OrgStatsResponse's
                // docstring (api/schemas/organization.py).
                NSSAuth.apiFetch(`/api/v1/organization/organizations/${orgPk}/stats`)
                    .then(r => r.ok ? r.json() : null).catch(() => null),
            ]);
            this.childStats = childRes;
            this.renewalsDue = statsRes ? (statsRes.renewals_due ?? null) : null;
            this.mahilaCount = statsRes ? (statsRes.mahila_sanghas ?? null) : null;

            // Membership split for this Anchalika/Zilla's subtree — same
            // single /stats call, no extra round trip. Home-based like
            // member_count, so it excludes Parichay Patra holders whose home
            // Sakha is elsewhere and who only attend here as Darshaks
            // (the Sakha tier is the only tier that adds those in).
            this.parichayPatraTotal = statsRes ? (statsRes.parichay_patra_holders ?? null) : null;
            this.darshakTotal = statsRes ? (statsRes.darshaks ?? null) : null;
            this.orgAttendancePct = statsRes ? (statsRes.attendance_pct ?? null) : null;
            this.orgAttendanceTracked = statsRes ? !!statsRes.attendance_tracked : false;
        },

        // ── Kendra tier data ───────────────────────────────

        async _loadKendraData() {
            const orgPk = this.org.organization_pk;
            const [childRes, statsRes] = await Promise.all([
                NSSAuth.apiFetch(`/api/v1/organization/organizations/${orgPk}/children-stats`)
                    .then(r => r.ok ? r.json() : []).catch(() => []),
                // Org-scoped COUNT(*)s for THIS Kendra's subtree — replaces
                // /admin/dashboard-stats (viewer-scoped, wrong for a Kendra
                // admin drilling into a peer Kendra) and the earlier
                // `/organizations?type_code=…&limit=500` calls, which were
                // both globally unscoped AND silently capped at MAX_LIMIT.
                NSSAuth.apiFetch(`/api/v1/organization/organizations/${orgPk}/stats`)
                    .then(r => r.ok ? r.json() : null).catch(() => null),
            ]);
            this.childStats = childRes;
            this.sakhaCount = statsRes ? (statsRes.sakha_sanghas ?? null) : null;
            this.mahilaCount = statsRes ? (statsRes.mahila_sanghas ?? null) : null;

            // Per-type constituent-body counts + the members split. All come
            // from the same single /stats call already being made above — no
            // extra round trip. null (request failed / not permitted) stays
            // distinct from a real 0 so statNum() renders "—".
            this.parichayPatraTotal = statsRes ? (statsRes.parichay_patra_holders ?? null) : null;
            this.darshakTotal   = statsRes ? (statsRes.darshaks ?? null) : null;
            this.orgAttendancePct = statsRes ? (statsRes.attendance_pct ?? null) : null;
            this.orgAttendanceTracked = statsRes ? !!statsRes.attendance_tracked : false;
            this.anchalikaCount = statsRes ? (statsRes.anchalika_sanghas ?? null) : null;
            this.zillaCount     = statsRes ? (statsRes.zilla_sanghas ?? null) : null;
            this.pathaChakraCount = statsRes ? (statsRes.patha_chakras ?? null) : null;
            this.paribarikCount = statsRes ? (statsRes.paribarik_sanghas ?? null) : null;
            this.kumariCount    = statsRes ? (statsRes.kumari_sanghas ?? null) : null;
            this.sevakCount     = statsRes ? (statsRes.sevak_sanghas ?? null) : null;
        },

        // ── Patha Chakra tier data ─────────────────────────

        async _loadPathaChakraData() {
            const orgPk = this.org.organization_pk;
            // A Patha Chakra sits directly under a Kendra and is a LEAF type:
            // _ALLOWED_PARENT_TYPES (api/routers/admin.py) never names
            // PATHA_CHAKRA as an allowed parent, so it can hold no child orgs,
            // and members may only attach to a Sakha Sangha
            // (require_sakha_organization in api/helpers.py). Its /stats
            // subtree is therefore always itself alone and the membership
            // figures are a structural zero, not "nobody registered yet" —
            // which is exactly what the note beside the tiles says. The call
            // is still made rather than hard-coding 0, so the tiles report
            // whatever the server actually computes (and show "—" if the
            // request is not permitted).
            const statsRes = await NSSAuth.apiFetch(`/api/v1/organization/organizations/${orgPk}/stats`)
                .then(r => r.ok ? r.json() : null).catch(() => null);
            this.parichayPatraTotal = statsRes ? (statsRes.parichay_patra_holders ?? null) : null;
            this.darshakTotal = statsRes ? (statsRes.darshaks ?? null) : null;
        },

        // ── Derived totals (Anchalika/Zilla/Kendra child table) ──

        get childMemberTotal() {
            return this.childStats.reduce((sum, c) => sum + (c.member_count || 0), 0);
        },
        get childFamilyTotal() {
            return this.childStats.reduce((sum, c) => sum + (c.family_count || 0), 0);
        },
        get largestChild() {
            if (this.childStats.length === 0) return null;
            return this.childStats.reduce((a, b) => (b.member_count > a.member_count ? b : a));
        },
        get smallestChild() {
            if (this.childStats.length === 0) return null;
            return this.childStats.reduce((a, b) => (b.member_count < a.member_count ? b : a));
        },

        // "Total Members" for every non-Sakha tier (Kendra, Anchalika, Zilla):
        // the two parts from /stats when available, so the headline figure and
        // the Parichay Patra / Darshak tiles beside it always agree. Falls back
        // to summing childStats (same home-based definition, different
        // endpoint) if /stats was not permitted. Kept separate from the Sakha
        // tier's sakhaTotalMembers, which deliberately ALSO adds visiting
        // Parichay Patra holders from other Sakhas.
        get orgMemberTotal() {
            if (this.parichayPatraTotal !== null && this.darshakTotal !== null) {
                return this.parichayPatraTotal + this.darshakTotal;
            }
            return this.childMemberTotal;
        },

        formatDate(d) {
            return NSS.formatDate(d);
        },

        // ── Tier 6: Governance section ─────────────────────
        // Permissions are read from the cached /auth/me payload (NSSAuth) so
        // this nested component is host-agnostic (dashboard.js exposes `user`,
        // admin.js exposes `currentUser` — both are mirrored into the cache).
        _cachedPerms() {
            return (NSSAuth.getCachedUser() || {}).permissions || [];
        },
        get canSeeGovernance() {
            const p = this._cachedPerms();
            return p.includes("GOVERNANCE_VIEW") || p.includes("GOVERNANCE_MANAGE");
        },
        get canSeeCorrespondence() {
            const p = this._cachedPerms();
            return p.includes("CORRESPONDENCE_VIEW") || p.includes("CORRESPONDENCE_MANAGE");
        },
        get canSeeAttendance() {
            const p = this._cachedPerms();
            return p.includes("ATTENDANCE_VIEW") || p.includes("ATTENDANCE_MANAGE");
        },

        // Sakha-tier attendance card (owner ask 2026-10-27, Review
        // Workflow §22 "Sakha Dashboard may display Attendance
        // percentage, Watch List"). Kendra-level aggregation (§23) is not
        // built in this pass — /attendance/stats/organizations/{pk} is
        // per-org only, no NSS-wide rollup endpoint exists yet.
        attendanceStats: null, attendanceWatchListCount: null,
        // Darshak (Visitors) box (owner ask 2026-10-27, demo-matched) —
        // cross-Sakha attendees at this Sakha's MOST RECENT Weekly Sangha
        // Puja (is_darshak=true on /attendance/records, same flag the
        // admin Mark Attendance panel's own Darshak section uses).
        attendanceLatestPuja: null, attendanceDarshaks: [],
        darshakShowAll: false,  // show-more (owner ask 2026-10-28): 5 rows by default

        // Top Attendance (top 5) / Full Attendance (all) — owner ask
        // 2026-10-28, revised 2026-10-28: ONE member list
        // (GET /attendance/stats/organizations/{pk}/members?limit=500,
        // sorted highest % first) backs both presentations — no separate
        // fetch for the full page. Each member carries recent_statuses
        // (last 3 puja attendances, most recent first) and latest_remarks
        // (the latest puja's own remark only), so both tables can share
        // identical columns: ID/Name/Type/Status/Remarks/Attendance %.
        attendanceAllMembers: [],
        get attendanceTopMembers() {
            return (this.attendanceAllMembers || []).slice(0, 5);
        },

        // "View Full Attendance" (owner correction 2026-10-28: "should
        // open in the same page with same left bar, top bar, all same")
        // — an in-flow section within this SAME org-dashboard view (NOT a
        // fixed/full-screen overlay, which was hiding the surrounding
        // sidebar/topbar), toggled in place of the normal Sakha-tier
        // content below. Data is already loaded, so opening it is instant.
        attFullView: false,
        attFullSearch: "",

        openFullAttendance() { this.attFullView = true; this.attFullSearch = ""; },
        closeFullAttendance() { this.attFullView = false; },

        // Full Attendance's search box (owner ask 2026-10-28: "search box
        // taking 2 min inputs") — filters the already-loaded member list
        // client-side by name / Sangha Sevi ID / local Sakha number, once
        // at least 2 characters are typed; same 2-char threshold the
        // shared register's own searchAttMarkMember() uses.
        attFullFilteredMembers() {
            const q = (this.attFullSearch || "").trim().toLowerCase();
            if (q.length < 2) return this.attendanceAllMembers;
            return (this.attendanceAllMembers || []).filter(m =>
                (m.person_name || "").toLowerCase().includes(q) ||
                (m.sangha_sevi_id || "").toLowerCase().includes(q) ||
                (m.local_sakha_erp_id || "").toLowerCase().includes(q)
            );
        },

        // Status column (owner correction 2026-10-28: "the status is last
        // 3 attendance") — up to 3 real puja outcomes, most recent first,
        // each coloured by what actually happened that week (not a fixed
        // P/A/L legend with one entry highlighted). Padded to exactly 3
        // slots so columns stay aligned when a member has less history.
        attRecentPadded(m) {
            const arr = (m.recent_statuses || []).slice(0, 3);
            while (arr.length < 3) arr.push(null);
            return arr;
        },
        attStatusLetterFor(code) {
            return { PRESENT: "P", ABSENT: "A", EXCUSED_ABSENCE: "L" }[code] || "?";
        },
        attStatusBadgeClassFor(code) {
            return { PRESENT: "badge-att-present", ABSENT: "badge-att-absent", EXCUSED_ABSENCE: "badge-att-excused_absence" }[code] || "badge-muted";
        },

        async _loadAttendanceCard() {
            this.attendanceStats = null;
            this.attendanceWatchListCount = null;
            this.attendanceLatestPuja = null;
            this.attendanceDarshaks = [];
            this.darshakShowAll = false;
            this.attendanceAllMembers = [];
            this.attFullView = false;
            this.attFullSearch = "";
            if (!this.org || !this.isSakha || !this.canSeeAttendance) return;
            try {
                // 3 calls: org stats, records (for the Darshak box + latest
                // puja), and the full member leaderboard (Top Attendance
                // card slices its own top 5 off this same list — no second
                // fetch when "View Full Attendance" opens).
                const [statsRes, recRes, membersRes] = await Promise.all([
                    NSSAuth.apiFetch(`/api/v1/attendance/stats/organizations/${this.org.organization_pk}`)
                        .then(r => r.ok ? r.json() : null).catch(() => null),
                    NSSAuth.apiFetch(`/api/v1/attendance/records?organization_pk=${this.org.organization_pk}&page_size=200`)
                        .then(r => r.ok ? r.json() : null).catch(() => null),
                    NSSAuth.apiFetch(`/api/v1/attendance/stats/organizations/${this.org.organization_pk}/members?limit=500`)
                        .then(r => r.ok ? r.json() : null).catch(() => null),
                ]);
                this.attendanceStats = statsRes;
                this.attendanceAllMembers = (membersRes && membersRes.members) || [];
                const records = (recRes && recRes.records) || [];
                if (records.length) {
                    const latestPk = records[0].weekly_sangha_puja_pk;
                    this.attendanceLatestPuja = { weekly_sangha_puja_pk: latestPk, puja_date: records[0].puja_date, sakha_name: records[0].attendance_sakha_name };
                    // Three-way Darshak classification (owner-confirmed
                    // 2026-10-27):
                    //   1. HOME  — attending their OWN Sakha, Probationary.
                    //      Labelled "Darshak" (not "New Visitor" — a known
                    //      Probationary member of this very Sakha).
                    //   2. OTHER — an ACTIVE+APPROVED darshak_attendance_
                    //      registration exists for this member at THIS
                    //      Sakha (the formal three-step-approved cross-Sakha
                    //      arrangement, membership tab's "Apply for
                    //      Darshak") — the real signal, not a bare
                    //      home-Sakha-mismatch guess.
                    //   3. NEW   — everything else still darshak-worthy
                    //      (cross-Sakha without that approval, i.e. a
                    //      casual/unregistered visitor).
                    this.attendanceDarshaks = records
                        .filter(r => r.weekly_sangha_puja_pk === latestPk)
                        .filter(r => r.is_darshak || r.membership_type_code === "PROBATIONARY" || r.has_approved_darshak_registration)
                        .map(r => {
                            let darshak_type;
                            if (!r.is_darshak && r.membership_type_code === "PROBATIONARY") darshak_type = "HOME";
                            else if (r.has_approved_darshak_registration) darshak_type = "OTHER";
                            else darshak_type = "NEW";
                            return { ...r, darshak_type };
                        });
                }
            } catch (e) {
                console.error("Failed to load attendance card", e);
            }
        },

        // Footer counts for the demo-style Darshak card.
        get darshakHomeCount() {
            return (this.attendanceDarshaks || []).filter(d => d.darshak_type === "HOME").length;
        },
        get darshakNewVisitorCount() {
            return (this.attendanceDarshaks || []).filter(d => d.darshak_type === "NEW").length;
        },
        get darshakOtherSakhaCount() {
            return (this.attendanceDarshaks || []).filter(d => d.darshak_type === "OTHER").length;
        },

        // Single source of truth for the Darshak card's badge class/label —
        // used by both dashboard.html's and admin.html's org-dashboard
        // embeds so the three-way rule isn't duplicated in markup.
        // Reverted 2026-10-28 (owner correction — "keep the original
        // green, blue for visitor and other sakha"): back to three
        // distinct colours (teal/green/blue), not one shared amber.
        darshakTypeBadgeClass(type) {
            return { HOME: "badge-darshak-home", OTHER: "badge-darshak-other", NEW: "badge-darshak-new" }[type] || "badge-muted";
        },
        darshakTypeLabel(type) {
            return { HOME: "Darshak", OTHER: "Other Sakha", NEW: "New Visitor" }[type] || type;
        },

        // Show-more (owner ask 2026-10-28): 5 rows by default.
        darshakVisibleRows() {
            return this.darshakShowAll ? this.attendanceDarshaks : this.attendanceDarshaks.slice(0, 5);
        },

        async _loadGovernanceSection() {
            this.govBodies = [];
            if (!this.org) return;
            // Kendra's governing bodies (Kendra Governing Body, Advisory Board,
            // central Mahila Parichalana Mandali) are NSS-wide singletons
            // (body_master.organization_pk IS NULL), so the per-org admin
            // /bodies?organization_pk= filter (exact-match, excludes NULL) can
            // never return them. They come from the login-only
            // /public/national-bodies panel instead — composition already
            // assembled, visible to every member, no GOVERNANCE_VIEW needed.
            //
            // Every other tier's governing body is org-scoped (anchored on the
            // org's own organization_pk: Sakha/Anchalika/Zilla/Patha Chakra
            // governing bodies and the LOCAL Mahila Parichalana Mandali), read
            // via the per-org admin endpoint which is gated on GOVERNANCE_VIEW.
            // A central Mahila Sangha's Mandali is NSS-wide, so the org-scoped
            // path returns nothing for it (it surfaces on the Kendra dashboard
            // instead) — deliberately rendered empty rather than fabricated.
            if (this.isKendra) return this._loadGovernanceNssWide();
            if (!this.canSeeGovernance) return;
            return this._loadGovernanceOrgScoped();
        },

        async _loadGovernanceNssWide() {
            this.govSectionLoading = true;
            try {
                const [bodiesRes, openRes] = await Promise.all([
                    NSSAuth.apiFetch("/api/v1/governance/public/national-bodies")
                        .then(r => r.ok ? r.json() : null).catch(() => null),
                    NSSAuth.apiFetch("/api/v1/governance/elections/open-for-voting")
                        .then(r => r.ok ? r.json() : null).catch(() => null),
                ]);
                const openByBody = {};
                ((openRes && openRes.items) || []).forEach(e => { openByBody[e.body_master_pk] = e; });
                // Only the NSS-wide singletons (organization_pk IS NULL) belong
                // on the Kendra's central-administration dashboard; the viewer's
                // own Sakha body that national-bodies also returns is excluded.
                const nssWide = ((bodiesRes && bodiesRes.bodies) || []).filter(b => !b.organization_pk);
                this.govBodies = nssWide.map(b => ({
                    body_master_pk: b.body_master_pk,
                    body_name: b.body_name,
                    body_type_name: b.body_type_name,
                    // Carried through so the shared card can key its per-
                    // body-type colour (NSS.govBodyCardClass/Title/Button
                    // Class) — owner ask, 2026-10-24.
                    body_type_code: b.body_type_code,
                    body_status: b.body_status,
                    // Carried through for the shared governance-body card
                    // (GOV-BODY-CARD block) — it renders the member count,
                    // scope badge, owning org and per-member term dates, so
                    // nothing from the assembler's shape may be dropped here.
                    member_count: b.member_count,
                    scope_label: b.scope_label,
                    organization_name: b.organization_name,
                    members: (b.members || []).map(m => ({
                        position_name: m.position_name,
                        position_code: m.position_code,
                        person_name: m.person_name,
                        sangha_sevi_id: m.sangha_sevi_id,
                        sakha_name: m.sakha_name,
                        anchalika_zilla_name: m.anchalika_zilla_name,
                        effective_from: m.effective_from,
                        effective_to: m.effective_to,
                        // "Absent — Acting" indicator (owner ask #3, 2026-10-24).
                        acting_person_name: m.acting_person_name,
                    })),
                    liveElection: openByBody[b.body_master_pk] || null,
                }));
            } finally {
                this.govSectionLoading = false;
            }
        },

        async _loadGovernanceOrgScoped() {
            const orgPk = this.org.organization_pk;
            this.govSectionLoading = true;
            try {
                // page_size caps at 100 on this endpoint (NSS.MAX_PAGE_SIZE=500
                // would 422) — one org never has more than a handful of bodies.
                //
                // include_members=true makes this endpoint run the SAME
                // _assemble_bodies_with_members composition assembler that
                // /public/national-bodies uses, so the composition arrives in
                // the identical member shape (Sangha Sevi ID, Sakha,
                // Anchalika/Zilla, term dates) the shared governance-body card
                // renders. That replaced a per-body /bodies/{pk}/assignments
                // fetch (an N+1 whose AssignmentResponse carried none of those
                // fields) — owner request, 2026-10-23, uniform governance cards.
                const listRes = await NSSAuth.apiFetch(
                    `/api/v1/governance/bodies?organization_pk=${orgPk}&include_members=true&page_size=100`
                ).then(r => r.ok ? r.json() : null).catch(() => null);
                const bodies = (listRes && listRes.items) || [];
                this.govBodies = await Promise.all(bodies.map(async (b) => {
                    // Still per-body: the live-election badge has no bulk endpoint.
                    const electRes = await NSSAuth.apiFetch(
                        `/api/v1/governance/elections?body_master_pk=${b.body_master_pk}&election_status=VOTING&page_size=100`
                    ).then(r => r.ok ? r.json() : null).catch(() => null);
                    const liveElection = ((electRes && electRes.items) || [])[0] || null;
                    return {
                        body_master_pk: b.body_master_pk,
                        body_name: b.body_name,
                        body_type_name: b.body_type_name,
                        body_type_code: b.body_type_code,
                        body_status: b.body_status,
                        member_count: b.member_count,
                        scope_label: b.scope_label,
                        organization_name: b.organization_name,
                        members: b.members || [],
                        liveElection,
                    };
                }));
            } finally {
                this.govSectionLoading = false;
            }
        },

        // ── Governance body banner helpers (same pattern as dashboard.js's
        // Governance tab) — cap/sort/filter logic lives in nss-config.js
        // (NSS.govBodyDisplayMembers / govBodyHasMore / filterGovMembers)
        // so it is not duplicated here; only the modal state is local.
        govBodyDisplayMembers(b) {
            return NSS.govBodyDisplayMembers(b, this.govMemberCap);
        },
        govBodyHasMore(b) {
            return NSS.govBodyHasMore(b, this.govMemberCap);
        },
        openGovAllMembers(b) {
            this.govAllMembers = { open: true, body: b, filter: "" };
        },
        closeGovAllMembers() {
            this.govAllMembers = { open: false, body: null, filter: "" };
        },
        govAllMembersFiltered() {
            const b = this.govAllMembers.body;
            if (!b) return [];
            return NSS.filterGovMembers(b.members || [], this.govAllMembers.filter);
        },

        // ── Tier 6: Correspondence section ─────────────────
        // The correspondence register is admin-scoped (CORRESPONDENCE_VIEW +
        // admin scope on register_organization_pk). Gated client-side on the
        // permission so a member who could never load it does not see a broken
        // or erroring card. For a scoped admin viewing an org inside their
        // subtree the list returns that org's records; outside it the API
        // scope-filters to an empty list (not a 403), so no error surfaces.
        async _loadCorrespondenceSection() {
            this.corrRecent = [];
            this.corrCount = null;
            if (!this.org || !this.canSeeCorrespondence) return;
            const orgPk = this.org.organization_pk;
            this.corrSectionLoading = true;
            try {
                // page_size caps at 100 here too; 5 is plenty for a recent list.
                const res = await NSSAuth.apiFetch(
                    `/api/v1/correspondence?register_organization_pk=${orgPk}&page_size=5`
                ).then(r => r.ok ? r.json() : null).catch(() => null);
                if (res) {
                    this.corrRecent = res.items || [];
                    this.corrCount = res.total != null ? res.total : this.corrRecent.length;
                }
            } finally {
                this.corrSectionLoading = false;
            }
        },
    };
}
