/**
 * NSS ERP — Dashboard Page (Tier 5)
 *
 * Alpine.js component for the member dashboard.
 * Calls GET /api/v1/auth/me for user context + roles,
 * then fetches person, membership, and family data via existing APIs.
 *
 * Admin tabs are dynamically added based on role scopes.
 *
 * Family tree uses the /graph endpoint for dynamic relationship
 * computation — same logic as family.html but embedded inline.
 */

/* ── Admin tab definitions ─────────────────────────────────────
 * Maps role_code → tab metadata. Only roles present in the
 * user's scopes appear in the sidebar.
 */
const ADMIN_TAB_MAP = {
    NSS_ERP_ADMIN: {
        label: "System Administration",
        description: "Full system access — users, roles, settings",
        adminUrl: "/admin",
    },
    NSS_ERP_KENDRA_ADMIN: {
        label: "Kendra Management",
        description: "Manage Kendra-level operations and oversight",
        adminUrl: "/admin",
    },
    NSS_ERP_ANCHALIKA_ADMIN: {
        label: "Anchalika Management",
        description: "Manage Anchalika-level coordination",
        adminUrl: "/admin",
    },
    NSS_ERP_ZILLA_ADMIN: {
        label: "Zilla Management",
        description: "Manage Zilla-level operations",
        adminUrl: "/admin",
    },
    NSS_ERP_SAKHA_ADMIN: {
        label: "Sakha Management",
        description: "Manage Sakha members, attendance, and records",
        adminUrl: "/admin",
    },
    NSS_ERP_PATHA_CHAKRA_ADMIN: {
        label: "Patha Chakra Management",
        description: "Manage Patha Chakra sessions and curriculum",
        adminUrl: "/admin",
    },
    NSS_ERP_AUDITOR: {
        label: "Audit & Compliance",
        description: "View audit trails, compliance reports",
        adminUrl: "/admin",
    },
    NSS_ERP_REPORT_VIEWER: {
        label: "Reports",
        description: "Access membership and organizational reports",
        adminUrl: "/admin",
    },
};

// The Administration group's contents for a super admin, in fixed display
// order: Administrator, Audit, Reports. NSS_ERP_ADMIN is the super admin
// (is_super_admin() gives it unrestricted scope and its permission set is a
// strict superset of the two read-only SYSTEM roles), so these three are the
// only tabs that make sense for it — see _buildAdminTabs().
const SUPER_ADMIN_TAB_ORDER = [
    "NSS_ERP_ADMIN",
    "NSS_ERP_AUDITOR",
    "NSS_ERP_REPORT_VIEWER",
];

// Permissions that actually back the Registration Approvals view — the exact
// pair every /api/v1/claims endpoint requires via
// require_any_permission("MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE")
// (api/routers/claim_approval.py). Gating the nav item on the permission
// rather than on a role list means the link can never point at a 403.
const CLAIM_APPROVAL_PERMISSIONS = ["MEMBERSHIP_APPROVE", "ADMIN_USER_MANAGE"];

// Scoped-admin role_code -> the org-dashboard tab's tier label for that
// role's own org (role_code implies org type 1:1 — a Sakha admin's scope
// org is always a Sakha, etc.). Shared shape with admin.js's own copy (no
// cross-file include mechanism exists in this static frontend).
const ROLE_ORG_LABELS = {
    NSS_ERP_KENDRA_ADMIN: "Kendra Dashboard",
    NSS_ERP_ANCHALIKA_ADMIN: "Anchalika Dashboard",
    NSS_ERP_ZILLA_ADMIN: "Zilla Dashboard",
    NSS_ERP_SAKHA_ADMIN: "Sakha Dashboard",
    NSS_ERP_PATHA_CHAKRA_ADMIN: "Patha Chakra Dashboard",
    NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN: "Mahila Parichalana Mandali Dashboard",
};

// The org-dashboard tiers listed in the sidebar's "Dashboards" group, in
// hierarchy order — one per ORGANIZATIONAL role in role_master
// (SOL-ADMIN-004 §8.7). Duplicated from admin.js by necessity: this static
// frontend has no cross-file include mechanism. Keep the two in step.
//
// MAHILA_SANGHA carries the "Mahila Parichalana Mandali" label because the
// Mandali is that Sangha's governing body (MAH-091 — one body, two names),
// not an organization type of its own.
const DASHBOARD_LEVELS = [
    { typeCode: "KENDRA", label: "Kendra" },
    { typeCode: "ANCHALIKA_SANGHA", label: "Anchalika" },
    { typeCode: "ZILLA_SANGHA", label: "Zilla" },
    { typeCode: "SAKHA_SANGHA", label: "Sakha" },
    { typeCode: "PATHA_CHAKRA", label: "Patha Chakra" },
    { typeCode: "MAHILA_SANGHA", label: "Mahila Parichalana Mandali" },
];

/* ── Tab labels for top bar ────────────────────────────────── */
const TAB_LABELS = {
    personal: "Personal Information",
    membership: "Membership Details",
    family: "Family",
    attendance: "Attendance",
    governance: "Governance",
    documents: "Documents",
};

/* ── Roles that get the org-level family browser ──────────── */
const FAMILY_BROWSER_ROLES = new Set([
    "NSS_ERP_ADMIN", "NSS_ERP_KENDRA_ADMIN",
    "NSS_ERP_ANCHALIKA_ADMIN", "NSS_ERP_ZILLA_ADMIN",
    "NSS_ERP_SAKHA_ADMIN",
]);

/* ── The five organizational admin-tab roles (Kendra/Anchalika/Zilla/
 * Sakha/Patha Chakra Management) — distinct from the three fixed SYSTEM
 * roles (NSS_ERP_ADMIN/NSS_ERP_AUDITOR/NSS_ERP_REPORT_VIEWER). Used to
 * gate the "pending approvals in your org" panel, which only makes sense
 * for a role anchored to one organization's subtree. */
const ORG_LEVEL_ADMIN_ROLES = new Set([
    "NSS_ERP_KENDRA_ADMIN", "NSS_ERP_ANCHALIKA_ADMIN", "NSS_ERP_ZILLA_ADMIN",
    "NSS_ERP_SAKHA_ADMIN", "NSS_ERP_PATHA_CHAKRA_ADMIN",
]);

/* ── Family tree constants (ported from family.js) ──────────── */
const SPOUSE_LABELS = new Set(["Husband", "Wife"]);
const PARENT_LABELS = new Set(["Father", "Mother", "Step-Father", "Step-Mother"]);
const GEN_LABELS = {
    "-3": "Great-Grandparents",
    "-2": "Grandparents",
    "-1": "Parents",
    "0":  "Self & Siblings",
    "1":  "Children",
    "2":  "Grandchildren",
    "3":  "Great-Grandchildren",
};

function _avatarClass(gen, isHead, isSpouse) {
    if (isSpouse)  return "av-spouse";
    switch (gen) {
        case -2: return "av-grandparent";
        case -1: return "av-parent";
        case 0:  return "av-sibling";
        case 1:  return "av-child";
        case 2:  return "av-grandchild";
        default: return "av-other";
    }
}

// Shared by the Family tab (this.treeNodes) and the Family-of-Origin org
// browser (this.orgTreeNodes) — was previously duplicated wholesale in
// both places. Builds the couple-tree structure from a flat array of
// person-like nodes (person_pk, spouse_person_pk, generation,
// parent_person_pks): pairs each person with their spouse, links parent →
// child-couple, then grafts any orphaned couple (no parent found in this
// dataset) onto a matching generation elsewhere in the tree, so an in-law
// never floats to the top as a spurious extra root.
function _buildCoupleTree(allPersons) {
    const personMap = new Map();
    for (const p of allPersons) personMap.set(p.person_pk, p);

    const usedInCouple = new Set();
    const coupleMap = new Map();
    const allCouples = [];

    for (const p of allPersons) {
        if (usedInCouple.has(p.person_pk)) continue;
        usedInCouple.add(p.person_pk);
        let spouse = null;
        if (p.spouse_person_pk) {
            const s = personMap.get(p.spouse_person_pk);
            if (s && !usedInCouple.has(s.person_pk)) {
                spouse = s;
                usedInCouple.add(s.person_pk);
            }
        }
        if (!spouse) {
            for (const s of allPersons) {
                if (s.spouse_person_pk === p.person_pk && !usedInCouple.has(s.person_pk)) {
                    spouse = s;
                    usedInCouple.add(s.person_pk);
                    break;
                }
            }
        }
        const couple = {
            couple: !!spouse,
            members: spouse ? [p, spouse] : [p],
            children: [],
            gen: p.generation,
        };
        for (const m of couple.members) coupleMap.set(m.person_pk, couple);
        allCouples.push(couple);
    }

    // Parent → child-couple map
    const childCouplesOf = new Map();
    const rootCouples = [];
    for (const c of allCouples) {
        let parentCouple = null;
        for (const m of c.members) {
            for (const ppk of (m.parent_person_pks || [])) {
                const pc = coupleMap.get(ppk);
                if (pc && pc !== c) { parentCouple = pc; break; }
            }
            if (parentCouple) break;
        }
        if (parentCouple) {
            if (!childCouplesOf.has(parentCouple)) childCouplesOf.set(parentCouple, []);
            childCouplesOf.get(parentCouple).push(c);
        } else {
            rootCouples.push(c);
        }
    }

    function attach(node) {
        const kids = childCouplesOf.get(node) || [];
        kids.sort((a, b) => (a.members[0].first_name || "").localeCompare(b.members[0].first_name || ""));
        node.children = kids;
        for (const kid of kids) attach(kid);
    }
    for (const root of rootCouples) attach(root);

    // Orphan rescue: if an orphan couple's generation matches a
    // non-root level, graft it as a sibling at that level.
    // This prevents in-laws from floating to the top of the tree.
    if (rootCouples.length > 1) {
        const minGen = Math.min(...rootCouples.map(c => c.gen));
        const trueRoots = [];
        const orphans = [];
        for (const c of rootCouples) {
            if (c.gen <= minGen) trueRoots.push(c);
            else orphans.push(c);
        }
        // For each orphan, find a parent-level couple in the tree
        // and graft the orphan as their child
        for (const orphan of orphans) {
            const targetGen = orphan.gen - 1;
            let grafted = false;
            // BFS through tree to find a couple at targetGen
            const bfsQueue = [...trueRoots];
            while (bfsQueue.length > 0 && !grafted) {
                const node = bfsQueue.shift();
                if (node.gen === targetGen) {
                    node.children.push(orphan);
                    grafted = true;
                }
                for (const kid of (node.children || [])) bfsQueue.push(kid);
            }
            if (!grafted) trueRoots.push(orphan); // fallback: keep as root
        }
        return trueRoots;
    }
    return rootCouples;
}


function dashboardApp() {
    // NSSAttendanceRegister.install() adds the shared attendance-register
    // members (permission getters, roster rows, tallies, filter,
    // search-to-add, submit) that the Administration > Attendance tab and
    // this dashboard's own Attendance Register nav tab both run — see
    // assets/js/attendance-register.js. install() never overwrites a
    // property defined below, which is how `_afterAttendanceSaved` wins.
    return NSSAttendanceRegister.install({
        // ── Shared layout (sidebar toggle, topbar user info) ──
        ...NSSLayout.mixin(),

        // ── State ─────────────────────────────────────────
        loading: true,
        error: "",
        tab: sessionStorage.getItem('nss_dashboard_tab') || "personal",

        // Core data
        user: {},       // from /me
        person: {},     // from /person/persons/{pk}
        member: {},     // from /membership/search
        addresses: [],  // from /person/persons/{pk}/addresses

        // Membership sub-data
        affiliations: [],
        parichayaPatras: [],
        anumatiPatras: [],
        journeyEvents: [],

        // Family data
        family: null,           // FamilyGroupResponse (primary family)
        ownFamily: null,        // User's own family (preserved for "Back" navigation)
        familyMembers: [],      // FamilyMemberResponse[]
        familyHeadHistory: [],  // FamilyHeadHistoryResponse[]
        familyAdmins: [],       // FamilyAdminResponse[] (current admins)
        familyMemberSummaries: {},  // { person_pk: PersonMembershipSummaryResponse }
        familyLoading: false,

        // Family tree (graph)
        viewerPersonPk: null,
        graphMembers: [],
        graphLoading: false,
        graphError: false,
        treeHead: null,
        treeSpouse: null,
        treeNodes: [],
        _allTreePersons: [],

        // Selected person (clicked in tree or member list)
        selectedPerson: null,
        selectedPersonDetail: null,
        selectedPersonLoading: false,
        selectedPersonMembership: null,
        selectedPersonMembershipLoading: false,

        // Add member modal
        showAddMemberModal: false,
        addMemberSearch: "",
        addMemberSearching: false,
        addMemberResults: [],
        addMemberSearchTotal: 0,
        addMemberSelected: null,
        addMemberRelType: "",
        addMemberLinkType: "",
        addMemberLinkTarget: "",
        addMemberRemarks: "",
        addMemberSaving: false,
        addMemberError: "",
        _addMemberDebounce: null,
        addMemberInferredLinks: [],  // auto-inferred family_link edges
        addMemberInlawSpouse: "",       // for in-law: which existing member is the spouse connector
        addMemberInlawSpouseNotInTree: false,  // "Spouse not in Family Tree" toggle
        addMemberExistingFamilies: [],  // families the selected person already belongs to

        // Create family modal
        showCreateFamilyModal: false,
        createFamilyName: "",
        createFamilySakhaPk: "",
        createFamilyFormedDate: "",
        createFamilyRemarks: "",
        createFamilySubmitting: false,
        createFamilyError: "",
        createFamilySakhaList: [],
        createFamilySakhaLoading: false,
        // Geography filter for "find a Sakha near me" (SOL-ARCH-010
        // Amendment, 2026-10-01) — narrows createFamilySakhaList by
        // country/state/district instead of always showing every Sakha in
        // the system.
        createFamilyCountries: [],
        createFamilyStates: [],
        createFamilyDistricts: [],
        createFamilyCountryPk: "",
        createFamilyStatePk: "",
        createFamilyDistrictPk: "",

        // Membership Change Request modal (Sakha Transfer / Apply for
        // Darshak, MBR-048/MBR-049) — self-service, POST /api/v1/
        // membership/change-requests.
        showChangeRequestModal: false,
        changeRequestType: "",           // "TRANSFER" or "DARSHAK"
        changeRequestOrgPk: "",
        changeRequestReason: "",
        changeRequestSaving: false,
        changeRequestError: "",
        changeRequestSakhaList: [],
        changeRequestSakhaLoading: false,
        myChangeRequests: [],
        myChangeRequestsLoading: false,

        // Send Application tab — member self-service "Send Application"
        // with a real 2-step approval chain for the Kendra-via-Sakha-
        // President addressing mode (owner request 2026-10-21;
        // api/routers/correspondence.py's /my-applications,
        // /addressed-to-me and /approval-steps/* endpoints). Own top-level
        // nav tab (tab === 'sendApplication'), not nested in Membership.
        sendApp: {
            subTab: "create",
            form: {
                addressing_mode: "SAKHA_ORG",
                recipient_person_pk: "",
                subject: "",
                remarks: "",
                follow_up_date: "",
            },
            saving: false,
            error: "",
            sakhaOfficeBearers: [],
            kendraOfficeBearers: [],
            // Added 2026-10-25 (gender-gated Mahila/Sevak addressing modes):
            // local Mahila Parichalana Mandali, central (Kendra-level)
            // Mahila Parichalana Mandali, local Sevak Sangha. Split out of
            // sakhaOfficeBearers below instead of being silently lumped
            // into "a specific office-bearer of my Sakha".
            mahilaOfficeBearers: [],
            kendraMahilaOfficeBearers: [],
            sevakOfficeBearers: [],
            // In-flight guard only (not a one-time latch — see
            // _loadSendApplicationOfficeBearers()'s own comment, 2026-10-25
            // fix): every tab visit refetches fresh data.
            officeBearersLoading: false,
            officeBearersError: "",
            history: [],
            historyLoading: false,
            historyLoaded: false,
            expandedPk: null,
            pendingApprovals: [],
            decisionRemarks: {},
            deciding: false,
        },


        // Find a Sakha / Patha Chakra directory (member dashboard).
        // Both a browsable directory (unfiltered load on tab open, capped
        // at NSS.MAX_PAGE_SIZE) and a search — free-text over the loaded
        // page plus a country/state/district cascade that re-queries the
        // server (same public-safe /organizations/selectable endpoint
        // Create Family's Sakha picker uses — authenticated members only,
        // no ORGANIZATION_VIEW required).
        findOrgResults: [],
        findOrgLoading: false,
        findOrgError: "",
        findOrgQuery: "",
        findOrgIncludeSakha: true,
        findOrgIncludePathaChakra: true,
        findOrgCountries: [],
        findOrgStates: [],
        findOrgDistricts: [],
        findOrgCountryPk: "",
        findOrgStatePk: "",
        findOrgDistrictPk: "",
        // Per-Sakha President/Secretary (name + mobile), keyed by
        // organization_pk, from the public governance endpoint. Loaded once
        // with the directory and merged into rows client-side (no N+1).
        findOrgOfficeBearers: {},

        // ── Member Directory tab (owner-confirmed 2026-10-27): any
        // logged-in member may browse/search every active member NSS-wide
        // via GET /membership/directory — deliberately not admin-scoped
        // (unlike admin.html's Member Directory, which calls /search under
        // MEMBERSHIP_VIEW). Sakha filter reuses the SAME public
        // /organization/organizations/selectable?type_code=SAKHA_SANGHA
        // list findOrg already loads (findOrgCountries' sibling), loaded
        // once and cached here rather than refetched.
        memberDirResults: [],
        memberDirTotal: 0,
        memberDirLoading: false,
        memberDirError: "",
        memberDirQuery: "",
        memberDirSakhaPk: "",
        memberDirSakhas: [],
        memberDirLimit: 50,
        _memberDirDebounce: null,

        // ── Attendance tab (Tier 6, 2026-10-27) — the member's own
        // history + stats, self-access (no ATTENDANCE_VIEW needed since
        // sangha_sevi_pk === caller) ──
        myAttRecords: [], myAttRecordsLoading: false, myAttRecordsError: "",
        myAttStats: null, myAttStatsLoading: false, myAttStatsError: "",

        async _loadMyAttendance() {
            if (!this.member || !this.member.sangha_sevi_pk) return;
            await Promise.all([this._loadMyAttRecords(), this._loadMyAttStats()]);
        },

        async _loadMyAttRecords() {
            this.myAttRecordsLoading = true;
            this.myAttRecordsError = "";
            try {
                const params = new URLSearchParams({ sangha_sevi_pk: this.member.sangha_sevi_pk, page_size: "200" });
                const res = await NSSAuth.apiFetch(`/api/v1/attendance/records?${params}`);
                if (!res.ok) throw new Error("Failed to load your attendance history.");
                const data = await res.json();
                this.myAttRecords = data.records || [];
            } catch (e) {
                this.myAttRecordsError = e.message || "Failed to load your attendance history.";
                this.myAttRecords = [];
            } finally {
                this.myAttRecordsLoading = false;
            }
        },

        async _loadMyAttStats() {
            this.myAttStatsLoading = true;
            this.myAttStatsError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/attendance/stats/members/${this.member.sangha_sevi_pk}`);
                const data = await res.json();
                if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                this.myAttStats = data;
            } catch (e) {
                this.myAttStatsError = e.message || "Failed to load your attendance statistics.";
                this.myAttStats = null;
            } finally {
                this.myAttStatsLoading = false;
            }
        },

        // ── Attendance Register tab (owner ask 2026-10-28: "not in sakha
        // dashboard add it in member left nav bar") — a top-level nav tab
        // for a designated marker (ATTENDANCE_MANAGE, typically the
        // per-Sakha NSS_ERP_ATTENDANCE_MARKER role or a Sakha admin) to
        // record Weekly Sangha Puja attendance without any administration
        // access. The marking grid itself — roster, tallies, filter,
        // search-to-add, submit — is the SHARED NSSAttendanceRegister
        // mixin installed on this component, the very same code the
        // Administration > Attendance tab runs; only the puja list /
        // create form and the Sakha picker are specific to this tab.
        //
        // Previously lived as a launcher card inside the Sakha dashboard
        // (org-dashboard.js) — moved out entirely per the owner's
        // correction, since a marker who is not also a Sakha admin has no
        // reason to open that dashboard at all.
        //
        // Which Sakha: a marker's admin_scope is always SAKHA-scoped
        // (role_permission seeds ATTENDANCE_MANAGE only onto SAKHA_SANGHA-
        // scoped roles), so dashboardOrgsFor('SAKHA_SANGHA') — the same
        // helper the "Dashboards" sidebar group already uses — is exactly
        // the right candidate list. One Sakha auto-selects; more than one
        // (a marker or Sakha admin holding several) shows a picker.
        attRegSakhaPk: "",
        attRegPujas: [], attRegPujasLoading: false, attRegPujasError: "",
        attRegForm: { show: false, saving: false, error: "", puja_date: "", remarks: "" },

        get attRegSakhaOptions() {
            return this.dashboardOrgsFor("SAKHA_SANGHA");
        },

        _initAttendanceRegister() {
            const options = this.attRegSakhaOptions;
            // Keep the current selection if it is still valid (e.g.
            // revisiting the tab); otherwise default to the only option,
            // or clear it so the picker prompts a choice.
            if (!options.some(o => o.organization_pk === this.attRegSakhaPk)) {
                this.attRegSakhaPk = options.length === 1 ? options[0].organization_pk : "";
            }
            this.closeMarkAttendance();
            if (this.attRegSakhaPk) this.loadAttRegPujas();
            else { this.attRegPujas = []; this.attRegPujasError = ""; }
        },

        onAttRegSakhaChange() {
            this.closeMarkAttendance();
            this.attRegForm = { show: false, saving: false, error: "", puja_date: "", remarks: "" };
            if (this.attRegSakhaPk) this.loadAttRegPujas();
            else this.attRegPujas = [];
        },

        async loadAttRegPujas() {
            if (!this.attRegSakhaPk) return;
            this.attRegPujasLoading = true;
            this.attRegPujasError = "";
            try {
                const params = new URLSearchParams({ organization_pk: this.attRegSakhaPk, page_size: "50" });
                const res = await NSSAuth.apiFetch(`/api/v1/attendance/pujas?${params}`);
                if (!res.ok) throw new Error("Failed to load Weekly Sangha Puja events.");
                const data = await res.json();
                this.attRegPujas = data.pujas || [];
            } catch (e) {
                this.attRegPujasError = e.message || "Failed to load Weekly Sangha Puja events.";
                this.attRegPujas = [];
            } finally {
                this.attRegPujasLoading = false;
            }
        },

        async submitCreateAttRegPuja() {
            if (!this.attRegSakhaPk || !this.attRegForm.puja_date) return;
            this.attRegForm.saving = true;
            this.attRegForm.error = "";
            try {
                const res = await NSSAuth.apiFetch("/api/v1/attendance/pujas", {
                    method: "POST",
                    body: JSON.stringify({
                        sakha_pk: this.attRegSakhaPk,
                        puja_date: this.attRegForm.puja_date,
                        remarks: this.attRegForm.remarks || null,
                    }),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                this.attRegForm = { show: false, saving: false, error: "", puja_date: "", remarks: "" };
                await this.loadAttRegPujas();
                // Straight into marking the puja just created — that is
                // the only reason to create one.
                await this.openMarkAttendance(data);
            } catch (e) {
                this.attRegForm.error = e.message || "Failed to create the puja event.";
            } finally {
                this.attRegForm.saving = false;
            }
        },

        // Host hook for the shared register (assets/js/attendance-
        // register.js) — the puja list's own tallies just changed.
        _afterAttendanceSaved() {
            return this.loadAttRegPujas();
        },

        // ── Governance tab (read-only, all logged-in users) ──
        // 4 bodies: the 3 NSS-wide singletons + the viewer's own Sakha
        // Governing Body, each with current composition. Public endpoint,
        // no GOVERNANCE_VIEW required.
        govBodies: [],
        mySakhaBodies: [],           // item 4 — viewer's own Sakha GB + local Mahila PM
        govLoading: false,
        govError: "",
        govLoaded: false,
        govMemberCap: 9,             // item 9 — inline banners show at most 9 members
        // item 9 — Advisory "show all" modal: full member list + Sakha-name filter
        govAllMembers: { open: false, body: null, filter: "" },

        // Open elections — member self-service voting (GOV-BR-045)
        govOpenElections: [],
        govVotingLoading: false,
        govVotingError: "",
        govSelectedNomination: {},   // key: electionPk + '-' + positionPk -> election_nomination_pk
        govVoteSubmitting: {},       // key: electionPk + '-' + positionPk -> bool
        govVoteError: {},            // key: electionPk -> message
        govVoteSuccess: {},          // key: electionPk -> message

        // ── "Acting on My Behalf" delegation (owner asks #2/#3/#4) ──
        // A sitting office bearer may nominate another member of the SAME
        // body to act on their behalf in a position THEY hold. Everything
        // here is driven by GET /governance/me/positions (login-only, so a
        // plain member needs no GOVERNANCE_VIEW): it returns only the bodies
        // the caller holds office on, each already carrying that body's full
        // composition — which is the candidate radio list, so picking a body
        // costs no extra fetch. Both loaders fail soft: a non-office-bearer
        // simply ends up with empty arrays and the whole section is hidden
        // (myGovPositions.length > 0 guards it in dashboard.html).
        myGovPositions: [],          // GET /me/positions  -> bodies[] (+ my_positions, members)
        myGovDelegations: [],        // GET /me/acting-delegations (incl. ENDED, newest first)
        myGovDelegationsError: "",
        // Owner request, 2026-10-25: "there should be a history page for
        // on behalf also" — mirrors the Applications tab's own Create/
        // History sub-tab split (sendApp.subTab). "current" shows the
        // create-form + only-live rows; "history" shows only resolved
        // (ENDED/REJECTED) rows and hides the create-form, same as
        // Applications' History sub-tab hides Create Application.
        myGovDelegationsView: "current",
        // Admin-initiated acting assignments awaiting the caller's own
        // approval — rows where the caller is the NOMINEE, the opposite
        // axis from myGovDelegations (which is scoped by the caller's own
        // office-bearer seats). GET /me/pending-acting-approvals; reuses
        // ActingAssignmentResponse, the same shape admin.js's govActing
        // already uses — no new response model (Priority 1, 2026-10-24).
        myPendingActingApprovals: [],
        myPendingActingApprovalsError: "",
        // stage "form" -> "confirm": Assign never submits (owner ask #4), it
        // flips to a plain-language preview with Confirm / Back.
        //
        // 2026-10-24 (owner ask #1): one candidate table PER delegation slot
        // and every table mandatory, so the form no longer holds a single
        // (body, position, person) triple — it holds a SELECTIONS MAP,
        // slot.key -> chosen person_pk, where slot.key is
        // `${body_master_pk}|${my_position_master_pk}` (see
        // myGovDelegationSlots()). effective_from/effective_to/reason stay
        // single-valued: one date range and one reason apply to the whole
        // batch, matching the owner's single-confirmation-table framing.
        delegateForm: {
            stage: "form", saving: false, error: "",
            selections: {},
            effective_from: "", effective_to: "", reason: "",
        },

        // GOV-BR-043-A — Parichalak-only "probationary candidate exception"
        // nomination. is_parichalak comes from the server (single source of
        // truth: _resolve_current_parichalak_sangha_sevi_pk in
        // api/routers/governance.py) — never inferred client-side. The panel
        // this drives only ever appears inside the member's own Governance
        // tab, for whoever is actually, currently seated as Parichalak.
        isParichalak: false,
        parichalakExceptionForm: {
            show: false, saving: false, error: "", success: "",
            elections: [], electionsLoading: false, election_pk: "",
            positions: [], positionsLoading: false, position_master_pk: "",
            candidateQuery: "", candidateResults: [], candidateSearching: false, selectedCandidate: null,
            probationary_exception_reason: "",
        },
        _parichalakCandidateTimer: null,

        // Transfer Head modal — themed replacement for the plain confirm()
        transferHeadTarget: null,     // the member being made Head, or null = closed
        transferHeadSubmitting: false,
        transferHeadError: "",

        // Assign Admin modal — themed replacement for the plain confirm()
        assignAdminTarget: null,      // the member being made Admin, or null = closed
        assignAdminSubmitting: false,
        assignAdminError: "",

        // Remove member
        removeMemberLoading: false,

        // Edit profile
        editingProfile: false,
        profileForm: { mobile_number: "", country_phone_code: "", email: "", date_of_birth: "" },
        profileSaving: false,
        profileError: "",
        profileSuccess: "",

        // Active sessions (personal tab)
        sessions: [],
        sessionsLoading: false,
        sessionsError: "",

        // ── Org-level family browser (admin view) ────────
        orgFamilyBrowser: false,       // is the org family browser active?
        orgBreadcrumb: [],             // [{organization_pk, organization_name, organization_type_name, organization_code}]
        orgChildren: [],               // child org nodes at current level
        orgChildrenLoading: false,
        orgChildrenStats: {},          // {organization_pk: {family_count, member_count, person_count}}
        orgFamilies: [],               // families at current Sakha level
        orgFamiliesLoading: false,
        orgSelectedSakhaCode: null,    // when a Sakha is selected
        orgSelectedFamily: null,       // FamilyGroupResponse of the selected family
        orgFamilyMembers: [],          // members of the selected family
        orgFamilyHeadHistory: [],      // head history of the selected family
        orgFamilyLoading: false,
        orgGraphMembers: [],           // graph response for org-viewed family
        orgGraphLoading: false,
        orgGraphError: false,
        orgViewerPersonPk: null,       // viewer for the org tree ("View As")
        orgTreeHead: null,
        orgTreeSpouse: null,
        orgTreeNodes: [],
        _orgAllTreePersons: [],
        orgSelectedPerson: null,       // clicked person in org tree
        orgSelectedPersonDetail: null,
        orgSelectedPersonLoading: false,
        orgSelectedPersonMembership: null,
        orgSelectedPersonMembershipLoading: false,
        orgFamilyMemberSummaries: {},

        // ── Member search (admin tab) ───────────────────
        memberSearchQuery: "",
        memberSearchResults: [],
        memberSearchLoading: false,
        memberSearchError: "",
        // Empty keeps the server default (newest account first).
        memberSearchSortBy: "",
        memberSearchSortDir: "asc",

        // Add-member search results are sorted in the browser — that request
        // returns the whole result set, unlike Member Search above.
        addMemberSortBy: "",
        addMemberSortDir: "asc",

        _personRowValue(row, key) {
            if (key === "person_name") {
                return [row.first_name, row.middle_name, row.last_name]
                    .filter(Boolean)
                    .join(" ");
            }
            return row ? row[key] : undefined;
        },

        sortAddMember(key) {
            const next = NSS.toggleSort(this.addMemberSortBy, this.addMemberSortDir, key);
            this.addMemberSortBy = next.key;
            this.addMemberSortDir = next.dir;
        },

        sortedAddMemberResults() {
            if (!this.addMemberSortBy) return this.addMemberResults;
            return NSS.sortRows(
                this.addMemberResults, this.addMemberSortBy,
                this.addMemberSortDir, this._personRowValue,
            );
        },

        // Computed
        adminTabs: [],
        adminStats: {},
        initials: "",

        // Audit & Compliance tab (NSS_ERP_AUDITOR) — real paginated data
        // from GET /api/v1/audit/change-log (api/routers/audit.py), loaded
        // lazily the first time that tab is viewed (see _refreshTab()).
        adminAudit: {
            loading: false,
            error: "",
            entries: [],
            tableFilter: "",
            actionFilter: "",
            offset: 0,
            pageSize: 20,
            hasMore: true,
        },

        // Pending-approvals panel for the 5 organizational admin tabs
        // (Kendra/Anchalika/Zilla/Sakha/Patha Chakra Management), keyed by
        // roleCode. Both counts reuse real, already-scoped endpoints — see
        // _loadOrgPendingApprovals().
        adminApprovals: {},
        myOrgDashboardPk: null,
        // Restored from sessionStorage like `tab` above — otherwise a
        // refresh landing back on the orgDashboard tab (tab alone is
        // enough to pick the tab) still rendered nothing, because the
        // template guards on `tab === 'orgDashboard' && viewingOrgPk`
        // and this was always re-initialized to null.
        viewingOrgPk: sessionStorage.getItem('nss_dashboard_org_pk') || null,

        // ── Init ──────────────────────────────────────────
        async init() {
            if (!NSSAuth.requireAuth()) return;

            this.loading = true;
            this.error = "";

            try {
                // Step 1: Get user context (profile + RBAC)
                const meRes = await NSSAuth.apiFetch("/api/v1/auth/me");
                if (!meRes.ok) throw new Error("Failed to load user profile.");
                this.user = await meRes.json();

                // Shared layout needs currentUser for topbar/sidebar
                this.currentUser = this.user;

                // Cache user for other pages
                NSSAuth.setCachedUser(this.user);

                // Compute initials
                this.initials = this._computeInitials(this.user.person_name);

                // Build admin tabs from scopes
                this._buildAdminTabs();
                this._buildAdminStats();

                // tab is restored from sessionStorage before /auth/me has been
                // read, so it can name an admin tab this user no longer has —
                // e.g. a role was revoked since the last session, or a
                // session simply predates the current role set. Every
                // admin_* block is x-show'd off adminTabs, so that would
                // render an empty content area with no way back except a
                // sidebar click. Fall back to the first tab this user
                // actually has.
                if (typeof this.tab === "string" && this.tab.startsWith("admin_")
                    && !this.adminTabs.some(t => t.key === this.tab)) {
                    this.switchTab(this.adminTabs.length ? this.adminTabs[0].key : "personal");
                }

                // Own org dashboard link (sidebar) — non-blocking, same
                // scope-vs-NSS-WIDE resolution as admin.js's myOrgDashboardPk.
                this._resolveMyOrgDashboardPk();

                // Fetch real dashboard stats (non-blocking)
                this._loadAdminStats();

                // Same per-tab-type content the sidebar's click handler
                // triggers (_refreshTab), fired once here too since a
                // restored `tab` from sessionStorage lands here without
                // ever going through switchTab()/_refreshTab().
                if (typeof this.tab === "string" && this.tab.startsWith("admin_")) {
                    const restoredTab = this.adminTabs.find(t => t.key === this.tab);
                    if (restoredTab?.roleCode === "NSS_ERP_AUDITOR") {
                        this._loadAuditRecent(true);
                    } else if (restoredTab && ORG_LEVEL_ADMIN_ROLES.has(restoredTab.roleCode)) {
                        this._loadOrgPendingApprovals(restoredTab);
                    }
                }

                // GOV-BR-043-A — non-blocking self-check; drives the
                // Parichalak-only exception panel inside the Governance tab.
                this._loadParichalakStatus();

                // Sidebar "pending items" badges (owner request, 2026-10-25:
                // "a pending items with pending items no. for everyone") —
                // these loaders were previously only triggered when their
                // own tab was opened, so the sidebar badge would show
                // nothing until the user had already visited the tab once.
                // Fire all unconditionally and non-blocking here so every
                // logged-in user sees an accurate count on login, regardless
                // of which tab they land on. Each endpoint is either
                // login-only (returning an empty list for a caller with
                // nothing pending — safe for every user) or, for the claims
                // count, internally gated on canApproveRegistrations.
                this._loadMyPendingActingApprovals();
                this._loadPendingApprovals();
                this._loadOpenElectionsForVoting();
                this._loadPendingClaimsCount();

                // Step 2: Fetch person + membership + family data
                await this._fetchPersonalDetail();

            } catch (err) {
                // NSSAuth.apiFetch() never returns a 401 to its caller — on a
                // genuine expired/invalid session it already attempts one
                // refresh, and on failure calls NSSAuth.logout() (clears
                // tokens, sets window.location.href = "/login") BEFORE
                // throwing this exact message. That redirect is already in
                // flight by the time we get here, so don't also render the
                // dead-end "Unable to load profile" card on top of it — on
                // a slow navigation that produced a confusing stuck screen
                // instead of a clean logout (2026-10-22). Every OTHER error
                // (a real backend failure, e.g. a DB auth/connection issue)
                // is not a session problem — forcing a logout wouldn't fix
                // it, so those still show the normal retry card.
                if (err.message !== "Session expired. Please log in again.") {
                    this.error = err.message || "An unexpected error occurred.";
                }
            } finally {
                this.loading = false;
            }

            // Step 3: Fetch detail data after main loading completes
            await Promise.all([
                this._fetchMembershipDetail(),
                this._fetchFamilyDetail(),
            ]);

            // A page refresh can restore straight onto the findOrg tab via
            // sessionStorage ('nss_dashboard_tab') — switchTab()'s
            // _refreshTab() only fires on an actual tab change, so cover
            // the direct-load case here too.
            if (this.tab === "findOrg") {
                this._loadFindOrgDirectory();
            }

            // Same direct-load coverage for the Member Directory tab.
            if (this.tab === "memberDirectory") {
                this._loadMemberDirectory();
            }

            // Same direct-load coverage for the Attendance tab.
            if (this.tab === "attendance") {
                this._loadMyAttendance();
            }

            // Same direct-load coverage for the Attendance Register tab.
            if (this.tab === "attendanceRegister") {
                this._initAttendanceRegister();
            }

            // personal is the default tab, so a direct/refreshed load lands
            // there without ever going through switchTab() — cover that
            // the same way findOrg is covered above.
            if (this.tab === "personal") {
                this.loadSessions();
            }

            // Same direct-load coverage for the Governance tab.
            if (this.tab === "governance") {
                this._loadGovernanceBodies();
                this._loadMySakhaBodies();
                this._loadOpenElectionsForVoting();
                this._loadMyGovPositions();
                this._loadMyGovDelegations();
                this._loadMyPendingActingApprovals();
            }
        },

        // ── Membership sub-data fetch ────────────────────
        async _fetchMembershipDetail() {
            if (!this.member.sangha_sevi_pk) return;
            const pk = this.member.sangha_sevi_pk;
            try {
                const [affRes, ppRes, apRes, journeyRes] = await Promise.all([
                    NSSAuth.apiFetch(`/api/v1/membership/members/${pk}/affiliations`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/membership/members/${pk}/parichaya-patra`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/membership/members/${pk}/anumati-patra`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/membership/members/${pk}/journey`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                ]);
                this.affiliations = affRes;
                this.parichayaPatras = ppRes;
                this.anumatiPatras = apRes;
                this.journeyEvents = journeyRes;
            } catch (err) {
                console.error("[Dashboard] _fetchMembershipDetail failed:", err);
            }
        },

        // ── Family detail fetch ──────────────────────────
        async _fetchFamilyDetail() {
            if (!this.family) return;
            this.familyLoading = true;
            try {
                const [membersRes, headRes, adminsRes] = await Promise.all([
                    NSSAuth.apiFetch(`/api/v1/family/families/${this.family.family_group_pk}/members`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/family/families/${this.family.family_group_pk}/head-history`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/family/families/${this.family.family_group_pk}/admins?current_only=true`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                ]);
                this.familyMembers = membersRes;
                this.familyHeadHistory = headRes;
                this.familyAdmins = adminsRes;
            } catch (err) {
                console.error("[Dashboard] _fetchFamilyDetail failed:", err);
            } finally {
                this.familyLoading = false;
            }

            // Fetch summaries + graph in parallel (non-blocking)
            this._fetchFamilyMemberSummaries();
            this._fetchFamilyGraph();
        },

        // ── Family member membership summaries ──────────
        async _fetchFamilyMemberSummaries() {
            if (!this.familyMembers.length) return;
            const summaries = {};
            await Promise.all(
                this.familyMembers.map(m =>
                    NSSAuth.apiFetch(`/api/v1/family/person/${m.person_pk}/membership-summary`)
                        .then(r => r.ok ? r.json() : null)
                        .then(data => { if (data) summaries[m.person_pk] = data; })
                        .catch(() => {})
                )
            );
            this.familyMemberSummaries = summaries;
        },

        getMemberSummary(personPk) {
            return this.familyMemberSummaries[personPk] || null;
        },

        // ═══════════════════════════════════════════════════
        //  FAMILY TREE — Graph API + recursive tree builder
        // ═══════════════════════════════════════════════════

        async _fetchFamilyGraph() {
            if (!this.family) return;

            // Viewer is always the logged-in user's person_pk.
            // They may not be in familyMembers (e.g. viewing a departed
            // family via ghost node click), but the graph API includes
            // them as a departed member so BFS still works.
            this.viewerPersonPk = this.user.person_pk;

            await this._loadGraph();
        },

        async _loadGraph() {
            if (!this.family || !this.viewerPersonPk) return;
            this.graphLoading = true;
            this.graphError = false;
            try {
                const url = `/api/v1/family/families/${this.family.family_group_pk}/graph?viewer_person_pk=${this.viewerPersonPk}`;
                const res = await NSSAuth.apiFetch(url);
                if (!res.ok) throw new Error(res.statusText);
                this.graphMembers = await res.json();
                this._buildTree();
            } catch {
                this.graphError = true;
            } finally {
                this.graphLoading = false;
            }
        },

        _buildTree() {
            const members = this.graphMembers;
            this.treeHead = null;
            this.treeSpouse = null;
            this.treeNodes = [];
            this._allTreePersons = [];

            // Viewer node (synthesized — not in graphMembers since BFS
            // skips the root).  Look in familyMembers first; if the
            // viewer isn't a current member (departed family view),
            // build a minimal node from the person record.
            let viewerMember = this.familyMembers.find(
                m => m.person_pk === this.viewerPersonPk
            );
            if (!viewerMember && this.person && this.person.person_pk === this.viewerPersonPk) {
                viewerMember = {
                    person_pk: this.person.person_pk,
                    person_id: this.person.person_id,
                    first_name: this.person.first_name,
                    middle_name: this.person.middle_name,
                    last_name: this.person.last_name,
                    gender_code: this.person.gender_code,
                };
            }
            const viewerSpouseGraph = members.find(
                m => SPOUSE_LABELS.has(m.relationship_label) && m.generation === 0
            );
            const viewerParentPks = members
                .filter(m => PARENT_LABELS.has(m.relationship_label))
                .map(m => m.person_pk);

            if (viewerMember) {
                this.treeHead = {
                    ...viewerMember,
                    relationship_label: "You",
                    generation: 0,
                    _isViewer: true,
                    _avatarClass: "av-viewer",
                    spouse_person_pk: viewerSpouseGraph ? viewerSpouseGraph.person_pk : null,
                    parent_person_pks: viewerParentPks,
                };
            }
            this.treeSpouse = viewerSpouseGraph || null;

            // Assign avatar classes
            for (const m of members) {
                const isSpouse = SPOUSE_LABELS.has(m.relationship_label);
                m._avatarClass = _avatarClass(m.generation, m.is_head, isSpouse);
            }

            // All persons
            const allPersons = [];
            if (this.treeHead) allPersons.push(this.treeHead);
            for (const m of members) allPersons.push(m);
            this._allTreePersons = allPersons;

            this.treeNodes = _buildCoupleTree(allPersons);
        },

        // ── Tree rendering (x-html) ─────────────────────
        renderTree() {
            if (!this.treeNodes?.length) return "";
            return this._renderSubtree(this.treeNodes, true);
        },

        // Shared tree-rendering skeleton for _renderSubtree/_renderOrgSubtree
        // below (previously duplicated wholesale) — parameterized on which
        // couple-renderer to call, since the Family tab and org browser
        // render different node markup for an otherwise identical tree shape.
        _renderGenSubtree(nodes, isRoot, renderCouple, recurse) {
            if (!nodes.length) return "";
            const gen = nodes[0].gen;
            const genLabel = GEN_LABELS[String(gen)] || (gen < 0 ? "Ancestors (" + Math.abs(gen) + ")" : "Descendants (" + gen + ")");
            let h = "";
            if (!isRoot) h += '<div class="conn-v"></div>';
            h += '<div class="gen-divider"><div class="gen-divider-line"></div><span class="gen-divider-text">' + genLabel + '</span><div class="gen-divider-line"></div></div>';
            if (nodes.length === 1) {
                h += '<div class="gen-row">' + renderCouple(nodes[0]) + '</div>';
                if (nodes[0].children.length) h += recurse(nodes[0].children, false);
            } else {
                const w = (nodes.length - 1) * 8;
                h += '<div class="bracket-wrap"><div class="conn-h" style="width:' + w + 'rem"></div><div class="bracket-row">';
                for (const node of nodes) {
                    const hasKids = node.children.length > 0;
                    h += '<div class="bracket-item' + (hasKids ? " flex flex-col items-center" : "") + '">';
                    h += renderCouple(node);
                    if (hasKids) h += recurse(node.children, false);
                    h += '</div>';
                }
                h += '</div></div>';
            }
            return h;
        },

        _renderSubtree(nodes, isRoot) {
            return this._renderGenSubtree(
                nodes, isRoot,
                (n) => this._renderCouple(n),
                (n, r) => this._renderSubtree(n, r),
            );
        },

        _renderCouple(node) {
            if (node.couple) {
                return '<div class="couple-group">' + this._renderPerson(node.members[0]) + '<div class="couple-join-line"></div>' + this._renderPerson(node.members[1]) + '</div>';
            }
            return this._renderPerson(node.members[0]);
        },

        _renderPerson(m) {
            const av = m._avatarClass || "av-other";
            const ini = this._esc(this._getInitials(m));
            const nm = this._esc(this.formatFamilyName(m));
            const rl = m._isViewer ? "<strong>You</strong>" : this._esc(m.relationship_label || "");
            const sel = this.selectedPerson?.person_pk === m.person_pk ? " is-selected" : "";
            const vr = m._isViewer ? " is-viewer" : "";
            const dep = m.is_departed ? " is-departed" : "";
            let ind = "";
            if (m._isViewer)
                ind = '<span class="node-indicator indicator-viewer">&#128065;</span>';
            else if (m.is_head)
                ind = '<span class="node-indicator indicator-head">&#9733;</span>';
            let depInfo = "";
            if (m.is_departed) {
                const fn = this._esc(m.departed_family_name || "");
                const sn = this._esc(m.departed_sakha_name || "");
                depInfo = '<div class="departed-info" title="Click to view ' + fn + ' family">'
                    + (fn ? '<div class="departed-family">' + fn + '</div>' : '')
                    + (sn ? '<div class="departed-sakha">' + sn + '</div>' : '')
                    + '</div>';
            }
            return '<div class="tree-node' + sel + dep + '" title="' + (m.is_departed ? 'Click to visit ' + this._esc(m.departed_family_name || 'their') + ' family' : '') + '" data-person-pk="' + m.person_pk + '">'
                 + '<div class="node-avatar ' + av + '">' + ini + ind + '</div>'
                 + '<div class="node-name">' + nm + '</div>'
                 + '<div class="node-role' + vr + '">' + rl + '</div>'
                 + depInfo
                 + '</div>';
        },

        _esc(s) {
            return NSS.escapeHtml(s);
        },

        _getInitials(m) {
            const first = (m.first_name || "")[0] || "";
            const last = (m.last_name || "")[0] || "";
            return (first + last).toUpperCase() || "?";
        },

        getAvatarClass(m) {
            if (!m) return "av-other";
            if (m._avatarClass) return m._avatarClass;
            if (m._isViewer) return "av-viewer";
            if (m.person_pk === this.viewerPersonPk) return "av-viewer";
            const gm = this.graphMembers.find(g => g.person_pk === m.person_pk);
            if (gm?._avatarClass) return gm._avatarClass;
            return "av-other";
        },

        isViewingForeignFamily() {
            if (!this.family || !this.ownFamily) return false;
            return this.family.family_group_pk !== this.ownFamily.family_group_pk;
        },

        async goBackToOwnFamily() {
            if (!this.ownFamily) return;
            this.family = this.ownFamily;
            this.selectedPerson = null;
            this.selectedPersonDetail = null;
            this.selectedPersonMembership = null;
            await this._fetchFamilyDetail();
        },

        handleTreeClick(event) {
            const el = event.target.closest("[data-person-pk]");
            if (!el) return;
            const pk = el.dataset.personPk;
            const member = this._allTreePersons?.find(m => m.person_pk === pk);
            if (!member) return;

            // Ghost node click: navigate only when viewing own family
            // When viewing a foreign family, ghosts are non-interactive (use Back banner)
            if (member.is_departed && member.departed_family_group_pk) {
                if (this.isViewingForeignFamily()) return; // not clickable in foreign view
                this._navigateToDepartedFamily(member.departed_family_group_pk);
                return;
            }
            this.selectTreePerson(member);
        },

        async _navigateToDepartedFamily(familyGroupPk) {
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/family/families/${familyGroupPk}`);
                if (!res.ok) throw new Error("Family not found");
                const familyData = await res.json();
                this.family = familyData;
                this.selectedPerson = null;
                this.selectedPersonDetail = null;
                this.selectedPersonMembership = null;
                await this._fetchFamilyDetail();
            } catch (err) {
                console.error("[Dashboard] Navigate to departed family failed:", err);
            }
        },

        displayRelationship(m) {
            if (m._isViewer) return "You";
            if (m.person_pk === this.viewerPersonPk) return "You";
            if (m.relationship_label) return m.relationship_label;
            const gm = this.graphMembers.find(g => g.person_pk === m.person_pk);
            if (gm?.relationship_label) return gm.relationship_label;
            if (m.is_head) return "Head of Family";
            return m.relationship_type_name || m.relationship_type_code || "—";
        },

        sortedFamilyMembers() {
            const ORDER = {
                'Grandfather': 1, 'Grandmother': 1, 'Grandparent': 1,
                'Father': 2, 'Mother': 2,
                'Wife': 4, 'Husband': 4, 'Spouse': 4,
                'Brother': 5, 'Sister': 5, 'Brother-in-Law': 5, 'Sister-in-Law': 5, 'Sibling': 5,
                'Son': 6, 'Daughter': 6, 'Child': 6,
                'Grandson': 7, 'Granddaughter': 7, 'Grandchild': 7
            };
            const self = this;
            function relOrder(m) {
                if (m.person_pk === self.viewerPersonPk) return 3;
                // Try graph member label first (computed by BFS)
                var gm = self.graphMembers.find(function(g) { return g.person_pk === m.person_pk; });
                var label = (gm && gm.relationship_label) || m.relationship_label || m.relationship_type_name || '';
                return ORDER[label] || 8;
            }
            return [...this.familyMembers].sort(function(a, b) { return relOrder(a) - relOrder(b); });
        },

        // ── Person selection (from tree click or member list) ─
        async selectTreePerson(member) {
            if (this.selectedPerson?.person_pk === member.person_pk) {
                this.selectedPerson = null;
                this.selectedPersonDetail = null;
                this.selectedPersonMembership = null;
                return;
            }
            this.selectedPerson = member;
            this.selectedPersonDetail = null;
            this.selectedPersonLoading = true;
            this.selectedPersonMembership = null;
            this.selectedPersonMembershipLoading = true;

            const [personData, membershipData] = await Promise.all([
                NSSAuth.apiFetch(`/api/v1/person/persons/${member.person_pk}`)
                    .then(r => r.ok ? r.json() : null).catch(() => null),
                NSSAuth.apiFetch(`/api/v1/family/person/${member.person_pk}/membership-summary`)
                    .then(r => r.ok ? r.json() : null).catch(() => null),
            ]);

            this.selectedPersonDetail = personData;
            this.selectedPersonLoading = false;
            this.selectedPersonMembership = membershipData;
            this.selectedPersonMembershipLoading = false;
        },

        getSpouseName(personPk) {
            const gm = this.graphMembers.find(g => g.person_pk === personPk);
            if (gm && gm.spouse_person_pk) {
                const spouse = this.graphMembers.find(g => g.person_pk === gm.spouse_person_pk)
                    || this.familyMembers.find(m => m.person_pk === gm.spouse_person_pk);
                if (spouse) return this.formatFamilyName(spouse);
            }
            if (personPk === this.viewerPersonPk && this.treeSpouse) {
                return this.formatFamilyName(this.treeSpouse);
            }
            return null;
        },

        getSpouseInitials(personPk) {
            const gm = this.graphMembers.find(g => g.person_pk === personPk);
            if (gm && gm.spouse_person_pk) {
                const spouse = this.graphMembers.find(g => g.person_pk === gm.spouse_person_pk)
                    || this.familyMembers.find(m => m.person_pk === gm.spouse_person_pk);
                if (spouse) return this._getInitials(spouse);
            }
            if (personPk === this.viewerPersonPk && this.treeSpouse) return this._getInitials(this.treeSpouse);
            return "?";
        },

        selectSpouse(personPk) {
            const gm = this.graphMembers.find(g => g.person_pk === personPk);
            const spousePk = gm?.spouse_person_pk || (personPk === this.viewerPersonPk && this.treeSpouse ? this.treeSpouse.person_pk : null);
            if (!spousePk) return;
            const spouseMember = this.graphMembers.find(g => g.person_pk === spousePk) || this.familyMembers.find(m => m.person_pk === spousePk);
            if (spouseMember) this.selectTreePerson(spouseMember);
        },

        // ── Add member — search ──────────────────────────
        openAddMemberModal() {
            this.showAddMemberModal = true;
            this.addMemberSearch = "";
            this.addMemberResults = [];
            this.addMemberSearchTotal = 0;
            this.addMemberSelected = null;
            this.addMemberRelType = "";
            this.addMemberLinkType = "";
            this.addMemberLinkTarget = "";
            this.addMemberRemarks = "";
            this.addMemberError = "";
            this.addMemberInferredLinks = [];
            this.addMemberInlawSpouse = "";
            this.addMemberInlawSpouseNotInTree = false;
            this.addMemberExistingFamilies = [];
            if (this._addMemberDebounce) clearTimeout(this._addMemberDebounce);
        },

        closeAddMemberModal() {
            this.showAddMemberModal = false;
            this.addMemberInlawSpouse = "";
            this.addMemberInlawSpouseNotInTree = false;
            this.addMemberExistingFamilies = [];
            if (this._addMemberDebounce) clearTimeout(this._addMemberDebounce);
        },

        // Enhancement 1: Debounced auto-search (300ms, same as person.js / membership.js)
        searchPersonForAdd() {
            const q = (this.addMemberSearch || "").trim();
            if (q.length < 2) { this.addMemberResults = []; this.addMemberSearchTotal = 0; return; }
            if (this._addMemberDebounce) clearTimeout(this._addMemberDebounce);
            this._addMemberDebounce = setTimeout(async () => {
                this.addMemberSearching = true;
                this.addMemberError = "";
                try {
                    const res = await NSSAuth.apiFetch(
                        `/api/v1/person/search-selectable?q=${encodeURIComponent(q)}`
                    );
                    if (!res.ok) throw new Error("Search failed");
                    const data = await res.json();
                    const results = data.persons;
                    this.addMemberSearchTotal = data.total;
                    // Exclude persons already in this family (current members only)
                    const existingPks = new Set(this.familyMembers.map(m => m.person_pk));
                    let filtered = results.filter(r => !existingPks.has(r.person_pk));

                    // Enhancement 4: Smart spouse filtering
                    if (this.addMemberRelType === "SPOUSE") {
                        filtered = this._filterForSpouse(filtered);
                    }

                    this.addMemberResults = filtered;
                } catch (err) {
                    this.addMemberError = err.message || "Search failed";
                    this.addMemberResults = [];
                    this.addMemberSearchTotal = 0;
                } finally {
                    this.addMemberSearching = false;
                }
            }, 300);
        },

        selectPersonForAdd(person) {
            this.addMemberSelected = person;
            // Reset relationship when person changes (gender may differ)
            this.addMemberRelType = "";
            this.addMemberLinkType = "";
            this.addMemberLinkTarget = "";
            this.addMemberInferredLinks = [];
            this.addMemberInlawSpouse = "";
            this.addMemberInlawSpouseNotInTree = false;
            this.addMemberExistingFamilies = [];

            // Fetch existing family memberships for this person
            this._fetchExistingFamilies(person.person_pk);
        },

        async _fetchExistingFamilies(personPk) {
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/family/person/${personPk}/families`);
                if (res.ok) {
                    const families = await res.json();
                    this.addMemberExistingFamilies = families;
                }
            } catch (e) {
                this.addMemberExistingFamilies = [];
            }
        },

        // Gender-based relationship type filtering
        // Returns list of {value, label, group} for the selected person's gender
        getGenderFilteredRelTypes() {
            const gender = this.addMemberSelected?.gender_code || this.addMemberSelected?.gender_name?.toUpperCase();
            // All relationship types grouped
            const ALL_RELS = [
                { group: "Immediate Family", items: [
                    { value: "SPOUSE", label: "Spouse", gender: null },
                    { value: "FATHER", label: "Father", gender: "MALE" },
                    { value: "MOTHER", label: "Mother", gender: "FEMALE" },
                    { value: "SON", label: "Son", gender: "MALE" },
                    { value: "DAUGHTER", label: "Daughter", gender: "FEMALE" },
                    { value: "BROTHER", label: "Brother", gender: "MALE" },
                    { value: "SISTER", label: "Sister", gender: "FEMALE" },
                ]},
                { group: "In-Laws", items: [
                    { value: "FATHER_IN_LAW", label: "Father-in-Law", gender: "MALE" },
                    { value: "MOTHER_IN_LAW", label: "Mother-in-Law", gender: "FEMALE" },
                    { value: "SON_IN_LAW", label: "Son-in-Law", gender: "MALE" },
                    { value: "DAUGHTER_IN_LAW", label: "Daughter-in-Law", gender: "FEMALE" },
                    { value: "BROTHER_IN_LAW", label: "Brother-in-Law", gender: "MALE" },
                    { value: "SISTER_IN_LAW", label: "Sister-in-Law", gender: "FEMALE" },
                ]},
                { group: "Grandparents / Grandchildren", items: [
                    { value: "GRANDFATHER", label: "Grandfather", gender: "MALE" },
                    { value: "GRANDMOTHER", label: "Grandmother", gender: "FEMALE" },
                    { value: "GRANDSON", label: "Grandson", gender: "MALE" },
                    { value: "GRANDDAUGHTER", label: "Granddaughter", gender: "FEMALE" },
                ]},
                { group: "Step Relations", items: [
                    { value: "STEP_FATHER", label: "Step-Father", gender: "MALE" },
                    { value: "STEP_MOTHER", label: "Step-Mother", gender: "FEMALE" },
                    { value: "STEP_SON", label: "Step-Son", gender: "MALE" },
                    { value: "STEP_DAUGHTER", label: "Step-Daughter", gender: "FEMALE" },
                ]},
                { group: "Other", items: [
                    { value: "UNCLE", label: "Uncle", gender: "MALE" },
                    { value: "AUNT", label: "Aunt", gender: "FEMALE" },
                    { value: "NEPHEW", label: "Nephew", gender: "MALE" },
                    { value: "NIECE", label: "Niece", gender: "FEMALE" },
                    { value: "COUSIN", label: "Cousin", gender: null },
                    { value: "GUARDIAN", label: "Guardian", gender: null },
                    { value: "WARD", label: "Ward", gender: null },
                    { value: "OTHER", label: "Other Relative", gender: null },
                ]},
            ];

            // Filter by gender if known
            return ALL_RELS.map(g => ({
                group: g.group,
                items: g.items.filter(r => !gender || !r.gender || r.gender === gender),
            })).filter(g => g.items.length > 0);
        },

        // Hide/show <option> elements by gender using hidden+disabled attributes
        // Called via x-effect when addMemberSelected changes
        updateRelTypeOptions(selectEl, _person) {
            if (!selectEl) return;
            const gender = this.addMemberSelected?.gender_code
                || (this.addMemberSelected?.gender_name || "").toUpperCase()
                || null;

            // Singular relationships — only one person can hold the role.
            // Map: relationship_type_code → graph label to check.
            // If the label already exists in graphMembers, hide that option.
            const SINGULAR_MAP = {
                FATHER:         "Father",
                MOTHER:         "Mother",
                SPOUSE:         "Husband",   // check both
                GRANDFATHER:    "Grandfather",
                GRANDMOTHER:    "Grandmother",
                FATHER_IN_LAW:  "Father-in-Law",
                MOTHER_IN_LAW:  "Mother-in-Law",
                STEP_FATHER:    "Step-Father",
                STEP_MOTHER:    "Step-Mother",
            };
            // Spouse can be Husband or Wife
            const graph = this.graphMembers || [];
            // Only check non-departed (current) members for singularity
            const currentGraph = graph.filter(g => !g.is_departed);
            const existingLabels = new Set(currentGraph.map(g => g.relationship_label));
            // Build set of codes already filled
            const filledCodes = new Set();
            for (const [code, label] of Object.entries(SINGULAR_MAP)) {
                if (code === "SPOUSE") {
                    if (existingLabels.has("Husband") || existingLabels.has("Wife")) {
                        filledCodes.add(code);
                    }
                } else if (existingLabels.has(label)) {
                    filledCodes.add(code);
                }
            }

            for (const opt of selectEl.querySelectorAll("option[value]")) {
                const val = opt.value;
                if (!val) continue; // skip placeholder

                const genderMismatch = opt.dataset.gender && gender && opt.dataset.gender !== gender;
                const alreadyFilled = filledCodes.has(val);

                if (genderMismatch || alreadyFilled) {
                    opt.hidden = true;
                    opt.disabled = true;
                } else {
                    opt.hidden = false;
                    opt.disabled = false;
                }
            }
            // Hide empty optgroups
            for (const og of selectEl.querySelectorAll("optgroup")) {
                const visible = [...og.querySelectorAll("option")].some(o => !o.hidden);
                og.hidden = !visible;
            }
        },

        // Check if the currently selected relationship type is an in-law type
        isInlawRelType() {
            const INLAW_TYPES = new Set([
                "FATHER_IN_LAW", "MOTHER_IN_LAW", "SON_IN_LAW", "DAUGHTER_IN_LAW",
                "BROTHER_IN_LAW", "SISTER_IN_LAW",
            ]);
            return INLAW_TYPES.has(this.addMemberRelType);
        },

        // Get candidate existing members who could be the "spouse connector" for an in-law.
        // e.g., adding a Sister-in-Law → which Brother or which Spouse links her?
        getInlawSpouseCandidates() {
            const relType = this.addMemberRelType;
            const graph = this.graphMembers;
            const findByRelLabel = (label) => graph.filter(g => g.relationship_label === label);

            // For each in-law type, which existing member role is the "connector"?
            switch (relType) {
                case "SISTER_IN_LAW":
                    // SIL = brother's wife OR spouse's sister
                    // Candidates: all Brothers (she marries one) + all Spouses (she's their sister)
                    return [
                        ...findByRelLabel("Brother").map(m => ({ ...m, _inlawPath: "sibling_spouse", _desc: `${this.formatFamilyName(m)}'s wife (Brother's wife)` })),
                    ];
                case "BROTHER_IN_LAW":
                    // BIL = sister's husband OR spouse's brother
                    return [
                        ...findByRelLabel("Sister").map(m => ({ ...m, _inlawPath: "sibling_spouse", _desc: `${this.formatFamilyName(m)}'s husband (Sister's husband)` })),
                    ];
                case "SON_IN_LAW":
                    // Son-in-law marries daughter
                    return [
                        ...findByRelLabel("Daughter").map(m => ({ ...m, _inlawPath: "child_spouse", _desc: `${this.formatFamilyName(m)}'s husband (Daughter's husband)` })),
                    ];
                case "DAUGHTER_IN_LAW":
                    // Daughter-in-law marries son
                    return [
                        ...findByRelLabel("Son").map(m => ({ ...m, _inlawPath: "child_spouse", _desc: `${this.formatFamilyName(m)}'s wife (Son's wife)` })),
                    ];
                case "FATHER_IN_LAW":
                    // Father-in-law = spouse's father
                    return [
                        ...findByRelLabel("Wife").concat(findByRelLabel("Husband")).map(m => ({ ...m, _inlawPath: "spouse_parent", _desc: `${this.formatFamilyName(m)}'s father (Spouse's father)` })),
                    ];
                case "MOTHER_IN_LAW":
                    // Mother-in-law = spouse's mother
                    return [
                        ...findByRelLabel("Wife").concat(findByRelLabel("Husband")).map(m => ({ ...m, _inlawPath: "spouse_parent", _desc: `${this.formatFamilyName(m)}'s mother (Spouse's mother)` })),
                    ];
                default:
                    return [];
            }
        },

        // When in-law spouse selection changes, re-compute links
        onInlawSpouseChange() {
            this.addMemberInferredLinks = [];
            this.addMemberLinkType = "";
            this.addMemberLinkTarget = "";

            const relType = this.addMemberRelType;
            if (!relType) return;

            // "Spouse not in Family Tree" — create parent links so the person appears at correct level
            if (this.addMemberInlawSpouseNotInTree) {
                const inferred = [];
                const graph = this.graphMembers;
                const findByRelLabel = (label) => graph.filter(g => g.relationship_label === label);

                if (relType === "SISTER_IN_LAW" || relType === "BROTHER_IN_LAW") {
                    // Place at gen 0 by linking to parents (same as siblings)
                    const fathers = findByRelLabel("Father");
                    const mothers = findByRelLabel("Mother");
                    for (const parent of [...fathers, ...mothers]) {
                        inferred.push({
                            type: "PARENT_OF",
                            description: `${this.formatFamilyName(parent)} (${parent.relationship_label}) is parent (placed as sibling-level)`,
                            person_a_pk: parent.person_pk,
                            person_b_pk: null,
                        });
                    }
                } else if (relType === "SON_IN_LAW" || relType === "DAUGHTER_IN_LAW") {
                    // Place at gen +1 by linking viewer as parent
                    const viewerPk = this.viewerPersonPk;
                    inferred.push({
                        type: "PARENT_OF",
                        description: `You are parent (placed at children level)`,
                        person_a_pk: viewerPk,
                        person_b_pk: null,
                    });
                    // Also add spouse as parent if exists
                    const spouses = findByRelLabel("Wife").concat(findByRelLabel("Husband"));
                    if (spouses.length > 0) {
                        inferred.push({
                            type: "PARENT_OF",
                            description: `${this.formatFamilyName(spouses[0])} (${spouses[0].relationship_label}) is also parent`,
                            person_a_pk: spouses[0].person_pk,
                            person_b_pk: null,
                        });
                    }
                } else if (relType === "FATHER_IN_LAW" || relType === "MOTHER_IN_LAW") {
                    // Place at gen -1 — no direct link possible without spouse
                    // Use viewer's spouse if available, otherwise leave manual
                    const spouses = findByRelLabel("Wife").concat(findByRelLabel("Husband"));
                    if (spouses.length > 0) {
                        this.addMemberLinkType = "PARENT_OF";
                        this.addMemberLinkTarget = spouses[0].person_pk;
                    }
                }
                this.addMemberInferredLinks = inferred;
                return;
            }

            // Normal in-law spouse selected — compute SPOUSE_OF link + parent inferred links
            const selectedPk = this.addMemberInlawSpouse;
            if (!selectedPk) return;

            const candidates = this.getInlawSpouseCandidates();
            const chosen = candidates.find(c => c.person_pk === selectedPk);
            if (!chosen) return;

            const inferred = [];

            if (chosen._inlawPath === "sibling_spouse") {
                // SIL/BIL = sibling's spouse → SPOUSE_OF the sibling
                this.addMemberLinkType = "SPOUSE_OF";
                this.addMemberLinkTarget = chosen.person_pk;
            } else if (chosen._inlawPath === "child_spouse") {
                // Son-in-Law/Daughter-in-Law = child's spouse → SPOUSE_OF the child
                this.addMemberLinkType = "SPOUSE_OF";
                this.addMemberLinkTarget = chosen.person_pk;
            } else if (chosen._inlawPath === "spouse_parent") {
                // Father-in-Law/Mother-in-Law = spouse's parent → PARENT_OF the spouse
                this.addMemberLinkType = "PARENT_OF";
                this.addMemberLinkTarget = chosen.person_pk;

                // Also infer SPOUSE_OF with existing opposite in-law
                const graph = this.graphMembers;
                const oppositeLabel = relType === "FATHER_IN_LAW" ? "Mother-in-Law" : "Father-in-Law";
                const existingOpposite = graph.filter(g => g.relationship_label === oppositeLabel);
                if (existingOpposite.length > 0) {
                    inferred.push({
                        type: "SPOUSE_OF",
                        description: `Spouse of ${this.formatFamilyName(existingOpposite[0])} (${oppositeLabel})`,
                        person_a_pk: null,
                        person_b_pk: existingOpposite[0].person_pk,
                    });
                }
            }

            this.addMemberInferredLinks = inferred;
        },

        // Enhancement 2 & 3: When relationship type changes, auto-infer complementary relations and links
        onRelTypeChange() {
            this.addMemberInferredLinks = [];
            this.addMemberLinkType = "";
            this.addMemberLinkTarget = "";
            this.addMemberInlawSpouse = "";
            this.addMemberInlawSpouseNotInTree = false;

            if (!this.addMemberRelType) return;

            // For in-law types, defer link computation to onInlawSpouseChange()
            // User must first select which existing member is the spouse connector
            if (this.isInlawRelType()) {
                // Auto-select if only one candidate
                const candidates = this.getInlawSpouseCandidates();
                if (candidates.length === 1) {
                    this.addMemberInlawSpouse = candidates[0].person_pk;
                    this.onInlawSpouseChange();
                }
                return;
            }

            const relType = this.addMemberRelType;
            const graph = this.graphMembers;
            const viewerPk = this.viewerPersonPk;

            // Helper: find existing members by their relationship label from graph
            const findByRelLabel = (label) => {
                return graph.filter(g => g.relationship_label === label);
            };

            const inferred = [];

            // ── FATHER / MOTHER ──────────────────────────────
            // Main link: new parent PARENT_OF viewer
            // Inferred: SPOUSE_OF with existing opposite parent
            // Inferred: PARENT_OF each sibling
            if (relType === "FATHER" || relType === "MOTHER") {
                this.addMemberLinkType = "PARENT_OF";
                this.addMemberLinkTarget = viewerPk;

                // Spouse with existing opposite parent
                const oppositeLabel = relType === "FATHER" ? "Mother" : "Father";
                const existingOpposite = findByRelLabel(oppositeLabel);
                if (existingOpposite.length > 0) {
                    inferred.push({
                        type: "SPOUSE_OF",
                        description: `Spouse of ${this.formatFamilyName(existingOpposite[0])} (${oppositeLabel})`,
                        person_a_pk: null, // will be new person
                        person_b_pk: existingOpposite[0].person_pk,
                    });
                }

                // PARENT_OF viewer's siblings (new parent is their parent too)
                const siblings = findByRelLabel("Brother").concat(findByRelLabel("Sister"));
                for (const sib of siblings) {
                    inferred.push({
                        type: "PARENT_OF",
                        description: `Parent of ${this.formatFamilyName(sib)} (${sib.relationship_label})`,
                        person_a_pk: null, // will be new person
                        person_b_pk: sib.person_pk,
                    });
                }

                this.addMemberInferredLinks = inferred;
            }

            // ── SPOUSE ───────────────────────────────────────
            // Main link: new person SPOUSE_OF viewer
            if (relType === "SPOUSE") {
                this.addMemberLinkType = "SPOUSE_OF";
                this.addMemberLinkTarget = viewerPk;
                // Re-trigger search with spouse filter
                this.searchPersonForAdd();
            }

            // ── BROTHER / SISTER ─────────────────────────────
            // A sibling shares the same parents as the viewer.
            // If the viewer already has a parent on file: keep the
            // existing (working) behaviour — infer PARENT_OF links from
            // each existing parent to the new sibling (new person is
            // person_b — child).
            // If the viewer has NO parent on file (owner decision,
            // 2026-10-22): there's nothing to anchor a PARENT_OF link
            // to, so send a direct SIBLING_OF link between the viewer
            // and the new person instead — the backend now supports
            // this (api/routers/family.py insert_family_link_edge /
            // SIBLING_OF link_type). This is what previously left
            // `inferred` empty and made the sibling invisible in the
            // tree view.
            if (relType === "BROTHER" || relType === "SISTER") {
                const fathers = findByRelLabel("Father");
                const mothers = findByRelLabel("Mother");
                const parents = [...fathers, ...mothers];

                if (parents.length > 0) {
                    // Use first parent as the main link
                    this.addMemberLinkType = "PARENT_OF";
                    // Direction: person_a (new member) is parent of person_b (target)
                    // BUT siblings are CHILDREN of the parent, not parents themselves.
                    // The main link creates: new_person PARENT_OF target — wrong direction!
                    // We need: parent PARENT_OF new_sibling
                    // So DON'T use the main link — use inferred links for all parents.
                    this.addMemberLinkType = "";
                    this.addMemberLinkTarget = "";

                    for (const parent of parents) {
                        inferred.push({
                            type: "PARENT_OF",
                            description: `${this.formatFamilyName(parent)} (${parent.relationship_label}) is parent of new ${relType.toLowerCase()}`,
                            person_a_pk: parent.person_pk, // existing parent
                            person_b_pk: null, // will be new person
                        });
                    }
                } else {
                    // No parent in the graph yet — create a direct
                    // SIBLING_OF edge between the viewer and the new
                    // person so they're still visible in the tree.
                    // SIBLING_OF is symmetric (like SPOUSE_OF), so it
                    // can use the main link_type/link_target_person_pk
                    // fields rather than the inferred-links array.
                    this.addMemberLinkType = "SIBLING_OF";
                    this.addMemberLinkTarget = viewerPk;
                }

                this.addMemberInferredLinks = inferred;
            }

            // ── SON / DAUGHTER ────────────────────────────────
            // Inferred: viewer PARENT_OF new child
            // Inferred: viewer's spouse PARENT_OF new child (if spouse exists)
            if (relType === "SON" || relType === "DAUGHTER") {
                // Can't use main link (it puts new member as person_a = parent, wrong direction)
                // Use inferred links instead
                inferred.push({
                    type: "PARENT_OF",
                    description: `You are parent of new ${relType.toLowerCase()}`,
                    person_a_pk: viewerPk, // viewer is parent
                    person_b_pk: null, // will be new person
                });

                // If viewer has a spouse, they're also a parent
                const spouseLabels = findByRelLabel("Wife").concat(findByRelLabel("Husband"));
                if (spouseLabels.length > 0) {
                    const spouse = spouseLabels[0];
                    inferred.push({
                        type: "PARENT_OF",
                        description: `${this.formatFamilyName(spouse)} (${spouse.relationship_label}) is also parent`,
                        person_a_pk: spouse.person_pk,
                        person_b_pk: null, // will be new person
                    });
                }

                this.addMemberInferredLinks = inferred;
            }

            // ── GRANDFATHER / GRANDMOTHER ────────────────────
            // Main link: new grandparent PARENT_OF existing parent
            // Inferred: SPOUSE_OF existing opposite grandparent
            if (relType === "GRANDFATHER" || relType === "GRANDMOTHER") {
                const fathers = findByRelLabel("Father");
                const mothers = findByRelLabel("Mother");
                const parents = [...fathers, ...mothers];
                if (parents.length > 0) {
                    this.addMemberLinkType = "PARENT_OF";
                    this.addMemberLinkTarget = parents[0].person_pk;

                    const oppositeGrandLabel = relType === "GRANDFATHER" ? "Grandmother" : "Grandfather";
                    const existingGrand = findByRelLabel(oppositeGrandLabel);
                    if (existingGrand.length > 0) {
                        inferred.push({
                            type: "SPOUSE_OF",
                            description: `Spouse of ${this.formatFamilyName(existingGrand[0])} (${oppositeGrandLabel})`,
                            person_a_pk: null,
                            person_b_pk: existingGrand[0].person_pk,
                        });
                    }
                    this.addMemberInferredLinks = inferred;
                }
            }

            // ── GRANDSON / GRANDDAUGHTER ─────────────────────
            // Inferred: viewer's child PARENT_OF new grandchild
            if (relType === "GRANDSON" || relType === "GRANDDAUGHTER") {
                const sons = findByRelLabel("Son");
                const daughters = findByRelLabel("Daughter");
                const children = [...sons, ...daughters];
                if (children.length > 0) {
                    inferred.push({
                        type: "PARENT_OF",
                        description: `${this.formatFamilyName(children[0])} (${children[0].relationship_label}) is parent of new ${relType.toLowerCase()}`,
                        person_a_pk: children[0].person_pk,
                        person_b_pk: null,
                    });
                    this.addMemberInferredLinks = inferred;
                }
            }

            // ── In-law types are now handled by onInlawSpouseChange() ──
            // (FATHER_IN_LAW, MOTHER_IN_LAW, SON_IN_LAW, DAUGHTER_IN_LAW,
            //  BROTHER_IN_LAW, SISTER_IN_LAW — all deferred to spouse selector)

            // ── STEP-FATHER / STEP-MOTHER ────────────────────
            // Parent's new spouse. Link: SPOUSE_OF existing parent
            if (relType === "STEP_FATHER" || relType === "STEP_MOTHER") {
                const targetLabel = relType === "STEP_FATHER" ? "Mother" : "Father";
                const existing = findByRelLabel(targetLabel);
                if (existing.length > 0) {
                    this.addMemberLinkType = "SPOUSE_OF";
                    this.addMemberLinkTarget = existing[0].person_pk;
                }
                this.addMemberInferredLinks = inferred;
            }

            // ── STEP-SON / STEP-DAUGHTER ─────────────────────
            // Spouse's child from another relationship. Link: spouse PARENT_OF new child
            if (relType === "STEP_SON" || relType === "STEP_DAUGHTER") {
                const spouses = findByRelLabel("Wife").concat(findByRelLabel("Husband"));
                if (spouses.length > 0) {
                    inferred.push({
                        type: "PARENT_OF",
                        description: `${this.formatFamilyName(spouses[0])} (${spouses[0].relationship_label}) is parent`,
                        person_a_pk: spouses[0].person_pk,
                        person_b_pk: null,
                    });
                }
                this.addMemberInferredLinks = inferred;
            }

            // ── UNCLE / AUNT ─────────────────────────────────
            // Parent's sibling. Link: grandparent PARENT_OF new uncle/aunt
            if (relType === "UNCLE" || relType === "AUNT") {
                const grandfathers = findByRelLabel("Grandfather");
                const grandmothers = findByRelLabel("Grandmother");
                const grandparents = [...grandfathers, ...grandmothers];
                for (const gp of grandparents) {
                    inferred.push({
                        type: "PARENT_OF",
                        description: `${this.formatFamilyName(gp)} (${gp.relationship_label}) is parent of new ${relType.toLowerCase()}`,
                        person_a_pk: gp.person_pk,
                        person_b_pk: null,
                    });
                }
                this.addMemberInferredLinks = inferred;
            }

            // ── NEPHEW / NIECE ───────────────────────────────
            // Sibling's child. Link: existing sibling PARENT_OF new nephew/niece
            if (relType === "NEPHEW" || relType === "NIECE") {
                const brothers = findByRelLabel("Brother");
                const sisters = findByRelLabel("Sister");
                const siblings = [...brothers, ...sisters];
                if (siblings.length > 0) {
                    inferred.push({
                        type: "PARENT_OF",
                        description: `${this.formatFamilyName(siblings[0])} (${siblings[0].relationship_label}) is parent of new ${relType.toLowerCase()}`,
                        person_a_pk: siblings[0].person_pk,
                        person_b_pk: null,
                    });
                }
                this.addMemberInferredLinks = inferred;
            }

            // ── COUSIN ───────────────────────────────────────
            // Parent's sibling's child. Link: existing uncle/aunt PARENT_OF new cousin
            if (relType === "COUSIN") {
                const uncles = findByRelLabel("Uncle");
                const aunts = findByRelLabel("Aunt");
                const unclesAunts = [...uncles, ...aunts];
                if (unclesAunts.length > 0) {
                    inferred.push({
                        type: "PARENT_OF",
                        description: `${this.formatFamilyName(unclesAunts[0])} (${unclesAunts[0].relationship_label}) is parent of new cousin`,
                        person_a_pk: unclesAunts[0].person_pk,
                        person_b_pk: null,
                    });
                }
                this.addMemberInferredLinks = inferred;
            }

            // ── GUARDIAN / WARD / OTHER ──────────────────────
            // No automatic graph links — these are non-standard.
            // User must manually set tree link if desired.
            if (relType === "GUARDIAN" || relType === "WARD" || relType === "OTHER") {
                // No inferred links
                this.addMemberInferredLinks = [];
            }
        },

        // Enhancement 4: Filter search results for spouse eligibility
        _filterForSpouse(results) {
            // Determine viewer's gender to find opposite
            const viewerGender = this.person.gender_code;
            if (!viewerGender) return results; // can't filter without viewer's gender

            const oppositeGender = viewerGender === "MALE" ? "FEMALE" : "MALE";

            // Exclude persons who already have spouses (check graph for existing SPOUSE_OF links)
            // We can only check within this family — external spouse data isn't available
            // Filter: opposite gender only
            return results.filter(r => {
                // gender_code may come from membership search — check if available
                if (r.gender_code && r.gender_code !== oppositeGender) return false;
                if (r.gender_name) {
                    const gn = r.gender_name.toUpperCase();
                    if (oppositeGender === "MALE" && gn !== "MALE") return false;
                    if (oppositeGender === "FEMALE" && gn !== "FEMALE") return false;
                }
                return true;
            });
        },

        async confirmAddMember() {
            if (!this.addMemberSelected || !this.addMemberRelType) return;
            if (!this.family) return;

            // In-law validation: must select a spouse connector or opt for "not in tree"
            if (this.isInlawRelType() && !this.addMemberInlawSpouse && !this.addMemberInlawSpouseNotInTree) {
                this.addMemberError = "Please select which existing member is the spouse, or choose 'Spouse not in Family Tree'.";
                return;
            }

            this.addMemberSaving = true;
            this.addMemberError = "";
            try {
                // Step 1: Add member to this family
                const payload = {
                    person_pk: this.addMemberSelected.person_pk,
                    relationship_type_code: this.addMemberRelType,
                    remarks: this.addMemberRemarks || null,
                };
                if (this.addMemberLinkType && this.addMemberLinkTarget) {
                    payload.link_type = this.addMemberLinkType;
                    payload.link_target_person_pk = this.addMemberLinkTarget;
                }

                const res = await NSSAuth.apiFetch(
                    `/api/v1/family/families/${this.family.family_group_pk}/members`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload),
                    }
                );

                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(NSS.errorMessage(err, res.status));
                }

                // Step 2: Auto-create inferred links
                if (this.addMemberInferredLinks.length > 0) {
                    const newPersonPk = this.addMemberSelected.person_pk;
                    for (const link of this.addMemberInferredLinks) {
                        try {
                            const linkPayload = {
                                person_a_pk: link.person_a_pk || newPersonPk,
                                person_b_pk: link.person_b_pk || newPersonPk,
                                link_type: link.type,
                            };
                            await NSSAuth.apiFetch(
                                `/api/v1/family/families/${this.family.family_group_pk}/links`,
                                {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify(linkPayload),
                                }
                            );
                        } catch (linkErr) {
                            console.warn("[Dashboard] Failed to create inferred link:", link, linkErr);
                        }
                    }
                }

                // Refresh family data
                this.closeAddMemberModal();
                await this._fetchFamilyDetail();
            } catch (err) {
                this.addMemberError = err.message || "Failed to add member";
            } finally {
                this.addMemberSaving = false;
            }
        },

        // ── Remove member (head or admin) ─────────────────
        isCurrentHead() {
            if (!this.familyHeadHistory || !this.user.person_pk) return false;
            return this.familyHeadHistory.some(
                h => h.person_pk === this.user.person_pk && !h.effective_to
            );
        },

        isCurrentAdmin() {
            if (!this.familyAdmins || !this.user.person_pk) return false;
            return this.familyAdmins.some(
                a => a.person_pk === this.user.person_pk
            );
        },

        isMemberAdmin(personPk) {
            return this.familyAdmins.some(a => a.person_pk === personPk);
        },

        /**
         * Can the viewer change this family's membership (add/remove)?
         *
         * Mirrors _require_family_manage() in api/routers/family.py: the
         * family head or a current family admin. Being merely a member is
         * not enough — the API returns 403, so any affordance shown to a
         * plain member would be a button that cannot work.
         *
         * Org administrators holding FAMILY_MANAGE are not considered here
         * because they reach families through the org-level family browser,
         * not through this panel, which only ever shows the viewer's own
         * family.
         */
        canManageMembers() {
            return this.isCurrentHead() || this.isCurrentAdmin();
        },

        // ── Transfer Head (FAM-049) ─────────────────────
        // Opens the themed Transfer Headship modal (dashboard-styled, matching
        // Add Member / Create Family) instead of a plain text confirm().
        transferHead(personPk) {
            if (!this.family) return;
            const member = this.familyMembers.find(m => m.person_pk === personPk);
            if (!member) return;
            this.transferHeadError = "";
            this.transferHeadTarget = member;
        },

        closeTransferHeadModal() {
            if (this.transferHeadSubmitting) return;
            this.transferHeadTarget = null;
            this.transferHeadError = "";
        },

        async submitTransferHead() {
            if (!this.family || !this.transferHeadTarget) return;
            this.transferHeadSubmitting = true;
            this.transferHeadError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/family/families/${this.family.family_group_pk}/transfer-head`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ person_pk: this.transferHeadTarget.person_pk }),
                    }
                );
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(NSS.errorMessage(err, res.status));
                }
                this.transferHeadTarget = null;
                await this._fetchFamilyDetail();
            } catch (err) {
                this.transferHeadError = err.message || "Failed to transfer headship";
            } finally {
                this.transferHeadSubmitting = false;
            }
        },

        // ── Assign Admin (FAM-046) ──────────────────────
        // Opens the themed Assign Admin modal instead of a plain text confirm().
        assignAdmin(personPk) {
            if (!this.family) return;
            const member = this.familyMembers.find(m => m.person_pk === personPk);
            if (!member) return;
            this.assignAdminError = "";
            this.assignAdminTarget = member;
        },

        closeAssignAdminModal() {
            if (this.assignAdminSubmitting) return;
            this.assignAdminTarget = null;
            this.assignAdminError = "";
        },

        async submitAssignAdmin() {
            if (!this.family || !this.assignAdminTarget) return;
            this.assignAdminSubmitting = true;
            this.assignAdminError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/family/families/${this.family.family_group_pk}/admins`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ person_pk: this.assignAdminTarget.person_pk }),
                    }
                );
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(NSS.errorMessage(err, res.status));
                }
                this.assignAdminTarget = null;
                await this._fetchFamilyDetail();
            } catch (err) {
                this.assignAdminError = err.message || "Failed to assign admin";
            } finally {
                this.assignAdminSubmitting = false;
            }
        },

        // ── Revoke Admin (FAM-046) ──────────────────────
        async revokeAdmin(personPk) {
            if (!this.family) return;
            const member = this.familyMembers.find(m => m.person_pk === personPk);
            const name = member ? this.formatFamilyName(member) : "this member";
            const ok = await NSSDialog.confirm(
                `Revoke admin role from ${name}?`,
                { title: "Revoke Admin", confirmText: "Revoke", confirmClass: "btn-error" }
            );
            if (!ok) return;

            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/family/families/${this.family.family_group_pk}/admins`,
                    {
                        method: "DELETE",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ person_pk: personPk }),
                    }
                );
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(NSS.errorMessage(err, res.status));
                }
                await this._fetchFamilyDetail();
            } catch (err) {
                await NSSDialog.alert(err.message || "Failed to revoke admin");
            }
        },

        async removeFamilyMember(personPk) {
            if (!this.family) return;
            const member = this.familyMembers.find(m => m.person_pk === personPk);
            const name = member ? this.formatFamilyName(member) : "this member";
            const ok = await NSSDialog.confirm(
                `Remove ${name} from this family? This action can be reversed by an admin.`,
                { title: "Remove Member", confirmText: "Remove", confirmClass: "btn-error" }
            );
            if (!ok) return;

            this.removeMemberLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/family/families/${this.family.family_group_pk}/members`,
                    {
                        method: "DELETE",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            person_pk: personPk,
                            remarks: "Removed via dashboard by family head",
                        }),
                    }
                );

                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(NSS.errorMessage(err, res.status));
                }

                // Clear selected if removed
                if (this.selectedPerson?.person_pk === personPk) {
                    this.selectedPerson = null;
                    this.selectedPersonDetail = null;
                    this.selectedPersonMembership = null;
                }

                // Refresh
                await this._fetchFamilyDetail();
            } catch (err) {
                await NSSDialog.alert(err.message || "Failed to remove member");
            } finally {
                this.removeMemberLoading = false;
            }
        },

        // ── Edit Profile ─────────────────────────────────

        // ── Membership self-service requests ──────────────────
        // Sakha Transfer (MBR-048) and Apply for Darshak (MBR-049) are
        // both membership-change requests on the same two-step request/
        // release/accept workflow (api/routers/membership_change_
        // request.py) — these two entry points just pre-set request_type
        // and open the shared modal; openChangeRequestModal() does the
        // rest.
        applyDarshak() {
            this.openChangeRequestModal("DARSHAK");
        },

        requestSakhaTransfer() {
            this.openChangeRequestModal("TRANSFER");
        },

        async openChangeRequestModal(requestType) {
            this.changeRequestType = requestType;
            this.changeRequestOrgPk = "";
            this.changeRequestReason = "";
            this.changeRequestError = "";
            this.showChangeRequestModal = true;
            if (this.changeRequestSakhaList.length === 0) {
                await this._loadChangeRequestSakhaList();
            }
        },

        closeChangeRequestModal() {
            this.showChangeRequestModal = false;
        },

        // Same public-safe /organizations/selectable endpoint Create
        // Family's Sakha picker uses (authenticated members only, no
        // ORGANIZATION_VIEW required) — unfiltered, capped at
        // NSS.MAX_PAGE_SIZE. No geography cascade here; the destination
        // Sakha list for a transfer/Darshak request is small enough that
        // the near-me filter Create Family needs isn't warranted yet.
        // Excludes the member's own current Sakha — attending or
        // transferring to the Sakha you're already affiliated with isn't
        // a valid request either way.
        async _loadChangeRequestSakhaList() {
            this.changeRequestSakhaLoading = true;
            try {
                const params = new URLSearchParams({
                    type_code: "SAKHA_SANGHA",
                    limit: NSS.MAX_PAGE_SIZE,
                });
                const res = await NSSAuth.apiFetch(
                    `/api/v1/organization/organizations/selectable?${params.toString()}`
                );
                if (res.ok) {
                    const list = await res.json();
                    const currentOrgPk = this.member?.organization_pk;
                    this.changeRequestSakhaList = currentOrgPk
                        ? list.filter(s => s.organization_pk !== currentOrgPk)
                        : list;
                }
            } catch (e) {
                console.error("Failed to load Sakha list", e);
            } finally {
                this.changeRequestSakhaLoading = false;
            }
        },

        async submitChangeRequest() {
            if (!this.changeRequestOrgPk) {
                this.changeRequestError = "Please select a Sakha.";
                return;
            }
            this.changeRequestError = "";
            this.changeRequestSaving = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/membership/change-requests", {
                    method: "POST",
                    body: JSON.stringify({
                        sangha_sevi_pk: this.user.sangha_sevi_pk,
                        request_type: this.changeRequestType,
                        new_organization_pk: this.changeRequestOrgPk,
                        transfer_reason: this.changeRequestReason.trim() || null,
                    }),
                });
                if (res.ok) {
                    this.showChangeRequestModal = false;
                    await this._loadMyChangeRequests();
                    await NSSDialog.alert(
                        "Your request has been submitted and is awaiting your current Sakha's decision.",
                        this.changeRequestType === "DARSHAK" ? "Apply for Darshak" : "Request Sakha Transfer"
                    );
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.changeRequestError = data.detail || "Failed to submit request.";
                }
            } catch (e) {
                console.error("Failed to submit change request", e);
                this.changeRequestError = "Unable to connect to server.";
            } finally {
                this.changeRequestSaving = false;
            }
        },

        // My Change Requests — self-scoped list (list_change_requests()
        // forces this to the caller's own rows when they hold neither
        // MEMBERSHIP_VIEW nor MEMBERSHIP_APPROVE, mirroring the self-or-
        // permission pattern Person/Membership detail already use).
        async _loadMyChangeRequests() {
            if (!this.user?.sangha_sevi_pk) return;
            this.myChangeRequestsLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    // page_size caps at 100 server-side (api/routers/
                    // membership_change_request.py le=100) — NSS.MAX_PAGE_SIZE
                    // (500) is for the separate `limit`-param family of
                    // endpoints (api/helpers.py MAX_LIMIT) and 500 here 422s.
                    `/api/v1/membership/change-requests?page_size=100`
                );
                if (res.ok) {
                    const data = await res.json();
                    this.myChangeRequests = data.requests || [];
                }
            } catch (e) {
                console.error("Failed to load change requests", e);
            } finally {
                this.myChangeRequestsLoading = false;
            }
        },

        // ── Send Application tab ────────────────────────────────────────
        // Loads the 4 dropdown sources (never duplicated SQL — these call
        // the real governance endpoints) every time the tab is opened.
        // Owner report, 2026-10-25 (two separate reports):
        //   1. a failed fetch was only ever logged to the console, never
        //      shown on screen — now surfaced via sendApp.officeBearersError
        //      (same .alert-msg.alert-error pattern used everywhere else).
        //   2. "it should refresh when I reselect the value from the
        //      dropdown.. but still I have to change tab and come back" —
        //      this used to be a permanent one-time latch
        //      (`officeBearersLoaded`, set true in `finally` and never
        //      reset): the FIRST visit to this tab fetched once, and every
        //      later visit — including after an admin seated/removed an
        //      office-bearer elsewhere — short-circuited on stale, possibly
        //      years-old in-memory data for the rest of the page's life.
        //      Only a full page reload (a fresh Alpine instance) ever
        //      actually refetched. Replaced with officeBearersLoading, an
        //      IN-FLIGHT guard only (blocks a second fetch while one is
        //      already running — e.g. a fast double tab-switch — but never
        //      blocks the NEXT visit), matching this project's established
        //      "refetch on tab reopen" fix for this exact bug class.
        async _loadSendApplicationOfficeBearers() {
            if (this.sendApp.officeBearersLoading) return;
            this.sendApp.officeBearersLoading = true;
            this.sendApp.officeBearersError = "";
            const isOfficeBearer = m => m.person_pk && m.position_name && m.position_name.toLowerCase() !== "member";
            try {
                const [mineRes, nationalRes] = await Promise.all([
                    NSSAuth.apiFetch("/api/v1/governance/public/my-sakha-bodies"),
                    NSSAuth.apiFetch("/api/v1/governance/public/national-bodies"),
                ]);
                const errors = [];
                if (mineRes.ok) {
                    const data = await mineRes.json();
                    const bodies = data.bodies || [];
                    // Split by body_type_name (2026-10-25) — Mahila/Sevak
                    // office-bearers get their own clearly-labelled
                    // addressing-mode options instead of being merged into
                    // the generic "office-bearer of my Sakha" bucket.
                    this.sendApp.sakhaOfficeBearers = bodies
                        .filter(b => b.body_type_name === "Sakha Governing Body")
                        .flatMap(b => b.members || [])
                        .filter(isOfficeBearer);
                    this.sendApp.mahilaOfficeBearers = bodies
                        .filter(b => b.body_type_name === "Mahila Parichalana Mandali")
                        .flatMap(b => b.members || [])
                        .filter(isOfficeBearer);
                    this.sendApp.sevakOfficeBearers = bodies
                        .filter(b => b.body_type_name === "Sevak Sangha")
                        .flatMap(b => b.members || [])
                        .filter(isOfficeBearer);
                } else {
                    errors.push(`your Sakha's office-bearers (${mineRes.status})`);
                }
                if (nationalRes.ok) {
                    const data = await nationalRes.json();
                    const bodies = data.bodies || [];
                    const kendraBody = bodies.find(b => b.body_type_name === "Kendra Governing Body");
                    this.sendApp.kendraOfficeBearers = kendraBody
                        ? (kendraBody.members || []).filter(isOfficeBearer)
                        : [];
                    // The central Mahila Parichalana Mandali — same
                    // body_type_name as the local one (not tier-
                    // distinguishing), disambiguated here simply by coming
                    // from the national-bodies response rather than
                    // my-sakha-bodies.
                    const kendraMahilaBody = bodies.find(b => b.body_type_name === "Mahila Parichalana Mandali");
                    this.sendApp.kendraMahilaOfficeBearers = kendraMahilaBody
                        ? (kendraMahilaBody.members || []).filter(isOfficeBearer)
                        : [];
                } else {
                    errors.push(`Kendra office-bearers (${nationalRes.status})`);
                }
                if (errors.length) {
                    this.sendApp.officeBearersError = `Failed to load ${errors.join(" and ")}. Try reloading the page.`;
                }
            } catch (e) {
                console.error("Failed to load office-bearer lookups", e);
                this.sendApp.officeBearersError = "Failed to load office-bearer lookups — check your connection and reload.";
            } finally {
                this.sendApp.officeBearersLoading = false;
            }
        },

        // Fail-closed gender gates (owner-confirmed 2026-10-25) for the
        // Mahila/Sevak addressing-mode options and picker blocks — reuse
        // this.person.gender_code (already loaded by _fetchPersonalDetail()
        // for the Personal tab; see line ~4198) rather than a new fetch.
        // Unset/unknown gender (including the seeded 'OTHER' value) must
        // show/allow NEITHER gendered option, mirroring the backend's
        // _require_gender() in correspondence.py.
        sendAppIsFemale() {
            return this.person && this.person.gender_code === "FEMALE";
        },

        sendAppIsMale() {
            return this.person && this.person.gender_code === "MALE";
        },

        resetSendApplicationForm() {
            this.sendApp.form = {
                addressing_mode: "SAKHA_ORG",
                recipient_person_pk: "",
                subject: "",
                remarks: "",
                follow_up_date: "",
            };
            this.sendApp.error = "";
        },

        async submitSendApplication() {
            const f = this.sendApp.form;
            if (!f.subject.trim()) {
                this.sendApp.error = "Please enter a subject.";
                return;
            }
            if (f.addressing_mode !== "SAKHA_ORG" && !f.recipient_person_pk) {
                this.sendApp.error = "Please select a recipient.";
                return;
            }
            this.sendApp.error = "";
            this.sendApp.saving = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/correspondence/my-applications", {
                    method: "POST",
                    body: JSON.stringify({
                        addressing_mode: f.addressing_mode,
                        recipient_person_pk: f.addressing_mode === "SAKHA_ORG" ? null : f.recipient_person_pk,
                        subject: f.subject.trim(),
                        remarks: f.remarks.trim() || null,
                        follow_up_date: f.follow_up_date || null,
                    }),
                });
                if (res.ok) {
                    this.resetSendApplicationForm();
                    this.sendApp.subTab = "history";
                    this.sendApp.historyLoaded = false;
                    await this.loadSendApplicationHistory();
                    await NSSDialog.alert("Your application has been submitted.", "Send Application");
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.sendApp.error = data.detail || "Failed to submit application.";
                }
            } catch (e) {
                console.error("Failed to submit application", e);
                this.sendApp.error = "Unable to connect to server.";
            } finally {
                this.sendApp.saving = false;
            }
        },

        async loadSendApplicationHistory() {
            if (this.sendApp.historyLoaded) return;
            this.sendApp.historyLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    // Item 2 fix (2026-10-23): /my-involvements, not
                    // /my-applications — every correspondence the member is
                    // attached to in ANY role (sender, recipient, responsible
                    // party, or an approver at either step), not just what
                    // they personally sent. page_size caps at 100 server-side
                    // (api/routers/correspondence.py le=100) — see the
                    // change-requests fix above for why NSS.MAX_PAGE_SIZE
                    // (500) 422s here.
                    `/api/v1/correspondence/my-involvements?page_size=100`
                );
                if (res.ok) {
                    const data = await res.json();
                    this.sendApp.history = data.items || [];
                }
            } catch (e) {
                console.error("Failed to load application history", e);
            } finally {
                this.sendApp.historyLoading = false;
                this.sendApp.historyLoaded = true;
            }
        },

        // Derives the viewer's role(s) on one /my-involvements row by
        // comparing sender/recipient/responsible/approver person_pks
        // against the logged-in user's own person_pk (item 2) — never
        // fabricates a role if nothing matches (shouldn't happen given the
        // endpoint's own filter, but the UI codes defensively rather than
        // assuming).
        sendAppRolesFor(item) {
            const myPk = this.user && this.user.person_pk;
            if (!item || !myPk) return [];
            const roles = [];
            if (item.sender_person_pk === myPk) roles.push("Sender");
            if (item.recipient_person_pk === myPk) roles.push("Addressed to me");
            if (item.responsible_person_pk === myPk) roles.push("Responsible party");
            for (const step of item.approval_steps || []) {
                if (step.approver_person_pk === myPk) {
                    roles.push(step.step_number === 1 ? "Step 1 approver" : `Step ${step.step_number} approver`);
                }
            }
            return roles;
        },

        // Finds the approval-chain step (1 or 2) that is this viewer's own
        // PENDING decision on a given /pending-for-me row — generalized
        // 2026-10-23 so the pending-decision panel and decideSendApplication
        // work identically for a step-1 (Sakha President) or step-2 (Kendra
        // office-bearer) item, instead of assuming step_number is always 1.
        sendAppMyStepFor(item) {
            const myPk = this.user && this.user.person_pk;
            if (!item || !myPk) return null;
            return (item.approval_steps || []).find(
                s => s.approver_person_pk === myPk && s.step_status === "PENDING"
            ) || null;
        },

        // "Approve & Forward" only makes sense when there is a real step 2
        // to forward TO. A collapsed single-step chain (owner request,
        // 2026-10-25: step-1 and step-2 approver were the same person, so
        // creation never inserted a redundant step 2 — see
        // correspondence.py::create_member_application) has exactly one
        // approval_steps row, and that row's own approval is already the
        // chain's terminal decision — so the button must read plain
        // "Approve", same as an ordinary step-2 decision.
        sendAppApproveLabel(item) {
            const myStep = this.sendAppMyStepFor(item);
            const hasStep2 = (item.approval_steps || []).length > 1;
            return (myStep && myStep.step_number === 1 && hasStep2) ? "Approve & Forward" : "Approve";
        },

        async _loadPendingApprovals() {
            try {
                const res = await NSSAuth.apiFetch(
                    // page_size caps at 100 server-side — see the
                    // change-requests fix above for why NSS.MAX_PAGE_SIZE
                    // (500) 422s here.
                    `/api/v1/correspondence/approval-steps/pending-for-me?page_size=100`
                );
                if (res.ok) {
                    const data = await res.json();
                    this.sendApp.pendingApprovals = data.items || [];
                }
            } catch (e) {
                console.error("Failed to load pending approvals", e);
            }
        },

        async decideSendApplication(item, decision) {
            // Generalized 2026-10-23 (owner item: step-2 decisions) — finds
            // WHICHEVER step (1 or 2) is this viewer's own pending decision
            // on this item, instead of hardcoding step_number === 1. The
            // backend (/approval-steps/{step_pk}/decision) independently
            // re-verifies the caller still holds that seat for either step.
            const myStep = this.sendAppMyStepFor(item);
            if (!myStep) return;
            this.sendApp.deciding = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/correspondence/approval-steps/${myStep.correspondence_approval_step_pk}/decision`,
                    {
                        method: "POST",
                        body: JSON.stringify({
                            decision,
                            remarks: (this.sendApp.decisionRemarks[item.correspondence_pk] || "").trim() || null,
                        }),
                    }
                );
                if (res.ok) {
                    delete this.sendApp.decisionRemarks[item.correspondence_pk];
                    await this._loadPendingApprovals();
                } else {
                    const data = await res.json().catch(() => ({}));
                    await NSSDialog.alert(data.detail || "Failed to record decision.", "Send Application");
                }
            } catch (e) {
                console.error("Failed to record approval decision", e);
                await NSSDialog.alert("Unable to connect to server.", "Send Application");
            } finally {
                this.sendApp.deciding = false;
            }
        },


        startEditProfile() {
            this.profileForm = {
                mobile_number: this.person.mobile_number || "",
                country_phone_code: this.person.country_phone_code || "+91",
                email: this.person.email || "",
                date_of_birth: this.person.date_of_birth ? this.person.date_of_birth.substring(0, 10) : "",
            };
            this.profileError = "";
            this.profileSuccess = "";
            this.editingProfile = true;
        },

        cancelEditProfile() {
            this.editingProfile = false;
            this.profileError = "";
            this.profileSuccess = "";
        },

        async saveProfile() {
            this.profileSaving = true;
            this.profileError = "";
            this.profileSuccess = "";
            try {
                // MBR-CONTACT-01/02: validate the effective contact values the
                // profile form holds before building the PATCH payload.
                const pfMobileErr = NSS.validateMobile((this.profileForm.country_phone_code || "").trim(), (this.profileForm.mobile_number || "").trim());
                if (pfMobileErr) { this.profileError = pfMobileErr; this.profileSaving = false; return; }
                const pfEmailErr = NSS.validateEmail((this.profileForm.email || "").trim());
                if (pfEmailErr) { this.profileError = pfEmailErr; this.profileSaving = false; return; }

                // Build payload with only changed fields
                const payload = {};
                if (this.profileForm.mobile_number !== (this.person.mobile_number || ""))
                    payload.mobile_number = this.profileForm.mobile_number || null;
                if (this.profileForm.country_phone_code !== (this.person.country_phone_code || "+91"))
                    payload.country_phone_code = this.profileForm.country_phone_code || null;
                if (this.profileForm.email !== (this.person.email || ""))
                    payload.email = this.profileForm.email || null;
                const origDob = this.person.date_of_birth ? this.person.date_of_birth.substring(0, 10) : "";
                if (this.profileForm.date_of_birth !== origDob)
                    payload.date_of_birth = this.profileForm.date_of_birth || null;

                if (Object.keys(payload).length === 0) {
                    this.profileError = "No changes detected.";
                    return;
                }

                const res = await NSSAuth.apiFetch("/api/v1/auth/profile", {
                    method: "PATCH",
                    body: JSON.stringify(payload),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    this.profileError = NSS.errorMessage(data, res.status);
                    return;
                }
                this.profileSuccess = data.message || "Profile updated.";
                this.editingProfile = false;

                // Refresh person data
                const personRes = await NSSAuth.apiFetch(`/api/v1/person/persons/${this.user.person_pk}`);
                if (personRes.ok) {
                    this.person = await personRes.json();
                }
            } catch (err) {
                this.profileError = err.message || "Failed to update profile.";
            } finally {
                this.profileSaving = false;
            }
        },

        // ── Active sessions (personal tab) ────────────────
        async loadSessions() {
            this.sessionsLoading = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/auth/sessions");
                if (!res.ok) throw new Error(res.statusText);
                const data = await res.json();
                // Backend schema for this list endpoint isn't finalized yet —
                // accept either a bare array (this codebase's established
                // list-endpoint convention, e.g. family members) or a
                // {sessions: [...]} wrapper (as described in the task spec).
                this.sessions = Array.isArray(data) ? data : (data.sessions || []);
            } catch (err) {
                console.error("[Dashboard] loadSessions failed:", err);
            } finally {
                this.sessionsLoading = false;
            }
        },

        async revokeSession(sessionPk) {
            const ok = await NSSDialog.confirm(
                "Log out this device? It will need to sign in again.",
                { title: "Log Out Device", confirmText: "Log Out", confirmClass: "btn-error" }
            );
            if (!ok) return;

            this.sessionsError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/auth/sessions/${sessionPk}`, {
                    method: "DELETE",
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(NSS.errorMessage(err, res.status));
                }
                await this.loadSessions();
            } catch (err) {
                this.sessionsError = err.message || "Failed to log out device.";
            }
        },

        // ── Create Family ───────────────────────────────

        async _loadSakhaList() {
            if (this.createFamilyCountries.length === 0) {
                try {
                    // Public /register/* geo endpoints — a regular member does
                    // NOT hold FOUNDATION_VIEW, so /foundation/countries would
                    // 403 and the cascade would never populate.
                    const res = await NSSAuth.apiFetch(`/api/v1/register/countries`);
                    if (res.ok) this.createFamilyCountries = await res.json();
                } catch (e) {
                    console.error("Failed to load countries", e);
                }
            }
            await this._loadFilteredSakhas();
        },

        // Re-queries the selectable-Sakha list scoped to the chosen
        // country/state/district, falling back to the unfiltered list when
        // none is selected. country_pk is always populated on a Sakha org,
        // so it filters reliably; state_pk/district_pk depend on the PIN
        // backfill in 05_sakha_branches.sql.
        async _loadFilteredSakhas() {
            this.createFamilySakhaLoading = true;
            try {
                const params = new URLSearchParams({
                    type_code: "SAKHA_SANGHA",
                    limit: NSS.MAX_PAGE_SIZE,
                });
                if (this.createFamilyCountryPk) params.set("country_pk", this.createFamilyCountryPk);
                if (this.createFamilyStatePk) params.set("state_pk", this.createFamilyStatePk);
                if (this.createFamilyDistrictPk) params.set("district_pk", this.createFamilyDistrictPk);
                const res = await NSSAuth.apiFetch(
                    `/api/v1/organization/organizations/selectable?${params.toString()}`
                );
                if (res.ok) {
                    const data = await res.json();
                    this.createFamilySakhaList = data;
                }
            } catch (e) {
                console.error("Failed to load Sakha list", e);
            } finally {
                this.createFamilySakhaLoading = false;
            }
        },

        async onCreateFamilyCountryChange() {
            this.createFamilyStatePk = "";
            this.createFamilyDistrictPk = "";
            this.createFamilyStates = [];
            this.createFamilyDistricts = [];
            this.createFamilySakhaPk = "";
            if (this.createFamilyCountryPk) {
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/register/states?country_pk=${this.createFamilyCountryPk}`);
                    if (res.ok) this.createFamilyStates = await res.json();
                } catch (e) {
                    console.error("Failed to load states", e);
                }
            }
            await this._loadFilteredSakhas();
        },

        async onCreateFamilyStateChange() {
            this.createFamilyDistrictPk = "";
            this.createFamilyDistricts = [];
            this.createFamilySakhaPk = "";
            if (this.createFamilyStatePk) {
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/register/districts?state_pk=${this.createFamilyStatePk}`);
                    if (res.ok) this.createFamilyDistricts = await res.json();
                } catch (e) {
                    console.error("Failed to load districts", e);
                }
            }
            await this._loadFilteredSakhas();
        },

        async onCreateFamilyDistrictChange() {
            this.createFamilySakhaPk = "";
            await this._loadFilteredSakhas();
        },

        // ── Find a Sakha / Patha Chakra (member dashboard directory) ────
        //
        // Both a browsable directory and a search: opening the tab loads
        // every active Sakha Sangha + Patha Chakra (capped at
        // NSS.MAX_PAGE_SIZE) with no filter, which doubles as the
        // directory; the type checkboxes + country/state/district cascade
        // + free-text box narrow it. Reuses the public /register/* geo
        // endpoints (member-safe, no FOUNDATION_VIEW) and the
        // authenticated-only /organizations/selectable endpoint — same
        // pattern as Create Family's Sakha picker.

        async _loadFindOrgDirectory() {
            if (this.findOrgCountries.length === 0) {
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/register/countries`);
                    if (res.ok) this.findOrgCountries = await res.json();
                } catch (e) {
                    console.error("Failed to load countries", e);
                }
            }
            await this._loadFindOrgResults();
            this._loadFindOrgOfficeBearers();
        },

        // One bulk fetch of every Sakha's President/Secretary (name + mobile),
        // merged into directory rows client-side via orgOfficeBearers(pk).
        // Public endpoint — any logged-in member. Fire-and-forget: the row
        // template renders fine before (and without) this data.
        async _loadFindOrgOfficeBearers() {
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/public/sakha-office-bearers`
                );
                if (res.ok) {
                    const data = await res.json();
                    this.findOrgOfficeBearers = data.office_bearers || {};
                }
            } catch (e) {
                console.error("Failed to load Sakha office-bearers", e);
            }
        },

        // President/Secretary entry for a directory row, or null (Patha
        // Chakra rows and Sakhas with no Governing Body have no entry).
        orgOfficeBearers(organizationPk) {
            return this.findOrgOfficeBearers[organizationPk] || null;
        },

        // ── Governance tab loader ────────────────────────
        async _loadGovernanceBodies() {
            this.govLoading = true;
            this.govError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/public/national-bodies`
                );
                if (res.ok) {
                    const data = await res.json();
                    this.govBodies = data.bodies || [];
                    await this._mergeMahilaInheritedParichalak();
                } else {
                    this.govError = "Failed to load governance bodies.";
                }
            } catch (e) {
                console.error("Failed to load governance bodies", e);
                this.govError = "Failed to load governance bodies.";
            } finally {
                this.govLoading = false;
                this.govLoaded = true;
            }
        },

        // ── Item 4 — viewer's own Sakha-level bodies ─────────
        // The member's own Sakha Governing Body + that Sakha's org-scoped
        // Mahila Parichalana Mandali, with current composition. Login-only
        // public endpoint; empty for members with no active Sakha Sangha
        // membership. Rendered in the same single-banner style as item 9.
        async _loadMySakhaBodies() {
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/public/my-sakha-bodies`
                );
                this.mySakhaBodies = res.ok ? ((await res.json()).bodies || []) : [];
            } catch (e) {
                console.error("Failed to load own Sakha governance bodies", e);
                this.mySakhaBodies = [];
            }
        },

        // Owner report, 2026-10-25: "to take the effect of removing on
        // behalf or to see the GB members, I have to switch to another tab
        // and come back to see it populate." Root cause: the "Absent —
        // Acting: X" annotation shown in the governance-body card comes
        // from govBodies/mySakhaBodies (acting_person_name, attached
        // server-side by _assemble_bodies_with_members), NOT from
        // myGovDelegations — but creating/ending a delegation, and
        // approving/rejecting one, only ever updated myGovDelegations (or
        // myPendingActingApprovals) in place. The card itself was never
        // told to re-fetch, so it kept showing the pre-mutation state
        // until something else (a tab switch) happened to reload it.
        // Shared by all three acting-delegation mutations below instead of
        // duplicating this pair of calls three times.
        async _refreshGovBodiesAfterActingChange() {
            await Promise.all([this._loadGovernanceBodies(), this._loadMySakhaBodies()]);
        },

        // ── Item 3 — inherited Parichalak on the NSS-wide Mahila PM ──
        // PARICHALAK is never a real row on the Mahila Parichalana Mandali
        // (it is excluded from that body's assignable positions) — the Kendra
        // Governing Body's current Parichalak is surfaced read-only so the
        // nine-member body reads completely.
        //
        // The admin dashboard reads this from the gated
        // /bodies/{pk}/inherited-positions endpoint; that endpoint requires
        // GOVERNANCE_VIEW, which ordinary members do NOT hold, so here the
        // inherited seat is derived from the Kendra Governing Body's Parichalak
        // member already present in the national-bodies payload (visible to
        // every member). The gated endpoint is still consulted as a fallback
        // for privileged viewers whose Kendra GB composition isn't populated.
        async _mergeMahilaInheritedParichalak() {
            const mahila = (this.govBodies || []).find(b => b.body_code === "KENDRA_MAHILA_PM");
            if (!mahila) return;
            mahila.members = mahila.members || [];
            // Already carries a Parichalak row? nothing to inherit-merge.
            if (mahila.members.some(m => (m.position_name || "").toLowerCase() === "parichalak")) return;

            let inherited = null;
            const kendraGb = (this.govBodies || []).find(b => b.body_code === "KENDRA_GB");
            const gbParichalak = (kendraGb?.members || [])
                .find(m => (m.position_name || "").toLowerCase() === "parichalak");
            if (gbParichalak) {
                inherited = { ...gbParichalak };
            } else {
                try {
                    const res = await NSSAuth.apiFetch(
                        `/api/v1/governance/bodies/${mahila.body_master_pk}/inherited-positions`
                    );
                    if (res.ok) {
                        const row = ((await res.json()).inherited || [])
                            .find(p => p.position_code === "PARICHALAK");
                        if (row) {
                            inherited = {
                                position_name: row.position_name,
                                position_code: row.position_code || "PARICHALAK",
                                person_name: row.person_name,
                                sangha_sevi_id: null, sakha_name: null,
                                anchalika_zilla_name: null,
                                effective_from: null, effective_to: null,
                            };
                        }
                    }
                } catch (e) {
                    // Gated for non-admins — the Kendra-GB-derived path is the
                    // member-visible source; silently skip when neither exists.
                }
            }

            const seat = inherited
                ? { ...inherited, position_name: "Parichalak", position_code: "PARICHALAK", is_inherited: true }
                : {
                    position_name: "Parichalak", position_code: "PARICHALAK", person_name: null,
                    sangha_sevi_id: null, sakha_name: null,
                    anchalika_zilla_name: null, effective_from: null,
                    effective_to: null, is_inherited: true,
                };
            mahila.members = [...mahila.members, seat];
            mahila.member_count = mahila.members.length;
        },

        // ── Items 9 + 4 — governance body banner helpers ────
        // One banner per board, grouped: the NSS-wide boards (national-bodies)
        // and the viewer's own Sakha boards (my-sakha-bodies, item 4).
        govBodyGroups() {
            const groups = [{
                key: "nss",
                label: "NSS-wide Governance Bodies",
                bodies: (this.govBodies || []).filter(b => b.scope_label === "NSS-wide"),
            }];
            if ((this.mySakhaBodies || []).length) {
                groups.push({ key: "sakha", label: "Your Sakha", bodies: this.mySakhaBodies });
            }
            return groups;
        },
        // At most govMemberCap members shown inline in a banner — President/
        // Secretary guaranteed a seat (owner fix, 2026-10-23). Shared with
        // org-dashboard.js's Governance section via NSS.govBodyDisplayMembers
        // (nss-config.js), not reimplemented here.
        govBodyDisplayMembers(b) {
            return NSS.govBodyDisplayMembers(b, this.govMemberCap);
        },
        // True when the board has more members than the inline cap (Advisory
        // Board) — drives the "Show all" control.
        govBodyHasMore(b) {
            return NSS.govBodyHasMore(b, this.govMemberCap);
        },
        openGovAllMembers(b) {
            this.govAllMembers = { open: true, body: b, filter: "" };
        },
        closeGovAllMembers() {
            this.govAllMembers = { open: false, body: null, filter: "" };
        },
        // The "show all" body's members filtered across all visible columns
        // (position, name, Sangha Sevi ID, Sakha, Anchalika/Zilla) —
        // client-side, over the already-loaded composition.
        govAllMembersFiltered() {
            const b = this.govAllMembers.body;
            if (!b) return [];
            return NSS.filterGovMembers(b.members || [], this.govAllMembers.filter);
        },


        // ── "Acting on My Behalf" delegation (owner asks #2/#3/#4) ─────
        // Loaders are deliberately silent on failure: this whole section is
        // an office-bearer-only extra, and an ordinary member must never see
        // an error card for an endpoint that simply has nothing for them.
        async _loadMyGovPositions() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/me/positions");
                this.myGovPositions = res.ok ? ((await res.json()).bodies || []) : [];
            } catch (e) {
                console.error("Failed to load my governance positions", e);
                this.myGovPositions = [];
            }
        },

        async _loadMyGovDelegations() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/me/acting-delegations");
                this.myGovDelegations = res.ok ? ((await res.json()).items || []) : [];
            } catch (e) {
                console.error("Failed to load my acting delegations", e);
                this.myGovDelegations = [];
            }
        },

        // ── "Awaiting My Approval" (Priority 1, 2026-10-24) — admin-
        // initiated acting assignments naming the caller as the nominee,
        // sitting PENDING_APPROVAL until the caller approves/rejects them.
        async _loadMyPendingActingApprovals() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/me/pending-acting-approvals");
                this.myPendingActingApprovals = res.ok ? ((await res.json()).items || []) : [];
            } catch (e) {
                console.error("Failed to load pending acting approvals", e);
                this.myPendingActingApprovals = [];
            }
        },

        async decideMyPendingActingApproval(a, decision) {
            // decision: "approve" | "reject".
            this.myPendingActingApprovalsError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/acting-assignments/${a.acting_position_assignment_pk}/${decision}`,
                    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) },
                );
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.myPendingActingApprovalsError = NSS.errorMessage(data, res.status);
                    return;
                }
                // Resolved either way — it is no longer pending, so it drops
                // off this list. If it was approved, it is now a live
                // delegation on the office-bearer's own "my delegations"
                // list too (that list is scoped by the CALLER's own seats,
                // not by who they delegated to — a row where the caller is
                // the nominee never appears there, so no refresh is needed
                // for myGovDelegations here) — but approving DOES make a
                // new "Absent — Acting: X" annotation appear on the
                // governance card for the seat the caller is now covering,
                // so govBodies/mySakhaBodies still need the same refresh.
                this.myPendingActingApprovals = this.myPendingActingApprovals.filter(
                    x => x.acting_position_assignment_pk !== a.acting_position_assignment_pk
                );
                this._refreshGovBodiesAfterActingChange();
            } catch (err) {
                this.myPendingActingApprovalsError = err.message || "Failed to record the decision.";
            }
        },

        // Owner ask #1, 2026-10-24: "every body should get their own table..
        // after selecting the on behalf they selected persons should be in a
        // single table for confirmation. for this you have to make all table
        // (indivual body table) mandatory to select." This REVERSES the
        // previous round's single combined candidate table (also an owner
        // ask) — deliberate.
        //
        // The unit of delegation is a (body, position-I-hold) PAIR, not a
        // body: in practice a caller holds one position per body, so this
        // renders as "one table per body" exactly as asked, but it stays
        // unambiguous if someone ever holds two seats on the same body
        // (then that body contributes two slots and `title` disambiguates
        // them by position name).
        //
        // Carried over unchanged from the previous combined list:
        //   - a slot whose (body, position) already has a LIVE delegation
        //     (ASSIGNED/ACTIVE/PENDING_APPROVAL — a pending-approval row
        //     still occupies the one-delegate-per-position slot, the same
        //     rule the server enforces) is omitted entirely;
        //   - the caller themselves is never a candidate.
        // New: a slot with no eligible candidate at all is also omitted —
        // it could never be satisfied, and since every table is mandatory
        // one such slot would otherwise block the Assign button forever.
        myGovDelegationSlots() {
            const me = this.user && this.user.person_pk;
            const LIVE_STATUSES = ["ASSIGNED", "ACTIVE", "PENDING_APPROVAL"];
            const slots = [];
            (this.myGovPositions || []).forEach(b => {
                const myPositions = b.my_positions || [];
                const multiSeat = myPositions.length > 1;
                myPositions.forEach(myPos => {
                    const taken = (this.myGovDelegations || []).some(d =>
                        d.body_master_pk === b.body_master_pk &&
                        d.position_master_pk === myPos.position_master_pk &&
                        LIVE_STATUSES.includes(d.acting_status)
                    );
                    if (taken) return;
                    const candidates = (b.members || [])
                        .filter(m => m.person_pk && m.person_pk !== me)
                        .map(m => ({
                            person_pk: m.person_pk,
                            person_name: m.person_name,
                            sangha_sevi_id: m.sangha_sevi_id,
                            position_code: m.position_code,
                            position_name: m.position_name,
                        }));
                    if (!candidates.length) return;
                    slots.push({
                        key: `${b.body_master_pk}|${myPos.position_master_pk}`,
                        body_master_pk: b.body_master_pk,
                        body_name: b.body_name,
                        // Drives NSS.govBodyTableClass() — the per-body-type
                        // table colour (owner ask #2). Comes from the server
                        // (_assemble_bodies_with_members), never inferred here.
                        body_type_code: b.body_type_code,
                        my_position_master_pk: myPos.position_master_pk,
                        my_position_code: myPos.position_code,
                        my_position_name: myPos.position_name,
                        title: multiSeat
                            ? `${b.body_name} — ${myPos.position_name}`
                            : b.body_name,
                        candidates,
                    });
                });
            });
            return slots;
        },

        // Picks the nominee for ONE slot. Each slot's radios share a group
        // name of their own (slot.key), so the slots are independent.
        selectDelegateFor(slot, personPk) {
            this.delegateForm.selections[slot.key] = personPk;
            this.delegateForm.error = "";
        },

        // "All tables mandatory" (owner ask #1) — a FRONTEND AFFORDANCE ONLY.
        // The server deliberately does not require a full set: the batch
        // endpoint validates each item on its own merits, so a future
        // surface may submit a subset.
        allSlotsSelected() {
            const slots = this.myGovDelegationSlots();
            if (!slots.length) return false;
            return slots.every(s => !!this.delegateForm.selections[s.key]);
        },

        // The combined confirmation list — one row per slot, resolving the
        // chosen candidate. This is also exactly the payload shape the batch
        // POST needs, so confirmDelegation() maps straight off it.
        myGovConfirmRows() {
            return this.myGovDelegationSlots().map(s => {
                const pk = this.delegateForm.selections[s.key];
                const c = (s.candidates || []).find(x => x.person_pk === pk) || null;
                return {
                    key: s.key,
                    body_master_pk: s.body_master_pk,
                    body_name: s.body_name,
                    body_type_code: s.body_type_code,
                    my_position_master_pk: s.my_position_master_pk,
                    my_position_code: s.my_position_code,
                    my_position_name: s.my_position_name,
                    person_pk: pk || "",
                    person_name: c ? c.person_name : "",
                    sangha_sevi_id: c ? c.sangha_sevi_id : "",
                };
            }).filter(r => r.person_pk);
        },

        // "Assign" does NOT submit — it validates and flips to the preview.
        startDelegateConfirm() {
            const f = this.delegateForm;
            f.error = "";
            if (!this.allSlotsSelected() || !f.effective_from) {
                f.error = "Select a member for every governance body, and an effective date.";
                return;
            }
            f.stage = "confirm";
        },

        backToDelegateForm() {
            this.delegateForm.stage = "form";
        },

        // One atomic batch POST, never N single POSTs: with every table
        // mandatory, a partial success (2 of 3 created, the 3rd rejected)
        // would leave a half-delegated state the member cannot easily
        // unwind. The server wraps the whole loop in a SAVEPOINT.
        async confirmDelegation() {
            const f = this.delegateForm;
            const rows = this.myGovConfirmRows();
            f.error = "";
            if (!rows.length) {
                f.error = "Select a member for every governance body, and an effective date.";
                f.stage = "form";
                return;
            }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/me/acting-delegations/batch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        items: rows.map(r => ({
                            body_master_pk: r.body_master_pk,
                            position_master_pk: r.my_position_master_pk,
                            person_pk: r.person_pk,
                        })),
                        effective_from: f.effective_from,
                        effective_to: f.effective_to || null,
                        reason: f.reason || null,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    f.stage = "form";
                    return;
                }
                // Newest first, matching GET /me/acting-delegations' order.
                // Each created row is ACTIVE, so myGovDelegationSlots()'s
                // live-delegation skip rule drops its slot on the next
                // render — the delegated tables disappear on their own.
                const created = (await res.json()).items || [];
                this.myGovDelegations = created.concat(this.myGovDelegations || []);
                f.selections = {};
                f.effective_from = ""; f.effective_to = ""; f.reason = "";
                f.stage = "form";
                this._refreshGovBodiesAfterActingChange();
            } catch (err) {
                f.error = err.message || "Failed to assign the delegations.";
                f.stage = "form";
            } finally {
                f.saving = false;
            }
        },

        // "current" = still live or awaiting a decision; "history" =
        // resolved and done. ACTING_STATUS_RESOLVED mirrors the DDL's
        // terminal values (ENDED/REJECTED/HISTORICAL) — ASSIGNED/ACTIVE/
        // PENDING_APPROVAL are all still "current" (owner request,
        // 2026-10-25: a dedicated history view for "on behalf").
        myGovDelegationsCurrent() {
            return (this.myGovDelegations || []).filter(
                d => !["ENDED", "REJECTED", "HISTORICAL"].includes(d.acting_status));
        },
        myGovDelegationsHistory() {
            return (this.myGovDelegations || []).filter(
                d => ["ENDED", "REJECTED", "HISTORICAL"].includes(d.acting_status));
        },

        // History split per body (owner request, 2026-10-25) — one table per
        // body_master_pk instead of one flat table spanning every body the
        // caller has ever held office on. Ordered by body_name so the list
        // is stable across reloads (the API itself orders by date, not body).
        myGovDelegationsHistoryGroups() {
            const groups = new Map();
            this.myGovDelegationsHistory().forEach(d => {
                const key = d.body_master_pk;
                if (!groups.has(key)) {
                    groups.set(key, { body_master_pk: key, body_name: d.body_name || "—", rows: [] });
                }
                groups.get(key).rows.push(d);
            });
            return Array.from(groups.values()).sort((a, b) => a.body_name.localeCompare(b.body_name));
        },

        // Sidebar "pending items" counts (owner request, 2026-10-25) — the
        // two things that sit waiting for THIS user's own decision: acting-
        // delegation nominations (Governance tab) and correspondence
        // applications routed to them as an office-bearer (Applications
        // tab). Kept as two separate counts (one badge per nav item,
        // mirroring admin.html's existing per-item count-badge pattern)
        // plus a combined total for anywhere a single number is wanted.
        myPendingActingApprovalsCount() {
            return (this.myPendingActingApprovals || []).length;
        },
        myPendingApplicationApprovalsCount() {
            return (this.sendApp.pendingApprovals || []).length;
        },
        // Open elections (GOV-BR-045) this member is entitled to vote in
        // AND has not yet cast every ballot for — item 2 follow-up
        // (2026-10-25): "pending items can be anything related to the
        // logged-in user", and an open ballot is squarely that. Each
        // election's own voted_position_pks (per-position, since one
        // election can elect several positions at once) is what makes
        // this accurate rather than just "is there an open election".
        myPendingElectionsToVote() {
            return (this.govOpenElections || []).filter(el => {
                const positions = new Set((el.nominations || []).map(n => n.position_master_pk));
                const voted = new Set(el.voted_position_pks || []);
                for (const p of positions) { if (!voted.has(p)) return true; }
                return false;
            });
        },
        myPendingElectionsCount() {
            return this.myPendingElectionsToVote().length;
        },
        myTotalPendingItemsCount() {
            return this.myPendingActingApprovalsCount() + this.myPendingApplicationApprovalsCount()
                + this.myPendingElectionsCount() + (this.pendingClaimsCount || 0);
        },

        // Mirrors admin.js::endGovActing — confirm(), POST, replace in place.
        async endMyDelegation(d) {
            const today = new Date().toISOString().slice(0, 10);
            const ok = await NSSDialog.confirm(
                `End ${d.person_name || "this member"}'s acting cover as ${d.position_name}?`,
                { title: "End Delegation", confirmText: "End", confirmClass: "danger" }
            );
            if (!ok) return;
            this.myGovDelegationsError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/me/acting-delegations/${d.acting_position_assignment_pk}/end`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ effective_to: today }),
                    },
                );
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.myGovDelegationsError = NSS.errorMessage(data, res.status);
                    return;
                }
                const updated = await res.json();
                const idx = this.myGovDelegations.findIndex(
                    x => x.acting_position_assignment_pk === d.acting_position_assignment_pk);
                if (idx !== -1) this.myGovDelegations[idx] = updated;
                this._refreshGovBodiesAfterActingChange();
            } catch (err) {
                this.myGovDelegationsError = err.message || "Failed to end the delegation.";
            }
        },


        // ── GOV-BR-043-A: Parichalak-only probationary candidate exception ──
        async _loadParichalakStatus() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/me/parichalak-status");
                this.isParichalak = res.ok ? !!(await res.json()).is_parichalak : false;
            } catch (e) {
                console.error("Failed to load Parichalak status", e);
                this.isParichalak = false;
            }
        },
        toggleParichalakExceptionForm() {
            this.parichalakExceptionForm.show = !this.parichalakExceptionForm.show;
            if (this.parichalakExceptionForm.show && this.parichalakExceptionForm.elections.length === 0) {
                this._loadParichalakExceptionElections();
            }
        },
        async _loadParichalakExceptionElections() {
            const f = this.parichalakExceptionForm;
            f.electionsLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections?election_status=NOMINATION&page_size=${NSS.MAX_PAGE_SIZE}`
                );
                f.elections = res.ok ? ((await res.json()).items || []) : [];
            } catch (e) {
                console.error("Failed to load elections open for nomination", e);
                f.elections = [];
            } finally {
                f.electionsLoading = false;
            }
        },
        async onParichalakExceptionElectionChange() {
            const f = this.parichalakExceptionForm;
            f.position_master_pk = "";
            f.positions = [];
            const election = f.elections.find(e => e.election_pk === f.election_pk);
            if (!election) return;
            f.positionsLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/bodies/${election.body_master_pk}/allowed-positions`
                );
                // GOV-BR-043-A only ever applies to Sakha President/Secretary —
                // narrow the dropdown here as a UX convenience; the server
                // (create_nomination / _require_candidate_eligible) remains the
                // sole source of truth and will reject anything else regardless.
                const all = res.ok ? ((await res.json()).positions || []) : [];
                f.positions = all.filter(p => p.position_code === "PRESIDENT" || p.position_code === "SECRETARY");
            } catch (e) {
                console.error("Failed to load allowed positions", e);
                f.positions = [];
            } finally {
                f.positionsLoading = false;
            }
        },
        onParichalakExceptionCandidateSearch() {
            const f = this.parichalakExceptionForm;
            clearTimeout(this._parichalakCandidateTimer);
            f.selectedCandidate = null;
            const q = (f.candidateQuery || "").trim();
            if (q.length < 2) { f.candidateResults = []; return; }
            this._parichalakCandidateTimer = setTimeout(async () => {
                f.candidateSearching = true;
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/membership/search?q=${encodeURIComponent(q)}`);
                    f.candidateResults = res.ok ? ((await res.json()).members || []) : [];
                } catch {
                    f.candidateResults = [];
                } finally {
                    f.candidateSearching = false;
                }
            }, 300);
        },
        selectParichalakExceptionCandidate(m) {
            const f = this.parichalakExceptionForm;
            f.selectedCandidate = m;
            const label = `${m.first_name} ${m.last_name || ""}`.trim();
            f.candidateQuery = m.sangha_sevi_id ? `${label} (${m.sangha_sevi_id})` : label;
            f.candidateResults = [];
        },
        async submitParichalakException() {
            const f = this.parichalakExceptionForm;
            f.error = "";
            f.success = "";
            if (!f.election_pk) { f.error = "Select an election."; return; }
            if (!f.position_master_pk) { f.error = "Select a position."; return; }
            if (!f.selectedCandidate) { f.error = "Search for and select the candidate."; return; }
            if (!f.probationary_exception_reason || !f.probationary_exception_reason.trim()) {
                f.error = "A reason is required for a probationary candidate exception.";
                return;
            }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${f.election_pk}/nominations`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            position_master_pk: f.position_master_pk,
                            candidate_person_pk: f.selectedCandidate.person_pk,
                            probationary_exception_reason: f.probationary_exception_reason.trim(),
                        }),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                f.success = "Nomination recorded with the probationary candidate exception.";
                f.position_master_pk = "";
                f.candidateQuery = "";
                f.selectedCandidate = null;
                f.probationary_exception_reason = "";
            } catch (err) {
                f.error = err.message || "Failed to submit the nomination.";
            } finally {
                f.saving = false;
            }
        },

        // ── Open elections — member self-service voting (GOV-BR-045) ──
        async _loadOpenElectionsForVoting() {
            this.govVotingLoading = true;
            this.govVotingError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/open-for-voting`
                );
                if (res.ok) {
                    const data = await res.json();
                    this.govOpenElections = data.items || [];
                } else {
                    this.govVotingError = "Failed to load open elections.";
                }
            } catch (e) {
                console.error("Failed to load open elections", e);
                this.govVotingError = "Failed to load open elections.";
            } finally {
                this.govVotingLoading = false;
            }
        },

        // Groups an election's accepted nominations by position, for the
        // per-position ballot rendering (one radio group + submit per position).
        govPositionsForElection(el) {
            const byPosition = {};
            const order = [];
            for (const nom of el.nominations || []) {
                if (!byPosition[nom.position_master_pk]) {
                    byPosition[nom.position_master_pk] = {
                        position_master_pk: nom.position_master_pk,
                        position_name: nom.position_name,
                        candidates: [],
                    };
                    order.push(nom.position_master_pk);
                }
                byPosition[nom.position_master_pk].candidates.push(nom);
            }
            return order.map((pk) => byPosition[pk]);
        },

        async castMySelfVote(el, positionPk) {
            const key = el.election_pk + "-" + positionPk;
            const nominationPk = this.govSelectedNomination[key];
            if (!nominationPk) return;

            this.govVoteSubmitting[key] = true;
            delete this.govVoteError[el.election_pk];
            delete this.govVoteSuccess[el.election_pk];
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${el.election_pk}/votes/self`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ election_nomination_pk: nominationPk }),
                    }
                );
                if (res.ok) {
                    if (!el.voted_position_pks.includes(positionPk)) {
                        el.voted_position_pks.push(positionPk);
                    }
                    this.govVoteSuccess[el.election_pk] = "Your vote has been recorded.";
                } else {
                    const err = await res.json().catch(() => ({}));
                    this.govVoteError[el.election_pk] =
                        err.detail || "Failed to cast your vote. You may have already voted for this position.";
                }
            } catch (e) {
                console.error("Failed to cast vote", e);
                this.govVoteError[el.election_pk] = "Failed to cast your vote.";
            } finally {
                this.govVoteSubmitting[key] = false;
            }
        },

        // 'Jun 2024' from an ISO date string, or '—'.
        govMonthYear(isoDate) {
            if (!isoDate) return "—";
            const d = new Date(isoDate);
            if (isNaN(d)) return "—";
            return d.toLocaleDateString("en-GB", { month: "short", year: "numeric" });
        },
        // backend's list[str] param picks up an OR match across both
        // types (organization.py 2026-10-02) — a single-value `type_code`
        // param would only ever match one type.
        async _loadFindOrgResults() {
            if (!this.findOrgIncludeSakha && !this.findOrgIncludePathaChakra) {
                this.findOrgResults = [];
                return;
            }
            this.findOrgLoading = true;
            this.findOrgError = "";
            try {
                const params = new URLSearchParams({ limit: NSS.MAX_PAGE_SIZE });
                if (this.findOrgIncludeSakha) params.append("type_code", "SAKHA_SANGHA");
                if (this.findOrgIncludePathaChakra) params.append("type_code", "PATHA_CHAKRA");
                if (this.findOrgCountryPk) params.set("country_pk", this.findOrgCountryPk);
                if (this.findOrgStatePk) params.set("state_pk", this.findOrgStatePk);
                if (this.findOrgDistrictPk) params.set("district_pk", this.findOrgDistrictPk);
                const res = await NSSAuth.apiFetch(
                    `/api/v1/organization/organizations/selectable?${params.toString()}`
                );
                if (res.ok) {
                    this.findOrgResults = await res.json();
                } else {
                    this.findOrgError = "Failed to load the directory.";
                }
            } catch (e) {
                console.error("Failed to load Sakha/Patha Chakra directory", e);
                this.findOrgError = "Failed to load the directory.";
            } finally {
                this.findOrgLoading = false;
            }
        },

        async onFindOrgTypeToggle() {
            await this._loadFindOrgResults();
        },

        async onFindOrgCountryChange() {
            this.findOrgStatePk = "";
            this.findOrgDistrictPk = "";
            this.findOrgStates = [];
            this.findOrgDistricts = [];
            if (this.findOrgCountryPk) {
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/register/states?country_pk=${this.findOrgCountryPk}`);
                    if (res.ok) this.findOrgStates = await res.json();
                } catch (e) {
                    console.error("Failed to load states", e);
                }
            }
            await this._loadFindOrgResults();
        },

        async onFindOrgStateChange() {
            this.findOrgDistrictPk = "";
            this.findOrgDistricts = [];
            if (this.findOrgStatePk) {
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/register/districts?state_pk=${this.findOrgStatePk}`);
                    if (res.ok) this.findOrgDistricts = await res.json();
                } catch (e) {
                    console.error("Failed to load districts", e);
                }
            }
            await this._loadFindOrgResults();
        },

        async onFindOrgDistrictChange() {
            await this._loadFindOrgResults();
        },

        // Client-side free-text narrowing over the already-fetched page —
        // matches name, code, district/state/country name, or PIN.
        findOrgFiltered() {
            const q = (this.findOrgQuery || "").trim().toLowerCase();
            if (!q) return this.findOrgResults;
            return this.findOrgResults.filter(o =>
                [o.organization_name, o.organization_code, o.district_name,
                 o.state_name, o.country_name, o.postal_code, o.city_village_name]
                    .filter(Boolean)
                    .some(v => String(v).toLowerCase().includes(q))
            );
        },

        // ── Member Directory tab ─────────────────────────────────
        async _loadMemberDirectory() {
            if (this.memberDirSakhas.length === 0) {
                try {
                    const res = await NSSAuth.apiFetch(
                        "/api/v1/organization/organizations/selectable?type_code=SAKHA_SANGHA&limit=" + NSS.MAX_PAGE_SIZE
                    );
                    if (res.ok) {
                        const orgs = await res.json();
                        this.memberDirSakhas = orgs.slice().sort(
                            (a, b) => (a.organization_name || "").localeCompare(b.organization_name || "")
                        );
                    }
                } catch (e) {
                    console.error("Failed to load Sakha filter list", e);
                }
            }
            await this._fetchMemberDirectory();
        },

        async _fetchMemberDirectory() {
            this.memberDirLoading = true;
            this.memberDirError = "";
            try {
                const params = new URLSearchParams({ limit: String(this.memberDirLimit) });
                const q = (this.memberDirQuery || "").trim();
                if (q.length >= 2) params.set("q", q);
                if (this.memberDirSakhaPk) params.set("organization_pk", this.memberDirSakhaPk);
                const res = await NSSAuth.apiFetch(`/api/v1/membership/directory?${params.toString()}`);
                if (!res.ok) throw new Error("Failed to load the Member Directory.");
                const data = await res.json();
                this.memberDirResults = data.members || [];
                this.memberDirTotal = data.total || 0;
            } catch (e) {
                this.memberDirError = e.message || "Failed to load the Member Directory.";
                this.memberDirResults = [];
                this.memberDirTotal = 0;
            } finally {
                this.memberDirLoading = false;
            }
        },

        // Debounced (300ms, same convention as searchPersonForAdd). A
        // 1-character query is held back entirely (owner ask 2026-10-27:
        // "search should take min 2 digits") rather than firing — the
        // backend's min_length=2 on q would 422 it anyway, and refetching
        // the full unfiltered list on every single keystroke before the
        // 2nd character is wasted work. 0 characters (cleared) still
        // refetches the unfiltered browsable list.
        searchMemberDirectory() {
            if (this._memberDirDebounce) clearTimeout(this._memberDirDebounce);
            if ((this.memberDirQuery || "").trim().length === 1) return;
            this._memberDirDebounce = setTimeout(() => {
                this.memberDirLimit = 50;
                this._fetchMemberDirectory();
            }, 300);
        },

        onMemberDirSakhaChange() {
            this.memberDirLimit = 50;
            this._fetchMemberDirectory();
        },

        loadMoreMemberDirectory() {
            this.memberDirLimit += 50;
            this._fetchMemberDirectory();
        },

        memberDirFullName(m) {
            return [m.first_name, m.middle_name, m.last_name].filter(Boolean).join(" ");
        },

        async submitCreateFamily() {
            if (!this.createFamilyName.trim() || !this.createFamilySakhaPk) return;
            this.createFamilySubmitting = true;
            this.createFamilyError = "";

            try {
                const payload = {
                    family_name: this.createFamilyName.trim(),
                    sakha_organization_pk: this.createFamilySakhaPk,
                };
                if (this.createFamilyFormedDate) {
                    payload.formed_date = this.createFamilyFormedDate;
                }
                if (this.createFamilyRemarks?.trim()) {
                    payload.remarks = this.createFamilyRemarks.trim();
                }

                const res = await NSSAuth.apiFetch("/api/v1/family/families", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });

                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(NSS.errorMessage(err, res.status));
                }

                const newFamily = await res.json();

                // Close modal and reset form
                this.showCreateFamilyModal = false;
                this.createFamilyName = "";
                this.createFamilySakhaPk = "";
                this.createFamilyFormedDate = "";
                this.createFamilyRemarks = "";
                this.createFamilyCountryPk = "";
                this.createFamilyStatePk = "";
                this.createFamilyDistrictPk = "";
                this.createFamilyStates = [];
                this.createFamilyDistricts = [];

                // Reload family data for dashboard
                this.family = newFamily;
                this.ownFamily = newFamily;
                await this._fetchFamilyDetail();

            } catch (err) {
                this.createFamilyError = err.message || "Failed to create family";
            } finally {
                this.createFamilySubmitting = false;
            }
        },

        // ═══════════════════════════════════════════════════
        //  MEMBER SEARCH (Admin Tabs)
        // ═══════════════════════════════════════════════════

        /**
         * Header click on Member Search.
         *
         * Server-side, because this request asks for only the first 10
         * matches — the browser holds a slice, not the result set, so
         * reordering locally would reorder 10 arbitrary rows and present
         * them as "the" order.
         */
        sortMemberSearch(key) {
            const next = NSS.toggleSort(this.memberSearchSortBy, this.memberSearchSortDir, key);
            this.memberSearchSortBy = next.key;
            this.memberSearchSortDir = next.dir;
            this.searchMembers();
        },

        async searchMembers() {
            const q = this.memberSearchQuery.trim();
            if (!q || q.length < 2) {
                this.memberSearchResults = [];
                this.memberSearchError = q.length === 1 ? "Type at least 2 characters" : "";
                return;
            }
            this.memberSearchLoading = true;
            this.memberSearchError = "";
            try {
                // Search the MEMBER (sangha_sevi) population, not user accounts.
                // /api/v1/membership/search is rooted on nss.sangha_sevi/nss.person
                // and matches SS ID, Person ID, ERP number, name (trigram), mobile,
                // email, and Kendra number — and crucially includes members who have
                // no login account, which the old /admin/users endpoint silently
                // excluded. Results come back ordered by relevance (trigram
                // similarity); the endpoint has no sort_by/sort_dir, so header
                // clicks sort the returned slice client-side below.
                const params = new URLSearchParams({ q, limit: 10, offset: 0 });
                const res = await NSSAuth.apiFetch(`/api/v1/membership/search?${params}`);
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                let results = (data.members || []).map((m) => ({
                    sangha_sevi_pk: m.sangha_sevi_pk,
                    person_pk: m.person_pk,
                    sangha_sevi_id: m.sangha_sevi_id,
                    person_name: [m.first_name, m.middle_name, m.last_name]
                        .filter(Boolean).join(" "),
                    organization_name: m.organization_name,
                    local_sakha_erp_id: m.local_sakha_erp_id,
                    // Membership lifecycle status (not an account status).
                    status_code: m.status_code,
                    status_name: m.status_name,
                }));
                // Client-side sort of the returned slice, honouring the header the
                // user clicked (the server returns relevance-ordered rows).
                if (this.memberSearchSortBy) {
                    const key = this.memberSearchSortBy === "account_status"
                        ? "status_name" : this.memberSearchSortBy;
                    const dir = this.memberSearchSortDir === "desc" ? -1 : 1;
                    results.sort((a, b) =>
                        dir * String(a[key] ?? "").localeCompare(String(b[key] ?? "")));
                }
                this.memberSearchResults = results;
                if (this.memberSearchResults.length === 0) {
                    this.memberSearchError = "No members found.";
                }
            } catch (err) {
                this.memberSearchError = err.message || "Search failed.";
                this.memberSearchResults = [];
            } finally {
                this.memberSearchLoading = false;
            }
        },

        clearMemberSearch() {
            this.memberSearchQuery = "";
            this.memberSearchResults = [];
            this.memberSearchError = "";
        },

        //  ORG-LEVEL FAMILY BROWSER (Admin Tabs)
        // ═══════════════════════════════════════════════════

        /** Check if the current admin tab has the family browser */
        adminTabHasFamilyBrowser() {
            const at = this.adminTabs.find(t => t.key === this.tab);
            return at && FAMILY_BROWSER_ROLES.has(at.roleCode);
        },

        /** Is roleCode one of the 5 organizational admin-tab roles (Kendra/
         * Anchalika/Zilla/Sakha/Patha Chakra Management)? Used by the
         * dashboard template to show the real "pending approvals in your
         * org" panel only where it makes sense. */
        isOrgLevelAdminRole(roleCode) {
            return ORG_LEVEL_ADMIN_ROLES.has(roleCode);
        },

        /** Get the start org scope for the current admin role (first match). */
        _getAdminOrgScope() {
            const at = this.adminTabs.find(t => t.key === this.tab);
            if (!at) return null;
            // Find the scope that matches this role
            const scope = this.user.scopes?.find(s => s.role_code === at.roleCode);
            return scope || null;
        },

        /**
         * ALL org-anchored scopes for the current admin tab's role.
         *
         * A user may hold the same organizational role over several sanghas
         * (one user_role row each — the frozen RBAC allows it). The family
         * browser must start from every one of them, not just the first, or
         * a multi-sangha admin only ever sees one sangha's families.
         * Deduplicated by organization_pk; org-anchored scopes only.
         */
        _getAdminOrgScopes() {
            const at = this.adminTabs.find(t => t.key === this.tab);
            if (!at) return [];
            const seen = new Set();
            const out = [];
            for (const s of this.user.scopes || []) {
                if (s.role_code !== at.roleCode) continue;
                if (!s.organization_pk) continue;
                if (seen.has(s.organization_pk)) continue;
                seen.add(s.organization_pk);
                out.push(s);
            }
            return out;
        },

        /** Map scope rows to the org-card shape the browser renders. */
        _scopeOrgCards(scopes) {
            return scopes.map(s => ({
                organization_pk: s.organization_pk,
                organization_name: s.organization_name || "Organization",
                organization_type_name:
                    s.organization_type_name || s.scope_level || "",
                organization_type_code:
                    s.organization_type_code || s.scope_level || "SAKHA_SANGHA",
                organization_code: s.organization_code || "",
            }));
        },

        /** Launch the org family browser from an admin tab */
        async openOrgFamilyBrowser() {
            this.orgFamilyBrowser = true;
            this._resetOrgBrowser();

            const scopes = this._getAdminOrgScopes();

            // No org-anchored scope → NSS-wide: start from the Kendra root.
            if (!scopes.length) {
                await this._fetchOrgRoot();
                return;
            }

            // More than one scoped org under this role (multi-sangha admin) —
            // show every scoped sangha as a top-level card so families across
            // ALL of them are reachable, then drill as usual.
            if (scopes.length > 1) {
                this.orgBreadcrumb = [{
                    organization_pk: null,
                    organization_name: "My Sanghas",
                    organization_type_name: "",
                    organization_type_code: "ROOT",
                    organization_code: "",
                    isScopeRoot: true,
                }];
                this.orgChildren = this._scopeOrgCards(scopes);
                this.orgSelectedSakhaCode = null;
                return;
            }

            // Single scope — start there.
            const scope = scopes[0];
            if (scope && scope.organization_pk) {
                // Role is scoped to a specific org — start there
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/organization/organizations/${scope.organization_pk}/children`);
                    this.orgBreadcrumb = [{
                        organization_pk: scope.organization_pk,
                        organization_name: scope.organization_name || "Organization",
                        organization_type_name: scope.organization_type_code || scope.scope_level || "Org",
                        organization_type_code: scope.organization_type_code || scope.scope_level || "KENDRA",
                        organization_code: "",
                    }];

                    if (res.ok) {
                        const children = await res.json();
                        if (children.length > 0) {
                            this.orgChildren = children;
                            this._fetchOrgChildrenStats(scope.organization_pk);
                        } else {
                            // Leaf org (Sakha) — load families directly
                            this.orgSelectedSakhaCode = scope.organization_pk;
                            await this._fetchOrgFamilies(scope.organization_pk);
                        }
                    }
                } catch {
                    // Fallback: start from Kendra root
                    await this._fetchOrgRoot();
                }
            } else {
                // NSS-wide scope — start from Kendra root
                await this._fetchOrgRoot();
            }
        },

        closeOrgFamilyBrowser() {
            this.orgFamilyBrowser = false;
            this._resetOrgBrowser();
        },

        _resetOrgBrowser() {
            this.orgBreadcrumb = [];
            this.orgChildren = [];
            this.orgChildrenLoading = false;
            this.orgChildrenStats = {};
            this.orgFamilies = [];
            this.orgFamiliesLoading = false;
            this.orgSelectedSakhaCode = null;
            this._resetOrgFamilyDetail();
        },

        _resetOrgFamilyDetail() {
            this.orgSelectedFamily = null;
            this.orgFamilyMembers = [];
            this.orgFamilyHeadHistory = [];
            this.orgFamilyLoading = false;
            this.orgGraphMembers = [];
            this.orgGraphLoading = false;
            this.orgGraphError = false;
            this.orgViewerPersonPk = null;
            this.orgTreeHead = null;
            this.orgTreeSpouse = null;
            this.orgTreeNodes = [];
            this._orgAllTreePersons = [];
            this.orgSelectedPerson = null;
            this.orgSelectedPersonDetail = null;
            this.orgSelectedPersonLoading = false;
            this.orgSelectedPersonMembership = null;
            this.orgSelectedPersonMembershipLoading = false;
            this.orgFamilyMemberSummaries = {};
        },

        // ── Org hierarchy navigation ──────────────────────

        async _fetchOrgRoot() {
            this.orgChildrenLoading = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/organization/organizations?type_code=KENDRA");
                if (!res.ok) throw new Error(res.statusText);
                const kendras = await res.json();
                if (kendras.length > 0) {
                    const k = kendras[0];
                    this.orgBreadcrumb = [{
                        organization_pk: k.organization_pk,
                        organization_name: k.organization_name,
                        organization_type_name: k.organization_type_name,
                        organization_type_code: k.organization_type_code || "KENDRA",
                        organization_code: k.organization_code,
                    }];
                    await this._fetchOrgChildren(k.organization_pk);
                }
            } catch {
                this.orgChildren = [];
            } finally {
                this.orgChildrenLoading = false;
            }
        },

        async _fetchOrgChildren(orgPk) {
            this.orgChildrenLoading = true;
            this.orgChildrenStats = {};
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/organization/organizations/${orgPk}/children`);
                this.orgChildren = res.ok ? await res.json() : [];
            } catch {
                this.orgChildren = [];
            } finally {
                this.orgChildrenLoading = false;
            }
            this._fetchOrgChildrenStats(orgPk);
        },

        async _fetchOrgChildrenStats(orgPk) {
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/organization/organizations/${orgPk}/children-stats`);
                if (res.ok) {
                    const stats = await res.json();
                    const map = {};
                    for (const s of stats) map[s.organization_pk] = s;
                    this.orgChildrenStats = map;
                }
            } catch { /* non-fatal */ }
        },

        getOrgChildStats(orgPk) {
            return this.orgChildrenStats[orgPk] || null;
        },

        /**
         * Returns icon style info per org/family category.
         * Org types: KENDRA (purple), ANCHALIKA_SANGHA (blue), ZILLA_SANGHA (teal),
         * SAKHA_SANGHA (emerald), FAMILY (orange-red).
         */
        orgCardIcon(typeCode) {
            const MAP = {
                KENDRA:            { bg: 'linear-gradient(135deg,#7c3aed,#a78bfa)', icon: 'temple', color: '#7c3aed' },
                ANCHALIKA_SANGHA:  { bg: 'linear-gradient(135deg,#2563eb,#60a5fa)', icon: 'grid', color: '#2563eb' },
                ZILLA_SANGHA:      { bg: 'linear-gradient(135deg,#0d9488,#2dd4bf)', icon: 'map', color: '#0d9488' },
                SAKHA_SANGHA:      { bg: 'linear-gradient(135deg,#059669,#34d399)', icon: 'users', color: '#059669' },
                FAMILY:            { bg: 'linear-gradient(135deg,#c2410c,#ea580c)', icon: 'family', color: '#c2410c' },
            };
            return MAP[typeCode] || MAP.KENDRA;
        },

        /** Returns inline SVG HTML for an org icon type */
        orgIconSvg(typeCode) {
            const ICONS = {
                temple: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0 0 12 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75Z"/>',
                grid:   '<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z"/>',
                map:    '<path stroke-linecap="round" stroke-linejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498 4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 0 0-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0Z"/>',
                users:  '<path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"/>',
                family: '<path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z"/>',
            };
            const info = this.orgCardIcon(typeCode);
            const path = ICONS[info.icon] || ICONS.temple;
            return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">' + path + '</svg>';
        },

        async orgDrillInto(org) {
            this._resetOrgFamilyDetail();

            // If Sakha → load families
            if (org.organization_type_code === "SAKHA_SANGHA") {
                this.orgBreadcrumb.push({
                    organization_pk: org.organization_pk,
                    organization_name: org.organization_name,
                    organization_type_name: org.organization_type_name,
                    organization_type_code: org.organization_type_code,
                    organization_code: org.organization_code,
                });
                this.orgSelectedSakhaCode = org.organization_code || org.organization_pk;
                this.orgChildren = [];
                await this._fetchOrgFamilies(org.organization_pk);
                return;
            }

            // Otherwise drill deeper
            this.orgBreadcrumb.push({
                organization_pk: org.organization_pk,
                organization_name: org.organization_name,
                organization_type_name: org.organization_type_name,
                organization_type_code: org.organization_type_code,
                organization_code: org.organization_code,
            });
            this.orgSelectedSakhaCode = null;
            this.orgFamilies = [];
            await this._fetchOrgChildren(org.organization_pk);
        },

        async orgBreadcrumbNav(index) {
            if (index < 0) return;
            const crumb = this.orgBreadcrumb[index];
            this.orgBreadcrumb = this.orgBreadcrumb.slice(0, index + 1);
            this.orgFamilies = [];
            this._resetOrgFamilyDetail();

            // Back to the multi-sangha scope root — re-render the scope cards
            // (there is no single parent org to fetch children for).
            if (crumb.isScopeRoot) {
                this.orgSelectedSakhaCode = null;
                this.orgChildrenStats = {};
                this.orgChildren = this._scopeOrgCards(this._getAdminOrgScopes());
                return;
            }

            // If navigating back to a Sakha, re-fetch families (not children)
            if (crumb.organization_type_code === "SAKHA_SANGHA") {
                this.orgSelectedSakhaCode = crumb.organization_code || crumb.organization_pk;
                this.orgChildren = [];
                await this._fetchOrgFamilies(crumb.organization_pk);
            } else {
                this.orgSelectedSakhaCode = null;
                await this._fetchOrgChildren(crumb.organization_pk);
            }
        },

        // ── Org-level family list ─────────────────────────

        async _fetchOrgFamilies(orgPk) {
            this.orgFamiliesLoading = true;
            try {
                let url = `/api/v1/family/families?limit=200&sakha_organization_pk=${encodeURIComponent(orgPk)}`;
                const res = await NSSAuth.apiFetch(url);
                this.orgFamilies = res.ok ? await res.json() : [];
            } catch {
                this.orgFamilies = [];
            } finally {
                this.orgFamiliesLoading = false;
            }
        },

        // ── Org-level family selection ────────────────────

        async orgSelectFamily(family) {
            this._resetOrgFamilyDetail();
            this.orgSelectedFamily = family;
            this.orgFamilyLoading = true;
            try {
                const [membersRes, headRes] = await Promise.all([
                    NSSAuth.apiFetch(`/api/v1/family/families/${family.family_group_pk}/members`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/family/families/${family.family_group_pk}/head-history`)
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                ]);
                this.orgFamilyMembers = membersRes;
                this.orgFamilyHeadHistory = headRes;
            } catch {
                this.orgFamilyMembers = [];
                this.orgFamilyHeadHistory = [];
            } finally {
                this.orgFamilyLoading = false;
            }

            // Set viewer to the family head or first member
            const head = this.orgFamilyMembers.find(m => m.is_head);
            this.orgViewerPersonPk = head ? head.person_pk : (this.orgFamilyMembers[0]?.person_pk || null);

            // Fetch graph + summaries
            this._loadOrgGraph();
            this._fetchOrgFamilyMemberSummaries();
        },

        async _loadOrgGraph() {
            if (!this.orgSelectedFamily || !this.orgViewerPersonPk) return;
            this.orgGraphLoading = true;
            this.orgGraphError = false;
            try {
                const url = `/api/v1/family/families/${this.orgSelectedFamily.family_group_pk}/graph?viewer_person_pk=${this.orgViewerPersonPk}`;
                const res = await NSSAuth.apiFetch(url);
                if (!res.ok) throw new Error(res.statusText);
                this.orgGraphMembers = await res.json();
                this._buildOrgTree();
            } catch {
                this.orgGraphError = true;
            } finally {
                this.orgGraphLoading = false;
            }
        },

        _buildOrgTree() {
            const members = this.orgGraphMembers;
            this.orgTreeHead = null;
            this.orgTreeSpouse = null;
            this.orgTreeNodes = [];
            this._orgAllTreePersons = [];

            const viewerMember = this.orgFamilyMembers.find(
                m => m.person_pk === this.orgViewerPersonPk
            );
            const viewerSpouseGraph = members.find(
                m => SPOUSE_LABELS.has(m.relationship_label) && m.generation === 0
            );
            const viewerParentPks = members
                .filter(m => PARENT_LABELS.has(m.relationship_label))
                .map(m => m.person_pk);

            if (viewerMember) {
                this.orgTreeHead = {
                    ...viewerMember,
                    relationship_label: "Viewer",
                    generation: 0,
                    _isViewer: true,
                    _avatarClass: "av-viewer",
                    spouse_person_pk: viewerSpouseGraph ? viewerSpouseGraph.person_pk : null,
                    parent_person_pks: viewerParentPks,
                };
            }
            this.orgTreeSpouse = viewerSpouseGraph || null;

            for (const m of members) {
                const isSpouse = SPOUSE_LABELS.has(m.relationship_label);
                m._avatarClass = _avatarClass(m.generation, m.is_head, isSpouse);
            }

            const allPersons = [];
            if (this.orgTreeHead) allPersons.push(this.orgTreeHead);
            for (const m of members) allPersons.push(m);
            this._orgAllTreePersons = allPersons;

            this.orgTreeNodes = _buildCoupleTree(allPersons);
        },

        renderOrgTree() {
            if (!this.orgTreeNodes?.length) return "";
            return this._renderOrgSubtree(this.orgTreeNodes, true);
        },

        _renderOrgSubtree(nodes, isRoot) {
            return this._renderGenSubtree(
                nodes, isRoot,
                (n) => this._renderOrgCouple(n),
                (n, r) => this._renderOrgSubtree(n, r),
            );
        },

        _renderOrgCouple(node) {
            if (node.couple) {
                return '<div class="couple-group">' + this._renderOrgPerson(node.members[0]) + '<div class="couple-join-line"></div>' + this._renderOrgPerson(node.members[1]) + '</div>';
            }
            return this._renderOrgPerson(node.members[0]);
        },

        _renderOrgPerson(m) {
            const av = m._avatarClass || "av-other";
            const ini = this._esc(this._getInitials(m));
            const nm = this._esc(this.formatFamilyName(m));
            const rl = m._isViewer ? "<strong>Head</strong>" : this._esc(m.relationship_label || "");
            const sel = this.orgSelectedPerson?.person_pk === m.person_pk ? " is-selected" : "";
            const vr = m._isViewer ? " is-viewer" : "";
            const dep = m.is_departed ? " is-departed" : "";
            let ind = "";
            if (m._isViewer)
                ind = '<span class="node-indicator indicator-viewer">&#128065;</span>';
            else if (m.is_head)
                ind = '<span class="node-indicator indicator-head">&#9733;</span>';
            let depInfo = "";
            if (m.is_departed) {
                const fn = this._esc(m.departed_family_name || "");
                const sn = this._esc(m.departed_sakha_name || "");
                depInfo = '<div class="departed-info" title="Click to view ' + fn + ' family">'
                    + (fn ? '<div class="departed-family">' + fn + '</div>' : '')
                    + (sn ? '<div class="departed-sakha">' + sn + '</div>' : '')
                    + '</div>';
            }
            return '<div class="tree-node' + sel + dep + '" title="' + (m.is_departed ? 'Click to visit ' + this._esc(m.departed_family_name || 'their') + ' family' : '') + '" data-org-person-pk="' + m.person_pk + '">'
                 + '<div class="node-avatar ' + av + '">' + ini + ind + '</div>'
                 + '<div class="node-name">' + nm + '</div>'
                 + '<div class="node-role' + vr + '">' + rl + '</div>'
                 + depInfo
                 + '</div>';
        },

        orgHandleTreeClick(event) {
            const el = event.target.closest("[data-org-person-pk]");
            if (!el) return;
            const pk = el.dataset.orgPersonPk;
            const member = this._orgAllTreePersons?.find(m => m.person_pk === pk);
            if (!member) return;

            // Ghost nodes are not clickable
            if (member.is_departed) return;

            this.orgSelectTreePerson(member);
        },

        async _orgNavigateToDepartedFamily(familyGroupPk) {
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/family/families/${familyGroupPk}`);
                if (!res.ok) throw new Error("Family not found");
                const familyData = await res.json();
                // Reset current selection and load the new family
                this.orgSelectedPerson = null;
                this.orgSelectedPersonDetail = null;
                this.orgSelectedPersonMembership = null;
                await this.orgSelectFamily(familyData);
            } catch (err) {
                console.error("[OrgBrowser] Navigate to departed family failed:", err);
            }
        },

        async orgSelectTreePerson(member) {
            if (this.orgSelectedPerson?.person_pk === member.person_pk) {
                this.orgSelectedPerson = null;
                this.orgSelectedPersonDetail = null;
                this.orgSelectedPersonMembership = null;
                return;
            }
            this.orgSelectedPerson = member;
            this.orgSelectedPersonDetail = null;
            this.orgSelectedPersonLoading = true;
            this.orgSelectedPersonMembership = null;
            this.orgSelectedPersonMembershipLoading = true;

            const [personData, membershipData] = await Promise.all([
                NSSAuth.apiFetch(`/api/v1/person/persons/${member.person_pk}`)
                    .then(r => r.ok ? r.json() : null).catch(() => null),
                NSSAuth.apiFetch(`/api/v1/family/person/${member.person_pk}/membership-summary`)
                    .then(r => r.ok ? r.json() : null).catch(() => null),
            ]);

            this.orgSelectedPersonDetail = personData;
            this.orgSelectedPersonLoading = false;
            this.orgSelectedPersonMembership = membershipData;
            this.orgSelectedPersonMembershipLoading = false;
        },

        orgDisplayRelationship(m) {
            if (m._isViewer) return "Viewer";
            if (m.person_pk === this.orgViewerPersonPk) return "Viewer";
            if (m.relationship_label) return m.relationship_label;
            const gm = this.orgGraphMembers.find(g => g.person_pk === m.person_pk);
            if (gm?.relationship_label) return gm.relationship_label;
            if (m.is_head) return "Head of Family";
            return m.relationship_type_name || m.relationship_type_code || "—";
        },

        orgGetSpouseName(personPk) {
            const gm = this.orgGraphMembers.find(g => g.person_pk === personPk);
            if (gm && gm.spouse_person_pk) {
                const spouse = this.orgGraphMembers.find(g => g.person_pk === gm.spouse_person_pk)
                    || this.orgFamilyMembers.find(m => m.person_pk === gm.spouse_person_pk);
                if (spouse) return this.formatFamilyName(spouse);
            }
            if (personPk === this.orgViewerPersonPk && this.orgTreeSpouse) {
                return this.formatFamilyName(this.orgTreeSpouse);
            }
            return null;
        },

        orgGetSpouseInitials(personPk) {
            const gm = this.orgGraphMembers.find(g => g.person_pk === personPk);
            if (gm && gm.spouse_person_pk) {
                const spouse = this.orgGraphMembers.find(g => g.person_pk === gm.spouse_person_pk)
                    || this.orgFamilyMembers.find(m => m.person_pk === gm.spouse_person_pk);
                if (spouse) return this._getInitials(spouse);
            }
            if (personPk === this.orgViewerPersonPk && this.orgTreeSpouse) return this._getInitials(this.orgTreeSpouse);
            return "?";
        },

        orgSelectSpouse(personPk) {
            const gm = this.orgGraphMembers.find(g => g.person_pk === personPk);
            const spousePk = gm?.spouse_person_pk || (personPk === this.orgViewerPersonPk && this.orgTreeSpouse ? this.orgTreeSpouse.person_pk : null);
            if (!spousePk) return;
            const spouseMember = this.orgGraphMembers.find(g => g.person_pk === spousePk) || this.orgFamilyMembers.find(m => m.person_pk === spousePk);
            if (spouseMember) this.orgSelectTreePerson(spouseMember);
        },

        async _fetchOrgFamilyMemberSummaries() {
            if (!this.orgFamilyMembers.length) return;
            const summaries = {};
            await Promise.all(
                this.orgFamilyMembers.map(m =>
                    NSSAuth.apiFetch(`/api/v1/family/person/${m.person_pk}/membership-summary`)
                        .then(r => r.ok ? r.json() : null)
                        .then(data => { if (data) summaries[m.person_pk] = data; })
                        .catch(() => {})
                )
            );
            this.orgFamilyMemberSummaries = summaries;
        },

        getOrgMemberSummary(personPk) {
            return this.orgFamilyMemberSummaries[personPk] || null;
        },

        orgGetAvatarClass(m) {
            if (!m) return "av-other";
            if (m._avatarClass) return m._avatarClass;
            if (m._isViewer || m.person_pk === this.orgViewerPersonPk) return "av-viewer";
            const gm = this.orgGraphMembers.find(g => g.person_pk === m.person_pk);
            if (gm?._avatarClass) return gm._avatarClass;
            return "av-other";
        },

        // ── Tab switching ─────────────────────────────────
        switchTab(newTab) {
            // Reset org browser when switching tabs
            if (this.orgFamilyBrowser && newTab !== this.tab) {
                this.orgFamilyBrowser = false;
                this._resetOrgBrowser();
            }
            this.tab = newTab;
            this.sidebarOpen = false;
            sessionStorage.setItem('nss_dashboard_tab', newTab);
            this._refreshTab(newTab);
        },

        /**
         * Re-fetch the data a tab renders, on every switch onto it.
         *
         * Without this, every tab except orgDashboard showed only what init()
         * fetched at page load — so a change made elsewhere (or by another
         * admin) stayed invisible until a manual F5. orgDashboard is excluded
         * because openOrgDashboard() already forces a remount, which re-runs
         * its own x-init; calling a loader here as well would double-fetch.
         *
         * Fire-and-forget by design: each loader owns its own loading flag and
         * error handling, and a switch must not block on the network.
         */

        /**
         * Person + own membership + own family — extracted from init()
         * (2026-10-22) so revisiting the Personal tab can actually retry
         * this instead of only ever running once at page load. Previously
         * inline-only: if this was still in flight (or failed) when the
         * user first landed on Personal, the card rendered blank with no
         * way to recover short of a full page reload — switching tabs and
         * back only "worked" because the original slow init() promise
         * happened to resolve while attention was elsewhere, not because
         * anything actually re-fetched. Safe to call more than once —
         * every assignment below is a plain overwrite.
         */
        async _fetchPersonalDetail() {
            const fetches = [];

            // Person details
            if (this.user.person_pk) {
                fetches.push(
                    NSSAuth.apiFetch(`/api/v1/person/persons/${this.user.person_pk}`)
                        .then(r => r.ok ? r.json() : null)
                        .catch(() => null)
                );
                // Addresses
                fetches.push(
                    NSSAuth.apiFetch(`/api/v1/person/persons/${this.user.person_pk}/addresses`)
                        .then(r => r.ok ? r.json() : [])
                        .catch(() => [])
                );
            } else {
                fetches.push(Promise.resolve(null));
                fetches.push(Promise.resolve([]));
            }

            // Membership detail (own record) — direct PK lookup now that
            // /auth/me exposes sangha_sevi_pk and GET /membership/members/{pk}
            // has an ownership carve-out, replacing the old /search-by-ID
            // workaround (which needed MEMBERSHIP_VIEW and 403'd for
            // regular members with no admin permissions).
            if (this.user.sangha_sevi_pk) {
                fetches.push(
                    NSSAuth.apiFetch(`/api/v1/membership/members/${this.user.sangha_sevi_pk}`)
                        .then(r => r.ok ? r.json() : null)
                        .catch(() => null)
                );
            } else {
                fetches.push(Promise.resolve(null));
            }

            // Person's families
            if (this.user.person_pk) {
                fetches.push(
                    NSSAuth.apiFetch(`/api/v1/family/person/${this.user.person_pk}/families`)
                        .then(r => r.ok ? r.json() : [])
                        .catch(() => [])
                );
            } else {
                fetches.push(Promise.resolve([]));
            }

            const [personData, addressData, memberData, familiesData] = await Promise.all(fetches);

            // Process person
            if (personData) {
                personData.display_name = this._buildDisplayName(personData);
                this.person = personData;
            }

            // Process addresses
            this.addresses = Array.isArray(addressData) ? addressData : [];

            // Process membership
            if (memberData) {
                this.member = memberData;
            }

            // Process family — use first family
            if (Array.isArray(familiesData) && familiesData.length > 0) {
                this.family = familiesData[0];
                this.ownFamily = familiesData[0];
            }
        },

        _refreshTab(tab) {
            if (typeof tab !== "string") return;
            try {
                if (tab === "membership" || tab === "documents") {
                    // Both render parichaya/anumati/affiliation/journey data,
                    // all of which _fetchMembershipDetail() populates.
                    if (this.member?.sangha_sevi_pk) this._fetchMembershipDetail();
                    if (tab === "membership") this._loadMyChangeRequests();
                } else if (tab === "family") {
                    if (this.family?.family_group_pk) this._fetchFamilyDetail();
                } else if (tab === "findOrg") {
                    this._loadFindOrgDirectory();
                } else if (tab === "memberDirectory") {
                    this._loadMemberDirectory();
                } else if (tab === "attendance") {
                    this._loadMyAttendance();
                } else if (tab === "attendanceRegister") {
                    this._initAttendanceRegister();
                } else if (tab.startsWith("admin_")) {
                    this._loadAdminStats();
                    const at = this.adminTabs.find(t => t.key === tab);
                    if (at?.roleCode === "NSS_ERP_AUDITOR") {
                        this._loadAuditRecent(true);
                    } else if (at && ORG_LEVEL_ADMIN_ROLES.has(at.roleCode)) {
                        this._loadOrgPendingApprovals(at);
                    }
                } else if (tab === "personal") {
                    this.loadSessions();
                    // Retry, not unconditional refetch: _fetchPersonalDetail()
                    // now exists as a real reusable loader (2026-10-22,
                    // extracted from init()) — only call it again here if
                    // the first load genuinely never landed (slow/failed
                    // request), so a normal tab revisit doesn't re-fetch
                    // data that's already there.
                    if (!this.person) this._fetchPersonalDetail();
                } else if (tab === "governance") {
                    this._loadGovernanceBodies();
                    this._loadMySakhaBodies();
                    this._loadOpenElectionsForVoting();
                    this._loadMyGovPositions();
                    this._loadMyGovDelegations();
                    this._loadMyPendingActingApprovals();
                } else if (tab === "sendApplication") {
                    this._loadSendApplicationOfficeBearers();
                    this._loadPendingApprovals();
                    if (this.sendApp.subTab === "history") this.loadSendApplicationHistory();
                } else if (tab === "pendingItems") {
                    // All four loaders already fire unconditionally at
                    // init() (so the sidebar count is correct on login), but
                    // refetch here too — same "revisit refetches" rule as
                    // every other tab, since any of them can have changed
                    // since the user last looked (e.g. an admin nominated
                    // them for a fresh acting delegation in the meantime).
                    this._loadMyPendingActingApprovals();
                    this._loadPendingApprovals();
                    this._loadOpenElectionsForVoting();
                    this._loadPendingClaimsCount();
                }
                // personal: see _fetchPersonalDetail() above — it is now a
                // real reusable loader, called both from init() and (as a
                // retry-if-missing) from the branch above. saveProfile()
                // already re-fetches after the only edit path on this page.
                // (Active Sessions is a separate concern: it has its own
                // loader, loadSessions(), wired above.)
                //
                // attendance: no endpoint exists yet (no attendance-session
                // table in the schema), so there is deliberately nothing to
                // refresh. Governance is covered above via the public
                // national-bodies endpoint.
                //
                // orgDashboard: openOrgDashboard() forces a remount which
                // re-runs the nested component's x-init; refreshing here too
                // would double-fetch.
            } catch (e) {
                console.warn("[dashboard] Tab refresh failed:", tab, e);
            }
        },

        // Opens the Org Dashboard tab on the given org (the admin's own
        // scope via the sidebar link, or a drill-down from a child Sakha
        // row inside the tab itself). Forces the nested orgDashboardTab()
        // component to unmount/remount (via viewingOrgPk toggling through
        // null) so switching orgs while already on the tab re-fetches.
        openOrgDashboard(orgPk) {
            this.viewingOrgPk = null;
            this.switchTab("orgDashboard");
            this.$nextTick(() => {
                this.viewingOrgPk = orgPk;
                // So a refresh while on this tab restores the same org
                // (see the viewingOrgPk initializer above).
                sessionStorage.setItem('nss_dashboard_org_pk', orgPk);
            });
        },

        get myOrgDashboardLabel() {
            const scopes = this.user?.scopes || [];
            const isNssWide = this.isGovNssWideAdmin;
            if (isNssWide) return "Kendra Dashboard";
            const scoped = scopes.find(s => s.organization_pk);
            return (scoped && ROLE_ORG_LABELS[scoped.role_code]) || "Org Dashboard";
        },

        // Orgs of a given type that this user personally administers, used by
        // the org-switcher dropdown inside the org-dashboard tab. A user may
        // legitimately hold the same role at several scopes (user_role has no
        // UNIQUE on (user_account_pk, role_master_pk) — "a user can have the
        // same role with different scopes"), so more than one entry here is
        // expected, not an error.
        //
        // Unlike admin.js's version this reads straight off /auth/me's scopes
        // rather than walking the org tree: this page never preloads the full
        // organization list, and a member-facing switcher only needs the orgs
        // the user is actually an admin of.
        dashboardOrgsFor(typeCode) {
            if (!typeCode) return [];
            const seen = new Set();
            return (this.user?.scopes || [])
                .filter(s => s.organization_pk && s.organization_type_code === typeCode)
                .filter(s => {
                    if (seen.has(s.organization_pk)) return false;
                    seen.add(s.organization_pk);
                    return true;
                })
                .map(s => ({
                    organization_pk: s.organization_pk,
                    organization_name: s.organization_name || "(unnamed)",
                    organization_code: "",
                }))
                .sort((a, b) => a.organization_name.localeCompare(b.organization_name));
        },

        // Sidebar "Dashboards" group: one entry per tier this user actually
        // administers. NSS-WIDE admins (NSS_ERP_ADMIN, or an org-anchor-less
        // NSS-WIDE role like NSS_ERP_KENDRA_ADMIN per CLAUDE.md — reserved
        // for governing-body members, capability-equivalent to
        // NSS_ERP_ADMIN but with no admin_scope.organization_pk row) hold no
        // org-scoped admin_scope rows of their own, so dashboardOrgsFor()
        // never surfaces a KENDRA entry for them — there is no
        // organization_pk on an NSS-WIDE scope row to filter on.
        //
        // Bug fix (Problem 3/4): this used to synthesize the Kendra entry
        // ONLY as a total fallback ("if no org-scoped tiers matched at all,
        // show Kendra instead") — so a user holding BOTH an NSS-WIDE role
        // (e.g. NSS_ERP_KENDRA_ADMIN) AND an org-scoped one (e.g.
        // NSS_ERP_SAKHA_ADMIN) got only the Sakha tier; the Kendra tier was
        // silently dropped because the Sakha match already made `levels`
        // non-empty and the fallback is `if (levels.length) return levels`.
        // The owner's explicit requirement is a UNION of every admin
        // level's access, so the Kendra tier must be added whenever an
        // NSS-WIDE scope is held, in ADDITION to whatever org-scoped tiers
        // also matched — not only when nothing else matched.
        get dashboardLevels() {
            const levels = DASHBOARD_LEVELS
                .map(lvl => ({ ...lvl, orgs: this.dashboardOrgsFor(lvl.typeCode) }))
                .filter(lvl => lvl.orgs.length > 0);
            const isNssWide = this.isGovNssWideAdmin;
            if (isNssWide && this.myOrgDashboardPk && !levels.some(l => l.typeCode === "KENDRA")) {
                levels.unshift({
                    typeCode: "KENDRA",
                    label: "Kendra",
                    orgs: [{ organization_pk: this.myOrgDashboardPk, organization_name: "Kendra" }],
                });
            }
            return levels;
        },

        // Topbar title for the org-dashboard tab — tracks the tier actually on
        // screen (the sidebar can open any tier this admin covers, and the
        // in-page switcher can move between orgs), falling back to the
        // role-derived label when the viewed org isn't one of this user's own
        // scopes (e.g. a drill-down into a child Sakha).
        get viewingOrgDashboardLabel() {
            const scope = (this.user?.scopes || []).find(
                s => s.organization_pk === this.viewingOrgPk
            );
            const lvl = scope && DASHBOARD_LEVELS.find(
                l => l.typeCode === scope.organization_type_code
            );
            return lvl ? `${lvl.label} Dashboard` : this.myOrgDashboardLabel;
        },

        get currentTabLabel() {
            if (this.tab === "orgDashboard") return this.viewingOrgDashboardLabel;
            if (TAB_LABELS[this.tab]) return TAB_LABELS[this.tab];
            const at = this.adminTabs.find(t => t.key === this.tab);
            return at ? at.label : "Dashboard";
        },

        // ── Formatting helpers ────────────────────────────
        formatDate(dateStr) {
            return NSS.formatDate(dateStr);
        },

        formatDateTime(dtStr) {
            return NSS.formatDateTime(dtStr);
        },

        formatPhone(code, number) {
            return NSS.formatPhone(code, number);
        },

        formatAddress(addr) {
            const lines = [];
            if (addr.address_line_1) lines.push(addr.address_line_1);
            if (addr.address_line_2) lines.push(addr.address_line_2);
            return lines.join("<br>") || "—";
        },

        formatFamilyName(m) {
            return NSS.formatName(m);
        },

        formatEventType(type) {
            if (!type) return "—";
            return type.replace(/_/g, " ");
        },

        // ── Internal helpers ──────────────────────────────
        _computeInitials(name) {
            if (!name) return "?";
            const parts = name.trim().split(/\s+/);
            if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
            return parts[0].substring(0, 2).toUpperCase();
        },

        _buildDisplayName(person) {
            return [person.first_name, person.middle_name, person.last_name].filter(Boolean).join(" ") || null;
        },

        // The org the sidebar's "Org Dashboard" link points at — the
        // admin's own scope, same resolution as admin.js's
        // myOrgDashboardPk getter (kept as a resolved value here, not a
        // computed getter, since the NSS-WIDE case needs an API call to
        // find the Kendra org rather than a preloaded organizations list).
        async _resolveMyOrgDashboardPk() {
            const scopes = this.user.scopes || [];
            if (scopes.length === 0) return;

            const isNssWide = this.isGovNssWideAdmin;
            if (isNssWide) {
                try {
                    const res = await NSSAuth.apiFetch("/api/v1/organization/organizations?type_code=KENDRA&limit=1");
                    if (res.ok) {
                        const orgs = await res.json();
                        this.myOrgDashboardPk = orgs[0]?.organization_pk || null;
                    }
                } catch (_) {
                    // Non-blocking — sidebar link just stays hidden.
                }
                return;
            }

            const scoped = scopes.find(s => s.organization_pk);
            this.myOrgDashboardPk = scoped ? scoped.organization_pk : null;
        },

        _buildAdminTabs() {
            if (!this.user.scopes || this.user.scopes.length === 0) { this.adminTabs = []; return; }

            // ── "True union" (owner-confirmed 2026-10-22, superseding an
            // earlier same-day decision that dropped organizational tabs
            // for a super-wide admin as "noise, not information" — the
            // owner explicitly rejected that rationale): a user holding
            // NSS_ERP_ADMIN or NSS_ERP_KENDRA_ADMIN ALWAYS sees the three
            // fixed system tabs below, in fixed order, AND a separate tab
            // for every organizational role (Kendra/Anchalika/Zilla/Sakha/
            // Patha Chakra Management) they also hold — never one at the
            // expense of the other.
            //
            // NSS_ERP_ADMIN is the super admin. NSS_ERP_KENDRA_ADMIN joins
            // this synthesis too (owner-confirmed 2026-10-22: "NSS = KENDRA
            // = NSS_WIDE" — Kendra admin is capability-equivalent to
            // NSS_ERP_ADMIN, reserved for governing-body members; see
            // UserContext.is_nss_wide() in api/services/rbac_service.py for
            // the backend side of this same equivalence). Deliberately NOT
            // a generic "any NSS-WIDE scope_level" check — NSS_ERP_AUDITOR
            // and NSS_ERP_REPORT_VIEWER also carry scope_level='NSS-WIDE'
            // per role_master but must NOT escalate to the full 3-tab set
            // on their own; only NSS_ERP_ADMIN and NSS_ERP_KENDRA_ADMIN
            // outrank everything.
            //
            // The Audit & Compliance and Reports tabs are built
            // unconditionally here, not gated on the literal NSS_ERP_AUDITOR
            // / NSS_ERP_REPORT_VIEWER role_codes being present in scopes. A
            // pure NSS_ERP_ADMIN (or Kendra admin) outranks both but each
            // of those views is surfaced by its own role tab, so it would
            // otherwise see neither. Synthesizing them here needs no
            // redundant user_role rows and no change to the frozen RBAC
            // (SOL-ADMIN-004 §8.7).
            //
            // Display-only: user_role rows are untouched, and a user WITHOUT
            // NSS_ERP_ADMIN/NSS_ERP_KENDRA_ADMIN still gets one tab per role
            // exactly as before (the loop below, unconditionally).
            const seen = new Set();
            const fixedTabs = [];
            const isSuperWide = this.user.scopes.some(
                s => s.role_code === "NSS_ERP_ADMIN" || s.role_code === "NSS_ERP_KENDRA_ADMIN"
            );
            if (isSuperWide) {
                for (const rc of SUPER_ADMIN_TAB_ORDER) {
                    const def = ADMIN_TAB_MAP[rc];
                    const held = this.user.scopes.some(s => s.role_code === rc);
                    fixedTabs.push({
                        key: "admin_" + rc.toLowerCase(),
                        label: def.label,
                        description: def.description,
                        adminUrl: def.adminUrl,
                        roleCode: rc,
                        // All three SYSTEM roles are fixed at
                        // scope_level='NSS-WIDE', so the scope never varies —
                        // only whether this user holds the row directly or
                        // reaches the view by outranking it.
                        scopeLabel: held ? "NSS-WIDE" : "NSS-WIDE (via System Administration)",
                    });
                    // Dedupe guard: a user holding NSS_ERP_ADMIN AND
                    // NSS_ERP_AUDITOR (say) must not also get a second,
                    // separate "Audit & Compliance" tab out of the loop
                    // below — the fixed tab above already covers that
                    // role_code.
                    seen.add(rc);
                }
            }

            // ── Organizational (and any other non-fixed) role tabs — one
            // per held role_code, same logic as always, now reachable
            // unconditionally rather than only for non-super-wide users.
            const orgTabs = [];
            for (const scope of this.user.scopes) {
                const def = ADMIN_TAB_MAP[scope.role_code];
                if (!def || seen.has(scope.role_code)) continue;
                seen.add(scope.role_code);
                let scopeLabel = scope.scope_level || "NSS-WIDE";
                if (scope.scope_level !== "NSS-WIDE" && scope.organization_pk) scopeLabel += " (Organization-scoped)";
                orgTabs.push({
                    key: "admin_" + scope.role_code.toLowerCase(),
                    label: def.label,
                    description: def.description,
                    adminUrl: def.adminUrl,
                    roleCode: scope.role_code,
                    scopeLabel,
                    // This role's own scope org, if org-anchored — used by
                    // _loadAdminStats() to fetch stats scoped to THIS tab's
                    // own org rather than the actor's combined scope across
                    // every role they hold (bug: a dual Kendra+Sakha admin
                    // was seeing byte-identical member/family counts on
                    // both tabs because one actor-wide number set got
                    // stamped onto every tab). null here means NSS-WIDE for
                    // this role, so the stats call is intentionally global.
                    organizationPk: scope.organization_pk || null,
                });
            }
            // Keep the pre-existing alphabetical-by-label order for the
            // organizational tabs specifically — the fixed system tabs
            // stay in SUPER_ADMIN_TAB_ORDER and are never re-sorted.
            orgTabs.sort((a, b) => a.label.localeCompare(b.label));

            this.adminTabs = [...fixedTabs, ...orgTabs];
        },

        /**
         * Whether this user may open the Registration Approvals view.
         * Mirrors the API's own guard on every /api/v1/claims endpoint, so
         * the nav item appears exactly when the view will actually load.
         */
        get canApproveRegistrations() {
            const perms = this.user?.permissions || [];
            return CLAIM_APPROVAL_PERMISSIONS.some(p => perms.includes(p));
        },

        // Pending Items tab (owner request, 2026-10-25, item 2: "pending
        // items can be anything related to the logged-in user... a
        // separate box for each foreseeable item") — a lightweight count
        // only, same pattern as admin.js::refreshCredsLapsedCount(): reuse
        // the existing list endpoint with page_size=1 rather than add a
        // dedicated summary endpoint. The full review workflow still lives
        // on /admin#claims (admin.html) — this box only surfaces that it
        // exists and links there, it does not duplicate that UI here.
        pendingClaimsCount: 0,
        async _loadPendingClaimsCount() {
            if (!this.canApproveRegistrations) { this.pendingClaimsCount = 0; return; }
            try {
                const res = await NSSAuth.apiFetch("/api/v1/admin/claims?claim_status=PENDING&page_size=1");
                if (res.ok) {
                    const data = await res.json();
                    this.pendingClaimsCount = data.total;
                }
            } catch { /* non-fatal — badge just stays at its last value */ }
        },

        /**
         * Whether this user may open the Governance (Tier 6) admin views
         * — mirrors the API's GOVERNANCE_VIEW/GOVERNANCE_MANAGE guard on
         * every /api/v1/governance endpoint.
         */
        get canViewGovernance() {
            const perms = this.user?.permissions || [];
            return perms.includes("GOVERNANCE_VIEW") || perms.includes("GOVERNANCE_MANAGE");
        },

        /**
         * Whether this user holds an NSS-wide (or NSS_ERP_ADMIN) scope —
         * mirrors admin.js's own isGovNssWideAdmin getter (same "is this
         * admin global" test; no cross-file include exists in this static
         * frontend, so the logic is duplicated, not shared). Used to gate
         * the sidebar's deep-link into admin.html's Governance catalog tab,
         * which admin.html itself restricts to the NSS-wide admin only
         * (2026-10-21 owner decision) — canViewGovernance alone (GOVERNANCE_
         * VIEW/MANAGE) is held by every scoped admin too and is no longer
         * the right gate for this link.
         */
        get isGovNssWideAdmin() {
            // KENDRA scope is NSS-wide-equivalent (owner-confirmed 2026-10-22:
            // "NSS = KENDRA = NSS_WIDE") — mirrors
            // api/services/rbac_service.py::UserContext.is_nss_wide().
            const scopes = this.user?.scopes || [];
            return scopes.some(s => s.role_code === "NSS_ERP_ADMIN" || s.scope_level === "NSS-WIDE" || s.scope_level === "KENDRA");
        },

        /**
         * Maps a variable stat card's caption to the /admin/dashboard-stats
         * field that actually answers it. A caption absent from this map has
         * no table behind it yet (no session, curriculum, audit-trail,
         * compliance or export module exists), so _statValue() renders
         * "Not tracked" instead of inventing a number.
         */
        STAT_FIELD_BY_LABEL: {
            "Sakha Sanghas": "sakha_sanghas",
            "Mahila Sanghas": "mahila_sanghas",
            "Anchalika Sanghas": "anchalika_sanghas",
            "Zilla Sanghas": "zilla_sanghas",
            "Patha Chakras": "patha_chakras",
            "Paribarik Sanghas": "paribarik_sanghas",
            "Renewals Due": "renewals_due",
            "Attendance %": "attendance_pct",
        },

        // Extra breakdown tiles rendered below the fixed 4-tile grid, keyed by
        // role. Only NSS_ERP_ADMIN gets these today — its old single "Total
        // Organizations" tile was a meaningless catch-all count (NSS/Kendra is
        // the one apex org; everything else is a child of it), so it is
        // replaced with a real per-tier breakdown of every org type whose
        // parent is Kendra. Sakha Sangha's parent is an Anchalika/Zilla (not
        // Kendra directly), so it stays in the existing "orgs" tile above
        // instead of moving here.
        MORE_TILES_BY_ROLE: {
            NSS_ERP_ADMIN: ["Anchalika Sanghas", "Zilla Sanghas", "Patha Chakras", "Paribarik Sanghas"],
        },

        _buildAdminStats() {
            this.adminStats = {
                NSS_ERP_ADMIN:              { members: "—", families: "—", orgs: "—", orgsLabel: "Sakha Sanghas", extra: "—", extraLabel: "Mahila Sanghas", moreTiles: [] },
                NSS_ERP_KENDRA_ADMIN:       { members: "—", families: "—", orgs: "—", orgsLabel: "Sakha Sanghas", extra: "—", extraLabel: "Mahila Sanghas", moreTiles: [] },
                NSS_ERP_ANCHALIKA_ADMIN:    { members: "—", families: "—", orgs: "—", orgsLabel: "Sakha Sanghas", extra: "—", extraLabel: "Mahila Sanghas", moreTiles: [] },
                NSS_ERP_ZILLA_ADMIN:        { members: "—", families: "—", orgs: "—", orgsLabel: "Sakha Sanghas", extra: "—", extraLabel: "Renewals Due", moreTiles: [] },
                NSS_ERP_SAKHA_ADMIN:        { members: "—", families: "—", orgs: "—", orgsLabel: "Renewals Due",  extra: "—", extraLabel: "Attendance %", moreTiles: [] },
                NSS_ERP_PATHA_CHAKRA_ADMIN: { members: "—", families: "—", orgs: "—", orgsLabel: "Sessions",      extra: "—", extraLabel: "Curriculum Items", moreTiles: [] },
                NSS_ERP_AUDITOR:            { members: "—", families: "—", orgs: "—", orgsLabel: "Audit Trails",   extra: "—", extraLabel: "Compliance Items", moreTiles: [] },
                NSS_ERP_REPORT_VIEWER:      { members: "—", families: "—", orgs: "—", orgsLabel: "Reports Available", extra: "—", extraLabel: "Exports", moreTiles: [] },
            };
        },

        async _loadAdminStats() {
            try {
                // One /dashboard-stats call per DISTINCT org scope among the
                // held admin tabs, not one call for the whole actor applied
                // to every tab. Bug fix: previously a single actor-wide call
                // (no org_pk) got its result stamped onto every tab in
                // this.adminTabs, so a dual-role admin (e.g. NSS-WIDE Kendra
                // admin + Sakha-scoped admin) saw byte-identical member/
                // family counts on both the Kendra and Sakha tabs — the
                // "orgs"/"extra" tiles differed only in LABEL (which field
                // STAT_FIELD_BY_LABEL picks), never in the underlying
                // numbers. Grouping by organizationPk (null = NSS-WIDE/
                // global for that tab) and passing it as ?org_pk= gives each
                // org-scoped tab its own subtree-scoped numbers; tabs that
                // are genuinely NSS-WIDE (the three super-admin tabs, or any
                // other NSS-WIDE role) correctly continue to share one
                // global number set — that sameness is accurate, not a bug.
                const groups = new Map();   // key -> { orgPk, tabs: [] }
                for (const tab of this.adminTabs) {
                    if (!this.adminStats[tab.roleCode]) continue;
                    const key = tab.organizationPk || "GLOBAL";
                    if (!groups.has(key)) groups.set(key, { orgPk: tab.organizationPk || null, tabs: [] });
                    groups.get(key).tabs.push(tab);
                }

                await Promise.all([...groups.values()].map(async ({ orgPk, tabs }) => {
                    const url = orgPk
                        ? `/api/v1/admin/dashboard-stats?org_pk=${encodeURIComponent(orgPk)}`
                        : "/api/v1/admin/dashboard-stats";
                    const res = await NSSAuth.apiFetch(url);
                    if (!res.ok) return;   // silently keep placeholders on auth/permission failure
                    const data = await res.json();

                    // Apply fetched numbers to every tab sharing this org scope.
                    //
                    // The two variable slots (`orgs` and `extra`) carry a DIFFERENT
                    // label per role, so they must not be fed a fixed field. This
                    // previously assigned `renewals_due` to the slot labelled
                    // "Sakha Sanghas" and `attendance_pct` to slots labelled
                    // "Mahila Sanghas" / "Total Organizations", so those cards
                    // showed a number that had nothing to do with their caption.
                    // Now the label picks the field via STAT_FIELD_BY_LABEL, and
                    // any label with no table behind it renders "Not tracked"
                    // rather than a plausible-looking 0.
                    for (const tab of tabs) {
                        const rc = tab.roleCode;
                        const cur = this.adminStats[rc];
                        const moreLabels = this.MORE_TILES_BY_ROLE[rc] || [];
                        this.adminStats[rc] = {
                            ...cur,
                            members:  data.members  ?? "—",
                            families: data.families ?? "—",
                            orgs:     this._statValue(cur.orgsLabel, data),
                            extra:    this._statValue(cur.extraLabel, data),
                            moreTiles: moreLabels.map(label => ({
                                label,
                                value: this._statValue(label, data),
                            })),
                        };
                    }
                }));
            } catch (e) {
                console.warn("[dashboard] Failed to load admin stats:", e);
            }
        },

        /**
         * Audit & Compliance tab content — real, paginated field-level
         * change history from GET /api/v1/audit/change-log
         * (api/routers/audit.py, AUDIT_VIEW permission). reset=true clears
         * the list and starts over (used when the tab is first opened or
         * a filter changes); reset=false appends the next page ("Load
         * more").
         */
        async _loadAuditRecent(reset) {
            const a = this.adminAudit;
            if (reset) {
                a.entries = [];
                a.offset = 0;
                a.hasMore = true;
            }
            if (a.loading || !a.hasMore) return;

            a.loading = true;
            a.error = "";
            try {
                const params = new URLSearchParams({
                    limit: String(a.pageSize),
                    offset: String(a.offset),
                });
                if (a.tableFilter) params.set("table_name", a.tableFilter);
                if (a.actionFilter) params.set("action", a.actionFilter);

                const res = await NSSAuth.apiFetch(`/api/v1/audit/change-log?${params}`);
                if (res.ok) {
                    const rows = await res.json();
                    a.entries = a.entries.concat(rows);
                    a.offset += rows.length;
                    a.hasMore = rows.length === a.pageSize;
                } else {
                    a.error = "Unable to load the audit trail.";
                }
            } catch (e) {
                a.error = "Unable to connect to server.";
            } finally {
                a.loading = false;
            }
        },

        /** "Load more" button handler for the Recent Changes panel. */
        loadMoreAuditRecent() {
            this._loadAuditRecent(false);
        },

        /** Re-run the query from the start when a filter changes. */
        applyAuditFilter() {
            this._loadAuditRecent(true);
        },

        /**
         * Pending-approvals panel for one of the 5 organizational admin
         * tabs (Kendra/Anchalika/Zilla/Sakha/Patha Chakra Management).
         *
         * transfersPending reuses a real, already-scoped list endpoint —
         * not a new backend feature: GET /api/v1/membership/change-requests,
         * summed over both open statuses (PENDING_SOURCE_RELEASE +
         * PENDING_DESTINATION_ACCEPT — api/routers/
         * membership_change_request.py's _OPEN_STATUSES), covering both
         * legs of the Sakha Transfer / Apply for Darshak workflow this
         * admin might need to act on.
         *
         * claimsPending (Registration Approvals count) was REMOVED
         * (owner decision, 2026-10-22) along with its Quick Actions
         * button — Registration Approvals must appear only as the one
         * left-sidebar nav item, not duplicated per admin tab.
         *
         * Known limitation (not fixed here — the endpoint doesn't accept
         * an org_pk override the way /admin/dashboard-stats does): the
         * count comes from the actor's whole admin scope, not this one
         * tab's own role/org. A user holding two organizational roles at
         * once would see an identical count on both tabs, same class of
         * issue _loadAdminStats() already works around for the 4 stat
         * tiles via ?org_pk=.
         */
        async _loadOrgPendingApprovals(tab) {
            const rc = tab.roleCode;
            if (!this.adminApprovals[rc]) {
                this.adminApprovals[rc] = { transfersPending: null, loading: false, error: "" };
            }
            const entry = this.adminApprovals[rc];
            entry.loading = true;
            entry.error = "";
            try {
                const [srcRes, destRes] = await Promise.all([
                    NSSAuth.apiFetch("/api/v1/membership/change-requests?status=PENDING_SOURCE_RELEASE&page_size=1"),
                    NSSAuth.apiFetch("/api/v1/membership/change-requests?status=PENDING_DESTINATION_ACCEPT&page_size=1"),
                ]);
                const srcTotal = srcRes.ok ? (await srcRes.json()).total : 0;
                const destTotal = destRes.ok ? (await destRes.json()).total : 0;
                entry.transfersPending = (srcRes.ok || destRes.ok) ? (srcTotal + destTotal) : null;
                if (!srcRes.ok && !destRes.ok) {
                    entry.error = "Unable to load pending approvals.";
                }
            } catch (e) {
                entry.error = "Unable to connect to server.";
            } finally {
                entry.loading = false;
            }
        },

        /**
         * Resolve one variable stat card's value from its own caption.
         * Returns "Not tracked" for captions that no table can answer yet, so
         * the card never presents an unbacked slot as a real figure.
         */
        _statValue(label, data) {
            const field = this.STAT_FIELD_BY_LABEL[label];
            if (!field) return "Not tracked";

            if (field === "attendance_pct") {
                // Explicitly untracked: darshak_attendance_registration is an
                // approval record, not a per-meeting log, and no session table
                // exists — so there is no denominator for a percentage.
                if (data.attendance_tracked === false) return "Not tracked";
                return data.attendance_pct != null ? `${data.attendance_pct}%` : "—";
            }

            return data[field] ?? "—";
        },
    });
}
