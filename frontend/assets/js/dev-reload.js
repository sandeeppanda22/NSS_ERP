/*
 * NSS ERP — dev-only browser auto-reload client.
 *
 * NOT part of the application. This file is never referenced from any HTML
 * source; api/main.py::_render_html_with_asset_versions() injects a
 * <script src="/assets/js/dev-reload.js"> tag before </body> only when the
 * DEV_LIVE_RELOAD setting is truthy, and the endpoint it polls
 * (GET /__dev/frontend-version) is only registered under the same flag. With
 * the flag at its default (off) neither the tag nor the route exists, so this
 * file is dead weight in a deployment rather than a live surface.
 *
 * Why polling and not SSE / WebSocket: the owner runs uvicorn with --reload,
 * which kills the whole process on every Python edit, so any long-lived
 * connection would need its own reconnect/backoff logic plus either a
 * background thread or a filesystem-watcher dependency. A 1s poll needs
 * none of that, survives server restarts for free (a failed poll is simply
 * ignored), and one request/second against localhost costs nothing. It also
 * works under the existing CSP untouched: an external same-origin script
 * (script-src 'self') doing a same-origin fetch (connect-src 'self') is
 * already allowed, whereas an inline <script> would be blocked because
 * script-src deliberately has no 'unsafe-inline'.
 *
 * Behaviour: remember the first successful fingerprint, then reload the page
 * the first time a *successful* response reports a different one. Never
 * reload on a failed or non-OK response (the server is mid-restart, and
 * reloading then would storm a down server). Stop entirely on 404.
 */
(function () {
    'use strict';

    var ENDPOINT = '/__dev/frontend-version';
    var INTERVAL_MS = 1000;

    var lastVersion = null;
    var timer = null;

    function stop() {
        if (timer !== null) {
            clearInterval(timer);
            timer = null;
        }
    }

    function poll() {
        var request;
        try {
            request = fetch(ENDPOINT, { cache: 'no-store' });
        } catch (err) {
            return; // fetch unavailable / threw synchronously — stay quiet
        }

        request.then(function (response) {
            if (response.status === 404) {
                // Flag is off server-side but this script is still in the
                // page (stale cached HTML). Nothing to watch — give up.
                stop();
                return null;
            }
            if (!response.ok) {
                return null; // server restarting; keep the old baseline
            }
            return response.json();
        }).then(function (data) {
            if (!data || typeof data.v !== 'string') {
                return;
            }
            if (lastVersion === null) {
                lastVersion = data.v;
                return;
            }
            if (data.v !== lastVersion) {
                lastVersion = data.v;
                stop();
                window.location.reload();
            }
        }).catch(function () {
            // Network error (server down between --reload restarts), bad
            // JSON, anything else: swallow it and keep polling.
        });
    }

    try {
        console.info('[dev-reload] active — polling ' + ENDPOINT + ' every ' + INTERVAL_MS + 'ms');
        poll(); // establish the baseline immediately
        timer = setInterval(poll, INTERVAL_MS);

        // Safari (far more than Chrome) throttles setInterval heavily while
        // the tab/window is not frontmost — editing in another app/window
        // can stall the 1s poll almost entirely, so switching back to
        // Safari doesn't show the reload until the throttled timer happens
        // to fire again. Force an immediate poll on every return-to-tab
        // signal so the check never waits on a throttled interval.
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'visible' && timer !== null) poll();
        });
        window.addEventListener('focus', function () {
            if (timer !== null) poll();
        });
    } catch (err) {
        stop();
    }
})();
