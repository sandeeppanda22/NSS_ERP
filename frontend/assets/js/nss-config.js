/**
 * NSS ERP — Shared Configuration & Display Mappings
 *
 * Single source of truth for display name overrides,
 * badge class lookups, and shared constants.
 *
 * Every page includes this before its own module JS.
 * Module JS can call NSS.typeBadgeClass(code) etc.
 * without duplicating the mapping logic.
 *
 * Design rule: value_code is the stable DB key.
 * Display names come from master_data.value_name (API)
 * unless overridden here per NSS Bye-Law terminology.
 */

const NSS = {
    /* ── Shared constants ──────────────────────────────────────
     * Single source of truth for values used across multiple JS files.
     * Avoids magic numbers scattered in register.js, admin.js, etc.
     */
    DEFAULT_COUNTRY_CODE: "+91",
    MAX_PAGE_SIZE: 500,
    PASSWORD_MIN_LENGTH: 8,
    REDIRECT_DELAY_MS: 1500,

    /* ── Membership type display name overrides ──────────────
     * DB stores value_name from master_data.
     * These overrides map value_code → portal display label
     * when the Bye-Law term differs from the DB name.
     *
     * If a code is NOT in this map, use API's value_name as-is.
     * Authority: NSS Bye-Law §B, MBR-007
     */
    TYPE_DISPLAY_NAMES: {
        PROBATIONARY: "Darshaka",
        // REGULAR, ASSOCIATE, HONORARY — use DB value_name as-is
    },

    /**
     * Get display name for a membership type.
     * @param {string} code   - value_code (e.g. "PROBATIONARY")
     * @param {string} dbName - value_name from API (e.g. "Darshaka")
     * @returns {string} display label
     */
    typeDisplayName(code, dbName) {
        return this.TYPE_DISPLAY_NAMES[code] || dbName || code;
    },

    /* ── Badge class lookups ─────────────────────────────────
     * Maps value_code → CSS class from badges.css.
     * Keeps HTML templates clean: :class="NSS.statusBadgeClass(code)"
     */

    STATUS_BADGE_MAP: {
        ACTIVE:              "badge-status-active",
        INACTIVE:            "badge-status-inactive",
        PROPOSED:            "badge-status-proposed",
        APPROVED:            "badge-status-approved",
        SUSPENDED:           "badge-status-suspended",
        LAPSED:              "badge-status-lapsed",
        TRANSFERRED:         "badge-status-transferred",
        RESIGNED:            "badge-status-resigned",
        EXPELLED:            "badge-status-expelled",
        DECEASED:            "badge-status-deceased",
        DISSOLVED:           "badge-status-dissolved",
        ARCHIVED:            "badge-status-archived",
        EXPIRED:             "badge-status-expired",
        CANCELLED:           "badge-status-cancelled",
        REPLACED:            "badge-status-replaced",
        RENEWAL_PENDING:     "badge-status-renewal-pending",
        ON_HOLD:             "badge-status-on-hold",
        DISCIPLINARY_REVIEW: "badge-status-disciplinary-review",
    },

    TYPE_BADGE_MAP: {
        PROBATIONARY: "badge-type-probationary",
        REGULAR:      "badge-type-regular",
        ASSOCIATE:    "badge-type-associate",
        HONORARY:     "badge-type-honorary",
    },

    AFF_BADGE_MAP: {
        ACTIVE:      "badge-aff-active",
        ARCHIVED:    "badge-aff-archived",
        REACTIVATED: "badge-aff-reactivated",
    },

    GENDER_BADGE_MAP: {
        MALE:   "badge-gender-male",
        FEMALE: "badge-gender-female",
        OTHER:  "badge-gender-other",
    },

    // Per-member credential health (admin Credentials tab) — computed
    // server-side in GET /api/v1/admin/credentials/members.
    CREDENTIAL_STATE_BADGE_MAP: {
        OK:       "badge-cred-state-ok",
        EXPIRING: "badge-cred-state-expiring",
        LAPSED:   "badge-cred-state-lapsed",
        MISSING:  "badge-cred-state-missing",
    },

    // Individual Anumati/Parichaya Patra row status (timeline viewer).
    CREDENTIAL_STATUS_BADGE_MAP: {
        ACTIVE:    "badge-cred-status-active",
        EXPIRED:   "badge-cred-status-expired",
        LAPSED:    "badge-cred-status-lapsed",
        CANCELLED: "badge-cred-status-cancelled",
    },

    // user_account.account_status — a separate domain from the STATUS
    // master_data category, so it has its own badge prefix. Values are the
    // full set allowed by chk_user_account_status.
    ACCOUNT_BADGE_MAP: {
        ACTIVE:           "badge-account-active",
        LOCKED:           "badge-account-locked",
        INACTIVE:         "badge-account-inactive",
        PENDING_APPROVAL: "badge-account-pending-approval",
    },

    // registration_claim.claim_status — full set per
    // chk_registration_claim_status.
    CLAIM_BADGE_MAP: {
        PENDING:  "badge-claim-pending",
        APPROVED: "badge-claim-approved",
        REJECTED: "badge-claim-rejected",
    },

    // membership_change_request.status — full set per
    // chk_mem_change_req_status (Sakha Transfer / Apply for Darshak).
    CHANGE_REQUEST_BADGE_MAP: {
        PENDING_SOURCE_RELEASE:      "badge-changereq-pending-release",
        PENDING_DESTINATION_ACCEPT:  "badge-changereq-pending-accept",
        COMPLETED:                   "badge-changereq-completed",
        REJECTED_BY_SOURCE:          "badge-changereq-rejected",
        REJECTED_BY_DESTINATION:     "badge-changereq-rejected",
    },

    // correspondence.status (CORRESPONDENCE_STATUS master_data value_code) —
    // the §6.2 precondition table's four states (api/routers/correspondence.py).
    CORRESPONDENCE_STATUS_BADGE_MAP: {
        REGISTERED:      "badge-corr-status-registered",
        PENDING_ACTION:  "badge-corr-status-pending_action",
        ACTIONED:        "badge-corr-status-actioned",
        CLOSED:          "badge-corr-status-closed",
    },

    // correspondence.direction — INWARD/OUTWARD only.
    CORRESPONDENCE_DIRECTION_BADGE_MAP: {
        INWARD:  "badge-corr-direction-inward",
        OUTWARD: "badge-corr-direction-outward",
    },

    // Human-readable label for the same status values — the raw codes
    // read awkwardly in a member-facing list (e.g. "PENDING_SOURCE_RELEASE").
    CHANGE_REQUEST_STATUS_LABELS: {
        PENDING_SOURCE_RELEASE:     "Awaiting your current Sakha",
        PENDING_DESTINATION_ACCEPT: "Awaiting destination Sakha",
        COMPLETED:                  "Completed",
        REJECTED_BY_SOURCE:         "Rejected by current Sakha",
        REJECTED_BY_DESTINATION:    "Rejected by destination Sakha",
    },

    /**
     * Lifecycle status → badge CSS class.
     * @param {string} code - status value_code
     * @returns {string} CSS class
     */
    statusBadgeClass(code) {
        return this.STATUS_BADGE_MAP[code] || "badge-muted";
    },

    /**
     * Membership type → badge CSS class.
     * @param {string} code - membership_type value_code
     * @returns {string} CSS class
     */
    typeBadgeClass(code) {
        return this.TYPE_BADGE_MAP[code] || "badge-muted";
    },

    /**
     * Affiliation status → badge CSS class.
     * @param {string} status - affiliation_status string
     * @returns {string} CSS class
     */
    affBadgeClass(status) {
        return this.AFF_BADGE_MAP[status] || "badge-muted";
    },

    /**
     * Gender code → badge CSS class.
     * @param {string} code - gender value_code
     * @returns {string} CSS class
     */
    genderBadgeClass(code) {
        return this.GENDER_BADGE_MAP[code] || "badge-muted";
    },

    /**
     * Per-member credential health → badge CSS class.
     * @param {string} state - OK | EXPIRING | LAPSED | MISSING
     * @returns {string} CSS class
     */
    credentialStateBadgeClass(state) {
        return this.CREDENTIAL_STATE_BADGE_MAP[state] || "badge-muted";
    },

    /**
     * Individual Anumati/Parichaya Patra row status → badge CSS class.
     * @param {string} status - ACTIVE | EXPIRED | LAPSED | CANCELLED
     * @returns {string} CSS class
     */
    credentialStatusBadgeClass(status) {
        return this.CREDENTIAL_STATUS_BADGE_MAP[status] || "badge-muted";
    },

    /**
     * User account status → badge CSS class.
     * @param {string} status - user_account.account_status
     * @returns {string} CSS class
     */
    accountBadgeClass(status) {
        return this.ACCOUNT_BADGE_MAP[status] || "badge-muted";
    },

    /**
     * Registration claim status → badge CSS class.
     * @param {string} status - registration_claim.claim_status
     * @returns {string} CSS class
     */
    claimBadgeClass(status) {
        return this.CLAIM_BADGE_MAP[status] || "badge-muted";
    },

    /**
     * Membership change-request status → badge CSS class.
     * @param {string} status - membership_change_request.status
     * @returns {string} CSS class
     */
    changeRequestBadgeClass(status) {
        return this.CHANGE_REQUEST_BADGE_MAP[status] || "badge-muted";
    },

    /**
     * Membership change-request status → human-readable label.
     * @param {string} status - membership_change_request.status
     * @returns {string} label text
     */
    changeRequestStatusLabel(status) {
        return this.CHANGE_REQUEST_STATUS_LABELS[status] || status;
    },

    /**
     * Correspondence status (REGISTERED/PENDING_ACTION/ACTIONED/CLOSED)
     * → badge CSS class.
     * @param {string} status - correspondence.status_value_code
     * @returns {string} CSS class
     */
    correspondenceStatusBadgeClass(status) {
        return this.CORRESPONDENCE_STATUS_BADGE_MAP[status] || "badge-muted";
    },

    /**
     * Correspondence direction (INWARD/OUTWARD) → badge CSS class.
     * @param {string} direction - correspondence.direction
     * @returns {string} CSS class
     */
    correspondenceDirectionBadgeClass(direction) {
        return this.CORRESPONDENCE_DIRECTION_BADGE_MAP[direction] || "badge-muted";
    },

    /* ── Document visibility rules ──────────────────────────────
     * Authority: NSS Bye-Law §B, MBR-019A/B
     *
     * Parichaya Patra:  All membership types (REGULAR, ASSOCIATE, HONORARY, PROBATIONARY)
     * Anumati Patra:    Darshaka (PROBATIONARY) and Regular only — NOT Associate (MBR-019A/B)
     *
     * Use these helpers in x-show / x-if to keep visibility
     * rules consistent across all pages.
     */

    /**
     * Whether Parichaya Patra section should be shown.
     * @param {string} typeCode - membership_type_code
     * @returns {boolean}
     */
    showParichayaPatra(typeCode) {
        return true; // All membership types receive Parichaya Patra
    },

    /**
     * Whether Anumati Patra section should be shown.
     * Darshaka (PROBATIONARY) receives Anumati Patra.
     * Associate does NOT (MBR-019A/B).
     * @param {string} typeCode - membership_type_code
     * @returns {boolean}
     */
    showAnumatiPatra(typeCode) {
        return typeCode !== "ASSOCIATE";
    },

    /* ── Table sorting ─────────────────────────────────────────────────
     * Shared click-to-sort primitive for every data table in the portal.
     *
     * Two modes, and the distinction matters for correctness:
     *
     *   CLIENT-SIDE (sortRows) — only valid when the table holds the
     *     COMPLETE result set. Sorting a single page of a server-paginated
     *     list reorders just the visible rows, which tells the user
     *     "A–Z" while showing them A–Z *within page 3*. That is wrong,
     *     not merely limited, so paginated tables must sort server-side
     *     by sending sort_by/sort_dir and re-fetching from page 1.
     *
     *   SERVER-SIDE — the same toggleSort/sortIcon state helpers apply;
     *     only the follow-up action differs (re-fetch vs re-slice).
     *
     * Ordering rules, applied uniformly so every table behaves alike:
     *   - Blank/null always sorts LAST, in both directions. A missing
     *     value is not "smallest"; burying it is what users expect.
     *   - Natural numeric ordering, so SS2 precedes SS10 and AMSAS9
     *     precedes AMSAS100. Plain string compare gets this backwards
     *     and it is the dominant ID shape in this system.
     *   - Real dates compare chronologically, not as display text.
     */

    SORT_DIR_ASC: "asc",
    SORT_DIR_DESC: "desc",

    /**
     * True for values that must always sink to the bottom of the list.
     * Note 0 and false are NOT blank — only null/undefined/empty string.
     * @param {*} v
     * @returns {boolean}
     */
    isBlankValue(v) {
        return v === null || v === undefined || (typeof v === "string" && v.trim() === "");
    },

    /**
     * Compare two cell values. Returns <0, 0 or >0 (ascending sense).
     * Blanks are handled by the caller so they can ignore direction.
     * @param {*} a
     * @param {*} b
     * @returns {number}
     */
    compareValues(a, b) {
        // Booleans: false before true.
        if (typeof a === "boolean" || typeof b === "boolean") {
            return (a ? 1 : 0) - (b ? 1 : 0);
        }

        // Real numbers compare numerically.
        if (typeof a === "number" && typeof b === "number") {
            return a - b;
        }

        const sa = String(a);
        const sb = String(b);

        // ISO date / datetime strings compare chronologically. Restricted
        // to the ISO shape on purpose — Date.parse() is far too willing,
        // and "SS1" or a bare number must not be read as a date.
        const iso = /^\d{4}-\d{2}-\d{2}([T ]|$)/;
        if (iso.test(sa) && iso.test(sb)) {
            const ta = Date.parse(sa);
            const tb = Date.parse(sb);
            if (!Number.isNaN(ta) && !Number.isNaN(tb)) return ta - tb;
        }

        // Everything else: natural compare, so embedded numbers order
        // numerically (SS2 < SS10) and case does not fragment the list.
        return sa.localeCompare(sb, undefined, {
            numeric: true,
            sensitivity: "base",
        });
    },

    /**
     * Sort a COMPLETE list of rows. Returns a new array — never mutates
     * the source, so Alpine re-renders predictably and the unsorted
     * order stays recoverable.
     *
     * @param {Array} rows
     * @param {string} key - property name, or any key your accessor knows
     * @param {string} dir - "asc" | "desc"
     * @param {function} [accessor] - (row, key) => value, for computed
     *        columns such as a joined full name
     * @returns {Array} new sorted array
     */
    sortRows(rows, key, dir, accessor) {
        if (!Array.isArray(rows) || !key) return Array.isArray(rows) ? rows : [];
        const get = accessor || ((row, k) => (row ? row[k] : undefined));
        const factor = dir === this.SORT_DIR_DESC ? -1 : 1;

        return [...rows].sort((ra, rb) => {
            const a = get(ra, key);
            const b = get(rb, key);

            // Blanks last regardless of direction — hence before `factor`.
            const ba = this.isBlankValue(a);
            const bb = this.isBlankValue(b);
            if (ba && bb) return 0;
            if (ba) return 1;
            if (bb) return -1;

            return factor * this.compareValues(a, b);
        });
    },

    /**
     * Next sort state for a header click. First click on a new column
     * sorts ascending; clicking the active column flips direction.
     *
     * @param {string} currentKey - currently sorted key ("" if none)
     * @param {string} currentDir - "asc" | "desc"
     * @param {string} clickedKey
     * @returns {{key: string, dir: string}}
     */
    toggleSort(currentKey, currentDir, clickedKey) {
        if (currentKey !== clickedKey) {
            return { key: clickedKey, dir: this.SORT_DIR_ASC };
        }
        return {
            key: clickedKey,
            dir: currentDir === this.SORT_DIR_ASC
                ? this.SORT_DIR_DESC
                : this.SORT_DIR_ASC,
        };
    },

    /**
     * Arrow glyph for a header. Inactive columns get a faint neutral
     * marker so it is discoverable that the header is clickable at all.
     * @param {string} currentKey
     * @param {string} currentDir
     * @param {string} columnKey
     * @returns {string}
     */
    sortIcon(currentKey, currentDir, columnKey) {
        if (currentKey !== columnKey) return "↕";
        return currentDir === this.SORT_DIR_DESC ? "↓" : "↑";
    },

    /**
     * Screen-reader / aria-sort value for a header cell.
     * @param {string} currentKey
     * @param {string} currentDir
     * @param {string} columnKey
     * @returns {string}
     */
    sortAria(currentKey, currentDir, columnKey) {
        if (currentKey !== columnKey) return "none";
        return currentDir === this.SORT_DIR_DESC ? "descending" : "ascending";
    },

    /* ── Shared utility functions ──────────────────────────────────── */

    /**
     * Format a person name from an object with first_name, middle_name, last_name.
     * @param {object} m - object with name fields
     * @returns {string}
     */
    formatName(m) {
        return [m.first_name, m.middle_name, m.last_name].filter(Boolean).join(" ");
    },

    /**
     * Format phone number: "+91 9876543210" or just the number.
     * @param {string} code - country_phone_code
     * @param {string} number - mobile_number
     * @returns {string}
     */
    formatPhone(code, number) {
        if (!number) return "";
        return code ? `${code} ${number}` : number;
    },

    /* ── Country-wise mobile rules ──────────────────────────────
     * MIRRORS api/helpers.py COUNTRY_PHONE_RULES. Keep the two in
     * sync — there is no build step sharing one source across
     * Python and the browser. Keyed by dial code (country_phone_code).
     * Unknown codes fall back to a permissive 7–15 digit range.
     * Authority: MBR-CONTACT-01.
     */
    COUNTRY_PHONE_RULES: {
        "+91":  { name: "India",        min: 10, max: 10, pattern: /^[6-9]\d{9}$/, hint: "10 digits, starting 6–9" },
        "+1":   { name: "US/Canada",    min: 10, max: 10, pattern: /^[2-9]\d{9}$/, hint: "10 digits" },
        "+44":  { name: "UK",           min: 10, max: 10, hint: "10 digits" },
        "+971": { name: "UAE",          min: 9,  max: 9,  hint: "9 digits" },
        "+65":  { name: "Singapore",    min: 8,  max: 8,  pattern: /^[689]\d{7}$/, hint: "8 digits" },
        "+61":  { name: "Australia",    min: 9,  max: 9,  hint: "9 digits" },
        "+966": { name: "Saudi Arabia", min: 9,  max: 9,  hint: "9 digits" },
        "+974": { name: "Qatar",        min: 8,  max: 8,  hint: "8 digits" },
        "+973": { name: "Bahrain",      min: 8,  max: 8,  hint: "8 digits" },
        "+968": { name: "Oman",         min: 8,  max: 8,  hint: "8 digits" },
        "+60":  { name: "Malaysia",     min: 9,  max: 10, hint: "9–10 digits" },
        "+49":  { name: "Germany",      min: 10, max: 11, hint: "10–11 digits" },
        "+33":  { name: "France",       min: 9,  max: 9,  hint: "9 digits" },
        "+81":  { name: "Japan",        min: 10, max: 10, hint: "10 digits" },
        "+86":  { name: "China",        min: 11, max: 11, hint: "11 digits" },
        "+880": { name: "Bangladesh",   min: 10, max: 10, hint: "10 digits" },
        "+977": { name: "Nepal",        min: 10, max: 10, hint: "10 digits" },
        "+94":  { name: "Sri Lanka",    min: 9,  max: 9,  hint: "9 digits" },
        "+975": { name: "Bhutan",       min: 8,  max: 8,  hint: "8 digits" },
    },
    DEFAULT_PHONE_RULE: { name: null, min: 7, max: 15, hint: "7–15 digits" },
    COUNTRY_PHONE_CODE_PATTERN: /^\+[0-9]{1,4}$/,
    EMAIL_PATTERN: /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/,

    /**
     * Validate a mobile number against its country's rule (MBR-CONTACT-01).
     * No-op when no number is supplied. Returns an error string on an
     * invalid value, or "" when valid.
     * @param {string} code - country_phone_code (e.g. "+91")
     * @param {string} number - national mobile number (digits only)
     * @returns {string} error message, or "" if valid
     */
    validateMobile(code, number) {
        if (!number) return "";
        if (!code) return "A country phone code (e.g. +91) is required with a mobile number.";
        if (!this.COUNTRY_PHONE_CODE_PATTERN.test(code))
            return `Country phone code "${code}" is invalid — expected a form like +91.`;
        if (!/^[0-9]+$/.test(number))
            return "Mobile number must contain digits only (no spaces, dashes, or country code).";
        const rule = this.COUNTRY_PHONE_RULES[code] || this.DEFAULT_PHONE_RULE;
        const label = rule.name || "This";
        const n = number.length;
        if (n < rule.min || n > rule.max)
            return `${label} (${code}) mobile number must be ${rule.hint} — got ${n} digits.`;
        if (rule.pattern && !rule.pattern.test(number))
            return `"${number}" is not a valid ${label} (${code}) mobile number — expected ${rule.hint}.`;
        return "";
    },

    /**
     * Validate email format (MBR-CONTACT-02). No-op when empty.
     * @param {string} email
     * @returns {string} error message, or "" if valid
     */
    validateEmail(email) {
        if (!email) return "";
        if (email.length > 254 || !this.EMAIL_PATTERN.test(email))
            return `"${email}" is not a valid email address.`;
        return "";
    },

    /**
     * Hint string for a dial code's expected mobile length (for placeholders).
     * @param {string} code - country_phone_code
     * @returns {string}
     */
    mobileHint(code) {
        return (this.COUNTRY_PHONE_RULES[code] || this.DEFAULT_PHONE_RULE).hint;
    },

    /**
     * Format ISO date string to locale date (e.g. "22 Sep 2026").
     * @param {string} dateStr - ISO date or datetime string
     * @returns {string}
     */
    formatDate(dateStr) {
        if (!dateStr) return "";
        return new Date(dateStr).toLocaleDateString("en-GB", {
            day: "numeric", month: "short", year: "numeric"
        });
    },

    /**
     * Format ISO datetime string to locale date+time.
     * @param {string} dateStr - ISO datetime string
     * @returns {string}
     */
    formatDateTime(dateStr) {
        if (!dateStr) return "";
        return new Date(dateStr).toLocaleString("en-GB", {
            day: "numeric", month: "short", year: "numeric",
            hour: "2-digit", minute: "2-digit"
        });
    },

    /**
     * Escape HTML special characters to prevent XSS.
     * @param {string} s - raw string
     * @returns {string} escaped string
     */
    escapeHtml(s) {
        if (!s) return "";
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    },

    /**
     * A readable sentence for a bare HTTP status, used only when the
     * server sent no `detail` at all (network failure, gateway error,
     * non-JSON body). The user must never be shown a raw status code as
     * the whole message.
     * @param {number} status
     * @returns {string}
     */
    statusMessage(status) {
        switch (status) {
            case 400:
                return "The request could not be processed. Please check the values and try again.";
            case 401:
                return "Your session has ended. Please sign in again.";
            case 403:
                return "You do not have permission to do this.";
            case 404:
                return "The requested record could not be found. It may have been removed.";
            case 409:
                return "That change conflicts with existing data. Please refresh the page and try again.";
            case 422:
                return "Some of the values entered are not valid. Please review them and try again.";
            case 429:
                return "Too many requests in a short time. Please wait a moment and try again.";
            case 500:
            case 502:
            case 503:
            case 504:
                return "The server could not complete the request. Nothing was saved — please try again in a moment.";
            default:
                return status
                    ? "Something went wrong and the request could not be completed. Please try again."
                    : "Could not reach the server. Please check your connection and try again.";
        }
    },

    /**
     * Normalise ANY API error body into a single readable sentence.
     *
     * The backend's error handlers (api/error_handlers.py) already flatten
     * validation errors to a string, so the string branch is the normal
     * path. The array/object branches are a safety net for responses that
     * bypass those handlers — previously `detail.join(" ")` was applied to
     * Pydantic's list of OBJECTS, which renders as the literal text
     * "[object Object] [object Object]".
     *
     * @param {object} data - parsed JSON body (may be {})
     * @param {number} status - HTTP status
     * @returns {string}
     */
    errorMessage(data, status) {
        const detail = data ? data.detail : null;

        if (typeof detail === "string" && detail.trim()) return detail.trim();

        if (Array.isArray(detail)) {
            const parts = detail.map((d) => {
                if (typeof d === "string") return d;
                if (d && typeof d === "object") {
                    const loc = Array.isArray(d.loc)
                        ? d.loc.filter(
                              (p) => !["body", "query", "path", "header", "cookie"].includes(p)
                          )
                        : [];
                    const raw = loc.length ? String(loc[loc.length - 1]) : "";
                    const field = raw
                        .replace(/_master_data_pk$|_pk$/, "")
                        .replace(/_/g, " ")
                        .trim();
                    const msg = d.msg || "is not valid";
                    if (!field) return msg;
                    return `${field.charAt(0).toUpperCase()}${field.slice(1)}: ${msg}.`;
                }
                return "";
            }).filter(Boolean);
            if (parts.length) return parts.join(" ");
        }

        if (detail && typeof detail === "object" && detail.msg) {
            return String(detail.msg);
        }

        return this.statusMessage(status);
    },

    /**
     * Extract a readable error message from a failed fetch Response.
     * @param {Response} res - fetch Response object
     * @returns {Promise<string>} error message — always a non-empty string
     */
    async extractError(res) {
        let data = {};
        try {
            data = await res.json();
        } catch {
            /* empty or non-JSON body — fall through to statusMessage */
        }
        return this.errorMessage(data, res.status);
    },

    /**
     * Check health endpoint and set component.health state.
     * @param {object} component - Alpine component with health.loading, health.connected
     */
    async fetchHealth(component) {
        component.health.loading = true;
        try {
            const res = await fetch("/api/v1/bootstrap/health");
            if (!res.ok) throw new Error(res.statusText);
            const data = await res.json();
            component.health.connected = data.database === "connected";
        } catch {
            component.health.connected = false;
        } finally {
            component.health.loading = false;
        }
    },
};
