/**
 * NSS ERP — Login Page (Tier 5)
 *
 * Alpine.js component for the login form.
 * Calls POST /api/v1/auth/login, stores JWT tokens,
 * handles force_password_change, password_expiry_warning,
 * and forgot-password / reset-password flows.
 */

function loginApp() {
    return {
        login_id: "",
        password: "",
        loading: false,
        error: "",

        // Force password change state
        showChangePassword: false,
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
        changeLoading: false,
        changeError: "",
        changeSuccess: "",

        // Forgot password state
        showForgotPassword: false,
        forgotLoginId: "",
        forgotLoading: false,
        forgotError: "",
        forgotSuccess: "",
        forgotMaskedContact: "",

        // Reset password (OTP) state
        showResetPassword: false,
        resetOtp: "",
        resetNewPassword: "",
        resetConfirmPassword: "",
        resetLoading: false,
        resetError: "",
        resetSuccess: "",

        // Debug OTP (development only — shown until email/SMS is integrated)
        debugOtp: "",

        init() {
            NSSAuth.redirectIfLoggedIn("/dashboard");
        },

        async login() {
            this.error = "";
            this.loading = true;

            try {
                const res = await fetch("/api/v1/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        login_id: this.login_id.trim(),
                        password: this.password,
                    }),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    if (res.status === 403) {
                        // PENDING_APPROVAL — show specific message
                        this.error = data.detail || "Your account is pending approval.";
                    } else {
                        this.error = NSS.errorMessage(data, res.status);
                    }
                    return;
                }

                const data = await res.json();

                // Store tokens
                NSSAuth.setTokens(data.access_token, data.refresh_token);

                // Check force_password_change
                if (data.force_password_change) {
                    this.currentPassword = this.password;
                    this.showChangePassword = true;
                    return;
                }

                // Password expiry warning
                if (data.password_expiry_warning) {
                    // Show warning but still proceed
                    const changeNow = await NSSDialog.confirm(
                        "Your password will expire soon. Would you like to change it now?",
                        { title: "Password Expiry", confirmText: "Change Now", cancelText: "Skip" }
                    );
                    if (!changeNow) {
                        window.location.href = "/dashboard";
                        return;
                    }
                    this.currentPassword = this.password;
                    this.showChangePassword = true;
                    return;
                }

                // All clear — redirect to dashboard
                window.location.href = "/dashboard";

            } catch (err) {
                this.error = "Unable to connect to server.";
            } finally {
                this.loading = false;
            }
        },

        async changePassword() {
            this.changeError = "";
            this.changeSuccess = "";

            if (this.newPassword !== this.confirmPassword) {
                this.changeError = "Passwords do not match.";
                return;
            }

            if (this.newPassword.length < NSS.PASSWORD_MIN_LENGTH) {
                this.changeError = `Password must be at least ${NSS.PASSWORD_MIN_LENGTH} characters.`;
                return;
            }

            this.changeLoading = true;

            try {
                const res = await NSSAuth.apiFetch("/api/v1/auth/change-password", {
                    method: "POST",
                    body: JSON.stringify({
                        current_password: this.currentPassword,
                        new_password: this.newPassword,
                    }),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.changeError = NSS.errorMessage(data, res.status);
                    return;
                }

                this.changeSuccess = "Password changed. Redirecting...";
                setTimeout(() => {
                    window.location.href = "/dashboard";
                }, 1500);

            } catch (err) {
                this.changeError = err.message || "Failed to change password.";
            } finally {
                this.changeLoading = false;
            }
        },

        // ── Forgot Password ──────────────────────────────────

        openForgotPassword() {
            this.showForgotPassword = true;
            this.forgotLoginId = this.login_id || "";
            this.forgotError = "";
            this.forgotSuccess = "";
            this.forgotMaskedContact = "";
            this.debugOtp = "";
        },

        backToLogin() {
            this.showForgotPassword = false;
            this.showResetPassword = false;
            this.forgotError = "";
            this.forgotSuccess = "";
            this.resetError = "";
            this.resetSuccess = "";
            this.debugOtp = "";
        },

        async submitForgotPassword() {
            this.forgotError = "";
            this.forgotSuccess = "";
            this.debugOtp = "";
            this.forgotLoading = true;

            try {
                const res = await fetch("/api/v1/auth/forgot-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        login_id: this.forgotLoginId.trim(),
                    }),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.forgotError = NSS.errorMessage(data, res.status);
                    return;
                }

                const data = await res.json();
                this.forgotSuccess = data.message;
                this.forgotMaskedContact = data.masked_contact || "";

                // Development: show OTP directly
                if (data.otp_debug) {
                    this.debugOtp = data.otp_debug;
                }

                // Auto-navigate to reset step
                this.showForgotPassword = false;
                this.showResetPassword = true;
                this.resetOtp = "";
                this.resetNewPassword = "";
                this.resetConfirmPassword = "";
                this.resetError = "";
                this.resetSuccess = "";

            } catch (err) {
                this.forgotError = "Unable to connect to server.";
            } finally {
                this.forgotLoading = false;
            }
        },

        // ── Reset Password (with OTP) ────────────────────────

        async submitResetPassword() {
            this.resetError = "";
            this.resetSuccess = "";

            if (this.resetNewPassword !== this.resetConfirmPassword) {
                this.resetError = "Passwords do not match.";
                return;
            }

            if (this.resetNewPassword.length < NSS.PASSWORD_MIN_LENGTH) {
                this.resetError = `Password must be at least ${NSS.PASSWORD_MIN_LENGTH} characters.`;
                return;
            }

            this.resetLoading = true;

            try {
                const res = await fetch("/api/v1/auth/reset-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        login_id: this.forgotLoginId.trim(),
                        otp: this.resetOtp.trim(),
                        new_password: this.resetNewPassword,
                    }),
                });

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    this.resetError = NSS.errorMessage(data, res.status);
                    return;
                }

                this.resetSuccess = "Password reset successfully. Redirecting to login...";
                this.debugOtp = "";
                setTimeout(() => {
                    this.backToLogin();
                }, 2000);

            } catch (err) {
                this.resetError = "Unable to connect to server.";
            } finally {
                this.resetLoading = false;
            }
        },

        handleKeydown(event) {
            if (event.key === "Enter") {
                if (this.showResetPassword) {
                    this.submitResetPassword();
                } else if (this.showForgotPassword) {
                    this.submitForgotPassword();
                } else if (!this.showChangePassword) {
                    this.login();
                }
            }
        },
    };
}
