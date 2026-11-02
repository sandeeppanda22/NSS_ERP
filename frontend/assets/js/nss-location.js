/**
 * NSS ERP — Shared Location Cascade Utility
 *
 * Reusable helper for the country → state → district → postal code
 * cascading dropdown pattern. Used by register.js, admin.js (org edit
 * and org create) to eliminate three near-identical implementations.
 *
 * 2026-10-30 changes (backward compatible for admin.js, which has no PIN list):
 *   - loadPostalCodes(ctx, districtPk) now takes a DISTRICT pk (was state pk)
 *     and is a no-op when `arrays.postalCodes` is not configured.
 *   - onStateChange clears district/city/PIN and loads districts only (PINs
 *     load when a district is chosen); onDistrictChange clears city AND
 *     PIN/post office (postal_code_value, postal_code_pk, post_office_pk,
 *     post_office_name, city_village_pk — each only if present on the form)
 *     and loads cities + PINs for the district; onCountryChange clears all.
 *   - Every load* has a stale-response guard (late responses for a superseded
 *     parent are discarded). No new config keys.
 *
 * Usage:
 *   // In Alpine.js init():
 *   this._loc = NSSLocation.create({
 *       fetchFn: fetch,                   // or NSSAuth.apiFetch
 *       basePath: '/api/v1/foundation',   // optional — see below
 *       arrays: {                         // where to store fetched lists
 *           countries: 'regCountries',
 *           states:    'regStates',
 *           districts: 'regDistricts',
 *           cities:    'regCities',       // optional — omit to skip the
 *                                         // city/village dropdown entirely
 *           postalCodes: 'regPostalCodes',
 *       },
 *       form: 'form',                     // property name of the form object on `this`
 *   });
 *
 *   // Call from Alpine methods:
 *   this._loc.loadCountries(this);
 *   this._loc.onCountryChange(this);
 *
 * All methods take `ctx` (the Alpine component `this`) as the first
 * argument so the utility stays stateless and framework-agnostic.
 *
 * Design:
 *   - No global state; each instance is a config object
 *   - Works with both plain fetch() and NSSAuth.apiFetch()
 *   - Form field names are fixed: country_pk, state_pk, district_pk,
 *     city_village_name, postal_code_pk (matches DB column names)
 *   - basePath defaults to '/api/v1/foundation' (the authenticated
 *     Foundation endpoints admin.js uses). register.js instead passes
 *     '/api/v1/register', a set of unauthenticated endpoints that call the
 *     exact same shared query functions as Foundation's — see
 *     api/routers/registration.py — since the person filling out that page
 *     has no JWT yet.
 */

const NSSLocation = {
    /**
     * Create a location cascade instance.
     * @param {Object} opts
     * @param {Function} opts.fetchFn - fetch or NSSAuth.apiFetch
     * @param {string} [opts.basePath] - API prefix, default '/api/v1/foundation'
     * @param {Object} opts.arrays - map of { countries, states, districts, cities, postalCodes } → Alpine property names (cities optional)
     * @param {string} opts.form - name of the form object property on the Alpine component
     * @returns {Object} cascade methods
     */
    create(opts) {
        const { fetchFn, arrays, form } = opts;
        const basePath = opts.basePath || "/api/v1/foundation";

        // Stale-response guard: every load* bumps a per-kind sequence number
        // (and so does anything upstream that empties that list). A response
        // is applied only if its number is still current, i.e. no newer load
        // or parent change happened while it was in flight. Equivalent to
        // "capture the parent value, discard if it changed" but also safe for
        // prefill paths that call load*(pk) before the form field is set.
        const seq = { countries: 0, states: 0, districts: 0, cities: 0, postalCodes: 0 };
        const bump = (...kinds) => kinds.forEach((k) => { seq[k]++; });
        const loadInto = async (ctx, kind, arrayName, url) => {
            const mine = ++seq[kind];
            try {
                const res = await fetchFn(url);
                if (res.ok) {
                    const data = await res.json();
                    if (mine === seq[kind]) ctx[arrayName] = data;
                }
            } catch (_) {}
        };

        return {
            async loadCountries(ctx) {
                await loadInto(ctx, "countries", arrays.countries, `${basePath}/countries`);
            },

            async loadStates(ctx, countryPk) {
                bump("states", "districts", "cities", "postalCodes");
                ctx[arrays.states] = [];
                ctx[arrays.districts] = [];
                if (arrays.postalCodes) ctx[arrays.postalCodes] = [];
                if (!countryPk) return;
                await loadInto(ctx, "states", arrays.states, `${basePath}/states?country_pk=${countryPk}`);
            },

            async loadDistricts(ctx, statePk) {
                bump("districts", "cities", "postalCodes");
                ctx[arrays.districts] = [];
                if (!statePk) return;
                await loadInto(ctx, "districts", arrays.districts, `${basePath}/districts?state_pk=${statePk}`);
            },

            async loadCities(ctx, districtPk) {
                if (!arrays.cities) return; // consumer opted out of city/village dropdown
                bump("cities");
                ctx[arrays.cities] = [];
                if (!districtPk) return;
                await loadInto(ctx, "cities", arrays.cities, `${basePath}/cities?district_pk=${districtPk}`);
            },

            // PINs are narrowed by DISTRICT (owner decision 2026-10-30), not
            // state. postal_code has no district column, so the backend
            // answers through approved nss.city_village rows: a district with
            // a sparse city_village seed lists few PINs, hence consumers must
            // keep a way to enter a new PIN (register: free-text + datalist;
            // address editor: propose). With no district the list is empty.
            async loadPostalCodes(ctx, districtPk) {
                if (!arrays.postalCodes) return; // consumer has no PIN list
                bump("postalCodes");
                ctx[arrays.postalCodes] = [];
                if (!districtPk) return;
                await loadInto(ctx, "postalCodes", arrays.postalCodes, `${basePath}/postal-codes?district_pk=${districtPk}`);
            },

            _emptyLists(ctx, ...names) {
                names.forEach((n) => { if (arrays[n]) ctx[arrays[n]] = []; });
            },

            onCountryChange(ctx) {
                const f = ctx[form];
                f.state_pk = "";
                f.district_pk = "";
                f.city_village_name = "";
                this._clearPostalCode(f);
                bump("states", "districts", "cities", "postalCodes");
                this._emptyLists(ctx, "states", "districts", "cities", "postalCodes");
                if (f.country_pk) this.loadStates(ctx, f.country_pk);
            },

            onStateChange(ctx) {
                const f = ctx[form];
                f.district_pk = "";
                f.city_village_name = "";
                this._clearPostalCode(f);
                bump("districts", "cities", "postalCodes");
                this._emptyLists(ctx, "districts", "cities", "postalCodes");
                if (f.state_pk) this.loadDistricts(ctx, f.state_pk);
            },

            // Cleared whenever country/state/district changes: a PIN typed
            // or picked for one district must not survive a switch. Both key
            // names are handled because consumers differ: register.js and
            // admin.js hold free text in `postal_code_value`; the dashboard
            // address editor holds `postal_code_pk` (+ `post_office_pk`,
            // which belongs to the PIN and is cleared with it).
            _clearPostalCode(f) {
                if ("postal_code_value" in f) f.postal_code_value = "";
                if ("postal_code_pk" in f) f.postal_code_pk = "";
                if ("post_office_pk" in f) f.post_office_pk = "";
                if ("post_office_name" in f) f.post_office_name = "";
            },

            onDistrictChange(ctx) {
                const f = ctx[form];
                f.city_village_name = "";
                if ("city_village_pk" in f) f.city_village_pk = "";
                this._clearPostalCode(f);
                bump("cities", "postalCodes");
                this._emptyLists(ctx, "cities", "postalCodes");
                if (f.district_pk) {
                    this.loadCities(ctx, f.district_pk);
                    this.loadPostalCodes(ctx, f.district_pk);
                }
            },
        };
    },
};
