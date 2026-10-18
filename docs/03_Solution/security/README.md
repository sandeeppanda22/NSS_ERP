# docs/03_Solution/security/

Solution-level security architecture and audit documentation, building on
`docs/00_Project_Governance/STD/05_security_standards.md` (RBAC, Row Level Security, auth
model).

## Files

- **`SECURITY_ARCHITECTURE.md`** — Cross-reference map of security ownership: STD-05 (policy),
  Authentication (identity), Administration (RBAC), Audit (logging), per-module business rules.
  Establishes authoritative-document routing without duplicating existing rules.
- **`TIER0_SECURITY_AUDIT.md`** (v1.1, Complete) — security audit scoped to all Tier 0 code.
  10 checks passed; 1 fix applied (ConfigDict removal); 6 advisory items (4 resolved, 1 partial,
  1 N/A). No blocking vulnerabilities found.
- **`TIER1_SECURITY_AUDIT.md`** (v1.1, Complete) — security audit scoped to all Tier 1 code.
  9 checks passed; 6 advisory items (3 resolved, 1 partial, 1 advisory, 1 N/A).
  No blocking vulnerabilities found.
- **`TIER2_SECURITY_AUDIT.md`** (v1.1, Complete) — security audit scoped to all Tier 2 code.
  15 checks passed; 0 fixes required; 4 advisory items (pagination, CTE depth, filter logging,
  helper duplication). No blocking vulnerabilities found.
- **`TIER3_SECURITY_AUDIT.md`** (v1.1, Complete) — security audit scoped to all Tier 3 (Person)
  code. 18 checks passed; 0 fixes required; 3 of 5 advisory items resolved (pagination, search
  limit, helper deduplication), 2 awareness-only items retained (Aadhaar key management deferred
  to Tier 5+, filter value logging). No blocking vulnerabilities found — confirms defence-in-depth
  for Aadhaar (encrypted at rest, never selected by the API, never modelled in Pydantic, never
  rendered in the UI).
- **`TIER4_SECURITY_AUDIT.md`** (v1.0, Complete) — security audit scoped to all Tier 4
  (Family + Membership) code: 4 GET endpoints over 3 Family tables, 7 GET endpoints over 5
  Membership tables, plus the Family/Membership DDL (4 + 12 tables), routers, schemas, and
  frontend. 21 checks passed; 0 fixes required; 2 advisory items (filter/search-term query
  logging, contact fields returned in member list/search — both flagged for RBAC gating at
  Tier 5). No blocking vulnerabilities found.
- **`TIER5_SECURITY_AUDIT.md`** (v1.2, Complete) — security audit scoped to all Tier 5
  (Authentication + Administration + Audit) code: the auth surface (login/refresh/logout/
  change-/forgot-/reset-password/me/profile), the RBAC enforcement layer
  (`require_permission`/`require_any_permission`), the permission-gated Administration API, and
  the new `AUDIT_VIEW`-gated audit-trail viewer (`GET /api/v1/audit/change-log`). 21 checks
  passed; 0 fixes required. The 5 advisory items were then worked (v1.2): **A2 Content-Security-Policy
  implemented** — an enforced, measured CSP whose `script-src` omits `'unsafe-inline'`, which
  required replacing all 7 inline event handlers with CSS state selectors and one delegated
  listener (residual `'unsafe-eval'` for Alpine and `style-src 'unsafe-inline'` tracked as
  follow-ups); **A3 filter-value logging closed as a verified no-op** — the inherited finding is
  contradicted by the only two logging call sites in `api/`; **A5 OTP debug echo mitigated** —
  startup now warns when `DEBUG_MODE` is enabled; **A4 token revocation on logout resolved
  (2026-10-05)** — a stateful session table, `nss.user_session`, was chosen over the stateless
  `credentials_changed_at` watermark alternative specifically because a "logged-in devices" UI
  was required, which only the stateful design supports. One item remains **OPEN** by design,
  needing a decision rather than a patch: **A1** contact-field gating (resolution path fixed as
  page retirement once the Dashboard reaches feature parity per Tier 1–4 page). No blocking
  vulnerabilities found. This tier discharges the "deferred to Tier 5"
  advisories carried by the Tier 0–4 audits (auth, RBAC enforcement, CSP) or re-tracks them
  explicitly.
- **`SECURITY_AUDIT_TIER0_4.md`** (`SOL-SEC-002`, v1.0.0) — aggregate cross-tier summary across
  Tiers 0–4: implemented controls (security headers, cache control, rate limiting, CORS,
  database access control, sensitive-data protection, input validation, docs toggle),
  intentionally deferred controls (auth, RBAC enforcement, HSTS, CSP, RLS, sessions, MFA — all
  Tier 5+; the auth, RBAC and CSP rows have since been delivered in Tier 5 and are annotated in
  place), and a table of potential improvements. Consolidates, rather than replaces, the
  per-tier audits above.

**Tier 6 (Governance, in progress/uncommitted) has not been audited yet** — there is no
`TIER6_SECURITY_AUDIT.md`; the new `governance.py` (46 endpoints) and
`membership_change_request.py` (5 endpoints) routers, the ballot-immutability triggers and the
secret-ballot split (`election_vote` / `election_vote_participation`) are outside the audits above.

See `docs/03_Solution/code_explanations/` for line-by-line code walkthroughs of the same
endpoints/files (a different concern from the audit findings recorded here), and
`docs/03_Solution/api/` for the formal API contracts.
