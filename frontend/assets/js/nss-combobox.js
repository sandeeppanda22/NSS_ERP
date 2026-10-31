/**
 * NSS ERP — Shared Searchable Combobox (select-existing OR propose-new)
 *
 * Generic Alpine.js component for the writable geographic address fields
 * introduced by Member-Assisted Geographic Entry (SOL-ARCH-010 Amendment).
 * A member picks an existing value from a filtered list, OR types a value
 * the system has not seen yet and proposes it — the proposal is created as
 * a PENDING row via a "propose" endpoint and immediately selected, so the
 * surrounding form always ends up holding a real PK.
 *
 * Modeled on nss-datepicker.js: a factory bound to a model path, with the
 * repetitive popup markup injected once from a single source of truth on
 * DOMContentLoaded (before Alpine starts).
 *
 * Usage (all paths resolve up the Alpine scope chain, like the datepicker):
 *
 *   <div x-data="nssCombobox('form.district_pk', {
 *            optionsPath:  'regDistricts',
 *            valueKey:     'district_pk',
 *            labelKey:     'district_name',
 *            proposeUrl:   '/api/v1/foundation/districts/propose',
 *            proposeField: 'district_name',
 *            proposeParams: { state_pk: 'form.state_pk' },
 *            placeholder:  'Select or type a district'
 *        })">
 *       <label class="form-label">District</label>
 *   </div>
 *
 * The selected PK is written into the model path. `optionsPath` names an
 * array on a parent scope (the same array nss-location.js populates); each
 * element must carry `valueKey` and `labelKey`. On propose, the request
 * body is { ...proposeParams resolved from scope, [proposeField]: typed }
 * and the new row (returned by the endpoint) is appended to the options
 * array and selected. Propose uses NSSAuth.apiFetch when present (the
 * endpoints are authenticated), falling back to plain fetch.
 */

function nssCombobox(modelPath, opts) {
    opts = opts || {};
    return {
        _modelPath: modelPath,
        _opts: {
            optionsPath: opts.optionsPath || null,
            valueKey: opts.valueKey || "pk",
            labelKey: opts.labelKey || "name",
            // Propose-new is on by default; set allowNew:false for a
            // pick-only combobox (no "Add …" row).
            allowNew: opts.allowNew !== false,
            proposeUrl: opts.proposeUrl || null,
            // The body field that carries the member's typed text.
            proposeField: opts.proposeField || "name",
            // Map of body-field → scope path, resolved at propose time so
            // dependent values (e.g. the chosen state_pk) are always current.
            proposeParams: opts.proposeParams || {},
            // Where to read the new PK / label out of the propose response.
            responseValueKey: opts.responseValueKey || opts.valueKey || "pk",
            responseLabelKey: opts.responseLabelKey || opts.labelKey || "name",
            placeholder: opts.placeholder || "Select or type…",
            minChars: typeof opts.minChars === "number" ? opts.minChars : 0,
        },

        open: false,
        query: "",            // live text in the input
        highlight: -1,        // keyboard-highlighted option index
        busy: false,          // a propose request is in flight
        error: "",
        _committedLabel: "",  // label of the current selection, for revert

        // ── Path resolution (walks the Alpine scope chain via `this`) ──

        _resolve(path) {
            var parts = path.split(".");
            var obj = this;
            for (var i = 0; i < parts.length - 1; i++) {
                obj = obj[parts[i]];
                if (obj == null) return { obj: null, key: null };
            }
            return { obj: obj, key: parts[parts.length - 1] };
        },

        _readModel() {
            var m = this._resolve(this._modelPath);
            return m.obj && m.key ? (m.obj[m.key] || "") : "";
        },

        _writeModel(value) {
            var m = this._resolve(this._modelPath);
            if (m.obj && m.key) m.obj[m.key] = value;
        },

        _options() {
            if (!this._opts.optionsPath) return [];
            var m = this._resolve(this._opts.optionsPath);
            var arr = m.obj && m.key ? m.obj[m.key] : null;
            return Array.isArray(arr) ? arr : [];
        },

        _labelOf(opt) {
            return opt ? String(opt[this._opts.labelKey] || "") : "";
        },
        _valueOf(opt) {
            return opt ? opt[this._opts.valueKey] : "";
        },

        // ── Lifecycle ────────────────────────────────────

        init() {
            this.syncFromModel();
            // Options usually load asynchronously (the location cascade
            // fetches districts/PINs after a parent select changes). Re-sync
            // the display label whenever the backing array or the bound PK
            // changes, so a programmatic selection shows its name once the
            // options arrive.
            if (this._opts.optionsPath) {
                this.$watch(this._opts.optionsPath, () => this.syncFromModel());
            }
            this.$watch(this._modelPath, () => this.syncFromModel());
        },

        // Set the input text to the label of the currently-bound PK.
        syncFromModel() {
            var val = this._readModel();
            if (!val) {
                this._committedLabel = "";
                if (!this.open) this.query = "";
                return;
            }
            var opts = this._options();
            for (var i = 0; i < opts.length; i++) {
                if (String(this._valueOf(opts[i])) === String(val)) {
                    this._committedLabel = this._labelOf(opts[i]);
                    if (!this.open) this.query = this._committedLabel;
                    return;
                }
            }
            // PK set but not (yet) in the options array — keep whatever
            // label we already committed rather than blanking the field.
        },

        // ── Filtering ────────────────────────────────────

        filtered() {
            var q = this.query.trim().toLowerCase();
            var opts = this._options();
            if (!q) return opts;
            var out = [];
            for (var i = 0; i < opts.length; i++) {
                if (this._labelOf(opts[i]).toLowerCase().indexOf(q) !== -1) {
                    out.push(opts[i]);
                }
            }
            return out;
        },

        // Show the "Add new" row only when propose is enabled, the typed
        // text is non-empty, and nothing in the list matches it exactly.
        showAddNew() {
            if (!this._opts.allowNew || !this._opts.proposeUrl) return false;
            var q = this.query.trim();
            if (q.length < Math.max(1, this._opts.minChars)) return false;
            var opts = this._options();
            for (var i = 0; i < opts.length; i++) {
                if (this._labelOf(opts[i]).toLowerCase() === q.toLowerCase()) return false;
            }
            return true;
        },

        // ── Interaction ──────────────────────────────────

        onInput() {
            this.open = true;
            this.highlight = -1;
            this.error = "";
        },

        onFocus() {
            this.open = true;
        },

        close() {
            this.open = false;
            this.highlight = -1;
            // Revert partial text to the committed selection so a half-typed
            // query never masquerades as a value.
            this.query = this._committedLabel;
        },

        select(opt) {
            this._writeModel(this._valueOf(opt));
            this._committedLabel = this._labelOf(opt);
            this.query = this._committedLabel;
            this.error = "";
            this.open = false;
            this.highlight = -1;
        },

        clearSelection() {
            this._writeModel("");
            this._committedLabel = "";
            this.query = "";
            this.error = "";
            this.open = false;
        },

        onKeydown(event) {
            if (!this.open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
                this.open = true;
                return;
            }
            var list = this.filtered();
            var addRow = this.showAddNew() ? 1 : 0;
            var total = list.length + addRow;
            if (event.key === "ArrowDown") {
                event.preventDefault();
                this.highlight = total ? (this.highlight + 1) % total : -1;
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                this.highlight = total ? (this.highlight - 1 + total) % total : -1;
            } else if (event.key === "Enter") {
                event.preventDefault();
                if (this.highlight >= 0 && this.highlight < list.length) {
                    this.select(list[this.highlight]);
                } else if (addRow && (this.highlight === list.length || this.highlight === -1)) {
                    this.addNew();
                }
            } else if (event.key === "Escape") {
                this.close();
            }
        },

        // ── Propose a brand-new value ────────────────────

        async addNew() {
            if (this.busy || !this._opts.proposeUrl) return;
            var text = this.query.trim();
            if (!text) return;

            var body = {};
            var params = this._opts.proposeParams || {};
            for (var key in params) {
                if (!Object.prototype.hasOwnProperty.call(params, key)) continue;
                var m = this._resolve(params[key]);
                var pv = m.obj && m.key ? m.obj[m.key] : null;
                // An unset scope value ("") must reach the API as null,
                // not an empty string that fails UUID validation.
                body[key] = pv === "" ? null : pv;
            }
            body[this._opts.proposeField] = text;

            var fetchFn = (window.NSSAuth && NSSAuth.apiFetch)
                ? NSSAuth.apiFetch.bind(NSSAuth)
                : window.fetch.bind(window);

            this.busy = true;
            this.error = "";
            try {
                var res = await fetchFn(this._opts.proposeUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
                var data = null;
                try { data = await res.json(); } catch (_) {}
                if (!res.ok) {
                    this.error = (data && (data.detail || data.message)) ||
                        "Could not submit this value for review. Please try again.";
                    return;
                }
                // Build an option in the same shape the list uses, append it
                // so it stays selectable, and select it. The row is PENDING
                // server-side but is a valid FK target immediately.
                var newOpt = {};
                newOpt[this._opts.valueKey] = data[this._opts.responseValueKey];
                newOpt[this._opts.labelKey] = data[this._opts.responseLabelKey] || text;
                // Carry through any extra response fields (useful for lists
                // that render more than just the label).
                for (var f in data) {
                    if (Object.prototype.hasOwnProperty.call(data, f) && !(f in newOpt)) {
                        newOpt[f] = data[f];
                    }
                }
                var arrRef = this._resolve(this._opts.optionsPath);
                if (arrRef.obj && arrRef.key && Array.isArray(arrRef.obj[arrRef.key])) {
                    arrRef.obj[arrRef.key].push(newOpt);
                }
                this.select(newOpt);
            } catch (e) {
                this.error = "Network error while submitting this value. Please try again.";
            } finally {
                this.busy = false;
            }
        },
    };
}


/* ═══════════════════════════════════════════════════════════
 * SHARED COMBOBOX MARKUP — single source of truth
 *
 * Mirrors nss-datepicker.js: each callsite declares intent only
 *   <div x-data="nssCombobox('form.district_pk', { … })">
 *       <label class="form-label">District</label>
 *   </div>
 * and the input + dropdown markup is injected here once, on
 * DOMContentLoaded (which runs before Alpine starts — this file is
 * a blocking head script, Alpine is loaded `defer`). Alpine then
 * compiles the injected directives normally.
 *
 * Optional per-callsite overrides (data attributes on the root):
 *   data-cb-input-class : input CSS class   (default nss-cb-input)
 *   data-cb-disabled    : Alpine expr for :disabled (e.g. "loading")
 * ═══════════════════════════════════════════════════════════ */

var NSS_CB_CARET_SVG = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" style="width:0.9rem;height:0.9rem;"><path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" /></svg>';

var NSS_CB_PLUS_SVG = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" style="width:0.85rem;height:0.85rem;"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>';

/**
 * Build the canonical input + dropdown markup.
 * @param {Object} cfg - { inputClass, disabledExpr }
 * @returns {string} HTML to append inside the nssCombobox root.
 */
function nssComboboxMarkup(cfg) {
    cfg = cfg || {};
    var inputClass = cfg.inputClass || "nss-cb-input";
    var disabled = cfg.disabledExpr ? ' :disabled="' + cfg.disabledExpr + '"' : "";

    return '' +
        '<div class="nss-cb-wrap">' +
            '<input type="text" class="' + inputClass + '" x-model="query"' +
                   ' @focus="onFocus()" @input="onInput()" @keydown="onKeydown($event)"' +
                   ' :placeholder="_opts.placeholder" autocomplete="off"' +
                   ' role="combobox" :aria-expanded="open"' + disabled + '>' +
            '<button type="button" class="nss-cb-caret" @click="open ? close() : (open = true)" tabindex="-1">' +
                NSS_CB_CARET_SVG +
            '</button>' +
        '</div>' +
        '<div x-show="open" x-cloak class="nss-cb-popup" @click.outside="close()" x-transition>' +
            '<ul class="nss-cb-list" role="listbox">' +
                '<template x-for="(opt, idx) in filtered()" :key="_valueOf(opt)">' +
                    '<li class="nss-cb-option" role="option"' +
                        ' :class="{ \'nss-cb-active\': idx === highlight,' +
                                  ' \'nss-cb-selected\': String(_valueOf(opt)) === String(_readModel()) }"' +
                        ' @click="select(opt)" @mouseenter="highlight = idx"' +
                        ' x-text="_labelOf(opt)"></li>' +
                '</template>' +
                '<li class="nss-cb-empty" x-show="filtered().length === 0 && !showAddNew()">' +
                    'No matches' +
                '</li>' +
                '<li class="nss-cb-add" x-show="showAddNew()"' +
                    ' :class="{ \'nss-cb-active\': highlight === filtered().length }"' +
                    ' @click="addNew()" @mouseenter="highlight = filtered().length">' +
                    '<span class="nss-cb-add-icon" x-show="!busy">' + NSS_CB_PLUS_SVG + '</span>' +
                    '<span class="nss-cb-spin" x-show="busy" x-cloak></span>' +
                    '<span>Add &ldquo;<span x-text="query.trim()"></span>&rdquo; for review</span>' +
                '</li>' +
            '</ul>' +
            '<div class="nss-cb-footer" x-show="_readModel()" x-cloak>' +
                '<button type="button" class="nss-cb-clear" @click="clearSelection()">Clear selection</button>' +
            '</div>' +
        '</div>' +
        '<div class="nss-cb-error" x-show="error" x-cloak x-text="error"></div>';
}

/**
 * Expand every nssCombobox root in `scope` with the shared markup.
 * Idempotent — a root already carrying data-nss-cb-built is skipped, so
 * it is safe to re-run after injecting dynamic HTML.
 *
 * Stamps data-nss-cb="<modelPath>" on the root as a stable test/code hook
 * that does not depend on the exact x-data argument spelling.
 */
function nssComboboxExpand(scope) {
    scope = scope || document;

    var nodes = scope.querySelectorAll('[x-data^="nssCombobox("]');
    for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        if (node.hasAttribute("data-nss-cb-built")) continue;

        var match = /nssCombobox\(\s*['"]([^'"]+)['"]/.exec(
            node.getAttribute("x-data") || ""
        );
        if (match) node.setAttribute("data-nss-cb", match[1]);

        if (!node.style.position) node.style.position = "relative";

        node.insertAdjacentHTML("beforeend", nssComboboxMarkup({
            inputClass: node.getAttribute("data-cb-input-class"),
            disabledExpr: node.getAttribute("data-cb-disabled"),
        }));

        node.setAttribute("data-nss-cb-built", "");
    }

    // Comboboxes nested inside Alpine <template> blocks are not reached by
    // querySelectorAll (it does not descend into template content), so
    // recurse explicitly — mirrors nss-datepicker.js.
    var tpls = scope.querySelectorAll("template");
    for (var t = 0; t < tpls.length; t++) {
        if (tpls[t].content) nssComboboxExpand(tpls[t].content);
    }
}

// Runs before Alpine.start() — see the block comment above.
document.addEventListener("DOMContentLoaded", function () {
    nssComboboxExpand(document);
});
