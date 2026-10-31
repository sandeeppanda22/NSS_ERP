/**
 * NSS ERP — shared password show/hide toggle.
 *
 * Alpine directive `x-pw-reveal` on an <input type="password"> wraps it and
 * adds an eye button that flips the input between password and text:
 *
 *   <input type="password" x-pw-reveal x-model="form.password">
 *
 * The wrap is deferred to a microtask: Alpine is mid-way through walking the
 * input's siblings when the directive runs, and moving the node synchronously
 * would make it skip them. Styles: nss-layout.css (.pw-reveal-*).
 */
(function () {
    const EYE = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>';
    const EYE_SLASH = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12c1.292 4.338 5.31 7.5 10.066 7.5.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" /></svg>';

    document.addEventListener("alpine:init", () => {
        Alpine.directive("pw-reveal", (el) => {
            queueMicrotask(() => {
                if (!el.parentNode || el.parentNode.classList.contains("pw-reveal-wrap")) return;
                const wrap = document.createElement("div");
                wrap.className = "pw-reveal-wrap";
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "pw-reveal-btn";
                btn.tabIndex = -1;
                btn.setAttribute("aria-label", "Show password");
                btn.innerHTML = EYE;
                btn.addEventListener("click", () => {
                    const show = el.type === "password";
                    el.type = show ? "text" : "password";
                    btn.innerHTML = show ? EYE_SLASH : EYE;
                    btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
                });
                el.parentNode.insertBefore(wrap, el);
                wrap.appendChild(el);
                wrap.appendChild(btn);
            });
        });
    });
})();
