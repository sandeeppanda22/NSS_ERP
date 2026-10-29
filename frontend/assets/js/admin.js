/**
 * NSS ERP — Admin Dashboard (Tier 5)
 *
 * Alpine.js component for user administration.
 * Tabs: Users list, User detail (with roles), Create user, Change password.
 * All API calls use NSSAuth.apiFetch() for automatic JWT handling.
 */

// Scoped-admin role_code -> the org-dashboard tab's tier label for that
// role's own org (role_code implies org type 1:1 — a Sakha admin's scope
// org is always a Sakha, etc.). Shared shape with dashboard.js's own copy
// (no cross-file include mechanism exists in this static frontend).
const ROLE_ORG_LABELS = {
    NSS_ERP_KENDRA_ADMIN: "Kendra Dashboard",
    NSS_ERP_ANCHALIKA_ADMIN: "Anchalika Dashboard",
    NSS_ERP_ZILLA_ADMIN: "Zilla Dashboard",
    NSS_ERP_SAKHA_ADMIN: "Sakha Dashboard",
    NSS_ERP_PATHA_CHAKRA_ADMIN: "Patha Chakra Dashboard",
    NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN: "Mahila Parichalana Mandali Dashboard",
};

// The dashboard levels shown in the sidebar's "Dashboards" section, in
// hierarchy order. These are exactly the six ORGANIZATIONAL roles in
// role_master (SOL-ADMIN-004 §8.7) — every scoped-admin role has one
// dashboard, and no dashboard exists without a role that can hold it:
//
//   KENDRA               <- NSS_ERP_KENDRA_ADMIN
//   ANCHALIKA_SANGHA     <- NSS_ERP_ANCHALIKA_ADMIN
//   ZILLA_SANGHA         <- NSS_ERP_ZILLA_ADMIN
//   SAKHA_SANGHA         <- NSS_ERP_SAKHA_ADMIN
//   PATHA_CHAKRA         <- NSS_ERP_PATHA_CHAKRA_ADMIN
//   MAHILA_SANGHA        <- NSS_ERP_KENDRA_MAHILA_SANGHA_ADMIN
//
// "Mahila Parichalana Mandali" is the user-facing name for the Mahila
// body; note it is strictly the *governing body* of a Mahila Sangha in
// the frozen domain model (MAH-091 — one body, two names), not an
// organization type of its own. The dashboard is therefore anchored on
// the MAHILA_SANGHA organization the Mandali governs.
const DASHBOARD_LEVELS = [
    { typeCode: "KENDRA", label: "Kendra" },
    { typeCode: "ANCHALIKA_SANGHA", label: "Anchalika" },
    { typeCode: "ZILLA_SANGHA", label: "Zilla" },
    { typeCode: "SAKHA_SANGHA", label: "Sakha" },
    { typeCode: "PATHA_CHAKRA", label: "Patha Chakra" },
    { typeCode: "MAHILA_SANGHA", label: "Mahila Parichalana Mandali" },
];

// Correspondence register tabs (owner 2026-10-26: "when tab is anchalika, we
// should have a dropdown to select the anchalika, not a tab for each
// anchalika, and it should be Anchalika/Zilla"). One tab per org TYPE GROUP,
// not per org: the tab picks the tier, a dropdown inside it picks which org
// of that tier when the admin can file for more than one. Anchalika and Zilla
// share a single tab — they are the same tier of the frozen hierarchy
// (Kendra -> Anchalika/Zilla -> Sakha) and an admin thinks of them as one
// choice. NILACHALA_KUTIRA/SMRUTI_MANDIRA are deliberately absent (apex
// singletons that keep no correspondence register of their own).
const CORR_REGISTER_TAB_GROUPS = [
    { key: "KENDRA", label: "Kendra", typeCodes: ["KENDRA"] },
    { key: "ANCHALIKA_ZILLA", label: "Anchalika/Zilla", typeCodes: ["ANCHALIKA_SANGHA", "ZILLA_SANGHA"] },
    { key: "PATHA_CHAKRA", label: "Patha Chakra", typeCodes: ["PATHA_CHAKRA"] },
    { key: "SAKHA_SANGHA", label: "Sakha", typeCodes: ["SAKHA_SANGHA"] },
    { key: "MAHILA_SANGHA", label: "Mahila Sangha", typeCodes: ["MAHILA_SANGHA"] },
];

function adminApp() {
    // Resolve the initial tab synchronously from the URL hash (e.g.
    // /admin#orgHierarchy) so the page renders the right tab immediately
    // on refresh instead of flashing the default "users" tab first while
    // init() below is still awaiting its network calls. The tab's lazy
    // data loader (e.g. loadOrgHierarchy()) still has to wait for init(),
    // since it needs an authenticated NSSAuth.apiFetch.
    const _initialHash = window.location.hash.replace("#", "");
    const _initialTab = _initialHash.startsWith("detail/") ? "detail"
        : _initialHash.startsWith("orgDashboard/") ? "orgDashboard"
        : (_initialHash || "users");

    // NSSAttendanceRegister.install() adds the shared attendance-register
    // members (permission getters, roster rows, tallies, filter,
    // search-to-add, submit) that this panel and the member dashboard both
    // run — see assets/js/attendance-register.js. install() never
    // overwrites a property defined below, which is how the
    // `_afterAttendanceSaved` hook further down wins.
    return NSSAttendanceRegister.install({
        // ── Shared layout (sidebar toggle, topbar user info) ──
        ...NSSLayout.mixin(),

        // ── Tab navigation ─────────────────────────────────────
        activeTab: _initialTab,  // users | detail | create | createSS | password | organizations | orgDashboard

        // ── Users list ─────────────────────────────────────────
        users: [],
        usersTotal: 0,
        usersPage: 1,
        usersPageSize: 20,
        usersSearch: "",
        usersStatusFilter: "",
        // Server-side sort state. Empty key = server default
        // (newest first), which is what the list showed before sorting
        // existed — so the initial view is unchanged.
        usersSortBy: "",
        usersSortDir: "asc",
        usersLoading: false,
        usersError: "",

        // ── User detail ────────────────────────────────────────
        selectedUser: null,
        detailLoading: false,
        detailError: "",

        // Role-assignment sorting. This list is sorted in the browser, not
        // on the server, and that is correct here: the detail response
        // carries every role the account has, so reordering what is on
        // screen reorders the whole set. (Contrast the paginated user list,
        // where the browser only ever holds one page.)
        rolesSortBy: "",
        rolesSortDir: "asc",

        // ── Create Person & Account ──────────────────────────────
        createForm: {
            person_pk: "", password: "", force_password_change: true,
            // Step 2: Sangha Sevi (membership) — its own step/endpoint now
            // (POST /admin/sangha-sevi), not a checkbox bundled into Step 3
            // Account Credentials. sangha_sevi_pk is set once created;
            // sangha_sevi_skipped lets the operator move on without one
            // (e.g. a person who isn't becoming a member right now).
            sangha_sevi_pk: "", sangha_sevi_skipped: false,
            membership_type_pk: "", organization_pk: "",
            joining_date: "", local_sakha_number: "",
            // Mandatory credential (MBR-010/014/019A/B) — see
            // credentialLabelFor(). Same fields/defaults as ssForm above.
            credential_is_legacy: false, credential_document_number: "",
        },
        createLoading: false,
        createSSLoading: false,
        createError: "",
        createSuccess: "",

        // ── Person search (for create user) ───────────────────
        personSearchQuery: "",
        personSearchResults: [],
        personSearchTotal: 0,
        personSearchLoading: false,
        personSearchDone: false,
        selectedPersonDisplay: {},

        // Search-result sorting (client-side — /person/search returns the
        // whole result set in one response, so what is on screen is all
        // there is). Empty means "keep relevance order", which is what the
        // search endpoint ranks by and usually the most useful default.
        personSearchSortBy: "",
        personSearchSortDir: "asc",
        ssPersonSearchSortBy: "",
        ssPersonSearchSortDir: "asc",

        // ── New person form (inline in create user) ───────────
        showNewPersonForm: false,
        newPersonForm: {
            first_name: "", middle_name: "", last_name: "",
            date_of_birth: "", gender_master_data_pk: "",
            country_phone_code: NSS.DEFAULT_COUNTRY_CODE,
            mobile_number: "", email: "",
        },
        newPersonLoading: false,
        // Live duplicate-contact lookup for the new-person form. Each holds
        // the conflicting person ({person_id, person_name}) or null.
        contactCheck: { mobile: null, email: null },
        _contactCheckTimer: null,

        // ── Reference data (loaded on init) ──────────────────
        genders: [],
        maritalStatuses: [],
        bloodGroups: [],
        relationships: [],

        // ── Profile Details edit (admin Detail view) ──────────
        profileEdit: {
            loading: false, saving: false, editing: false,
            error: null, saveError: null,
            form: {
                first_name: "", middle_name: "", last_name: "",
                date_of_birth: "", gender_master_data_pk: "",
                marital_status_master_data_pk: "", blood_group_master_data_pk: "",
                country_phone_code: "", mobile_number: "", email: "",
                emergency_contact_name: "", emergency_contact_phone: "",
                emergency_relationship_master_data_pk: "", remarks: "",
            },
            reason: "",
        },

        // ── Create Sangha Sevi ────────────────────────────────
        ssForm: {
            person_pk: "", membership_type_pk: "", organization_pk: "",
            joining_date: "", local_sakha_number: "",
            // Mandatory credential (MBR-010/014/019A/B) — see
            // credentialLabelFor(). Leave credential_is_legacy false (the
            // default) to auto-generate a new FY document number; check it
            // to record an already-issued legacy credential by hand.
            credential_is_legacy: false, credential_document_number: "",
            // Optional bundled login-account creation. Login is by
            // sangha_sevi_id, so the SS flow is the right place to offer it.
            create_user_account: false, password: "", force_password_change: true,
        },
        ssLoading: false,
        ssError: "",
        ssSuccess: "",
        ssPersonSearchQuery: "",
        ssPersonSearchResults: [],
        ssPersonSearchTotal: 0,
        ssPersonSearchLoading: false,
        ssPersonSearchDone: false,
        ssSelectedPerson: {},

        // Sakha auto-select/lock for member-attach forms (mirrors the
        // Kumari/Sevak parent-Sakha pattern): a single-Sakha admin gets
        // their Sakha auto-selected and the dropdown locked.
        sakhaScope: { mode: "choose", auto_select_pk: null, sakhas: [] },

        // ── Membership types (for SS creation) ────────────────
        membershipTypes: [],

        // ── Reset password ─────────────────────────────────────
        resetForm: { new_password: "", force_password_change: true },
        resetLoading: false,
        resetError: "",
        resetSuccess: "",
        showResetModal: false,
        resetTargetPk: null,
        resetTargetName: "",

        // ── Create Account picker (for a Sangha Sevi who has an SS ID
        // but no login yet) ─────────────────────────────────────────
        showCreateAccountModal: false,
        cazSearch: "",
        cazLoading: false,
        cazError: "",
        cazMembers: [],
        cazSelected: null,        // the AccountlessSanghaSeviResponse chosen from the list
        cazForm: { password: "", force_password_change: true },
        cazSubmitLoading: false,
        cazSubmitError: "",

        // ── Role assignment ────────────────────────────────────
        roleForm: { role_code: "", scope_level: "NSS-WIDE", organization_pk: "" },
        roleLoading: false,
        roleError: "",
        roleSuccess: "",
        showRoleModal: false,
        roleTargetPk: null,
        roleTargetName: "",
        roleTargetRoles: [],

        // ── Available roles (fetched from bootstrap API) ───────
        availableRoles: [],

        // ── Available organizations (fetched for scope picker) ──
        organizations: [],

        // ── Change own password ────────────────────────────────
        pwForm: { current_password: "", new_password: "", confirm_password: "" },
        pwLoading: false,
        pwError: "",
        pwSuccess: "",

        // ── Toast ──────────────────────────────────────────────
        toast: "",
        toastType: "success",

        // ── Organization management ───────────────────────────
        orgsList: [],
        orgsTotal: 0,
        orgPage: 1,
        orgPageSize: 50,
        orgSearch: "",
        orgTypeFilter: "SAKHA_SANGHA",
        orgsLoading: false,
        // Organizations sorting. Empty keeps the server default
        // (organization_code), the order this list shipped with.
        orgsSortBy: "",
        orgsSortDir: "asc",
        editingOrgPk: null,
        editingShortCode: "",
        savingShortCode: false,
        inlineShortCodeCheck: { checking: false, conflict: null },

        // ── Organization detail editing ───────────────────────
        editOrgDetailPk: null,
        editOrgForm: {},
        savingOrgDetail: false,

        // ── Create Organization (NSS_ERP_ADMIN only) ─────────
        createOrgForm: {
            organization_name: "", organization_type_code: "",
            parent_organization_pk: "", organization_code: "", short_code: "",
            has_own_premises: false,
            address_line_1: "", city_village_name: "",
            country_pk: "", state_pk: "", district_pk: "", postal_code_value: "",
            phone_number: "", country_phone_code: NSS.DEFAULT_COUNTRY_CODE, mobile_number: "", org_email: "",
            org_website_url: "", org_youtube_channel_url: "",
        },
        createOrgLoading: false,
        createOrgError: "",
        createOrgSuccess: "",
        orgTypes: [],
        createOrgCountries: [],
        createOrgStates: [],
        createOrgDistricts: [],
        createOrgCities: [],
        // Kumari/Sevak Sakha-scoped parent selection (ORG-BR-101/102).
        // { mode: 'choose'|'locked', auto_select_pk, sakhas: [...] }
        kumariSevakScope: { mode: "choose", auto_select_pk: null, sakhas: [] },
        kumariSevakScopeLoading: false,

        // ── Auto-generated org code preview (ORG-BR-105) ─────────────
        // Live "what the code will be if submitted" value for the selected
        // non-wing type, peeked from the sequence (never consumed) via
        // GET /admin/organizations/next-code. Blank for wings/typeless.
        orgCodePreview: "",
        orgCodePreviewLoading: false,

        // ── Live duplicate check for organization_code / short_code ──
        // { checking, conflict, checkedValue } per field; _codeCheckTimers
        // holds the per-field debounce handles.
        orgCodeCheck: { checking: false, conflict: null },
        shortCodeCheck: { checking: false, conflict: null },
        _codeCheckTimers: {},

        // ── Location lookups (for org edit cascading dropdowns) ──
        locationCountries: [],
        locationStates: [],
        locationDistricts: [],
        locationCities: [],

        // ── Governance (Tier 6) ─────────────────────────────────
        govCatalogLoading: false,
        govCatalogError: "",
        govBodyTypes: [],
        govPositions: [],
        govBodyTypeForm: { show: false, saving: false, error: "", body_type_code: "", body_type_name: "", description: "" },
        govBodyTypeEdit: { pk: null, body_type_name: "", description: "", saving: false, error: "" },
        govPositionForm: { show: false, saving: false, error: "", position_code: "", position_name: "", description: "", display_order: 0 },
        govPositionEdit: { pk: null, position_name: "", description: "", display_order: 0, saving: false, error: "" },

        govBodiesLoading: false,
        govBodiesError: "",
        govBodies: [],
        // Unfiltered copy of the same fetch — the Assignments tab's body
        // picker (govSelectedBodyPk) must always offer every body the
        // admin can see, independent of whatever body_type_master_pk
        // filter is set on the Bodies tab's own list (govBodies). Those
        // two previously shared one filtered array, so narrowing the
        // Bodies tab to e.g. "Mahila Parichalana Mandali" silently hid
        // every other body from the Assignments picker too.
        govBodiesAll: [],
        govBodyTypeFilter: "",
        govBodyForm: {
            show: false, saving: false, error: "", body_type_master_pk: "", body_code: "", body_name: "",
            description: "", organization_pk: "", effective_from: "",
            orgQuery: "", orgResults: [], orgSearching: false, selectedOrg: null,
        },
        // Scoped Sakha picker state for the Sakha-anchored body types in
        // govScopedSakhaBodyTypes (requirement: auto-select the admin's
        // own Sakha when unambiguous, else a dropdown restricted to only
        // their scoped Sakhas) — same shape/mechanism as kumariSevakScope.
        govBodySakhaScope: { mode: "choose", auto_select_pk: null, sakhas: [] },
        govBodySakhaScopeLoading: false,
        // Which Organization type a Governance Body's org-picker should
        // search within, keyed by body_type_code. Kendra Governing Body
        // and Advisory Board are NSS-wide (no org — field stays blank).
        // SEVAK_SANGHA_EXECUTIVE (display label "Sevak Sangha") is a
        // local/per-Sakha body, same pattern as Mahila Parichalana
        // Mandali below — it maps to SAKHA_SANGHA too.
        //
        // MAHILA_PARICHALANA_MANDALI and SEVAK_SANGHA_EXECUTIVE both map
        // to SAKHA_SANGHA, not a separate "Mahila Sangha"/"Sevak Sangha"
        // organization — confirmed against the backend (api/routers/
        // admin.py create_organization): MAHILA_SANGHA has no entry in
        // _ALLOWED_PARENT_TYPES/_STANDARD_CREATABLE_TYPES/
        // _SAKHA_GATED_TYPES, i.e. there is no creation path for a
        // standalone Mahila Sangha org row per Sakha. A Sakha's Mahila
        // Parichalana Mandali (and its Sevak Sangha executive) is a
        // second/third governance body attached to that SAME Sakha
        // organization, not to a distinct org. (The one genuinely
        // separate Mahila Sangha — the central Nilachala Saraswata
        // Mahila Sangha at Puri — is NSS-wide and already auto-seeded
        // with organization_pk NULL; see 03_body_master.sql.)
        govBodyOrgTypeByBodyType: {
            SAKHA_GOVERNING_BODY: "SAKHA_SANGHA",
            MAHILA_PARICHALANA_MANDALI: "SAKHA_SANGHA",
            SEVAK_SANGHA_EXECUTIVE: "SAKHA_SANGHA",
        },
        // Code-generation suffix per body_type_code, used instead of the
        // raw body_type_code when it would be redundant with the org
        // itself being a Sakha (e.g. "SKH1_SAKHA_GOVERNING_BODY" →
        // "SKH1_GOVERNING_BODY"). Falls back to the full body_type_code
        // for any type not listed here.
        govBodyCodeSuffixByBodyType: {
            SAKHA_GOVERNING_BODY: "GOVERNING_BODY",
            MAHILA_PARICHALANA_MANDALI: "MAHILA_PARICHALANA_MANDALI",
            SEVAK_SANGHA_EXECUTIVE: "SEVAK_SANGHA",
        },
        // Sakha-anchored body types whose org-picker should use the
        // scoped auto-select/locked-dropdown UX (requirement: admin's
        // own Sakha scope), same mechanism as loadKumariSevakScope.
        govScopedSakhaBodyTypes: [
            "SAKHA_GOVERNING_BODY", "MAHILA_PARICHALANA_MANDALI", "SEVAK_SANGHA_EXECUTIVE",
        ],
        govBodyEdit: { pk: null, body_name: "", description: "", body_status: "", effective_from: "", effective_to: "", saving: false, error: "" },

        govSelectedBodyPk: "",
        govAssignmentsLoading: false,
        govAssignmentsError: "",
        govAssignments: [],
        // Current Assignments list is capped at NSS.GOV_MEMBER_CAP (9) rows
        // with a "Show all N" toggle, matching the governance-body cards
        // elsewhere (owner ask #2, 2026-10-24). Reset to collapsed whenever
        // the body or the Sakha filter changes (see onGovBodyChange /
        // _applyGovSakhaFilterDefault / the dropdown's @change).
        govAssignmentsShowAll: false,
        // Sakha filter (owner ask #3): a sakha_organization_pk, "" = All
        // Sakhas. Auto-select/lock follows the universal Sakha-scope rule
        // mirrored from govAssignableBodies (isGovNssWideAdmin +
        // currentUser.admin_scope_org_pks).
        govSakhaFilter: "",

        govAllowedPositions: [],
        govSeatLimit: null,
        govSeatsFilled: 0,
        govInheritedPositions: [],
        govAssignFromResults: [],
        govAssignFromResultsLoading: false,
        govAssignOfficersFromMembers: false,
        govAssignOrgPk: null,
        govMissingNominations: [],
        govMissingNominationsLoading: false,
        govMissingNominationsError: "",
        govAssignForm: {
            show: false, saving: false, error: "",
            position_master_pk: "", effective_from: "",
            personQuery: "", personResults: [], personSearching: false,
            selectedPerson: null,
        },

        // ── Acting / Interim Cover (GOV-BR-018/019/020) — a separate table
        // from body_member_assignment, no composition/seat-limit check, and
        // its own position list (allowed-positions?exclude_filled=false:
        // interim cover is legitimate WHILE a seat is vacant or unavailable,
        // so an already-filled position must still be offered).
        govActingLoading: false,
        govActingError: "",
        govActing: [],
        govActingPositions: [],
        govActingForm: {
            show: false, saving: false, error: "",
            position_master_pk: "", effective_from: "", effective_to: "",
            reason: "", remarks: "",
            personQuery: "", personResults: [], personSearching: false,
            selectedPerson: null,
        },

        // ── Governance Elections (Tier 6 voting slice, GOV-BR-045) ──
        govElectionsLoading: false,
        govElectionsError: "",
        govElections: [],
        govElectionForm: {
            show: false, saving: false, error: "",
            body_master_pk: "", election_code: "", election_name: "",
            election_type: "ELECTION",
            election_date: "", nomination_start_date: "", nomination_end_date: "",
            voting_start_date: "", voting_end_date: "", is_secret_ballot: false,
            description: "", remarks: "",
        },
        govSelectedElectionPk: "",
        govSelectedElection: null,
        govElectionBusy: false,
        govElectionActionError: "",
        govElectionPositions: [],
        govNominations: [],
        govNominationsLoading: false,
        govNominationForm: {
            show: false, saving: false, error: "",
            position_master_pk: "", nomination_date: "", remarks: "",
            candidateQuery: "", candidateResults: [], candidateSearching: false, selectedCandidate: null,
            proposerQuery: "", proposerResults: [], proposerSearching: false, selectedProposer: null,
        },
        govVoteForm: {
            show: false, saving: false, error: "",
            election_nomination_pk: "",
            voterQuery: "", voterResults: [], voterSearching: false, selectedVoter: null,
            remarks: "",
        },
        govSelfVote: { saving: false, error: "", notice: "", election_nomination_pk: "" },
        govTally: [],
        govTallyLoading: false,
        govTallyError: "",
        govResults: [],
        govResultsLoading: false,
        govResultForm: {
            show: false, saving: false, error: "",
            position_master_pk: "", winning_nomination_pk: "", result_status: "DECLARED", remarks: "",
        },
        govResetForm: {
            show: false, saving: false, error: "",
            reset_mode: "PRESIDENT_UNILATERAL", position_master_pk: "", reason: "",
            presidentQuery: "", presidentResults: [], presidentSearching: false, selectedPresident: null,
        },
        _govTypeTimers: {},

        // ── Correspondence Register (Tier 6, SOL-ADMIN-009) ─────
        // Mirrors the Governance tabs' loading/error/form conventions
        // above. A "picker" is the shared shape used for every person/
        // organization type-ahead field: { query, results, searching,
        // selected }. Debounce timers live on the picker object itself
        // (picker._timer) rather than a shared keyed dict.
        corrLoading: false,
        corrError: "",
        corrItems: [],
        corrTotal: 0,
        corrPage: 1,
        corrPageSize: 20,
        corrDirectionFilter: "",
        corrStatusFilter: "",
        corrOrgFilter: { pk: "", query: "", results: [], searching: false, selected: null },

        corrMediums: [],
        corrFinanceRelationshipTypes: [],
        corrCatalogLoaded: false,

        // GET /foundation/documents needs FOUNDATION_VIEW, which a
        // Correspondence-only admin may not hold — handled as a graceful
        // degrade (manual document_master_pk entry) rather than a hard
        // dependency; see corrLoadDocumentOptions().
        corrDocumentOptions: [],
        corrDocumentOptionsError: "",

        corrSelected: null,
        corrDetailLoading: false,
        corrDetailError: "",

        corrDocuments: [],
        corrDocumentsLoading: false,
        corrDocumentsError: "",
        corrFinanceRefs: [],
        corrFinanceRefsLoading: false,
        corrFinanceRefsError: "",

        // History + reply-thread "path tracker" (owner 2026-10-26: "can we
        // add history with path tracker for correspondance?") — events is
        // the full nss.system_event_log activity log for this one record
        // (status transitions, manual or the 2026-10-26 auto ones, dispatch,
        // responsible-party reassignment); ancestors/descendants are the
        // reply thread (in_reply_to_correspondence_pk) walked both ways.
        corrHistory: { events: [], ancestors: [], descendants: [] },
        corrHistoryLoading: false,
        corrHistoryError: "",

        // Simplified create form (owner request, 2026-10-25: "make the ui
        // simpler for send/receive application/letter"). The insight that
        // drives the simplification: an admin filing correspondence
        // through THIS form is always filing it FOR their own
        // organization — so whichever party that implies (sender for a
        // Send/OUTWARD letter, recipient for a Receive/INWARD letter) is
        // silently defaulted to ORGANIZATION = the register organization,
        // instead of asking the admin to pick it every time. The genuinely
        // open question is always the OTHER party, which stays fully
        // visible. usPartyOverride reveals the full original Person/
        // Organization/External picker for "our" side too, for the rare
        // case it wasn't the organization generally (e.g. a specific
        // office-bearer signed it personally). Direction itself is no
        // longer a form field — toggleCorrCreateForm() already fixes it
        // from which quick-action button was clicked.
        corrCreateForm: {
            show: false, saving: false, error: "",
            org: { query: "", results: [], searching: false, selected: null },
            orgAutoResolved: false, orgPickerExpanded: false,
            orgTabGroups: [], orgMultipleChoices: false,
            activeOrgTab: "", activeOrgPk: "",
            direction: "INWARD",
            // Single collapsed date (defaults to today in
            // corrResetCreateForm/toggleCorrCreateForm); splitDates reveals
            // the original two independent fields for the rare case a
            // letter's written date and received/sent date differ.
            date: "", splitDates: false,
            correspondence_date: "", received_or_sent_date: "", follow_up_date: "",
            subject: "", remarks: "", medium: "",

            // Circular (owner request, 2026-10-26: "sometimes, kendra/
            // anchalika/zilla send letter to all sakhas under it") — OUTWARD
            // only, posts to POST /correspondence/broadcast instead of the
            // single-letter endpoint. No sender override: a circular is
            // always sent BY the organization (see createBroadcastCorrespondence()).
            isBroadcast: false, broadcastRecipientTypeCode: "",

            moreOptions: false,
            usPartyOverride: false,

            sender_type: "PERSON",
            sender_person_capacity: "",
            senderPerson: { query: "", results: [], searching: false, selected: null },
            senderPersonOrg: { query: "", results: [], searching: false, selected: null },
            senderOrg: { query: "", results: [], searching: false, selected: null },
            sender_external_name: "", sender_external_organization: "",

            recipient_type: "ORGANIZATION",
            recipientPerson: { query: "", results: [], searching: false, selected: null },
            recipientOrg: { query: "", results: [], searching: false, selected: null },
            recipient_external_name: "", recipient_external_organization: "",

            // Optional responsible-party-at-creation (schema allows it) —
            // separate pickers so clearing one doesn't disturb sender/
            // recipient state.
            responsiblePerson: { query: "", results: [], searching: false, selected: null },
            responsibleOrg: { query: "", results: [], searching: false, selected: null },

            // Reply threading (v1.2, owner 2026-10-26: "we should also add
            // reply option to letter too") — set only via replyToCorrespondence()
            // prefill, carried through to the create payload as
            // in_reply_to_correspondence_pk. replyingToReference is display-only
            // (the banner above the form); the pk is what's actually submitted.
            inReplyToPk: "", replyingToReference: "",
        },

        corrDispatchForm: { saving: false, error: "" },

        corrResponsibleForm: {
            show: false, saving: false, error: "", mode: "person",
            person: { query: "", results: [], searching: false, selected: null },
            org: { query: "", results: [], searching: false, selected: null },
        },

        corrDocumentForm: { show: false, saving: false, error: "", document_master_pk: "", document_purpose: "ORIGINAL", remarks: "" },
        corrFinanceForm: { show: false, saving: false, error: "", financial_transaction_pk: "", relationship_type: "", remarks: "" },

        // ── Computed helpers ───────────────────────────────────
        get totalPages() {
            return Math.max(1, Math.ceil(this.usersTotal / this.usersPageSize));
        },

        get canManageUsers() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("ADMIN_USER_MANAGE") ||
                 this.currentUser.permissions.includes("PERSON_MANAGE"));
        },

        // ADMIN-BR-078: account provisioning is a scoped operation, not
        // reserved to the global authority. Any admin who can manage users
        // (ADMIN_USER_MANAGE or PERSON_MANAGE) may create accounts within
        // their scope; the API enforces the scope boundary.
        get canCreateAccounts() {
            return this.canManageUsers;
        },

        get canViewUsers() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("ADMIN_USER_VIEW") ||
                 this.currentUser.permissions.includes("ADMIN_USER_MANAGE") ||
                 this.currentUser.permissions.includes("MEMBERSHIP_APPROVE"));
        },

        get canManageRoles() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("ADMIN_ROLE_MANAGE"));
        },

        get canManageSettings() {
            return this.currentUser &&
                this.currentUser.permissions.includes("FOUNDATION_MANAGE");
        },

        get canManageMasterData() {
            return this.currentUser &&
                this.currentUser.permissions.includes("FOUNDATION_MANAGE");
        },

        // GEO_ENTRY_APPROVE (2026-10-21): narrower than FOUNDATION_MANAGE —
        // lets a Sakha admin reach the Location Approvals tab for their own
        // Sakha's geography proposals without the broader master-data
        // authority. geo_approval.py accepts either permission on every
        // /admin/geo-entries endpoint.
        get canApproveGeoEntries() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("GEO_ENTRY_APPROVE") ||
                 this.currentUser.permissions.includes("FOUNDATION_MANAGE"));
        },

        // SOL-ARCH-013: adding/confirming festival calendar dates is a
        // narrower authority than general Foundation settings — only
        // NSS_ERP_ADMIN holds FOUNDATION_CALENDAR_MANAGE.
        get canManageCalendar() {
            return this.currentUser &&
                this.currentUser.permissions.includes("FOUNDATION_CALENDAR_MANAGE");
        },

        get canApproveClaims() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("MEMBERSHIP_APPROVE"));
        },

        // Sakha Transfer / Apply for Darshak queue (MBR-048/MBR-049) —
        // mirrors the GET /api/v1/membership/change-requests admin-view
        // gate (MEMBERSHIP_VIEW or MEMBERSHIP_APPROVE).
        get canViewChangeRequests() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("MEMBERSHIP_VIEW") ||
                 this.currentUser.permissions.includes("MEMBERSHIP_APPROVE"));
        },

        // Member Credentials tab (MBR-010/MBR-019B/MBR-030H) — view gate
        // mirrors GET /api/v1/admin/credentials/members; manage gate mirrors
        // the issue/promote POST endpoints.
        get canViewCredentials() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("MEMBERSHIP_VIEW") ||
                 this.currentUser.permissions.includes("MEMBERSHIP_MANAGE") ||
                 this.currentUser.permissions.includes("ADMIN_USER_MANAGE"));
        },

        get canManageCredentials() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("MEMBERSHIP_MANAGE") ||
                 this.currentUser.permissions.includes("ADMIN_USER_MANAGE"));
        },

        get isNssAdmin() {
            return this.currentUser &&
                this.currentUser.scopes &&
                this.currentUser.scopes.some(s => s.role_code === "NSS_ERP_ADMIN");
        },

        // A Sakha-scoped admin (NSS_ERP_SAKHA_ADMIN or any other role holding
        // a SAKHA-level scope). Single source of truth — was previously
        // inlined in creatableOrgTypes alone; now also gates the Create
        // Organization nav item (2026-10-27), so it needs to live here.
        get hasSakhaScope() {
            return !!(this.currentUser && (this.currentUser.scopes || []).some(
                s => s.scope_level === "SAKHA"
            ));
        },

        // ── Governance (Tier 6) permissions ──────────────────────
        get canViewGovernance() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("GOVERNANCE_VIEW") ||
                 this.currentUser.permissions.includes("GOVERNANCE_MANAGE"));
        },

        get canManageGovernance() {
            return this.currentUser &&
                this.currentUser.permissions.includes("GOVERNANCE_MANAGE");
        },

        // ── Attendance (Tier 6, 2026-10-27) ───────────────────────
        // canViewAttendance / canManageAttendance and the whole
        // mark-attendance grid (rows, tallies, filter, search-to-add,
        // submit) come from the shared NSSAttendanceRegister mixin
        // installed on this component — the member dashboard runs the
        // identical register, so that logic lives exactly once, in
        // assets/js/attendance-register.js.

        // ── Attendance state (Tier 6) ──────────────────────────────
        attPujas: [], attPujasTotal: 0, attPujasLoading: false, attPujasError: "",
        attPujaOrgFilter: "", attPujaSakhaOptions: [],
        attPujaForm: { show: false, saving: false, error: "", sakha_pk: "", puja_date: "", remarks: "" },

        // Host hook for the shared register — the puja list's
        // marked/present/absent tallies just changed, so reload it.
        _afterAttendanceSaved() {
            return this.loadAttPujas();
        },

        // When the admin's scope resolves to exactly one Sakha, the puja
        // form / filters / stats pick it automatically and show it as
        // plain text instead of a one-option dropdown (owner ask
        // 2026-10-27). null for a multi-Sakha or NSS-wide admin.
        get attSingleSakha() {
            return this.attPujaSakhaOptions.length === 1 ? this.attPujaSakhaOptions[0] : null;
        },

        attReviews: [], attReviewsTotal: 0, attReviewsLoading: false, attReviewsError: "",
        attReviewStatusFilter: "", attReviewActionBusy: null, attReviewActionError: {},

        attWatchList: [], attWatchListLoading: false, attWatchListError: "",

        attOrgStatsOrgPk: "", attOrgStats: null, attOrgStatsLoading: false, attOrgStatsError: "",
        attMemberStatsQuery: "", attMemberStatsResults: [], attMemberStats: null,
        attMemberStatsLoading: false, attMemberStatsError: "",

        attExceptionForm: {
            show: false, saving: false, error: "", sangha_sevi_pk: "", person_label: "",
            exception_type_code: "MEDICAL", from_date: "", to_date: "", remarks: "",
        },
        attExceptionMemberResults: [],

        // Bug fix (owner report, 2026-10-27): this previously called the
        // PUBLIC /organization/organizations/selectable endpoint, which
        // has no admin_scope filtering by design (it's the unauthenticated
        // self-registration Sakha picker) — every admin, including the
        // narrowest Sakha admin, saw all 175 Sakhas nationwide in the
        // puja/stats Sakha picker. Reuses _fetchAllAdminOrganizations
        // (already scoped via /admin/organizations -> _actor_scope_org_pks,
        // the same helper loadAssignSakhaData uses) instead of a second,
        // unscoped data source.
        async _loadAttSakhaOptions() {
            if (this.attPujaSakhaOptions.length) return;
            try {
                const orgs = await this._fetchAllAdminOrganizations("SAKHA_SANGHA");
                this.attPujaSakhaOptions = orgs.slice().sort(
                    (a, b) => (a.organization_name || "").localeCompare(b.organization_name || "")
                );
                // Single-Sakha admin: pre-select it everywhere (form,
                // list filter, org-stats picker) so the UI can render it
                // as text instead of a one-option dropdown.
                if (this.attPujaSakhaOptions.length === 1) {
                    const only = this.attPujaSakhaOptions[0].organization_pk;
                    this.attPujaForm.sakha_pk = only;
                    this.attOrgStatsOrgPk = only;
                }
            } catch (e) {
                console.error("Failed to load Sakha list for Attendance", e);
            }
        },

        async loadAttPujas() {
            await this._loadAttSakhaOptions();
            this.attPujasLoading = true;
            this.attPujasError = "";
            try {
                const params = new URLSearchParams({ page_size: "50" });
                if (this.attPujaOrgFilter) params.set("organization_pk", this.attPujaOrgFilter);
                const res = await NSSAuth.apiFetch(`/api/v1/attendance/pujas?${params}`);
                if (!res.ok) throw new Error("Failed to load Weekly Sangha Puja events.");
                const data = await res.json();
                this.attPujas = data.pujas || [];
                this.attPujasTotal = data.total || 0;
            } catch (e) {
                this.attPujasError = e.message || "Failed to load Weekly Sangha Puja events.";
                this.attPujas = [];
            } finally {
                this.attPujasLoading = false;
            }
        },

        async submitCreatePuja() {
            if (!this.attPujaForm.sakha_pk || !this.attPujaForm.puja_date) return;
            this.attPujaForm.saving = true;
            this.attPujaForm.error = "";
            try {
                const res = await NSSAuth.apiFetch("/api/v1/attendance/pujas", {
                    method: "POST",
                    body: JSON.stringify({
                        sakha_pk: this.attPujaForm.sakha_pk,
                        puja_date: this.attPujaForm.puja_date,
                        remarks: this.attPujaForm.remarks || null,
                    }),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                this.attPujaForm = { show: false, saving: false, error: "", sakha_pk: "", puja_date: "", remarks: "" };
                await this.loadAttPujas();
            } catch (e) {
                this.attPujaForm.error = e.message || "Failed to create puja event.";
            } finally {
                this.attPujaForm.saving = false;
            }
        },

        async loadAttReviews() {
            this.attReviewsLoading = true;
            this.attReviewsError = "";
            try {
                const params = new URLSearchParams({ page_size: "50" });
                if (this.attReviewStatusFilter) params.set("review_status", this.attReviewStatusFilter);
                const res = await NSSAuth.apiFetch(`/api/v1/attendance/reviews?${params}`);
                if (!res.ok) throw new Error("Failed to load Attendance Reviews.");
                const data = await res.json();
                this.attReviews = data.reviews || [];
                this.attReviewsTotal = data.total || 0;
            } catch (e) {
                this.attReviewsError = e.message || "Failed to load Attendance Reviews.";
                this.attReviews = [];
            } finally {
                this.attReviewsLoading = false;
            }
        },

        // action in {close, defer, revisit, 'escalate-to-president',
        // 'escalate-to-parichalak', reopen}. Buttons are shown to anyone
        // with ATTENDANCE_VIEW (entry gate); the real Secretary/President
        // seat check happens server-side (ATT-042) and surfaces as a 403
        // here if the caller isn't the seated office-holder.
        async actOnReview(review, action) {
            this.attReviewActionBusy = review.review_pk;
            this.attReviewActionError = { ...this.attReviewActionError, [review.review_pk]: "" };
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/attendance/reviews/${review.review_pk}/${action}`, {
                    method: "POST",
                    body: JSON.stringify({ remarks: null }),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                await this.loadAttReviews();
            } catch (e) {
                this.attReviewActionError = {
                    ...this.attReviewActionError,
                    [review.review_pk]: e.message || "Action failed.",
                };
            } finally {
                this.attReviewActionBusy = null;
            }
        },

        // Searches Member Directory for the attExceptionForm's target
        // member — same pattern as searchAttMemberStats, reused rather
        // than duplicated by a shared results array keyed per-form-use.
        async searchAttExceptionMember() {
            const q = (this.attExceptionForm.person_label || "").trim();
            if (q.length < 2 || this.attExceptionForm.sangha_sevi_pk) { this.attExceptionMemberResults = []; return; }
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/membership/directory?q=${encodeURIComponent(q)}&limit=10`);
                if (res.ok) {
                    const data = await res.json();
                    this.attExceptionMemberResults = data.members || [];
                }
            } catch (e) {
                console.error("Exception-form member search failed", e);
            }
        },

        pickAttExceptionMember(m) {
            this.attExceptionForm.sangha_sevi_pk = m.sangha_sevi_pk;
            this.attExceptionForm.person_label =
                [m.first_name, m.middle_name, m.last_name].filter(Boolean).join(" ") + " (" + m.sangha_sevi_id + ")";
            this.attExceptionMemberResults = [];
        },

        async submitCreateException() {
            if (!this.attExceptionForm.sangha_sevi_pk || !this.attExceptionForm.from_date) return;
            this.attExceptionForm.saving = true;
            this.attExceptionForm.error = "";
            try {
                const res = await NSSAuth.apiFetch("/api/v1/attendance/exceptions", {
                    method: "POST",
                    body: JSON.stringify({
                        sangha_sevi_pk: this.attExceptionForm.sangha_sevi_pk,
                        exception_type_code: this.attExceptionForm.exception_type_code,
                        from_date: this.attExceptionForm.from_date,
                        to_date: this.attExceptionForm.to_date || null,
                        remarks: this.attExceptionForm.remarks || null,
                    }),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                this.attExceptionForm = {
                    show: false, saving: false, error: "", sangha_sevi_pk: "", person_label: "",
                    exception_type_code: "MEDICAL", from_date: "", to_date: "", remarks: "",
                };
            } catch (e) {
                this.attExceptionForm.error = e.message || "Failed to approve exception.";
            } finally {
                this.attExceptionForm.saving = false;
            }
        },

        async loadAttWatchList() {
            await this._loadAttSakhaOptions();
            this.attWatchListLoading = true;
            this.attWatchListError = "";
            try {
                const res = await NSSAuth.apiFetch("/api/v1/attendance/watch-list");
                if (!res.ok) throw new Error("Failed to load the Attendance watch list.");
                const data = await res.json();
                this.attWatchList = data.items || [];
            } catch (e) {
                this.attWatchListError = e.message || "Failed to load the Attendance watch list.";
                this.attWatchList = [];
            } finally {
                this.attWatchListLoading = false;
            }
        },

        async loadAttOrgStats() {
            await this._loadAttSakhaOptions();  // single-Sakha admin auto-selects attOrgStatsOrgPk here
            if (!this.attOrgStatsOrgPk) { this.attOrgStats = null; return; }
            this.attOrgStatsLoading = true;
            this.attOrgStatsError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/attendance/stats/organizations/${this.attOrgStatsOrgPk}`);
                const data = await res.json();
                if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                this.attOrgStats = data;
            } catch (e) {
                this.attOrgStatsError = e.message || "Failed to load attendance statistics.";
                this.attOrgStats = null;
            } finally {
                this.attOrgStatsLoading = false;
            }
        },

        async searchAttMemberStats() {
            const q = (this.attMemberStatsQuery || "").trim();
            if (q.length < 2) { this.attMemberStatsResults = []; return; }
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/membership/directory?q=${encodeURIComponent(q)}&limit=10`);
                if (res.ok) {
                    const data = await res.json();
                    this.attMemberStatsResults = data.members || [];
                }
            } catch (e) {
                console.error("Member stats search failed", e);
            }
        },

        async loadAttMemberStats(sangha_sevi_pk) {
            this.attMemberStatsLoading = true;
            this.attMemberStatsError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/attendance/stats/members/${sangha_sevi_pk}`);
                const data = await res.json();
                if (!res.ok) throw new Error(NSS.errorMessage(data, res.status));
                this.attMemberStats = data;
            } catch (e) {
                this.attMemberStatsError = e.message || "Failed to load member attendance statistics.";
                this.attMemberStats = null;
            } finally {
                this.attMemberStatsLoading = false;
            }
        },

        // body_type_code of the currently-selected governance body — feeds
        // NSS.govBodyCardClass/Title/ButtonClass() for the Current
        // Assignments / Acting-Interim-Cover panels (owner ask, 2026-10-24:
        // per-body-type colours on the assignment page too, not just the
        // read-only Governance tab cards).
        get govSelectedBodyType() {
            const b = (this.govBodiesAll || [])
                .find(x => x.body_master_pk === this.govSelectedBodyPk);
            return b ? b.body_type_code : null;
        },

        // "Absent — Acting" indicator (owner ask #3, 2026-10-24) for the
        // Current Assignments table — admin already has GOVERNANCE_VIEW/
        // MANAGE, so the existing GET /bodies/{pk}/acting-assignments call
        // (loadGovActing(), this.govActing) is reused as-is, no new fetch.
        // Matched by position_code, same as the public-panel version in
        // governance.py::_assemble_bodies_with_members. Only an ACTIVE row
        // whose effective window actually covers today counts — govActing
        // (is_active=TRUE) also still contains ENDED rows (ending only
        // flips acting_status, never is_active) and can contain a
        // not-yet-started or already-finished bounded-date delegation
        // (bug found 2026-10-25 server-side; mirrored here too so a
        // future/past delegation never shows as "currently acting").
        govActingFor(a) {
            const today = new Date().toISOString().slice(0, 10);
            const row = (this.govActing || []).find(x =>
                x.position_code === a.position_code && x.acting_status === "ACTIVE" &&
                x.effective_from <= today && (!x.effective_to || x.effective_to >= today)
            );
            return row ? row.person_name : null;
        },

        // ── Assignments: Sakha filter (owner ask #3) + 9-row cap (ask #2),
        // 2026-10-24. The assignment rows carry the holder's home Sakha
        // (sakha_name / sakha_organization_pk, added server-side in
        // _ASSIGNMENT_SELECT_SQL). All client-side over the already-loaded
        // govAssignments — no new fetch. Inherited rows (govInheritedPositions)
        // have no home Sakha and are unaffected by either control. ──────────

        // Distinct home Sakhas across ALL loaded rows, ignoring admin scope —
        // decides whether a body has enough Sakha variety to warrant the
        // filter at all (0/1 for Kendra GB etc. whose seats aren't
        // Sakha-nominated → dropdown hidden).
        get govAssignmentDistinctSakhaCount() {
            const seen = new Set();
            for (const a of (this.govAssignments || [])) {
                if (a.sakha_organization_pk) seen.add(a.sakha_organization_pk);
            }
            return seen.size;
        },

        // Only offer the filter when there are ≥2 distinct Sakhas among the
        // rows (hide it entirely for non-Sakha-bearing bodies).
        get govShowSakhaFilter() {
            return this.govAssignmentDistinctSakhaCount >= 2;
        },

        // The dropdown's options: distinct Sakhas present in govAssignments,
        // but narrowed to the admin's own scoped Sakha(s) when they are not
        // NSS-wide — mirrors the isGovNssWideAdmin + admin_scope_org_pks test
        // govAssignableBodies already uses in this tab.
        get govAssignmentSakhaOptions() {
            const seen = new Map();
            for (const a of (this.govAssignments || [])) {
                if (a.sakha_organization_pk && a.sakha_name && !seen.has(a.sakha_organization_pk)) {
                    seen.set(a.sakha_organization_pk, {
                        organization_pk: a.sakha_organization_pk,
                        organization_name: a.sakha_name,
                    });
                }
            }
            let opts = [...seen.values()];
            const scopeOrgPks = this.currentUser ? this.currentUser.admin_scope_org_pks : null;
            if (!this.isGovNssWideAdmin && scopeOrgPks != null) {
                opts = opts.filter(o => scopeOrgPks.includes(o.organization_pk));
            }
            return opts.sort((x, y) =>
                (x.organization_name || "").localeCompare(y.organization_name || ""));
        },

        // A single-Sakha-scoped admin has their Sakha auto-selected AND the
        // dropdown locked (they may only ever see their own Sakha's rows).
        get govSakhaFilterLocked() {
            const scopeOrgPks = this.currentUser ? this.currentUser.admin_scope_org_pks : null;
            return !this.isGovNssWideAdmin && scopeOrgPks != null
                && this.govAssignmentSakhaOptions.length === 1;
        },

        // govAssignments narrowed by the Sakha filter (ask #3).
        get govAssignmentsFiltered() {
            if (!this.govSakhaFilter) return this.govAssignments || [];
            return (this.govAssignments || []).filter(
                a => a.sakha_organization_pk === this.govSakhaFilter);
        },

        // True when the filtered list exceeds the cap — drives "Show all N".
        get govAssignmentsHasMore() {
            return this.govAssignmentsFiltered.length > NSS.GOV_MEMBER_CAP;
        },

        // Rows actually rendered: filtered (ask #3), then capped at
        // NSS.GOV_MEMBER_CAP (ask #2) unless expanded via "Show all".
        govAssignmentsDisplayed() {
            const list = this.govAssignmentsFiltered;
            return this.govAssignmentsShowAll ? list : list.slice(0, NSS.GOV_MEMBER_CAP);
        },

        // Default the Sakha filter after a load: a single-Sakha-scoped admin
        // gets their Sakha pre-selected (and locked via govSakhaFilterLocked);
        // NSS-wide and multi-scoped admins default to "All Sakhas". Always
        // collapses the "Show all" expansion.
        _applyGovSakhaFilterDefault() {
            this.govAssignmentsShowAll = false;
            const opts = this.govAssignmentSakhaOptions;
            this.govSakhaFilter = (this.govSakhaFilterLocked && opts.length === 1)
                ? opts[0].organization_pk
                : "";
        },

        // Dropdown @change — switching Sakha starts the list collapsed again.
        onGovSakhaFilterChange() {
            this.govAssignmentsShowAll = false;
        },


        // ── Correspondence Register (Tier 6, SOL-ADMIN-009) permissions ──
        get canViewCorrespondence() {
            return this.currentUser &&
                (this.currentUser.permissions.includes("CORRESPONDENCE_VIEW") ||
                 this.currentUser.permissions.includes("CORRESPONDENCE_MANAGE"));
        },

        get canManageCorrespondence() {
            return this.currentUser &&
                this.currentUser.permissions.includes("CORRESPONDENCE_MANAGE");
        },

        // Mirrors governance.py's _SAKHA_NOMINATED_BODY_TYPES — the only
        // body type where a scope-bounded admin has a legitimate secondary
        // capability (nominate) over an NSS-wide body. Client-side only
        // for a UI label switch ("Nominate" vs "Add Assignment"); the
        // actual nomination authority is enforced server-side.
        GOV_SAKHA_NOMINATED_BODY_TYPES: ["ADVISORY_BOARD"],

        // Bug fix: a Sakha-scoped admin was seeing (and could attempt to
        // fill) every NSS-wide/Kendra-level governance body in the
        // Assignments tab's body picker — Kendra Governing Body, the
        // central Mahila Parichalana Mandali, etc. — because that picker
        // used the unfiltered govBodiesAll. The backend write guards
        // (_require_scope_for_org_or_nss_wide / _require_nominating_sakha_scope
        // in governance.py) already correctly reject those actions; this
        // is a frontend-only visibility narrowing so the picker only ever
        // offers what the admin could actually act on:
        //   - NSS-wide/global admin: every body, unfiltered.
        //   - Otherwise: bodies anchored (organization_pk) within the
        //     admin's own scope subtree (admin_scope_org_pks from GET
        //     /auth/me), PLUS the small allowlist of NSS-wide body types
        //     a scope-bounded admin may still nominate into (currently
        //     just Advisory Board) — those are flagged isNominationBody
        //     so the template can render "Nominate" instead of "Add
        //     Assignment" for them.
        //
        // isGovNssWideAdmin: same "is this admin global" test, exposed as its
        // own getter — used to gate NSS-wide-only governance UI (the
        // Advisory Board missing-nominations panel, and excluding the
        // Sakha-nominated MEMBER seat from a direct-assignment dropdown).
        get isGovNssWideAdmin() {
            // KENDRA scope is NSS-wide-equivalent (owner-confirmed 2026-10-22:
            // "NSS = KENDRA = NSS_WIDE") — mirrors
            // api/services/rbac_service.py::UserContext.is_nss_wide().
            return !!(this.currentUser && (
                this.isNssAdmin ||
                (this.currentUser.scopes || []).some(s => s.scope_level === "NSS-WIDE" || s.scope_level === "KENDRA")
            ));
        },
        get govAssignableBodies() {
            const isGlobal = this.isGovNssWideAdmin;
            const scopeOrgPks = this.currentUser ? this.currentUser.admin_scope_org_pks : null;
            return (this.govBodiesAll || []).filter(b => {
                if (isGlobal || scopeOrgPks == null) return true;
                const inScope = b.organization_pk && scopeOrgPks.includes(b.organization_pk);
                const nominable = this.GOV_SAKHA_NOMINATED_BODY_TYPES.includes(b.body_type_code);
                return inScope || nominable;
            }).map(b => ({
                ...b,
                isNominationBody: !isGlobal && !(
                    b.organization_pk && scopeOrgPks != null && scopeOrgPks.includes(b.organization_pk)
                ) && this.GOV_SAKHA_NOMINATED_BODY_TYPES.includes(b.body_type_code),
            }));
        },

        canEditOrg(org) {
            if (!this.currentUser) return false;
            // ORGANIZATION_MANAGE = can edit any org (NSS Admin, Kendra Admin)
            if (this.currentUser.permissions.includes("ORGANIZATION_MANAGE")) return true;
            // Scoped admins: can edit orgs within their own scope SUBTREE
            // (their org + descendants) — matches the backend's subtree-aware
            // org_in_scope()/_require_org_in_scope(), not just an exact match
            // on their own org row (that was the pre-existing gap: a Zilla/
            // Anchalika admin could edit their own org but the button never
            // even showed for their child Sakhas).
            if (!this.currentUser.scopes) return false;
            return this.currentUser.scopes.some(
                s => s.organization_pk && this.isOrgOrDescendantOf(org, s.organization_pk)
            );
        },

        // Walks org's parent chain (via the flat this.organizations list,
        // loaded in full at init) to check whether ancestorPk is org itself
        // or one of its ancestors. Mirrors the backend's recursive subtree
        // CTE (api/services/rbac_service.py::actor_scope_org_pks) client-side.
        isOrgOrDescendantOf(org, ancestorPk) {
            let current = org;
            const seen = new Set();
            while (current) {
                if (current.organization_pk === ancestorPk) return true;
                if (!current.parent_organization_pk || seen.has(current.organization_pk)) return false;
                seen.add(current.organization_pk);
                current = this.organizations.find(o => o.organization_pk === current.parent_organization_pk);
            }
            return false;
        },

        // Roles offered in the Assign-Role modal, minus roles that would be a
        // guaranteed duplicate for this target user. Every role now has a
        // single fixed scope_level (enforced server-side too — see
        // assign_role() in api/routers/admin.py), so a SYSTEM role
        // (NSS_ERP_ADMIN/AUDITOR/REPORT_VIEWER — always NSS-WIDE, no org) can
        // only ever be held once; offering it again would just 409. An
        // ORGANIZATIONAL role (e.g. SAKHA_ADMIN) stays offered even if
        // already held, since the same role at a different org scope is a
        // legitimate, frozen-by-design assignment (SOL-ADMIN-004 §8.7).
        get assignableRoles() {
            const heldSystemRoleCodes = new Set(
                (this.roleTargetRoles || [])
                    .filter(r => r.is_active)
                    .map(r => r.role_code)
            );
            return this.availableRoles.filter(role =>
                role.role_class !== "SYSTEM" || !heldSystemRoleCodes.has(role.role_code)
            );
        },

        // Orgs filtered by the selected scope level in role assignment modal
        get scopeFilteredOrgs() {
            const level = this.roleForm.scope_level;
            if (!level || level === "NSS-WIDE") return [];
            // KENDRA_MAHILA_SANGHA is not its own organization_type_code —
            // it's the single MAHILA_SANGHA row whose parent is KENDRA
            // (see api/routers/admin.py's _ALLOWED_PARENT_TYPES comment).
            if (level === "KENDRA_MAHILA_SANGHA") {
                const kendra = this.organizations.find(o => o.organization_type_code === "KENDRA");
                return this.organizations.filter(
                    o => o.organization_type_code === "MAHILA_SANGHA" &&
                         kendra && o.parent_organization_pk === kendra.organization_pk
                );
            }
            // Map scope levels to org type codes
            const scopeToType = {
                KENDRA: ["KENDRA"],
                ZILLA: ["ZILLA_SANGHA"],
                ANCHALIKA: ["ANCHALIKA_SANGHA"],
                SAKHA: ["SAKHA_SANGHA"],
                PATHA_CHAKRA: ["PATHA_CHAKRA"],
            };
            const allowedTypes = scopeToType[level];
            if (!allowedTypes) return this.organizations;
            return this.organizations.filter(
                o => allowedTypes.includes(o.organization_type_code)
            );
        },

        // ── Initialization ─────────────────────────────────────

        async init() {
            const ok = await NSSLayout.initAuth(this);
            if (!ok) return;

            // ── Authorization guard: admin permissions required ────
            // Redirect non-admin users to the dashboard.
            const perms = this.currentUser.permissions || [];
            const hasAdminAccess = perms.some(p =>
                p.startsWith("ADMIN_") || p === "MEMBERSHIP_APPROVE"
            );
            if (!hasAdminAccess) {
                window.location.href = "/dashboard";
                return;
            }

            // Load reference data in parallel
            await Promise.all([
                this.fetchUsers(),
                this.fetchAvailableRoles(),
                this.fetchOrganizations(),
                this.fetchMembershipTypes(),
                this.loadOrgTypes(),
                this.loadClaimsPendingCount(),
                this.loadClaimSakhas(),
                this.loadGenders(),
                this.loadMaritalStatuses(),
                this.loadBloodGroups(),
                this.loadRelationships(),
                this.loadSakhaScope(),
                this.loadGeoEntriesPendingCount(),
            ]);

            // Handle hash-based tab navigation (e.g. /admin#claims, /admin#detail/uuid).
            // activeTab itself was already resolved synchronously above
            // (before Alpine's first render), so this only fires each
            // tab's lazy data loader — mirroring what its nav item's
            // @click handler does — since landing here via a refreshed
            // or shared URL bypassed that click. Without this, e.g. the
            // Organization Hierarchy tab rendered permanently empty on
            // refresh because loadOrgHierarchy() never ran.
            const hash = window.location.hash.replace("#", "");
            if (hash.startsWith("detail/")) {
                const userPk = hash.substring("detail/".length);
                if (userPk) this.viewUser(userPk);
            } else if (hash.startsWith("orgDashboard/")) {
                const orgPk = hash.substring("orgDashboard/".length);
                if (orgPk) this.openOrgDashboard(orgPk);
            } else if (hash === "orgDashboard") {
                // Bare #orgDashboard names no org. Land on the top tier this
                // admin's scope covers (dashboardLevels is hierarchy-ordered),
                // falling back to their own scope org, so the tab never
                // renders as a blank "No organization specified."
                const firstLevel = this.dashboardLevels[0];
                const orgPk = firstLevel
                    ? firstLevel.orgs[0].organization_pk
                    : this.myOrgDashboardPk;
                if (orgPk) this.openOrgDashboard(orgPk);
            } else if (hash) {
                const tabLoaders = {
                    organizations: () => this.loadOrganizations(),
                    createOrg: () => this.loadCreateOrgData(),
                    claims: () => { this.loadClaims(); this.loadClaimsPendingCount(); },
                    personDir: () => this.loadPersonDirectory(),
                    memberDir: () => this.loadMemberDirectory(),
                    orgHierarchy: () => this.loadOrgHierarchy(),
                    assignSakha: () => this.loadAssignSakhaData(),
                    refData: () => this.loadReferenceData(),
                    geography: () => this.loadGeography(),
                    geoApprovals: () => this.loadGeoEntries(),
                    sysSettings: () => this.loadSystemSettings(),
                    govCatalog: () => { if (this.isGovNssWideAdmin) this.loadGovCatalog(); },
                    govBodies: () => { if (this.canViewGovernance) this.loadGovBodies(); },
                    govAssignments: () => { if (this.canViewGovernance) this.loadGovAssignments(); },
                    govElections: () => { if (this.canViewGovernance) this.loadGovElections(); },
                    attPujas: () => { if (this.canViewAttendance) this.loadAttPujas(); },
                    attReviews: () => { if (this.canViewAttendance) this.loadAttReviews(); },
                    attWatchList: () => { if (this.canViewAttendance) { this.loadAttWatchList(); this.loadAttOrgStats(); } },
                    credentials: () => this.loadCredentials(),
                    correspondence: () => this.loadCorrespondence(),
                };
                if (tabLoaders[hash]) tabLoaders[hash]();
            }

            // Sync tab state to URL hash on every switch
            this.$watch("activeTab", (tab) => {
                // detail/orgDashboard hashes are managed by viewUser()/
                // openOrgDashboard() to include the target PK
                if (tab !== "detail" && tab !== "orgDashboard") {
                    history.replaceState(null, "", `#${tab}`);
                }
            });
        },

        // ── Users list ─────────────────────────────────────────

        /**
         * Generic client-side sort state, keyed by list name.
         *
         * Used by the small fully-loaded lists — Reference Data values and
         * documents, Geography cities and postal codes. Each of those holds
         * its entire dataset in the browser, so reordering on screen
         * reorders the whole list and no request is needed. The named
         * per-list handlers above exist only where the list is paginated or
         * capped and the sort therefore has to happen in SQL.
         */
        clientSort: {},

        sortList(list, key) {
            const current = this.clientSort[list] || { key: "", dir: NSS.SORT_DIR_ASC };
            this.clientSort = {
                ...this.clientSort,
                [list]: NSS.toggleSort(current.key, current.dir, key),
            };
        },

        clientSortKey(list) {
            return (this.clientSort[list] || {}).key || "";
        },

        clientSortDir(list) {
            return (this.clientSort[list] || {}).dir || NSS.SORT_DIR_ASC;
        },

        sortedList(list, rows, accessor) {
            const state = this.clientSort[list];
            if (!state || !state.key) return rows || [];
            return NSS.sortRows(rows || [], state.key, state.dir, accessor);
        },

        /**
         * Value accessor for person rows.
         *
         * Needed because the Name column is not a field — the table
         * composes it from first/middle/last. Sorting on a non-existent
         * "person_name" property would compare undefined against
         * undefined and silently leave the rows in place, which looks
         * like a broken header rather than a missing accessor.
         */
        _personRowValue(row, key) {
            if (key === "person_name") {
                return [row.first_name, row.middle_name, row.last_name]
                    .filter(Boolean)
                    .join(" ");
            }
            return row ? row[key] : undefined;
        },

        sortPersonSearch(key) {
            const next = NSS.toggleSort(this.personSearchSortBy, this.personSearchSortDir, key);
            this.personSearchSortBy = next.key;
            this.personSearchSortDir = next.dir;
        },

        sortedPersonSearchResults() {
            if (!this.personSearchSortBy) return this.personSearchResults;
            return NSS.sortRows(
                this.personSearchResults, this.personSearchSortBy,
                this.personSearchSortDir, this._personRowValue,
            );
        },

        sortSsPersonSearch(key) {
            const next = NSS.toggleSort(this.ssPersonSearchSortBy, this.ssPersonSearchSortDir, key);
            this.ssPersonSearchSortBy = next.key;
            this.ssPersonSearchSortDir = next.dir;
        },

        sortedSsPersonSearchResults() {
            if (!this.ssPersonSearchSortBy) return this.ssPersonSearchResults;
            return NSS.sortRows(
                this.ssPersonSearchResults, this.ssPersonSearchSortBy,
                this.ssPersonSearchSortDir, this._personRowValue,
            );
        },

        /**
         * Header click on the Role Assignments table (client-side).
         */
        sortUserRoles(key) {
            const next = NSS.toggleSort(this.rolesSortBy, this.rolesSortDir, key);
            this.rolesSortBy = next.key;
            this.rolesSortDir = next.dir;
        },

        /**
         * Role rows in the currently requested order.
         *
         * Returns the untouched array when no column is selected, so the
         * order the API sent is preserved until the user asks otherwise.
         */
        sortedUserRoles() {
            const rows = this.selectedUser?.roles || [];
            if (!this.rolesSortBy) return rows;
            return NSS.sortRows(rows, this.rolesSortBy, this.rolesSortDir);
        },

        /**
         * Header click on the User Accounts table.
         *
         * Resets to page 1 deliberately: re-sorting while sitting on
         * page 3 would leave the user looking at rows 41-60 of a brand
         * new ordering, which reads as random data.
         */
        sortUsers(key) {
            const next = NSS.toggleSort(this.usersSortBy, this.usersSortDir, key);
            this.usersSortBy = next.key;
            this.usersSortDir = next.dir;
            this.usersPage = 1;
            this.fetchUsers();
        },

        async fetchUsers() {
            this.usersLoading = true;
            this.usersError = "";

            try {
                const params = new URLSearchParams({
                    page: this.usersPage,
                    page_size: this.usersPageSize,
                });
                if (this.usersSearch.trim()) params.set("search", this.usersSearch.trim());
                if (this.usersStatusFilter) params.set("account_status", this.usersStatusFilter);
                if (this.usersSortBy) {
                    params.set("sort_by", this.usersSortBy);
                    params.set("sort_dir", this.usersSortDir);
                }

                const res = await NSSAuth.apiFetch(`/api/v1/admin/users?${params}`);
                if (!res.ok) {
                    if (res.status === 403) {
                        this.usersError = "You do not have permission to view users.";
                        return;
                    }
                    throw new Error(await NSS.extractError(res));
                }
                const data = await res.json();
                this.users = data.users;
                this.usersTotal = data.total;
            } catch (err) {
                this.usersError = err.message || "Failed to load users.";
            } finally {
                this.usersLoading = false;
            }
        },

        searchUsers() {
            this.usersPage = 1;
            this.fetchUsers();
        },

        goToPage(page) {
            if (page < 1 || page > this.totalPages) return;
            this.usersPage = page;
            this.fetchUsers();
        },

        // ── User detail ────────────────────────────────────────

        async viewUser(userAccountPk) {
            this.activeTab = "detail";
            history.replaceState(null, "", `#detail/${userAccountPk}`);
            this.detailLoading = true;
            this.detailError = "";
            this.selectedUser = null;

            try {
                const res = await NSSAuth.apiFetch(`/api/v1/admin/users/${userAccountPk}`);
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.selectedUser = await res.json();
                this.loadProfileEdit(this.selectedUser.person_pk);
            } catch (err) {
                this.detailError = err.message || "Failed to load user detail.";
            } finally {
                this.detailLoading = false;
            }
        },

        backToList() {
            this.activeTab = "users";
            this.selectedUser = null;
            this.fetchUsers();
        },

        // ── Create user ────────────────────────────────────────

        async searchPersons() {
            const q = this.personSearchQuery.trim();
            if (q.length < 2) return;
            this.personSearchLoading = true;
            this.personSearchResults = [];
            this.personSearchDone = false;

            try {
                const res = await NSSAuth.apiFetch(`/api/v1/person/search?q=${encodeURIComponent(q)}`);
                if (res.ok) {
                    const data = await res.json();
                    this.personSearchResults = data.persons;
                    this.personSearchTotal = data.total;
                }
            } catch (_) {}
            this.personSearchLoading = false;
            this.personSearchDone = true;
        },

        selectPerson(p) {
            this.createForm.person_pk = p.person_pk;
            this.selectedPersonDisplay = {
                person_pk: p.person_pk,
                person_id: p.person_id,
                person_name: p.person_name || [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" "),
                mobile_number: p.mobile_number,
                email: p.email,
                has_account: false,
            };
            this.showNewPersonForm = false;
            // Pre-fill Step 2's Sakha field immediately (scoped admins get
            // it auto-selected/locked) rather than waiting for the operator
            // to touch anything.
            this.applySakhaAutoSelect("createForm");

            // Check if person already has a user account. Keyed on
            // person_pk via a dedicated endpoint — GET /admin/users?search=
            // only matches sangha_sevi_id/first_name/last_name, so passing
            // person_id there (the old approach) never matched anything.
            NSSAuth.apiFetch(`/api/v1/admin/users/check-account/${p.person_pk}`)
                .then(res => res.ok ? res.json() : null)
                .then(data => {
                    if (data && data.has_account) {
                        this.selectedPersonDisplay.has_account = true;
                        this.selectedPersonDisplay.has_deleted_account = data.is_active === false;
                    }
                })
                .catch(() => {});
        },

        clearSelectedPerson() {
            this.createForm.person_pk = "";
            this.selectedPersonDisplay = {};
        },

        async createNewPerson() {
            this.createError = "";
            this.newPersonLoading = true;

            try {
                const f = this.newPersonForm;

                // Validate mandatory fields
                if (!f.first_name.trim()) { this.createError = "First name is required."; return; }
                if (!f.last_name.trim()) { this.createError = "Last name is required."; return; }
                if (!f.date_of_birth) { this.createError = "Date of birth is required."; return; }
                if (!f.gender_master_data_pk) { this.createError = "Gender is required."; return; }

                // Country-wise mobile + email format — MBR-CONTACT-01/02.
                const npMobileErr = NSS.validateMobile(f.country_phone_code.trim(), f.mobile_number.trim());
                if (npMobileErr) { this.createError = npMobileErr; return; }
                const npEmailErr = NSS.validateEmail(f.email.trim());
                if (npEmailErr) { this.createError = npEmailErr; return; }

                const payload = {
                    first_name: f.first_name.trim(),
                    last_name: f.last_name.trim(),
                    date_of_birth: f.date_of_birth,
                    gender_master_data_pk: f.gender_master_data_pk,
                    password: crypto.randomUUID().slice(0, 12) + "Ax1!",  // Random throwaway — overwritten by createUser
                };
                if (f.middle_name.trim()) payload.middle_name = f.middle_name.trim();
                if (f.country_phone_code.trim()) payload.country_phone_code = f.country_phone_code.trim();
                if (f.mobile_number.trim()) payload.mobile_number = f.mobile_number.trim();
                if (f.email.trim()) payload.email = f.email.trim();

                // Use the registration endpoint to create person (admin bypass)
                const res = await NSSAuth.apiFetch("/api/v1/admin/persons", {
                    method: "POST",
                    body: JSON.stringify(payload),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.createError = NSS.errorMessage(data, res.status);
                    return;
                }

                const data = await res.json();
                this.selectPerson({
                    person_pk: data.person_pk,
                    person_id: data.person_id,
                    person_name: data.person_name,
                    mobile_number: f.mobile_number.trim(),
                    email: f.email.trim(),
                    has_account: false,
                });
                this.showNewPersonForm = false;
                this.newPersonForm = {
                    first_name: "", middle_name: "", last_name: "",
                    date_of_birth: "", gender_master_data_pk: "",
                    country_phone_code: NSS.DEFAULT_COUNTRY_CODE,
                    mobile_number: "", email: "",
                };
                this.contactCheck = { mobile: null, email: null };
            } catch (err) {
                this.createError = err.message || "Failed to create person.";
            } finally {
                this.newPersonLoading = false;
            }
        },

        // Live, advisory duplicate-contact lookup for the new-person form.
        // Warns inline when the entered mobile/email already belongs to an
        // active person; the authoritative 409 still fires on submit.
        async checkNewPersonContact() {
            const f = this.newPersonForm;
            const mobile = (f.mobile_number || "").trim();
            const email = (f.email || "").trim();
            if (!mobile && !email) {
                this.contactCheck = { mobile: null, email: null };
                return;
            }
            const params = new URLSearchParams();
            if (mobile) {
                params.set("mobile_number", mobile);
                params.set("country_phone_code", (f.country_phone_code || "").trim());
            }
            if (email) params.set("email", email);
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/persons/check-contact?${params.toString()}`
                );
                if (!res.ok) { this.contactCheck = { mobile: null, email: null }; return; }
                const data = await res.json();
                this.contactCheck = {
                    mobile: data?.mobile_conflict || null,
                    email: data?.email_conflict || null,
                };
            } catch (e) {
                this.contactCheck = { mobile: null, email: null };
            }
        },

        // ── Create Person tab, Step 2: Sangha Sevi ──────────────
        // Its own step against POST /admin/sangha-sevi (person_pk mandatory,
        // no account) — mirrors the standalone Create Sangha Sevi tab, but
        // sequenced right after Person so the operator isn't forced into a
        // separate tab. Step 3 (Account Credentials) follows once this step
        // resolves, whether by creating one or skipping.
        // Shared by createSanghaSeviForNewPerson() and createSanghaSevi() —
        // adds the credential_* fields to a Sangha Sevi creation payload.
        // The operator is never asked for an issue date or membership year:
        // the server resolves the issue date itself (a Parichaya Patra on the
        // governing Dola Purnima, an Anumati Patra on the day of application —
        // SOL-ARCH-013 FC-DECISION-01). Only the legacy number is sent, and
        // only when the operator checked "already has one" and typed it in.
        _credentialPayloadFields(form) {
            const fields = {};
            if (form.credential_is_legacy) {
                const num = String(form.credential_document_number || "").trim();
                if (num) fields.credential_document_number = num;
            }
            return fields;
        },

        async createSanghaSeviForNewPerson() {
            this.createError = "";
            this.createSuccess = "";
            this.createSSLoading = true;
            try {
                const f = this.createForm;
                const payload = {
                    person_pk: f.person_pk,
                    membership_type_pk: f.membership_type_pk,
                    organization_pk: f.organization_pk,
                    joining_date: f.joining_date,
                    ...this._credentialPayloadFields(f),
                };
                const num = String(f.local_sakha_number || "").trim();
                if (num) payload.local_sakha_erp_id = num;

                const res = await NSSAuth.apiFetch("/api/v1/admin/sangha-sevi", {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.createError = NSS.errorMessage(data, res.status);
                    return;
                }
                const data = await res.json();
                this.createForm.sangha_sevi_pk = data.sangha_sevi_pk;
                this.createSuccess = `Sangha Sevi created — ID: ${data.sangha_sevi_id || data.sangha_sevi_pk}. `
                    + `${data.credential_type === "ANUMATI_PATRA" ? "Anumati Patra" : "Parichaya Patra"} issued: ${data.credential_document_number}.`;
            } catch (err) {
                this.createError = err.message || "Failed to create Sangha Sevi.";
            } finally {
                this.createSSLoading = false;
            }
        },

        skipCreateSanghaSevi() {
            this.createForm.sangha_sevi_skipped = true;
        },

        async createUser() {
            this.createError = "";
            this.createSuccess = "";
            this.createLoading = true;

            try {
                const payload = {
                    person_pk: this.createForm.person_pk,
                    password: this.createForm.password,
                    force_password_change: this.createForm.force_password_change,
                };

                const res = await NSSAuth.apiFetch("/api/v1/admin/users", {
                    method: "POST",
                    body: JSON.stringify(payload),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.createError = NSS.errorMessage(data, res.status);
                    return;
                }

                const newUser = await res.json();
                this.createSuccess = `User account created for ${newUser.person_name || newUser.user_account_pk}.`;

                // Reset form
                this.createForm = {
                    person_pk: "", password: "", force_password_change: true,
                    sangha_sevi_pk: "", sangha_sevi_skipped: false,
                    membership_type_pk: "", organization_pk: "",
                    joining_date: "", local_sakha_number: "",
                    credential_is_legacy: false, credential_document_number: "",
                };
                this.selectedPersonDisplay = {};
                this.personSearchResults = [];
                this.personSearchQuery = "";
                this.personSearchDone = false;
                this.applySakhaAutoSelect("createForm");

                this.fetchUsers();
            } catch (err) {
                this.createError = err.message || "Failed to create user.";
            } finally {
                this.createLoading = false;
            }
        },

        // ── Create Sangha Sevi ────────────────────────────────

        async searchPersonsForSS() {
            const q = this.ssPersonSearchQuery.trim();
            if (q.length < 2) return;
            this.ssPersonSearchLoading = true;
            this.ssPersonSearchResults = [];
            this.ssPersonSearchDone = false;

            try {
                const res = await NSSAuth.apiFetch(`/api/v1/person/search?q=${encodeURIComponent(q)}`);
                if (res.ok) {
                    const data = await res.json();
                    const persons = data.persons;
                    this.ssPersonSearchResults = persons;
                    this.ssPersonSearchTotal = data.total;

                    // Batch-check which persons already have a Sangha Sevi record
                    if (persons.length > 0) {
                        const pks = persons.map(p => p.person_pk);
                        try {
                            const checkRes = await NSSAuth.apiFetch("/api/v1/admin/sangha-sevi/check-batch", {
                                method: "POST",
                                body: JSON.stringify({ person_pks: pks }),
                            });
                            if (checkRes.ok) {
                                const ssMap = await checkRes.json();
                                this.ssPersonSearchResults = persons.map(p => {
                                    const info = ssMap[p.person_pk] || {};
                                    return {
                                        ...p,
                                        _already_ss: !!info.sangha_sevi_id,
                                        _existing_ss_id: info.sangha_sevi_id || null,
                                        _pending_claim: !!info.pending_claim_pk,
                                        _pending_claim_pk: info.pending_claim_pk || null,
                                        _pending_claim_org: info.pending_claim_org || null,
                                    };
                                });
                            }
                        } catch (_) {}
                    }
                }
            } catch (_) {}
            this.ssPersonSearchLoading = false;
            this.ssPersonSearchDone = true;
        },

        selectPersonForSS(p) {
            // Block selection if already flagged as existing SS from batch check
            if (p._already_ss) {
                this.ssError = `This person is already a Sangha Sevi (ID: ${p._existing_ss_id}). Cannot create another.`;
                return;
            }
            // Block selection if a pending registration claim exists
            if (p._pending_claim) {
                this.ssError = `This person has a pending registration claim. Approve or reject it first.`;
                return;
            }

            this.ssForm.person_pk = p.person_pk;
            this.ssSelectedPerson = {
                person_pk: p.person_pk,
                person_id: p.person_id,
                person_name: p.person_name || [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" "),
            };
            this.ssError = "";

            // Check if this person already has a Sangha Sevi record
            NSSAuth.apiFetch(`/api/v1/admin/sangha-sevi/check/${p.person_pk}`)
                .then(res => res.ok ? res.json() : null)
                .then(data => {
                    if (data && data.has_sangha_sevi) {
                        this.ssSelectedPerson.already_ss = true;
                        this.ssSelectedPerson.existing_ss_id = data.sangha_sevi_id;
                        this.ssError = `This person is already a Sangha Sevi (ID: ${data.sangha_sevi_id}). Cannot create another.`;
                    }
                })
                .catch(() => {});
        },

        // Fetch the caller's Sakha selection mode for member-attach forms.
        // mode="locked" → single eligible Sakha, auto-selected + dropdown
        // disabled; mode="choose" → NSS-wide or multi-Sakha admin picks.
        async loadSakhaScope() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/admin/sakha-scope-options");
                if (!res.ok) return;
                const data = await res.json();
                this.sakhaScope = {
                    mode: data.mode || "choose",
                    auto_select_pk: data.auto_select_pk || null,
                    sakhas: data.sakhas || [],
                };
                this.applySakhaAutoSelect();
            } catch (_) { /* non-fatal: dropdown stays in choose mode */ }
        },

        // Fill the locked Sakha into a member-attach form if nothing is
        // chosen yet. `formKey` names the reactive form ("ssForm" by
        // default, or "createForm" for the bundled Create-User+SS flow —
        // both use the same organization_pk field name).
        applySakhaAutoSelect(formKey = "ssForm") {
            const form = this[formKey];
            if (this.sakhaScope.mode === "locked" && this.sakhaScope.auto_select_pk
                && !form.organization_pk) {
                form.organization_pk = this.sakhaScope.auto_select_pk;
            }
        },

        async createSanghaSevi() {
            this.ssError = "";
            this.ssSuccess = "";
            this.ssLoading = true;

            try {
                const payload = {
                    person_pk: this.ssForm.person_pk,
                    membership_type_pk: this.ssForm.membership_type_pk,
                    organization_pk: this.ssForm.organization_pk,
                    joining_date: this.ssForm.joining_date,
                    ...this._credentialPayloadFields(this.ssForm),
                };
                // Send raw local number — backend composes <short_code><number>
                const num = String(this.ssForm.local_sakha_number || "").trim();
                if (num) {
                    payload.local_sakha_erp_id = num;
                }

                // Optional bundled login-account creation (requires the
                // caller to hold ADMIN_USER_MANAGE — the backend enforces it
                // and returns a clear 403 otherwise).
                if (this.ssForm.create_user_account) {
                    payload.create_user_account = true;
                    payload.password = this.ssForm.password;
                    payload.force_password_change = this.ssForm.force_password_change;
                }

                const res = await NSSAuth.apiFetch("/api/v1/admin/sangha-sevi", {
                    method: "POST",
                    body: JSON.stringify(payload),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.ssError = NSS.errorMessage(data, res.status);
                    return;
                }

                const data = await res.json();
                const credentialNote = `${data.credential_type === "ANUMATI_PATRA" ? "Anumati Patra" : "Parichaya Patra"} issued: ${data.credential_document_number}.`;
                this.ssSuccess = data.user_account_pk
                    ? `Sangha Sevi created — ID: ${data.sangha_sevi_id || data.sangha_sevi_pk}. Login account created (login with the Sangha Sevi ID). ${credentialNote}`
                    : `Sangha Sevi created — ID: ${data.sangha_sevi_id || data.sangha_sevi_pk}. ${credentialNote}`;

                // Reset form
                this.ssForm = {
                    person_pk: "", membership_type_pk: "", organization_pk: "",
                    joining_date: "", local_sakha_number: "",
                    credential_is_legacy: false, credential_document_number: "",
                    create_user_account: false, password: "", force_password_change: true,
                };
                this.ssSelectedPerson = {};
                this.ssPersonSearchResults = [];
                this.ssPersonSearchQuery = "";
                this.ssPersonSearchDone = false;
                this.applySakhaAutoSelect();
            } catch (err) {
                this.ssError = err.message || "Failed to create Sangha Sevi.";
            } finally {
                this.ssLoading = false;
            }
        },

        // ── Reset password modal ───────────────────────────────

        // ── Membership-change entry points (MBR-048/MBR-049) ────
        // Sakha transfer and Darshak-at-another-Sangha are member
        // self-service actions (filed from the member's own dashboard);
        // these Member-Directory buttons stay as a discoverability notice
        // pointing an admin to where the request gets filed and where it
        // gets reviewed, rather than posting on the member's behalf.
        requestSakhaTransfer(member) {
            const name = member ? (this.mdMemberName(member) || member.sangha_sevi_id) : "this member";
            NSSDialog.alert(
                `Sakha transfer moves ${name}'s affiliation to a receiving Sakha, subject to that Sakha's release and the destination Sakha's acceptance. The member files this themself from their dashboard (Membership tab → Request Sakha Transfer); review it here under "Sakha Transfer / Darshak".`,
                "Sakha Transfer"
            );
        },

        applyDarshak(member) {
            const name = member ? (this.mdMemberName(member) || member.sangha_sevi_id) : "this member";
            NSSDialog.alert(
                `A Darshak attends another Sangha without transferring membership — ${name} would retain their base Sakha and Local Sakha ERP ID. The member files this themself from their dashboard (Membership tab → Apply for Darshak); review it here under "Sakha Transfer / Darshak".`,
                "Apply for Darshak"
            );
        },

        openResetModal(user) {
            this.resetTargetPk = user.user_account_pk;
            this.resetTargetName = user.sangha_sevi_id || user.person_name || "User";
            this.resetForm = { new_password: "", force_password_change: true };
            this.resetError = "";
            this.resetSuccess = "";
            this.showResetModal = true;
        },

        async submitResetPassword() {
            this.resetError = "";
            this.resetSuccess = "";
            this.resetLoading = true;

            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/users/${this.resetTargetPk}/reset-password`,
                    {
                        method: "POST",
                        body: JSON.stringify(this.resetForm),
                    }
                );

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.resetError = NSS.errorMessage(data, res.status);
                    return;
                }

                this.resetSuccess = "Password reset successfully.";
                setTimeout(() => { this.showResetModal = false; }, 1200);
            } catch (err) {
                this.resetError = err.message || "Failed to reset password.";
            } finally {
                this.resetLoading = false;
            }
        },

        // ── Create Account picker ──────────────────────────────
        // A Sangha Sevi can be created without ever getting a login (the
        // Create Sangha Sevi flow's account step is optional, and a
        // standalone SS can be recorded from a legacy paper register). This
        // finds those members and lets an admin provision the login they're
        // missing, without going through the full "new person" wizard.

        openCreateAccountModal() {
            this.cazSearch = "";
            this.cazMembers = [];
            this.cazError = "";
            this.cazSelected = null;
            this.cazForm = { password: "", force_password_change: true };
            this.cazSubmitError = "";
            this.showCreateAccountModal = true;
            this.searchAccountlessMembers();
        },

        async searchAccountlessMembers() {
            this.cazLoading = true;
            this.cazError = "";
            try {
                const params = new URLSearchParams({ page: 1, page_size: 25 });
                if (this.cazSearch.trim()) params.set("search", this.cazSearch.trim());

                const res = await NSSAuth.apiFetch(`/api/v1/admin/sangha-sevi/without-account?${params}`);
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                this.cazMembers = data.members;
            } catch (err) {
                this.cazError = err.message || "Failed to load Sangha Sevis without an account.";
            } finally {
                this.cazLoading = false;
            }
        },

        cazSelectMember(m) {
            this.cazSelected = m;
            this.cazForm = { password: "", force_password_change: true };
            this.cazSubmitError = "";
        },

        cazBackToPicker() {
            this.cazSelected = null;
            this.cazSubmitError = "";
        },

        async submitCreateAccountForMember() {
            if (!this.cazSelected) return;
            this.cazSubmitError = "";
            this.cazSubmitLoading = true;

            try {
                const res = await NSSAuth.apiFetch("/api/v1/admin/users", {
                    method: "POST",
                    body: JSON.stringify({
                        person_pk: this.cazSelected.person_pk,
                        password: this.cazForm.password,
                        force_password_change: this.cazForm.force_password_change,
                    }),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.cazSubmitError = NSS.errorMessage(data, res.status);
                    return;
                }

                this.showCreateAccountModal = false;
                this.showToast(
                    `${this.cazSelected.has_deleted_account ? "Access restored" : "Account created"} for ${this.cazSelected.sangha_sevi_id}.`
                );
                this.fetchUsers();
            } catch (err) {
                this.cazSubmitError = err.message || "Failed to create account.";
            } finally {
                this.cazSubmitLoading = false;
            }
        },

        // ── Status change modal ────────────────────────────────

        // Single-purpose status actions (Activate / Reactivate / Lock),
        // replacing the old generic "Change Status" modal — one direct
        // action per button instead of a dropdown + confirm step.
        async setUserStatus(userAccountPk, newStatus, displayName, verb) {
            if (userAccountPk === this.currentUser?.user_account_pk) {
                await NSSDialog.alert("You cannot change your own account status.");
                return;
            }
            const ok = await NSSDialog.confirm(
                `${verb} account for "${displayName}"?`,
                { title: `${verb} Account`, confirmText: verb }
            );
            if (!ok) return;

            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/users/${userAccountPk}/status`,
                    { method: "PATCH", body: JSON.stringify({ account_status: newStatus }) }
                );
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    await NSSDialog.alert(NSS.errorMessage(data, res.status));
                    return;
                }
                this.showToast(`Account status changed to ${newStatus}.`);
                this.fetchUsers();
                if (this.selectedUser && this.selectedUser.user_account_pk === userAccountPk) {
                    this.viewUser(userAccountPk);
                }
            } catch (err) {
                await NSSDialog.alert(err.message || "Failed to update status.");
            }
        },

        // A soft-deleted (INACTIVE) account can't be flipped back to ACTIVE
        // via PATCH /status — delete_user() sets is_active=FALSE, and
        // update_status() only ever operates on is_active=TRUE rows (a
        // deliberate guard, not a bug: an INACTIVE row's password/lockout
        // state is stale and shouldn't just be un-paused). Reactivating goes
        // through the same POST /users path a fresh account creation would,
        // which detects the existing soft-deleted row by person_pk and
        // reactivates it in place with a freshly-set password instead of
        // erroring on "account already exists".
        reactivateForm: { password: "", force_password_change: true },
        reactivateError: "",
        reactivateLoading: false,

        async reactivateUser(selectedUser) {
            this.reactivateError = "";
            const pw = this.reactivateForm.password;
            if (!pw || pw.length < 8) {
                this.reactivateError = "Enter a new password (min 8 characters) to reactivate this account.";
                return;
            }
            this.reactivateLoading = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/admin/users", {
                    method: "POST",
                    body: JSON.stringify({
                        person_pk: selectedUser.person_pk,
                        password: pw,
                        force_password_change: this.reactivateForm.force_password_change,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.reactivateError = NSS.errorMessage(data, res.status);
                    return;
                }
                this.showToast("Account reactivated.");
                this.reactivateForm = { password: "", force_password_change: true };
                this.fetchUsers();
                this.viewUser(selectedUser.user_account_pk);
            } catch (err) {
                this.reactivateError = err.message || "Failed to reactivate account.";
            } finally {
                this.reactivateLoading = false;
            }
        },

        // ── Role assignment modal ──────────────────────────────

        openRoleModal(user) {
            this.roleTargetPk = user.user_account_pk;
            this.roleTargetName = user.sangha_sevi_id || user.person_name || "User";
            this.roleTargetRoles = user.roles || [];
            this.roleForm = { role_code: "", scope_level: "NSS-WIDE", organization_pk: "" };
            this.roleError = "";
            this.roleSuccess = "";
            this.showRoleModal = true;
        },

        // Each role has exactly one fixed scope_level (role_master.scope_level
        // — SOL-ADMIN-004 §8.7); the backend now rejects any other value for
        // that role, so the moment a role is picked its scope is locked to
        // that fixed value instead of staying a free, independently-set field.
        onRoleFormRoleChange() {
            const role = this.availableRoles.find(r => r.role_code === this.roleForm.role_code);
            this.roleForm.scope_level = role ? role.scope_level : "NSS-WIDE";
            this.roleForm.organization_pk = "";
        },

        async submitAssignRole() {
            this.roleError = "";
            this.roleSuccess = "";
            this.roleLoading = true;

            try {
                const body = {
                    role_code: this.roleForm.role_code,
                    scope_level: this.roleForm.scope_level,
                    organization_pk: this.roleForm.scope_level === "NSS-WIDE"
                        ? null
                        : (this.roleForm.organization_pk || null),
                };

                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/users/${this.roleTargetPk}/roles`,
                    { method: "POST", body: JSON.stringify(body) }
                );

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.roleError = NSS.errorMessage(data, res.status);
                    return;
                }

                this.roleSuccess = "Role assigned successfully.";
                setTimeout(() => { this.showRoleModal = false; }, 1200);
                // Refresh detail
                if (this.selectedUser && this.selectedUser.user_account_pk === this.roleTargetPk) {
                    this.viewUser(this.roleTargetPk);
                }
            } catch (err) {
                this.roleError = err.message || "Failed to assign role.";
            } finally {
                this.roleLoading = false;
            }
        },

        async revokeRole(userAccountPk, userRolePk) {
            if (userAccountPk === this.currentUser?.user_account_pk) {
                await NSSDialog.alert("You cannot revoke your own role — this would remove your own access.");
                return;
            }
            const ok = await NSSDialog.confirm(
                "Revoke this role assignment?",
                { title: "Revoke Role", confirmText: "Revoke", confirmClass: "btn-error" }
            );
            if (!ok) return;

            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/users/${userAccountPk}/roles/${userRolePk}`,
                    { method: "DELETE" }
                );
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    await NSSDialog.alert(data.detail || "Failed to revoke role.");
                    return;
                }
                this.showToast("Role revoked.");
                this.viewUser(userAccountPk);
            } catch (err) {
                await NSSDialog.alert(err.message || "Failed to revoke role.");
            }
        },

        // ── Delete user ───────────────────────────────────────

        async deleteUser(userAccountPk, displayName) {
            if (userAccountPk === this.currentUser?.user_account_pk) {
                await NSSDialog.alert("You cannot delete your own account.");
                return;
            }
            const ok = await NSSDialog.confirm(
                `Permanently deactivate account for "${displayName}"? This will revoke all roles and disable login.`,
                { title: "Delete User Account", confirmText: "Delete", confirmClass: "btn-error" }
            );
            if (!ok) return;

            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/users/${userAccountPk}`,
                    { method: "DELETE" }
                );
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    await NSSDialog.alert(data.detail || "Failed to delete user.");
                    return;
                }
                const data = await res.json();
                this.showToast(data.message || "User deleted.");
                // Go back to list and refresh
                if (this.activeTab === "detail") {
                    this.backToList();
                }
                this.fetchUsers();
            } catch (err) {
                await NSSDialog.alert(err.message || "Failed to delete user.");
            }
        },

        // ── Change own password ────────────────────────────────

        async changeOwnPassword() {
            this.pwError = "";
            this.pwSuccess = "";

            if (this.pwForm.new_password !== this.pwForm.confirm_password) {
                this.pwError = "Passwords do not match.";
                return;
            }

            this.pwLoading = true;

            try {
                const res = await NSSAuth.apiFetch("/api/v1/auth/change-password", {
                    method: "POST",
                    body: JSON.stringify({
                        current_password: this.pwForm.current_password,
                        new_password: this.pwForm.new_password,
                    }),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.pwError = NSS.errorMessage(data, res.status);
                    return;
                }

                this.pwSuccess = "Password changed successfully.";
                this.pwForm = { current_password: "", new_password: "", confirm_password: "" };
            } catch (err) {
                this.pwError = err.message || "Failed to change password.";
            } finally {
                this.pwLoading = false;
            }
        },

        // ── Reference data ─────────────────────────────────────

        async fetchAvailableRoles() {
            try {
                const res = await fetch("/api/v1/bootstrap/roles");
                if (res.ok) this.availableRoles = await res.json();
            } catch { /* non-critical */ }
        },

        async fetchMembershipTypes() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=MEMBERSHIP_TYPE");
                if (res.ok) this.membershipTypes = await res.json();
            } catch { /* non-critical */ }
        },

        async loadGenders() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=GENDER");
                if (res.ok) this.genders = await res.json();
            } catch { /* non-critical */ }
        },

        async loadMaritalStatuses() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=MARITAL_STATUS");
                if (res.ok) this.maritalStatuses = await res.json();
            } catch { /* non-critical */ }
        },

        async loadBloodGroups() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=BLOOD_GROUP");
                if (res.ok) this.bloodGroups = await res.json();
            } catch { /* non-critical */ }
        },

        async loadRelationships() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=RELATIONSHIP");
                if (res.ok) this.relationships = await res.json();
            } catch { /* non-critical */ }
        },

        // ── Profile Details edit (admin Detail view) ──────────

        async loadProfileEdit(personPk) {
            this.profileEdit.loading = true;
            this.profileEdit.error = null;
            this.profileEdit.editing = false;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/admin/persons/${personPk}`);
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const p = await res.json();
                this.profileEdit.form = {
                    first_name: p.first_name || "",
                    middle_name: p.middle_name || "",
                    last_name: p.last_name || "",
                    date_of_birth: p.date_of_birth || "",
                    gender_master_data_pk: p.gender_master_data_pk || "",
                    marital_status_master_data_pk: p.marital_status_master_data_pk || "",
                    blood_group_master_data_pk: p.blood_group_master_data_pk || "",
                    country_phone_code: p.country_phone_code || NSS.DEFAULT_COUNTRY_CODE,
                    mobile_number: p.mobile_number || "",
                    email: p.email || "",
                    emergency_contact_name: p.emergency_contact_name || "",
                    emergency_contact_phone: p.emergency_contact_phone || "",
                    emergency_relationship_master_data_pk: p.emergency_relationship_master_data_pk || "",
                    remarks: p.remarks || "",
                };
                this.profileEdit.reason = "";
            } catch (err) {
                this.profileEdit.error = err.message || "Failed to load profile details.";
            } finally {
                this.profileEdit.loading = false;
            }
        },

        startEditProfile() {
            this.profileEdit.editing = true;
            this.profileEdit.saveError = null;
        },

        cancelEditProfile() {
            this.profileEdit.editing = false;
            this.profileEdit.saveError = null;
            if (this.selectedUser) this.loadProfileEdit(this.selectedUser.person_pk);
        },

        async saveProfile() {
            if (!this.selectedUser) return;
            const f = this.profileEdit.form;
            if (!f.first_name || !f.first_name.trim()) {
                this.profileEdit.saveError = "First name is required.";
                return;
            }
            this.profileEdit.saving = true;
            this.profileEdit.saveError = null;
            try {
                const payload = {
                    first_name: f.first_name,
                    middle_name: f.middle_name,
                    last_name: f.last_name,
                    date_of_birth: f.date_of_birth || null,
                    gender_master_data_pk: f.gender_master_data_pk || null,
                    marital_status_master_data_pk: f.marital_status_master_data_pk || null,
                    blood_group_master_data_pk: f.blood_group_master_data_pk || null,
                    country_phone_code: f.country_phone_code,
                    mobile_number: f.mobile_number,
                    email: f.email,
                    emergency_contact_name: f.emergency_contact_name,
                    emergency_contact_phone: f.emergency_contact_phone,
                    emergency_relationship_master_data_pk: f.emergency_relationship_master_data_pk || null,
                    remarks: f.remarks,
                    reason: this.profileEdit.reason || null,
                };
                const res = await NSSAuth.apiFetch(`/api/v1/admin/persons/${this.selectedUser.person_pk}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.profileEdit.editing = false;
                // Name/contact also surface on the Account Details card and
                // the Users list — viewUser() refreshes both, and triggers
                // loadProfileEdit() itself for this card too.
                await this.viewUser(this.selectedUser.user_account_pk);
                this.fetchUsers();
                this.showToast("Profile updated.");
            } catch (err) {
                this.profileEdit.saveError = err.message || "Failed to save profile.";
            } finally {
                this.profileEdit.saving = false;
            }
        },

        async fetchOrganizations() {
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/organization/organizations?limit=${NSS.MAX_PAGE_SIZE}`);
                if (res.ok) {
                    const data = await res.json();
                    this.organizations = data.organizations || data || [];
                } else {
                    console.error("fetchOrganizations: API returned", res.status);
                }
            } catch (err) {
                console.error("fetchOrganizations: fetch error", err);
            }
        },

        // ── Organization short code management ─────────────────

        sortOrgs(key) {
            const next = NSS.toggleSort(this.orgsSortBy, this.orgsSortDir, key);
            this.orgsSortBy = next.key;
            this.orgsSortDir = next.dir;
            this.orgPage = 1;
            this.loadOrganizations();
        },

        async loadOrganizations() {
            this.orgsLoading = true;
            try {
                const params = new URLSearchParams({
                    page: this.orgPage,
                    page_size: this.orgPageSize,
                });
                if (this.orgTypeFilter) params.set("type_code", this.orgTypeFilter);
                if (this.orgSearch.trim()) params.set("search", this.orgSearch.trim());
                if (this.orgsSortBy) {
                    params.set("sort_by", this.orgsSortBy);
                    params.set("sort_dir", this.orgsSortDir);
                }

                const res = await NSSAuth.apiFetch(`/api/v1/admin/organizations?${params}`);
                if (res.ok) {
                    const data = await res.json();
                    this.orgsList = data.organizations;
                    this.orgsTotal = data.total;
                }
            } catch (err) {
                console.error("Failed to load organizations:", err);
            } finally {
                this.orgsLoading = false;
            }
        },

        startEditShortCode(org) {
            this.editingOrgPk = org.organization_pk;
            this.editingShortCode = org.short_code || "";
            this.inlineShortCodeCheck = { checking: false, conflict: null };
            this.$nextTick(() => {
                const input = this.$refs.shortCodeInput;
                if (input) input.focus();
            });
        },

        async saveShortCode(org) {
            if (this.inlineShortCodeCheck.conflict) {
                this.showToast(
                    `Short Code is already used by ${this.inlineShortCodeCheck.conflict.organization_name}.`,
                    "error"
                );
                return;
            }
            this.savingShortCode = true;
            const code = this.editingShortCode.trim().toUpperCase() || null;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/organizations/${org.organization_pk}/short-code`,
                    {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ short_code: code }),
                    }
                );
                if (res.ok) {
                    const data = await res.json();
                    org.short_code = data.short_code;
                    this.editingOrgPk = null;
                    this.inlineShortCodeCheck = { checking: false, conflict: null };
                    this.showToast(data.message);
                } else {
                    const err = await res.json().catch(() => ({}));
                    this.showToast(err.detail || "Failed to update short code.", "error");
                }
            } catch (err) {
                this.showToast("Network error. Try again.", "error");
            } finally {
                this.savingShortCode = false;
            }
        },

        // ── Organization detail editing ───────────────────────

        startEditOrgDetail(org) {
            this.editOrgDetailPk = org.organization_pk;
            this.editOrgForm = {
                organization_name: org.organization_name || "",
                address_line_1: org.address_line_1 || "",
                phone_number: org.phone_number || "",
                country_phone_code: org.country_phone_code || NSS.DEFAULT_COUNTRY_CODE,
                mobile_number: org.mobile_number || "",
                org_email: org.org_email || "",
                org_website_url: org.org_website_url || "",
                org_youtube_channel_url: org.org_youtube_channel_url || "",
                country_pk: org.country_pk || "",
                state_pk: org.state_pk || "",
                district_pk: org.district_pk || "",
                city_village_name: org.city_village_name || "",
                postal_code_value: org.postal_code || "",
            };
            // Load cascading location lookups
            this.loadLocationCountries();
            if (org.country_pk) this.loadLocationStates(org.country_pk);
            if (org.state_pk) {
                this.loadLocationDistricts(org.state_pk);
            }
            if (org.district_pk) {
                this.loadLocationCities(org.district_pk);
            }
        },

        // ── Org-edit location cascade (shared utility) ──────────────

        _editLocCascade: NSSLocation.create({
            fetchFn: (...args) => NSSAuth.apiFetch(...args),
            arrays: {
                countries: 'locationCountries',
                states: 'locationStates',
                districts: 'locationDistricts',
                cities: 'locationCities',
            },
            form: 'editOrgForm',
        }),

        async loadLocationCountries() { await this._editLocCascade.loadCountries(this); },
        async loadLocationStates(pk)   { await this._editLocCascade.loadStates(this, pk); },
        async loadLocationDistricts(pk){ await this._editLocCascade.loadDistricts(this, pk); },
        async loadLocationCities(pk)   { await this._editLocCascade.loadCities(this, pk); },
        onCountryChange()              { this._editLocCascade.onCountryChange(this); },
        onStateChange()                { this._editLocCascade.onStateChange(this); },
        onDistrictChange()             { this._editLocCascade.onDistrictChange(this); },

        // Auto-fill PIN from the city_village→postal_code mapping when an
        // existing city/village is chosen; leave blank (user types) on a
        // mapping gap or a brand-new name. Mirrors register.js.
        onEditOrgCityVillageChange() {
            const name = (this.editOrgForm.city_village_name || "").trim().toLowerCase();
            if (!name) return;
            const match = this.locationCities.find(
                cv => (cv.city_village_name || "").trim().toLowerCase() === name
            );
            if (match && match.postal_code) this.editOrgForm.postal_code_value = match.postal_code;
        },

        cancelEditOrgDetail() {
            this.editOrgDetailPk = null;
            this.editOrgForm = {};
        },

        // ── Create Organization ──────────────────────────────

        // Parent orgs: dynamic based on selected org type (hierarchy rules)
        get parentOrgs() {
            const typeCode = this.createOrgForm.organization_type_code;
            if (!typeCode) return [];

            // Hierarchy: which parent types are allowed for each org type
            // (frozen NSS Bye-Law hierarchy — see api/routers/admin.py's
            // _ALLOWED_PARENT_TYPES for the authoritative comment).
            // Note: on the Create-Org form, ANCHALIKA_SANGHA/ZILLA_SANGHA/
            // PATHA_CHAKRA (ORG-BR-100, auto-resolved) and KUMARI_SANGHA/
            // SEVAK_SANGHA (ORG-BR-101/102, Sakha-scoped dropdown) are
            // rendered via dedicated UI paths and never reach this getter
            // for their own parent selection — those entries below stay for
            // completeness/parity with the backend map, not because this
            // form dispatches through them.
            const allowedParentTypes = {
                ANCHALIKA_SANGHA: ["KENDRA"],
                ZILLA_SANGHA: ["KENDRA"],
                PATHA_CHAKRA: ["KENDRA"],
                PARIBARIK_SANGHA: ["KENDRA"],
                SAKHA_SANGHA: ["ANCHALIKA_SANGHA", "ZILLA_SANGHA"],
                SAKHA_ASANA: ["ANCHALIKA_SANGHA", "ZILLA_SANGHA"],
                KUMARI_SANGHA: ["SAKHA_SANGHA"],
                SEVAK_SANGHA: ["SAKHA_SANGHA"],
                MAHILA_SANGHA: ["KENDRA", "SAKHA_SANGHA"],
                PARIBARIK_ASANA: ["SAKHA_SANGHA"],
            };

            const allowed = allowedParentTypes[typeCode];
            if (!allowed) return [];

            return this.organizations.filter(
                o => allowed.includes(o.organization_type_code)
            );
        },

        /**
         * Organization types that are never offered when a user is
         * *selecting* or *filtering by* an organization type.
         *
         * Basis — an operational convention, NOT an enforced invariant:
         *
         *   NILACHALA_KUTIRA, SMRUTI_MANDIRA — unique singleton
         *     institutions (Eternal Abode, Puri / Nigamananda Smruti
         *     Mandir), outside the membership hierarchy by convention.
         *
         *   KUMARI_SANGHA, SEVAK_SANGHA, MAHILA_SANGHA — wing bodies
         *     that hang off a Sakha Sangha (see the parent-type map in
         *     `parentOrgs`); membership is conventionally held at the
         *     Sakha, so the Sakha is the unit of selection.
         *
         *   PARIBARIK_ASANA — attaches to a `sangha_sevi`, not to an
         *     organization (ORG-BR-094); its `parent_organization_pk` is
         *     an explicitly labelled implementation proxy.
         *
         * IMPORTANT CAVEAT — do not read this list as a guarantee that
         * no member can sit on these types. Nothing enforces that:
         * `sangha_sevi.organization_pk` and
         * `membership_sakha_affiliation.organization_pk` are bare FKs to
         * nss.organization with no type CHECK, no trigger, and no API
         * validation (contrast family.py, which DOES validate
         * SAKHA_SANGHA). The bootstrap admin member SS1 in fact sits on
         * the KENDRA org, and admin.py defaults claim-less members to
         * KEN. So excluding a type here removes the ability to FILTER by
         * it; members on such an org remain visible under "All".
         *
         * OPEN: if these types must genuinely never hold members, that
         * belongs in a DB CHECK / API validation, not in a dropdown.
         *
         * This governs selection/filter dropdowns only. It is NOT an
         * authorization boundary and NOT applied to the Create
         * Organization type list — these organizations still exist and
         * are still reachable in the Organizations list and hierarchy.
         */
        nonSelectableOrgTypes: [
            "NILACHALA_KUTIRA",
            "SMRUTI_MANDIRA",
            "KUMARI_SANGHA",
            "SEVAK_SANGHA",
            "MAHILA_SANGHA",
            "PARIBARIK_ASANA",
        ],

        /**
         * The org types offered in every "pick / filter by an org type"
         * dropdown. Single source for the Organizations list filter and
         * the Member Directory Org Type filter, so the two can no longer
         * drift apart.
         */
        get selectableOrgTypes() {
            return this.orgTypes.filter(
                t => !this.nonSelectableOrgTypes.includes(t.value_code)
            );
        },

        // Org types for Create Org. ORG-BR-096: only these four are
        // creatable directly through the standard flow. Apex peers
        // (KENDRA / NILACHALA_KUTIRA / SMRUTI_MANDIRA) are singletons that
        // are never created; MAHILA_SANGHA is auto-created with its parent
        // Sakha; SAKHA_ASANA is not a distinct type (it is a SAKHA_SANGHA
        // with has_own_premises = FALSE, ORG-BR-098).
        get creatableOrgTypes() {
            const standard = ["ANCHALIKA_SANGHA", "ZILLA_SANGHA", "PATHA_CHAKRA", "SAKHA_SANGHA"];
            const allowed = [...standard];
            // Kumari/Sevak Sangha follow a Sakha-gated creation path
            // (ORG-BR-096, ORG-BR-101/102): offered only to NSS admins or
            // Sakha-scoped admins, parented by a Sakha the operator is
            // scoped to (see loadKumariSevakScope + backend gate).
            if (this.isNssAdmin || this.hasSakhaScope) {
                allowed.push("KUMARI_SANGHA", "SEVAK_SANGHA");
            }
            return this.orgTypes.filter(t => allowed.includes(t.value_code));
        },

        // ── Create-Org type-driven form behaviour (ORG-BR-098/099/100) ──
        // Shared by both the create form and the org-detail edit form so
        // the two stay consistent with the DB trigger (ORG-BR-099).
        // ORG-BR-099 was narrowed (2026-09-28): these 3 types may still
        // never carry a physical PREMISES address (address_line_1,
        // city_village_pk, postal_code_pk, latitude, longitude), but
        // country/state/district are administrative JURISDICTION, not a
        // premises, and are now allowed for every type — see the separate,
        // unconditional Country/State/District block in both forms.
        addressProhibitedForType(typeCode) {
            return ["ANCHALIKA_SANGHA", "ZILLA_SANGHA", "PATHA_CHAKRA"].includes(typeCode);
        },
        // ORG-BR-098: only SAKHA_SANGHA carries a premises attribute.
        get orgTypeHasPremises() {
            return this.createOrgForm.organization_type_code === "SAKHA_SANGHA";
        },
        // ORG-BR-099: premises-address columns (not country/state/district)
        // must stay NULL for these types.
        get orgTypeProhibitsAddress() {
            return this.addressProhibitedForType(this.createOrgForm.organization_type_code);
        },
        // ORG-BR-100: single-instance types are parented by the sole KENDRA;
        // the parent is auto-resolved and locked (operator does not choose).
        get isParentAutoResolved() {
            return this.addressProhibitedForType(this.createOrgForm.organization_type_code);
        },
        // ORG-BR-101/102: Kumari/Sevak Sangha are parented by a scoped Sakha.
        get isKumariSevakType() {
            return ["KUMARI_SANGHA", "SEVAK_SANGHA"].includes(
                this.createOrgForm.organization_type_code
            );
        },
        // The sole KENDRA org (parent for auto-resolved single-instance types).
        get kendraOrg() {
            return this.organizations.find(
                o => o.organization_type_code === "KENDRA"
            ) || null;
        },

        // The admin's own scope org — now a fallback rather than the sidebar's
        // target (the sidebar lists one entry per tier via dashboardLevels,
        // and the in-page switcher moves between orgs within a tier). Still
        // used to resolve a bare #orgDashboard hash. An NSS-WIDE admin
        // resolves to the Kendra (top-level) view; a scoped admin to the first
        // org their scope actually names. Null if neither is resolvable yet
        // (organizations/scopes still loading).
        get myOrgDashboardPk() {
            const scopes = this.currentUser?.scopes || [];
            // KENDRA scope is NSS-wide-equivalent (owner-confirmed 2026-10-22).
            if (this.isGovNssWideAdmin) return this.kendraOrg?.organization_pk || null;
            const scoped = scopes.find(s => s.organization_pk);
            return scoped ? scoped.organization_pk : null;
        },

        // The sidebar nav item's own label — matches the org-dashboard tab's
        // own tier name (role_code implies org type 1:1, see ROLE_ORG_LABELS)
        // rather than a generic "Org Dashboard", per design request.
        get myOrgDashboardLabel() {
            const scopes = this.currentUser?.scopes || [];
            // KENDRA scope is NSS-wide-equivalent (owner-confirmed 2026-10-22).
            if (this.isGovNssWideAdmin) return "Kendra Dashboard";
            const scoped = scopes.find(s => s.organization_pk);
            return (scoped && ROLE_ORG_LABELS[scoped.role_code]) || "Org Dashboard";
        },

        // ── Dashboards section / org switcher ──────────────────
        // The set of organization_pks this admin may open a dashboard for.
        // null means "every org" — the client-side mirror of the server's
        // actor_scope_org_pks() (rbac_service.py): NSS_ERP_ADMIN or an
        // NSS-WIDE scope is unbounded, any other admin is bounded to the
        // recursive subtree of each org their scopes name. Walking the tree
        // here (rather than trusting a flat scope list) matters because a
        // Zilla admin must reach the Sakha dashboards *under* that Zilla,
        // not just the Zilla's own.
        get scopeOrgPkSet() {
            const scopes = this.currentUser?.scopes || [];
            // KENDRA scope is NSS-wide-equivalent (owner-confirmed 2026-10-22).
            if (this.isGovNssWideAdmin) {
                return null;
            }
            const roots = scopes.filter(s => s.organization_pk).map(s => s.organization_pk);
            if (!roots.length) return new Set();

            const childrenByParent = new Map();
            for (const o of this.organizations) {
                const parent = o.parent_organization_pk;
                if (!parent) continue;
                if (!childrenByParent.has(parent)) childrenByParent.set(parent, []);
                childrenByParent.get(parent).push(o.organization_pk);
            }

            const inScope = new Set();
            const stack = [...roots];
            while (stack.length) {
                const pk = stack.pop();
                if (inScope.has(pk)) continue;   // also guards cyclic parents
                inScope.add(pk);
                for (const child of childrenByParent.get(pk) || []) stack.push(child);
            }
            return inScope;
        },

        // Every org of one type that this admin may open a dashboard for,
        // name-sorted. Drives both the sidebar "Dashboards" entries and the
        // in-page org switcher, so the two can never disagree about what is
        // reachable.
        dashboardOrgsFor(typeCode) {
            if (!typeCode) return [];
            const inScope = this.scopeOrgPkSet;
            return this.organizations
                .filter(o => o.organization_type_code === typeCode)
                .filter(o => inScope === null || inScope.has(o.organization_pk))
                .sort((a, b) => (a.organization_name || "").localeCompare(b.organization_name || ""));
        },

        // The dashboard levels to actually render in the sidebar: one per
        // org type the admin has at least one in-scope org for. A Sakha
        // admin therefore sees only "Sakha", while an NSS-WIDE admin sees
        // every level that exists in the data — which is what "visible to
        // the admin as per his scope" means.
        get dashboardLevels() {
            return DASHBOARD_LEVELS
                .map(lvl => ({ ...lvl, orgs: this.dashboardOrgsFor(lvl.typeCode) }))
                .filter(lvl => lvl.orgs.length > 0);
        },

        // Topbar title for the org-dashboard tab — named after the org
        // actually on screen, not the admin's own scope, so drilling from a
        // Zilla into one of its Sakhas retitles the page correctly.
        get viewingOrgDashboardLabel() {
            const lvl = DASHBOARD_LEVELS.find(
                l => l.typeCode === this.viewingOrgTypeCode
            );
            return lvl ? `${lvl.label} Dashboard` : this.myOrgDashboardLabel;
        },

        // Org type of the dashboard currently on screen — drives both the
        // topbar title above and which sidebar "Dashboards" entry highlights
        // as active.
        get viewingOrgTypeCode() {
            const org = this.organizations.find(
                o => o.organization_pk === this.viewingOrgPk
            );
            return org?.organization_type_code || "";
        },

        // Opens the Org Dashboard tab on the given org (the admin's own
        // scope via the sidebar link, or any org via "View Dashboard" on
        // an Organizations-tab card, or a drill-down from a child Sakha
        // row inside the tab itself). Forces the nested orgDashboardTab()
        // component to unmount/remount (via viewingOrgPk toggling through
        // null) so switching orgs while already on the tab re-fetches.
        openOrgDashboard(orgPk) {
            this.activeTab = "orgDashboard";
            this.viewingOrgPk = null;
            this.$nextTick(() => { this.viewingOrgPk = orgPk; });
            history.replaceState(null, "", `#orgDashboard/${orgPk}`);
        },
        viewingOrgPk: null,

        // Shared by the "Local Sakha Number" field on both the Create
        // Person tab's Sangha Sevi step and the standalone Create Sangha
        // Sevi tab (ssForm) — previously the same lookup expression
        // duplicated in both templates. '???' matches the pre-existing
        // fallback shown while short_code hasn't been assigned yet.
        sakhaShortCode(orgPk) {
            return (this.sakhaOrgs.find(o => o.organization_pk === orgPk) || {}).short_code || "???";
        },

        // True when a Sakha is selected but has no short_code yet — drives
        // the "An NSS admin must set it first" warning in the same two
        // templates as sakhaShortCode() above.
        sakhaMissingShortCode(orgPk) {
            return !!orgPk && !(this.sakhaOrgs.find(o => o.organization_pk === orgPk) || {}).short_code;
        },

        // Which mandatory credential (MBR-010/014/019A/B) a membership type
        // requires: PROBATIONARY -> Anumati Patra, everything else ->
        // Parichaya Patra. Shared by the Sangha Sevi step on both the
        // Create Person tab (createForm) and the standalone Create Sangha
        // Sevi tab (ssForm) — same lookup, so the two can't drift.
        credentialLabelFor(membershipTypePk) {
            const mt = this.membershipTypes.find(m => m.master_data_pk === membershipTypePk);
            if (!mt) return "";
            return mt.value_code === "PROBATIONARY" ? "Anumati Patra" : "Parichaya Patra";
        },

        // Sakha orgs only (for SS creation dropdown), scoped by admin's org
        get sakhaOrgs() {
            const allSakha = this.organizations.filter(
                o => o.organization_type_code === "SAKHA_SANGHA"
            );
            // NSS-WIDE or full admin: show all
            if (this.isNssAdmin || !this.currentUser?.scopes) return allSakha;
            // KENDRA scope is NSS-wide-equivalent (owner-confirmed 2026-10-22).
            if (this.isGovNssWideAdmin) return allSakha;
            // Scoped admin: filter to only their assigned org(s)
            const scopedPks = new Set(
                this.currentUser.scopes
                    .filter(s => s.organization_pk)
                    .map(s => s.organization_pk)
            );
            if (scopedPks.size === 0) return allSakha;
            return allSakha.filter(o => scopedPks.has(o.organization_pk));
        },

        async loadCreateOrgData() {
            // Load org types + countries if not already loaded
            await Promise.all([
                this.loadOrgTypes(),
                this.loadCreateOrgCountries(),
            ]);
        },

        // Handles every type-driven side effect on the Create Org form
        // (ORG-BR-098/099/100/101/102): reset stale parent/premises state,
        // lock the parent for single-instance-parent types, and fetch the
        // Kumari/Sevak Sakha-scope options when applicable.
        onCreateOrgTypeChange() {
            this.createOrgForm.parent_organization_pk = "";
            this.createOrgForm.has_own_premises = false;

            // ORG-BR-105: show the auto-generated org code preview for the
            // newly-selected type. Wings return no code (handled server-side);
            // non-wing types get a live "what the code will be" value.
            this.fetchOrgCodePreview();

            if (this.isParentAutoResolved) {
                // ORG-BR-100: single legal parent instance (the sole Kendra) —
                // resolved and locked here rather than left for the operator
                // to pick from a one-item list.
                if (this.kendraOrg) {
                    this.createOrgForm.parent_organization_pk = this.kendraOrg.organization_pk;
                }
                this.kumariSevakScope = { mode: "choose", auto_select_pk: null, sakhas: [] };
                return;
            }

            if (this.isKumariSevakType) {
                this.loadKumariSevakScope(this.createOrgForm.organization_type_code);
                return;
            }

            this.kumariSevakScope = { mode: "choose", auto_select_pk: null, sakhas: [] };
        },

        // ORG-BR-105: fetch a read-only preview of the org code that will be
        // minted for the selected type on submit. Peeked (not consumed) via
        // GET /admin/organizations/next-code, so opening the form never burns
        // a sequence number. Wings and typeless states resolve to a blank
        // preview. The authoritative code is assigned only on submit.
        async fetchOrgCodePreview() {
            const typeCode = this.createOrgForm.organization_type_code;
            if (!typeCode) {
                this.orgCodePreview = "";
                this.orgCodePreviewLoading = false;
                return;
            }
            this.orgCodePreviewLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/organizations/next-code?organization_type_code=${encodeURIComponent(typeCode)}`
                );
                if (!res.ok) {
                    this.orgCodePreview = "";
                    return;
                }
                const data = await res.json();
                this.orgCodePreview = data?.next_code || "";
            } catch (e) {
                // Non-fatal: the code is authoritatively generated on submit
                // regardless. Leave the preview blank on failure.
                this.orgCodePreview = "";
            } finally {
                this.orgCodePreviewLoading = false;
            }
        },

        // ORG-BR-101/102: fetch the caller's Sakha selection mode for
        // Kumari/Sevak Sangha creation and auto-fill/lock the parent field
        // when unambiguous. Mirrors loadSakhaScope for member-attach forms.
        async loadKumariSevakScope(typeCode) {
            this.kumariSevakScopeLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/organizations/kumari-sevak-sakha-options?type_code=${encodeURIComponent(typeCode)}`
                );
                if (!res.ok) {
                    this.kumariSevakScope = { mode: "choose", auto_select_pk: null, sakhas: [] };
                    return;
                }
                const data = await res.json();
                this.kumariSevakScope = {
                    mode: data.mode || "choose",
                    auto_select_pk: data.auto_select_pk || null,
                    sakhas: data.sakhas || [],
                };
                if (this.kumariSevakScope.mode === "locked" && this.kumariSevakScope.auto_select_pk) {
                    this.createOrgForm.parent_organization_pk = this.kumariSevakScope.auto_select_pk;
                }
            } catch (_) {
                this.kumariSevakScope = { mode: "choose", auto_select_pk: null, sakhas: [] };
            } finally {
                this.kumariSevakScopeLoading = false;
            }
        },

        async loadOrgTypes() {
            if (this.orgTypes.length === 0) {
                try {
                    const res = await NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=ORGANIZATION_TYPE");
                    if (res.ok) {
                        this.orgTypes = await res.json();
                    } else {
                        console.error("loadOrgTypes: API returned", res.status);
                    }
                } catch (err) {
                    console.error("loadOrgTypes: fetch error", err);
                }
            }
        },

        // ── Create-org location cascade (shared utility) ────────────

        _createLocCascade: NSSLocation.create({
            fetchFn: (...args) => NSSAuth.apiFetch(...args),
            arrays: {
                countries: 'createOrgCountries',
                states: 'createOrgStates',
                districts: 'createOrgDistricts',
                cities: 'createOrgCities',
            },
            form: 'createOrgForm',
        }),

        async loadCreateOrgCountries() {
            if (this.createOrgCountries.length === 0) {
                await this._createLocCascade.loadCountries(this);
            }
        },
        async loadCreateOrgStates(pk)      { await this._createLocCascade.loadStates(this, pk); },
        async loadCreateOrgDistricts(pk)   { await this._createLocCascade.loadDistricts(this, pk); },
        async loadCreateOrgCities(pk)      { await this._createLocCascade.loadCities(this, pk); },
        onCreateOrgCountryChange()         { this._createLocCascade.onCountryChange(this); },
        onCreateOrgStateChange()           { this._createLocCascade.onStateChange(this); },
        onCreateOrgDistrictChange()        { this._createLocCascade.onDistrictChange(this); },

        onCreateOrgCityVillageChange() {
            const name = (this.createOrgForm.city_village_name || "").trim().toLowerCase();
            if (!name) return;
            const match = this.createOrgCities.find(
                cv => (cv.city_village_name || "").trim().toLowerCase() === name
            );
            if (match && match.postal_code) this.createOrgForm.postal_code_value = match.postal_code;
        },

        // ── Live duplicate check for organization_code / short_code ──
        // Debounced per field. `field` is "organization_code" or
        // "short_code"; `stateKey` names the reactive slot to write into
        // ("orgCodeCheck" / "shortCodeCheck" / "inlineShortCodeCheck").
        // `excludePk` skips the row being edited (null on the create form).
        // Mirrors the server's GET /admin/organizations/code-availability,
        // which itself matches the DB uniqueness constraints (all rows,
        // active or not). `stateKey` also selects which form field to read
        // back for the staleness check — "inlineShortCodeCheck" reads the
        // inline-edit's `editingShortCode` rather than createOrgForm.
        onCodeInput(field, stateKey, rawValue, excludePk = null) {
            const slot = this[stateKey];
            // Both codes are stored/submitted uppercased (short_code by the
            // DB CHECK, organization_code by submitCreateOrg), so check
            // against the uppercased value to match what will actually land.
            const value = (rawValue || "").trim().toUpperCase();

            // Clear any stale result immediately; empty value = nothing to check.
            slot.conflict = null;
            if (!value) {
                slot.checking = false;
                if (this._codeCheckTimers[stateKey]) clearTimeout(this._codeCheckTimers[stateKey]);
                return;
            }

            slot.checking = true;
            if (this._codeCheckTimers[stateKey]) clearTimeout(this._codeCheckTimers[stateKey]);
            this._codeCheckTimers[stateKey] = setTimeout(async () => {
                try {
                    const params = new URLSearchParams({ field, value });
                    if (excludePk) params.set("exclude_pk", excludePk);
                    const res = await NSSAuth.apiFetch(
                        `/api/v1/admin/organizations/code-availability?${params}`
                    );
                    if (!res.ok) { slot.checking = false; slot.conflict = null; return; }
                    const data = await res.json();
                    // Ignore a stale response if the field changed meanwhile.
                    const current = stateKey === "inlineShortCodeCheck"
                        ? (this.editingShortCode || "").trim().toUpperCase()
                        : field === "short_code"
                            ? (this.createOrgForm.short_code || "").trim().toUpperCase()
                            : (this.createOrgForm.organization_code || "").trim().toUpperCase();
                    if (current !== data.value) return;
                    slot.conflict = data.available ? null : data.conflict;
                } catch (_e) {
                    slot.conflict = null;
                } finally {
                    slot.checking = false;
                }
            }, 350);
        },

        async submitCreateOrg() {
            this.createOrgError = "";
            this.createOrgSuccess = "";

            // Block submit on a known code/short-code conflict; the DB would
            // reject it anyway, but this gives a clean message up front.
            if (this.orgCodeCheck.conflict) {
                this.createOrgError = `Organization Code is already used by ${this.orgCodeCheck.conflict.organization_name}.`;
                return;
            }
            if (this.shortCodeCheck.conflict) {
                this.createOrgError = `Short Code is already used by ${this.shortCodeCheck.conflict.organization_name}.`;
                return;
            }
            // ORG-BR-099: Anchalika/Zilla/Patha Chakra have no premises but
            // must still record their administrative jurisdiction — mirrors
            // the backend's mandatory check in create_organization().
            if (this.orgTypeProhibitsAddress && !(
                this.createOrgForm.country_pk && this.createOrgForm.state_pk && this.createOrgForm.district_pk
            )) {
                this.createOrgError = `${this.createOrgForm.organization_type_code} requires country, state, and district.`;
                return;
            }

            // MBR-CONTACT-01/02: organization email + country-wise mobile.
            const orgEmailErr = NSS.validateEmail((this.createOrgForm.org_email || "").trim());
            if (orgEmailErr) {
                this.createOrgError = orgEmailErr;
                return;
            }
            const orgMobileErr = NSS.validateMobile((this.createOrgForm.country_phone_code || "").trim(), (this.createOrgForm.mobile_number || "").trim());
            if (orgMobileErr) {
                this.createOrgError = orgMobileErr;
                return;
            }

            this.createOrgLoading = true;

            try {
                const f = this.createOrgForm;
                const payload = {
                    organization_name: f.organization_name.trim(),
                    organization_type_code: f.organization_type_code,
                };

                if (f.parent_organization_pk) payload.parent_organization_pk = f.parent_organization_pk;
                // ORG-BR-098: has_own_premises is only meaningful for
                // SAKHA_SANGHA; send the operator's choice for that type,
                // otherwise omit and let the backend default apply.
                if (this.orgTypeHasPremises) payload.has_own_premises = !!f.has_own_premises;
                // KUMARI_SANGHA/SEVAK_SANGHA inherit their organization_code
                // and all location/contact detail from the parent Sakha
                // server-side — never send operator-entered values for these
                // two types (the backend ignores them regardless).
                if (!this.isKumariSevakType) {
                    if (f.organization_code.trim()) payload.organization_code = f.organization_code.trim().toUpperCase();
                    if (f.short_code.trim()) payload.short_code = f.short_code.trim().toUpperCase();
                    if (f.address_line_1.trim()) payload.address_line_1 = f.address_line_1.trim();
                    if (f.country_pk) payload.country_pk = f.country_pk;
                    if (f.state_pk) payload.state_pk = f.state_pk;
                    if (f.district_pk) payload.district_pk = f.district_pk;
                    if (f.city_village_name.trim()) payload.city_village_name = f.city_village_name.trim();
                    if (f.postal_code_value.trim()) payload.postal_code_value = f.postal_code_value.trim();
                    if (f.phone_number.trim()) payload.phone_number = f.phone_number.trim();
                    if (f.mobile_number.trim()) {
                        payload.mobile_number = f.mobile_number.trim();
                        if (f.country_phone_code.trim()) payload.country_phone_code = f.country_phone_code.trim();
                    }
                    if (f.org_email.trim()) payload.org_email = f.org_email.trim();
                    if (f.org_website_url.trim()) payload.org_website_url = f.org_website_url.trim();
                    if (f.org_youtube_channel_url.trim()) payload.org_youtube_channel_url = f.org_youtube_channel_url.trim();
                }

                const res = await NSSAuth.apiFetch("/api/v1/admin/organizations", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.createOrgError = NSS.errorMessage(data, res.status);
                    return;
                }

                const data = await res.json();
                this.createOrgSuccess = data.organization_code
                    ? `Organization "${data.organization_name}" created successfully (code: ${data.organization_code}).`
                    : `Organization "${data.organization_name}" created successfully (wing of its parent Sakha — no separate code).`;

                // Reset form
                this.createOrgForm = {
                    organization_name: "", organization_type_code: "",
                    parent_organization_pk: "", has_own_premises: false,
                    organization_code: "", short_code: "",
                    address_line_1: "", city_village_name: "",
                    country_pk: "", state_pk: "", district_pk: "", postal_code_value: "",
                    phone_number: "", mobile_number: "", org_email: "",
                    org_website_url: "", org_youtube_channel_url: "",
                };
                this.orgCodeCheck = { checking: false, conflict: null };
                this.shortCodeCheck = { checking: false, conflict: null };
                this.orgCodePreview = "";
                this.orgCodePreviewLoading = false;
                this.kumariSevakScope = { mode: "choose", auto_select_pk: null, sakhas: [] };

                // Refresh the organizations list reference data
                this.fetchOrganizations();
                // loadOrgHierarchy() now always refetches on tab open (no more
                // orgTreeLoaded latch), so clearing the cached tree here just
                // avoids a stale flash if the Hierarchy tab is already visible.
                this.orgTree = [];
            } catch (err) {
                this.createOrgError = err.message || "Failed to create organization.";
            } finally {
                this.createOrgLoading = false;
            }
        },

        async saveOrgDetail(org) {
            // MBR-CONTACT-01/02: validate organization email + country-wise mobile.
            const orgEmailErr = NSS.validateEmail((this.editOrgForm.org_email || "").trim());
            if (orgEmailErr) {
                this.showToast(orgEmailErr, "error");
                return;
            }
            const orgMobileErr = NSS.validateMobile((this.editOrgForm.country_phone_code || "").trim(), (this.editOrgForm.mobile_number || "").trim());
            if (orgMobileErr) {
                this.showToast(orgMobileErr, "error");
                return;
            }
            this.savingOrgDetail = true;
            try {
                const body = {};
                if (this.editOrgForm.organization_name !== (org.organization_name || ""))
                    body.organization_name = this.editOrgForm.organization_name;

                // ORG-BR-099 (narrowed): address_line_1/city_village/postal_code
                // are premises-only and still prohibited for these types — the
                // DB trigger rejects them, and the fields are hidden in the UI,
                // but guard here too in case editOrgForm still holds stale
                // values from before the row was opened. Country/state/district
                // are jurisdiction fields, not premises, so they're always sent.
                if (!this.addressProhibitedForType(org.organization_type_code)) {
                    if (this.editOrgForm.address_line_1 !== (org.address_line_1 || ""))
                        body.address_line_1 = this.editOrgForm.address_line_1;

                    // City/Village — text name, lookup/create on backend
                    if (this.editOrgForm.city_village_name !== (org.city_village_name || ""))
                        body.city_village_name = this.editOrgForm.city_village_name;

                    // PIN Code — text value, lookup/create on backend
                    if (this.editOrgForm.postal_code_value !== (org.postal_code || ""))
                        body.postal_code_value = this.editOrgForm.postal_code_value;
                }

                // Location FK fields (except city_village and postal_code — sent as text)
                for (const fk of ["country_pk", "state_pk", "district_pk"]) {
                    if (this.editOrgForm[fk] !== (org[fk] || ""))
                        body[fk] = this.editOrgForm[fk];
                }

                if (this.editOrgForm.phone_number !== (org.phone_number || ""))
                    body.phone_number = this.editOrgForm.phone_number;
                if (this.editOrgForm.mobile_number !== (org.mobile_number || ""))
                    body.mobile_number = this.editOrgForm.mobile_number;
                if (this.editOrgForm.country_phone_code !== (org.country_phone_code || ""))
                    body.country_phone_code = this.editOrgForm.country_phone_code;
                if (this.editOrgForm.org_email !== (org.org_email || ""))
                    body.org_email = this.editOrgForm.org_email;
                if (this.editOrgForm.org_website_url !== (org.org_website_url || ""))
                    body.org_website_url = this.editOrgForm.org_website_url;
                if (this.editOrgForm.org_youtube_channel_url !== (org.org_youtube_channel_url || ""))
                    body.org_youtube_channel_url = this.editOrgForm.org_youtube_channel_url;

                if (Object.keys(body).length === 0) {

                    this.showToast("No changes to save.", "error");
                    this.savingOrgDetail = false;
                    return;
                }

                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/organizations/${org.organization_pk}`,
                    {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(body),
                    }
                );
                if (res.ok) {
                    // Apply changes locally
                    for (const [k, v] of Object.entries(body)) {
                        org[k] = v;
                    }
                    // Update display names for location fields
                    if (body.country_pk !== undefined) {
                        const c = this.locationCountries.find(x => x.country_pk === this.editOrgForm.country_pk);
                        org.country_name = c ? c.country_name : null;
                    }
                    if (body.state_pk !== undefined) {
                        const s = this.locationStates.find(x => x.state_pk === this.editOrgForm.state_pk);
                        org.state_name = s ? s.state_name : null;
                    }
                    if (body.district_pk !== undefined) {
                        const d = this.locationDistricts.find(x => x.district_pk === this.editOrgForm.district_pk);
                        org.district_name = d ? d.district_name : null;
                    }
                    if (body.city_village_name !== undefined) {
                        org.city_village_name = this.editOrgForm.city_village_name || null;
                    }
                    if (body.postal_code_value !== undefined) {
                        org.postal_code = this.editOrgForm.postal_code_value || null;
                    }
                    this.editOrgDetailPk = null;
                    this.showToast("Organization updated.");
                    // The Geography tab holds its own cached lists (it is
                    // x-show, not re-rendered on tab switch), so an org
                    // rename/relocation here would otherwise show stale on
                    // that tab until a full re-select. Refresh in place,
                    // preserving the current drill selections.
                    this.refreshGeoLists();
                } else {
                    const err = await res.json().catch(() => ({}));
                    this.showToast(err.detail || "Failed to update.", "error");
                }
            } catch (err) {
                this.showToast("Network error. Try again.", "error");
            } finally {
                this.savingOrgDetail = false;
            }
        },

        // ── Toast helper ───────────────────────────────────────

        showToast(msg, type = "success") {
            this.toast = msg;
            this.toastType = type;
            setTimeout(() => { this.toast = ""; }, 3000);
        },

        // ── Formatting helpers ─────────────────────────────────

        formatDate(iso) {
            return NSS.formatDateTime(iso);
        },

        // NOTE: no local statusBadgeClass here — badge classes come from
        // NSS.* helpers in nss-config.js (the single source of truth that
        // pairs with frontend/assets/css/badges.css). For account_status use
        // NSS.accountBadgeClass(); for claim_status NSS.claimBadgeClass().

        async logout() {
            await NSSAuth.logout();
        },

        // ── Registration Claims (merged from claim-approval) ──────

        // Claims data
        claims: [],
        claimsTotal: 0,
        claimsPage: 1,
        claimsPageSize: 20,
        claimsLoading: false,
        claimsStatusFilter: "PENDING",
        claimsPendingCount: 0,

        // Claims sorting. Empty claimsSortBy means "leave the server's
        // default" — oldest-first, because this is an approval queue.
        claimsSortBy: "",
        claimsSortDir: "asc",

        // Claim detail
        selectedClaim: null,
        adminRemarks: "",
        claimActionLoading: false,
        claimActionError: "",

        // Claim edit
        claimEditing: false,
        claimEditForm: {},
        claimEditLoading: false,
        claimEditError: "",

        // Claim sakhas lookup
        claimSakhas: [],

        formatPhone(code, number) {
            return NSS.formatPhone(code, number);
        },

        sortClaims(key) {
            const next = NSS.toggleSort(this.claimsSortBy, this.claimsSortDir, key);
            this.claimsSortBy = next.key;
            this.claimsSortDir = next.dir;
            // Back to page 1: the requested order changes which rows belong
            // on any given page, so staying on page 3 would show an
            // arbitrary slice of the new ordering.
            this.claimsPage = 1;
            this.loadClaims();
        },

        async loadClaims() {
            this.claimsLoading = true;
            try {
                const params = new URLSearchParams({
                    claim_status: this.claimsStatusFilter,
                    page: this.claimsPage,
                    page_size: this.claimsPageSize,
                });
                if (this.claimsSortBy) {
                    params.set("sort_by", this.claimsSortBy);
                    params.set("sort_dir", this.claimsSortDir);
                }
                const res = await NSSAuth.apiFetch(`/api/v1/admin/claims?${params}`);
                if (res.ok) {
                    const data = await res.json();
                    this.claims = data.claims;
                    this.claimsTotal = data.total;
                } else if (res.status === 403) {
                    this.claims = [];
                    this.claimsTotal = 0;
                }
            } catch (err) {
                console.error("Failed to load claims:", err);
            } finally {
                this.claimsLoading = false;
            }
        },

        async loadClaimsPendingCount() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/admin/claims?claim_status=PENDING&page_size=1");
                if (res.ok) {
                    const data = await res.json();
                    this.claimsPendingCount = data.total;
                }
            } catch { /* ignore */ }
        },

        async loadClaimSakhas() {
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/organization/organizations?type_code=SAKHA_SANGHA&limit=${NSS.MAX_PAGE_SIZE}`
                );
                if (res.ok) {
                    const data = await res.json();
                    this.claimSakhas = Array.isArray(data) ? data : (data.organizations || []);
                }
            } catch { /* non-critical */ }
        },

        async viewClaim(claimPk) {
            this.claimActionError = "";
            this.adminRemarks = "";
            this.claimEditing = false;
            this.claimEditError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/admin/claims/${claimPk}`);
                if (res.ok) {
                    this.selectedClaim = await res.json();
                } else {
                    const data = await res.json().catch(() => ({}));
                    await NSSDialog.alert(data.detail || "Failed to load claim details.");
                }
            } catch {
                await NSSDialog.alert("Failed to load claim details.");
            }
        },

        async approveClaim() {
            this.claimActionError = "";
            this.claimActionLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/claims/${this.selectedClaim.registration_claim_pk}/approve`,
                    {
                        method: "POST",
                        body: JSON.stringify({ admin_remarks: this.adminRemarks.trim() || null }),
                    }
                );
                if (res.ok) {
                    const data = await res.json();
                    const ssId = data.sangha_sevi_id || "";
                    await NSSDialog.alert(
                        `Claim approved successfully.${ssId ? `\nSangha Sevi ID: ${ssId}` : ""}\n\nThe user account is now ACTIVE — the member can log in using the password they set during registration.`
                    );
                    this.selectedClaim = null;
                    this.adminRemarks = "";
                    await this.loadClaims();
                    await this.loadClaimsPendingCount();
                    this.fetchUsers();
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.claimActionError = data.detail || "Approval failed.";
                }
            } catch {
                this.claimActionError = "Unable to connect to server.";
            } finally {
                this.claimActionLoading = false;
            }
        },

        async rejectClaim() {
            if (!this.adminRemarks.trim()) {
                this.claimActionError = "Rejection reason is required.";
                return;
            }
            this.claimActionError = "";
            this.claimActionLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/claims/${this.selectedClaim.registration_claim_pk}/reject`,
                    {
                        method: "POST",
                        body: JSON.stringify({ admin_remarks: this.adminRemarks.trim() }),
                    }
                );
                if (res.ok) {
                    this.selectedClaim = null;
                    this.adminRemarks = "";
                    await this.loadClaims();
                    await this.loadClaimsPendingCount();
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.claimActionError = data.detail || "Rejection failed.";
                }
            } catch {
                this.claimActionError = "Unable to connect to server.";
            } finally {
                this.claimActionLoading = false;
            }
        },

        startClaimEdit() {
            if (!this.selectedClaim) return;
            const c = this.selectedClaim;
            const nameParts = (c.person_name || "").split(/\s+/);

            // Pre-populate form with current claim values
            const formData = {
                first_name: nameParts[0] || "",
                middle_name: nameParts.length > 2 ? nameParts.slice(1, -1).join(" ") : "",
                last_name: nameParts.length > 1 ? nameParts[nameParts.length - 1] : "",
                claimed_organization_pk: c.claimed_organization_pk || "",
                claimed_membership_type_master_data_pk: c.claimed_membership_type_master_data_pk || "",
                claimed_local_sakha_number: c.claimed_local_sakha_number || "",
                claimed_credential_document_number: c.claimed_credential_document_number || "",
                claimed_joining_date: c.claimed_joining_date || "",
                darshak_local_sakha_number: c.darshak_local_sakha_number || "",
                country_phone_code: c.country_phone_code || NSS.DEFAULT_COUNTRY_CODE,
                mobile_number: c.mobile_number || "",
                email: c.email || "",
            };

            this.claimEditForm = formData;
            this.claimEditError = "";
            this.claimEditing = true;

            // Re-apply form values after DOM renders the <select> elements
            // (x-if creates DOM fresh; x-model on <select> can lose the
            // initial value if the options aren't yet present in the same tick)
            this.$nextTick(() => {
                this.claimEditForm.claimed_organization_pk = formData.claimed_organization_pk;
                this.claimEditForm.claimed_membership_type_master_data_pk = formData.claimed_membership_type_master_data_pk;
            });
        },

        cancelClaimEdit() {
            this.claimEditing = false;
            this.claimEditError = "";
        },

        async saveClaimEdit() {
            this.claimEditError = "";
            // MBR-CONTACT-01/02: validate the effective contact values held by
            // the edit form before submitting.
            const ceMobileErr = NSS.validateMobile((this.claimEditForm.country_phone_code || "").trim(), (this.claimEditForm.mobile_number || "").trim());
            if (ceMobileErr) { this.claimEditError = ceMobileErr; return; }
            const ceEmailErr = NSS.validateEmail((this.claimEditForm.email || "").trim());
            if (ceEmailErr) { this.claimEditError = ceEmailErr; return; }
            this.claimEditLoading = true;
            try {
                const payload = {};
                const c = this.selectedClaim;
                const f = this.claimEditForm;

                if (f.claimed_organization_pk !== c.claimed_organization_pk)
                    payload.claimed_organization_pk = f.claimed_organization_pk;
                if (f.claimed_membership_type_master_data_pk !== (c.claimed_membership_type_master_data_pk || ""))
                    payload.claimed_membership_type_master_data_pk = f.claimed_membership_type_master_data_pk;
                if (f.claimed_local_sakha_number !== (c.claimed_local_sakha_number || ""))
                    payload.claimed_local_sakha_number = f.claimed_local_sakha_number;
                if (f.claimed_credential_document_number !== (c.claimed_credential_document_number || ""))
                    payload.claimed_credential_document_number = f.claimed_credential_document_number;
                if (f.claimed_joining_date !== (c.claimed_joining_date || ""))
                    payload.claimed_joining_date = f.claimed_joining_date;
                if (f.darshak_local_sakha_number !== (c.darshak_local_sakha_number || ""))
                    payload.darshak_local_sakha_number = f.darshak_local_sakha_number;

                const nameParts = (c.person_name || "").split(/\s+/);
                const origFirst = nameParts[0] || "";
                const origLast = nameParts.length > 1 ? nameParts[nameParts.length - 1] : "";
                if (f.first_name.trim() !== origFirst) payload.first_name = f.first_name;
                if (f.last_name.trim() !== origLast) payload.last_name = f.last_name;
                if (f.country_phone_code !== (c.country_phone_code || ""))
                    payload.country_phone_code = f.country_phone_code;
                if (f.mobile_number !== (c.mobile_number || ""))
                    payload.mobile_number = f.mobile_number;
                if (f.email.toLowerCase() !== (c.email || "").toLowerCase())
                    payload.email = f.email;

                if (Object.keys(payload).length === 0) {
                    this.claimEditing = false;
                    return;
                }

                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/claims/${c.registration_claim_pk}`,
                    { method: "PATCH", body: JSON.stringify(payload) }
                );

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.claimEditError = NSS.errorMessage(data, res.status);
                    return;
                }

                this.claimEditing = false;
                await this.viewClaim(c.registration_claim_pk);
            } catch {
                this.claimEditError = "Unable to connect to server.";
            } finally {
                this.claimEditLoading = false;
            }
        },

        // ── Sakha Transfer / Apply for Darshak change requests
        //    (MBR-048/MBR-049) ──────────────────────────────────
        // Mirrors the Registration Claims queue above. The backend status
        // filter only matches a single mcr.status value, so there is no
        // single "REJECTED" status — the UI's Rejected pill merges the two
        // terminal rejection statuses with two parallel fetches below.
        changeRequests: [],
        changeRequestsTotal: 0,
        changeRequestsPage: 1,
        changeRequestsPageSize: 20,
        changeRequestsLoading: false,
        changeRequestsStatusFilter: "PENDING_SOURCE_RELEASE",
        changeRequestsPendingCount: 0,

        selectedChangeRequest: null,
        changeRequestActionRemarks: "",
        changeRequestActionLoading: false,
        changeRequestActionError: "",
        changeRequestIsLegacyImport: false,
        changeRequestNewLocalNumber: "",

        get changeRequestsStatusFilterLabel() {
            const labels = {
                PENDING_SOURCE_RELEASE: "Pending Release",
                PENDING_DESTINATION_ACCEPT: "Pending Accept",
                COMPLETED: "Completed",
                REJECTED: "Rejected",
            };
            return labels[this.changeRequestsStatusFilter] || this.changeRequestsStatusFilter;
        },

        async loadChangeRequests() {
            this.changeRequestsLoading = true;
            try {
                if (this.changeRequestsStatusFilter === "REJECTED") {
                    // No single backend status covers both rejection
                    // outcomes — fetch each and merge client-side.
                    const [resSrc, resDest] = await Promise.all([
                        NSSAuth.apiFetch(`/api/v1/membership/change-requests?status=REJECTED_BY_SOURCE&page=1&page_size=${this.changeRequestsPageSize}`),
                        NSSAuth.apiFetch(`/api/v1/membership/change-requests?status=REJECTED_BY_DESTINATION&page=1&page_size=${this.changeRequestsPageSize}`),
                    ]);
                    const dataSrc = resSrc.ok ? await resSrc.json() : { requests: [], total: 0 };
                    const dataDest = resDest.ok ? await resDest.json() : { requests: [], total: 0 };
                    this.changeRequests = [...dataSrc.requests, ...dataDest.requests]
                        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                    this.changeRequestsTotal = dataSrc.total + dataDest.total;
                    return;
                }
                const params = new URLSearchParams({
                    status: this.changeRequestsStatusFilter,
                    page: this.changeRequestsPage,
                    page_size: this.changeRequestsPageSize,
                });
                const res = await NSSAuth.apiFetch(`/api/v1/membership/change-requests?${params}`);
                if (res.ok) {
                    const data = await res.json();
                    this.changeRequests = data.requests;
                    this.changeRequestsTotal = data.total;
                } else if (res.status === 403) {
                    this.changeRequests = [];
                    this.changeRequestsTotal = 0;
                }
            } catch (err) {
                console.error("Failed to load change requests:", err);
            } finally {
                this.changeRequestsLoading = false;
            }
        },

        async loadChangeRequestsPendingCount() {
            try {
                const res = await NSSAuth.apiFetch("/api/v1/membership/change-requests?status=PENDING_SOURCE_RELEASE&page_size=1");
                if (res.ok) {
                    const data = await res.json();
                    this.changeRequestsPendingCount = data.total;
                }
            } catch { /* ignore */ }
        },

        async viewChangeRequest(pk) {
            this.changeRequestActionError = "";
            this.changeRequestActionRemarks = "";
            this.changeRequestIsLegacyImport = false;
            this.changeRequestNewLocalNumber = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/membership/change-requests/${pk}`);
                if (res.ok) {
                    this.selectedChangeRequest = await res.json();
                } else {
                    const data = await res.json().catch(() => ({}));
                    await NSSDialog.alert(data.detail || "Failed to load change request details.");
                }
            } catch {
                await NSSDialog.alert("Failed to load change request details.");
            }
        },

        async releaseChangeRequest() {
            await this._changeRequestSourceDecision("RELEASE");
        },

        async rejectSourceChangeRequest() {
            if (!this.changeRequestActionRemarks.trim()) {
                this.changeRequestActionError = "A reason is required to reject.";
                return;
            }
            await this._changeRequestSourceDecision("REJECT");
        },

        async _changeRequestSourceDecision(decision) {
            this.changeRequestActionError = "";
            this.changeRequestActionLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/membership/change-requests/${this.selectedChangeRequest.membership_change_request_pk}/source-decision`,
                    {
                        method: "POST",
                        body: JSON.stringify({ decision, remarks: this.changeRequestActionRemarks.trim() || null }),
                    }
                );
                if (res.ok) {
                    this.selectedChangeRequest = await res.json();
                    this.changeRequestActionRemarks = "";
                    await this.loadChangeRequestsPendingCount();
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.changeRequestActionError = NSS.errorMessage ? NSS.errorMessage(data, res.status) : (data.detail || "Action failed.");
                }
            } catch {
                this.changeRequestActionError = "Unable to connect to server.";
            } finally {
                this.changeRequestActionLoading = false;
            }
        },

        async acceptChangeRequest() {
            if (this.changeRequestIsLegacyImport && !this.changeRequestNewLocalNumber.trim()) {
                this.changeRequestActionError = "Enter the legacy Local Sakha Number, or uncheck legacy-import to auto-number it.";
                return;
            }
            await this._changeRequestDestinationDecision("ACCEPT");
        },

        async rejectDestinationChangeRequest() {
            if (!this.changeRequestActionRemarks.trim()) {
                this.changeRequestActionError = "A reason is required to reject.";
                return;
            }
            await this._changeRequestDestinationDecision("REJECT");
        },

        async _changeRequestDestinationDecision(decision) {
            this.changeRequestActionError = "";
            this.changeRequestActionLoading = true;
            try {
                const body = {
                    decision,
                    remarks: this.changeRequestActionRemarks.trim() || null,
                };
                if (decision === "ACCEPT" && this.changeRequestIsLegacyImport) {
                    body.is_legacy_import = true;
                    body.new_local_number = this.changeRequestNewLocalNumber.trim();
                }
                const res = await NSSAuth.apiFetch(
                    `/api/v1/membership/change-requests/${this.selectedChangeRequest.membership_change_request_pk}/destination-decision`,
                    { method: "POST", body: JSON.stringify(body) }
                );
                if (res.ok) {
                    this.selectedChangeRequest = await res.json();
                    this.changeRequestActionRemarks = "";
                    this.changeRequestIsLegacyImport = false;
                    this.changeRequestNewLocalNumber = "";
                    await this.loadChangeRequestsPendingCount();
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.changeRequestActionError = NSS.errorMessage ? NSS.errorMessage(data, res.status) : (data.detail || "Action failed.");
                }
            } catch {
                this.changeRequestActionError = "Unable to connect to server.";
            } finally {
                this.changeRequestActionLoading = false;
            }
        },

        // ═══════════════════════════════════════════════════════
        //  PERSON DIRECTORY  (Tier-3 parity — replaces /person page)
        // ═══════════════════════════════════════════════════════
        pdPersons: [],
        pdTotal: 0,
        pdLoading: false,
        pdError: "",
        pdGenderFilter: "",
        pdMaritalFilter: "",
        pdBloodFilter: "",
        pdGenderOptions: [],
        pdMaritalOptions: [],
        pdBloodOptions: [],
        pdSelected: null,
        pdAddresses: [],
        pdDetailLoading: false,
        pdOptionsLoaded: false,

        // Person Directory sorting. Empty means "keep the server default"
        // (first name, last name), which is the order this list has always
        // shown, so the initial view is unchanged.
        pdSortBy: "",
        pdSortDir: "asc",

        /**
         * Sort-bar click on the Person Directory.
         *
         * Re-queries rather than reordering in place: the endpoint caps the
         * response at 500 rows, so the browser does not hold the full set
         * and sorting locally would order an arbitrary subset.
         */
        sortPersonDir(key) {
            const next = NSS.toggleSort(this.pdSortBy, this.pdSortDir, key);
            this.pdSortBy = next.key;
            this.pdSortDir = next.dir;
            this.fetchPersonDirectory();
        },

        /**
         * True when any Person Directory filter or sort is active.
         * Drives the Clear button's disabled state.
         */
        get pdFiltersActive() {
            return Boolean(
                this.pdGenderFilter || this.pdMaritalFilter ||
                this.pdBloodFilter || this.pdSortBy
            );
        },

        /**
         * Clear button — resets the Person Directory to its opening state:
         * all three filters, the sort order, and the open detail row
         * (fetchPersonDirectory clears pdSelected).
         */
        clearPersonDirFilters() {
            this.pdGenderFilter = "";
            this.pdMaritalFilter = "";
            this.pdBloodFilter = "";
            this.pdSortBy = "";
            this.pdSortDir = "asc";
            return this.fetchPersonDirectory();
        },

        async loadPersonDirectory() {
            if (!this.pdOptionsLoaded) {
                this.pdOptionsLoaded = true;
                const cats = ["GENDER", "MARITAL_STATUS", "BLOOD_GROUP"];
                const [g, m, b] = await Promise.all(cats.map(c =>
                    NSSAuth.apiFetch(`/api/v1/foundation/master-data?category_code=${c}`)
                        .then(r => r.ok ? r.json() : []).catch(() => [])
                ));
                this.pdGenderOptions = g;
                this.pdMaritalOptions = m;
                this.pdBloodOptions = b;
            }
            await this.fetchPersonDirectory();
        },

        async fetchPersonDirectory() {
            this.pdLoading = true;
            this.pdError = "";
            this.pdSelected = null;
            try {
                const params = new URLSearchParams({ limit: NSS.MAX_PAGE_SIZE });
                if (this.pdGenderFilter) params.set("gender_code", this.pdGenderFilter);
                if (this.pdMaritalFilter) params.set("marital_status_code", this.pdMaritalFilter);
                if (this.pdBloodFilter) params.set("blood_group_code", this.pdBloodFilter);
                if (this.pdSortBy) {
                    params.set("sort_by", this.pdSortBy);
                    params.set("sort_dir", this.pdSortDir);
                }
                const res = await NSSAuth.apiFetch(`/api/v1/person/persons?${params}`);
                if (res.status === 403) { this.pdError = "You do not have permission to view persons."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                this.pdPersons = data.persons;
                this.pdTotal = data.total;
            } catch (err) {
                this.pdError = err.message || "Failed to load persons.";
            } finally {
                this.pdLoading = false;
            }
        },

        async viewPerson(person) {
            // Toggle: clicking the already-selected row closes it.
            if (this.pdSelected && this.pdSelected.person_pk === person.person_pk) {
                this.pdSelected = null;
                this.pdAddresses = [];
                return;
            }
            this.pdSelected = person;
            this.pdAddresses = [];
            this.pdDetailLoading = true;
            try {
                const [detailRes, addrRes] = await Promise.all([
                    NSSAuth.apiFetch(`/api/v1/person/persons/${person.person_pk}`),
                    NSSAuth.apiFetch(`/api/v1/person/persons/${person.person_pk}/addresses`),
                ]);
                if (detailRes.ok) this.pdSelected = await detailRes.json();
                if (addrRes.ok) this.pdAddresses = await addrRes.json();
            } catch { /* keep summary on failure */ } finally {
                this.pdDetailLoading = false;
            }
        },

        pdFullName(p) {
            return [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" ");
        },

        // ═══════════════════════════════════════════════════════
        //  MEMBER DIRECTORY  (Tier-4 parity — replaces /membership page)
        // ═══════════════════════════════════════════════════════
        mdMembers: [],
        mdTotal: 0,
        mdLoading: false,
        mdError: "",
        mdTypeFilter: "",
        mdStatusFilter: "",
        mdOrgTypeFilter: "",
        mdOrgFilter: "",
        mdTypeOptions: [],
        mdStatusOptions: [],
        // No mdOrgTypeOptions — the Org Type dropdown reads the shared
        // `selectableOrgTypes` getter instead of a private copy.
        mdOrgOptions: [],
        mdOrgsLoading: false,
        mdSelected: null,
        mdDetailLoading: false,
        mdAffiliations: [],
        mdParichaya: [],
        mdAnumati: [],
        mdJourney: [],
        mdOptionsLoaded: false,

        // Patra number correction (MBR-030H, admin-only). type is
        // 'parichaya' or 'anumati'; pk is that record's own PK, used to
        // key which inline form (if any) is open across both lists.
        patraCorrect: { type: null, pk: null, value: "", reason: "", loading: false, error: "" },

        // Member Directory sorting — server-side for the same reason as the
        // Person Directory: the response is capped, so the browser never
        // holds the whole list.
        mdSortBy: "",
        mdSortDir: "asc",

        sortMemberDir(key) {
            const next = NSS.toggleSort(this.mdSortBy, this.mdSortDir, key);
            this.mdSortBy = next.key;
            this.mdSortDir = next.dir;
            this.fetchMemberDirectory();
        },

        async loadMemberDirectory() {
            if (!this.mdOptionsLoaded) {
                this.mdOptionsLoaded = true;
                // Organization types are NOT fetched here — loadOrgTypes()
                // already populates `orgTypes` from init(), and the Org Type
                // dropdown reads it through `selectableOrgTypes`. Fetching a
                // second private copy is what let this filter's option list
                // drift out of step with the Organizations list filter.
                const [t, s] = await Promise.all([
                    NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=MEMBERSHIP_TYPE")
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=STATUS")
                        .then(r => r.ok ? r.json() : []).catch(() => []),
                    this.loadOrgTypes(),
                ]);
                this.mdTypeOptions = t;
                this.mdStatusOptions = s;
                await this.mdLoadOrgs();
            }
            await this.fetchMemberDirectory();
        },

        // Load the Org Name dropdown, scoped to the selected Org Type (if any).
        async mdLoadOrgs() {
            this.mdOrgsLoading = true;
            try {
                const params = new URLSearchParams({ page_size: 200 });
                if (this.mdOrgTypeFilter) params.set("type_code", this.mdOrgTypeFilter);
                const res = await NSSAuth.apiFetch(`/api/v1/admin/organizations?${params}`);
                if (res.ok) {
                    const data = await res.json();
                    this.mdOrgOptions = data.organizations || [];
                } else {
                    this.mdOrgOptions = [];
                }
            } catch {
                this.mdOrgOptions = [];
            } finally {
                this.mdOrgsLoading = false;
            }
        },

        /**
         * The Org Name dropdown is only a meaningful choice once an Org
         * Type narrows it, and it stops being a choice at all when the
         * chosen type has exactly one organization.
         *
         *   no type selected ("All") → disabled. Picking one name out of
         *     every organization of every type is not a filter the
         *     directory is built around, and it contradicts the Org Type
         *     field sitting right next to it reading "All".
         *   type with exactly one org (today only KENDRA, whose sole
         *     organization is Nilachala Saraswata Sangha) → disabled,
         *     with that organization already selected by
         *     mdSyncSingletonOrg(). There is nothing to choose.
         *
         * Derived from the loaded option list rather than a hardcoded
         * type list, so it stays correct if the seed changes.
         */
        get mdOrgSelectDisabled() {
            if (this.mdOrgsLoading) return true;
            if (!this.mdOrgTypeFilter) return true;
            return this.mdOrgOptions.length === 1;
        },

        /**
         * Hint shown under the Org Name dropdown explaining why it is
         * locked, so a disabled control never looks like a bug.
         */
        get mdOrgSelectHint() {
            if (this.mdOrgsLoading) return "";
            if (!this.mdOrgTypeFilter) return "Select an Org Type first";
            if (this.mdOrgOptions.length === 1) return "Only one organization of this type";
            return "";
        },

        /**
         * When the selected Org Type has exactly one organization, select
         * it automatically — the user's only possible answer.
         */
        mdSyncSingletonOrg() {
            if (this.mdOrgTypeFilter && this.mdOrgOptions.length === 1) {
                this.mdOrgFilter = this.mdOrgOptions[0].organization_code;
            } else if (!this.mdOrgTypeFilter) {
                this.mdOrgFilter = "";
            }
        },

        // Org Type changed → reset the Org Name selection, reload the org list,
        // re-apply the singleton auto-select, refetch.
        async mdOnOrgTypeChange() {
            this.mdOrgFilter = "";
            await this.mdLoadOrgs();
            this.mdSyncSingletonOrg();
            await this.fetchMemberDirectory();
        },

        /**
         * True when any Member Directory filter or sort is active.
         * Drives the Clear button's disabled state so the control is
         * visibly inert when there is nothing to clear.
         */
        get mdFiltersActive() {
            return Boolean(
                this.mdTypeFilter || this.mdStatusFilter ||
                this.mdOrgTypeFilter || this.mdOrgFilter || this.mdSortBy
            );
        },

        /**
         * Clear button — resets the Member Directory to its opening state:
         * all four filters, the sort order, and the open detail row.
         * mdOrgTypeFilter is cleared first so mdLoadOrgs() reloads the
         * unscoped organization list, otherwise the Org Name dropdown
         * would keep showing only the previously selected type's orgs.
         */
        async clearMemberDirFilters() {
            this.mdTypeFilter = "";
            this.mdStatusFilter = "";
            this.mdOrgTypeFilter = "";
            this.mdOrgFilter = "";
            this.mdSortBy = "";
            this.mdSortDir = "asc";
            await this.mdLoadOrgs();
            this.mdSyncSingletonOrg();
            await this.fetchMemberDirectory();
        },

        async fetchMemberDirectory() {
            this.mdLoading = true;
            this.mdError = "";
            this.mdSelected = null;
            try {
                const params = new URLSearchParams({ limit: NSS.MAX_PAGE_SIZE });
                if (this.mdTypeFilter) params.set("type_code", this.mdTypeFilter);
                if (this.mdStatusFilter) params.set("status_code", this.mdStatusFilter);
                if (this.mdOrgTypeFilter) params.set("org_type_code", this.mdOrgTypeFilter);
                if (this.mdOrgFilter) params.set("org_code", this.mdOrgFilter);
                if (this.mdSortBy) {
                    params.set("sort_by", this.mdSortBy);
                    params.set("sort_dir", this.mdSortDir);
                }
                const res = await NSSAuth.apiFetch(`/api/v1/membership/members?${params}`);
                if (res.status === 403) { this.mdError = "You do not have permission to view members."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                this.mdMembers = data.members;
                this.mdTotal = data.total;
            } catch (err) {
                this.mdError = err.message || "Failed to load members.";
            } finally {
                this.mdLoading = false;
            }
        },

        async viewMember(member) {
            // Toggle: clicking the already-selected row closes it.
            this.cancelPatraCorrect();
            if (this.mdSelected && this.mdSelected.sangha_sevi_pk === member.sangha_sevi_pk) {
                this.mdSelected = null;
                this.mdAffiliations = [];
                this.mdParichaya = [];
                this.mdAnumati = [];
                this.mdJourney = [];
                return;
            }
            this.mdSelected = member;
            this.mdAffiliations = [];
            this.mdParichaya = [];
            this.mdAnumati = [];
            this.mdJourney = [];
            this.mdDetailLoading = true;
            const pk = member.sangha_sevi_pk;
            try {
                const [aff, pp, ap, jr] = await Promise.all([
                    NSSAuth.apiFetch(`/api/v1/membership/members/${pk}/affiliations`).then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/membership/members/${pk}/parichaya-patra`).then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/membership/members/${pk}/anumati-patra`).then(r => r.ok ? r.json() : []).catch(() => []),
                    NSSAuth.apiFetch(`/api/v1/membership/members/${pk}/journey`).then(r => r.ok ? r.json() : []).catch(() => []),
                ]);
                this.mdAffiliations = aff;
                this.mdParichaya = pp;
                this.mdAnumati = ap;
                this.mdJourney = jr;
            } catch { /* non-fatal */ } finally {
                this.mdDetailLoading = false;
            }
        },

        mdMemberName(m) {
            return [m.first_name, m.middle_name, m.last_name].filter(Boolean).join(" ");
        },

        // ── Patra number correction (MBR-030H, admin-only) ──────────────
        // Reaches PATCH /api/v1/admin/patra/{type}/{pk}/document-number
        // (api/routers/admin.py). The backend re-validates the number
        // against the Patra's own issue_date and enforces the actor's
        // scope — this form just surfaces that capability.
        openPatraCorrect(type, p) {
            const pk = type === "parichaya" ? p.parichaya_patra_pk : p.anumati_patra_pk;
            this.patraCorrect = { type, pk, value: p.document_number || "", reason: "", loading: false, error: "" };
        },

        cancelPatraCorrect() {
            this.patraCorrect = { type: null, pk: null, value: "", reason: "", loading: false, error: "" };
        },

        async savePatraCorrect() {
            const { type, pk, value, reason } = this.patraCorrect;
            if (!value.trim()) return;
            this.patraCorrect.loading = true;
            this.patraCorrect.error = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/admin/patra/${type}/${pk}/document-number`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        document_number: value.trim(),
                        reason: reason.trim() ? reason.trim() : null,
                    }),
                });
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const updated = await res.json();
                const list = type === "parichaya" ? this.mdParichaya : this.mdAnumati;
                const pkField = type === "parichaya" ? "parichaya_patra_pk" : "anumati_patra_pk";
                const row = list.find(p => p[pkField] === pk);
                if (row) row.document_number = updated.document_number;
                this.cancelPatraCorrect();
            } catch (err) {
                this.patraCorrect.error = err.message || "Failed to correct the number.";
            } finally {
                this.patraCorrect.loading = false;
            }
        },

        // ═══════════════════════════════════════════════════════
        //  MEMBER CREDENTIALS  (MBR-010 / MBR-019B / MBR-030H)
        //  GET /api/v1/admin/credentials/members[...]/timeline
        //  POST .../issue, POST .../promote
        // ═══════════════════════════════════════════════════════
        credsMembers: [],
        credsTotal: 0,
        credsPage: 1,
        credsPageSize: 50,
        credsLoading: false,
        credsError: "",
        credsSearch: "",
        credsStateFilter: "",
        credsTypeFilter: "",
        credsLapsedCount: 0,

        async loadCredentials(page = 1) {
            this.credsPage = page;
            this.credsLoading = true;
            this.credsError = "";
            try {
                const params = new URLSearchParams({ page: this.credsPage, page_size: this.credsPageSize });
                if (this.credsSearch.trim()) params.set("search", this.credsSearch.trim());
                if (this.credsStateFilter) params.set("state", this.credsStateFilter);
                if (this.credsTypeFilter) params.set("membership_type", this.credsTypeFilter);
                const res = await NSSAuth.apiFetch(`/api/v1/admin/credentials/members?${params}`);
                if (res.status === 403) { this.credsError = "You do not have permission to view member credentials."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                this.credsMembers = data.members;
                this.credsTotal = data.total;
            } catch (err) {
                this.credsError = err.message || "Failed to load member credentials.";
            } finally {
                this.credsLoading = false;
            }
            this.refreshCredsLapsedCount();
        },

        async refreshCredsLapsedCount() {
            // Lightweight nav-badge count — reuses the same list endpoint
            // rather than standing up a second summary endpoint.
            try {
                const res = await NSSAuth.apiFetch("/api/v1/admin/credentials/members?state=LAPSED&page=1&page_size=1");
                if (res.ok) {
                    const data = await res.json();
                    this.credsLapsedCount = data.total;
                }
            } catch { /* non-fatal — badge just stays at its last value */ }
        },

        clearCredentialFilters() {
            this.credsSearch = "";
            this.credsStateFilter = "";
            this.credsTypeFilter = "";
            this.loadCredentials(1);
        },

        // ── Credential Timeline viewer ───────────────────────────
        showCredTimelineModal: false,
        credTimelineMember: null,
        credTimelineEntries: [],
        credTimelineLoading: false,
        credTimelineError: "",

        async openCredentialTimeline(m) {
            this.credTimelineMember = m;
            this.credTimelineEntries = [];
            this.credTimelineError = "";
            this.credTimelineLoading = true;
            this.showCredTimelineModal = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/admin/credentials/members/${m.sangha_sevi_pk}/timeline`);
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                this.credTimelineEntries = data.entries;
            } catch (err) {
                this.credTimelineError = err.message || "Failed to load the credential timeline.";
            } finally {
                this.credTimelineLoading = false;
            }
        },

        // ── Issue / renew credential ──────────────────────────────
        showIssueCredentialModal: false,
        issueCredMember: null,
        issueCredForm: { document_number: "", president_override: false, remarks: "" },
        issueCredLoading: false,
        issueCredError: "",

        openIssueCredentialModal(m) {
            this.issueCredMember = m;
            this.issueCredForm = { document_number: "", president_override: false, remarks: "" };
            this.issueCredError = "";
            this.showIssueCredentialModal = true;
        },

        async submitIssueCredential() {
            this.issueCredLoading = true;
            this.issueCredError = "";
            try {
                const body = {
                    document_number: this.issueCredForm.document_number.trim() || null,
                    president_override: !!this.issueCredForm.president_override,
                    remarks: this.issueCredForm.remarks.trim() || null,
                };
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/credentials/members/${this.issueCredMember.sangha_sevi_pk}/issue`,
                    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
                );
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.showIssueCredentialModal = false;
                await this.loadCredentials(this.credsPage);
            } catch (err) {
                this.issueCredError = err.message || "Failed to issue the credential.";
            } finally {
                this.issueCredLoading = false;
            }
        },

        // ── Promote Darshaka → Regular ────────────────────────────
        showPromoteModal: false,
        promoteMember: null,
        promoteForm: { effective_date: "", document_number: "", remarks: "" },
        promoteLoading: false,
        promoteError: "",

        openPromoteModal(m) {
            this.promoteMember = m;
            this.promoteForm = { effective_date: "", document_number: "", remarks: "" };
            this.promoteError = "";
            this.showPromoteModal = true;
        },

        async submitPromote() {
            this.promoteLoading = true;
            this.promoteError = "";
            try {
                const body = {
                    effective_date: this.promoteForm.effective_date || null,
                    document_number: this.promoteForm.document_number.trim() || null,
                    remarks: this.promoteForm.remarks.trim() || null,
                };
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/credentials/members/${this.promoteMember.sangha_sevi_pk}/promote`,
                    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
                );
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.showPromoteModal = false;
                await this.loadCredentials(this.credsPage);
            } catch (err) {
                this.promoteError = err.message || "Failed to promote this member.";
            } finally {
                this.promoteLoading = false;
            }
        },

        // ═══════════════════════════════════════════════════════
        //  REFERENCE DATA  (Tier-1 parity — master data + documents)
        // ═══════════════════════════════════════════════════════
        rdCategories: [],
        rdSelectedCategory: "",
        rdValues: [],
        rdLoading: false,
        rdValuesLoading: false,
        rdError: "",
        rdDocuments: [],
        rdDocsLoading: false,
        rdView: "master",   // master | documents

        async loadReferenceData() {
            // Refetches on EVERY tab open. This used to latch on a one-shot
            // `rdLoaded` flag, so the tab kept showing whatever was fetched
            // the first time it was opened until the user pressed F5. The
            // only guard now is against a concurrent in-flight request.
            if (this.rdLoading) return;
            this.rdLoading = true;
            this.rdError = "";
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/categories");
                if (res.status === 403) { this.rdError = "You do not have permission to view reference data."; return; }
                if (res.ok) this.rdCategories = await res.json();
            } catch (err) {
                this.rdError = "Failed to load categories.";
            } finally {
                this.rdLoading = false;
            }
            // Keep the visible pane in step: re-pull whichever sub-view is
            // on screen, otherwise the categories refresh but the rows below
            // them stay stale.
            if (this.rdView === "documents") {
                await this.loadDocuments();
            } else if (this.rdSelectedCategory) {
                await this.loadMasterValues();
            }
        },

        async loadMasterValues() {
            this.rdValues = [];
            if (!this.rdSelectedCategory) return;
            this.rdValuesLoading = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/foundation/master-data?category_code=${encodeURIComponent(this.rdSelectedCategory)}`);
                if (res.ok) this.rdValues = await res.json();
            } catch { /* non-fatal */ } finally {
                this.rdValuesLoading = false;
            }
        },

        async loadDocuments() {
            // In-flight guard only — was `if (this.rdDocuments.length) return;`,
            // which permanently froze the document list after its first load.
            if (this.rdDocsLoading) return;
            this.rdDocsLoading = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/documents");
                if (res.ok) this.rdDocuments = await res.json();
            } catch { /* non-fatal */ } finally {
                this.rdDocsLoading = false;
            }
        },

        // ── Master-data value add/edit modal ────────────────────────
        mdModalOpen: false,
        mdModalMode: "edit",     // "edit" | "add"
        mdModalSaving: false,
        mdModalError: "",
        mdForm: { master_data_pk: "", category_code: "", value_code: "", value_name: "", description: "", display_order: 0 },
        mdExamples: [],          // existing values of the selected category, used as live examples
        mdExamplesLoading: false,

        openAddValue() {
            this.mdModalMode = "add";
            this.mdModalError = "";
            this.mdExamples = [];
            this.mdForm = {
                master_data_pk: "",
                category_code: this.rdSelectedCategory || "",
                value_code: "",
                value_name: "",
                description: "",
                display_order: 0,
            };
            this.mdModalOpen = true;
            if (this.mdForm.category_code) this.mdLoadExamples();
        },

        // Load a few existing values from the chosen category to show as live examples.
        async mdLoadExamples() {
            this.mdExamples = [];
            const cat = (this.mdForm.category_code || "").trim();
            if (!cat) return;
            this.mdExamplesLoading = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/foundation/master-data?category_code=${encodeURIComponent(cat)}`);
                if (res.ok) {
                    const vals = await res.json();
                    this.mdExamples = vals.slice(0, 3).map(v => ({ value_code: v.value_code, value_name: v.value_name }));
                }
            } catch { /* non-fatal */ } finally {
                this.mdExamplesLoading = false;
            }
        },

        mdCodePlaceholder() {
            return this.mdExamples.length ? ("e.g. " + this.mdExamples[0].value_code) : "e.g. ID_PROOF";
        },
        mdNamePlaceholder() {
            return this.mdExamples.length ? ("e.g. " + this.mdExamples[0].value_name) : "e.g. Identity Proof";
        },
        mdExamplesHint() {
            if (!this.mdExamples.length) return "";
            return "Existing values: " + this.mdExamples.map(e => `${e.value_code} — ${e.value_name}`).join(", ");
        },

        openEditValue(v) {
            this.mdModalMode = "edit";
            this.mdModalError = "";
            this.mdForm = {
                master_data_pk: v.master_data_pk,
                category_code: v.category_code,
                value_code: v.value_code,
                value_name: v.value_name,
                description: v.description || "",
                display_order: v.display_order ?? 0,
            };
            this.mdModalOpen = true;
        },

        closeMdModal() {
            this.mdModalOpen = false;
        },

        async saveMasterData() {
            this.mdModalError = "";
            const name = (this.mdForm.value_name || "").trim();
            if (!name) { this.mdModalError = "Value name is required."; return; }
            if (this.mdModalMode === "add") {
                if (!(this.mdForm.category_code || "").trim()) { this.mdModalError = "Category is required."; return; }
                if (!(this.mdForm.value_code || "").trim()) { this.mdModalError = "Value code is required."; return; }
            }
            const order = parseInt(this.mdForm.display_order, 10);
            this.mdModalSaving = true;
            try {
                let res;
                if (this.mdModalMode === "add") {
                    res = await NSSAuth.apiFetch("/api/v1/foundation/master-data", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            category_code: this.mdForm.category_code.trim(),
                            value_code: this.mdForm.value_code.trim(),
                            value_name: name,
                            description: this.mdForm.description.trim() || null,
                            display_order: Number.isNaN(order) ? 0 : order,
                        }),
                    });
                } else {
                    res = await NSSAuth.apiFetch(`/api/v1/foundation/master-data/${encodeURIComponent(this.mdForm.master_data_pk)}`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            value_name: name,
                            description: this.mdForm.description.trim(),
                            display_order: Number.isNaN(order) ? 0 : order,
                        }),
                    });
                }
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.mdModalError = NSS.errorMessage(data, res.status);
                    return;
                }
                // Ensure the list reflects the category we just changed
                if (this.mdModalMode === "add") this.rdSelectedCategory = this.mdForm.category_code.trim();
                this.mdModalOpen = false;
                await this.loadMasterValues();
                this.showToast(this.mdModalMode === "add" ? "Value added." : "Value updated.");
            } catch (err) {
                this.mdModalError = err.message || "Failed to save value.";
            } finally {
                this.mdModalSaving = false;
            }
        },

        // ═══════════════════════════════════════════════════════
        //  SYSTEM SETTINGS  (Tier-1 parity — settings + sequences)
        // ═══════════════════════════════════════════════════════
        ssSettings: [],
        ssSequences: [],
        ssSettingsLoading: false,
        ssError: "",

        async loadSystemSettings() {
            // Always refetch on tab open (was latched behind a one-shot
            // `ssLoaded`). reloadSettings() already has its own in-flight
            // flag, so a double-click can't fire two overlapping loads.
            if (this.ssSettingsLoading) return;
            await this.reloadSettings();
        },

        async reloadSettings() {
            this.ssSettingsLoading = true;
            try {
                const [setRes, seqRes] = await Promise.all([
                    NSSAuth.apiFetch("/api/v1/foundation/settings"),
                    NSSAuth.apiFetch("/api/v1/foundation/sequences"),
                ]);
                if (setRes.status === 403 || seqRes.status === 403) {
                    this.ssError = "You do not have permission to view system settings.";
                    return;
                }
                if (setRes.ok) this.ssSettings = await setRes.json();
                if (seqRes.ok) this.ssSequences = await seqRes.json();
            } catch (err) {
                this.ssError = "Failed to load system settings.";
            } finally {
                this.ssSettingsLoading = false;
            }
        },

        // ── Setting add/edit modal ──────────────────────────────────
        ssModalOpen: false,
        ssModalMode: "edit",     // "edit" | "add"
        ssModalSaving: false,
        ssModalError: "",
        ssForm: { setting_key: "", setting_value: "", description: "", data_type: "STRING" },

        openEditSetting(s) {
            this.ssModalMode = "edit";
            this.ssModalError = "";
            this.ssForm = {
                setting_key: s.setting_key,
                setting_value: s.setting_value,
                description: s.description || "",
                data_type: s.data_type || "STRING",
            };
            this.ssModalOpen = true;
        },

        openAddSetting() {
            this.ssModalMode = "add";
            this.ssModalError = "";
            this.ssForm = { setting_key: "", setting_value: "", description: "", data_type: "STRING" };
            this.ssModalOpen = true;
        },

        closeSettingModal() {
            this.ssModalOpen = false;
        },

        async saveSetting() {
            this.ssModalError = "";
            const val = (this.ssForm.setting_value || "").trim();
            if (!val) { this.ssModalError = "Value is required."; return; }
            if (this.ssModalMode === "add" && !(this.ssForm.setting_key || "").trim()) {
                this.ssModalError = "Key is required."; return;
            }
            this.ssModalSaving = true;
            try {
                let res;
                if (this.ssModalMode === "add") {
                    res = await NSSAuth.apiFetch("/api/v1/foundation/settings", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            setting_key: this.ssForm.setting_key.trim(),
                            setting_value: val,
                            data_type: this.ssForm.data_type,
                            description: this.ssForm.description.trim() || null,
                        }),
                    });
                } else {
                    res = await NSSAuth.apiFetch(`/api/v1/foundation/settings/${encodeURIComponent(this.ssForm.setting_key)}`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            setting_value: val,
                            description: this.ssForm.description.trim() || null,
                        }),
                    });
                }
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.ssModalError = NSS.errorMessage(data, res.status);
                    return;
                }
                this.ssModalOpen = false;
                await this.reloadSettings();
                this.showToast(this.ssModalMode === "add" ? "Setting added." : "Setting updated.");
            } catch (err) {
                this.ssModalError = err.message || "Failed to save setting.";
            } finally {
                this.ssModalSaving = false;
            }
        },

        // ── Sequence add/edit modal ─────────────────────────────────
        seqModalOpen: false,
        seqModalMode: "edit",     // "edit" | "add"
        seqModalSaving: false,
        seqModalError: "",
        seqForm: { sequence_code: "", sequence_name: "", prefix: "", padding_length: 8, description: "" },

        openEditSequence(q) {
            this.seqModalMode = "edit";
            this.seqModalError = "";
            this.seqForm = {
                sequence_code: q.sequence_code,
                sequence_name: q.sequence_name || "",
                prefix: q.prefix || "",
                padding_length: (q.padding_length ?? 0),
                description: q.description || "",
            };
            this.seqModalOpen = true;
        },

        openAddSequence() {
            this.seqModalMode = "add";
            this.seqModalError = "";
            this.seqForm = { sequence_code: "", sequence_name: "", prefix: "", padding_length: 8, description: "" };
            this.seqModalOpen = true;
        },

        closeSequenceModal() {
            this.seqModalOpen = false;
        },

        // Preview of the next identifier the sequence would mint, e.g. SKH00001.
        seqPreview() {
            const p = (this.seqForm.prefix || "").trim().toUpperCase();
            const pad = Number(this.seqForm.padding_length) || 0;
            return p + String(1).padStart(pad, "0");
        },

        async saveSequence() {
            this.seqModalError = "";
            const name = (this.seqForm.sequence_name || "").trim();
            const prefix = (this.seqForm.prefix || "").trim();
            const pad = Number(this.seqForm.padding_length);
            if (!name) { this.seqModalError = "Sequence name is required."; return; }
            if (!prefix) { this.seqModalError = "Prefix is required."; return; }
            if (!Number.isInteger(pad) || pad < 0 || pad > 12) {
                this.seqModalError = "Padding must be a whole number between 0 and 12."; return;
            }
            if (this.seqModalMode === "add" && !(this.seqForm.sequence_code || "").trim()) {
                this.seqModalError = "Sequence code is required."; return;
            }
            this.seqModalSaving = true;
            try {
                let res;
                if (this.seqModalMode === "add") {
                    res = await NSSAuth.apiFetch("/api/v1/foundation/sequences", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            sequence_code: this.seqForm.sequence_code.trim(),
                            sequence_name: name,
                            prefix: prefix,
                            padding_length: pad,
                            description: this.seqForm.description.trim() || null,
                        }),
                    });
                } else {
                    res = await NSSAuth.apiFetch(`/api/v1/foundation/sequences/${encodeURIComponent(this.seqForm.sequence_code)}`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            sequence_name: name,
                            prefix: prefix,
                            padding_length: pad,
                            description: this.seqForm.description.trim() || null,
                        }),
                    });
                }
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.seqModalError = NSS.errorMessage(data, res.status);
                    return;
                }
                this.seqModalOpen = false;
                await this.reloadSettings();
                this.showToast(this.seqModalMode === "add" ? "Sequence added." : "Sequence updated.");
            } catch (err) {
                this.seqModalError = err.message || "Failed to save sequence.";
            } finally {
                this.seqModalSaving = false;
            }
        },

        // ═══════════════════════════════════════════════════════
        //  FESTIVAL CALENDAR  (SOL-ARCH-013) — nss.festival_calendar_date
        // ═══════════════════════════════════════════════════════
        fcDates: [],
        fcFestivals: [],
        fcLoading: false,
        fcError: "",
        fcFilterYear: "",

        async loadFestivalCalendar() {
            if (this.fcLoading) return;
            this.fcLoading = true;
            this.fcError = "";
            try {
                const [fRes, dRes] = await Promise.all([
                    NSSAuth.apiFetch("/api/v1/foundation/festivals"),
                    NSSAuth.apiFetch("/api/v1/foundation/festival-calendar-dates"),
                ]);
                if (fRes.status === 403 || dRes.status === 403) {
                    this.fcError = "You do not have permission to view the festival calendar.";
                    return;
                }
                if (fRes.ok) this.fcFestivals = await fRes.json();
                if (dRes.ok) this.fcDates = await dRes.json();
            } catch (err) {
                this.fcError = "Failed to load the festival calendar.";
            } finally {
                this.fcLoading = false;
            }
        },

        get fcDatesFiltered() {
            if (!this.fcFilterYear) return this.fcDates;
            const y = Number(this.fcFilterYear);
            return this.fcDates.filter(d => d.calendar_year === y);
        },

        // ── Add/edit modal ──────────────────────────────────────────
        fcModalOpen: false,
        fcModalMode: "edit",     // "edit" | "add"
        fcModalSaving: false,
        fcModalError: "",
        fcForm: {
            festival_calendar_date_pk: null, festival_code: "DOLA_PURNIMA",
            calendar_year: new Date().getFullYear(), observed_date: "",
            is_confirmed: false, source_reference: "", remarks: "",
        },

        openAddFestivalDate() {
            this.fcModalMode = "add";
            this.fcModalError = "";
            this.fcForm = {
                festival_calendar_date_pk: null, festival_code: "DOLA_PURNIMA",
                calendar_year: new Date().getFullYear(), observed_date: "",
                is_confirmed: false, source_reference: "", remarks: "",
            };
            this.fcModalOpen = true;
        },

        openEditFestivalDate(d) {
            this.fcModalMode = "edit";
            this.fcModalError = "";
            this.fcForm = {
                festival_calendar_date_pk: d.festival_calendar_date_pk,
                festival_code: d.festival_code,
                calendar_year: d.calendar_year,
                observed_date: d.observed_date,
                is_confirmed: d.is_confirmed,
                source_reference: d.source_reference || "",
                remarks: d.remarks || "",
            };
            this.fcModalOpen = true;
        },

        closeFestivalDateModal() {
            this.fcModalOpen = false;
        },

        async saveFestivalDate() {
            this.fcModalError = "";
            if (!this.fcForm.observed_date) { this.fcModalError = "Observed date is required."; return; }
            const year = Number(this.fcForm.calendar_year);
            if (!Number.isInteger(year) || year < 1900 || year > 2200) {
                this.fcModalError = "Calendar year must be between 1900 and 2200."; return;
            }
            this.fcModalSaving = true;
            try {
                let res;
                if (this.fcModalMode === "add") {
                    res = await NSSAuth.apiFetch("/api/v1/foundation/festival-calendar-dates", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            festival_code: this.fcForm.festival_code,
                            calendar_year: year,
                            observed_date: this.fcForm.observed_date,
                            is_confirmed: !!this.fcForm.is_confirmed,
                            source_reference: this.fcForm.source_reference.trim() || null,
                            remarks: this.fcForm.remarks.trim() || null,
                        }),
                    });
                } else {
                    res = await NSSAuth.apiFetch(
                        `/api/v1/foundation/festival-calendar-dates/${encodeURIComponent(this.fcForm.festival_calendar_date_pk)}`,
                        {
                            method: "PATCH",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                observed_date: this.fcForm.observed_date,
                                is_confirmed: !!this.fcForm.is_confirmed,
                                source_reference: this.fcForm.source_reference.trim() || null,
                                remarks: this.fcForm.remarks.trim() || null,
                            }),
                        },
                    );
                }
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.fcModalError = NSS.errorMessage(data, res.status);
                    return;
                }
                this.fcModalOpen = false;
                await this.loadFestivalCalendar();
                this.showToast(this.fcModalMode === "add" ? "Festival date recorded." : "Festival date updated.");
            } catch (err) {
                this.fcModalError = err.message || "Failed to save festival date.";
            } finally {
                this.fcModalSaving = false;
            }
        },

        // One-click confirm from the list row — no need to open the modal
        // just to flip is_confirmed TRUE once the admin has verified the date.
        async confirmFestivalDate(d) {
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/foundation/festival-calendar-dates/${encodeURIComponent(d.festival_calendar_date_pk)}`,
                    {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ is_confirmed: true }),
                    },
                );
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.showToast(NSS.errorMessage(data, res.status), "error");
                    return;
                }
                await this.loadFestivalCalendar();
                this.showToast("Festival date confirmed.");
            } catch (err) {
                this.showToast("Failed to confirm festival date.", "error");
            }
        },

        // ═══════════════════════════════════════════════════════
        //  GEOGRAPHY  (Tier-1 parity — country → state → district → city)
        // ═══════════════════════════════════════════════════════
        geoCountries: [],
        geoStates: [],
        geoDistricts: [],
        geoCities: [],
        geoPostalCodes: [],
        geoSakhas: [],
        geoCountryPk: "",
        geoStatePk: "",
        geoDistrictPk: "",
        geoCityPk: "",
        geoPostalCodePk: "",
        geoLoading: false,
        geoError: "",
        geoPostalCodeQuery: "",
        geoCityQuery: "",
        geoSakhaQuery: "",
        // Set when a PIN filter returned zero cities/villages directly
        // anchored to it and we fell back to the district-wide list — see
        // geoSelectPostalCode(). This happens for any multi-PIN city whose
        // single city_village row is anchored to a different representative
        // PIN (uq_city_village_district_name forces one row per city per
        // district, so a city spanning many PINs — e.g. Bhubaneswar across
        // 751001-751030+ — only "owns" one of them in this table).
        geoCitiesFallbackNotice: "",

        // PIN search is SERVER-side. The API's ?q= matches the PIN digits only.
        geoPostalCodeSearching: false,

        // Post offices under the selected PIN (SOL-ARCH-010 Amendment,
        // 2026-10-03 — nss.post_office was reinstated: one PIN can carry
        // several offices, one HO plus several SO/BO). Loaded whenever a
        // PIN row is expanded; cleared when it's collapsed/deselected.
        geoPostOffices: [],
        geoPostOfficesLoading: false,

        async geoLoadPostOffices(postalCodePk) {
            if (!postalCodePk) { this.geoPostOffices = []; return; }
            this.geoPostOfficesLoading = true;
            try {
                this.geoPostOffices = await NSSAuth.apiFetch(`/api/v1/foundation/post-offices?postal_code_pk=${postalCodePk}`)
                    .then(r => r.ok ? r.json() : []).catch(() => []);
            } finally {
                this.geoPostOfficesLoading = false;
            }
        },

        // ── Location (geo-entry) approvals — FOUNDATION_MANAGE ──────────
        // Reviews member-proposed geographic values that landed PENDING via
        // the foundation "propose" endpoints (SOL-ARCH-010 Amendment).
        // Backend: api/routers/geo_approval.py, /api/v1/admin/geo-entries/{entity}.
        geoEntryEntity: "post-office",   // district | postal-code | post-office | city-village
        geoEntryStatus: "PENDING",       // PENDING | APPROVED | CORRECTED
        geoEntries: [],
        geoEntriesTotal: 0,
        geoEntriesLoading: false,
        geoEntriesError: "",
        geoEntriesPendingCount: 0,
        geoApproveBusyPk: null,
        geoCorrect: { pk: null, value: "", remarks: "", loading: false, error: "" },

        async loadGeoEntries() {
            this.geoEntriesLoading = true;
            this.geoEntriesError = "";
            this.cancelGeoCorrect();
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/geo-entries/${this.geoEntryEntity}?status=${this.geoEntryStatus}&page_size=100`);
                if (res.status === 403) {
                    this.geoEntriesError = "You do not have permission to review location entries.";
                    this.geoEntries = []; this.geoEntriesTotal = 0; return;
                }
                const data = res.ok ? await res.json() : { entries: [], total: 0 };
                this.geoEntries = data.entries || [];
                this.geoEntriesTotal = data.total || 0;
                if (this.geoEntryStatus === "PENDING") this.geoEntriesPendingCount = this.geoEntriesTotal;
            } catch (e) {
                this.geoEntriesError = "Failed to load location entries.";
            } finally {
                this.geoEntriesLoading = false;
            }
        },

        // Sidebar badge: total PENDING across all four entities. Errors
        // (incl. 403 for non-managers) are swallowed so the badge just
        // stays at 0 rather than surfacing noise on load.
        async loadGeoEntriesPendingCount() {
            const entities = ["district", "postal-code", "post-office", "city-village"];
            let total = 0;
            for (const ent of entities) {
                try {
                    const res = await NSSAuth.apiFetch(`/api/v1/admin/geo-entries/${ent}?status=PENDING&page_size=1`);
                    if (res.ok) { const d = await res.json(); total += (d.total || 0); }
                } catch (e) { /* ignore */ }
            }
            this.geoEntriesPendingCount = total;
        },

        setGeoEntryEntity(ent) { if (ent === this.geoEntryEntity) return; this.geoEntryEntity = ent; this.loadGeoEntries(); },
        setGeoEntryStatus(st) { if (st === this.geoEntryStatus) return; this.geoEntryStatus = st; this.loadGeoEntries(); },

        // Human label for an entry — the primary name/code column, whichever
        // this entity carries in its `value` dict.
        geoEntryLabel(e) {
            const v = (e && e.value) || {};
            return v.district_name || v.postal_code || v.post_office_name || v.city_village_name || "—";
        },

        // Which corrected_value key the backend expects for the current entity.
        geoEntryCorrectedKey() {
            return ({
                "district": "district_name",
                "postal-code": "postal_code",
                "post-office": "post_office_name",
                "city-village": "city_village_name",
            })[this.geoEntryEntity];
        },

        async approveGeoEntry(e) {
            this.geoApproveBusyPk = e.entry_pk;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/geo-entries/${this.geoEntryEntity}/${e.entry_pk}/approve`,
                    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.showToast("Location approved.", "success");
                await this.loadGeoEntries();
                this.loadGeoEntriesPendingCount();
            } catch (err) {
                this.showToast(err.message || "Approve failed.", "error");
            } finally {
                this.geoApproveBusyPk = null;
            }
        },

        openGeoCorrect(e) {
            this.geoCorrect = { pk: e.entry_pk, value: this.geoEntryLabel(e), remarks: "", loading: false, error: "" };
        },
        cancelGeoCorrect() {
            this.geoCorrect = { pk: null, value: "", remarks: "", loading: false, error: "" };
        },
        async saveGeoCorrect(e) {
            if (!this.geoCorrect.value.trim() || !this.geoCorrect.remarks.trim()) {
                this.geoCorrect.error = "Both the corrected value and a reason are required.";
                return;
            }
            this.geoCorrect.loading = true;
            this.geoCorrect.error = "";
            try {
                const corrected_value = {};
                corrected_value[this.geoEntryCorrectedKey()] = this.geoCorrect.value.trim();
                // Preserve the original city/village type on correction.
                if (this.geoEntryEntity === "city-village" && e.value && e.value.city_village_type) {
                    corrected_value.city_village_type = e.value.city_village_type;
                }
                const res = await NSSAuth.apiFetch(
                    `/api/v1/admin/geo-entries/${this.geoEntryEntity}/${e.entry_pk}/correct`,
                    { method: "POST", headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ corrected_value, admin_remarks: this.geoCorrect.remarks.trim() }) });
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.showToast("Location corrected.", "success");
                this.cancelGeoCorrect();
                await this.loadGeoEntries();
                this.loadGeoEntriesPendingCount();
            } catch (err) {
                this.geoCorrect.error = err.message || "Correction failed.";
            } finally {
                this.geoCorrect.loading = false;
            }
        },


        async geoSearchPostalCodes() {
            // Scope the search to the narrowest selected level. A selected
            // PIN is deliberately NOT part of the scope — you search to find
            // a different PIN, so narrowing by the current one is useless.
            let scope;
            if (this.geoDistrictPk) scope = `district_pk=${this.geoDistrictPk}`;
            else if (this.geoStatePk) scope = `state_pk=${this.geoStatePk}`;
            else if (this.geoCountryPk) scope = `country_pk=${this.geoCountryPk}`;
            else return;
            // The API enforces a 2-char minimum; below that just show the
            // unfiltered scope rather than firing a rejected request.
            const q = (this.geoPostalCodeQuery || "").trim();
            const qs = q.length >= 2 ? `${scope}&q=${encodeURIComponent(q)}` : scope;
            this.geoPostalCodeSearching = true;
            try {
                this.geoPostalCodes = await NSSAuth.apiFetch(`/api/v1/foundation/postal-codes?${qs}`)
                    .then(r => r.ok ? r.json() : []).catch(() => []);
            } finally {
                this.geoPostalCodeSearching = false;
            }
        },

        // Human-readable label for each level of the active scope, for the
        // breadcrumb above the three panels.
        geoScopeLabel(level) {
            if (level === "country") {
                const c = this.geoCountries.find(x => x.country_pk === this.geoCountryPk);
                return c ? c.country_name : "";
            }
            if (level === "state") {
                const s = this.geoStates.find(x => x.state_pk === this.geoStatePk);
                return s ? s.state_name : "";
            }
            if (level === "district") {
                const d = this.geoDistricts.find(x => x.district_pk === this.geoDistrictPk);
                return d ? d.district_name : "";
            }
            if (level === "pin") {
                const p = this.geoPostalCodes.find(x => x.postal_code_pk === this.geoPostalCodePk);
                return p ? p.postal_code : "";
            }
            return "";
        },

        // Unified, de-duplicated list of every unique location NAME under
        // the selected PIN (user decision, 2026-10-04). Merges city/village
        // names with post-office names, strips the office-type suffix
        // (S.O / B.O / H.O / G.P.O) so "Kalpana Square S.O" collapses onto
        // the city/village "Kalpana Square", and dedupes case-insensitively.
        // City/village names are added first so their (already clean) form
        // wins as the display label on a tie.
        geoUniqueNames() {
            const strip = (s) => (s || "")
                .replace(/\s*\b(?:S\.?O|B\.?O|H\.?O|G\.?P\.?O)\b\.?/gi, "")
                .replace(/\s{2,}/g, " ")
                .trim();
            const seen = new Map(); // lowercased clean name -> display form
            const add = (name) => {
                const clean = strip(name);
                if (!clean) return;
                const key = clean.toLowerCase();
                if (!seen.has(key)) seen.set(key, clean);
            };
            (this.geoCities || []).forEach(c => add(c.city_village_name));
            (this.geoPostOffices || []).forEach(p => add(p.post_office_name));
            return Array.from(seen.values()).sort((a, b) => a.localeCompare(b));
        },

        // A single Odisha district can hold thousands of villages
        // (e.g. Mayurbhanj: ~3,888) — filter by name or type first.
        geoFilteredCities() {            const q = (this.geoCityQuery || "").trim().toLowerCase();
            if (!q) return this.geoCities;
            return this.geoCities.filter(c =>
                (c.city_village_name || "").toLowerCase().includes(q) ||
                (c.city_village_type || "").toLowerCase().includes(q)
            );
        },

        // Sakha branches linked to a PIN in the selected state.
        geoFilteredSakhas() {
            const q = (this.geoSakhaQuery || "").trim().toLowerCase();
            if (!q) return this.geoSakhas;
            return this.geoSakhas.filter(s =>
                (s.organization_name || "").toLowerCase().includes(q) ||
                (s.organization_code || "").toLowerCase().includes(q) ||
                (s.postal_code || "").toLowerCase().includes(q) ||
                (s.state_name || "").toLowerCase().includes(q)
            );
        },

        async loadGeography() {
            // Always refetch on tab open (was latched behind `geoLoaded`).
            if (this.geoLoading) return;
            this.geoLoading = true;
            this.geoError = "";
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/countries");
                if (res.status === 403) { this.geoError = "You do not have permission to view geography data."; return; }
                if (res.ok) this.geoCountries = await res.json();
            } catch (err) {
                this.geoError = "Failed to load countries.";
            } finally {
                this.geoLoading = false;
            }
        },

        async geoSelectCountry(countryPk) {
            this.geoCountryPk = countryPk;
            this.geoStatePk = "";
            this.geoDistrictPk = "";
            this.geoCityPk = "";
            this.geoStates = [];
            this.geoDistricts = [];
            this.geoCities = [];
            this.geoPostalCodes = [];
            this.geoSakhas = [];
            if (!countryPk) return;
            // Only load the next level (states). Postal codes wait for a state selection.
            const res = await NSSAuth.apiFetch(`/api/v1/foundation/states?country_pk=${countryPk}`);
            this.geoStates = res.ok ? await res.json() : [];
        },

        async geoSelectState(statePk) {
            this.geoStatePk = statePk;
            this.geoDistrictPk = "";
            this.geoCityPk = "";
            this.geoPostalCodePk = "";
            this.geoDistricts = [];
            this.geoCities = [];
            this.geoPostalCodes = [];
            this.geoSakhas = [];
            this.geoPostalCodeQuery = "";
            this.geoCityQuery = "";
            this.geoSakhaQuery = "";
            if (!statePk) return;
            // Load this state's districts, its postal codes, and the Sakha
            // branches linked to those PINs (all scoped to the state).
            const [dist, pc, sk] = await Promise.all([
                NSSAuth.apiFetch(`/api/v1/foundation/districts?state_pk=${statePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                NSSAuth.apiFetch(`/api/v1/foundation/postal-codes?state_pk=${statePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                NSSAuth.apiFetch(`/api/v1/foundation/sakha-postal-codes?state_pk=${statePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
            ]);
            this.geoDistricts = dist;
            this.geoPostalCodes = pc;
            this.geoSakhas = sk;
        },

        // Picking a district now narrows all three panels together
        // (Cities/Villages, Postal Codes, Sakha Branches) instead of
        // leaving Postal Codes/Sakhas at state scope while only Cities
        // narrowed — the three were not actually "interconnected" before
        // this fix (SOL-ARCH-010 Amendment, 2026-10-01).
        async geoSelectDistrict(districtPk) {
            this.geoDistrictPk = districtPk;
            this.geoCityPk = "";
            this.geoPostalCodePk = "";
            this.geoCities = [];
            this.geoCityQuery = "";
            this.geoPostalCodeQuery = "";
            this.geoCitiesFallbackNotice = "";
            if (!districtPk) {
                // Cleared back to state scope — reload state-wide lists.
                if (this.geoStatePk) {
                    const [pc, sk] = await Promise.all([
                        NSSAuth.apiFetch(`/api/v1/foundation/postal-codes?state_pk=${this.geoStatePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                        NSSAuth.apiFetch(`/api/v1/foundation/sakha-postal-codes?state_pk=${this.geoStatePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                    ]);
                    this.geoPostalCodes = pc;
                    this.geoSakhas = sk;
                }
                return;
            }
            const [cv, pc, sk] = await Promise.all([
                NSSAuth.apiFetch(`/api/v1/foundation/cities?district_pk=${districtPk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                NSSAuth.apiFetch(`/api/v1/foundation/postal-codes?district_pk=${districtPk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                NSSAuth.apiFetch(`/api/v1/foundation/sakha-postal-codes?district_pk=${districtPk}`).then(r => r.ok ? r.json() : []).catch(() => []),
            ]);
            this.geoCities = cv;
            this.geoPostalCodes = pc;
            this.geoSakhas = sk;
        },

        // Completes the Geography cascade one level further: picking a
        // postal code (SOL-ARCH-010 Amendment, 2026-10-01 — postal_code_pk
        // is now the primary location anchor on city_village and on
        // organization) re-narrows both Cities/Villages and Sakha Branches
        // to that exact PIN, instead of leaving them at state/district scope.
        async geoSelectPostalCode(postalCodePk) {
            this.geoPostalCodePk = postalCodePk;
            this.geoCityQuery = "";
            this.geoSakhaQuery = "";
            this.geoCitiesFallbackNotice = "";
            this.geoLoadPostOffices(postalCodePk);
            if (!postalCodePk) {
                this.geoCityPk = "";
                // Cleared back to district/state scope. Defer entirely to
                // the district handler when a district is selected so all
                // three panels land back on the same scope together;
                // otherwise fall back to state-wide postal codes + sakhas.
                if (this.geoDistrictPk) {
                    await this.geoSelectDistrict(this.geoDistrictPk);
                } else {
                    this.geoCities = [];
                    if (this.geoStatePk) {
                        const [pc, sk] = await Promise.all([
                            NSSAuth.apiFetch(`/api/v1/foundation/postal-codes?state_pk=${this.geoStatePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                            NSSAuth.apiFetch(`/api/v1/foundation/sakha-postal-codes?state_pk=${this.geoStatePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                        ]);
                        this.geoPostalCodes = pc;
                        this.geoSakhas = sk;
                    }
                }
                return;
            }
            const [cv, sk] = await Promise.all([
                NSSAuth.apiFetch(`/api/v1/foundation/cities?postal_code_pk=${postalCodePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
                NSSAuth.apiFetch(`/api/v1/foundation/sakha-postal-codes?postal_code_pk=${postalCodePk}`).then(r => r.ok ? r.json() : []).catch(() => []),
            ]);
            if (cv.length === 0 && this.geoDistrictPk) {
                // No city/village row is directly anchored to this exact
                // PIN. Very common for a multi-PIN city/town — e.g. a PIN
                // like 751006 (one of Bhubaneswar's many post offices) when
                // Bhubaneswar's single city_village row is anchored to its
                // representative PIN 751001 instead. Fall back to the
                // district-wide list rather than showing a false "empty"
                // result, and say so.
                this.geoCities = await NSSAuth.apiFetch(`/api/v1/foundation/cities?district_pk=${this.geoDistrictPk}`)
                    .then(r => r.ok ? r.json() : []).catch(() => []);
                this.geoCitiesFallbackNotice =
                    "No city/village record is anchored to this exact PIN " +
                    "(common for a locality that spans several post offices) " +
                    "— showing all cities/villages in the selected district instead.";
            } else {
                this.geoCities = cv;
            }
            this.geoSakhas = sk;
        },

        // City/village selector that drives the PIN display: picking a
        // city/village focuses the whole Geography scope on its PIN —
        // highlighting that PIN row, listing its post offices, and
        // narrowing Sakha Branches. Clicking the already-selected
        // city clears the PIN scope. Cities with no resolved PIN are
        // inert (nothing to drive).
        async geoSelectCity(c) {
            if (!c || !c.postal_code_pk) {
                this.showToast("No PIN is mapped to this city/village yet.", "error");
                return;
            }
            const clearing = this.geoPostalCodePk === c.postal_code_pk;
            this.geoCityPk = clearing ? "" : c.city_village_pk;
            await this.geoSelectPostalCode(clearing ? "" : c.postal_code_pk);
        },

        // City/Village dropdown (cascade) counterpart to geoSelectCity():
        // x-model has already written the chosen city_village_pk to
        // geoCityPk, so resolve it against the loaded list and drive the
        // same PIN focus. Empty value ("All…") clears the PIN scope.
        async geoApplyCitySelection() {
            const pk = this.geoCityPk;
            if (!pk) {
                await this.geoSelectPostalCode("");
                return;
            }
            const c = this.geoCities.find(x => x.city_village_pk === pk);
            if (!c) return;
            if (!c.postal_code_pk) {
                this.showToast("No PIN is mapped to this city/village yet.", "error");
                return;
            }
            await this.geoSelectPostalCode(c.postal_code_pk);
        },

        // Re-fetch the Geography tab's PIN-scoped lists at whatever the
        // current drill scope is (PIN > district > state), without
        // disturbing the active selections. Called after an org edit so a
        // renamed/relocated branch reflects immediately on the Sakha
        // Branches panel. Cache-busted so a browser-cached GET can't serve
        // the pre-edit name back.
        async refreshGeoLists() {
            if (!this.geoStatePk) return;
            let scope;
            if (this.geoPostalCodePk) scope = `postal_code_pk=${this.geoPostalCodePk}`;
            else if (this.geoDistrictPk) scope = `district_pk=${this.geoDistrictPk}`;
            else scope = `state_pk=${this.geoStatePk}`;
            const bust = `&_=${Date.now()}`;
            this.geoSakhas = await NSSAuth.apiFetch(`/api/v1/foundation/sakha-postal-codes?${scope}${bust}`)
                .then(r => r.ok ? r.json() : this.geoSakhas).catch(() => this.geoSakhas);
        },


        // ═══════════════════════════════════════════════════════
        //  ORGANIZATION HIERARCHY  (Tier-2 parity — full tree)
        // ═══════════════════════════════════════════════════════
        orgTree: [],
        orgTreeLoading: false,
        orgTreeError: "",

        // Drill-down navigation state (breadcrumb of node objects; empty = top level)
        orgDrillPath: [],
        orgDrillSelect: "",

        async loadOrgHierarchy() {
            // Always refetch on tab open. This was latched behind
            // `orgTreeLoaded`, which two callers then had to manually
            // invalidate (`orgTreeLoaded = false`) after creating/reassigning
            // an org — a pattern that only worked for the mutations someone
            // remembered. Refetching unconditionally removes the need for
            // any invalidation bookkeeping.
            if (this.orgTreeLoading) return;
            this.orgTreeLoading = true;
            this.orgTreeError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/organization/hierarchy?limit=${NSS.MAX_PAGE_SIZE}`);
                if (res.status === 403) { this.orgTreeError = "You do not have permission to view the hierarchy."; return; }
                if (res.ok) this.orgTree = await res.json();
            } catch (err) {
                this.orgTreeError = "Failed to load hierarchy.";
            } finally {
                this.orgTreeLoading = false;
            }
        },

        // Direct children of a given parent pk (null pk = top-level roots)
        orgChildrenOf(parentPk) {
            return this.orgTree.filter(n => n.parent_organization_pk === parentPk);
        },
        // Nodes to display at the current drill level
        orgLevelNodes() {
            const parent = this.orgDrillPath.length ? this.orgDrillPath[this.orgDrillPath.length - 1] : null;
            return this.orgChildrenOf(parent ? parent.organization_pk : null);
        },
        orgChildCount(node) {
            return this.orgChildrenOf(node.organization_pk).length;
        },
        orgHasChildren(node) {
            return this.orgChildCount(node) > 0;
        },
        // Drill into a node (only if it has children)
        orgDrillInto(node) {
            if (!this.orgHasChildren(node)) return;
            this.orgDrillPath.push(node);
            this.orgDrillSelect = "";
        },
        // Jump via the dropdown selection (value = organization_pk)
        orgDrillPick() {
            if (!this.orgDrillSelect) return;
            const node = this.orgLevelNodes().find(n => n.organization_pk === this.orgDrillSelect);
            if (node) this.orgDrillInto(node);
            this.orgDrillSelect = "";
        },
        // Breadcrumb navigation: index -1 = top level, else truncate path to that node
        orgDrillTo(index) {
            this.orgDrillPath = index < 0 ? [] : this.orgDrillPath.slice(0, index + 1);
            this.orgDrillSelect = "";
        },

        // ═══════════════════════════════════════════════════════
        //  ASSIGN SAKHAS TO ANCHALIKA / ZILLA SANGHA
        // ═══════════════════════════════════════════════════════
        assignSakhaList: [],
        anchalikaZillaOptions: [],
        assignSakhaTarget: {},      // organization_pk -> selected new parent pk
        assignSakhaLoading: false,
        assignSakhaSaving: null,    // organization_pk currently being saved, or null
        assignSakhaError: "",
        assignSakhaSuccess: "",
        assignSakhaSearch: "",
        assignSakhaOnlyUnassigned: false,

        async loadAssignSakhaData() {
            // Always refetch on tab open. Latching this behind
            // `assignSakhaLoaded` meant a Sakha created in the Create
            // Organization tab never appeared here for the rest of the
            // session — submitCreateOrg() invalidated the hierarchy tree but
            // not this list.
            if (this.assignSakhaLoading) return;
            this.assignSakhaLoading = true;
            this.assignSakhaError = "";
            try {
                // Two different scopes on purpose (see the per-call comment
                // below): the SAKHA list uses the admin-scoped
                // /admin/organizations (you only re-parent Sakhas you
                // administer); the Anchalika/Zilla PARENT options use the
                // nationwide selectable list (a Sakha admin must be able to
                // pick any Anchalika as the new parent).
                // The SAKHA list (what you may RE-PARENT) stays admin-scoped
                // — you can only move Sakhas within your own admin scope.
                // But the Anchalika/Zilla PARENT options must be nationwide:
                // a Sakha admin's scope subtree is their own Sakha (downward
                // only), so the scoped /admin/organizations returns ZERO
                // Anchalikas and the parent dropdown was empty — a Sakha
                // admin literally could not assign their Sakha under a newly
                // created Anchalika (owner report, 2026-10-27). The valid
                // PARENTS are the whole NSS regardless of the caller's
                // downward scope, so the parent options come from the
                // authenticated-but-unscoped /organization/organizations/
                // selectable list (same source find-a-Sakha uses). The
                // backend PATCH (update_organization) authorizes the write on
                // the SAKHA being edited (in scope) and only validates the
                // parent's TYPE, not its scope — so this is purely restoring
                // the missing options, not widening write authority.
                const [sakhas, parentOrgs] = await Promise.all([
                    this._fetchAllAdminOrganizations("SAKHA_SANGHA"),
                    NSSAuth.apiFetch(
                        "/api/v1/organization/organizations/selectable?type_code=ANCHALIKA_SANGHA&type_code=ZILLA_SANGHA&limit=" + NSS.MAX_PAGE_SIZE
                    ).then(r => r.ok ? r.json() : []).catch(() => []),
                ]);
                this.assignSakhaList = sakhas;
                this.anchalikaZillaOptions = (parentOrgs || []).slice().sort(
                    (a, b) => a.organization_name.localeCompare(b.organization_name)
                );
                // Pre-select each row's dropdown to its current parent.
                const targets = {};
                for (const s of sakhas) targets[s.organization_pk] = s.parent_organization_pk || "";
                this.assignSakhaTarget = targets;
            } catch (err) {
                this.assignSakhaError = err.message || "Failed to load Sakha/Anchalika/Zilla organizations.";
            } finally {
                this.assignSakhaLoading = false;
            }
        },

        // Fetches every page of /api/v1/admin/organizations for one
        // organization type (page_size is capped at 200 server-side, below
        // NSS.MAX_PAGE_SIZE, so a single page can't be assumed complete).
        // Throws on a non-OK response so loadAssignSakhaData's catch can
        // report the failure the same way it did for the old bare-array
        // endpoint.
        async _fetchAllAdminOrganizations(typeCode) {
            const pageSize = 200;
            let page = 1;
            let all = [];
            while (true) {
                const params = new URLSearchParams({
                    type_code: typeCode,
                    page: String(page),
                    page_size: String(pageSize),
                });
                const res = await NSSAuth.apiFetch(`/api/v1/admin/organizations?${params}`);
                if (!res.ok) {
                    throw new Error(`Failed to load ${typeCode} organizations.`);
                }
                const data = await res.json();
                all = all.concat(data.organizations || []);
                if (all.length >= data.total || !(data.organizations || []).length) break;
                page += 1;
            }
            return all;
        },

        // A Sakha still parented directly under Kendra (i.e. not yet under
        // any Anchalika/Zilla Sangha) — the seed's initial flat state.
        isSakhaUnassigned(s) {
            return !this.anchalikaZillaOptions.some(p => p.organization_pk === s.parent_organization_pk);
        },

        filteredAssignSakhaList() {
            const q = this.assignSakhaSearch.trim().toLowerCase();
            return this.assignSakhaList.filter(s => {
                if (this.assignSakhaOnlyUnassigned && !this.isSakhaUnassigned(s)) return false;
                if (!q) return true;
                return s.organization_name.toLowerCase().includes(q)
                    || (s.organization_code || "").toLowerCase().includes(q);
            });
        },

        async assignSakhaToParent(s) {
            const newParentPk = this.assignSakhaTarget[s.organization_pk];
            if (!newParentPk || newParentPk === s.parent_organization_pk) return;
            this.assignSakhaSaving = s.organization_pk;
            this.assignSakhaError = "";
            this.assignSakhaSuccess = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/admin/organizations/${s.organization_pk}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ parent_organization_pk: newParentPk }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.assignSakhaError = NSS.errorMessage(data, res.status);
                    return;
                }
                const newParent = this.anchalikaZillaOptions.find(p => p.organization_pk === newParentPk);
                s.parent_organization_pk = newParentPk;
                s.parent_organization_name = newParent ? newParent.organization_name : s.parent_organization_name;
                this.assignSakhaSuccess = `${s.organization_name} assigned to ${s.parent_organization_name}.`;
                // The Organization Hierarchy tab's tree is now stale too;
                // loadOrgHierarchy() always refetches on tab open, so just
                // clear the cached tree to avoid a stale flash if it's visible.
                this.orgTree = [];
            } catch (err) {
                this.assignSakhaError = err.message || "Failed to assign organization.";
            } finally {
                this.assignSakhaSaving = null;
            }
        },

        // ── Governance (Tier 6): Body Types & Positions catalog ──

        async loadGovCatalog() {
            if (this.govCatalogLoading) return;
            this.govCatalogLoading = true;
            this.govCatalogError = "";
            try {
                const [bt, p] = await Promise.all([
                    NSSAuth.apiFetch("/api/v1/governance/body-types"),
                    NSSAuth.apiFetch("/api/v1/governance/positions"),
                ]);
                if (bt.status === 403 || p.status === 403) {
                    this.govCatalogError = "You do not have permission to view the Governance catalog.";
                    return;
                }
                this.govBodyTypes = bt.ok ? await bt.json() : [];
                this.govPositions = p.ok ? await p.json() : [];
            } catch (err) {
                this.govCatalogError = err.message || "Failed to load the Governance catalog.";
            } finally {
                this.govCatalogLoading = false;
            }
        },

        async createGovBodyType() {
            const f = this.govBodyTypeForm;
            f.error = "";
            if (!f.body_type_code.trim() || !f.body_type_name.trim()) {
                f.error = "Code and name are required.";
                return;
            }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/body-types", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        body_type_code: f.body_type_code.trim().toUpperCase(),
                        body_type_name: f.body_type_name.trim(),
                        description: f.description.trim() || null,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.govBodyTypes.push(await res.json());
                f.show = false;
                f.body_type_code = ""; f.body_type_name = ""; f.description = "";
            } catch (err) {
                f.error = err.message || "Failed to create body type.";
            } finally {
                f.saving = false;
            }
        },

        startEditGovBodyType(bt) {
            this.govBodyTypeEdit = {
                pk: bt.body_type_master_pk, body_type_name: bt.body_type_name,
                description: bt.description || "", saving: false, error: "",
            };
        },

        async saveGovBodyType() {
            const e = this.govBodyTypeEdit;
            e.saving = true; e.error = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/body-types/${e.pk}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ body_type_name: e.body_type_name.trim(), description: e.description.trim() || null }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    e.error = NSS.errorMessage(data, res.status);
                    return;
                }
                const updated = await res.json();
                const idx = this.govBodyTypes.findIndex(x => x.body_type_master_pk === e.pk);
                if (idx !== -1) this.govBodyTypes[idx] = updated;
                this.govBodyTypeEdit.pk = null;
            } catch (err) {
                e.error = err.message || "Failed to save body type.";
            } finally {
                e.saving = false;
            }
        },

        async createGovPosition() {
            const f = this.govPositionForm;
            f.error = "";
            if (!f.position_code.trim() || !f.position_name.trim()) {
                f.error = "Code and name are required.";
                return;
            }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/positions", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        position_code: f.position_code.trim().toUpperCase(),
                        position_name: f.position_name.trim(),
                        description: f.description.trim() || null,
                        display_order: Number(f.display_order) || 0,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.govPositions.push(await res.json());
                this.govPositions.sort((a, b) => a.display_order - b.display_order);
                f.show = false;
                f.position_code = ""; f.position_name = ""; f.description = ""; f.display_order = 0;
            } catch (err) {
                f.error = err.message || "Failed to create position.";
            } finally {
                f.saving = false;
            }
        },

        startEditGovPosition(p) {
            this.govPositionEdit = {
                pk: p.position_master_pk, position_name: p.position_name,
                description: p.description || "", display_order: p.display_order,
                saving: false, error: "",
            };
        },

        async saveGovPosition() {
            const e = this.govPositionEdit;
            e.saving = true; e.error = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/positions/${e.pk}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        position_name: e.position_name.trim(),
                        description: e.description.trim() || null,
                        display_order: Number(e.display_order) || 0,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    e.error = NSS.errorMessage(data, res.status);
                    return;
                }
                const updated = await res.json();
                const idx = this.govPositions.findIndex(x => x.position_master_pk === e.pk);
                if (idx !== -1) this.govPositions[idx] = updated;
                this.govPositions.sort((a, b) => a.display_order - b.display_order);
                this.govPositionEdit.pk = null;
            } catch (err) {
                e.error = err.message || "Failed to save position.";
            } finally {
                e.saving = false;
            }
        },

        // ── Governance: Bodies ────────────────────────────────────

        async loadGovBodies() {
            if (this.govBodiesLoading) return;
            this.govBodiesLoading = true;
            this.govBodiesError = "";
            try {
                if (this.govBodyTypes.length === 0) {
                    const bt = await NSSAuth.apiFetch("/api/v1/governance/body-types");
                    if (bt.ok) this.govBodyTypes = await bt.json();
                }
                // page_size is capped at 100 server-side (Query(..., le=100));
                // the endpoint has no body_type_master_pk filter, so that's
                // applied client-side below instead.
                const params = new URLSearchParams({ page: 1, page_size: 100 });
                const res = await NSSAuth.apiFetch(`/api/v1/governance/bodies?${params}`);
                if (res.status === 403) { this.govBodiesError = "You do not have permission to view Governance Bodies."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                this.govBodiesAll = data.items;
                this.govBodies = this.govBodyTypeFilter
                    ? data.items.filter(b => b.body_type_master_pk === this.govBodyTypeFilter)
                    : data.items;
                if (!this.govSelectedBodyPk && this.govBodiesAll.length) {
                    this.govSelectedBodyPk = this.govBodiesAll[0].body_master_pk;
                }
            } catch (err) {
                this.govBodiesError = err.message || "Failed to load Governance Bodies.";
            } finally {
                this.govBodiesLoading = false;
            }
        },

        async createGovBody() {
            const f = this.govBodyForm;
            f.error = "";
            if (!f.body_type_master_pk || !f.body_code.trim() || !f.body_name.trim()) {
                f.error = "Body type, code, and name are required.";
                return;
            }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/bodies", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        body_type_master_pk: f.body_type_master_pk,
                        body_code: f.body_code.trim().toUpperCase(),
                        body_name: f.body_name.trim(),
                        description: f.description.trim() || null,
                        organization_pk: f.organization_pk || null,
                        effective_from: f.effective_from || null,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                const created = await res.json();
                this.govBodies.push(created);
                this.govBodiesAll.push(created);
                f.show = false;
                f.body_type_master_pk = ""; f.body_code = ""; f.body_name = "";
                f.description = ""; f.organization_pk = ""; f.effective_from = "";
                f.orgQuery = ""; f.orgResults = []; f.selectedOrg = null;
            } catch (err) {
                f.error = err.message || "Failed to create Governance Body.";
            } finally {
                f.saving = false;
            }
        },

        startEditGovBody(b) {
            this.govBodyEdit = {
                pk: b.body_master_pk, body_name: b.body_name, description: b.description || "",
                body_status: b.body_status, effective_from: b.effective_from || "",
                effective_to: b.effective_to || "", saving: false, error: "",
            };
        },

        async saveGovBody() {
            const e = this.govBodyEdit;
            e.saving = true; e.error = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/bodies/${e.pk}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        body_name: e.body_name.trim(), description: e.description.trim() || null,
                        body_status: e.body_status || null,
                        effective_from: e.effective_from || null, effective_to: e.effective_to || null,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    e.error = NSS.errorMessage(data, res.status);
                    return;
                }
                const updated = await res.json();
                const idx = this.govBodies.findIndex(x => x.body_master_pk === e.pk);
                if (idx !== -1) this.govBodies[idx] = updated;
                const idxAll = this.govBodiesAll.findIndex(x => x.body_master_pk === e.pk);
                if (idxAll !== -1) this.govBodiesAll[idxAll] = updated;
                this.govBodyEdit.pk = null;
            } catch (err) {
                e.error = err.message || "Failed to save Governance Body.";
            } finally {
                e.saving = false;
            }
        },

        // Body types an admin may manually create via "Add Body". Kendra
        // Governing Body / Advisory Board / the central Mahila Parichalana
        // Mandali are NSS-wide singletons that are auto-created by the
        // 03_body_master.sql seed instead (owner-confirmed 2026-10-07) —
        // they never appear in this picker. Everything else (Sakha
        // Governing Body, per-Sakha Mahila Parichalana Mandali, Sevak
        // Sangha Executive — Sakha level only) stays manually creatable.
        get govBodyTypesCreatable() {
            return this.govBodyTypes.filter(bt => !["KENDRA_GOVERNING_BODY", "ADVISORY_BOARD"].includes(bt.body_type_code));
        },

        // Auto-fills Code/Name from the chosen Body Type so the admin
        // doesn't have to invent either by hand. For NSS-wide singleton
        // types (Kendra Governing Body / Advisory Board) the type's own
        // name/code IS the body's name/code — there's only ever one.
        // For per-organization types, this prefills with just the type's
        // code/name for now; selectGovBodyOrg() below re-derives both
        // once an Organization is picked, since that's what disambiguates
        // one Sakha's body from another's.
        onGovBodyTypeChange() {
            const f = this.govBodyForm;
            const bt = this.govBodyTypes.find(x => x.body_type_master_pk === f.body_type_master_pk);
            if (!bt) return;
            f.body_code = bt.body_type_code;
            f.body_name = bt.body_type_name;
            f.organization_pk = "";
            f.selectedOrg = null;
            f.orgQuery = "";
            f.orgResults = [];
            if (this.govScopedSakhaBodyTypes.includes(bt.body_type_code)) {
                this.loadGovBodySakhaScope(f.body_type_master_pk);
            } else {
                this.govBodySakhaScope = { mode: "choose", auto_select_pk: null, sakhas: [] };
            }
        },

        // Same auto-select/locked-dropdown UX as loadKumariSevakScope,
        // for the "Add Body" form's org-picker when the chosen body type
        // is Sakha-anchored (SAKHA_GOVERNING_BODY, MAHILA_PARICHALANA_MANDALI,
        // SEVAK_SANGHA_EXECUTIVE) — the admin should only ever attach one
        // of these to a Sakha within their own admin scope.
        isGovScopedSakhaBodyType() {
            const bt = this.govBodyTypes.find(x => x.body_type_master_pk === this.govBodyForm.body_type_master_pk);
            return !!bt && this.govScopedSakhaBodyTypes.includes(bt.body_type_code);
        },

        async loadGovBodySakhaScope(bodyTypeMasterPk) {
            this.govBodySakhaScopeLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/bodies/sakha-scope-options?body_type_master_pk=${encodeURIComponent(bodyTypeMasterPk)}`
                );
                if (!res.ok) {
                    this.govBodySakhaScope = { mode: "choose", auto_select_pk: null, sakhas: [] };
                    return;
                }
                const data = await res.json();
                this.govBodySakhaScope = {
                    mode: data.mode || "choose",
                    auto_select_pk: data.auto_select_pk || null,
                    sakhas: data.sakhas || [],
                };
                if (this.govBodySakhaScope.mode === "locked" && this.govBodySakhaScope.auto_select_pk) {
                    const org = this.govBodySakhaScope.sakhas.find(
                        s => s.organization_pk === this.govBodySakhaScope.auto_select_pk
                    );
                    if (org) this.selectGovBodyOrg({ ...org, type_code: "SAKHA_SANGHA" });
                }
            } catch (_) {
                this.govBodySakhaScope = { mode: "choose", auto_select_pk: null, sakhas: [] };
            } finally {
                this.govBodySakhaScopeLoading = false;
            }
        },

        onGovBodySakhaScopeSelect(organizationPk) {
            const org = this.govBodySakhaScope.sakhas.find(s => s.organization_pk === organizationPk);
            if (org) this.selectGovBodyOrg({ ...org, type_code: "SAKHA_SANGHA" });
        },

        // Debounced type-ahead org picker for the Add Body form — mirrors
        // onGovPersonQueryInput()/searchGovPerson() below, so an admin
        // picks a Sakha/Mahila Sangha by NAME instead of pasting a PK.
        // Scoped to the org type implied by the chosen Body Type where
        // one is known (govBodyOrgTypeByBodyType); otherwise unfiltered.
        _govBodyOrgSearchTimer: null,
        onGovBodyOrgQueryInput() {
            clearTimeout(this._govBodyOrgSearchTimer);
            this.govBodyForm.selectedOrg = null;
            this.govBodyForm.organization_pk = "";
            const q = this.govBodyForm.orgQuery.trim();
            if (q.length < 2) { this.govBodyForm.orgResults = []; return; }
            this._govBodyOrgSearchTimer = setTimeout(() => this.searchGovBodyOrg(q), 300);
        },

        async searchGovBodyOrg(q) {
            this.govBodyForm.orgSearching = true;
            try {
                const bt = this.govBodyTypes.find(x => x.body_type_master_pk === this.govBodyForm.body_type_master_pk);
                const typeCode = bt ? this.govBodyOrgTypeByBodyType[bt.body_type_code] : null;
                const params = new URLSearchParams({ search: q, page_size: 20 });
                if (typeCode) params.set("type_code", typeCode);
                const res = await NSSAuth.apiFetch(`/api/v1/admin/organizations?${params}`);
                this.govBodyForm.orgResults = res.ok ? (await res.json()).organizations : [];
            } catch {
                this.govBodyForm.orgResults = [];
            } finally {
                this.govBodyForm.orgSearching = false;
            }
        },

        selectGovBodyOrg(org) {
            this.govBodyForm.selectedOrg = org;
            this.govBodyForm.organization_pk = org.organization_pk;
            this.govBodyForm.orgQuery = `${org.organization_name} (${org.type_name || org.type_code})`;
            this.govBodyForm.orgResults = [];
            // Re-derive Code/Name now that we know WHICH org this instance
            // belongs to — e.g. "Puri Sakha Governing Body" / a
            // "<ORG_CODE>_<BODY_TYPE_CODE>" code, so two Sakhas' bodies
            // never collide on the auto-filled default from onGovBodyTypeChange().
            const bt = this.govBodyTypes.find(x => x.body_type_master_pk === this.govBodyForm.body_type_master_pk);
            if (bt) {
                const orgTag = org.organization_code || org.short_code || org.organization_name;
                const codeSuffix = this.govBodyCodeSuffixByBodyType[bt.body_type_code] || bt.body_type_code;
                this.govBodyForm.body_code = `${orgTag}_${codeSuffix}`.toUpperCase();
                this.govBodyForm.body_name = `${org.organization_name} ${bt.body_type_name}`;
            }
        },

        // ── Governance: Assignments ───────────────────────────────

        async loadGovAssignments() {
            // The assign-form's Position dropdown needs govPositions, which
            // only the Body Types & Positions tab normally loads — fetch it
            // here too so Assignments works as a standalone entry point.
            if (this.govPositions.length === 0) {
                const p = await NSSAuth.apiFetch("/api/v1/governance/positions");
                if (p.ok) this.govPositions = await p.json();
            }
            // "Which Sakhas haven't nominated their Advisory Board rep" is
            // body-independent (NSS-wide-only) — load it once per tab visit.
            if (this.isGovNssWideAdmin) this.loadGovMissingNominations();
            if (!this.govSelectedBodyPk) {
                if (this.govBodies.length === 0) await this.loadGovBodies();
                if (!this.govSelectedBodyPk) return;
            }
            this._loadGovAllowedPositions();
            this._loadGovActingPositions();
            this.loadGovActing();
            this.govAssignmentsLoading = true;
            this.govAssignmentsError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/bodies/${this.govSelectedBodyPk}/assignments`);
                if (res.status === 403) { this.govAssignmentsError = "You do not have permission to view assignments."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                this.govAssignments = data.items;
                this._applyGovSakhaFilterDefault();
            } catch (err) {
                this.govAssignmentsError = err.message || "Failed to load assignments.";
            } finally {
                this.govAssignmentsLoading = false;
            }
        },

        // NSS-admin-only: active Sakha Sanghas with no current Advisory
        // Board representative. Backend 403s a Sakha-scoped admin, so only
        // fetch for a global admin (isGovNssWideAdmin).
        async loadGovMissingNominations() {
            this.govMissingNominationsLoading = true;
            this.govMissingNominationsError = "";
            try {
                const res = await NSSAuth.apiFetch("/api/v1/governance/advisory-board/missing-nominations");
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govMissingNominationsError = NSS.errorMessage(data, res.status);
                    this.govMissingNominations = [];
                    return;
                }
                const data = await res.json();
                this.govMissingNominations = data.items || [];
            } catch (err) {
                this.govMissingNominationsError = err.message || "Failed to load missing nominations.";
                this.govMissingNominations = [];
            } finally {
                this.govMissingNominationsLoading = false;
            }
        },

        onGovBodyChange() {
            this.govAssignments = [];
            this.govActing = [];
            this.govSakhaFilter = "";
            this.govAssignmentsShowAll = false;
            this.loadGovAssignments();
        },

        // Positions valid for the selected body's type (GOV-BR-011A) —
        // drives the assign-form Position dropdown.
        async _loadGovAllowedPositions() {
            this.govAllowedPositions = [];
            this.govSeatLimit = null;
            this.govSeatsFilled = 0;
            this.govInheritedPositions = [];
            this.govAssignFromResults = [];
            this.govAssignOfficersFromMembers = false;
            this.govAssignOrgPk = null;
            if (!this.govSelectedBodyPk) return;
            const res = await NSSAuth.apiFetch(`/api/v1/governance/bodies/${this.govSelectedBodyPk}/allowed-positions`);
            if (res.ok) {
                const data = await res.json();
                this.govAllowedPositions = data.positions;
                this.govSeatLimit = data.seat_limit;
                this.govSeatsFilled = data.seats_filled;
                // Drives the Member-search scope in the Add Assignment form:
                // a body whose officers are chosen from among its own existing
                // members (Advisory Board President/Secretary) must search
                // only this body's current members; an org-scoped body
                // searches its own org subtree; an NSS-wide body with neither
                // searches everyone. See onGovPersonQueryInput().
                this.govAssignOfficersFromMembers = !!data.officers_from_members;
                this.govAssignOrgPk = data.organization_pk || null;
            }
            // Read-only office-holders inherited from another body (e.g. the
            // Mahila Parichalana Mandali inherits the Kendra GB's Parichalak).
            const inh = await NSSAuth.apiFetch(`/api/v1/governance/bodies/${this.govSelectedBodyPk}/inherited-positions`);
            if (inh.ok) {
                const idata = await inh.json();
                this.govInheritedPositions = idata.inherited || [];
            }
            this._loadGovAssignFromResults();
        },

        // Declared election results (DECLARED/UNCONTESTED with a winner) for
        // elections held on the currently-selected body, restricted to
        // positions this admin's dropdown actually offers (govAllowedPositions
        // — for Advisory Board that is President/Secretary once the
        // Sakha-nominated Member seat is excluded for an NSS-wide admin, see
        // list_allowed_positions in governance.py). Drives a one-click
        // "assign winner" action alongside the normal manual person search,
        // for the Advisory Board President/Secretary + any other elected body.
        async _loadGovAssignFromResults() {
            this.govAssignFromResults = [];
            if (!this.govSelectedBodyPk || !(this.govAllowedPositions || []).length) return;
            this.govAssignFromResultsLoading = true;
            try {
                const er = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections?body_master_pk=${this.govSelectedBodyPk}&page=1&page_size=${NSS.MAX_PAGE_SIZE}`);
                if (!er.ok) return;
                const elections = (await er.json()).items || [];
                const allowedPks = new Set(this.govAllowedPositions.map(p => String(p.position_master_pk)));
                const out = [];
                for (const e of elections) {
                    const rr = await NSSAuth.apiFetch(`/api/v1/governance/elections/${e.election_pk}/results`);
                    if (!rr.ok) continue;
                    const items = (await rr.json()).items || [];
                    for (const r of items) {
                        if (!r.is_active || !r.winner_person_pk) continue;
                        if (!["DECLARED", "UNCONTESTED"].includes(r.result_status)) continue;
                        if (!allowedPks.has(String(r.position_master_pk))) continue;
                        out.push(r);
                    }
                }
                this.govAssignFromResults = out;
            } catch {
                this.govAssignFromResults = [];
            } finally {
                this.govAssignFromResultsLoading = false;
            }
        },

        // One-click "assign from election result" for the Assignments tab —
        // same POST /results/{pk}/apply the Elections tab's applyGovResult()
        // uses. If the position already has a holder (e.g. replacing a prior
        // Advisory Board President/Secretary), end that assignment first and
        // retry — the update/replace path the backend otherwise requires as
        // two explicit calls (End, then Apply/Add Assignment).
        async assignGovResultWinner(result) {
            const ok = await NSSDialog.confirm(
                `Assign ${result.winner_name || "the declared winner"} as ${result.position_name} from this election result?`,
                { title: "Assign Winner", confirmText: "Assign", confirmClass: "primary" }
            );
            if (!ok) return;
            this.govAssignmentsError = "";
            try {
                let res = await NSSAuth.apiFetch(`/api/v1/governance/results/${result.election_result_pk}/apply`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({}),
                });
                if (res.status === 409) {
                    const existing = (this.govAssignments || []).find(
                        a => String(a.position_master_pk) === String(result.position_master_pk) && a.is_active
                    );
                    if (!existing) {
                        const data = await res.json().catch(() => ({}));
                        this.govAssignmentsError = NSS.errorMessage(data, res.status);
                        return;
                    }
                    const replaceOk = await NSSDialog.confirm(
                        `${existing.person_name || "The current holder"} currently holds ${result.position_name}. End their assignment and assign ${result.winner_name} instead?`,
                        { title: "Replace Office-Bearer", confirmText: "End & Assign", confirmClass: "danger" }
                    );
                    if (!replaceOk) {
                        return;
                    }
                    const today = new Date().toISOString().slice(0, 10);
                    const endRes = await NSSAuth.apiFetch(`/api/v1/governance/assignments/${existing.body_member_assignment_pk}/end`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ effective_to: today }),
                    });
                    if (!endRes.ok) {
                        const data = await endRes.json().catch(() => ({}));
                        this.govAssignmentsError = NSS.errorMessage(data, endRes.status);
                        return;
                    }
                    res = await NSSAuth.apiFetch(`/api/v1/governance/results/${result.election_result_pk}/apply`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({}),
                    });
                }
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govAssignmentsError = NSS.errorMessage(data, res.status);
                    return;
                }
                await this.loadGovAssignments();
            } catch (err) {
                this.govAssignmentsError = err.message || "Failed to assign from election result.";
            }
        },

        // Debounced type-ahead against the membership search endpoint —
        // returns sangha_sevi_pk alongside person_pk, which is exactly
        // what a governance assignment needs (GOV-BR-056/074: the holder
        // must be an active member, not just a Person). Scoped so the
        // results are actually eligible candidates for the position chosen,
        // not every member in NSS (same bug class as the election
        // typeahead, which already scopes via _govSearchMembers/orgPk):
        //   - officers-from-members body (Advisory Board President/
        //     Secretary — GOV-BR-033/034) -> only this body's own current
        //     members (member_of_body_pk), since the officer must already
        //     be seated as Member here;
        //   - org-scoped body (Sakha GB, Sevak Sangha Executive, ...) ->
        //     that org's own subtree (organization_pk), same as everywhere
        //     else this pattern is used;
        //   - NSS-wide body with no such rule (Kendra GB, Advisory Board's
        //     own MEMBER seat, which is filled via nomination not body
        //     membership) -> unscoped, any active member.
        _govPersonSearchTimer: null,
        onGovPersonQueryInput() {
            clearTimeout(this._govPersonSearchTimer);
            this.govAssignForm.selectedPerson = null;
            const q = this.govAssignForm.personQuery.trim();
            if (q.length < 2) { this.govAssignForm.personResults = []; return; }
            this._govPersonSearchTimer = setTimeout(() => this.searchGovPerson(q), 300);
        },

        get govAssignSelectedPositionCode() {
            const p = (this.govAllowedPositions || [])
                .find(p => p.position_master_pk === this.govAssignForm.position_master_pk);
            return p ? p.position_code : null;
        },

        async searchGovPerson(q) {
            this.govAssignForm.personSearching = true;
            try {
                let url = `/api/v1/membership/search?q=${encodeURIComponent(q)}`;
                if (this.govAssignOfficersFromMembers && this.govAssignSelectedPositionCode !== "MEMBER") {
                    url += `&member_of_body_pk=${encodeURIComponent(this.govSelectedBodyPk)}`;
                } else if (this.govAssignOrgPk) {
                    url += `&organization_pk=${encodeURIComponent(this.govAssignOrgPk)}`;
                }
                const res = await NSSAuth.apiFetch(url);
                this.govAssignForm.personResults = res.ok ? (await res.json()).members : [];
            } catch {
                this.govAssignForm.personResults = [];
            } finally {
                this.govAssignForm.personSearching = false;
            }
        },

        selectGovPerson(member) {
            this.govAssignForm.selectedPerson = member;
            this.govAssignForm.personQuery =
                `${member.first_name} ${member.last_name || ""}`.trim() + ` (${member.sangha_sevi_id || ""})`;
            this.govAssignForm.personResults = [];
        },

        async createGovAssignment() {
            const f = this.govAssignForm;
            f.error = "";
            if (!f.position_master_pk || !f.selectedPerson || !f.effective_from) {
                f.error = "Position, member, and effective date are required.";
                return;
            }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/bodies/${this.govSelectedBodyPk}/assignments`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        position_master_pk: f.position_master_pk,
                        person_pk: f.selectedPerson.person_pk,
                        sangha_sevi_pk: f.selectedPerson.sangha_sevi_pk,
                        effective_from: f.effective_from,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.govAssignments.push(await res.json());
                this._loadGovAllowedPositions();
                f.show = false;
                f.position_master_pk = ""; f.effective_from = "";
                f.personQuery = ""; f.personResults = []; f.selectedPerson = null;
            } catch (err) {
                f.error = err.message || "Failed to create assignment.";
            } finally {
                f.saving = false;
            }
        },

        async endGovAssignment(a) {
            const today = new Date().toISOString().slice(0, 10);
            const ok = await NSSDialog.confirm(
                `End ${a.person_name || "this holder"}'s Position as ${a.position_name}?`,
                { title: "End Assignment", confirmText: "End", confirmClass: "danger" }
            );
            if (!ok) return;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/assignments/${a.body_member_assignment_pk}/end`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ effective_to: today }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govAssignmentsError = NSS.errorMessage(data, res.status);
                    return;
                }
                const updated = await res.json();
                const idx = this.govAssignments.findIndex(x => x.body_member_assignment_pk === a.body_member_assignment_pk);
                if (idx !== -1) this.govAssignments[idx] = updated;
                this._loadGovAllowedPositions();
            } catch (err) {
                this.govAssignmentsError = err.message || "Failed to end assignment.";
            }
        },

        // ── Governance: Acting / Interim Cover (GOV-BR-018/019/020) ──
        // Separate table from body_member_assignment — no composition/
        // seat-limit check, so the position dropdown is fetched with
        // exclude_filled=false (interim cover is legitimate while a seat
        // is vacant or its holder unavailable).
        async _loadGovActingPositions() {
            this.govActingPositions = [];
            if (!this.govSelectedBodyPk) return;
            const res = await NSSAuth.apiFetch(
                `/api/v1/governance/bodies/${this.govSelectedBodyPk}/allowed-positions?exclude_filled=false`);
            if (res.ok) this.govActingPositions = (await res.json()).positions;
        },

        async loadGovActing() {
            if (!this.govSelectedBodyPk) { this.govActing = []; return; }
            this.govActingLoading = true;
            this.govActingError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/bodies/${this.govSelectedBodyPk}/acting-assignments`);
                if (res.status === 403) { this.govActingError = "You do not have permission to view acting assignments."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.govActing = (await res.json()).items;
            } catch (err) {
                this.govActingError = err.message || "Failed to load acting assignments.";
            } finally {
                this.govActingLoading = false;
            }
        },

        // Member-search typeahead for the acting-cover form — org-scoped
        // the same way the regular Assignment form is (govAssignOrgPk, set
        // by _loadGovAllowedPositions), but deliberately NOT restricted to
        // the body's own current members (unlike officers-from-members):
        // an acting holder is defined against the Person performing the
        // role, not against prior membership on this body (DDL comment,
        // 05_acting_position_assignment.sql).
        _govActingPersonSearchTimer: null,
        onGovActingPersonQueryInput() {
            clearTimeout(this._govActingPersonSearchTimer);
            this.govActingForm.selectedPerson = null;
            const q = this.govActingForm.personQuery.trim();
            if (q.length < 2) { this.govActingForm.personResults = []; return; }
            this._govActingPersonSearchTimer = setTimeout(() => this.searchGovActingPerson(q), 300);
        },

        async searchGovActingPerson(q) {
            this.govActingForm.personSearching = true;
            try {
                let url = `/api/v1/membership/search?q=${encodeURIComponent(q)}`;
                if (this.govAssignOrgPk) url += `&organization_pk=${encodeURIComponent(this.govAssignOrgPk)}`;
                const res = await NSSAuth.apiFetch(url);
                this.govActingForm.personResults = res.ok ? (await res.json()).members : [];
            } catch {
                this.govActingForm.personResults = [];
            } finally {
                this.govActingForm.personSearching = false;
            }
        },

        selectGovActingPerson(member) {
            this.govActingForm.selectedPerson = member;
            this.govActingForm.personQuery =
                `${member.first_name} ${member.last_name || ""}`.trim() + ` (${member.sangha_sevi_id || ""})`;
            this.govActingForm.personResults = [];
        },

        async createGovActing() {
            const f = this.govActingForm;
            f.error = "";
            if (!f.position_master_pk || !f.selectedPerson || !f.effective_from) {
                f.error = "Position, acting person, and effective date are required.";
                return;
            }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/bodies/${this.govSelectedBodyPk}/acting-assignments`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        position_master_pk: f.position_master_pk,
                        person_pk: f.selectedPerson.person_pk,
                        effective_from: f.effective_from,
                        effective_to: f.effective_to || null,
                        reason: f.reason || null,
                        remarks: f.remarks || null,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.govActing.unshift(await res.json());
                f.show = false;
                f.position_master_pk = ""; f.effective_from = ""; f.effective_to = "";
                f.reason = ""; f.remarks = "";
                f.personQuery = ""; f.personResults = []; f.selectedPerson = null;
            } catch (err) {
                f.error = err.message || "Failed to create acting assignment.";
            } finally {
                f.saving = false;
            }
        },

        async endGovActing(a) {
            const today = new Date().toISOString().slice(0, 10);
            const ok = await NSSDialog.confirm(
                `End ${a.person_name || "this person"}'s acting cover as ${a.position_name}?`,
                { title: "End Acting Cover", confirmText: "End", confirmClass: "danger" }
            );
            if (!ok) return;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/governance/acting-assignments/${a.acting_position_assignment_pk}/end`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ effective_to: today }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govActingError = NSS.errorMessage(data, res.status);
                    return;
                }
                const updated = await res.json();
                const idx = this.govActing.findIndex(x => x.acting_position_assignment_pk === a.acting_position_assignment_pk);
                if (idx !== -1) this.govActing[idx] = updated;
            } catch (err) {
                this.govActingError = err.message || "Failed to end acting assignment.";
            }
        },

        // ══════════════════════════════════════════════════════════
        //  Governance Elections (Tier 6 voting slice, GOV-BR-045)
        //  Mirrors the govAssignment* conventions above.
        // ══════════════════════════════════════════════════════════

        govFmtDate(iso) {
            if (!iso) return "";
            const s = String(iso).slice(0, 10).split("-");
            return s.length === 3 ? `${s[2]}/${s[1]}/${s[0]}` : iso;
        },
        govElectionStatusBadge(status) {
            switch (status) {
                case "VOTING":    return "badge-info";
                case "COMPLETED": return "badge-success";
                case "CANCELLED": return "badge-muted";
                default:          return "badge-muted"; // SCHEDULED / NOMINATION
            }
        },
        govNominationStatusBadge(status) {
            switch (status) {
                case "ACCEPTED":  return "badge-success";
                case "REJECTED":
                case "WITHDRAWN": return "badge-muted";
                default:          return "badge-info"; // NOMINATED
            }
        },
        // Allowed status transitions (By-Law election lifecycle). Mirrors the
        // server-side table in api/routers/governance.py
        // (_ELECTION_STATUS_TRANSITIONS) — the API is the authority; this copy
        // only decides which buttons to draw.
        //
        // An ELECTION cycle runs SCHEDULED -> NOMINATION -> VOTING -> COMPLETED.
        // A NOMINATION cycle (consensus/selection, GOV-BR-042) runs
        // SCHEDULED -> NOMINATION -> COMPLETED, skipping VOTING entirely.
        govNextStatuses(status, electionType) {
            const isNominationOnly = electionType === "NOMINATION";
            switch (status) {
                case "SCHEDULED":  return ["NOMINATION", "CANCELLED"];
                case "NOMINATION": return isNominationOnly
                    ? ["COMPLETED", "CANCELLED"]
                    : ["VOTING", "CANCELLED"];
                case "VOTING":     return ["COMPLETED", "CANCELLED"];
                default:           return [];
            }
        },
        govIsNominationOnly() {
            return this.govSelectedElection &&
                   this.govSelectedElection.election_type === "NOMINATION";
        },
        govElectionTypeLabel(t) {
            return t === "NOMINATION" ? "Nomination (consensus)" : "Election (ballot)";
        },
        // Outcomes available when declaring a result. A nomination-only cycle
        // held no ballot, so DECLARED (from a tally) and TIE are impossible.
        govResultStatusOptions() {
            return this.govIsNominationOnly()
                ? ["UNCONTESTED", "VACANT"]
                : ["DECLARED", "UNCONTESTED", "TIE", "VACANT"];
        },
        // Only ACCEPTED nominations are votable.
        govVotableNominations() {
            return this.govNominations.filter(n => n.nomination_status === "ACCEPTED");
        },
        govNominationsForPosition(positionPk) {
            if (!positionPk) return [];
            return this.govNominations.filter(
                n => String(n.position_master_pk) === String(positionPk) && n.nomination_status === "ACCEPTED");
        },

        // ── Member typeahead (shared by every election sub-form) ──
        // `orgPk` restricts results to one organization's own members *and its
        // branches* (the API search is subtree-aware). Used for the nomination
        // candidate/proposer search AND the vote form's voter search so an
        // org-scoped body (Sakha Governing Body, Sevak Sangha Executive,
        // per-Sakha Mahila Parichalana Mandali, ...) only offers members from
        // its own subtree — the electorate the server will accept (GOV-BR-094).
        // Omit for an NSS-wide body (organization_pk IS NULL), or for the reset
        // form's president field (an approval authority, not an electorate
        // member), which searches across all members.
        async _govSearchMembers(q, orgPk) {
            try {
                let url = `/api/v1/membership/search?q=${encodeURIComponent(q)}`;
                if (orgPk) url += `&organization_pk=${encodeURIComponent(orgPk)}`;
                const res = await NSSAuth.apiFetch(url);
                if (!res.ok) return [];
                const data = await res.json();
                return data.members || [];
            } catch {
                return [];
            }
        },
        _govCap(s) { return s.charAt(0).toUpperCase() + s.slice(1); },
        onGovMemberSearch(form, key, orgPk) {
            clearTimeout(this._govTypeTimers[key]);
            form["selected" + this._govCap(key)] = null;
            const q = (form[key + "Query"] || "").trim();
            if (q.length < 2) { form[key + "Results"] = []; return; }
            this._govTypeTimers[key] = setTimeout(async () => {
                form[key + "Searching"] = true;
                form[key + "Results"] = await this._govSearchMembers(q, orgPk);
                form[key + "Searching"] = false;
            }, 300);
        },
        selectGovMember(form, key, m) {
            form["selected" + this._govCap(key)] = m;
            const label = `${m.first_name} ${m.last_name || ""}`.trim();
            form[key + "Query"] = m.sangha_sevi_id ? `${label} (${m.sangha_sevi_id})` : label;
            form[key + "Results"] = [];
        },

        // ── Elections list / create ──
        async loadGovElections() {
            if (!this.canViewGovernance) return;
            this.govElectionsLoading = true;
            this.govElectionsError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections?page=1&page_size=${NSS.MAX_PAGE_SIZE}&sort_by=election_date&sort_dir=desc`);
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govElectionsError = NSS.errorMessage(data, res.status);
                    return;
                }
                const data = await res.json();
                this.govElections = data.items || [];
                // Governance bodies feed the create form + reset scope.
                if (!this.govBodiesAll.length) await this.loadGovBodies();
            } catch (err) {
                this.govElectionsError = err.message || "Failed to load elections.";
            } finally {
                this.govElectionsLoading = false;
            }
        },
        async createGovElection() {
            const f = this.govElectionForm;
            f.error = "";
            if (!f.body_master_pk) { f.error = "Select a governance body."; return; }
            if (!f.election_code.trim()) { f.error = "Election code is required."; return; }
            if (!f.election_name.trim()) { f.error = "Election name is required."; return; }
            if (!f.election_date) { f.error = "Election date is required."; return; }
            const nominationOnly = f.election_type === "NOMINATION";
            if (nominationOnly && (f.voting_start_date || f.voting_end_date)) {
                f.error = "A Nomination (consensus) cycle holds no ballot — clear the voting dates.";
                return;
            }
            f.saving = true;
            try {
                const payload = {
                    election_code: f.election_code.trim(),
                    // body_master_pk is a UUID — never Number(), which yields NaN
                    // and serialises to null, so the API rejected every create.
                    body_master_pk: f.body_master_pk,
                    election_name: f.election_name.trim(),
                    election_type: f.election_type || "ELECTION",
                    election_date: f.election_date,
                    is_secret_ballot: !nominationOnly && !!f.is_secret_ballot,
                };
                if (f.description.trim()) payload.description = f.description.trim();
                if (f.nomination_start_date) payload.nomination_start_date = f.nomination_start_date;
                if (f.nomination_end_date) payload.nomination_end_date = f.nomination_end_date;
                if (!nominationOnly) {
                    if (f.voting_start_date) payload.voting_start_date = f.voting_start_date;
                    if (f.voting_end_date) payload.voting_end_date = f.voting_end_date;
                }
                const res = await NSSAuth.apiFetch(`/api/v1/governance/elections`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                const created = await res.json();
                this.govElections.unshift(created);
                this.govElectionForm = {
                    show: false, saving: false, error: "",
                    body_master_pk: "", election_code: "", election_name: "",
                    election_type: "ELECTION",
                    election_date: "", nomination_start_date: "", nomination_end_date: "",
                    voting_start_date: "", voting_end_date: "", is_secret_ballot: false,
                    description: "", remarks: "",
                };
            } catch (err) {
                f.error = err.message || "Failed to create election.";
            } finally {
                f.saving = false;
            }
        },

        // ── Election detail ──
        async openGovElection(e) {
            this.govSelectedElectionPk = e.election_pk;
            this.govSelectedElection = e;
            this.govElectionActionError = "";
            this.govNominationForm.show = false;
            this.govResultForm.show = false;
            // A nomination-only cycle has no tally to declare from, so its
            // outcome defaults to UNCONTESTED rather than DECLARED (which the
            // API rejects for that mode).
            this.govResultForm.result_status =
                e.election_type === "NOMINATION" ? "UNCONTESTED" : "DECLARED";
            this.govResetForm.show = false;
            this.govSelfVote = { saving: false, error: "", notice: "", election_nomination_pk: "" };
            await Promise.all([
                this.loadGovElectionPositions(),
                this.loadGovNominations(),
                this.loadGovResults(),
                // No ballots are cast in a nomination-only cycle, so there is
                // nothing to tally.
                e.election_type === "NOMINATION" ? Promise.resolve() : this.loadGovTally(),
            ]);
        },
        closeGovElection() {
            this.govSelectedElectionPk = "";
            this.govSelectedElection = null;
            this.govNominations = [];
            this.govResults = [];
            this.govTally = [];
            this.govElectionPositions = [];
        },
        async loadGovElectionPositions() {
            const e = this.govSelectedElection;
            if (!e) { this.govElectionPositions = []; return; }
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/bodies/${e.body_master_pk}/allowed-positions`);
                this.govElectionPositions = res.ok ? ((await res.json()).positions || []) : [];
            } catch {
                this.govElectionPositions = [];
            }
        },
        async changeGovElectionStatus(status) {
            if (!this.govSelectedElection) return;
            if (status === "CANCELLED") {
                const ok = await NSSDialog.confirm(
                    "Cancel this election?",
                    { title: "Cancel Election", confirmText: "Cancel Election", confirmClass: "danger" }
                );
                if (!ok) return;
            }
            this.govElectionBusy = true;
            this.govElectionActionError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/status`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ election_status: status }),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govElectionActionError = NSS.errorMessage(data, res.status);
                    return;
                }
                const updated = await res.json();
                this.govSelectedElection = updated;
                const idx = this.govElections.findIndex(x => x.election_pk === updated.election_pk);
                if (idx !== -1) this.govElections[idx] = updated;
            } catch (err) {
                this.govElectionActionError = err.message || "Failed to change status.";
            } finally {
                this.govElectionBusy = false;
            }
        },

        // ── Nominations ──
        async loadGovNominations() {
            if (!this.govSelectedElectionPk) return;
            this.govNominationsLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/nominations`);
                this.govNominations = res.ok ? ((await res.json()).items || []) : [];
            } catch {
                this.govNominations = [];
            } finally {
                this.govNominationsLoading = false;
            }
        },
        async createGovNomination() {
            const f = this.govNominationForm;
            f.error = "";
            if (!f.position_master_pk) { f.error = "Select a position."; return; }
            if (!f.selectedCandidate) { f.error = "Select a candidate."; return; }
            f.saving = true;
            try {
                const payload = {
                    position_master_pk: f.position_master_pk,  // UUID — not Number()
                    candidate_person_pk: f.selectedCandidate.person_pk,
                };
                if (f.selectedProposer) payload.proposer_person_pk = f.selectedProposer.person_pk;
                if (f.nomination_date) payload.nomination_date = f.nomination_date;
                if (f.remarks && f.remarks.trim()) payload.remarks = f.remarks.trim();
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/nominations`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.govNominations.push(await res.json());
                this.govNominationForm = {
                    show: false, saving: false, error: "",
                    position_master_pk: "", nomination_date: "", remarks: "",
                    candidateQuery: "", candidateResults: [], candidateSearching: false, selectedCandidate: null,
                    proposerQuery: "", proposerResults: [], proposerSearching: false, selectedProposer: null,
                };
            } catch (err) {
                f.error = err.message || "Failed to add nomination.";
            } finally {
                f.saving = false;
            }
        },
        async changeNominationStatus(n, status) {
            this.govElectionActionError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/nominations/${n.election_nomination_pk}/status`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ nomination_status: status }),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govElectionActionError = NSS.errorMessage(data, res.status);
                    return;
                }
                const updated = await res.json();
                const idx = this.govNominations.findIndex(x => x.election_nomination_pk === updated.election_nomination_pk);
                if (idx !== -1) this.govNominations[idx] = updated;
            } catch (err) {
                this.govElectionActionError = err.message || "Failed to update nomination.";
            }
        },

        // ── Voting ──
        async castSelfVote() {
            const v = this.govSelfVote;
            v.error = ""; v.notice = "";
            if (!v.election_nomination_pk) { v.error = "Select a candidate."; return; }
            v.saving = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/votes/self`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ election_nomination_pk: Number(v.election_nomination_pk) }),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    v.error = NSS.errorMessage(data, res.status);
                    return;
                }
                v.notice = "Your vote has been recorded. Ballots are immutable.";
                v.election_nomination_pk = "";
                this.loadGovTally();
            } catch (err) {
                v.error = err.message || "Failed to cast vote.";
            } finally {
                v.saving = false;
            }
        },
        async castOfficerVote() {
            const f = this.govVoteForm;
            f.error = "";
            if (!f.election_nomination_pk) { f.error = "Select a candidate."; return; }
            if (!f.selectedVoter) { f.error = "Select the voting member."; return; }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/votes`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            election_nomination_pk: f.election_nomination_pk,  // UUID — not Number()
                            voter_person_pk: f.selectedVoter.person_pk,
                        }),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.govVoteForm = {
                    show: false, saving: false, error: "",
                    election_nomination_pk: "",
                    voterQuery: "", voterResults: [], voterSearching: false, selectedVoter: null,
                    remarks: "",
                };
                this.loadGovTally();
            } catch (err) {
                f.error = err.message || "Failed to record vote.";
            } finally {
                f.saving = false;
            }
        },

        // ── Tally ──
        async loadGovTally() {
            if (!this.govSelectedElectionPk) return;
            this.govTallyLoading = true;
            this.govTallyError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/tally`);
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govTallyError = NSS.errorMessage(data, res.status);
                    this.govTally = [];
                    return;
                }
                this.govTally = (await res.json()).items || [];
            } catch (err) {
                this.govTallyError = err.message || "Failed to load tally.";
            } finally {
                this.govTallyLoading = false;
            }
        },

        // ── Results ──
        async loadGovResults() {
            if (!this.govSelectedElectionPk) return;
            this.govResultsLoading = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/results`);
                this.govResults = res.ok ? ((await res.json()).items || []) : [];
            } catch {
                this.govResults = [];
            } finally {
                this.govResultsLoading = false;
            }
        },
        async declareGovResult() {
            const f = this.govResultForm;
            f.error = "";
            if (!f.position_master_pk) { f.error = "Select a position."; return; }
            f.saving = true;
            try {
                const payload = {
                    // These are UUIDs — Number() yields NaN, which serialises
                    // to null and the API rejects as a missing field.
                    position_master_pk: f.position_master_pk,
                    result_status: f.result_status,
                };
                if (f.winning_nomination_pk) {
                    payload.winning_nomination_pk = f.winning_nomination_pk;
                    const win = this.govNominations.find(
                        n => String(n.election_nomination_pk) === String(f.winning_nomination_pk));
                    if (win) payload.winner_person_pk = win.candidate_person_pk;
                    // A consensus cycle has no tally, so no vote_count is sent.
                    const row = this.govTally.find(
                        t => String(t.election_nomination_pk) === String(f.winning_nomination_pk));
                    if (row) payload.vote_count = row.vote_count;
                }
                if (f.remarks && f.remarks.trim()) payload.remarks = f.remarks.trim();
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/results`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                await this.loadGovResults();
                this.govResultForm = {
                    show: false, saving: false, error: "",
                    position_master_pk: "", winning_nomination_pk: "",
                    result_status: this.govIsNominationOnly() ? "UNCONTESTED" : "DECLARED",
                    remarks: "",
                };
            } catch (err) {
                f.error = err.message || "Failed to declare result.";
            } finally {
                f.saving = false;
            }
        },
        async applyGovResult(r) {
            const ok = await NSSDialog.confirm(
                `Apply this result — create a governance assignment for ${r.winner_name}?`,
                { title: "Apply Result", confirmText: "Apply", confirmClass: "primary" }
            );
            if (!ok) return;
            this.govElectionActionError = "";
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/results/${r.election_result_pk}/apply`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({}),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.govElectionActionError = NSS.errorMessage(data, res.status);
                    return;
                }
                const data = await res.json();
                this.govElectionActionError = "";
                await NSSDialog.alert(data.message || "Assignment created from election result.", "Result Applied");
            } catch (err) {
                this.govElectionActionError = err.message || "Failed to apply result.";
            }
        },

        // ── Reset ballots ──
        async resetGovBallots() {
            const f = this.govResetForm;
            f.error = "";
            if (!f.reason || f.reason.trim().length < 3) { f.error = "A reason (min 3 characters) is required."; return; }
            if (f.reset_mode === "ADMIN_WITH_PRESIDENT_APPROVAL" && !f.selectedPresident) {
                f.error = "Select the approving President."; return;
            }
            const ok = await NSSDialog.confirm(
                "This permanently deletes the cast ballots in scope. Continue?",
                { title: "Reset Ballots", confirmText: "Reset Ballots", confirmClass: "danger" }
            );
            if (!ok) return;
            f.saving = true;
            try {
                const payload = {
                    reset_mode: f.reset_mode,
                    reason: f.reason.trim(),
                };
                if (f.position_master_pk) payload.position_master_pk = f.position_master_pk;  // UUID — not Number()
                if (f.reset_mode === "ADMIN_WITH_PRESIDENT_APPROVAL" && f.selectedPresident) {
                    payload.president_person_pk = f.selectedPresident.person_pk;
                }
                const res = await NSSAuth.apiFetch(
                    `/api/v1/governance/elections/${this.govSelectedElectionPk}/votes/reset`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload),
                    });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                const data = await res.json();
                this.govResetForm = {
                    show: false, saving: false, error: "",
                    reset_mode: "PRESIDENT_UNILATERAL", position_master_pk: "", reason: "",
                    presidentQuery: "", presidentResults: [], presidentSearching: false, selectedPresident: null,
                };
                await NSSDialog.alert(data.message || `Ballots reset: ${data.votes_deleted} vote(s), ${data.participation_deleted} participation record(s) deleted.`, "Ballots Reset");
                this.loadGovTally();
            } catch (err) {
                f.error = err.message || "Failed to reset ballots.";
            } finally {
                f.saving = false;
            }
        },

        // ══════════════════════════════════════════════════════════
        //  Correspondence Register (Tier 6, SOL-ADMIN-009)
        //  api/routers/correspondence.py — 9 endpoints under
        //  /api/v1/correspondence. Permissions CORRESPONDENCE_VIEW/
        //  _MANAGE, bounded by admin scope on register_organization_pk.
        // ══════════════════════════════════════════════════════════

        // Lazily loads the two master-data categories a Create/Document/
        // Finance form needs (CORRESPONDENCE_MEDIUM,
        // CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE) — once per session,
        // same lazy-catalog pattern as loadGovBodies()'s govBodyTypes.
        async corrLoadCatalog() {
            // Medium default (owner request, 2026-10-25: simpler create
            // form) — the first catalog value, applied whether this is a
            // fresh fetch or the catalog was already cached from an
            // earlier form open, so a second "+ Send Application" click
            // still gets a pre-filled Medium instead of a bare "Select…".
            if (this.corrCatalogLoaded) {
                if (!this.corrCreateForm.medium && this.corrMediums.length) {
                    this.corrCreateForm.medium = this.corrMediums[0].value_code;
                }
                return;
            }
            try {
                const [mediumRes, financeRes] = await Promise.all([
                    NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=CORRESPONDENCE_MEDIUM"),
                    NSSAuth.apiFetch("/api/v1/foundation/master-data?category_code=CORRESPONDENCE_FINANCE_RELATIONSHIP_TYPE"),
                ]);
                this.corrMediums = mediumRes.ok ? await mediumRes.json() : [];
                this.corrFinanceRelationshipTypes = financeRes.ok ? await financeRes.json() : [];
                this.corrCatalogLoaded = true;
                if (!this.corrCreateForm.medium && this.corrMediums.length) {
                    this.corrCreateForm.medium = this.corrMediums[0].value_code;
                }
            } catch { /* non-fatal — dropdowns stay empty */ }
        },

        // Register Organization auto-resolution (owner request, 2026-10-25)
        // — an admin scoped to exactly one organization almost certainly
        // means THAT org every single time they file correspondence, so
        // asking them to re-search-and-pick it on every letter is pure
        // friction. An admin holding more than one distinct org-anchored
        // scope (e.g. a Kendra Governing Body President who is ALSO a
        // Sakha President — owner follow-up, 2026-10-26: "it should show
        // for every admin and i was checking kendra president, who is
        // also sakhas president who has dual admin roles") gets a real
        // tab-per-org switcher, same .tab-pill chrome as the status
        // filters above.
        //
        // Correction from the first version of this method (which called
        // GET /admin/organizations and keyed off its total count): that
        // endpoint collapses the instant ANY of the admin's grants is
        // NSS-WIDE scope_level — which a Kendra-President composite grant
        // (§63, rbac_service.load_composite_grants) always is — to
        // "unrestricted" (null scope = every org in the system), because
        // that collapse is CORRECT for backend authorization but wrong
        // for "which hats does this person wear". It made every dual
        // Kendra+Sakha admin fall straight to the manual search picker,
        // which is exactly the bug just reported.
        //
        // Fixed by reading the admin's own RAW currentUser.scopes array
        // instead (already loaded at login, no network call needed) —
        // one entry per role grant, each resolved to its real
        // organization_pk individually (a NULL organization_pk means
        // NSS-WIDE scope_level, e.g. the Kendra-President grant, and
        // resolves to the actual Kendra organization row — same
        // resolution myOrgDashboardPk already does for the sidebar, not
        // re-derived here). Deduplicated by resolved org, so two role
        // grants pointing at the same org only ever produce one tab.
        corrResolveDefaultOrg() {
            const f = this.corrCreateForm;
            const scopes = this.currentUser?.scopes || [];
            const kendraPk = this.kendraOrg?.organization_pk || null;
            const seenPks = new Set();
            const candidates = [];
            const pushOrg = (pk) => {
                if (!pk || seenPks.has(pk)) return;
                const org = this.organizations.find(o => o.organization_pk === pk);
                if (!org) return;
                seenPks.add(pk);
                candidates.push(org);
            };

            // Scope-derived registers: a scoped admin's own org(s); a KENDRA /
            // NSS-WIDE scope carries a null org and resolves to the Kendra
            // register.
            for (const s of scopes) {
                pushOrg(s.organization_pk || kendraPk);
            }

            // Owner 2026-10-26 ("we should have anchalika/zilla and
            // pathhchakra tab also for send and receive"): an NSS-wide /
            // Kendra-equivalent admin may file for ANY register, so offer
            // every register org, not just the scope-derived ones. Grouping
            // by tier below means even the 175 Sakhas cost one tab with a
            // dropdown — which is why this no longer has to exclude them the
            // way the old one-tab-per-org switcher did. A scope-bounded
            // admin never enters this branch, so they keep seeing only their
            // own register.
            if (this.isGovNssWideAdmin) {
                pushOrg(kendraPk);
                const TABBED_TYPES = CORR_REGISTER_TAB_GROUPS.flatMap(g => g.typeCodes);
                for (const org of this.organizations) {
                    if (TABBED_TYPES.includes(org.organization_type_code)) {
                        pushOrg(org.organization_pk);
                    }
                }
            }

            // Group the candidates into tier tabs, dropping empty tiers and
            // name-sorting each tier's dropdown.
            const groups = CORR_REGISTER_TAB_GROUPS
                .map(g => ({
                    key: g.key,
                    label: g.label,
                    orgs: candidates
                        .filter(o => g.typeCodes.includes(o.organization_type_code))
                        .sort((a, b) => (a.organization_name || "").localeCompare(b.organization_name || "")),
                }))
                .filter(g => g.orgs.length > 0);

            // An org whose type matches no tab group (nothing does today —
            // this is a guard against a future org type silently losing its
            // register rather than a live case) still has to be reachable, so
            // fall through to the manual search picker in that case.
            const grouped = groups.reduce((n, g) => n + g.orgs.length, 0);
            if (!groups.length || grouped !== candidates.length) {
                f.orgTabGroups = [];
                f.orgMultipleChoices = false;
                if (candidates.length === 1) {
                    this.corrSelectOrg(f.org, candidates[0]);
                    f.orgAutoResolved = true;
                }
                this.corrSyncBroadcastToOrg();
                return;
            }

            f.orgTabGroups = groups;
            if (groups.length === 1 && groups[0].orgs.length === 1) {
                // Exactly one register overall — no tabs, no dropdown, just
                // the read-only "Register: X" strip.
                this.corrSelectOrg(f.org, groups[0].orgs[0]);
                f.orgAutoResolved = true;
            } else {
                f.orgMultipleChoices = true;
                this.corrSelectRegisterTab(groups[0].key);
            }
            this.corrSyncBroadcastToOrg();
        },

        // The orgs behind the currently active register tab — drives the
        // tier's dropdown, and decides whether a dropdown is needed at all.
        get corrActiveTabOrgs() {
            const f = this.corrCreateForm;
            const g = (f.orgTabGroups || []).find(x => x.key === f.activeOrgTab);
            return g ? g.orgs : [];
        },

        // Switching tier: a tier holding exactly one org selects it outright
        // (a dropdown with one option is noise); a tier holding several
        // clears the selection so its dropdown opens on "Select…" rather
        // than silently filing against an arbitrary first org.
        corrSelectRegisterTab(groupKey) {
            const f = this.corrCreateForm;
            f.activeOrgTab = groupKey;
            const orgs = this.corrActiveTabOrgs;
            if (orgs.length === 1) {
                f.activeOrgPk = orgs[0].organization_pk;
                this.corrSelectOrg(f.org, orgs[0]);
            } else {
                f.activeOrgPk = "";
                this.corrClearPicker(f.org);
            }
            // The register changed, so anything derived from it must follow:
            // the circular controls, and the recipient (whose candidates are
            // that register's descendants — a stale pick could now be
            // outside the new register's subtree entirely).
            this.corrSyncBroadcastToOrg();
            this.corrClearPicker(f.recipientOrg);
        },

        corrSelectOrgChoice(organizationPk) {
            const f = this.corrCreateForm;
            const org = this.corrActiveTabOrgs.find(o => o.organization_pk === organizationPk);
            if (org) {
                f.activeOrgPk = organizationPk;
                this.corrSelectOrg(f.org, org);
                this.corrSyncBroadcastToOrg();
                this.corrClearPicker(f.recipientOrg);
            }
        },

        // GET /foundation/documents needs FOUNDATION_VIEW, which a
        // Correspondence-only admin may not hold. A 403 here is expected
        // and non-fatal: the Documents sub-section's x-if below falls
        // back to a manual document_master_pk input when this list is
        // empty, instead of blocking document association entirely.
        async corrLoadDocumentOptions() {
            if (this.corrDocumentOptions.length || this.corrDocumentOptionsError) return;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/foundation/documents");
                if (res.ok) {
                    this.corrDocumentOptions = await res.json();
                } else if (res.status === 403) {
                    this.corrDocumentOptionsError = "You do not have permission to browse the document catalog — enter the Document PK directly below.";
                }
            } catch { /* non-fatal */ }
        },

        async loadCorrespondence() {
            if (this.corrLoading) return;
            this.corrLoading = true;
            this.corrError = "";
            this.corrLoadCatalog();
            try {
                const params = new URLSearchParams({ page: this.corrPage, page_size: this.corrPageSize });
                if (this.corrOrgFilter.pk) params.set("register_organization_pk", this.corrOrgFilter.pk);
                if (this.corrDirectionFilter) params.set("direction", this.corrDirectionFilter);
                if (this.corrStatusFilter) params.set("status", this.corrStatusFilter);
                const res = await NSSAuth.apiFetch(`/api/v1/correspondence?${params}`);
                if (res.status === 403) { this.corrError = "You do not have permission to view the Correspondence Register."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                const data = await res.json();
                this.corrItems = data.items;
                this.corrTotal = data.total;
            } catch (err) {
                this.corrError = err.message || "Failed to load the Correspondence Register.";
            } finally {
                this.corrLoading = false;
            }
        },

        corrChangePage(delta) {
            this.corrPage += delta;
            this.loadCorrespondence();
        },

        // ── Shared person/organization type-ahead pickers ───────
        // One pair of generic helpers backs every picker object
        // ({ query, results, searching, selected }) on this page —
        // Create form's sender/recipient/responsible-at-creation
        // fields, the list filter, the responsible-party reassignment
        // control. Avoids ~10 near-identical search functions.

        corrOnPersonQueryInput(picker) {
            clearTimeout(picker._timer);
            picker.selected = null;
            const q = (picker.query || "").trim();
            if (q.length < 2) { picker.results = []; return; }
            picker._timer = setTimeout(() => this.corrSearchPerson(picker), 300);
        },

        async corrSearchPerson(picker) {
            picker.searching = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/person/search?q=${encodeURIComponent(picker.query.trim())}`);
                picker.results = res.ok ? (await res.json()).persons : [];
            } catch {
                picker.results = [];
            } finally {
                picker.searching = false;
            }
        },

        corrSelectPerson(picker, person) {
            picker.selected = person;
            picker.query = `${person.first_name} ${person.last_name || ""}`.trim() + ` (${person.person_id})`;
            picker.results = [];
        },

        corrOnOrgQueryInput(picker) {
            clearTimeout(picker._timer);
            picker.selected = null;
            const q = (picker.query || "").trim();
            if (q.length < 2) { picker.results = []; return; }
            picker._timer = setTimeout(() => this.corrSearchOrg(picker), 300);
        },

        async corrSearchOrg(picker) {
            picker.searching = true;
            try {
                const params = new URLSearchParams({ search: picker.query.trim(), page_size: 20 });
                const res = await NSSAuth.apiFetch(`/api/v1/admin/organizations?${params}`);
                picker.results = res.ok ? (await res.json()).organizations : [];
            } catch {
                picker.results = [];
            } finally {
                picker.searching = false;
            }
        },

        corrSelectOrg(picker, org) {
            picker.selected = org;
            // Two source shapes reach this: /admin/organizations search hits
            // carry type_name/type_code, while this.organizations entries (the
            // register tabs' dropdown and the recipient candidates) carry
            // organization_type_name/organization_type_code. Reading only the
            // first pair rendered "Name (undefined)" for the latter.
            const typeLabel = org.type_name || org.organization_type_name
                || org.type_code || org.organization_type_code;
            picker.query = typeLabel
                ? `${org.organization_name} (${typeLabel})`
                : org.organization_name;
            picker.results = [];
        },

        corrClearPicker(picker) {
            picker.selected = null;
            picker.query = "";
            picker.results = [];
        },

        // ── List filter ──────────────────────────────────────────

        corrApplyFilters() {
            this.corrPage = 1;
            this.loadCorrespondence();
        },

        corrClearOrgFilter() {
            this.corrOrgFilter = { pk: "", query: "", results: [], searching: false, selected: null };
            this.corrApplyFilters();
        },

        // ── Create ───────────────────────────────────────────────

        // Live "From → To" summaries for the .corr-flow strip, which states
        // the record's direction instead of asking for it (owner-confirmed
        // 2026-10-25: Send is always OUTWARD and Receive always INWARD for
        // the logged-in admin's own organization, so a direction dropdown
        // on this form was redundant and confusing). Returns "" while the
        // other party is still unfilled — the markup renders a muted
        // placeholder in that case rather than an empty line.
        _corrPartySummary(type, personPicker, orgPicker, externalName) {
            const f = this.corrCreateForm;
            if (type === "PERSON") {
                const p = f[personPicker].selected;
                return p ? `${p.first_name} ${p.last_name || ""}`.trim() : "";
            }
            if (type === "ORGANIZATION") {
                const o = f[orgPicker].selected;
                return o ? o.organization_name : "";
            }
            const name = (f[externalName] || "").trim();
            return name;
        },

        get corrSenderSummary() {
            const f = this.corrCreateForm;
            return this._corrPartySummary(
                f.sender_type, "senderPerson", "senderOrg", "sender_external_name",
            );
        },

        get corrRecipientSummary() {
            const f = this.corrCreateForm;
            return this._corrPartySummary(
                f.recipient_type, "recipientPerson", "recipientOrg", "recipient_external_name",
            );
        },

        corrResetCreateForm() {
            const empty = () => ({ query: "", results: [], searching: false, selected: null });
            this.corrCreateForm = {
                show: false, saving: false, error: "",
                org: empty(), orgAutoResolved: false, orgPickerExpanded: false,
                orgTabGroups: [], orgMultipleChoices: false,
                activeOrgTab: "", activeOrgPk: "",
                direction: "INWARD",
                date: "", splitDates: false,
                correspondence_date: "", received_or_sent_date: "", follow_up_date: "",
                subject: "", remarks: "", medium: "",
                isBroadcast: false, broadcastRecipientTypeCode: "",
                moreOptions: false, usPartyOverride: false,
                sender_type: "PERSON",
                sender_person_capacity: "",
                senderPerson: empty(), senderPersonOrg: empty(), senderOrg: empty(),
                sender_external_name: "", sender_external_organization: "",
                recipient_type: "ORGANIZATION",
                recipientPerson: empty(), recipientOrg: empty(),
                recipient_external_name: "", recipient_external_organization: "",
                responsiblePerson: empty(), responsibleOrg: empty(),
                inReplyToPk: "", replyingToReference: "",
            };
        },

        // direction is optional — the two quick-action buttons ("Send
        // Application" / "Receive Application") pass OUTWARD/INWARD to
        // preset the register's direction; omitted it defaults to INWARD
        // same as before.
        toggleCorrCreateForm(direction) {
            if (this.corrCreateForm.show) {
                this.corrResetCreateForm();
            } else {
                this.corrResetCreateForm();
                this.corrCreateForm.show = true;
                this.corrCreateForm.direction = direction === "OUTWARD" ? "OUTWARD" : "INWARD";
                // Date defaults to today — the overwhelmingly common case
                // (same-day filing); splitDates reveals the two original
                // independent fields when that's not true.
                this.corrCreateForm.date = new Date().toISOString().slice(0, 10);
                this.corrLoadCatalog();
                this.corrResolveDefaultOrg();
            }
        },

        // Reply (v1.2, owner 2026-10-26: "we should also add reply option to
        // letter too. which will have its own numbers (conceptually same
        // process)") — opens the ordinary create form, pre-filled from the
        // letter being replied to, rather than a separate reply-specific
        // endpoint/payload: a reply IS just a new correspondence row (own
        // reference_number via the normal counter) that additionally
        // carries in_reply_to_correspondence_pk. `original` is the detail
        // view's corrSelected.
        replyToCorrespondence(original) {
            this.corrResetCreateForm();
            const f = this.corrCreateForm;
            f.show = true;
            // The create form lives inside the "!corrSelected" wrapper (same
            // markup the list view uses) — Reply is launched FROM the detail
            // view (corrSelected still set), so without this the form opens
            // but stays invisible behind the still-showing detail panel
            // (bug reported 2026-10-26: "REPLY TO CORRESPONDENCE LETTER NOT
            // WORKING. nothing happening"). Mirrors what backToCorrList()
            // clears, minus the list reload — reply doesn't need one yet.
            this.corrSelected = null;
            f.direction = original.direction === "OUTWARD" ? "INWARD" : "OUTWARD";
            f.date = new Date().toISOString().slice(0, 10);
            f.inReplyToPk = original.correspondence_pk;
            f.replyingToReference = original.reference_number;
            f.subject = "Re: " + (original.subject || "").replace(/^re:\s*/i, "");

            // Filed under the SAME register the original lives in — a reply
            // is always written as/to whoever that register belongs to.
            const regOrg = this.organizations.find(
                o => o.organization_pk === original.register_organization_pk
            );
            if (regOrg) {
                this.corrSelectOrg(f.org, regOrg);
                f.orgAutoResolved = true;
            }
            // Else: leave org unresolved — the manual search picker (reset's
            // default) covers it, same as any other letter with no scope
            // match. Shouldn't normally happen; a correspondence's own
            // register is always a real, loaded organization.

            // The "other party" carries over unchanged from the original —
            // only WHICH form field it occupies (sender vs recipient) flips,
            // mirroring the direction flip: whichever party was NOT "us" in
            // the original stays NOT "us" here, it just changes slot name.
            if (original.direction === "INWARD") {
                this.corrPrefillParty("recipient", original, "sender");
            } else {
                this.corrPrefillParty("sender", original, "recipient");
            }

            this.corrLoadCatalog();
            this.corrSyncBroadcastToOrg();
        },

        // Shared by replyToCorrespondence(): copies one party's resolved
        // identity from a CorrespondenceResponse (fromPrefix: "sender" or
        // "recipient" on the ORIGINAL record) onto this form's matching
        // type/picker/external fields (toPrefix: "sender" or "recipient" —
        // the opposite one, per the direction flip above). Capacity-only
        // fields (sender_person_capacity, the "acting for" org) have no
        // equivalent to carry over and are deliberately left for the admin
        // to fill fresh when toPrefix is "sender" and the party is a PERSON.
        corrPrefillParty(toPrefix, original, fromPrefix) {
            const f = this.corrCreateForm;
            const type = original[`${fromPrefix}_type`];
            f[`${toPrefix}_type`] = type;
            if (type === "PERSON") {
                const pk = original[`${fromPrefix}_person_pk`];
                if (!pk) return;
                const name = original[`${fromPrefix}_person_name`] || "";
                f[`${toPrefix}Person`].selected = { person_pk: pk, first_name: name, last_name: "", person_id: "" };
                f[`${toPrefix}Person`].query = name;
            } else if (type === "ORGANIZATION") {
                const pk = original[`${fromPrefix}_organization_pk`];
                if (!pk) return;
                const name = original[`${fromPrefix}_organization_name`] || "";
                f[`${toPrefix}Org`].selected = { organization_pk: pk, organization_name: name };
                f[`${toPrefix}Org`].query = name;
            } else if (type === "EXTERNAL") {
                f[`${toPrefix}_external_name`] = original[`${fromPrefix}_external_name`] || "";
                f[`${toPrefix}_external_organization`] = original[`${fromPrefix}_external_organization`] || "";
            }
        },

        // Shared by the circular's "Send To Every" select and the
        // From/To flow strip's own label — resolves an ORGANIZATION_TYPE
        // value_code to its display name from the already-loaded
        // orgTypes catalog (loadOrgTypes(), awaited in init()'s own
        // Promise.all — no new fetch).
        corrOrgTypeName(valueCode) {
            return (this.orgTypes.find(t => t.value_code === valueCode) || {}).value_name || valueCode;
        },

        // Circular eligibility (owner 2026-10-26: the circular "should be
        // inside kendra sangha, anchalaika/zilla tab only.. they are the
        // parents to multiple sakhas and other org types"). A circular is
        // offered ONLY when the selected register org is one of these three
        // parent types — a Sakha or Patha Chakra register never shows it.
        // The selected org can come from either source shape: a tab/
        // this.organizations entry (organization_type_code) or the manual
        // search picker (/admin/organizations → type_code).
        get corrCanBroadcast() {
            const o = this.corrCreateForm.org.selected;
            if (!o) return false;
            const t = o.organization_type_code || o.type_code;
            return ["KENDRA", "ANCHALIKA_SANGHA", "ZILLA_SANGHA"].includes(t);
        },

        // "Send To Every <type>" options (owner 2026-10-26: "we cannot add
        // all types in dropdown. check the repo for parent and child
        // relationship. (always exclude kutira and smurti mandira)").
        // POST /correspondence/broadcast targets the RECURSIVE subtree of the
        // register org (org_subtree_pks), filtered to one descendant type —
        // so the only sensible options are the descendant org types actually
        // present under the selected org. We walk the same parent/child links
        // (this.organizations' parent_organization_pk) the backend recursion
        // uses, collect the distinct descendant types, and drop the two apex
        // singletons that are never descendants anyway. This stays WYSIWYG
        // with what the endpoint will really send to (no dead options that
        // would just 422 "no organizations of this type under here").
        // Shared subtree walk (standing no-duplicates rule): every active
        // descendant organization of one org, read from the already-loaded
        // this.organizations tree — the same parent/child links the backend's
        // org_subtree_pks() recursion follows, so the UI can never offer a
        // target the endpoint wouldn't actually reach. Excludes the root
        // itself and the two apex singletons (owner 2026-10-26: "always
        // exclude kutira and smurti mandira") while still traversing THROUGH
        // them, so anything parented under one stays reachable. Backs both the
        // circular's type dropdown and the recipient picker.
        _corrDescendantOrgs(rootPk) {
            if (!rootPk) return [];
            const EXCLUDED = new Set(["NILACHALA_KUTIRA", "SMRUTI_MANDIRA"]);
            const childrenByParent = new Map();
            for (const org of this.organizations) {
                const p = org.parent_organization_pk;
                if (!p) continue;
                if (!childrenByParent.has(p)) childrenByParent.set(p, []);
                childrenByParent.get(p).push(org);
            }
            const seen = new Set([rootPk]);
            const out = [];
            const stack = [rootPk];
            while (stack.length) {
                const pk = stack.pop();
                for (const child of childrenByParent.get(pk) || []) {
                    if (seen.has(child.organization_pk)) continue;   // guards cycles
                    seen.add(child.organization_pk);
                    if (!EXCLUDED.has(child.organization_type_code)) out.push(child);
                    stack.push(child.organization_pk);
                }
            }
            return out;
        },

        get corrBroadcastTypeOptions() {
            const o = this.corrCreateForm.org.selected;
            if (!o) return [];
            const typeCodes = new Set(
                this._corrDescendantOrgs(o.organization_pk).map(d => d.organization_type_code)
            );
            // Preserve orgTypes' display order / option shape.
            return this.orgTypes.filter(t => typeCodes.has(t.value_code));
        },

        // Valid ORGANIZATION recipients (owner 2026-10-26: "in receipient only
        // childrem under that parent should show, not everything else") — the
        // selected register org's own descendants, name-sorted. Filtered
        // client-side from this.organizations (fully loaded in init()) rather
        // than via the global /admin/organizations search the other org
        // pickers use, since that endpoint has no subtree filter to pass.
        //
        // Owner follow-up, same day: "Sakha, pathachakra, anachalik/zilla can
        // send letter to kendra" — the one upward exception. Sakha/Patha
        // Chakra/Anchalika/Zilla additionally get the Kendra org itself as a
        // candidate (Kendra has no parent of its own, so it never needs the
        // reverse case). A Kendra register stays descendants-only — it has
        // nothing further upward to address.
        get corrRecipientOrgCandidates() {
            const o = this.corrCreateForm.org.selected;
            if (!o) return [];
            const out = this._corrDescendantOrgs(o.organization_pk);
            const t = o.organization_type_code || o.type_code;
            if (["SAKHA_SANGHA", "PATHA_CHAKRA", "ANCHALIKA_SANGHA", "ZILLA_SANGHA"].includes(t)) {
                const kendra = this.kendraOrg;
                if (kendra && !out.some(org => org.organization_pk === kendra.organization_pk)) {
                    out.push(kendra);
                }
            }
            return out.sort((a, b) => (a.organization_name || "").localeCompare(b.organization_name || ""));
        },

        // Recipient-org type-ahead. Deliberately NOT corrOnOrgQueryInput /
        // corrSearchOrg: that pair searches every organization in the system,
        // which is exactly what the owner asked to stop. In-memory filtering
        // also needs no debounce and no fetch.
        corrOnRecipientOrgQueryInput(picker) {
            picker.selected = null;
            const q = (picker.query || "").trim().toLowerCase();
            const all = this.corrRecipientOrgCandidates;
            picker.results = (
                q ? all.filter(o => (o.organization_name || "").toLowerCase().includes(q)) : all
            ).slice(0, 20);
        },

        // Whenever the register org changes, keep the circular controls
        // consistent with it: a register that can't circulate (Sakha / Patha
        // Chakra / anything but Kendra-Anchalika-Zilla) must not leave the
        // form armed with a hidden-but-true isBroadcast, and a previously
        // chosen target type that isn't under the new org must be cleared.
        corrSyncBroadcastToOrg() {
            const f = this.corrCreateForm;
            if (!this.corrCanBroadcast) {
                f.isBroadcast = false;
                f.broadcastRecipientTypeCode = "";
            } else if (
                f.broadcastRecipientTypeCode &&
                !this.corrBroadcastTypeOptions.some(t => t.value_code === f.broadcastRecipientTypeCode)
            ) {
                f.broadcastRecipientTypeCode = "";
            }
        },

        // Circular (owner request, 2026-10-26: "sometimes, kendra/
        // anchalika/zilla send letter to all sakhas under it. we should
        // have some option") — POST /correspondence/broadcast, one admin
        // action instead of N manual create+dispatch repeats. Always
        // sender=ORGANIZATION (no override), always OUTWARD — both
        // enforced by the markup already hiding the controls that would
        // let either vary, but re-checked here too since this method
        // doesn't re-run createCorrespondence()'s own validation.
        async createBroadcastCorrespondence() {
            const f = this.corrCreateForm;
            f.error = "";

            if (!f.org.selected) { f.error = "Select the register organization."; return; }
            if (!f.broadcastRecipientTypeCode) { f.error = "Select which organization type to send to."; return; }
            const correspondence_date = f.splitDates ? f.correspondence_date : f.date;
            const received_or_sent_date = f.splitDates ? f.received_or_sent_date : f.date;
            if (!correspondence_date || !received_or_sent_date) {
                f.error = f.splitDates
                    ? "Correspondence date and received/sent date are required."
                    : "Date is required.";
                return;
            }
            if (!f.subject.trim()) { f.error = "Subject is required."; return; }
            if (!f.medium) { f.error = "Medium is required."; return; }

            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/correspondence/broadcast", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        register_organization_pk: f.org.selected.organization_pk,
                        recipient_organization_type_code: f.broadcastRecipientTypeCode,
                        correspondence_date,
                        received_or_sent_date,
                        follow_up_date: f.follow_up_date || null,
                        subject: f.subject.trim(),
                        remarks: f.remarks.trim() || null,
                        medium: f.medium,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                const data = await res.json();
                this.corrResetCreateForm();
                this.corrPage = 1;
                await this.loadCorrespondence();
                this.showToast(`Circular sent to ${data.recipient_count} organization(s).`);
            } catch (err) {
                f.error = err.message || "Failed to send the circular.";
            } finally {
                f.saving = false;
            }
        },

        async createCorrespondence() {
            const f = this.corrCreateForm;
            f.error = "";

            // A circular has its own endpoint/payload shape entirely
            // (CorrespondenceBroadcastCreate has no sender_*/recipient_*
            // fields at all) — delegate rather than branch every field
            // below for a case that never shares them.
            if (f.isBroadcast) { return this.createBroadcastCorrespondence(); }

            if (!f.org.selected) { f.error = "Select the register organization."; return; }
            // splitDates=false (the default): both DB dates come from the
            // single collapsed Date field. splitDates=true: the two
            // original independent fields, exactly as before this form
            // was simplified.
            const correspondence_date = f.splitDates ? f.correspondence_date : f.date;
            const received_or_sent_date = f.splitDates ? f.received_or_sent_date : f.date;
            if (!correspondence_date || !received_or_sent_date) {
                f.error = f.splitDates
                    ? "Correspondence date and received/sent date are required."
                    : "Date is required.";
                return;
            }
            if (!f.subject.trim()) { f.error = "Subject is required."; return; }
            if (!f.medium) { f.error = "Medium is required."; return; }

            const body = {
                register_organization_pk: f.org.selected.organization_pk,
                direction: f.direction,
                correspondence_date,
                received_or_sent_date,
                follow_up_date: f.follow_up_date || null,
                subject: f.subject.trim(),
                remarks: f.remarks.trim() || null,
                medium: f.medium,
                responsible_person_pk: f.responsiblePerson.selected ? f.responsiblePerson.selected.person_pk : null,
                responsible_organization_pk: f.responsibleOrg.selected ? f.responsibleOrg.selected.organization_pk : null,
                in_reply_to_correspondence_pk: f.inReplyToPk || null,
            };

            // "Our" side (owner request, 2026-10-25: simpler form) —
            // defaults silently to ORGANIZATION = the register
            // organization, unless usPartyOverride reveals the full
            // picker for it. usIsSender mirrors create_member_application
            // ()'s own OUTWARD/INWARD framing (§4.6): sending FROM us is
            // OUTWARD, receiving addressed TO us is INWARD.
            const usIsSender = f.direction === "OUTWARD";

            if (usIsSender && !f.usPartyOverride) {
                body.sender_type = "ORGANIZATION";
                body.sender_organization_pk = f.org.selected.organization_pk;
            } else if (!usIsSender && !f.usPartyOverride) {
                body.recipient_type = "ORGANIZATION";
                body.recipient_organization_pk = f.org.selected.organization_pk;
            }

            // The sender fields are filled whenever sender is the "other
            // party" (INWARD) OR the override is in effect for an OUTWARD
            // letter — i.e. whenever they were NOT just defaulted above.
            if (!usIsSender || f.usPartyOverride) {
                body.sender_type = f.sender_type;
                if (f.sender_type === "PERSON") {
                    if (!f.senderPerson.selected) { f.error = "Select the sender."; return; }
                    if (!f.sender_person_capacity) { f.error = "Sender capacity (Personal/Organizational) is required."; return; }
                    if (f.sender_person_capacity === "ORGANIZATIONAL" && !f.senderPersonOrg.selected) {
                        f.error = "Select the organization the sender is acting for."; return;
                    }
                    body.sender_person_pk = f.senderPerson.selected.person_pk;
                    body.sender_person_capacity = f.sender_person_capacity;
                    body.sender_person_organization_pk = f.sender_person_capacity === "ORGANIZATIONAL"
                        ? f.senderPersonOrg.selected.organization_pk : null;
                } else if (f.sender_type === "ORGANIZATION") {
                    if (!f.senderOrg.selected) { f.error = "Select the sender organization."; return; }
                    body.sender_organization_pk = f.senderOrg.selected.organization_pk;
                } else {
                    if (!f.sender_external_name.trim()) { f.error = "Sender name is required for an external sender."; return; }
                    body.sender_external_name = f.sender_external_name.trim();
                    body.sender_external_organization = f.sender_external_organization.trim() || null;
                }
            }

            if (usIsSender || f.usPartyOverride) {
                body.recipient_type = f.recipient_type;
                if (f.recipient_type === "PERSON") {
                    if (!f.recipientPerson.selected) { f.error = "Select the recipient."; return; }
                    body.recipient_person_pk = f.recipientPerson.selected.person_pk;
                } else if (f.recipient_type === "ORGANIZATION") {
                    if (!f.recipientOrg.selected) { f.error = "Select the recipient organization."; return; }
                    body.recipient_organization_pk = f.recipientOrg.selected.organization_pk;
                } else {
                    if (!f.recipient_external_name.trim()) { f.error = "Recipient name is required for an external recipient."; return; }
                    body.recipient_external_name = f.recipient_external_name.trim();
                    body.recipient_external_organization = f.recipient_external_organization.trim() || null;
                }
            }

            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch("/api/v1/correspondence", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.corrResetCreateForm();
                this.corrPage = 1;
                await this.loadCorrespondence();
            } catch (err) {
                f.error = err.message || "Failed to register correspondence.";
            } finally {
                f.saving = false;
            }
        },

        // ── Detail (list ↔ detail toggle, same shape as Claims'
        //    selectedClaim rather than a true in-row expand — this
        //    record carries too many fields + two sub-resources to
        //    read comfortably inside a table row) ──────────────────

        async viewCorrespondence(pk) {
            this.corrDetailError = "";
            this.corrDetailLoading = true;
            this.corrHistory = { events: [], ancestors: [], descendants: [] };
            this.corrHistoryError = "";
            this.corrResponsibleForm = {
                show: false, saving: false, error: "", mode: "person",
                person: { query: "", results: [], searching: false, selected: null },
                org: { query: "", results: [], searching: false, selected: null },
            };
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/correspondence/${pk}`);
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.corrSelected = await res.json();
                this.loadCorrDocuments();
                this.loadCorrFinanceRefs();
                this.loadCorrHistory();
            } catch (err) {
                this.corrDetailError = err.message || "Failed to load correspondence detail.";
            } finally {
                this.corrDetailLoading = false;
            }
        },

        backToCorrList() {
            this.corrSelected = null;
            this.corrDetailError = "";
            this.loadCorrespondence();
        },

        // The manual status-transition box in admin.html (and its next-status/
        // reopen/submit helpers and valid-transition tables here) was removed
        // 2026-10-26 (owner: "remove the
        // trnasition status box entirely" — after the event-driven lifecycle
        // amendment made the REGISTERED->PENDING_ACTION and ->ACTIONED hops
        // automatic, the manual dropdown mostly just confused what was now
        // happening on its own). The POST /{pk}/transition endpoint itself is
        // UNCHANGED and still live — this only removes its one UI surface.
        // Net effect: there is currently no UI control left for ACTIONED->
        // CLOSED or for reopening (ACTIONED/CLOSED->PENDING_ACTION, §6.3) —
        // those remain reachable only via direct API call. Flagged, not
        // silently dropped — a lighter "Close"/"Reopen" control may be
        // wanted back as a follow-up.

        // ── Dispatch (v1.1, owner-confirmed 2026-10-25) — mints the
        //    recipient organization's own linked INWARD counterpart row.
        //    Only ever shown (admin.html) for an OUTWARD row addressed to
        //    recipient_type=ORGANIZATION with no counterpart yet; the API
        //    independently re-validates all of that (422/409) regardless
        //    of what this button's visibility already implies.
        async dispatchCorrespondence() {
            const f = this.corrDispatchForm;
            f.error = "";
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch(
                    `/api/v1/correspondence/${this.corrSelected.correspondence_pk}/dispatch`,
                    { method: "POST" },
                );
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.corrSelected = await res.json();
                await this.loadCorrespondence();
            } catch (err) {
                f.error = err.message || "Failed to dispatch this correspondence.";
            } finally {
                f.saving = false;
            }
        },

        // ── Responsible-party reassignment (§5.4) — a distinct
        //    endpoint from status transition; never itself moves status.
        async submitCorrResponsibleParty() {
            const f = this.corrResponsibleForm;
            f.error = "";
            let responsible_person_pk = null;
            let responsible_organization_pk = null;
            if (f.mode === "person") {
                if (!f.person.selected) { f.error = "Select the responsible person."; return; }
                responsible_person_pk = f.person.selected.person_pk;
            } else if (f.mode === "organization") {
                if (!f.org.selected) { f.error = "Select the responsible organization."; return; }
                responsible_organization_pk = f.org.selected.organization_pk;
            } // mode === "clear" leaves both null

            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/correspondence/${this.corrSelected.correspondence_pk}/responsible-party`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ responsible_person_pk, responsible_organization_pk }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.corrSelected = await res.json();
                this.corrResponsibleForm = {
                    show: false, saving: false, error: "", mode: "person",
                    person: { query: "", results: [], searching: false, selected: null },
                    org: { query: "", results: [], searching: false, selected: null },
                };
            } catch (err) {
                f.error = err.message || "Failed to reassign the responsible party.";
            } finally {
                f.saving = false;
            }
        },

        // ── Documents sub-section ────────────────────────────────

        async loadCorrDocuments() {
            if (!this.corrSelected) return;
            this.corrDocumentsLoading = true;
            this.corrDocumentsError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/correspondence/${this.corrSelected.correspondence_pk}/documents`);
                if (res.status === 403) { this.corrDocumentsError = "You do not have permission to view attached documents."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.corrDocuments = (await res.json()).items;
            } catch (err) {
                this.corrDocumentsError = err.message || "Failed to load documents.";
            } finally {
                this.corrDocumentsLoading = false;
            }
        },

        toggleCorrDocumentForm() {
            this.corrDocumentForm.show = !this.corrDocumentForm.show;
            if (this.corrDocumentForm.show) this.corrLoadDocumentOptions();
        },

        async addCorrDocument() {
            const f = this.corrDocumentForm;
            f.error = "";
            if (!f.document_master_pk.trim()) { f.error = "Select or enter a Document PK."; return; }
            if (!f.document_purpose) { f.error = "Document purpose is required."; return; }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/correspondence/${this.corrSelected.correspondence_pk}/documents`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        document_master_pk: f.document_master_pk.trim(),
                        document_purpose: f.document_purpose,
                        remarks: f.remarks ? f.remarks.trim() || null : null,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.corrDocuments.unshift(await res.json());
                this.corrDocumentForm = { show: false, saving: false, error: "", document_master_pk: "", document_purpose: "ORIGINAL", remarks: "" };
            } catch (err) {
                f.error = err.message || "Failed to attach the document.";
            } finally {
                f.saving = false;
            }
        },

        // ── Finance references sub-section ──────────────────────
        // financial_transaction_pk has no FK/existence check — Finance
        // (Tier 12) doesn't exist yet (api/routers/correspondence.py
        // §9.3 note) — the hint shown next to the input is load-bearing,
        // not decorative.

        async loadCorrFinanceRefs() {
            if (!this.corrSelected) return;
            this.corrFinanceRefsLoading = true;
            this.corrFinanceRefsError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/correspondence/${this.corrSelected.correspondence_pk}/finance-references`);
                if (res.status === 403) { this.corrFinanceRefsError = "You do not have permission to view finance references."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.corrFinanceRefs = (await res.json()).items;
            } catch (err) {
                this.corrFinanceRefsError = err.message || "Failed to load finance references.";
            } finally {
                this.corrFinanceRefsLoading = false;
            }
        },

        toggleCorrFinanceForm() {
            this.corrFinanceForm.show = !this.corrFinanceForm.show;
            if (this.corrFinanceForm.show) this.corrLoadCatalog();
        },

        // ── History + reply-thread path tracker ──────────────────
        // (owner 2026-10-26: "can we add history with path tracker for
        // correspondance?") — one GET, both parts of the response.
        async loadCorrHistory() {
            if (!this.corrSelected) return;
            this.corrHistoryLoading = true;
            this.corrHistoryError = "";
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/correspondence/${this.corrSelected.correspondence_pk}/history`);
                if (res.status === 403) { this.corrHistoryError = "You do not have permission to view this record's history."; return; }
                if (!res.ok) throw new Error(await NSS.extractError(res));
                this.corrHistory = await res.json();
            } catch (err) {
                this.corrHistoryError = err.message || "Failed to load history.";
            } finally {
                this.corrHistoryLoading = false;
            }
        },

        async addCorrFinanceRef() {
            const f = this.corrFinanceForm;
            f.error = "";
            if (!f.financial_transaction_pk.trim()) { f.error = "Financial transaction reference is required."; return; }
            if (!f.relationship_type) { f.error = "Relationship type is required."; return; }
            f.saving = true;
            try {
                const res = await NSSAuth.apiFetch(`/api/v1/correspondence/${this.corrSelected.correspondence_pk}/finance-references`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        financial_transaction_pk: f.financial_transaction_pk.trim(),
                        relationship_type: f.relationship_type,
                        remarks: f.remarks ? f.remarks.trim() || null : null,
                    }),
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    f.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.corrFinanceRefs.unshift(await res.json());
                this.corrFinanceForm = { show: false, saving: false, error: "", financial_transaction_pk: "", relationship_type: "", remarks: "" };
            } catch (err) {
                f.error = err.message || "Failed to add the finance reference.";
            } finally {
                f.saving = false;
            }
        },
    });
}
