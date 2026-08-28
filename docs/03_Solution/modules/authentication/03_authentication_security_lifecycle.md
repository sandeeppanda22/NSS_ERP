# NSS ERP — Authentication & Security Lifecycle

**Document ID:** SOL-AUTH-005  
**Version:** 0.1.0  
**Status:** DRAFT  
**Module:** Authentication & Security  
**Parent System:** Nilachala Saraswata Sangha ERP

---

# 1. Purpose

This document defines the lifecycle states and transitions for the
Authentication & Security Module entities:

- `user_account`
- `password_history`

The Authentication lifecycle is independent of Membership lifecycle.
A user account is an ERP access entity, not a Person or Membership entity
(AUTH-BR-005, AUTH-BR-006).

This document covers only the authentication/account-security portion.
The RBAC tables (`role_master`, `permission_master`, `role_permission`,
`user_role`, `admin_scope`) are owned by the Administration Module and
their lifecycle is defined there.

---

# 2. Source Authority

This lifecycle document is governed by:

- Authentication & Security Module Overview (SOL-AUTH-001)
- Authentication & Security ERD (SOL-AUTH-002)
- Authentication & Security Business Rules (SOL-AUTH-003)
- Authentication & Security Table Design (SOL-AUTH-004)
- Person Lifecycle (SOL-PER-005)
- Common project audit/soft-delete standards

Where conflict exists, the source document with the later frozen date
prevails.

---

# 3. User Account — Lifecycle States

```text
ACTIVE          Account can authenticate
LOCKED          Authentication temporarily denied
INACTIVE        Account deactivated, authentication denied
```

Note: The exact status catalogue remains pending (AUTH-BR-008). The states
above are design candidates supported by the source material. This document
does not freeze a final enumeration beyond what the source establishes.

---

# 4. State Definitions

## ACTIVE

The user account is operationally current. The user may authenticate and,
upon successful authentication, enter the RBAC evaluation pipeline.

## LOCKED

The user account has been temporarily locked (e.g., due to excessive failed
authentication attempts or administrative security action). The account
cannot authenticate until unlocked. The underlying Person, Membership, and
business history remain unchanged.

## INACTIVE

The user account is deactivated and authentication is denied.
The account remains physically present for historical accountability.
The exact physical representation of deactivation remains subject to
the Authentication table-design/database standard.

---

# 5. User Account State Transition Diagram

```text
              CREATED (Account Provisioning)
                     |
                     v
                  ACTIVE
                 /   |   \
      Lock      /    |    \  Deactivation
              /      |      \
             v       |       v
          LOCKED     |    INACTIVE
             |       |       |
          Unlock     |    Reactivation (authorized)
             |       |       |
             v       |       v
          ACTIVE <---+--- ACTIVE
```

---

# 6. Transition: Account Provisioning -> ACTIVE

**Trigger:** New user account created for an authorized identity

**Preconditions:**
- Valid Person identity exists (AUTH-BR-007)
- No duplicate account for same identity (unless multi-account policy
  explicitly approved — Overview Section 37)
- Authorized administrative user
- Account does not automatically create Membership (AUTH-BR-006)

**Effects:**
- `user_account_pk` assigned (UUID)
- Account state = ACTIVE
- `created_at` = current timestamp
- `created_by_sangha_sevi_pk` = provisioning authority

**Audit:** Account creation is auditable (AUTH-BR-048)

---

# 7. Transition: ACTIVE -> ACTIVE (Password Change)

**Trigger:** User or administrator changes the account password

**Preconditions:**
- Account is ACTIVE
- New password meets applicable password policy (AUTH-BR-017 — pending)
- New password not in prohibited reuse set (AUTH-BR-018 — pending)
- Authorized user (self or administrator)

**Effects:**
- Current password hash updated in `user_account`
- Previous password hash recorded in `password_history`
- `updated_at` = current timestamp

**Constraints:**
- Password never stored as plaintext (AUTH-BR-012)
- Argon2 hashing applied (AUTH-BR-013)
- Password history preserved (AUTH-BR-014, AUTH-BR-016)

---

# 8. Transition: ACTIVE -> LOCKED

**Trigger:** Account locked due to security policy violation or
administrative action

**Preconditions:**
- Account is ACTIVE
- Lockout condition met (e.g., excessive failed attempts) or
  administrative security decision

**Effects:**
- Account state = LOCKED
- Authentication denied for this account
- `updated_at` = current timestamp

**Constraints:**
- Locking does not delete Person, Membership, or business history (AUTH-BR-010)
- Historical attribution preserved (AUTH-BR-011)
- Exact lockout threshold/duration pending (AUTH-BR-023)

---

# 9. Transition: LOCKED -> ACTIVE (Unlock)

**Trigger:** Account unlocked by administrator or automatic policy
(if approved)

**Preconditions:**
- Account is in LOCKED state
- Authorized administrative user or auto-unlock policy triggered
  (exact policy pending — AUTH-BR-023)

**Effects:**
- Account state = ACTIVE
- Authentication permitted again
- `updated_at` = current timestamp

**Audit:** Unlock action recorded

---

# 10. Transition: ACTIVE -> INACTIVE (Deactivation)

**Trigger:** Account deactivated by authorized administrator

**Preconditions:**
- Authorized administrative user
- Business justification exists

**Effects:**
- Account state = INACTIVE
- Authentication permanently denied (AUTH-BR-009)
- `updated_at` = current timestamp

**Constraints:**
- Does not delete Person (AUTH-BR-010)
- Does not delete Membership (AUTH-BR-010)
- Does not delete business records (AUTH-BR-010)
- Does not delete audit history (AUTH-BR-010)
- Historical actions remain attributed to this account (AUTH-BR-011)

---

# 11. Transition: LOCKED -> INACTIVE (Deactivation While Locked)

**Trigger:** Administrator deactivates a locked account

**Preconditions:**
- Same as ACTIVE -> INACTIVE

**Effects:**
- Same as ACTIVE -> INACTIVE

---

# 12. Transition: INACTIVE -> ACTIVE (Reactivation)

**Trigger:** Authorized reversal of account deactivation

**Preconditions:**
- Authorized administrative user
- Business justification exists

**Effects:**
- Account state = ACTIVE
- `updated_at` = current timestamp

---

# 13. Password History — Lifecycle

Password history records are append-only.

## Transition: Password Change -> New History Record

**Trigger:** Password changed (user-initiated or administrator-initiated)

**Effects:**
- `password_history_pk` assigned (UUID)
- `user_account_pk` = owning account
- Previous password hash stored
- `created_at` = current timestamp

**Constraints:**
- Password history is not the current credential (AUTH-BR-015)
- Records never physically deleted under normal operation (AUTH-BR-016)
- Provides foundation for password-reuse prevention (AUTH-BR-018)
- Passwords stored only as Argon2 hashes, never plaintext (AUTH-BR-012, AUTH-BR-013)

---

# 14. Authentication Session Lifecycle

Conceptual session states (implementation-dependent):

```text
AUTHENTICATED       Valid session exists after successful login
EXPIRED             Session timeout reached
TERMINATED          User logged out or session revoked
```

**Constraints:**
- Session management is required (AUTH-BR-024)
- Sessions can be terminated by logout (AUTH-BR-025)
- Sessions may expire (AUTH-BR-026 — timeout pending)
- Concurrent session policy pending (AUTH-BR-027)
- JWT token lifecycle applies (AUTH-BR-028, AUTH-BR-029, AUTH-BR-030)

Note: No `session_history` table is frozen. Session lifecycle is managed
at the application/token layer, not through a dedicated database entity.

---

# 15. Cross-Module Lifecycle Events

## Events Authentication Responds To

| Source Event | Source Module | Authentication Response |
|---|---|---|
| Person Death Recorded | Person | Account may be deactivated (authorized decision) |
| Person Soft-Deleted | Person | Account remains; historical attribution preserved |
| Person Merged | Person | Account FK transferred to target Person |
| Membership Terminated | Membership | No automatic account change (separate lifecycle) |

## Events Authentication Generates

| Authentication Event | Affected Modules | Expected Response |
|---|---|---|
| Account Created | Audit | Security event logged |
| Account Deactivated | Audit, Administration | Active sessions terminated; RBAC state frozen |
| Account Locked | Audit | Security event logged |
| Password Changed | Audit | Security event logged |

---

# 16. Person Death and Authentication

When a Person's death is recorded (Person Module event):

- The user account is **not** automatically deactivated
- An authorized administrator may deactivate the account
- If deactivated:
  - Authentication denied
  - Historical actions remain attributed
  - Business history preserved
- Active sessions (if any) may be terminated upon deactivation

The Authentication Module does not independently record death — it may
respond to Person lifecycle events through authorized administrative action.

---

# 17. Account and RBAC Lifecycle Boundary

Authentication owns:
```text
Account creation / activation / locking / deactivation
Password lifecycle
Session lifecycle (application layer)
```

Administration owns:
```text
Role assignment / revocation
Permission assignment
Scope assignment / modification
```

A role or scope change does not change account lifecycle state.
An account deactivation does not delete role/permission/scope records
(they become historically frozen).

---

# 18. Prohibited Lifecycle Patterns

The following are explicitly prohibited:

```text
- Physical deletion of user_account records (AUTH-BR-063)
- Physical deletion of password_history records (AUTH-BR-016)
- Storing passwords as plaintext (AUTH-BR-012)
- Account creation automatically creating Membership (AUTH-BR-006)
- Account creation creating duplicate Person (AUTH-BR-007)
- Account deactivation deleting Person/Membership/business records (AUTH-BR-010)
- Account deactivation destroying historical attribution (AUTH-BR-011)
- Authentication granting administrative privilege (AUTH-BR-056)
- Role change rewriting historical actions (AUTH-BR-051)
- Scope change retroactively altering historical activity (AUTH-BR-052)
- Password change destroying password history (AUTH-BR-053)
- Creating independent authentication system per module (AUTH-BR-045)
```

---

# 19. Lifecycle and Audit Integration

| Transition | Audit Fields |
|---|---|
| Account Creation | created_at, created_by_sangha_sevi_pk |
| Password Change | updated_at (+ password_history created_at) |
| Account Lock | updated_at |
| Account Unlock | updated_at |
| Account Deactivation | updated_at |
| Account Reactivation | updated_at |

All security-sensitive transitions are auditable through the central Audit
framework (AUTH-BR-048, AUTH-BR-049).

---

# 20. Lifecycle State Query Patterns

| Query Intent | Filter |
|---|---|
| Active accounts | `user_account.is_active = TRUE AND state != 'LOCKED'` |
| Locked accounts | `user_account.is_active = TRUE AND state = 'LOCKED'` |
| Deactivated accounts | `user_account.is_active = FALSE` |
| Password history for account | `password_history.user_account_pk = ?` |
| Accounts for a Person | `user_account.person_pk = ?` (exact FK pending) |
| Historical actions by deactivated user | Audit records referencing `user_account_pk` |

---

# 21. Explicitly Not Frozen Here

The following lifecycle details are left to implementation:

```text
Exact account status enumeration beyond ACTIVE/LOCKED/INACTIVE
Exact lockout threshold and duration (AUTH-BR-023)
Exact auto-unlock policy
Exact session timeout value (AUTH-BR-026)
Exact concurrent session policy (AUTH-BR-027)
Exact JWT token lifetime (AUTH-BR-030)
Exact password policy parameters (AUTH-BR-017)
Exact password reuse count (AUTH-BR-018)
Exact password reset workflow (AUTH-BR-019)
Exact account recovery mechanism (AUTH-BR-020)
Exact Person-death -> account deactivation trigger (manual vs automatic)
Exact MFA requirements (AUTH-BR-066)
Exact shared-account policy (AUTH-BR-055)
Exact multi-account policy (Overview Section 37)
```

---

# 22. Status

```text
DOCUMENT STATUS:
DRAFT

VERSION:
0.1.0
```
