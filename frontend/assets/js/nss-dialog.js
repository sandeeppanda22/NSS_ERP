/**
 * NSS ERP — Custom Dialog Utility
 *
 * Replaces native browser alert()/confirm() with styled modals
 * matching the NSS palette (Navy/Teal/Saffron/Lotus).
 *
 * Uses inline styles — works on all pages regardless of whether
 * DaisyUI or other CSS frameworks are loaded.
 *
 * Usage:
 *   await NSSDialog.alert("Something went wrong.");
 *   const ok = await NSSDialog.confirm("Remove this member?");
 *   if (ok) { ... }
 *
 * Included via nss-config.js (appended to the NSS global).
 * Every page that loads nss-config.js gets this automatically.
 */

const NSSDialog = {
    _modalEl: null,
    _resolve: null,

    /**
     * Ensure the modal DOM element exists (created once, reused).
     */
    _ensureModal() {
        if (this._modalEl) return;

        const overlay = document.createElement("div");
        overlay.id = "nss-dialog-overlay";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        overlay.setAttribute("x-ignore", "");  // Prevent Alpine.js from processing this tree
        overlay.style.cssText = `
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.45);
            z-index: 9999;
            align-items: center;
            justify-content: center;
            padding: 1rem;
            isolation: isolate;
        `;

        overlay.innerHTML = `
            <div id="nss-dialog-card" style="
                background: #fff;
                border-radius: 0.75rem;
                box-shadow: 0 20px 60px rgba(0,0,0,0.2);
                width: 100%;
                max-width: 400px;
                overflow: hidden;
                font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            ">
                <div style="padding: 1.25rem 1.25rem 0;">
                    <h3 id="nss-dialog-title" style="
                        font-size: 1rem;
                        font-weight: 700;
                        color: #1B2A4A;
                        margin: 0 0 0.5rem;
                    "></h3>
                    <p id="nss-dialog-message" style="
                        font-size: 0.85rem;
                        color: #374151;
                        margin: 0;
                        white-space: pre-wrap;
                        line-height: 1.5;
                    "></p>
                </div>
                <div id="nss-dialog-actions" style="
                    padding: 1rem 1.25rem;
                    display: flex;
                    justify-content: flex-end;
                    gap: 0.5rem;
                    margin-top: 0.5rem;
                "></div>
            </div>
        `.trim();

        document.body.appendChild(overlay);
        this._modalEl = overlay;
    },

    /**
     * Create a styled button element.
     */
    /**
     * Variant color definitions — single source of truth.
     */
    _VARIANTS: {
        primary:  { bg: "#0D7377", hover: "#0a5f62", color: "#fff" },
        danger:   { bg: "#D64A6A", hover: "#be3d5c", color: "#fff" },
        warning:  { bg: "#D4920B", hover: "#b87c09", color: "#fff" },
        default:  { bg: "#fff",    hover: "#f3f4f6", color: "#374151", border: "#e5e7eb" },
    },

    _makeButton(text, variant = "default") {
        const v = this._VARIANTS[variant] || this._VARIANTS.default;
        const borderColor = v.border || v.bg;

        const btn = document.createElement("button");
        btn.textContent = text;
        btn.setAttribute("type", "button");
        // All styles in one cssText — most reliable against CSS resets
        btn.style.cssText = `
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.45rem 1rem;
            border-radius: 0.375rem;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
            font-family: inherit;
            background-color: ${v.bg};
            color: ${v.color};
            border: 1px solid ${borderColor};
        `;

        btn.addEventListener("mouseenter", () => {
            btn.style.backgroundColor = v.hover;
        });
        btn.addEventListener("mouseleave", () => {
            btn.style.backgroundColor = v.bg;
        });

        return btn;
    },

    _show() {
        this._modalEl.style.display = "flex";
    },

    _hide() {
        this._modalEl.style.display = "none";
    },

    /** True while an alert/confirm/prompt is on screen (live refresh never reloads under one). */
    isOpen() {
        return !!this._modalEl && this._modalEl.style.display === "flex";
    },

    /**
     * Show an alert dialog (single OK button).
     * Replaces native alert().
     *
     * @param {string} message - The message to display
     * @param {string} [title=""] - Optional title
     * @returns {Promise<void>}
     */
    alert(message, title = "") {
        return new Promise((resolve) => {
            this._ensureModal();
            this._resolve = resolve;

            const titleEl = document.getElementById("nss-dialog-title");
            const msgEl = document.getElementById("nss-dialog-message");
            const actionsEl = document.getElementById("nss-dialog-actions");

            titleEl.textContent = title;
            titleEl.style.display = title ? "" : "none";
            msgEl.textContent = message;

            actionsEl.innerHTML = "";
            const okBtn = this._makeButton("OK", "primary");

            const cleanup = () => {
                this._hide();
                this._resolve = null;
                resolve();
            };

            okBtn.addEventListener("click", cleanup);

            // Close on overlay click
            const onOverlay = (e) => {
                if (e.target === this._modalEl) {
                    this._modalEl.removeEventListener("click", onOverlay);
                    cleanup();
                }
            };
            this._modalEl.addEventListener("click", onOverlay);

            actionsEl.appendChild(okBtn);
            this._show();
        });
    },

    /**
     * Show a confirm dialog (Cancel + Confirm buttons).
     * Replaces native confirm().
     *
     * @param {string} message - The message to display
     * @param {Object} [opts] - Options
     * @param {string} [opts.title=""] - Optional title
     * @param {string} [opts.confirmText="Confirm"] - Confirm button label
     * @param {string} [opts.cancelText="Cancel"] - Cancel button label
     * @param {string} [opts.confirmClass="primary"] - "primary" or "danger"
     * @returns {Promise<boolean>} true if confirmed, false if cancelled
     */
    confirm(message, opts = {}) {
        const {
            title = "",
            confirmText = "Confirm",
            cancelText = "Cancel",
            confirmClass = "primary",
        } = opts;

        // Map DaisyUI class names to our variant names for backwards compat
        let variant = confirmClass;
        if (confirmClass === "btn-primary") variant = "primary";
        else if (confirmClass === "btn-error") variant = "danger";
        else if (confirmClass === "btn-warning") variant = "warning";

        return new Promise((resolve) => {
            this._ensureModal();
            this._resolve = resolve;

            const titleEl = document.getElementById("nss-dialog-title");
            const msgEl = document.getElementById("nss-dialog-message");
            const actionsEl = document.getElementById("nss-dialog-actions");

            titleEl.textContent = title;
            titleEl.style.display = title ? "" : "none";
            msgEl.textContent = message;

            actionsEl.innerHTML = "";

            const cancelBtn = this._makeButton(cancelText, "default");
            const confirmBtn = this._makeButton(confirmText, variant);

            const cleanup = (result) => {
                this._hide();
                this._resolve = null;
                resolve(result);
            };

            cancelBtn.addEventListener("click", () => cleanup(false));
            confirmBtn.addEventListener("click", () => cleanup(true));

            // Close on overlay click → cancel
            const onOverlay = (e) => {
                if (e.target === this._modalEl) {
                    this._modalEl.removeEventListener("click", onOverlay);
                    cleanup(false);
                }
            };
            this._modalEl.addEventListener("click", onOverlay);

            actionsEl.appendChild(cancelBtn);
            actionsEl.appendChild(confirmBtn);
            this._show();
        });
    },
};
