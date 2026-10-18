/**
 * NSS ERP — Registration Page (Tier 5)
 *
 * Alpine.js component for multi-step registration form.
 * Steps:
 *   1. Personal details (name, DOB, gender, contact)
 *   2. Membership claim details (optional toggle)
 *      - Select Sakha first, then Local Sakha Number appears
 *      - Darshaka: Local Sakha Number optional
 *      - Non-Darshaka: Local Sakha Number required
 *      - Optional: attending another Sangha as Darshak
 *   3. Password creation
 *   4. Success screen (Person ID only — pending admin approval)
 *
 * Calls POST /api/v1/register (public — no auth required).
 * Loads dropdown data from Foundation master_data API.
 *
 * Authority: SOL-AUTH-006 (Registration Claim Business Rules)
 */

function registerApp() {
    return {
        step: 1,
        loading: false,
        error: "",
        showPassword: false,
        confirmPassword: "",

        // "Previously registered? Add membership" flow — mode stays 'new'
        // for the ordinary wizard; switches to 'existing' once lookupExisting()
        // verifies a Person ID + DOB that has no account/claim/SS yet.
        // Submits to POST /register/claim instead of POST /register.
        mode: "new",

        // Standalone "Apply for Darshak" entry (step === 'darshak-entry') —
        // a dedicated, visitor-facing shortcut into the SAME wizard/claim
        // plumbing above. It only decides which branch to start (existing
        // Person ID via lookupExisting(), or a fresh person via the normal
        // step-1 wizard) and pre-locks the membership type to Darshaka
        // (PROBATIONARY) once personal/identity details are settled — no
        // new backend endpoint, no duplicate submit logic.
        darshakFlow: false,
        lookup: {
            person_id: "",
            date_of_birth: "",
            loading: false,
        },
        existingPerson: {
            person_pk: "",
            person_id: "",
            person_name: "",
        },

        // Dropdown data
        genders: [],
        maritalStatuses: [],
        bloodGroups: [],
        membershipTypes: [],
        sakhas: [],

        // Address lookup data
        regCountries: [],
        regStates: [],
        regDistricts: [],
        regCities: [],
        regPostalCodes: [],
        regPostOffices: [],
        regPostOfficesLoading: false,
        // The postal_code_pk resolved client-side from regPostalCodes once
        // the typed postal_code_value exactly matches a known PIN — scopes
        // the Post Office field, which has no meaning without a real PIN.
        regMatchedPostalCodePk: "",

        // Form data
        form: {
            first_name: "",
            middle_name: "",
            last_name: "",
            date_of_birth: "",
            gender_master_data_pk: "",
            marital_status_master_data_pk: "",
            blood_group_master_data_pk: "",
            country_phone_code: NSS.DEFAULT_COUNTRY_CODE,
            mobile_number: "",
            email: "",
            // Address
            country_pk: "",
            state_pk: "",
            district_pk: "",
            city_village_name: "",
            postal_code_value: "",
            post_office_name: "",
            address_line_1: "",
            address_line_2: "",
            landmark: "",
            // Membership
            has_membership: false,
            membership_type_master_data_pk: "",
            organization_pk: "",
            joining_date: "",
            claimed_local_sakha_number: "",
            claimed_credential_document_number: "",
            is_attending_as_darshak: false,
            darshak_organization_pk: "",
            darshak_local_sakha_number: "",
            password: "",
        },

        // Registration result
        result: {
            person_pk: "",
            person_id: "",
            person_name: "",
            message: "",
        },

        async init() {
            // Redirect if already logged in
            NSSAuth.redirectIfLoggedIn("/dashboard");

            await this.loadReferenceData();
            await this.restoreDraft();

            // Persist step + form (never the password) on every change, so
            // an accidental refresh resumes where the registrant left off
            // instead of silently dropping back to step 1 with a blank
            // form. Mirrors the sessionStorage pattern dashboard.js already
            // uses for its active-tab restore.
            this.$watch("form", () => this.saveDraft());
            this.$watch("step", () => this.saveDraft());
        },

        // Load a previously-saved draft (if any) and re-populate the
        // address cascade's dependent dropdowns to match it. Uses the
        // cascade's plain loadStates/loadDistricts/loadCities/loadPostalCodes
        // — NOT onCountryChange/onStateChange/onDistrictChange, which clear
        // child form fields on the assumption a human just changed the
        // parent dropdown; that would erase the very values being restored.
        async restoreDraft() {
            let draft;
            try {
                const raw = sessionStorage.getItem("nss_register_draft");
                if (!raw) return;
                draft = JSON.parse(raw);
            } catch (_) {
                return;
            }
            if (!draft || typeof draft !== "object" || !draft.form) return;

            const savedPostOffice = draft.form.post_office_name || "";
            Object.assign(this.form, draft.form, { password: "" });
            this.confirmPassword = "";
            if ([1, 2, 3].includes(draft.step)) this.step = draft.step;

            if (this.form.country_pk) {
                await this._locCascade.loadStates(this, this.form.country_pk);
            }
            if (this.form.state_pk) {
                await Promise.all([
                    this._locCascade.loadDistricts(this, this.form.state_pk),
                    this._locCascade.loadPostalCodes(this, this.form.state_pk),
                ]);
            }
            if (this.form.district_pk) {
                await this._locCascade.loadCities(this, this.form.district_pk);
            }

            // Re-resolve the matched PIN against the just-reloaded list and
            // restore Post Office suggestions — mirrors onRegPostalCodeChange()
            // but without its form.post_office_name = "" reset.
            const code = (this.form.postal_code_value || "").trim();
            const match = code
                ? this.regPostalCodes.find(pc => (pc.postal_code || "").trim() === code)
                : null;
            this.regMatchedPostalCodePk = match ? match.postal_code_pk : "";
            this.form.post_office_name = savedPostOffice;
            await this.loadRegPostOffices();
        },

        // Draft is cleared on successful registration (register()) so a
        // later visit to this page starts fresh rather than resuming a
        // completed signup.
        saveDraft() {
            if (this.step >= 4) return;
            if (this.mode === "existing") return; // don't clobber a 'new' draft with existing-mode state
            try {
                const { password, ...formNoPassword } = this.form;
                sessionStorage.setItem("nss_register_draft", JSON.stringify({
                    step: this.step,
                    form: formNoPassword,
                }));
            } catch (_) {
                // Storage unavailable (private browsing, quota) — the
                // registrant can still complete the form in one sitting.
            }
        },

        // Every dropdown this page needs, in one round trip — public,
        // no auth (this visitor has no JWT yet). See
        // GET /api/v1/register/reference-data (api/routers/registration.py).
        async loadReferenceData() {
            try {
                const res = await fetch("/api/v1/register/reference-data");
                if (res.ok) {
                    const data = await res.json();
                    this.genders = data.genders;
                    this.maritalStatuses = data.marital_statuses;
                    this.bloodGroups = data.blood_groups;
                    this.membershipTypes = data.membership_types;
                    this.sakhas = data.sakhas;
                    this.regCountries = data.countries;
                }
            } catch (err) {
                console.error("Failed to load reference data:", err);
            }
        },

        // ── Address cascade (shared utility) ────────────────────────────

        _locCascade: NSSLocation.create({
            fetchFn: fetch,
            basePath: '/api/v1/register',
            arrays: {
                countries: 'regCountries',
                states: 'regStates',
                districts: 'regDistricts',
                cities: 'regCities',
                postalCodes: 'regPostalCodes',
            },
            form: 'form',
        }),

        onRegCountryChange()     { this._locCascade.onCountryChange(this); this.onRegPostalCodeChange(); },
        onRegStateChange()       { this._locCascade.onStateChange(this); this.onRegPostalCodeChange(); },
        onRegDistrictChange()    { this._locCascade.onDistrictChange(this); },

        // When the registrant picks (or types an exact match of) a known
        // city/village, auto-fill the PIN from the city_village→postal_code
        // mapping. If the name isn't on file, or the matched record has no
        // mapped PIN, the field is left untouched for the user to type by
        // hand (mapping gap — common outside Odisha).
        onRegCityVillageChange() {
            const name = (this.form.city_village_name || "").trim().toLowerCase();
            if (!name) return;
            const match = this.regCities.find(
                cv => (cv.city_village_name || "").trim().toLowerCase() === name
            );
            if (match && match.postal_code) {
                this.form.postal_code_value = match.postal_code;
            }
            this.onRegPostalCodeChange();
        },

        // When the typed PIN exactly matches a known postal_code row,
        // resolve its postal_code_pk client-side (the submit payload still
        // sends postal_code_value as text — this is only to scope the Post
        // Office suggestions, which have no meaning without a real PIN).
        // No match (a brand-new PIN) just clears Post Office — it will be
        // created without one, same as resolve_or_create_postal_code()
        // creating the PIN itself on submit.
        onRegPostalCodeChange() {
            const code = (this.form.postal_code_value || "").trim();
            const match = code
                ? this.regPostalCodes.find(pc => (pc.postal_code || "").trim() === code)
                : null;
            this.regMatchedPostalCodePk = match ? match.postal_code_pk : "";
            this.form.post_office_name = "";
            this.loadRegPostOffices();
        },

        async loadRegPostOffices() {
            this.regPostOffices = [];
            if (!this.regMatchedPostalCodePk) return;
            this.regPostOfficesLoading = true;
            try {
                const res = await fetch(`/api/v1/register/post-offices?postal_code_pk=${this.regMatchedPostalCodePk}`);
                if (res.ok) this.regPostOffices = await res.json();
            } catch (_) {
                // Suggestions only — a failed fetch just leaves the Post
                // Office field as free text with no datalist options.
            } finally {
                this.regPostOfficesLoading = false;
            }
        },

        // "Find a Sakha near me" (SOL-ARCH-010 Amendment, revised 2026-10-04) —
        // the registrant's address must NEVER hide a Sakha. A Darshak attends
        // a Sakha outside their home district, and ~1/3 of Sakhas have no
        // backfilled district_pk and would vanish under a hard filter. So we
        // keep the FULL list (loaded once by reference-data) and only RE-ORDER
        // it: Sakhas in the selected district first, then the selected state,
        // then everyone else — all still present and selectable.
        get sakhasNearFirst() {
            const dpk = this.form.district_pk;
            const spk = this.form.state_pk;
            const rank = (s) => (dpk && s.district_pk === dpk) ? 0
                              : (spk && s.state_pk === spk) ? 1 : 2;
            return [...this.sakhas].sort(
                (a, b) => rank(a) - rank(b) ||
                    (a.organization_name || "").localeCompare(b.organization_name || "")
            );
        },

        // ── Title Case helper ─────────────────────────────────────────

        /**
         * Capitalize first letter of every word (Title Case).
         * Applied live on name fields for UX; also enforced server-side.
         */
        toTitleCase(str) {
            return str.replace(/\b\w/g, c => c.toUpperCase());
        },

        onNameInput(field) {
            this.form[field] = this.toTitleCase(this.form[field]);
        },

        // ── Computed helpers ──────────────────────────────────────────

        /**
         * Check if the selected membership type is PROBATIONARY (Darshaka).
         */
        isDarshaka() {
            if (!this.form.membership_type_master_data_pk) return false;
            const selected = this.membershipTypes.find(
                t => t.master_data_pk === this.form.membership_type_master_data_pk
            );
            return selected && selected.value_code === "PROBATIONARY";
        },

        /**
         * Get membership type display name for a given pk.
         */
        membershipTypeName(pk) {
            const t = this.membershipTypes.find(m => m.master_data_pk === pk);
            if (!t) return "";
            return t.value_code === "PROBATIONARY" ? "Darshaka" : t.value_name;
        },

        /**
         * The Darshaka (PROBATIONARY) membership type's master_data_pk —
         * used by the standalone Darshak flow to pre-lock Step 2's
         * Membership Type instead of asking the applicant to pick it.
         */
        darshakaTypePk() {
            const t = this.membershipTypes.find(m => m.value_code === "PROBATIONARY");
            return t ? t.master_data_pk : "";
        },

        // ── Standalone "Apply for Darshak" entry ────────────────────────
        // Branches on whether the applicant already has a Person ID:
        //   - Yes: reuse the existing lookupExisting() → POST /register/claim
        //     path (verifies Person ID + DOB, then applies at a Sakha).
        //   - No: reuse the normal Step 1 wizard → POST /register with
        //     has_membership=true (creates the person, then applies at a
        //     Sakha). Both branches lock Step 2's membership type to
        //     Darshaka — no new endpoint, no duplicated submit logic.

        goDarshakEntry() {
            this.error = "";
            this.step = "darshak-entry";
        },

        startDarshakExisting() {
            this.darshakFlow = true;
            this.goLookupExisting();
        },

        startDarshakNew() {
            this.darshakFlow = true;
            this.error = "";
            this.form.has_membership = true;
            this.step = 1;
        },

        // ── "Previously registered? Add membership" flow ────────────────
        // For a person who registered earlier with has_membership=false:
        // no account exists for them (user decision, 2026-10-06), so they
        // can't log in to add membership — this public lookup, keyed on
        // Person ID + DOB, re-identifies them and skips straight to the
        // membership step instead of re-asking for personal details.

        goLookupExisting() {
            this.error = "";
            this.lookup = { person_id: "", date_of_birth: "", loading: false };
            this.step = "lookup";
        },

        async lookupExisting() {
            this.error = "";
            this.lookup.loading = true;
            try {
                const res = await fetch("/api/v1/register/lookup-existing", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        person_id: this.lookup.person_id.trim(),
                        date_of_birth: this.lookup.date_of_birth,
                    }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    this.error = NSS.errorMessage(data, res.status);
                    return;
                }
                this.existingPerson = {
                    person_pk: data.person_pk,
                    person_id: data.person_id,
                    person_name: data.person_name,
                };
                this.mode = "existing";
                this.form.has_membership = true;
                if (this.darshakFlow) {
                    this.form.membership_type_master_data_pk = this.darshakaTypePk();
                }
                this.step = 2;
            } catch (err) {
                this.error = "Unable to connect to server. Please try again.";
            } finally {
                this.lookup.loading = false;
            }
        },

        // ── Step navigation with validation ────────────────────────

        async goStep2() {
            this.error = "";

            if (!this.form.first_name.trim()) {
                this.error = "First name is required.";
                return;
            }

            if (!this.form.last_name.trim()) {
                this.error = "Last name is required.";
                return;
            }

            if (!this.form.date_of_birth) {
                this.error = "Date of birth is required.";
                return;
            }

            if (!this.form.gender_master_data_pk) {
                this.error = "Gender is required.";
                return;
            }

            if (!this.form.mobile_number && !this.form.email) {
                this.error = "At least one of mobile number or email is required.";
                return;
            }

            // Validate mobile (country-wise) + email format — MBR-CONTACT-01/02.
            const mobileErr = NSS.validateMobile(this.form.country_phone_code, this.form.mobile_number);
            if (mobileErr) {
                this.error = mobileErr;
                return;
            }
            const emailErr = NSS.validateEmail(this.form.email);
            if (emailErr) {
                this.error = emailErr;
                return;
            }

            // ── Check for duplicate mobile/email before proceeding ────
            // POST with a JSON body, not GET with query params (2026-10-05) —
            // mobile number and email are PII and must not land in access logs.
            try {
                const body = {};
                if (this.form.mobile_number && this.form.country_phone_code) {
                    body.mobile_number = this.form.mobile_number;
                    body.country_phone_code = this.form.country_phone_code;
                }
                if (this.form.email) {
                    body.email = this.form.email.trim();
                }

                const res = await fetch("/api/v1/register/check-duplicate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
                if (res.ok) {
                    const data = await res.json();
                    const errors = [];
                    if (data.mobile_exists) {
                        errors.push("A person with this mobile number already exists.");
                    }
                    if (data.email_exists) {
                        errors.push("A person with this email already exists.");
                    }
                    if (errors.length > 0) {
                        this.error = errors.join(" ");
                        return;
                    }
                }
            } catch (_) {
                // Non-blocking — if the check fails, the backend will catch it on submit
            }

            if (this.darshakFlow) {
                this.form.membership_type_master_data_pk = this.darshakaTypePk();
            }
            this.step = 2;
        },

        goStep3() {
            this.error = "";

            if (this.form.has_membership) {
                if (!this.form.membership_type_master_data_pk) {
                    this.error = "Membership type is required.";
                    return;
                }
                if (!this.form.organization_pk) {
                    this.error = "Sakha selection is required.";
                    return;
                }

                // Local Sakha Number is required for every membership type,
                // including Darshaka (AUTH-BR-086) — Darshak members get a
                // number in a separate namespace, not no number at all.
                // Exception: the standalone Apply-for-Darshak flow never
                // shows this field — that number is system-generated at
                // admin approval, not self-reported by the applicant.
                if (!this.darshakFlow && !this.form.claimed_local_sakha_number.trim()) {
                    this.error = "Local Sakha Number is required.";
                    return;
                }

                // Parichaya Patra Number is mandatory for every membership
                // type except Darshaka — Darshak members hold an Anumati
                // Patra instead, which is issued later, not claimed here.
                if (!this.darshakFlow && !this.isDarshaka() && !this.form.claimed_credential_document_number.trim()) {
                    this.error = "Parichaya Patra Number is required.";
                    return;
                }

                // Darshak attendance: must have org + its own local number
                if (this.form.is_attending_as_darshak) {
                    if (!this.form.darshak_organization_pk) {
                        this.error = "Select the Sakha you are attending as Darshak.";
                        return;
                    }
                    if (!this.form.darshak_local_sakha_number.trim()) {
                        this.error = "Local Sakha Number at the Darshak Sakha is required.";
                        return;
                    }
                }
            }

            this.step = 3;
        },

        // ── Reset membership-dependent fields when type changes ────

        onMembershipTypeChange() {
            // Reset Local Sakha Number when switching types
            this.form.claimed_local_sakha_number = "";
            this.form.claimed_credential_document_number = "";
            // Reset darshak fields
            this.form.is_attending_as_darshak = false;
            this.form.darshak_organization_pk = "";
            this.form.darshak_local_sakha_number = "";
        },

        // ── Password validation ────────────────────────────────────

        isPasswordValid() {
            const pw = this.form.password;
            return (
                pw.length >= NSS.PASSWORD_MIN_LENGTH &&
                /[A-Z]/.test(pw) &&
                /\d/.test(pw) &&
                this.confirmPassword === pw
            );
        },

        // ── Submit registration ────────────────────────────────────

        async register() {
            if (this.mode === "existing") {
                return this.submitExistingClaim();
            }
            return this.submitNewRegistration();
        },

        // Previously-registered person adding membership — POST /register/claim.
        async submitExistingClaim() {
            this.error = "";

            if (!this.isPasswordValid()) {
                this.error = "Please fix password issues before submitting.";
                return;
            }

            this.loading = true;
            try {
                const payload = {
                    person_id: this.existingPerson.person_id,
                    date_of_birth: this.lookup.date_of_birth,
                    membership_type_master_data_pk: this.form.membership_type_master_data_pk,
                    organization_pk: this.form.organization_pk,
                    password: this.form.password,
                };
                if (this.form.joining_date) payload.joining_date = this.form.joining_date;
                if (this.form.claimed_local_sakha_number.trim()) {
                    payload.claimed_local_sakha_number = this.form.claimed_local_sakha_number.trim();
                }
                if (this.form.claimed_credential_document_number.trim()) {
                    payload.claimed_credential_document_number = this.form.claimed_credential_document_number.trim();
                }
                if (this.form.is_attending_as_darshak && this.form.darshak_organization_pk) {
                    payload.is_attending_as_darshak = true;
                    payload.darshak_organization_pk = this.form.darshak_organization_pk;
                    if (this.form.darshak_local_sakha_number.trim()) {
                        payload.darshak_local_sakha_number = this.form.darshak_local_sakha_number.trim();
                    }
                }

                const res = await fetch("/api/v1/register/claim", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.error = NSS.errorMessage(data, res.status);
                    return;
                }

                const data = await res.json();
                this.result = {
                    person_pk: data.person_pk,
                    person_id: data.person_id,
                    person_name: data.person_name,
                    message: data.message,
                };
                this.step = 4;
            } catch (err) {
                this.error = "Unable to connect to server. Please try again.";
            } finally {
                this.loading = false;
            }
        },

        async submitNewRegistration() {
            this.error = "";

            if (!this.isPasswordValid()) {
                this.error = "Please fix password issues before submitting.";
                return;
            }

            this.loading = true;

            try {
                // Build payload — only send non-empty optional fields
                const payload = {
                    first_name: this.form.first_name.trim(),
                    password: this.form.password,
                    has_membership: this.form.has_membership,
                };

                if (this.form.middle_name) payload.middle_name = this.form.middle_name.trim();
                if (this.form.last_name) payload.last_name = this.form.last_name.trim();
                if (this.form.date_of_birth) payload.date_of_birth = this.form.date_of_birth;
                if (this.form.gender_master_data_pk) payload.gender_master_data_pk = this.form.gender_master_data_pk;
                if (this.form.marital_status_master_data_pk) payload.marital_status_master_data_pk = this.form.marital_status_master_data_pk;
                if (this.form.blood_group_master_data_pk) payload.blood_group_master_data_pk = this.form.blood_group_master_data_pk;

                // Contact
                if (this.form.mobile_number) {
                    payload.country_phone_code = this.form.country_phone_code;
                    payload.mobile_number = this.form.mobile_number;
                }
                if (this.form.email) payload.email = this.form.email.trim();

                // Address — mandatory (MBR-030H-adjacent user decision, 2026-10-03):
                // country/state/district/city/PIN plus Address Line 1 are all
                // required at registration; goStep1Next()'s disabled-check on
                // the Next button already gates on these, but send them
                // unconditionally so the backend's own 422 is the single
                // source of truth if that gate is ever bypassed.
                payload.country_pk = this.form.country_pk;
                payload.state_pk = this.form.state_pk;
                payload.district_pk = this.form.district_pk;
                payload.city_village_name = this.form.city_village_name.trim();
                payload.postal_code_value = this.form.postal_code_value.trim();
                payload.address_line_1 = this.form.address_line_1.trim();
                if (this.form.address_line_2.trim()) payload.address_line_2 = this.form.address_line_2.trim();
                if (this.form.landmark.trim()) payload.landmark = this.form.landmark.trim();

                // Membership claim
                if (this.form.has_membership) {
                    payload.membership_type_master_data_pk = this.form.membership_type_master_data_pk;
                    payload.organization_pk = this.form.organization_pk;
                    if (this.form.joining_date) {
                        payload.joining_date = this.form.joining_date;
                    }

                    // Local Sakha Number (claim — not validated)
                    if (this.form.claimed_local_sakha_number.trim()) {
                        payload.claimed_local_sakha_number = this.form.claimed_local_sakha_number.trim();
                    }

                    // Existing Parichaya/Anumati Patra number, if already issued
                    if (this.form.claimed_credential_document_number.trim()) {
                        payload.claimed_credential_document_number = this.form.claimed_credential_document_number.trim();
                    }

                    // Darshak attendance
                    if (this.form.is_attending_as_darshak && this.form.darshak_organization_pk) {
                        payload.is_attending_as_darshak = true;
                        payload.darshak_organization_pk = this.form.darshak_organization_pk;
                        if (this.form.darshak_local_sakha_number.trim()) {
                            payload.darshak_local_sakha_number = this.form.darshak_local_sakha_number.trim();
                        }
                    }
                }

                const res = await fetch("/api/v1/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.error = NSS.errorMessage(data, res.status);
                    return;
                }

                const data = await res.json();
                this.result = {
                    person_pk: data.person_pk,
                    person_id: data.person_id,
                    person_name: data.person_name,
                    message: data.message,
                };
                this.step = 4;
                sessionStorage.removeItem("nss_register_draft");

            } catch (err) {
                this.error = "Unable to connect to server. Please try again.";
            } finally {
                this.loading = false;
            }
        },
    };
}
