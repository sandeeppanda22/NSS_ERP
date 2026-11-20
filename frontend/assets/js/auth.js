/**
 * NSS ERP — Authentication Utilities (Tier 5)
 *
 * Shared auth layer for all authenticated pages.
 * Manages JWT tokens in localStorage, provides authenticated
 * fetch wrapper, handles token refresh and forced logout.
 *
 * Include this BEFORE page-specific JS on any authenticated page.
 *
 * Usage:
 *   const data = await NSSAuth.apiFetch("/api/v1/admin/users");
 *   NSSAuth.logout();
 *   NSSAuth.requireAuth();   // redirects to /login if not logged in
 */

const NSSAuth = {
    TOKEN_KEY: "nss_access_token",
    REFRESH_KEY: "nss_refresh_token",
    USER_KEY: "nss_user",

    // ── Token storage ──────────────────────────────────────────

    getAccessToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    getRefreshToken() {
        return localStorage.getItem(this.REFRESH_KEY);
    },

    setTokens(accessToken, refreshToken) {
        localStorage.setItem(this.TOKEN_KEY, accessToken);
        if (refreshToken) {
            localStorage.setItem(this.REFRESH_KEY, refreshToken);
        }
    },

    clearTokens() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.REFRESH_KEY);
        localStorage.removeItem(this.USER_KEY);
    },

    isLoggedIn() {
        return !!this.getAccessToken();
    },

    // ── User profile cache ─────────────────────────────────────

    getCachedUser() {
        try {
            const raw = localStorage.getItem(this.USER_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch {
            return null;
        }
    },

    setCachedUser(user) {
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    },

    // ── JWT decode (no validation — just payload peek) ─────────

    decodePayload(token) {
        try {
            const base64 = token.split(".")[1];
            const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
            return JSON.parse(json);
        } catch {
            return null;
        }
    },

    isTokenExpired(token) {
        const payload = this.decodePayload(token);
        if (!payload || !payload.exp) return true;
        // 30-second buffer before actual expiry
        return Date.now() / 1000 > payload.exp - 30;
    },

    // ── Token refresh ──────────────────────────────────────────

    async refreshAccessToken() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) return false;

        try {
            const res = await fetch("/api/v1/auth/refresh", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh_token: refreshToken }),
            });

            if (!res.ok) {
                this.clearTokens();
                return false;
            }

            const data = await res.json();
            localStorage.setItem(this.TOKEN_KEY, data.access_token);
            return true;
        } catch {
            return false;
        }
    },

    // ── Authenticated fetch ────────────────────────────────────

    /**
     * Fetch with automatic Bearer token injection and refresh.
     *
     * @param {string} url
     * @param {RequestInit} opts
     * @returns {Promise<Response>}
     */
    async apiFetch(url, opts = {}) {
        // Refresh if access token is expired
        let token = this.getAccessToken();
        if (!token || this.isTokenExpired(token)) {
            const refreshed = await this.refreshAccessToken();
            if (!refreshed) {
                this.logout();
                throw new Error("Session expired. Please log in again.");
            }
            token = this.getAccessToken();
        }

        const headers = {
            ...opts.headers,
            Authorization: `Bearer ${token}`,
        };

        // Set Content-Type for JSON body if not already set
        if (opts.body && typeof opts.body === "string" && !headers["Content-Type"]) {
            headers["Content-Type"] = "application/json";
        }

        // `cache: "no-store"` is listed first so an explicit opts.cache can
        // still override it. The API already sends Cache-Control: no-store
        // (api/middleware.py), but that only governs a response the browser
        // has already fetched — it does not stop the browser reusing a
        // previously cached one, or a bfcache restore replaying stale JSON.
        // Every call here is authenticated, per-user, scope-filtered data
        // where showing a stale copy is a correctness bug, not a perf win.
        const res = await fetch(url, { cache: "no-store", ...opts, headers });

        // If 401, try one refresh cycle
        if (res.status === 401) {
            const refreshed = await this.refreshAccessToken();
            if (refreshed) {
                headers.Authorization = `Bearer ${this.getAccessToken()}`;
                const retried = await fetch(url, { cache: "no-store", ...opts, headers });
                this._noteOwnWrite(url, opts, retried);
                return retried;
            }
            this.logout();
            throw new Error("Session expired. Please log in again.");
        }

        this._noteOwnWrite(url, opts, res);
        return res;
    },

    // A write THIS page just made changes data the live-refresh feed will report; tell it, so the page does not offer itself a
    // "This view has new updates - Refresh" banner for its own save (live-refresh.js: noteOwnWrite).
    _noteOwnWrite(url, opts, res) {
        const method = String((opts && opts.method) || "GET").toUpperCase();
        if (method === "GET" || method === "HEAD" || !res || !res.ok) return;
        if (typeof NSSLiveRefresh !== "undefined" && NSSLiveRefresh.noteOwnWrite) NSSLiveRefresh.noteOwnWrite();
    },

    // ── Auth headers (for manual fetch calls) ───────────────────

    /**
     * Return an Authorization header object for manual fetch calls.
     * Use NSSAuth.apiFetch() when possible (handles refresh automatically).
     * This is for cases where you need raw headers (e.g. in claim-approval).
     */
    authHeaders() {
        const token = this.getAccessToken();
        if (!token) return {};
        return { Authorization: `Bearer ${token}` };
    },

    // ── Navigation helpers ─────────────────────────────────────

    /**
     * Redirect to login if not authenticated.
     * Call at the top of any page that requires auth.
     */
    requireAuth() {
        if (!this.isLoggedIn()) {
            window.location.href = "/login";
            return false;
        }
        return true;
    },

    /**
     * Redirect away from login if already authenticated.
     * Call on the login page.
     */
    redirectIfLoggedIn(target = "/dashboard") {
        if (this.isLoggedIn() && !this.isTokenExpired(this.getAccessToken())) {
            window.location.href = target;
        }
    },

    /**
     * Logout: call API, clear tokens, redirect to login.
     */
    async logout() {
        const token = this.getAccessToken();
        if (token) {
            try {
                await fetch("/api/v1/auth/logout", {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                });
            } catch {
                // Best-effort — server might be unreachable
            }
        }
        this.clearTokens();
        window.location.href = "/login";
    },
};
