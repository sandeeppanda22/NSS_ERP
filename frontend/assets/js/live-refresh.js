/**
 * Live refresh (owner decision 2026-11-03: "make data refresh automatically so
 * users do not have to reload a tab or the page"). ONE poll per open page of
 * GET /api/v1/live/changes, which says only the latest change number of each
 * watched table (the page compares it with the one it saw last); this
 * mixin then re-runs the page's own (scoped) loaders for the tabs that show
 * those tables. Mixed into adminApp() (admin.js) and dashboard() (dashboard.js)
 * with the same property-descriptor pattern as attendance-register.js.
 *
 * What it does NOT touch: the attendance register keeps its own finer-grained
 * poller (attendance-register.js LIVE_POLL, with conflict handling) and no
 * attendance table is on the feed.
 *
 * Contract with the host - `NSSLiveRefresh.install(target, config)`:
 *   config.tableTabs  { table_name: [tabKey, ...] }  which tab(s) a table feeds.
 *                     Declared by the host (LIVE_TABLE_TABS in admin.js /
 *                     dashboard.js); every table named must be in the server's
 *                     LIVE_FEED_TABLES whitelist (api/routers/live.py - the
 *                     authoritative list; tests/api/test_live_changes.py checks).
 *   config.activeTab(host)  -> the host's current tab key.
 *   config.tabs       { tabKey: { reload(host), busy(host), background?, reloadOnOpen? } }
 *       reload  re-run the tab's EXISTING loader (it already uses the current
 *               filters / paging / selection; loaders take {silent:true} so they
 *               neither flash a spinner nor reset the user's view).
 *       busy    "liveBusy()" - true while a create/edit form, modal, dialog or
 *               typed-but-unsaved input is open for that tab; a busy ACTIVE tab
 *               is never reloaded, the banner is shown instead.
 *       background  reload even when the tab is not on screen (sidebar badges).
 *       reloadOnOpen  default true: opening a tab already runs its loader, so a
 *               stale mark is simply cleared on open; set false to reload then.
 *
 * Nested components (the org dashboard's x-data) are not part of the host's
 * scope: they register themselves with NSSLiveRefresh.registerTarget(name, obj)
 * and the host's tab entry calls NSSLiveRefresh.target(name).liveReload().
 */
(function () {
    "use strict";

    /**
     * Poll policy - the ONE place these numbers live (tests/ui/test_ui_live_refresh.py
     * pins them). Simpler sibling of attendance-register.js LIVE_POLL.
     *   ACTIVE_MS / IDLE_MS / IDLE_AFTER_MS: 5 s while there was a change or user
     *     activity in the last IDLE_AFTER_MS, else 15 s.
     *   BACKOFF_MS: consecutive-error delays (the last repeats); a 429's
     *     Retry-After raises the delay if longer; any success resets.
     *   A hidden browser tab is not polled; it refreshes at once on return.
     */
    const LIVE_FEED = Object.freeze({
        ENDPOINT: "/api/v1/live/changes",
        ACTIVE_MS: 5000,
        IDLE_MS: 15000,
        IDLE_AFTER_MS: 60000,
        BACKOFF_MS: Object.freeze([4000, 8000, 16000, 30000]),
        ACTIVITY_EVENTS: Object.freeze(["pointerdown", "keydown"]),
    });

    /** Next poll delay in ms (pure). Errors back off; otherwise active vs idle cadence. */
    function pollDelay(failures, msSinceActivity, retryAfterMs) {
        if (failures > 0) {
            const back = LIVE_FEED.BACKOFF_MS[Math.min(failures, LIVE_FEED.BACKOFF_MS.length) - 1];
            return Math.max(back, retryAfterMs || 0);
        }
        return msSinceActivity >= LIVE_FEED.IDLE_AFTER_MS ? LIVE_FEED.IDLE_MS : LIVE_FEED.ACTIVE_MS;
    }

    /**
     * Which tabs does a poll reply affect (pure)? The server lists EVERY watched
     * table with the change_seq of its latest committed write (no cursor, so a
     * slow transaction can never be skipped). `seen` maps table -> last change_seq
     * seen; a table counts as changed when its number DIFFERS from the one seen
     * (a table first appearing after the baseline counts too). `seen` === null
     * means "no baseline yet": the first reply only records the numbers - what
     * they describe was already visible to the page's initial loads - and
     * affects no tab.
     * Returns { tabs: [tabKey], seen: <new map> }.
     */
    function changedTabs(changed, seen, tableTabs) {
        const nextSeen = { ...(seen || {}) };
        const tabs = new Set();
        for (const ch of changed || []) {
            const seq = Number(ch.change_seq);
            if (!Number.isFinite(seq)) continue;
            const prev = nextSeen[ch.table_name];
            nextSeen[ch.table_name] = seq;
            if (seen === null || prev === seq) continue;
            for (const tab of tableTabs[ch.table_name] || []) tabs.add(tab);
        }
        return { tabs: [...tabs], seen: nextSeen };
    }

    // Nested components (e.g. orgDashboardTab) the host's tab entries reach.
    const targets = {};
    function registerTarget(name, obj) { targets[name] = obj; }
    function unregisterTarget(name, obj) { if (targets[name] === obj) delete targets[name]; }
    function target(name) { return targets[name] || null; }

    const BANNER_ID = "nss-live-banner";
    const BANNER_TEXT = "This view has new updates";
    let runSeq = 0;  // identity of a poller run (Alpine proxies break object ===)

    function liveRefreshMixin(config) {
        return {
            // Banner shown when a change arrived while the active tab was busy.
            liveBannerVisible: false,

            // The banner is built here (once per page, like NSSDialog's overlay)
            // so admin.html and dashboard.html carry no copy of its markup, and
            // its button is wired with addEventListener (CSP: no inline handlers).
            // x-ignore keeps Alpine out of it; inline styles keep it independent
            // of the generated Tailwind bundle.
            _liveSetBanner(visible) {
                this.liveBannerVisible = visible;
                let el = document.getElementById(BANNER_ID);
                if (!el && !visible) return;
                if (!el) {
                    el = document.createElement("div");
                    el.id = BANNER_ID;
                    el.setAttribute("x-ignore", "");
                    el.setAttribute("role", "status");
                    el.style.cssText = "position:fixed;left:50%;bottom:1.25rem;transform:translateX(-50%);z-index:9000;"
                        + "display:none;align-items:center;gap:0.75rem;padding:0.55rem 0.9rem;border-radius:0.5rem;"
                        + "background:#1B2A4A;color:#fff;font-size:0.85rem;box-shadow:0 6px 24px rgba(0,0,0,0.25);";
                    const msg = document.createElement("span");
                    msg.textContent = BANNER_TEXT;
                    const btn = document.createElement("button");
                    btn.type = "button";
                    btn.textContent = "Refresh";
                    btn.style.cssText = "background:#fff;color:#1B2A4A;border:0;border-radius:0.35rem;padding:0.2rem 0.6rem;"
                        + "font-weight:600;cursor:pointer;";
                    btn.addEventListener("click", () => this.liveRefreshNow());
                    el.append(msg, btn);
                    document.body.appendChild(el);
                }
                el.style.display = visible ? "flex" : "none";
            },

            _liveRun: null,   // poller state, created by liveStart()

            liveStart() {
                this.liveStop();
                const run = {
                    id: ++runSeq, gen: 0, timer: null, seen: null,
                    failures: 0, retryAfterMs: 0, busy: false,
                    activityAt: Date.now(), stale: new Set(), bannerTab: null,
                    onVis: null, onActivity: null,
                };
                this._liveRun = run;
                run.onVis = () => {
                    // Back on screen: poll now and return to the fast cadence.
                    if (!document.hidden && this._liveRun && this._liveRun.id === run.id) {
                        run.activityAt = Date.now();
                        this._liveSchedule(0);
                    }
                };
                run.onActivity = () => { run.activityAt = Date.now(); };
                document.addEventListener("visibilitychange", run.onVis);
                for (const ev of LIVE_FEED.ACTIVITY_EVENTS) document.addEventListener(ev, run.onActivity, { passive: true });
                this._liveSchedule(0);
            },

            liveStop() {
                const run = this._liveRun;
                if (!run) return;
                run.gen++;
                clearTimeout(run.timer);
                document.removeEventListener("visibilitychange", run.onVis);
                for (const ev of LIVE_FEED.ACTIVITY_EVENTS) document.removeEventListener(ev, run.onActivity);
                this._liveRun = null;
                this._liveSetBanner(false);
            },

            _liveSchedule(delayMs) {
                const run = this._liveRun;
                if (!run) return;
                clearTimeout(run.timer);
                const gen = run.gen;
                run.timer = setTimeout(() => this._livePoll(gen), delayMs);
            },

            async _livePoll(gen) {
                const run = this._liveRun;
                if (!run || gen !== run.gen) return;
                // Hidden browser tab: no request, no timer; visibilitychange resumes.
                if (document.hidden) return;
                if (run.busy) return;
                run.busy = true;
                try {
                    const res = await NSSAuth.apiFetch(LIVE_FEED.ENDPOINT);
                    if (gen !== run.gen) return;
                    if (!res.ok) {
                        const ra = Number(res.headers && res.headers.get && res.headers.get("Retry-After"));
                        run.retryAfterMs = res.status === 429 && ra > 0 ? ra * 1000 : 0;
                        throw new Error(`Live feed failed (${res.status})`);
                    }
                    const data = await res.json();
                    if (gen !== run.gen) return;
                    const out = changedTabs(data.changed, run.seen, config.tableTabs);
                    run.seen = out.seen;
                    run.failures = 0;
                    run.retryAfterMs = 0;
                    if (out.tabs.length) {
                        run.activityAt = Date.now();
                        await this._liveApply(out.tabs);
                    }
                } catch (e) {
                    if (gen === run.gen) run.failures++;
                } finally {
                    if (gen === run.gen) {
                        run.busy = false;
                        this._liveSchedule(pollDelay(run.failures, Date.now() - run.activityAt, run.retryAfterMs));
                    }
                }
            },

            // Decide, per affected tab, between reload now / banner / stale mark.
            async _liveApply(tabs) {
                const run = this._liveRun;
                const active = config.activeTab(this);
                const jobs = [];
                for (const tab of tabs) {
                    const def = config.tabs[tab];
                    if (!def) continue;
                    if (tab === active) {
                        if (this._liveIsBusy(tab)) {
                            run.bannerTab = tab;
                            this._liveSetBanner(true);
                        } else {
                            jobs.push(this._liveReloadTab(tab));
                        }
                    } else if (def.background) {
                        jobs.push(this._liveReloadTab(tab));
                    } else {
                        run.stale.add(tab);
                    }
                }
                await Promise.all(jobs);
            },

            _liveIsBusy(tab) {
                const def = config.tabs[tab];
                const dialogOpen = typeof NSSDialog !== "undefined" && NSSDialog.isOpen && NSSDialog.isOpen();
                return dialogOpen || !!(def.busy && def.busy(this));
            },

            async _liveReloadTab(tab) {
                try {
                    await config.tabs[tab].reload(this);
                } catch (e) {
                    console.warn("[live-refresh] reload failed:", tab, e);
                }
            },

            // Banner click: reload the tab that had to wait, if it is still the
            // active one and no longer busy; otherwise leave the banner up.
            async liveRefreshNow() {
                const run = this._liveRun;
                if (!run) { this._liveSetBanner(false); return; }
                const tab = config.activeTab(this);
                if (this._liveIsBusy(tab)) return;
                this._liveSetBanner(false);
                run.bannerTab = null;
                run.stale.delete(tab);
                await this._liveReloadTab(tab);
            },

            // Host calls this from its activeTab watcher. The tab's own opener
            // already runs its loader (reloadOnOpen), so a stale mark is just
            // cleared; a tab that opts out is reloaded here. The banner belongs
            // to the tab that raised it.
            async liveTabOpened(tab) {
                const run = this._liveRun;
                if (!run) return;
                if (run.bannerTab && run.bannerTab !== tab) {
                    this._liveSetBanner(false);
                    run.bannerTab = null;
                }
                if (!run.stale.delete(tab)) return;
                const def = config.tabs[tab];
                if (def && def.reloadOnOpen === false) await this._liveReloadTab(tab);
            },
        };
    }

    window.NSSLiveRefresh = {
        LIVE_FEED,
        pollDelay,
        changedTabs,
        registerTarget,
        unregisterTarget,
        target,
        install(target, config) {
            const descriptors = Object.getOwnPropertyDescriptors(liveRefreshMixin(config));
            for (const key of Object.keys(descriptors)) {
                if (Object.prototype.hasOwnProperty.call(target, key)) continue;
                Object.defineProperty(target, key, descriptors[key]);
            }
            return target;
        },
    };
})();
